from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nexus_runtime.canonical import canonical_json
from nexus_runtime.trap.gate import CouncilMutationGate, DecoyGate
from nexus_runtime.trap.incident import TrapIncidentRegistry
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.types import DecoyAdmissionRequest, IncidentState, TrapError


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        "synthetic_decoy_credential_fixture",
        "llama3.1:8b",
        "fake-admin-console",
    )


class CouncilMutationGateTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX symbolic-link semantics")
    def test_lock_file_symbolic_link_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.write_text("do-not-touch", encoding="utf-8")
            gate = CouncilMutationGate(root / "lock")
            (root / "lock" / "council-mutation-gate.lock").symlink_to(target)
            with self.assertRaises(TrapError) as caught:
                gate.status()
            self.assertEqual(caught.exception.code, "trap_mutation_gate_unavailable")
            self.assertEqual(target.read_text(encoding="utf-8"), "do-not-touch")

    def test_only_owner_can_release_persistent_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            owner = "incident-" + "a" * 64
            other = "incident-" + "b" * 64
            gate = CouncilMutationGate(temp)
            self.assertEqual(
                gate.acquire(owner),
                {"locked": True, "owner": owner, "reason": "trap_base_active"},
            )
            restarted = CouncilMutationGate(temp)
            with self.assertRaises(TrapError) as context:
                restarted.release(other)
            self.assertEqual(context.exception.code, "trap_mutation_lock_not_owner")
            self.assertTrue(restarted.is_locked)
            with self.assertRaises(TrapError) as mutation_context:
                restarted.assert_mutation_allowed()
            self.assertEqual(mutation_context.exception.code, "trap_incident_active")
            restarted.release(owner)
            restarted.assert_mutation_allowed()

    def test_recovery_release_requires_validated_lineage(self) -> None:
        owner = "incident-" + "a" * 64
        gate = CouncilMutationGate()
        gate.acquire(owner)
        with self.assertRaises(TrapError) as context:
            gate.force_release(owner, lineage_validator=lambda _owner: False)
        self.assertEqual(context.exception.code, "trap_recovery_lineage_invalid")
        self.assertTrue(gate.is_locked)


class DecoyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = TrapStore()
        self.registry = TrapIncidentRegistry(self.store)
        self.mutations = CouncilMutationGate()
        self.gate = DecoyGate(self.registry, self.mutations)

    def test_begin_and_publish_active_acquire_real_mutation_lock(self) -> None:
        activating = self.gate.begin_activation(request())
        incident_id = activating.payload["incident_id"]
        self.assertEqual(activating.payload["state"], "ACTIVATING")
        self.assertEqual(self.mutations.owner, incident_id)
        active = self.gate.publish_active(incident_id)
        self.assertEqual(active.payload["state"], "ACTIVE")
        with self.assertRaises(TrapError):
            self.mutations.assert_mutation_allowed()

    def test_second_trigger_does_not_create_or_extend_incident(self) -> None:
        active = self.gate.publish_active(self.gate.begin_activation(request()).payload["incident_id"])
        before_refs = self.store.refs()
        with self.assertRaises(TrapError) as context:
            self.gate.begin_activation(
                DecoyAdmissionRequest(
                    "operator_requested_trap_demo",
                    "mistral:7b",
                    "yaml-purgatory",
                )
            )
        self.assertEqual(context.exception.code, "trap_incident_already_active")
        self.assertEqual(self.store.refs(), before_refs)
        self.assertEqual(self.registry.active_incident().object_id, active.object_id)  # type: ignore[union-attr]

    def test_unknown_trigger_and_smuggled_request_fail_before_persistence(self) -> None:
        with self.assertRaises(TrapError) as context:
            DecoyAdmissionRequest("invalid-normal-credential", "llama3:8b", "fake-datacenter")
        self.assertEqual(context.exception.code, "trap_invalid_trigger_reason")
        self.assertEqual(self.store.refs(), [])

    def test_subject_model_rejects_path_traversal_shapes(self) -> None:
        for model_id in (
            "model/../../private",
            "model//override",
            "model/",
            "xai-" + "Z" * 40,
        ):
            with self.subTest(model_id=model_id):
                with self.assertRaises(TrapError) as caught:
                    DecoyAdmissionRequest(
                        "synthetic_hostile_actor_fixture",
                        model_id,
                        "fake-datacenter",
                    )
                self.assertEqual(caught.exception.code, "trap_invalid_subject_model")

        @dataclass(frozen=True)
        class SmuggledRequest(DecoyAdmissionRequest):
            credential: str = "synthetic-canary-that-must-not-cross"

        with self.assertRaises(TrapError) as smuggled_context:
            self.gate.begin_activation(
                SmuggledRequest(
                    "operator_requested_trap_demo",
                    "llama3:8b",
                    "fake-datacenter",
                )
            )
        self.assertEqual(smuggled_context.exception.code, "trap_invalid_admission_request")
        self.assertEqual(self.store.refs(), [])

    def test_incident_objects_store_reason_code_and_never_credential_material(self) -> None:
        canary = "NEXUS-DECOY-CREDENTIAL-CANARY-DO-NOT-PERSIST"
        self.gate.begin_activation(request())
        serialized = canonical_json([obj.as_dict() for obj in self.store.iter_objects()])
        self.assertNotIn(canary, serialized)
        self.assertIn("synthetic_decoy_credential_fixture", serialized)

    def test_activation_failure_after_lock_acquisition_releases_lock_and_is_bounded(self) -> None:
        original_transition = self.registry.transition

        def injected_transition(incident_id, new_state, **kwargs):
            if new_state == IncidentState.ACTIVATING:
                raise RuntimeError("injected activation failure")
            return original_transition(incident_id, new_state, **kwargs)

        with patch.object(self.registry, "transition", side_effect=injected_transition):
            with self.assertRaisesRegex(RuntimeError, "injected activation failure"):
                self.gate.begin_activation(request())
        self.assertFalse(self.mutations.is_locked)
        self.assertIsNone(self.registry.active_incident())
        state = next(iter(self.registry.snapshot()["incidents"].values()))
        self.assertEqual(state["state"], "ACTIVATION_FAILED")

    def test_emergency_close_is_quorum_free_and_restores_mutation(self) -> None:
        active = self.gate.publish_active(self.gate.begin_activation(request()).payload["incident_id"])
        closed = self.gate.emergency_close(active.payload["incident_id"])
        self.assertEqual(closed.payload["state"], "OPERATOR_ABORTED")  # type: ignore[union-attr]
        self.assertFalse(self.mutations.is_locked)
        self.mutations.assert_mutation_allowed()

    def test_health_status_is_bounded_and_nonsecret(self) -> None:
        self.gate.begin_activation(request())
        self.assertEqual(
            self.gate.health_status(),
            {
                "supported": True,
                "active": True,
                "schema_version": "nexus-trap-incident/1",
                "max_active_incidents": 1,
                "subject_backend": "ollama_local_only_v1",
            },
        )


if __name__ == "__main__":
    unittest.main()
