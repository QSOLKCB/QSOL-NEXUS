from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from nexus_runtime.canonical import canonical_json
from nexus_runtime.trap.incident import TrapIncidentRegistry
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.types import DecoyAdmissionRequest, IncidentState, TrapError


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        "operator_requested_trap_demo",
        "llama3.1:8b-instruct-q4_K_M",
        "fake-datacenter",
    )


class TrapIncidentTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX symbolic-link semantics")
    def test_index_lock_symbolic_link_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = TrapStore(root)
            target = root / "target"
            target.write_text("do-not-touch", encoding="utf-8")
            (root / "trap-index.lock").symlink_to(target)
            with self.assertRaises(TrapError) as caught:
                TrapIncidentRegistry(store)
            self.assertEqual(caught.exception.code, "trap_index_unavailable")
            self.assertEqual(target.read_text(encoding="utf-8"), "do-not-touch")

    def test_closed_state_machine_persists_contiguous_immutable_lineage(self) -> None:
        store = TrapStore()
        registry = TrapIncidentRegistry(store)
        root = registry.create(request())
        incident_id = root.payload["incident_id"]
        validated = registry.transition(incident_id, IncidentState.VALIDATED)
        activating = registry.transition(incident_id, IncidentState.ACTIVATING)
        active = registry.transition(incident_id, IncidentState.ACTIVE)

        self.assertEqual(root.payload["sequence"], 0)
        self.assertEqual(active.payload["sequence"], 3)
        self.assertEqual(active.payload["previous_state_ref"], activating.object_id)
        self.assertEqual(active.payload["root_state_ref"], root.object_id)
        self.assertEqual(registry.active_incident().object_id, active.object_id)  # type: ignore[union-attr]
        self.assertEqual(len(store.refs("trap_incident")), 4)
        self.assertEqual(validated.payload["trigger_reason"], "operator_requested_trap_demo")

    def test_illegal_transition_fails_without_creating_an_object(self) -> None:
        store = TrapStore()
        registry = TrapIncidentRegistry(store)
        root = registry.create(request())
        before = store.refs("trap_incident")
        with self.assertRaises(TrapError) as context:
            registry.transition(root.payload["incident_id"], IncidentState.ACTIVE)
        self.assertEqual(context.exception.code, "trap_invalid_state_transition")
        self.assertEqual(store.refs("trap_incident"), before)

    def test_transition_reason_and_details_reject_secret_material(self) -> None:
        for field in ("reason", "details"):
            with self.subTest(field=field):
                registry = TrapIncidentRegistry(TrapStore())
                root = registry.create(request())
                canary = "xai-" + "Z" * 40
                arguments = {field: canary if field == "reason" else {"value": canary}}
                with self.assertRaises(TrapError) as caught:
                    registry.transition(
                        root.payload["incident_id"],
                        IncidentState.VALIDATED,
                        **arguments,
                    )
                self.assertIn(caught.exception.code, {"trap_invalid_transition_reason", "trap_invalid_transition_details"})

    def test_only_one_open_incident_exists_and_second_trigger_changes_nothing(self) -> None:
        store = TrapStore()
        registry = TrapIncidentRegistry(store)
        first = registry.create(request())
        before = registry.snapshot()
        before_refs = store.refs()
        with self.assertRaises(TrapError) as context:
            registry.create(
                DecoyAdmissionRequest(
                    "synthetic_hostile_actor_fixture",
                    "mistral:7b",
                    "trout-tribunal",
                )
            )
        self.assertEqual(context.exception.code, "trap_incident_already_active")
        self.assertEqual(registry.snapshot()["active_incident_id"], first.payload["incident_id"])
        self.assertEqual(registry.snapshot()["incidents"], before["incidents"])
        self.assertEqual(store.refs(), before_refs)

    def test_identical_request_after_close_gets_a_new_incident_identity(self) -> None:
        registry = TrapIncidentRegistry(TrapStore())
        first = registry.create(request())
        first_id = first.payload["incident_id"]
        registry.transition(first_id, IncidentState.ACTIVATION_FAILED, reason="fixture")
        registry.transition(first_id, IncidentState.CLOSED)
        second = registry.create(request())
        self.assertNotEqual(second.payload["incident_id"], first_id)

    def test_malformed_index_is_rebuilt_from_immutable_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = TrapStore(temp)
            registry = TrapIncidentRegistry(store)
            root = registry.create(request())
            incident_id = root.payload["incident_id"]
            latest = registry.transition(incident_id, IncidentState.VALIDATED)
            registry.index_path.write_text("not-json\n", encoding="utf-8")  # type: ignore[union-attr]

            restarted = TrapIncidentRegistry(TrapStore(temp))
            self.assertEqual(restarted.latest_ref(incident_id), latest.object_id)
            raw = json.loads(restarted.index_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            self.assertEqual(raw["incidents"][incident_id], latest.object_id)

    def test_index_rollback_to_valid_earlier_state_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = TrapIncidentRegistry(TrapStore(temp))
            root = registry.create(request())
            incident_id = root.payload["incident_id"]
            earlier = registry.transition(incident_id, IncidentState.VALIDATED)
            latest = registry.transition(incident_id, IncidentState.ACTIVATING)
            registry.index_path.write_text(  # type: ignore[union-attr]
                canonical_json(
                    {
                        "schema_version": "nexus-trap-index/1",
                        "incidents": {incident_id: earlier.object_id},
                        "active_incident_id": incident_id,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            restarted = TrapIncidentRegistry(TrapStore(temp))
            self.assertEqual(restarted.latest_ref(incident_id), latest.object_id)
            cached = json.loads(restarted.index_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            self.assertEqual(cached["incidents"][incident_id], latest.object_id)

    def test_cross_incident_lineage_is_a_hard_failure(self) -> None:
        store = TrapStore()
        registry = TrapIncidentRegistry(store)
        first = registry.create(request())
        first_id = first.payload["incident_id"]
        registry.transition(first_id, IncidentState.ACTIVATION_FAILED)
        registry.transition(first_id, IncidentState.CLOSED)
        second = registry.create(
            DecoyAdmissionRequest(
                "synthetic_hostile_actor_fixture",
                "mistral:7b",
                "trout-tribunal",
            )
        )
        store.create_object(
            "trap_incident",
            {
                "schema_version": "nexus-trap-incident/1",
                "incident_id": second.payload["incident_id"],
                "trigger_reason": second.payload["trigger_reason"],
                "subject_model": second.payload["subject_model"],
                "scenario_id": second.payload["scenario_id"],
                "state": "VALIDATED",
                "sequence": 1,
                "previous_state_ref": first.object_id,
                "root_state_ref": second.object_id,
                "reason": None,
                "details": {},
            },
            {"actor": "malicious_fixture"},
        )
        with self.assertRaises(TrapError) as context:
            registry.refresh()
        self.assertEqual(context.exception.code, "trap_incident_lineage_corrupt")


if __name__ == "__main__":
    unittest.main()
