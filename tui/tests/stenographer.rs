use nexus_irc_tui::{
    command_completions, is_watch_only_room, parse_input, room_from_name, InputCommand,
    StenographerCommand,
};

#[test]
fn courtroom_stenographer_room_is_a_distinct_watch_only_view() {
    let room = room_from_name("#stenographer").expect("#stenographer room");
    assert_eq!(room.channel, "#stenographer");
    assert_eq!(room.mode_id, "stenographer");
    assert_eq!(room.region_id, "courtroom");
    assert_eq!(room_from_name("courtroom"), Some(room));
    assert!(is_watch_only_room(room));
    assert!(!is_watch_only_room(
        room_from_name("#observatory").expect("ordinary room")
    ));
}

#[test]
fn steno_command_is_closed_and_completed() {
    assert_eq!(
        parse_input("/steno verify").expect("read-only Stenographer command"),
        InputCommand::Stenographer(StenographerCommand::Verify)
    );
    assert!(parse_input("/steno").is_err());
    assert!(parse_input("/steno clear").is_err());
    assert_eq!(command_completions("/steno"), vec!["/steno"]);
}
