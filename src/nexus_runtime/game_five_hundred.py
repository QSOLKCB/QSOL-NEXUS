from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Sequence

from .game_cards import (
    append_event,
    clean_seed,
    deterministic_shuffle,
    digest_int,
    exact_int,
    player_roster,
    require_args,
    require_player,
)
from .world import WorldObject, WorldStore


FIVE_HUNDRED_SCHEMA = "nexus-five-hundred/1"
FIVE_HUNDRED_KIND = "deterministic_human_ai_partnership_500"
FIVE_HUNDRED_TITLE = "NEXUS 500"
SUITS = ("spades", "clubs", "diamonds", "hearts")
SUIT_CODES = {"S": "spades", "C": "clubs", "D": "diamonds", "H": "hearts", "NT": None}
SUIT_ORDER = {"S": 0, "C": 1, "D": 2, "H": 3, "NT": 4}
CONTRACT_RE = re.compile(r"^(6|7|8|9|10)(S|C|D|H|NT)$")
RANKS = ("4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_POWER = {rank: index for index, rank in enumerate(RANKS, start=1)}
_CLAIM_BOUNDARY = {
    "fictional_game": True,
    "human_and_ai_players": True,
    "model_narration_mutates_state": False,
    "hidden_hands_are_public_evidence": False,
    "gambling_or_stakes": False,
}

FIVE_HUNDRED_ACTIONS = (
    {"action": "bid", "args": ["contract"], "description": "Bid 6-10 in S/C/D/H/NT, for example 7H or 8NT."},
    {"action": "pass", "args": [], "description": "Pass in the auction."},
    {"action": "discard", "args": ["card_id", "card_id", "card_id"], "description": "Declarer discards three after taking the kitty."},
    {"action": "play", "args": ["card_id"], "description": "Play one legal card and follow effective suit."},
)


def action_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(FIVE_HUNDRED_ACTIONS))


def _deck() -> list[dict[str, str | None]]:
    cards: list[dict[str, str | None]] = [{"card_id": "joker", "suit": None, "rank": "JOKER"}]
    for suit in SUITS:
        ranks = list(RANKS[1:])
        if suit in {"spades", "clubs"}:
            ranks.insert(0, "4")
        for rank in ranks:
            cards.append({"card_id": f"{suit}-{rank}", "suit": suit, "rank": rank})
    return cards


def _teams(players: Sequence[str]) -> dict[str, list[str]]:
    return {"team_0": [players[0], players[2]], "team_1": [players[1], players[3]]}


def _team_for(state: dict[str, Any], player: str) -> str:
    return "team_0" if player in state["teams"]["team_0"] else "team_1"


def _current_player(state: dict[str, Any]) -> str:
    return state["players"][state["current_player_index"]]


def _card_label(card: dict[str, Any]) -> str:
    if card["rank"] == "JOKER":
        return "JOKER"
    return f"{card['rank']} of {str(card['suit']).title()}"


def _contract(token: str) -> dict[str, Any]:
    normalized = token.strip().upper()
    match = CONTRACT_RE.fullmatch(normalized)
    if match is None:
        raise ValueError("500 contract must be 6-10 followed by S, C, D, H or NT")
    tricks = int(match.group(1))
    suit_code = match.group(2)
    points = 40 + SUIT_ORDER[suit_code] * 20 + (tricks - 6) * 100
    return {
        "token": normalized,
        "tricks": tricks,
        "suit_code": suit_code,
        "trump": SUIT_CODES[suit_code],
        "points": points,
        "rank": (tricks - 6) * 5 + SUIT_ORDER[suit_code],
    }


def _board_content(state: dict[str, Any]) -> str:
    contract = state["contract"]["token"] if state["contract"] else "none"
    lines = [
        "NEXUS 500 — AUTHORITATIVE PUBLIC TABLE",
        f"hand={state['hand_number']} phase={state['phase']} dealer={state['players'][state['dealer_index']]} "
        f"current_player={_current_player(state) if state['phase'] != 'complete' else '-'} contract={contract}",
        f"scores=team_0:{state['scores']['team_0']} team_1:{state['scores']['team_1']} "
        f"tricks=team_0:{state['tricks_won']['team_0']} team_1:{state['tricks_won']['team_1']}",
        "seats:",
    ]
    for index, player in enumerate(state["players"]):
        lines.append(
            f"- seat={index} player={player} controller={state['controllers'][player]} "
            f"team={_team_for(state, player)} cards={len(state['hands'][player])}"
        )
    if state["highest_bid"]:
        lines.append(f"highest_bid={state['highest_bid']['contract']['token']} by {state['highest_bid']['player_id']}")
    if state["current_trick"]:
        lines.append(
            "current_trick="
            + ", ".join(f"{play['player_id']}:{play['card']['card_id']}" for play in state["current_trick"])
        )
    if state["winner_team"]:
        lines.append(f"winner_team={state['winner_team']}")
    if state["event_log"]:
        lines.append(f"latest_event={state['event_log'][-1]['text']}")
    lines.append("hidden_hands_and_kitty=redacted; no_misere_profile=true; narration_mutates_state=false")
    return "\n".join(lines)


def _deal(state: dict[str, Any]) -> None:
    deck = deterministic_shuffle(
        _deck(), state["seed"], f"five-hundred-hand-{state['hand_number']}"
    )
    hands = {player: [] for player in state["players"]}
    first = (state["dealer_index"] + 1) % 4
    for _ in range(10):
        for offset in range(4):
            player = state["players"][(first + offset) % 4]
            hands[player].append(deck.pop())
    state.update(
        {
            "hands": hands,
            "kitty": deck,
            "discard_pile": [],
            "phase": "bidding",
            "current_player_index": first,
            "highest_bid": None,
            "passes": 0,
            "bid_history": [],
            "contract": None,
            "declarer": None,
            "current_trick": [],
            "completed_tricks": [],
            "tricks_won": {"team_0": 0, "team_1": 0},
        }
    )


def _new_state(seed: str, players: Sequence[str], human_players: Sequence[str]) -> dict[str, Any]:
    roster, controllers = player_roster(
        players, human_players=human_players, minimum=4, maximum=4
    )
    dealer_index = digest_int(seed, "five-hundred-dealer") % 4
    state: dict[str, Any] = {
        "schema": FIVE_HUNDRED_SCHEMA,
        "game_kind": FIVE_HUNDRED_KIND,
        "title": FIVE_HUNDRED_TITLE,
        "rules_profile": "australian-partnership-500-no-misere-v1",
        "seed": seed,
        "players": roster,
        "controllers": controllers,
        "teams": _teams(roster),
        "scores": {"team_0": 0, "team_1": 0},
        "dealer_index": dealer_index,
        "hand_number": 1,
        "winner_team": None,
        "transition_count": 0,
        "event_log": [],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "claim_boundary": deepcopy(_CLAIM_BOUNDARY),
    }
    _deal(state)
    state["event_log"] = [
        {
            "sequence": 0,
            "kind": "new_game",
            "text": f"{roster[dealer_index]} deals the first deterministic hand.",
        }
    ]
    state["content"] = _board_content(state)
    return state


def new_five_hundred(
    world: WorldStore,
    seed: str = "adelaide-card-night",
    players: Sequence[str] = ("operator", "Alpha", "Beta", "Gamma"),
    human_players: Sequence[str] = (),
) -> WorldObject:
    state = _new_state(clean_seed(seed, "adelaide-card-night"), players, human_players)
    return world.create_object(
        "five_hundred_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_five_hundred_game"},
    )


def _all_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    cards = list(state["kitty"]) + list(state["discard_pile"])
    cards.extend(play["card"] for play in state["current_trick"])
    for trick in state["completed_tricks"]:
        cards.extend(play["card"] for play in trick["plays"])
    for player in state["players"]:
        cards.extend(state["hands"][player])
    return cards


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != FIVE_HUNDRED_SCHEMA or state.get("game_kind") != FIVE_HUNDRED_KIND:
        raise ValueError("unsupported 500 game state schema")
    if state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("500 claim boundary is invalid")
    players = state.get("players")
    controllers = state.get("controllers")
    if not isinstance(players, list) or not isinstance(controllers, dict):
        raise ValueError("500 roster is malformed")
    human_players = [player for player in players if controllers.get(player) == "human"]
    _, expected_controllers = player_roster(
        players, human_players=human_players, minimum=4, maximum=4
    )
    if controllers != expected_controllers:
        raise ValueError("500 controllers must mark at least one human and all other seats as AI")
    if state.get("teams") != _teams(players):
        raise ValueError("500 teams must use opposite seats")
    hands = state.get("hands")
    if not isinstance(hands, dict) or set(hands) != set(players):
        raise ValueError("500 hands must match the roster")
    cards = _all_cards(state)
    if len(cards) != 43 or len({card.get("card_id") for card in cards}) != 43:
        raise ValueError("500 state must conserve all 43 unique cards")
    expected_cards = {(card["card_id"], card["suit"], card["rank"]) for card in _deck()}
    observed_cards = {(card.get("card_id"), card.get("suit"), card.get("rank")) for card in cards}
    if observed_cards != expected_cards:
        raise ValueError("500 card records do not match the canonical deck")
    if state.get("phase") not in {"bidding", "discard", "play", "complete"}:
        raise ValueError("invalid 500 phase")
    current = exact_int(state.get("current_player_index"), "500 current_player_index", minimum=0)
    dealer = exact_int(state.get("dealer_index"), "500 dealer_index", minimum=0)
    if current >= 4 or dealer >= 4:
        raise ValueError("500 seat index is outside the roster")
    for team in ("team_0", "team_1"):
        exact_int(state.get("scores", {}).get(team), "500 score")
        exact_int(state.get("tricks_won", {}).get(team), "500 trick count", minimum=0)
    if len(state.get("current_trick", [])) > 3:
        raise ValueError("500 current trick cannot contain four retained plays")
    completed = state.get("completed_tricks")
    if (
        not isinstance(completed, list)
        or len(completed) > 10
        or any(
            not isinstance(trick, dict)
            or len(trick.get("plays", [])) != 4
            or trick.get("winner") not in players
            for trick in completed
        )
    ):
        raise ValueError("500 completed trick ledger is malformed")
    if sum(state["tricks_won"].values()) != len(completed):
        raise ValueError("500 trick totals must match the completed trick ledger")
    highest = state.get("highest_bid")
    if highest is not None:
        highest_contract = highest.get("contract") if isinstance(highest, dict) else None
        if (
            not isinstance(highest, dict)
            or highest.get("player_id") not in players
            or not isinstance(highest_contract, dict)
            or highest_contract != _contract(highest_contract.get("token", ""))
        ):
            raise ValueError("500 highest bid is malformed")
    contract = state.get("contract")
    if contract is not None and (
        not isinstance(contract, dict) or contract != _contract(contract.get("token", ""))
    ):
        raise ValueError("500 contract is malformed")
    declarer = state.get("declarer")
    if state["phase"] == "bidding":
        if contract is not None or declarer is not None or len(state["kitty"]) != 3:
            raise ValueError("500 bidding phase cannot retain a contract or opened kitty")
        if any(len(hands[player]) != 10 for player in players) or state["discard_pile"]:
            raise ValueError("500 bidding phase requires four ten-card hands and a three-card kitty")
    elif state["phase"] == "discard":
        if contract is None or declarer not in players or len(state["kitty"]) != 0:
            raise ValueError("500 discard phase requires a declarer with the kitty")
        if len(hands[declarer]) != 13 or any(
            len(hands[player]) != 10 for player in players if player != declarer
        ):
            raise ValueError("500 declarer must hold thirteen cards before discarding")
    elif state["phase"] in {"play", "complete"}:
        if contract is None or declarer not in players or len(state["kitty"]) != 0:
            raise ValueError("500 play requires a valid contract and declarer")
        if len(state["discard_pile"]) != 3:
            raise ValueError("500 play requires the declarer's three-card discard")
    winner_team = state.get("winner_team")
    if (state["phase"] == "complete") != (winner_team is not None):
        raise ValueError("500 complete phase and winner_team must agree")
    if winner_team is not None and winner_team not in {"team_0", "team_1"}:
        raise ValueError("500 winner_team is invalid")
    if state.get("content") != _board_content(state):
        raise ValueError("500 content view does not match authoritative state")


def inspect_five_hundred(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "five_hundred_game_state":
        raise ValueError("object is not a 500 game state")
    _validate_state(obj.payload)
    return obj


def _advance_bidder(state: dict[str, Any]) -> None:
    state["current_player_index"] = (state["current_player_index"] + 1) % 4


def _begin_contract(state: dict[str, Any]) -> None:
    highest = state["highest_bid"]
    state["contract"] = deepcopy(highest["contract"])
    state["declarer"] = highest["player_id"]
    state["hands"][state["declarer"]].extend(state["kitty"])
    state["kitty"] = []
    state["phase"] = "discard"
    state["current_player_index"] = state["players"].index(state["declarer"])
    append_event(
        state,
        "contract",
        f"{state['declarer']} wins the auction at {state['contract']['token']} and takes the kitty.",
        player_id=state["declarer"],
    )


def _redeal_after_all_pass(state: dict[str, Any]) -> None:
    state["dealer_index"] = (state["dealer_index"] + 1) % 4
    state["hand_number"] += 1
    _deal(state)
    append_event(state, "redeal", "All four players pass; the next deterministic hand is dealt.")


def _same_color(left: str, right: str) -> bool:
    return {left, right} <= {"hearts", "diamonds"} or {left, right} <= {"spades", "clubs"}


def _effective_suit(card: dict[str, Any], trump: str | None) -> str:
    if card["rank"] == "JOKER":
        return trump or "joker"
    if trump is not None and card["rank"] == "J" and (
        card["suit"] == trump or _same_color(str(card["suit"]), trump)
    ):
        return trump
    return str(card["suit"])


def _card_power(card: dict[str, Any], trump: str | None, lead_suit: str) -> tuple[int, int]:
    effective = _effective_suit(card, trump)
    if card["rank"] == "JOKER":
        return (3, 100)
    if trump is not None and effective == trump:
        if card["rank"] == "J" and card["suit"] == trump:
            return (2, 99)
        if card["rank"] == "J" and card["suit"] != trump:
            return (2, 98)
        return (2, RANK_POWER[str(card["rank"])])
    if effective == lead_suit:
        return (1, RANK_POWER[str(card["rank"])])
    return (0, RANK_POWER.get(str(card["rank"]), 0))


def _finish_hand(state: dict[str, Any]) -> None:
    contract = state["contract"]
    bidder_team = _team_for(state, state["declarer"])
    defender_team = "team_1" if bidder_team == "team_0" else "team_0"
    made = state["tricks_won"][bidder_team] >= contract["tricks"]
    state["scores"][bidder_team] += contract["points"] if made else -contract["points"]
    state["scores"][defender_team] += state["tricks_won"][defender_team] * 10
    append_event(
        state,
        "hand_score",
        f"{bidder_team} {'makes' if made else 'fails'} {contract['token']}; scores are "
        f"{state['scores']['team_0']} to {state['scores']['team_1']}.",
    )
    candidates = [
        team
        for team in ("team_0", "team_1")
        if state["scores"][team] >= 500 or state["scores"]["team_1" if team == "team_0" else "team_0"] <= -500
    ]
    if candidates:
        candidates.sort(key=lambda team: (-state["scores"][team], team))
        state["winner_team"] = candidates[0]
        state["phase"] = "complete"
        append_event(state, "win", f"{state['winner_team']} wins NEXUS 500.")
        return
    state["dealer_index"] = (state["dealer_index"] + 1) % 4
    state["hand_number"] += 1
    _deal(state)
    append_event(state, "new_hand", f"Hand {state['hand_number']} is dealt.")


def _persist(world: WorldStore, previous_ref: str, state: dict[str, Any], transition: dict[str, Any]) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "five_hundred_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "five_hundred_transition"},
    )


def apply_action(
    world: WorldStore,
    game_ref: str,
    player_id: str,
    action: str,
    args: Sequence[str] = (),
) -> WorldObject:
    current = inspect_five_hundred(world, game_ref)
    state = deepcopy(current.payload)
    require_player(state, player_id)
    if state["phase"] == "complete":
        raise ValueError("500 game is complete")
    if player_id != _current_player(state):
        raise ValueError("it is not that player's 500 turn")
    action = action.strip().lower() if isinstance(action, str) else ""
    args = require_args(args, maximum=3)
    state["transition_count"] += 1

    if state["phase"] == "bidding":
        if action == "bid" and len(args) == 1:
            contract = _contract(args[0])
            if state["highest_bid"] and contract["rank"] <= state["highest_bid"]["contract"]["rank"]:
                raise ValueError("500 bid must outrank the current contract")
            state["highest_bid"] = {"player_id": player_id, "contract": contract}
            state["passes"] = 0
            state["bid_history"].append({"player_id": player_id, "bid": contract["token"]})
            append_event(state, "bid", f"{player_id} bids {contract['token']}.", player_id=player_id)
            _advance_bidder(state)
        elif action == "pass" and not args:
            state["bid_history"].append({"player_id": player_id, "bid": "PASS"})
            state["passes"] += 1
            append_event(state, "pass", f"{player_id} passes.", player_id=player_id)
            if state["highest_bid"] is None and state["passes"] == 4:
                _redeal_after_all_pass(state)
            elif state["highest_bid"] is not None and state["passes"] == 3:
                _begin_contract(state)
            else:
                _advance_bidder(state)
        else:
            raise ValueError("500 bidding accepts bid <contract> or pass")
    elif state["phase"] == "discard":
        if action != "discard" or len(args) != 3 or len(set(args)) != 3:
            raise ValueError("500 declarer must discard three distinct card ids")
        hand = state["hands"][player_id]
        selected = []
        for card_id in args:
            card = next((item for item in hand if item["card_id"] == card_id), None)
            if card is None:
                raise ValueError("discarded 500 card is not in the declarer's hand")
            selected.append(card)
        for card in selected:
            hand.remove(card)
        state["discard_pile"] = selected
        state["phase"] = "play"
        state["current_player_index"] = state["players"].index(player_id)
        append_event(state, "discard", f"{player_id} discards three cards and leads.", player_id=player_id)
    elif state["phase"] == "play":
        if action != "play" or len(args) != 1:
            raise ValueError("500 play phase requires play <card_id>")
        hand = state["hands"][player_id]
        card = next((item for item in hand if item["card_id"] == args[0]), None)
        if card is None:
            raise ValueError("500 card is not in the player's hand")
        trump = state["contract"]["trump"]
        if state["current_trick"]:
            lead_suit = _effective_suit(state["current_trick"][0]["card"], trump)
            if _effective_suit(card, trump) != lead_suit and any(
                _effective_suit(item, trump) == lead_suit for item in hand
            ):
                raise ValueError("500 player must follow effective suit")
        hand.remove(card)
        state["current_trick"].append({"player_id": player_id, "card": card})
        append_event(state, "play", f"{player_id} plays {_card_label(card)}.", player_id=player_id, card_id=card["card_id"])
        if len(state["current_trick"]) < 4:
            state["current_player_index"] = (state["current_player_index"] + 1) % 4
        else:
            lead_suit = _effective_suit(state["current_trick"][0]["card"], trump)
            winning_play = max(
                state["current_trick"],
                key=lambda play: _card_power(play["card"], trump, lead_suit),
            )
            winner = winning_play["player_id"]
            state["tricks_won"][_team_for(state, winner)] += 1
            state["completed_tricks"].append(
                {"trick": len(state["completed_tricks"]) + 1, "winner": winner, "plays": state["current_trick"]}
            )
            state["current_trick"] = []
            state["current_player_index"] = state["players"].index(winner)
            append_event(state, "trick", f"{winner} wins the trick.", player_id=winner)
            if len(state["completed_tricks"]) == 10:
                _finish_hand(state)
    else:
        raise ValueError("invalid 500 phase")

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
        "schema": FIVE_HUNDRED_SCHEMA,
        "title": FIVE_HUNDRED_TITLE,
        "player_id": player_id,
        "controller": state["controllers"][player_id],
        "team": _team_for(state, player_id),
        "phase": state["phase"],
        "current_player": None if state["phase"] == "complete" else _current_player(state),
        "hand": deepcopy(state["hands"][player_id]),
        "hand_counts": {player: len(state["hands"][player]) for player in state["players"]},
        "scores": deepcopy(state["scores"]),
        "highest_bid": deepcopy(state["highest_bid"]),
        "contract": deepcopy(state["contract"]),
        "declarer": state["declarer"],
        "current_trick": deepcopy(state["current_trick"]),
        "tricks_won": deepcopy(state["tricks_won"]),
        "winner_team": state["winner_team"],
        "legal_actions": [item["action"] for item in FIVE_HUNDRED_ACTIONS],
        "last_event": deepcopy(state["event_log"][-1]),
    }
