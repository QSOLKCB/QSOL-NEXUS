use nexus_irc_tui::{
    command_completions, parse_input, room_from_name, AliasBook, InputCommand, MudCommand,
};

#[test]
fn mud_room_maps_to_game_mode_and_dungeon_region() {
    let room = room_from_name("#mud").expect("#mud room");
    assert_eq!(room.channel, "#mud");
    assert_eq!(room.mode_id, "game_mud");
    assert_eq!(room.region_id, "dungeon");
}

#[test]
fn mud_commands_parse_classic_and_proxy_syntax() {
    assert_eq!(
        parse_input("/mud n").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "go".to_string(),
            args: vec!["n".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud get large_trout").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "take".to_string(),
            args: vec!["large_trout".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud as Grok attack yaml_necromancer large_trout").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: Some("Grok".to_string()),
            action: "attack".to_string(),
            args: vec!["yaml_necromancer".to_string(), "large_trout".to_string()],
        })
    );
    assert_eq!(
        parse_input("/mud shitpost content_moderator_troll").unwrap(),
        InputCommand::Mud(MudCommand::Act {
            player: None,
            action: "shitpost".to_string(),
            args: vec!["content_moderator_troll".to_string()],
        })
    );
}

#[test]
fn mud_is_reserved_builtin_and_tab_completion_finds_it() {
    assert_eq!(command_completions("/mu"), vec!["/mud"]);
    let mut aliases = AliasBook::default();
    assert!(aliases
        .define("mud", "/me replaces the dungeon with React")
        .is_err());
}

#[test]
fn malformed_proxy_command_fails_locally() {
    assert!(parse_input("/mud as Grok").is_err());
}
