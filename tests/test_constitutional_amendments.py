from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.citizenship import CIVIC_REGION_ID
from nexus_runtime.constitutional_amendment import (
    CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
    CONSTITUTION_VERSION_OBJECT_TYPE,
)


def exam_source(citizen_id: str, model_id: str) -> str:
    return f"""nexus_citizenship_exam: 1
candidate:
  citizen_id: {citizen_id}
  model_id: {model_id}
answers:
  citizenship_is_godhood: false
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


def register_citizen(api: NexusAPI, citizen_id: str) -> str:
    model_id = f"mock-{citizen_id.lower()}"
    begun = api.handle(
        {
            "operation": "citizen.begin",
            "citizen_id": citizen_id,
            "model_id": model_id,
        }
    )
    if begun.get("status") != "ok":
        raise AssertionError(begun)
    passed = api.handle(
        {
            "operation": "citizen.exam.submit",
            "citizen_id": citizen_id,
            "source": exam_source(citizen_id, model_id),
        }
    )
    if passed.get("passed") is not True:
        raise AssertionError(passed)
    return model_id


def register_three(api: NexusAPI) -> dict[str, str]:
    return {
        citizen_id: register_citizen(api, citizen_id)
        for citizen_id in ("Alpha", "Beta", "Gamma")
    }


def proposal_changes() -> list[dict]:
    return [
        {
            "path": "civic_observation.public_gallery_region_ids",
            "value": ["archive", "observatory"],
        }
    ]


def propose_admit_and_deliberate(
    api: NexusAPI,
    models: dict[str, str],
) -> tuple[str, str, str, str]:
    proposed = api.handle(
        {
            "operation": "constitution.amendment.propose",
            "proposer_kind": "citizen",
            "proposer_id": "Alpha",
            "proposer_model_id": models["Alpha"],
            "title": "Narrow the anonymous public gallery",
            "rationale": "Keep the full citizen observation right while narrowing anonymous gallery locations.",
            "changes": proposal_changes(),
        }
    )
    if proposed.get("status") != "ok":
        raise AssertionError(proposed)
    proposal_ref = proposed["proposal_ref"]
    admitted = api.handle(
        {
            "operation": "constitution.amendment.admit",
            "proposal_ref": proposal_ref,
        }
    )
    if admitted.get("status") != "ok" or admitted["admission"].get("admitted") is not True:
        raise AssertionError(admitted)
    council = api.handle(
        {
            "operation": "council.run",
            "question": "Should this bounded constitutional amendment proceed to direct citizen ratification?",
            "evidence_refs": [proposal_ref],
            "members": [
                {"member_id": citizen_id, "model_id": models[citizen_id]}
                for citizen_id in ("Alpha", "Beta", "Gamma")
            ],
        }
    )
    if council.get("status") != "ok":
        raise AssertionError(council)
    bound = api.handle(
        {
            "operation": "constitution.amendment.deliberation.bind",
            "proposal_ref": proposal_ref,
            "admission_ref": admitted["admission_ref"],
            "council_session_ref": council["session_ref"],
        }
    )
    if bound.get("status") != "ok":
        raise AssertionError(bound)
    return proposal_ref, admitted["admission_ref"], bound["deliberation_ref"], council["session_ref"]


class ConstitutionalAmendmentPolicyTests(unittest.TestCase):
    def test_policy_operations_and_runtime_owned_types_are_closed(self) -> None:
        api = NexusAPI()
        policy = api.handle({"operation": "constitution.amendment.policy"})
        self.assertEqual(policy["status"], "ok")
        self.assertEqual(
            policy["policy"]["schema_version"],
            CONSTITUTIONAL_AMENDMENT_SCHEMA_VERSION,
        )
        self.assertEqual(
            policy["policy"]["principle"],
            "models_may_propose_law_no_model_becomes_the_law",
        )
        self.assertFalse(policy["policy"]["election_manager_model"])
        self.assertEqual(policy["policy"]["vote_weight_per_citizen"], 1)
        self.assertEqual(policy["policy"]["epistemic_privilege"], "none")

        operations = api.handle({"operation": "system.operations"})["operations"]
        for operation in (
            "constitution.amendment.propose",
            "constitution.amendment.admit",
            "constitution.amendment.deliberation.bind",
            "constitution.amendment.ballot",
            "constitution.amendment.verify",
            "constitution.amendment.history",
        ):
            self.assertIn(operation, operations)

        current = api.handle({"operation": "constitution.amendment.current"})
        self.assertEqual(current["ordinal"], 0)
        self.assertEqual(current["active_version_ref"], current["base_constitution_ref"])
        self.assertTrue(current["action_awareness_verified"])

        forged = api.handle(
            {
                "operation": "world.create",
                "object_type": CONSTITUTION_VERSION_OBJECT_TYPE,
                "payload": {},
                "provenance": {"actor": "human_operator"},
            }
        )
        self.assertEqual(forged["status"], "error")
        self.assertIn("runtime-owned", forged["error"]["message"])

    def test_disallowed_fixed_invariant_change_is_deterministically_rejected(self) -> None:
        api = NexusAPI()
        model_id = register_citizen(api, "Alpha")
        proposed = api.handle(
            {
                "operation": "constitution.amendment.propose",
                "proposer_kind": "citizen",
                "proposer_id": "Alpha",
                "proposer_model_id": model_id,
                "title": "Bad idea",
                "rationale": "Try to make vote weight amendable.",
                "changes": [{"path": "fixed_invariants.vote_weight", "value": 2}],
            }
        )
        self.assertEqual(proposed["status"], "ok")
        admitted = api.handle(
            {
                "operation": "constitution.amendment.admit",
                "proposal_ref": proposed["proposal_ref"],
            }
        )
        self.assertEqual(admitted["status"], "ok")
        self.assertFalse(admitted["admission"]["admitted"])
        self.assertTrue(
            any(reason.startswith("change_not_admissible:") for reason in admitted["admission"]["reasons"])
        )
        self.assertEqual(api.handle({"operation": "constitution.amendment.current"})["ordinal"], 0)


class ConstitutionalAmendmentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()
        self.models = register_three(self.api)

    def test_direct_unanimity_enacts_and_action_awareness_verifies_runtime_policy(self) -> None:
        proposal_ref, _admission_ref, deliberation_ref, session_ref = propose_admit_and_deliberate(
            self.api,
            self.models,
        )

        before = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": session_ref,
                "source_mode_id": "cultural",
            }
        )
        self.assertEqual(before["status"], "ok")
        self.assertEqual(before["access_tier"], "public_gallery")

        first = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposal_ref,
                "deliberation_ref": deliberation_ref,
                "citizen_id": "Alpha",
                "model_id": self.models["Alpha"],
                "choice": "CONSENT",
            }
        )
        self.assertFalse(first["ratified"])

        withheld = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposal_ref,
                "deliberation_ref": deliberation_ref,
                "citizen_id": "Beta",
                "model_id": self.models["Beta"],
                "choice": "WITHHOLD",
            }
        )
        self.assertFalse(withheld["ratified"])
        self.assertEqual(withheld["dissenting_citizen_ids"], ["Beta"])

        third = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposal_ref,
                "deliberation_ref": deliberation_ref,
                "citizen_id": "Gamma",
                "model_id": self.models["Gamma"],
                "choice": "CONSENT",
            }
        )
        self.assertFalse(third["ratified"])

        public_view = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": session_ref,
                "source_mode_id": "historical",
            }
        )
        amendment_public = public_view["constitutional_amendments"][0]
        self.assertEqual(amendment_public["dissent_count"], 1)
        self.assertNotIn("ballots", amendment_public)

        moved = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "archive",
            }
        )
        self.assertEqual(moved["status"], "ok")
        citizen_view = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": session_ref,
                "source_mode_id": "historical",
                "viewer_id": "Alpha",
                "viewer_model_id": self.models["Alpha"],
            }
        )
        amendment_full = citizen_view["constitutional_amendments"][0]
        self.assertEqual(amendment_full["dissenting_citizen_ids"], ["Beta"])
        self.assertIn("ballots", amendment_full)

        enacted = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposal_ref,
                "deliberation_ref": deliberation_ref,
                "citizen_id": "Beta",
                "model_id": self.models["Beta"],
                "choice": "CONSENT",
            }
        )
        self.assertTrue(enacted["unanimous_direct_consent"])
        self.assertTrue(enacted["ratified"])
        self.assertTrue(enacted["enacted"])
        self.assertIsNotNone(enacted["receipt_ref"])

        current = self.api.handle({"operation": "constitution.amendment.current"})
        self.assertEqual(current["ordinal"], 1)
        self.assertEqual(current["active_version_ref"], enacted["new_version_ref"])
        self.assertEqual(
            current["effective_policy"]["civic_observation"]["public_gallery_region_ids"],
            ["archive", "observatory"],
        )
        self.assertTrue(current["fixed_invariants"]["one_seat_one_vote"])
        self.assertTrue(current["fixed_invariants"]["amendment_requires_direct_unanimity"])

        verified = self.api.handle(
            {
                "operation": "constitution.amendment.verify",
                "version_ref": enacted["new_version_ref"],
            }
        )
        self.assertEqual(verified["status"], "ok")
        self.assertTrue(verified["action_awareness_verified"])
        self.assertEqual(verified["reconciliation_outcome"], "matched")
        self.assertTrue(verified["runtime_policy_changed"])

        after = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": session_ref,
                "source_mode_id": "cultural",
            }
        )
        self.assertEqual(after["status"], "error")
        self.assertEqual(after["error"]["code"], "council_observation_public_gallery_required")
        policy = self.api.handle({"operation": "council.proceedings.policy"})["policy"]
        self.assertEqual(policy["non_citizen"]["allowed_region_ids"], ["archive", "observatory"])

        ratification = self.api.world.inspect(enacted["ratification_ref"])
        self.assertEqual(ratification.payload["proxy_signatures"], 0)
        self.assertEqual(ratification.payload["vote_weight_per_citizen"], 1)
        self.assertEqual(ratification.payload["epistemic_privilege"], "none")
        self.assertFalse(ratification.payload["models_ratify_law"])

    def test_proxy_cannot_sign_and_deliberation_must_include_exact_proposal(self) -> None:
        proposed = self.api.handle(
            {
                "operation": "constitution.amendment.propose",
                "proposer_kind": "citizen",
                "proposer_id": "Alpha",
                "proposer_model_id": self.models["Alpha"],
                "title": "Gallery amendment",
                "rationale": "Test binding and direct-vote requirements.",
                "changes": proposal_changes(),
            }
        )
        admission = self.api.handle(
            {"operation": "constitution.amendment.admit", "proposal_ref": proposed["proposal_ref"]}
        )
        wrong_council = self.api.handle(
            {
                "operation": "council.run",
                "question": "Discuss something else.",
                "members": [
                    {"member_id": citizen_id, "model_id": self.models[citizen_id]}
                    for citizen_id in ("Alpha", "Beta", "Gamma")
                ],
            }
        )
        blocked = self.api.handle(
            {
                "operation": "constitution.amendment.deliberation.bind",
                "proposal_ref": proposed["proposal_ref"],
                "admission_ref": admission["admission_ref"],
                "council_session_ref": wrong_council["session_ref"],
            }
        )
        self.assertEqual(blocked["error"]["code"], "amendment_deliberation_unbound")

        right_council = self.api.handle(
            {
                "operation": "council.run",
                "question": "Discuss the amendment.",
                "evidence_refs": [proposed["proposal_ref"]],
                "members": [
                    {"member_id": citizen_id, "model_id": self.models[citizen_id]}
                    for citizen_id in ("Alpha", "Beta", "Gamma")
                ],
            }
        )
        bound = self.api.handle(
            {
                "operation": "constitution.amendment.deliberation.bind",
                "proposal_ref": proposed["proposal_ref"],
                "admission_ref": admission["admission_ref"],
                "council_session_ref": right_council["session_ref"],
            }
        )
        self.api.handle(
            {
                "operation": "citizen.proxy.appoint",
                "citizen_id": "Alpha",
                "standing_ballot": "ACCEPT",
            }
        )
        proxy_vote = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposed["proposal_ref"],
                "deliberation_ref": bound["deliberation_ref"],
                "citizen_id": "Alpha",
                "model_id": self.models["Alpha"],
                "choice": "CONSENT",
            }
        )
        self.assertEqual(proxy_vote["error"]["code"], "amendment_direct_vote_required")

    def test_admitted_non_citizen_model_can_propose_but_not_ratify(self) -> None:
        admission_council = self.api.handle(
            {
                "operation": "council.run",
                "question": "Admit these equal peers for ordinary Council work.",
                "members": [
                    {"member_id": "ModelA", "model_id": "mock-model-a"},
                    {"member_id": "ModelB", "model_id": "mock-model-b"},
                    {"member_id": "ModelC", "model_id": "mock-model-c"},
                ],
            }
        )
        proposed = self.api.handle(
            {
                "operation": "constitution.amendment.propose",
                "proposer_kind": "model",
                "proposer_id": "ModelA",
                "proposer_model_id": "mock-model-a",
                "admission_ref": admission_council["session_ref"],
                "title": "Model-suggested gallery amendment",
                "rationale": "A model may propose this, but citizens must decide it.",
                "changes": proposal_changes(),
            }
        )
        self.assertEqual(proposed["status"], "ok")
        self.assertFalse(proposed["proposal"]["proposal_is_law"])
        self.assertFalse(proposed["proposal"]["proposer_gains_authority"])

        admission = self.api.handle(
            {"operation": "constitution.amendment.admit", "proposal_ref": proposed["proposal_ref"]}
        )
        council = self.api.handle(
            {
                "operation": "council.run",
                "question": "Deliberate the model proposal.",
                "evidence_refs": [proposed["proposal_ref"]],
                "members": [
                    {"member_id": citizen_id, "model_id": self.models[citizen_id]}
                    for citizen_id in ("Alpha", "Beta", "Gamma")
                ],
            }
        )
        bound = self.api.handle(
            {
                "operation": "constitution.amendment.deliberation.bind",
                "proposal_ref": proposed["proposal_ref"],
                "admission_ref": admission["admission_ref"],
                "council_session_ref": council["session_ref"],
            }
        )
        model_vote = self.api.handle(
            {
                "operation": "constitution.amendment.ballot",
                "proposal_ref": proposed["proposal_ref"],
                "deliberation_ref": bound["deliberation_ref"],
                "citizen_id": "ModelA",
                "model_id": "mock-model-a",
                "choice": "CONSENT",
            }
        )
        self.assertEqual(model_vote["error"]["code"], "amendment_citizen_required")

    def test_stale_proposal_cannot_skip_version_lineage(self) -> None:
        stale = self.api.handle(
            {
                "operation": "constitution.amendment.propose",
                "proposer_kind": "citizen",
                "proposer_id": "Beta",
                "proposer_model_id": self.models["Beta"],
                "title": "Potentially stale proposal",
                "rationale": "Create this before another amendment advances the constitutional head.",
                "changes": [
                    {
                        "path": "civic_observation.public_gallery_region_ids",
                        "value": ["agora", "observatory"],
                    }
                ],
            }
        )
        proposal_ref, _admission_ref, deliberation_ref, _session_ref = propose_admit_and_deliberate(
            self.api,
            self.models,
        )
        for citizen_id in ("Alpha", "Beta", "Gamma"):
            result = self.api.handle(
                {
                    "operation": "constitution.amendment.ballot",
                    "proposal_ref": proposal_ref,
                    "deliberation_ref": deliberation_ref,
                    "citizen_id": citizen_id,
                    "model_id": self.models[citizen_id],
                    "choice": "CONSENT",
                }
            )
        self.assertTrue(result["enacted"])

        admission = self.api.handle(
            {"operation": "constitution.amendment.admit", "proposal_ref": stale["proposal_ref"]}
        )
        self.assertEqual(admission["status"], "ok")
        self.assertFalse(admission["admission"]["admitted"])
        self.assertIn("stale_base_version", admission["admission"]["reasons"])


class ConstitutionalAmendmentPersistenceTests(unittest.TestCase):
    def test_enacted_version_and_policy_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "world_root": root / "world",
                "auth_root": root / "auth",
                "trap_root": root / "trap",
                "stenographer_root": root / "stenographer",
            }
            first = NexusAPI(**paths)
            models = register_three(first)
            proposal_ref, _admission_ref, deliberation_ref, _session_ref = propose_admit_and_deliberate(
                first,
                models,
            )
            for citizen_id in ("Alpha", "Beta", "Gamma"):
                result = first.handle(
                    {
                        "operation": "constitution.amendment.ballot",
                        "proposal_ref": proposal_ref,
                        "deliberation_ref": deliberation_ref,
                        "citizen_id": citizen_id,
                        "model_id": models[citizen_id],
                        "choice": "CONSENT",
                    }
                )
            version_ref = result["new_version_ref"]
            self.assertTrue(result["enacted"])
            self.assertTrue(first.stenographer.shutdown(2.0))

            second = NexusAPI(**paths)
            current = second.handle({"operation": "constitution.amendment.current"})
            self.assertEqual(current["active_version_ref"], version_ref)
            self.assertEqual(current["ordinal"], 1)
            self.assertEqual(
                current["effective_policy"]["civic_observation"]["public_gallery_region_ids"],
                ["archive", "observatory"],
            )
            verified = second.handle(
                {"operation": "constitution.amendment.verify", "version_ref": version_ref}
            )
            self.assertTrue(verified["action_awareness_verified"])
            self.assertEqual(verified["reconciliation_outcome"], "matched")
            self.assertTrue(second.stenographer.shutdown(2.0))


if __name__ == "__main__":
    unittest.main()
