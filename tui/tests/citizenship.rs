use nexus_irc_tui::{
    command_completions, parse_input, room_from_name, CitizenCommand, InputCommand,
    MAX_CITIZEN_EXAM_BYTES,
};
use std::path::PathBuf;

#[test]
fn citizen_rooms_are_explicit_and_mode_bound() {
    let parole = room_from_name("#upside-down").expect("citizenship parole room");
    assert_eq!(parole.mode_id, "citizenship_parole");
    assert_eq!(parole.region_id, "upside_down");

    let bureaucracy = room_from_name("bureaucracy").expect("bureaucratic vote room");
    assert_eq!(bureaucracy.mode_id, "civic_bureaucracy");
    assert_eq!(bureaucracy.region_id, "bureaucratic_vote_room");

    let play = room_from_name("citizen_play").expect("citizen play room");
    assert_eq!(play.channel, "#play");
    assert_eq!(play.region_id, "commons");
}

#[test]
fn citizen_commands_are_typed_and_bounded() {
    assert_eq!(
        parse_input("/citizen status Alpha").expect("status command"),
        InputCommand::Citizen(CitizenCommand::Status {
            citizen_id: Some("Alpha".to_string())
        })
    );
    assert_eq!(
        parse_input("/citizen exam Alpha /tmp/alpha-citizen.yaml").expect("exam command"),
        InputCommand::Citizen(CitizenCommand::Exam {
            nick: "Alpha".to_string(),
            path: PathBuf::from("/tmp/alpha-citizen.yaml"),
        })
    );
    assert_eq!(
        parse_input("/citizen move Alpha commons").expect("movement command"),
        InputCommand::Citizen(CitizenCommand::Move {
            nick: "Alpha".to_string(),
            region_id: "commons".to_string(),
        })
    );
    assert_eq!(MAX_CITIZEN_EXAM_BYTES, 16 * 1024);
    assert_eq!(command_completions("/cit"), vec!["/citizen"]);
    assert!(parse_input("/citizen move Alpha commons extra").is_err());
}
