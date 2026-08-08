from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor exactly once, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- tui/src/go64.rs ---
replace_once(
    "tui/src/go64.rs",
    """pub struct Go64Action {\n    pub lines: Vec<String>,\n    pub exit_alias: bool,\n    pub quit_app: bool,\n}\n\nimpl Go64Action {\n    fn output(lines: Vec<String>) -> Self {\n        Self {\n            lines,\n            exit_alias: false,\n            quit_app: false,\n        }\n    }\n}\n""",
    """pub struct Go64Action {\n    pub lines: Vec<String>,\n    pub exit_alias: bool,\n    pub quit_app: bool,\n    pub clear_view: bool,\n}\n\nimpl Go64Action {\n    fn output(lines: Vec<String>) -> Self {\n        Self {\n            lines,\n            exit_alias: false,\n            quit_app: false,\n            clear_view: false,\n        }\n    }\n}\n""",
)

replace_once(
    "tui/src/go64.rs",
    """            return Go64Action {\n                lines: prefix,\n                exit_alias: false,\n                quit_app: true,\n            };\n""",
    """            return Go64Action {\n                lines: prefix,\n                exit_alias: false,\n                quit_app: true,\n                clear_view: false,\n            };\n""",
)

replace_once(
    "tui/src/go64.rs",
    """                return Go64Action {\n                    lines: prefix,\n                    exit_alias: true,\n                    quit_app: false,\n                };\n""",
    """                return Go64Action {\n                    lines: prefix,\n                    exit_alias: true,\n                    quit_app: false,\n                    clear_view: false,\n                };\n""",
)

replace_once(
    "tui/src/go64.rs",
    """            let remaining = GRASS_AFTER.saturating_sub(elapsed);\n            prefix.push(format!(\n                \"?DEVICE NOT READY  /grass unlocks in {}\",\n                format_duration(remaining)\n            ));\n""",
    """            let remaining = GRASS_AFTER.saturating_sub(elapsed);\n            let remaining_secs =\n                remaining.as_secs() + u64::from(remaining.subsec_nanos() > 0);\n            prefix.push(format!(\n                \"?DEVICE NOT READY  /grass unlocks in {:02}:{:02}\",\n                remaining_secs / 60,\n                remaining_secs % 60\n            ));\n""",
)

replace_once(
    "tui/src/go64.rs",
    """            _ if trimmed.eq_ignore_ascii_case(\"/clear\") => vec![\n                \"GO64 VIRTUAL SCREEN CLEARED. NEXUS SCROLLBACK PRESERVED.\".to_string(),\n                \"READY.\".to_string(),\n            ],\n""",
    """            _ if trimmed.eq_ignore_ascii_case(\"/clear\") => {\n                return Go64Action {\n                    lines: vec![\n                        \"GO64 VIRTUAL SCREEN CLEARED. NEXUS SCROLLBACK PRESERVED.\".to_string(),\n                        \"READY.\".to_string(),\n                    ],\n                    exit_alias: false,\n                    quit_app: false,\n                    clear_view: true,\n                };\n            }\n""",
)

replace_once(
    "tui/src/go64.rs",
    """    #[test]\n    fn grass_is_locked_until_thirty_minutes_then_exits() {\n""",
    """    #[test]\n    fn grass_countdown_rounds_fractional_second_up() {\n        let mut session = Go64Session::new();\n        let almost = session.handle_at(\n            \"/grass\",\n            \"Trent\",\n            GRASS_AFTER - Duration::from_millis(1),\n        );\n        let text = almost.lines.join(\" \");\n        assert!(!almost.exit_alias);\n        assert!(text.contains(\"00:01\"));\n        assert!(!text.contains(\"unlocks in 00:00\"));\n    }\n\n    #[test]\n    fn clear_requests_go64_view_reset_only() {\n        let mut session = Go64Session::new();\n        let clear = session.handle_at(\"/clear\", \"Trent\", Duration::ZERO);\n        assert!(clear.clear_view);\n        assert!(!clear.exit_alias);\n        assert!(!clear.quit_app);\n        assert!(clear\n            .lines\n            .iter()\n            .any(|line| line.contains(\"NEXUS SCROLLBACK PRESERVED\")));\n    }\n\n    #[test]\n    fn grass_is_locked_until_thirty_minutes_then_exits() {\n""",
)

# --- tui/src/main.rs ---
replace_once(
    "tui/src/main.rs",
    """    go64_confirmation_pending: bool,\n    go64: Option<Go64Session>,\n    targeted_evidence: BTreeMap<String, Vec<String>>,\n""",
    """    go64_confirmation_pending: bool,\n    go64: Option<Go64Session>,\n    go64_view_start: Option<usize>,\n    targeted_evidence: BTreeMap<String, Vec<String>>,\n""",
)

replace_once(
    "tui/src/main.rs",
    """            go64_confirmation_pending: false,\n            go64: None,\n            targeted_evidence: BTreeMap::new(),\n""",
    """            go64_confirmation_pending: false,\n            go64: None,\n            go64_view_start: None,\n            targeted_evidence: BTreeMap::new(),\n""",
)

replace_once(
    "tui/src/main.rs",
    """    fn handle_go64_line(&mut self, line: &str) -> bool {\n        let trimmed = line.trim();\n\n        if self.go64_confirmation_pending {\n""",
    """    fn handle_go64_line(&mut self, line: &str) -> bool {\n        let trimmed = line.trim();\n\n        if self.go64_confirmation_pending\n            && (trimmed.eq_ignore_ascii_case(\"/quit\")\n                || trimmed.eq_ignore_ascii_case(\"/exit\"))\n        {\n            self.go64_confirmation_pending = false;\n            self.running = false;\n            return true;\n        }\n\n        if self.go64_confirmation_pending {\n""",
)

replace_once(
    "tui/src/main.rs",
    """            if trimmed.eq_ignore_ascii_case(\"yes\") || trimmed.eq_ignore_ascii_case(\"y\") {\n                self.go64_confirmation_pending = false;\n                self.go64 = Some(Go64Session::new());\n                for line in Go64Session::boot_lines(&self.nick) {\n""",
    """            if trimmed.eq_ignore_ascii_case(\"yes\") || trimmed.eq_ignore_ascii_case(\"y\") {\n                self.go64_confirmation_pending = false;\n                self.go64_view_start = Some(self.scrollback.len());\n                self.go64 = Some(Go64Session::new());\n                for line in Go64Session::boot_lines(&self.nick) {\n""",
)

replace_once(
    "tui/src/main.rs",
    """    fn apply_go64_action(&mut self, action: Go64Action) {\n        for line in action.lines {\n            self.append(&line);\n        }\n        if action.exit_alias {\n            self.go64 = None;\n            self.go64_confirmation_pending = false;\n            self.append(&format!(\n""",
    """    fn apply_go64_action(&mut self, action: Go64Action) {\n        if action.clear_view {\n            self.go64_view_start = Some(self.scrollback.len());\n            self.scroll_offset = 0;\n        }\n        for line in action.lines {\n            self.append(&line);\n        }\n        if action.exit_alias {\n            self.go64 = None;\n            self.go64_confirmation_pending = false;\n            self.go64_view_start = None;\n            self.scroll_offset = 0;\n            self.append(&format!(\n""",
)

replace_once(
    "tui/src/main.rs",
    """    fn go64_active(&self) -> bool {\n        self.go64.is_some()\n    }\n\n    fn execute_command(\n""",
    """    fn go64_active(&self) -> bool {\n        self.go64.is_some()\n    }\n\n    fn visible_scrollback_start(&self) -> usize {\n        if self.go64.is_some() {\n            self.go64_view_start\n                .unwrap_or(self.scrollback.len())\n                .min(self.scrollback.len())\n        } else {\n            0\n        }\n    }\n\n    fn execute_command(\n""",
)

replace_once(
    "tui/src/main.rs",
    """        let body_height = height.saturating_sub(3) as usize;\n        let end = self\n            .scrollback\n            .len()\n            .saturating_sub(self.scroll_offset.min(self.scrollback.len()));\n        let start = end.saturating_sub(body_height);\n        for (row, line) in self.scrollback[start..end].iter().enumerate() {\n""",
    """        let body_height = height.saturating_sub(3) as usize;\n        let visible_floor = self.visible_scrollback_start();\n        let visible_len = self.scrollback.len().saturating_sub(visible_floor);\n        let end = self\n            .scrollback\n            .len()\n            .saturating_sub(self.scroll_offset.min(visible_len));\n        let start = end.saturating_sub(body_height).max(visible_floor);\n        for (row, line) in self.scrollback[start..end].iter().enumerate() {\n""",
)

replace_once(
    "tui/src/main.rs",
    """    #[test]\n    fn current_game_ref_requires_board_to_remain_shared_evidence() {\n""",
    """    #[test]\n    fn go64_confirmation_keeps_quit_as_process_exit() {\n        let mut app = App::new(\n            \"Trent\".to_string(),\n            PathBuf::from(\"/definitely/not/a/state/file\"),\n        );\n        app.go64_confirmation_pending = true;\n        assert!(app.handle_go64_line(\"/quit\"));\n        assert!(!app.running);\n        assert!(!app.go64_confirmation_pending);\n    }\n\n    #[test]\n    fn go64_clear_moves_only_the_visible_overlay_boundary() {\n        let mut app = App::new(\n            \"Trent\".to_string(),\n            PathBuf::from(\"/definitely/not/a/state/file\"),\n        );\n        let host_scrollback = app.scrollback.clone();\n        app.go64_view_start = Some(app.scrollback.len());\n        app.go64 = Some(Go64Session::new());\n        app.append(\"OLD GO64 OUTPUT\");\n        let old_go64_index = app.scrollback.len();\n        app.apply_go64_action(Go64Action {\n            lines: vec![\"READY.\".to_string()],\n            exit_alias: false,\n            quit_app: false,\n            clear_view: true,\n        });\n\n        assert_eq!(app.go64_view_start, Some(old_go64_index));\n        assert_eq!(&app.scrollback[..host_scrollback.len()], host_scrollback.as_slice());\n        assert_eq!(app.visible_scrollback_start(), old_go64_index);\n        assert!(app.scrollback.iter().any(|line| line.contains(\"OLD GO64 OUTPUT\")));\n    }\n\n    #[test]\n    fn current_game_ref_requires_board_to_remain_shared_evidence() {\n""",
)

print("Applied GO64 Copilot review fixes.")
