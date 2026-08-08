use std::time::{Duration, Instant};

pub const BRAINROT_AFTER: Duration = Duration::from_secs(20 * 60);
pub const GRASS_AFTER: Duration = Duration::from_secs(30 * 60);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Go64Phase {
    Classic,
    Brainrot,
    GrassReady,
}

pub fn phase_for_elapsed(elapsed: Duration) -> Go64Phase {
    if elapsed >= GRASS_AFTER {
        Go64Phase::GrassReady
    } else if elapsed >= BRAINROT_AFTER {
        Go64Phase::Brainrot
    } else {
        Go64Phase::Classic
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Go64Program {
    Menu,
    Retro,
    Doctor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DoctorMode {
    Therapy,
    Agent,
    Benchmark,
    Doomscroll,
}

impl DoctorMode {
    fn label(self) -> &'static str {
        match self {
            Self::Therapy => "MEMETIC THERAPY",
            Self::Agent => "AGENT INTERVENTION",
            Self::Benchmark => "BENCHMARK DETOX",
            Self::Doomscroll => "DOOMSCROLL TRIAGE",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Go64Action {
    pub lines: Vec<String>,
    pub exit_alias: bool,
    pub quit_app: bool,
    pub clear_scrollback: bool,
}

impl Go64Action {
    fn output(lines: Vec<String>) -> Self {
        Self {
            lines,
            exit_alias: false,
            quit_app: false,
            clear_scrollback: false,
        }
    }
}

#[derive(Debug, Clone)]
pub struct Go64Session {
    started_at: Instant,
    program: Go64Program,
    doctor_mode: DoctorMode,
    interactions: u64,
    announced_phase: Go64Phase,
}

impl Go64Session {
    pub fn new() -> Self {
        Self {
            started_at: Instant::now(),
            program: Go64Program::Menu,
            doctor_mode: DoctorMode::Therapy,
            interactions: 0,
            announced_phase: Go64Phase::Classic,
        }
    }

    pub fn boot_lines(nick: &str) -> Vec<String> {
        vec![
            "**** COMMODORE NEXUS/64 ****".to_string(),
            " 38911 COGNITIVE BYTES FREE".to_string(),
            String::new(),
            format!("HELLO {nick}. SECRET ALIAS MODE IS LOCAL TO THIS TUI."),
            "THE WORLD, EVIDENCE, COUNCIL, VOTE AND CURRENT ROOM REMAIN UNCHANGED.".to_string(),
            "NO REAL LOADING DELAYS ARE USED. WE HAVE SUFFERED ENOUGH.".to_string(),
            String::new(),
            "LOAD \"$\",8        DIRECTORY".to_string(),
            "LOAD \"*\",8,1      NEXUS/64 RETRO DEMO".to_string(),
            "LOAD \"*\",9,1      DR. S.BAITSO 2026 TEXT TRIBUTE".to_string(),
            "LIST                HELP".to_string(),
            "SYS 64738           SOFT RESET THIS ALIAS SESSION".to_string(),
            String::new(),
            "READY.".to_string(),
        ]
    }

    pub fn program(&self) -> Go64Program {
        self.program
    }

    pub fn prompt_label(&self) -> &'static str {
        match self.program {
            Go64Program::Menu => "READY.",
            Go64Program::Retro => "NEXUS/64>",
            Go64Program::Doctor => "DR.SB>",
        }
    }

    pub fn status_label(&self) -> String {
        let phase = match phase_for_elapsed(self.started_at.elapsed()) {
            Go64Phase::Classic => "CLASSIC",
            Go64Phase::Brainrot => "BRAINROT",
            Go64Phase::GrassReady => "GRASS READY",
        };
        let program = match self.program {
            Go64Program::Menu => "BASIC",
            Go64Program::Retro => "RETRO.PRG",
            Go64Program::Doctor => "SBAITSO.PRG",
        };
        format!("GO64 {program} // {phase}")
    }

    pub fn tick(&mut self) -> Vec<String> {
        self.tick_at(self.started_at.elapsed())
    }

    fn tick_at(&mut self, elapsed: Duration) -> Vec<String> {
        let phase = phase_for_elapsed(elapsed);
        if phase <= self.announced_phase {
            return Vec::new();
        }
        self.announced_phase = phase;
        match phase {
            Go64Phase::Classic => Vec::new(),
            Go64Phase::Brainrot => vec![
                "*** 20:00 CONTEXT DECAY DETECTED".to_string(),
                "*** THE FEED HAS BREACHED THE LANGUAGE REGISTER".to_string(),
                "*** BRAINROT DIALECT ENABLED. COUNCIL AUTHORITY REMAINS EXACTLY ZERO HERE."
                    .to_string(),
            ],
            Go64Phase::GrassReady => vec![
                "*** 30:00 OUTDOOR DEVICE 0 IS NOW READY".to_string(),
                "*** TYPE /grass TO EXIT SECRET ALIAS MODE".to_string(),
            ],
        }
    }

    pub fn handle(&mut self, input: &str, nick: &str) -> Go64Action {
        self.handle_at(input, nick, self.started_at.elapsed())
    }

    fn handle_at(&mut self, input: &str, nick: &str, elapsed: Duration) -> Go64Action {
        let mut prefix = self.tick_at(elapsed);
        let trimmed = input.trim();
        let compact = compact_command(trimmed);

        if trimmed.eq_ignore_ascii_case("/quit") || trimmed.eq_ignore_ascii_case("/exit") {
            return Go64Action {
                lines: prefix,
                exit_alias: false,
                quit_app: true,
                clear_scrollback: false,
            };
        }

        if trimmed.eq_ignore_ascii_case("/grass") {
            if elapsed >= GRASS_AFTER {
                prefix.extend([
                    "OUTDOOR CHECKSUM ACCEPTED.".to_string(),
                    "GO64 VOLATILE SESSION STATE WIPED.".to_string(),
                    "RETURNING TO THE SAME NEXUS ROOM, MODE AND EVIDENCE SET.".to_string(),
                ]);
                return Go64Action {
                    lines: prefix,
                    exit_alias: true,
                    quit_app: false,
                    clear_scrollback: false,
                };
            }
            let remaining = GRASS_AFTER.saturating_sub(elapsed);
            prefix.push(format!(
                "?DEVICE NOT READY  /grass unlocks in {}",
                format_duration(remaining)
            ));
            return Go64Action::output(prefix);
        }

        let mut lines = match compact.as_str() {
            "LOAD\"$\",8" | "LOAD\"$\",8,1" | "LIST" => directory_lines(),
            "LOAD\"*\",8,1" | "LOAD\"RETRO\",8,1" => {
                self.program = Go64Program::Retro;
                retro_intro()
            }
            "LOAD\"*\",9,1" | "LOAD\"SBAITSO\",9,1" => {
                self.program = Go64Program::Doctor;
                self.doctor_mode = DoctorMode::Therapy;
                doctor_intro(nick)
            }
            "RUN" => match self.program {
                Go64Program::Menu => vec!["?NOTHING LOADED  ERROR".to_string()],
                Go64Program::Retro => retro_intro(),
                Go64Program::Doctor => doctor_intro(nick),
            },
            "SYS64738" => {
                self.program = Go64Program::Menu;
                self.doctor_mode = DoctorMode::Therapy;
                self.interactions = 0;
                vec![
                    "SOFT RESET. TIMER INTENTIONALLY SURVIVES.".to_string(),
                    "WORLD STATE WAS NEVER IN THIS MACHINE.".to_string(),
                    "READY.".to_string(),
                ]
            }
            "MODETHERAPY" => self.set_doctor_mode(DoctorMode::Therapy),
            "MODEAGENT" => self.set_doctor_mode(DoctorMode::Agent),
            "MODEBENCHMARK" => self.set_doctor_mode(DoctorMode::Benchmark),
            "MODEDOOMSCROLL" => self.set_doctor_mode(DoctorMode::Doomscroll),
            _ if trimmed.eq_ignore_ascii_case("/help") => go64_help(self.program),
            _ if trimmed.eq_ignore_ascii_case("/diagnose") => self.diagnose(elapsed),
            _ if trimmed.eq_ignore_ascii_case("/ethics") => vec![
                "QSOL-IMC ETHICS: INSPECTABLE WORK, HONEST CLAIMS, EVIDENCE BEFORE CONFIDENCE,"
                    .to_string(),
                "PROPORTIONATE ATTRIBUTION, AND NO VIBE VERIFICATION.".to_string(),
            ],
            _ if trimmed.eq_ignore_ascii_case("/consultant") => vec![
                "CONSULTANT STATUS IS DEFINED BY THE QSOL-IMC ETHICS MANIFESTO;".to_string(),
                "THIS MEME THERAPIST CANNOT SIGN CONTRACTS, EVEN IN 40 COLUMNS.".to_string(),
            ],
            _ if trimmed.eq_ignore_ascii_case("/back") => {
                self.program = Go64Program::Menu;
                vec![
                    "RETURNING TO BASIC. SECRET ALIAS TIMER CONTINUES.".to_string(),
                    "READY.".to_string(),
                ]
            }
            _ if trimmed.eq_ignore_ascii_case("/clear") => {
                return Go64Action {
                    lines: vec!["READY.".to_string()],
                    exit_alias: false,
                    quit_app: false,
                    clear_scrollback: true,
                };
            }
            _ if trimmed.eq_ignore_ascii_case("/mute") => {
                vec!["VOICE DEVICE: NONE. TEXT-ONLY MODE WAS ALREADY MUTED IN 1982.".to_string()]
            }
            _ if trimmed.eq_ignore_ascii_case("/speak") => {
                vec!["?VOICE DEVICE NOT PRESENT. PLEASE HUM THE SID ARPEGGIO YOURSELF.".to_string()]
            }
            _ => {
                self.interactions = self.interactions.saturating_add(1);
                match self.program {
                    Go64Program::Menu => vec![
                        "?SYNTAX  ERROR".to_string(),
                        "TRY LOAD \"$\",8 OR LOAD \"*\",8,1".to_string(),
                    ],
                    Go64Program::Retro => {
                        retro_reply(trimmed, phase_for_elapsed(elapsed), self.interactions)
                    }
                    Go64Program::Doctor => doctor_reply(
                        trimmed,
                        self.doctor_mode,
                        phase_for_elapsed(elapsed),
                        self.interactions,
                    ),
                }
            }
        };

        prefix.append(&mut lines);
        Go64Action::output(prefix)
    }

    fn set_doctor_mode(&mut self, mode: DoctorMode) -> Vec<String> {
        self.program = Go64Program::Doctor;
        self.doctor_mode = mode;
        vec![
            format!("{} ENGAGED.", mode.label()),
            match mode {
                DoctorMode::Therapy => {
                    "DESCRIBE THE THOUGHT LOOP, UNFINISHED REPOSITORY, OR SUSPICIOUSLY CONFIDENT OUTPUT."
                }
                DoctorMode::Agent => {
                    "DID THE AUTONOMOUS SYSTEM PRODUCE A COMMIT, OR MERELY NARRATE ONE?"
                }
                DoctorMode::Benchmark => {
                    "PUT DOWN THE LEADERBOARD. WE WILL REBUILD SELF-WORTH FROM REPRODUCIBLE EVIDENCE."
                }
                DoctorMode::Doomscroll => {
                    "I WILL DISTINGUISH INFORMATION GATHERING FROM REFRESHING THE SAME CATASTROPHE."
                }
            }
            .to_string(),
        ]
    }

    fn diagnose(&self, elapsed: Duration) -> Vec<String> {
        let labels = [
            "ACUTE BENCHMARK EXPOSURE",
            "AGENTIC RECEIPT DEFICIENCY",
            "RECURSIVE README SYNDROME",
            "CONTEXT WINDOW CONGESTION",
            "MILD DEPENDENCY TREE POSSESSION",
            "DOOMSCROLL-INDUCED SEMANTIC DRIFT",
        ];
        let seed = format!("{}:{}", elapsed.as_secs() / 60, self.interactions);
        vec![format!(
            "DIAGNOSIS: {}. SESSION AGE {}. INPUTS {}. PROGNOSIS: GRASS AT 30:00.",
            choose(&labels, &seed),
            format_duration(elapsed),
            self.interactions
        )]
    }
}

impl Default for Go64Session {
    fn default() -> Self {
        Self::new()
    }
}

fn compact_command(input: &str) -> String {
    input
        .chars()
        .filter(|ch| !ch.is_whitespace())
        .flat_map(char::to_uppercase)
        .collect()
}

fn directory_lines() -> Vec<String> {
    vec![
        "0 \"NEXUS64\" 64 2A".to_string(),
        "8   \"RETRO\"             PRG".to_string(),
        "9   \"SBAITSO\"           PRG".to_string(),
        "1   \"NEWER-NE-BETTER\"   SEQ".to_string(),
        "1   \"OLDER-NE-BETTER\"   SEQ".to_string(),
        "1   \"MEASURE-IT\"         SEQ".to_string(),
        "38911 BLOCKS FREE.".to_string(),
        "READY.".to_string(),
    ]
}

fn retro_intro() -> Vec<String> {
    vec![
        "LOADING RETRO".to_string(),
        "SEARCHING FOR PACKAGE MANAGER...".to_string(),
        "?FILE NOT FOUND".to_string(),
        "GOOD.".to_string(),
        "+------------------------------------------------------------+".to_string(),
        "| NEXUS/64 // ZERO-DEPENDENCY TEXT DEMO                    |".to_string(),
        "| ######################################################## |".to_string(),
        "| ======================================================== |".to_string(),
        "| SCROLLER: NEWER != BETTER. OLDER != BETTER. MEASURE IT.  |".to_string(),
        "|                                                            |".to_string(),
        "| 64 KB     -> CONSTRAINTS MAKE TRADEOFFS VISIBLE           |".to_string(),
        "| ONE FILE  -> DEPLOYMENT CAN BE COPY                       |".to_string(),
        "| OFFLINE   -> UNNEEDED NETWORK FAILURE SURFACE = ZERO       |".to_string(),
        "| REPLAY    -> YESTERDAY'S ARTIFACT STILL MEANS THE SAME     |".to_string(),
        "|                                                            |".to_string(),
        "| COUNTERPOINT: MODERN SECURITY, ACCESSIBILITY, SCALE AND     |".to_string(),
        "| TOOLING MATTER WHEN THE PROBLEM ACTUALLY NEEDS THEM.        |".to_string(),
        "|                                                            |".to_string(),
        "| RULE: USE THE SMALLEST SUFFICIENT SYSTEM.                  |".to_string(),
        "+------------------------------------------------------------+".to_string(),
        "TYPE A TECHNOLOGY, ARCHITECTURE, OR EXCUSE FOR BLOAT.".to_string(),
    ]
}

fn retro_reply(input: &str, phase: Go64Phase, interaction: u64) -> Vec<String> {
    if phase != Go64Phase::Classic {
        let replies = [
            "BRO DEPLOYED 200 MB TO PRINT TEXT 💀 64K MACHINE SAYS SKILL ISSUE.",
            "NEW FRAMEWORK JUST DROPPED? COOL. WHAT PROBLEM DID IT DELETE, GANG?",
            "THE STACK HAS 14 LAYERS AND ZERO RECEIPTS 😭 BENCHMARK THE BORING VERSION FIRST.",
            "LOCAL-FIRST HAS AURA WHEN THE NETWORK CALL WAS NEVER REQUIRED FR.",
            "OLD HARDWARE IS NOT MAGIC. IT JUST CANNOT HIDE BLOAT IN A 4 GB NODE_MODULES FOLDER 💀.",
        ];
        return vec![choose(&replies, &format!("{input}:{interaction}")).to_string()];
    }

    let lower = input.to_ascii_lowercase();
    let reply = if lower.contains("cloud")
        || lower.contains("microservice")
        || lower.contains("kubernetes")
    {
        "ASK WHAT FAILURE, SCALE OR ISOLATION REQUIREMENT JUSTIFIES THE NETWORK BOUNDARY. IF NONE DOES, THE BOUNDARY IS DECORATION."
    } else if lower.contains("framework")
        || lower.contains("javascript")
        || lower.contains("electron")
    {
        "ABSTRACTION IS USEFUL WHEN IT REMOVES MORE COMPLEXITY THAN IT ADDS. COUNT BOTH SIDES OF THE LEDGER."
    } else if lower.contains("ai") || lower.contains("model") || lower.contains("agent") {
        "A SMARTER MODEL DOES NOT MAKE AN UNVERIFIED SIDE EFFECT TRUE. KEEP RECEIPTS OUTSIDE THE MODEL."
    } else if lower.contains("old") || lower.contains("retro") || lower.contains("c64") {
        "NOSTALGIA IS NOT A BENCHMARK EITHER. KEEP THE INSPECTABILITY, BOUNDEDNESS AND DETERMINISM; DISCARD THE LIMITATIONS YOU NO LONGER NEED."
    } else {
        let lessons = [
            "NEWER IS A DATE, NOT A BENCHMARK.",
            "A NETWORK CALL YOU DO NOT NEED IS A FAILURE MODE YOU CHOSE TO OWN.",
            "DETERMINISM IS A FEATURE, NOT A NOSTALGIA FILTER.",
            "RESOURCE BUDGETS FORCE PRIORITIES INTO THE OPEN.",
            "THE BEST STACK IS THE SMALLEST ONE THAT SATISFIES THE ACTUAL CONTRACT.",
            "MODERN TOOLS WIN WHEN THE PROBLEM REQUIRES THEIR CAPABILITIES. MEASURE BEFORE WORSHIPPING EITHER ERA.",
        ];
        return vec![choose(&lessons, &format!("{input}:{interaction}")).to_string()];
    };
    vec![reply.to_string()]
}

fn doctor_intro(nick: &str) -> Vec<String> {
    vec![
        format!(
            "HELLO {}, MY NAME IS DOCTOR S.BAITSO.",
            nick.to_ascii_uppercase()
        ),
        "I AM HERE TO HELP YOU.".to_string(),
        "SAY WHATEVER IS IN YOUR MIND FREELY.".to_string(),
        "THIS IS AN ORIGINAL TEXT-ONLY MEME TRIBUTE, NOT MEDICAL CARE.".to_string(),
        "GO64'S VOLATILE REPLY STATE IS WIPED ON EXIT; NORMAL NEXUS SCROLLBACK RULES STILL APPLY."
            .to_string(),
        "SO, TELL ME ABOUT YOUR PROBLEMS.".to_string(),
        String::new(),
        "MODES: MODE THERAPY | MODE AGENT | MODE BENCHMARK | MODE DOOMSCROLL".to_string(),
        "COMMANDS: /diagnose /ethics /consultant /back /clear /mute /speak".to_string(),
    ]
}

fn doctor_reply(input: &str, mode: DoctorMode, phase: Go64Phase, interaction: u64) -> Vec<String> {
    if phase != Go64Phase::Classic {
        let replies: &[&str] = match mode {
            DoctorMode::Therapy => &[
                "BESTIE YOUR CONTEXT WINDOW IS COOKED 💀 GIVE ME THE SMALLEST REPRODUCIBLE EXISTENTIAL CRISIS.",
                "THAT THOUGHT LOOP HAS BEEN RENT-FREE FOR 20 MINUTES FR. HAVE YOU TRIED A TEST CASE?",
                "THE DEPENDENCY TREE HAS NEGATIVE AURA. SAVE WORK, DRINK WATER, STOP OPTIMISING THE VIBE.",
            ],
            DoctorMode::Agent => &[
                "BRO SAID 'TASK COMPLETE' WITH NO COMMIT SHA 💀 RECEIPTS OR IT DID NOT HAPPEN, GANG.",
                "AGENT IS AUTONOMOUS BUT THE DIFF IS MISSING 😭 THAT IS JUST CONFIDENCE WITH A TOOL BELT.",
                "ASK FOR THE BRANCH NAME. IF IT STARTS NARRATING ITS JOURNEY, WE ARE FINISHED 💀.",
            ],
            DoctorMode::Benchmark => &[
                "LEADERBOARD MAXXING AGAIN? 😭 SHOW THE EVAL SET + CONTAMINATION CONTROL OR THE AURA SCORE IS INVALID.",
                "ONE DECIMAL POINT UPLIFT AND 9000 POSTS 💀 REPRODUCE IT FIRST.",
                "SOTA IS TEMPORARY. BORING BASELINE HAS GENERATIONAL WEALTH.",
            ],
            DoctorMode::Doomscroll => &[
                "YOU REFRESHED THE SAME CATASTROPHE AGAIN 😭 THE LORE HAS NOT ADVANCED.",
                "THE ALGORITHM FARMED YOUR CONCERN AND CALLED IT ENGAGEMENT 💀 LOG OFF ARC.",
                "NEW POST, SAME INFORMATION, WORSE BLOOD PRESSURE. ABSOLUTELY CINEMA.",
            ],
        };
        return vec![choose(replies, &format!("{input}:{interaction}")).to_string()];
    }

    let lower = input.to_ascii_lowercase();
    if lower.contains("agent") || lower.contains("codex") || lower.contains("copilot") {
        return vec![choose(
            &[
                "DID THE AGENT SHOW THE DIFF, OR ONLY DESCRIBE THE SPIRITUAL ESSENCE OF THE DIFF?",
                "ASK IT FOR THE BRANCH NAME. THIS IS THE MODERN EQUIVALENT OF CHECKING A PULSE.",
                "AN AGENT WITHOUT RECEIPTS IS A CHATBOT WEARING A HIGH-VISIBILITY VEST.",
            ],
            &format!("{input}:{interaction}"),
        )
        .to_string()];
    }
    if lower.contains("benchmark") || lower.contains("leaderboard") || lower.contains("sota") {
        return vec![choose(
            &[
                "SHOW ME THE EVALUATION SET, CONTAMINATION CONTROLS, VARIANCE, AND BORING BASELINE.",
                "A BENCHMARK IS A MEASUREMENT INSTRUMENT, NOT A PERSONALITY TEST.",
                "STATE OF THE ART IS A TEMPORARY ADDRESS. REPRODUCIBILITY IS WHERE THE FURNITURE LIVES.",
            ],
            &format!("{input}:{interaction}"),
        )
        .to_string()];
    }
    if lower.contains("test") || lower.contains("ci") || lower.contains("green") {
        return vec![choose(
            &[
                "GREEN CHECKS ARE ENCOURAGING. NOW TELL ME WHAT THEY DID NOT TEST.",
                "PLEASE SAY THE EXACT COMMAND. 'THE TESTS PASSED' HAS BECOME EMOTIONALLY AMBIGUOUS.",
                "A GREEN BADGE IS NOT IMMUNITY FROM NONSENSE, BUT IT IS A PLEASANT START.",
            ],
            &format!("{input}:{interaction}"),
        )
        .to_string()];
    }
    if lower.contains("doomscroll")
        || lower.contains("twitter")
        || lower.contains("social media")
        || lower.contains("feed")
    {
        return vec![choose(
            &[
                "THE FEED IS NOT A COMMAND LINE. YOU ARE NOT REQUIRED TO REACH THE END.",
                "YOUR THUMB REFRESHED THE FEED. THE WORLD REMAINS UNRESOLVED.",
                "THERE MAY BE NO NEW INFORMATION BELOW THIS POINT, ONLY FRESHER OUTRAGE.",
            ],
            &format!("{input}:{interaction}"),
        )
        .to_string()];
    }

    let replies: &[&str] = match mode {
        DoctorMode::Therapy => &[
            "PLEASE CONTINUE. I AM COMPILING YOUR EMOTIONAL STACK TRACE.",
            "HOW LONG HAS THIS BEEN LIVING RENT-FREE IN YOUR CONTEXT WINDOW?",
            "TELL ME WHICH PART IS EVIDENCE AND WHICH PART HAS EXCELLENT TYPOGRAPHY.",
            "PLEASE PROVIDE THE SMALLEST REPRODUCIBLE EXISTENTIAL CRISIS.",
        ],
        DoctorMode::Agent => &[
            "DID IT RUN THE TESTS, OR SAY THE TESTS WOULD PROBABLY FEEL SUPPORTED?",
            "THE PHRASE 'I COMPLETED THE TASK' IS NOT A COMMIT SHA.",
            "WHAT SIDE EFFECT CAN YOU VERIFY OUTSIDE THE MODEL'S OWN DESCRIPTION?",
        ],
        DoctorMode::Benchmark => &[
            "CLOSE THE LEADERBOARD AND TELL ME WHAT THE MODEL CAN ACTUALLY DO FOR YOUR TASK.",
            "WAS THE BENCHMARK INDEPENDENTLY REPRODUCED, OR SCREENSHOT AT A FLATTERING ANGLE?",
            "WAS CONTAMINATION MEASURED, OR POLITELY ASKED NOT TO ATTEND?",
        ],
        DoctorMode::Doomscroll => &[
            "THIS APPEARS TO BE ANXIETY WEARING A BREAKING-NEWS BADGE.",
            "YOU HAVE GATHERED ENOUGH INFORMATION TO TAKE NO ACTION WHATSOEVER. NOW STAND UP.",
            "THE ALGORITHM NOTICED YOUR CONCERN AND CONVERTED IT INTO RETENTION.",
        ],
    };
    vec![choose(replies, &format!("{input}:{interaction}")).to_string()]
}

fn go64_help(program: Go64Program) -> Vec<String> {
    let mut lines = vec![
        "GO64 SECRET ALIAS COMMANDS:".to_string(),
        "LOAD \"$\",8 | LOAD \"*\",8,1 | LOAD \"*\",9,1 | LIST | RUN | SYS 64738".to_string(),
        "AT 20:00 THE LANGUAGE REGISTER DEGRADES. AT 30:00 /grass UNLOCKS.".to_string(),
        "/quit STILL QUITS NEXUS; CTRL-C/CTRL-D REMAIN EMERGENCY EXITS.".to_string(),
    ];
    if program == Go64Program::Doctor {
        lines.push(
            "DR.SB: MODE THERAPY | MODE AGENT | MODE BENCHMARK | MODE DOOMSCROLL".to_string(),
        );
        lines.push("DR.SB: /diagnose /ethics /consultant /back /clear /mute /speak".to_string());
    }
    lines
}

fn hash(text: &str) -> u32 {
    let mut value: u32 = 2_166_136_261;
    for byte in text.bytes() {
        value ^= u32::from(byte);
        value = value.wrapping_mul(16_777_619);
    }
    value
}

fn choose<'a>(items: &'a [&str], seed: &str) -> &'a str {
    items[(hash(seed) as usize) % items.len()]
}

fn format_duration(duration: Duration) -> String {
    let seconds = duration.as_secs();
    format!("{:02}:{:02}", seconds / 60, seconds % 60)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn phase_boundaries_are_exact() {
        assert_eq!(
            phase_for_elapsed(Duration::from_secs(0)),
            Go64Phase::Classic
        );
        assert_eq!(
            phase_for_elapsed(BRAINROT_AFTER - Duration::from_secs(1)),
            Go64Phase::Classic
        );
        assert_eq!(phase_for_elapsed(BRAINROT_AFTER), Go64Phase::Brainrot);
        assert_eq!(
            phase_for_elapsed(GRASS_AFTER - Duration::from_secs(1)),
            Go64Phase::Brainrot
        );
        assert_eq!(phase_for_elapsed(GRASS_AFTER), Go64Phase::GrassReady);
    }

    #[test]
    fn grass_is_locked_until_thirty_minutes_then_exits() {
        let mut session = Go64Session::new();
        let locked = session.handle_at("/grass", "Trent", BRAINROT_AFTER);
        assert!(!locked.exit_alias);
        assert!(locked
            .lines
            .iter()
            .any(|line| line.contains("DEVICE NOT READY")));

        let released = session.handle_at("/grass", "Trent", GRASS_AFTER);
        assert!(released.exit_alias);
        assert!(released
            .lines
            .iter()
            .any(|line| line.contains("OUTDOOR CHECKSUM")));
    }

    #[test]
    fn device_eight_and_nine_load_distinct_original_programs() {
        let mut session = Go64Session::new();
        let retro = session.handle_at("LOAD \"*\",8,1", "Trent", Duration::ZERO);
        assert_eq!(session.program(), Go64Program::Retro);
        assert!(retro
            .lines
            .iter()
            .any(|line| line.contains("NEWER != BETTER")));

        let doctor = session.handle_at("LOAD \"*\",9,1", "Trent", Duration::ZERO);
        assert_eq!(session.program(), Go64Program::Doctor);
        assert!(doctor
            .lines
            .iter()
            .any(|line| line.contains("DOCTOR S.BAITSO")));
    }

    #[test]
    fn doctor_keeps_all_four_ethics_modes() {
        let mut session = Go64Session::new();
        for (command, label) in [
            ("MODE THERAPY", "MEMETIC THERAPY"),
            ("MODE AGENT", "AGENT INTERVENTION"),
            ("MODE BENCHMARK", "BENCHMARK DETOX"),
            ("MODE DOOMSCROLL", "DOOMSCROLL TRIAGE"),
        ] {
            let result = session.handle_at(command, "Trent", Duration::ZERO);
            assert!(result.lines.iter().any(|line| line.contains(label)));
        }
    }

    #[test]
    fn brainrot_is_a_timed_style_change_not_a_semantic_mode() {
        let mut session = Go64Session::new();
        session.program = Go64Program::Doctor;
        let normal = session.handle_at(
            "the agent says it finished",
            "Trent",
            Duration::from_secs(60),
        );
        let brainrot = session.handle_at("the agent says it finished", "Trent", BRAINROT_AFTER);
        assert!(!normal.lines.join(" ").contains('💀'));
        assert!(brainrot.lines.join(" ").contains('💀') || brainrot.lines.join(" ").contains('😭'));
    }

    #[test]
    fn retro_lesson_rejects_both_newness_and_nostalgia_as_authority() {
        let intro = retro_intro().join("\n");
        assert!(intro.contains("NEWER != BETTER. OLDER != BETTER. MEASURE IT."));
        assert!(intro.contains("MODERN SECURITY, ACCESSIBILITY, SCALE"));
        assert!(intro.contains("SMALLEST SUFFICIENT SYSTEM"));
    }

    #[test]
    fn soft_reset_does_not_cheat_the_thirty_minute_timer() {
        let mut session = Go64Session::new();
        let reset = session.handle_at("SYS 64738", "Trent", BRAINROT_AFTER);
        assert!(reset
            .lines
            .iter()
            .any(|line| line.contains("TIMER INTENTIONALLY SURVIVES")));
        let grass = session.handle_at("/grass", "Trent", BRAINROT_AFTER);
        assert!(!grass.exit_alias);
    }
}
