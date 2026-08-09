from __future__ import annotations

from copy import deepcopy
import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.game_blackjack import (
    BLACKJACK_SCHEMA,
    apply_action as apply_blackjack,
    inspect_blackjack,
    new_blackjack,
    player_view as blackjack_view,
)
from nexus_runtime.game_five_hundred import (
    FIVE_HUNDRED_SCHEMA,
    apply_action as apply_500,
    inspect_five_hundred,
    new_five_hundred,
    player_view as view_500,
)
from nexus_runtime.game_monopoly import (
    MONOPOLY_SCHEMA,
    apply_action as apply_monopoly,
    inspect_monopoly,
    new_monopoly,
)
from nexus_runtime.game_uno import (
    UNO_SCHEMA,
    WILD_RANKS,
    apply_action as apply_uno,
    inspect_uno,
    new_uno,
    player_view as uno_view,
)
from nexus_runtime.world import WorldStore


PLAYERS = ["Trent", "Alpha", "Beta", "Gamma"]


class DeterministicUNOTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def test_same_seed_and_roster_have_same_identity(self) -> None:
        first = new_uno(self.world, "same", PLAYERS, ["Trent"])
        second = new_uno(self.world, "same", PLAYERS, ["Trent"])
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload["controllers"]["Trent"], "human")
        self.assertEqual(first.payload["controllers"]["Alpha"], "ai")

    def test_private_view_exposes_only_requesting_hand(self) -> None:
        game = new_uno(self.world, "hidden", PLAYERS, ["Trent"])
        view = uno_view(game.payload, "Trent")
        self.assertEqual(len(view["hand"]), 7)
        self.assertNotIn("hands", view)
        opponent_card = game.payload["hands"]["Alpha"][0]["card_id"]
        self.assertNotIn(opponent_card, game.payload["content"])

    def test_same_state_and_action_are_content_address_identical(self) -> None:
        game = new_uno(self.world, "move", PLAYERS, ["Trent"])
        state = game.payload
        top = state["discard_pile"][-1]
        card = next(
            (
                item
                for item in state["hands"]["Trent"]
                if item["rank"] in WILD_RANKS
                or item["color"] == state["active_color"]
                or item["rank"] == top["rank"]
            ),
            None,
        )
        if card is None:
            first = apply_uno(self.world, game.object_id, "Trent", "draw")
            second = apply_uno(self.world, game.object_id, "Trent", "draw")
        else:
            args = [card["card_id"]]
            if card["rank"] in WILD_RANKS:
                args.append("red")
            first = apply_uno(self.world, game.object_id, "Trent", "play", args)
            second = apply_uno(self.world, game.object_id, "Trent", "play", args)
        self.assertEqual(first.object_id, second.object_id)
        with self.assertRaisesRegex(ValueError, "not that player's"):
            apply_uno(self.world, game.object_id, "Alpha", "draw")

    def test_tampered_content_is_rejected(self) -> None:
        game = new_uno(self.world, "tamper", ["Trent", "Alpha"], ["Trent"])
        forged = deepcopy(game.payload)
        forged["content"] = "Alpha has the blue seven. Trust me."
        obj = self.world.create_object("uno_game_state", forged, {"actor": "forger"})
        with self.assertRaisesRegex(ValueError, "content view"):
            inspect_uno(self.world, obj.object_id)

    def test_deterministic_table_can_play_to_completion(self) -> None:
        game = new_uno(self.world, "complete", PLAYERS, ["Trent"])
        for _ in range(2_000):
            if game.payload["phase"] == "complete":
                break
            state = game.payload
            player = state["players"][state["turn_index"]]
            if state["phase"] == "play":
                next_game = None
                for card in state["hands"][player]:
                    args = [card["card_id"]]
                    if card["rank"] in WILD_RANKS:
                        args.append("red")
                    try:
                        next_game = apply_uno(self.world, game.object_id, player, "play", args)
                        break
                    except ValueError:
                        pass
                game = next_game or apply_uno(self.world, game.object_id, player, "draw")
            else:
                card_id = state["drawn_card_id"]
                card = next(item for item in state["hands"][player] if item["card_id"] == card_id)
                args = [card_id, "red"] if card["rank"] in WILD_RANKS else [card_id]
                try:
                    game = apply_uno(self.world, game.object_id, player, "play", args)
                except ValueError:
                    game = apply_uno(self.world, game.object_id, player, "pass")
        self.assertEqual(game.payload["phase"], "complete")
        self.assertIn(game.payload["winner"], PLAYERS)


class DeterministicMonopolyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def test_original_board_and_deterministic_dice(self) -> None:
        game = new_monopoly(self.world, "dice", PLAYERS, ["Trent"])
        self.assertEqual(game.payload["schema"], MONOPOLY_SCHEMA)
        self.assertTrue(game.payload["claim_boundary"]["official_commercial_board_assets"] is False)
        first = apply_monopoly(self.world, game.object_id, "Trent", "roll")
        second = apply_monopoly(self.world, game.object_id, "Trent", "roll")
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(first.payload["last_roll"], second.payload["last_roll"])
        self.assertTrue(all(1 <= die <= 6 for die in first.payload["last_roll"]))
        inspect_monopoly(self.world, first.object_id)

    def test_out_of_turn_and_unowned_purchase_rules_are_enforced(self) -> None:
        game = new_monopoly(self.world, "turn", ["Trent", "Alpha"], ["Trent"])
        with self.assertRaisesRegex(ValueError, "not that player's"):
            apply_monopoly(self.world, game.object_id, "Alpha", "roll")
        rolled = apply_monopoly(self.world, game.object_id, "Trent", "roll")
        if rolled.payload["phase"] == "property_offer":
            offered = rolled.payload["pending_property"]
            bought = apply_monopoly(self.world, rolled.object_id, "Trent", "buy")
            self.assertEqual(bought.payload["assets"][offered]["owner"], "Trent")

    def test_bounded_table_reaches_a_canonical_winner(self) -> None:
        game = new_monopoly(self.world, "bounded", PLAYERS, ["Trent"])
        for _ in range(2_000):
            if game.payload["phase"] == "complete":
                break
            state = game.payload
            player = state["players"][state["turn_index"]]
            if state["phase"] == "await_roll":
                game = apply_monopoly(self.world, game.object_id, player, "roll")
            elif state["phase"] == "property_offer":
                try:
                    game = apply_monopoly(self.world, game.object_id, player, "buy")
                except ValueError:
                    game = apply_monopoly(self.world, game.object_id, player, "pass")
            else:
                next_game = None
                for property_id in state["accounts"][player]["properties"]:
                    try:
                        next_game = apply_monopoly(
                            self.world, game.object_id, player, "mortgage", [property_id]
                        )
                        break
                    except ValueError:
                        pass
                game = next_game or apply_monopoly(self.world, game.object_id, player, "bankrupt")
        self.assertEqual(game.payload["phase"], "complete")
        self.assertLessEqual(game.payload["turn_number"], 400)
        inspect_monopoly(self.world, game.object_id)

    def test_even_building_sale_mortgage_and_redemption_rules(self) -> None:
        game = new_monopoly(self.world, "build-0", ["Trent", "Alpha"], ["Trent"])
        brown = ["cobol_close", "punch_card_parade"]
        owner = None
        for _ in range(200):
            state = game.payload
            if state["phase"] == "complete":
                break
            player = state["players"][state["turn_index"]]
            if (
                state["phase"] == "await_roll"
                and state["accounts"][player]["cash"] >= 100
                and all(state["assets"][property_id]["owner"] == player for property_id in brown)
            ):
                owner = player
                break
            if state["phase"] == "await_roll":
                game = apply_monopoly(self.world, game.object_id, player, "roll")
            elif state["phase"] == "property_offer":
                try:
                    game = apply_monopoly(self.world, game.object_id, player, "buy")
                except ValueError:
                    game = apply_monopoly(self.world, game.object_id, player, "pass")
            else:
                next_game = None
                for property_id in state["accounts"][player]["properties"]:
                    try:
                        next_game = apply_monopoly(
                            self.world, game.object_id, player, "mortgage", [property_id]
                        )
                        break
                    except ValueError:
                        pass
                game = next_game or apply_monopoly(self.world, game.object_id, player, "bankrupt")

        self.assertIsNotNone(owner)
        game = apply_monopoly(self.world, game.object_id, owner, "build", [brown[0]])
        with self.assertRaisesRegex(ValueError, "evenly"):
            apply_monopoly(self.world, game.object_id, owner, "build", [brown[0]])
        game = apply_monopoly(self.world, game.object_id, owner, "build", [brown[1]])
        game = apply_monopoly(self.world, game.object_id, owner, "sell_house", [brown[0]])
        with self.assertRaisesRegex(ValueError, "color group"):
            apply_monopoly(self.world, game.object_id, owner, "mortgage", [brown[0]])
        game = apply_monopoly(self.world, game.object_id, owner, "sell_house", [brown[1]])
        game = apply_monopoly(self.world, game.object_id, owner, "mortgage", [brown[0]])
        self.assertTrue(game.payload["assets"][brown[0]]["mortgaged"])
        game = apply_monopoly(self.world, game.object_id, owner, "unmortgage", [brown[0]])
        self.assertFalse(game.payload["assets"][brown[0]]["mortgaged"])


class DeterministicFiveHundredTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def test_four_seat_partnership_auction_and_kitty(self) -> None:
        game = new_five_hundred(self.world, "auction", PLAYERS, ["Trent"])
        self.assertEqual(game.payload["schema"], FIVE_HUNDRED_SCHEMA)
        self.assertEqual(game.payload["teams"], {"team_0": ["Trent", "Beta"], "team_1": ["Alpha", "Gamma"]})
        bidder = game.payload["players"][game.payload["current_player_index"]]
        game = apply_500(self.world, game.object_id, bidder, "bid", ["6S"])
        for _ in range(3):
            player = game.payload["players"][game.payload["current_player_index"]]
            game = apply_500(self.world, game.object_id, player, "pass")
        self.assertEqual(game.payload["phase"], "discard")
        self.assertEqual(game.payload["declarer"], bidder)
        self.assertEqual(len(game.payload["hands"][bidder]), 13)
        hidden_card = next(
            card["card_id"]
            for player in PLAYERS
            if player != bidder
            for card in game.payload["hands"][player]
        )
        self.assertNotIn(hidden_card, game.payload["content"])

        discard_ids = [card["card_id"] for card in game.payload["hands"][bidder][:3]]
        game = apply_500(self.world, game.object_id, bidder, "discard", discard_ids)
        self.assertEqual(game.payload["phase"], "play")
        self.assertEqual(len(view_500(game.payload, bidder)["hand"]), 10)
        card_id = game.payload["hands"][bidder][0]["card_id"]
        first = apply_500(self.world, game.object_id, bidder, "play", [card_id])
        second = apply_500(self.world, game.object_id, bidder, "play", [card_id])
        self.assertEqual(first.object_id, second.object_id)

    def test_requires_exactly_four_players(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 4 and 4"):
            new_five_hundred(self.world, players=["Trent", "Alpha", "Beta"])

    def test_contract_plays_through_ten_legal_tricks_and_scores(self) -> None:
        game = new_five_hundred(self.world, "full-hand", PLAYERS, ["Trent"])
        bidder = game.payload["players"][game.payload["current_player_index"]]
        game = apply_500(self.world, game.object_id, bidder, "bid", ["6S"])
        for _ in range(3):
            player = game.payload["players"][game.payload["current_player_index"]]
            game = apply_500(self.world, game.object_id, player, "pass")
        discard_ids = [card["card_id"] for card in game.payload["hands"][bidder][:3]]
        game = apply_500(self.world, game.object_id, bidder, "discard", discard_ids)

        plays = 0
        while game.payload["phase"] == "play":
            player = game.payload["players"][game.payload["current_player_index"]]
            for card in game.payload["hands"][player]:
                try:
                    game = apply_500(self.world, game.object_id, player, "play", [card["card_id"]])
                    plays += 1
                    break
                except ValueError:
                    pass
            else:
                self.fail("500 engine offered no legal card")
        self.assertEqual(plays, 40)
        self.assertIn(game.payload["phase"], {"bidding", "complete"})
        self.assertNotEqual(game.payload["scores"], {"team_0": 0, "team_1": 0})
        inspect_five_hundred(self.world, game.object_id)


class DeterministicBlackjackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = WorldStore()

    def _bet_all(self, game):
        while game.payload["phase"] == "betting":
            player = game.payload["players"][game.payload["current_player_index"]]
            game = apply_blackjack(self.world, game.object_id, player, "bet", ["10"])
        return game

    def test_deterministic_dealer_hides_hole_card_then_settles(self) -> None:
        game = new_blackjack(self.world, "dealer", PLAYERS, ["Trent"])
        first_bet = apply_blackjack(self.world, game.object_id, "Trent", "bet", ["10"])
        repeated = apply_blackjack(self.world, game.object_id, "Trent", "bet", ["10"])
        self.assertEqual(first_bet.object_id, repeated.object_id)
        game = first_bet
        while game.payload["phase"] == "betting":
            player = game.payload["players"][game.payload["current_player_index"]]
            game = apply_blackjack(self.world, game.object_id, player, "bet", ["10"])

        if game.payload["phase"] == "player_turns":
            hole = game.payload["dealer"]["hand"][1]["card_id"]
            self.assertIn("HIDDEN", game.payload["content"])
            self.assertNotIn(hole, game.payload["content"])
            while game.payload["phase"] == "player_turns":
                player = game.payload["players"][game.payload["current_player_index"]]
                game = apply_blackjack(self.world, game.object_id, player, "stand")
        self.assertIn(game.payload["phase"], {"round_complete", "complete"})
        self.assertTrue(game.payload["dealer"]["revealed"])
        inspect_blackjack(self.world, game.object_id)

    def test_blackjack_private_view_and_bet_validation(self) -> None:
        game = new_blackjack(self.world, "view", ["Trent", "Alpha"], ["Trent"])
        with self.assertRaisesRegex(ValueError, "even"):
            apply_blackjack(self.world, game.object_id, "Trent", "bet", ["9"])
        game = apply_blackjack(self.world, game.object_id, "Trent", "bet", ["10"])
        game = apply_blackjack(self.world, game.object_id, "Alpha", "bet", ["10"])
        view = blackjack_view(game.payload, "Trent")
        self.assertNotIn("shoe", view)
        if not game.payload["dealer"]["revealed"]:
            self.assertEqual(view["dealer_hand"][1], {"hidden": True})

    def test_single_human_can_play_more_than_one_round_against_dealer(self) -> None:
        game = new_blackjack(self.world, "solo", ["Trent"], ["Trent"])
        game = apply_blackjack(self.world, game.object_id, "Trent", "bet", ["2"])
        if game.payload["phase"] == "player_turns":
            game = apply_blackjack(self.world, game.object_id, "Trent", "stand")
        self.assertEqual(game.payload["phase"], "round_complete")
        self.assertIsNone(game.payload["winner"])
        game = apply_blackjack(self.world, game.object_id, "Trent", "new_round")
        self.assertEqual(game.payload["round_number"], 2)
        self.assertEqual(game.payload["phase"], "betting")


class TabletopAPITests(unittest.TestCase):
    def test_health_operations_catalogs_and_player_controller_metadata(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["protocol"], "nexus/0.12")
        games = {item["game_id"]: item for item in health["games"]}
        self.assertEqual(set(games) & {"uno", "monopoly", "500", "blackjack", "dork"}, {"uno", "monopoly", "500", "blackjack", "dork"})
        self.assertTrue(games["blackjack"]["deterministic_dealer"])
        self.assertTrue(games["dork"]["human_only"])

        operations = api.handle({"operation": "system.operations"})["operations"]
        for game_id in ("uno", "monopoly", "500", "blackjack"):
            self.assertIn(f"game.{game_id}.act", operations)
            catalog = api.handle({"operation": f"game.{game_id}.catalog"})
            self.assertEqual(catalog["status"], "ok")
            self.assertTrue(catalog["human_and_ai"])

        created = api.handle(
            {
                "operation": "game.uno.new",
                "players": PLAYERS,
                "human_players": ["Trent"],
                "seed": "api",
            }
        )
        self.assertEqual(created["status"], "ok")
        self.assertEqual(created["game"]["controllers"]["Trent"], "human")
        self.assertEqual(created["game"]["controllers"]["Alpha"], "ai")
        inspected = api.handle(
            {
                "operation": "game.uno.inspect",
                "game_ref": created["game_ref"],
                "player_id": "Alpha",
            }
        )
        self.assertEqual(inspected["view"]["player_id"], "Alpha")

        monopoly = api.handle(
            {
                "operation": "game.monopoly.new",
                "players": PLAYERS,
                "human_players": ["Trent"],
                "seed": "api-monopoly",
            }
        )
        rolled = api.handle(
            {
                "operation": "game.monopoly.act",
                "game_ref": monopoly["game_ref"],
                "player_id": "Trent",
                "action": "roll",
                "args": [],
            }
        )
        self.assertEqual(rolled["status"], "ok")

        five_hundred = api.handle(
            {
                "operation": "game.500.new",
                "players": PLAYERS,
                "human_players": ["Trent"],
                "seed": "api-500",
            }
        )
        bidder = five_hundred["game"]["players"][five_hundred["game"]["current_player_index"]]
        bid = api.handle(
            {
                "operation": "game.500.act",
                "game_ref": five_hundred["game_ref"],
                "player_id": bidder,
                "action": "bid",
                "args": ["6S"],
            }
        )
        self.assertEqual(bid["status"], "ok")

        blackjack = api.handle(
            {
                "operation": "game.blackjack.new",
                "players": PLAYERS,
                "human_players": ["Trent"],
                "seed": "api-blackjack",
            }
        )
        bet = api.handle(
            {
                "operation": "game.blackjack.act",
                "game_ref": blackjack["game_ref"],
                "player_id": "Trent",
                "action": "bet",
                "args": ["10"],
            }
        )
        self.assertEqual(bet["status"], "ok")

        dork = api.handle(
            {"operation": "game.dork.new", "human_player_id": "Trent", "seed": "api-dork"}
        )
        looked = api.handle(
            {
                "operation": "game.dork.act",
                "game_ref": dork["game_ref"],
                "player_id": "Trent",
                "action": "look",
                "args": [],
            }
        )
        self.assertEqual(looked["status"], "ok")

    def test_table_api_scrubs_seed_and_rejects_credential_shaped_player_id(self) -> None:
        api = NexusAPI()
        secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD"
        created = api.handle(
            {
                "operation": "game.uno.new",
                "players": ["Trent", "Alpha"],
                "human_players": ["Trent"],
                "seed": f"table-{secret}",
            }
        )
        self.assertEqual(created["status"], "ok")
        self.assertTrue(created["secret_scrub"]["changed"])
        self.assertNotIn(secret, created["game"]["seed"])
        rejected = api.handle(
            {
                "operation": "game.uno.new",
                "players": ["Trent", secret],
                "human_players": ["Trent"],
            }
        )
        self.assertEqual(rejected["status"], "error")


class CanonicalTableBoundaryTests(unittest.TestCase):
    def test_claim_boundary_tampering_is_rejected_for_every_table(self) -> None:
        world = WorldStore()
        games = (
            (new_uno(world, "claims", PLAYERS, ["Trent"]), inspect_uno),
            (new_monopoly(world, "claims", PLAYERS, ["Trent"]), inspect_monopoly),
            (new_five_hundred(world, "claims", PLAYERS, ["Trent"]), inspect_five_hundred),
            (new_blackjack(world, "claims", PLAYERS, ["Trent"]), inspect_blackjack),
        )
        for game, inspect in games:
            with self.subTest(game=game.object_type):
                forged = deepcopy(game.payload)
                forged["claim_boundary"]["model_narration_mutates_state"] = True
                obj = world.create_object(game.object_type, forged, {"actor": "forger"})
                with self.assertRaisesRegex(ValueError, "claim boundary"):
                    inspect(world, obj.object_id)


if __name__ == "__main__":
    unittest.main()
