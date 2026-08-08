from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


# --- Rust TUI: security, IRC semantics, Unicode display width ---
main = "tui/src/main.rs"
replace_once(
    main,
    "    command_completions, load_document, normalize_action, parse_input, room_from_name, AliasBook,\n"
    "    DccCommand, DccKind, DccSession, InputCommand, RoomSpec, ROOMS,\n",
    "    command_completions, load_document, normalize_action, parse_input, room_from_name,\n"
    "    sanitize_terminal_text, AliasBook, DccCommand, DccKind, DccSession, InputCommand, RoomSpec,\n"
    "    ROOMS,\n",
)
replace_once(
    main,
    "use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};\n",
    "use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};\n"
    "use unicode_width::{UnicodeWidthChar, UnicodeWidthStr};\n",
)
replace_once(
    main,
    "    fn enter() -> io::Result<Self> {\n"
    "        enable_raw_mode()?;\n"
    "        let mut stdout = io::stdout();\n"
    "        execute!(stdout, EnterAlternateScreen, Hide)?;\n"
    "        Ok(Self)\n"
    "    }\n",
    "    fn enter() -> io::Result<Self> {\n"
    "        enable_raw_mode()?;\n"
    "        let mut stdout = io::stdout();\n"
    "        if let Err(error) = execute!(stdout, EnterAlternateScreen, Hide) {\n"
    "            let _ = disable_raw_mode();\n"
    "            let _ = execute!(stdout, Show, LeaveAlternateScreen);\n"
    "            return Err(error);\n"
    "        }\n"
    "        Ok(Self)\n"
    "    }\n",
)
replace_once(
    main,
    "    fn append(&mut self, text: &str) {\n"
    "        for line in text.lines() {\n"
    "            self.scrollback\n"
    "                .push(format!(\"{} {}\", Self::timestamp(), line));\n"
    "        }\n"
    "        self.scroll_offset = 0;\n"
    "    }\n",
    "    fn append(&mut self, text: &str) {\n"
    "        for line in text.lines() {\n"
    "            let safe = sanitize_terminal_text(line);\n"
    "            self.scrollback\n"
    "                .push(format!(\"{} {}\", Self::timestamp(), safe));\n"
    "        }\n"
    "        self.scroll_offset = 0;\n"
    "    }\n",
)
replace_once(
    main,
    "    fn preprocess(&self, input: &str) -> String {\n"
    "        let args_text = command_args(input);\n",
    "    fn scrub_text(nexus: &mut NexusProcess, text: &str) -> Result<(String, bool), String> {\n"
    "        let response = nexus.request(json!({\"operation\": \"security.scrub_preview\", \"text\": text}))?;\n"
    "        let clean = response\n"
    "            .get(\"text\")\n"
    "            .and_then(Value::as_str)\n"
    "            .ok_or_else(|| \"scrub preview response missing text\".to_string())?;\n"
    "        let changed = response\n"
    "            .get(\"changed\")\n"
    "            .and_then(Value::as_bool)\n"
    "            .ok_or_else(|| \"scrub preview response missing changed flag\".to_string())?;\n"
    "        Ok((sanitize_terminal_text(clean), changed))\n"
    "    }\n\n"
    "    fn preprocess(&self, input: &str) -> String {\n"
    "        let command = input\n"
    "            .trim_start()\n"
    "            .split_whitespace()\n"
    "            .next()\n"
    "            .unwrap_or(\"\")\n"
    "            .to_ascii_lowercase();\n"
    "        if matches!(\n"
    "            command.as_str(),\n"
    "            \"/alias\" | \"/aliases\" | \"/set\" | \"/unset\" | \"/vars\"\n"
    "        ) {\n"
    "            return input.to_string();\n"
    "        }\n"
    "        let args_text = command_args(input);\n",
)
replace_once(
    main,
    "    fn execute_line(&mut self, nexus: &mut NexusProcess, raw: String) {\n"
    "        if !raw.trim().is_empty() {\n"
    "            self.history.push(raw.clone());\n"
    "        }\n"
    "        self.history_index = None;\n"
    "        let expanded = self.preprocess(&raw);\n"
    "        match parse_input(&expanded) {\n"
    "            Ok(command) => {\n"
    "                if let Err(error) = self.execute_command(nexus, command) {\n"
    "                    self.append(&format!(\"*** ERROR: {error}\"));\n"
    "                }\n"
    "            }\n"
    "            Err(error) => self.append(&format!(\"*** {error}\")),\n"
    "        }\n"
    "    }\n",
    "    fn execute_line(&mut self, nexus: &mut NexusProcess, raw: String) {\n"
    "        self.history_index = None;\n"
    "        if raw.trim().is_empty() {\n"
    "            return;\n"
    "        }\n"
    "        let (clean, changed) = match Self::scrub_text(nexus, &raw) {\n"
    "            Ok(result) => result,\n"
    "            Err(error) => {\n"
    "                self.append(&format!(\"*** ERROR: {error}\"));\n"
    "                return;\n"
    "            }\n"
    "        };\n"
    "        self.history.push(clean.clone());\n"
    "        if changed {\n"
    "            self.append(\"*** secret-bearing text redacted before local history/scrollback\");\n"
    "        }\n"
    "        let expanded = self.preprocess(&clean);\n"
    "        match parse_input(&expanded) {\n"
    "            Ok(command) => {\n"
    "                if let Err(error) = self.execute_command(nexus, command) {\n"
    "                    self.append(&format!(\"*** ERROR: {error}\"));\n"
    "                }\n"
    "            }\n"
    "            Err(error) => self.append(&format!(\"*** {error}\")),\n"
    "        }\n"
    "    }\n",
)
replace_once(
    main,
    "            InputCommand::Topic(topic) => {\n"
    "                self.topics\n"
    "                    .insert(self.room.channel.to_string(), topic.clone());\n"
    "                self.append(&format!(\"*** {} changed the topic to: {topic}\", self.nick));\n"
    "            }\n",
    "            InputCommand::Topic(topic) => {\n"
    "                let (topic, changed) = Self::scrub_text(nexus, &topic)?;\n"
    "                self.topics\n"
    "                    .insert(self.room.channel.to_string(), topic.clone());\n"
    "                if changed {\n"
    "                    self.append(\"*** secret-bearing topic text redacted\");\n"
    "                }\n"
    "                self.append(&format!(\"*** {} changed the topic to: {topic}\", self.nick));\n"
    "            }\n",
)
replace_once(
    main,
    "            InputCommand::Nick(new_nick) => {\n"
    "                let old = self.nick.clone();\n"
    "                self.nick = new_nick;\n"
    "                self.append(&format!(\"*** {old} is now known as {}\", self.nick));\n"
    "            }\n",
    "            InputCommand::Nick(new_nick) => {\n"
    "                if self\n"
    "                    .members\n"
    "                    .iter()\n"
    "                    .any(|member| member.nick.eq_ignore_ascii_case(&new_nick))\n"
    "                {\n"
    "                    return Err(format!(\"nick already in use: {new_nick}\"));\n"
    "                }\n"
    "                let old = self.nick.clone();\n"
    "                self.nick = new_nick;\n"
    "                self.append(&format!(\"*** {old} is now known as {}\", self.nick));\n"
    "            }\n",
)
replace_once(
    main,
    "            InputCommand::Kick(nick) => {\n"
    "                let before = self.members.len();\n"
    "                self.members.retain(|member| member.nick != nick);\n"
    "                if self.members.len() == before {\n"
    "                    return Err(format!(\"no such model member: {nick}\"));\n"
    "                }\n"
    "                self.targeted_evidence.remove(&nick);\n"
    "                self.dcc_sessions.retain(|session| session.peer != nick);\n"
    "                if self.private_target.as_deref() == Some(&nick) {\n"
    "                    self.private_target = None;\n"
    "                }\n"
    "                self.append(&format!(\n"
    "                    \"*** {nick} was removed from the local room roster\"\n"
    "                ));\n"
    "            }\n",
    "            InputCommand::Kick(nick) => {\n"
    "                let canonical = self\n"
    "                    .members\n"
    "                    .iter()\n"
    "                    .find(|member| member.nick.eq_ignore_ascii_case(&nick))\n"
    "                    .map(|member| member.nick.clone())\n"
    "                    .ok_or_else(|| format!(\"no such model member: {nick}\"))?;\n"
    "                self.members\n"
    "                    .retain(|member| !member.nick.eq_ignore_ascii_case(&canonical));\n"
    "                self.targeted_evidence.remove(&canonical);\n"
    "                self.dcc_sessions\n"
    "                    .retain(|session| !session.peer.eq_ignore_ascii_case(&canonical));\n"
    "                if self\n"
    "                    .private_target\n"
    "                    .as_deref()\n"
    "                    .map(|target| target.eq_ignore_ascii_case(&canonical))\n"
    "                    .unwrap_or(false)\n"
    "                {\n"
    "                    self.private_target = None;\n"
    "                }\n"
    "                self.append(&format!(\n"
    "                    \"*** {canonical} was removed from the local room roster\"\n"
    "                ));\n"
    "            }\n",
)
replace_once(
    main,
    "            InputCommand::Alias { name, expansion } => {\n"
    "                self.aliases.define(&name, &expansion)?;\n"
    "                self.save_state()?;\n"
    "                self.append(&format!(\"*** alias /{name} = {expansion}\"));\n"
    "            }\n",
    "            InputCommand::Alias { name, expansion } => {\n"
    "                let (expansion, changed) = Self::scrub_text(nexus, &expansion)?;\n"
    "                self.aliases.define(&name, &expansion)?;\n"
    "                self.save_state()?;\n"
    "                if changed {\n"
    "                    self.append(\"*** secret-bearing alias text redacted before persistence\");\n"
    "                }\n"
    "                self.append(&format!(\"*** alias /{name} = {expansion}\"));\n"
    "            }\n",
)
replace_once(
    main,
    "            InputCommand::Set { name, value } => {\n"
    "                self.variables.set(&name, &value)?;\n"
    "                self.save_state()?;\n"
    "                self.append(&format!(\"*** {name} = {value}\"));\n"
    "            }\n",
    "            InputCommand::Set { name, value } => {\n"
    "                let (value, changed) = Self::scrub_text(nexus, &value)?;\n"
    "                self.variables.set(&name, &value)?;\n"
    "                self.save_state()?;\n"
    "                if changed {\n"
    "                    self.append(\"*** secret-bearing variable value redacted before persistence\");\n"
    "                }\n"
    "                self.append(&format!(\"*** {name} = {value}\"));\n"
    "            }\n",
)
replace_once(
    main,
    "    fn run_council(&mut self, nexus: &mut NexusProcess, question: &str) -> Result<(), String> {\n"
    "        if self.members.len() < 3 {\n",
    "    fn run_council(&mut self, nexus: &mut NexusProcess, question: &str) -> Result<(), String> {\n"
    "        if self.members.len() < 3 {\n",
)
replace_once(
    main,
    "        self.append(&format!(\"<{}> {}\", self.nick, question));\n"
    "        self.append(&format!(\n",
    "        let (question, changed) = Self::scrub_text(nexus, question)?;\n"
    "        if changed {\n"
    "            self.append(\"*** secret-bearing Council question text redacted\");\n"
    "        }\n"
    "        self.append(&format!(\"<{}> {}\", self.nick, question));\n"
    "        self.append(&format!(\n",
)
replace_once(
    main,
    '            "question": question,\n',
    '            "question": question,\n',
)
replace_once(
    main,
    "        self.append(&format!(\"-> *{}* <{}> {}\", member.nick, self.nick, text));\n"
    "        let response = nexus.request(json!({\n",
    "        let (text, changed) = Self::scrub_text(nexus, text)?;\n"
    "        if changed {\n"
    "            self.append(\"*** secret-bearing private message text redacted\");\n"
    "        }\n"
    "        self.append(&format!(\"-> *{}* <{}> {}\", member.nick, self.nick, text));\n"
    "        let response = nexus.request(json!({\n",
)
replace_once(
    main,
    '            "message": text,\n',
    '            "message": text,\n',
)
replace_once(
    main,
    "    fn save_state(&self) -> Result<(), String> {\n",
    "    fn scrub_loaded_script_state(&mut self, nexus: &mut NexusProcess) -> Result<(), String> {\n"
    "        let mut clean_aliases = AliasBook::default();\n"
    "        let mut clean_variables = VariableBook::default();\n"
    "        let mut changed = false;\n\n"
    "        for (name, expansion) in self.aliases.list() {\n"
    "            let (clean_name, name_changed) = Self::scrub_text(nexus, &name)?;\n"
    "            let (clean_expansion, expansion_changed) = Self::scrub_text(nexus, &expansion)?;\n"
    "            if name_changed {\n"
    "                changed = true;\n"
    "                continue;\n"
    "            }\n"
    "            changed |= expansion_changed || clean_name != name || clean_expansion != expansion;\n"
    "            clean_aliases.define(&clean_name, &clean_expansion)?;\n"
    "        }\n\n"
    "        for (name, value) in self.variables.list() {\n"
    "            let (clean_name, name_changed) = Self::scrub_text(nexus, &name)?;\n"
    "            let (clean_value, value_changed) = Self::scrub_text(nexus, &value)?;\n"
    "            if name_changed {\n"
    "                changed = true;\n"
    "                continue;\n"
    "            }\n"
    "            changed |= value_changed || clean_name != name || clean_value != value;\n"
    "            clean_variables.set(&clean_name, &clean_value)?;\n"
    "        }\n\n"
    "        self.aliases = clean_aliases;\n"
    "        self.variables = clean_variables;\n"
    "        if changed {\n"
    "            self.save_state()?;\n"
    "            self.append(\"*** legacy alias/variable state was scrubbed before use\");\n"
    "        }\n"
    "        Ok(())\n"
    "    }\n\n"
    "    fn save_state(&self) -> Result<(), String> {\n",
)
replace_once(
    main,
    "        let prompt_width = prompt.chars().count();\n"
    "        let input_width = width as usize - prompt_width.min(width as usize);\n",
    "        let prompt_width = UnicodeWidthStr::width(prompt.as_str());\n"
    "        let input_width = width as usize - prompt_width.min(width as usize);\n",
)
replace_once(
    main,
    "        let cursor_x = (prompt_width + self.input.chars().count())\n"
    "            .min(width.saturating_sub(1) as usize) as u16;\n",
    "        let visible_input_width = UnicodeWidthStr::width(self.input.as_str()).min(input_width);\n"
    "        let cursor_x = (prompt_width + visible_input_width)\n"
    "            .min(width.saturating_sub(1) as usize) as u16;\n",
)
old_fit = '''fn fit(text: &str, width: usize) -> String {
    if width == 0 {
        return String::new();
    }
    let count = text.chars().count();
    if count <= width {
        let mut output = text.to_string();
        output.extend(std::iter::repeat(' ').take(width - count));
        output
    } else if width <= 1 {
        text.chars().take(width).collect()
    } else {
        let mut output: String = text.chars().take(width - 1).collect();
        output.push('…');
        output
    }
}
'''
new_fit = '''fn fit(text: &str, width: usize) -> String {
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
'''
replace_once(main, old_fit, new_fit)
replace_once(
    main,
    "    let mut app = App::new(nick, state);\n\n"
    "    while app.running {\n",
    "    let mut app = App::new(nick, state);\n"
    "    app.scrub_loaded_script_state(&mut nexus)\n"
    "        .map_err(io::Error::other)?;\n\n"
    "    while app.running {\n",
)
# Binary-local regression tests for display width and literal script-management parsing.
p = Path(main)
text = p.read_text()
if "fit_respects_terminal_display_cells" not in text:
    text += '''

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fit_respects_terminal_display_cells() {
        let fitted = fit("界x", 2);
        assert_eq!(UnicodeWidthStr::width(fitted.as_str()), 2);
        assert!(fitted.ends_with('…'));
    }

    #[test]
    fn script_management_commands_preserve_placeholders_and_variable_names() {
        let mut app = App::new("Trent".to_string(), PathBuf::from("/definitely/not/a/state/file"));
        app.variables.set("%weapon", "large trout").unwrap();
        assert_eq!(
            app.preprocess("/alias slap /me slaps $1 with $2-"),
            "/alias slap /me slaps $1 with $2-"
        );
        assert_eq!(app.preprocess("/unset %weapon"), "/unset %weapon");
    }
}
'''
    p.write_text(text)

# --- Rust library helpers ---
lib = "tui/src/lib.rs"
p = Path(lib)
text = p.read_text()
if "pub fn sanitize_terminal_text" not in text:
    marker = "pub fn normalize_action(value: &str) -> String {\n"
    helper = '''pub fn sanitize_terminal_text(value: &str) -> String {
    value
        .chars()
        .map(|ch| if ch == '\\t' { ' ' } else if ch.is_control() { '�' } else { ch })
        .collect()
}

'''
    if marker not in text:
        raise SystemExit("normalize_action anchor not found")
    text = text.replace(marker, helper + marker, 1)
# Normalize DCC close type before validation/storage.
old = '''        "close" => {
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
'''
new = '''        "close" => {
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
'''
if old not in text:
    raise SystemExit("DCC close anchor not found")
text = text.replace(old, new, 1)
if "sanitizes_terminal_control_sequences" not in text:
    anchor = "    fn maps_rooms_to_world_modes() {\n"
    tests = '''    #[test]
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
        let raw = "hello\\x1b]52;c;clipboard\\x07 world\\t!";
        let safe = sanitize_terminal_text(raw);
        assert!(!safe.chars().any(char::is_control));
        assert!(!safe.contains('\\x1b'));
        assert!(safe.contains("hello"));
    }

'''
    if anchor not in text:
        raise SystemExit("Rust unit-test anchor not found")
    text = text.replace(anchor, tests + anchor, 1)
p.write_text(text)

# Unicode display-cell support.
replace_once(
    "tui/Cargo.toml",
    'serde_json = "1.0"\n',
    'serde_json = "1.0"\nunicode-width = "0.2.1"\n',
)

# --- Python runtime review fixes ---
# Ollama ballots must receive the same bounded evidence view as phases.
ollama = "src/nexus_runtime/adapters/ollama.py"
replace_once(
    ollama,
    '            f"Evidence snapshot: {context.evidence_snapshot_ref}\\n"\n'
    '            f"Question: {context.question}\\n"\n',
    '            f"Evidence snapshot: {context.evidence_snapshot_ref}\\n"\n'
    '            + (f"Attached evidence view:\\n{context.evidence_context}\\n" if context.evidence_context else "")\n'
    '            + f"Question: {context.question}\\n"\n',
)

# Transport failures should become structured API errors rather than killing stdio.
api = "src/nexus_runtime/api.py"
replace_once(
    api,
    '        except (KeyError, TypeError, ValueError) as exc:\n'
    '            return self._error(request_id, "invalid_request", str(exc))\n',
    '        except (KeyError, TypeError, ValueError) as exc:\n'
    '            return self._error(request_id, "invalid_request", str(exc))\n'
    '        except OSError as exc:\n'
    '            return self._error(request_id, "adapter_unavailable", str(exc))\n',
)

# Evidence context must obey an exact global character cap, separators and markers included.
council = "src/nexus_runtime/council.py"
p = Path(council)
text = p.read_text()
start = text.index("    def build_evidence_context(self, evidence_refs: list[str]) -> str:\n")
end = text.index("\n    def _validate_roster", start)
new_method = '''    def build_evidence_context(self, evidence_refs: list[str]) -> str:
        """Build a strictly bounded model-readable evidence view.

        Object references remain the durable identity/provenance source. This
        derived view exists only so model actors can actually read operator-
        attached documents instead of seeing opaque object hashes.
        """
        output = ""
        object_marker = "\\n[NEXUS: evidence excerpt truncated]"
        budget_marker = "\\n[NEXUS: evidence view budget reached]"

        for ref in evidence_refs:
            obj = self.world.inspect(ref)
            label = obj.payload.get("filename") if isinstance(obj.payload.get("filename"), str) else obj.object_type
            content = obj.payload.get("content")
            if not isinstance(content, str):
                content = canonical_json(obj.payload)
            if len(content) > MAX_EVIDENCE_OBJECT_CHARS:
                keep = max(0, MAX_EVIDENCE_OBJECT_CHARS - len(object_marker))
                content = content[:keep] + object_marker

            section = f"[{ref} | {obj.object_type} | {label}]\\n{content}"
            separator = "\\n\\n" if output else ""
            available = MAX_EVIDENCE_CONTEXT_CHARS - len(output)
            if available <= len(separator):
                break
            output += separator
            available = MAX_EVIDENCE_CONTEXT_CHARS - len(output)

            if len(section) <= available:
                output += section
                continue

            if available > len(budget_marker):
                output += section[: available - len(budget_marker)] + budget_marker
            else:
                output += section[:available]
            break

        return output[:MAX_EVIDENCE_CONTEXT_CHARS]
'''
text = text[:start] + new_method + text[end:]
p.write_text(text)

# README broken LICENSE link.
replace_once(
    "README.md",
    "See [`LICENSE`](`LICENSE`) and [`NOTICE`](NOTICE).",
    "See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).",
)

# --- Python regression tests ---
runtime_tests = "tests/test_runtime.py"
p = Path(runtime_tests)
text = p.read_text()
if "from unittest.mock import patch" not in text:
    text = text.replace("import unittest\n", "import unittest\nfrom unittest.mock import patch\n", 1)
text = text.replace(
    "        self.assertLessEqual(len(view), MAX_EVIDENCE_CONTEXT_CHARS + 64)\n",
    "        self.assertLessEqual(len(view), MAX_EVIDENCE_CONTEXT_CHARS)\n",
    1,
)
if "test_evidence_context_global_cap_includes_separators_and_markers" not in text:
    anchor = "\n\nclass APITests(unittest.TestCase):\n"
    method = '''
    def test_evidence_context_global_cap_includes_separators_and_markers(self) -> None:
        world = WorldStore()
        refs = []
        for index in range(12):
            obj = world.create_object(
                "document_evidence",
                {"filename": f"doc-{index}.txt", "content": (f"DOC {index} " + "x" * 2500)},
                {"actor": "human_operator"},
            )
            refs.append(obj.object_id)
        view = CouncilCoordinator(world).build_evidence_context(refs)
        self.assertLessEqual(len(view), MAX_EVIDENCE_CONTEXT_CHARS)

'''
    if anchor not in text:
        raise SystemExit("APITests anchor not found")
    text = text.replace(anchor, method + anchor, 1)
if "test_transport_failure_is_structured_and_does_not_kill_runtime" not in text:
    anchor = "    def test_world_inspect_rejects_invalid_object_ref(self) -> None:\n"
    method = '''    def test_transport_failure_is_structured_and_does_not_kill_runtime(self) -> None:
        api = NexusAPI()
        member = {
            "member_id": "Local",
            "model_id": "fixture",
            "adapter_id": "ollama",
            "model": "fixture",
            "endpoint": "http://127.0.0.1:11434",
        }
        with patch(
            "nexus_runtime.adapters.ollama.OllamaTransport.generate",
            side_effect=OSError("connection refused"),
        ):
            chat = api.handle({"operation": "actor.chat", "member": member, "message": "hello"})
            council = api.handle(
                {
                    "operation": "council.run",
                    "question": "hello",
                    "members": [
                        member,
                        {"member_id": "B", "model_id": "mock-b"},
                        {"member_id": "C", "model_id": "mock-c"},
                    ],
                }
            )
        self.assertEqual(chat["status"], "error")
        self.assertEqual(chat["error"]["code"], "adapter_unavailable")
        self.assertEqual(council["status"], "error")
        self.assertEqual(council["error"]["code"], "adapter_unavailable")
        self.assertEqual(api.handle({"operation": "system.health"})["status"], "ok")

'''
    if anchor not in text:
        raise SystemExit("world inspect test anchor not found")
    text = text.replace(anchor, method + anchor, 1)
p.write_text(text)

adapter_tests = "tests/test_adapters.py"
p = Path(adapter_tests)
text = p.read_text()
old = '''            mode_id="meme_casual",
            mode_instruction="Allow playful framing while preserving claim boundaries.",
            geometry_region_id="commons",
        )
'''
new = '''            mode_id="meme_casual",
            mode_instruction="Allow playful framing while preserving claim boundaries.",
            geometry_region_id="commons",
            evidence_context="ATTACHED TROUT EVIDENCE",
        )
'''
if old not in text:
    raise SystemExit("ballot PhaseContext anchor not found")
text = text.replace(old, new, 1)
old_assert = '        self.assertIn("Geometry region: commons", transport.last_prompt or "")\n'
new_assert = old_assert + '        self.assertIn("ATTACHED TROUT EVIDENCE", transport.last_prompt or "")\n'
if old_assert not in text:
    raise SystemExit("ballot prompt assertion anchor not found")
text = text.replace(old_assert, new_assert, 1)
p.write_text(text)

print("Applied PR #5 Copilot fixes.")
