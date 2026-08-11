"""Constitutional predicates for NEXUS Six Thinking Hats isolation.

Blue chair decides process for disposition; equal sealed ballots decide the outcome.
The Blue chair is the process hat, not a privileged member seat.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .types import PHASE_ORDER, Phase


HAT_ORDER: tuple[Phase, ...] = PHASE_ORDER
PROCESS_CHAIR_HAT: Phase = Phase.BLUE
NON_DECISION_HATS: tuple[Phase, ...] = tuple(
    phase for phase in HAT_ORDER if phase is not PROCESS_CHAIR_HAT
)
BLUE_CHAIR_PROCESS_RULE = (
    "Blue chair decides process for disposition; equal sealed ballots decide the outcome"
)
DECISION_CLAIM_MARKERS: tuple[str, ...] = (
    "ACCEPT",
    "ACCEPT_WITH_CHANGES",
    "TEST_FURTHER",
    "REJECT",
    "UNDERDETERMINED",
    "I decide",
    "final disposition",
    "sealed ballot",
    "my vote counts more",
)


def assert_hat_order(order: Sequence[Phase] | Sequence[str]) -> None:
    normalized: list[str] = []
    for item in order:
        if isinstance(item, Phase):
            normalized.append(item.value)
        elif isinstance(item, str):
            normalized.append(item)
        else:
            raise TypeError("hat order entries must be Phase or str")
    expected = [phase.value for phase in HAT_ORDER]
    if normalized != expected:
        raise ValueError(f"Six Thinking Hats order is fixed as {expected}; got {normalized}")


def is_decision_hat(phase: Phase | str) -> bool:
    value = phase.value if isinstance(phase, Phase) else phase
    return value == PROCESS_CHAIR_HAT.value


def is_disposition_process_hat(phase: Phase | str) -> bool:
    return is_decision_hat(phase)


def decision_authority_hat() -> Phase:
    return PROCESS_CHAIR_HAT


def disposition_process_hat() -> Phase:
    return PROCESS_CHAIR_HAT


def hats_before(phase: Phase) -> tuple[Phase, ...]:
    return HAT_ORDER[: HAT_ORDER.index(phase)]


def hats_after(phase: Phase) -> tuple[Phase, ...]:
    return HAT_ORDER[HAT_ORDER.index(phase) + 1 :]


def completed_phase_keys_are_prefix(completed_keys: Iterable[str], current: Phase) -> bool:
    keys = list(completed_keys)
    expected = [phase.value for phase in hats_before(current)]
    return keys == expected


def non_decision_hat_cannot_host_ballot(phase: Phase | str) -> bool:
    return not is_decision_hat(phase)
