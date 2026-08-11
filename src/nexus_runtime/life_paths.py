from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Sequence

from .game_cards import clean_seed, player_roster
from .world import WorldObject, WorldStore


LIFE_PATHS_SCHEMA = "nexus-life-paths/1"
LIFE_PATHS_KIND = "original_cooperative_life_path_simulation"
LIFE_PATHS_TITLE = "NEXUS LIFE PATHS"
MAX_PLAYERS = 8

TRAITS = ("curiosity", "craft", "community", "resilience")

CHAPTERS: tuple[dict[str, Any], ...] = (
    {
        "chapter_id": "launch",
        "label": "Launch",
        "prompt": "How do you begin when the map is incomplete?",
        "choices": {
            "learn": {"label": "Learn deeply", "delta": {"curiosity": 2, "craft": 1}},
            "wander": {"label": "Explore widely", "delta": {"curiosity": 2, "resilience": 1}},
            "build": {"label": "Make something small", "delta": {"craft": 2, "resilience": 1}},
        },
    },
    {
        "chapter_id": "vocation",
        "label": "Vocation",
        "prompt": "What kind of useful work do you lean into?",
        "choices": {
            "specialize": {"label": "Become a specialist", "delta": {"craft": 2, "curiosity": 1}},
            "organize": {"label": "Organize a project", "delta": {"craft": 1, "community": 2}},
            "serve": {"label": "Take a public-service role", "delta": {"community": 2, "resilience": 1}},
        },
    },
    {
        "chapter_id": "community",
        "label": "Community",
        "prompt": "How do you relate to the people and models around you?",
        "choices": {
            "mentor": {"label": "Mentor someone", "delta": {"community": 2, "craft": 1}},
            "collaborate": {"label": "Build together", "delta": {"community": 2, "curiosity": 1}},
            "explore_together": {"label": "Explore together", "delta": {"community": 1, "curiosity": 2}},
        },
    },
    {
        "chapter_id": "setback",
        "label": "Setback",
        "prompt": "Something goes wrong. What do you practice?",
        "choices": {
            "rebuild": {"label": "Rebuild patiently", "delta": {"resilience": 2, "craft": 1}},
            "pivot": {"label": "Change direction", "delta": {"resilience": 1, "curiosity": 2}},
            "ask_for_help": {"label": "Ask for help", "delta": {"resilience": 1, "community": 2}},
        },
    },
    {
        "chapter_id": "reinvention",
        "label": "Reinvention",
        "prompt": "You get another chapter. What do you do with it?",
        "choices": {
            "research": {"label": "Research a new field", "delta": {"curiosity": 2, "craft": 1}},
            "create": {"label": "Create something original", "delta": {"craft": 2, "curiosity": 1}},
            "steward": {"label": "Steward what already works", "delta": {"community": 1, "resilience": 2}},
        },
    },
    {
        "chapter_id": "legacy",
        "label": "Legacy",
        "prompt": "What do you leave behind for whoever comes next?",
        "choices": {
            "archive": {"label": "Archive the knowledge", "delta": {"craft": 1, "community": 1, "curiosity": 1}},
            "teach": {"label": "Teach the next traveller", "delta": {"community": 2, "craft": 1}},
            "seed_next": {"label": "Seed a new experiment", "delta": {"curiosity": 2, "resilience": 1}},
        },
    },
)


def life_paths_catalog() -> dict[str, Any]:
    return {
        "schema": LIFE_PATHS_SCHEMA,
        "title": LIFE_PATHS_TITLE,
        "game_kind": LIFE_PATHS_KIND,
        "traits": list(TRAITS),
        "chapters": deepcopy(list(CHAPTERS)),
        "claim_boundary": {
            "original_nexus_game": True,
            "commercial_game_of_life_rules_or_assets": False,
            "fictional_resources_and_choices": True,
            "real_person_or_model_destiny_claim": False,
            "progression_creates_authority": False,
        },
    }


def _bonus(seed: str, player: str, chapter_id: str, choice_id: str) -> tuple[str, int]:
    digest = hashlib.sha256(f"{seed}|{player}|{chapter_id}|{choice_id}".encode("utf-8")).digest()
    trait = TRAITS[digest[0] % len(TRAITS)]
    return trait, digest[1] % 2


def _summary(account: dict[str, int]) -> str:
    highest = max(account.values())
    leaders = [trait for trait in TRAITS if account[trait] == highest]
    if len(leaders) == 1:
        return f"strongest thread: {leaders[0]}"
    return "balanced threads: " + ", ".join(leaders)


def _content(state: dict[str, Any]) -> str:
    lines = [
        "NEXUS LIFE PATHS — ORIGINAL COOPERATIVE LIFE SIMULATION",
        f"chapter_index={state['chapter_index']} completed={state['completed']}",
    ]
    if not state["completed"]:
        chapter = CHAPTERS[state["chapter_index"]]
        lines.append(f"chapter={chapter['chapter_id']} prompt={chapter['prompt']}")
        lines.append(f"current_player={state['players'][state['turn_index']]}")
        lines.append("choices=" + ",".join(chapter["choices"]))
    for player in state["players"]:
        account = state["accounts"][player]
        lines.append(
            f"- {player} curiosity={account['curiosity']} craft={account['craft']} "
            f"community={account['community']} resilience={account['resilience']}"
        )
    if state["completed"]:
        for player in state["players"]:
            lines.append(f"legacy[{player}]={_summary(state['accounts'][player])}")
    lines.append("fictional_game=true; authority_effect=none")
    return "\n".join(lines)


def new_life_paths(
    world: WorldStore,
    *,
    seed: str = "long-road-home",
    players: Sequence[str] = ("Alpha",),
    human_players: Sequence[str] = (),
) -> WorldObject:
    roster, controllers = player_roster(
        players,
        human_players=human_players,
        minimum=1,
        maximum=MAX_PLAYERS,
    )
    state: dict[str, Any] = {
        "schema": LIFE_PATHS_SCHEMA,
        "game_kind": LIFE_PATHS_KIND,
        "title": LIFE_PATHS_TITLE,
        "seed": clean_seed(seed, "long-road-home"),
        "players": roster,
        "controllers": controllers,
        "accounts": {
            player: {trait: 2 for trait in TRAITS}
            for player in roster
        },
        "chapter_index": 0,
        "turn_index": 0,
        "completed": False,
        "transition_count": 0,
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game"},
        "event_log": [
            {
                "sequence": 0,
                "kind": "new_game",
                "text": f"{roster[0]} begins the first Life Paths chapter.",
            }
        ],
        "claim_boundary": life_paths_catalog()["claim_boundary"],
    }
    state["content"] = _content(state)
    return world.create_object(
        "life_paths_state",
        state,
        {"actor": "nexus_game_engine", "reason": "new_life_paths_game"},
    )


def _validate(state: dict[str, Any]) -> None:
    if state.get("schema") != LIFE_PATHS_SCHEMA or state.get("game_kind") != LIFE_PATHS_KIND:
        raise ValueError("unsupported Life Paths state schema")
    players = state.get("players")
    controllers = state.get("controllers")
    accounts = state.get("accounts")
    if not isinstance(players, list) or not 1 <= len(players) <= MAX_PLAYERS:
        raise ValueError("Life Paths player roster is invalid")
    if not isinstance(controllers, dict) or set(controllers) != set(players):
        raise ValueError("Life Paths controllers are invalid")
    if not isinstance(accounts, dict) or set(accounts) != set(players):
        raise ValueError("Life Paths accounts are invalid")
    for player in players:
        account = accounts[player]
        if not isinstance(account, dict) or set(account) != set(TRAITS):
            raise ValueError("Life Paths trait account is invalid")
        if not all(type(account[trait]) is int and 0 <= account[trait] <= 64 for trait in TRAITS):
            raise ValueError("Life Paths trait values are invalid")
    chapter_index = state.get("chapter_index")
    turn_index = state.get("turn_index")
    completed = state.get("completed")
    if type(chapter_index) is not int or not 0 <= chapter_index <= len(CHAPTERS):
        raise ValueError("Life Paths chapter index is invalid")
    if type(turn_index) is not int or not 0 <= turn_index < len(players):
        raise ValueError("Life Paths turn index is invalid")
    if type(completed) is not bool or completed != (chapter_index == len(CHAPTERS)):
        raise ValueError("Life Paths completion state is invalid")
    if state.get("claim_boundary") != life_paths_catalog()["claim_boundary"]:
        raise ValueError("Life Paths claim boundary is invalid")
    if state.get("content") != _content(state):
        raise ValueError("Life Paths public content is inconsistent")


def inspect_life_paths(world: WorldStore, state_ref: str) -> WorldObject:
    obj = world.inspect(state_ref)
    if obj.object_type != "life_paths_state":
        raise ValueError("object is not a Life Paths game state")
    _validate(obj.payload)
    return obj


def apply_life_paths_choice(
    world: WorldStore,
    state_ref: str,
    *,
    player_id: str,
    choice_id: str,
) -> WorldObject:
    current = inspect_life_paths(world, state_ref)
    state = deepcopy(current.payload)
    if state["completed"]:
        raise ValueError("Life Paths is already complete")
    current_player = state["players"][state["turn_index"]]
    if player_id != current_player:
        raise ValueError("it is not that player's Life Paths turn")
    chapter = CHAPTERS[state["chapter_index"]]
    if choice_id not in chapter["choices"]:
        raise ValueError("choice_id is not available in the current Life Paths chapter")
    choice = chapter["choices"][choice_id]
    for trait, amount in choice["delta"].items():
        state["accounts"][player_id][trait] += amount
    bonus_trait, bonus = _bonus(state["seed"], player_id, chapter["chapter_id"], choice_id)
    state["accounts"][player_id][bonus_trait] += bonus
    state["transition_count"] += 1
    state["event_log"].append(
        {
            "sequence": state["transition_count"],
            "kind": "choice",
            "text": (
                f"{player_id} chose {choice_id} in {chapter['chapter_id']}"
                + (f" and gained a deterministic {bonus_trait} bonus" if bonus else "")
                + "."
            ),
        }
    )
    if len(state["event_log"]) > 64:
        state["event_log"] = state["event_log"][-64:]
    if state["turn_index"] + 1 < len(state["players"]):
        state["turn_index"] += 1
    else:
        state["turn_index"] = 0
        state["chapter_index"] += 1
    state["completed"] = state["chapter_index"] == len(CHAPTERS)
    state["previous_state_ref"] = current.object_id
    state["last_transition"] = {
        "kind": "choice",
        "player_id": player_id,
        "chapter_id": chapter["chapter_id"],
        "choice_id": choice_id,
        "bonus_trait": bonus_trait,
        "bonus": bonus,
    }
    state["content"] = _content(state)
    return world.create_object(
        "life_paths_state",
        state,
        {"actor": "nexus_game_engine", "reason": "life_paths_choice"},
    )


__all__ = [
    "CHAPTERS",
    "LIFE_PATHS_KIND",
    "LIFE_PATHS_SCHEMA",
    "LIFE_PATHS_TITLE",
    "apply_life_paths_choice",
    "inspect_life_paths",
    "life_paths_catalog",
    "new_life_paths",
]
