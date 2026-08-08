from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor once, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tui/src/go64.rs",
    '''pub struct Go64Action {\n    pub lines: Vec<String>,\n    pub exit_alias: bool,\n    pub quit_app: bool,\n    pub clear_scrollback: bool,\n}\n''',
    '''pub struct Go64Action {\n    pub lines: Vec<String>,\n    pub exit_alias: bool,\n    pub quit_app: bool,\n}\n''',
)
replace_once(
    "tui/src/go64.rs",
    '''        Self {\n            lines,\n            exit_alias: false,\n            quit_app: false,\n            clear_scrollback: false,\n        }\n''',
    '''        Self {\n            lines,\n            exit_alias: false,\n            quit_app: false,\n        }\n''',
)
replace_once(
    "tui/src/go64.rs",
    '''    pub fn status_label(&self) -> String {\n        let phase = match phase_for_elapsed(self.started_at.elapsed()) {\n            Go64Phase::Classic => "CLASSIC",\n            Go64Phase::Brainrot => "BRAINROT",\n            Go64Phase::GrassReady => "GRASS READY",\n        };\n        let program = match self.program {\n            Go64Program::Menu => "BASIC",\n            Go64Program::Retro => "RETRO.PRG",\n            Go64Program::Doctor => "SBAITSO.PRG",\n        };\n        format!("GO64 {program} // {phase}")\n    }\n''',
    '''    pub fn status_label(&self) -> String {\n        let elapsed = self.started_at.elapsed();\n        let phase = match phase_for_elapsed(elapsed) {\n            Go64Phase::Classic => "CLASSIC",\n            Go64Phase::Brainrot => "BRAINROT",\n            Go64Phase::GrassReady => "GRASS READY",\n        };\n        let program = match self.program {\n            Go64Program::Menu => "BASIC",\n            Go64Program::Retro => "RETRO.PRG",\n            Go64Program::Doctor => "SBAITSO.PRG",\n        };\n        let raster = (elapsed.as_millis() / 250) % 312;\n        format!("GO64 {program} // {phase} // RASTER {raster:03}")\n    }\n''',
)
replace_once(
    "tui/src/go64.rs",
    '''            return Go64Action {\n                lines: prefix,\n                exit_alias: false,\n                quit_app: true,\n                clear_scrollback: false,\n            };\n''',
    '''            return Go64Action {\n                lines: prefix,\n                exit_alias: false,\n                quit_app: true,\n            };\n''',
)
replace_once(
    "tui/src/go64.rs",
    '''                return Go64Action {\n                    lines: prefix,\n                    exit_alias: true,\n                    quit_app: false,\n                    clear_scrollback: false,\n                };\n''',
    '''                return Go64Action {\n                    lines: prefix,\n                    exit_alias: true,\n                    quit_app: false,\n                };\n''',
)
replace_once(
    "tui/src/go64.rs",
    '''            _ if trimmed.eq_ignore_ascii_case("/clear") => {\n                return Go64Action {\n                    lines: vec!["READY.".to_string()],\n                    exit_alias: false,\n                    quit_app: false,\n                    clear_scrollback: true,\n                };\n            }\n''',
    '''            _ if trimmed.eq_ignore_ascii_case("/clear") => vec![\n                "GO64 VIRTUAL SCREEN CLEARED. NEXUS SCROLLBACK PRESERVED.".to_string(),\n                "READY.".to_string(),\n            ],\n''',
)
replace_once(
    "tui/src/main.rs",
    '''    fn apply_go64_action(&mut self, action: Go64Action) {\n        if action.clear_scrollback {\n            self.scrollback.clear();\n            self.scroll_offset = 0;\n        }\n        for line in action.lines {\n''',
    '''    fn apply_go64_action(&mut self, action: Go64Action) {\n        for line in action.lines {\n''',
)

print("Hardened GO64 overlay boundary.")
