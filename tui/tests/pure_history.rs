use nexus_irc_tui::room_from_name;

#[test]
fn pure_history_room_shares_archive_geometry_without_aliasing_normal_history() {
    let pure = room_from_name("#pure-history").expect("#pure-history room");
    assert_eq!(pure.channel, "#pure-history");
    assert_eq!(pure.mode_id, "pure_history");
    assert_eq!(pure.region_id, "archive");

    let by_mode = room_from_name("pure_history").expect("pure_history mode");
    assert_eq!(by_mode.channel, "#pure-history");

    let ordinary = room_from_name("#archive").expect("historical room");
    assert_eq!(ordinary.mode_id, "historical");
    assert_eq!(ordinary.region_id, "archive");
}
