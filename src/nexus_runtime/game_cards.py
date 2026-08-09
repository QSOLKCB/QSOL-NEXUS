from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any, Iterable, Sequence, TypeVar

from .canonical import canonical_json


PLAYER_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
MAX_EVENT_LOG = 24
T = TypeVar("T")


def digest_int(*parts: object) -> int:
    material = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def deterministic_shuffle(items: Sequence[T], seed: str, domain: str) -> list[T]:
    """Return a stable permutation without process randomness.

    The original index is part of the key so duplicate values remain distinct.
    A deep copy prevents later state mutation from changing caller-owned input.
    """

    ranked = list(enumerate(items))
    ranked.sort(
        key=lambda pair: (
            digest_int(seed, domain, pair[0], canonical_json(pair[1])),
            pair[0],
        )
    )
    return [deepcopy(item) for _, item in ranked]


def clean_seed(seed: str, default: str) -> str:
    if not isinstance(seed, str):
        raise ValueError("game seed must be text")
    value = seed.strip() or default
    if len(value) > 128:
        raise ValueError("game seed must be at most 128 characters")
    return value


def player_roster(
    players: Sequence[str],
    *,
    human_players: Iterable[str] = (),
    minimum: int,
    maximum: int,
) -> tuple[list[str], dict[str, str]]:
    if isinstance(players, (str, bytes)) or not isinstance(players, Sequence):
        raise ValueError("players must be a list of player ids")
    if not minimum <= len(players) <= maximum:
        raise ValueError(f"game requires between {minimum} and {maximum} players")
    clean: list[str] = []
    folded: set[str] = set()
    for player in players:
        if not isinstance(player, str) or PLAYER_ID_RE.fullmatch(player) is None:
            raise ValueError("player ids must use 1-32 ASCII letters, digits, _, . or -")
        key = player.casefold()
        if key in folded:
            raise ValueError("player ids must be unique ignoring case")
        folded.add(key)
        clean.append(player)

    humans = set(human_players)
    if not humans:
        humans = {clean[0]}
    if not all(isinstance(player, str) for player in humans) or not humans.issubset(set(clean)):
        raise ValueError("human_players must name registered players")
    controllers = {player: ("human" if player in humans else "ai") for player in clean}
    return clean, controllers


def require_player(state: dict[str, Any], player_id: str) -> None:
    if not isinstance(player_id, str) or player_id not in state.get("players", []):
        raise ValueError("unknown game player")


def require_args(args: Sequence[str], *, maximum: int = 8) -> list[str]:
    if isinstance(args, (str, bytes)) or not isinstance(args, Sequence):
        raise ValueError("args must be a list of strings")
    if len(args) > maximum or not all(isinstance(arg, str) and 0 < len(arg) <= 64 for arg in args):
        raise ValueError(f"args must contain at most {maximum} bounded non-empty strings")
    return list(args)


def append_event(state: dict[str, Any], kind: str, text: str, **extra: Any) -> None:
    sequence = state.get("transition_count", 0)
    state.setdefault("event_log", []).append(
        {"sequence": sequence, "kind": kind, "text": text, **extra}
    )
    state["event_log"] = state["event_log"][-MAX_EVENT_LOG:]


def next_live_player(players: Sequence[str], inactive: set[str], current_index: int) -> int:
    for offset in range(1, len(players) + 1):
        candidate = (current_index + offset) % len(players)
        if players[candidate] not in inactive:
            return candidate
    return current_index


def exact_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an exact integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value
