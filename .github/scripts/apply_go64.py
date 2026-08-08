from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor exactly once, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Export the self-contained Rust GO64 engine without adding it to normal command
# completion. /GO64 remains an intentionally hidden TUI interception.
replace_once("tui/src/lib.rs", "pub mod scripting;\n", "pub mod go64;\npub mod scripting;\n")

# Main TUI hooks. Secret scrubbing still happens before GO64 sees input.
replace_once(
    "tui/src/main.rs",
    "use nexus_irc_tui::scripting::{expand_identifiers, IdentifierContext, VariableBook};\n",
    "use nexus_irc_tui::go64::{Go64Action, Go64Session};\nuse nexus_irc_tui::scripting::{expand_identifiers, IdentifierContext, VariableBook};\n",
)
replace_once(
    "tui/src/main.rs",
    "use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};\n",
    "use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};\nuse std::time::Duration;\n",
)
replace_once(
    "tui/src/main.rs",
    "    game_refs: BTreeMap<String, String>,\n    mud_refs: BTreeMap<String, String>,\n    targeted_evidence: BTreeMap<String, Vec<String>>,\n",
    "    game_refs: BTreeMap<String, String>,\n    mud_refs: BTreeMap<String, String>,\n    go64_confirmation_pending: bool,\n    go64: Option<Go64Session>,\n    targeted_evidence: BTreeMap<String, Vec<String>>,\n",
)
replace_once(
    "tui/src/main.rs",
    "            game_refs: BTreeMap::new(),\n            mud_refs: BTreeMap::new(),\n            targeted_evidence: BTreeMap::new(),\n",
    "            game_refs: BTreeMap::new(),\n            mud_refs: BTreeMap::new(),\n            go64_confirmation_pending: false,\n            go64: None,\n            targeted_evidence: BTreeMap::new(),\n",
)
replace_once(
    "tui/src/main.rs",
    "        app.append(\"*** NEXUS 2.0 alpha6.4 IRC/TUI — local room, no IRC server\");\n",
    "        app.append(\"*** NEXUS TUI 2.0 alpha6.5 — local room, no IRC server\");\n",
)
replace_once(
    "tui/src/main.rs",
    '''        if changed {\n            self.append("*** secret-bearing text redacted before local history/scrollback");\n        }\n        let expanded = self.preprocess(&clean);\n''',
    '''        if changed {\n            self.append("*** secret-bearing text redacted before local history/scrollback");\n        }\n        if self.handle_go64_line(&clean) {\n            return;\n        }\n        let expanded = self.preprocess(&clean);\n''',
)

replace_once(
    "tui/src/main.rs",
    "    fn execute_command(\n",
    '''    fn handle_go64_line(&mut self, line: &str) -> bool {\n        let trimmed = line.trim();\n\n        if self.go64_confirmation_pending {\n            if trimmed.eq_ignore_ascii_case("yes") || trimmed.eq_ignore_ascii_case("y") {\n                self.go64_confirmation_pending = false;\n                self.go64 = Some(Go64Session::new());\n                for line in Go64Session::boot_lines(&self.nick) {\n                    self.append(&line);\n                }\n            } else if trimmed.eq_ignore_ascii_case("no") || trimmed.eq_ignore_ascii_case("n") {\n                self.go64_confirmation_pending = false;\n                self.append("*** SECRET ALIAS CANCELLED. PROBABLY WISE.");\n            } else {\n                self.append("ARE YOU SURE? TYPE YES OR NO.");\n            }\n            return true;\n        }\n\n        if self.go64.is_some() {\n            let nick = self.nick.clone();\n            let action = self\n                .go64\n                .as_mut()\n                .expect("GO64 checked above")\n                .handle(trimmed, &nick);\n            self.apply_go64_action(action);\n            return true;\n        }\n\n        if trimmed.eq_ignore_ascii_case("/go64") {\n            self.go64_confirmation_pending = true;\n            self.private_target = None;\n            self.append("*** SECRET ALIAS DETECTED: /GO64");\n            self.append("*** THIS TEMPORARILY HIDES THE TUI, NOT THE NEXUS SUBSTRATE.");\n            self.append("ARE YOU SURE?");\n            self.append("TYPE YES OR NO.");\n            return true;\n        }\n\n        false\n    }\n\n    fn apply_go64_action(&mut self, action: Go64Action) {\n        if action.clear_scrollback {\n            self.scrollback.clear();\n            self.scroll_offset = 0;\n        }\n        for line in action.lines {\n            self.append(&line);\n        }\n        if action.exit_alias {\n            self.go64 = None;\n            self.go64_confirmation_pending = false;\n            self.append(&format!(\n                "*** GO64 EXITED. STILL IN {} mode={} region={}",\n                self.room.channel, self.room.mode_id, self.room.region_id\n            ));\n        }\n        if action.quit_app {\n            self.running = false;\n        }\n    }\n\n    fn tick_go64(&mut self) {\n        let lines = match self.go64.as_mut() {\n            Some(session) => session.tick(),\n            None => return,\n        };\n        for line in lines {\n            self.append(&line);\n        }\n    }\n\n    fn go64_active(&self) -> bool {\n        self.go64.is_some()\n    }\n\n    fn execute_command(\n''',
)

# GO64 owns only presentation while active. The status bar keeps the underlying
# room/mode/region visible to make that boundary impossible to mistake.
old_status = '''        let topic = self.current_topic();\n        let status = format!(\n            " NEXUS {}  mode={} region={}  topic={} ",\n            self.room.channel,\n            self.room.mode_id,\n            self.room.region_id,\n            if topic.is_empty() { "(none)" } else { topic }\n        );\n'''
new_status = '''        let topic = self.current_topic();\n        let status = if let Some(go64) = &self.go64 {\n            format!(\n                " {} | under={} mode={} region={} ",\n                go64.status_label(),\n                self.room.channel,\n                self.room.mode_id,\n                self.room.region_id\n            )\n        } else if self.go64_confirmation_pending {\n            " SECRET ALIAS /GO64 // CONFIRM YES OR NO ".to_string()\n        } else {\n            format!(\n                " NEXUS {}  mode={} region={}  topic={} ",\n                self.room.channel,\n                self.room.mode_id,\n                self.room.region_id,\n                if topic.is_empty() { "(none)" } else { topic }\n            )\n        };\n'''
replace_once("tui/src/main.rs", old_status, new_status)

old_prompt = '''        let prompt = match &self.private_target {\n            Some(target) => format!(" DCC:{target}> "),\n            None => format!(" {}> ", self.room.channel),\n        };\n'''
new_prompt = '''        let prompt = if self.go64_confirmation_pending {\n            " ARE YOU SURE? ".to_string()\n        } else if let Some(go64) = &self.go64 {\n            format!(" {} ", go64.prompt_label())\n        } else {\n            match &self.private_target {\n                Some(target) => format!(" DCC:{target}> "),\n                None => format!(" {}> ", self.room.channel),\n            }\n        };\n'''
replace_once("tui/src/main.rs", old_prompt, new_prompt)

replace_once(
    "tui/src/main.rs",
    '''    while app.running {\n        app.render()?;\n        if let Event::Key(key) = event::read()? {\n''',
    '''    while app.running {\n        app.tick_go64();\n        app.render()?;\n        if app.go64_active() && !event::poll(Duration::from_millis(250))? {\n            continue;\n        }\n        if let Event::Key(key) = event::read()? {\n''',
)

# README: make the shell version distinction explicit. The control runtime and
# protocol are unchanged because GO64 never crosses into the substrate API.
replace_once(
    "README.md",
    "- **Pure History Mode — No Ancient Aliens Edition** for source-forensic historical deliberation.\n",
    "- **Pure History Mode — No Ancient Aliens Edition** for source-forensic historical deliberation;\n- a hidden Rust-TUI **`/GO64` Secret Alias Mode** with a text demoscene and DR. S.BAITSO tribute.\n",
)
replace_once(
    "README.md",
    "runtime version: 2.0.0-alpha6.4\ncontrol transport: JSONL over stdio\noperator shell: Rust IRC-style TUI\n",
    "runtime version: 2.0.0-alpha6.4\noperator TUI version: 2.0.0-alpha6.5\ncontrol transport: JSONL over stdio\noperator shell: Rust IRC-style TUI\n",
)
replace_once(
    "README.md",
    "            | /game + /mud        |\n",
    "            | /game + /mud        |\n            | hidden /GO64        |\n",
)
replace_once(
    "README.md",
    "Normal public text is treated as a Council question. Council phases and ballots stream into chronological text scrollback so results are easy to copy, quote and archive.\n\nUseful commands:\n",
    '''Normal public text is treated as a Council question. Council phases and ballots stream into chronological text scrollback so results are easy to copy, quote and archive.\n\n### GO64 secret alias easter egg\n\nThe Rust shell also contains a deliberately hidden `/GO64` overlay. It is absent from ordinary `/help` and command completion, changes no World Mode or evidence state, and leaves the current room underneath it. Device 8 loads an original text-only NEXUS/64 demoscene about why **newer is not automatically better**; device 9 loads an original DR. S.BAITSO meme-therapist tribute adapted from QSOLKCB/ETHICS. At 20 minutes both programs acquire terminally-online brainrot diction; at 30 minutes `/grass` unlocks and returns to the unchanged NEXUS room.\n\nSee [`docs/GO64.md`](docs/GO64.md) for the contract and copyright/claim boundary.\n\nUseful commands:\n''',
)

# IRC docs: document the easter egg without putting it into normal /help.
replace_once(
    "docs/IRC_TUI.md",
    "## `/me`\n",
    '''## Secret alias: `/GO64`\n\n`/GO64` is a hidden local TUI overlay, intentionally absent from ordinary help/completion. After explicit YES confirmation it presents a Commodore-inspired text shell while preserving the underlying room, mode, evidence, roster and Council state.\n\n```text\n/GO64\nARE YOU SURE?\nYES\nLOAD "*",8,1\n```\n\nDevice 8 is an original text demoscene/retro architecture tutor. Device 9 is an original text-only DR. S.BAITSO meme tribute adapted from QSOLKCB/ETHICS. At 20 minutes both switch to deterministic brainrot diction; at 30 minutes `/grass` becomes the normal exit. `/quit`, Ctrl-C and Ctrl-D still terminate NEXUS itself.\n\nThe overlay does not alter protocol `nexus/0.8`, World Modes, geometry, evidence or voting. See [`GO64.md`](GO64.md).\n\n## `/me`\n''',
)

# Changelog: alpha6.5 is a TUI edition milestone only. Python runtime/protocol
# deliberately remain alpha6.4 / nexus/0.8.
replace_once(
    "CHANGELOG.md",
    "All notable changes to QSOL NEXUS are documented here.\n\n",
    '''All notable changes to QSOL NEXUS are documented here.\n\n## 2.0.0-alpha6.5 — Secret Alias / GO64 TUI edition\n\n- add hidden `/GO64` + explicit YES confirmation to the Rust operator shell;\n- add original NEXUS/64 text demoscene teaching `NEWER != BETTER; OLDER != BETTER; MEASURE IT`;\n- add original text-only DR. S.BAITSO tribute adapted from QSOLKCB/ETHICS with Therapy, Agent Intervention, Benchmark Detox and Doomscroll Triage modes;\n- add monotonic 20-minute deterministic brainrot transition and 30-minute `/grass` release gate;\n- preserve `/quit` and Ctrl-C/Ctrl-D as process-level emergency exits;\n- keep `/GO64` out of normal command help/completion;\n- preserve the current World Mode, geometry, evidence, roster and Council state underneath the overlay;\n- keep the Python runtime at `2.0.0-alpha6.4` and protocol at `nexus/0.8` because no substrate contract changes.\n\n> **The terminal can cosplay as 1982. The substrate cannot.**\n\n''',
)

# Structured roadmap had the later alpha6.x milestones only in the appended
# architecture sketch. Record them formally and preserve the user's sketch.
replace_once(
    "ROADMAP.md",
    "## 2.0-alpha7 — Instruments\n",
    '''## 2.0-alpha6.3 — HERESY MUD\n\nCompleted in PR #9.\n\n- [x] deterministic multi-avatar `#mud`;\n- [x] DORK/HERESY-inspired rooms, items, NPCs, combat and quest lineage;\n- [x] authoritative game mutation separated from model narration;\n- [x] anti-score-farming and defeated-avatar item recovery invariants.\n\n## 2.0-alpha6.4 — Pure History / No Ancient Aliens\n\nCompleted in PR #10.\n\n- [x] `pure_history` source-forensic sibling of Historical Mode;\n- [x] shared Archive geometry without a gratuitous topology bump;\n- [x] source/chronology/retelling/speculation separation;\n- [x] bounded chatbot-autobiography retry guard;\n- [x] Equality Guard preserved across history restatements.\n\n## 2.0-alpha6.5 — Secret Alias / GO64 TUI edition\n\nImplemented / targeted in PR #11.\n\n- [x] hidden `/GO64` confirmation gate;\n- [x] original NEXUS/64 text demoscene;\n- [x] original DR. S.BAITSO text tribute adapted from QSOLKCB/ETHICS;\n- [x] 20-minute brainrot register transition;\n- [x] 30-minute `/grass` release gate with process-level emergency exits retained;\n- [x] no World Mode, geometry, evidence, Council or protocol mutation.\n\nCore invariant:\n\n> **The terminal can cosplay as 1982. The substrate cannot.**\n\n## 2.0-alpha7 — Instruments\n''',
)
replace_once(
    "ROADMAP.md",
    "PURE HISTORY / epistemic discipline - In Progress.\n  ↓\n==============================\n",
    "PURE HISTORY / epistemic discipline - Done.\n  ↓\nGO64 / SECRET ALIAS RETRO MODE - Done.\n  ↓\n==============================\n",
)

print("Applied GO64 TUI integration patches.")
