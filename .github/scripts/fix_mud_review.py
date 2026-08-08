from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Rust parser: proxy movement aliases must normalize to the engine's `go`.
# ---------------------------------------------------------------------------
path = "tui/src/lib.rs"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    '''fn normalize_mud_action(action: &str) -> String {
    match action.to_ascii_lowercase().as_str() {
        "get" => "take".to_string(),
        other => other.to_string(),
    }
}
''',
    '''fn normalize_mud_action(action: &str) -> String {
    match action.to_ascii_lowercase().as_str() {
        "get" => "take".to_string(),
        "n" | "s" | "e" | "w" | "north" | "south" | "east" | "west" => "go".to_string(),
        other => other.to_string(),
    }
}
''',
    "normalize proxy movement aliases",
)
write(path, text)

path = "tui/tests/mud.rs"
text = Path(path).read_text(encoding="utf-8")
anchor = '''    assert_eq!(
        parse_input("/mud as Grok attack yaml_necromancer large_trout").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: Some("Grok".to_string()),
            action: "attack".to_string(),
            args: vec!["yaml_necromancer".to_string(), "large_trout".to_string()],
        })
    );
'''
addition = anchor + '''    assert_eq!(
        parse_input("/mud as Grok n").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: Some("Grok".to_string()),
            action: "go".to_string(),
            args: vec!["n".to_string()],
        })
    );
'''
text = replace_once(text, anchor, addition, "proxy direction regression")
write(path, text)

# ---------------------------------------------------------------------------
# Python MUD engine: one-time item score, death drops, and accurate quest state.
# ---------------------------------------------------------------------------
path = "src/nexus_runtime/game_mud.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    '''            "score": spec["score"],
            "location": deepcopy(spec["initial_location"]),
''',
    '''            "score": spec["score"],
            "score_awarded": False,
            "location": deepcopy(spec["initial_location"]),
''',
    "item score award state",
)
text = replace_once(
    text,
    '''        for field in ("item_id", "name", "description", "kind", "power", "score"):
            if item.get(field) != spec[field]:
                raise ValueError(f"cursed MUD item immutable field mismatch: {item_id}.{field}")
        location = item.get("location")
''',
    '''        for field in ("item_id", "name", "description", "kind", "power", "score"):
            if item.get(field) != spec[field]:
                raise ValueError(f"cursed MUD item immutable field mismatch: {item_id}.{field}")
        if type(item.get("score_awarded")) is not bool:
            raise ValueError(f"cursed MUD item score_awarded must be boolean: {item_id}")
        location = item.get("location")
''',
    "validate item score award state",
)
text = replace_once(
    text,
    '''def _drop_npc_items(state: dict[str, Any], npc_id: str, room_id: str) -> None:
    for item in state["items"].values():
        if item["location"] == {"kind": "npc", "id": npc_id}:
            item["location"] = {"kind": "room", "id": room_id}
            _event(state, "drop", f"{item['name']} drops into {state['rooms'][room_id]['name']}.", item_id=item["item_id"])


def _retaliate''',
    '''def _drop_npc_items(state: dict[str, Any], npc_id: str, room_id: str) -> None:
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


def _retaliate''',
    "death inventory drop helper",
)
text = replace_once(
    text,
    '''    if not player["alive"]:
        _event(state, "defeat", f"{player['player_id']} has been defeated by legacy infrastructure.")
''',
    '''    if not player["alive"]:
        _drop_player_items(state, player["player_id"], player["room_id"])
        _event(state, "defeat", f"{player['player_id']} has been defeated by legacy infrastructure; inventory dropped into the room.")
''',
    "drop inventory on defeat",
)
text = replace_once(
    text,
    '''        item["location"] = {"kind": "player", "id": player_id}
        player["score"] += item["score"]
        _event(state, "take", f"{player_id} takes {item['name']}.", player_id=player_id, item_id=item_id)
''',
    '''        if item_id == "zero_dependency_crown" and state["npcs"]["dependency_dragon"]["alive"]:
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
''',
    "one-time item score and crown completion",
)
text = replace_once(
    text,
    '''            if npc_id == "dependency_dragon":
                state["quest"]["status"] = "complete"
                state["quest"]["completed_by"] = player_id
                player["clout"] += 10
                _event(state, "quest_complete", f"{player_id} has defeated the Dependency Dragon. Small is beautiful; bloat is unholy.")
''',
    '''            if npc_id == "dependency_dragon":
                _event(
                    state,
                    "quest_progress",
                    f"{player_id} defeats the Dependency Dragon. The Zero-Dependency Crown drops and must still be recovered.",
                    player_id=player_id,
                )
''',
    "attack dragon quest progress",
)
text = replace_once(
    text,
    '''                if npc_id == "dependency_dragon":
                    state["quest"]["status"] = "complete"
                    state["quest"]["completed_by"] = player_id
                    player["clout"] += 10
                    _event(state, "quest_complete", f"{player_id} ratioed the Dependency Dragon out of production.")
''',
    '''                if npc_id == "dependency_dragon":
                    _event(
                        state,
                        "quest_progress",
                        f"{player_id} shitposts the Dependency Dragon out of production. The Zero-Dependency Crown drops and must still be recovered.",
                        player_id=player_id,
                    )
''',
    "shitpost dragon event accuracy",
)
text = replace_once(
    text,
    '''                if npc_id == "dependency_dragon":
                    state["quest"]["status"] = "complete"
                    state["quest"]["completed_by"] = player_id
                    player["clout"] += 10
                    _event(state, "quest_complete", f"{player_id} has ratioed the Dependency Dragon into a single static binary.")
''',
    '''                if npc_id == "dependency_dragon":
                    _event(
                        state,
                        "quest_progress",
                        f"{player_id} ratios the Dependency Dragon into a single static binary. The Zero-Dependency Crown drops and must still be recovered.",
                        player_id=player_id,
                    )
''',
    "ratio dragon quest progress",
)
write(path, text)

# ---------------------------------------------------------------------------
# Python regression tests.
# ---------------------------------------------------------------------------
path = "tests/test_mud.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    'from nexus_runtime.game_mud import MUD_SCHEMA, apply_action, inspect_mud, new_mud, player_view\n',
    'from nexus_runtime.game_mud import MUD_SCHEMA, _board_content, apply_action, inspect_mud, new_mud, player_view\n',
    "test board helper import",
)
anchor = '''    def test_same_state_same_combat_action_is_content_address_identical(self) -> None:
'''
new_tests = '''    def test_item_score_is_awarded_only_once_across_drop_and_transfer(self) -> None:
        game = new_mud(self.world, "trout-economy", ["Trent", "Grok"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        game = apply_action(self.world, game.object_id, "Grok", "go", ["east"])
        game = apply_action(self.world, game.object_id, "Trent", "take", ["large_trout"])
        self.assertEqual(game.payload["players"]["Trent"]["score"], 1)
        self.assertTrue(game.payload["items"]["large_trout"]["score_awarded"])
        game = apply_action(self.world, game.object_id, "Trent", "drop", ["large_trout"])
        game = apply_action(self.world, game.object_id, "Grok", "take", ["large_trout"])
        self.assertEqual(game.payload["players"]["Trent"]["score"], 1)
        self.assertEqual(game.payload["players"]["Grok"]["score"], 0)

    def test_defeated_avatar_drops_unique_inventory_into_current_room(self) -> None:
        game = new_mud(self.world, "death-drop", ["Trent", "Grok"])
        payload = deepcopy(game.payload)
        payload["players"]["Trent"]["room_id"] = "dependency_cache"
        payload["players"]["Trent"]["hp"] = 1
        payload["items"]["punch_card"]["location"] = {"kind": "player", "id": "Trent"}
        payload["content"] = _board_content(payload)
        fixture = self.world.create_object("mud_game_state", payload, {"actor": "test_fixture"})
        defeated = apply_action(self.world, fixture.object_id, "Trent", "attack", ["dependency_dragon"])
        self.assertFalse(defeated.payload["players"]["Trent"]["alive"])
        self.assertEqual(
            defeated.payload["items"]["punch_card"]["location"],
            {"kind": "room", "id": "dependency_cache"},
        )

    def test_dragon_defeat_is_progress_until_crown_is_recovered(self) -> None:
        game = new_mud(self.world, "crown-objective", ["Trent"])
        payload = deepcopy(game.payload)
        payload["players"]["Trent"]["room_id"] = "dependency_cache"
        payload["items"]["punch_card"]["location"] = {"kind": "player", "id": "Trent"}
        payload["npcs"]["dependency_dragon"]["hp"] = 1
        payload["content"] = _board_content(payload)
        fixture = self.world.create_object("mud_game_state", payload, {"actor": "test_fixture"})
        defeated = apply_action(self.world, fixture.object_id, "Trent", "attack", ["dependency_dragon"])
        self.assertEqual(defeated.payload["quest"]["status"], "open")
        self.assertIsNone(defeated.payload["quest"]["completed_by"])
        self.assertEqual(
            defeated.payload["items"]["zero_dependency_crown"]["location"],
            {"kind": "room", "id": "dependency_cache"},
        )
        recovered = apply_action(self.world, defeated.object_id, "Trent", "take", ["zero_dependency_crown"])
        self.assertEqual(recovered.payload["quest"]["status"], "complete")
        self.assertEqual(recovered.payload["quest"]["completed_by"], "Trent")
        self.assertEqual(recovered.payload["players"]["Trent"]["clout"], 10)

    def test_shitpost_dragon_defeat_event_reports_shitpost_not_ratio(self) -> None:
        game = new_mud(self.world, "shitpost-dragon", ["Trent"])
        payload = deepcopy(game.payload)
        payload["players"]["Trent"]["room_id"] = "dependency_cache"
        payload["items"]["punch_card"]["location"] = {"kind": "player", "id": "Trent"}
        payload["npcs"]["dependency_dragon"]["hp"] = 1
        payload["content"] = _board_content(payload)
        fixture = self.world.create_object("mud_game_state", payload, {"actor": "test_fixture"})
        result = apply_action(self.world, fixture.object_id, "Trent", "shitpost", ["dependency_dragon"])
        progress = [event for event in result.payload["event_log"] if event["kind"] == "quest_progress"]
        self.assertTrue(progress)
        self.assertIn("shitposts", progress[-1]["text"])
        self.assertNotIn("ratioed", progress[-1]["text"])

'''
text = replace_once(text, anchor, new_tests + anchor, "MUD exploit regressions")
write(path, text)

# ---------------------------------------------------------------------------
# Public docs: protocol/runtime/geometry and MUD operation surface.
# ---------------------------------------------------------------------------
path = "README.md"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(text, '- the first explicit game room: **`#un-sim`**.\n', '- explicit game rooms: **`#un-sim`** and the cursed multi-avatar **`#mud`**.\n', "README game status")
text = replace_once(text, 'protocol: nexus/0.6\nruntime version: 2.0.0-alpha6.2', 'protocol: nexus/0.7\nruntime version: 2.0.0-alpha6.3', "README protocol versions")
text = replace_once(text, 'world modes: analytical / historical / cultural / meme_casual / game_un\ngeometry: named-regions-v2\nfirst game room: #un-sim / Assembly Hall', 'world modes: analytical / historical / cultural / meme_casual / game_un / game_mud\ngeometry: named-regions-v3\ngame rooms: #un-sim / Assembly Hall + #mud / Dungeon', "README modes geometry")
text = replace_once(text, '            | /game               |', '            | /game + /mud        |', "README TUI commands")
text = replace_once(
    text,
    'See [`docs/UN_SIM.md`](docs/UN_SIM.md).\n\n## What is deliberately not here yet',
    '''See [`docs/UN_SIM.md`](docs/UN_SIM.md).

## `#mud` — HERESY MUD

The second explicit game room is a deterministic multi-avatar dungeon built from old BBS/MUD interaction grammar plus DORK/HERESY satire:

```text
/join #mud
/mud new beige-night
/mud n
/mud take large_trout
/mud as Grok shitpost yaml_necromancer
```

The human operator and current model roster become avatars in one immutable shared dungeon state. Models may narrate and advise, but only validated `/mud` / `game.mud.*` operations mutate the substrate. Item discovery score is awarded once per item, defeated avatars drop inventory into their room, and the final quest completes only when the Zero-Dependency Crown is actually recovered after the Dependency Dragon falls.

See [`docs/MUD.md`](docs/MUD.md).

## What is deliberately not here yet''',
    "README MUD section",
)
text = replace_once(text, '- [`docs/UN_SIM.md`](docs/UN_SIM.md) — fictional UN simulation game contract\n', '- [`docs/UN_SIM.md`](docs/UN_SIM.md) — fictional UN simulation game contract\n- [`docs/MUD.md`](docs/MUD.md) — HERESY MUD deterministic multi-avatar dungeon contract\n', "README MUD docs map") if '- [`docs/UN_SIM.md`](docs/UN_SIM.md) — fictional UN simulation game contract\n' in text else text
write(path, text)

path = "docs/API.md"
text = Path(path).read_text(encoding="utf-8")
text = text.replace("nexus/0.6", "nexus/0.7")
text = text.replace("2.0.0-alpha6.2", "2.0.0-alpha6.3")
text = text.replace("named-regions-v2", "named-regions-v3")
text = replace_once(text, 'UN simulation     -> supported as a deterministic fictional local game\n', 'UN simulation     -> supported as a deterministic fictional local game\nHERESY MUD        -> supported as a deterministic fictional multi-avatar local game\n', "API posture MUD")
text = replace_once(
    text,
    '''    {
      "game_id": "un_sim",
      "schema": "nexus-un-sim/1",
      "room": "#un-sim",
      "fictional_only": true
    }
''',
    '''    {
      "game_id": "un_sim",
      "schema": "nexus-un-sim/1",
      "room": "#un-sim",
      "fictional_only": true
    },
    {
      "game_id": "mud",
      "schema": "nexus-cursed-mud/1",
      "room": "#mud",
      "fictional_only": true
    }
''',
    "API health MUD registry",
)
text = replace_once(text, 'game.un.turn\nactor.chat', 'game.un.turn\ngame.mud.catalog\ngame.mud.new\ngame.mud.inspect\ngame.mud.act\nactor.chat', "API MUD operations list")
text = replace_once(
    text,
    'See [`UN_SIM.md`](UN_SIM.md).\n\n## World modes',
    '''See [`UN_SIM.md`](UN_SIM.md).

## HERESY MUD

The local protocol exposes the deterministic multi-avatar `#mud` engine:

```text
game.mud.catalog
game.mud.new
game.mud.inspect
game.mud.act
```

Create one shared dungeon state:

```json
{"operation":"game.mud.new","seed":"beige-night","players":["Trent","Alpha","Grok"]}
```

Inspect a player's current view:

```json
{"operation":"game.mud.inspect","mud_ref":"object:<sha256>","player_id":"Trent"}
```

Apply an authoritative action:

```json
{"operation":"game.mud.act","mud_ref":"object:<sha256>","player_id":"Grok","action":"go","args":["north"]}
```

Movement, loot, combat, `shitpost`, and `ratio` transitions are deterministic and content-addressed. Narration never mutates the dungeon. Item score is a one-time acquisition award, defeated avatars drop held items into their current room, and defeating the Dependency Dragon only drops the Crown; the quest becomes complete when a player subsequently takes `zero_dependency_crown`.

See [`MUD.md`](MUD.md).

## World modes''',
    "API MUD section",
)
text = replace_once(text, 'game_un     -> Assembly Hall / #un-sim\n', 'game_un     -> Assembly Hall / #un-sim\ngame_mud    -> Dungeon / #mud\n', "API game_mud mode")
text = replace_once(text, 'It includes the Assembly Hall used by `game_un`.', 'It includes the Assembly Hall used by `game_un` and the Dungeon region used by `game_mud`.', "API geometry regions")
text = replace_once(text, 'Alpha5 additionally derives a bounded, labelled model-readable view from those refs so actors can actually read attached document material. Alpha6.2 reuses that same generic mechanism for the compact current `#un-sim` board view.', 'Alpha5 additionally derives a bounded, labelled model-readable view from those refs so actors can actually read attached document material. Alpha6.3 reuses that same generic mechanism for the compact current `#un-sim` board and `#mud` dungeon views.', "API bounded evidence games")
write(path, text)

path = "docs/MODES_GEOMETRY.md"
text = Path(path).read_text(encoding="utf-8")
old_map = '''```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \\
                       /        \\
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \\             /   |
                       \\           /    |
                        COMMONS ----+    |
                      Meme/Casual    \\   |
                         (2,1)        \\  |
                                    ASSEMBLY HALL
                                    UN Simulation
                                       (0,-2)
```
'''
new_map = '''```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \\
                       /        \\
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \\             /  |  \\
                       \\           /   |   \\
                        COMMONS ----+   |   DUNGEON
                      Meme/Casual       |   HERESY MUD
                         (2,1)           |     (2,-2)
                            \\           |      /
                             \\          |     /
                              ASSEMBLY HALL ---+
                               UN Simulation
                                  (0,-2)
```
'''
text = replace_once(text, old_map, new_map, "geometry map dungeon")
text = replace_once(
    text,
    'All countries, wars, territory values and arms packages are fictional game objects. See [`UN_SIM.md`](UN_SIM.md).\n\n## Why runtime modes',
    '''All countries, wars, territory values and arms packages are fictional game objects. See [`UN_SIM.md`](UN_SIM.md).

### Cursed MUD — Dungeon

`game_mud` situates HERESY MUD in the NEXUS `dungeon` region. The MUD's internal room graph is a separate game topology contained inside the current content-addressed `mud_game_state`.

Actors may role-play avatars, propose moves, joke, shitpost or discuss tactics, but only explicit validated `/mud` / `game.mud.*` operations change authoritative dungeon state.

```text
Council/model output -> narration, proposals and role-play
/mud operation        -> authoritative MUD-state transition
```

See [`MUD.md`](MUD.md).

## Why runtime modes''',
    "geometry MUD mode section",
)
text = text.replace("named-regions-v2", "named-regions-v3")
write(path, text)

path = "docs/MUD.md"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(text, 'Items have exactly one authoritative location at a time: room, player, NPC, or consumed.\n', 'Items have exactly one authoritative location at a time: room, player, NPC, or consumed. Item score is awarded only on the first acquisition globally; dropping or transferring an already-discovered item cannot mint additional score.\n', "MUD scoring docs")
text = replace_once(text, 'Attacking a non-hostile NPC costs clout. Hostile surviving NPCs may retaliate.\n', 'Attacking a non-hostile NPC costs clout. Hostile surviving NPCs may retaliate. A defeated avatar drops all held inventory into its current room, preventing unique quest items from being permanently stranded on an unusable avatar.\n\nDefeating the Dependency Dragon drops the Zero-Dependency Crown but does **not** complete the quest. The quest completes only when an avatar subsequently takes the Crown.\n', "MUD defeat and crown docs")
write(path, text)

print("Applied all Copilot MUD review fixes.")
