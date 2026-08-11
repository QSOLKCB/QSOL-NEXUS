from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.culture_lineage import MAX_CHESS_LINEAGE_STATES
from nexus_runtime.psyche_chess_hardened import (
    MAX_PSYCHE_CHESS_LINEAGE_STATES,
    add_psyche,
    apply_psyche_chess_move,
    inspect_psyche_chess,
    new_psyche_chess,
)
from nexus_runtime.world import WorldStore


class AICultureCodexReviewTests(unittest.TestCase):
    @staticmethod
    def _member(member_id: str, model_id: str) -> dict[str, str]:
        return {
            "member_id": member_id,
            "model_id": model_id,
            "adapter_id": "mock",
            "profile": "balanced",
        }

    def _api(self, root: Path):
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    def _ai_long_shift_turn(self, api, member_id: str, model_id: str, choice_id: str, game_ref: str):
        member = self._member(member_id, model_id)
        actor = api._actor(member)
        with mock.patch.object(api, "_culture_actor", return_value=actor), mock.patch.object(
            actor, "direct_message", return_value=choice_id
        ):
            return api.handle({"operation": "long.shift.ai_act", "game_ref": game_ref, "member": member})

    def _ai_chess_move(self, api, member_id: str, model_id: str, move: str, game_ref: str):
        member = self._member(member_id, model_id)
        actor = api._actor(member)
        with mock.patch.object(api, "_culture_actor", return_value=actor), mock.patch.object(
            actor, "direct_message", return_value=move
        ):
            return api.handle({"operation": "psyche.chess.ai_move", "game_ref": game_ref, "member": member})

    def test_long_shift_credit_is_bound_to_executed_model_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "long.shift.new",
                    "seed": "codex-model-binding",
                    "players": ["Alpha"],
                    "human_players": [],
                }
            )
            manual = api.handle(
                {
                    "operation": "long.shift.act",
                    "game_ref": created["game_ref"],
                    "player_id": "Alpha",
                    "choice_id": "diagnose",
                }
            )
            self.assertEqual(manual["status"], "error")
            self.assertEqual(manual["error"]["code"], "culture_ai_execution_required")

            ref = created["game_ref"]
            for choice in ("diagnose", "patch", "brief", "inspect", "calculate", "document"):
                result = self._ai_long_shift_turn(api, "Alpha", "mock-alpha", choice, ref)
                self.assertEqual(result["status"], "ok")
                self.assertIn("execution_ref", result)
                ref = result["game_ref"]
            self.assertTrue(result["game"]["completed"])

            impostor = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member("Alpha", "mock-impostor"),
                    "game_kind": "long_shift",
                    "game_ref": ref,
                }
            )
            self.assertEqual(impostor["status"], "error")
            self.assertEqual(impostor["error"]["code"], "progression_game_execution_mismatch")

            credited = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member("Alpha", "mock-alpha"),
                    "game_kind": "long_shift",
                    "game_ref": ref,
                }
            )
            self.assertEqual(credited["status"], "ok")

    def test_psyche_chess_credit_is_bound_to_executed_model_moves(self) -> None:
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
            manual = api.handle(
                {
                    "operation": "psyche.chess.move",
                    "game_ref": created["game_ref"],
                    "player_id": "Alpha",
                    "move": "f2f3",
                }
            )
            self.assertEqual(manual["status"], "error")
            self.assertEqual(manual["error"]["code"], "culture_ai_execution_required")

            ref = created["game_ref"]
            for player, model_id, move in (
                ("Alpha", "mock-alpha", "f2f3"),
                ("Beta", "mock-beta", "e7e5"),
                ("Alpha", "mock-alpha", "g2g4"),
                ("Beta", "mock-beta", "d8h4"),
            ):
                result = self._ai_chess_move(api, player, model_id, move, ref)
                self.assertEqual(result["status"], "ok")
                ref = result["game_ref"]
            self.assertTrue(result["game"]["completed"])

            impostor = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member("Beta", "mock-not-beta"),
                    "game_kind": "psyche_chess",
                    "game_ref": ref,
                }
            )
            self.assertEqual(impostor["status"], "error")
            self.assertEqual(impostor["error"]["code"], "progression_game_execution_mismatch")

            credited = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._member("Beta", "mock-beta"),
                    "game_kind": "psyche_chess",
                    "game_ref": ref,
                }
            )
            self.assertEqual(credited["status"], "ok")

    def test_bounded_chess_event_log_keeps_monotonic_sequences(self) -> None:
        world = WorldStore()
        state = new_psyche_chess(
            world,
            white_player="Alpha",
            black_player="Beta",
            human_players=["Alpha", "Beta"],
        )
        ref = state.object_id
        cycle = (
            ("Alpha", "Beta", "g1f3"),
            ("Beta", "Alpha", "g8f6"),
            ("Alpha", "Beta", "f3g1"),
            ("Beta", "Alpha", "f6g8"),
        )
        for index in range(9):
            for player, opponent, move in cycle:
                taunted = add_psyche(world, ref, from_player=opponent, text=f"banter-{index}-{player}")
                moved = apply_psyche_chess_move(world, taunted.object_id, player_id=player, move=move)
                ref = moved.object_id
        final = inspect_psyche_chess(world, ref)
        sequences = [event["sequence"] for event in final.payload["event_log"]]
        self.assertEqual(len(sequences), 64)
        self.assertEqual(sequences, list(range(sequences[0], sequences[0] + 64)))
        self.assertGreater(sequences[-1], 64)

    def test_engine_and_replay_share_the_same_chess_lineage_bound(self) -> None:
        self.assertEqual(MAX_CHESS_LINEAGE_STATES, MAX_PSYCHE_CHESS_LINEAGE_STATES)
        world = WorldStore()
        genesis = new_psyche_chess(
            world,
            white_player="Alpha",
            black_player="Beta",
            human_players=["Alpha", "Beta"],
        )
        forged_payload = deepcopy(genesis.payload)
        forged_payload["event_log"] = [
            {
                "sequence": MAX_PSYCHE_CHESS_LINEAGE_STATES - 1,
                "kind": "new_game",
                "text": "synthetic bound probe",
            }
        ]
        forged = world.create_object(
            "psyche_chess_state",
            forged_payload,
            {"actor": "nexus_game_engine", "reason": "new_psyche_chess_game"},
        )
        with self.assertRaisesRegex(ValueError, "lineage-state limit"):
            add_psyche(world, forged.object_id, from_player="Beta", text="last permitted probe")


if __name__ == "__main__":
    unittest.main()
