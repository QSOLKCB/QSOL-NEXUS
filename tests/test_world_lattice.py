from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.wall_api import WallNexusAPI
from nexus_runtime.world_lattice import (
    LATTICE_PROFILE_FINGERPRINT,
    LATTICE_PROFILE_ID,
    WORLD_LATTICE_RESERVED_OBJECT_TYPES,
    WorldLatticeError,
    current_lattice_profile_descriptor,
    validate_lattice_migration_manifest,
    validate_lattice_profile_descriptor,
)


_FIXTURE = Path(__file__).parents[1] / "fixtures" / "lattice" / "nexus-consumer-v1.json"


class WorldLatticeTests(unittest.TestCase):
    @staticmethod
    def _api(base: Path) -> NexusAPI:
        return NexusAPI(
            base / "world",
            auth_root=base / "auth",
            trap_root=base / "trap",
            stenographer_root=base / "stenographer",
            guardian_root=base / "guardian",
        )

    @staticmethod
    def _fixture() -> dict[str, object]:
        return json.loads(_FIXTURE.read_text(encoding="utf-8"))

    def test_public_runtime_exposes_world_lattice_surface(self) -> None:
        self.assertIs(NexusAPI, WallNexusAPI)
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            operations = set(api.handle({"operation": "system.operations"})["operations"])
            self.assertTrue(
                {
                    "world.lattice.policy",
                    "world.lattice.validate_migration",
                    "world.place",
                    "world.move",
                    "world.migrate",
                    "world.presence",
                }.issubset(operations)
            )
            policy = api.handle({"operation": "world.lattice.policy"})["policy"]
            self.assertEqual(policy["lattice_profile"]["profile_id"], LATTICE_PROFILE_ID)
            self.assertEqual(
                policy["lattice_profile"]["profile_fingerprint"],
                LATTICE_PROFILE_FINGERPRINT,
            )
            self.assertFalse(policy["placement"]["automatic_semantic_coordinate_inference"])
            self.assertEqual(policy["authority_effect"], "none")
            self.assertEqual(api.handle({"operation": "system.health"})["world_lattice"]["status"], "ok")

    def test_fixture_round_trip_records_move_and_identity_preserving_migration(self) -> None:
        fixture = self._fixture()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            subject = api.world.create_object(
                "research_note",
                {"title": "one immutable subject"},
                {"actor": "test"},
            )
            placement = fixture["placement"]
            placed = api.handle(
                {
                    "operation": "world.place",
                    "object_ref": subject.object_id,
                    "region_id": placement["region_id"],
                    "lattice_reference": placement["lattice_reference"],
                }
            )
            self.assertEqual(placed["status"], "ok")
            placed_ref = placed["presence_event"]["object_id"]

            move = fixture["move"]
            moved = api.handle(
                {
                    "operation": "world.move",
                    "object_ref": subject.object_id,
                    "previous_presence_ref": placed_ref,
                    "region_id": move["region_id"],
                    "lattice_reference": move["lattice_reference"],
                }
            )
            self.assertEqual(moved["status"], "ok")
            moved_ref = moved["presence_event"]["object_id"]
            moved_detail = moved["presence_event"]["payload"]["transition_detail"]
            self.assertEqual(moved_detail["hop_distance"], 1)
            self.assertEqual(moved_detail["source_lattice_identity"]["address"], "L[0,0,0]")
            self.assertEqual(moved_detail["target_lattice_identity"]["address"], "L[2,0,2]")

            migrated = api.handle(
                {
                    "operation": "world.migrate",
                    "object_ref": subject.object_id,
                    "previous_presence_ref": moved_ref,
                    "migration_manifest": fixture["migration"],
                }
            )
            self.assertEqual(migrated["status"], "ok")
            migrated_ref = migrated["presence_event"]["object_id"]
            detail = migrated["presence_event"]["payload"]["transition_detail"]
            expected = fixture["expected"]
            self.assertEqual(detail["migrated_reference"]["source_identity"], expected["source_lattice_identity"])
            self.assertEqual(detail["migrated_reference"]["target_identity"], expected["target_lattice_identity"])
            self.assertTrue(detail["region_unchanged"])

            # Re-open the public runtime on disk. World-presence events are ordinary
            # immutable WorldStore objects, so continuity persistence recovers them
            # without a second bespoke database or a mutable position rewrite.
            reopened = self._api(base)
            presence = reopened.handle({"operation": "world.presence", "event_ref": migrated_ref})
            self.assertEqual(presence["status"], "ok")
            self.assertEqual(presence["presence"]["lineage_length"], 3)
            self.assertEqual(presence["presence"]["current"]["region_id"], expected["region_after_migration"])
            self.assertEqual(
                presence["presence"]["current"]["lattice_identity"],
                expected["target_lattice_identity"],
            )
            self.assertFalse(presence["presence"]["branching_uniqueness_claimed"])
            self.assertEqual(presence["presence"]["authority_effect"], "none")

            ark = base / "NEXUS-LATTICE-ARK"
            created = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created["verified"])
            restored_root = base / "restored-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")
            restored_api = NexusAPI(
                restored_root,
                auth_root=base / "restored-auth",
                trap_root=base / "restored-trap",
                stenographer_root=base / "restored-stenographer",
                guardian_root=base / "restored-guardian",
            )
            restored_presence = restored_api.handle(
                {"operation": "world.presence", "event_ref": migrated_ref}
            )
            self.assertEqual(restored_presence["status"], "ok")
            self.assertEqual(restored_presence["presence"]["lineage_length"], 3)
            self.assertEqual(
                restored_presence["presence"]["current"]["lattice_identity"],
                expected["target_lattice_identity"],
            )

    def test_unknown_major_and_semantic_fingerprint_drift_fail_closed(self) -> None:
        unknown = current_lattice_profile_descriptor()
        unknown["profile_id"] = "qsol-3x3x3-sierpinski-derived-memory/2"
        with self.assertRaises(WorldLatticeError) as caught:
            validate_lattice_profile_descriptor(unknown)
        self.assertEqual(caught.exception.code, "world_lattice_profile_unsupported")

        drifted = current_lattice_profile_descriptor()
        drifted["profile_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaises(WorldLatticeError) as caught:
            validate_lattice_profile_descriptor(drifted)
        self.assertEqual(caught.exception.code, "world_lattice_profile_drift")

    def test_additive_profile_metadata_is_compatible(self) -> None:
        report = validate_lattice_profile_descriptor(
            current_lattice_profile_descriptor(
                {"consumer": "QSOL-NEXUS", "description": "non-semantic metadata only"}
            )
        )
        self.assertEqual(report["status"], "compatible")
        self.assertEqual(report["compatibility"], "additive-metadata")

    def test_migration_rejects_duplicate_sources_identity_rewrite_and_false_preservation(self) -> None:
        valid = self._fixture()["migration"]

        duplicate = deepcopy(valid)
        duplicate["mappings"].append(deepcopy(duplicate["mappings"][0]))
        with self.assertRaises(WorldLatticeError):
            validate_lattice_migration_manifest(duplicate)

        identity_rewrite = deepcopy(valid)
        identity_rewrite["mode"] = "identity"
        with self.assertRaises(WorldLatticeError):
            validate_lattice_migration_manifest(identity_rewrite)

        destructive = deepcopy(valid)
        destructive["preserve_source_identity"] = False
        with self.assertRaises(WorldLatticeError):
            validate_lattice_migration_manifest(destructive)

    def test_world_move_is_one_explicit_adjacent_transition(self) -> None:
        fixture = self._fixture()
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            subject = api.world.create_object("note", {"n": 1}, {"actor": "test"})
            placement = fixture["placement"]
            placed = api.handle(
                {
                    "operation": "world.place",
                    "object_ref": subject.object_id,
                    "region_id": placement["region_id"],
                    "lattice_reference": placement["lattice_reference"],
                }
            )
            response = api.handle(
                {
                    "operation": "world.move",
                    "object_ref": subject.object_id,
                    "previous_presence_ref": placed["presence_event"]["object_id"],
                    "region_id": "upside_down",
                    "lattice_reference": fixture["move"]["lattice_reference"],
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "world_lattice_move_invalid")

    def test_content_ref_cannot_be_relabelled_from_nexus_object_id(self) -> None:
        fixture = self._fixture()
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            subject = api.world.create_object("note", {"n": 2}, {"actor": "test"})
            reference = deepcopy(fixture["placement"]["lattice_reference"])
            reference["content_ref"] = "sha256:" + subject.object_id.removeprefix("object:")
            result = api.handle(
                {
                    "operation": "world.place",
                    "object_ref": subject.object_id,
                    "region_id": "observatory",
                    "lattice_reference": reference,
                }
            )
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error"]["code"], "world_lattice_content_mismatch")

    def test_reserved_presence_object_types_cannot_bypass_validated_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in WORLD_LATTICE_RESERVED_OBJECT_TYPES:
                with self.subTest(object_type=object_type):
                    response = api.handle(
                        {
                            "operation": "world.create",
                            "object_type": object_type,
                            "payload": {"forged": True},
                        }
                    )
                    self.assertEqual(response["status"], "error")
                    self.assertEqual(response["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
