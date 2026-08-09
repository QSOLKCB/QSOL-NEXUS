from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from .game_cards import (
    append_event,
    clean_seed,
    deterministic_shuffle,
    digest_int,
    exact_int,
    next_live_player,
    player_roster,
    require_args,
    require_player,
)
from .world import WorldObject, WorldStore


MONOPOLY_SCHEMA = "nexus-monopoly/1"
MONOPOLY_KIND = "deterministic_human_ai_property_game"
MONOPOLY_TITLE = "NEXUS MONOPOLY: Substrate Edition"
STARTING_CASH = 1500
GO_SALARY = 200
MAX_TURNS = 400
_CLAIM_BOUNDARY = {
    "fictional_game": True,
    "human_and_ai_players": True,
    "official_commercial_board_assets": False,
    "model_narration_mutates_state": False,
}


def _property(
    square_id: str,
    name: str,
    group: str,
    cost: int,
    rents: tuple[int, int, int, int, int, int],
    house_cost: int,
) -> dict[str, Any]:
    return {
        "square_id": square_id,
        "name": name,
        "kind": "property",
        "group": group,
        "cost": cost,
        "rents": list(rents),
        "house_cost": house_cost,
    }


BOARD: tuple[dict[str, Any], ...] = (
    {"square_id": "go", "name": "GO / Ship the Small Thing", "kind": "go"},
    _property("cobol_close", "COBOL Close", "brown", 60, (2, 10, 30, 90, 160, 250), 50),
    {"square_id": "community_patch_1", "name": "Community Patch", "kind": "chance"},
    _property("punch_card_parade", "Punch-Card Parade", "brown", 60, (4, 20, 60, 180, 320, 450), 50),
    {"square_id": "dependency_tax", "name": "Dependency Tax", "kind": "tax", "amount": 100},
    {"square_id": "dialup_rail", "name": "Dial-Up Railway", "kind": "railroad", "cost": 200},
    _property("yaml_yard", "YAML Yard", "cyan", 100, (6, 30, 90, 270, 400, 550), 50),
    {"square_id": "chance_1", "name": "Chance", "kind": "chance"},
    _property("microservice_meadows", "Microservice Meadows", "cyan", 100, (6, 30, 90, 270, 400, 550), 50),
    _property("leftpad_lane", "Left-Pad Lane", "cyan", 120, (8, 40, 100, 300, 450, 600), 50),
    {"square_id": "jail", "name": "Jail / Just Visiting", "kind": "jail"},
    _property("nft_nook", "NFT Nook", "magenta", 140, (10, 50, 150, 450, 625, 750), 100),
    {"square_id": "cloud_utility", "name": "Cloud Billing Utility", "kind": "utility", "cost": 150},
    _property("ai_wrapper_way", "AI Wrapper Way", "magenta", 140, (10, 50, 150, 450, 625, 750), 100),
    _property("lockfile_lagoon", "Lockfile Lagoon", "magenta", 160, (12, 60, 180, 500, 700, 900), 100),
    {"square_id": "mainframe_rail", "name": "Mainframe Railway", "kind": "railroad", "cost": 200},
    _property("nixos_cathedral", "NixOS Cathedral", "orange", 180, (14, 70, 200, 550, 750, 950), 100),
    {"square_id": "community_patch_2", "name": "Community Patch", "kind": "chance"},
    _property("dependency_drive", "Dependency Drive", "orange", 180, (14, 70, 200, 550, 750, 950), 100),
    _property("kubernetes_keep", "Kubernetes Keep", "orange", 200, (16, 80, 220, 600, 800, 1000), 100),
    {"square_id": "free_parking", "name": "Free Parking / Offline Mode", "kind": "free"},
    _property("venture_valley", "Venture Valley", "red", 220, (18, 90, 250, 700, 875, 1050), 150),
    {"square_id": "chance_2", "name": "Chance", "kind": "chance"},
    _property("subscription_square", "Subscription Square", "red", 220, (18, 90, 250, 700, 875, 1050), 150),
    _property("terms_tower", "Terms-of-Service Tower", "red", 240, (20, 100, 300, 750, 925, 1100), 150),
    {"square_id": "fiber_rail", "name": "Fibre Railway", "kind": "railroad", "cost": 200},
    _property("gpu_gardens", "GPU Gardens", "yellow", 260, (22, 110, 330, 800, 975, 1150), 150),
    _property("benchmark_boulevard", "Benchmark Boulevard", "yellow", 260, (22, 110, 330, 800, 975, 1150), 150),
    {"square_id": "electric_utility", "name": "Electricity Utility", "kind": "utility", "cost": 150},
    _property("frontier_folly", "Frontier Folly", "yellow", 280, (24, 120, 360, 850, 1025, 1200), 150),
    {"square_id": "go_to_jail", "name": "Go To Jail / Mandatory Rewrite", "kind": "go_to_jail"},
    _property("receipt_row", "Receipt Row", "green", 300, (26, 130, 390, 900, 1100, 1275), 200),
    _property("hash_heights", "Hash Heights", "green", 300, (26, 130, 390, 900, 1100, 1275), 200),
    {"square_id": "community_patch_3", "name": "Community Patch", "kind": "chance"},
    _property("canonical_court", "Canonical Court", "green", 320, (28, 150, 450, 1000, 1200, 1400), 200),
    {"square_id": "archive_rail", "name": "Archive Railway", "kind": "railroad", "cost": 200},
    {"square_id": "chance_3", "name": "Chance", "kind": "chance"},
    _property("zero_dependency_zone", "Zero-Dependency Zone", "blue", 350, (35, 175, 500, 1100, 1300, 1500), 200),
    {"square_id": "platform_tax", "name": "Platform Tax", "kind": "tax", "amount": 200},
    _property("substrate_station", "Substrate Station", "blue", 400, (50, 200, 600, 1400, 1700, 2000), 200),
)

BOARD_BY_ID = {square["square_id"]: square for square in BOARD}
OWNABLE_IDS = tuple(
    square["square_id"] for square in BOARD if square["kind"] in {"property", "railroad", "utility"}
)

CHANCE_CARDS: tuple[dict[str, Any], ...] = (
    {"card_id": "advance_go", "text": "Your tiny static site ships. Advance to GO.", "effect": "advance_go"},
    {"card_id": "bank_dividend", "text": "The COBOL ledger balances. Collect 100.", "effect": "cash", "amount": 100},
    {"card_id": "dependency_audit", "text": "A transitive dependency requests venture funding. Pay 50.", "effect": "cash", "amount": -50},
    {"card_id": "go_to_jail", "text": "A rewrite introduced fourteen regressions. Go to Jail.", "effect": "jail"},
    {"card_id": "move_back_three", "text": "The migration rolls back. Move back three spaces.", "effect": "back", "steps": 3},
    {"card_id": "consulting", "text": "Explain determinism to the table. Collect 20 from every player.", "effect": "each", "amount": 20},
    {"card_id": "saas_renewal", "text": "The free tier discovers billing. Pay every player 20.", "effect": "each", "amount": -20},
    {"card_id": "nearest_rail", "text": "Take the nearest railway. The timetable is canonical.", "effect": "nearest_rail"},
)

MONOPOLY_ACTIONS = (
    {"action": "roll", "args": [], "description": "Roll deterministic dice and resolve the landing."},
    {"action": "buy", "args": [], "description": "Buy the currently offered unowned property."},
    {"action": "pass", "args": [], "description": "Decline the current property offer under NEXUS compact rules."},
    {"action": "build", "args": ["property_id"], "description": "Build evenly on a complete color group."},
    {"action": "sell_house", "args": ["property_id"], "description": "Sell one building back to the bank."},
    {"action": "mortgage", "args": ["property_id"], "description": "Mortgage an undeveloped property."},
    {"action": "unmortgage", "args": ["property_id"], "description": "Redeem a mortgage for 110 percent."},
    {"action": "pay_bail", "args": [], "description": "Pay 50 before rolling to leave Jail."},
    {"action": "bankrupt", "args": [], "description": "Concede while insolvent."},
)


def action_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(MONOPOLY_ACTIONS))


def _current_player(state: dict[str, Any]) -> str:
    return state["players"][state["turn_index"]]


def _square(state: dict[str, Any], player: str) -> dict[str, Any]:
    return BOARD[state["accounts"][player]["position"]]


def _board_content(state: dict[str, Any]) -> str:
    lines = [
        "NEXUS MONOPOLY — AUTHORITATIVE PUBLIC TABLE",
        f"phase={state['phase']} turn={state['turn_number']} current_player="
        f"{_current_player(state) if state['winner'] is None else '-'}",
        "players:",
    ]
    for player in state["players"]:
        account = state["accounts"][player]
        square = BOARD[account["position"]]
        status = " BANKRUPT" if account["bankrupt"] else (" JAILED" if account["in_jail"] else "")
        lines.append(
            f"- {player} controller={state['controllers'][player]} cash={account['cash']} "
            f"position={square['square_id']} properties={len(account['properties'])}{status}"
        )
    if state["pending_property"]:
        lines.append(f"property_offer={state['pending_property']}")
    if state["winner"]:
        lines.append(f"winner={state['winner']}")
    if state["event_log"]:
        lines.append(f"latest_event={state['event_log'][-1]['text']}")
    lines.append("compact_original_board=true; model_narration_mutates_state=false")
    return "\n".join(lines)


def _new_state(seed: str, players: Sequence[str], human_players: Sequence[str]) -> dict[str, Any]:
    roster, controllers = player_roster(
        players, human_players=human_players, minimum=2, maximum=8
    )
    accounts = {
        player: {
            "cash": STARTING_CASH,
            "position": 0,
            "properties": [],
            "in_jail": False,
            "jail_turns": 0,
            "bankrupt": False,
        }
        for player in roster
    }
    assets = {
        property_id: {"owner": None, "buildings": 0, "mortgaged": False}
        for property_id in OWNABLE_IDS
    }
    chance_deck = deterministic_shuffle(CHANCE_CARDS, seed, "monopoly-chance")
    state: dict[str, Any] = {
        "schema": MONOPOLY_SCHEMA,
        "game_kind": MONOPOLY_KIND,
        "title": MONOPOLY_TITLE,
        "rules_profile": "nexus-compact-monopoly-v1",
        "seed": seed,
        "players": roster,
        "controllers": controllers,
        "accounts": accounts,
        "assets": assets,
        "turn_index": 0,
        "turn_number": 1,
        "phase": "await_roll",
        "pending_property": None,
        "debt_creditor": None,
        "extra_roll": False,
        "consecutive_doubles": 0,
        "roll_count": 0,
        "last_roll": None,
        "chance_deck": chance_deck,
        "chance_cursor": 0,
        "winner": None,
        "transition_count": 0,
        "event_log": [{"sequence": 0, "kind": "new_game", "text": f"{roster[0]} takes the first turn."}],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "claim_boundary": deepcopy(_CLAIM_BOUNDARY),
    }
    state["content"] = _board_content(state)
    return state


def new_monopoly(
    world: WorldStore,
    seed: str = "beige-property-night",
    players: Sequence[str] = ("operator", "Alpha"),
    human_players: Sequence[str] = (),
) -> WorldObject:
    state = _new_state(clean_seed(seed, "beige-property-night"), players, human_players)
    return world.create_object(
        "monopoly_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_monopoly_game"},
    )


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != MONOPOLY_SCHEMA or state.get("game_kind") != MONOPOLY_KIND:
        raise ValueError("unsupported Monopoly game state schema")
    if state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("Monopoly claim boundary is invalid")
    players = state.get("players")
    controllers = state.get("controllers")
    if not isinstance(players, list) or not isinstance(controllers, dict):
        raise ValueError("Monopoly roster is malformed")
    human_players = [player for player in players if controllers.get(player) == "human"]
    _, expected_controllers = player_roster(
        players, human_players=human_players, minimum=2, maximum=8
    )
    if controllers != expected_controllers:
        raise ValueError("Monopoly controllers must mark at least one human and all other seats as AI")
    accounts = state.get("accounts")
    if not isinstance(accounts, dict) or set(accounts) != set(players):
        raise ValueError("Monopoly accounts must match the roster")
    assets = state.get("assets")
    if not isinstance(assets, dict) or set(assets) != set(OWNABLE_IDS):
        raise ValueError("Monopoly asset ledger is incomplete")
    seen_owned: set[str] = set()
    for player in players:
        account = accounts[player]
        if not isinstance(account, dict):
            raise ValueError("Monopoly account is malformed")
        exact_int(account.get("cash"), "Monopoly cash")
        position = exact_int(account.get("position"), "Monopoly position", minimum=0)
        if position >= len(BOARD):
            raise ValueError("Monopoly position is outside the board")
        properties = account.get("properties")
        if (
            not isinstance(properties, list)
            or len(properties) != len(set(properties))
            or properties != sorted(properties)
        ):
            raise ValueError("Monopoly property list must be unique")
        for property_id in properties:
            if property_id not in assets or assets[property_id]["owner"] != player:
                raise ValueError("Monopoly ownership ledger mismatch")
            seen_owned.add(property_id)
        if type(account.get("bankrupt")) is not bool or type(account.get("in_jail")) is not bool:
            raise ValueError("Monopoly status flags must be boolean")
        if account["bankrupt"] and (account["cash"] != 0 or properties):
            raise ValueError("bankrupt Monopoly accounts must have zero cash and no properties")
    for property_id, asset in assets.items():
        if asset.get("owner") is not None and asset["owner"] not in players:
            raise ValueError("Monopoly asset owner is unknown")
        if asset.get("owner") is not None and property_id not in seen_owned:
            raise ValueError("Monopoly asset is missing from owner account")
        buildings = exact_int(asset.get("buildings"), "Monopoly buildings", minimum=0)
        if buildings > 5 or (BOARD_BY_ID[property_id]["kind"] != "property" and buildings):
            raise ValueError("Monopoly building ledger is invalid")
        if type(asset.get("mortgaged")) is not bool or (asset["mortgaged"] and buildings):
            raise ValueError("mortgaged Monopoly assets cannot retain buildings")
        if asset.get("owner") is not None and accounts[asset["owner"]]["bankrupt"]:
            raise ValueError("bankrupt Monopoly players cannot own assets")
        if buildings:
            group_ids = _group_ids(property_id)
            if not group_ids or any(assets[item]["owner"] != asset["owner"] for item in group_ids):
                raise ValueError("Monopoly buildings require one owner to hold the complete group")
    turn_index = exact_int(state.get("turn_index"), "Monopoly turn_index", minimum=0)
    if turn_index >= len(players):
        raise ValueError("Monopoly turn_index is outside the roster")
    if state.get("phase") not in {"await_roll", "property_offer", "debt", "complete"}:
        raise ValueError("invalid Monopoly phase")
    pending = state.get("pending_property")
    if pending is not None and (pending not in assets or assets[pending]["owner"] is not None):
        raise ValueError("Monopoly pending property is invalid")
    if (state["phase"] == "property_offer") != (pending is not None):
        raise ValueError("Monopoly property_offer phase and pending property must agree")
    current_cash = accounts[_current_player(state)]["cash"]
    if (state["phase"] == "debt") != (current_cash < 0):
        raise ValueError("Monopoly debt phase must exactly track current-player insolvency")
    if any(
        account["cash"] < 0
        for player, account in accounts.items()
        if player != _current_player(state) and not account["bankrupt"]
    ):
        raise ValueError("only the current Monopoly player may be resolving negative cash")
    winner = state.get("winner")
    if (state["phase"] == "complete") != (winner is not None):
        raise ValueError("Monopoly complete phase and winner must agree")
    if winner is not None and (winner not in players or accounts[winner]["bankrupt"]):
        raise ValueError("Monopoly winner must be an active player")
    if state.get("chance_deck") != deterministic_shuffle(
        CHANCE_CARDS, state.get("seed"), "monopoly-chance"
    ):
        raise ValueError("Monopoly chance deck does not match its deterministic seed")
    exact_int(state.get("chance_cursor"), "Monopoly chance_cursor", minimum=0)
    last_roll = state.get("last_roll")
    if last_roll is not None and (
        not isinstance(last_roll, list)
        or len(last_roll) != 2
        or any(type(die) is not int or not 1 <= die <= 6 for die in last_roll)
    ):
        raise ValueError("Monopoly last_roll must contain two valid dice")
    if state.get("content") != _board_content(state):
        raise ValueError("Monopoly content view does not match authoritative state")


def inspect_monopoly(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "monopoly_game_state":
        raise ValueError("object is not a Monopoly game state")
    _validate_state(obj.payload)
    return obj


def _dice(state: dict[str, Any]) -> tuple[int, int]:
    count = state["roll_count"]
    first = 1 + digest_int(state["seed"], "monopoly-die-a", count) % 6
    second = 1 + digest_int(state["seed"], "monopoly-die-b", count) % 6
    state["roll_count"] += 1
    state["last_roll"] = [first, second]
    return first, second


def _send_to_jail(state: dict[str, Any], player: str, reason: str) -> None:
    account = state["accounts"][player]
    account["position"] = 10
    account["in_jail"] = True
    account["jail_turns"] = 0
    state["extra_roll"] = False
    state["consecutive_doubles"] = 0
    append_event(state, "jail", f"{player} goes to Jail: {reason}", player_id=player)


def _pass_go(state: dict[str, Any], player: str, old: int, new: int) -> None:
    if new < old:
        state["accounts"][player]["cash"] += GO_SALARY
        append_event(state, "pass_go", f"{player} passes GO and collects {GO_SALARY}.", player_id=player)


def _move(state: dict[str, Any], player: str, steps: int) -> None:
    account = state["accounts"][player]
    old = account["position"]
    account["position"] = (old + steps) % len(BOARD)
    if steps > 0:
        _pass_go(state, player, old, account["position"])


def _rent(state: dict[str, Any], property_id: str, dice_total: int) -> int:
    square = BOARD_BY_ID[property_id]
    asset = state["assets"][property_id]
    owner = asset["owner"]
    if owner is None or asset["mortgaged"]:
        return 0
    if square["kind"] == "railroad":
        count = sum(
            1
            for owned in state["accounts"][owner]["properties"]
            if BOARD_BY_ID[owned]["kind"] == "railroad" and not state["assets"][owned]["mortgaged"]
        )
        return 25 * (2 ** max(0, count - 1))
    if square["kind"] == "utility":
        count = sum(
            1
            for owned in state["accounts"][owner]["properties"]
            if BOARD_BY_ID[owned]["kind"] == "utility" and not state["assets"][owned]["mortgaged"]
        )
        return dice_total * (10 if count >= 2 else 4)
    buildings = asset["buildings"]
    rent = square["rents"][buildings]
    group_ids = [item["square_id"] for item in BOARD if item.get("group") == square["group"]]
    if buildings == 0 and all(state["assets"][item]["owner"] == owner for item in group_ids):
        rent *= 2
    return rent


def _draw_chance(state: dict[str, Any], player: str) -> None:
    card = state["chance_deck"][state["chance_cursor"] % len(state["chance_deck"])]
    state["chance_cursor"] += 1
    account = state["accounts"][player]
    effect = card["effect"]
    append_event(state, "chance", f"{player}: {card['text']}", player_id=player, card_id=card["card_id"])
    if effect == "advance_go":
        account["position"] = 0
        account["cash"] += GO_SALARY
    elif effect == "cash":
        account["cash"] += card["amount"]
    elif effect == "jail":
        _send_to_jail(state, player, "Chance card")
    elif effect == "back":
        _move(state, player, -card["steps"])
        _resolve_landing(state, player, allow_chance=False)
    elif effect == "each":
        amount = card["amount"]
        for other in state["players"]:
            if other == player or state["accounts"][other]["bankrupt"]:
                continue
            if amount > 0:
                paid = min(amount, state["accounts"][other]["cash"])
                account["cash"] += paid
                state["accounts"][other]["cash"] -= paid
            else:
                account["cash"] += amount
                state["accounts"][other]["cash"] -= amount
    elif effect == "nearest_rail":
        rails = [5, 15, 25, 35]
        target = next((position for position in rails if position > account["position"]), rails[0])
        old = account["position"]
        account["position"] = target
        _pass_go(state, player, old, target)
        _resolve_landing(state, player, allow_chance=False)


def _resolve_landing(state: dict[str, Any], player: str, *, allow_chance: bool = True) -> None:
    account = state["accounts"][player]
    square = BOARD[account["position"]]
    append_event(state, "land", f"{player} lands on {square['name']}.", player_id=player, square_id=square["square_id"])
    if square["kind"] in {"property", "railroad", "utility"}:
        asset = state["assets"][square["square_id"]]
        if asset["owner"] is None:
            state["phase"] = "property_offer"
            state["pending_property"] = square["square_id"]
            return
        if asset["owner"] != player and not state["accounts"][asset["owner"]]["bankrupt"]:
            amount = _rent(state, square["square_id"], sum(state["last_roll"] or [0, 0]))
            account["cash"] -= amount
            state["accounts"][asset["owner"]]["cash"] += amount
            state["debt_creditor"] = asset["owner"]
            append_event(state, "rent", f"{player} pays {amount} rent to {asset['owner']}.", player_id=player, amount=amount)
    elif square["kind"] == "tax":
        account["cash"] -= square["amount"]
        state["debt_creditor"] = None
        append_event(state, "tax", f"{player} pays {square['amount']} to the bank.", player_id=player, amount=square["amount"])
    elif square["kind"] == "go_to_jail":
        _send_to_jail(state, player, "board instruction")
    elif square["kind"] == "chance" and allow_chance:
        _draw_chance(state, player)


def _active_players(state: dict[str, Any]) -> list[str]:
    return [player for player in state["players"] if not state["accounts"][player]["bankrupt"]]


def _net_worth(state: dict[str, Any], player: str) -> int:
    account = state["accounts"][player]
    total = account["cash"]
    for property_id in account["properties"]:
        square = BOARD_BY_ID[property_id]
        asset = state["assets"][property_id]
        total += square["cost"] // 2 if asset["mortgaged"] else square["cost"]
        if square["kind"] == "property":
            total += asset["buildings"] * square["house_cost"]
    return total


def _end_turn(state: dict[str, Any]) -> None:
    if len(_active_players(state)) == 1:
        state["winner"] = _active_players(state)[0]
        state["phase"] = "complete"
        append_event(state, "win", f"{state['winner']} wins NEXUS MONOPOLY.", player_id=state["winner"])
        return
    if state["turn_number"] >= MAX_TURNS:
        active = _active_players(state)
        state["winner"] = max(
            active,
            key=lambda player: (
                _net_worth(state, player),
                -state["players"].index(player),
            ),
        )
        state["phase"] = "complete"
        append_event(
            state,
            "turn_limit",
            f"The bounded {MAX_TURNS}-turn table closes; {state['winner']} wins on net worth.",
            player_id=state["winner"],
            net_worth=_net_worth(state, state["winner"]),
        )
        return
    if state["extra_roll"] and not state["accounts"][_current_player(state)]["in_jail"]:
        state["phase"] = "await_roll"
        state["pending_property"] = None
        state["debt_creditor"] = None
        append_event(state, "extra_roll", f"{_current_player(state)} rolls again for doubles.")
        return
    inactive = {player for player in state["players"] if state["accounts"][player]["bankrupt"]}
    state["turn_index"] = next_live_player(state["players"], inactive, state["turn_index"])
    state["turn_number"] += 1
    state["phase"] = "await_roll"
    state["pending_property"] = None
    state["debt_creditor"] = None
    state["extra_roll"] = False
    state["consecutive_doubles"] = 0


def _after_resolution(state: dict[str, Any]) -> None:
    player = _current_player(state)
    if state["accounts"][player]["cash"] < 0:
        state["phase"] = "debt"
    elif state["phase"] not in {"property_offer", "complete"}:
        _end_turn(state)


def _group_ids(property_id: str) -> list[str]:
    square = BOARD_BY_ID[property_id]
    return [item["square_id"] for item in BOARD if item.get("group") == square.get("group")]


def _persist(world: WorldStore, previous_ref: str, state: dict[str, Any], transition: dict[str, Any]) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "monopoly_game_state",
        state,
        {"actor": "nexus_game_engine", "reason": "monopoly_transition"},
    )


def apply_action(
    world: WorldStore,
    game_ref: str,
    player_id: str,
    action: str,
    args: Sequence[str] = (),
) -> WorldObject:
    current = inspect_monopoly(world, game_ref)
    state = deepcopy(current.payload)
    require_player(state, player_id)
    if state["winner"] is not None:
        raise ValueError("Monopoly game is complete")
    if player_id != _current_player(state):
        raise ValueError("it is not that player's Monopoly turn")
    if state["accounts"][player_id]["bankrupt"]:
        raise ValueError("bankrupt players cannot act")
    action = action.strip().lower() if isinstance(action, str) else ""
    args = require_args(args, maximum=1)
    state["transition_count"] += 1
    account = state["accounts"][player_id]

    if action == "roll":
        if args or state["phase"] != "await_roll":
            raise ValueError("roll is only available at the start of a Monopoly turn")
        first, second = _dice(state)
        is_double = first == second
        state["extra_roll"] = is_double
        state["consecutive_doubles"] = state["consecutive_doubles"] + 1 if is_double else 0
        append_event(state, "roll", f"{player_id} rolls {first}+{second}.", player_id=player_id, dice=[first, second])
        if state["consecutive_doubles"] >= 3:
            _send_to_jail(state, player_id, "three consecutive doubles")
            _end_turn(state)
        elif account["in_jail"]:
            if is_double:
                account["in_jail"] = False
                account["jail_turns"] = 0
                state["extra_roll"] = False
                _move(state, player_id, first + second)
                _resolve_landing(state, player_id)
                _after_resolution(state)
            else:
                account["jail_turns"] += 1
                if account["jail_turns"] >= 3:
                    account["cash"] -= 50
                    account["in_jail"] = False
                    account["jail_turns"] = 0
                    _move(state, player_id, first + second)
                    _resolve_landing(state, player_id)
                    _after_resolution(state)
                else:
                    state["extra_roll"] = False
                    _end_turn(state)
        else:
            _move(state, player_id, first + second)
            _resolve_landing(state, player_id)
            _after_resolution(state)
    elif action in {"buy", "pass"}:
        if args or state["phase"] != "property_offer" or state["pending_property"] is None:
            raise ValueError(f"{action} requires an active Monopoly property offer")
        property_id = state["pending_property"]
        square = BOARD_BY_ID[property_id]
        if action == "buy":
            if account["cash"] < square["cost"]:
                raise ValueError("player cannot afford the offered Monopoly property")
            account["cash"] -= square["cost"]
            account["properties"].append(property_id)
            account["properties"].sort()
            state["assets"][property_id]["owner"] = player_id
            append_event(state, "buy", f"{player_id} buys {square['name']} for {square['cost']}.", player_id=player_id, property_id=property_id)
        else:
            append_event(state, "pass_property", f"{player_id} leaves {square['name']} unowned under compact house rules.", player_id=player_id, property_id=property_id)
        state["pending_property"] = None
        _end_turn(state)
    elif action == "pay_bail":
        if args or state["phase"] != "await_roll" or not account["in_jail"]:
            raise ValueError("pay_bail is only available before rolling in Jail")
        if account["cash"] < 50:
            raise ValueError("player cannot afford bail")
        account["cash"] -= 50
        account["in_jail"] = False
        account["jail_turns"] = 0
        append_event(state, "bail", f"{player_id} pays 50 bail.", player_id=player_id)
    elif action in {"build", "sell_house", "mortgage", "unmortgage"}:
        if len(args) != 1 or state["phase"] not in {"await_roll", "debt"}:
            raise ValueError(f"{action} requires one property_id before rolling or while resolving debt")
        property_id = args[0]
        if property_id not in account["properties"]:
            raise ValueError("player does not own that Monopoly property")
        square = BOARD_BY_ID[property_id]
        asset = state["assets"][property_id]
        if action == "build":
            if state["phase"] != "await_roll" or square["kind"] != "property" or asset["mortgaged"]:
                raise ValueError("build requires an unmortgaged color property before rolling")
            group_ids = _group_ids(property_id)
            if not group_ids or not all(state["assets"][item]["owner"] == player_id for item in group_ids):
                raise ValueError("build requires ownership of the complete color group")
            if any(state["assets"][item]["mortgaged"] for item in group_ids):
                raise ValueError("cannot build while the color group contains a mortgage")
            minimum_buildings = min(state["assets"][item]["buildings"] for item in group_ids)
            if asset["buildings"] != minimum_buildings or asset["buildings"] >= 5:
                raise ValueError("buildings must be added evenly and cannot exceed a hotel")
            if account["cash"] < square["house_cost"]:
                raise ValueError("player cannot afford that building")
            account["cash"] -= square["house_cost"]
            asset["buildings"] += 1
            append_event(state, "build", f"{player_id} builds on {square['name']}.", player_id=player_id, property_id=property_id)
        elif action == "sell_house":
            if square["kind"] != "property" or asset["buildings"] <= 0:
                raise ValueError("property has no building to sell")
            group_ids = _group_ids(property_id)
            maximum_buildings = max(state["assets"][item]["buildings"] for item in group_ids)
            if asset["buildings"] != maximum_buildings:
                raise ValueError("buildings must be sold evenly")
            asset["buildings"] -= 1
            account["cash"] += square["house_cost"] // 2
            append_event(state, "sell_house", f"{player_id} sells a building on {square['name']}.", player_id=player_id, property_id=property_id)
        elif action == "mortgage":
            group_ids = _group_ids(property_id) if square["kind"] == "property" else []
            if asset["mortgaged"] or asset["buildings"] or any(state["assets"][item]["buildings"] for item in group_ids):
                raise ValueError("mortgage requires an undeveloped, unmortgaged asset and color group")
            asset["mortgaged"] = True
            account["cash"] += square["cost"] // 2
            append_event(state, "mortgage", f"{player_id} mortgages {square['name']}.", player_id=player_id, property_id=property_id)
        else:
            redemption = (square["cost"] // 2 * 110 + 99) // 100
            if not asset["mortgaged"] or account["cash"] < redemption:
                raise ValueError("asset is not mortgaged or player cannot afford redemption")
            asset["mortgaged"] = False
            account["cash"] -= redemption
            append_event(state, "unmortgage", f"{player_id} unmortgages {square['name']} for {redemption}.", player_id=player_id, property_id=property_id)
        if state["phase"] == "debt" and account["cash"] >= 0:
            _end_turn(state)
    elif action == "bankrupt":
        if args or state["phase"] != "debt" or account["cash"] >= 0:
            raise ValueError("bankrupt is only available while insolvent")
        creditor = state["debt_creditor"]
        for property_id in list(account["properties"]):
            asset = state["assets"][property_id]
            asset["buildings"] = 0
            asset["mortgaged"] = False
            if creditor is not None and not state["accounts"][creditor]["bankrupt"]:
                asset["owner"] = creditor
                state["accounts"][creditor]["properties"].append(property_id)
                state["accounts"][creditor]["properties"].sort()
            else:
                asset["owner"] = None
        account["properties"] = []
        account["bankrupt"] = True
        account["cash"] = 0
        append_event(state, "bankrupt", f"{player_id} is bankrupt.", player_id=player_id)
        _end_turn(state)
    else:
        raise ValueError("unknown Monopoly action")

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
        "schema": MONOPOLY_SCHEMA,
        "title": MONOPOLY_TITLE,
        "player_id": player_id,
        "controller": state["controllers"][player_id],
        "phase": state["phase"],
        "current_player": None if state["winner"] else _current_player(state),
        "account": deepcopy(state["accounts"][player_id]),
        "square": deepcopy(_square(state, player_id)),
        "players": deepcopy(state["accounts"]),
        "assets": deepcopy(state["assets"]),
        "pending_property": state["pending_property"],
        "last_roll": deepcopy(state["last_roll"]),
        "winner": state["winner"],
        "legal_actions": [item["action"] for item in MONOPOLY_ACTIONS],
        "last_event": deepcopy(state["event_log"][-1]),
    }
