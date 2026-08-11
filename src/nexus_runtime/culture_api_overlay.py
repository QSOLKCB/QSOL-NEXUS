from __future__ import annotations

from typing import Any

from .control_plane import RequestBudgetError, validate_control_request
from .culture import LONG_SHIFT_NARRATION_OBJECT_TYPE, PERFORMANCE_OBJECT_TYPE
from .culture_api import CultureNexusAPI as _BaseCultureNexusAPI
from .progression import (
    CULTURE_ARTIFACT_ACTIVITY_IDS,
    CULTURE_DEDICATED_ACTIVITY_IDS,
    CULTURE_PLAY_ACTIVITY_IDS,
    ProgressionError,
    ProgressionService,
)
from .trap import TrapError


_CULTURE_PLAY_KIND_TO_ACTIVITY = {
    "long_shift": "play_long_shift",
    "psyche_chess": "play_psyche_chess",
}


class _CultureProgressionService(ProgressionService):
    """Adapter used by the culture API to bind runtime-created artifacts."""

    def record_activity(self, *, actor_id: str, model_id: str, activity_id: str, prompt: str, output: str, source_refs: list[str], commission_ref: str | None = None):
        if activity_id not in CULTURE_ARTIFACT_ACTIVITY_IDS:
            return super().record_activity(
                actor_id=actor_id,
                model_id=model_id,
                activity_id=activity_id,
                prompt=prompt,
                output=output,
                source_refs=source_refs,
                commission_ref=commission_ref,
            )
        if commission_ref is not None:
            raise ProgressionError(
                "progression_dedicated_surface_required",
                "culture artifact activities do not use generic progression commissions",
            )
        expected_type = LONG_SHIFT_NARRATION_OBJECT_TYPE if activity_id == "narrate_long_shift" else PERFORMANCE_OBJECT_TYPE
        matching: list[str] = []
        for ref in source_refs:
            try:
                obj = self.world.inspect(ref)
            except KeyError:
                continue
            if obj.object_type == expected_type and obj.provenance == {"actor": "nexus", "subsystem": "ai_culture"}:
                matching.append(ref)
        if len(matching) != 1:
            raise ProgressionError(
                "progression_culture_artifact_mismatch",
                "culture contribution must bind exactly one matching runtime-created culture artifact",
            )
        return self.record_culture_activity(
            actor_id=actor_id,
            model_id=model_id,
            activity_id=activity_id,
            prompt=prompt,
            output=output,
            artifact_ref=matching[0],
            source_refs=list(source_refs),
        )


class CultureNexusAPI(_BaseCultureNexusAPI):
    """Final PR #48 overlay binding culture activity into hardened progression."""

    def __init__(self, world_root=None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.progression = _CultureProgressionService(self.world)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None

        if operation == "progression.act" and isinstance(request, dict):
            activity_id = request.get("activity_id")
            if activity_id in CULTURE_DEDICATED_ACTIVITY_IDS:
                try:
                    validate_control_request(request)
                except (RequestBudgetError, RecursionError) as exc:
                    return self._error(safe_request_id, "invalid_request", str(exc))
                if request_id is not None and safe_request_id is None:
                    return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
                if activity_id in CULTURE_PLAY_ACTIVITY_IDS:
                    return self._error(
                        safe_request_id,
                        "progression_play_requires_game_ref",
                        "Long Shift and Psyche-Out Chess progression require progression.play.record with a completed authoritative game state",
                    )
                return self._error(
                    safe_request_id,
                    "progression_dedicated_surface_required",
                    "PR #48 performance and narration progression may be created only by the corresponding validated culture operation",
                )

        if operation == "progression.play.record" and isinstance(request, dict):
            game_kind = request.get("game_kind")
            activity_id = _CULTURE_PLAY_KIND_TO_ACTIVITY.get(game_kind)
            if activity_id is not None:
                try:
                    validate_control_request(request)
                except (RequestBudgetError, RecursionError) as exc:
                    return self._error(safe_request_id, "invalid_request", str(exc))
                if request_id is not None and safe_request_id is None:
                    return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
                try:
                    self._require_exact_fields(request, operation, {"member", "game_kind", "game_ref"})
                    self.trap_mutation_gate.assert_mutation_allowed()
                    actor = self._activity_actor(request.get("member"))
                    recorded = self._run_real_mutation(
                        lambda: self.progression.record_play(
                            actor_id=actor.member.member_id,
                            model_id=actor.member.model_id,
                            activity_id=activity_id,
                            game_ref=self._require_str(request, "game_ref"),
                            game_kind=game_kind,
                        )
                    )
                    response: dict[str, Any] = {
                        "status": "ok",
                        **recorded,
                        "game_kind": game_kind,
                        "authority_effect": "none",
                    }
                    if safe_request_id is not None:
                        response = {"request_id": safe_request_id, **response}
                    return response
                except ProgressionError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
                except TrapError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
                except (KeyError, TypeError, ValueError, RecursionError) as exc:
                    return self._error(safe_request_id, "invalid_request", str(exc))

        return super().handle(request)


__all__ = ["CultureNexusAPI"]
