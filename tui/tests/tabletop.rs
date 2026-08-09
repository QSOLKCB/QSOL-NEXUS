use nexus_irc_tui::{parse_input, room_from_name, InputCommand, TableCommand};

#[test]
fn tabletop_rooms_map_to_explicit_modes() {
    assert_eq!(room_from_name("#uno").unwrap().mode_id, "game_uno");
    assert_eq!(room_from_name("monopoly").unwrap().mode_id, "game_monopoly");
    assert_eq!(room_from_name("#500").unwrap().region_id, "commons");
    assert_eq!(
        room_from_name("blackjack").unwrap().mode_id,
        "game_blackjack"
    );
    assert_eq!(room_from_name("#dork").unwrap().region_id, "dungeon");
}

#[test]
fn parses_human_and_ai_table_actions() {
    assert_eq!(
        parse_input("/uno play red-7-a").unwrap(),
        InputCommand::Table(TableCommand::Act {
            game_id: "uno".to_string(),
            player: None,
            action: "play".to_string(),
            args: vec!["red-7-a".to_string()],
        })
    );
    assert_eq!(
        parse_input("/500 as Alpha bid 7H").unwrap(),
        InputCommand::Table(TableCommand::Act {
            game_id: "500".to_string(),
            player: Some("Alpha".to_string()),
            action: "bid".to_string(),
            args: vec!["7H".to_string()],
        })
    );
    assert_eq!(
        parse_input("/blackjack new canonical-shoe").unwrap(),
        InputCommand::Table(TableCommand::New {
            game_id: "blackjack".to_string(),
            seed: "canonical-shoe".to_string(),
        })
    );
}

#[test]
fn dork_parser_has_no_proxy_player_surface() {
    assert!(parse_input("/dork as Grok n").is_err());
    assert!(parse_input("/dork status Grok").is_err());
    assert_eq!(
        parse_input("/dork n").unwrap(),
        InputCommand::Table(TableCommand::Act {
            game_id: "dork".to_string(),
            player: None,
            action: "n".to_string(),
            args: vec![],
        })
    );
}
