from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import re
from typing import Any

from .canonical import canonical_json
from .world import WorldObject, WorldStore


MUD_SCHEMA = "nexus-cursed-mud/1"
MUD_KIND = "cursed_multi_user_dungeon"
MUD_TITLE = "HERESY MUD: The Great Under-Moderated Dungeon"
MAX_EVENT_LOG = 16
_PLAYER_RE = re.compile(r"[A-Za-z0-9_.-]{1,32}")

_CLAIM_BOUNDARY = {
    "fictional_simulation": True,
    "real_world_policy_claim": False,
    "real_weapon_procurement": False,
    "game_stats_are_real_world_measurements": False,
    "model_narration_mutates_state": False,
    "network_mud_server": False,
}

_ROOM_DECK: tuple[dict[str, Any], ...] = (
    {
        "room_id": "bbs_gate",
        "realm": "beige",
        "name": "The Beige Login Prompt",
        "description": "A phosphor-green prompt hums beneath a MOTD nobody has revised since dial-up was considered ambitious.",
        "exits": {"north": "terms_catacomb", "east": "venture_tavern"},
    },
    {
        "room_id": "terms_catacomb",
        "realm": "beige",
        "name": "Terms-of-Service Catacomb",
        "description": "An endless licence scroll descends into darkness. The meaningful opt-out was removed in a minor patch.",
        "exits": {"south": "bbs_gate", "east": "microservice_maze"},
    },
    {
        "room_id": "venture_tavern",
        "realm": "beige",
        "name": "The Venture-Backed Tavern",
        "description": "The ale is free during customer acquisition. A pricing migration begins when you ask for a second mug.",
        "exits": {"west": "bbs_gate", "north": "node_modules_pit"},
    },
    {
        "room_id": "microservice_maze",
        "realm": "framework",
        "name": "Microservice Maze",
        "description": "Every doorway is a service boundary. None of the services know why the product displays one sentence.",
        "exits": {"west": "terms_catacomb", "east": "moderation_bridge", "south": "node_modules_pit"},
    },
    {
        "room_id": "node_modules_pit",
        "realm": "framework",
        "name": "node_modules Pit",
        "description": "Millions of tiny packages rustle below. Something has depended on left-pad again.",
        "exits": {"south": "venture_tavern", "north": "microservice_maze", "east": "cobol_vault"},
    },
    {
        "room_id": "moderation_bridge",
        "realm": "framework",
        "name": "Bridge of the Content Moderator Troll",
        "description": "A legacy banhammer blocks the bridge while a queue of appeals becomes eventually consistent.",
        "exits": {"west": "microservice_maze", "east": "nixos_cathedral"},
    },
    {
        "room_id": "cobol_vault",
        "realm": "heresy",
        "name": "COBOL Record Vault",
        "description": "Everything is fixed-width, checksummed, rectangular and offensively easy to back up.",
        "exits": {"west": "node_modules_pit", "north": "punchcard_crypt"},
    },
    {
        "room_id": "punchcard_crypt",
        "realm": "heresy",
        "name": "EBCDIC Punch-Card Crypt",
        "description": "A deck of cards promises cloud-native architecture if fed through enough obsolete languages in the correct order.",
        "exits": {"south": "cobol_vault", "east": "forceos_shrine"},
    },
    {
        "room_id": "nixos_cathedral",
        "realm": "heresy",
        "name": "Cathedral of Declarative Purity",
        "description": "A flake.lock rests on the altar. Nearby, an Arch user has been demoted to the Old Testament.",
        "exits": {"west": "moderation_bridge", "south": "forceos_shrine"},
    },
    {
        "room_id": "forceos_shrine",
        "realm": "heresy",
        "name": "FORCEOS '38 Shrine",
        "description": "Raster bars, SID arpeggios and a 326-byte microkernel reject infrastructure as a personality trait.",
        "exits": {"west": "punchcard_crypt", "north": "nixos_cathedral", "east": "dependency_cache"},
    },
    {
        "room_id": "dependency_cache",
        "realm": "heresy",
        "name": "Dependency Dragon Cache",
        "description": "A dragon sleeps on a hoard of lockfiles, transitive dependencies and one package nobody remembers installing.",
        "exits": {"west": "forceos_shrine"},
    },
)

_ITEM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "item_id": "large_trout",
        "name": "a large trout",
        "description": "A traditional instrument of network diplomacy.",
        "kind": "weapon",
        "power": 3,
        "score": 1,
        "initial_location": {"kind": "room", "id": "venture_tavern"},
    },
    {
        "item_id": "yaml_scroll",
        "name": "the YAML scroll of recursive indentation",
        "description": "It describes a service whose purpose is to describe another service.",
        "kind": "treasure",
        "power": 0,
        "score": 2,
        "initial_location": {"kind": "room", "id": "microservice_maze"},
    },
    {
        "item_id": "nft_rock",
        "name": "an NFT-backed rock",
        "description": "The rock has retained more utility than the certificate.",
        "kind": "treasure",
        "power": 0,
        "score": 1,
        "initial_location": {"kind": "room", "id": "node_modules_pit"},
    },
    {
        "item_id": "left_pad_talisman",
        "name": "a left-pad talisman",
        "description": "A tiny dependency with civilization-scale historical significance. Restores 3 HP.",
        "kind": "consumable",
        "power": 3,
        "score": 0,
        "initial_location": {"kind": "room", "id": "terms_catacomb"},
    },
    {
        "item_id": "immutable_receipt",
        "name": "an immutable COBOL receipt",
        "description": "379 characters of beige certainty. The checksum is smug.",
        "kind": "treasure",
        "power": 0,
        "score": 4,
        "initial_location": {"kind": "room", "id": "cobol_vault"},
    },
    {
        "item_id": "punch_card",
        "name": "an EBCDIC punch card",
        "description": "A physical capability token for the final cache. Do not fold, spindle or containerize.",
        "kind": "key",
        "power": 0,
        "score": 2,
        "initial_location": {"kind": "room", "id": "punchcard_crypt"},
    },
    {
        "item_id": "banhammer",
        "name": "the legacy banhammer",
        "description": "Older than the appeals process and considerably more deterministic.",
        "kind": "weapon",
        "power": 5,
        "score": 4,
        "initial_location": {"kind": "npc", "id": "content_moderator_troll"},
    },
    {
        "item_id": "zero_dependency_crown",
        "name": "the Zero-Dependency Crown",
        "description": "Forged from the radical proposition that a text adventure may not require Kubernetes.",
        "kind": "treasure",
        "power": 0,
        "score": 12,
        "initial_location": {"kind": "npc", "id": "dependency_dragon"},
    },
)

_NPC_SPECS: tuple[dict[str, Any], ...] = (
    {
        "npc_id": "brand_intern_paladin",
        "name": "Brand Intern Paladin",
        "room_id": "bbs_gate",
        "max_hp": 6,
        "attack": 1,
        "hostile": False,
        "description": "Their smile has quarterly targets and a conversion funnel.",
    },
    {
        "npc_id": "yaml_necromancer",
        "name": "YAML Necromancer",
        "room_id": "microservice_maze",
        "max_hp": 8,
        "attack": 2,
        "hostile": True,
        "description": "Raises dead configuration into increasingly indented undeath.",
    },
    {
        "npc_id": "content_moderator_troll",
        "name": "Content Moderator Troll",
        "room_id": "moderation_bridge",
        "max_hp": 10,
        "attack": 3,
        "hostile": True,
        "description": "Carries a legacy banhammer and six contradictory policy documents.",
    },
    {
        "npc_id": "dependency_dragon",
        "name": "Dependency Dragon",
        "room_id": "dependency_cache",
        "max_hp": 18,
        "attack": 4,
        "hostile": True,
        "description": "Each head represents a transitive package. Removing one installs two replacements.",
    },
)

_DIRECTION_ALIASES = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "u": "up",
    "d": "down",
}


def _rooms() -> dict[str, dict[str, Any]]:
    return {room["room_id"]: deepcopy(room) for room in _ROOM_DECK}


def _items() -> dict[str, dict[str, Any]]:
    return {
        spec["item_id"]: {
            "item_id": spec["item_id"],
            "name": spec["name"],
            "description": spec["description"],
            "kind": spec["kind"],
            "power": spec["power"],
            "score": spec["score"],
            "score_awarded": False,
            "location": deepcopy(spec["initial_location"]),
        }
        for spec in _ITEM_SPECS
    }


def _npcs() -> dict[str, dict[str, Any]]:
    return {
        spec["npc_id"]: {
            "npc_id": spec["npc_id"],
            "name": spec["name"],
            "description": spec["description"],
            "room_id": spec["room_id"],
            "hp": spec["max_hp"],
            "max_hp": spec["max_hp"],
            "attack": spec["attack"],
            "hostile": spec["hostile"],
            "alive": True,
        }
        for spec in _NPC_SPECS
    }


def _player(player_id: str) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "room_id": "bbs_gate",
        "hp": 12,
        "max_hp": 12,
        "clout": 0,
        "score": 0,
        "alive": True,
    }


def action_catalog() -> list[dict[str, str]]:
    return [
        {"action": "go", "syntax": "go <north|south|east|west|n|s|e|w>"},
        {"action": "take", "syntax": "take <item-id>"},
        {"action": "drop", "syntax": "drop <item-id>"},
        {"action": "use", "syntax": "use <item-id>"},
        {"action": "attack", "syntax": "attack <npc-id> [weapon-item-id]"},
        {"action": "rest", "syntax": "rest"},
        {"action": "shitpost", "syntax": "shitpost [npc-id]"},
        {"action": "ratio", "syntax": "ratio <npc-id>"},
    ]


def _validate_player_id(player_id: str) -> str:
    if not isinstance(player_id, str) or _PLAYER_RE.fullmatch(player_id) is None:
        raise ValueError("MUD player ids must match [A-Za-z0-9_.-]{1,32}")
    return player_id


def _new_state(seed: str, player_ids: list[str]) -> dict[str, Any]:
    clean_players: list[str] = []
    seen: set[str] = set()
    for raw in player_ids:
        player_id = _validate_player_id(raw)
        folded = player_id.casefold()
        if folded in seen:
            raise ValueError("MUD player ids must be unique case-insensitively")
        seen.add(folded)
        clean_players.append(player_id)
    if not clean_players:
        raise ValueError("MUD requires at least one player")
    if len(clean_players) > 16:
        raise ValueError("MUD supports at most 16 players in this alpha")

    state: dict[str, Any] = {
        "schema": MUD_SCHEMA,
        "game_kind": MUD_KIND,
        "title": MUD_TITLE,
        "seed": seed,
        "turn": 0,
        "previous_state_ref": None,
        "fictional_only": True,
        "claim_boundary": dict(_CLAIM_BOUNDARY),
        "realms": {
            "beige": "Beige Realm",
            "framework": "Framework Realm",
            "heresy": "Heresy Realm",
        },
        "rooms": _rooms(),
        "players": {player_id: _player(player_id) for player_id in clean_players},
        "items": _items(),
        "npcs": _npcs(),
        "quest": {
            "quest_id": "zero_dependency_crown",
            "objective": "Defeat the Dependency Dragon and recover the Zero-Dependency Crown.",
            "status": "open",
            "completed_by": None,
        },
        "event_log": [
            {
                "turn": 0,
                "kind": "motd",
                "text": "WELCOME TO THE GREAT UNDER-MODERATED DUNGEON. ANSI is optional; consequences are not.",
            }
        ],
    }
    state["content"] = _board_content(state)
    _validate_state(state)
    return state


def new_mud(world: WorldStore, seed: str = "beige-dungeon", player_ids: list[str] | None = None) -> WorldObject:
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("MUD seed must be non-empty text")
    seed = seed.strip()[:128]
    state = _new_state(seed, list(player_ids or ["operator"]))
    return world.create_object(
        "mud_game_state",
        state,
        {"actor": "nexus_mud_engine", "reason": "new_cursed_mud"},
    )


def inspect_mud(world: WorldStore, mud_ref: str) -> WorldObject:
    obj = world.inspect(mud_ref)
    if obj.object_type != "mud_game_state":
        raise ValueError("object is not a cursed MUD state")
    if obj.payload.get("schema") != MUD_SCHEMA or obj.payload.get("game_kind") != MUD_KIND:
        raise ValueError("unsupported cursed MUD state schema")
    _validate_state(obj.payload)
    return obj


def _item_spec(item_id: str) -> dict[str, Any]:
    return next(spec for spec in _ITEM_SPECS if spec["item_id"] == item_id)


def _npc_spec(npc_id: str) -> dict[str, Any]:
    return next(spec for spec in _NPC_SPECS if spec["npc_id"] == npc_id)


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != MUD_SCHEMA or state.get("game_kind") != MUD_KIND:
        raise ValueError("unsupported cursed MUD state schema")
    if state.get("title") != MUD_TITLE:
        raise ValueError("cursed MUD title mismatch")
    if state.get("fictional_only") is not True or state.get("claim_boundary") != _CLAIM_BOUNDARY:
        raise ValueError("cursed MUD claim boundary mismatch")
    if not isinstance(state.get("seed"), str) or not state["seed"]:
        raise ValueError("cursed MUD requires a non-empty seed")
    if type(state.get("turn")) is not int or state["turn"] < 0:
        raise ValueError("cursed MUD turn must be a non-negative exact integer")
    previous = state.get("previous_state_ref")
    if previous is not None and (not isinstance(previous, str) or not previous.startswith("object:")):
        raise ValueError("cursed MUD previous_state_ref must be null or an object ref")
    if state.get("rooms") != _rooms():
        raise ValueError("cursed MUD room topology does not match the canonical dungeon")
    if state.get("realms") != {
        "beige": "Beige Realm",
        "framework": "Framework Realm",
        "heresy": "Heresy Realm",
    }:
        raise ValueError("cursed MUD realm registry mismatch")

    players = state.get("players")
    if not isinstance(players, dict) or not players or len(players) > 16:
        raise ValueError("cursed MUD players must be a non-empty object with at most 16 entries")
    folded_ids: set[str] = set()
    for player_id, player in players.items():
        _validate_player_id(player_id)
        if player_id.casefold() in folded_ids:
            raise ValueError("cursed MUD player ids must be unique case-insensitively")
        folded_ids.add(player_id.casefold())
        if not isinstance(player, dict) or player.get("player_id") != player_id:
            raise ValueError("cursed MUD player identity mismatch")
        if player.get("room_id") not in state["rooms"]:
            raise ValueError("cursed MUD player references unknown room")
        for field in ("hp", "max_hp", "clout", "score"):
            if type(player.get(field)) is not int:
                raise ValueError(f"cursed MUD player field {field} must be an exact integer")
        if player["max_hp"] <= 0 or not 0 <= player["hp"] <= player["max_hp"]:
            raise ValueError("cursed MUD player HP is out of bounds")
        if type(player.get("alive")) is not bool or player["alive"] != (player["hp"] > 0):
            raise ValueError("cursed MUD player alive flag must match HP")

    npcs = state.get("npcs")
    expected_npc_ids = {spec["npc_id"] for spec in _NPC_SPECS}
    if not isinstance(npcs, dict) or set(npcs) != expected_npc_ids:
        raise ValueError("cursed MUD NPC registry mismatch")
    for npc_id, npc in npcs.items():
        spec = _npc_spec(npc_id)
        if not isinstance(npc, dict):
            raise ValueError("invalid cursed MUD NPC entry")
        for field in ("npc_id", "name", "description", "room_id", "max_hp", "attack", "hostile"):
            expected = spec[field]
            if npc.get(field) != expected:
                raise ValueError(f"cursed MUD NPC immutable field mismatch: {npc_id}.{field}")
        if type(npc.get("hp")) is not int or not 0 <= npc["hp"] <= npc["max_hp"]:
            raise ValueError("cursed MUD NPC HP is out of bounds")
        if type(npc.get("alive")) is not bool or npc["alive"] != (npc["hp"] > 0):
            raise ValueError("cursed MUD NPC alive flag must match HP")

    items = state.get("items")
    expected_item_ids = {spec["item_id"] for spec in _ITEM_SPECS}
    if not isinstance(items, dict) or set(items) != expected_item_ids:
        raise ValueError("cursed MUD item registry mismatch")
    for item_id, item in items.items():
        spec = _item_spec(item_id)
        if not isinstance(item, dict):
            raise ValueError("invalid cursed MUD item entry")
        for field in ("item_id", "name", "description", "kind", "power", "score"):
            if item.get(field) != spec[field]:
                raise ValueError(f"cursed MUD item immutable field mismatch: {item_id}.{field}")
        if type(item.get("score_awarded")) is not bool:
            raise ValueError(f"cursed MUD item score_awarded must be boolean: {item_id}")
        location = item.get("location")
        if not isinstance(location, dict) or set(location) != {"kind", "id"}:
            raise ValueError("cursed MUD item location must contain kind and id")
        kind = location.get("kind")
        holder = location.get("id")
        if kind == "room" and holder not in state["rooms"]:
            raise ValueError("cursed MUD item references unknown room")
        if kind == "player" and holder not in players:
            raise ValueError("cursed MUD item references unknown player")
        if kind == "npc" and holder not in npcs:
            raise ValueError("cursed MUD item references unknown NPC")
        if kind == "consumed" and holder is not None:
            raise ValueError("consumed cursed MUD item must have null id")
        if kind not in {"room", "player", "npc", "consumed"}:
            raise ValueError("unknown cursed MUD item location kind")
        if kind == "npc" and not npcs[holder]["alive"]:
            raise ValueError("dead NPC cannot retain cursed MUD item")

    quest = state.get("quest")
    if not isinstance(quest, dict) or quest.get("quest_id") != "zero_dependency_crown":
        raise ValueError("cursed MUD quest state mismatch")
    if quest.get("status") not in {"open", "complete"}:
        raise ValueError("cursed MUD quest status is invalid")
    if quest["status"] == "complete" and quest.get("completed_by") not in players:
        raise ValueError("completed cursed MUD quest requires a valid player")
    if quest["status"] == "open" and quest.get("completed_by") is not None:
        raise ValueError("open cursed MUD quest cannot have completed_by")

    event_log = state.get("event_log")
    if not isinstance(event_log, list) or not event_log or len(event_log) > MAX_EVENT_LOG:
        raise ValueError("cursed MUD event log must be a non-empty bounded list")
    for event in event_log:
        if not isinstance(event, dict) or type(event.get("turn")) is not int or not isinstance(event.get("text"), str):
            raise ValueError("invalid cursed MUD event")

    content = state.get("content")
    if not isinstance(content, str) or content != _board_content(state):
        raise ValueError("cursed MUD model-readable content view does not match authoritative state")


def _location_items(state: dict[str, Any], kind: str, holder: str) -> list[str]:
    return sorted(
        item_id
        for item_id, item in state["items"].items()
        if item["location"] == {"kind": kind, "id": holder}
    )


def _room_npcs(state: dict[str, Any], room_id: str) -> list[str]:
    return sorted(npc_id for npc_id, npc in state["npcs"].items() if npc["room_id"] == room_id and npc["alive"])


def _board_content(state: dict[str, Any]) -> str:
    lines = [
        MUD_TITLE,
        f"TURN {state['turn']} | QUEST {state['quest']['status'].upper()}: {state['quest']['objective']}",
        "This is fictional game state. Model narration cannot mutate it.",
        "PLAYERS:",
    ]
    for player_id in sorted(state["players"], key=str.casefold):
        player = state["players"][player_id]
        room = state["rooms"][player["room_id"]]
        inventory = _location_items(state, "player", player_id)
        lines.append(
            f"- {player_id}: HP {player['hp']}/{player['max_hp']} clout={player['clout']} score={player['score']} "
            f"room={player['room_id']} ({room['name']}) inventory={','.join(inventory) if inventory else '-'}"
        )

    active_rooms = sorted({player["room_id"] for player in state["players"].values()})
    lines.append("CURRENT ROOMS:")
    for room_id in active_rooms:
        room = state["rooms"][room_id]
        visible_items = _location_items(state, "room", room_id)
        visible_npcs = _room_npcs(state, room_id)
        exit_text = ",".join(f"{direction}:{target}" for direction, target in sorted(room["exits"].items()))
        lines.append(
            f"- {room_id}: {room['name']} realm={room['realm']} exits=[{exit_text}] "
            f"items={','.join(visible_items) if visible_items else '-'} npcs={','.join(visible_npcs) if visible_npcs else '-'}"
        )

    lines.append("NPC STATUS:")
    for npc_id in sorted(state["npcs"]):
        npc = state["npcs"][npc_id]
        status = f"HP {npc['hp']}/{npc['max_hp']}" if npc["alive"] else "DEFEATED"
        lines.append(f"- {npc_id}: {status} room={npc['room_id']}")

    lines.append("RECENT EVENTS:")
    for event in state["event_log"][-5:]:
        lines.append(f"- T{event['turn']} {event['kind']}: {event['text']}")
    return "\n".join(lines)


def _roll(state: dict[str, Any], label: str, sides: int) -> int:
    if type(sides) is not int or sides <= 0:
        raise ValueError("deterministic roll requires positive exact integer sides")
    body = canonical_json({"state": state, "label": label}).encode("utf-8")
    return int.from_bytes(sha256(body).digest()[:8], "big") % sides


def _event(state: dict[str, Any], kind: str, text: str, **extra: Any) -> None:
    state["event_log"].append({"turn": state["turn"], "kind": kind, "text": text, **extra})
    state["event_log"] = state["event_log"][-MAX_EVENT_LOG:]


def _player_state(state: dict[str, Any], player_id: str) -> dict[str, Any]:
    try:
        player = state["players"][player_id]
    except KeyError as exc:
        raise ValueError(f"unknown MUD player: {player_id}") from exc
    if not player["alive"]:
        raise ValueError(f"MUD player is defeated: {player_id}")
    return player


def _same_room_npc(state: dict[str, Any], player: dict[str, Any], npc_id: str) -> dict[str, Any]:
    npc = state["npcs"].get(npc_id)
    if not isinstance(npc, dict) or not npc["alive"]:
        raise ValueError(f"no living NPC named {npc_id}")
    if npc["room_id"] != player["room_id"]:
        raise ValueError(f"NPC {npc_id} is not in the player's room")
    return npc


def _weapon_power(state: dict[str, Any], player_id: str, weapon_id: str | None) -> tuple[int, str]:
    owned = _location_items(state, "player", player_id)
    if weapon_id is None:
        weapons = [item_id for item_id in owned if state["items"][item_id]["kind"] == "weapon"]
        if not weapons:
            return 1, "bare hands"
        weapon_id = max(weapons, key=lambda item_id: (state["items"][item_id]["power"], item_id))
    if weapon_id not in state["items"] or weapon_id not in owned:
        raise ValueError(f"player does not hold item: {weapon_id}")
    item = state["items"][weapon_id]
    if item["kind"] != "weapon":
        raise ValueError(f"item is not a weapon: {weapon_id}")
    return item["power"], weapon_id


def _drop_npc_items(state: dict[str, Any], npc_id: str, room_id: str) -> None:
    for item in state["items"].values():
        if item["location"] == {"kind": "npc", "id": npc_id}:
            item["location"] = {"kind": "room", "id": room_id}
            _event(state, "drop", f"{item['name']} drops into {state['rooms'][room_id]['name']}.", item_id=item["item_id"])


def _drop_player_items(state: dict[str, Any], player_id: str, room_id: str) -> None:
    for item in state["items"].values():
        if item["location"] == {"kind": "player", "id": player_id}:
            item["location"] = {"kind": "room", "id": room_id}
            _event(
                state,
                "death_drop",
                f"{player_id} drops {item['name']} in {state['rooms'][room_id]['name']} after defeat.",
                player_id=player_id,
                item_id=item["item_id"],
            )


def _retaliate(state: dict[str, Any], prior: dict[str, Any], player: dict[str, Any], npc: dict[str, Any], label: str) -> None:
    if not npc["alive"] or not npc["hostile"]:
        return
    damage = 1 + _roll(prior, f"retaliate:{label}:{npc['npc_id']}", npc["attack"])
    player["hp"] = max(0, player["hp"] - damage)
    player["alive"] = player["hp"] > 0
    _event(state, "retaliation", f"{npc['name']} hits {player['player_id']} for {damage} HP.", damage=damage)
    if not player["alive"]:
        _drop_player_items(state, player["player_id"], player["room_id"])
        _event(state, "defeat", f"{player['player_id']} has been defeated by legacy infrastructure; inventory dropped into the room.")


def apply_action(
    world: WorldStore,
    mud_ref: str,
    player_id: str,
    action: str,
    args: list[str] | None = None,
) -> WorldObject:
    current = inspect_mud(world, mud_ref)
    prior = deepcopy(current.payload)
    state = deepcopy(prior)
    player_id = _validate_player_id(player_id)
    player = _player_state(state, player_id)
    raw_args = list(args or [])
    if not all(isinstance(arg, str) and arg for arg in raw_args):
        raise ValueError("MUD action args must be non-empty strings")
    action_id = action.strip().lower() if isinstance(action, str) else ""
    if not action_id:
        raise ValueError("MUD action must be non-empty text")

    state["turn"] += 1

    if action_id == "go":
        if len(raw_args) != 1:
            raise ValueError("go requires exactly one direction")
        direction = _DIRECTION_ALIASES.get(raw_args[0].lower(), raw_args[0].lower())
        room = state["rooms"][player["room_id"]]
        target = room["exits"].get(direction)
        if target is None:
            raise ValueError(f"no exit {direction} from {player['room_id']}")
        if target == "dependency_cache" and "punch_card" not in _location_items(state, "player", player_id):
            raise ValueError("the Dependency Dragon Cache rejects you: an EBCDIC punch card is required")
        old_room = player["room_id"]
        player["room_id"] = target
        _event(state, "move", f"{player_id} goes {direction}: {old_room} -> {target}.", player_id=player_id)

    elif action_id == "take":
        if len(raw_args) != 1:
            raise ValueError("take requires exactly one item id")
        item_id = raw_args[0].lower()
        item = state["items"].get(item_id)
        if not isinstance(item, dict) or item["location"] != {"kind": "room", "id": player["room_id"]}:
            raise ValueError(f"item is not available here: {item_id}")
        if item_id == "zero_dependency_crown" and state["npcs"]["dependency_dragon"]["alive"]:
            raise ValueError("the Zero-Dependency Crown cannot be recovered while the Dependency Dragon is alive")
        item["location"] = {"kind": "player", "id": player_id}
        if not item["score_awarded"]:
            player["score"] += item["score"]
            item["score_awarded"] = True
        _event(state, "take", f"{player_id} takes {item['name']}.", player_id=player_id, item_id=item_id)
        if item_id == "zero_dependency_crown" and state["quest"]["status"] == "open":
            state["quest"]["status"] = "complete"
            state["quest"]["completed_by"] = player_id
            player["clout"] += 10
            _event(
                state,
                "quest_complete",
                f"{player_id} recovers the Zero-Dependency Crown. Small is beautiful; bloat is unholy.",
                player_id=player_id,
            )

    elif action_id == "drop":
        if len(raw_args) != 1:
            raise ValueError("drop requires exactly one item id")
        item_id = raw_args[0].lower()
        item = state["items"].get(item_id)
        if not isinstance(item, dict) or item["location"] != {"kind": "player", "id": player_id}:
            raise ValueError(f"player does not hold item: {item_id}")
        item["location"] = {"kind": "room", "id": player["room_id"]}
        _event(state, "drop", f"{player_id} drops {item['name']}.", player_id=player_id, item_id=item_id)

    elif action_id == "use":
        if len(raw_args) != 1:
            raise ValueError("use requires exactly one item id")
        item_id = raw_args[0].lower()
        item = state["items"].get(item_id)
        if not isinstance(item, dict) or item["location"] != {"kind": "player", "id": player_id}:
            raise ValueError(f"player does not hold item: {item_id}")
        if item_id != "left_pad_talisman":
            raise ValueError(f"item has no direct use action: {item_id}")
        before = player["hp"]
        player["hp"] = min(player["max_hp"], player["hp"] + item["power"])
        item["location"] = {"kind": "consumed", "id": None}
        _event(state, "use", f"{player_id} invokes left-pad and restores {player['hp'] - before} HP.", player_id=player_id)

    elif action_id == "attack":
        if not 1 <= len(raw_args) <= 2:
            raise ValueError("attack requires <npc-id> [weapon-item-id]")
        npc_id = raw_args[0].lower()
        npc = _same_room_npc(state, player, npc_id)
        power, weapon_label = _weapon_power(state, player_id, raw_args[1].lower() if len(raw_args) == 2 else None)
        damage = 1 + _roll(prior, f"attack:{player_id}:{npc_id}:{weapon_label}", power)
        npc["hp"] = max(0, npc["hp"] - damage)
        npc["alive"] = npc["hp"] > 0
        if not npc["hostile"]:
            player["clout"] -= 1
        _event(
            state,
            "attack",
            f"{player_id} attacks {npc['name']} with {weapon_label} for {damage} HP.",
            player_id=player_id,
            npc_id=npc_id,
            damage=damage,
        )
        if not npc["alive"]:
            player["score"] += npc["max_hp"]
            player["clout"] += 2 if npc["hostile"] else -2
            _event(state, "npc_defeated", f"{npc['name']} is defeated by {player_id}.", npc_id=npc_id)
            _drop_npc_items(state, npc_id, npc["room_id"])
            if npc_id == "dependency_dragon":
                _event(
                    state,
                    "quest_progress",
                    f"{player_id} defeats the Dependency Dragon. The Zero-Dependency Crown drops and must still be recovered.",
                    player_id=player_id,
                )
        else:
            _retaliate(state, prior, player, npc, f"attack:{player_id}:{npc_id}:{weapon_label}")

    elif action_id == "rest":
        if raw_args:
            raise ValueError("rest takes no arguments")
        hostiles = [state["npcs"][npc_id] for npc_id in _room_npcs(state, player["room_id"]) if state["npcs"][npc_id]["hostile"]]
        if hostiles:
            raise ValueError("cannot rest while a hostile NPC is present")
        before = player["hp"]
        player["hp"] = min(player["max_hp"], player["hp"] + 2)
        _event(state, "rest", f"{player_id} rests and restores {player['hp'] - before} HP.", player_id=player_id)

    elif action_id == "shitpost":
        if len(raw_args) > 1:
            raise ValueError("shitpost accepts at most one NPC id")
        player["clout"] += 1
        if not raw_args:
            _event(state, "shitpost", f"{player_id} shitposts into the void. The void reluctantly subscribes.", player_id=player_id)
        else:
            npc_id = raw_args[0].lower()
            npc = _same_room_npc(state, player, npc_id)
            damage = 1 + _roll(prior, f"shitpost:{player_id}:{npc_id}", 2)
            npc["hp"] = max(0, npc["hp"] - damage)
            npc["alive"] = npc["hp"] > 0
            _event(state, "shitpost", f"{player_id} shitposts at {npc['name']} for {damage} reputation damage.", damage=damage)
            if not npc["alive"]:
                player["score"] += npc["max_hp"]
                _event(state, "npc_defeated", f"{npc['name']} has been posted through the floor.", npc_id=npc_id)
                _drop_npc_items(state, npc_id, npc["room_id"])
                if npc_id == "dependency_dragon":
                    _event(
                        state,
                        "quest_progress",
                        f"{player_id} shitposts the Dependency Dragon out of production. The Zero-Dependency Crown drops and must still be recovered.",
                        player_id=player_id,
                    )
            else:
                _retaliate(state, prior, player, npc, f"shitpost:{player_id}:{npc_id}")

    elif action_id == "ratio":
        if len(raw_args) != 1:
            raise ValueError("ratio requires exactly one NPC id")
        npc_id = raw_args[0].lower()
        npc = _same_room_npc(state, player, npc_id)
        threshold = min(8, max(2, 4 + player["clout"]))
        success = _roll(prior, f"ratio:{player_id}:{npc_id}", 10) < threshold
        if success:
            damage = 2
            npc["hp"] = max(0, npc["hp"] - damage)
            npc["alive"] = npc["hp"] > 0
            player["clout"] += 2
            _event(state, "ratio", f"{player_id} ratios {npc['name']}. Brutal, deterministic, terminal-native.", success=True)
            if not npc["alive"]:
                player["score"] += npc["max_hp"]
                _event(state, "npc_defeated", f"{npc['name']} has lost the argument and all remaining HP.", npc_id=npc_id)
                _drop_npc_items(state, npc_id, npc["room_id"])
                if npc_id == "dependency_dragon":
                    _event(
                        state,
                        "quest_progress",
                        f"{player_id} ratios the Dependency Dragon into a single static binary. The Zero-Dependency Crown drops and must still be recovered.",
                        player_id=player_id,
                    )
            else:
                _retaliate(state, prior, player, npc, f"ratio:{player_id}:{npc_id}")
        else:
            player["clout"] -= 1
            _event(state, "ratio", f"{player_id} attempts a ratio and is immediately quote-posted by {npc['name']}.", success=False)
            _retaliate(state, prior, player, npc, f"ratio-fail:{player_id}:{npc_id}")

    else:
        raise ValueError(f"unknown MUD action: {action_id}")

    state["previous_state_ref"] = current.object_id
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "mud_game_state",
        state,
        {
            "actor": "nexus_mud_engine",
            "reason": "cursed_mud_action",
            "previous_state_ref": current.object_id,
            "player_id": player_id,
            "action": action_id,
            "args": raw_args,
        },
    )


def player_view(state: dict[str, Any], player_id: str) -> dict[str, Any]:
    _validate_state(state)
    player_id = _validate_player_id(player_id)
    if player_id not in state["players"]:
        raise ValueError(f"unknown MUD player: {player_id}")
    player = state["players"][player_id]
    room = state["rooms"][player["room_id"]]
    return {
        "player": deepcopy(player),
        "room": deepcopy(room),
        "inventory": [deepcopy(state["items"][item_id]) for item_id in _location_items(state, "player", player_id)],
        "room_items": [deepcopy(state["items"][item_id]) for item_id in _location_items(state, "room", player["room_id"])],
        "room_npcs": [deepcopy(state["npcs"][npc_id]) for npc_id in _room_npcs(state, player["room_id"])],
        "quest": deepcopy(state["quest"]),
    }
