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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoomSpec {
    pub channel: &'static str,
    pub mode_id: &'static str,
    pub region_id: &'static str,
    pub label: &'static str,
}

pub const ROOMS: [RoomSpec; 4] = [
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
];

pub const COMMANDS: [&str; 28] = [
    "/help",
    "/join",
    "/mode",
    "/topic",
    "/ask",
    "/council",
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
pub enum InputCommand {
    Noop,
    Help,
    Join(String),
    Mode(String),
    Topic(String),
    Ask(String),
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
            if kind != "send" && kind != "chat" {
                return Err("DCC close type must be send or chat".to_string());
            }
            Ok(DccCommand::Close {
                kind: kind.to_string(),
                nick: nick.to_string(),
            })
        }
        _ => Err("usage: /dcc <send|chat|close|list> ...".to_string()),
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
    fn maps_rooms_to_world_modes() {
        assert_eq!(room_from_name("#agora").unwrap().mode_id, "cultural");
        assert_eq!(room_from_name("commons").unwrap().mode_id, "meme_casual");
        assert_eq!(
            room_from_name("analytical").unwrap().channel,
            "#observatory"
        );
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
