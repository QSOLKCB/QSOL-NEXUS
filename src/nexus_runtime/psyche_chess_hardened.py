from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Sequence

from . import psyche_chess as _base
from .world import WorldObject, WorldStore


INITIAL_FEN = _base.INITIAL_FEN
MAX_PSYCHE_CHARS = _base.MAX_PSYCHE_CHARS
PSYCHE_CHESS_KIND = _base.PSYCHE_CHESS_KIND
PSYCHE_CHESS_SCHEMA = _base.PSYCHE_CHESS_SCHEMA
PSYCHE_CHESS_TITLE = _base.PSYCHE_CHESS_TITLE
extract_legal_uci = _base.extract_legal_uci
legal_moves_for_fen = _base.legal_moves_for_fen
new_psyche_chess = _base.new_psyche_chess
psyche_chess_catalog = _base.psyche_chess_catalog


def _validate_successor_shape(state: dict[str, Any]) -> None:
    ply = state.get("ply")
    previous = state.get("previous_state_ref")
    transition = state.get("last_transition")
    if not isinstance(transition, dict) or not isinstance(transition.get("kind"), str):
        raise ValueError("Psyche-Out Chess transition metadata is invalid")
    kind = transition["kind"]
    if kind == "new_game":
        if ply != 0 or previous is not None or state.get("pending_psyche") is not None:
            raise ValueError("new Psyche-Out Chess state must be the unique predecessor-free genesis state")
        return
    if not isinstance(previous, str) or not previous:
        raise ValueError("Psyche-Out Chess successor state must bind its predecessor")
    if kind == "psyche":
        if state.get("pending_psyche") is None:
            raise ValueError("psyche transition must leave one pending psyche line")
    elif kind == "move":
        if type(ply) is not int or ply < 1 or state.get("pending_psyche") is not None:
            raise ValueError("move transition must advance ply and consume pending psyche text")
    else:
        raise ValueError("Psyche-Out Chess transition kind is invalid")


def inspect_psyche_chess(world: WorldStore, state_ref: str) -> WorldObject:
    obj = world.inspect(state_ref)
    if obj.object_type != "psyche_chess_state":
        raise ValueError("object is not a Psyche-Out Chess state")
    payload = obj.payload
    _validate_successor_shape(payload)

    # The PR #48 base validator correctly validates chess/FEN/controller/banter
    # semantics but its genesis shortcut originally assumed every ply=0 state
    # had no predecessor. For a pre-first-move psyche successor, validate an
    # equivalent temporary shape with only that genesis shortcut neutralized;
    # content does not depend on previous_state_ref.
    if payload.get("last_transition", {}).get("kind") == "psyche" and payload.get("ply") == 0:
        adjusted = deepcopy(payload)
        adjusted["previous_state_ref"] = None
        _base._validate(adjusted)
    else:
        _base._validate(payload)
    return obj


def add_psyche(world: WorldStore, state_ref: str, *, from_player: str, text: str) -> WorldObject:
    current = inspect_psyche_chess(world, state_ref)
    state = current.payload
    if state["completed"]:
        raise ValueError("Psyche-Out Chess is already complete")
    if state["pending_psyche"] is not None:
        raise ValueError("a psyche line is already pending for this turn")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_PSYCHE_CHARS:
        raise ValueError(f"psyche text must be 1-{MAX_PSYCHE_CHARS} characters")
    position = _base._parse_fen(state["fen"])
    current_player = state["colors"][position["turn"]]
    opponent = state["colors"][_base._enemy(position["turn"])]
    if from_player != opponent:
        raise ValueError("only the opponent of the side to move may deliver the psyche line")
    pending = {
        "from_player": from_player,
        "to_player": current_player,
        "text": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    successor = _base._build_state(
        players=state["players"],
        controllers=state["controllers"],
        colors=state["colors"],
        fen=state["fen"],
        ply=state["ply"],
        previous_state_ref=current.object_id,
        pending_psyche=pending,
        last_transition={"kind": "psyche", "from_player": from_player, "to_player": current_player, "sha256": pending["sha256"]},
        event_log=state["event_log"] + [{"sequence": len(state["event_log"]), "kind": "psyche", "from_player": from_player, "to_player": current_player, "sha256": pending["sha256"]}],
    )
    return world.create_object(
        "psyche_chess_state",
        successor,
        {"actor": "nexus_game_engine", "reason": "psyche_chess_taunt"},
    )


def apply_psyche_chess_move(world: WorldStore, state_ref: str, *, player_id: str, move: str) -> WorldObject:
    current = inspect_psyche_chess(world, state_ref)
    state = current.payload
    if state["completed"]:
        raise ValueError("Psyche-Out Chess is already complete")
    if not isinstance(move, str) or _base.UCI_RE.fullmatch(move) is None:
        raise ValueError("move must use bounded UCI notation")
    position = _base._parse_fen(state["fen"])
    current_player = state["colors"][position["turn"]]
    if player_id != current_player:
        raise ValueError("it is not that player's chess turn")
    if move not in state["legal_moves"]:
        raise ValueError("move is not legal in the current chess position")
    parsed = (move[:2], move[2:4], move[4] if len(move) == 5 else None)
    next_position = _base._apply_unchecked(position, parsed)
    next_fen = _base._fen(next_position)
    psyche = state["pending_psyche"]
    successor = _base._build_state(
        players=state["players"],
        controllers=state["controllers"],
        colors=state["colors"],
        fen=next_fen,
        ply=state["ply"] + 1,
        previous_state_ref=current.object_id,
        pending_psyche=None,
        last_transition={
            "kind": "move",
            "player_id": player_id,
            "move": move,
            "psyche_sha256": None if psyche is None else psyche["sha256"],
        },
        event_log=state["event_log"] + [{
            "sequence": len(state["event_log"]),
            "kind": "move",
            "player_id": player_id,
            "move": move,
            "psyche_sha256": None if psyche is None else psyche["sha256"],
        }],
    )
    return world.create_object(
        "psyche_chess_state",
        successor,
        {"actor": "nexus_game_engine", "reason": "psyche_chess_move"},
    )


__all__ = [
    "INITIAL_FEN",
    "MAX_PSYCHE_CHARS",
    "PSYCHE_CHESS_KIND",
    "PSYCHE_CHESS_SCHEMA",
    "PSYCHE_CHESS_TITLE",
    "add_psyche",
    "apply_psyche_chess_move",
    "extract_legal_uci",
    "inspect_psyche_chess",
    "legal_moves_for_fen",
    "new_psyche_chess",
    "psyche_chess_catalog",
]
