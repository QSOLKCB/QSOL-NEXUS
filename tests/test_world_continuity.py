from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI, WorldContinuityNexusAPI
from nexus_runtime.canonical import sha256_ref
from nexus_runtime.world import WorldStore
from nexus_runtime.world_continuity import (
    CONTINUITY_SCHEMA_VERSION,
    MIGRATION_OBJECT_TYPE,
    ContinuityWorldStore,
    WorldContinuityError,
)


class WorldContinuityTests(unittest.TestCase):
    def _replicated(self, root: Path) -> ContinuityWorldStore:
        return ContinuityWorldStore(
            root / "primary",
            replica_roots=[root / "mirror-a", root / "mirror-b"],
            write_quorum=2,
        )

    def test_legacy_world_is_baselined_without_changing_object_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            legacy = WorldStore(root)
            original = legacy.create_object(
                "legacy_note",
                {"message": "already here"},
                {"actor": "legacy"},
            )
            continuity = ContinuityWorldStore(root)
            loaded = continuity.inspect(original.object_id)
            self.assertEqual(loaded.as_dict(), original.as_dict())
            status = continuity.status()
            self.assertEqual(status["generation"], 0)
            self.assertEqual(status["recognized_object_count"], 1)

    def test_three_replica_quorum_writes_and_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            obj = store.create_object("note", {"n": 1}, {"actor": "test"})
            self.assertEqual(store.inspect(obj.object_id).as_dict(), obj.as_dict())
            status = store.status()
            self.assertEqual(status["replica_count"], 3)
            self.assertEqual(status["write_quorum"], 2)
            self.assertEqual(status["generation"], 1)
            self.assertEqual(status["head_quorum_support"], 3)
            for replica in store._replicas:
                path = replica.store.objects_dir / f"{obj.object_id.removeprefix('object:')}.json"
                self.assertTrue(path.is_file())

    def test_quorum_beats_lone_newer_replica(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            obj = store.create_object("note", {"n": 1}, {"actor": "test"})
            old_head = store.status()["recognized_head_ref"]
            old_manifest = store._read_manifest(store._replicas[0].state.root, old_head)
            body = {
                "schema_version": CONTINUITY_SCHEMA_VERSION,
                "generation": old_manifest["generation"] + 1,
                "previous_manifest_ref": old_head,
                "event_type": "object_commit",
                "inventory_refs": [],
                "object_ref": obj.object_id,
                "write_quorum": 2,
                "replica_ids": [item.state.replica_id for item in store._replicas],
                "digest_policy": {"object_identity": "sha256", "continuity_identity": "sha256"},
                "authority_effect": "none",
            }
            fake_ref = sha256_ref("world-manifest", body)
            lone = store._replicas[-1]
            store._write_immutable(
                store._manifest_path(lone.state.root, fake_ref),
                {"manifest_ref": fake_ref, **body},
            )
            store._write_head(lone.state.root, fake_ref)

            status = store.status()
            self.assertEqual(status["recognized_head_ref"], old_head)
            self.assertEqual(status["head_quorum_support"], 2)

    def test_concurrent_instances_share_one_manifest_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._replicated(root)
            second = ContinuityWorldStore(
                root / "primary",
                replica_roots=[root / "mirror-a", root / "mirror-b"],
                write_quorum=2,
            )

            def create(store: ContinuityWorldStore, value: int) -> str:
                return store.create_object("race", {"value": value}, {"actor": "test"}).object_id

            with ThreadPoolExecutor(max_workers=2) as pool:
                refs = list(pool.map(lambda pair: create(*pair), [(first, 1), (second, 2)]))

            reopened = self._replicated(root)
            status = reopened.status()
            self.assertEqual(status["generation"], 2)
            for ref in refs:
                self.assertEqual(reopened.inspect(ref).object_id, ref)

    def test_scrub_repairs_one_corrupt_replica_and_emits_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            obj = store.create_object("note", {"n": 7}, {"actor": "test"})
            damaged = store._replicas[-1]
            path = damaged.store.objects_dir / f"{obj.object_id.removeprefix('object:')}.json"
            path.write_text("{}\n", encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o600)

            report = store.scrub(repair=True)
            self.assertEqual(report["status"], "repaired")
            self.assertTrue(report["repair_receipt_ref"].startswith("world-repair:"))
            self.assertGreaterEqual(report["repair_count"], 1)
            self.assertEqual(
                WorldStore._read_validated(obj.object_id, path).as_dict(),
                obj.as_dict(),
            )

    def test_zero_known_good_object_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            obj = store.create_object("note", {"n": 9}, {"actor": "test"})
            for replica in store._replicas:
                path = replica.store.objects_dir / f"{obj.object_id.removeprefix('object:')}.json"
                path.write_text("{}\n", encoding="utf-8")
                if os.name != "nt":
                    path.chmod(0o600)
            report = store.scrub(repair=True)
            self.assertEqual(report["status"], "unrecoverable")
            self.assertIn(obj.object_id, report["unrecoverable_refs"])
            with self.assertRaisesRegex(WorldContinuityError, "read quorum"):
                store.inspect(obj.object_id)

    def test_ark_is_self_verifying_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(root / "world")
            obj = store.create_object("note", {"message": "ark me"}, {"actor": "test"})
            ark = root / "NEXUS-ARK-000001"
            created = store.create_ark(ark, compute_epoch=0)
            self.assertTrue(created["verified"])
            verified = store.verify_ark(ark)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["compute_epoch"], 0)

            object_path = ark / "objects" / f"{obj.object_id.removeprefix('object:')}.json"
            object_path.write_text("{}\n", encoding="utf-8")
            if os.name != "nt":
                object_path.chmod(0o600)
            with self.assertRaisesRegex(WorldContinuityError, "failed verification"):
                store.verify_ark(ark)

    def test_recovery_restores_to_new_target_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(root / "world")
            obj = store.create_object("note", {"message": "survive"}, {"actor": "test"})
            ark = root / "ark"
            store.create_ark(ark, compute_epoch=0)
            target = root / "restored"
            restored = store.restore_ark(ark, target)
            self.assertEqual(restored["status"], "restored")
            recovered_store = ContinuityWorldStore(target)
            self.assertEqual(recovered_store.inspect(obj.object_id).as_dict(), obj.as_dict())
            with self.assertRaisesRegex(WorldContinuityError, "new path"):
                store.restore_ark(ark, target)

    def test_migration_receipt_is_additive_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = ContinuityWorldStore(Path(temporary) / "world")
            obj = store.create_object("note", {"message": "old bytes stay"}, {"actor": "test"})
            receipt = store.create_migration_receipt(obj.object_id)
            self.assertEqual(receipt.object_type, MIGRATION_OBJECT_TYPE)
            self.assertEqual(receipt.payload["source_object_ref"], obj.object_id)
            self.assertTrue(receipt.payload["source_bytes_preserved"])
            self.assertEqual(store.inspect(obj.object_id).as_dict(), obj.as_dict())

    def test_public_runtime_alias_exposes_continuity_operations(self) -> None:
        self.assertIs(NexusAPI, WorldContinuityNexusAPI)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                stenographer_root=root / "stenographer",
                guardian_root=root / "guardian",
            )
            operations = api.handle({"operation": "system.operations"})
            self.assertIn("world.continuity.status", operations["operations"])
            self.assertIn("world.ark.create", operations["operations"])
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["world_continuity"]["status"], "ok")

    def test_public_world_create_cannot_forge_migration_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                stenographer_root=root / "stenographer",
                guardian_root=root / "guardian",
            )
            response = api.handle(
                {
                    "operation": "world.create",
                    "object_type": MIGRATION_OBJECT_TYPE,
                    "payload": {},
                }
            )
            self.assertEqual(response["status"], "error")

    def test_runtime_scrub_repair_records_guardian_scar_without_granting_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                world_replica_roots=[root / "mirror-a", root / "mirror-b"],
                world_write_quorum=2,
                auth_root=root / "auth",
                trap_root=root / "trap",
                stenographer_root=root / "stenographer",
                guardian_root=root / "guardian",
            )
            created = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "note",
                    "payload": {"message": "repair me"},
                }
            )
            object_ref = created["object"]["object_id"]
            damaged = api.world._replicas[-1]
            path = damaged.store.objects_dir / f"{object_ref.removeprefix('object:')}.json"
            path.write_text("{}\n", encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o600)

            response = api.handle({"operation": "world.continuity.scrub", "repair": True})
            self.assertEqual(response["status"], "ok")
            self.assertEqual(response["scrub"]["status"], "repaired")
            self.assertIsNotNone(response["guardian_scar_ref"])
            self.assertFalse(response["guardian_storage_authority"])


if __name__ == "__main__":
    unittest.main()
