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


BLACKJACK_SCHEMA = "nexus-blackjack/1"
BLACKJACK_KIND = "deterministic_dealer_human_ai_blackjack"
BLACKJACK_TITLE = "NEXUS BLACKJACK"
SUITS = ("spades", "clubs", "diamonds", "hearts")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
STARTING_BANKROLL = 200
MIN_BET = 2
MAX_ROUNDS = 250
_CLAIM_BOUNDARY = {
    "fictional_game": True,
    "human_and_ai_players": True,
    "deterministic_dealer": True,
    "real_money_or_gambling": False,
    "model_narration_mutates_state": False,
    "dealer_hole_card_is_public_evidence": False,
}

BLACKJACK_ACTIONS = (
    {"action": "bet", "args": ["even_chip_amount"], "description": "Place an even whole-chip bet during the betting round."},
    {"action": "hit", "args": [], "description": "Take one card."},
    {"action": "stand", "args": [], "description": "End the player's hand."},
    {"action": "double", "args": [], "description": "Double the initial bet, take exactly one card, then stand."},
    {"action": "new_round", "args": [], "description": "Start the next round after settlement."},
)


def action_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(BLACKJACK_ACTIONS))


def _shoe() -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for deck_index in range(1, 7):
        for suit in SUITS:
            for rank in RANKS:
                cards.append(
                    {
                        "card_id": f"d{deck_index}-{suit}-{rank}",
                        "suit": suit,
                        "rank": rank,
                    }
                )
    return cards


def hand_value(hand: Sequence[dict[str, Any]]) -> tuple[int, bool]:
    total = 0
    aces = 0
    for card in hand:
        rank = card["rank"]
        if rank == "A":
            total += 11
            aces += 1
        elif rank in {"J", "Q", "K"}:
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def _current_player(state: dict[str, Any]) -> str | None:
    if state["phase"] not in {"betting", "player_turns"}:
        return None
    return state["players"][state["current_player_index"]]


def _dealer_public(state: dict[str, Any]) -> list[dict[str, Any] | dict[str, bool]]:
    hand = state["dealer"]["hand"]
    if state["dealer"]["revealed"] or len(hand) <= 1:
        return deepcopy(hand)
    return [deepcopy(hand[0]), {"hidden": True}]


def _board_content(state: dict[str, Any]) -> str:
    current = _current_player(state) or "-"
    dealer_cards = _dealer_public(state)
    dealer_text = ",".join(
        "HIDDEN" if card.get("hidden") else str(card.get("card_id")) for card in dealer_cards
    )
    lines = [
        "NEXUS BLACKJACK — AUTHORITATIVE PUBLIC TABLE",
        f"round={state['round_number']} phase={state['phase']} current_player={current}",
        f"dealer_rule=stand_on_soft_17 dealer_cards={dealer_text or 'none'} shoe={len(state['shoe'])}",
        "players:",
    ]
    for player in state["players"]:
        seat = state["seats"][player]
        total, _ = hand_value(seat["hand"])
        lines.append(
            f"- {player} controller={state['controllers'][player]} bankroll={seat['bankroll']} "
            f"bet={seat['bet']} status={seat['status']} cards={len(seat['hand'])} total={total if seat['hand'] else 0}"
        )
    if state["winner"]:
        lines.append(f"table_winner={state['winner']}")
    if state["event_log"]:
        lines.append(f"latest_event={state['event_log'][-1]['text']}")
    lines.append("dealer_is_deterministic=true; splits_not_in_profile=true; real_money_or_gambling=false")
    return "\n".join(lines)


def _new_state(seed: str, players: Sequence[str], human_players: Sequence[str]) -> dict[str, Any]:
    roster, controllers = player_roster(
        players, human_players=human_players, minimum=1, maximum=7
    )
    state: dict[str, Any] = {
        "schema": BLACKJACK_SCHEMA,
        "game_kind": BLACKJACK_KIND,
        "title": BLACKJACK_TITLE,
        "rules_profile": "six-deck-stand-soft-17-no-splits-v1",
        "seed": seed,
        "players": roster,
        "controllers": controllers,
        "seats": {
            player: {
                "bankroll": STARTING_BANKROLL,
                "bet": 0,
                "hand": [],
                "status": "awaiting_bet",
                "result": None,
            }
            for player in roster
        },
        "dealer": {"hand": [], "revealed": False},
        "shoe": deterministic_shuffle(_shoe(), seed, "blackjack-shoe-1"),
        "discard_pile": [],
        "round_number": 1,
        "phase": "betting",
        "current_player_index": 0,
        "winner": None,
        "transition_count": 0,
        "event_log": [{"sequence": 0, "kind": "new_table", "text": f"{roster[0]} opens the betting round."}],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "claim_boundary": deepcopy(_CLAIM_BOUNDARY),
    }
    state["content"] = _board_content(state)
    return state


def new_blackjack(
    world: WorldStore,
    seed: str = "canonical-shoe-night",
    players: Sequence[str] = ("operator", "Alpha", "Beta", "Gamma"),
    human_players: Sequence[str] = (),
) -> WorldObject:
    state = _new_state(clean_seed(seed, "canonical-shoe-night"), players, human_players)
    return world.create_object(
        "blackjack_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_blackjack_game"},
    )


def _all_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    cards = list(state["shoe"]) + list(state["discard_pile"]) + list(state["dealer"]["hand"])
    for player in state["players"]:
        cards.extend(state["seats"][player]["hand"])
    return cards


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != BLACKJACK_SCHEMA or state.get("game_kind") != BLACKJACK_KIND:
        raise ValueError("unsupported Blackjack game state schema")
    if state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("Blackjack claim boundary is invalid")
    players = state.get("players")
    controllers = state.get("controllers")
    if not isinstance(players, list) or not isinstance(controllers, dict):
        raise ValueError("Blackjack roster is malformed")
    humans = [player for player in players if controllers.get(player) == "human"]
    _, expected_controllers = player_roster(
        players, human_players=humans, minimum=1, maximum=7
    )
    if controllers != expected_controllers:
        raise ValueError("Blackjack controllers must mark at least one human and all other seats as AI")
    seats = state.get("seats")
    if not isinstance(seats, dict) or set(seats) != set(players):
        raise ValueError("Blackjack seats must match the roster")
    for player in players:
        seat = seats[player]
        exact_int(seat.get("bankroll"), "Blackjack bankroll", minimum=0)
        bet = exact_int(seat.get("bet"), "Blackjack bet", minimum=0)
        if bet % 2:
            raise ValueError("Blackjack bets must be even whole-chip amounts")
        if not isinstance(seat.get("hand"), list) or seat.get("status") not in {
            "awaiting_bet", "active", "stand", "bust", "blackjack", "settled", "broke"
        }:
            raise ValueError("Blackjack seat is malformed")
    cards = _all_cards(state)
    if len(cards) != 312 or len({card.get("card_id") for card in cards}) != 312:
        raise ValueError("Blackjack state must conserve all 312 unique cards")
    expected_cards = {(card["card_id"], card["suit"], card["rank"]) for card in _shoe()}
    observed_cards = {(card.get("card_id"), card.get("suit"), card.get("rank")) for card in cards}
    if observed_cards != expected_cards:
        raise ValueError("Blackjack card records do not match the canonical shoe")
    if state.get("phase") not in {"betting", "player_turns", "round_complete", "complete"}:
        raise ValueError("invalid Blackjack phase")
    round_number = exact_int(state.get("round_number"), "Blackjack round_number", minimum=1)
    if round_number > MAX_ROUNDS:
        raise ValueError("Blackjack round_number exceeds the bounded table")
    exact_int(state.get("transition_count"), "Blackjack transition_count", minimum=0)
    index = exact_int(state.get("current_player_index"), "Blackjack current_player_index", minimum=0)
    if index >= len(players):
        raise ValueError("Blackjack current_player_index is outside the roster")
    if type(state.get("dealer", {}).get("revealed")) is not bool:
        raise ValueError("Blackjack dealer reveal flag must be boolean")
    winner = state.get("winner")
    if (state["phase"] == "complete") != (winner is not None):
        raise ValueError("Blackjack complete phase and winner must agree")
    if winner is not None and winner not in [*players, "dealer"]:
        raise ValueError("Blackjack winner must be a registered player or the dealer")
    if state["phase"] in {"betting", "player_turns"} and state["dealer"]["revealed"]:
        raise ValueError("Blackjack dealer hole card cannot be revealed before dealer resolution")
    if state["phase"] in {"round_complete", "complete"} and not state["dealer"]["revealed"]:
        raise ValueError("Blackjack dealer must be revealed during and after resolution")
    if state["phase"] == "betting":
        if state["dealer"]["hand"]:
            raise ValueError("Blackjack betting phase cannot retain a dealer hand")
        current_player = players[index]
        if seats[current_player]["status"] != "awaiting_bet":
            raise ValueError("Blackjack betting cursor must identify an awaiting player")
        for seat in seats.values():
            if seat["hand"] or seat["result"] is not None:
                raise ValueError("Blackjack betting seats cannot retain cards or results")
            if seat["status"] == "active" and seat["bet"] >= MIN_BET:
                continue
            if seat["status"] == "awaiting_bet" and seat["bet"] == 0 and seat["bankroll"] >= MIN_BET:
                continue
            if seat["status"] == "broke" and seat["bet"] == 0 and seat["bankroll"] < MIN_BET:
                continue
            raise ValueError("Blackjack betting seat state is inconsistent")
    if state["phase"] == "player_turns":
        current_player = players[index]
        if seats[current_player]["status"] != "active" or len(state["dealer"]["hand"]) != 2:
            raise ValueError("Blackjack player-turn cursor or dealer hand is invalid")
    if state["phase"] in {"round_complete", "complete"} and any(
        seat["status"] not in {"settled", "broke"} for seat in seats.values()
    ):
        raise ValueError("Blackjack settled phases cannot retain an active seat")
    if state.get("content") != _board_content(state):
        raise ValueError("Blackjack content view does not match authoritative state")


def inspect_blackjack(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "blackjack_game_state":
        raise ValueError("object is not a Blackjack game state")
    _validate_state(obj.payload)
    return obj


def _draw(state: dict[str, Any]) -> dict[str, Any]:
    if not state["shoe"]:
        raise ValueError("Blackjack shoe is exhausted")
    return state["shoe"].pop()


def _next_with_status(state: dict[str, Any], status: str, start: int) -> int | None:
    for offset in range(1, len(state["players"]) + 1):
        index = (start + offset) % len(state["players"])
        if state["seats"][state["players"][index]]["status"] == status:
            return index
    return None


def _deal_initial(state: dict[str, Any]) -> None:
    active = [player for player in state["players"] if state["seats"][player]["bet"] > 0]
    for _ in range(2):
        for player in active:
            state["seats"][player]["hand"].append(_draw(state))
        state["dealer"]["hand"].append(_draw(state))
    for player in active:
        total, _ = hand_value(state["seats"][player]["hand"])
        state["seats"][player]["status"] = "blackjack" if total == 21 else "active"
    state["phase"] = "player_turns"
    state["dealer"]["revealed"] = False
    first = next((index for index, player in enumerate(state["players"]) if state["seats"][player]["status"] == "active"), None)
    dealer_total, _ = hand_value(state["dealer"]["hand"])
    append_event(state, "deal", "The deterministic dealer completes the initial deal.")
    if dealer_total == 21 or first is None:
        _play_dealer(state)
    else:
        state["current_player_index"] = first


def _advance_player(state: dict[str, Any]) -> None:
    next_index = _next_with_status(state, "active", state["current_player_index"])
    if next_index is None:
        _play_dealer(state)
    else:
        state["current_player_index"] = next_index


def _settle(state: dict[str, Any]) -> None:
    dealer_total, _ = hand_value(state["dealer"]["hand"])
    dealer_blackjack = dealer_total == 21 and len(state["dealer"]["hand"]) == 2
    dealer_bust = dealer_total > 21
    for player in state["players"]:
        seat = state["seats"][player]
        if seat["bet"] == 0:
            continue
        total, _ = hand_value(seat["hand"])
        player_blackjack = total == 21 and len(seat["hand"]) == 2
        if total > 21:
            result, payout = "loss_bust", 0
        elif player_blackjack and not dealer_blackjack:
            result, payout = "blackjack", seat["bet"] * 5 // 2
        elif dealer_blackjack and player_blackjack:
            result, payout = "push", seat["bet"]
        elif dealer_blackjack:
            result, payout = "loss_dealer_blackjack", 0
        elif dealer_bust or total > dealer_total:
            result, payout = "win", seat["bet"] * 2
        elif total == dealer_total:
            result, payout = "push", seat["bet"]
        else:
            result, payout = "loss", 0
        seat["bankroll"] += payout
        seat["result"] = result
        seat["status"] = "settled"
        append_event(state, "settlement", f"{player}: {result}, payout {payout}.", player_id=player, payout=payout)

    solvent = [player for player in state["players"] if state["seats"][player]["bankroll"] >= MIN_BET]
    last_competitor = len(state["players"]) > 1 and len(solvent) == 1
    if not solvent or last_competitor or state["round_number"] >= MAX_ROUNDS:
        state["winner"] = (
            max(
                solvent,
                key=lambda player: (
                    state["seats"][player]["bankroll"],
                    -state["players"].index(player),
                ),
            )
            if solvent
            else "dealer"
        )
        state["phase"] = "complete"
        append_event(state, "table_win", f"{state['winner']} wins the Blackjack table.")
    else:
        state["phase"] = "round_complete"


def _play_dealer(state: dict[str, Any]) -> None:
    state["phase"] = "dealer"
    state["dealer"]["revealed"] = True
    while True:
        total, _soft = hand_value(state["dealer"]["hand"])
        if total >= 17:
            break
        state["dealer"]["hand"].append(_draw(state))
    total, soft = hand_value(state["dealer"]["hand"])
    append_event(
        state,
        "dealer",
        f"Dealer resolves to {total}{' soft' if soft else ''} under stand-on-soft-17.",
        total=total,
    )
    _settle(state)


def _start_next_round(state: dict[str, Any]) -> None:
    for player in state["players"]:
        state["discard_pile"].extend(state["seats"][player]["hand"])
    state["discard_pile"].extend(state["dealer"]["hand"])
    state["round_number"] += 1
    if len(state["shoe"]) < 60:
        state["shoe"] = deterministic_shuffle(
            state["shoe"] + state["discard_pile"],
            state["seed"],
            f"blackjack-shoe-{state['round_number']}",
        )
        state["discard_pile"] = []
    for player in state["players"]:
        seat = state["seats"][player]
        seat.update(
            {
                "bet": 0,
                "hand": [],
                "status": "awaiting_bet" if seat["bankroll"] >= MIN_BET else "broke",
                "result": None,
            }
        )
    state["dealer"] = {"hand": [], "revealed": False}
    state["phase"] = "betting"
    first = next(index for index, player in enumerate(state["players"]) if state["seats"][player]["status"] == "awaiting_bet")
    state["current_player_index"] = first
    append_event(state, "new_round", f"Blackjack round {state['round_number']} opens for bets.")


def _persist(world: WorldStore, previous_ref: str, state: dict[str, Any], transition: dict[str, Any]) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "blackjack_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "blackjack_transition"},
    )


def apply_action(
    world: WorldStore,
    game_ref: str,
    player_id: str,
    action: str,
    args: Sequence[str] = (),
) -> WorldObject:
    current = inspect_blackjack(world, game_ref)
    state = deepcopy(current.payload)
    require_player(state, player_id)
    action = action.strip().lower() if isinstance(action, str) else ""
    args = require_args(args, maximum=1)
    state["transition_count"] += 1

    if action == "new_round":
        if args or state["phase"] != "round_complete":
            raise ValueError("new_round is only available after Blackjack settlement")
        _start_next_round(state)
    elif state["phase"] == "betting":
        if player_id != _current_player(state):
            raise ValueError("it is not that player's Blackjack betting turn")
        if action != "bet" or len(args) != 1:
            raise ValueError("Blackjack betting phase requires bet <even_chip_amount>")
        try:
            amount = int(args[0], 10)
        except ValueError as exc:
            raise ValueError("Blackjack bet must be a whole-chip integer") from exc
        seat = state["seats"][player_id]
        if amount < MIN_BET or amount % 2 or amount > seat["bankroll"]:
            raise ValueError("Blackjack bet must be even, at least 2, and no more than the bankroll")
        seat["bankroll"] -= amount
        seat["bet"] = amount
        seat["status"] = "active"
        append_event(state, "bet", f"{player_id} bets {amount} fictional chips.", player_id=player_id, amount=amount)
        next_index = _next_with_status(state, "awaiting_bet", state["current_player_index"])
        if next_index is None:
            _deal_initial(state)
        else:
            state["current_player_index"] = next_index
    elif state["phase"] == "player_turns":
        if player_id != _current_player(state) or state["seats"][player_id]["status"] != "active":
            raise ValueError("it is not that player's active Blackjack turn")
        seat = state["seats"][player_id]
        if action == "hit" and not args:
            seat["hand"].append(_draw(state))
            total, _ = hand_value(seat["hand"])
            append_event(state, "hit", f"{player_id} hits to {total}.", player_id=player_id, total=total)
            if total >= 21:
                seat["status"] = "bust" if total > 21 else "stand"
                _advance_player(state)
        elif action == "stand" and not args:
            seat["status"] = "stand"
            append_event(state, "stand", f"{player_id} stands on {hand_value(seat['hand'])[0]}.", player_id=player_id)
            _advance_player(state)
        elif action == "double" and not args:
            if len(seat["hand"]) != 2 or seat["bankroll"] < seat["bet"]:
                raise ValueError("double requires an initial two-card hand and enough bankroll")
            seat["bankroll"] -= seat["bet"]
            seat["bet"] *= 2
            seat["hand"].append(_draw(state))
            total, _ = hand_value(seat["hand"])
            seat["status"] = "bust" if total > 21 else "stand"
            append_event(state, "double", f"{player_id} doubles and finishes on {total}.", player_id=player_id, total=total)
            _advance_player(state)
        else:
            raise ValueError("Blackjack player turn accepts hit, stand or double")
    else:
        raise ValueError("action is not available in the current Blackjack phase")

    return _persist(
        world,
        current.object_id,
        state,
        {"kind": "action", "player_id": player_id, "action": action, "args": args},
    )


def player_view(state: dict[str, Any], player_id: str) -> dict[str, Any]:
    require_player(state, player_id)
    _validate_state(state)
    seat = state["seats"][player_id]
    total, soft = hand_value(seat["hand"])
    return {
        "schema": BLACKJACK_SCHEMA,
        "title": BLACKJACK_TITLE,
        "player_id": player_id,
        "controller": state["controllers"][player_id],
        "phase": state["phase"],
        "current_player": _current_player(state),
        "bankroll": seat["bankroll"],
        "bet": seat["bet"],
        "hand": deepcopy(seat["hand"]),
        "hand_total": total,
        "soft": soft,
        "status": seat["status"],
        "result": seat["result"],
        "dealer_hand": _dealer_public(state),
        "dealer_revealed": state["dealer"]["revealed"],
        "table": {
            player: {
                "bankroll": state["seats"][player]["bankroll"],
                "bet": state["seats"][player]["bet"],
                "status": state["seats"][player]["status"],
                "cards": len(state["seats"][player]["hand"]),
            }
            for player in state["players"]
        },
        "winner": state["winner"],
        "legal_actions": [item["action"] for item in BLACKJACK_ACTIONS],
        "last_event": deepcopy(state["event_log"][-1]),
    }
