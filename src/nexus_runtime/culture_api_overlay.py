from __future__ import annotations

from typing import Any

from .control_plane import RequestBudgetError, validate_control_request
from .culture_api import CultureNexusAPI as _BaseCultureNexusAPI
from .progression import CULTURE_DEDICATED_ACTIVITY_IDS, CULTURE_PLAY_ACTIVITY_IDS, ProgressionError
from .trap import TrapError


_CULTURE_PLAY_KIND_TO_ACTIVITY = {
    "long_shift": "play_long_shift",
    "psyche_chess": "play_psyche_chess",
}


class CultureNexusAPI(_BaseCultureNexusAPI):
    """Final PR #48 overlay binding culture activity into hardened progression."""

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
