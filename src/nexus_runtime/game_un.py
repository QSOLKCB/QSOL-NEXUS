from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .canonical import canonical_json
from .world import WorldObject, WorldStore

GAME_SCHEMA = "nexus-un-sim/1"
GAME_KIND = "fictional_un_simulation"
MAX_EVENT_LOG = 12

COUNTRY_DECK: tuple[tuple[str, str], ...] = (
    ("troutistan", "Republic of Troutistan"),
    ("bananovia", "Commonwealth of Bananovia"),
    ("kestrelia", "Federation of Kestrelia"),
    ("sablemere", "Free State of Sablemere"),
    ("wombatia", "People's Republic of Wombatia"),
    ("pixelgrad", "Democratic Union of Pixelgrad"),
)

ACTIONS: dict[str, dict[str, str]] = {
    "sanction": {"targets": "one_or_more", "description": "Reduce economy/stability; raise tension."},
    "support": {"targets": "one_or_more", "description": "Increase economy/influence; backing belligerents raises tension."},
    "aid": {"targets": "one_or_more", "description": "Increase economy/stability and UN legitimacy."},
    "arms": {"targets": "one_or_more", "description": "Abstract arms trade: military +1, economy -1, tension +2."},
    "meme": {"targets": "one_or_more", "description": "Meme campaign with deterministic success/backfire."},
    "suspend": {"targets": "one_or_more", "description": "Suspend fictional member state from the Assembly."},
    "reinstate": {"targets": "one_or_more", "description": "Restore a suspended fictional member state."},
    "recognize": {"targets": "one_or_more", "description": "Increase influence/reputation."},
    "mediate": {"targets": "exactly_two", "description": "Attempt a deterministic ceasefire."},
    "do_nothing": {"targets": "none", "description": "Take no action while the crisis continues."},
}

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def action_catalog() -> dict[str, dict[str, str]]:
    return copy.deepcopy(ACTIONS)


def _digest_int(*parts: object) -> int:
    material = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _bounded(value: int, low: int = 0, high: int = 12) -> int:
    return max(low, min(high, value))


def _stat(seed: str, country_id: str, field: str, low: int, high: int) -> int:
    return low + _digest_int(seed, country_id, field) % (high - low + 1)


def _country(seed: str, country_id: str, name: str) -> dict[str, Any]:
    return {
        "country_id": country_id,
        "name": name,
        "economy": _stat(seed, country_id, "economy", 4, 9),
        "military": _stat(seed, country_id, "military", 3, 8),
        "stability": _stat(seed, country_id, "stability", 4, 9),
        "influence": _stat(seed, country_id, "influence", 2, 7),
        "reputation": _stat(seed, country_id, "reputation", 4, 9),
        "territory": 3,
        "sanctions": 0,
        "arms_imports": 0,
        "meme_heat": 0,
        "suspended": False,
    }


def _initial_pair(seed: str) -> tuple[str, str]:
    ranked = [country_id for country_id, _ in COUNTRY_DECK]
    ranked.sort(key=lambda country_id: (_digest_int(seed, "initial-war", country_id), country_id))
    a, b = sorted((ranked[0], ranked[1]))
    return a, b


def _board_content(state: dict[str, Any]) -> str:
    """Compact deterministic model-readable board view.

    Full state remains in the content-addressed world object. The generic
    Council evidence path prefers this `content` field so model actors see the
    whole current board without spending the per-object evidence budget on
    historical event detail.
    """
    lines = [
        "NEXUS UN SIMULATION — FICTIONAL GAME STATE ONLY",
        f"turn={state['turn']} world_tension={state['world_tension']} un_legitimacy={state['un_legitimacy']}",
        "wars:",
    ]
    wars = state["wars"]
    if wars:
        for war in sorted(wars, key=lambda item: (item["a"], item["b"])):
            lines.append(
                f"- {war['a']} vs {war['b']} score={war['score_a']}-{war['score_b']} started_turn={war['started_turn']}"
            )
    else:
        lines.append("- none")

    lines.append("countries:")
    for country_id in sorted(state["countries"]):
        country = state["countries"][country_id]
        status = " suspended" if country["suspended"] else ""
        lines.append(
            f"- {country_id} | {country['name']} | economy={country['economy']} military={country['military']} "
            f"stability={country['stability']} influence={country['influence']} reputation={country['reputation']} "
            f"territory={country['territory']} sanctions={country['sanctions']} arms_imports={country['arms_imports']} "
            f"meme_heat={country['meme_heat']}{status}"
        )

    if state["event_log"]:
        latest = state["event_log"][-1]
        lines.append(f"latest_event={latest['kind']}: {latest['text']}")
    lines.append("boundary=fictional simulation; not real-world policy, evidence, or weapons procurement")
    return "\n".join(lines)


def _new_state(seed: str) -> dict[str, Any]:
    countries = {country_id: _country(seed, country_id, name) for country_id, name in COUNTRY_DECK}
    a, b = _initial_pair(seed)
    state: dict[str, Any] = {
        "schema": GAME_SCHEMA,
        "game_kind": GAME_KIND,
        "fictional_only": True,
        "seed": seed,
        "turn": 0,
        "world_tension": 6,
        "un_legitimacy": 7,
        "countries": countries,
        "wars": [{"a": a, "b": b, "score_a": 0, "score_b": 0, "started_turn": 0}],
        "event_log": [
            {
                "turn": 0,
                "kind": "crisis_start",
                "text": f"{countries[a]['name']} and {countries[b]['name']} have gone to war. The Assembly has opinions.",
            }
        ],
        "previous_state_ref": None,
        "last_transition": {"kind": "new_game", "seed": seed},
        "claim_boundary": {
            "fictional_simulation": True,
            "real_world_policy_claim": False,
            "real_weapon_procurement": False,
            "game_stats_are_real_world_measurements": False,
        },
    }
    state["content"] = _board_content(state)
    return state


def new_game(world: WorldStore, seed: str = "trout-council") -> WorldObject:
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("game seed must be non-empty text")
    seed = seed.strip()[:128]
    return world.create_object(
        "un_sim_game_state",
        _new_state(seed),
        {"actor": "nexus_game_engine", "reason": "new_fictional_un_simulation"},
    )


def inspect_game(world: WorldStore, game_ref: str) -> WorldObject:
    obj = world.inspect(game_ref)
    if obj.object_type != "un_sim_game_state":
        raise ValueError("object is not a UN simulation game state")
    if obj.payload.get("schema") != GAME_SCHEMA or obj.payload.get("game_kind") != GAME_KIND:
        raise ValueError("unsupported UN simulation game state schema")
    _validate_state(obj.payload)
    return obj


def _validate_state(state: dict[str, Any]) -> None:
    if type(state.get("turn")) is not int or state["turn"] < 0:
        raise ValueError("game turn must be a non-negative exact integer")
    if not isinstance(state.get("content"), str) or not state["content"]:
        raise ValueError("game state requires a non-empty model-readable content view")
    countries = state.get("countries")
    wars = state.get("wars")
    if not isinstance(countries, dict) or not countries:
        raise ValueError("game countries must be a non-empty object")
    for country_id, country in countries.items():
        if not isinstance(country_id, str) or _ID_RE.fullmatch(country_id) is None or not isinstance(country, dict):
            raise ValueError("invalid game country entry")
        if country.get("country_id") != country_id or not isinstance(country.get("name"), str):
            raise ValueError("game country identity mismatch")
        for field in (
            "economy",
            "military",
            "stability",
            "influence",
            "reputation",
            "territory",
            "sanctions",
            "arms_imports",
            "meme_heat",
        ):
            if type(country.get(field)) is not int or country[field] < 0:
                raise ValueError(f"country field {field} must be a non-negative exact integer")
        if type(country.get("suspended")) is not bool:
            raise ValueError("country suspended must be boolean")
    if not isinstance(wars, list):
        raise ValueError("game wars must be a list")
    for war in wars:
        if not isinstance(war, dict) or war.get("a") not in countries or war.get("b") not in countries:
            raise ValueError("invalid game war entry")
        if war["a"] >= war["b"]:
            raise ValueError("war country ids must be canonically ordered")
        for field in ("score_a", "score_b", "started_turn"):
            if type(war.get(field)) is not int or war[field] < 0:
                raise ValueError(f"war field {field} must be a non-negative exact integer")


def _targets(state: dict[str, Any], raw_targets: list[str]) -> list[str]:
    clean: list[str] = []
    for raw in raw_targets:
        if not isinstance(raw, str):
            raise ValueError("game targets must be strings")
        country_id = raw.strip().lower()
        if country_id not in state["countries"]:
            raise ValueError(f"unknown fictional country: {raw}")
        if country_id not in clean:
            clean.append(country_id)
    return clean


def _find_war(state: dict[str, Any], a: str, b: str) -> dict[str, Any] | None:
    left, right = sorted((a, b))
    return next((war for war in state["wars"] if war["a"] == left and war["b"] == right), None)


def _at_war(state: dict[str, Any], country_id: str) -> bool:
    return any(country_id in (war["a"], war["b"]) for war in state["wars"])


def _event(state: dict[str, Any], kind: str, text: str, **extra: Any) -> None:
    state["event_log"].append({"turn": state["turn"], "kind": kind, "text": text, **extra})
    state["event_log"] = state["event_log"][-MAX_EVENT_LOG:]


def _persist(world: WorldStore, previous_ref: str, state: dict[str, Any], transition: dict[str, Any]) -> WorldObject:
    state["previous_state_ref"] = previous_ref
    state["last_transition"] = transition
    state["world_tension"] = _bounded(state["world_tension"], 0, 20)
    state["un_legitimacy"] = _bounded(state["un_legitimacy"], 0, 10)
    state["content"] = _board_content(state)
    _validate_state(state)
    return world.create_object(
        "un_sim_game_state",
        state,
        {
            "actor": "nexus_game_engine",
            "previous_state_ref": previous_ref,
            "transition": canonical_json(transition),
        },
    )


def apply_action(world: WorldStore, game_ref: str, action: str, targets: list[str] | None = None) -> WorldObject:
    obj = inspect_game(world, game_ref)
    state = copy.deepcopy(obj.payload)
    if not isinstance(action, str):
        raise ValueError("game action must be text")
    action_id = action.strip().lower()
    if action_id not in ACTIONS:
        raise ValueError(f"unknown UN simulation action: {action}")
    target_ids = _targets(state, list(targets or []))
    rule = ACTIONS[action_id]["targets"]
    if rule == "none" and target_ids:
        raise ValueError(f"{action_id} does not accept targets")
    if rule == "exactly_two" and len(target_ids) != 2:
        raise ValueError(f"{action_id} requires exactly two fictional country ids")
    if rule == "one_or_more" and not target_ids:
        raise ValueError(f"{action_id} requires at least one fictional country id")

    countries = state["countries"]
    transition: dict[str, Any] = {"kind": "action", "action": action_id, "targets": target_ids}

    if action_id == "sanction":
        for country_id in target_ids:
            country = countries[country_id]
            country["economy"] = _bounded(country["economy"] - 1)
            country["stability"] = _bounded(country["stability"] - 1)
            country["sanctions"] += 1
            state["world_tension"] += 1
            _event(state, "sanction", f"The Assembly sanctioned {country['name']}.", country_id=country_id)
    elif action_id == "support":
        for country_id in target_ids:
            country = countries[country_id]
            country["economy"] = _bounded(country["economy"] + 1)
            country["influence"] = _bounded(country["influence"] + 1)
            if _at_war(state, country_id):
                state["world_tension"] += 1
            _event(state, "support", f"The Assembly backed {country['name']} with political/economic support.", country_id=country_id)
    elif action_id == "aid":
        for country_id in target_ids:
            country = countries[country_id]
            country["economy"] = _bounded(country["economy"] + 1)
            country["stability"] = _bounded(country["stability"] + 1)
            state["un_legitimacy"] += 1
            _event(state, "aid", f"Humanitarian aid reached {country['name']}.", country_id=country_id)
    elif action_id == "arms":
        selected = set(target_ids)
        opposing_pair = any({war["a"], war["b"]}.issubset(selected) for war in state["wars"])
        for country_id in target_ids:
            country = countries[country_id]
            country["military"] = _bounded(country["military"] + 1)
            country["economy"] = _bounded(country["economy"] - 1)
            country["arms_imports"] += 1
            state["world_tension"] += 2
            _event(state, "arms_trade", f"An abstract arms package was sold to {country['name']}. The spreadsheet is delighted.", country_id=country_id)
        if opposing_pair:
            state["un_legitimacy"] -= 1
            _event(state, "arms_hypocrisy", "The Assembly armed both sides of the same war. Editorial cartoons write themselves.")
    elif action_id == "meme":
        for country_id in target_ids:
            country = countries[country_id]
            roll = _digest_int(game_ref, state["turn"], action_id, country_id, country["meme_heat"]) % 100
            country["meme_heat"] += 1
            state["world_tension"] += 1
            if roll < 35:
                country["reputation"] = _bounded(country["reputation"] + 1)
                state["un_legitimacy"] -= 1
                _event(state, "meme_backfire", f"The meme campaign against {country['name']} backfired spectacularly.", country_id=country_id, roll=roll)
            else:
                country["reputation"] = _bounded(country["reputation"] - 1)
                _event(state, "meme_hit", f"The Assembly's meme campaign landed against {country['name']}.", country_id=country_id, roll=roll)
    elif action_id == "suspend":
        for country_id in target_ids:
            country = countries[country_id]
            if country["suspended"]:
                _event(state, "suspension_unchanged", f"{country['name']} was already suspended. The motion achieved paperwork.", country_id=country_id)
                continue
            country["suspended"] = True
            country["influence"] = _bounded(country["influence"] - 2)
            state["world_tension"] += 1
            _event(state, "suspension", f"{country['name']} was suspended from the Assembly.", country_id=country_id)
    elif action_id == "reinstate":
        for country_id in target_ids:
            country = countries[country_id]
            if not country["suspended"]:
                _event(state, "reinstatement_unchanged", f"{country['name']} was already in the Assembly. A committee nevertheless took credit.", country_id=country_id)
                continue
            country["suspended"] = False
            country["influence"] = _bounded(country["influence"] + 1)
            _event(state, "reinstatement", f"{country['name']} was reinstated to the Assembly.", country_id=country_id)
    elif action_id == "recognize":
        for country_id in target_ids:
            country = countries[country_id]
            country["influence"] = _bounded(country["influence"] + 1)
            country["reputation"] = _bounded(country["reputation"] + 1)
            _event(state, "recognition", f"The Assembly formally recognized {country['name']}'s latest diplomatic fiction.", country_id=country_id)
    elif action_id == "mediate":
        a, b = sorted(target_ids)
        war = _find_war(state, a, b)
        if war is None:
            raise ValueError("mediate targets must currently be at war with each other")
        threshold = min(85, 35 + state["un_legitimacy"] * 5)
        roll = _digest_int(game_ref, state["turn"], "mediate", a, b) % 100
        transition.update({"roll": roll, "success_threshold": threshold})
        if roll < threshold:
            state["wars"].remove(war)
            state["world_tension"] -= 3
            countries[a]["reputation"] = _bounded(countries[a]["reputation"] + 1)
            countries[b]["reputation"] = _bounded(countries[b]["reputation"] + 1)
            _event(state, "ceasefire", f"Mediation produced a ceasefire between {countries[a]['name']} and {countries[b]['name']}.", roll=roll)
        else:
            state["world_tension"] += 1
            _event(state, "mediation_failed", f"Mediation failed between {countries[a]['name']} and {countries[b]['name']}. Everyone blamed the chair.", roll=roll)
    elif action_id == "do_nothing":
        state["world_tension"] += 1
        _event(state, "inaction", "The Assembly did nothing. A strongly worded draft statement is rumored to exist.")

    return _persist(world, game_ref, state, transition)


def advance_turn(world: WorldStore, game_ref: str) -> WorldObject:
    obj = inspect_game(world, game_ref)
    state = copy.deepcopy(obj.payload)
    state["turn"] += 1
    countries = state["countries"]
    surviving: list[dict[str, Any]] = []

    for war in sorted(state["wars"], key=lambda item: (item["a"], item["b"])):
        a, b = war["a"], war["b"]
        country_a, country_b = countries[a], countries[b]
        roll_a = _digest_int(game_ref, state["turn"], "war", a) % 20
        roll_b = _digest_int(game_ref, state["turn"], "war", b) % 20
        power_a = country_a["military"] * 10 + country_a["stability"] * 3 + roll_a
        power_b = country_b["military"] * 10 + country_b["stability"] * 3 + roll_b
        if power_a > power_b or (power_a == power_b and a < b):
            winner, loser = a, b
        else:
            winner, loser = b, a

        winner_country, loser_country = countries[winner], countries[loser]
        winner_country["influence"] = _bounded(winner_country["influence"] + 1)
        loser_country["economy"] = _bounded(loser_country["economy"] - 1)
        loser_country["stability"] = _bounded(loser_country["stability"] - 1)
        war["score_a" if winner == a else "score_b"] += 1
        state["world_tension"] += 1
        _event(state, "war_round", f"{winner_country['name']} gained the advantage over {loser_country['name']} this turn.", winner=winner, loser=loser, roll_a=roll_a, roll_b=roll_b)

        if abs(war["score_a"] - war["score_b"]) >= 2 and loser_country["territory"] > 1:
            loser_country["territory"] -= 1
            winner_country["territory"] += 1
            war["score_a"] = 0
            war["score_b"] = 0
            _event(state, "territory_shift", f"One abstract territory point shifted from {loser_country['name']} to {winner_country['name']}.")

        if loser_country["economy"] <= 1 or loser_country["stability"] <= 1:
            state["world_tension"] -= 2
            _event(state, "war_exhaustion", f"War exhaustion forced an armistice between {country_a['name']} and {country_b['name']}.")
        else:
            surviving.append(war)

    state["wars"] = surviving
    _apply_turn_event(state, game_ref)
    return _persist(world, game_ref, state, {"kind": "advance_turn", "turn": state["turn"]})


def _apply_turn_event(state: dict[str, Any], game_ref: str) -> None:
    countries = state["countries"]
    country_ids = sorted(countries)
    country_id = country_ids[_digest_int(game_ref, state["turn"], "event-country") % len(country_ids)]
    country = countries[country_id]
    event_kind = _digest_int(game_ref, state["turn"], "event-kind") % 5

    if event_kind == 0:
        country["economy"] = _bounded(country["economy"] + 1)
        _event(state, "commodity_boom", f"A suspiciously convenient commodity boom helped {country['name']}.", country_id=country_id)
    elif event_kind == 1:
        country["reputation"] = _bounded(country["reputation"] - 1)
        country["meme_heat"] += 1
        _event(state, "cable_leak", f"A diplomatic cable leaked from {country['name']}. The screenshots are already memes.", country_id=country_id)
    elif event_kind == 2:
        state["world_tension"] -= 1
        country["stability"] = _bounded(country["stability"] + 1)
        _event(state, "peace_march", f"A mass peace march in {country['name']} lowered the temperature slightly.", country_id=country_id)
    elif event_kind == 3:
        country["meme_heat"] += 2
        country["reputation"] = _bounded(country["reputation"] - 1)
        _event(state, "meme_scandal", f"A minister from {country['name']} posted through it. This was a mistake.", country_id=country_id)
    else:
        state["world_tension"] += 1
        _event(state, "border_rumor", f"Unverified border rumors involving {country['name']} raised world tension. The Assembly demands receipts.", country_id=country_id)
