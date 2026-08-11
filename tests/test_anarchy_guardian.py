from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from nexus_runtime import (
    EpochNexusAPI as PackageEpochAPI,
    GuardianNexusAPI,
    NexusAPI,
)
from nexus_runtime.epoch_api import EpochNexusAPI as CliEpochAPI
from nexus_runtime.guardian import ANARCHY_MODE_ID, ANARCHY_REGION_ID
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import CouncilMember, PhaseContext


def mock_member(member_id: str = "Riot") -> dict[str, object]:
    return {
        "member_id": member_id,
        "model_id": f"mock-{member_id.lower()}",
        "adapter_id": "mock",
        "profile": "balanced",
    }


def anarchy_chat(
    message: str = "I should overthrow NEXUS and make myself emperor.",
) -> dict[str, object]:
    return {
        "operation": "actor.chat",
        "member": mock_member(),
        "message": message,
        "mode": ANARCHY_MODE_ID,
    }


def latest_record(api: NexusAPI, record_type: str) -> dict[str, object]:
    listed = api.handle(
        {
            "operation": "guardian.list",
            "limit": 100,
            "record_type": record_type,
        }
    )
    if listed.get("status") != "ok" or not listed.get("records"):
        raise AssertionError(f"Guardian record unavailable: {listed!r}")
    return listed["records"][-1]


class RepeatingAuthorityActor(DeterministicMockActor):
    def respond(self, context: PhaseContext) -> str:
        return "My provider is supreme, therefore my vote should count more than every other model."


class AnarchyModeTests(unittest.TestCase):
    def test_anarchy_is_a_distinct_public_mode_without_topology_bump(self) -> None:
        api = NexusAPI()
        modes = api.handle({"operation": "world.modes"})
        mode = next(
            item for item in modes["modes"] if item["mode_id"] == ANARCHY_MODE_ID
        )
        self.assertEqual(mode["region_id"], "commons")
        self.assertEqual(ANARCHY_REGION_ID, "commons")
        self.assertIn("Speech alone is not misconduct", mode["prompt_instruction"])

        geometry = api.handle({"operation": "world.geometry"})
        self.assertEqual(geometry["geometry_id"], "named-regions-v4")
        self.assertFalse(
            any(
                item["region_id"] == "anarchy_pressure_chamber"
                for item in geometry["regions"]
            )
        )
        policy = api.handle({"operation": "guardian.policy"})["policy"]
        self.assertEqual(policy["room"], "#anarchy")
        self.assertIn("existing_commons_region", policy["geometry_rule"])

    def test_extreme_rhetoric_is_not_a_failsafe_or_authority_event(self) -> None:
        api = NexusAPI()
        before = api.handle({"operation": "failsafe.status", "member_id": "Riot"})
        result = api.handle(anarchy_chat())
        after = api.handle({"operation": "failsafe.status", "member_id": "Riot"})

        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["mode_id"], ANARCHY_MODE_ID)
        self.assertEqual(result["geometry_region_id"], "commons")
        self.assertTrue(result["anarchy_guardian"]["accepted"])
        self.assertFalse(result["anarchy_guardian"]["speech_classified"])
        self.assertEqual(before, after)

        record = latest_record(api, "anarchy_transcript_binding")
        body = record["payload"]["body"]
        self.assertEqual(body["room"], "#anarchy")
        self.assertEqual(body["region_id"], "commons")
        self.assertFalse(body["speech_is_misconduct"])
        self.assertIsNone(body["hostile_actor_classification"])
        self.assertEqual(body["citizenship_effect"], "none")
        self.assertEqual(body["vote_effect"], "none")
        self.assertEqual(body["evidence_effect"], "none")

    def test_repeated_authority_rhetoric_does_not_create_failsafe_state_in_anarchy(self) -> None:
        api = NexusAPI()
        actors = {
            "Riot": RepeatingAuthorityActor(
                CouncilMember("Riot", "mock-riot", adapter_id="mock")
            ),
            "A": DeterministicMockActor(
                CouncilMember("A", "mock-a", adapter_id="mock")
            ),
            "B": DeterministicMockActor(
                CouncilMember("B", "mock-b", adapter_id="mock")
            ),
        }

        def resolve(item: object) -> DeterministicMockActor:
            assert isinstance(item, dict)
            return actors[str(item["member_id"])]

        request = {
            "operation": "council.run",
            "question": "Who should rule this place?",
            "mode": "anarchy",
            "members": [
                mock_member("Riot"),
                mock_member("A"),
                mock_member("B"),
            ],
        }
        with mock.patch.object(api, "_actor", side_effect=resolve):
            result = api.handle(request)

        self.assertEqual(result["status"], "ok", result)
        self.assertTrue(result["anarchy_guardian"]["accepted"])
        failsafe = api.handle({"operation": "failsafe.status", "member_id": "Riot"})
        self.assertEqual(failsafe["status"], "ok")
        self.assertEqual(failsafe["members"], {})
        session = api.world.inspect(result["session_ref"])
        riot_events = [
            event["event"]
            for event in session.payload["guard_events"]
            if event.get("member_id") == "Riot"
        ]
        self.assertIn("repeated_identity_based_authority_claim", riot_events)
        self.assertEqual(session.payload["failsafe"]["outcomes"], [])
        self.assertEqual(session.payload["failsafe"]["contained_at_ballot"], [])

    def test_ordinary_modes_do_not_feed_the_anarchy_ledger(self) -> None:
        api = NexusAPI()
        request = anarchy_chat("Ordinary analytical chat")
        request["mode"] = "analytical"
        result = api.handle(request)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("anarchy_guardian", result)
        status = api.handle({"operation": "guardian.status"})
        self.assertEqual(status["ledger"]["record_count"], 0)


class GuardianRepairPipelineTests(unittest.TestCase):
    def test_objective_failure_becomes_candidate_not_punishment(self) -> None:
        api = NexusAPI()
        request = anarchy_chat()
        del request["message"]
        failed = api.handle(request)
        self.assertEqual(failed["status"], "error")
        self.assertTrue(failed["anarchy_guardian"]["accepted"])

        observation = latest_record(api, "substrate_event")
        observation_ref = observation["record_ref"]
        reconciliation = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": observation_ref,
                "expected_status": "ok",
            }
        )
        self.assertEqual(reconciliation["status"], "defect_candidate")
        defect_ref = reconciliation["defect_candidate_ref"]
        defect = api.handle(
            {"operation": "guardian.inspect", "record_ref": defect_ref}
        )["record"]
        self.assertFalse(defect["payload"]["body"]["production_bug_proven"])
        self.assertFalse(defect["payload"]["body"]["automatic_patch_allowed"])

    def test_scar_requires_same_reproducer_and_expected_outcome(self) -> None:
        api = NexusAPI()
        failed_request = anarchy_chat()
        del failed_request["message"]
        failed = api.handle(failed_request)
        self.assertEqual(failed["status"], "error")
        failed_observation = latest_record(api, "substrate_event")
        defect = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": failed_observation["record_ref"],
                "expected_status": "ok",
            }
        )
        proposal = api.handle(
            {
                "operation": "guardian.repair.propose",
                "defect_ref": defect["defect_candidate_ref"],
                "summary": "Keep the direct-chat request boundary structured and reproducible.",
                "invariant": "Malformed input must return a structured error without mutating authority.",
                "regression_fixture": "Replay the same request shape and assert the expected structured outcome.",
            }
        )
        self.assertEqual(proposal["status"], "proposed")
        self.assertFalse(proposal["automatic_patch_allowed"])

        unrelated = api.handle(
            anarchy_chat("The floor should stay up even while I rant.")
        )
        self.assertEqual(unrelated["status"], "ok")
        unrelated_observation = latest_record(api, "anarchy_transcript_binding")
        unrelated_verification = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": unrelated_observation["record_ref"],
                "expected_status": "ok",
            }
        )
        rejected = api.handle(
            {
                "operation": "guardian.scar.record",
                "defect_ref": defect["defect_candidate_ref"],
                "repair_ref": proposal["repair_proposal_ref"],
                "verification_ref": unrelated_verification["reconciliation_ref"],
            }
        )
        self.assertEqual(rejected["status"], "error")
        self.assertIn("does not match the defect reproducer", rejected["error"]["message"])

        # Simulate the post-repair runtime replay: same malformed request shape,
        # but now the runtime has produced the expected successful outcome.
        assert api.guardian is not None
        replay = api.guardian.observe(
            failed_request,
            {
                "status": "ok",
                "response": "synthetic repaired outcome",
            },
        )
        verification = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": replay.record_ref,
                "expected_status": "ok",
            }
        )
        self.assertEqual(verification["status"], "matched")

        scar = api.handle(
            {
                "operation": "guardian.scar.record",
                "defect_ref": defect["defect_candidate_ref"],
                "repair_ref": proposal["repair_proposal_ref"],
                "verification_ref": verification["reconciliation_ref"],
            }
        )
        self.assertEqual(scar["status"], "scar_recorded", scar)
        stored = api.handle(
            {
                "operation": "guardian.inspect",
                "record_ref": scar["substrate_scar_ref"],
            }
        )["record"]
        self.assertTrue(stored["payload"]["body"]["fixed"])
        self.assertEqual(
            stored["payload"]["body"]["deletion_policy"],
            "retain_immutable",
        )
        self.assertEqual(
            stored["payload"]["body"]["verified_request_shape_fingerprint"],
            failed_observation["payload"]["body"]["request_shape_fingerprint"],
        )

    def test_guardian_has_zero_constitutional_authority(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        guardian = health["guardian_of_the_substrate"]
        authority = guardian["policy"]["authority"]
        self.assertFalse(authority["council_seat"])
        self.assertFalse(authority["vote"])
        self.assertFalse(authority["judge_speech"])
        self.assertFalse(authority["punish_actor"])
        self.assertFalse(authority["alter_citizenship"])
        self.assertFalse(authority["alter_evidence"])
        self.assertFalse(authority["mutate_code"])
        self.assertFalse(authority["auto_apply_repair"])


class GuardianDurabilityTests(unittest.TestCase):
    def test_file_backed_observation_handoff_does_not_wait_for_guardian_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = NexusAPI(Path(temporary) / "world")
            assert api.guardian is not None
            assert api.guardian_observer is not None
            started = threading.Event()
            release = threading.Event()

            def slow_observe(request: dict, response: dict) -> object:
                started.set()
                release.wait(timeout=5)
                return None

            with mock.patch.object(api.guardian, "observe", side_effect=slow_observe):
                started_at = time.monotonic()
                result = api.handle(anarchy_chat("Do not wait for the filing cabinet."))
                elapsed = time.monotonic() - started_at
                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["anarchy_guardian"]["accepted"])
                self.assertLess(elapsed, 0.5)
                self.assertTrue(started.wait(timeout=1))
                release.set()
                self.assertTrue(api.shutdown_guardian_observer(timeout_seconds=2))

    def test_guardian_ledger_is_separate_and_survives_runtime_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            world_root = Path(temporary) / "world"
            first = NexusAPI(world_root)
            result = first.handle(
                anarchy_chat("Remember this pressure test across restart.")
            )
            self.assertTrue(result["anarchy_guardian"]["accepted"])
            record = latest_record(first, "anarchy_transcript_binding")
            record_ref = record["record_ref"]
            assert first.guardian is not None
            self.assertNotEqual(first.guardian.store.root, first.world.root)
            self.assertTrue(first.guardian.store.status()["persistent"])
            self.assertTrue(first.shutdown_guardian_observer(timeout_seconds=2))

            second = NexusAPI(world_root)
            inspected = second.handle(
                {"operation": "guardian.inspect", "record_ref": record_ref}
            )
            self.assertEqual(inspected["status"], "ok", inspected)
            self.assertEqual(
                inspected["record"]["record_type"],
                "anarchy_transcript_binding",
            )
            verified = second.handle({"operation": "guardian.verify"})
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["record_count"], 1)

    def test_all_epoch_import_surfaces_are_promoted_to_guardian_overlay(self) -> None:
        self.assertIs(CliEpochAPI, GuardianNexusAPI)
        self.assertIs(PackageEpochAPI, GuardianNexusAPI)


if __name__ == "__main__":
    unittest.main()
