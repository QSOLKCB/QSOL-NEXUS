from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from nexus_runtime import NexusAPI, WorldContinuityNexusAPI
from nexus_runtime.canonical import canonical_json, sha256_ref
from nexus_runtime.civilization_api import CivilizationNexusAPI
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

    @staticmethod
    def _rewrite_ark_manifest(ark: Path, raw: dict[str, object]) -> None:
        body = {key: value for key, value in raw.items() if key != "ark_ref"}
        raw["ark_ref"] = sha256_ref("world-ark", body)
        manifest = ark / "ARK_MANIFEST.json"
        manifest.write_text(canonical_json(raw) + "\n", encoding="utf-8")
        files = raw["files"]
        assert isinstance(files, dict)
        checksum = ark / "SHA256SUMS"
        checksum.write_text(
            "\n".join(
                f"{digest}  {name}"
                for name, digest in sorted(files.items())
            )
            + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            manifest.chmod(0o600)
            checksum.chmod(0o600)

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

    def test_existing_continuity_with_missing_head_fails_closed_instead_of_rebaseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "world"
            store = ContinuityWorldStore(root)
            committed = store.create_object("note", {"n": 1}, {"actor": "test"})
            head = store._head_path(root)
            head.unlink()
            orphan = WorldStore(root).create_object(
                "orphan",
                {"must_not_become_history": True},
                {"actor": "failed_commit"},
            )
            with self.assertRaises(WorldContinuityError) as caught:
                ContinuityWorldStore(root)
            self.assertEqual(caught.exception.code, "world_continuity_no_quorum")
            self.assertNotEqual(committed.object_id, orphan.object_id)

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

    def test_failed_head_publication_restores_previous_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(
                root / "primary",
                replica_roots=[root / "a", root / "b", root / "c"],
                write_quorum=3,
            )
            old_head = store.status()["recognized_head_ref"]
            original_write_head = store._write_head
            failing_roots = {
                store._replicas[2].state.root,
                store._replicas[3].state.root,
            }

            def flaky(root_path: Path, manifest_ref: str) -> None:
                if manifest_ref != old_head and root_path in failing_roots:
                    raise OSError("simulated HEAD publication failure")
                original_write_head(root_path, manifest_ref)

            with mock.patch.object(store, "_write_head", side_effect=flaky):
                with self.assertRaises(WorldContinuityError) as caught:
                    store.create_object("note", {"n": 2}, {"actor": "test"})
            self.assertEqual(caught.exception.code, "world_continuity_head_quorum_unavailable")
            observations = store._head_observations()
            self.assertGreaterEqual(
                sum(value == old_head for value in observations.values()),
                store.write_quorum,
            )
            self.assertEqual(store.status()["recognized_head_ref"], old_head)

    def test_cached_history_is_revalidated_before_new_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            store.create_object("note", {"n": 1}, {"actor": "test"})
            head_ref = store.status()["recognized_head_ref"]
            _, manifest_refs = store._history(head_ref)
            predecessor = manifest_refs[0]
            for replica in store._replicas:
                store._manifest_path(replica.state.root, predecessor).unlink()
            with self.assertRaises(WorldContinuityError) as caught:
                store.create_object("note", {"n": 2}, {"actor": "test"})
            self.assertIn(
                caught.exception.code,
                {"world_continuity_corrupt", "world_continuity_degraded_read_only"},
            )
            observations = store._head_observations()
            self.assertTrue(all(value == head_ref for value in observations.values()))

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

    def test_observational_scrub_reports_degraded_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._replicated(Path(temporary))
            obj = store.create_object("note", {"n": 6}, {"actor": "test"})
            damaged = store._replicas[-1]
            path = damaged.store.objects_dir / f"{obj.object_id.removeprefix('object:')}.json"
            path.write_text("{}\n", encoding="utf-8")
            if os.name != "nt":
                path.chmod(0o600)

            report = store.scrub(repair=False)
            self.assertEqual(report["status"], "degraded")
            self.assertGreater(report["defect_count"], 0)
            self.assertEqual(report["repair_count"], 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")

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

    def test_ark_destination_must_be_disjoint_from_worldstore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            world = root / "world"
            store = ContinuityWorldStore(world)
            store.create_object("note", {"n": 1}, {"actor": "test"})
            destination = world / "objects" / "ark"
            with self.assertRaises(WorldContinuityError) as caught:
                store.create_ark(destination)
            self.assertEqual(caught.exception.code, "world_ark_storage_overlap")
            reopened = ContinuityWorldStore(world)
            self.assertEqual(reopened.status()["status"], "healthy")

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

    def test_ark_manifest_cannot_omit_object_referenced_by_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(root / "world")
            first = store.create_object("note", {"n": 1}, {"actor": "test"})
            store.create_object("note", {"n": 2}, {"actor": "test"})
            ark = root / "ark"
            store.create_ark(ark, compute_epoch=0)

            manifest_path = ark / "ARK_MANIFEST.json"
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw["object_refs"].remove(first.object_id)
            object_name = f"objects/{first.object_id.removeprefix('object:')}.json"
            raw["files"].pop(object_name)
            (ark / object_name).unlink()
            self._rewrite_ark_manifest(ark, raw)

            with self.assertRaisesRegex(WorldContinuityError, "continuity chain"):
                store.verify_ark(ark)

    def test_ark_checksum_paths_cannot_escape_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(root / "world")
            store.create_object("note", {"n": 1}, {"actor": "test"})
            ark = root / "ark"
            store.create_ark(ark, compute_epoch=0)
            outside = root / "outside.txt"
            outside.write_text("not part of the ark\n", encoding="utf-8")

            manifest_path = ark / "ARK_MANIFEST.json"
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw["files"]["../outside.txt"] = hashlib.sha256(outside.read_bytes()).hexdigest()
            self._rewrite_ark_manifest(ark, raw)
            with self.assertRaises(WorldContinuityError):
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

    def test_trap_mutation_gate_blocks_continuity_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                stenographer_root=root / "stenographer",
                guardian_root=root / "guardian",
            )
            created = api.handle(
                {"operation": "world.create", "object_type": "note", "payload": {"n": 1}}
            )
            object_ref = created["object"]["object_id"]
            owner = "incident-" + "0" * 64
            api.trap_mutation_gate.acquire(owner)
            try:
                migration = api.handle(
                    {
                        "operation": "world.continuity.migration.receipt",
                        "object_ref": object_ref,
                    }
                )
                self.assertEqual(migration["error"]["code"], "trap_incident_active")
                ark = root / "blocked-ark"
                ark_response = api.handle(
                    {"operation": "world.ark.create", "destination": str(ark)}
                )
                self.assertEqual(ark_response["error"]["code"], "trap_incident_active")
                self.assertFalse(ark.exists())
                scrub = api.handle(
                    {"operation": "world.continuity.scrub", "repair": True}
                )
                self.assertEqual(scrub["error"]["code"], "trap_incident_active")
            finally:
                api.trap_mutation_gate.release(owner)

    def test_context_scoped_worldstore_factory_does_not_leak_to_historical_api(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entered = threading.Event()
            release = threading.Event()
            original_init = ContinuityWorldStore.__init__

            def slow_init(instance, *args, **kwargs):
                entered.set()
                if not release.wait(timeout=10):
                    raise RuntimeError("test synchronization timed out")
                original_init(instance, *args, **kwargs)

            def build_continuity() -> NexusAPI:
                return NexusAPI(
                    root / "continuity-world",
                    world_replica_roots=[root / "mirror-a", root / "mirror-b"],
                    world_write_quorum=2,
                    auth_root=root / "auth-a",
                    trap_root=root / "trap-a",
                    stenographer_root=root / "steno-a",
                    guardian_root=root / "guardian-a",
                )

            with mock.patch.object(ContinuityWorldStore, "__init__", new=slow_init):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    continuity_future = pool.submit(build_continuity)
                    self.assertTrue(entered.wait(timeout=10))
                    historical = CivilizationNexusAPI(
                        root / "historical-world",
                        auth_root=root / "auth-b",
                        trap_root=root / "trap-b",
                        stenographer_root=root / "steno-b",
                    )
                    self.assertIs(type(historical.world), WorldStore)
                    release.set()
                    continuity = continuity_future.result(timeout=20)
                    self.assertIsInstance(continuity.world, ContinuityWorldStore)

    def test_inherited_world_operations_preserve_continuity_error_codes(self) -> None:
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
                {"operation": "world.create", "object_type": "note", "payload": {"n": 1}}
            )
            object_ref = created["object"]["object_id"]
            for replica in api.world._replicas[:2]:
                path = replica.store.objects_dir / f"{object_ref.removeprefix('object:')}.json"
                path.write_text("{}\n", encoding="utf-8")
                if os.name != "nt":
                    path.chmod(0o600)
            inspected = api.handle({"operation": "world.inspect", "object_ref": object_ref})
            self.assertEqual(
                inspected["error"]["code"],
                "world_continuity_read_quorum_unavailable",
            )

            # Restore the object, then force only one replica write to succeed.
            api.world.scrub(repair=True)
            original_base_create = api.world._base_create
            allowed_store = api.world._replicas[0].store

            def one_replica_only(store, object_type, payload, provenance):
                if store is not allowed_store:
                    raise OSError("simulated replica outage")
                return original_base_create(store, object_type, payload, provenance)

            with mock.patch.object(api.world, "_base_create", side_effect=one_replica_only):
                failed_write = api.handle(
                    {"operation": "world.create", "object_type": "note", "payload": {"n": 2}}
                )
            self.assertEqual(
                failed_write["error"]["code"],
                "world_continuity_write_quorum_unavailable",
            )

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
