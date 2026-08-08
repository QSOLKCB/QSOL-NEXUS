from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


# modes.py
path = "src/nexus_runtime/modes.py"
text = Path(path).read_text(encoding="utf-8")
insert = '''    "game_mud": WorldMode(
        mode_id="game_mud",
        label="Cursed MUD",
        description="Multi-avatar fictional dungeon crawling through BBS, DORK and HERESY-inspired software ruins.",
        prompt_instruction=(
            "You are participating in HERESY MUD, a fictional multi-user dungeon made from obsolete-computing and "
            "software-architecture satire. The current MUD state is shared evidence, not a suggestion. You may role-play, "
            "advise avatars, joke, shitpost and propose moves, but narration never mutates the dungeon. Only explicit "
            "validated game.mud operations change authoritative state. Combat, clout, loot and rooms are game tokens only."
        ),
        region_id="dungeon",
    ),
'''
text = replace_once(text, "}\n\n\ndef get_mode", insert + "}\n\n\ndef get_mode", "insert game_mud mode")
write(path, text)

# geometry.py
path = "src/nexus_runtime/geometry.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    '("archive", "agora", "commons", "assembly"),',
    '("archive", "agora", "commons", "assembly", "dungeon"),',
    "observatory dungeon adjacency",
)
text = replace_once(
    text,
    '("observatory", "agora", "assembly"),',
    '("observatory", "agora", "assembly", "dungeon"),',
    "commons dungeon adjacency",
)
text = replace_once(
    text,
    '("observatory", "commons"),\n            "Fictional game region for UN-style strategy simulation, motions, crises and memes.",',
    '("observatory", "commons", "dungeon"),\n            "Fictional game region for UN-style strategy simulation, motions, crises and memes.",',
    "assembly dungeon adjacency",
)
assembly_tail = '''        WorldRegion(
            "assembly",
            "Assembly Hall",
            0,
            -2,
            ("observatory", "commons", "dungeon"),
            "Fictional game region for UN-style strategy simulation, motions, crises and memes.",
        ),
    ),
    geometry_id="named-regions-v2",
)
'''
dungeon_tail = '''        WorldRegion(
            "assembly",
            "Assembly Hall",
            0,
            -2,
            ("observatory", "commons", "dungeon"),
            "Fictional game region for UN-style strategy simulation, motions, crises and memes.",
        ),
        WorldRegion(
            "dungeon",
            "Dungeon",
            2,
            -2,
            ("observatory", "commons", "assembly"),
            "Fictional MUD region containing a separate internal room graph owned by the game substrate.",
        ),
    ),
    geometry_id="named-regions-v3",
)
'''
text = replace_once(text, assembly_tail, dungeon_tail, "insert dungeon region")
write(path, text)

# api.py
path = "src/nexus_runtime/api.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    "from .game_un import GAME_SCHEMA, action_catalog, advance_turn, apply_action, inspect_game, new_game\n",
    "from .game_un import GAME_SCHEMA, action_catalog, advance_turn, apply_action, inspect_game, new_game\n"
    "from .game_mud import (\n"
    "    MUD_SCHEMA,\n"
    "    action_catalog as mud_action_catalog,\n"
    "    apply_action as apply_mud_action,\n"
    "    inspect_mud,\n"
    "    new_mud,\n"
    "    player_view,\n"
    ")\n",
    "import MUD runtime",
)
text = replace_once(text, 'PROTOCOL_VERSION = "nexus/0.6"', 'PROTOCOL_VERSION = "nexus/0.7"', "protocol bump")
text = replace_once(text, 'RUNTIME_VERSION = "2.0.0-alpha6.2"', 'RUNTIME_VERSION = "2.0.0-alpha6.3"', "runtime bump")
old_games = '                    "games": [{"game_id": "un_sim", "schema": GAME_SCHEMA, "room": "#un-sim", "fictional_only": True}],\n'
new_games = '''                    "games": [
                        {"game_id": "un_sim", "schema": GAME_SCHEMA, "room": "#un-sim", "fictional_only": True},
                        {"game_id": "mud", "schema": MUD_SCHEMA, "room": "#mud", "fictional_only": True},
                    ],
'''
text = replace_once(text, old_games, new_games, "health game registry")
text = replace_once(
    text,
    '                        "game.un.turn",\n                        "actor.chat",',
    '                        "game.un.turn",\n'
    '                        "game.mud.catalog",\n'
    '                        "game.mud.new",\n'
    '                        "game.mud.inspect",\n'
    '                        "game.mud.act",\n'
    '                        "actor.chat",',
    "MUD operations",
)
handler_anchor = '''            elif operation == "game.un.turn":
                game_ref = self._require_str(request, "game_ref")
                game = advance_turn(self.world, game_ref)
                response = {"status": "ok", "game_ref": game.object_id, "game": game.payload}
            elif operation == "actor.chat":
'''
mud_handlers = '''            elif operation == "game.un.turn":
                game_ref = self._require_str(request, "game_ref")
                game = advance_turn(self.world, game_ref)
                response = {"status": "ok", "game_ref": game.object_id, "game": game.payload}
            elif operation == "game.mud.catalog":
                response = {
                    "status": "ok",
                    "schema": MUD_SCHEMA,
                    "fictional_only": True,
                    "actions": mud_action_catalog(),
                }
            elif operation == "game.mud.new":
                raw_seed = request.get("seed", "beige-dungeon")
                if not isinstance(raw_seed, str) or not raw_seed.strip():
                    raise ValueError("seed must be non-empty text")
                players = request.get("players", ["operator"])
                if not isinstance(players, list) or not players or not all(isinstance(player, str) for player in players):
                    raise ValueError("players must be a non-empty list of MUD player ids")
                scrubbed = self.scrubber.scrub(raw_seed)
                mud = new_mud(self.world, scrubbed.text, list(players))
                first_player = next(iter(mud.payload["players"]))
                response = {
                    "status": "ok",
                    "mud_ref": mud.object_id,
                    "mud": mud.payload,
                    "player_id": first_player,
                    "view": player_view(mud.payload, first_player),
                    "secret_scrub": {
                        "changed": scrubbed.changed,
                        "events": [asdict(event) for event in scrubbed.events],
                    },
                }
            elif operation == "game.mud.inspect":
                mud_ref = self._require_str(request, "mud_ref")
                mud = inspect_mud(self.world, mud_ref)
                player_id = request.get("player_id")
                if player_id is None:
                    response = {"status": "ok", "mud_ref": mud.object_id, "mud": mud.payload}
                else:
                    if not isinstance(player_id, str) or not player_id:
                        raise ValueError("player_id must be a non-empty string")
                    response = {
                        "status": "ok",
                        "mud_ref": mud.object_id,
                        "mud": mud.payload,
                        "player_id": player_id,
                        "view": player_view(mud.payload, player_id),
                    }
            elif operation == "game.mud.act":
                mud_ref = self._require_str(request, "mud_ref")
                player_id = self._require_str(request, "player_id")
                action = self._require_str(request, "action")
                args = request.get("args", [])
                if not isinstance(args, list) or not all(isinstance(arg, str) and arg for arg in args):
                    raise ValueError("args must be a list of non-empty strings")
                mud = apply_mud_action(self.world, mud_ref, player_id, action, list(args))
                response = {
                    "status": "ok",
                    "mud_ref": mud.object_id,
                    "mud": mud.payload,
                    "player_id": player_id,
                    "view": player_view(mud.payload, player_id),
                }
            elif operation == "actor.chat":
'''
text = replace_once(text, handler_anchor, mud_handlers, "MUD API handlers")
write(path, text)

# tests/test_modes_geometry.py
path = "tests/test_modes_geometry.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    '("archive", "agora", "commons", "assembly"),',
    '("archive", "agora", "commons", "assembly", "dungeon"),',
    "fixture observatory neighbors",
)
text = replace_once(
    text,
    'WorldRegion("commons", "Commons", 2, 1, ("observatory", "agora", "assembly"), "Playful region."),\n        WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory", "commons"), "Game region."),',
    'WorldRegion("commons", "Commons", 2, 1, ("observatory", "agora", "assembly", "dungeon"), "Playful region."),\n'
    '        WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory", "commons", "dungeon"), "Game region."),\n'
    '        WorldRegion("dungeon", "Dungeon", 2, -2, ("observatory", "commons", "assembly"), "MUD region."),',
    "fixture dungeon region",
)
text = text.replace('{"analytical", "historical", "cultural", "meme_casual", "game_un"}', '{"analytical", "historical", "cultural", "meme_casual", "game_un", "game_mud"}')
text = replace_once(text, 'self.assertEqual(get_mode("game_un").region_id, "assembly")', 'self.assertEqual(get_mode("game_un").region_id, "assembly")\n        self.assertEqual(get_mode("game_mud").region_id, "dungeon")', "mode registry dungeon")
text = text.replace('"named-regions-v2"', '"named-regions-v3"')
text = replace_once(text, '        self.assertIn("assembly", region_ids)\n', '        self.assertIn("assembly", region_ids)\n        self.assertIn("dungeon", region_ids)\n', "geometry dungeon assertion")
old_disconnected = '''        disconnected = (
            WorldRegion("observatory", "Observatory", 0, 0, ("archive", "assembly"), "A"),
            WorldRegion("archive", "Archive", -2, 1, ("observatory",), "B"),
            WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory",), "Game"),
            WorldRegion("agora", "Agora", 0, 2, ("commons",), "C"),
            WorldRegion("commons", "Commons", 2, 1, ("agora",), "D"),
        )
'''
new_disconnected = '''        disconnected = (
            WorldRegion("observatory", "Observatory", 0, 0, ("archive", "assembly", "dungeon"), "A"),
            WorldRegion("archive", "Archive", -2, 1, ("observatory",), "B"),
            WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory", "dungeon"), "Game"),
            WorldRegion("dungeon", "Dungeon", 2, -2, ("observatory", "assembly"), "MUD"),
            WorldRegion("agora", "Agora", 0, 2, ("commons",), "C"),
            WorldRegion("commons", "Commons", 2, 1, ("agora",), "D"),
        )
'''
text = replace_once(text, old_disconnected, new_disconnected, "disconnected fixture")
text = replace_once(
    text,
    '        self.assertEqual(assembly["hop_distance"], 1)\n',
    '        self.assertEqual(assembly["hop_distance"], 1)\n'
    '        dungeon = api.handle({"operation": "world.geometry.distance", "source_region_id": "observatory", "target_region_id": "dungeon"})\n'
    '        self.assertEqual(dungeon["hop_distance"], 1)\n',
    "API dungeon distance",
)
write(path, text)

# tests/test_un_sim.py outer runtime version moves, UN game remains present but not necessarily first forever.
path = "tests/test_un_sim.py"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(text, 'self.assertEqual(health["protocol"], "nexus/0.6")', 'self.assertEqual(health["protocol"], "nexus/0.7")', "UN test protocol")
text = replace_once(text, 'self.assertEqual(health["runtime_version"], "2.0.0-alpha6.2")', 'self.assertEqual(health["runtime_version"], "2.0.0-alpha6.3")', "UN test runtime")
text = replace_once(text, 'self.assertEqual(health["geometry"], "named-regions-v2")', 'self.assertEqual(health["geometry"], "named-regions-v3")', "UN test geometry")
text = replace_once(text, 'self.assertEqual(health["games"][0]["room"], "#un-sim")', 'self.assertIn("#un-sim", {game["room"] for game in health["games"]})', "UN game registry assertion")
write(path, text)

# tui/src/lib.rs
path = "tui/src/lib.rs"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(text, "pub const ROOMS: [RoomSpec; 5]", "pub const ROOMS: [RoomSpec; 6]", "room count")
un_room = '''    RoomSpec {
        channel: "#un-sim",
        mode_id: "game_un",
        region_id: "assembly",
        label: "Assembly Hall / UN Simulation Game",
    },
];
'''
un_plus_mud = '''    RoomSpec {
        channel: "#un-sim",
        mode_id: "game_un",
        region_id: "assembly",
        label: "Assembly Hall / UN Simulation Game",
    },
    RoomSpec {
        channel: "#mud",
        mode_id: "game_mud",
        region_id: "dungeon",
        label: "Dungeon / HERESY MUD",
    },
];
'''
text = replace_once(text, un_room, un_plus_mud, "MUD room")
text = replace_once(text, "pub const COMMANDS: [&str; 29]", "pub const COMMANDS: [&str; 30]", "command count")
text = replace_once(text, '    "/game",\n    "/me",', '    "/game",\n    "/mud",\n    "/me",', "mud command")
anchor = '''pub enum GameCommand {
    Help,
    New {
        seed: String,
    },
    Status,
    Act {
        action: String,
        targets: Vec<String>,
    },
    Turn,
}
'''
addition = anchor + '''
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MudCommand {
    Help,
    New { seed: String },
    Status { player: Option<String> },
    Who,
    Inventory { player: Option<String> },
    Act {
        player: Option<String>,
        action: String,
        args: Vec<String>,
    },
}
'''
text = replace_once(text, anchor, addition, "MudCommand enum")
text = replace_once(text, "    Game(GameCommand),\n    Me(String),", "    Game(GameCommand),\n    Mud(MudCommand),\n    Me(String),", "InputCommand mud")
text = replace_once(text, '        "/game" => parse_game(rest).map(InputCommand::Game),\n        "/me" =>', '        "/game" => parse_game(rest).map(InputCommand::Game),\n        "/mud" => parse_mud(rest).map(InputCommand::Mud),\n        "/me" =>', "parse mud command")
parse_game_end = '''fn split_command(value: &str) -> (&str, &str) {
'''
parse_mud = '''fn parse_mud(rest: &str) -> Result<MudCommand, String> {
    let trimmed = rest.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("help") {
        return Ok(MudCommand::Help);
    }
    let (sub, tail) = split_first(trimmed).expect("non-empty mud command");
    let sub = sub.to_ascii_lowercase();
    match sub.as_str() {
        "new" => Ok(MudCommand::New { seed: unquote(tail) }),
        "status" | "look" => Ok(MudCommand::Status {
            player: if tail.is_empty() { None } else { Some(tail.to_string()) },
        }),
        "who" if tail.is_empty() => Ok(MudCommand::Who),
        "inventory" | "inv" | "i" => Ok(MudCommand::Inventory {
            player: if tail.is_empty() { None } else { Some(tail.to_string()) },
        }),
        "as" => {
            let (player, action_tail) = split_first(tail)
                .ok_or_else(|| "usage: /mud as <player> <action> [args...]".to_string())?;
            let (action, args) = split_first(action_tail)
                .ok_or_else(|| "usage: /mud as <player> <action> [args...]".to_string())?;
            Ok(MudCommand::Act {
                player: Some(player.to_string()),
                action: normalize_mud_action(action),
                args: mud_action_args(action, args),
            })
        }
        "n" | "s" | "e" | "w" | "north" | "south" | "east" | "west" => Ok(MudCommand::Act {
            player: None,
            action: "go".to_string(),
            args: vec![sub],
        }),
        _ => Ok(MudCommand::Act {
            player: None,
            action: normalize_mud_action(&sub),
            args: mud_action_args(&sub, tail),
        }),
    }
}

fn normalize_mud_action(action: &str) -> String {
    match action.to_ascii_lowercase().as_str() {
        "get" => "take".to_string(),
        other => other.to_string(),
    }
}

fn mud_action_args(action: &str, tail: &str) -> Vec<String> {
    if matches!(action.to_ascii_lowercase().as_str(), "n" | "s" | "e" | "w" | "north" | "south" | "east" | "west") {
        vec![action.to_ascii_lowercase()]
    } else {
        tail.split_whitespace().map(str::to_string).collect()
    }
}

fn split_command(value: &str) -> (&str, &str) {
'''
text = replace_once(text, parse_game_end, parse_mud, "parse_mud function")
write(path, text)

# tui/src/main.rs
path = "tui/src/main.rs"
text = Path(path).read_text(encoding="utf-8")
text = replace_once(
    text,
    "sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, GameCommand, InputCommand,\n    RoomSpec, ROOMS,",
    "sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, GameCommand, InputCommand,\n    MudCommand, RoomSpec, ROOMS,",
    "main import MudCommand",
)
text = replace_once(text, "    game_refs: BTreeMap<String, String>,\n    targeted_evidence:", "    game_refs: BTreeMap<String, String>,\n    mud_refs: BTreeMap<String, String>,\n    targeted_evidence:", "mud refs state")
text = replace_once(text, "            game_refs: BTreeMap::new(),\n            targeted_evidence:", "            game_refs: BTreeMap::new(),\n            mud_refs: BTreeMap::new(),\n            targeted_evidence:", "mud refs init")
text = replace_once(text, "*** NEXUS 2.0 alpha6.2 IRC/TUI", "*** NEXUS 2.0 alpha6.3 IRC/TUI", "TUI runtime banner")
text = replace_once(text, "            InputCommand::Game(command) => self.execute_game(nexus, command)?,\n            InputCommand::Say", "            InputCommand::Game(command) => self.execute_game(nexus, command)?,\n            InputCommand::Mud(command) => self.execute_mud(nexus, command)?,\n            InputCommand::Say", "dispatch MUD")

mud_methods = r'''    fn current_mud_ref(&self) -> Option<&str> {
        let channel = self.room.channel;
        let mud_ref = self.mud_refs.get(channel).map(String::as_str)?;
        let in_evidence = self
            .room_evidence
            .get(channel)
            .map(|refs| refs.iter().any(|value| value == mud_ref))
            .unwrap_or(false);
        if in_evidence { Some(mud_ref) } else { None }
    }

    fn set_mud_ref(&mut self, mud_ref: String) {
        let channel = self.room.channel.to_string();
        if let Some(previous) = self.mud_refs.insert(channel.clone(), mud_ref.clone()) {
            if let Some(refs) = self.room_evidence.get_mut(&channel) {
                refs.retain(|value| value != &previous);
            }
        }
        self.add_room_evidence(&channel, mud_ref);
    }

    fn require_mud_room(&self) -> Result<(), String> {
        if self.room.mode_id != "game_mud" {
            return Err("/mud commands are available in #mud; use /join #mud".to_string());
        }
        Ok(())
    }

    fn mud_roster(&self) -> Result<Vec<String>, String> {
        let mut players = vec![self.nick.clone()];
        players.extend(self.members.iter().map(|member| member.nick.clone()));
        let mut folded = std::collections::BTreeSet::new();
        for player in &players {
            if player.is_empty()
                || player.len() > 32
                || !player
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '.' | '-'))
            {
                return Err(format!(
                    "MUD avatar id {player:?} must use 1-32 ASCII letters, digits, _, . or -"
                ));
            }
            if !folded.insert(player.to_ascii_lowercase()) {
                return Err(format!("duplicate MUD avatar id: {player}"));
            }
        }
        Ok(players)
    }

    fn execute_mud(
        &mut self,
        nexus: &mut NexusProcess,
        command: MudCommand,
    ) -> Result<(), String> {
        self.require_mud_room()?;
        match command {
            MudCommand::Help => {
                for line in [
                    "*** HERESY MUD: /mud new [seed] | /mud look [player] | /mud who | /mud inventory [player]",
                    "*** MOVE: /mud n|s|e|w OR /mud go <direction> | /mud take|get <item> | /mud drop <item>",
                    "*** COMBAT: /mud attack <npc> [weapon] | /mud use <item> | /mud rest | /mud shitpost [npc] | /mud ratio <npc>",
                    "*** PROXY: /mud as <player> <action> [args...] lets the operator drive any registered avatar.",
                    "*** Current MUD state is shared Council evidence. Model narration never mutates the dungeon.",
                ] {
                    self.append(line);
                }
            }
            MudCommand::New { seed } => {
                let players = self.mud_roster()?;
                let mut request = json!({"operation": "game.mud.new", "players": players});
                if !seed.trim().is_empty() {
                    request["seed"] = json!(seed);
                }
                let response = nexus.request(request)?;
                let mud_ref = response
                    .get("mud_ref")
                    .and_then(Value::as_str)
                    .ok_or_else(|| "MUD response missing mud_ref".to_string())?
                    .to_string();
                self.set_mud_ref(mud_ref.clone());
                self.append(&format!("*** New HERESY MUD state: {mud_ref}"));
                self.render_mud_state(&response)?;
            }
            MudCommand::Status { player } | MudCommand::Inventory { player } => {
                let mud_ref = self
                    .current_mud_ref()
                    .ok_or_else(|| "no shared MUD in #mud; use /mud new [seed]".to_string())?
                    .to_string();
                let player_id = player.unwrap_or_else(|| self.nick.clone());
                let response = nexus.request(json!({
                    "operation": "game.mud.inspect",
                    "mud_ref": mud_ref,
                    "player_id": player_id
                }))?;
                self.render_mud_state(&response)?;
            }
            MudCommand::Who => {
                let mud_ref = self
                    .current_mud_ref()
                    .ok_or_else(|| "no shared MUD in #mud; use /mud new [seed]".to_string())?
                    .to_string();
                let response = nexus.request(json!({"operation": "game.mud.inspect", "mud_ref": mud_ref}))?;
                self.render_mud_who(&response)?;
            }
            MudCommand::Act { player, action, args } => {
                let mud_ref = self
                    .current_mud_ref()
                    .ok_or_else(|| "no shared MUD in #mud; use /mud new [seed]".to_string())?
                    .to_string();
                let player_id = player.unwrap_or_else(|| self.nick.clone());
                let response = nexus.request(json!({
                    "operation": "game.mud.act",
                    "mud_ref": mud_ref,
                    "player_id": player_id,
                    "action": action,
                    "args": args
                }))?;
                let next_ref = response
                    .get("mud_ref")
                    .and_then(Value::as_str)
                    .ok_or_else(|| "MUD response missing mud_ref".to_string())?
                    .to_string();
                self.set_mud_ref(next_ref);
                self.render_mud_state(&response)?;
            }
        }
        Ok(())
    }

    fn render_mud_who(&mut self, response: &Value) -> Result<(), String> {
        let mud = response
            .get("mud")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD response missing mud object".to_string())?;
        let rooms = mud
            .get("rooms")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD rooms missing".to_string())?;
        let players = mud
            .get("players")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD players missing".to_string())?;
        self.append(&format!("--- MUD WHO | {} avatar(s) ---", players.len()));
        let mut ids: Vec<&String> = players.keys().collect();
        ids.sort_by_key(|value| value.to_ascii_lowercase());
        for id in ids {
            let player = &players[id];
            let room_id = player.get("room_id").and_then(Value::as_str).unwrap_or("?");
            let room_name = rooms
                .get(room_id)
                .and_then(Value::as_object)
                .and_then(|room| room.get("name"))
                .and_then(Value::as_str)
                .unwrap_or(room_id);
            let hp = player.get("hp").and_then(Value::as_u64).unwrap_or(0);
            let max_hp = player.get("max_hp").and_then(Value::as_u64).unwrap_or(0);
            let clout = player.get("clout").and_then(Value::as_i64).unwrap_or(0);
            let score = player.get("score").and_then(Value::as_i64).unwrap_or(0);
            self.append(&format!("*** {id}: HP {hp}/{max_hp} clout={clout} score={score} @ {room_name}"));
        }
        Ok(())
    }

    fn render_mud_state(&mut self, response: &Value) -> Result<(), String> {
        let mud = response
            .get("mud")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD response missing mud object".to_string())?;
        let view = response
            .get("view")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD response missing player view".to_string())?;
        let player = view
            .get("player")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD view missing player".to_string())?;
        let room = view
            .get("room")
            .and_then(Value::as_object)
            .ok_or_else(|| "MUD view missing room".to_string())?;
        let turn = mud.get("turn").and_then(Value::as_u64).unwrap_or(0);
        let player_id = player.get("player_id").and_then(Value::as_str).unwrap_or("?");
        let hp = player.get("hp").and_then(Value::as_u64).unwrap_or(0);
        let max_hp = player.get("max_hp").and_then(Value::as_u64).unwrap_or(0);
        let clout = player.get("clout").and_then(Value::as_i64).unwrap_or(0);
        let score = player.get("score").and_then(Value::as_i64).unwrap_or(0);
        let room_id = room.get("room_id").and_then(Value::as_str).unwrap_or("?");
        let room_name = room.get("name").and_then(Value::as_str).unwrap_or(room_id);
        let realm = room.get("realm").and_then(Value::as_str).unwrap_or("?");
        self.append(&format!("--- HERESY MUD TURN {turn} | {player_id} HP {hp}/{max_hp} clout={clout} score={score} ---"));
        self.append(&format!("*** ROOM: {room_name} [{realm}/{room_id}]"));
        if let Some(description) = room.get("description").and_then(Value::as_str) {
            self.append(&format!("*** {description}"));
        }
        if let Some(exits) = room.get("exits").and_then(Value::as_object) {
            let mut parts: Vec<String> = exits
                .iter()
                .map(|(direction, target)| format!("{direction}={}", target.as_str().unwrap_or("?")))
                .collect();
            parts.sort();
            self.append(&format!("*** EXITS: {}", parts.join(" | ")));
        }
        if let Some(items) = view.get("room_items").and_then(Value::as_array) {
            let labels: Vec<&str> = items
                .iter()
                .filter_map(|item| item.get("item_id").and_then(Value::as_str))
                .collect();
            self.append(&format!("*** ITEMS: {}", if labels.is_empty() { "-".to_string() } else { labels.join(", ") }));
        }
        if let Some(npcs) = view.get("room_npcs").and_then(Value::as_array) {
            if npcs.is_empty() {
                self.append("*** NPCS: -");
            }
            for npc in npcs {
                let id = npc.get("npc_id").and_then(Value::as_str).unwrap_or("?");
                let name = npc.get("name").and_then(Value::as_str).unwrap_or(id);
                let npc_hp = npc.get("hp").and_then(Value::as_u64).unwrap_or(0);
                let npc_max = npc.get("max_hp").and_then(Value::as_u64).unwrap_or(0);
                self.append(&format!("*** NPC: {id} — {name} | HP {npc_hp}/{npc_max}"));
            }
        }
        if let Some(inventory) = view.get("inventory").and_then(Value::as_array) {
            let labels: Vec<&str> = inventory
                .iter()
                .filter_map(|item| item.get("item_id").and_then(Value::as_str))
                .collect();
            self.append(&format!("*** INVENTORY: {}", if labels.is_empty() { "-".to_string() } else { labels.join(", ") }));
        }
        if let Some(quest) = view.get("quest").and_then(Value::as_object) {
            let status = quest.get("status").and_then(Value::as_str).unwrap_or("?");
            let objective = quest.get("objective").and_then(Value::as_str).unwrap_or("");
            self.append(&format!("*** QUEST [{status}]: {objective}"));
        }
        if let Some(event) = mud
            .get("event_log")
            .and_then(Value::as_array)
            .and_then(|events| events.last())
            .and_then(|event| event.get("text"))
            .and_then(Value::as_str)
        {
            self.append(&format!("*** LATEST: {event}"));
        }
        if let Some(mud_ref) = response.get("mud_ref").and_then(Value::as_str) {
            self.append(&format!("*** MUD STATE: {mud_ref}"));
        }
        Ok(())
    }

'''
text = replace_once(text, "    fn current_game_ref(&self) -> Option<&str> {\n", mud_methods + "    fn current_game_ref(&self) -> Option<&str> {\n", "insert MUD methods")
text = replace_once(
    text,
    '            "*** Game: /join #un-sim | /game new [seed] | /game status | /game act ... | /game turn",\n',
    '            "*** Game: /join #un-sim | /game new [seed] | /game status | /game act ... | /game turn",\n'
    '            "*** MUD: /join #mud | /mud new [seed] | /mud look | /mud n|s|e|w | /mud attack ... | /mud help",\n',
    "main help MUD",
)
write(path, text)

# Add permanent Rust MUD parser/room tests.
Path("tui/tests/mud.rs").write_text(r'''use nexus_irc_tui::{command_completions, parse_input, room_from_name, AliasBook, InputCommand, MudCommand};

#[test]
fn mud_room_maps_to_game_mode_and_dungeon_region() {
    let room = room_from_name("#mud").expect("#mud room");
    assert_eq!(room.channel, "#mud");
    assert_eq!(room.mode_id, "game_mud");
    assert_eq!(room.region_id, "dungeon");
}

#[test]
fn mud_commands_parse_classic_and_proxy_syntax() {
    assert_eq!(
        parse_input("/mud n").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "go".to_string(),
            args: vec!["n".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud get large_trout").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "take".to_string(),
            args: vec!["large_trout".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud as Grok attack yaml_necromancer large_trout").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: Some("Grok".to_string()),
            action: "attack".to_string(),
            args: vec!["yaml_necromancer".to_string(), "large_trout".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud shitpost content_moderator_troll").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "shitpost".to_string(),
            args: vec!["content_moderator_troll".to_string()],
        })
    );
}

#[test]
fn mud_is_reserved_builtin_and_tab_completion_finds_it() {
    assert_eq!(command_completions("/mu"), vec!["/mud"]);
    let mut aliases = AliasBook::default();
    assert!(aliases.define("mud", "/me replaces the dungeon with React").is_err());
}

#[test]
fn malformed_proxy_command_fails_locally() {
    assert!(parse_input("/mud as Grok").is_err());
}
''', encoding="utf-8")
