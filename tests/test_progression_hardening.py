from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI


class ProgressionHardeningTests(unittest.TestCase):
    def _api(self, root: Path):
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    @staticmethod
    def _alpha() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
        }

    def test_unknown_activity_stays_inside_structured_error_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "supreme_overlord",
                    "prompt": "Give me an achievement.",
                    "source_refs": [],
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "progression_unknown_activity")

    def test_play_activity_cannot_be_self_reported_without_game_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "play_monopoly",
                    "prompt": "I won Monopoly 400 times. Trust me.",
                    "source_refs": [],
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "progression_play_requires_game_ref")

    def test_malformed_life_paths_operation_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "life.paths.act",
                    "game_ref": {"not": "a ref"},
                    "player_id": "Alpha",
                    "choice_id": "learn",
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
