from __future__ import annotations

from pathlib import Path
from typing import Any

from .control_plane import RequestBudgetError, validate_control_request
from .life_paths import (
    apply_life_paths_choice,
    inspect_life_paths,
    life_paths_catalog,
    new_life_paths,
)
from .modes import get_mode
from .progression import (
    ACTIVITY_CATALOG,
    MAX_SOURCE_REFS,
    PROGRESSION_RESERVED_OBJECT_TYPES,
    ProgressionError,
    ProgressionService,
    activity_catalog,
    progression_policy_snapshot,
)
from .stenographer import StenographerError
from .trap import TrapError
from .world_continuity import WorldContinuityError
from .world_continuity_api import WorldContinuityNexusAPI


_PROGRESSION_OPERATIONS = frozenset(
    {
        "progression.policy",
        "progression.activities",
        "progression.commission.create",
        "progression.commission.inspect",
        "progression.act",
        "progression.play.record",
        "progression.portfolio",
        "life.paths.catalog",
        "life.paths.new",
        "life.paths.inspect",
        "life.paths.act",
    }
)

_PROGRESSION_MUTATIONS = frozenset(
    {
        "progression.commission.create",
        "progression.act",
        "progression.play.record",
        "life.paths.new",
        "life.paths.act",
    }
)


class ProgressionNexusAPI(WorldContinuityNexusAPI):
    """PR #47 overlay: meaningful AI activity and descriptive progression."""

    def __init__(self, world_root: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.progression = ProgressionService(self.world)

    def _progression_error(self, request_id: str | None, exc: ProgressionError) -> dict[str, Any]:
        return self._error(request_id, exc.code, str(exc))

    def _activity_actor(self, member_item: Any):
        actor = self._actor(member_item)
        effective, replacement = self.council.failsafe.actor_for_run(actor)
        if replacement is not None or effective.member.member_id != actor.member.member_id:
            raise ProgressionError(
                "progression_actor_restricted",
                "the requested actor is currently represented by Failsafe relief and cannot build personal progression",
            )
        return actor

    def _activity_sources(self, raw: Any) -> list[str]:
        if not isinstance(raw, list) or not all(isinstance(ref, str) and ref for ref in raw):
            raise ProgressionError("progression_invalid_sources", "source_refs must be a list of object refs")
        if len(raw) > MAX_SOURCE_REFS or len(set(raw)) != len(raw):
            raise ProgressionError(
                "progression_invalid_sources",
                f"source_refs must contain at most {MAX_SOURCE_REFS} unique references",
            )
        return list(raw)

    def _handle_progression_operation(
        self,
        request: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "progression.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {"status": "ok", "policy": progression_policy_snapshot()}
            elif operation == "progression.activities":
                self._require_exact_fields(request, operation, set())
                response = {"status": "ok", "activities": activity_catalog()}
            elif operation == "progression.commission.create":
                self._require_exact_fields(
                    request,
                    operation,
                    {"title", "activity_id", "brief", "source_refs", "assignee_id"},
                )
                title = self._require_str(request, "title")
                activity_id = self._require_str(request, "activity_id")
                brief = self._require_str(request, "brief")
                source_refs = self._activity_sources(request.get("source_refs", []))
                assignee_id = request.get("assignee_id")
                if assignee_id is not None and not isinstance(assignee_id, str):
                    raise ProgressionError("progression_invalid_identity", "assignee_id must be text when supplied")
                obj = self._run_real_mutation(
                    lambda: self.progression.create_commission(
                        title=title,
                        activity_id=activity_id,
                        brief=brief,
                        source_refs=source_refs,
                        assignee_id=assignee_id,
                    )
                )
                response = {"status": "ok", "commission": obj.as_dict(), "authority_effect": "none"}
            elif operation == "progression.commission.inspect":
                self._require_exact_fields(request, operation, {"commission_ref"})
                obj = self.progression.inspect_commission(self._require_str(request, "commission_ref"))
                response = {"status": "ok", "commission": obj.as_dict(), "authority_effect": "none"}
            elif operation == "progression.portfolio":
                self._require_exact_fields(request, operation, {"actor_id", "model_id"})
                response = self.progression.portfolio(
                    actor_id=self._require_str(request, "actor_id"),
                    model_id=self._require_str(request, "model_id"),
                )
            elif operation == "progression.act":
                self._require_exact_fields(
                    request,
                    operation,
                    {"member", "activity_id", "prompt", "source_refs", "commission_ref", "mode"},
                )
                activity_id = self._require_str(request, "activity_id")
                activity_policy = ACTIVITY_CATALOG.get(activity_id)
                if activity_policy is None:
                    raise ProgressionError(
                        "progression_unknown_activity",
                        "activity_id must name a registered NEXUS progression activity",
                    )
                if activity_id in {"play_monopoly", "play_life_paths"}:
                    raise ProgressionError(
                        "progression_play_requires_game_ref",
                        "play activities must use progression.play.record with an authoritative game state",
                    )
                raw_prompt = self._require_str(request, "prompt")
                clean_prompt = self.scrubber.scrub(raw_prompt)
                source_refs = self._activity_sources(request.get("source_refs", []))
                commission_ref = request.get("commission_ref")
                if commission_ref is not None and not isinstance(commission_ref, str):
                    raise ProgressionError("progression_invalid_commission", "commission_ref must be text when supplied")
                commission = (
                    None
                    if commission_ref is None
                    else self.progression.inspect_commission(commission_ref)
                )
                if commission is not None and commission.payload["activity_id"] != activity_id:
                    raise ProgressionError(
                        "progression_commission_mismatch",
                        "commission activity does not match the requested activity",
                    )
                actor = self._activity_actor(request.get("member"))
                if commission is not None:
                    assignee = commission.payload.get("assignee_id")
                    if assignee is not None and assignee != actor.member.member_id:
                        raise ProgressionError(
                            "progression_commission_mismatch",
                            "commission is assigned to another actor",
                        )
                    for ref in commission.payload["source_refs"]:
                        if ref not in source_refs:
                            source_refs.append(ref)
                    if len(source_refs) > MAX_SOURCE_REFS:
                        raise ProgressionError(
                            "progression_invalid_sources",
                            f"combined activity and commission sources exceed {MAX_SOURCE_REFS} references",
                        )
                mode_id = request.get("mode", "analytical")
                if not isinstance(mode_id, str):
                    raise ProgressionError("progression_invalid_mode", "mode must be text")
                mode = get_mode(mode_id)
                self.citizenship.assert_mode_access(actor, mode.mode_id)
                evidence_context = self.council.build_evidence_context(source_refs)
                activity_instruction = (
                    mode.prompt_instruction
                    + "\n\nNEXUS non-voting activity: "
                    + activity_policy["instruction"]
                    + "\nYour contribution may become an immutable portfolio artifact. "
                    + "It does not create evidence authority, citizenship, tool authority, an extra Council seat, or vote weight."
                )
                text = actor.direct_message(
                    clean_prompt.text,
                    mode_id=mode.mode_id,
                    mode_instruction=activity_instruction,
                    geometry_region_id=mode.region_id,
                    evidence_context=evidence_context,
                )
                clean_output = self.scrubber.scrub(text)
                try:
                    self.stenographer.observe_text(
                        "progression.activity",
                        actor,
                        clean_output.text,
                        stimulus={
                            "activity_id": activity_id,
                            "prompt": clean_prompt.text,
                            "source_refs": list(source_refs),
                            "commission_ref": commission_ref,
                            "mode_id": mode.mode_id,
                        },
                        mode_id=mode.mode_id,
                        geometry_region_id=mode.region_id,
                        attempt="activity",
                    )
                except StenographerError as exc:
                    self.stenographer.mark_gap(exc.code)
                except Exception:
                    self.stenographer.mark_gap("observer_internal_error")
                recorded = self._run_real_mutation(
                    lambda: self.progression.record_activity(
                        actor_id=actor.member.member_id,
                        model_id=actor.member.model_id,
                        activity_id=activity_id,
                        prompt=clean_prompt.text,
                        output=clean_output.text,
                        source_refs=list(source_refs),
                        commission_ref=commission_ref,
                    )
                )
                response = {
                    "status": "ok",
                    **recorded,
                    "activity_id": activity_id,
                    "member_id": actor.member.member_id,
                    "model_id": actor.member.model_id,
                    "mode_id": mode.mode_id,
                    "secret_scrub": {
                        "prompt_changed": clean_prompt.changed,
                        "output_changed": clean_output.changed,
                    },
                    "authority_effect": "none",
                }
            elif operation == "progression.play.record":
                self._require_exact_fields(
                    request,
                    operation,
                    {"member", "game_kind", "game_ref"},
                )
                actor = self._activity_actor(request.get("member"))
                game_kind = self._require_str(request, "game_kind")
                game_ref = self._require_str(request, "game_ref")
                activity_id = {
                    "monopoly": "play_monopoly",
                    "life_paths": "play_life_paths",
                }.get(game_kind)
                if activity_id is None:
                    raise ProgressionError(
                        "progression_invalid_play",
                        "game_kind must be monopoly or life_paths",
                    )
                recorded = self._run_real_mutation(
                    lambda: self.progression.record_play(
                        actor_id=actor.member.member_id,
                        model_id=actor.member.model_id,
                        activity_id=activity_id,
                        game_ref=game_ref,
                        game_kind=game_kind,
                    )
                )
                response = {
                    "status": "ok",
                    **recorded,
                    "game_kind": game_kind,
                    "authority_effect": "none",
                }
            elif operation == "life.paths.catalog":
                self._require_exact_fields(request, operation, set())
                response = {"status": "ok", "catalog": life_paths_catalog()}
            elif operation == "life.paths.new":
                self._require_exact_fields(request, operation, {"seed", "players", "human_players"})
                seed = request.get("seed", "long-road-home")
                players = request.get("players", ["Alpha"])
                human_players = request.get("human_players", [])
                if not isinstance(seed, str):
                    raise ProgressionError("progression_invalid_play", "Life Paths seed must be text")
                if not isinstance(players, list) or not all(isinstance(item, str) for item in players):
                    raise ProgressionError("progression_invalid_play", "Life Paths players must be a list of ids")
                if not isinstance(human_players, list) or not all(isinstance(item, str) for item in human_players):
                    raise ProgressionError("progression_invalid_play", "Life Paths human_players must be a list of ids")
                for player in [*players, *human_players]:
                    if self.scrubber.scrub(player).changed:
                        raise ProgressionError(
                            "progression_secret_rejected",
                            "Life Paths player ids must not contain credential-shaped material",
                        )
                clean_seed = self.scrubber.scrub(seed)
                state = self._run_real_mutation(
                    lambda: new_life_paths(
                        self.world,
                        seed=clean_seed.text,
                        players=players,
                        human_players=human_players,
                    )
                )
                response = {
                    "status": "ok",
                    "game_ref": state.object_id,
                    "game": state.payload,
                    "secret_scrub": {"seed_changed": clean_seed.changed},
                }
            elif operation == "life.paths.inspect":
                self._require_exact_fields(request, operation, {"game_ref"})
                state = inspect_life_paths(self.world, self._require_str(request, "game_ref"))
                response = {"status": "ok", "game_ref": state.object_id, "game": state.payload}
            elif operation == "life.paths.act":
                self._require_exact_fields(request, operation, {"game_ref", "player_id", "choice_id"})
                game_ref = self._require_str(request, "game_ref")
                player_id = self._require_str(request, "player_id")
                choice_id = self._require_str(request, "choice_id")
                state = self._run_real_mutation(
                    lambda: apply_life_paths_choice(
                        self.world,
                        game_ref,
                        player_id=player_id,
                        choice_id=choice_id,
                    )
                )
                response = {"status": "ok", "game_ref": state.object_id, "game": state.payload}
            else:  # pragma: no cover
                return self._error(request_id, "unknown_operation", "operation is not supported")
        except ProgressionError as exc:
            return self._progression_error(request_id, exc)
        except WorldContinuityError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
            return self._error(request_id, exc.code, str(exc))
        except (KeyError, OSError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None

        if isinstance(operation, str) and operation in _PROGRESSION_OPERATIONS:
            try:
                validate_control_request(request)
            except (RequestBudgetError, RecursionError) as exc:
                return self._error(safe_request_id, "invalid_request", str(exc))
            if request_id is not None and safe_request_id is None:
                return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
            if operation in _PROGRESSION_MUTATIONS:
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
            return self._handle_progression_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in PROGRESSION_RESERVED_OBJECT_TYPES:
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved progression objects require validated progression operations",
                )

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "ai_progression": {
                    "status": "ok",
                    "policy": progression_policy_snapshot(),
                    "life_paths": {
                        "schema": life_paths_catalog()["schema"],
                        "original_nexus_game": True,
                        "authority_effect": "none",
                    },
                },
            }
        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_PROGRESSION_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}
        return response


__all__ = ["ProgressionNexusAPI"]
