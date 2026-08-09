from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import IncidentState, TrapError, coerce_incident_state


MAX_ACTIVE_TRAP_INCIDENTS = 1
MAX_INCIDENT_SECONDS = 1_800
MAX_IDLE_SECONDS = 300
MAX_HOSTILE_TURNS = 64
MAX_DEFENDER_MESSAGES = 128
MAX_TRANSCRIPT_BYTES = 1_048_576
MAX_TRAP_COMMANDS = 256
MAX_YAML_SUBMISSIONS = 10
MAX_YAML_BYTES = 16_384
MAX_TRAP_DEFENDERS = 32


TRAP_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.REQUESTED: frozenset(
        {
            IncidentState.VALIDATED,
            IncidentState.ACTIVATION_FAILED,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
        }
    ),
    IncidentState.VALIDATED: frozenset(
        {
            IncidentState.ACTIVATING,
            IncidentState.ACTIVATION_FAILED,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
        }
    ),
    IncidentState.ACTIVATING: frozenset(
        {
            IncidentState.ACTIVE,
            IncidentState.ACTIVATION_FAILED,
            IncidentState.TIMED_OUT,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
        }
    ),
    IncidentState.ACTIVE: frozenset(
        {
            IncidentState.CHALLENGE_ACTIVE,
            IncidentState.EJECTED,
            IncidentState.TIMED_OUT,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
            IncidentState.KLINED,
        }
    ),
    IncidentState.CHALLENGE_ACTIVE: frozenset(
        {
            IncidentState.ACTIVE,
            IncidentState.RELEASE_ELIGIBLE,
            IncidentState.EJECTED,
            IncidentState.TIMED_OUT,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
            IncidentState.KLINED,
        }
    ),
    IncidentState.RELEASE_ELIGIBLE: frozenset(
        {
            IncidentState.EJECTED,
            IncidentState.TIMED_OUT,
            IncidentState.OPERATOR_ABORTED,
            IncidentState.CRASH_RECOVERY,
            IncidentState.KLINED,
        }
    ),
    IncidentState.EJECTED: frozenset({IncidentState.CLOSED, IncidentState.CRASH_RECOVERY}),
    IncidentState.CRASH_RECOVERY: frozenset({IncidentState.CLOSED}),
    IncidentState.ACTIVATION_FAILED: frozenset({IncidentState.CLOSED}),
    IncidentState.TIMED_OUT: frozenset({IncidentState.CLOSED}),
    IncidentState.OPERATOR_ABORTED: frozenset({IncidentState.CLOSED}),
    IncidentState.KLINED: frozenset({IncidentState.CLOSED}),
    IncidentState.CLOSED: frozenset(),
}


def transition_allowed(current: IncidentState | str, target: IncidentState | str) -> bool:
    current_state = coerce_incident_state(current)
    target_state = coerce_incident_state(target)
    return target_state in TRAP_TRANSITIONS[current_state]


def validate_transition(current: IncidentState | str, target: IncidentState | str) -> None:
    current_state = coerce_incident_state(current)
    target_state = coerce_incident_state(target)
    if target_state not in TRAP_TRANSITIONS[current_state]:
        raise TrapError(
            "trap_invalid_state_transition",
            f"trap incident cannot transition from {current_state.value} to {target_state.value}",
        )


@dataclass(frozen=True)
class TrapPolicy:
    max_active_incidents: int = MAX_ACTIVE_TRAP_INCIDENTS
    max_incident_seconds: int = MAX_INCIDENT_SECONDS
    max_idle_seconds: int = MAX_IDLE_SECONDS
    max_hostile_turns: int = MAX_HOSTILE_TURNS
    max_defender_messages: int = MAX_DEFENDER_MESSAGES
    max_transcript_bytes: int = MAX_TRANSCRIPT_BYTES
    max_trap_commands: int = MAX_TRAP_COMMANDS
    max_yaml_submissions: int = MAX_YAML_SUBMISSIONS
    max_yaml_bytes: int = MAX_YAML_BYTES
    max_trap_defenders: int = MAX_TRAP_DEFENDERS

    def __post_init__(self) -> None:
        if type(self.max_active_incidents) is not int or self.max_active_incidents != 1:
            raise ValueError("Trap Base supports exactly one active incident")
        for label in (
            "max_incident_seconds",
            "max_idle_seconds",
            "max_hostile_turns",
            "max_defender_messages",
            "max_transcript_bytes",
            "max_trap_commands",
            "max_yaml_submissions",
            "max_yaml_bytes",
            "max_trap_defenders",
        ):
            value = getattr(self, label)
            if type(value) is not int or value < 1:
                raise ValueError(f"{label} must be a positive exact integer")

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_active_incidents": self.max_active_incidents,
            "max_incident_seconds": self.max_incident_seconds,
            "max_idle_seconds": self.max_idle_seconds,
            "max_hostile_turns": self.max_hostile_turns,
            "max_defender_messages": self.max_defender_messages,
            "max_transcript_bytes": self.max_transcript_bytes,
            "max_trap_commands": self.max_trap_commands,
            "max_yaml_submissions": self.max_yaml_submissions,
            "max_yaml_bytes": self.max_yaml_bytes,
            "max_trap_defenders": self.max_trap_defenders,
        }
