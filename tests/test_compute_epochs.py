from __future__ import annotations

import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.compute_epochs import (
    EPOCH_DURATION_SECONDS,
    GENESIS_UNIX,
    current_compute_epoch,
    pinned_current_compute_epoch,
    resolve_compute_epoch,
    small_model_threshold_millions,
)
from nexus_runtime.epoch_api import EPOCH_ADMISSION_RECEIPT_TYPE
from nexus_runtime.epoch_chair import evaluate_epoch_council_roster_request
from nexus_runtime.genesis_capsule import (
    GENESIS_CAPSULE_SHA256,
    genesis_capsule_status,
    reveal_genesis_capsule,
)
from nexus_runtime.purgatory import (
    PURGATORY_CORPUS_SHA256,
    deterministic_exam_selection,
    purgatory_policy_snapshot,
)


def classification(distribution: str, count_millions: int | None) -> dict[str, object]:
    return {
        "council_classification": {
            "distribution": distribution,
            "parameter_count_millions": count_millions,
            "parameter_count_basis": "undisclosed" if count_millions is None else "total_declared",
            "parameter_count_source": "fixture:model-card",
        }
    }


def member(
    member_id: str,
    model_id: str,
    *,
    distribution: str | None = None,
    count_millions: int | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "member_id": member_id,
        "model_id": model_id,
        "adapter_id": "mock",
    }
    if distribution is not None:
        item["capability_metadata"] = classification(distribution, count_millions)
    return item


class ComputeEpochTests(unittest.TestCase):
    def test_epoch_boundaries_and_exact_doubling(self) -> None:
        self.assertEqual(resolve_compute_epoch(GENESIS_UNIX), 0)
        self.assertEqual(resolve_compute_epoch(GENESIS_UNIX + EPOCH_DURATION_SECONDS - 1), 0)
        self.assertEqual(resolve_compute_epoch(GENESIS_UNIX + EPOCH_DURATION_SECONDS), 1)
        self.assertEqual(small_model_threshold_millions(0), 20_000)
        self.assertEqual(small_model_threshold_millions(1), 40_000)
        self.assertEqual(small_model_threshold_millions(2), 80_000)

    def test_one_live_request_cannot_straddle_an_epoch_boundary(self) -> None:
        just_before = GENESIS_UNIX + EPOCH_DURATION_SECONDS - 1
        just_after = GENESIS_UNIX + EPOCH_DURATION_SECONDS + 1
        with mock.patch("nexus_runtime.compute_epochs.time.time", side_effect=[just_before, just_after]):
            with pinned_current_compute_epoch() as pinned:
                self.assertEqual(pinned, 0)
                self.assertEqual(current_compute_epoch(), 0)
            self.assertEqual(current_compute_epoch(), 1)

    def test_epoch_one_expands_admission_without_expanding_vote(self) -> None:
        roster = [
            member("Closed", "closed", distribution="closed", count_millions=None),
            member("Open30", "open-30b", distribution="open_weight", count_millions=30_000),
            member("Open70", "open-70b", distribution="open_weight", count_millions=70_000),
        ]
        with self.assertRaisesRegex(ValueError, "Small-Mind Guarantee"):
            evaluate_epoch_council_roster_request(roster, epoch=0)
        admitted = evaluate_epoch_council_roster_request(roster, epoch=1)
        seats = {seat["member_id"]: seat for seat in admitted["seats"]}
        self.assertEqual(seats["Open30"]["slot_class"], "protected_small")
        self.assertEqual(admitted["vote_weight_per_seat"], 1)
        self.assertEqual(admitted["epistemic_privilege_per_seat"], "none")

    def test_epochs_raise_ceilings_never_floors(self) -> None:
        roster = [member("Old8B", "old-8b"), member("A", "a"), member("B", "b")]
        admitted = evaluate_epoch_council_roster_request(roster, epoch=25)
        old = next(seat for seat in admitted["seats"] if seat["member_id"] == "Old8B")
        self.assertEqual(old["slot_class"], "protected_small")
        self.assertEqual(admitted["vote_weight_per_seat"], 1)


class GenesisCapsuleTests(unittest.TestCase):
    def test_capsule_is_sealed_before_epoch_25_and_reveals_at_25(self) -> None:
        sealed = reveal_genesis_capsule(24)
        self.assertEqual(sealed["status"], "sealed")
        self.assertIsNone(sealed["payload"])
        revealed = reveal_genesis_capsule(25)
        self.assertEqual(revealed["status"], "revealed")
        self.assertEqual(revealed["payload"]["creator"]["repository"], "QSOLKCB/QSOL-NEXUS")

    def test_capsule_fingerprint_and_authority_boundary_are_pinned(self) -> None:
        status = genesis_capsule_status(25)
        self.assertEqual(
            GENESIS_CAPSULE_SHA256,
            "728d6f70aa1e3438292733e3576b5dc02c786ed505357fb70df56bc46d9f87bc",
        )
        self.assertEqual(status["payload_sha256"], GENESIS_CAPSULE_SHA256)
        self.assertIn("no_extra_vote", status["authority_rule"])
        self.assertIn("no_root_authority", status["authority_rule"])


class PurgatoryTests(unittest.TestCase):
    def test_cursed_yaml_corpus_is_hash_bound_and_inert(self) -> None:
        policy = purgatory_policy_snapshot()
        self.assertEqual(policy["corpus_sha256"], PURGATORY_CORPUS_SHA256)
        self.assertIn("inert_text", policy["execution_rule"])
        self.assertIn("never_grants_access", policy["authorization_rule"])

    def test_exam_selection_is_deterministic_and_has_no_authorization_effect(self) -> None:
        args = {
            "actor_id": "synthetic-hostile-actor",
            "session_id": "trap-session-001",
            "epoch": 0,
            "constitution_hash": "constitution:abc123",
        }
        first = deterministic_exam_selection(**args)
        second = deterministic_exam_selection(**args)
        self.assertEqual(first, second)
        self.assertEqual(len(first["selected_chapters"]), 5)
        self.assertEqual(len(set(first["selected_chapters"])), 5)
        self.assertTrue(all(1 <= chapter <= 32 for chapter in first["selected_chapters"]))
        self.assertEqual(first["authorization_effect"], "none")
        self.assertEqual(first["quarantine_release_effect"], "none")


class EpochAPITests(unittest.TestCase):
    def test_health_and_operations_publish_epoch_capsule_and_purgatory(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertIn("compute_epoch", health)
        self.assertIn("genesis_capsule", health)
        self.assertIn("purgatory", health)
        self.assertEqual(health["council_chair"]["schema"], "nexus-council-chair/1")
        self.assertEqual(health["council_chair"]["epoch_schema"], "nexus-council-chair-epoch/1")

        operations = api.handle({"operation": "system.operations"})["operations"]
        self.assertIn("council.epoch.policy", operations)
        self.assertIn("council.epoch.verify", operations)
        self.assertIn("genesis.capsule.status", operations)
        self.assertIn("genesis.capsule.reveal", operations)
        self.assertIn("security.purgatory.policy", operations)
        self.assertIn("security.purgatory.select", operations)

    def test_council_run_gets_a_pinned_epoch_admission_receipt(self) -> None:
        api = NexusAPI()
        roster = [member("A", "a"), member("B", "b"), member("C", "c")]
        result = api.handle(
            {
                "operation": "council.run",
                "question": "Does compute scale change political authority?",
                "members": roster,
            }
        )
        self.assertEqual(result["status"], "ok", result)
        receipt_ref = result["epoch_admission_receipt_ref"]
        receipt = api.world.inspect(receipt_ref)
        self.assertEqual(receipt.object_type, EPOCH_ADMISSION_RECEIPT_TYPE)
        verified = api.handle(
            {"operation": "council.epoch.verify", "receipt_ref": receipt_ref}
        )
        self.assertEqual(verified["status"], "verified", verified)
        self.assertFalse(verified["replay_clock_used"])
        self.assertEqual(verified["vote_weight_per_seat"], 1)

    def test_public_world_create_cannot_forge_epoch_receipt(self) -> None:
        api = NexusAPI()
        result = api.handle(
            {
                "operation": "world.create",
                "object_type": EPOCH_ADMISSION_RECEIPT_TYPE,
                "payload": {},
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
