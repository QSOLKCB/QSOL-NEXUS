use nexus_irc_tui::go64::{phase_for_elapsed, Go64Phase, Go64Program, Go64Session, BRAINROT_AFTER, GRASS_AFTER};
use nexus_irc_tui::command_completions;
use std::time::Duration;

#[test]
fn go64_stays_secret_from_normal_slash_completion() {
    assert!(command_completions("/go").is_empty());
    assert!(!command_completions("/")
        .iter()
        .any(|command| command.eq_ignore_ascii_case("/go64")));
}

#[test]
fn go64_phase_contract_is_twenty_then_thirty_minutes() {
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
fn fresh_go64_session_starts_at_basic_menu() {
    let session = Go64Session::new();
    assert_eq!(session.program(), Go64Program::Menu);
    assert_eq!(session.prompt_label(), "READY.");
}
