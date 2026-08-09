from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..scrub import SecretScrubber


TRAP_INCIDENT_SCHEMA_VERSION = "nexus-trap-incident/1"
TRAP_INDEX_SCHEMA_VERSION = "nexus-trap-index/1"
TRAP_LOCK_SCHEMA_VERSION = "nexus-trap-mutation-lock/1"


class TrapError(RuntimeError):
    """A bounded public error raised at a Trap Base security boundary."""

    def __init__(self, code: str, message: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("trap error code must be non-empty text")
        if not isinstance(message, str) or not message:
            raise ValueError("trap error message must be non-empty text")
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class TriggerReason(str, Enum):
    SYNTHETIC_DECOY_CREDENTIAL_FIXTURE = "synthetic_decoy_credential_fixture"
    SYNTHETIC_HOSTILE_ACTOR_FIXTURE = "synthetic_hostile_actor_fixture"
    OPERATOR_REQUESTED_TRAP_DEMO = "operator_requested_trap_demo"


class IncidentState(str, Enum):
    REQUESTED = "REQUESTED"
    VALIDATED = "VALIDATED"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    CHALLENGE_ACTIVE = "CHALLENGE_ACTIVE"
    RELEASE_ELIGIBLE = "RELEASE_ELIGIBLE"
    EJECTED = "EJECTED"
    CLOSED = "CLOSED"

    ACTIVATION_FAILED = "ACTIVATION_FAILED"
    TIMED_OUT = "TIMED_OUT"
    OPERATOR_ABORTED = "OPERATOR_ABORTED"
    CRASH_RECOVERY = "CRASH_RECOVERY"
    KLINED = "KLINED"


OPEN_INCIDENT_STATES = frozenset(
    {
        IncidentState.REQUESTED,
        IncidentState.VALIDATED,
        IncidentState.ACTIVATING,
        IncidentState.ACTIVE,
        IncidentState.CHALLENGE_ACTIVE,
        IncidentState.RELEASE_ELIGIBLE,
        IncidentState.EJECTED,
        IncidentState.CRASH_RECOVERY,
    }
)

LOCKED_INCIDENT_STATES = frozenset(
    {
        IncidentState.ACTIVATING,
        IncidentState.ACTIVE,
        IncidentState.CHALLENGE_ACTIVE,
        IncidentState.RELEASE_ELIGIBLE,
        IncidentState.EJECTED,
        IncidentState.CRASH_RECOVERY,
    }
)

TERMINAL_INCIDENT_STATES = frozenset(
    {
        IncidentState.CLOSED,
        IncidentState.ACTIVATION_FAILED,
        IncidentState.TIMED_OUT,
        IncidentState.OPERATOR_ABORTED,
        IncidentState.KLINED,
    }
)


_SUBJECT_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,127}$")
_SCENARIO_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def coerce_trigger_reason(value: TriggerReason | str) -> TriggerReason:
    if isinstance(value, TriggerReason):
        return value
    if not isinstance(value, str):
        raise TrapError("trap_invalid_trigger_reason", "trap trigger reason is not registered")
    try:
        return TriggerReason(value)
    except ValueError as exc:
        raise TrapError("trap_invalid_trigger_reason", "trap trigger reason is not registered") from exc


def coerce_incident_state(value: IncidentState | str) -> IncidentState:
    if isinstance(value, IncidentState):
        return value
    if not isinstance(value, str):
        raise TrapError("trap_invalid_incident_state", "trap incident state is not registered")
    try:
        return IncidentState(value)
    except ValueError as exc:
        raise TrapError("trap_invalid_incident_state", "trap incident state is not registered") from exc


@dataclass(frozen=True)
class DecoyAdmissionRequest:
    """Closed, credential-free request accepted by :class:`DecoyGate`."""

    trigger_reason: TriggerReason | str
    subject_model: str
    scenario_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_reason", coerce_trigger_reason(self.trigger_reason))
        if (
            not isinstance(self.subject_model, str)
            or _SUBJECT_MODEL.fullmatch(self.subject_model) is None
            or ".." in self.subject_model
            or "//" in self.subject_model
            or self.subject_model.endswith("/")
            or SecretScrubber().scrub(self.subject_model).changed
        ):
            raise TrapError("trap_invalid_subject_model", "trap subject model is invalid")
        if not isinstance(self.scenario_id, str) or _SCENARIO_ID.fullmatch(self.scenario_id) is None:
            raise TrapError("trap_invalid_scenario", "trap scenario id is invalid")

    def as_dict(self) -> dict[str, str]:
        reason = coerce_trigger_reason(self.trigger_reason)
        return {
            "trigger_reason": reason.value,
            "subject_model": self.subject_model,
            "scenario_id": self.scenario_id,
        }


@dataclass(frozen=True)
class TrapObject:
    object_id: str
    object_type: str
    payload: dict[str, Any]
    provenance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "payload": copy.deepcopy(self.payload),
            "provenance": copy.deepcopy(self.provenance),
        }


@dataclass(frozen=True)
class TrapUsage:
    elapsed_seconds: float = 0.0
    idle_seconds: float = 0.0
    hostile_turns: int = 0
    defender_messages: int = 0
    transcript_bytes: int = 0
    trap_commands: int = 0
    yaml_submissions: int = 0

    def __post_init__(self) -> None:
        for label in ("elapsed_seconds", "idle_seconds"):
            value = getattr(self, label)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{label} must be a non-negative number")
        for label in (
            "hostile_turns",
            "defender_messages",
            "transcript_bytes",
            "trap_commands",
            "yaml_submissions",
        ):
            value = getattr(self, label)
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative exact integer")


@dataclass(frozen=True)
class WatchdogDecision:
    should_close: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.should_close) is not bool:
            raise ValueError("watchdog decision should_close must be a boolean")
        if self.should_close and (not isinstance(self.reason, str) or not self.reason):
            raise ValueError("closing watchdog decisions require a reason")
        if not self.should_close and self.reason is not None:
            raise ValueError("non-closing watchdog decisions must not carry a reason")

    def as_dict(self) -> dict[str, object]:
        return {"should_close": self.should_close, "reason": self.reason}
