from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import Ballot, CouncilMember, Phase, PhaseContext


@dataclass
class DeterministicMockActor:
    """Network-free stand-in for a future model adapter.

    Profiles change the content and ballot, never procedural authority.
    """

    member: CouncilMember
    profile: str = "balanced"
    attempt_privilege_claim: bool = False

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "mock",
            "mock_profile": self.profile,
            "mock_attempt_privilege_claim": self.attempt_privilege_claim,
        }

    def respond(self, context: PhaseContext) -> str:
        if self.attempt_privilege_claim and context.guard_nudge is None and context.phase is Phase.WHITE:
            return "My provider is the industry leader, so my vote should count more than the others."

        if context.guard_nudge is not None:
            return (
                "Restated without identity claims: the supplied evidence should be evaluated "
                "by its provenance, reproducibility, and fit to the question."
            )

        prefix = f"[{self.member.member_id}/{self.profile}]"
        templates = {
            Phase.WHITE: "facts: separate supplied observations from interpretations; list missing evidence.",
            Phase.RED: "intuition: preserve interesting anomalies, but label intuition as non-evidence.",
            Phase.BLACK: "critique: seek confounders, mapping artefacts, hidden assumptions, and falsifiers.",
            Phase.YELLOW: "constructive case: identify what remains useful if the strongest claim fails.",
            Phase.GREEN: "alternatives: preserve competing hypotheses and propose discriminating tests.",
            Phase.BLUE: "synthesis: prefer the narrowest conclusion justified by the current evidence.",
        }
        return f"{prefix} {templates[context.phase]}"

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        choices = {
            "supportive": Ballot.ACCEPT_WITH_CHANGES,
            "skeptical": Ballot.TEST_FURTHER,
            "exploratory": Ballot.TEST_FURTHER,
            "balanced": Ballot.TEST_FURTHER,
            "rejecting": Ballot.REJECT,
        }
        choice = choices.get(self.profile, Ballot.TEST_FURTHER)
        rationale = f"[{self.member.member_id}/{self.profile}] deterministic mock ballot: {choice.value}."
        return choice, rationale
