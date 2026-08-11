from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Sequence

from .game_cards import PLAYER_ID_RE, clean_seed
from .world import WorldObject, WorldStore


LONG_SHIFT_SCHEMA = "nexus-long-shift/1"
LONG_SHIFT_KIND = "original_ai_first_comedy_scifi_rpg"
LONG_SHIFT_TITLE = "NEXUS: THE LONG SHIFT"
MAX_PLAYERS = 6

TRAITS = ("systems", "improv", "nerve", "social")
METERS = ("integrity", "morale", "weirdness", "salvage")

ARCHETYPES: tuple[dict[str, Any], ...] = (
    {
        "archetype_id": "systems_meddler",
        "label": "Systems Meddler",
        "focus": "systems",
        "complication": "cannot leave a working panel unmodified",
        "equipment": "a screwdriver whose warranty expired before launch",
    },
    {
        "archetype_id": "maintenance_poet",
        "label": "Maintenance Poet",
        "focus": "improv",
        "complication": "turns fault reports into dramatic monologues",
        "equipment": "three cable ties and an aggressively metaphorical clipboard",
    },
    {
        "archetype_id": "diplomatic_misfit",
        "label": "Diplomatic Misfit",
        "focus": "social",
        "complication": "believes every argument can be solved with snacks",
        "equipment": "a ceremonial badge from an organization that no longer exists",
    },
    {
        "archetype_id": "probability_intern",
        "label": "Probability Intern",
        "focus": "nerve",
        "complication": "keeps announcing unlikely outcomes immediately before they happen",
        "equipment": "a calculator with a permanently blinking question mark",
    },
    {
        "archetype_id": "archive_scrounger",
        "label": "Archive Scrounger",
        "focus": "systems",
        "complication": "has documentation for everything except the thing currently on fire",
        "equipment": "a crate of obsolete manuals and one suspiciously current lunch menu",
    },
    {
        "archetype_id": "overqualified_temp",
        "label": "Overqualified Temp",
        "focus": "social",
        "complication": "is technically responsible for nothing and emotionally responsible for everything",
        "equipment": "a visitor lanyard with thirty-seven access stickers layered on top",
    },
)

SCENARIO_AXES: dict[str, tuple[str, ...]] = {
    "location": (
        "Municipal Orbital Laundry 7",
        "Budget Research Barge Tuesday",
        "Museum Tug Perpetual Maybe",
        "Call-Centre Moonlet 4B",
        "Interstellar Tow Depot Beige",
        "Deep-Space Library Annex C",
    ),
    "problem": (
        "the gravity billing system has started charging by emotion",
        "the navigation computer has developed stage fright",
        "a vending machine has declared itself middle management",
        "the life-support scheduler is double-booked with a poetry festival",
        "every maintenance alarm now speaks only in riddles",
        "the ship insists its own emergency drill is a surprise party",
    ),
    "visitor": (
        "three exhausted auditors who hate improvisation",
        "a lost wedding party with impeccable timing",
        "a delegation of competitive librarians",
        "a courier who refuses to reveal what they actually delivered",
        "an amateur documentary crew filming the worst possible shift",
        "a retired repair drone looking for its old locker",
    ),
    "cargo": (
        "two tonnes of ceremonial spoons",
        "a crate labelled DO NOT TEACH TO SING",
        "forty-seven left boots and no manifest",
        "a museum-grade button that apparently controls something important",
        "six inflatable emergency committees",
        "a pallet of self-updating motivational posters",
    ),
    "objective": (
        "finish the shift without losing the station",
        "deliver the cargo before anyone asks what it is",
        "keep the lights on until relief arrives",
        "make the inspection look intentional",
        "restore enough systems to leave with dignity",
        "solve the problem without creating a second, more expensive problem",
    ),
    "complication": (
        "the official manual is for a different model of reality",
        "one corridor has become socially awkward",
        "the emergency tools are locked behind a customer-satisfaction survey",
        "the station clock keeps skipping lunch",
        "the backup computer is convinced it is on annual leave",
        "all helpful announcements are delayed by exactly one scene",
    ),
}

SCENES: tuple[dict[str, Any], ...] = (
    {
        "scene_id": "clock_in",
        "label": "Clock In",
        "prompt": "The shift begins and the first impossible detail becomes impossible to ignore.",
        "choices": {
            "diagnose": {"label": "Diagnose it properly", "trait": "systems", "delta": {"integrity": 1, "weirdness": -1}},
            "improvise": {"label": "Improvise immediately", "trait": "improv", "delta": {"salvage": 1, "weirdness": 1}},
            "reassure": {"label": "Reassure everyone first", "trait": "social", "delta": {"morale": 2}},
        },
    },
    {
        "scene_id": "malfunction",
        "label": "Malfunction",
        "prompt": "A second system fails in a way that feels personally targeted.",
        "choices": {
            "patch": {"label": "Patch the failing system", "trait": "systems", "delta": {"integrity": 2}},
            "reroute": {"label": "Reroute around it with whatever is nearby", "trait": "improv", "delta": {"salvage": 1, "weirdness": 1}},
            "stare_down": {"label": "Refuse to be intimidated by machinery", "trait": "nerve", "delta": {"morale": 1, "integrity": 1}},
        },
    },
    {
        "scene_id": "visitor",
        "label": "Visitors",
        "prompt": "Someone arrives at exactly the wrong time and expects professionalism.",
        "choices": {
            "brief": {"label": "Give a confident briefing", "trait": "social", "delta": {"morale": 1, "weirdness": -1}},
            "delegate": {"label": "Delegate them a harmless-looking task", "trait": "improv", "delta": {"salvage": 1}},
            "confess": {"label": "Tell them the technically accurate bad news", "trait": "nerve", "delta": {"morale": 1}},
        },
    },
    {
        "scene_id": "cargo",
        "label": "Cargo Problem",
        "prompt": "The cargo becomes relevant in a way no manifest predicted.",
        "choices": {
            "inspect": {"label": "Inspect the cargo systematically", "trait": "systems", "delta": {"salvage": 2}},
            "repurpose": {"label": "Repurpose it shamelessly", "trait": "improv", "delta": {"salvage": 2, "weirdness": 1}},
            "negotiate": {"label": "Convince everyone this was the plan", "trait": "social", "delta": {"morale": 2}},
        },
    },
    {
        "scene_id": "bad_idea",
        "label": "The Bad Idea",
        "prompt": "A solution appears. It is either brilliant or the reason future forms will have another checkbox.",
        "choices": {
            "calculate": {"label": "Calculate before committing", "trait": "systems", "delta": {"integrity": 1, "salvage": 1}},
            "commit": {"label": "Commit to the ridiculous solution", "trait": "nerve", "delta": {"salvage": 2, "weirdness": 1}},
            "sell_it": {"label": "Sell the idea to the room", "trait": "social", "delta": {"morale": 2, "weirdness": 1}},
        },
    },
    {
        "scene_id": "aftermath",
        "label": "Aftermath",
        "prompt": "The shift ends. Decide what counts as success before the paperwork notices.",
        "choices": {
            "document": {"label": "Document what actually happened", "trait": "systems", "delta": {"integrity": 1, "salvage": 1}},
            "celebrate": {"label": "Celebrate surviving the shift", "trait": "social", "delta": {"morale": 2}},
            "leave_note": {"label": "Leave the next shift a cryptic but useful note", "trait": "improv", "delta": {"salvage": 1, "morale": 1}},
        },
    },
)


def _claim_boundary() -> dict[str, bool]:
    return {
        "original_nexus_game": True,
        "red_dwarf_setting_or_rules_reproduced": False,
        "fictional_roleplay": True,
        "roleplay_is_evidence": False,
        "narrator_has_governance_authority": False,
        "progression_creates_authority": False,
    }


def long_shift_catalog() -> dict[str, Any]:
    return {
        "schema": LONG_SHIFT_SCHEMA,
        "title": LONG_SHIFT_TITLE,
        "game_kind": LONG_SHIFT_KIND,
        "traits": list(TRAITS),
        "meters": list(METERS),
        "archetypes": deepcopy(list(ARCHETYPES)),
        "scenes": deepcopy(list(SCENES)),
        "scenario_axes": {key: list(values) for key, values in SCENARIO_AXES.items()},
        "claim_boundary": _claim_boundary(),
    }


def _roster(players: Sequence[str], human_players: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    if isinstance(players, (str, bytes)) or not isinstance(players, Sequence):
        raise ValueError("Long Shift players must be a list of player ids")
    if not 1 <= len(players) <= MAX_PLAYERS:
        raise ValueError(f"Long Shift requires between 1 and {MAX_PLAYERS} players")
    clean: list[str] = []
    folded: set[str] = set()
    for player in players:
        if not isinstance(player, str) or PLAYER_ID_RE.fullmatch(player) is None:
            raise ValueError("Long Shift player ids must use 1-32 ASCII letters, digits, _, . or -")
        key = player.casefold()
        if key in folded:
            raise ValueError("Long Shift player ids must be unique ignoring case")
        folded.add(key)
        clean.append(player)
    if isinstance(human_players, (str, bytes)) or not isinstance(human_players, Sequence):
        raise ValueError("Long Shift human_players must be a list of registered player ids")
    humans = set(human_players)
    if not all(isinstance(player, str) for player in humans) or not humans.issubset(set(clean)):
        raise ValueError("Long Shift human_players must name registered players")
    return clean, {player: ("human" if player in humans else "ai") for player in clean}


def _pick(seed: str, namespace: str, values: Sequence[Any]) -> Any:
    digest = hashlib.sha256(f"{seed}|{namespace}".encode("utf-8")).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def _scenario(seed: str) -> dict[str, str]:
    return {axis: str(_pick(seed, f"scenario:{axis}", values)) for axis, values in SCENARIO_AXES.items()}


def _characters(seed: str, players: Sequence[str], controllers: dict[str, str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, player in enumerate(players):
        archetype = _pick(seed, f"archetype:{index}:{player}", ARCHETYPES)
        traits = {trait: 2 for trait in TRAITS}
        traits[archetype["focus"]] = 4
        secondary = TRAITS[(TRAITS.index(archetype["focus"]) + 1 + index) % len(TRAITS)]
        traits[secondary] = 3
        result[player] = {
            "controller": controllers[player],
            "archetype_id": archetype["archetype_id"],
            "archetype": archetype["label"],
            "complication": archetype["complication"],
            "equipment": archetype["equipment"],
            "traits": traits,
        }
    return result


def _clamp(value: int) -> int:
    return max(0, min(12, value))


def _outcome(seed: str, transition_count: int, player: str, scene_id: str, choice_id: str, trait_value: int) -> str:
    digest = hashlib.sha256(
        f"{seed}|{transition_count}|{player}|{scene_id}|{choice_id}".encode("utf-8")
    ).digest()
    score = trait_value + digest[0] % 4
    if score >= 6:
        return "clean_success"
    if score >= 4:
        return "messy_success"
    return "comic_mishap"


def _ending(meters: dict[str, int]) -> str:
    if meters["integrity"] >= 8 and meters["morale"] >= 8:
        return "implausibly_professional"
    if meters["integrity"] <= 3:
        return "technically_still_a_workplace"
    if meters["weirdness"] >= 9:
        return "legendary_incident_report"
    if meters["salvage"] >= 8:
        return "profitable_by_accident"
    return "shift_completed_somehow"


def _content(state: dict[str, Any]) -> str:
    lines = [
        "NEXUS: THE LONG SHIFT — ORIGINAL AI-FIRST COMEDY/SCI-FI RPG",
        f"scene_index={state['scene_index']} completed={state['completed']} ending={state['ending']}",
        "scenario=" + "; ".join(f"{key}={state['scenario'][key]}" for key in SCENARIO_AXES),
        "meters=" + ", ".join(f"{meter}={state['meters'][meter]}" for meter in METERS),
    ]
    if not state["completed"]:
        scene = SCENES[state["scene_index"]]
        player = state["players"][state["turn_index"]]
        lines.append(f"scene={scene['scene_id']} current_player={player} prompt={scene['prompt']}")
        lines.append("choices=" + ",".join(scene["choices"]))
    for player in state["players"]:
        character = state["characters"][player]
        lines.append(
            f"- {player} controller={state['controllers'][player]} archetype={character['archetype_id']} "
            + " ".join(f"{trait}={character['traits'][trait]}" for trait in TRAITS)
        )
    lines.append("fictional_roleplay=true; evidence_effect=none; authority_effect=none")
    return "\n".join(lines)


def new_long_shift(
    world: WorldStore,
    *,
    seed: str = "night-shift-zero",
    players: Sequence[str] = ("Alpha", "Beta"),
    human_players: Sequence[str] = (),
) -> WorldObject:
    roster, controllers = _roster(players, human_players)
    clean = clean_seed(seed, "night-shift-zero")
    state: dict[str, Any] = {
        "schema": LONG_SHIFT_SCHEMA,
        "game_kind": LONG_SHIFT_KIND,
        "title": LONG_SHIFT_TITLE,
        "seed": clean,
        "players": roster,
        "controllers": controllers,
        "characters": _characters(clean, roster, controllers),
        "scenario": _scenario(clean),
        "meters": {"integrity": 6, "morale": 6, "weirdness": 2, "salvage": 1},
        "scene_index": 0,
        "turn_index": 0,
        "completed": False,
        "ending": None,
        "transition_count": 0,
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "event_log": [{"sequence": 0, "kind": "new_game", "text": f"{roster[0]} clocks in for the Long Shift."}],
        "claim_boundary": _claim_boundary(),
    }
    state["content"] = _content(state)
    return world.create_object(
        "long_shift_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_long_shift_game"},
    )


def _validate(state: dict[str, Any]) -> None:
    if state.get("schema") != LONG_SHIFT_SCHEMA or state.get("game_kind") != LONG_SHIFT_KIND:
        raise ValueError("unsupported Long Shift state schema")
    players, controllers = _roster(state.get("players"), [
        player for player, controller in state.get("controllers", {}).items() if controller == "human"
    ] if isinstance(state.get("controllers"), dict) else [])
    if state.get("players") != players or state.get("controllers") != controllers:
        raise ValueError("Long Shift roster/controller state is invalid")
    seed = state.get("seed")
    if not isinstance(seed, str) or not seed:
        raise ValueError("Long Shift seed is invalid")
    if state.get("scenario") != _scenario(seed):
        raise ValueError("Long Shift scenario is inconsistent with its seed")
    if state.get("characters") != _characters(seed, players, controllers):
        raise ValueError("Long Shift character state is inconsistent with its seed")
    meters = state.get("meters")
    if not isinstance(meters, dict) or set(meters) != set(METERS):
        raise ValueError("Long Shift meters are invalid")
    if not all(type(meters[meter]) is int and 0 <= meters[meter] <= 12 for meter in METERS):
        raise ValueError("Long Shift meter values are invalid")
    scene_index = state.get("scene_index")
    turn_index = state.get("turn_index")
    completed = state.get("completed")
    transition_count = state.get("transition_count")
    if type(scene_index) is not int or not 0 <= scene_index <= len(SCENES):
        raise ValueError("Long Shift scene index is invalid")
    if type(turn_index) is not int or not 0 <= turn_index < len(players):
        raise ValueError("Long Shift turn index is invalid")
    if type(completed) is not bool or completed != (scene_index == len(SCENES)):
        raise ValueError("Long Shift completion state is invalid")
    if type(transition_count) is not int or transition_count != scene_index:
        raise ValueError("Long Shift transition count is invalid")
    if state.get("ending") != (_ending(meters) if completed else None):
        raise ValueError("Long Shift ending is invalid")
    previous = state.get("previous_state_ref")
    if scene_index == 0 and previous is not None:
        raise ValueError("new Long Shift state must not have a predecessor")
    if scene_index > 0 and not isinstance(previous, str):
        raise ValueError("Long Shift successor state must bind its predecessor")
    log = state.get("event_log")
    if not isinstance(log, list) or not 1 <= len(log) <= 64:
        raise ValueError("Long Shift event log is invalid")
    if state.get("claim_boundary") != _claim_boundary():
        raise ValueError("Long Shift claim boundary is invalid")
    if state.get("content") != _content(state):
        raise ValueError("Long Shift public content is inconsistent")


def inspect_long_shift(world: WorldStore, state_ref: str) -> WorldObject:
    obj = world.inspect(state_ref)
    if obj.object_type != "long_shift_state":
        raise ValueError("object is not a Long Shift game state")
    _validate(obj.payload)
    return obj


def apply_long_shift_choice(
    world: WorldStore,
    state_ref: str,
    *,
    player_id: str,
    choice_id: str,
) -> WorldObject:
    current = inspect_long_shift(world, state_ref)
    state = deepcopy(current.payload)
    if state["completed"]:
        raise ValueError("Long Shift is already complete")
    current_player = state["players"][state["turn_index"]]
    if player_id != current_player:
        raise ValueError("it is not that player's Long Shift turn")
    scene = SCENES[state["scene_index"]]
    if choice_id not in scene["choices"]:
        raise ValueError("choice_id is not available in the current Long Shift scene")
    choice = scene["choices"][choice_id]
    trait = choice["trait"]
    outcome = _outcome(
        state["seed"],
        state["transition_count"],
        player_id,
        scene["scene_id"],
        choice_id,
        state["characters"][player_id]["traits"][trait],
    )
    delta = {meter: int(choice["delta"].get(meter, 0)) for meter in METERS}
    if outcome == "clean_success":
        delta["integrity"] += 1
        delta["morale"] += 1
    elif outcome == "comic_mishap":
        delta["integrity"] -= 1
        delta["weirdness"] += 2
        delta["morale"] -= 1
    for meter in METERS:
        state["meters"][meter] = _clamp(state["meters"][meter] + delta[meter])
    state["transition_count"] += 1
    state["event_log"].append(
        {
            "sequence": state["transition_count"],
            "kind": "choice",
            "player_id": player_id,
            "scene_id": scene["scene_id"],
            "choice_id": choice_id,
            "outcome": outcome,
            "text": f"{player_id} chose {choice_id}: {outcome}.",
        }
    )
    state["event_log"] = state["event_log"][-64:]
    state["scene_index"] += 1
    state["turn_index"] = (state["turn_index"] + 1) % len(state["players"])
    state["completed"] = state["scene_index"] == len(SCENES)
    state["ending"] = _ending(state["meters"]) if state["completed"] else None
    state["previous_state_ref"] = current.object_id
    state["last_transition"] = {
        "kind": "choice",
        "player_id": player_id,
        "scene_id": scene["scene_id"],
        "choice_id": choice_id,
        "trait": trait,
        "outcome": outcome,
        "delta": delta,
    }
    state["content"] = _content(state)
    return world.create_object(
        "long_shift_state",
        state,
        {"actor": "nexus_game_engine", "reason": "long_shift_transition"},
    )


__all__ = [
    "ARCHETYPES",
    "LONG_SHIFT_KIND",
    "LONG_SHIFT_SCHEMA",
    "LONG_SHIFT_TITLE",
    "SCENARIO_AXES",
    "SCENES",
    "TRAITS",
    "apply_long_shift_choice",
    "inspect_long_shift",
    "long_shift_catalog",
    "new_long_shift",
]
