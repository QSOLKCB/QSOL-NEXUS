use nexus_irc_tui::{command_completions, parse_input, room_from_name, InputCommand, WallCommand};

#[test]
fn wall_room_is_real_commons_surface() {
    let room = room_from_name("#wall").expect("Wall room");
    assert_eq!(room.channel, "#wall");
    assert_eq!(room.mode_id, "meme_casual");
    assert_eq!(room.region_id, "commons");
}

#[test]
fn wall_commands_parse_bounded_old_school_syntax() {
    assert_eq!(
        parse_input("/wall").unwrap(),
        InputCommand::Wall(WallCommand::Recent { limit: 20 })
    );
    assert_eq!(
        parse_input("/wall 7").unwrap(),
        InputCommand::Wall(WallCommand::Recent { limit: 7 })
    );
    assert_eq!(
        parse_input("/wall oldest 3").unwrap(),
        InputCommand::Wall(WallCommand::Oldest { limit: 3 })
    );
    assert_eq!(
        parse_input("/wall mine").unwrap(),
        InputCommand::Wall(WallCommand::Mine { limit: 20 })
    );
    assert_eq!(
        parse_input("/wall since 24h 9").unwrap(),
        InputCommand::Wall(WallCommand::Since {
            seconds: 86_400,
            limit: 9
        })
    );
    assert_eq!(
        parse_input("/wall post hello from the commons").unwrap(),
        InputCommand::Wall(WallCommand::Post {
            text: "hello from the commons".to_string()
        })
    );
    assert_eq!(
        parse_input("/wall ai Alpha say something memorable").unwrap(),
        InputCommand::Wall(WallCommand::AiPost {
            nick: "Alpha".to_string(),
            prompt: "say something memorable".to_string()
        })
    );
    let object_ref = format!("object:{}", "a".repeat(64));
    assert_eq!(
        parse_input(&format!("/wall inspect {object_ref}")).unwrap(),
        InputCommand::Wall(WallCommand::Inspect {
            event_ref: object_ref.clone()
        })
    );
    assert_eq!(
        parse_input(&format!("/wall tombstone {object_ref} duplicate post")).unwrap(),
        InputCommand::Wall(WallCommand::Tombstone {
            post_ref: object_ref,
            reason: "duplicate post".to_string()
        })
    );
}

#[test]
fn wall_parser_rejects_unbounded_limits_and_bad_duration() {
    assert!(parse_input("/wall 0").is_err());
    assert!(parse_input("/wall 101").is_err());
    assert!(parse_input("/wall since yesterday").is_err());
    assert!(command_completions("/wal").contains(&"/wall"));
}
