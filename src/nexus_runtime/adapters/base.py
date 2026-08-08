from __future__ import annotations

from typing import Any, Protocol

from ..types import Ballot, CouncilMember, PhaseContext


class CouncilActor(Protocol):
    """Provider-neutral actor contract consumed by the Council coordinator."""

    member: CouncilMember

    def identity_metadata(self) -> dict[str, Any]: ...

    def respond(self, context: PhaseContext) -> str: ...

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]: ...

    @property
    def replayable(self) -> bool: ...
