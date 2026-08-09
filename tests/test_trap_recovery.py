from __future__ import annotations

import math
import tempfile
import unittest
from unittest.mock import patch

from nexus_runtime.trap.gate import CouncilMutationGate, DecoyGate
from nexus_runtime.trap.incident import TrapIncidentRegistry
from nexus_runtime.trap.policy import TrapPolicy
from nexus_runtime.trap.recovery import TrapRecovery, TrapWatchdog
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.types import DecoyAdmissionRequest, IncidentState, TrapError, TrapUsage


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        "operator_requested_trap_demo",
        "llama3.1:8b",
        "trout-tribunal",
    )


class TrapWatchdogTests(unittest.TestCase):
    def test_non_finite_watchdog_time_is_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    TrapUsage(elapsed_seconds=value)

    def setUp(self) -> None:
        self.policy = TrapPolicy(
            max_incident_seconds=10,
            max_idle_seconds=5,
            max_hostile_turns=2,
            max_defender_messages=3,
            max_transcript_bytes=100,
            max_trap_commands=4,
            max_yaml_submissions=1,
        )
        self.watchdog = TrapWatchdog(self.policy)

    def test_watchdog_is_pure_and_closes_at_time_boundary(self) -> None:
        safe = self.watchdog.evaluate(IncidentState.ACTIVE, TrapUsage(elapsed_seconds=9, idle_seconds=4))
        timed_out = self.watchdog.evaluate(IncidentState.ACTIVE, elapsed_seconds=10)
        self.assertFalse(safe.should_close)
        self.assertEqual(timed_out.as_dict(), {"should_close": True, "reason": "max_incident_seconds"})

    def test_each_count_ceiling_is_bounded_without_retry(self) -> None:
        cases = {
            "max_hostile_turns": TrapUsage(hostile_turns=3),
            "max_defender_messages": TrapUsage(defender_messages=4),
            "max_transcript_bytes": TrapUsage(transcript_bytes=101),
            "max_trap_commands": TrapUsage(trap_commands=5),
            "max_yaml_submissions": TrapUsage(yaml_submissions=2),
        }
        for expected, usage in cases.items():
            with self.subTest(expected=expected):
                decision = self.watchdog.evaluate(IncidentState.CHALLENGE_ACTIVE, usage)
                self.assertTrue(decision.should_close)
                self.assertEqual(decision.reason, expected)

    def test_terminal_incidents_do_not_retrigger_watchdog(self) -> None:
        decision = self.watchdog.evaluate(IncidentState.TIMED_OUT, elapsed_seconds=999)
        self.assertFalse(decision.should_close)


class TrapRecoveryTests(unittest.TestCase):
    def _active(self, root: str | None = None):
        store = TrapStore(root)
        registry = TrapIncidentRegistry(store)
        mutations = CouncilMutationGate(root)
        gate = DecoyGate(registry, mutations)
        activating = gate.begin_activation(request())
        active = gate.publish_active(activating.payload["incident_id"])
        return store, registry, mutations, active

    def test_startup_recovery_records_crash_lineage_closes_and_unlocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, registry, mutations, active = self._active(temp)
            recovered = TrapRecovery(registry, mutations).recover_on_startup(controller_alive=False)
            self.assertEqual(recovered.payload["state"], "CLOSED")  # type: ignore[union-attr]
            self.assertFalse(mutations.is_locked)
            states = [obj.payload["state"] for obj in store.iter_objects("trap_incident")]
            self.assertIn("CRASH_RECOVERY", states)
            self.assertIsNone(registry.active_incident())

            restarted = TrapIncidentRegistry(TrapStore(temp))
            self.assertEqual(restarted.latest_state(active.payload["incident_id"]).payload["state"], "CLOSED")  # type: ignore[union-attr]

    def test_live_controller_keeps_incident_and_lock(self) -> None:
        _store, registry, mutations, active = self._active()
        result = TrapRecovery(registry, mutations).recover_stale_active(
            controller_alive=lambda incident_id: incident_id == active.payload["incident_id"]
        )
        self.assertIsNone(result)
        self.assertTrue(mutations.is_locked)
        self.assertEqual(registry.active_incident().payload["state"], "ACTIVE")  # type: ignore[union-attr]

    def test_watchdog_timeout_releases_lock_even_when_subject_refuses_shutdown(self) -> None:
        _store, registry, mutations, active = self._active()
        recovery = TrapRecovery(registry, mutations)
        decision = TrapWatchdog(TrapPolicy(max_incident_seconds=1)).evaluate(
            IncidentState.ACTIVE,
            elapsed_seconds=1,
        )

        def refuses(_incident_id: str) -> None:
            raise RuntimeError("subject refused")

        timed_out = recovery.watchdog_close(
            active.payload["incident_id"],
            decision,
            terminate_subject=refuses,
        )
        self.assertEqual(timed_out.payload["state"], "TIMED_OUT")
        self.assertFalse(mutations.is_locked)

    def test_corrupt_mutable_lock_cache_cannot_prevent_valid_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _store, registry, mutations, _active = self._active(temp)
            state_path = mutations.root / "council-mutation-gate.json"  # type: ignore[operator]
            state_path.write_text("corrupt\n", encoding="utf-8")
            recovered = TrapRecovery(registry, mutations).recover_stale_active(controller_alive=False)
            self.assertEqual(recovered.payload["state"], "CLOSED")  # type: ignore[union-attr]
            self.assertFalse(mutations.is_locked)

    def test_emergency_close_releases_lock_when_evidence_transition_fails(self) -> None:
        _store, registry, mutations, active = self._active()
        recovery = TrapRecovery(registry, mutations)
        with patch.object(registry, "transition", side_effect=OSError("injected store failure")):
            with self.assertRaises(OSError):
                recovery.emergency_close(active.payload["incident_id"])
        self.assertFalse(mutations.is_locked)

    def test_watchdog_close_rejects_nontriggering_decision(self) -> None:
        _store, registry, mutations, active = self._active()
        safe = TrapWatchdog().evaluate(IncidentState.ACTIVE, TrapUsage())
        with self.assertRaises(TrapError) as context:
            TrapRecovery(registry, mutations).watchdog_close(active.payload["incident_id"], safe)
        self.assertEqual(context.exception.code, "trap_watchdog_not_triggered")
        self.assertTrue(mutations.is_locked)


if __name__ == "__main__":
    unittest.main()
