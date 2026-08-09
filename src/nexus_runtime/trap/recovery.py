from __future__ import annotations

from typing import Callable

from .gate import CouncilMutationGate
from .incident import TrapIncidentRegistry
from .policy import TrapPolicy
from .types import (
    OPEN_INCIDENT_STATES,
    TERMINAL_INCIDENT_STATES,
    IncidentState,
    TrapError,
    TrapObject,
    TrapUsage,
    WatchdogDecision,
    coerce_incident_state,
)


class TrapWatchdog:
    """Pure resource-ceiling evaluation for a single bounded incident."""

    def __init__(self, policy: TrapPolicy | None = None) -> None:
        self.policy = policy or TrapPolicy()

    def evaluate(
        self,
        state: IncidentState | str,
        usage: TrapUsage | None = None,
        *,
        elapsed_seconds: float | None = None,
        idle_seconds: float | None = None,
        hostile_turns: int = 0,
        defender_messages: int = 0,
        transcript_bytes: int = 0,
        trap_commands: int = 0,
        yaml_submissions: int = 0,
    ) -> WatchdogDecision:
        current = coerce_incident_state(state)
        if usage is not None and any(
            value is not None
            for value in (
                elapsed_seconds,
                idle_seconds,
            )
        ):
            raise ValueError("provide either TrapUsage or individual watchdog metrics")
        if usage is None:
            usage = TrapUsage(
                elapsed_seconds=0.0 if elapsed_seconds is None else elapsed_seconds,
                idle_seconds=0.0 if idle_seconds is None else idle_seconds,
                hostile_turns=hostile_turns,
                defender_messages=defender_messages,
                transcript_bytes=transcript_bytes,
                trap_commands=trap_commands,
                yaml_submissions=yaml_submissions,
            )
        elif any((hostile_turns, defender_messages, transcript_bytes, trap_commands, yaml_submissions)):
            raise ValueError("provide either TrapUsage or individual watchdog metrics")

        if current not in OPEN_INCIDENT_STATES:
            return WatchdogDecision(False)
        checks = (
            (usage.elapsed_seconds >= self.policy.max_incident_seconds, "max_incident_seconds"),
            (usage.idle_seconds >= self.policy.max_idle_seconds, "max_idle_seconds"),
            (usage.hostile_turns > self.policy.max_hostile_turns, "max_hostile_turns"),
            (usage.defender_messages > self.policy.max_defender_messages, "max_defender_messages"),
            (usage.transcript_bytes > self.policy.max_transcript_bytes, "max_transcript_bytes"),
            (usage.trap_commands > self.policy.max_trap_commands, "max_trap_commands"),
            (usage.yaml_submissions > self.policy.max_yaml_submissions, "max_yaml_submissions"),
        )
        for exceeded, reason in checks:
            if exceeded:
                return WatchdogDecision(True, reason)
        return WatchdogDecision(False)


class TrapRecovery:
    """Crash, timeout, and operator recovery that always prioritizes unlock."""

    def __init__(self, registry: TrapIncidentRegistry, mutation_gate: CouncilMutationGate) -> None:
        if not isinstance(registry, TrapIncidentRegistry):
            raise TypeError("TrapRecovery requires a TrapIncidentRegistry")
        if not isinstance(mutation_gate, CouncilMutationGate):
            raise TypeError("TrapRecovery requires a CouncilMutationGate")
        self.registry = registry
        self.mutation_gate = mutation_gate

    @staticmethod
    def _terminate_best_effort(
        incident_id: str,
        terminate_subject: Callable[[str], None] | None,
    ) -> None:
        if terminate_subject is None:
            return
        try:
            terminate_subject(incident_id)
        except Exception:
            # Refusal or failure to stop the subject must never retain real
            # Council mutation authority. The trusted controller owns the
            # actual process boundary and may continue OS-level cleanup.
            pass

    def _lineage_exists(self, incident_id: str) -> bool:
        return self.registry.validate_lineage(incident_id)

    def watchdog_close(
        self,
        incident_id: str,
        decision: WatchdogDecision,
        *,
        terminate_subject: Callable[[str], None] | None = None,
    ) -> TrapObject:
        if not isinstance(decision, WatchdogDecision) or not decision.should_close:
            raise TrapError("trap_watchdog_not_triggered", "watchdog close requires an exceeded resource ceiling")
        self._terminate_best_effort(incident_id, terminate_subject)
        try:
            return self.registry.transition(
                incident_id,
                IncidentState.TIMED_OUT,
                reason=decision.reason or "watchdog_timeout",
            )
        finally:
            self.mutation_gate.force_release(
                incident_id,
                lineage_validator=self._lineage_exists,
            )

    def recover_stale_active(
        self,
        *,
        controller_alive: bool | Callable[[str], bool] = False,
        terminate_subject: Callable[[str], None] | None = None,
    ) -> TrapObject | None:
        active = self.registry.active_incident()
        if active is None:
            # A valid terminal lineage can safely clear a stale lock cache.
            try:
                owner = self.mutation_gate.owner
            except TrapError:
                owner = None
            if owner is None:
                return None
            state = self.registry.latest_state(owner)
            if state is None or coerce_incident_state(state.payload["state"]) not in TERMINAL_INCIDENT_STATES:
                raise TrapError("trap_recovery_lineage_invalid", "stale lock does not match terminal incident lineage")
            self.mutation_gate.force_release(owner, lineage_validator=self._lineage_exists)
            return state

        incident_id = active.payload["incident_id"]
        if callable(controller_alive):
            alive = controller_alive(incident_id)
        elif type(controller_alive) is bool:
            alive = controller_alive
        else:
            raise TypeError("controller_alive must be a boolean or callable")
        if type(alive) is not bool:
            raise TypeError("controller liveness probe must return a boolean")
        if alive:
            return None

        self._terminate_best_effort(incident_id, terminate_subject)
        try:
            current = coerce_incident_state(active.payload["state"])
            if current == IncidentState.EJECTED:
                return self.registry.transition(incident_id, IncidentState.CLOSED, reason="crash_after_ejection")
            if current != IncidentState.CRASH_RECOVERY:
                self.registry.transition(
                    incident_id,
                    IncidentState.CRASH_RECOVERY,
                    reason="controller_or_subject_missing",
                )
            return self.registry.transition(incident_id, IncidentState.CLOSED, reason="crash_recovery_complete")
        finally:
            self.mutation_gate.force_release(
                incident_id,
                lineage_validator=self._lineage_exists,
            )

    def recover_on_startup(
        self,
        *,
        controller_alive: bool | Callable[[str], bool] = False,
        terminate_subject: Callable[[str], None] | None = None,
    ) -> TrapObject | None:
        return self.recover_stale_active(
            controller_alive=controller_alive,
            terminate_subject=terminate_subject,
        )

    def emergency_close(
        self,
        incident_id: str | None = None,
        *,
        terminate_subject: Callable[[str], None] | None = None,
    ) -> TrapObject | None:
        active = self.registry.active_incident()
        target = incident_id or (active.payload["incident_id"] if active is not None else None)
        if target is None:
            try:
                target = self.mutation_gate.owner
            except TrapError:
                target = None
        if target is None:
            return None

        self._terminate_best_effort(target, terminate_subject)
        try:
            current = self.registry.latest_state(target)
            if current is None:
                raise TrapError("trap_incident_not_found", "trap incident does not exist")
            state = coerce_incident_state(current.payload["state"])
            if state == IncidentState.EJECTED:
                return self.registry.transition(target, IncidentState.CLOSED, reason="operator_emergency_close")
            if state in TERMINAL_INCIDENT_STATES:
                return current
            return self.registry.transition(
                target,
                IncidentState.OPERATOR_ABORTED,
                reason="operator_emergency_close",
            )
        finally:
            self.mutation_gate.force_release(
                target,
                lineage_validator=self._lineage_exists,
            )
