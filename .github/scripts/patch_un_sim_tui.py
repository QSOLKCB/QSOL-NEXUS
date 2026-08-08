from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


lib_path = Path("tui/src/lib.rs")
lib = lib_path.read_text()
lib = replace_once(lib, "pub const ROOMS: [RoomSpec; 4] = [", "pub const ROOMS: [RoomSpec; 5] = [", "room count")
lib = replace_once(
    lib,
    '''    RoomSpec {
        channel: "#commons",
        mode_id: "meme_casual",
        region_id: "commons",
        label: "Commons / Meme-Casual",
    },
];''',
    '''    RoomSpec {
        channel: "#commons",
        mode_id: "meme_casual",
        region_id: "commons",
        label: "Commons / Meme-Casual",
    },
    RoomSpec {
        channel: "#un-sim",
        mode_id: "game_un",
        region_id: "assembly",
        label: "Assembly Hall / UN Simulation Game",
    },
];''',
    "un-sim room",
)
lib = replace_once(lib, "pub const COMMANDS: [&str; 28] = [", "pub const COMMANDS: [&str; 29] = [", "command count")
lib = replace_once(lib, '    "/council",\n    "/me",', '    "/council",\n    "/game",\n    "/me",', "game completion")
lib = replace_once(
    lib,
    '''pub enum DccCommand {
    Send { target: String, path: PathBuf },
    Chat { nick: String },
    Close { kind: String, nick: String },
    List,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InputCommand {''',
    '''pub enum DccCommand {
    Send { target: String, path: PathBuf },
    Chat { nick: String },
    Close { kind: String, nick: String },
    List,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GameCommand {
    Help,
    New { seed: String },
    Status,
    Act { action: String, targets: Vec<String> },
    Turn,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InputCommand {''',
    "game enum",
)
lib = replace_once(lib, "    Ask(String),\n    Me(String),", "    Ask(String),\n    Game(GameCommand),\n    Me(String),", "game input enum")
lib = replace_once(
    lib,
    '        "/ask" | "/council" => Ok(InputCommand::Ask(rest.to_string())),\n        "/me" =>',
    '        "/ask" | "/council" => Ok(InputCommand::Ask(rest.to_string())),\n        "/game" => parse_game(rest).map(InputCommand::Game),\n        "/me" =>',
    "game parser dispatch",
)
lib = replace_once(
    lib,
    '''fn split_command(value: &str) -> (&str, &str) {''',
    '''fn parse_game(rest: &str) -> Result<GameCommand, String> {
    let trimmed = rest.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("help") {
        return Ok(GameCommand::Help);
    }
    let (sub, tail) = split_first(trimmed).expect("non-empty game command");
    match sub.to_ascii_lowercase().as_str() {
        "new" => Ok(GameCommand::New { seed: unquote(tail) }),
        "status" if tail.is_empty() => Ok(GameCommand::Status),
        "turn" if tail.is_empty() => Ok(GameCommand::Turn),
        "act" => {
            let (action, targets) = split_first(tail)
                .ok_or_else(|| "usage: /game act <action> [country-id ...]".to_string())?;
            Ok(GameCommand::Act {
                action: action.to_string(),
                targets: targets.split_whitespace().map(str::to_string).collect(),
            })
        }
        _ => Err("usage: /game <new [seed]|status|act <action> [country-id ...]|turn|help>".to_string()),
    }
}

fn split_command(value: &str) -> (&str, &str) {''',
    "game parser",
)
lib_path.write_text(lib)

main_path = Path("tui/src/main.rs")
main = main_path.read_text()
main = replace_once(
    main,
    '''    sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, InputCommand, RoomSpec,
    ROOMS,
};''',
    '''    sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, GameCommand, InputCommand,
    RoomSpec, ROOMS,
};''',
    "game import",
)
main = replace_once(
    main,
    '''    room_evidence: BTreeMap<String, Vec<String>>,
    targeted_evidence: BTreeMap<String, Vec<String>>,''',
    '''    room_evidence: BTreeMap<String, Vec<String>>,
    game_refs: BTreeMap<String, String>,
    targeted_evidence: BTreeMap<String, Vec<String>>,''',
    "game refs field",
)
main = replace_once(
    main,
    '''            room_evidence: BTreeMap::new(),
            targeted_evidence: BTreeMap::new(),''',
    '''            room_evidence: BTreeMap::new(),
            game_refs: BTreeMap::new(),
            targeted_evidence: BTreeMap::new(),''',
    "game refs init",
)
main = replace_once(main, 'app.append("*** NEXUS 2.0 alpha5 IRC/TUI — local room, no IRC server");', 'app.append("*** NEXUS 2.0 alpha6.2 IRC/TUI — local room, no IRC server");', "version banner")
main = replace_once(
    main,
    '''            InputCommand::Say(text) => {
                if let Some(target) = self.private_target.clone() {''',
    '''            InputCommand::Game(command) => self.execute_game(nexus, command)?,
            InputCommand::Say(text) => {
                if let Some(target) = self.private_target.clone() {''',
    "game match arm",
)
main = replace_once(
    main,
    '''    fn run_council(&mut self, nexus: &mut NexusProcess, question: &str) -> Result<(), String> {''',
    '''    fn current_game_ref(&self) -> Option<&str> {
        self.game_refs.get(self.room.channel).map(String::as_str)
    }

    fn set_game_ref(&mut self, game_ref: String) {
        let channel = self.room.channel.to_string();
        if let Some(previous) = self.game_refs.insert(channel.clone(), game_ref.clone()) {
            if let Some(refs) = self.room_evidence.get_mut(&channel) {
                refs.retain(|value| value != &previous);
            }
        }
        self.add_room_evidence(&channel, game_ref);
    }

    fn require_game_room(&self) -> Result<(), String> {
        if self.room.mode_id != "game_un" {
            return Err("/game commands are available in #un-sim; use /join #un-sim".to_string());
        }
        Ok(())
    }

    fn execute_game(&mut self, nexus: &mut NexusProcess, command: GameCommand) -> Result<(), String> {
        self.require_game_room()?;
        match command {
            GameCommand::Help => {
                for line in [
                    "*** UN SIM: /game new [seed] | /game status | /game turn",
                    "*** ACTION: /game act <sanction|support|aid|arms|meme|suspend|reinstate|recognize> <country-id ...>",
                    "*** PEACE: /game act mediate <country-a> <country-b> | /game act do_nothing",
                    "*** The current board is shared Council evidence. Debate never mutates it; /game does.",
                ] {
                    self.append(line);
                }
            }
            GameCommand::New { seed } => {
                let mut request = json!({"operation": "game.un.new"});
                if !seed.trim().is_empty() {
                    request["seed"] = json!(seed);
                }
                let response = nexus.request(request)?;
                let game_ref = response.get("game_ref").and_then(Value::as_str)
                    .ok_or_else(|| "game response missing game_ref".to_string())?.to_string();
                self.set_game_ref(game_ref.clone());
                self.append(&format!("*** New fictional UN simulation: {game_ref}"));
                self.render_game_state(&response)?;
            }
            GameCommand::Status => {
                let game_ref = self.current_game_ref()
                    .ok_or_else(|| "no game in #un-sim; use /game new [seed]".to_string())?.to_string();
                let response = nexus.request(json!({"operation": "game.un.inspect", "game_ref": game_ref}))?;
                self.render_game_state(&response)?;
            }
            GameCommand::Act { action, targets } => {
                let game_ref = self.current_game_ref()
                    .ok_or_else(|| "no game in #un-sim; use /game new [seed]".to_string())?.to_string();
                let response = nexus.request(json!({"operation": "game.un.act", "game_ref": game_ref, "action": action, "targets": targets}))?;
                let next_ref = response.get("game_ref").and_then(Value::as_str)
                    .ok_or_else(|| "game response missing game_ref".to_string())?.to_string();
                self.set_game_ref(next_ref);
                self.render_game_state(&response)?;
            }
            GameCommand::Turn => {
                let game_ref = self.current_game_ref()
                    .ok_or_else(|| "no game in #un-sim; use /game new [seed]".to_string())?.to_string();
                let response = nexus.request(json!({"operation": "game.un.turn", "game_ref": game_ref}))?;
                let next_ref = response.get("game_ref").and_then(Value::as_str)
                    .ok_or_else(|| "game response missing game_ref".to_string())?.to_string();
                self.set_game_ref(next_ref);
                self.render_game_state(&response)?;
            }
        }
        Ok(())
    }

    fn render_game_state(&mut self, response: &Value) -> Result<(), String> {
        let game = response.get("game").and_then(Value::as_object)
            .ok_or_else(|| "game response missing game object".to_string())?;
        let turn = game.get("turn").and_then(Value::as_u64).unwrap_or(0);
        let tension = game.get("world_tension").and_then(Value::as_u64).unwrap_or(0);
        let legitimacy = game.get("un_legitimacy").and_then(Value::as_u64).unwrap_or(0);
        self.append(&format!("--- UN SIM TURN {turn} | tension={tension} | UN legitimacy={legitimacy} ---"));
        if let Some(wars) = game.get("wars").and_then(Value::as_array) {
            if wars.is_empty() {
                self.append("*** WARS: none. This is presumably temporary.");
            }
            for war in wars {
                let a = war.get("a").and_then(Value::as_str).unwrap_or("?");
                let b = war.get("b").and_then(Value::as_str).unwrap_or("?");
                let sa = war.get("score_a").and_then(Value::as_u64).unwrap_or(0);
                let sb = war.get("score_b").and_then(Value::as_u64).unwrap_or(0);
                self.append(&format!("*** WAR: {a} vs {b} | score {sa}-{sb}"));
            }
        }
        if let Some(countries) = game.get("countries").and_then(Value::as_object) {
            let mut ids: Vec<&String> = countries.keys().collect();
            ids.sort();
            for id in ids {
                let country = &countries[id];
                let name = country.get("name").and_then(Value::as_str).unwrap_or(id);
                let e = country.get("economy").and_then(Value::as_u64).unwrap_or(0);
                let m = country.get("military").and_then(Value::as_u64).unwrap_or(0);
                let s = country.get("stability").and_then(Value::as_u64).unwrap_or(0);
                let i = country.get("influence").and_then(Value::as_u64).unwrap_or(0);
                let r = country.get("reputation").and_then(Value::as_u64).unwrap_or(0);
                let t = country.get("territory").and_then(Value::as_u64).unwrap_or(0);
                let sanctions = country.get("sanctions").and_then(Value::as_u64).unwrap_or(0);
                let arms = country.get("arms_imports").and_then(Value::as_u64).unwrap_or(0);
                let memes = country.get("meme_heat").and_then(Value::as_u64).unwrap_or(0);
                let suspended = if country.get("suspended").and_then(Value::as_bool).unwrap_or(false) { " SUSPENDED" } else { "" };
                self.append(&format!("*** {id}: {name} | E{e} M{m} S{s} I{i} R{r} T{t} | sanctions={sanctions} arms={arms} memes={memes}{suspended}"));
            }
        }
        if let Some(event) = game.get("event_log").and_then(Value::as_array).and_then(|events| events.last()) {
            if let Some(text) = event.get("text").and_then(Value::as_str) {
                self.append(&format!("*** LATEST: {text}"));
            }
        }
        if let Some(game_ref) = response.get("game_ref").and_then(Value::as_str) {
            self.append(&format!("*** BOARD: {game_ref}"));
        }
        Ok(())
    }

    fn run_council(&mut self, nexus: &mut NexusProcess, question: &str) -> Result<(), String> {''',
    "game methods",
)
main = replace_once(
    main,
    '''            "*** Core: /join #room | /mode mode | /topic text | /ask text | plain text = Council question",
            "*** IRC: /me action | /msg nick text | /nick name | /who | /search text | /save file | /clear | /quit",''',
    '''            "*** Core: /join #room | /mode mode | /topic text | /ask text | plain text = Council question",
            "*** Game: /join #un-sim | /game new [seed] | /game status | /game act ... | /game turn",
            "*** IRC: /me action | /msg nick text | /nick name | /who | /search text | /save file | /clear | /quit",''',
    "game help",
)
main_path.write_text(main)

runtime_test = Path("tests/test_runtime.py")
runtime = runtime_test.read_text()
runtime = replace_once(
    runtime,
    '        self.assertEqual(result["protocol"], "nexus/0.5")',
    '        self.assertEqual(result["protocol"], "nexus/0.6")\n        self.assertEqual(result["runtime_version"], "2.0.0-alpha6.2")',
    "runtime protocol expectation",
)
runtime_test.write_text(runtime)
