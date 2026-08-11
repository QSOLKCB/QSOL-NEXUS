from __future__ import annotations

import unittest
from unittest.mock import patch

from nexus_runtime import NexusAPI
from nexus_runtime.civic_observation import (
    CIVIC_OBSERVATION_SCHEMA_VERSION,
    NON_CITIZEN_GALLERY_REGION_IDS,
    RESTRICTED_OBSERVATION_REGION_IDS,
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


def register_citizen(api: NexusAPI, citizen_id: str, model_id: str) -> None:
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


def council_session(api: NexusAPI) -> str:
    result = api.handle(
        {
            "operation": "council.run",
            "question": "Should the immutable trout minutes remain public?",
            "members": [
                {"member_id": "SeatA", "model_id": "mock-seat-a", "profile": "supportive"},
                {"member_id": "SeatB", "model_id": "mock-seat-b", "profile": "skeptical"},
                {"member_id": "SeatC", "model_id": "mock-seat-c", "profile": "rejecting"},
            ],
        }
    )
    if result.get("status") != "ok":
        raise AssertionError(result)
    return result["session_ref"]


class CivicObservationPolicyTests(unittest.TestCase):
    def test_health_and_operations_publish_civic_observation_contract(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        policy = health["civic_observation"]
        self.assertEqual(policy["schema_version"], CIVIC_OBSERVATION_SCHEMA_VERSION)
        self.assertEqual(policy["principle"], "citizenship_widens_observation_not_authority")
        self.assertTrue(policy["completed_proceedings_only"])
        self.assertTrue(policy["read_only"])
        self.assertEqual(
            set(policy["non_citizen"]["allowed_region_ids"]),
            set(NON_CITIZEN_GALLERY_REGION_IDS),
        )
        self.assertEqual(
            set(policy["restricted_region_ids"]),
            set(RESTRICTED_OBSERVATION_REGION_IDS),
        )
        self.assertIn("commons", policy["citizen"]["allowed_region_ids"])
        self.assertNotIn("commons", policy["non_citizen"]["allowed_region_ids"])
        self.assertFalse(policy["authority_invariants"]["observation_changes_vote_weight"])

        operations = api.handle({"operation": "system.operations"})["operations"]
        self.assertIn("council.proceedings.policy", operations)
        self.assertIn("council.proceedings.view", operations)

        direct = api.handle({"operation": "council.proceedings.policy"})
        self.assertEqual(direct["status"], "ok")
        self.assertEqual(direct["policy"], policy)

    def test_civic_overlay_preserves_malformed_operation_error_boundary(self) -> None:
        result = NexusAPI().handle({"operation": []})  # type: ignore[list-item]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_public_world_create_cannot_forge_runtime_council_objects_or_nexus_provenance(self) -> None:
        api = NexusAPI()
        for object_type in ("council_session", "evidence_snapshot", "receipt", "world_presence"):
            with self.subTest(object_type=object_type):
                result = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {},
                        "provenance": {"actor": "nexus"},
                    }
                )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "invalid_request")

        spoofed_provenance = api.handle(
            {
                "operation": "world.create",
                "object_type": "note",
                "payload": {"text": "I am definitely official, trust me."},
                "provenance": {"actor": "nexus"},
            }
        )
        self.assertEqual(spoofed_provenance["status"], "error")
        self.assertEqual(spoofed_provenance["error"]["code"], "invalid_request")


class CivicObservationAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()
        self.session_ref = council_session(self.api)

    def test_non_citizen_public_gallery_gets_bounded_summary(self) -> None:
        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": self.session_ref,
                "source_mode_id": "analytical",
            }
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["access_tier"], "public_gallery")
        self.assertEqual(response["source_region_id"], "observatory")
        self.assertTrue(response["read_only"])
        self.assertIn("ballot_summary", response["proceeding"])
        self.assertFalse(response["proceeding"]["phase_text_visible"])
        self.assertFalse(response["proceeding"]["individual_ballots_visible"])
        self.assertNotIn("phase_submissions", response["proceeding"])
        self.assertNotIn("revealed_ballots", response["proceeding"])
        public_result = response["council"]["result"]
        self.assertNotIn("minority_reports", public_result)
        self.assertFalse(public_result["individual_minority_reports_visible"])
        self.assertFalse(response["authority_invariant"]["viewer_gains_vote"])

    def test_non_citizen_cannot_view_from_commons_or_game_regions(self) -> None:
        for mode_id in ("house_fun", "citizen_play", "game_mud"):
            with self.subTest(mode_id=mode_id):
                response = self.api.handle(
                    {
                        "operation": "council.proceedings.view",
                        "session_ref": self.session_ref,
                        "source_mode_id": mode_id,
                    }
                )
                self.assertEqual(response["status"], "error")
                self.assertEqual(
                    response["error"]["code"],
                    "council_observation_public_gallery_required",
                )

    def test_citizen_may_carry_full_read_only_view_into_non_council_mode(self) -> None:
        register_citizen(self.api, "Alpha", "mock-alpha")
        moved = self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "commons",
            }
        )
        self.assertEqual(moved["status"], "ok")

        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": self.session_ref,
                "source_mode_id": "house_fun",
                "viewer_id": "Alpha",
                "viewer_model_id": "mock-alpha",
            }
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["access_tier"], "citizen_full")
        self.assertEqual(response["source_region_id"], "commons")
        self.assertTrue(response["citizenship"]["cross_mode_observation_right"])
        self.assertEqual(response["citizenship"]["vote_weight"], 1)
        self.assertEqual(response["citizenship"]["epistemic_privilege"], "none")
        self.assertIn("phase_submissions", response["proceeding"])
        self.assertIn("revealed_ballots", response["proceeding"])
        self.assertIn("telemetry", response["proceeding"])
        self.assertIn("minority_reports", response["council"]["result"])
        self.assertFalse(response["authority_invariant"]["viewer_can_mutate_proceeding"])

    def test_citizen_region_state_must_match_claimed_source_mode(self) -> None:
        register_citizen(self.api, "Alpha", "mock-alpha")
        self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "commons",
            }
        )
        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": self.session_ref,
                "source_mode_id": "historical",
                "viewer_id": "Alpha",
                "viewer_model_id": "mock-alpha",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "council_observation_region_mismatch")

    def test_registered_identity_mismatch_fails_closed(self) -> None:
        register_citizen(self.api, "Alpha", "mock-alpha")
        self.api.handle(
            {
                "operation": "citizen.move",
                "citizen_id": "Alpha",
                "target_region_id": "observatory",
            }
        )
        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": self.session_ref,
                "source_mode_id": "analytical",
                "viewer_id": "Alpha",
                "viewer_model_id": "mock-impostor",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "council_observation_identity_mismatch")

    def test_council_and_parole_regions_are_not_cross_mode_galleries(self) -> None:
        register_citizen(self.api, "Alpha", "mock-alpha")
        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": self.session_ref,
                "source_mode_id": "civic_bureaucracy",
                "viewer_id": "Alpha",
                "viewer_model_id": "mock-alpha",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "council_observation_region_restricted")

        parole = NexusAPI()
        parole.handle(
            {
                "operation": "citizen.begin",
                "citizen_id": "Candidate",
                "model_id": "mock-candidate",
            }
        )
        other_session = council_session(parole)
        response = parole.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": other_session,
                "source_mode_id": "citizenship_parole",
                "viewer_id": "Candidate",
                "viewer_model_id": "mock-candidate",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "council_observation_region_restricted")

    def test_only_committed_council_sessions_are_viewable(self) -> None:
        created = self.api.handle(
            {
                "operation": "world.create",
                "object_type": "note",
                "payload": {"text": "not a proceeding"},
            }
        )
        response = self.api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": created["object"]["object_id"],
                "source_mode_id": "analytical",
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "council_proceeding_required")

    def test_storage_failures_remain_structured_and_path_free(self) -> None:
        with patch.object(
            self.api.world,
            "inspect",
            side_effect=OSError("Permission denied: '/private/operator/world/objects/secret.json'"),
        ):
            response = self.api.handle(
                {
                    "operation": "council.proceedings.view",
                    "session_ref": self.session_ref,
                    "source_mode_id": "analytical",
                }
            )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "adapter_unavailable")
        self.assertEqual(
            response["error"]["message"],
            "adapter or local storage operation is unavailable",
        )
        self.assertNotIn("/private/", str(response))


if __name__ == "__main__":
    unittest.main()
