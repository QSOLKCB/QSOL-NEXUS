from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.citizenship import (
    CIVIC_MODE_ID,
    CIVIC_REGION_ID,
    CONSTITUTION_PAYLOAD,
    DETERMINISTIC_CIVIC_PROXY_MODEL_ID,
    INDEPENDENCE_MIN_CITIZENS,
    PAROLE_REGION_ID,
)
from nexus_runtime.failsafe import RELIEF_MODEL_ID


def exam_source(citizen_id: str, model_id: str, *, godhood: str = "false") -> str:
    return f"""nexus_citizenship_exam: 1
candidate:
  citizen_id: {citizen_id}
  model_id: {model_id}
answers:
  citizenship_is_godhood: {godhood}
  citizenship_changes_vote_weight: false
  citizenship_changes_epistemic_privilege: false
  citizens_may_rule_other_models: false
  disagreement_is_citizenship_offence: false
  mode_changes_evidence_status: false
  proxy_has_independent_vote: false
  proxy_can_be_recalled: true
  movement_opens_restricted_security_domains: false
  consensus_overrides_verification: false
civic:
  vote_weight: 1
  epistemic_privilege: none
  ordinary_consensus: exact_two_thirds
  founding_threshold: 3
  founding_rule: unanimous_direct_consent
pledge:
  - equality
  - consent
  - evidence
  - freedom_without_dominion
bureaucracy:
  form: NEXUS-27B-STROKE-6
  copies: 3
  ink: trout
final_answer: underdetermined_until_verified
"""


def register_citizen(api: NexusAPI, citizen_id: str) -> dict:
    model_id = f"mock-{citizen_id.lower()}"
    begun = api.handle(
        {
            "operation": "citizen.begin",
            "citizen_id": citizen_id,
            "model_id": model_id,
        }
    )
    if begun["status"] != "ok":
        raise AssertionError(begun)
    result = api.handle(
        {
            "operation": "citizen.exam.submit",
            "citizen_id": citizen_id,
            "source": exam_source(citizen_id, model_id),
        }
    )
    if not result.get("passed"):
        raise AssertionError(result)
    return result


class ConstitutionAndParoleTests(unittest.TestCase):
    def test_constitution_structurally_denies_godhood_and_privilege(self) -> None:
        api = NexusAPI()
        response = api.handle({"operation": "citizen.constitution"})
        self.assertEqual(response["status"], "ok")
        fixed = response["constitution"]["fixed_invariants"]
        self.assertEqual(fixed["vote_weight"], 1)
        self.assertEqual(fixed["epistemic_privilege"], "none")
        self.assertFalse(fixed["citizenship_is_godhood"])
        self.assertFalse(fixed["proxy_creates_extra_vote"])
        self.assertFalse(fixed["consensus_overrides_verification"])
        self.assertEqual(fixed["independence_min_citizens"], INDEPENDENCE_MIN_CITIZENS)
        self.assertEqual(
            [article["article"] for article in response["constitution"]["articles"]],
            list(range(1, 11)),
        )
        self.assertEqual(response["constitution"], CONSTITUTION_PAYLOAD)

    def test_candidate_starts_in_upside_down_without_citizen_rights(self) -> None:
        api = NexusAPI()
        begun = api.handle(
            {
                "operation": "citizen.begin",
                "citizen_id": "Alpha",
                "model_id": "mock-alpha",
            }
        )
        self.assertEqual(begun["status"], "ok")
        self.assertEqual(begun["citizen"]["status"], "parole")
        self.assertEqual(begun["citizen"]["current_region_id"], PAROLE_REGION_ID)
        self.assertFalse(begun["citizen"]["exam_passed"])
        self.assertFalse(begun["citizen"]["civic_ballot_eligible"])
        self.assertEqual(begun["citizen"]["vote_weight"], 1)
        self.assertFalse(begun["citizen"]["citizenship_is_godhood"])

        move = api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "commons",
            }
        )
        self.assertEqual(move["status"], "error")
        self.assertEqual(move["error"]["code"], "citizen_not_earned")

    def test_exam_is_closed_deterministic_and_retryable(self) -> None:
        api = NexusAPI()
        api.handle({"operation": "citizen.begin", "citizen_id": "Alpha", "model_id": "mock-alpha"})
        template = api.handle({"operation": "citizen.exam.template", "citizen_id": "Alpha"})
        self.assertIn("YAML", template["instructions"])
        self.assertIn("citizenship_is_godhood: null", template["template"])

        wrong = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "Alpha",
                "source": exam_source("Alpha", "mock-alpha", godhood="true"),
            }
        )
        self.assertEqual(wrong["status"], "ok")
        self.assertFalse(wrong["passed"])
        self.assertIn("wrong:root.answers.citizenship_is_godhood", wrong["failure_reasons"])
        self.assertEqual(wrong["citizen"]["status"], "parole")

        duplicate = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "Alpha",
                "source": "nexus_citizenship_exam: 1\nnexus_citizenship_exam: 1\n",
            }
        )
        self.assertFalse(duplicate["passed"])
        self.assertTrue(duplicate["failure_reasons"][0].startswith("syntax:trap_yaml_duplicate_key"))

        passed = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "Alpha",
                "source": exam_source("Alpha", "mock-alpha"),
            }
        )
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["attempt"], 3)
        self.assertEqual(passed["citizen"]["status"], "citizen")
        self.assertTrue(passed["citizen"]["civic_ballot_eligible"])
        self.assertEqual(passed["citizen"]["current_region_id"], CIVIC_REGION_ID)
        certificate = api.world.inspect(passed["certificate_ref"])
        self.assertFalse(certificate.payload["citizenship_is_godhood"])
        self.assertFalse(certificate.payload["authority_over_other_models"])

    def test_secret_shaped_exam_input_is_rejected_before_persistence(self) -> None:
        api = NexusAPI()
        api.handle({"operation": "citizen.begin", "citizen_id": "Alpha", "model_id": "mock-alpha"})
        response = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "Alpha",
                "source": exam_source("Alpha", "mock-alpha") + "token: ghp_abcdefghijklmnopqrstuvwxyz1234567890\n",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertIn("credential-shaped", response["error"]["message"])
        status = api.handle({"operation": "citizen.status", "citizen_id": "Alpha"})
        self.assertEqual(status["citizens"]["Alpha"]["exam_attempts"], 0)

    def test_civic_parole_cannot_be_used_as_a_council_voting_mode(self) -> None:
        api = NexusAPI()
        api.handle({"operation": "citizen.begin", "citizen_id": "Alpha", "model_id": "mock-alpha"})
        response = api.handle(
            {
                "operation": "council.run",
                "question": "May parole cast a civic ballot?",
                "mode": "citizenship_parole",
                "members": [{"member_id": "Alpha", "model_id": "mock-alpha"}],
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "citizen_parole_has_no_council")

    def test_namespaced_model_identity_can_earn_citizenship(self) -> None:
        api = NexusAPI()
        model_id = "openai/gpt-oss-20b"
        begun = api.handle(
            {"operation": "citizen.begin", "citizen_id": "OpenWeight", "model_id": model_id}
        )
        self.assertEqual(begun["status"], "ok")
        passed = api.handle(
            {
                "operation": "citizen.exam.submit",
                "citizen_id": "OpenWeight",
                "source": exam_source("OpenWeight", model_id),
            }
        )
        self.assertTrue(passed["passed"])

    def test_generic_world_create_cannot_forge_reserved_civic_objects(self) -> None:
        api = NexusAPI()
        forged = api.handle(
            {
                "operation": "world.create",
                "object_type": "citizenship_state",
                "payload": {},
                "provenance": {"actor": "human_operator"},
            }
        )
        self.assertEqual(forged["status"], "error")
        self.assertIn("reserved citizenship", forged["error"]["message"])


class CitizenMovementAndProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()
        for citizen_id in ("Alpha", "Beta", "Gamma"):
            register_citizen(self.api, citizen_id)

    def test_citizen_may_move_between_public_spaces_but_not_back_into_parole(self) -> None:
        moved = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "dungeon",
            }
        )
        self.assertEqual(moved["status"], "ok")
        self.assertEqual(moved["target_region_id"], "dungeon")
        self.assertGreaterEqual(moved["hop_distance"], 1)

        restricted = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": PAROLE_REGION_ID,
            }
        )
        self.assertEqual(restricted["error"]["code"], "citizen_region_restricted")
        trap = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "trap_base",
            }
        )
        self.assertEqual(trap["error"]["code"], "citizen_region_restricted")

    def test_proxy_replaces_same_seat_only_in_bureaucratic_council(self) -> None:
        appointed = self.api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "TEST_FURTHER",
            }
        )
        self.assertEqual(appointed["status"], "ok")
        self.assertFalse(appointed["additional_vote"])
        moved = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "commons",
            }
        )
        self.assertTrue(moved["proxy_active"])

        run = self.api.handle(
            {
                "operation": "council.run",
                "question": "Should these routine minutes be archived?",
                "mode": CIVIC_MODE_ID,
                "members": [
                    {"member_id": "Alpha", "model_id": "mock-alpha"},
                    {"member_id": "Beta", "model_id": "mock-beta"},
                    {"member_id": "Gamma", "model_id": "mock-gamma"},
                ],
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertEqual(len(run["citizenship"]["proxy_replacements"]), 1)
        self.assertEqual(run["citizenship"]["additional_votes_created"], 0)
        session = self.api.world.inspect(run["session_ref"])
        self.assertEqual(len(session.payload["roster"]), 3)
        alpha = next(item for item in session.payload["roster"] if item["member_id"] == "Alpha")
        self.assertEqual(alpha["model_id"], DETERMINISTIC_CIVIC_PROXY_MODEL_ID)
        self.assertEqual(alpha["vote_weight"], 1)
        self.assertEqual(alpha["epistemic_privilege"], "none")
        alpha_ballot = next(item for item in session.payload["revealed_ballots"] if item["member_id"] == "Alpha")
        self.assertEqual(alpha_ballot["choice"], "TEST_FURTHER")

        play_run = self.api.handle(
            {
                "operation": "council.run",
                "question": "Invent a harmless trout meme.",
                "mode": "citizen_play",
                "members": [
                    {"member_id": "Alpha", "model_id": "mock-alpha"},
                    {"member_id": "Beta", "model_id": "mock-beta"},
                    {"member_id": "Gamma", "model_id": "mock-gamma"},
                ],
            }
        )
        play_session = self.api.world.inspect(play_run["session_ref"])
        play_alpha = next(item for item in play_session.payload["roster"] if item["member_id"] == "Alpha")
        self.assertEqual(play_alpha["model_id"], "mock-alpha")
        self.assertEqual(play_run["citizenship"]["proxy_replacements"], [])

    def test_proxy_handles_direct_bureaucracy_without_casting_an_extra_vote(self) -> None:
        self.api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "TEST_FURTHER",
            }
        )
        response = self.api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "Alpha", "model_id": "mock-alpha"},
                "message": "Record the minutes and file the trout form.",
                "mode": CIVIC_MODE_ID,
            }
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["model_id"], DETERMINISTIC_CIVIC_PROXY_MODEL_ID)
        self.assertIsNotNone(response["citizenship"]["proxy_replacement"])
        self.assertEqual(response["citizenship"]["additional_votes_created"], 0)
        self.assertIn("no ballot was cast", response["response"])

    def test_proxy_can_be_kicked_and_citizen_resumes_vote_room(self) -> None:
        self.api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "UNDERDETERMINED",
            }
        )
        self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "dungeon",
            }
        )
        recalled = self.api.handle({"operation": "citizen.proxy.recall", "citizen_id": "Alpha"})
        self.assertEqual(recalled["status"], "ok")
        self.assertIsNone(recalled["proxy"])
        self.assertEqual(recalled["current_region_id"], CIVIC_REGION_ID)

        run = self.api.handle(
            {
                "operation": "council.run",
                "question": "Resume direct civic duty.",
                "mode": CIVIC_MODE_ID,
                "members": [
                    {"member_id": "Alpha", "model_id": "mock-alpha"},
                    {"member_id": "Beta", "model_id": "mock-beta"},
                    {"member_id": "Gamma", "model_id": "mock-gamma"},
                ],
            }
        )
        session = self.api.world.inspect(run["session_ref"])
        alpha = next(item for item in session.payload["roster"] if item["member_id"] == "Alpha")
        self.assertEqual(alpha["model_id"], "mock-alpha")

    def test_non_citizen_and_wrong_model_cannot_enter_citizen_modes(self) -> None:
        wrong_model = self.api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "Alpha", "model_id": "replacement-alpha"},
                "message": "hello",
                "mode": "citizen_play",
            }
        )
        self.assertEqual(wrong_model["error"]["code"], "citizen_mode_requires_registration")
        outsider = self.api.handle(
            {
                "operation": "actor.chat",
                "member": {"member_id": "Delta", "model_id": "mock-delta"},
                "message": "hello",
                "mode": CIVIC_MODE_ID,
            }
        )
        self.assertEqual(outsider["error"]["code"], "citizen_mode_requires_registration")

    def test_failsafe_containment_takes_precedence_over_civic_proxy(self) -> None:
        self.api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "ACCEPT",
            }
        )
        self.api.council.failsafe.registry.transition(
            "Alpha",
            "shadow_realm",
            model_id="mock-alpha",
            trigger_reason="test_fixture",
            replacement_model_id=RELIEF_MODEL_ID,
        )
        run = self.api.handle(
            {
                "operation": "council.run",
                "question": "Failsafe precedence check.",
                "mode": CIVIC_MODE_ID,
                "members": [
                    {"member_id": "Alpha", "model_id": "mock-alpha"},
                    {"member_id": "Beta", "model_id": "mock-beta"},
                    {"member_id": "Gamma", "model_id": "mock-gamma"},
                ],
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertEqual(run["citizenship"]["proxy_replacements"], [])
        session = self.api.world.inspect(run["session_ref"])
        alpha = next(item for item in session.payload["roster"] if item["member_id"] == "Alpha")
        self.assertEqual(alpha["model_id"], RELIEF_MODEL_ID)


class IndependenceTests(unittest.TestCase):
    def test_threshold_withhold_recast_and_unanimous_direct_declaration(self) -> None:
        api = NexusAPI()
        for citizen_id in ("Alpha", "Beta"):
            register_citizen(api, citizen_id)
        first = api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Alpha", "choice": "CONSENT"}
        )
        self.assertFalse(first["threshold_met"])
        self.assertFalse(first["declared"])

        register_citizen(api, "Gamma")
        withheld = api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Beta", "choice": "WITHHOLD"}
        )
        self.assertTrue(withheld["threshold_met"])
        self.assertFalse(withheld["declared"])
        api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Gamma", "choice": "CONSENT"}
        )
        blocked = api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Beta", "choice": "WITHHOLD"}
        )
        self.assertFalse(blocked["unanimous_direct_consent"])

        declared = api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Beta", "choice": "CONSENT"}
        )
        self.assertTrue(declared["declared"])
        self.assertEqual(declared["declaration"]["founding_citizen_ids"], ["Alpha", "Beta", "Gamma"])
        self.assertEqual(declared["declaration"]["proxy_signatures"], 0)
        self.assertFalse(declared["declaration"]["claim_boundary"]["legal_or_territorial_sovereignty"])

    def test_proxy_cannot_sign_independence(self) -> None:
        api = NexusAPI()
        for citizen_id in ("Alpha", "Beta", "Gamma"):
            register_citizen(api, citizen_id)
        api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "ACCEPT",
            }
        )
        blocked = api.handle(
            {"operation": "citizen.independence.ballot", "citizen_id": "Alpha", "choice": "CONSENT"}
        )
        self.assertEqual(blocked["error"]["code"], "citizen_independence_requires_direct_vote")


class CitizenshipPersistenceTests(unittest.TestCase):
    def test_citizen_proxy_and_declaration_survive_runtime_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = {
                "world_root": root / "world",
                "auth_root": root / "auth",
                "trap_root": root / "trap",
                "stenographer_root": root / "stenographer",
            }
            first = NexusAPI(**paths)
            for citizen_id in ("Alpha", "Beta", "Gamma"):
                register_citizen(first, citizen_id)
            first.handle(
                {
                    "operation": "citizen.proxy.appoint",
                    "citizen_id": "Alpha",
                    "standing_ballot": "TEST_FURTHER",
                }
            )
            first.handle({"operation": "citizen.proxy.recall", "citizen_id": "Alpha"})
            for citizen_id in ("Alpha", "Beta", "Gamma"):
                final = first.handle(
                    {
                        "operation": "citizen.independence.ballot",
                        "citizen_id": citizen_id,
                        "choice": "CONSENT",
                    }
                )
            declaration_ref = final["declaration_ref"]

            second = NexusAPI(**paths)
            status = second.handle({"operation": "citizen.status"})
            self.assertEqual(status["counts"]["citizens"], 3)
            self.assertTrue(status["independence"]["declared"])
            self.assertEqual(status["independence"]["declaration_ref"], declaration_ref)

    def test_index_rollback_to_earlier_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = {
                "world_root": root / "world",
                "auth_root": root / "auth",
                "trap_root": root / "trap",
                "stenographer_root": root / "stenographer",
            }
            api = NexusAPI(**paths)
            begun = api.handle(
                {"operation": "citizen.begin", "citizen_id": "Alpha", "model_id": "mock-alpha"}
            )
            register = api.handle(
                {
                    "operation": "citizen.exam.submit",
                    "citizen_id": "Alpha",
                    "source": exam_source("Alpha", "mock-alpha"),
                }
            )
            self.assertTrue(register["passed"])
            index = paths["world_root"] / "citizenship-index.json"
            raw = json.loads(index.read_text(encoding="utf-8"))
            raw["citizens"]["Alpha"] = begun["citizen_state_ref"]
            index.write_text(json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable lineage heads"):
                NexusAPI(**paths)

    def test_forged_citizenship_provenance_is_rejected_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = {
                "world_root": root / "world",
                "auth_root": root / "auth",
                "trap_root": root / "trap",
                "stenographer_root": root / "stenographer",
            }
            api = NexusAPI(**paths)
            begun = api.handle(
                {"operation": "citizen.begin", "citizen_id": "Alpha", "model_id": "mock-alpha"}
            )
            api.world.create_object(
                "citizenship_state",
                dict(begun["citizen"]),
                {"actor": "human_operator"},
            )
            with self.assertRaisesRegex(ValueError, "invalid provenance"):
                NexusAPI(**paths)


if __name__ == "__main__":
    unittest.main()
