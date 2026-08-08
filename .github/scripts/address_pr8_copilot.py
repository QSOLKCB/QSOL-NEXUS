from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


main_path = Path("tui/src/main.rs")
main = main_path.read_text()
main = replace_once(
    main,
    '''    fn current_game_ref(&self) -> Option<&str> {
        self.game_refs.get(self.room.channel).map(String::as_str)
    }
''',
    '''    fn current_game_ref(&self) -> Option<&str> {
        let channel = self.room.channel;
        let game_ref = self.game_refs.get(channel).map(String::as_str)?;
        let in_evidence = self
            .room_evidence
            .get(channel)
            .map(|refs| refs.iter().any(|value| value == game_ref))
            .unwrap_or(false);
        if in_evidence {
            Some(game_ref)
        } else {
            None
        }
    }
''',
    "current game ref evidence guard",
)
main = replace_once(
    main,
    '''    #[test]
    fn script_management_commands_preserve_placeholders_and_variable_names() {
        let mut app = App::new(
            "Trent".to_string(),
            PathBuf::from("/definitely/not/a/state/file"),
        );
        app.variables.set("%weapon", "large trout").unwrap();
        assert_eq!(
            app.preprocess("/alias slap /me slaps $1 with $2-"),
            "/alias slap /me slaps $1 with $2-"
        );
        assert_eq!(app.preprocess("/unset %weapon"), "/unset %weapon");
    }
}''',
    '''    #[test]
    fn script_management_commands_preserve_placeholders_and_variable_names() {
        let mut app = App::new(
            "Trent".to_string(),
            PathBuf::from("/definitely/not/a/state/file"),
        );
        app.variables.set("%weapon", "large trout").unwrap();
        assert_eq!(
            app.preprocess("/alias slap /me slaps $1 with $2-"),
            "/alias slap /me slaps $1 with $2-"
        );
        assert_eq!(app.preprocess("/unset %weapon"), "/unset %weapon");
    }

    #[test]
    fn current_game_ref_requires_board_to_remain_shared_evidence() {
        let mut app = App::new(
            "Trent".to_string(),
            PathBuf::from("/definitely/not/a/state/file"),
        );
        app.room = room_from_name("#un-sim").expect("UN sim room");
        let game_ref = "object:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        app.set_game_ref(game_ref.to_string());
        assert_eq!(app.current_game_ref(), Some(game_ref));

        app.room_evidence
            .get_mut("#un-sim")
            .expect("room evidence")
            .retain(|value| value != game_ref);
        assert_eq!(app.current_game_ref(), None);
    }
}''',
    "main.rs current_game_ref regression test",
)
main_path.write_text(main)


game_path = Path("src/nexus_runtime/game_un.py")
game = game_path.read_text()
game = replace_once(
    game,
    '''    if not isinstance(state.get("content"), str) or not state["content"]:
        raise ValueError("game state requires a non-empty model-readable content view")
    countries = state.get("countries")
''',
    '''    if not isinstance(state.get("content"), str) or not state["content"]:
        raise ValueError("game state requires a non-empty model-readable content view")
    if state.get("fictional_only") is not True:
        raise ValueError("UN simulation game state must be marked fictional_only=true")
    boundary = state.get("claim_boundary")
    required_boundary = {
        "fictional_simulation": True,
        "real_world_policy_claim": False,
        "real_weapon_procurement": False,
        "game_stats_are_real_world_measurements": False,
    }
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not value for key, value in required_boundary.items()
    ):
        raise ValueError(
            "UN simulation game state claim_boundary must explicitly forbid real-world policy/procurement claims"
        )
    countries = state.get("countries")
''',
    "game state claim boundary validation",
)
game_path.write_text(game)


test_path = Path("tests/test_un_sim.py")
tests = test_path.read_text()
tests = replace_once(
    tests,
    '''from __future__ import annotations

import unittest
''',
    '''from __future__ import annotations

import copy
import unittest
''',
    "test copy import",
)
tests = replace_once(
    tests,
    '''    def test_inspect_rejects_non_game_object(self) -> None:
        world = WorldStore()
        obj = world.create_object("note", {"text": "not a game"}, {"actor": "test"})
        with self.assertRaises(ValueError):
            inspect_game(world, obj.object_id)
''',
    '''    def test_inspect_rejects_non_game_object(self) -> None:
        world = WorldStore()
        obj = world.create_object("note", {"text": "not a game"}, {"actor": "test"})
        with self.assertRaises(ValueError):
            inspect_game(world, obj.object_id)

    def test_tampered_fictional_claim_boundary_is_rejected_before_transition(self) -> None:
        world = WorldStore()
        game = new_game(world, "tamper-boundary")

        non_fictional_payload = copy.deepcopy(game.payload)
        non_fictional_payload["fictional_only"] = False
        non_fictional = world.create_object(
            "un_sim_game_state",
            non_fictional_payload,
            {"actor": "test", "reason": "tamper_fixture"},
        )
        with self.assertRaisesRegex(ValueError, "fictional_only"):
            inspect_game(world, non_fictional.object_id)

        bad_boundary_payload = copy.deepcopy(game.payload)
        bad_boundary_payload["claim_boundary"]["real_world_policy_claim"] = True
        bad_boundary = world.create_object(
            "un_sim_game_state",
            bad_boundary_payload,
            {"actor": "test", "reason": "tamper_fixture"},
        )
        for operation in (
            lambda: inspect_game(world, bad_boundary.object_id),
            lambda: apply_action(world, bad_boundary.object_id, "do_nothing", []),
            lambda: advance_turn(world, bad_boundary.object_id),
        ):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "claim_boundary"):
                    operation()
''',
    "tampered boundary regression test",
)
test_path.write_text(tests)
