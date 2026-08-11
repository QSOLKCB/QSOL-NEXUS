from __future__ import annotations

import copy
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator, MAX_EVIDENCE_OBJECT_CHARS
from nexus_runtime.game_un import GAME_SCHEMA, MAX_EVENT_LOG, advance_turn, apply_action, inspect_game, new_game
from nexus_runtime.world import WorldStore


class UNSimulationEngineTests(unittest.TestCase):
    def test_same_seed_produces_same_content_addressed_initial_state(self) -> None:
        world = WorldStore()
        first = new_game(world, "forum-night")
        second = new_game(world, "forum-night")
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(first.payload["schema"], GAME_SCHEMA)
        self.assertTrue(first.payload["fictional_only"])
        self.assertEqual(len(first.payload["wars"]), 1)

    def test_game_starts_with_only_fictional_country_ids(self) -> None:
        game = new_game(WorldStore(), "fake-map")
        self.assertEqual(
            set(game.payload["countries"]),
            {"troutistan", "bananovia", "kestrelia", "sablemere", "wombatia", "pixelgrad"},
        )
        self.assertFalse(game.payload["claim_boundary"]["real_world_policy_claim"])
        self.assertFalse(game.payload["claim_boundary"]["real_weapon_procurement"])

    def test_same_action_from_same_state_is_deterministic(self) -> None:
        world = WorldStore()
        game = new_game(world, "deterministic-memes")
        target = sorted(game.payload["countries"])[0]
        first = apply_action(world, game.object_id, "meme", [target])
        second = apply_action(world, game.object_id, "meme", [target])
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(first.payload["previous_state_ref"], game.object_id)

    def test_arming_both_belligerents_is_abstract_and_costs_legitimacy(self) -> None:
        world = WorldStore()
        game = new_game(world, "arms-dealer-un")
        war = game.payload["wars"][0]
        targets = [war["a"], war["b"]]
        before = {target: game.payload["countries"][target]["military"] for target in targets}
        result = apply_action(world, game.object_id, "arms", targets)
        for target in targets:
            self.assertEqual(result.payload["countries"][target]["military"], before[target] + 1)
            self.assertEqual(result.payload["countries"][target]["arms_imports"], 1)
        self.assertEqual(result.payload["un_legitimacy"], game.payload["un_legitimacy"] - 1)
        self.assertTrue(any(event["kind"] == "arms_hypocrisy" for event in result.payload["event_log"]))
        self.assertFalse(result.payload["claim_boundary"]["real_weapon_procurement"])

    def test_arming_both_belligerents_is_detected_even_among_extra_targets(self) -> None:
        world = WorldStore()
        game = new_game(world, "arms-everyone")
        war = game.payload["wars"][0]
        extra = next(country_id for country_id in sorted(game.payload["countries"]) if country_id not in (war["a"], war["b"]))
        result = apply_action(world, game.object_id, "arms", [extra, war["b"], war["a"]])
        self.assertEqual(result.payload["un_legitimacy"], game.payload["un_legitimacy"] - 1)
        self.assertTrue(any(event["kind"] == "arms_hypocrisy" for event in result.payload["event_log"]))

    def test_suspend_and_reinstate_cannot_be_replayed_to_farm_influence(self) -> None:
        world = WorldStore()
        game = new_game(world, "procedural-farming")
        target = sorted(game.payload["countries"])[0]
        initial = game.payload["countries"][target]["influence"]

        suspended = apply_action(world, game.object_id, "suspend", [target])
        self.assertEqual(suspended.payload["countries"][target]["influence"], max(0, initial - 2))
        suspended_again = apply_action(world, suspended.object_id, "suspend", [target])
        self.assertEqual(
            suspended_again.payload["countries"][target]["influence"],
            suspended.payload["countries"][target]["influence"],
        )

        reinstated = apply_action(world, suspended_again.object_id, "reinstate", [target])
        once = reinstated.payload["countries"][target]["influence"]
        reinstated_again = apply_action(world, reinstated.object_id, "reinstate", [target])
        self.assertEqual(reinstated_again.payload["countries"][target]["influence"], once)

    def test_turn_resolution_is_deterministic_and_lineaged(self) -> None:
        world = WorldStore()
        game = new_game(world, "risk-ish")
        first = advance_turn(world, game.object_id)
        second = advance_turn(world, game.object_id)
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload["turn"], 1)
        self.assertEqual(first.payload["previous_state_ref"], game.object_id)
        self.assertEqual(first.payload["last_transition"], {"kind": "advance_turn", "turn": 1})

    def test_invalid_country_and_non_warring_mediation_fail_closed(self) -> None:
        world = WorldStore()
        game = new_game(world, "fail-closed")
        with self.assertRaises(ValueError):
            apply_action(world, game.object_id, "sanction", ["canada"])
        peaceful = sorted(set(game.payload["countries"]) - set(game.payload["wars"][0].values()))
        with self.assertRaises(ValueError):
            apply_action(world, game.object_id, "mediate", peaceful[:2])

    def test_current_game_state_has_compact_complete_council_evidence_view(self) -> None:
        world = WorldStore()
        game = new_game(world, "shared-board")
        state = game
        for _ in range(MAX_EVENT_LOG + 5):
            state = apply_action(world, state.object_id, "do_nothing", [])

        self.assertLessEqual(len(state.payload["event_log"]), MAX_EVENT_LOG)
        self.assertLess(len(state.payload["content"]), MAX_EVIDENCE_OBJECT_CHARS)
        context = CouncilCoordinator(world).build_evidence_context([state.object_id])
        self.assertIn("NEXUS UN SIMULATION", context)
        self.assertIn("world_tension=", context)
        self.assertIn("wars:", context)
        for country_id in state.payload["countries"]:
            self.assertIn(country_id, context)
        self.assertIn("not real-world policy", context)
        self.assertNotIn("[NEXUS: evidence excerpt truncated]", context)

    def test_inspect_rejects_non_game_object(self) -> None:
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


class UNSimulationAPITests(unittest.TestCase):
    def test_api_exposes_game_mode_region_and_operations(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["protocol"], "nexus/0.14")
        self.assertEqual(health["runtime_version"], "2.0.0")
        self.assertIn("game_un", health["world_modes"])
        self.assertEqual(health["geometry"], "named-regions-v4")
        self.assertIn("#un-sim", {game["room"] for game in health["games"]})
        geometry = api.handle({"operation": "world.geometry"})
        regions = {region["region_id"] for region in geometry["regions"]}
        self.assertIn("assembly", regions)
        operations = api.handle({"operation": "system.operations"})["operations"]
        for name in ("game.un.catalog", "game.un.new", "game.un.inspect", "game.un.act", "game.un.turn"):
            self.assertIn(name, operations)

    def test_api_game_lifecycle_returns_content_addressed_state(self) -> None:
        api = NexusAPI()
        created = api.handle({"operation": "game.un.new", "seed": "night-shift"})
        self.assertEqual(created["status"], "ok")
        game_ref = created["game_ref"]
        war = created["game"]["wars"][0]
        acted = api.handle(
            {
                "operation": "game.un.act",
                "game_ref": game_ref,
                "action": "arms",
                "targets": [war["a"], war["b"]],
            }
        )
        self.assertEqual(acted["status"], "ok")
        self.assertNotEqual(acted["game_ref"], game_ref)
        advanced = api.handle({"operation": "game.un.turn", "game_ref": acted["game_ref"]})
        self.assertEqual(advanced["status"], "ok")
        self.assertEqual(advanced["game"]["turn"], 1)
        inspected = api.handle({"operation": "game.un.inspect", "game_ref": advanced["game_ref"]})
        self.assertEqual(inspected["game"], advanced["game"])

    def test_seed_is_secret_scrubbed_before_persistence(self) -> None:
        api = NexusAPI()
        secret = "ghp_" + "Z" * 32
        created = api.handle({"operation": "game.un.new", "seed": f"campaign-{secret}"})
        self.assertEqual(created["status"], "ok")
        self.assertTrue(created["secret_scrub"]["changed"])
        self.assertNotIn(secret, str(created))


if __name__ == "__main__":
    unittest.main()
