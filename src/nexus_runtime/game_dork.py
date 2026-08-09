from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from .game_cards import PLAYER_ID_RE, append_event, clean_seed, digest_int, exact_int, require_args
from .world import WorldObject, WorldStore


DORK_SCHEMA = "nexus-dork-v2/1"
DORK_KIND = "human_only_dork_text_adventure"
DORK_TITLE = "DORK v2: The Great Under-Moderated NEXUS"
_CLAIM_BOUNDARY = {
    "fictional_game": True,
    "human_only": True,
    "ai_player_seats": False,
    "model_narration_mutates_state": False,
    "zork_story_binary_embedded": False,
    "original_dork_nexus_runtime": True,
}
_FLAG_NAMES = {
    "mailbox_open",
    "window_open",
    "troll_ratioed",
    "troll_muted",
    "wrapper_prompted",
    "server_deployed",
    "subscribed",
}

ROOMS: dict[str, dict[str, Any]] = {
    "west_of_startup": {
        "name": "West of White Startup",
        "description": (
            "You are standing in an open field west of a suspiciously familiar white startup. "
            "The front door has been boarded up by Growth. A small mailbox waits nearby with the confidence of prior art."
        ),
        "exits": {"north": "north_of_startup", "west": "forest_cache"},
    },
    "north_of_startup": {
        "name": "North Side of White Startup",
        "description": "A side window is slightly ajar. The onboarding funnel insists this counts as accessibility.",
        "exits": {"south": "west_of_startup", "in": "landing_page"},
    },
    "forest_cache": {
        "name": "Forest Cache",
        "description": "The trees contain cached copies of websites that were better before the redesign.",
        "exits": {"east": "west_of_startup"},
    },
    "landing_page": {
        "name": "Conversion-Optimized Landing Page",
        "description": "Every surface is a call to action. None of the calls explain what the product does.",
        "exits": {"out": "north_of_startup", "down": "terms_cellar"},
    },
    "terms_cellar": {
        "name": "Terms-of-Service Cellar",
        "description": "An endless legal scroll descends into the floor. The meaningful opt-out was removed in a minor patch.",
        "exits": {"up": "landing_page", "west": "microservice_maze"},
    },
    "microservice_maze": {
        "name": "Microservice Maze",
        "description": "You are in a maze of tiny service boundaries, all architecturally significant and productively identical.",
        "exits": {"east": "terms_cellar", "south": "node_modules_pit", "north": "ai_wrapper_lab", "west": "moderator_bridge"},
    },
    "node_modules_pit": {
        "name": "node_modules Pit",
        "description": "Millions of tiny packages rustle below. Something has depended on left-pad again.",
        "exits": {"north": "microservice_maze"},
    },
    "ai_wrapper_lab": {
        "name": "AI Wrapper Laboratory",
        "description": "A textarea, a POST request and a valuation sit beneath a green dashboard. The prompt cursor blinks expectantly.",
        "exits": {"south": "microservice_maze"},
    },
    "moderator_bridge": {
        "name": "Bridge of the Content Moderator Troll",
        "description": "A moderator troll guards the western bridge with a legacy banhammer and six contradictory policies.",
        "exits": {"east": "microservice_maze", "west": "nixos_cathedral"},
    },
    "nixos_cathedral": {
        "name": "Cathedral of Declarative Purity",
        "description": "A flake.lock rests on the altar. An Arch user has been demoted to the Old Testament.",
        "exits": {"east": "moderator_bridge", "down": "server_closet"},
    },
    "server_closet": {
        "name": "Zero-Dependency Server Closet",
        "description": "One beige computer performs useful work in total silence. There is no cluster to manage and nobody knows what to bill.",
        "exits": {"up": "nixos_cathedral"},
    },
}

ITEMS: dict[str, dict[str, Any]] = {
    "dork_leaflet": {
        "name": "DORK leaflet",
        "description": "WELCOME TO DORK. This looked legally distinct until you opened the mailbox. Now it is terminally online.",
        "initial_location": "mailbox",
        "score": 5,
    },
    "beige_lantern": {
        "name": "beige lantern",
        "description": "Battery powered, dependency free, and not connected to an account.",
        "initial_location": "forest_cache",
        "score": 5,
    },
    "large_trout": {
        "name": "large trout",
        "description": "A traditional instrument of network diplomacy.",
        "initial_location": "terms_cellar",
        "score": 5,
    },
    "tos_scroll": {
        "name": "endless terms-of-service scroll",
        "description": "Clause 14 permits muting trolls when the appeals queue becomes eventually consistent.",
        "initial_location": "terms_cellar",
        "score": 10,
    },
    "nft_rock": {
        "name": "NFT-backed rock",
        "description": "The underlying rock has retained more value and utility than the certificate.",
        "initial_location": "node_modules_pit",
        "score": 10,
    },
    "prompt_token": {
        "name": "prompt token",
        "description": "One whole token of context, locally sourced and insufficient for a wrapper startup.",
        "initial_location": "hidden",
        "score": 10,
    },
    "legacy_banhammer": {
        "name": "legacy banhammer",
        "description": "Older than the policy it enforces and considerably more deterministic.",
        "initial_location": "hidden",
        "score": 10,
    },
    "punch_card": {
        "name": "EBCDIC punch card",
        "description": "A physical capability token. Do not fold, spindle, containerize or put it behind OAuth.",
        "initial_location": "nixos_cathedral",
        "score": 10,
    },
    "zero_dependency_crown": {
        "name": "Zero-Dependency Crown",
        "description": "Forged from the radical proposition that a text adventure may not require Kubernetes.",
        "initial_location": "hidden",
        "score": 15,
    },
}

DORK_ACTIONS = (
    {"action": "look", "args": [], "description": "Describe the current location."},
    {"action": "go", "args": ["direction"], "description": "Move north/south/east/west/up/down/in/out."},
    {"action": "open", "args": ["mailbox_or_window"], "description": "Open a scenery object."},
    {"action": "take", "args": ["item_id"], "description": "Take a visible item."},
    {"action": "drop", "args": ["item_id"], "description": "Drop a carried item."},
    {"action": "read", "args": ["item_id"], "description": "Read or inspect an item."},
    {"action": "inventory", "args": [], "description": "List carried items."},
    {"action": "score", "args": [], "description": "Show the DORK score."},
    {"action": "shitpost", "args": [], "description": "Post deterministically into the void."},
    {"action": "ratio", "args": ["target"], "description": "Attempt a local ratio."},
    {"action": "mute", "args": ["target"], "description": "Apply a rules-backed mute."},
    {"action": "lurk", "args": [], "description": "Observe without producing content."},
    {"action": "prompt", "args": [], "description": "Prompt the wrapper in its laboratory."},
    {"action": "deploy", "args": [], "description": "Deploy the zero-dependency program."},
    {"action": "subscribe", "args": [], "description": "Subscribe to the landing page's free tier."},
    {"action": "grass", "args": [], "description": "Touch grass when the quest permits it."},
)


def action_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(DORK_ACTIONS))


def _visible_items(state: dict[str, Any]) -> list[str]:
    visible = [item_id for item_id, location in state["item_locations"].items() if location == state["room_id"]]
    if state["room_id"] == "west_of_startup" and state["flags"]["mailbox_open"]:
        visible.extend(item_id for item_id, location in state["item_locations"].items() if location == "mailbox")
    return sorted(visible)


def _room_message(state: dict[str, Any]) -> str:
    room = ROOMS[state["room_id"]]
    items = _visible_items(state)
    suffix = ""
    if items:
        suffix = " Visible: " + ", ".join(f"{item_id} ({ITEMS[item_id]['name']})" for item_id in items) + "."
    return f"{room['name']}. {room['description']}{suffix}"


def _board_content(state: dict[str, Any]) -> str:
    room = ROOMS[state["room_id"]]
    lines = [
        "DORK v2 — HUMAN-ONLY AUTHORITATIVE ADVENTURE STATE",
        f"operator={state['human_operator_id']} status={state['status']} moves={state['moves']} score={state['score']}/100",
        f"location={state['room_id']} | {room['name']}",
        f"description={room['description']}",
        "visible_items=" + (", ".join(_visible_items(state)) or "none"),
        "inventory=" + (", ".join(sorted(state["inventory"])) or "empty"),
        f"last_message={state['last_message']}",
    ]
    if state["event_log"]:
        lines.append(f"latest_event={state['event_log'][-1]['text']}")
    lines.append("ai_player_seats=none; models_may_advise_but_cannot_be_adventure_player=true")
    return "\n".join(lines)


def _new_state(seed: str, human_operator_id: str) -> dict[str, Any]:
    if not isinstance(human_operator_id, str) or PLAYER_ID_RE.fullmatch(human_operator_id) is None:
        raise ValueError("DORK human_operator_id must use 1-32 ASCII letters, digits, _, . or -")
    state: dict[str, Any] = {
        "schema": DORK_SCHEMA,
        "game_kind": DORK_KIND,
        "title": DORK_TITLE,
        "seed": seed,
        "human_only": True,
        "human_operator_id": human_operator_id,
        "room_id": "west_of_startup",
        "inventory": [],
        "item_locations": {item_id: item["initial_location"] for item_id, item in ITEMS.items()},
        "flags": {
            "mailbox_open": False,
            "window_open": False,
            "troll_ratioed": False,
            "troll_muted": False,
            "wrapper_prompted": False,
            "server_deployed": False,
            "subscribed": False,
        },
        "discovery_scores": [],
        "score": 0,
        "clout": 0,
        "moves": 0,
        "status": "playing",
        "last_message": (
            "You are standing in an open field west of a suspiciously familiar white startup. "
            "This is probably fine."
        ),
        "transition_count": 0,
        "event_log": [{"sequence": 0, "kind": "new_game", "text": "The human operator enters DORK v2."}],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "claim_boundary": deepcopy(_CLAIM_BOUNDARY),
    }
    state["content"] = _board_content(state)
    return state


def new_dork(
    world: WorldStore,
    seed: str = "mailbox-with-prior-art",
    human_operator_id: str = "operator",
) -> WorldObject:
    state = _new_state(clean_seed(seed, "mailbox-with-prior-art"), human_operator_id)
    return world.create_object(
        "dork_v2_game_state",
        state,
        {"actor": "human_operator", "reason": "new_human_only_dork_v2"},
    )


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != DORK_SCHEMA or state.get("game_kind") != DORK_KIND:
        raise ValueError("unsupported DORK v2 state schema")
    if state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("DORK v2 claim boundary is invalid")
    operator = state.get("human_operator_id")
    if not isinstance(operator, str) or PLAYER_ID_RE.fullmatch(operator) is None or state.get("human_only") is not True:
        raise ValueError("DORK v2 requires one valid human operator")
    if state.get("room_id") not in ROOMS:
        raise ValueError("DORK v2 room is unknown")
    inventory = state.get("inventory")
    locations = state.get("item_locations")
    if not isinstance(inventory, list) or len(inventory) != len(set(inventory)) or not isinstance(locations, dict):
        raise ValueError("DORK v2 inventory ledger is malformed")
    if set(locations) != set(ITEMS) or any(item_id not in ITEMS for item_id in inventory):
        raise ValueError("DORK v2 item ledger is incomplete")
    for item_id in ITEMS:
        location = locations[item_id]
        in_inventory = item_id in inventory
        if in_inventory != (location == "inventory"):
            raise ValueError("DORK v2 inventory and item locations disagree")
        if location not in set(ROOMS) | {"inventory", "mailbox", "hidden"}:
            raise ValueError("DORK v2 item location is invalid")
    flags = state.get("flags")
    if (
        not isinstance(flags, dict)
        or set(flags) != _FLAG_NAMES
        or not all(type(value) is bool for value in flags.values())
    ):
        raise ValueError("DORK v2 flags must be boolean")
    discoveries = state.get("discovery_scores")
    if (
        not isinstance(discoveries, list)
        or discoveries != sorted(set(discoveries))
        or not set(discoveries).issubset(ITEMS)
    ):
        raise ValueError("DORK v2 discovery score ledger is invalid")
    exact_int(state.get("moves"), "DORK moves", minimum=0)
    transition_count = exact_int(state.get("transition_count"), "DORK transition_count", minimum=0)
    if state["moves"] != transition_count:
        raise ValueError("DORK v2 moves must match its transition count")
    clout = exact_int(state.get("clout"), "DORK clout", minimum=0)
    if flags["troll_ratioed"] and clout < 5:
        raise ValueError("DORK v2 ratio state requires its canonical clout award")
    if flags["troll_muted"] and (
        not flags["troll_ratioed"]
        or not {"tos_scroll", "nft_rock"}.issubset(discoveries)
        or locations["legacy_banhammer"] == "hidden"
    ):
        raise ValueError("DORK v2 troll state is inconsistent")
    if flags["wrapper_prompted"] != (locations["prompt_token"] != "hidden"):
        raise ValueError("DORK v2 wrapper state is inconsistent")
    if flags["server_deployed"] and (
        not {"punch_card", "prompt_token"}.issubset(discoveries)
        or locations["zero_dependency_crown"] == "hidden"
    ):
        raise ValueError("DORK v2 deployment state is inconsistent")
    if not flags["server_deployed"] and locations["zero_dependency_crown"] != "hidden":
        raise ValueError("DORK v2 crown cannot appear before deployment")
    score = exact_int(state.get("score"), "DORK score", minimum=0)
    if state.get("status") not in {"playing", "won"}:
        raise ValueError("DORK v2 status is invalid")
    expected_score = sum(ITEMS[item_id]["score"] for item_id in discoveries)
    expected_score += 10 if flags["troll_muted"] else 0
    expected_score += 10 if flags["server_deployed"] else 0
    if state["status"] == "won":
        if (
            "zero_dependency_crown" not in inventory
            or state["room_id"] not in {"west_of_startup", "forest_cache"}
            or not flags["server_deployed"]
        ):
            raise ValueError("DORK v2 victory requires the crown outdoors")
        expected_score = 100
    if score != expected_score:
        raise ValueError("DORK v2 score does not match discoveries and quest state")
    if state.get("content") != _board_content(state):
        raise ValueError("DORK v2 content view does not match authoritative state")


def inspect_dork(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "dork_v2_game_state":
        raise ValueError("object is not a DORK v2 game state")
    _validate_state(obj.payload)
    return obj


def _discover(state: dict[str, Any], item_id: str) -> None:
    if item_id not in state["discovery_scores"]:
        state["discovery_scores"].append(item_id)
        state["discovery_scores"].sort()
        state["score"] += ITEMS[item_id]["score"]


def _target_id(raw: str) -> str:
    return raw.strip().lower().replace("-", "_")


def _persist(world: WorldStore, previous_ref: str, state: dict[str, Any], transition: dict[str, Any]) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "dork_v2_game_state",
        state,
        {"actor": "human_operator", "reason": "dork_v2_transition"},
    )


def apply_action(
    world: WorldStore,
    game_ref: str,
    player_id: str,
    action: str,
    args: Sequence[str] = (),
) -> WorldObject:
    current = inspect_dork(world, game_ref)
    state = deepcopy(current.payload)
    if player_id != state["human_operator_id"]:
        raise ValueError("DORK v2 is human-only and bound to its creating operator")
    if state["status"] == "won":
        raise ValueError("DORK v2 is complete; the human has touched grass")
    action = action.strip().lower() if isinstance(action, str) else ""
    args = require_args(args, maximum=2)
    aliases = {
        "n": ("go", ["north"]),
        "north": ("go", ["north"]),
        "s": ("go", ["south"]),
        "south": ("go", ["south"]),
        "e": ("go", ["east"]),
        "east": ("go", ["east"]),
        "w": ("go", ["west"]),
        "west": ("go", ["west"]),
        "u": ("go", ["up"]),
        "up": ("go", ["up"]),
        "d": ("go", ["down"]),
        "down": ("go", ["down"]),
        "in": ("go", ["in"]),
        "enter": ("go", ["in"]),
        "out": ("go", ["out"]),
        "exit": ("go", ["out"]),
        "get": ("take", args),
        "i": ("inventory", []),
    }
    if action in aliases:
        if action != "get" and args:
            raise ValueError("DORK shorthand actions do not accept extra arguments")
        action, args = aliases[action]
    state["transition_count"] += 1
    state["moves"] += 1

    if action == "look" and not args:
        state["last_message"] = _room_message(state)
    elif action == "go" and len(args) == 1:
        direction = args[0].lower()
        room = ROOMS[state["room_id"]]
        if direction not in room["exits"]:
            raise ValueError("there is no DORK exit in that direction")
        if state["room_id"] == "north_of_startup" and direction == "in" and not state["flags"]["window_open"]:
            raise ValueError("the side window is closed")
        if state["room_id"] == "moderator_bridge" and direction == "west" and not state["flags"]["troll_muted"]:
            raise ValueError("the Content Moderator Troll blocks the bridge")
        state["room_id"] = room["exits"][direction]
        state["last_message"] = _room_message(state)
        append_event(state, "move", f"{player_id} moves {direction} to {ROOMS[state['room_id']]['name']}.")
    elif action == "open" and len(args) == 1:
        target = _target_id(args[0])
        if target == "mailbox" and state["room_id"] == "west_of_startup":
            state["flags"]["mailbox_open"] = True
            state["last_message"] = "The mailbox opens. Inside is a leaflet that immediately destroys the illusion that this is ordinary Zork."
        elif target == "window" and state["room_id"] == "north_of_startup":
            state["flags"]["window_open"] = True
            state["last_message"] = "The side window opens without JavaScript. You may GO IN."
        else:
            raise ValueError("that DORK object cannot be opened here")
    elif action == "take" and len(args) == 1:
        item_id = _target_id(args[0])
        if item_id not in ITEMS or item_id not in _visible_items(state):
            raise ValueError("that DORK item is not visible here")
        state["item_locations"][item_id] = "inventory"
        state["inventory"].append(item_id)
        state["inventory"].sort()
        _discover(state, item_id)
        state["last_message"] = f"Taken: {ITEMS[item_id]['name']}."
        append_event(state, "take", f"{player_id} takes {ITEMS[item_id]['name']}.", item_id=item_id)
    elif action == "drop" and len(args) == 1:
        item_id = _target_id(args[0])
        if item_id not in state["inventory"]:
            raise ValueError("that DORK item is not carried")
        state["inventory"].remove(item_id)
        state["item_locations"][item_id] = state["room_id"]
        state["last_message"] = f"Dropped: {ITEMS[item_id]['name']}."
    elif action == "read" and len(args) == 1:
        item_id = _target_id(args[0])
        if item_id not in state["inventory"] and item_id not in _visible_items(state):
            raise ValueError("that DORK item is not available to read")
        state["last_message"] = ITEMS[item_id]["description"]
    elif action == "inventory" and not args:
        state["last_message"] = "You are carrying: " + (
            ", ".join(ITEMS[item_id]["name"] for item_id in sorted(state["inventory"])) or "nothing"
        ) + "."
    elif action == "score" and not args:
        state["last_message"] = f"Your DORK score is {state['score']} out of a possible 100, with {state['clout']} synthetic clout."
    elif action == "shitpost" and not args:
        gained = digest_int(state["seed"], "shitpost", state["moves"]) % 2
        state["clout"] += gained
        state["last_message"] = "Your post achieves " + ("one unit of synthetic clout." if gained else "perfect algorithmic invisibility.")
    elif action == "lurk" and not args:
        state["last_message"] = "You lurk. For one glorious move, the content pipeline receives nothing."
    elif action == "subscribe" and not args:
        if state["room_id"] != "landing_page":
            raise ValueError("there is no subscription funnel here")
        state["flags"]["subscribed"] = True
        state["last_message"] = "You subscribe to the free tier. It is deprecated before the confirmation message finishes rendering."
    elif action == "prompt" and not args:
        if state["room_id"] != "ai_wrapper_lab":
            raise ValueError("there is no AI wrapper to prompt here")
        if not state["flags"]["wrapper_prompted"]:
            state["flags"]["wrapper_prompted"] = True
            state["item_locations"]["prompt_token"] = "ai_wrapper_lab"
        state["last_message"] = "The wrapper calls somebody else's API and emits one locally actionable prompt token."
    elif action == "ratio" and len(args) == 1:
        target = _target_id(args[0])
        if state["room_id"] != "moderator_bridge" or target not in {"troll", "moderator", "content_moderator_troll"}:
            raise ValueError("there is no ratioable troll here")
        if "nft_rock" not in state["inventory"]:
            raise ValueError("the troll ignores ratios without the evidentiary NFT-backed rock")
        if not state["flags"]["troll_ratioed"]:
            state["flags"]["troll_ratioed"] = True
            state["clout"] += 5
            state["last_message"] = "The rock has more engagement than the troll. The ratio is devastating but not yet procedurally binding."
        else:
            state["last_message"] = "The ratio is already canonical. Reposting it creates no new clout."
    elif action == "mute" and len(args) == 1:
        target = _target_id(args[0])
        if state["room_id"] != "moderator_bridge" or target not in {"troll", "moderator", "content_moderator_troll"}:
            raise ValueError("there is no mutable troll here")
        if "tos_scroll" not in state["inventory"] or not state["flags"]["troll_ratioed"]:
            raise ValueError("mute requires both the terms scroll and a completed troll ratio")
        if not state["flags"]["troll_muted"]:
            state["flags"]["troll_muted"] = True
            state["item_locations"]["legacy_banhammer"] = "moderator_bridge"
            state["score"] += 10
            state["last_message"] = "Clause 14 and the prior ratio prevail. The troll is muted and drops the legacy banhammer."
        else:
            state["last_message"] = "The troll is already muted. Civilization briefly continues."
    elif action == "deploy" and not args:
        if state["room_id"] != "server_closet":
            raise ValueError("deployment is only useful in the zero-dependency server closet")
        if not {"punch_card", "prompt_token"}.issubset(set(state["inventory"])):
            raise ValueError("deploy requires the EBCDIC punch card and prompt token")
        if not state["flags"]["server_deployed"]:
            state["flags"]["server_deployed"] = True
            state["item_locations"]["zero_dependency_crown"] = "server_closet"
            state["score"] += 10
        state["last_message"] = "The beige computer deploys instantly. No image is pulled. The Zero-Dependency Crown materializes."
    elif action == "grass" and not args:
        if state["room_id"] not in {"west_of_startup", "forest_cache"} or "zero_dependency_crown" not in state["inventory"]:
            raise ValueError("you must return outdoors with the Zero-Dependency Crown before touching grass")
        state["status"] = "won"
        state["score"] = 100
        state["last_message"] = "You touch grass. The Great Under-Moderated NEXUS loses jurisdiction. You have won DORK v2."
        append_event(state, "win", f"{player_id} wins DORK v2 by touching grass.")
    else:
        raise ValueError("unknown or malformed DORK v2 action")

    if action not in {"go", "take", "grass"}:
        append_event(state, action or "action", state["last_message"], player_id=player_id)
    return _persist(
        world,
        current.object_id,
        state,
        {"kind": "action", "player_id": player_id, "action": action, "args": args},
    )


def player_view(state: dict[str, Any], player_id: str) -> dict[str, Any]:
    if player_id != state.get("human_operator_id"):
        raise ValueError("DORK v2 has no AI or alternate player view")
    _validate_state(state)
    room = ROOMS[state["room_id"]]
    return {
        "schema": DORK_SCHEMA,
        "title": DORK_TITLE,
        "human_only": True,
        "player_id": player_id,
        "status": state["status"],
        "room": {"room_id": state["room_id"], **deepcopy(room)},
        "visible_items": [
            {"item_id": item_id, "name": ITEMS[item_id]["name"]} for item_id in _visible_items(state)
        ],
        "inventory": [
            {"item_id": item_id, "name": ITEMS[item_id]["name"]} for item_id in sorted(state["inventory"])
        ],
        "score": state["score"],
        "clout": state["clout"],
        "moves": state["moves"],
        "message": state["last_message"],
        "legal_actions": [item["action"] for item in DORK_ACTIONS],
    }
