from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI, ProgressionNexusAPI
from nexus_runtime.progression import ProgressionService
from nexus_runtime.world_continuity import ContinuityWorldStore


class ProgressionTests(unittest.TestCase):
    def _api(self, root: Path) -> ProgressionNexusAPI:
        return NexusAPI(
            root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            stenographer_root=root / "stenographer",
            guardian_root=root / "guardian",
        )

    @staticmethod
    def _alpha() -> dict[str, object]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    def test_public_alias_and_policy_keep_progression_non_authoritative(self) -> None:
        self.assertIs(NexusAPI, ProgressionNexusAPI)
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            policy = api.handle({"operation": "progression.policy"})
            self.assertEqual(policy["status"], "ok")
            invariants = policy["policy"]["authority_invariants"]
            self.assertEqual(invariants["vote_weight_created"], 0)
            self.assertEqual(invariants["council_seats_created"], 0)
            self.assertFalse(invariants["citizenship_created"])
            self.assertFalse(invariants["evidence_promoted"])
            self.assertTrue(invariants["milestones_are_titles_not_powers"])

            operations = api.handle({"operation": "system.operations"})["operations"]
            self.assertIn("progression.act", operations)
            self.assertIn("progression.portfolio", operations)
            self.assertIn("life.paths.new", operations)
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["ai_progression"]["status"], "ok")

    def test_model_activity_creates_artifact_and_descriptive_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for index in range(3):
                response = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": "research",
                        "prompt": f"Investigate deterministic question {index}.",
                        "source_refs": [],
                    }
                )
                self.assertEqual(response["status"], "ok")
                self.assertEqual(response["authority_effect"], "none")
                self.assertEqual(response["portfolio_state"]["payload"]["vote_weight_created"], 0)

            portfolio = api.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(portfolio["total_activities"], 3)
            self.assertEqual(portfolio["counts"]["research"], 3)
            milestone_ids = {item["milestone_id"] for item in portfolio["milestones"]}
            self.assertIn("first_step", milestone_ids)
            self.assertIn("role:researcher", milestone_ids)
            self.assertEqual(portfolio["vote_weight_created"], 0)
            self.assertEqual(portfolio["citizenship_effect"], "none")
            self.assertEqual(portfolio["evidence_effect"], "none")

    def test_commission_assignment_and_activity_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            commission = api.handle(
                {
                    "operation": "progression.commission.create",
                    "title": "Archive cleanup",
                    "activity_id": "curate",
                    "brief": "Curate the supplied material into a concise map.",
                    "source_refs": [],
                    "assignee_id": "Alpha",
                }
            )["commission"]
            ref = commission["object_id"]
            wrong = api.handle(
                {
                    "operation": "progression.act",
                    "member": {
                        "member_id": "Beta",
                        "model_id": "mock-beta",
                        "adapter_id": "mock",
                    },
                    "activity_id": "curate",
                    "prompt": "Do the commission.",
                    "source_refs": [],
                    "commission_ref": ref,
                }
            )
            self.assertEqual(wrong["status"], "error")
            self.assertEqual(wrong["error"]["code"], "progression_commission_mismatch")

            right = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "curate",
                    "prompt": "Do the commission.",
                    "source_refs": [],
                    "commission_ref": ref,
                }
            )
            self.assertEqual(right["status"], "ok")
            self.assertEqual(right["activity"]["payload"]["commission_ref"], ref)

    def test_monopoly_ai_seat_can_enter_play_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            game = api.handle(
                {
                    "operation": "game.monopoly.new",
                    "seed": "progression-table",
                    "players": ["operator", "Alpha"],
                    "human_players": ["operator"],
                }
            )
            self.assertEqual(game["status"], "ok")
            recorded = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._alpha(),
                    "game_kind": "monopoly",
                    "game_ref": game["game_ref"],
                }
            )
            self.assertEqual(recorded["status"], "ok")
            self.assertEqual(recorded["activity"]["payload"]["activity_id"], "play_monopoly")
            self.assertEqual(recorded["authority_effect"], "none")

    def test_human_monopoly_seat_does_not_create_ai_progression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            game = api.handle(
                {
                    "operation": "game.monopoly.new",
                    "seed": "human-table",
                    "players": ["operator", "Alpha"],
                    "human_players": ["operator"],
                }
            )
            rejected = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": {
                        "member_id": "operator",
                        "model_id": "mock-operator",
                        "adapter_id": "mock",
                    },
                    "game_kind": "monopoly",
                    "game_ref": game["game_ref"],
                }
            )
            self.assertEqual(rejected["status"], "error")
            self.assertEqual(rejected["error"]["code"], "progression_game_identity_mismatch")

    def test_life_paths_is_original_all_ai_and_replayable_by_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            created = api.handle(
                {
                    "operation": "life.paths.new",
                    "seed": "road-47",
                    "players": ["Alpha"],
                    "human_players": [],
                }
            )
            self.assertEqual(created["status"], "ok")
            self.assertEqual(created["game"]["controllers"]["Alpha"], "ai")
            self.assertFalse(created["game"]["claim_boundary"]["commercial_game_of_life_rules_or_assets"])
            ref = created["game_ref"]
            choices = ["learn", "specialize", "mentor", "rebuild", "create", "archive"]
            for choice in choices:
                result = api.handle(
                    {
                        "operation": "life.paths.act",
                        "game_ref": ref,
                        "player_id": "Alpha",
                        "choice_id": choice,
                    }
                )
                self.assertEqual(result["status"], "ok")
                ref = result["game_ref"]
            self.assertTrue(result["game"]["completed"])
            self.assertIn("legacy[Alpha]", result["game"]["content"])

            play = api.handle(
                {
                    "operation": "progression.play.record",
                    "member": self._alpha(),
                    "game_kind": "life_paths",
                    "game_ref": ref,
                }
            )
            self.assertEqual(play["status"], "ok")
            self.assertEqual(play["activity"]["payload"]["activity_id"], "play_life_paths")

    def test_file_backed_portfolio_reconstructs_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._api(root)
            first.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "create",
                    "prompt": "Create a tiny handoff artifact.",
                    "source_refs": [],
                }
            )
            heads = root / "world" / "progression" / "heads.json"
            heads.unlink()

            second = self._api(root)
            portfolio = second.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(portfolio["status"], "ok")
            self.assertEqual(portfolio["total_activities"], 1)
            self.assertEqual(portfolio["counts"]["create"], 1)

    def test_stale_mutable_head_cannot_roll_back_immutable_progression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = self._api(root)
            refs: list[str] = []
            for activity in ("explore", "create"):
                result = api.handle(
                    {
                        "operation": "progression.act",
                        "member": self._alpha(),
                        "activity_id": activity,
                        "prompt": f"Do one {activity} activity.",
                        "source_refs": [],
                    }
                )
                refs.append(result["portfolio_state"]["object_id"])

            heads_path = root / "world" / "progression" / "heads.json"
            raw = json.loads(heads_path.read_text(encoding="utf-8"))
            key = "Alpha\u0000mock-alpha"
            raw["heads"][key] = refs[0]
            from nexus_runtime.canonical import canonical_json

            heads_path.write_text(canonical_json(raw) + "\n", encoding="utf-8")
            if __import__("os").name != "nt":
                heads_path.chmod(0o600)

            reopened = self._api(root)
            portfolio = reopened.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(portfolio["state_ref"], refs[1])
            self.assertEqual(portfolio["total_activities"], 2)

    def test_two_services_serialize_one_progression_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            world_a = ContinuityWorldStore(root / "world")
            world_b = ContinuityWorldStore(root / "world")
            first = ProgressionService(world_a)
            second = ProgressionService(world_b)

            def record(service: ProgressionService, activity: str) -> None:
                service.record_activity(
                    actor_id="Alpha",
                    model_id="mock-alpha",
                    activity_id=activity,
                    prompt=activity,
                    output=f"completed {activity}",
                    source_refs=[],
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(record, first, "explore"),
                    pool.submit(record, second, "create"),
                ]
                for future in futures:
                    future.result()

            final = ProgressionService(ContinuityWorldStore(root / "world")).portfolio(
                actor_id="Alpha",
                model_id="mock-alpha",
            )
            self.assertEqual(final["total_activities"], 2)
            self.assertEqual(final["counts"]["explore"], 1)
            self.assertEqual(final["counts"]["create"], 1)

    def test_public_world_create_cannot_forge_progression_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "ai_progression_state",
                    "payload": {},
                }
            )
            self.assertEqual(response["status"], "error")


if __name__ == "__main__":
    unittest.main()
