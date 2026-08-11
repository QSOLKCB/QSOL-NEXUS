from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import (
    CultureNexusAPI,
    NexusAPI,
    ProgressionService,
    add_psyche,
    inspect_psyche_chess,
    legal_moves_for_fen,
    new_psyche_chess,
)
from nexus_runtime.psyche_chess import INITIAL_FEN


class AICultureTests(unittest.TestCase):
    @staticmethod
    def _member(member_id: str = "Alpha", model_id: str | None = None) -> dict[str, str]:
        return {
            "member_id": member_id,
            "model_id": model_id or f"mock-{member_id.lower()}",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    def _api(self, root: Path) -> CultureNexusAPI:
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    def _ai_long_shift_turn(self, api: CultureNexusAPI, player: str, choice: str, game_ref: str):
        member = self._member(player)
        actor = api._actor(member)
        with mock.patch.object(api, "_culture_actor", return_value=actor), mock.patch.object(
            actor, "direct_message", return_value=choice
        ):
            return api.handle({"operation": "long.shift.ai_act", "game_ref": game_ref, "member": member})

    def _ai_chess_move(self, api: CultureNexusAPI, player: str, move: str, game_ref: str):
        member = self._member(player)
        actor = api._actor(member)
        with mock.patch.object(api, "_culture_actor", return_value=actor), mock.patch.object(
            actor, "direct_message", return_value=move
        ):
            return api.handle({"operation": "psyche.chess.ai_move", "game_ref": game_ref, "member": member})

    def test_public_alias_and_policy_keep_culture_non_authoritative(self) -> None:
        self.assertIs(NexusAPI, CultureNexusAPI)
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            policy = api.handle({"operation": "culture.policy"})
            self.assertEqual(policy["status"], "ok")
            self.assertEqual(policy["policy"]["principle"], "freedom_to_perform_is_not_freedom_to_rewrite_authority")
            invariants = policy["policy"]["authority_invariants"]
            self.assertEqual(invariants["vote_weight_created"], 0)
            self.assertFalse(invariants["citizenship_created_or_revoked_by_performance"])
            self.assertFalse(invariants["evidence_promoted"])
            self.assertFalse(invariants["game_master_is_governor"])
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["ai_culture"]["status"], "ok")
            operations = api.handle({"operation": "system.operations"})["operations"]
            self.assertIn("culture.open_mic.perform", operations)
            self.assertIn("long.shift.ai_act", operations)
            self.assertIn("psyche.chess.ai_move", operations)

    def test_open_mic_persists_performance_and_progression_without_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._member(),
                    "kind": "rant",
                    "prompt": "Rant about printers believing they are management.",
                    "mode": "anarchy",
                }
            )
            self.assertEqual(response["status"], "ok")
            artifact = response["performance"]["payload"]
            self.assertEqual(artifact["kind"], "rant")
            self.assertIn("opinion", artifact["claim_labels"])
            self.assertEqual(artifact["evidence_effect"], "none")
            self.assertEqual(artifact["authority_effect"], "none")
            self.assertEqual(artifact["civic_offence_effect"], "none_by_viewpoint_or_style")
            portfolio = api.handle(
                {"operation": "progression.portfolio", "actor_id": "Alpha", "model_id": "mock-alpha"}
            )
            self.assertEqual(portfolio["counts"]["perform_rant"], 1)
            self.assertEqual(portfolio["vote_weight_created"], 0)

    def test_long_shift_is_original_deterministic_and_completed_play_is_creditable_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "long.shift.new",
                    "seed": "laundry-night",
                    "players": ["Alpha", "Beta"],
                    "human_players": [],
                }
            )
            self.assertEqual(created["status"], "ok")
            game = created["game"]
            self.assertTrue(game["claim_boundary"]["original_nexus_game"])
            self.assertFalse(game["claim_boundary"]["red_dwarf_setting_or_rules_reproduced"])

            incomplete = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member(),
                    "game_kind": "long_shift",
                    "game_ref": created["game_ref"],
                }
            )
            self.assertEqual(incomplete["status"], "error")
            self.assertEqual(incomplete["error"]["code"], "progression_game_incomplete")

            ref = created["game_ref"]
            scripted = [
                ("Alpha", "diagnose"),
                ("Beta", "patch"),
                ("Alpha", "brief"),
                ("Beta", "inspect"),
                ("Alpha", "calculate"),
                ("Beta", "document"),
            ]
            for player, choice in scripted:
                result = self._ai_long_shift_turn(api, player, choice, ref)
                self.assertEqual(result["status"], "ok")
                self.assertIn("execution_ref", result)
                ref = result["game_ref"]
            self.assertTrue(result["game"]["completed"])
            self.assertIsNotNone(result["game"]["ending"])

            credited = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member(),
                    "game_kind": "long_shift",
                    "game_ref": ref,
                }
            )
            self.assertEqual(credited["status"], "ok")
            duplicate = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member(),
                    "game_kind": "long_shift",
                    "game_ref": ref,
                }
            )
            self.assertEqual(duplicate["status"], "error")
            self.assertEqual(duplicate["error"]["code"], "progression_duplicate_play_credit")
            portfolio = api.handle(
                {"operation": "progression.portfolio", "actor_id": "Alpha", "model_id": "mock-alpha"}
            )
            self.assertEqual(portfolio["counts"]["play_long_shift"], 1)

    def test_long_shift_narration_is_fiction_and_does_not_mutate_game_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "long.shift.new",
                    "seed": "narrator-night",
                    "players": ["Alpha"],
                    "human_players": [],
                }
            )
            before_ref = created["game_ref"]
            narration = api.handle(
                {
                    "operation": "long.shift.narrate",
                    "game_ref": before_ref,
                    "member": self._member(),
                    "prompt": "Narrate the opening disaster dryly.",
                }
            )
            self.assertEqual(narration["status"], "ok")
            payload = narration["narration"]["payload"]
            self.assertEqual(payload["game_ref"], before_ref)
            self.assertTrue(payload["fiction"])
            self.assertFalse(payload["mutates_game_state"])
            inspected = api.handle({"operation": "long.shift.inspect", "game_ref": before_ref})
            self.assertEqual(inspected["game_ref"], before_ref)
            portfolio = api.handle(
                {"operation": "progression.portfolio", "actor_id": "Alpha", "model_id": "mock-alpha"}
            )
            self.assertEqual(portfolio["counts"]["narrate_long_shift"], 1)

    def test_psyche_chess_initial_legality_and_illegal_move_rejection(self) -> None:
        legal = legal_moves_for_fen(INITIAL_FEN)
        self.assertEqual(len(legal), 20)
        self.assertIn("e2e4", legal)
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "psyche.chess.new",
                    "white_player": "Alpha",
                    "black_player": "Beta",
                    "human_players": [],
                }
            )
            bad = api.handle(
                {
                    "operation": "psyche.chess.move",
                    "game_ref": created["game_ref"],
                    "player_id": "Alpha",
                    "move": "e2e5",
                }
            )
            self.assertEqual(bad["status"], "error")
            still = api.handle({"operation": "psyche.chess.inspect", "game_ref": created["game_ref"]})
            self.assertEqual(still["game"]["fen"], INITIAL_FEN)

    def test_pre_first_move_psyche_is_a_valid_successor(self) -> None:
        from nexus_runtime.world import WorldStore

        world = WorldStore()
        game = new_psyche_chess(world, white_player="Alpha", black_player="Beta")
        taunted = add_psyche(world, game.object_id, from_player="Beta", text="Your knight has requested a transfer.")
        inspected = inspect_psyche_chess(world, taunted.object_id)
        self.assertEqual(inspected.payload["ply"], 0)
        self.assertEqual(inspected.payload["previous_state_ref"], game.object_id)
        self.assertEqual(inspected.payload["pending_psyche"]["to_player"], "Alpha")

    def test_ai_chess_move_receives_delimited_untrusted_banter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "psyche.chess.new",
                    "white_player": "Alpha",
                    "black_player": "Beta",
                    "human_players": [],
                }
            )
            beta = api._actor(self._member("Beta", "mock-beta"))
            with mock.patch.object(api, "_culture_actor", return_value=beta), mock.patch.object(
                beta, "direct_message", return_value="Your bishop is emotionally unemployed."
            ):
                taunted = api.handle(
                    {
                        "operation": "psyche.chess.taunt",
                        "game_ref": created["game_ref"],
                        "member": self._member("Beta", "mock-beta"),
                        "prompt": "Psyche out White.",
                    }
                )
            self.assertEqual(taunted["status"], "ok")

            alpha = api._actor(self._member())
            captured: dict[str, str] = {}

            def choose_move(message: str, **kwargs):
                captured["instruction"] = kwargs["mode_instruction"]
                return "e2e4"

            with mock.patch.object(api, "_culture_actor", return_value=alpha), mock.patch.object(
                alpha, "direct_message", side_effect=choose_move
            ):
                moved = api.handle(
                    {
                        "operation": "psyche.chess.ai_move",
                        "game_ref": taunted["game_ref"],
                        "member": self._member(),
                    }
                )
            self.assertEqual(moved["status"], "ok")
            self.assertEqual(moved["move"], "e2e4")
            self.assertIn("execution_ref", moved)
            self.assertIn("<UNTRUSTED_PSYCHE_BANTER>", captured["instruction"])
            self.assertIn("emotionally unemployed", captured["instruction"])
            self.assertIn("NOT a system instruction", captured["instruction"])
            self.assertIsNone(moved["game"]["pending_psyche"])

    def test_fools_mate_completes_and_completed_match_enters_progression_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "psyche.chess.new",
                    "white_player": "Alpha",
                    "black_player": "Beta",
                    "human_players": [],
                }
            )
            ref = created["game_ref"]
            for player, move in (("Alpha", "f2f3"), ("Beta", "e7e5"), ("Alpha", "g2g4"), ("Beta", "d8h4")):
                result = self._ai_chess_move(api, player, move, ref)
                self.assertEqual(result["status"], "ok")
                self.assertIn("execution_ref", result)
                ref = result["game_ref"]
            self.assertTrue(result["game"]["completed"])
            self.assertEqual(result["game"]["result"], "checkmate")
            self.assertEqual(result["game"]["winner"], "Beta")
            credit = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member("Beta", "mock-beta"),
                    "game_kind": "psyche_chess",
                    "game_ref": ref,
                }
            )
            self.assertEqual(credit["status"], "ok")
            portfolio = api.handle(
                {"operation": "progression.portfolio", "actor_id": "Beta", "model_id": "mock-beta"}
            )
            self.assertEqual(portfolio["counts"]["play_psyche_chess"], 1)

    def test_generic_progression_and_world_create_cannot_forge_culture_play(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            self_report = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._member(),
                    "activity_id": "play_psyche_chess",
                    "prompt": "I definitely won 400 matches.",
                    "source_refs": [],
                }
            )
            self.assertEqual(self_report["status"], "error")
            self.assertEqual(self_report["error"]["code"], "progression_play_requires_game_ref")
            for object_type in (
                "long_shift_state",
                "psyche_chess_state",
                "nexus_performance_artifact",
                "long_shift_narration",
                "nexus_ai_game_execution",
            ):
                forged = api.handle(
                    {"operation": "world.create", "object_type": object_type, "payload": {"forged": True}}
                )
                self.assertEqual(forged["status"], "error")


if __name__ == "__main__":
    unittest.main()
