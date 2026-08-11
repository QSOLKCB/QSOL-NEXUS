from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from . import long_shift as _long
from .psyche_chess_hardened import apply_psyche_chess_move, inspect_psyche_chess
from .world import WorldObject, WorldStore


AI_GAME_EXECUTION_SCHEMA = "nexus-ai-game-execution/1"
AI_GAME_EXECUTION_OBJECT_TYPE = "nexus_ai_game_execution"
_AI_EXECUTION_PROVENANCE = {"actor": "nexus", "subsystem": "ai_game_execution"}
_EXECUTION_FIELDS = {
    "schema",
    "game_kind",
    "predecessor_ref",
    "member_id",
    "model_id",
    "action_kind",
    "action_value",
    "model_output_sha256",
    "authority_effect",
}


def create_ai_game_execution(
    world: WorldStore,
    *,
    game_kind: str,
    predecessor_ref: str,
    member_id: str,
    model_id: str,
    action_kind: str,
    action_value: str,
    model_output: str,
) -> WorldObject:
    if game_kind not in {"long_shift", "psyche_chess"}:
        raise ValueError("unsupported AI game execution kind")
    for name, value in {
        "predecessor_ref": predecessor_ref,
        "member_id": member_id,
        "model_id": model_id,
        "action_kind": action_kind,
        "action_value": action_value,
        "model_output": model_output,
    }.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be non-empty text")
    world.inspect(predecessor_ref)
    return world.create_object(
        AI_GAME_EXECUTION_OBJECT_TYPE,
        {
            "schema": AI_GAME_EXECUTION_SCHEMA,
            "game_kind": game_kind,
            "predecessor_ref": predecessor_ref,
            "member_id": member_id,
            "model_id": model_id,
            "action_kind": action_kind,
            "action_value": action_value,
            "model_output_sha256": hashlib.sha256(model_output.encode("utf-8")).hexdigest(),
            "authority_effect": "none",
        },
        dict(_AI_EXECUTION_PROVENANCE),
    )


def inspect_ai_game_execution(
    world: WorldStore,
    execution_ref: str,
    *,
    game_kind: str,
    predecessor_ref: str,
    member_id: str,
    action_kind: str,
    action_value: str,
) -> WorldObject:
    obj = world.inspect(execution_ref)
    payload = obj.payload
    if (
        obj.object_type != AI_GAME_EXECUTION_OBJECT_TYPE
        or obj.provenance != _AI_EXECUTION_PROVENANCE
        or set(payload) != _EXECUTION_FIELDS
        or payload.get("schema") != AI_GAME_EXECUTION_SCHEMA
        or payload.get("game_kind") != game_kind
        or payload.get("predecessor_ref") != predecessor_ref
        or payload.get("member_id") != member_id
        or payload.get("action_kind") != action_kind
        or payload.get("action_value") != action_value
        or not isinstance(payload.get("model_id"), str)
        or not payload["model_id"]
        or not isinstance(payload.get("model_output_sha256"), str)
        or len(payload["model_output_sha256"]) != 64
        or payload.get("authority_effect") != "none"
    ):
        raise ValueError("AI game execution receipt is invalid")
    try:
        int(payload["model_output_sha256"], 16)
    except ValueError as exc:
        raise ValueError("AI game execution receipt hash is invalid") from exc
    return obj


def apply_attested_long_shift_choice(
    world: WorldStore,
    state_ref: str,
    *,
    player_id: str,
    choice_id: str,
    execution_ref: str,
) -> WorldObject:
    current = _long.inspect_long_shift(world, state_ref)
    scratch = WorldStore()
    prior = scratch.create_object(
        "long_shift_state",
        deepcopy(current.payload),
        dict(current.provenance),
    )
    if prior.object_id != current.object_id:
        raise ValueError("Long Shift predecessor identity is not canonical")
    expected = _long.apply_long_shift_choice(
        scratch,
        prior.object_id,
        player_id=player_id,
        choice_id=choice_id,
    )
    payload = deepcopy(expected.payload)
    payload["last_transition"] = dict(payload["last_transition"])
    payload["last_transition"]["execution_ref"] = execution_ref
    return world.create_object(
        "long_shift_state",
        payload,
        {"actor": "nexus_game_engine", "reason": "long_shift_transition"},
    )


def apply_attested_psyche_chess_move(
    world: WorldStore,
    state_ref: str,
    *,
    player_id: str,
    move: str,
    execution_ref: str,
) -> WorldObject:
    current = inspect_psyche_chess(world, state_ref)
    scratch = WorldStore()
    prior = scratch.create_object(
        "psyche_chess_state",
        deepcopy(current.payload),
        dict(current.provenance),
    )
    if prior.object_id != current.object_id:
        raise ValueError("Psyche-Out Chess predecessor identity is not canonical")
    expected = apply_psyche_chess_move(
        scratch,
        prior.object_id,
        player_id=player_id,
        move=move,
    )
    payload = deepcopy(expected.payload)
    payload["last_transition"] = dict(payload["last_transition"])
    payload["last_transition"]["execution_ref"] = execution_ref
    return world.create_object(
        "psyche_chess_state",
        payload,
        {"actor": "nexus_game_engine", "reason": "psyche_chess_move"},
    )


__all__ = [
    "AI_GAME_EXECUTION_OBJECT_TYPE",
    "AI_GAME_EXECUTION_SCHEMA",
    "apply_attested_long_shift_choice",
    "apply_attested_psyche_chess_move",
    "create_ai_game_execution",
    "inspect_ai_game_execution",
]
