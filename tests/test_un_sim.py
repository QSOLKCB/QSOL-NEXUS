from __future__ import annotations

import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.game_un import GAME_SCHEMA, advance_turn, apply_action, inspect_game, new_game
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

    def test_current_game_state_is_readable_as_council_evidence(self) -> None:
        world = WorldStore()
        game = new_game(world, "shared-board")
        context = CouncilCoordinator(world).build_evidence_context([game.object_id])
        self.assertIn("fictional_un_simulation", context)
        self.assertIn("troutistan", context)
        self.assertIn(game.payload["wars"][0]["a"], context)

    def test_inspect_rejects_non_game_object(self) -> None:
        world = WorldStore()
        obj = world.create_object("note", {"text": "not a game"}, {"actor": "test"})
        with self.assertRaises(ValueError):
            inspect_game(world, obj.object_id)


class UNSimulationAPITests(unittest.TestCase):
    def test_api_exposes_game_mode_region_and_operations(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["protocol"], "nexus/0.6")
        self.assertEqual(health["runtime_version"], "2.0.0-alpha6.2")
        self.assertIn("game_un", health["world_modes"])
        self.assertEqual(health["geometry"], "named-regions-v2")
        self.assertEqual(health["games"][0]["room"], "#un-sim")
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
