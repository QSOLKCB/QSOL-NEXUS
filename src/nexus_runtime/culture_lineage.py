from __future__ import annotations

from copy import deepcopy
from typing import Any

from . import long_shift as _long
from . import psyche_chess as _chess
from .culture_execution import inspect_ai_game_execution
from .psyche_chess_hardened import (
    MAX_PSYCHE_CHESS_LINEAGE_STATES,
    inspect_psyche_chess,
)
from .world import WorldObject, WorldStore


# Backward-compatible public name; the engine and verifier now share this exact
# admitted limit so a history allowed to complete cannot fail later for length.
MAX_CHESS_LINEAGE_STATES = MAX_PSYCHE_CHESS_LINEAGE_STATES


def _append_log(previous: list[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
    return (list(previous) + [event])[-64:]


def _next_event_sequence(previous: list[dict[str, Any]]) -> int:
    if not previous:
        raise ValueError("game event log is empty")
    sequence = previous[-1].get("sequence")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("game event sequence is invalid")
    return sequence + 1


def _validate_claimed_execution(
    *,
    claimed_actor_id: str | None,
    claimed_model_id: str | None,
    execution_models: dict[str, set[str]],
    controllers: dict[str, str],
) -> None:
    if claimed_actor_id is None and claimed_model_id is None:
        return
    if not isinstance(claimed_actor_id, str) or not claimed_actor_id or not isinstance(claimed_model_id, str) or not claimed_model_id:
        raise ValueError("claimed AI progression identity is invalid")
    if controllers.get(claimed_actor_id) != "ai":
        raise ValueError("claimed progression actor is not an AI-controlled seat")
    models = execution_models.get(claimed_actor_id, set())
    if not models:
        raise ValueError("claimed AI seat has no runtime-owned model execution in this game")
    if models != {claimed_model_id}:
        raise ValueError("claimed model identity does not match the AI executions bound to this seat")


def verify_long_shift_lineage(
    world: WorldStore,
    state_ref: str,
    *,
    claimed_actor_id: str | None = None,
    claimed_model_id: str | None = None,
) -> WorldObject:
    """Verify a complete Long Shift chain by deterministic transition replay."""

    current = _long.inspect_long_shift(world, state_ref)
    chain_rev: list[WorldObject] = []
    seen: set[str] = set()
    cursor = current
    while True:
        if cursor.object_id in seen:
            raise ValueError("Long Shift lineage is cyclic")
        seen.add(cursor.object_id)
        chain_rev.append(cursor)
        previous_ref = cursor.payload["previous_state_ref"]
        if previous_ref is None:
            break
        if len(chain_rev) > len(_long.SCENES) + 1:
            raise ValueError("Long Shift lineage exceeds the closed scene budget")
        cursor = _long.inspect_long_shift(world, previous_ref)

    chain = list(reversed(chain_rev))
    genesis = chain[0]
    expected_genesis = _long.new_long_shift(
        WorldStore(),
        seed=genesis.payload["seed"],
        players=genesis.payload["players"],
        human_players=[
            player for player, controller in genesis.payload["controllers"].items() if controller == "human"
        ],
    )
    if (
        genesis.payload != expected_genesis.payload
        or genesis.provenance != {"actor": "nexus_game_engine", "reason": "new_long_shift_game"}
    ):
        raise ValueError("Long Shift genesis state is not engine-canonical")

    execution_models: dict[str, set[str]] = {}
    for index, successor in enumerate(chain[1:], start=1):
        predecessor = chain[index - 1]
        transition = successor.payload.get("last_transition")
        if not isinstance(transition, dict) or transition.get("kind") != "choice":
            raise ValueError("Long Shift successor does not contain a choice transition")
        if successor.payload.get("previous_state_ref") != predecessor.object_id:
            raise ValueError("Long Shift predecessor binding is invalid")
        player_id = transition.get("player_id")
        choice_id = transition.get("choice_id")
        if not isinstance(player_id, str) or not isinstance(choice_id, str):
            raise ValueError("Long Shift transition identity is invalid")

        execution_ref = transition.get("execution_ref")
        controller = predecessor.payload["controllers"].get(player_id)
        if controller == "ai":
            if not isinstance(execution_ref, str) or not execution_ref:
                raise ValueError("AI Long Shift turn lacks a runtime-owned execution binding")
            execution = inspect_ai_game_execution(
                world,
                execution_ref,
                game_kind="long_shift",
                predecessor_ref=predecessor.object_id,
                member_id=player_id,
                action_kind="choice",
                action_value=choice_id,
            )
            execution_models.setdefault(player_id, set()).add(execution.payload["model_id"])
        elif controller == "human":
            if execution_ref is not None:
                raise ValueError("human Long Shift turn must not claim an AI execution binding")
        else:
            raise ValueError("Long Shift controller binding is invalid")

        scratch = WorldStore()
        prior_copy = scratch.create_object(
            "long_shift_state",
            deepcopy(predecessor.payload),
            dict(predecessor.provenance),
        )
        if prior_copy.object_id != predecessor.object_id:
            raise ValueError("Long Shift predecessor object identity is not canonical")
        expected = _long.apply_long_shift_choice(
            scratch,
            prior_copy.object_id,
            player_id=player_id,
            choice_id=choice_id,
        )
        expected_payload = deepcopy(expected.payload)
        if execution_ref is not None:
            expected_payload["last_transition"] = dict(expected_payload["last_transition"])
            expected_payload["last_transition"]["execution_ref"] = execution_ref
        if (
            successor.payload != expected_payload
            or successor.provenance != {"actor": "nexus_game_engine", "reason": "long_shift_transition"}
        ):
            raise ValueError("Long Shift successor does not replay from its predecessor")

    _validate_claimed_execution(
        claimed_actor_id=claimed_actor_id,
        claimed_model_id=claimed_model_id,
        execution_models=execution_models,
        controllers=genesis.payload["controllers"],
    )
    return current


def _canonical_chess_genesis(payload: dict[str, Any]) -> dict[str, Any]:
    scratch = WorldStore()
    genesis = _chess.new_psyche_chess(
        scratch,
        white_player=payload["colors"]["w"],
        black_player=payload["colors"]["b"],
        human_players=[
            player for player, controller in payload["controllers"].items() if controller == "human"
        ],
    )
    return genesis.payload


def verify_psyche_chess_lineage(
    world: WorldStore,
    state_ref: str,
    *,
    claimed_actor_id: str | None = None,
    claimed_model_id: str | None = None,
) -> WorldObject:
    """Verify Psyche-Out Chess lineage and replay every taunt/move transition."""

    current = inspect_psyche_chess(world, state_ref)
    chain_rev: list[WorldObject] = []
    seen: set[str] = set()
    cursor = current
    while True:
        if cursor.object_id in seen:
            raise ValueError("Psyche-Out Chess lineage is cyclic")
        seen.add(cursor.object_id)
        chain_rev.append(cursor)
        if len(chain_rev) > MAX_CHESS_LINEAGE_STATES:
            raise ValueError("Psyche-Out Chess lineage exceeds the engine-enforced admitted bound")
        previous_ref = cursor.payload["previous_state_ref"]
        if previous_ref is None:
            break
        cursor = inspect_psyche_chess(world, previous_ref)

    chain = list(reversed(chain_rev))
    genesis = chain[0]
    if (
        genesis.payload != _canonical_chess_genesis(genesis.payload)
        or genesis.provenance != {"actor": "nexus_game_engine", "reason": "new_psyche_chess_game"}
    ):
        raise ValueError("Psyche-Out Chess genesis state is not engine-canonical")

    execution_models: dict[str, set[str]] = {}
    for index, successor in enumerate(chain[1:], start=1):
        predecessor = chain[index - 1]
        payload = successor.payload
        transition = payload.get("last_transition")
        if not isinstance(transition, dict) or payload.get("previous_state_ref") != predecessor.object_id:
            raise ValueError("Psyche-Out Chess predecessor binding is invalid")
        kind = transition.get("kind")
        expected_sequence = _next_event_sequence(predecessor.payload["event_log"])
        if kind == "psyche":
            if successor.provenance != {"actor": "nexus_game_engine", "reason": "psyche_chess_taunt"}:
                raise ValueError("Psyche-Out Chess psyche provenance is invalid")
            if transition.get("execution_ref") is not None:
                raise ValueError("Psyche banter transition must not masquerade as a chess-move execution")
            pending = payload.get("pending_psyche")
            if not isinstance(pending, dict):
                raise ValueError("Psyche-Out Chess psyche transition lacks pending banter")
            if predecessor.payload.get("pending_psyche") is not None:
                raise ValueError("Psyche-Out Chess cannot stack pending psyche lines")
            if payload["fen"] != predecessor.payload["fen"] or payload["ply"] != predecessor.payload["ply"]:
                raise ValueError("Psyche-Out Chess psyche transition changed chess state")
            expected_pending = {
                "from_player": transition.get("from_player"),
                "to_player": transition.get("to_player"),
                "text": pending.get("text"),
                "sha256": pending.get("sha256"),
            }
            if pending != expected_pending or transition.get("sha256") != pending.get("sha256"):
                raise ValueError("Psyche-Out Chess psyche transition binding is invalid")
            expected_event = {
                "sequence": expected_sequence,
                "kind": "psyche",
                "from_player": pending["from_player"],
                "to_player": pending["to_player"],
                "sha256": pending["sha256"],
            }
            if payload["event_log"] != _append_log(predecessor.payload["event_log"], expected_event):
                raise ValueError("Psyche-Out Chess psyche event lineage is invalid")
        elif kind == "move":
            if successor.provenance != {"actor": "nexus_game_engine", "reason": "psyche_chess_move"}:
                raise ValueError("Psyche-Out Chess move provenance is invalid")
            move = transition.get("move")
            player_id = transition.get("player_id")
            if not isinstance(move, str) or not isinstance(player_id, str):
                raise ValueError("Psyche-Out Chess move transition is invalid")
            position = _chess._parse_fen(predecessor.payload["fen"])
            current_player = predecessor.payload["colors"][position["turn"]]
            if player_id != current_player or move not in predecessor.payload["legal_moves"]:
                raise ValueError("Psyche-Out Chess move was not legal for the bound predecessor")

            execution_ref = transition.get("execution_ref")
            controller = predecessor.payload["controllers"].get(player_id)
            if controller == "ai":
                if not isinstance(execution_ref, str) or not execution_ref:
                    raise ValueError("AI Psyche-Out Chess move lacks a runtime-owned execution binding")
                execution = inspect_ai_game_execution(
                    world,
                    execution_ref,
                    game_kind="psyche_chess",
                    predecessor_ref=predecessor.object_id,
                    member_id=player_id,
                    action_kind="move",
                    action_value=move,
                )
                execution_models.setdefault(player_id, set()).add(execution.payload["model_id"])
            elif controller == "human":
                if execution_ref is not None:
                    raise ValueError("human chess move must not claim an AI execution binding")
            else:
                raise ValueError("Psyche-Out Chess controller binding is invalid")

            parsed = (move[:2], move[2:4], move[4] if len(move) == 5 else None)
            expected_fen = _chess._fen(_chess._apply_unchecked(position, parsed))
            expected_psyche = predecessor.payload.get("pending_psyche")
            expected_hash = None if expected_psyche is None else expected_psyche["sha256"]
            if (
                payload["fen"] != expected_fen
                or payload["ply"] != predecessor.payload["ply"] + 1
                or payload.get("pending_psyche") is not None
                or transition.get("psyche_sha256") != expected_hash
            ):
                raise ValueError("Psyche-Out Chess move successor does not replay from its predecessor")
            expected_event = {
                "sequence": expected_sequence,
                "kind": "move",
                "player_id": player_id,
                "move": move,
                "psyche_sha256": expected_hash,
            }
            if payload["event_log"] != _append_log(predecessor.payload["event_log"], expected_event):
                raise ValueError("Psyche-Out Chess move event lineage is invalid")
        else:
            raise ValueError("Psyche-Out Chess transition kind is invalid")

        for field in ("players", "controllers", "colors", "claim_boundary"):
            if payload[field] != predecessor.payload[field]:
                raise ValueError(f"Psyche-Out Chess immutable field changed across lineage: {field}")

    _validate_claimed_execution(
        claimed_actor_id=claimed_actor_id,
        claimed_model_id=claimed_model_id,
        execution_models=execution_models,
        controllers=genesis.payload["controllers"],
    )
    return current


__all__ = ["MAX_CHESS_LINEAGE_STATES", "verify_long_shift_lineage", "verify_psyche_chess_lineage"]
