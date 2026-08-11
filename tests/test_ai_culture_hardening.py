from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI, ProgressionService
from nexus_runtime import long_shift as long_shift_module
from nexus_runtime.progression import PR47_ACTIVITY_IDS, ProgressionError
from nexus_runtime.progression_core import (
    PROGRESSION_ACTIVITY_OBJECT_TYPE,
    PROGRESSION_SCHEMA_VERSION,
    PROGRESSION_STATE_OBJECT_TYPE,
    _milestones,
)
from nexus_runtime.world import WorldStore


class AICultureHardeningTests(unittest.TestCase):
    @staticmethod
    def _alpha() -> dict[str, str]:
        return {"member_id": "Alpha", "model_id": "mock-alpha", "adapter_id": "mock", "profile": "balanced"}

    def _api(self, root: Path):
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    def test_pr47_portfolio_state_survives_pr48_activity_catalog_extension(self) -> None:
        world = WorldStore()
        activity = world.create_object(
            PROGRESSION_ACTIVITY_OBJECT_TYPE,
            {
                "schema_version": PROGRESSION_SCHEMA_VERSION,
                "actor_id": "Alpha",
                "model_id": "mock-alpha",
                "activity_id": "research",
                "prompt": "legacy research prompt",
                "output": "legacy research output",
                "source_refs": [],
                "commission_ref": None,
                "play_binding": None,
                "evidence_effect": "none",
                "authority_effect": "none",
            },
            {"actor": "nexus", "subsystem": "ai_progression"},
        )
        counts = {activity_id: 0 for activity_id in PR47_ACTIVITY_IDS}
        counts["research"] = 1
        legacy = world.create_object(
            PROGRESSION_STATE_OBJECT_TYPE,
            {
                "schema_version": PROGRESSION_SCHEMA_VERSION,
                "actor_id": "Alpha",
                "model_id": "mock-alpha",
                "sequence": 0,
                "previous_state_ref": None,
                "latest_activity_ref": activity.object_id,
                "latest_commission_ref": None,
                "counts": counts,
                "total_activities": 1,
                "distinct_activity_types": 1,
                "milestones": _milestones(counts),
                "recent_activity_refs": [activity.object_id],
                "vote_weight_created": 0,
                "council_seats_created": 0,
                "citizenship_effect": "none",
                "evidence_effect": "none",
                "tool_authority_effect": "none",
            },
            {"actor": "nexus", "subsystem": "ai_progression"},
        )
        service = ProgressionService(world)
        portfolio = service.portfolio(actor_id="Alpha", model_id="mock-alpha")
        self.assertEqual(portfolio["state_ref"], legacy.object_id)
        self.assertEqual(portfolio["counts"]["research"], 1)
        self.assertEqual(portfolio["counts"]["perform_rant"], 0)
        self.assertEqual(portfolio["counts"]["play_psyche_chess"], 0)

        successor = service.record_activity(
            actor_id="Alpha",
            model_id="mock-alpha",
            activity_id="create",
            prompt="new post-upgrade contribution",
            output="new post-upgrade output",
            source_refs=[],
        )
        next_counts = successor["portfolio_state"]["payload"]["counts"]
        self.assertEqual(next_counts["research"], 1)
        self.assertEqual(next_counts["create"], 1)
        self.assertEqual(next_counts["perform_rant"], 0)

    def test_direct_progression_service_refuses_self_reported_culture_activity(self) -> None:
        service = ProgressionService(WorldStore())
        with self.assertRaises(ProgressionError) as raised:
            service.record_activity(
                actor_id="Alpha",
                model_id="mock-alpha",
                activity_id="perform_rant",
                prompt="I performed at Open Mic.",
                output="Trust me, it was devastating.",
                source_refs=[],
            )
        self.assertEqual(raised.exception.code, "progression_dedicated_surface_required")

    def test_public_generic_progression_refuses_performance_self_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "perform_standup",
                    "prompt": "Pretend this happened at Open Mic.",
                    "source_refs": [],
                }
            )
            self.assertEqual(response["status"], "error")
            self.assertEqual(response["error"]["code"], "progression_dedicated_surface_required")

    def test_forged_valid_looking_completed_long_shift_state_cannot_gain_credit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "long.shift.new",
                    "seed": "forgery-night",
                    "players": ["Alpha"],
                    "human_players": [],
                }
            )
            ref = created["game_ref"]
            for choice in ("diagnose", "patch", "brief", "inspect", "calculate", "document"):
                result = api.handle(
                    {"operation": "long.shift.act", "game_ref": ref, "player_id": "Alpha", "choice_id": choice}
                )
                self.assertEqual(result["status"], "ok")
                ref = result["game_ref"]
            legitimate = api.world.inspect(ref)
            forged_payload = deepcopy(legitimate.payload)
            forged_payload["meters"]["weirdness"] = min(12, forged_payload["meters"]["weirdness"] + 1)
            forged_payload["ending"] = long_shift_module._ending(forged_payload["meters"])
            forged_payload["content"] = long_shift_module._content(forged_payload)
            forged = api.world.create_object(
                "long_shift_state",
                forged_payload,
                {"actor": "nexus_game_engine", "reason": "long_shift_transition"},
            )
            # The current-state structural inspector alone accepts this object;
            # progression must additionally replay its predecessor lineage.
            long_shift_module.inspect_long_shift(api.world, forged.object_id)
            rejected = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._alpha(),
                    "game_kind": "long_shift",
                    "game_ref": forged.object_id,
                }
            )
            self.assertEqual(rejected["status"], "error")
            self.assertEqual(rejected["error"]["code"], "progression_game_mismatch")

    def test_progression_policy_names_all_four_authoritative_play_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            policy = api.handle({"operation": "progression.policy"})["policy"]
            rule = policy["play_rule"]
            self.assertIn("Monopoly", rule)
            self.assertIn("Life Paths", rule)
            self.assertIn("The Long Shift", rule)
            self.assertIn("Psyche-Out Chess", rule)
            self.assertIn("PR #47 progression states remain immutable", policy["compatibility_rule"])


if __name__ == "__main__":
    unittest.main()
