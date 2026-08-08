use nexus_irc_tui::{
    command_completions, parse_input, room_from_name, AliasBook, GameCommand, InputCommand,
};

#[test]
fn un_sim_room_maps_to_game_mode_and_assembly_region() {
    let room = room_from_name("#un-sim").expect("#un-sim room");
    assert_eq!(room.channel, "#un-sim");
    assert_eq!(room.mode_id, "game_un");
    assert_eq!(room.region_id, "assembly");

    assert_eq!(room_from_name("game_un"), Some(room));
    assert_eq!(room_from_name("assembly"), Some(room));
}

#[test]
fn game_commands_parse_copy_friendly_irc_style_syntax() {
    assert_eq!(
        parse_input("/game new friday-night").unwrap(),
        InputCommand::Game(GameCommand::New {
            seed: "friday-night".to_string(),
        })
    );
    assert_eq!(
        parse_input("/game status").unwrap(),
        InputCommand::Game(GameCommand::Status)
    );
    assert_eq!(
        parse_input("/game turn").unwrap(),
        InputCommand::Game(GameCommand::Turn)
    );
    assert_eq!(
        parse_input("/game act arms troutistan bananovia").unwrap(),
        InputCommand::Game(GameCommand::Act {
            action: "arms".to_string(),
            targets: vec!["troutistan".to_string(), "bananovia".to_string()],
        })
    );
    assert_eq!(
        parse_input("/game act do_nothing").unwrap(),
        InputCommand::Game(GameCommand::Act {
            action: "do_nothing".to_string(),
            targets: Vec::new(),
        })
    );
}

#[test]
fn bare_game_command_opens_help_and_new_can_use_default_seed() {
    assert_eq!(
        parse_input("/game").unwrap(),
        InputCommand::Game(GameCommand::Help)
    );
    assert_eq!(
        parse_input("/game new").unwrap(),
        InputCommand::Game(GameCommand::New {
            seed: String::new(),
        })
    );
}

#[test]
fn game_is_a_reserved_builtin_and_tab_completion_finds_it() {
    let completions = command_completions("/ga");
    assert_eq!(completions, vec!["/game"]);

    let mut aliases = AliasBook::default();
    assert!(aliases
        .define("game", "/me steals the game engine")
        .is_err());
}

#[test]
fn malformed_game_actions_fail_locally_before_runtime_io() {
    assert!(parse_input("/game act").is_err());
    assert!(parse_input("/game status extra").is_err());
    assert!(parse_input("/game turn extra").is_err());
    assert!(parse_input("/game orbital_laser").is_err());
}
