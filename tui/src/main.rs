use chrono::Local;
use crossterm::cursor::{Hide, MoveTo, Show};
use crossterm::event::{self, Event, KeyCode, KeyModifiers};
use crossterm::style::Print;
use crossterm::terminal::{
    self, disable_raw_mode, enable_raw_mode, Clear, ClearType, EnterAlternateScreen,
    LeaveAlternateScreen,
};
use crossterm::{execute, queue};
use nexus_irc_tui::scripting::{expand_identifiers, IdentifierContext, VariableBook};
use nexus_irc_tui::{
    command_completions, load_document, normalize_action, parse_input, room_from_name,
    sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, GameCommand, InputCommand,
    RoomSpec, ROOMS,
};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use unicode_width::{UnicodeWidthChar, UnicodeWidthStr};

#[derive(Debug, Clone)]
struct MemberConfig {
    nick: String,
    config: Value,
}

impl MemberConfig {
    fn mock(nick: &str, profile: &str) -> Self {
        Self {
            nick: nick.to_string(),
            config: json!({
                "member_id": nick,
                "model_id": format!("mock-{}", nick.to_ascii_lowercase()),
                "adapter_id": "mock",
                "profile": profile
            }),
        }
    }

    fn ollama(nick: &str, model: &str) -> Self {
        Self {
            nick: nick.to_string(),
            config: json!({
                "member_id": nick,
                "model_id": model,
                "adapter_id": "ollama",
                "model": model,
                "endpoint": "http://127.0.0.1:11434",
                "timeout_seconds": 120
            }),
        }
    }

    fn backend_label(&self) -> &str {
        self.config
            .get("adapter_id")
            .and_then(Value::as_str)
            .unwrap_or("?")
    }
}

struct NexusProcess {
    child: Child,
    stdin: BufWriter<ChildStdin>,
    stdout: BufReader<ChildStdout>,
    request_id: u64,
}

impl NexusProcess {
    fn spawn(world: &Path) -> Result<Self, String> {
        let python = env::var("NEXUS_PYTHON").unwrap_or_else(|_| "python3".to_string());
        let mut command = Command::new(&python);
        command
            .arg("-m")
            .arg("nexus_runtime")
            .arg("--world")
            .arg(world)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());

        if let Some(pythonpath) = discover_pythonpath() {
            command.env("PYTHONPATH", pythonpath);
        }

        let mut child = command
            .spawn()
            .map_err(|e| format!("cannot start NEXUS Python runtime with {python}: {e}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "NEXUS runtime stdin unavailable".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "NEXUS runtime stdout unavailable".to_string())?;
        let mut process = Self {
            child,
            stdin: BufWriter::new(stdin),
            stdout: BufReader::new(stdout),
            request_id: 0,
        };
        process.request(json!({"operation": "system.health"}))?;
        Ok(process)
    }

    fn request(&mut self, mut request: Value) -> Result<Value, String> {
        self.request_id += 1;
        let object = request
            .as_object_mut()
            .ok_or_else(|| "internal request must be a JSON object".to_string())?;
        object.insert(
            "request_id".to_string(),
            json!(format!("tui-{}", self.request_id)),
        );
        writeln!(self.stdin, "{request}")
            .map_err(|e| format!("cannot write to NEXUS runtime: {e}"))?;
        self.stdin
            .flush()
            .map_err(|e| format!("cannot flush NEXUS runtime request: {e}"))?;

        let mut line = String::new();
        let bytes = self
            .stdout
            .read_line(&mut line)
            .map_err(|e| format!("cannot read NEXUS runtime response: {e}"))?;
        if bytes == 0 {
            return Err("NEXUS runtime closed its stdout".to_string());
        }
        let response: Value = serde_json::from_str(line.trim())
            .map_err(|e| format!("invalid JSON from NEXUS runtime: {e}: {}", line.trim()))?;
        if response.get("status").and_then(Value::as_str) == Some("error") {
            let message = response
                .pointer("/error/message")
                .and_then(Value::as_str)
                .unwrap_or("unknown NEXUS runtime error");
            return Err(message.to_string());
        }
        Ok(response)
    }
}

impl Drop for NexusProcess {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn discover_pythonpath() -> Option<String> {
    if let Ok(value) = env::var("NEXUS_PYTHONPATH") {
        if !value.trim().is_empty() {
            return Some(value);
        }
    }
    for candidate in [Path::new("src"), Path::new("../src")] {
        if candidate.join("nexus_runtime").is_dir() {
            return Some(candidate.to_string_lossy().to_string());
        }
    }
    env::var("PYTHONPATH")
        .ok()
        .filter(|value| !value.trim().is_empty())
}

struct TerminalGuard;

impl TerminalGuard {
    fn enter() -> io::Result<Self> {
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        if let Err(error) = execute!(stdout, EnterAlternateScreen, Hide) {
            let _ = disable_raw_mode();
            let _ = execute!(stdout, Show, LeaveAlternateScreen);
            return Err(error);
        }
        Ok(Self)
    }
}

impl Drop for TerminalGuard {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let mut stdout = io::stdout();
        let _ = execute!(stdout, Show, LeaveAlternateScreen);
    }
}

struct App {
    nick: String,
    room: RoomSpec,
    topics: BTreeMap<String, String>,
    members: Vec<MemberConfig>,
    room_evidence: BTreeMap<String, Vec<String>>,
    game_refs: BTreeMap<String, String>,
    targeted_evidence: BTreeMap<String, Vec<String>>,
    dcc_sessions: Vec<DccSession>,
    private_target: Option<String>,
    aliases: AliasBook,
    variables: VariableBook,
    state_path: PathBuf,
    scrollback: Vec<String>,
    input: String,
    history: Vec<String>,
    history_index: Option<usize>,
    scroll_offset: usize,
    running: bool,
}

impl App {
    fn new(nick: String, state_path: PathBuf) -> Self {
        let mut app = Self {
            nick,
            room: ROOMS[0],
            topics: BTreeMap::new(),
            members: vec![
                MemberConfig::mock("Alpha", "balanced"),
                MemberConfig::mock("Beta", "skeptical"),
                MemberConfig::mock("Gamma", "exploratory"),
            ],
            room_evidence: BTreeMap::new(),
            game_refs: BTreeMap::new(),
            targeted_evidence: BTreeMap::new(),
            dcc_sessions: Vec::new(),
            private_target: None,
            aliases: AliasBook::default(),
            variables: VariableBook::default(),
            state_path,
            scrollback: Vec::new(),
            input: String::new(),
            history: Vec::new(),
            history_index: None,
            scroll_offset: 0,
            running: true,
        };
        app.load_state();
        app.append("*** NEXUS 2.0 alpha6.2 IRC/TUI — local room, no IRC server");
        app.append(
            "*** /help for commands. The mode can change the vibe; it cannot change the vote.",
        );
        app.append(&format!(
            "*** You have joined {} ({})",
            app.room.channel, app.room.label
        ));
        app
    }

    fn timestamp() -> String {
        Local::now().format("%H:%M").to_string()
    }

    fn append(&mut self, text: &str) {
        for line in text.lines() {
            let safe = sanitize_terminal_text(line);
            self.scrollback
                .push(format!("{} {}", Self::timestamp(), safe));
        }
        self.scroll_offset = 0;
    }

    fn current_topic(&self) -> &str {
        self.topics
            .get(self.room.channel)
            .map(String::as_str)
            .unwrap_or("")
    }

    fn current_evidence(&self) -> Vec<String> {
        self.room_evidence
            .get(self.room.channel)
            .cloned()
            .unwrap_or_default()
    }

    fn add_room_evidence(&mut self, channel: &str, object_ref: String) {
        let refs = self.room_evidence.entry(channel.to_string()).or_default();
        if !refs.contains(&object_ref) {
            refs.push(object_ref);
        }
    }

    fn scrub_text(nexus: &mut NexusProcess, text: &str) -> Result<(String, bool), String> {
        let response =
            nexus.request(json!({"operation": "security.scrub_preview", "text": text}))?;
        let clean = response
            .get("text")
            .and_then(Value::as_str)
            .ok_or_else(|| "scrub preview response missing text".to_string())?;
        let changed = response
            .get("changed")
            .and_then(Value::as_bool)
            .ok_or_else(|| "scrub preview response missing changed flag".to_string())?;
        Ok((sanitize_terminal_text(clean), changed))
    }

    fn preprocess(&self, input: &str) -> String {
        let command = input
            .trim_start()
            .split_whitespace()
            .next()
            .unwrap_or("")
            .to_ascii_lowercase();
        if matches!(
            command.as_str(),
            "/alias" | "/aliases" | "/set" | "/unset" | "/vars"
        ) {
            return input.to_string();
        }
        let args_text = command_args(input);
        let aliased = self
            .aliases
            .expand(input, &self.nick, self.room.channel)
            .unwrap_or_else(|| input.to_string());
        let with_variables = self.variables.expand(&aliased);
        if !with_variables.trim_start().starts_with('/') {
            return with_variables;
        }
        expand_identifiers(
            &with_variables,
            IdentifierContext {
                me: &self.nick,
                channel: self.room.channel,
                mode: self.room.mode_id,
                region: self.room.region_id,
                topic: self.current_topic(),
            },
            args_text,
        )
    }

    fn execute_line(&mut self, nexus: &mut NexusProcess, raw: String) {
        self.history_index = None;
        if raw.trim().is_empty() {
            return;
        }
        let (clean, changed) = match Self::scrub_text(nexus, &raw) {
            Ok(result) => result,
            Err(error) => {
                self.append(&format!("*** ERROR: {error}"));
                return;
            }
        };
        self.history.push(clean.clone());
        if changed {
            self.append("*** secret-bearing text redacted before local history/scrollback");
        }
        let expanded = self.preprocess(&clean);
        match parse_input(&expanded) {
            Ok(command) => {
                if let Err(error) = self.execute_command(nexus, command) {
                    self.append(&format!("*** ERROR: {error}"));
                }
            }
            Err(error) => self.append(&format!("*** {error}")),
        }
    }

    fn execute_command(
        &mut self,
        nexus: &mut NexusProcess,
        command: InputCommand,
    ) -> Result<(), String> {
        match command {
            InputCommand::Noop => {}
            InputCommand::Help => self.show_help(),
            InputCommand::Join(name) | InputCommand::Mode(name) => {
                let room = room_from_name(&name)
                    .ok_or_else(|| format!("unknown NEXUS room/mode: {name}"))?;
                self.room = room;
                self.private_target = None;
                self.append(&format!(
                    "*** You have joined {} ({})",
                    room.channel, room.label
                ));
                let topic = self.current_topic().to_string();
                if !topic.is_empty() {
                    self.append(&format!("*** Topic: {topic}"));
                }
            }
            InputCommand::Topic(topic) => {
                let (topic, changed) = Self::scrub_text(nexus, &topic)?;
                self.topics
                    .insert(self.room.channel.to_string(), topic.clone());
                if changed {
                    self.append("*** secret-bearing topic text redacted");
                }
                self.append(&format!("*** {} changed the topic to: {topic}", self.nick));
            }
            InputCommand::Ask(question) => {
                let question = if question.trim().is_empty() {
                    self.current_topic().to_string()
                } else {
                    question
                };
                if question.trim().is_empty() {
                    return Err("no question supplied and the room topic is empty".to_string());
                }
                self.run_council(nexus, &question)?;
            }
            InputCommand::Game(command) => self.execute_game(nexus, command)?,
            InputCommand::Say(text) => {
                if let Some(target) = self.private_target.clone() {
                    self.direct_message(nexus, &target, &text)?;
                } else {
                    self.run_council(nexus, &text)?;
                }
            }
            InputCommand::Me(action) => {
                self.append(&format!("* {} {}", self.nick, normalize_action(&action)));
            }
            InputCommand::Msg { target, text } => self.direct_message(nexus, &target, &text)?,
            InputCommand::Nick(new_nick) => {
                if self
                    .members
                    .iter()
                    .any(|member| member.nick.eq_ignore_ascii_case(&new_nick))
                {
                    return Err(format!("nick already in use: {new_nick}"));
                }
                let old = self.nick.clone();
                self.nick = new_nick;
                self.append(&format!("*** {old} is now known as {}", self.nick));
            }
            InputCommand::Who => self.show_who(),
            InputCommand::Upload(path) => {
                let object_ref =
                    self.import_document(nexus, &path, self.room.channel, "room_upload")?;
                let channel = self.room.channel.to_string();
                self.add_room_evidence(&channel, object_ref.clone());
                self.append(&format!(
                    "*** DCC-style room evidence attached: {object_ref}"
                ));
            }
            InputCommand::Dcc(command) => self.execute_dcc(nexus, command)?,
            InputCommand::Evidence => self.show_evidence(),
            InputCommand::Ref(object_ref) => {
                nexus.request(json!({"operation": "world.inspect", "object_ref": object_ref}))?;
                let channel = self.room.channel.to_string();
                self.add_room_evidence(&channel, object_ref.clone());
                self.append(&format!(
                    "*** referenced {object_ref} as {} evidence",
                    self.room.channel
                ));
            }
            InputCommand::Unref(object_ref) => {
                if let Some(refs) = self.room_evidence.get_mut(self.room.channel) {
                    refs.retain(|value| value != &object_ref);
                }
                self.append(&format!(
                    "*** removed {object_ref} from {} evidence",
                    self.room.channel
                ));
            }
            InputCommand::AddMock { nick, profile } => {
                self.ensure_unique_member(&nick)?;
                self.members.push(MemberConfig::mock(&nick, &profile));
                self.append(&format!(
                    "*** {nick} joined {} [mock/{profile}]",
                    self.room.channel
                ));
            }
            InputCommand::AddOllama { nick, model } => {
                self.ensure_unique_member(&nick)?;
                self.members.push(MemberConfig::ollama(&nick, &model));
                self.append(&format!(
                    "*** {nick} joined {} [ollama/{model}]",
                    self.room.channel
                ));
            }
            InputCommand::Kick(nick) => {
                let canonical = self
                    .members
                    .iter()
                    .find(|member| member.nick.eq_ignore_ascii_case(&nick))
                    .map(|member| member.nick.clone())
                    .ok_or_else(|| format!("no such model member: {nick}"))?;
                self.members
                    .retain(|member| !member.nick.eq_ignore_ascii_case(&canonical));
                self.targeted_evidence.remove(&canonical);
                self.dcc_sessions
                    .retain(|session| !session.peer.eq_ignore_ascii_case(&canonical));
                if self
                    .private_target
                    .as_deref()
                    .map(|target| target.eq_ignore_ascii_case(&canonical))
                    .unwrap_or(false)
                {
                    self.private_target = None;
                }
                self.append(&format!(
                    "*** {canonical} was removed from the local room roster"
                ));
            }
            InputCommand::Alias { name, expansion } => {
                let (expansion, changed) = Self::scrub_text(nexus, &expansion)?;
                self.aliases.define(&name, &expansion)?;
                self.save_state()?;
                if changed {
                    self.append("*** secret-bearing alias text redacted before persistence");
                }
                self.append(&format!("*** alias /{name} = {expansion}"));
            }
            InputCommand::Aliases => {
                let aliases = self.aliases.list();
                if aliases.is_empty() {
                    self.append("*** no aliases defined");
                } else {
                    for (name, expansion) in aliases {
                        self.append(&format!("*** /{name} = {expansion}"));
                    }
                }
            }
            InputCommand::Set { name, value } => {
                let (value, changed) = Self::scrub_text(nexus, &value)?;
                self.variables.set(&name, &value)?;
                self.save_state()?;
                if changed {
                    self.append("*** secret-bearing variable value redacted before persistence");
                }
                self.append(&format!("*** {name} = {value}"));
            }
            InputCommand::Unset(name) => {
                let removed = self.variables.unset(&name)?;
                self.save_state()?;
                self.append(if removed {
                    "*** variable removed"
                } else {
                    "*** variable was not set"
                });
            }
            InputCommand::Vars => {
                let variables = self.variables.list();
                if variables.is_empty() {
                    self.append("*** no variables defined");
                } else {
                    for (name, value) in variables {
                        self.append(&format!("*** {name} = {value}"));
                    }
                }
            }
            InputCommand::Search(needle) => {
                let lower = needle.to_ascii_lowercase();
                let matches: Vec<String> = self
                    .scrollback
                    .iter()
                    .filter(|line| line.to_ascii_lowercase().contains(&lower))
                    .rev()
                    .take(12)
                    .cloned()
                    .collect();
                self.append(&format!(
                    "*** search {needle:?}: {} recent match(es)",
                    matches.len()
                ));
                for line in matches.into_iter().rev() {
                    self.scrollback
                        .push(format!("{} > {line}", Self::timestamp()));
                }
            }
            InputCommand::Save(path) => {
                if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
                    fs::create_dir_all(parent)
                        .map_err(|e| format!("cannot create {}: {e}", parent.display()))?;
                }
                fs::write(&path, self.scrollback.join("\n") + "\n")
                    .map_err(|e| format!("cannot save {}: {e}", path.display()))?;
                self.append(&format!("*** scrollback saved to {}", path.display()));
            }
            InputCommand::Clear => {
                self.scrollback.clear();
                self.scroll_offset = 0;
            }
            InputCommand::Quit => self.running = false,
        }
        Ok(())
    }

    fn current_game_ref(&self) -> Option<&str> {
        let channel = self.room.channel;
        let game_ref = self.game_refs.get(channel).map(String::as_str)?;
        let in_evidence = self
            .room_evidence
            .get(channel)
            .map(|refs| refs.iter().any(|value| value == game_ref))
            .unwrap_or(false);
        if in_evidence {
            Some(game_ref)
        } else {
            None
        }
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

    fn execute_game(
        &mut self,
        nexus: &mut NexusProcess,
        command: GameCommand,
    ) -> Result<(), String> {
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
        let game = response
            .get("game")
            .and_then(Value::as_object)
            .ok_or_else(|| "game response missing game object".to_string())?;
        let turn = game.get("turn").and_then(Value::as_u64).unwrap_or(0);
        let tension = game
            .get("world_tension")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let legitimacy = game
            .get("un_legitimacy")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        self.append(&format!(
            "--- UN SIM TURN {turn} | tension={tension} | UN legitimacy={legitimacy} ---"
        ));
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
                let s = country
                    .get("stability")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let i = country
                    .get("influence")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let r = country
                    .get("reputation")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let t = country
                    .get("territory")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let sanctions = country
                    .get("sanctions")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let arms = country
                    .get("arms_imports")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let memes = country
                    .get("meme_heat")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                let suspended = if country
                    .get("suspended")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
                {
                    " SUSPENDED"
                } else {
                    ""
                };
                self.append(&format!("*** {id}: {name} | E{e} M{m} S{s} I{i} R{r} T{t} | sanctions={sanctions} arms={arms} memes={memes}{suspended}"));
            }
        }
        if let Some(event) = game
            .get("event_log")
            .and_then(Value::as_array)
            .and_then(|events| events.last())
        {
            if let Some(text) = event.get("text").and_then(Value::as_str) {
                self.append(&format!("*** LATEST: {text}"));
            }
        }
        if let Some(game_ref) = response.get("game_ref").and_then(Value::as_str) {
            self.append(&format!("*** BOARD: {game_ref}"));
        }
        Ok(())
    }

    fn run_council(&mut self, nexus: &mut NexusProcess, question: &str) -> Result<(), String> {
        if self.members.len() < 3 {
            return Err(
                "Council requires at least three model members; use /addmock or /addollama"
                    .to_string(),
            );
        }
        let (question, changed) = Self::scrub_text(nexus, question)?;
        if changed {
            self.append("*** secret-bearing Council question text redacted");
        }
        self.append(&format!("<{}> {}", self.nick, question));
        self.append(&format!(
            "*** Council running in {} / {} ...",
            self.room.mode_id, self.room.region_id
        ));
        let members: Vec<Value> = self
            .members
            .iter()
            .map(|member| member.config.clone())
            .collect();
        let response = nexus.request(json!({
            "operation": "council.run",
            "question": question,
            "members": members,
            "evidence_refs": self.current_evidence(),
            "evidence_state": "UNTESTED",
            "mode": self.room.mode_id
        }))?;
        let session_ref = response
            .get("session_ref")
            .and_then(Value::as_str)
            .ok_or_else(|| "Council response missing session_ref".to_string())?;
        let session =
            nexus.request(json!({"operation": "world.inspect", "object_ref": session_ref}))?;
        self.render_session_to_scrollback(&session)?;
        Ok(())
    }

    fn render_session_to_scrollback(&mut self, response: &Value) -> Result<(), String> {
        let payload = response
            .pointer("/object/payload")
            .and_then(Value::as_object)
            .ok_or_else(|| "session object payload missing".to_string())?;
        let phases = payload
            .get("phase_submissions")
            .and_then(Value::as_object)
            .ok_or_else(|| "session phase_submissions missing".to_string())?;
        for phase in ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"] {
            self.append(&format!("--- {phase} ---"));
            if let Some(entries) = phases.get(phase).and_then(Value::as_array) {
                for entry in entries {
                    let member = entry
                        .get("member_id")
                        .and_then(Value::as_str)
                        .unwrap_or("?");
                    let content = entry.get("content").and_then(Value::as_str).unwrap_or("");
                    self.append(&format!("<{member}> {content}"));
                }
            }
        }
        self.append("--- SEALED BALLOTS ---");
        if let Some(ballots) = payload.get("revealed_ballots").and_then(Value::as_array) {
            for ballot in ballots {
                let member = ballot
                    .get("member_id")
                    .and_then(Value::as_str)
                    .unwrap_or("?");
                let choice = ballot.get("choice").and_then(Value::as_str).unwrap_or("?");
                let rationale = ballot
                    .get("rationale")
                    .and_then(Value::as_str)
                    .unwrap_or("");
                self.append(&format!("<{member}> {choice} — {rationale}"));
            }
        }
        let result = payload.get("result").and_then(Value::as_object);
        let label = result
            .and_then(|value| value.get("consensus_label"))
            .and_then(Value::as_str)
            .unwrap_or("?");
        let disposition = result
            .and_then(|value| value.get("disposition"))
            .and_then(Value::as_str)
            .unwrap_or("?");
        let evidence_state = result
            .and_then(|value| value.get("evidence_state"))
            .and_then(Value::as_str)
            .unwrap_or("?");
        self.append(&format!(
            "*** Council: {label} / {disposition} | Evidence: {evidence_state}"
        ));
        if let Some(telemetry) = payload.get("telemetry").and_then(Value::as_object) {
            self.append("--- COUNCIL TELEMETRY (OBSERVATIONAL ONLY) ---");
            if let Some(ballot) = telemetry.get("ballot_metrics").and_then(Value::as_object) {
                let entropy = ballot
                    .get("shannon_entropy_bits")
                    .and_then(Value::as_f64)
                    .unwrap_or(0.0);
                let unique = ballot
                    .get("unique_choice_count")
                    .and_then(Value::as_u64)
                    .unwrap_or(0);
                self.append(&format!(
                    "*** BALLOT: H={entropy:.3} bits | unique choices={unique}"
                ));
            }
            if let Some(phases) = telemetry.get("phase_metrics").and_then(Value::as_object) {
                for phase in ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"] {
                    if let Some(metric) = phases.get(phase).and_then(Value::as_object) {
                        let exact = metric
                            .get("exact_response_entropy_bits")
                            .and_then(Value::as_f64)
                            .unwrap_or(0.0);
                        let lexical = metric
                            .get("mean_pairwise_lexical_jaccard_distance")
                            .and_then(Value::as_f64)
                            .unwrap_or(0.0);
                        self.append(&format!(
                            "*** {phase}: H_exact={exact:.3} bits | lexical_div={lexical:.3}"
                        ));
                    }
                }
            }
            self.append(
                "*** Entropy/diversity are not truth, confidence, quality, evidence status, or vote weight."
            );
        }
        Ok(())
    }

    fn direct_message(
        &mut self,
        nexus: &mut NexusProcess,
        target: &str,
        text: &str,
    ) -> Result<(), String> {
        let member = self
            .members
            .iter()
            .find(|member| member.nick.eq_ignore_ascii_case(target))
            .cloned()
            .ok_or_else(|| format!("no such model member: {target}"))?;
        let mut evidence = self.current_evidence();
        if let Some(private_refs) = self.targeted_evidence.get(&member.nick) {
            for object_ref in private_refs {
                if !evidence.contains(object_ref) {
                    evidence.push(object_ref.clone());
                }
            }
        }
        let (text, changed) = Self::scrub_text(nexus, text)?;
        if changed {
            self.append("*** secret-bearing private message text redacted");
        }
        self.append(&format!("-> *{}* <{}> {}", member.nick, self.nick, text));
        let response = nexus.request(json!({
            "operation": "actor.chat",
            "member": member.config,
            "message": text,
            "mode": self.room.mode_id,
            "evidence_refs": evidence
        }))?;
        let reply = response
            .get("response")
            .and_then(Value::as_str)
            .unwrap_or("");
        self.append(&format!("*{}* <{}> {}", member.nick, member.nick, reply));
        Ok(())
    }

    fn execute_dcc(&mut self, nexus: &mut NexusProcess, command: DccCommand) -> Result<(), String> {
        match command {
            DccCommand::List => {
                if self.dcc_sessions.is_empty() {
                    self.append("*** DCC: no active local Direct Cognitive Channels");
                } else {
                    for session in self.dcc_sessions.clone() {
                        let kind = match session.kind {
                            DccKind::Send => "SEND",
                            DccKind::Chat => "CHAT",
                        };
                        let object = session.object_ref.unwrap_or_else(|| "-".to_string());
                        self.append(&format!(
                            "*** DCC {kind} {} {} {}",
                            session.peer, object, session.label
                        ));
                    }
                }
            }
            DccCommand::Chat { nick } => {
                let canonical = self
                    .members
                    .iter()
                    .find(|member| member.nick.eq_ignore_ascii_case(&nick))
                    .map(|member| member.nick.clone())
                    .ok_or_else(|| format!("no such model member: {nick}"))?;
                self.private_target = Some(canonical.clone());
                if !self
                    .dcc_sessions
                    .iter()
                    .any(|s| s.kind == DccKind::Chat && s.peer == canonical)
                {
                    self.dcc_sessions.push(DccSession {
                        kind: DccKind::Chat,
                        peer: canonical.clone(),
                        object_ref: None,
                        label: "private non-Council channel".to_string(),
                    });
                }
                self.append(&format!(
                    "*** DCC CHAT with {canonical} opened (non-Council)"
                ));
            }
            DccCommand::Send { target, path } => {
                if target.starts_with('#') {
                    let room = room_from_name(&target)
                        .ok_or_else(|| format!("unknown room target: {target}"))?;
                    let object_ref =
                        self.import_document(nexus, &path, room.channel, "dcc_room_send")?;
                    self.add_room_evidence(room.channel, object_ref.clone());
                    self.dcc_sessions.push(DccSession {
                        kind: DccKind::Send,
                        peer: room.channel.to_string(),
                        object_ref: Some(object_ref.clone()),
                        label: path.display().to_string(),
                    });
                    self.append(&format!(
                        "*** DCC SEND {} -> {} ({object_ref})",
                        path.display(),
                        room.channel
                    ));
                } else {
                    let member = self
                        .members
                        .iter()
                        .find(|member| member.nick.eq_ignore_ascii_case(&target))
                        .cloned()
                        .ok_or_else(|| format!("no such model member: {target}"))?;
                    let object_ref =
                        self.import_document(nexus, &path, &member.nick, "dcc_targeted_send")?;
                    self.targeted_evidence
                        .entry(member.nick.clone())
                        .or_default()
                        .push(object_ref.clone());
                    self.dcc_sessions.push(DccSession {
                        kind: DccKind::Send,
                        peer: member.nick.clone(),
                        object_ref: Some(object_ref.clone()),
                        label: path.display().to_string(),
                    });
                    self.append(&format!(
                        "*** DCC SEND {} -> {} ({object_ref}) [targeted; not Council evidence until /ref]",
                        path.display(), member.nick
                    ));
                }
            }
            DccCommand::Close { kind, nick } => {
                let wanted = if kind == "send" {
                    DccKind::Send
                } else {
                    DccKind::Chat
                };
                self.dcc_sessions.retain(|session| {
                    !(session.kind == wanted && session.peer.eq_ignore_ascii_case(&nick))
                });
                if wanted == DccKind::Chat
                    && self
                        .private_target
                        .as_deref()
                        .map(|v| v.eq_ignore_ascii_case(&nick))
                        .unwrap_or(false)
                {
                    self.private_target = None;
                }
                self.append(&format!("*** DCC {kind} channel with {nick} closed"));
            }
        }
        Ok(())
    }

    fn import_document(
        &mut self,
        nexus: &mut NexusProcess,
        path: &Path,
        target: &str,
        delivery: &str,
    ) -> Result<String, String> {
        let document = load_document(path)?;
        let filename = document.filename.clone();
        let format = document.format.clone();
        let response = nexus.request(json!({
            "operation": "world.create",
            "object_type": "document_evidence",
            "payload": document.world_payload(),
            "provenance": {
                "actor": "human_operator",
                "source": "nexus_irc_tui",
                "delivery": delivery,
                "target": target
            }
        }))?;
        let object_ref = response
            .pointer("/object/object_id")
            .and_then(Value::as_str)
            .ok_or_else(|| "world.create did not return object_id".to_string())?
            .to_string();
        self.append(&format!(
            "*** imported {filename} [{format}] as {object_ref}"
        ));
        Ok(object_ref)
    }

    fn ensure_unique_member(&self, nick: &str) -> Result<(), String> {
        if nick.trim().is_empty() {
            return Err("member nick cannot be empty".to_string());
        }
        if nick.eq_ignore_ascii_case(&self.nick)
            || self
                .members
                .iter()
                .any(|member| member.nick.eq_ignore_ascii_case(nick))
        {
            return Err(format!("nick already in use: {nick}"));
        }
        Ok(())
    }

    fn show_who(&mut self) {
        self.append(&format!(
            "*** {} users in {}",
            self.members.len() + 1,
            self.room.channel
        ));
        self.append(&format!("*** @{} [human operator]", self.nick));
        for member in self.members.clone() {
            self.append(&format!(
                "*** +{} [{}]",
                member.nick,
                member.backend_label()
            ));
        }
    }

    fn show_evidence(&mut self) {
        let refs = self.current_evidence();
        self.append(&format!(
            "*** {} Council evidence ref(s) in {}",
            refs.len(),
            self.room.channel
        ));
        for object_ref in refs {
            self.append(&format!("*** {object_ref}"));
        }
        if let Some(target) = self.private_target.clone() {
            let private_refs = self
                .targeted_evidence
                .get(&target)
                .cloned()
                .unwrap_or_default();
            self.append(&format!(
                "*** {} targeted DCC ref(s) for {target}",
                private_refs.len()
            ));
            for object_ref in private_refs {
                self.append(&format!("*** private: {object_ref}"));
            }
        }
    }

    fn show_help(&mut self) {
        for line in [
            "*** Core: /join #room | /mode mode | /topic text | /ask text | plain text = Council question",
            "*** Game: /join #un-sim | /game new [seed] | /game status | /game act ... | /game turn",
            "*** IRC: /me action | /msg nick text | /nick name | /who | /search text | /save file | /clear | /quit",
            "*** Models: /addmock nick [profile] | /addollama nick model | /kick nick",
            "*** Evidence: /upload file | /ref object:... | /unref object:... | /evidence",
            "*** DCC: /dcc send <nick|#room> <file> | /dcc chat nick | /dcc close <send|chat> nick | /dcc list",
            "*** Aliases: /alias slap /me slaps $1 with $2- | /aliases",
            "*** Variables: /set %weapon a large trout | /unset %weapon | /vars",
            "*** Identifiers: $me $chan $mode $region $topic $1..$9 $1-..$9-",
            "*** Example: /set %weapon a large trout ; /alias slap /me slaps $1 with %weapon ; /slap Grok",
            "*** TAB completes unambiguous slash commands; Up/Down recalls input; PgUp/PgDn scrolls.",
            "*** DCC means Direct Cognitive Channel here. No IRC daemon, listening socket, or peer-to-peer transfer is opened.",
        ] {
            self.append(line);
        }
    }

    fn load_state(&mut self) {
        let Ok(text) = fs::read_to_string(&self.state_path) else {
            return;
        };
        let Ok(value) = serde_json::from_str::<Value>(&text) else {
            return;
        };
        if let Some(aliases) = value.get("aliases").and_then(Value::as_object) {
            for (name, expansion) in aliases {
                if let Some(expansion) = expansion.as_str() {
                    let _ = self.aliases.define(name, expansion);
                }
            }
        }
        if let Some(variables) = value.get("variables").and_then(Value::as_object) {
            for (name, variable_value) in variables {
                if let Some(variable_value) = variable_value.as_str() {
                    let _ = self.variables.set(name, variable_value);
                }
            }
        }
    }

    fn scrub_loaded_script_state(&mut self, nexus: &mut NexusProcess) -> Result<(), String> {
        let mut clean_aliases = AliasBook::default();
        let mut clean_variables = VariableBook::default();
        let mut changed = false;

        for (name, expansion) in self.aliases.list() {
            let (clean_name, name_changed) = Self::scrub_text(nexus, &name)?;
            let (clean_expansion, expansion_changed) = Self::scrub_text(nexus, &expansion)?;
            if name_changed {
                changed = true;
                continue;
            }
            changed |= expansion_changed || clean_name != name || clean_expansion != expansion;
            clean_aliases.define(&clean_name, &clean_expansion)?;
        }

        for (name, value) in self.variables.list() {
            let (clean_name, name_changed) = Self::scrub_text(nexus, &name)?;
            let (clean_value, value_changed) = Self::scrub_text(nexus, &value)?;
            if name_changed {
                changed = true;
                continue;
            }
            changed |= value_changed || clean_name != name || clean_value != value;
            clean_variables.set(&clean_name, &clean_value)?;
        }

        self.aliases = clean_aliases;
        self.variables = clean_variables;
        if changed {
            self.save_state()?;
            self.append("*** legacy alias/variable state was scrubbed before use");
        }
        Ok(())
    }

    fn save_state(&self) -> Result<(), String> {
        if let Some(parent) = self
            .state_path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
        {
            fs::create_dir_all(parent)
                .map_err(|e| format!("cannot create {}: {e}", parent.display()))?;
        }
        let aliases: serde_json::Map<String, Value> = self
            .aliases
            .list()
            .into_iter()
            .map(|(name, expansion)| (name, Value::String(expansion)))
            .collect();
        let variables: serde_json::Map<String, Value> = self
            .variables
            .list()
            .into_iter()
            .map(|(name, value)| {
                (
                    name.trim_start_matches('%').to_string(),
                    Value::String(value),
                )
            })
            .collect();
        let state = json!({"aliases": aliases, "variables": variables});
        fs::write(
            &self.state_path,
            serde_json::to_string_pretty(&state).unwrap() + "\n",
        )
        .map_err(|e| format!("cannot save TUI state {}: {e}", self.state_path.display()))
    }

    fn handle_tab(&mut self) {
        if self.input.starts_with('/') && !self.input.contains(char::is_whitespace) {
            let mut matches: Vec<String> = command_completions(&self.input)
                .into_iter()
                .map(str::to_string)
                .collect();
            let prefix = self.input.trim_start_matches('/').to_ascii_lowercase();
            for (name, _) in self.aliases.list() {
                let candidate = format!("/{name}");
                if name.starts_with(&prefix) {
                    matches.push(candidate);
                }
            }
            matches.sort();
            matches.dedup();
            if matches.len() == 1 {
                self.input = format!("{} ", matches[0]);
            } else if !matches.is_empty() {
                self.append(&format!("*** {}", matches.join("  ")));
            }
        }
    }

    fn history_up(&mut self) {
        if self.history.is_empty() {
            return;
        }
        let index = self
            .history_index
            .unwrap_or(self.history.len())
            .saturating_sub(1);
        self.history_index = Some(index);
        self.input = self.history[index].clone();
    }

    fn history_down(&mut self) {
        let Some(index) = self.history_index else {
            return;
        };
        if index + 1 >= self.history.len() {
            self.history_index = None;
            self.input.clear();
        } else {
            self.history_index = Some(index + 1);
            self.input = self.history[index + 1].clone();
        }
    }

    fn render(&self) -> io::Result<()> {
        let (width, height) = terminal::size()?;
        let mut stdout = io::stdout();
        queue!(stdout, MoveTo(0, 0), Clear(ClearType::All))?;

        let side_width: u16 = if width >= 90 { 24 } else { 0 };
        let main_width = width
            .saturating_sub(side_width + if side_width > 0 { 1 } else { 0 })
            .max(20);
        let topic = self.current_topic();
        let status = format!(
            " NEXUS {}  mode={} region={}  topic={} ",
            self.room.channel,
            self.room.mode_id,
            self.room.region_id,
            if topic.is_empty() { "(none)" } else { topic }
        );
        queue!(stdout, MoveTo(0, 0), Print(fit(&status, width as usize)))?;

        let body_height = height.saturating_sub(3) as usize;
        let end = self
            .scrollback
            .len()
            .saturating_sub(self.scroll_offset.min(self.scrollback.len()));
        let start = end.saturating_sub(body_height);
        for (row, line) in self.scrollback[start..end].iter().enumerate() {
            queue!(
                stdout,
                MoveTo(0, (row + 1) as u16),
                Print(fit(line, main_width as usize))
            )?;
        }

        if side_width > 0 {
            let x = main_width;
            for y in 1..height.saturating_sub(1) {
                queue!(stdout, MoveTo(x, y), Print("|"))?;
            }
            let sx = x + 1;
            queue!(
                stdout,
                MoveTo(sx, 1),
                Print(fit(" USERS", side_width as usize))
            )?;
            queue!(
                stdout,
                MoveTo(sx, 2),
                Print(fit(&format!(" @{}", self.nick), side_width as usize))
            )?;
            for (index, member) in self
                .members
                .iter()
                .take(body_height.saturating_sub(4))
                .enumerate()
            {
                let marker = if self.private_target.as_deref() == Some(member.nick.as_str()) {
                    "*"
                } else {
                    "+"
                };
                queue!(
                    stdout,
                    MoveTo(sx, (index + 3) as u16),
                    Print(fit(
                        &format!(" {marker}{} [{}]", member.nick, member.backend_label()),
                        side_width as usize
                    ))
                )?;
            }
        }

        let prompt = match &self.private_target {
            Some(target) => format!(" DCC:{target}> "),
            None => format!(" {}> ", self.room.channel),
        };
        let prompt_width = UnicodeWidthStr::width(prompt.as_str());
        let input_width = width as usize - prompt_width.min(width as usize);
        queue!(
            stdout,
            MoveTo(0, height.saturating_sub(1)),
            Clear(ClearType::CurrentLine),
            Print(&prompt),
            Print(fit(&self.input, input_width))
        )?;
        let visible_input_width = UnicodeWidthStr::width(self.input.as_str()).min(input_width);
        let cursor_x =
            (prompt_width + visible_input_width).min(width.saturating_sub(1) as usize) as u16;
        queue!(stdout, MoveTo(cursor_x, height.saturating_sub(1)))?;
        stdout.flush()
    }
}

fn command_args(input: &str) -> &str {
    let trimmed = input.trim();
    let split = trimmed.find(char::is_whitespace).unwrap_or(trimmed.len());
    trimmed[split..].trim_start()
}

fn fit(text: &str, width: usize) -> String {
    if width == 0 {
        return String::new();
    }
    let display_width = UnicodeWidthStr::width(text);
    if display_width <= width {
        let mut output = text.to_string();
        output.extend(std::iter::repeat(' ').take(width - display_width));
        return output;
    }

    let ellipsis_width = UnicodeWidthChar::width('…').unwrap_or(1).min(width);
    let target = width.saturating_sub(ellipsis_width);
    let mut output = String::new();
    let mut used = 0usize;
    for ch in text.chars() {
        let char_width = UnicodeWidthChar::width(ch).unwrap_or(0);
        if used + char_width > target {
            break;
        }
        output.push(ch);
        used += char_width;
    }
    if ellipsis_width > 0 {
        output.push('…');
        used += ellipsis_width;
    }
    output.extend(std::iter::repeat(' ').take(width.saturating_sub(used)));
    output
}

fn parse_args() -> (PathBuf, PathBuf, String) {
    let mut world = PathBuf::from(".nexus-world");
    let mut state: Option<PathBuf> = None;
    let mut nick = env::var("USER").unwrap_or_else(|_| "operator".to_string());
    let args: Vec<String> = env::args().skip(1).collect();
    let mut index = 0usize;
    while index < args.len() {
        match args[index].as_str() {
            "--world" if index + 1 < args.len() => {
                world = PathBuf::from(&args[index + 1]);
                index += 2;
            }
            "--state" if index + 1 < args.len() => {
                state = Some(PathBuf::from(&args[index + 1]));
                index += 2;
            }
            "--nick" if index + 1 < args.len() => {
                nick = args[index + 1].clone();
                index += 2;
            }
            _ => index += 1,
        }
    }
    let state = state.unwrap_or_else(|| world.join("tui-state.json"));
    (world, state, nick)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (world, state, nick) = parse_args();
    let mut nexus = NexusProcess::spawn(&world).map_err(io::Error::other)?;
    let _guard = TerminalGuard::enter()?;
    let mut app = App::new(nick, state);
    app.scrub_loaded_script_state(&mut nexus)
        .map_err(io::Error::other)?;

    while app.running {
        app.render()?;
        if let Event::Key(key) = event::read()? {
            if key.modifiers.contains(KeyModifiers::CONTROL)
                && matches!(key.code, KeyCode::Char('c') | KeyCode::Char('d'))
            {
                app.running = false;
                continue;
            }
            match key.code {
                KeyCode::Char(ch) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                    app.input.push(ch)
                }
                KeyCode::Backspace => {
                    app.input.pop();
                }
                KeyCode::Enter => {
                    let line = std::mem::take(&mut app.input);
                    app.execute_line(&mut nexus, line);
                }
                KeyCode::Up => app.history_up(),
                KeyCode::Down => app.history_down(),
                KeyCode::PageUp => {
                    app.scroll_offset = app
                        .scroll_offset
                        .saturating_add(10)
                        .min(app.scrollback.len())
                }
                KeyCode::PageDown => app.scroll_offset = app.scroll_offset.saturating_sub(10),
                KeyCode::Tab => app.handle_tab(),
                KeyCode::Esc => app.private_target = None,
                _ => {}
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fit_respects_terminal_display_cells() {
        let fitted = fit("界x", 2);
        assert_eq!(UnicodeWidthStr::width(fitted.as_str()), 2);
        assert!(fitted.trim_end().ends_with('…'));
    }

    #[test]
    fn script_management_commands_preserve_placeholders_and_variable_names() {
        let mut app = App::new(
            "Trent".to_string(),
            PathBuf::from("/definitely/not/a/state/file"),
        );
        app.variables.set("%weapon", "large trout").unwrap();
        assert_eq!(
            app.preprocess("/alias slap /me slaps $1 with $2-"),
            "/alias slap /me slaps $1 with $2-"
        );
        assert_eq!(app.preprocess("/unset %weapon"), "/unset %weapon");
    }

    #[test]
    fn current_game_ref_requires_board_to_remain_shared_evidence() {
        let mut app = App::new(
            "Trent".to_string(),
            PathBuf::from("/definitely/not/a/state/file"),
        );
        app.room = room_from_name("#un-sim").expect("UN sim room");
        let game_ref = "object:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        app.set_game_ref(game_ref.to_string());
        assert_eq!(app.current_game_ref(), Some(game_ref));

        app.room_evidence
            .get_mut("#un-sim")
            .expect("room evidence")
            .retain(|value| value != game_ref);
        assert_eq!(app.current_game_ref(), None);
    }
}
