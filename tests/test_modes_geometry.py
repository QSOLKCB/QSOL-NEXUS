from __future__ import annotations

import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry, WorldRegion
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.modes import get_mode, list_modes
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


def actor(member_id: str, profile: str = "balanced") -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"),
        profile=profile,
    )


def connected_regions(*, observatory_x: int = 0) -> tuple[WorldRegion, ...]:
    return (
        WorldRegion(
            "observatory",
            "Observatory",
            observatory_x,
            0,
            ("archive", "agora", "commons", "assembly", "dungeon"),
            "Analytical region.",
        ),
        WorldRegion("archive", "Archive", -2, 1, ("observatory", "agora"), "Historical region."),
        WorldRegion("agora", "Agora", 0, 2, ("archive", "observatory", "commons"), "Cultural region."),
        WorldRegion("commons", "Commons", 2, 1, ("observatory", "agora", "assembly", "dungeon"), "Playful region."),
        WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory", "commons", "dungeon"), "Game region."),
        WorldRegion("dungeon", "Dungeon", 2, -2, ("observatory", "commons", "assembly"), "MUD region."),
    )


class WorldModeTests(unittest.TestCase):
    def test_initial_mode_registry_is_explicit(self) -> None:
        self.assertEqual(
            {mode.mode_id for mode in list_modes()},
            {
                "analytical",
                "historical",
                "pure_history",
                "cultural",
                "meme_casual",
                "clinical_differential",
                "house_fun",
                "cbt_learning",
                "roman_orator",
                "house_of_wisdom",
                "ultimate_questions",
                "game_un",
                "game_mud",
                "game_uno",
                "game_monopoly",
                "game_500",
                "game_blackjack",
                "game_dork",
            },
        )
        self.assertEqual(get_mode("historical").region_id, "archive")
        self.assertEqual(get_mode("pure_history").region_id, "archive")
        self.assertEqual(get_mode("game_un").region_id, "assembly")
        self.assertEqual(get_mode("game_mud").region_id, "dungeon")
        self.assertEqual(get_mode("clinical_differential").region_id, "observatory")
        self.assertEqual(get_mode("house_fun").region_id, "commons")
        self.assertEqual(get_mode("cbt_learning").region_id, "observatory")
        self.assertEqual(get_mode("roman_orator").region_id, "agora")
        self.assertEqual(get_mode("house_of_wisdom").region_id, "archive")
        self.assertEqual(get_mode("ultimate_questions").region_id, "observatory")
        self.assertEqual(get_mode("game_uno").region_id, "commons")
        self.assertEqual(get_mode("game_monopoly").region_id, "commons")
        self.assertEqual(get_mode("game_500").region_id, "commons")
        self.assertEqual(get_mode("game_blackjack").region_id, "commons")
        self.assertEqual(get_mode("game_dork").region_id, "dungeon")
        with self.assertRaises(ValueError):
            get_mode("corporate_supremacy")

    def test_mode_changes_framing_not_vote_mechanics(self) -> None:
        world = WorldStore()
        council = CouncilCoordinator(world)
        actors = [actor("A"), actor("B"), actor("C", "supportive")]
        analytical = council.run("same question", actors, mode_id="analytical")
        playful = council.run("same question", actors, mode_id="meme_casual")
        self.assertNotEqual(analytical["session_id"], playful["session_id"])
        self.assertEqual(analytical["result"]["tally"], playful["result"]["tally"])
        self.assertEqual(analytical["result"]["consensus_label"], playful["result"]["consensus_label"])

    def test_council_creates_world_presence_in_mode_region(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            "Compare two cultural interpretations.",
            [actor("A"), actor("B"), actor("C")],
            mode_id="cultural",
        )
        self.assertEqual(result["mode_id"], "cultural")
        self.assertEqual(result["geometry_region_id"], "agora")
        presence = world.inspect(result["world_presence_ref"])
        self.assertEqual(presence.object_type, "world_presence")
        self.assertEqual(presence.payload["mode_id"], "cultural")
        self.assertEqual(presence.payload["region_id"], "agora")
        self.assertEqual(presence.payload["coordinates"], [0, 2])
        self.assertEqual(presence.payload["geometry_id"], "named-regions-v3")
        self.assertEqual(presence.payload["geometry_topology_ref"], DEFAULT_WORLD_GEOMETRY.snapshot()["topology_ref"])
        session = world.inspect(result["session_ref"])
        self.assertEqual(session.payload["world_presence_ref"], presence.object_id)
        white = session.payload["phase_submissions"]["WHITE"][0]["content"]
        self.assertIn("cultural@agora", white)


class GeometryTests(unittest.TestCase):
    def test_geometry_is_connected_and_mode_complete(self) -> None:
        snapshot = DEFAULT_WORLD_GEOMETRY.snapshot()
        self.assertEqual(snapshot["geometry_id"], "named-regions-v3")
        self.assertTrue(str(snapshot["topology_ref"]).startswith("geometry:"))
        self.assertEqual(snapshot["semantics"], "operational_topology_not_physical_claim")
        region_ids = [region["region_id"] for region in snapshot["regions"]]  # type: ignore[index]
        self.assertIn("assembly", region_ids)
        self.assertIn("dungeon", region_ids)
        for source in region_ids:
            for target in region_ids:
                with self.subTest(source=source, target=target):
                    distance = DEFAULT_WORLD_GEOMETRY.distance(source, target)
                    self.assertGreaterEqual(distance, 0)
                    self.assertEqual(distance, DEFAULT_WORLD_GEOMETRY.distance(target, source))
                    if source == target:
                        self.assertEqual(distance, 0)
        for mode in list_modes():
            self.assertEqual(DEFAULT_WORLD_GEOMETRY.region_for_mode(mode.mode_id).region_id, mode.region_id)

    def test_geometry_rejects_non_integer_coordinates(self) -> None:
        for bad_x in ("0", 0.0, False):
            with self.subTest(bad_x=bad_x):
                regions = list(connected_regions())
                original = regions[0]
                regions[0] = WorldRegion(
                    original.region_id,
                    original.label,
                    bad_x,  # type: ignore[arg-type]
                    original.y,
                    original.neighbors,
                    original.description,
                )
                with self.assertRaisesRegex(ValueError, "exact integers"):
                    WorldGeometry(tuple(regions))

    def test_geometry_rejects_disconnected_mode_complete_map(self) -> None:
        disconnected = (
            WorldRegion("observatory", "Observatory", 0, 0, ("archive", "assembly", "dungeon"), "A"),
            WorldRegion("archive", "Archive", -2, 1, ("observatory",), "B"),
            WorldRegion("assembly", "Assembly Hall", 0, -2, ("observatory", "dungeon"), "Game"),
            WorldRegion("dungeon", "Dungeon", 2, -2, ("observatory", "assembly"), "MUD"),
            WorldRegion("agora", "Agora", 0, 2, ("commons",), "C"),
            WorldRegion("commons", "Commons", 2, 1, ("agora",), "D"),
        )
        with self.assertRaisesRegex(ValueError, "fully connected"):
            WorldGeometry(disconnected)

    def test_topology_ref_distinguishes_maps_even_with_same_alias_and_selected_region(self) -> None:
        first_geometry = WorldGeometry(connected_regions(observatory_x=0), geometry_id="custom-map")
        second_geometry = WorldGeometry(connected_regions(observatory_x=1), geometry_id="custom-map")
        self.assertEqual(first_geometry.snapshot()["geometry_id"], second_geometry.snapshot()["geometry_id"])
        self.assertNotEqual(first_geometry.snapshot()["topology_ref"], second_geometry.snapshot()["topology_ref"])

        world = WorldStore()
        actors = [actor("A"), actor("B"), actor("C")]
        first = CouncilCoordinator(world, geometry=first_geometry).run("same question", actors, mode_id="cultural")
        second = CouncilCoordinator(world, geometry=second_geometry).run("same question", actors, mode_id="cultural")
        self.assertEqual(first["geometry_region_id"], second["geometry_region_id"])
        self.assertNotEqual(first["world_presence_ref"], second["world_presence_ref"])
        self.assertNotEqual(first["session_id"], second["session_id"])


class ModeGeometryAPITests(unittest.TestCase):
    def test_api_exposes_modes_geometry_and_distance(self) -> None:
        api = NexusAPI()
        modes = api.handle({"operation": "world.modes"})
        self.assertEqual(modes["status"], "ok")
        self.assertEqual(
            {item["mode_id"] for item in modes["modes"]},
            {
                "analytical",
                "historical",
                "pure_history",
                "cultural",
                "meme_casual",
                "clinical_differential",
                "house_fun",
                "cbt_learning",
                "roman_orator",
                "house_of_wisdom",
                "ultimate_questions",
                "game_un",
                "game_mud",
                "game_uno",
                "game_monopoly",
                "game_500",
                "game_blackjack",
                "game_dork",
            },
        )
        geometry = api.handle({"operation": "world.geometry"})
        self.assertEqual(geometry["geometry_id"], "named-regions-v3")
        self.assertTrue(geometry["topology_ref"].startswith("geometry:"))
        distance = api.handle(
            {
                "operation": "world.geometry.distance",
                "source_region_id": "archive",
                "target_region_id": "commons",
            }
        )
        self.assertEqual(distance["hop_distance"], 2)
        assembly = api.handle(
            {
                "operation": "world.geometry.distance",
                "source_region_id": "observatory",
                "target_region_id": "assembly",
            }
        )
        self.assertEqual(assembly["hop_distance"], 1)
        dungeon = api.handle({"operation": "world.geometry.distance", "source_region_id": "observatory", "target_region_id": "dungeon"})
        self.assertEqual(dungeon["hop_distance"], 1)

    def test_api_council_accepts_mode_and_rejects_unknown_mode(self) -> None:
        api = NexusAPI()
        members = [
            {"member_id": "A", "model_id": "a"},
            {"member_id": "B", "model_id": "b"},
            {"member_id": "C", "model_id": "c"},
        ]
        run = api.handle(
            {
                "operation": "council.run",
                "question": "Tell me the cultural context.",
                "mode": "cultural",
                "members": members,
            }
        )
        self.assertEqual(run["status"], "ok")
        self.assertEqual(run["mode_id"], "cultural")
        self.assertEqual(run["geometry_region_id"], "agora")

        game = api.handle(
            {
                "operation": "council.run",
                "question": "Debate the fictional crisis.",
                "mode": "game_un",
                "members": members,
            }
        )
        self.assertEqual(game["status"], "ok")
        self.assertEqual(game["geometry_region_id"], "assembly")

        bad = api.handle(
            {
                "operation": "council.run",
                "question": "q",
                "mode": "vogons_only",
                "members": members,
            }
        )
        self.assertEqual(bad["status"], "error")
        self.assertIn("unknown world mode", bad["error"]["message"])


if __name__ == "__main__":
    unittest.main()
