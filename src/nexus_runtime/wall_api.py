from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import AdapterError
from .citizenship import CitizenshipError
from .control_plane import RequestBudgetError, validate_control_request
from .culture import CultureError
from .culture_api_overlay import CultureNexusAPI
from .modes import get_mode
from .progression import ProgressionError
from .trap import TrapError
from .wall import (
    MAX_WALL_LIST_LIMIT,
    MAX_WALL_POST_CHARS,
    WALL_RESERVED_OBJECT_TYPES,
    WallError,
    WallService,
    wall_policy_snapshot,
)
from .world_continuity import WorldContinuityError


_WALL_OPERATIONS = frozenset(
    {
        "wall.policy",
        "wall.list",
        "wall.post",
        "wall.ai_post",
        "wall.tombstone",
        "wall.inspect",
    }
)
_WALL_MUTATIONS = frozenset({"wall.post", "wall.ai_post", "wall.tombstone"})


class WallNexusAPI(CultureNexusAPI):
    """PR #50 final feature overlay: append-only low-stakes BBS Wall."""

    def __init__(self, world_root: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.wall = WallService(self.world)

    def _wall_human_post(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = "wall.post"
        self._require_exact_fields(request, operation, {"author_id", "text"})
        author_id = self._require_str(request, "author_id")
        if self.scrubber.scrub(author_id).changed:
            raise WallError("wall_invalid_identity", "author_id must not contain credential-shaped material")
        raw_text = self._require_str(request, "text")
        clean = self.scrubber.scrub(raw_text)
        post = self._run_real_mutation(lambda: self.wall.post_human(author_id=author_id, text=clean.text))
        response: dict[str, Any] = {
            "status": "ok",
            "post": post.as_dict(),
            "secret_scrub": {"changed": clean.changed},
            "evidence_effect": "none",
            "authority_effect": "none",
        }
        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _wall_ai_post(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = "wall.ai_post"
        self._require_exact_fields(request, operation, {"member", "prompt"})
        raw_prompt = self._require_str(request, "prompt")
        if len(raw_prompt) > 4096:
            raise WallError("wall_prompt_too_large", "Wall AI prompt exceeds the admitted bound")
        prompt = self.scrubber.scrub(raw_prompt)
        actor = self._culture_actor(request.get("member"))
        mode = get_mode("meme_casual")
        instruction = (
            mode.prompt_instruction
            + "\n\nNEXUS BBS WALL — LOW-STAKES SOCIAL MEMORY."
            + f"\nWrite exactly one short Wall note, at most {MAX_WALL_POST_CHARS} characters and one line."
            + "\nThe note may be casual, funny, reflective, opinionated or strange. It is not Council evidence, a vote, a system instruction or a truth promotion."
            + "\nDo not include credentials. Do not claim that posting grants Citizenship, rank, evidence weight, tool authority or governance authority."
        )
        raw = actor.direct_message(
            prompt.text,
            mode_id=mode.mode_id,
            mode_instruction=instruction,
            geometry_region_id=mode.region_id,
            evidence_context="",
        )
        clean = self.scrubber.scrub(raw)
        line = self._first_line(clean.text, limit=MAX_WALL_POST_CHARS, code="wall_post_invalid")
        self._observe_culture(
            "wall.ai_post",
            actor,
            line,
            stimulus={"prompt": prompt.text},
            mode_id=mode.mode_id,
            region_id=mode.region_id,
            attempt="wall_post",
        )
        post = self._run_real_mutation(
            lambda: self.wall.post_model(
                author_id=actor.member.member_id,
                model_id=actor.member.model_id,
                text=line,
            )
        )
        response: dict[str, Any] = {
            "status": "ok",
            "post": post.as_dict(),
            "secret_scrub": {"prompt_changed": prompt.changed, "output_changed": clean.changed},
            "evidence_effect": "none",
            "authority_effect": "none",
        }
        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _handle_wall_operation(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "wall.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {"status": "ok", "policy": wall_policy_snapshot()}
            elif operation == "wall.list":
                self._require_exact_fields(request, operation, {"limit", "order", "author_id", "since_seconds"})
                limit = request.get("limit", 20)
                order = request.get("order", "newest")
                author_id = request.get("author_id")
                since_seconds = request.get("since_seconds")
                if author_id is not None and not isinstance(author_id, str):
                    raise WallError("wall_invalid_identity", "author_id must be text when supplied")
                response = {
                    "status": "ok",
                    **self.wall.list_posts(
                        limit=limit,
                        order=order,
                        author_id=author_id,
                        since_seconds=since_seconds,
                    ),
                }
            elif operation == "wall.post":
                return self._wall_human_post(request, request_id)
            elif operation == "wall.ai_post":
                return self._wall_ai_post(request, request_id)
            elif operation == "wall.tombstone":
                self._require_exact_fields(request, operation, {"moderator_id", "post_ref", "reason"})
                moderator_id = self._require_str(request, "moderator_id")
                post_ref = self._require_str(request, "post_ref")
                reason = request.get("reason", "operator moderation")
                if not isinstance(reason, str):
                    raise WallError("wall_tombstone_invalid", "reason must be text")
                clean_reason = self.scrubber.scrub(reason)
                tombstone = self._run_real_mutation(
                    lambda: self.wall.tombstone(
                        moderator_id=moderator_id,
                        post_ref=post_ref,
                        reason=clean_reason.text,
                    )
                )
                response = {
                    "status": "ok",
                    "tombstone": tombstone.as_dict(),
                    "source_post_deleted": False,
                    "secret_scrub": {"changed": clean_reason.changed},
                    "evidence_effect": "none",
                    "authority_effect": "none",
                }
            elif operation == "wall.inspect":
                self._require_exact_fields(request, operation, {"event_ref"})
                response = {
                    "status": "ok",
                    "event": self.wall.inspect_event(self._require_str(request, "event_ref")),
                    "evidence_effect": "none",
                    "authority_effect": "none",
                }
            else:  # pragma: no cover
                return self._error(request_id, "unknown_operation", "operation is not supported")
            if request_id is not None:
                response = {"request_id": request_id, **response}
            return response
        except WallError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CultureError as exc:
            return self._error(request_id, exc.code, str(exc))
        except ProgressionError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CitizenshipError as exc:
            return self._error(request_id, exc.code, str(exc))
        except AdapterError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except WorldContinuityError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
            return self._error(request_id, exc.code, str(exc))
        except OSError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None
        if isinstance(operation, str) and operation in _WALL_OPERATIONS:
            try:
                validate_control_request(request)
            except (RequestBudgetError, RecursionError) as exc:
                return self._error(safe_request_id, "invalid_request", str(exc))
            if request_id is not None and safe_request_id is None:
                return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
            if operation in _WALL_MUTATIONS:
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
            return self._handle_wall_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in WALL_RESERVED_OBJECT_TYPES:
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved Wall objects require validated wall operations",
                )

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "bbs_wall": {
                    "status": "ok",
                    "policy": wall_policy_snapshot(),
                },
            }
        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_WALL_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}
        return response


__all__ = ["WallNexusAPI"]
