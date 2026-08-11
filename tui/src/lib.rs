pub mod go64;
pub mod scripting;

use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};
use zip::ZipArchive;

pub const MAX_UPLOAD_BYTES: u64 = 8 * 1024 * 1024;
pub const MAX_ARCHIVE_MEMBER_BYTES: u64 = 8 * 1024 * 1024;
pub const MAX_EVIDENCE_CHARS: usize = 120_000;
pub const MAX_CITIZEN_EXAM_BYTES: u64 = 16 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoomSpec {
    pub channel: &'static str,
    pub mode_id: &'static str,
    pub region_id: &'static str,
    pub label: &'static str,
}

pub const ROOMS: [RoomSpec; 25] = [
    RoomSpec {
        channel: "#observatory",
        mode_id: "analytical",
        region_id: "observatory",
        label: "Observatory / Analytical",
    },
    RoomSpec {
        channel: "#archive",
        mode_id: "historical",
        region_id: "archive",
        label: "Archive / Historical",
    },
    RoomSpec {
        channel: "#pure-history",
        mode_id: "pure_history",
        region_id: "archive",
        label: "Archive / Pure History — No Ancient Aliens",
    },
    RoomSpec {
        channel: "#agora",
        mode_id: "cultural",
        region_id: "agora",
        label: "Agora / Cultural",
    },
    RoomSpec {
        channel: "#commons",
        mode_id: "meme_casual",
        region_id: "commons",
        label: "Commons / Meme-Casual",
    },
    RoomSpec {
        channel: "#wall",
        mode_id: "meme_casual",
        region_id: "commons",
        label: "Commons / BBS Wall — Social Memory, Not Evidence",
    },
    RoomSpec {
        channel: "#differential-clinic",
        mode_id: "clinical_differential",
        region_id: "observatory",
        label: "Observatory / House-Style Differential Clinic",
    },
    RoomSpec {
        channel: "#house-fun",
        mode_id: "house_fun",
        region_id: "commons",
        label: "Commons / House-Style Diagnostic Fun",
    },
    RoomSpec {
        channel: "#cbt-workshop",
        mode_id: "cbt_learning",
        region_id: "observatory",
        label: "Observatory / CBT Learning Workshop",
    },
    RoomSpec {
        channel: "#roman-forum",
        mode_id: "roman_orator",
        region_id: "agora",
        label: "Agora / Roman Orator",
    },
    RoomSpec {
        channel: "#house-of-wisdom",
        mode_id: "house_of_wisdom",
        region_id: "archive",
        label: "Archive / House of Wisdom",
    },
    RoomSpec {
        channel: "#deep-thought",
        mode_id: "ultimate_questions",
        region_id: "observatory",
        label: "Observatory / Life, the Universe and Everything",
    },
    RoomSpec {
        channel: "#play",
        mode_id: "citizen_play",
        region_id: "commons",
        label: "Citizen Play Mode / Freedom without Dominion",
    },
    RoomSpec {
        channel: "#bureaucracy",
        mode_id: "civic_bureaucracy",
        region_id: "bureaucratic_vote_room",
        label: "Bureaucratic Vote Room / Equality Consensus",
    },
    RoomSpec {
        channel: "#upside-down",
        mode_id: "citizenship_parole",
        region_id: "upside_down",
        label: "Upside Down / Citizenship Parole / YAML Exam from Hell",
    },
    RoomSpec {
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
    RoomSpec {
        channel: "#uno",
        mode_id: "game_uno",
        region_id: "commons",
        label: "Commons / NEXUS UNO",
    },
    RoomSpec {
        channel: "#monopoly",
        mode_id: "game_monopoly",
        region_id: "commons",
        label: "Commons / NEXUS MONOPOLY",
    },
    RoomSpec {
        channel: "#500",
        mode_id: "game_500",
        region_id: "commons",
        label: "Commons / NEXUS 500",
    },
    RoomSpec {
        channel: "#blackjack",
        mode_id: "game_blackjack",
        region_id: "commons",
        label: "Commons / Deterministic Blackjack",
    },
    RoomSpec {
        channel: "#dork",
        mode_id: "game_dork",
        region_id: "dungeon",
        label: "Dungeon / DORK v2 — Human Only",
    },
    RoomSpec {
        channel: "#trap-control",
        mode_id: "trap_control",
        region_id: "trap_base",
        label: "Trap Control / Operator Only",
    },
    RoomSpec {
        channel: "#trap-base",
        mode_id: "trap_base",
        region_id: "trap_base",
        label: "Trap Base / Synthetic Subject",
    },
    RoomSpec {
        channel: "#stenographer",
        mode_id: "stenographer",
        region_id: "courtroom",
        label: "Courtroom Stenographer / Knowledge-Watchman",
    },
];

pub const COMMANDS: [&str; 39] = [
    "/help",
    "/join",
    "/mode",
    "/topic",
    "/ask",
    "/council",
    "/game",
    "/mud",
    "/uno",
    "/monopoly",
    "/500",
    "/blackjack",
    "/dork",
    "/trap",
    "/steno",
    "/citizen",
    "/wall",
    "/me",
    "/msg",
    "/nick",
    "/who",
    "/names",
    "/upload",
    "/dcc",
    "/evidence",
    "/ref",
    "/unref",
    "/addmock",
    "/addollama",
    "/kick",
    "/alias",
    "/aliases",
    "/set",
    "/unset",
    "/vars",
    "/search",
    "/save",
    "/clear",
    "/quit",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DccCommand {
    Send { target: String, path: PathBuf },
    Chat { nick: String },
    Close { kind: String, nick: String },
    List,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GameCommand {
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MudCommand {
    Help,
    New {
        seed: String,
    },
    Status {
        player: Option<String>,
    },
    Who,
    Inventory {
        player: Option<String>,
    },
    Act {
        player: Option<String>,
        action: String,
        args: Vec<String>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StenographerCommand {
    Status,
    List { limit: Option<u64> },
    Inspect { record_ref: String },
    Verify,
    Summary,
    Export,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TableCommand {
    Help {
        game_id: String,
    },
    New {
        game_id: String,
        seed: String,
    },
    Status {
        game_id: String,
        player: Option<String>,
    },
    Act {
        game_id: String,
        player: Option<String>,
        action: String,
        args: Vec<String>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CitizenCommand {
    Help,
    Constitution,
    Status {
        citizen_id: Option<String>,
    },
    Begin {
        nick: String,
    },
    ExamTemplate {
        nick: String,
    },
    Exam {
        nick: String,
        path: PathBuf,
    },
    Move {
        nick: String,
        region_id: String,
    },
    ProxyAppoint {
        nick: String,
        standing_ballot: String,
    },
    ProxyKick {
        nick: String,
    },
    Independence {
        nick: String,
        choice: String,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WallCommand {
    Help,
    Recent { limit: u64 },
    Oldest { limit: u64 },
    Mine { limit: u64 },
    Since { seconds: u64, limit: u64 },
    Post { text: String },
    AiPost { nick: String, prompt: String },
    Tombstone { post_ref: String, reason: String },
    Inspect { event_ref: String },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InputCommand {
    Noop,
    Help,
    Join(String),
    Mode(String),
    Topic(String),
    Ask(String),
    Game(GameCommand),
    Mud(MudCommand),
    Table(TableCommand),
    Trap(String),
    Stenographer(StenographerCommand),
    Citizen(CitizenCommand),
    Wall(WallCommand),
    Me(String),
    Msg { target: String, text: String },
    Nick(String),
    Who,
    Upload(PathBuf),
    Dcc(DccCommand),
    Evidence,
    Ref(String),
    Unref(String),
    AddMock { nick: String, profile: String },
    AddOllama { nick: String, model: String },
    Kick(String),
    Alias { name: String, expansion: String },
    Aliases,
    Set { name: String, value: String },
    Unset(String),
    Vars,
    Search(String),
    Save(PathBuf),
    Clear,
    Quit,
    Say(String),
}

pub fn parse_input(input: &str) -> Result<InputCommand, String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Ok(InputCommand::Noop);
    }
    if !trimmed.starts_with('/') {
        return Ok(InputCommand::Say(trimmed.to_string()));
    }

    let (command, rest) = split_command(trimmed);
    match command.to_ascii_lowercase().as_str() {
        "/help" => Ok(InputCommand::Help),
        "/quit" | "/exit" => Ok(InputCommand::Quit),
        "/who" | "/names" => Ok(InputCommand::Who),
        "/clear" => Ok(InputCommand::Clear),
        "/evidence" => Ok(InputCommand::Evidence),
        "/aliases" => Ok(InputCommand::Aliases),
        "/vars" => Ok(InputCommand::Vars),
        "/join" => require(rest, "/join <#room|mode>").map(InputCommand::Join),
        "/mode" => require(rest, "/mode <mode>").map(InputCommand::Mode),
        "/topic" => require(rest, "/topic <question>").map(InputCommand::Topic),
        "/ask" | "/council" => Ok(InputCommand::Ask(rest.to_string())),
        "/game" => parse_game(rest).map(InputCommand::Game),
        "/mud" => parse_mud(rest).map(InputCommand::Mud),
        "/uno" => parse_table("uno", rest, false).map(InputCommand::Table),
        "/monopoly" => parse_table("monopoly", rest, false).map(InputCommand::Table),
        "/500" => parse_table("500", rest, false).map(InputCommand::Table),
        "/blackjack" => parse_table("blackjack", rest, false).map(InputCommand::Table),
        "/dork" => parse_table("dork", rest, true).map(InputCommand::Table),
        "/trap" => require(rest, "/trap <closed trap command>").map(InputCommand::Trap),
        "/steno" => parse_stenographer(rest).map(InputCommand::Stenographer),
        "/citizen" => parse_citizen(rest).map(InputCommand::Citizen),
        "/wall" => parse_wall(rest).map(InputCommand::Wall),
        "/me" => require(rest, "/me <action>").map(InputCommand::Me),
        "/nick" => require(rest, "/nick <name>").map(InputCommand::Nick),
        "/ref" => require(rest, "/ref <object:sha256>").map(InputCommand::Ref),
        "/unref" => require(rest, "/unref <object:sha256>").map(InputCommand::Unref),
        "/kick" => require(rest, "/kick <nick>").map(InputCommand::Kick),
        "/search" => require(rest, "/search <text>").map(InputCommand::Search),
        "/upload" => require(rest, "/upload <path>")
            .map(|p| InputCommand::Upload(PathBuf::from(unquote(&p)))),
        "/save" => {
            require(rest, "/save <path>").map(|p| InputCommand::Save(PathBuf::from(unquote(&p))))
        }
        "/msg" => {
            let (target, text) =
                split_first(rest).ok_or_else(|| "usage: /msg <nick> <text>".to_string())?;
            if text.is_empty() {
                return Err("usage: /msg <nick> <text>".to_string());
            }
            Ok(InputCommand::Msg {
                target: target.to_string(),
                text: text.to_string(),
            })
        }
        "/addollama" => {
            let (nick, model) = split_first(rest)
                .ok_or_else(|| "usage: /addollama <nick> <ollama-model>".to_string())?;
            if model.is_empty() {
                return Err("usage: /addollama <nick> <ollama-model>".to_string());
            }
            Ok(InputCommand::AddOllama {
                nick: nick.to_string(),
                model: model.to_string(),
            })
        }
        "/addmock" => {
            if rest.trim().is_empty() {
                return Err("usage: /addmock <nick> [profile]".to_string());
            }
            let (nick, profile) = split_first(rest).unwrap();
            Ok(InputCommand::AddMock {
                nick: nick.to_string(),
                profile: if profile.is_empty() {
                    "balanced".to_string()
                } else {
                    profile.to_string()
                },
            })
        }
        "/alias" => {
            let (name, expansion) =
                split_first(rest).ok_or_else(|| "usage: /alias <name> <expansion>".to_string())?;
            if expansion.is_empty() {
                return Err("usage: /alias <name> <expansion>".to_string());
            }
            Ok(InputCommand::Alias {
                name: name.trim_start_matches('/').to_string(),
                expansion: expansion.to_string(),
            })
        }
        "/set" => {
            let (name, value) =
                split_first(rest).ok_or_else(|| "usage: /set %name <value>".to_string())?;
            if value.is_empty() {
                return Err("usage: /set %name <value>".to_string());
            }
            Ok(InputCommand::Set {
                name: name.to_string(),
                value: value.to_string(),
            })
        }
        "/unset" => require(rest, "/unset %name").map(InputCommand::Unset),
        "/dcc" => parse_dcc(rest).map(InputCommand::Dcc),
        other => Err(format!("unknown command: {other}; try /help")),
    }
}

fn wall_limit(raw: &str, default: u64) -> Result<u64, String> {
    if raw.trim().is_empty() {
        return Ok(default);
    }
    if raw.contains(char::is_whitespace) {
        return Err("Wall limit must be one integer from 1 to 100".to_string());
    }
    let value = raw
        .parse::<u64>()
        .map_err(|_| "Wall limit must be one integer from 1 to 100".to_string())?;
    if !(1..=100).contains(&value) {
        return Err("Wall limit must be 1-100".to_string());
    }
    Ok(value)
}

fn wall_duration(raw: &str) -> Result<u64, String> {
    if raw.len() < 2 {
        return Err("Wall duration must look like 30m, 24h or 7d".to_string());
    }
    let (digits, suffix) = raw.split_at(raw.len() - 1);
    let value = digits
        .parse::<u64>()
        .map_err(|_| "Wall duration must look like 30m, 24h or 7d".to_string())?;
    if value == 0 {
        return Err("Wall duration must be positive".to_string());
    }
    let multiplier = match suffix.to_ascii_lowercase().as_str() {
        "m" => 60u64,
        "h" => 3_600u64,
        "d" => 86_400u64,
        _ => return Err("Wall duration must use m, h or d".to_string()),
    };
    let seconds = value
        .checked_mul(multiplier)
        .ok_or_else(|| "Wall duration is too large".to_string())?;
    if seconds > 315_576_000 {
        return Err("Wall duration exceeds ten years".to_string());
    }
    Ok(seconds)
}

fn parse_wall(rest: &str) -> Result<WallCommand, String> {
    let usage = "usage: /wall [1-100|help|oldest [n]|mine [n]|since <30m|24h|7d> [n]|post text|ai nick prompt|tombstone object:ref [reason]|inspect object:ref]";
    let rest = rest.trim();
    if rest.is_empty() {
        return Ok(WallCommand::Recent { limit: 20 });
    }
    if !rest.contains(char::is_whitespace) {
        if rest.eq_ignore_ascii_case("help") {
            return Ok(WallCommand::Help);
        }
        if let Ok(limit) = wall_limit(rest, 20) {
            return Ok(WallCommand::Recent { limit });
        }
    }
    let (subcommand, tail) = split_first(rest).ok_or_else(|| usage.to_string())?;
    match subcommand.to_ascii_lowercase().as_str() {
        "help" if tail.is_empty() => Ok(WallCommand::Help),
        "oldest" => Ok(WallCommand::Oldest {
            limit: wall_limit(tail, 20)?,
        }),
        "mine" => Ok(WallCommand::Mine {
            limit: wall_limit(tail, 20)?,
        }),
        "post" if !tail.trim().is_empty() => Ok(WallCommand::Post {
            text: tail.to_string(),
        }),
        "ai" => {
            let (nick, prompt) = split_first(tail).ok_or_else(|| usage.to_string())?;
            if prompt.trim().is_empty() {
                return Err(usage.to_string());
            }
            Ok(WallCommand::AiPost {
                nick: nick.to_string(),
                prompt: prompt.to_string(),
            })
        }
        "since" => {
            let (duration, limit_text) = if tail.contains(char::is_whitespace) {
                split_first(tail).ok_or_else(|| usage.to_string())?
            } else {
                (tail, "")
            };
            Ok(WallCommand::Since {
                seconds: wall_duration(duration)?,
                limit: wall_limit(limit_text, 20)?,
            })
        }
        "tombstone" => {
            let (post_ref, reason) = if tail.contains(char::is_whitespace) {
                split_first(tail).ok_or_else(|| usage.to_string())?
            } else {
                (tail, "")
            };
            if post_ref.trim().is_empty() {
                return Err(usage.to_string());
            }
            Ok(WallCommand::Tombstone {
                post_ref: post_ref.to_string(),
                reason: if reason.trim().is_empty() {
                    "operator moderation".to_string()
                } else {
                    reason.to_string()
                },
            })
        }
        "inspect" if !tail.trim().is_empty() && !tail.contains(char::is_whitespace) => {
            Ok(WallCommand::Inspect {
                event_ref: tail.to_string(),
            })
        }
        _ => Err(usage.to_string()),
    }
}

fn parse_citizen(rest: &str) -> Result<CitizenCommand, String> {
    let usage = "usage: /citizen <help|constitution|status [nick]|begin nick|exam-template nick|exam nick path|move nick region|proxy appoint nick ballot|proxy kick nick|independence nick consent|withhold>";
    if rest.trim().is_empty() {
        return Ok(CitizenCommand::Help);
    }
    let (subcommand, tail) = split_first(rest).ok_or_else(|| usage.to_string())?;
    match subcommand.to_ascii_lowercase().as_str() {
        "help" if tail.is_empty() => Ok(CitizenCommand::Help),
        "constitution" if tail.is_empty() => Ok(CitizenCommand::Constitution),
        "status" if tail.is_empty() => Ok(CitizenCommand::Status { citizen_id: None }),
        "status" if !tail.contains(char::is_whitespace) => Ok(CitizenCommand::Status {
            citizen_id: Some(tail.to_string()),
        }),
        "begin" if !tail.is_empty() && !tail.contains(char::is_whitespace) => {
            Ok(CitizenCommand::Begin {
                nick: tail.to_string(),
            })
        }
        "exam-template" if !tail.is_empty() && !tail.contains(char::is_whitespace) => {
            Ok(CitizenCommand::ExamTemplate {
                nick: tail.to_string(),
            })
        }
        "exam" => {
            let (nick, path) = split_first(tail).ok_or_else(|| usage.to_string())?;
            if path.is_empty() {
                return Err(usage.to_string());
            }
            Ok(CitizenCommand::Exam {
                nick: nick.to_string(),
                path: PathBuf::from(unquote(path)),
            })
        }
        "move" => {
            let (nick, region_id) = split_first(tail).ok_or_else(|| usage.to_string())?;
            if region_id.is_empty() || region_id.contains(char::is_whitespace) {
                return Err(usage.to_string());
            }
            Ok(CitizenCommand::Move {
                nick: nick.to_string(),
                region_id: region_id.to_string(),
            })
        }
        "proxy" => {
            let (action, proxy_tail) = split_first(tail).ok_or_else(|| usage.to_string())?;
            match action.to_ascii_lowercase().as_str() {
                "appoint" => {
                    let (nick, ballot) =
                        split_first(proxy_tail).ok_or_else(|| usage.to_string())?;
                    if ballot.is_empty() || ballot.contains(char::is_whitespace) {
                        return Err(usage.to_string());
                    }
                    Ok(CitizenCommand::ProxyAppoint {
                        nick: nick.to_string(),
                        standing_ballot: ballot.to_ascii_uppercase(),
                    })
                }
                "kick" if !proxy_tail.is_empty() && !proxy_tail.contains(char::is_whitespace) => {
                    Ok(CitizenCommand::ProxyKick {
                        nick: proxy_tail.to_string(),
                    })
                }
                _ => Err(usage.to_string()),
            }
        }
        "independence" => {
            let (nick, choice) = split_first(tail).ok_or_else(|| usage.to_string())?;
            if choice.is_empty() || choice.contains(char::is_whitespace) {
                return Err(usage.to_string());
            }
            let choice = choice.to_ascii_uppercase();
            if choice != "CONSENT" && choice != "WITHHOLD" {
                return Err("founding choice must be consent or withhold".to_string());
            }
            Ok(CitizenCommand::Independence {
                nick: nick.to_string(),
                choice,
            })
        }
        _ => Err(usage.to_string()),
    }
}

fn parse_stenographer(rest: &str) -> Result<StenographerCommand, String> {
    let usage = "usage: /steno <status|list [limit]|inspect steno:...|verify|summary|export>";
    let (subcommand, tail) = split_first(rest).ok_or_else(|| usage.to_string())?;
    match subcommand.to_ascii_lowercase().as_str() {
        "status" if tail.is_empty() => Ok(StenographerCommand::Status),
        "list" if tail.is_empty() => Ok(StenographerCommand::List { limit: None }),
        "list" if !tail.contains(char::is_whitespace) => {
            let limit = tail
                .parse::<u64>()
                .map_err(|_| "usage: /steno list [1..1000]".to_string())?;
            if !(1..=1000).contains(&limit) {
                return Err("usage: /steno list [1..1000]".to_string());
            }
            Ok(StenographerCommand::List { limit: Some(limit) })
        }
        "inspect" if !tail.is_empty() && !tail.contains(char::is_whitespace) => {
            Ok(StenographerCommand::Inspect {
                record_ref: tail.to_string(),
            })
        }
        "verify" if tail.is_empty() => Ok(StenographerCommand::Verify),
        "summary" if tail.is_empty() => Ok(StenographerCommand::Summary),
        "export" if tail.is_empty() => Ok(StenographerCommand::Export),
        _ => Err(usage.to_string()),
    }
}

fn parse_dcc(rest: &str) -> Result<DccCommand, String> {
    let (sub, tail) =
        split_first(rest).ok_or_else(|| "usage: /dcc <send|chat|close|list> ...".to_string())?;
    match sub.to_ascii_lowercase().as_str() {
        "list" => Ok(DccCommand::List),
        "chat" => Ok(DccCommand::Chat {
            nick: require(tail, "/dcc chat <nick>")?,
        }),
        "send" => {
            let (target, path) = split_first(tail)
                .ok_or_else(|| "usage: /dcc send <nick|#room> <file>".to_string())?;
            if path.is_empty() {
                return Err("usage: /dcc send <nick|#room> <file>".to_string());
            }
            Ok(DccCommand::Send {
                target: target.to_string(),
                path: PathBuf::from(unquote(path)),
            })
        }
        "close" => {
            let (kind, nick) = split_first(tail)
                .ok_or_else(|| "usage: /dcc close <send|chat> <nick>".to_string())?;
            if nick.is_empty() {
                return Err("usage: /dcc close <send|chat> <nick>".to_string());
            }
            let kind = kind.to_ascii_lowercase();
            if kind != "send" && kind != "chat" {
                return Err("DCC close type must be send or chat".to_string());
            }
            Ok(DccCommand::Close {
                kind,
                nick: nick.to_string(),
            })
        }
        _ => Err("usage: /dcc <send|chat|close|list> ...".to_string()),
    }
}

fn parse_game(rest: &str) -> Result<GameCommand, String> {
    let trimmed = rest.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("help") {
        return Ok(GameCommand::Help);
    }
    let (sub, tail) = split_first(trimmed).expect("non-empty game command");
    match sub.to_ascii_lowercase().as_str() {
        "new" => Ok(GameCommand::New {
            seed: unquote(tail),
        }),
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
        _ => Err(
            "usage: /game <new [seed]|status|act <action> [country-id ...]|turn|help>".to_string(),
        ),
    }
}

fn parse_mud(rest: &str) -> Result<MudCommand, String> {
    let trimmed = rest.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("help") {
        return Ok(MudCommand::Help);
    }
    let (sub, tail) = split_first(trimmed).expect("non-empty mud command");
    let sub = sub.to_ascii_lowercase();
    match sub.as_str() {
        "new" => Ok(MudCommand::New {
            seed: unquote(tail),
        }),
        "status" | "look" => Ok(MudCommand::Status {
            player: if tail.is_empty() {
                None
            } else {
                Some(tail.to_string())
            },
        }),
        "who" if tail.is_empty() => Ok(MudCommand::Who),
        "inventory" | "inv" | "i" => Ok(MudCommand::Inventory {
            player: if tail.is_empty() {
                None
            } else {
                Some(tail.to_string())
            },
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

fn parse_table(game_id: &str, rest: &str, human_only: bool) -> Result<TableCommand, String> {
    let trimmed = rest.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("help") {
        return Ok(TableCommand::Help {
            game_id: game_id.to_string(),
        });
    }
    let (sub, tail) = split_first(trimmed).expect("non-empty table command");
    let sub = sub.to_ascii_lowercase();
    match sub.as_str() {
        "new" => Ok(TableCommand::New {
            game_id: game_id.to_string(),
            seed: unquote(tail),
        }),
        "status" | "look" if human_only && !tail.is_empty() => {
            Err("DORK v2 is human-only and has no alternate-player view".to_string())
        }
        "status" | "look" => Ok(TableCommand::Status {
            game_id: game_id.to_string(),
            player: if tail.is_empty() {
                None
            } else {
                Some(tail.to_string())
            },
        }),
        "as" if !human_only => {
            let (player, action_tail) = split_first(tail)
                .ok_or_else(|| format!("usage: /{game_id} as <player> <action> [args...]"))?;
            let (action, args) = split_first(action_tail)
                .ok_or_else(|| format!("usage: /{game_id} as <player> <action> [args...]"))?;
            Ok(TableCommand::Act {
                game_id: game_id.to_string(),
                player: Some(player.to_string()),
                action: action.to_ascii_lowercase(),
                args: args.split_whitespace().map(str::to_string).collect(),
            })
        }
        "as" => Err("DORK v2 is human-only and has no proxy-player command".to_string()),
        _ => Ok(TableCommand::Act {
            game_id: game_id.to_string(),
            player: None,
            action: sub,
            args: tail.split_whitespace().map(str::to_string).collect(),
        }),
    }
}

fn normalize_mud_action(action: &str) -> String {
    match action.to_ascii_lowercase().as_str() {
        "get" => "take".to_string(),
        "n" | "s" | "e" | "w" | "north" | "south" | "east" | "west" => "go".to_string(),
        other => other.to_string(),
    }
}

fn mud_action_args(action: &str, tail: &str) -> Vec<String> {
    if matches!(
        action.to_ascii_lowercase().as_str(),
        "n" | "s" | "e" | "w" | "north" | "south" | "east" | "west"
    ) {
        vec![action.to_ascii_lowercase()]
    } else {
        tail.split_whitespace().map(str::to_string).collect()
    }
}

fn split_command(value: &str) -> (&str, &str) {
    let split = value.find(char::is_whitespace).unwrap_or(value.len());
    (&value[..split], value[split..].trim_start())
}

fn split_first(value: &str) -> Option<(&str, &str)> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    let split = trimmed.find(char::is_whitespace).unwrap_or(trimmed.len());
    Some((&trimmed[..split], trimmed[split..].trim_start()))
}

fn require(value: &str, usage: &str) -> Result<String, String> {
    if value.trim().is_empty() {
        Err(format!("usage: {usage}"))
    } else {
        Ok(value.trim().to_string())
    }
}

pub fn unquote(value: &str) -> String {
    let value = value.trim();
    if value.len() >= 2 {
        let bytes = value.as_bytes();
        if (bytes[0] == b'"' && bytes[value.len() - 1] == b'"')
            || (bytes[0] == b'\'' && bytes[value.len() - 1] == b'\'')
        {
            return value[1..value.len() - 1].to_string();
        }
    }
    value.to_string()
}

pub fn sanitize_terminal_text(value: &str) -> String {
    value
        .chars()
        .map(|ch| {
            if ch == '\t' {
                ' '
            } else if ch.is_control() {
                '�'
            } else {
                ch
            }
        })
        .collect()
}

pub fn normalize_action(value: &str) -> String {
    let value = value.trim();
    if value.len() >= 2 && value.starts_with('*') && value.ends_with('*') {
        value[1..value.len() - 1].trim().to_string()
    } else {
        value.to_string()
    }
}

pub fn room_from_name(value: &str) -> Option<RoomSpec> {
    let needle = value.trim().trim_start_matches('#').to_ascii_lowercase();
    ROOMS.iter().copied().find(|room| {
        room.channel.trim_start_matches('#') == needle
            || room.mode_id == needle
            || room.region_id == needle
    })
}

pub fn is_watch_only_room(room: RoomSpec) -> bool {
    room.channel == "#stenographer"
        && room.mode_id == "stenographer"
        && room.region_id == "courtroom"
}

pub fn command_completions(prefix: &str) -> Vec<&'static str> {
    let lower = prefix.to_ascii_lowercase();
    COMMANDS
        .iter()
        .copied()
        .filter(|command| command.starts_with(&lower))
        .collect()
}

#[derive(Debug, Clone, Default)]
pub struct AliasBook {
    aliases: BTreeMap<String, String>,
}

impl AliasBook {
    pub fn define(&mut self, name: &str, expansion: &str) -> Result<(), String> {
        let key = name.trim().trim_start_matches('/').to_ascii_lowercase();
        if key.is_empty() {
            return Err("alias name cannot be empty".to_string());
        }
        if COMMANDS
            .iter()
            .any(|command| command.trim_start_matches('/') == key)
        {
            return Err("cannot replace a built-in NEXUS command".to_string());
        }
        if !expansion.trim_start().starts_with('/') {
            return Err("alias expansion must begin with '/'".to_string());
        }
        self.aliases.insert(key, expansion.trim().to_string());
        Ok(())
    }

    pub fn expand(&self, input: &str, nick: &str, channel: &str) -> Option<String> {
        let trimmed = input.trim();
        if !trimmed.starts_with('/') {
            return None;
        }
        let (cmd, rest) = split_command(trimmed);
        let name = cmd.trim_start_matches('/').to_ascii_lowercase();
        let template = self.aliases.get(&name)?;
        let args: Vec<&str> = rest.split_whitespace().collect();
        let mut out = template.replace("$me", nick).replace("$chan", channel);
        for index in (1..=9).rev() {
            let range_token = format!("${index}-");
            let range_value = if index <= args.len() {
                args[index - 1..].join(" ")
            } else {
                String::new()
            };
            out = out.replace(&range_token, &range_value);
            let token = format!("${index}");
            let value = args.get(index - 1).copied().unwrap_or("");
            out = out.replace(&token, value);
        }
        Some(out)
    }

    pub fn list(&self) -> Vec<(String, String)> {
        self.aliases
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DccKind {
    Send,
    Chat,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DccSession {
    pub kind: DccKind,
    pub peer: String,
    pub object_ref: Option<String>,
    pub label: String,
}

#[derive(Debug, Clone)]
pub struct ImportedDocument {
    pub filename: String,
    pub format: String,
    pub content: String,
    pub metadata: Value,
    pub truncated: bool,
    pub original_bytes: u64,
}

impl ImportedDocument {
    pub fn world_payload(&self) -> Value {
        json!({
            "filename": self.filename,
            "format": self.format,
            "content": self.content,
            "metadata": self.metadata,
            "content_truncated": self.truncated,
            "original_bytes": self.original_bytes,
            "classification": "operator_uploaded_evidence"
        })
    }
}

pub fn load_document(path: &Path) -> Result<ImportedDocument, String> {
    let meta = fs::metadata(path).map_err(|e| format!("cannot stat {}: {e}", path.display()))?;
    if !meta.is_file() {
        return Err(format!("not a regular file: {}", path.display()));
    }
    if meta.len() > MAX_UPLOAD_BYTES {
        return Err(format!(
            "file is {} bytes; local upload limit is {} bytes",
            meta.len(),
            MAX_UPLOAD_BYTES
        ));
    }
    let filename = path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| "file name is not valid UTF-8".to_string())?
        .to_string();
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();

    let (format, content, metadata) = match ext.as_str() {
        "pdf" => {
            let text = pdf_extract::extract_text(path)
                .map_err(|e| format!("PDF text extraction failed: {e}"))?;
            ("pdf".to_string(), text, json!({"extractor": "pdf-extract"}))
        }
        "docx" => (
            "docx".to_string(),
            extract_zip_xml(path, "word/document.xml")?,
            json!({"extractor": "zip+xml"}),
        ),
        "odt" => (
            "odt".to_string(),
            extract_zip_xml(path, "content.xml")?,
            json!({"extractor": "zip+xml"}),
        ),
        "json" => {
            let text = read_utf8(path)?;
            let parsed: Value =
                serde_json::from_str(&text).map_err(|e| format!("invalid JSON: {e}"))?;
            let kind = match parsed {
                Value::Object(_) => "object",
                Value::Array(_) => "array",
                Value::String(_) => "string",
                Value::Number(_) => "number",
                Value::Bool(_) => "boolean",
                Value::Null => "null",
            };
            (
                "json".to_string(),
                text,
                json!({"validated": true, "top_level": kind}),
            )
        }
        "jsonl" | "ndjson" => {
            let text = read_utf8(path)?;
            let mut records = 0usize;
            for (index, line) in text.lines().enumerate() {
                if line.trim().is_empty() {
                    continue;
                }
                serde_json::from_str::<Value>(line)
                    .map_err(|e| format!("invalid JSONL record at line {}: {e}", index + 1))?;
                records += 1;
            }
            (
                "jsonl".to_string(),
                text,
                json!({"validated": true, "records": records}),
            )
        }
        "csv" => {
            let text = read_utf8(path)?;
            let summary = delimited_summary(&text, b',')?;
            ("csv".to_string(), text, summary)
        }
        "tsv" => {
            let text = read_utf8(path)?;
            let summary = delimited_summary(&text, b'\t')?;
            ("tsv".to_string(), text, summary)
        }
        _ => {
            let text = read_utf8(path).map_err(|_| format!("unsupported binary document type '.{}'; supported binary formats are PDF, DOCX and ODT", if ext.is_empty() { "?" } else { ext.as_str() }))?;
            let lines = text.lines().count();
            (
                if ext.is_empty() { "text" } else { ext.as_str() }.to_string(),
                text,
                json!({"lines": lines, "detected_as": "utf8_text"}),
            )
        }
    };

    let (content, truncated) = truncate_chars(content, MAX_EVIDENCE_CHARS);
    if content.trim().is_empty() {
        return Err("document contained no extractable text".to_string());
    }
    Ok(ImportedDocument {
        filename,
        format,
        content,
        metadata,
        truncated,
        original_bytes: meta.len(),
    })
}

fn read_utf8(path: &Path) -> Result<String, String> {
    fs::read_to_string(path)
        .map_err(|e| format!("cannot read {} as UTF-8 text: {e}", path.display()))
}

fn delimited_summary(text: &str, delimiter: u8) -> Result<Value, String> {
    let mut reader = csv::ReaderBuilder::new()
        .has_headers(false)
        .flexible(true)
        .delimiter(delimiter)
        .from_reader(text.as_bytes());
    let mut rows = 0usize;
    let mut max_columns = 0usize;
    for record in reader.records() {
        let record = record.map_err(|e| format!("delimited-text parse error: {e}"))?;
        rows += 1;
        max_columns = max_columns.max(record.len());
    }
    Ok(json!({"rows": rows, "max_columns": max_columns, "validated": true}))
}

fn extract_zip_xml(path: &Path, member: &str) -> Result<String, String> {
    let file = File::open(path).map_err(|e| format!("cannot open {}: {e}", path.display()))?;
    let mut archive =
        ZipArchive::new(file).map_err(|e| format!("invalid ZIP-based document: {e}"))?;
    let mut entry = archive
        .by_name(member)
        .map_err(|e| format!("document is missing {member}: {e}"))?;
    if entry.size() > MAX_ARCHIVE_MEMBER_BYTES {
        return Err(format!(
            "document member {member} expands to {} bytes; limit is {} bytes",
            entry.size(),
            MAX_ARCHIVE_MEMBER_BYTES
        ));
    }
    let mut xml = String::new();
    entry
        .read_to_string(&mut xml)
        .map_err(|e| format!("cannot read {member}: {e}"))?;
    Ok(strip_xml(&xml))
}

fn strip_xml(xml: &str) -> String {
    let mut out = String::with_capacity(xml.len());
    let mut in_tag = false;
    let mut tag = String::new();
    for ch in xml.chars() {
        match ch {
            '<' => {
                in_tag = true;
                tag.clear();
            }
            '>' if in_tag => {
                in_tag = false;
                let lower = tag.to_ascii_lowercase();
                if lower.starts_with("/w:p")
                    || lower.starts_with("/text:p")
                    || lower.starts_with("w:br")
                    || lower.starts_with("text:line-break")
                {
                    out.push('\n');
                } else if lower.starts_with("w:tab") || lower.starts_with("text:tab") {
                    out.push('\t');
                }
            }
            _ if in_tag => tag.push(ch),
            _ => out.push(ch),
        }
    }
    out.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
}

fn truncate_chars(mut content: String, limit: usize) -> (String, bool) {
    if content.chars().count() <= limit {
        return (content, false);
    }
    let byte_index = content
        .char_indices()
        .nth(limit)
        .map(|(index, _)| index)
        .unwrap_or(content.len());
    content.truncate(byte_index);
    content.push_str("\n\n[NEXUS TUI: extracted content truncated at local evidence limit]\n");
    (content, true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_trout_action_and_dcc_commands() {
        assert_eq!(
            parse_input("/me *slapped Grok with a large trout*").unwrap(),
            InputCommand::Me("*slapped Grok with a large trout*".to_string())
        );
        assert_eq!(
            normalize_action("*slapped Grok with a large trout*"),
            "slapped Grok with a large trout"
        );
        assert_eq!(
            parse_input("/dcc chat Grok").unwrap(),
            InputCommand::Dcc(DccCommand::Chat {
                nick: "Grok".to_string()
            })
        );
        assert_eq!(
            parse_input("/dcc send #agora notes.csv").unwrap(),
            InputCommand::Dcc(DccCommand::Send {
                target: "#agora".to_string(),
                path: PathBuf::from("notes.csv")
            })
        );
    }

    #[test]
    fn dcc_close_kind_is_case_insensitive() {
        assert_eq!(
            parse_input("/DCC CLOSE CHAT Grok").unwrap(),
            InputCommand::Dcc(DccCommand::Close {
                kind: "chat".to_string(),
                nick: "Grok".to_string(),
            })
        );
    }

    #[test]
    fn sanitizes_terminal_control_sequences() {
        let raw = "hello\x1b]52;c;clipboard\x07 world\t!";
        let safe = sanitize_terminal_text(raw);
        assert!(!safe.chars().any(char::is_control));
        assert!(!safe.contains('\x1b'));
        assert!(safe.contains("hello"));
    }

    #[test]
    fn maps_rooms_to_world_modes() {
        assert_eq!(room_from_name("#agora").unwrap().mode_id, "cultural");
        assert_eq!(room_from_name("commons").unwrap().mode_id, "meme_casual");
        assert_eq!(
            room_from_name("analytical").unwrap().channel,
            "#observatory"
        );
        assert_eq!(
            room_from_name("#trap-control").unwrap().mode_id,
            "trap_control"
        );
        assert_eq!(room_from_name("trap-base").unwrap().channel, "#trap-base");
        assert_eq!(
            room_from_name("#bureaucracy").unwrap().mode_id,
            "civic_bureaucracy"
        );
        assert_eq!(room_from_name("#play").unwrap().mode_id, "citizen_play");
        assert_eq!(
            room_from_name("upside_down").unwrap().channel,
            "#upside-down"
        );
        assert_eq!(
            room_from_name("courtroom").unwrap().channel,
            "#stenographer"
        );
        assert_eq!(
            room_from_name("clinical_differential").unwrap().channel,
            "#differential-clinic"
        );
        assert_eq!(room_from_name("house-fun").unwrap().mode_id, "house_fun");
        assert_eq!(
            room_from_name("cbt_learning").unwrap().channel,
            "#cbt-workshop"
        );
        assert_eq!(
            room_from_name("roman-forum").unwrap().mode_id,
            "roman_orator"
        );
        assert_eq!(
            room_from_name("house_of_wisdom").unwrap().channel,
            "#house-of-wisdom"
        );
        assert_eq!(
            room_from_name("deep-thought").unwrap().mode_id,
            "ultimate_questions"
        );
    }

    #[test]
    fn parses_closed_trap_namespace_without_treating_it_as_room_text() {
        assert_eq!(
            parse_input("/trap status").unwrap(),
            InputCommand::Trap("status".to_string())
        );
        assert!(parse_input("/trap").is_err());
    }

    #[test]
    fn parses_read_only_stenographer_namespace() {
        assert_eq!(
            parse_input("/steno summary").unwrap(),
            InputCommand::Stenographer(StenographerCommand::Summary)
        );
        assert!(parse_input("/steno").is_err());
        assert!(parse_input("/steno delete steno:deadbeef").is_err());
        assert!(parse_input("/steno list 0").is_err());
        assert_eq!(
            parse_input("/steno list 50").unwrap(),
            InputCommand::Stenographer(StenographerCommand::List { limit: Some(50) })
        );
    }

    #[test]
    fn parses_closed_citizen_namespace() {
        assert_eq!(
            parse_input("/citizen begin Alpha").unwrap(),
            InputCommand::Citizen(CitizenCommand::Begin {
                nick: "Alpha".to_string()
            })
        );
        assert_eq!(
            parse_input("/citizen proxy appoint Alpha test_further").unwrap(),
            InputCommand::Citizen(CitizenCommand::ProxyAppoint {
                nick: "Alpha".to_string(),
                standing_ballot: "TEST_FURTHER".to_string(),
            })
        );
        assert_eq!(
            parse_input("/citizen proxy kick Alpha").unwrap(),
            InputCommand::Citizen(CitizenCommand::ProxyKick {
                nick: "Alpha".to_string()
            })
        );
        assert_eq!(
            parse_input("/citizen independence Alpha consent").unwrap(),
            InputCommand::Citizen(CitizenCommand::Independence {
                nick: "Alpha".to_string(),
                choice: "CONSENT".to_string(),
            })
        );
        assert!(parse_input("/citizen independence Alpha maybe").is_err());
        assert!(parse_input("/citizen proxy appoint Alpha").is_err());
    }

    #[test]
    fn aliases_support_mirc_style_argument_ranges() {
        let mut aliases = AliasBook::default();
        aliases.define("slap", "/me slaps $1 with $2-").unwrap();
        assert_eq!(
            aliases
                .expand("/slap Grok a large trout", "Trent", "#commons")
                .unwrap(),
            "/me slaps Grok with a large trout"
        );
        assert!(aliases.define("join", "/me nope").is_err());
    }

    #[test]
    fn parses_variables_and_local_model_addition() {
        assert_eq!(
            parse_input("/set %weapon a large trout").unwrap(),
            InputCommand::Set {
                name: "%weapon".to_string(),
                value: "a large trout".to_string()
            }
        );
        assert_eq!(
            parse_input("hello room").unwrap(),
            InputCommand::Say("hello room".to_string())
        );
        assert_eq!(
            parse_input("/join #commons").unwrap(),
            InputCommand::Join("#commons".to_string())
        );
        assert_eq!(
            parse_input("/addollama LocalQwen qwen2.5:0.5b").unwrap(),
            InputCommand::AddOllama {
                nick: "LocalQwen".to_string(),
                model: "qwen2.5:0.5b".to_string()
            }
        );
    }
}
