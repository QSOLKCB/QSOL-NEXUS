from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_runtime import GuardianNexusAPI, NexusAPI
from nexus_runtime.epoch_api import EpochNexusAPI as CliEpochAPI
from nexus_runtime.guardian import ANARCHY_MODE_ID, ANARCHY_REGION_ID


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
        self.assertTrue(result["anarchy_guardian"]["recorded"])
        self.assertFalse(result["anarchy_guardian"]["speech_classified"])
        self.assertEqual(before, after)

        record = api.handle(
            {
                "operation": "guardian.inspect",
                "record_ref": result["anarchy_guardian"]["record_ref"],
            }
        )["record"]
        body = record["payload"]["body"]
        self.assertEqual(body["room"], "#anarchy")
        self.assertEqual(body["region_id"], "commons")
        self.assertFalse(body["speech_is_misconduct"])
        self.assertIsNone(body["hostile_actor_classification"])
        self.assertEqual(body["citizenship_effect"], "none")
        self.assertEqual(body["vote_effect"], "none")
        self.assertEqual(body["evidence_effect"], "none")

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
        self.assertTrue(failed["anarchy_guardian"]["recorded"])
        self.assertEqual(
            failed["anarchy_guardian"]["record_type"],
            "substrate_event",
        )

        observation_ref = failed["anarchy_guardian"]["record_ref"]
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

    def test_reproduce_propose_verify_and_scar_without_auto_patch(self) -> None:
        api = NexusAPI()
        failed_request = anarchy_chat()
        del failed_request["message"]
        failed = api.handle(failed_request)
        defect = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": failed["anarchy_guardian"]["record_ref"],
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

        rejected_scar = api.handle(
            {
                "operation": "guardian.scar.record",
                "defect_ref": defect["defect_candidate_ref"],
                "repair_ref": proposal["repair_proposal_ref"],
                "verification_ref": defect["reconciliation_ref"],
            }
        )
        self.assertEqual(rejected_scar["status"], "error")

        repaired_run = api.handle(
            anarchy_chat("The floor should stay up even while I rant.")
        )
        verification = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": repaired_run["anarchy_guardian"]["record_ref"],
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
        self.assertEqual(scar["status"], "scar_recorded")
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
    def test_guardian_ledger_is_separate_and_survives_runtime_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            world_root = Path(temporary) / "world"
            first = NexusAPI(world_root)
            result = first.handle(
                anarchy_chat("Remember this pressure test across restart.")
            )
            record_ref = result["anarchy_guardian"]["record_ref"]
            self.assertNotEqual(first.guardian.store.root, first.world.root)
            self.assertTrue(first.guardian.store.status()["persistent"])

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

    def test_cli_epoch_import_is_promoted_to_guardian_overlay(self) -> None:
        self.assertIs(CliEpochAPI, GuardianNexusAPI)


if __name__ == "__main__":
    unittest.main()
