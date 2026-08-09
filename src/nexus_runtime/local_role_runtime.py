from __future__ import annotations

from typing import Any

from .adapters.base import CouncilActor
from .local_roles import LocalRoleActor, LocalRoleRegistry


class LocalAwareFailsafe:
    """Decorator that enriches only Failsafe-generated replacement actors."""

    def __init__(self, base: Any, local_roles: LocalRoleRegistry) -> None:
        self._base = base
        self._local_roles = local_roles

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:
        effective, metadata = self._base.actor_for_run(actor)
        if metadata is None:
            return effective, None
        wrapped = self._local_roles.wrap("failsafe_relief", effective)
        enriched = dict(metadata)
        if isinstance(wrapped, LocalRoleActor):
            enriched["local_role_backend"] = wrapped.backend.public_dict()
            enriched["local_model_language_only"] = True
            enriched["governance_ballot_source"] = "wrapped_deterministic_role"
        return wrapped, enriched


class LocalAwareCitizenship:
    """Decorator that enriches only deterministic civic proxy actors."""

    def __init__(self, base: Any, local_roles: LocalRoleRegistry) -> None:
        self._base = base
        self._local_roles = local_roles

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def proxy_for_civic_duty(
        self,
        actor: CouncilActor,
        *,
        mode_id: str,
    ) -> tuple[CouncilActor, dict[str, Any] | None]:
        effective, metadata = self._base.proxy_for_civic_duty(actor, mode_id=mode_id)
        if metadata is None:
            return effective, None
        wrapped = self._local_roles.wrap("civic_proxy", effective)
        enriched = dict(metadata)
        if isinstance(wrapped, LocalRoleActor):
            enriched["local_role_backend"] = wrapped.backend.public_dict()
            enriched["local_model_language_only"] = True
            enriched["standing_ballot_remains_authoritative"] = True
        return wrapped, enriched


__all__ = ["LocalAwareCitizenship", "LocalAwareFailsafe"]
