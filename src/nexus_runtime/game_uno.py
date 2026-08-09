from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from .game_cards import (
    append_event,
    clean_seed,
    deterministic_shuffle,
    exact_int,
    player_roster,
    require_args,
    require_player,
)
from .world import WorldObject, WorldStore


UNO_SCHEMA = "nexus-uno/1"
UNO_KIND = "deterministic_human_ai_uno"
UNO_TITLE = "NEXUS UNO"
COLORS = ("red", "yellow", "green", "blue")
WILD_RANKS = {"wild", "wild4"}
ACTION_RANKS = {"skip", "reverse", "draw2"}
_CLAIM_BOUNDARY = {
    "fictional_game": True,
    "human_and_ai_players": True,
    "model_narration_mutates_state": False,
    "hidden_hands_are_public_evidence": False,
}

UNO_ACTIONS = (
    {"action": "play", "args": ["card_id", "chosen_color_for_wild"], "description": "Play one legal card."},
    {"action": "draw", "args": [], "description": "Draw one card; then play that card or pass."},
    {"action": "pass", "args": [], "description": "End the turn after drawing."},
)


def action_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(UNO_ACTIONS))


def _deck() -> list[dict[str, str | None]]:
    cards: list[dict[str, str | None]] = []
    for color in COLORS:
        cards.append({"card_id": f"{color}-0", "color": color, "rank": "0"})
        for rank in tuple(str(value) for value in range(1, 10)) + tuple(sorted(ACTION_RANKS)):
            for copy_id in ("a", "b"):
                cards.append(
                    {"card_id": f"{color}-{rank}-{copy_id}", "color": color, "rank": rank}
                )
    for rank in ("wild", "wild4"):
        for copy_index in range(1, 5):
            cards.append({"card_id": f"{rank}-{copy_index}", "color": None, "rank": rank})
    return cards


def _card_label(card: dict[str, Any]) -> str:
    if card["color"] is None:
        return str(card["rank"]).upper()
    return f"{str(card['color']).upper()} {str(card['rank']).upper()}"


def _current_player(state: dict[str, Any]) -> str:
    return state["players"][state["turn_index"]]


def _board_content(state: dict[str, Any]) -> str:
    top = state["discard_pile"][-1]
    lines = [
        "NEXUS UNO — AUTHORITATIVE PUBLIC TABLE",
        f"phase={state['phase']} current_player={_current_player(state) if state['winner'] is None else '-'} "
        f"direction={state['direction']} active_color={state['active_color']}",
        f"top_card={top['card_id']} ({_card_label(top)}) draw_pile={len(state['draw_pile'])}",
        "players:",
    ]
    for player in state["players"]:
        marker = " <- turn" if state["winner"] is None and player == _current_player(state) else ""
        lines.append(
            f"- {player} controller={state['controllers'][player]} cards={len(state['hands'][player])}{marker}"
        )
    if state["winner"] is not None:
        lines.append(f"winner={state['winner']}")
    if state["event_log"]:
        lines.append(f"latest_event={state['event_log'][-1]['text']}")
    lines.append("hidden_hands=redacted; narration_does_not_mutate_state=true")
    return "\n".join(lines)


def _new_state(seed: str, players: Sequence[str], human_players: Sequence[str]) -> dict[str, Any]:
    roster, controllers = player_roster(
        players, human_players=human_players, minimum=2, maximum=8
    )
    draw_pile = deterministic_shuffle(_deck(), seed, "uno-initial-deck")
    hands = {player: [] for player in roster}
    for _ in range(7):
        for player in roster:
            hands[player].append(draw_pile.pop())

    # A numeric opener keeps the initial transition free of unresolved action
    # effects while preserving the deterministic deck permutation.
    numeric_index = next(
        index
        for index in range(len(draw_pile) - 1, -1, -1)
        if draw_pile[index]["color"] is not None and str(draw_pile[index]["rank"]).isdigit()
    )
    draw_pile[numeric_index], draw_pile[-1] = draw_pile[-1], draw_pile[numeric_index]
    opener = draw_pile.pop()
    state: dict[str, Any] = {
        "schema": UNO_SCHEMA,
        "game_kind": UNO_KIND,
        "title": UNO_TITLE,
        "seed": seed,
        "players": roster,
        "controllers": controllers,
        "turn_index": 0,
        "direction": 1,
        "phase": "play",
        "hands": hands,
        "draw_pile": draw_pile,
        "discard_pile": [opener],
        "active_color": opener["color"],
        "drawn_card_id": None,
        "winner": None,
        "transition_count": 0,
        "event_log": [
            {
                "sequence": 0,
                "kind": "new_game",
                "text": f"{roster[0]} opens after {_card_label(opener)}.",
            }
        ],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "claim_boundary": deepcopy(_CLAIM_BOUNDARY),
    }
    state["content"] = _board_content(state)
    return state


def new_uno(
    world: WorldStore,
    seed: str = "reverse-card-night",
    players: Sequence[str] = ("operator", "Alpha"),
    human_players: Sequence[str] = (),
) -> WorldObject:
    state = _new_state(clean_seed(seed, "reverse-card-night"), players, human_players)
    return world.create_object(
        "uno_game_state", state, {"actor": "nexus_game_engine", "reason": "new_uno_game"}
    )


def _all_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    cards = list(state["draw_pile"]) + list(state["discard_pile"])
    for player in state["players"]:
        cards.extend(state["hands"][player])
    return cards


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != UNO_SCHEMA or state.get("game_kind") != UNO_KIND:
        raise ValueError("unsupported UNO game state schema")
    if state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("UNO claim boundary is invalid")
    players = state.get("players")
    if not isinstance(players, list):
        raise ValueError("UNO players must be a list")
    controllers = state.get("controllers")
    if not isinstance(controllers, dict):
        raise ValueError("UNO controllers must be an object")
    _, expected_controllers = player_roster(
        players,
        human_players=[p for p in players if controllers.get(p) == "human"],
        minimum=2,
        maximum=8,
    )
    if controllers != expected_controllers:
        raise ValueError("UNO controllers must mark at least one human and all other seats as AI")
    exact_int(state.get("turn_index"), "UNO turn_index", minimum=0)
    if state["turn_index"] >= len(players):
        raise ValueError("UNO turn_index is outside the player roster")
    if state.get("direction") not in (-1, 1):
        raise ValueError("UNO direction must be -1 or 1")
    if state.get("phase") not in {"play", "drawn", "complete"}:
        raise ValueError("invalid UNO phase")
    hands = state.get("hands")
    if not isinstance(hands, dict) or set(hands) != set(players):
        raise ValueError("UNO hands must exactly match the player roster")
    if not isinstance(state.get("draw_pile"), list) or not isinstance(state.get("discard_pile"), list) or not state["discard_pile"]:
        raise ValueError("UNO piles are malformed")
    cards = _all_cards(state)
    if len(cards) != 108:
        raise ValueError("UNO state must conserve all 108 cards")
    ids = [card.get("card_id") for card in cards if isinstance(card, dict)]
    if len(ids) != 108 or len(set(ids)) != 108:
        raise ValueError("UNO card ids must be complete and unique")
    expected_cards = {
        (card["card_id"], card["color"], card["rank"]) for card in _deck()
    }
    observed_cards = {
        (card.get("card_id"), card.get("color"), card.get("rank")) for card in cards
    }
    if observed_cards != expected_cards:
        raise ValueError("UNO card records do not match the canonical deck")
    if state.get("active_color") not in COLORS:
        raise ValueError("UNO active_color is invalid")
    winner = state.get("winner")
    if winner is not None and (winner not in players or hands[winner]):
        raise ValueError("UNO winner must be a player with an empty hand")
    if (winner is None and state["phase"] == "complete") or (
        winner is not None and state["phase"] != "complete"
    ):
        raise ValueError("UNO completed state must use phase=complete")
    drawn_card_id = state.get("drawn_card_id")
    if state["phase"] == "drawn":
        if drawn_card_id not in {card["card_id"] for card in hands[_current_player(state)]}:
            raise ValueError("UNO drawn_card_id must identify a card in the current hand")
    elif drawn_card_id is not None:
        raise ValueError("UNO drawn_card_id is only valid during phase=drawn")
    if state.get("content") != _board_content(state):
        raise ValueError("UNO model-readable content view does not match authoritative state")


def inspect_uno(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "uno_game_state":
        raise ValueError("object is not an UNO game state")
    _validate_state(obj.payload)
    return obj


def _recycle(state: dict[str, Any]) -> None:
    if state["draw_pile"] or len(state["discard_pile"]) <= 1:
        return
    top = state["discard_pile"][-1]
    recyclable = state["discard_pile"][:-1]
    state["draw_pile"] = deterministic_shuffle(
        recyclable,
        state["seed"],
        f"uno-recycle-{state['transition_count']}",
    )
    state["discard_pile"] = [top]


def _draw_one(state: dict[str, Any], player: str) -> dict[str, Any]:
    _recycle(state)
    if not state["draw_pile"]:
        raise ValueError("UNO draw pile is exhausted")
    card = state["draw_pile"].pop()
    state["hands"][player].append(card)
    return card


def _advance(state: dict[str, Any], steps: int = 1) -> None:
    state["turn_index"] = (
        state["turn_index"] + state["direction"] * steps
    ) % len(state["players"])
    state["phase"] = "play"
    state["drawn_card_id"] = None


def _playable(card: dict[str, Any], state: dict[str, Any]) -> bool:
    top = state["discard_pile"][-1]
    return (
        card["rank"] in WILD_RANKS
        or card["color"] == state["active_color"]
        or card["rank"] == top["rank"]
    )


def _persist(
    world: WorldStore,
    previous_ref: str,
    state: dict[str, Any],
    transition: dict[str, Any],
) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "uno_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "uno_transition"},
    )


def apply_action(
    world: WorldStore,
    game_ref: str,
    player_id: str,
    action: str,
    args: Sequence[str] = (),
) -> WorldObject:
    current = inspect_uno(world, game_ref)
    state = deepcopy(current.payload)
    require_player(state, player_id)
    if state["winner"] is not None:
        raise ValueError("UNO game is complete")
    if player_id != _current_player(state):
        raise ValueError("it is not that player's UNO turn")
    action = action.strip().lower() if isinstance(action, str) else ""
    args = require_args(args, maximum=2)
    state["transition_count"] += 1

    if action == "draw":
        if args or state["phase"] != "play":
            raise ValueError("draw is available once at the start of an UNO turn")
        card = _draw_one(state, player_id)
        state["phase"] = "drawn"
        state["drawn_card_id"] = card["card_id"]
        append_event(state, "draw", f"{player_id} draws one card.", player_id=player_id)
    elif action == "pass":
        if args or state["phase"] != "drawn":
            raise ValueError("pass is only available after drawing")
        append_event(state, "pass", f"{player_id} passes after drawing.", player_id=player_id)
        _advance(state)
    elif action == "play":
        if not args:
            raise ValueError("play requires a card_id")
        card_id = args[0]
        hand = state["hands"][player_id]
        card = next((item for item in hand if item["card_id"] == card_id), None)
        if card is None:
            raise ValueError("card is not in the player's UNO hand")
        if state["phase"] == "drawn" and card_id != state["drawn_card_id"]:
            raise ValueError("after drawing, only the drawn UNO card may be played")
        if not _playable(card, state):
            raise ValueError("UNO card does not match the active color or rank")
        if card["rank"] == "wild4" and any(
            item["card_id"] != card_id and item["color"] == state["active_color"]
            for item in hand
        ):
            raise ValueError("wild4 is illegal while the player holds the active color")
        chosen_color = args[1].lower() if len(args) == 2 else None
        if card["rank"] in WILD_RANKS:
            if chosen_color not in COLORS:
                raise ValueError("wild cards require chosen_color: red, yellow, green or blue")
        elif len(args) != 1:
            raise ValueError("chosen_color is only accepted for wild cards")

        hand.remove(card)
        state["discard_pile"].append(card)
        state["active_color"] = chosen_color or card["color"]
        append_event(
            state,
            "play",
            f"{player_id} plays {_card_label(card)}.",
            player_id=player_id,
            card_id=card_id,
        )
        if not hand:
            state["winner"] = player_id
            state["phase"] = "complete"
            state["drawn_card_id"] = None
            append_event(state, "win", f"{player_id} wins NEXUS UNO.", player_id=player_id)
        elif card["rank"] == "reverse":
            state["direction"] *= -1
            _advance(state, 2 if len(state["players"]) == 2 else 1)
        elif card["rank"] == "skip":
            _advance(state, 2)
        elif card["rank"] in {"draw2", "wild4"}:
            penalty = 2 if card["rank"] == "draw2" else 4
            target_index = (state["turn_index"] + state["direction"]) % len(state["players"])
            target = state["players"][target_index]
            for _ in range(penalty):
                _draw_one(state, target)
            append_event(
                state,
                "draw_penalty",
                f"{target} draws {penalty} cards and is skipped.",
                player_id=target,
                count=penalty,
            )
            _advance(state, 2)
        else:
            _advance(state)
    else:
        raise ValueError("unknown UNO action")

    return _persist(
        world,
        current.object_id,
        state,
        {"kind": "action", "player_id": player_id, "action": action, "args": args},
    )


def player_view(state: dict[str, Any], player_id: str) -> dict[str, Any]:
    require_player(state, player_id)
    _validate_state(state)
    return {
        "schema": UNO_SCHEMA,
        "title": UNO_TITLE,
        "player_id": player_id,
        "controller": state["controllers"][player_id],
        "phase": state["phase"],
        "current_player": None if state["winner"] is not None else _current_player(state),
        "active_color": state["active_color"],
        "top_card": deepcopy(state["discard_pile"][-1]),
        "hand": deepcopy(state["hands"][player_id]),
        "opponent_card_counts": {
            player: len(state["hands"][player]) for player in state["players"] if player != player_id
        },
        "drawn_card_id": state["drawn_card_id"] if player_id == _current_player(state) else None,
        "winner": state["winner"],
        "legal_actions": [item["action"] for item in UNO_ACTIONS],
        "last_event": deepcopy(state["event_log"][-1]),
    }
