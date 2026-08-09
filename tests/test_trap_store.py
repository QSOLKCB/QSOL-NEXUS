from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from nexus_runtime.canonical import canonical_json
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.types import TrapError


class TrapStoreTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX permission semantics")
    def test_store_does_not_chmod_or_use_a_broad_existing_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-store-broad-") as temporary:
            root = Path(temporary) / "broad"
            root.mkdir(mode=0o755)
            os.chmod(root, 0o755)
            with self.assertRaises(TrapError) as caught:
                TrapStore(root)
            self.assertEqual(caught.exception.code, "trap_store_unavailable")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)

    def test_content_addressed_objects_are_immutable_defensive_copies(self) -> None:
        store = TrapStore()
        source = {"nested": {"values": [1, 2]}, "synthetic_context": True}
        created = store.create_object("trap_message", source, {"actor": "defender"})
        source["nested"]["values"].append(3)
        created.payload["nested"]["values"].append(4)

        inspected = store.inspect(created.object_id)
        self.assertRegex(created.object_id, r"^trap:[0-9a-f]{64}$")
        self.assertEqual(inspected.payload["nested"]["values"], [1, 2])
        inspected.payload["nested"]["values"].append(5)
        self.assertEqual(store.inspect(created.object_id).payload["nested"]["values"], [1, 2])

    def test_canonical_identity_is_stable_across_key_order_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = TrapStore(temp)
            left = first.create_object("trap_message", {"b": 2, "a": [1, 2]})
            right = first.create_object("trap_message", {"a": [1, 2], "b": 2})
            self.assertEqual(left.object_id, right.object_id)

            restarted = TrapStore(temp)
            self.assertEqual(restarted.inspect(left.object_id).as_dict(), left.as_dict())
            self.assertEqual(restarted.refs("trap_message"), [left.object_id])

    def test_real_and_bare_references_fail_at_trap_scope_boundary(self) -> None:
        store = TrapStore()
        with self.assertRaises(TrapError) as context:
            store.inspect("object:" + "a" * 64)
        self.assertEqual(context.exception.code, "trap_reference_scope_violation")

        for invalid in ("a" * 64, "trap:" + "A" * 64, "trap:../secret"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(TrapError) as invalid_context:
                    store.inspect(invalid)
                self.assertEqual(invalid_context.exception.code, "trap_invalid_reference")

    def test_unknown_object_types_and_noncanonical_values_fail_closed(self) -> None:
        store = TrapStore()
        with self.assertRaises(TrapError) as type_context:
            store.create_object("not_a_trap_type", {})
        self.assertEqual(type_context.exception.code, "trap_invalid_object_type")

        with self.assertRaises(TrapError) as value_context:
            store.create_object("trap_message", {"number": float("nan")})
        self.assertEqual(value_context.exception.code, "trap_invalid_object")

    def test_tampered_immutable_object_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = TrapStore(temp)
            created = store.create_object("trap_message", {"text": "synthetic only"})
            path = store.objects_dir / f"{created.object_id.removeprefix('trap:')}.json"  # type: ignore[operator]
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["payload"]["text"] = "tampered"
            path.write_text(canonical_json(raw) + "\n", encoding="utf-8")

            with self.assertRaises(TrapError) as context:
                TrapStore(temp).inspect(created.object_id)
            self.assertEqual(context.exception.code, "trap_store_corrupt")

    def test_invalid_object_filename_cannot_hide_in_durable_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = TrapStore(temp)
            path = store.objects_dir / "not-a-content-address.json"  # type: ignore[operator]
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(TrapError) as context:
                store.refs()
            self.assertEqual(context.exception.code, "trap_store_corrupt")


if __name__ == "__main__":
    unittest.main()
