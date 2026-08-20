use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::env;
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

const MAX_OPERATOR_COUNCIL_SEATS: usize = 5;
const MAX_REMOTE_XAI_SEATS: usize = 4;

#[derive(Debug, Clone)]
struct MemberConfig {
    nick: String,
    config: Value,
}

impl MemberConfig {
    fn xai(nick: &str, model: &str, profile: &str) -> Self {
        Self {
            nick: nick.to_string(),
            config: json!({
                "member_id": nick,
                "model_id": model,
                "adapter_id": "xai",
                "auth_profile": profile,
                "timeout_seconds": 600
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

    fn adapter_id(&self) -> &str {
        self.config
            .get("adapter_id")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
    }

    fn model_id(&self) -> &str {
        self.config
            .get("model_id")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
    }

    fn profile_name(&self) -> Option<&str> {
        self.config.get("auth_profile").and_then(Value::as_str)
    }
}

struct Runtime {
    child: Child,
    stdin: BufWriter<ChildStdin>,
    stdout: BufReader<ChildStdout>,
    request_id: u64,
}

impl Runtime {
    fn spawn() -> Result<Self, String> {
        let python = env::var("NEXUS_PYTHON").unwrap_or_else(|_| "python3".to_string());
        let mut command = Command::new(&python);
        command.arg("-m").arg("nexus_runtime");
        if let Ok(auth_root) = env::var("NEXUS_AUTH_ROOT") {
            if !auth_root.trim().is_empty() {
                command.arg("--auth-root").arg(auth_root);
            }
        }
        if let Ok(world) = env::var("NEXUS_WORLD") {
            if !world.trim().is_empty() {
                command.arg("--world").arg(world);
            }
        }
        if let Ok(trap) = env::var("NEXUS_TRAP_ROOT") {
            if !trap.trim().is_empty() {
                command.arg("--trap-root").arg(trap);
            }
        }
        if let Ok(steno) = env::var("NEXUS_STENOGRAPHER_ROOT") {
            if !steno.trim().is_empty() {
                command.arg("--stenographer-root").arg(steno);
            }
        }
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());

        if let Some(pythonpath) = discover_pythonpath() {
            command.env("PYTHONPATH", pythonpath);
        }

        let mut child = command
            .spawn()
            .map_err(|error| format!("cannot start NEXUS runtime with {python}: {error}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "NEXUS runtime stdin unavailable".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "NEXUS runtime stdout unavailable".to_string())?;
        let mut runtime = Self {
            child,
            stdin: BufWriter::new(stdin),
            stdout: BufReader::new(stdout),
            request_id: 0,
        };
        runtime.request(json!({"operation": "system.health"}))?;
        Ok(runtime)
    }

    fn request(&mut self, mut request: Value) -> Result<Value, String> {
        self.request_id += 1;
        let object = request
            .as_object_mut()
            .ok_or_else(|| "internal request must be a JSON object".to_string())?;
        object.insert(
            "request_id".to_string(),
            json!(format!("alpha9-tui-{}", self.request_id)),
        );
        writeln!(self.stdin, "{request}")
            .map_err(|error| format!("cannot write NEXUS request: {error}"))?;
        self.stdin
            .flush()
            .map_err(|error| format!("cannot flush NEXUS request: {error}"))?;
        let mut line = String::new();
        let read = self
            .stdout
            .read_line(&mut line)
            .map_err(|error| format!("cannot read NEXUS response: {error}"))?;
        if read == 0 {
            return Err("NEXUS runtime closed stdout".to_string());
        }
        let response: Value = serde_json::from_str(line.trim())
            .map_err(|error| format!("invalid JSON from NEXUS runtime: {error}"))?;
        if response.get("status").and_then(Value::as_str) == Some("error") {
            let message = response
                .pointer("/error/message")
                .and_then(Value::as_str)
                .unwrap_or("unknown NEXUS runtime error");
            return Err(safe_text(message));
        }
        Ok(response)
    }
}

impl Drop for Runtime {
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
    None
}

fn safe_text(value: &str) -> String {
    value
        .chars()
        .filter(|character| !character.is_control() || *character == '\t')
        .take(1024)
        .collect()
}

fn looks_like_secret(value: &str) -> bool {
    let lower = value.to_ascii_lowercase();
    lower.contains("bearer ")
        || lower.contains("api_key=")
        || lower.contains("api-key=")
        || lower.contains("access_token=")
        || lower.contains("refresh_token=")
        || lower.contains("password=")
        || value.contains("xai-")
        || value.contains("sk-")
        || value.contains("ghp_")
        || value.contains("gsk_")
        || value.contains("hf_")
}

fn valid_identity(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || "._:-".contains(character))
}

fn valid_model(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 256
        && value
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || "._:/+-".contains(character))
}

fn help() {
    println!("NEXUS alpha9 remote operator TUI");
    println!("  help");
    println!("  auth adapters");
    println!("  auth list");
    println!("  auth test xai [profile]");
    println!("  auth add                  # prints secure external enrollment instructions");
    println!("  models xai [profile]");
    println!("  add xai <nick> <model> [profile]");
    println!("  add ollama <nick> <model>");
    println!("  add mock <nick> [profile]");
    println!("  remove <nick>");
    println!("  roster");
    println!("  ask <question>");
    println!("  quit");
    println!();
    println!("The public operator Council admits at most {MAX_OPERATOR_COUNCIL_SEATS} seats.");
    println!("Raw provider credentials are intentionally not accepted by this TUI.");
}

fn ensure_unique(roster: &BTreeMap<String, MemberConfig>, nick: &str) -> Result<(), String> {
    if !valid_identity(nick) {
        return Err("nick must be a bounded non-secret identifier".to_string());
    }
    if roster.contains_key(&nick.to_ascii_lowercase()) {
        return Err("nick is already present in the roster".to_string());
    }
    if roster.len() >= MAX_OPERATOR_COUNCIL_SEATS {
        return Err(format!(
            "public operator Council permits at most {MAX_OPERATOR_COUNCIL_SEATS} seats"
        ));
    }
    Ok(())
}

fn count_xai(roster: &BTreeMap<String, MemberConfig>) -> usize {
    roster
        .values()
        .filter(|member| member.adapter_id() == "xai")
        .count()
}

fn render_roster(roster: &BTreeMap<String, MemberConfig>) {
    if roster.is_empty() {
        println!("roster: empty");
        return;
    }
    println!(
        "roster: {} member(s), public limit {}",
        roster.len(),
        MAX_OPERATOR_COUNCIL_SEATS
    );
    for member in roster.values() {
        if let Some(profile) = member.profile_name() {
            println!(
                "  {} [{} / {} / profile={}]",
                safe_text(&member.nick),
                member.adapter_id(),
                safe_text(member.model_id()),
                safe_text(profile)
            );
        } else {
            println!(
                "  {} [{} / {}]",
                safe_text(&member.nick),
                member.adapter_id(),
                safe_text(member.model_id())
            );
        }
    }
    println!("all Council vote weights remain runtime-owned and equal to 1");
}

fn render_auth_profiles(response: &Value) {
    let profiles = response.get("profiles").and_then(Value::as_array);
    match profiles {
        Some(values) if !values.is_empty() => {
            for profile in values {
                let adapter = profile
                    .get("adapter_id")
                    .and_then(Value::as_str)
                    .unwrap_or("?");
                let name = profile
                    .get("profile_name")
                    .and_then(Value::as_str)
                    .unwrap_or("?");
                let method = profile.get("method").and_then(Value::as_str).unwrap_or("?");
                println!(
                    "{} profile={} method={}",
                    safe_text(adapter),
                    safe_text(name),
                    safe_text(method)
                );
            }
        }
        _ => println!("no configured auth profiles"),
    }
}

fn render_models(response: &Value) {
    let models = response.get("models").and_then(Value::as_array);
    match models {
        Some(values) if !values.is_empty() => {
            println!("{} remote model(s)", values.len());
            for model in values {
                if let Some(model_id) = model.get("id").and_then(Value::as_str) {
                    println!("  {}", safe_text(model_id));
                }
            }
        }
        _ => println!("no language models returned"),
    }
}

fn run_question(
    runtime: &mut Runtime,
    roster: &BTreeMap<String, MemberConfig>,
    question: &str,
) -> Result<(), String> {
    if roster.len() < 3 {
        return Err("Council requires at least three roster members".to_string());
    }
    if roster.len() > MAX_OPERATOR_COUNCIL_SEATS {
        return Err(format!(
            "public operator Council permits at most {MAX_OPERATOR_COUNCIL_SEATS} seats"
        ));
    }
    if question.trim().is_empty() || question.len() > 4096 {
        return Err("question must be non-empty and at most 4096 characters".to_string());
    }
    if looks_like_secret(question) {
        return Err("credential-shaped text is not accepted as a Council question".to_string());
    }
    let members: Vec<Value> = roster
        .values()
        .map(|member| member.config.clone())
        .collect();
    let response = runtime.request(json!({
        "operation": "council.run",
        "question": question,
        "mode_id": "analytical",
        "evidence_state": "UNTESTED",
        "members": members
    }))?;
    let session_ref = response
        .get("session_ref")
        .and_then(Value::as_str)
        .unwrap_or("?");
    let receipt_ref = response
        .get("receipt_ref")
        .and_then(Value::as_str)
        .unwrap_or("?");
    let label = response
        .pointer("/result/consensus_label")
        .and_then(Value::as_str)
        .unwrap_or("?");
    let disposition = response
        .pointer("/result/disposition")
        .and_then(Value::as_str)
        .unwrap_or("?");
    println!("session_ref={}", safe_text(session_ref));
    println!("receipt_ref={}", safe_text(receipt_ref));
    println!("consensus_label={}", safe_text(label));
    println!("disposition={}", safe_text(disposition));
    println!("remote provider identity confers no additional vote weight or epistemic privilege");
    Ok(())
}

fn handle_line(
    runtime: &mut Runtime,
    roster: &mut BTreeMap<String, MemberConfig>,
    line: &str,
) -> Result<bool, String> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return Ok(true);
    }
    if looks_like_secret(trimmed) {
        return Err(
            "credential-shaped text rejected; enroll credentials with `python3 -m nexus_runtime auth add ...` outside the TUI"
                .to_string(),
        );
    }
    let mut words = trimmed.split_whitespace();
    let raw_command = words.next().unwrap_or("");
    let command = raw_command.to_ascii_lowercase();
    match command.as_str() {
        "help" | "?" => help(),
        "quit" | "exit" => return Ok(false),
        "roster" => render_roster(roster),
        "remove" => {
            let nick = words
                .next()
                .ok_or_else(|| "usage: remove <nick>".to_string())?;
            if roster.remove(&nick.to_ascii_lowercase()).is_some() {
                println!("removed {}", safe_text(nick));
            } else {
                println!("{} was not in the roster", safe_text(nick));
            }
        }
        "auth" => {
            let action = words.next().unwrap_or("").to_ascii_lowercase();
            match action.as_str() {
                "adapters" => {
                    let response = runtime.request(json!({"operation": "auth.adapters"}))?;
                    println!("{}", safe_text(&response.to_string()));
                }
                "list" => {
                    let response = runtime.request(json!({"operation": "auth.list"}))?;
                    render_auth_profiles(&response);
                }
                "test" => {
                    let adapter = words.next().unwrap_or("xai");
                    let profile = words.next().unwrap_or("default");
                    if words.next().is_some() || adapter != "xai" || !valid_identity(profile) {
                        return Err("usage: auth test xai [profile]".to_string());
                    }
                    let response = runtime.request(json!({
                        "operation": "auth.test",
                        "adapter_id": "xai",
                        "profile_name": profile
                    }))?;
                    println!(
                        "xai profile={} status={}",
                        safe_text(profile),
                        safe_text(
                            response
                                .get("status")
                                .and_then(Value::as_str)
                                .unwrap_or("ok")
                        )
                    );
                }
                "add" => {
                    println!("credential enrollment is deliberately outside this TUI");
                    println!("use one of:");
                    println!("  python3 -m nexus_runtime auth add xai --method browser-key");
                    println!("  python3 -m nexus_runtime auth add xai --method api-key");
                    println!(
                        "  python3 -m nexus_runtime auth add xai --method env --env XAI_API_KEY"
                    );
                    println!("the hidden prompt/environment/helper boundary keeps credential bytes out of TUI history and world state");
                }
                _ => return Err("usage: auth adapters|list|test|add".to_string()),
            }
        }
        "models" => {
            let adapter = words.next().unwrap_or("xai");
            let profile = words.next().unwrap_or("default");
            if words.next().is_some() || adapter != "xai" || !valid_identity(profile) {
                return Err("usage: models xai [profile]".to_string());
            }
            let response = runtime.request(json!({
                "operation": "models.list",
                "adapter_id": "xai",
                "profile_name": profile,
                "timeout_seconds": 120
            }))?;
            render_models(&response);
        }
        "add" => {
            let adapter = words
                .next()
                .ok_or_else(|| "usage: add xai|ollama|mock ...".to_string())?;
            match adapter.to_ascii_lowercase().as_str() {
                "xai" => {
                    let nick = words
                        .next()
                        .ok_or_else(|| "usage: add xai <nick> <model> [profile]".to_string())?;
                    let model = words
                        .next()
                        .ok_or_else(|| "usage: add xai <nick> <model> [profile]".to_string())?;
                    let profile = words.next().unwrap_or("default");
                    if words.next().is_some() || !valid_model(model) || !valid_identity(profile) {
                        return Err("usage: add xai <nick> <model> [profile]".to_string());
                    }
                    ensure_unique(roster, nick)?;
                    if count_xai(roster) >= MAX_REMOTE_XAI_SEATS {
                        return Err(format!(
                            "Council permits at most {MAX_REMOTE_XAI_SEATS} remote xAI seats"
                        ));
                    }
                    roster.insert(
                        nick.to_ascii_lowercase(),
                        MemberConfig::xai(nick, model, profile),
                    );
                    println!(
                        "added {} [xai/{} profile={}]",
                        safe_text(nick),
                        safe_text(model),
                        safe_text(profile)
                    );
                }
                "ollama" => {
                    let nick = words
                        .next()
                        .ok_or_else(|| "usage: add ollama <nick> <model>".to_string())?;
                    let model = words
                        .next()
                        .ok_or_else(|| "usage: add ollama <nick> <model>".to_string())?;
                    if words.next().is_some() || !valid_model(model) {
                        return Err("usage: add ollama <nick> <model>".to_string());
                    }
                    ensure_unique(roster, nick)?;
                    roster.insert(nick.to_ascii_lowercase(), MemberConfig::ollama(nick, model));
                    println!("added {} [ollama/{}]", safe_text(nick), safe_text(model));
                }
                "mock" => {
                    let nick = words
                        .next()
                        .ok_or_else(|| "usage: add mock <nick> [profile]".to_string())?;
                    let profile = words.next().unwrap_or("balanced");
                    if words.next().is_some() || !valid_identity(profile) {
                        return Err("usage: add mock <nick> [profile]".to_string());
                    }
                    ensure_unique(roster, nick)?;
                    roster.insert(nick.to_ascii_lowercase(), MemberConfig::mock(nick, profile));
                    println!("added {} [mock/{}]", safe_text(nick), safe_text(profile));
                }
                _ => return Err("usage: add xai|ollama|mock ...".to_string()),
            }
        }
        "ask" => {
            let question = trimmed.get(raw_command.len()..).unwrap_or("").trim();
            run_question(runtime, roster, question)?;
        }
        _ => return Err("unknown command; type `help`".to_string()),
    }
    Ok(true)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut runtime = Runtime::spawn().map_err(io::Error::other)?;
    let mut roster: BTreeMap<String, MemberConfig> = BTreeMap::new();
    println!("NEXUS alpha9 remote operator TUI");
    println!("fixed-destination xAI + loopback Ollama + deterministic mock roster setup");
    println!("type `help`; raw credentials are never accepted here");

    let stdin = io::stdin();
    loop {
        print!("alpha9> ");
        io::stdout().flush()?;
        let mut line = String::new();
        if stdin.read_line(&mut line)? == 0 {
            break;
        }
        match handle_line(&mut runtime, &mut roster, &line) {
            Ok(true) => {}
            Ok(false) => break,
            Err(error) => eprintln!("error: {}", safe_text(&error)),
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn xai_roster_entry_contains_profile_reference_not_credential() {
        let member = MemberConfig::xai("Remote", "grok-4.5", "research");
        assert_eq!(member.adapter_id(), "xai");
        assert_eq!(member.model_id(), "grok-4.5");
        assert_eq!(member.profile_name(), Some("research"));
        let rendered = member.config.to_string();
        assert!(!rendered.contains("api_key"));
        assert!(!rendered.contains("authorization"));
        assert!(!rendered.contains("bearer"));
    }

    #[test]
    fn credential_shapes_are_rejected_by_local_input_guard() {
        assert!(looks_like_secret(&format!("xai-{}", "A".repeat(32))));
        assert!(looks_like_secret(&format!("sk-{}", "A".repeat(32))));
        assert!(looks_like_secret("Bearer abcdefghijklmnopqrstuvwxyz"));
        assert!(!looks_like_secret("add xai Grok grok-4.5 research"));
    }

    #[test]
    fn remote_seat_count_is_bounded() {
        let mut roster = BTreeMap::new();
        for index in 0..MAX_REMOTE_XAI_SEATS {
            let nick = format!("R{index}");
            roster.insert(
                nick.to_ascii_lowercase(),
                MemberConfig::xai(&nick, "grok-4.5", "default"),
            );
        }
        assert_eq!(count_xai(&roster), MAX_REMOTE_XAI_SEATS);
    }

    #[test]
    fn public_operator_roster_matches_five_seat_chair_limit() {
        let mut roster = BTreeMap::new();
        for index in 0..MAX_OPERATOR_COUNCIL_SEATS {
            let nick = format!("M{index}");
            roster.insert(
                nick.to_ascii_lowercase(),
                MemberConfig::mock(&nick, "balanced"),
            );
        }
        let error = ensure_unique(&roster, "Sixth").expect_err("sixth seat must fail closed");
        assert!(error.contains("at most 5 seats"));
    }

    #[test]
    fn identities_and_models_use_closed_safe_character_sets() {
        assert!(valid_identity("profile-1"));
        assert!(!valid_identity("../profile"));
        assert!(valid_model("grok-4.5"));
        assert!(valid_model("qwen2.5:7b"));
        assert!(!valid_model("model with spaces"));
    }
}
