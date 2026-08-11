from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.trap import TrapError


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

    def test_generic_world_create_cannot_forge_progression_game_states(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in ("monopoly_game_state", "life_paths_state"):
                response = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {},
                        "provenance": {"actor": "nexus_game_engine", "reason": "forged"},
                    }
                )
                self.assertEqual(response["status"], "error")

    def test_copied_monopoly_payload_with_wrong_provenance_cannot_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            legitimate = api.handle(
                {
                    "operation": "game.monopoly.new",
                    "seed": "provenance-table",
                    "players": ["operator", "Alpha"],
                    "human_players": ["operator"],
                }
            )
            copied = api.world.create_object(
                "monopoly_game_state",
                legitimate["game"],
                {"actor": "human_operator", "reason": "copied_payload"},
            )
            response = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._alpha(),
                    "game_kind": "monopoly",
                    "game_ref": copied.object_id,
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "progression_game_provenance_invalid")

    def test_commission_sources_enter_model_context_before_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            source = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "note",
                    "payload": {"content": "commission source"},
                }
            )["object"]["object_id"]
            commission = api.handle(
                {
                    "operation": "progression.commission.create",
                    "title": "Use the source",
                    "activity_id": "research",
                    "brief": "Research the source object.",
                    "source_refs": [source],
                    "assignee_id": "Alpha",
                }
            )["commission"]["object_id"]
            with mock.patch.object(
                api.council,
                "build_evidence_context",
                wraps=api.council.build_evidence_context,
            ) as build_context:
                response = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "Complete the commission.",
                        "source_refs": [],
                        "commission_ref": commission,
                    }
                )
            self.assertEqual(response["status"], "ok")
            build_context.assert_called_once_with([source])
            self.assertEqual(response["activity"]["payload"]["source_refs"], [source])

    def test_trap_gate_rejects_mutating_progression_before_actor_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            with mock.patch.object(
                api.trap_mutation_gate,
                "assert_mutation_allowed",
                side_effect=TrapError("trap_incident_active", "quarantine active"),
            ), mock.patch.object(api, "_activity_actor") as actor:
                response = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "Do not call the actor.",
                        "source_refs": [],
                    }
                )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "trap_incident_active")
            actor.assert_not_called()

    def test_life_paths_seed_is_scrubbed_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            raw = "xai-1234567890abcdefghijklmnopqrstuvwxyz"
            response = api.handle(
                {
                    "operation": "life.paths.new",
                    "seed": raw,
                    "players": ["Alpha"],
                    "human_players": [],
                }
            )
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["secret_scrub"]["seed_changed"])
            self.assertNotIn(raw, response["game"]["seed"])

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
