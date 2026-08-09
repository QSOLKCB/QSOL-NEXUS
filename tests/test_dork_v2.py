from __future__ import annotations

from copy import deepcopy
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.game_dork import DORK_SCHEMA, apply_action, inspect_dork, new_dork, player_view
from nexus_runtime.world import WorldStore


class DORKV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def act(self, game, action: str, *args: str):
        return apply_action(self.world, game.object_id, "Trent", action, list(args))

    def test_opening_looks_familiar_then_reveals_dork(self) -> None:
        game = new_dork(self.world, "mailbox", "Trent")
        self.assertEqual(game.payload["schema"], DORK_SCHEMA)
        self.assertTrue(game.payload["human_only"])
        self.assertIn("open field west", game.payload["last_message"])
        game = self.act(game, "open", "mailbox")
        self.assertIn("ordinary Zork", game.payload["last_message"])
        game = self.act(game, "take", "dork_leaflet")
        game = self.act(game, "read", "dork_leaflet")
        self.assertIn("WELCOME TO DORK", game.payload["last_message"])
        view = player_view(game.payload, "Trent")
        self.assertTrue(view["human_only"])
        self.assertEqual(view["player_id"], "Trent")

    def test_ai_or_alternate_player_cannot_act_or_receive_view(self) -> None:
        game = new_dork(self.world, human_operator_id="Trent")
        with self.assertRaisesRegex(ValueError, "human-only"):
            apply_action(self.world, game.object_id, "Alpha", "look")
        with self.assertRaisesRegex(ValueError, "no AI"):
            player_view(game.payload, "Alpha")

    def test_full_adventure_path_reaches_grass_without_model_seat(self) -> None:
        game = new_dork(self.world, "full-run", "Trent")
        game = self.act(game, "open", "mailbox")
        game = self.act(game, "take", "dork_leaflet")
        game = self.act(game, "go", "north")
        game = self.act(game, "open", "window")
        game = self.act(game, "go", "in")
        game = self.act(game, "subscribe")
        game = self.act(game, "go", "down")
        game = self.act(game, "take", "tos_scroll")
        game = self.act(game, "take", "large_trout")
        game = self.act(game, "go", "west")
        game = self.act(game, "go", "south")
        game = self.act(game, "take", "nft_rock")
        game = self.act(game, "go", "north")
        game = self.act(game, "go", "north")
        game = self.act(game, "prompt")
        game = self.act(game, "take", "prompt_token")
        game = self.act(game, "go", "south")
        game = self.act(game, "go", "west")
        game = self.act(game, "ratio", "troll")
        game = self.act(game, "mute", "troll")
        game = self.act(game, "take", "legacy_banhammer")
        game = self.act(game, "go", "west")
        game = self.act(game, "take", "punch_card")
        game = self.act(game, "go", "down")
        game = self.act(game, "deploy")
        game = self.act(game, "take", "zero_dependency_crown")
        game = self.act(game, "go", "up")
        game = self.act(game, "go", "east")
        game = self.act(game, "go", "east")
        game = self.act(game, "go", "east")
        game = self.act(game, "go", "up")
        game = self.act(game, "go", "out")
        game = self.act(game, "go", "south")
        game = self.act(game, "grass")
        self.assertEqual(game.payload["status"], "won")
        self.assertEqual(game.payload["score"], 100)
        self.assertIn("touch grass", game.payload["last_message"])
        self.assertFalse(game.payload["claim_boundary"]["ai_player_seats"])

    def test_same_state_and_action_are_deterministic_and_content_is_derived(self) -> None:
        game = new_dork(self.world, "deterministic", "Trent")
        first = apply_action(self.world, game.object_id, "Trent", "look")
        second = apply_action(self.world, game.object_id, "Trent", "look")
        self.assertEqual(first.object_id, second.object_id)

        forged = deepcopy(game.payload)
        forged["content"] = "A model has taken the crown."
        obj = self.world.create_object("dork_v2_game_state", forged, {"actor": "forger"})
        with self.assertRaisesRegex(ValueError, "content view"):
            inspect_dork(self.world, obj.object_id)

    def test_full_word_direction_aliases_preserve_text_adventure_grammar(self) -> None:
        game = new_dork(self.world, "directions", "Trent")
        with self.assertRaisesRegex(ValueError, "extra arguments"):
            apply_action(self.world, game.object_id, "Trent", "north", ["please"])
        north = apply_action(self.world, game.object_id, "Trent", "north")
        self.assertEqual(north.payload["room_id"], "north_of_startup")
        opened = apply_action(self.world, north.object_id, "Trent", "open", ["window"])
        entered = apply_action(self.world, opened.object_id, "Trent", "enter")
        self.assertEqual(entered.payload["room_id"], "landing_page")
        exited = apply_action(self.world, entered.object_id, "Trent", "exit")
        self.assertEqual(exited.payload["room_id"], "north_of_startup")


class DORKV2APITests(unittest.TestCase):
    def test_api_is_human_only_and_scrubs_seed(self) -> None:
        api = NexusAPI()
        secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD"
        created = api.handle(
            {
                "operation": "game.dork.new",
                "human_player_id": "Trent",
                "seed": f"mail-{secret}",
            }
        )
        self.assertEqual(created["status"], "ok")
        self.assertTrue(created["secret_scrub"]["changed"])
        self.assertNotIn(secret, created["game"]["seed"])
        rejected = api.handle(
            {
                "operation": "game.dork.act",
                "game_ref": created["game_ref"],
                "player_id": "Alpha",
                "action": "look",
                "args": [],
            }
        )
        self.assertEqual(rejected["status"], "error")
        self.assertIn("human-only", rejected["error"]["message"])


if __name__ == "__main__":
    unittest.main()
