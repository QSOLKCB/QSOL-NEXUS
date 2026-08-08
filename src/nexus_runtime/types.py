from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Phase(str, Enum):
    WHITE = "WHITE"
    RED = "RED"
    BLACK = "BLACK"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"


PHASE_ORDER = tuple(Phase)


class Ballot(str, Enum):
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_CHANGES = "ACCEPT_WITH_CHANGES"
    TEST_FURTHER = "TEST_FURTHER"
    REJECT = "REJECT"
    UNDERDETERMINED = "UNDERDETERMINED"


@dataclass(frozen=True)
class CouncilMember:
    member_id: str
    model_id: str
    adapter_id: str = "mock"
    deployment_metadata: Mapping[str, Any] = field(default_factory=dict)
    capability_metadata: Mapping[str, Any] = field(default_factory=dict)
    vote_weight: int = 1
    epistemic_privilege: str = "none"

    def __post_init__(self) -> None:
        if type(self.vote_weight) is not int or self.vote_weight != 1:
            raise ValueError("NEXUS constitutional invariant: vote_weight must be integer 1")
        if self.epistemic_privilege != "none":
            raise ValueError("NEXUS constitutional invariant: epistemic_privilege must be 'none'")
        if not self.member_id or not self.model_id:
            raise ValueError("member_id and model_id are required")


@dataclass(frozen=True)
class CouncilPolicy:
    consensus_numerator: int = 2
    consensus_denominator: int = 3
    minimum_members: int = 3
    first_pass_blind: bool = True
    ballot_sealed: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("consensus_numerator", self.consensus_numerator),
            ("consensus_denominator", self.consensus_denominator),
            ("minimum_members", self.minimum_members),
        ):
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")
        if self.consensus_numerator <= 0 or self.consensus_denominator <= 0:
            raise ValueError("consensus fraction must be positive")
        if self.consensus_numerator > self.consensus_denominator:
            raise ValueError("consensus threshold cannot exceed 1")
        if self.minimum_members < 3:
            raise ValueError("minimum_members must be at least 3")
        if type(self.first_pass_blind) is not bool or type(self.ballot_sealed) is not bool:
            raise ValueError("Council policy boolean fields must be booleans")

    def reaches_consensus(self, supporting_votes: int, total_votes: int) -> bool:
        return supporting_votes * self.consensus_denominator >= total_votes * self.consensus_numerator


@dataclass(frozen=True)
class PhaseContext:
    session_id: str
    phase: Phase
    question: str
    evidence_snapshot_ref: str
    completed_phases: Mapping[str, Mapping[str, str]]
    guard_nudge: str | None = None


@dataclass(frozen=True)
class PhaseSubmission:
    member_id: str
    phase: Phase
    content: str
    guard_events: tuple[str, ...] = ()


@dataclass(frozen=True)
class BallotRecord:
    member_id: str
    choice: Ballot
    rationale: str
    commitment: str
