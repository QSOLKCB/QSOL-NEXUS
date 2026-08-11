from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters import AdapterError
from nexus_runtime.canonical import canonical_json
from nexus_runtime.citizenship import CitizenshipError
from nexus_runtime.progression import (
    ACTIVITY_CATALOG,
    PROGRESSION_SCHEMA_VERSION,
    ProgressionError,
    ProgressionService,
)
from nexus_runtime.world import WorldStore
from nexus_runtime.world_continuity import ContinuityWorldStore


class ProgressionCodexReviewTests(unittest.TestCase):
    @staticmethod
    def _alpha() -> dict[str, str]:
        return {"member_id": "Alpha", "model_id": "mock-alpha", "adapter_id": "mock"}

    def _api(self, root: Path):
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    def test_direct_service_rejects_forged_game_state(self) -> None:
        world = WorldStore()
        forged = world.create_object(
            "monopoly_game_state",
            {"players": ["Alpha"], "controllers": {"Alpha": "ai"}},
            {"actor": "not_the_game_engine"},
        )
        service = ProgressionService(world)
        with self.assertRaises(ProgressionError) as raised:
            service.record_play(
                actor_id="Alpha",
                model_id="mock-alpha",
                activity_id="play_monopoly",
                game_ref=forged.object_id,
                game_kind="monopoly",
            )
        self.assertIn(raised.exception.code, {"progression_game_mismatch", "progression_game_provenance_invalid"})

    def test_commission_title_and_brief_are_injected_before_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            commission_ref = api.handle(
                {
                    "operation": "progression.commission.create",
                    "title": "Map the archive",
                    "activity_id": "research",
                    "brief": "Compare the two archival paths and explain the tradeoff.",
                    "source_refs": [],
                    "assignee_id": "Alpha",
                }
            )["commission"]["object_id"]
            actor = api._actor(self._alpha())
            captured: dict[str, str] = {}

            def direct_message(message: str, **kwargs):
                captured["instruction"] = kwargs["mode_instruction"]
                return "Commission completed from the stored brief."

            with mock.patch.object(api, "_activity_actor", return_value=actor), mock.patch.object(
                actor, "direct_message", side_effect=direct_message
            ):
                response = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "Complete the commission.",
                        "source_refs": [],
                        "commission_ref": commission_ref,
                    }
                )
            self.assertEqual(response["status"], "ok")
            self.assertIn("Map the archive", captured["instruction"])
            self.assertIn("Compare the two archival paths", captured["instruction"])

    def test_same_game_state_can_only_be_credited_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            game = api.handle(
                {
                    "operation": "game.monopoly.new",
                    "seed": "one-board-one-credit",
                    "players": ["operator", "Alpha"],
                    "human_players": ["operator"],
                }
            )
            request = {
                "operation": "progression.play.record",
                "member": self._alpha(),
                "game_kind": "monopoly",
                "game_ref": game["game_ref"],
            }
            self.assertEqual(api.handle(request)["status"], "ok")
            duplicate = api.handle(request)
            self.assertEqual(duplicate["status"], "error")
            self.assertEqual(duplicate["error"]["code"], "progression_duplicate_play_credit")
            portfolio = api.handle({"operation": "progression.portfolio", "actor_id": "Alpha", "model_id": "mock-alpha"})
            self.assertEqual(portfolio["counts"]["play_monopoly"], 1)
            self.assertEqual(portfolio["total_activities"], 1)

    def test_rebuild_binds_state_to_real_activity_artifact(self) -> None:
        world = WorldStore()
        note = world.create_object("note", {"content": "not progression"}, {"actor": "operator"})
        counts = {activity: 0 for activity in ACTIVITY_CATALOG}
        counts["research"] = 1
        world.create_object(
            "ai_progression_state",
            {
                "schema_version": PROGRESSION_SCHEMA_VERSION,
                "actor_id": "Alpha",
                "model_id": "mock-alpha",
                "sequence": 0,
                "previous_state_ref": None,
                "latest_activity_ref": note.object_id,
                "latest_commission_ref": None,
                "counts": counts,
                "total_activities": 1,
                "distinct_activity_types": 1,
                "milestones": [{"milestone_id": "first_step", "label": "First Step", "threshold": 1}],
                "recent_activity_refs": [note.object_id],
                "vote_weight_created": 0,
                "council_seats_created": 0,
                "citizenship_effect": "none",
                "evidence_effect": "none",
                "tool_authority_effect": "none",
            },
            {"actor": "nexus", "subsystem": "ai_progression"},
        )
        with self.assertRaises(ProgressionError) as raised:
            ProgressionService(world).portfolio(actor_id="Alpha", model_id="mock-alpha")
        self.assertEqual(raised.exception.code, "progression_lineage_invalid")

    def test_prompt_bound_rejects_before_actor_construction_or_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            with mock.patch.object(api, "_activity_actor") as activity_actor:
                response = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "x" * 8193,
                        "source_refs": [],
                    }
                )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "progression_invalid_activity")
            activity_actor.assert_not_called()

    def test_continuity_rebuild_traverses_manifest_history_constant_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            world = ContinuityWorldStore(Path(temporary) / "world")
            service = ProgressionService(world)
            service.record_activity(actor_id="Alpha", model_id="mock-alpha", activity_id="explore", prompt="one", output="one", source_refs=[])
            for index in range(8):
                world.create_object("note", {"index": index}, {"actor": "test"})
            with mock.patch.object(world, "_history", wraps=world._history) as history:
                portfolio = service.portfolio(actor_id="Alpha", model_id="mock-alpha")
            self.assertEqual(portfolio["total_activities"], 1)
            self.assertLessEqual(history.call_count, 2)

    def test_domain_errors_are_not_laundered_into_invalid_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            with mock.patch.object(
                api.citizenship,
                "assert_mode_access",
                side_effect=CitizenshipError("citizenship_mode_denied", "no civic access"),
            ):
                denied = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "test",
                        "source_refs": [],
                    }
                )
            self.assertEqual(denied["error"]["code"], "citizenship_mode_denied")

            actor = api._actor(self._alpha())
            with mock.patch.object(api, "_activity_actor", return_value=actor), mock.patch.object(
                actor, "direct_message", side_effect=AdapterError("provider down")
            ):
                unavailable = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": "test",
                        "source_refs": [],
                    }
                )
            self.assertEqual(unavailable["error"]["code"], "adapter_unavailable")

    def test_malformed_private_head_cache_is_rebuilt_from_immutable_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = self._api(root)
            first = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "create",
                    "prompt": "create one artifact",
                    "source_refs": [],
                }
            )
            self.assertEqual(first["status"], "ok")
            heads_path = root / "world" / "progression" / "heads.json"
            heads_path.write_text("{broken", encoding="utf-8")
            if os.name != "nt":
                heads_path.chmod(0o600)
            reopened = self._api(root)
            portfolio = reopened.handle({"operation": "progression.portfolio", "actor_id": "Alpha", "model_id": "mock-alpha"})
            self.assertEqual(portfolio["status"], "ok")
            self.assertEqual(portfolio["total_activities"], 1)
            repaired = json.loads(heads_path.read_text(encoding="utf-8"))
            self.assertEqual(heads_path.read_bytes(), (canonical_json(repaired) + "\n").encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
