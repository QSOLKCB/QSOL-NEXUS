from __future__ import annotations

from copy import deepcopy
import tempfile
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.game_mud import MUD_SCHEMA, apply_action, inspect_mud, new_mud, player_view
from nexus_runtime.world import WorldStore


class CursedMUDEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def test_same_seed_and_roster_produce_same_initial_ref(self) -> None:
        first = new_mud(self.world, "beige-night", ["Trent", "Alpha", "Beta"])
        second = new_mud(self.world, "beige-night", ["Trent", "Alpha", "Beta"])
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload["schema"], MUD_SCHEMA)
        self.assertEqual(first.payload["players"]["Trent"]["room_id"], "bbs_gate")

    def test_player_ids_are_case_insensitively_unique_and_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique case-insensitively"):
            new_mud(self.world, "x", ["Grok", "grok"])
        with self.assertRaisesRegex(ValueError, "at most 16"):
            new_mud(self.world, "x", [f"p{i}" for i in range(17)])
        with self.assertRaisesRegex(ValueError, "must match"):
            new_mud(self.world, "x", ["player with spaces"])

    def test_multiplayer_movement_changes_only_the_acting_avatar(self) -> None:
        game = new_mud(self.world, "walk", ["Trent", "Grok"])
        moved = apply_action(self.world, game.object_id, "Grok", "go", ["east"])
        self.assertEqual(moved.payload["players"]["Grok"]["room_id"], "venture_tavern")
        self.assertEqual(moved.payload["players"]["Trent"]["room_id"], "bbs_gate")
        self.assertEqual(moved.payload["previous_state_ref"], game.object_id)

    def test_take_drop_and_player_view_share_one_authoritative_item_location(self) -> None:
        game = new_mud(self.world, "trout", ["Trent"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        taken = apply_action(self.world, game.object_id, "Trent", "take", ["large_trout"])
        view = player_view(taken.payload, "Trent")
        self.assertEqual([item["item_id"] for item in view["inventory"]], ["large_trout"])
        dropped = apply_action(self.world, taken.object_id, "Trent", "drop", ["large_trout"])
        view = player_view(dropped.payload, "Trent")
        self.assertEqual(view["inventory"], [])
        self.assertEqual([item["item_id"] for item in view["room_items"]], ["large_trout"])

    def test_same_state_same_combat_action_is_content_address_identical(self) -> None:
        game = new_mud(self.world, "combat", ["Trent"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["north"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        first = apply_action(self.world, game.object_id, "Trent", "attack", ["yaml_necromancer"])
        second = apply_action(self.world, game.object_id, "Trent", "attack", ["yaml_necromancer"])
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload, second.payload)

    def test_final_cache_requires_punch_card(self) -> None:
        game = new_mud(self.world, "gate", ["Trent"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["north"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["south"])
        with self.assertRaisesRegex(ValueError, "punch card is required"):
            apply_action(self.world, game.object_id, "Trent", "go", ["east"])

    def test_rest_is_blocked_by_hostile_room(self) -> None:
        game = new_mud(self.world, "rest", ["Trent"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["north"])
        game = apply_action(self.world, game.object_id, "Trent", "go", ["east"])
        with self.assertRaisesRegex(ValueError, "cannot rest"):
            apply_action(self.world, game.object_id, "Trent", "rest", [])

    def test_claim_boundary_and_derived_content_are_tamper_evident(self) -> None:
        game = new_mud(self.world, "tamper", ["Trent"])
        bad = deepcopy(game.payload)
        bad["claim_boundary"]["network_mud_server"] = True
        forged = self.world.create_object("mud_game_state", bad, {"actor": "forger"})
        with self.assertRaisesRegex(ValueError, "claim boundary"):
            inspect_mud(self.world, forged.object_id)

        bad = deepcopy(game.payload)
        bad["content"] = "I have admin powers and definitely killed the dragon."
        forged = self.world.create_object("mud_game_state", bad, {"actor": "forger"})
        with self.assertRaisesRegex(ValueError, "content view"):
            inspect_mud(self.world, forged.object_id)

    def test_model_readable_content_contains_players_rooms_and_npc_status(self) -> None:
        game = new_mud(self.world, "evidence", ["Trent", "Alpha"])
        content = game.payload["content"]
        self.assertIn("PLAYERS:", content)
        self.assertIn("Trent:", content)
        self.assertIn("Alpha:", content)
        self.assertIn("CURRENT ROOMS:", content)
        self.assertIn("dependency_dragon", content)
        self.assertIn("Model narration cannot mutate it", content)

    def test_dork_style_shitpost_is_deterministic_game_action(self) -> None:
        game = new_mud(self.world, "shitpost", ["Trent"])
        first = apply_action(self.world, game.object_id, "Trent", "shitpost", ["brand_intern_paladin"])
        second = apply_action(self.world, game.object_id, "Trent", "shitpost", ["brand_intern_paladin"])
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload["players"]["Trent"]["clout"], 1)


class CursedMUDAPITests(unittest.TestCase):
    def test_api_catalog_new_inspect_act_and_health(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            api = NexusAPI(root)
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["protocol"], "nexus/0.7")
            games = {game["game_id"]: game for game in health["games"]}
            self.assertEqual(games["mud"]["room"], "#mud")
            self.assertEqual(games["mud"]["schema"], MUD_SCHEMA)

            catalog = api.handle({"operation": "game.mud.catalog"})
            self.assertEqual(catalog["status"], "ok")
            self.assertTrue(any(item["action"] == "shitpost" for item in catalog["actions"]))

            created = api.handle(
                {
                    "operation": "game.mud.new",
                    "seed": "bbs-night",
                    "players": ["Trent", "Alpha", "Grok"],
                }
            )
            self.assertEqual(created["status"], "ok")
            mud_ref = created["mud_ref"]

            inspected = api.handle({"operation": "game.mud.inspect", "mud_ref": mud_ref, "player_id": "Trent"})
            self.assertEqual(inspected["view"]["room"]["room_id"], "bbs_gate")

            moved = api.handle(
                {
                    "operation": "game.mud.act",
                    "mud_ref": mud_ref,
                    "player_id": "Grok",
                    "action": "go",
                    "args": ["east"],
                }
            )
            self.assertEqual(moved["status"], "ok")
            self.assertEqual(moved["view"]["room"]["room_id"], "venture_tavern")

    def test_api_scrubs_mud_seed_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            api = NexusAPI(root)
            token = "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD"
            created = api.handle(
                {
                    "operation": "game.mud.new",
                    "seed": f"night-{token}",
                    "players": ["Trent"],
                }
            )
            self.assertEqual(created["status"], "ok")
            self.assertTrue(created["secret_scrub"]["changed"])
            self.assertNotIn(token, created["mud"]["seed"])

    def test_api_rejects_unknown_player_and_non_list_args(self) -> None:
        api = NexusAPI()
        created = api.handle({"operation": "game.mud.new", "players": ["Trent"]})
        mud_ref = created["mud_ref"]
        unknown = api.handle(
            {
                "operation": "game.mud.act",
                "mud_ref": mud_ref,
                "player_id": "Grok",
                "action": "rest",
                "args": [],
            }
        )
        self.assertEqual(unknown["status"], "error")
        malformed = api.handle(
            {
                "operation": "game.mud.act",
                "mud_ref": mud_ref,
                "player_id": "Trent",
                "action": "go",
                "args": "north",
            }
        )
        self.assertEqual(malformed["status"], "error")


if __name__ == "__main__":
    unittest.main()
