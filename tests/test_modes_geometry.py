from __future__ import annotations

import unittest

from nexus_runtime.api import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.geometry import DEFAULT_WORLD_GEOMETRY
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.modes import get_mode, list_modes
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


def actor(member_id: str, profile: str = "balanced") -> DeterministicMockActor:
    return DeterministicMockActor(
        CouncilMember(member_id=member_id, model_id=f"mock-{member_id.lower()}"),
        profile=profile,
    )


class WorldModeTests(unittest.TestCase):
    def test_initial_mode_registry_is_explicit(self) -> None:
        self.assertEqual(
            {mode.mode_id for mode in list_modes()},
            {"analytical", "historical", "cultural", "meme_casual"},
        )
        self.assertEqual(get_mode("historical").region_id, "archive")
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
        session = world.inspect(result["session_ref"])
        self.assertEqual(session.payload["world_presence_ref"], presence.object_id)
        white = session.payload["phase_submissions"]["WHITE"][0]["content"]
        self.assertIn("cultural@agora", white)


class GeometryTests(unittest.TestCase):
    def test_geometry_is_connected_and_mode_complete(self) -> None:
        snapshot = DEFAULT_WORLD_GEOMETRY.snapshot()
        self.assertEqual(snapshot["geometry_id"], "named-regions-v1")
        self.assertEqual(snapshot["semantics"], "operational_topology_not_physical_claim")
        self.assertEqual(DEFAULT_WORLD_GEOMETRY.distance("archive", "commons"), 2)
        self.assertEqual(DEFAULT_WORLD_GEOMETRY.distance("agora", "agora"), 0)
        for mode in list_modes():
            self.assertEqual(DEFAULT_WORLD_GEOMETRY.region_for_mode(mode.mode_id).region_id, mode.region_id)


class ModeGeometryAPITests(unittest.TestCase):
    def test_api_exposes_modes_geometry_and_distance(self) -> None:
        api = NexusAPI()
        modes = api.handle({"operation": "world.modes"})
        self.assertEqual(modes["status"], "ok")
        self.assertEqual(
            {item["mode_id"] for item in modes["modes"]},
            {"analytical", "historical", "cultural", "meme_casual"},
        )
        geometry = api.handle({"operation": "world.geometry"})
        self.assertEqual(geometry["geometry_id"], "named-regions-v1")
        distance = api.handle(
            {
                "operation": "world.geometry.distance",
                "source_region_id": "archive",
                "target_region_id": "commons",
            }
        )
        self.assertEqual(distance["hop_distance"], 2)

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
