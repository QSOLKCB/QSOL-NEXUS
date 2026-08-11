from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.wall import (
    WALL_POST_OBJECT_TYPE,
    WALL_RESERVED_OBJECT_TYPES,
    WALL_SCHEMA_VERSION,
    WallError,
    WallService,
)
from nexus_runtime.world import WorldStore


class WallTests(unittest.TestCase):
    @staticmethod
    def _member() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    @staticmethod
    def _api(base: Path, world_name: str = "world") -> NexusAPI:
        return NexusAPI(
            base / world_name,
            auth_root=base / f"{world_name}-auth",
            trap_root=base / f"{world_name}-trap",
            stenographer_root=base / f"{world_name}-stenographer",
            guardian_root=base / f"{world_name}-guardian",
        )

    def test_wall_surface_is_public_and_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            operations = set(api.handle({"operation": "system.operations"})["operations"])
            self.assertTrue(
                {
                    "wall.policy",
                    "wall.list",
                    "wall.post",
                    "wall.ai_post",
                    "wall.tombstone",
                    "wall.inspect",
                }.issubset(operations)
            )
            policy = api.handle({"operation": "wall.policy"})["policy"]
            self.assertEqual(policy["principle"], "wall_post_is_social_memory_not_evidence")
            self.assertEqual(policy["authority_invariants"]["vote_weight_created"], 0)
            self.assertEqual(policy["authority_invariants"]["council_seats_created"], 0)
            self.assertFalse(policy["authority_invariants"]["evidence_promoted"])
            self.assertFalse(policy["authority_invariants"]["popularity_promotes_truth"])
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["bbs_wall"]["status"], "ok")

    def test_human_posts_are_immutable_chronological_social_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            first = api.handle({"operation": "wall.post", "author_id": "Trent", "text": "First post."})
            second = api.handle({"operation": "wall.post", "author_id": "Trent", "text": "Second post."})
            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertEqual(first["post"]["payload"]["sequence"], 1)
            self.assertIsNone(first["post"]["payload"]["previous_event_ref"])
            self.assertEqual(second["post"]["payload"]["sequence"], 2)
            self.assertEqual(
                second["post"]["payload"]["previous_event_ref"], first["post"]["object_id"]
            )
            newest = api.handle({"operation": "wall.list", "limit": 20, "order": "newest"})
            self.assertEqual([row["text"] for row in newest["posts"]], ["Second post.", "First post."])
            self.assertTrue(all(row["evidence_effect"] == "none" for row in newest["posts"]))
            self.assertTrue(all(row["authority_effect"] == "none" for row in newest["posts"]))

    def test_wall_secret_canary_is_scrubbed_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            canary = "NEXUS_WALL_PRIVATE_CANARY_93A1"
            key_kind = "PRIVATE" + " KEY"
            text = f"hello -----BEGIN {key_kind}----- {canary} -----END {key_kind}-----"
            response = api.handle({"operation": "wall.post", "author_id": "Trent", "text": text})
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["secret_scrub"]["changed"])
            self.assertNotIn(canary, json.dumps(response, sort_keys=True))
            needle = canary.encode("utf-8")
            for path in base.rglob("*"):
                if path.is_file():
                    self.assertNotIn(needle, path.read_bytes(), str(path))

    def test_generic_world_create_cannot_forge_wall_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in sorted(WALL_RESERVED_OBJECT_TYPES):
                response = api.handle(
                    {"operation": "world.create", "object_type": object_type, "payload": {"forged": True}}
                )
                self.assertEqual(response["status"], "error", object_type)

    def test_tombstone_is_append_only_and_normal_display_hides_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            posted = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "Please hide this in normal display."}
            )
            post_ref = posted["post"]["object_id"]
            tombstone = api.handle(
                {
                    "operation": "wall.tombstone",
                    "moderator_id": "Trent",
                    "post_ref": post_ref,
                    "reason": "operator moderation",
                }
            )
            self.assertEqual(tombstone["status"], "ok")
            self.assertFalse(tombstone["source_post_deleted"])
            listing = api.handle({"operation": "wall.list"})
            self.assertEqual(listing["posts"][0]["text"], "[tombstoned]")
            self.assertTrue(listing["posts"][0]["tombstoned"])
            self.assertEqual(listing["posts"][0]["tombstone_reason"], "operator moderation")
            original = api.handle({"operation": "world.inspect", "object_ref": post_ref})
            self.assertEqual(original["object"]["payload"]["text"], "Please hide this in normal display.")
            again = api.handle(
                {
                    "operation": "wall.tombstone",
                    "moderator_id": "Trent",
                    "post_ref": post_ref,
                    "reason": "again",
                }
            )
            self.assertEqual(again["status"], "error")
            self.assertEqual(again["error"]["code"], "wall_already_tombstoned")

    def test_wall_history_fails_closed_on_forked_reserved_event(self) -> None:
        world = WorldStore()
        wall = WallService(world)
        legitimate = wall.post_human(author_id="Trent", text="canonical")
        forged_payload = deepcopy(legitimate.payload)
        forged_payload["text"] = "fork"
        world.create_object(
            WALL_POST_OBJECT_TYPE,
            forged_payload,
            {"actor": "nexus", "subsystem": "bbs_wall"},
        )
        with self.assertRaisesRegex(WallError, "same sequence"):
            wall.list_posts()

    def test_ai_wall_post_binds_runtime_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {"operation": "wall.ai_post", "member": self._member(), "prompt": "Leave a short note about old BBS systems."}
            )
            self.assertEqual(response["status"], "ok")
            author = response["post"]["payload"]["author"]
            self.assertEqual(author, {"kind": "model", "author_id": "Alpha", "model_id": "mock-alpha"})
            self.assertEqual(response["authority_effect"], "none")
            self.assertEqual(response["evidence_effect"], "none")

    def test_wall_ark_roundtrip_reconstructs_from_immutable_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            posted = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "Leave this for the future."}
            )
            self.assertEqual(posted["status"], "ok")
            post_ref = posted["post"]["object_id"]
            ark = base / "NEXUS-WALL-ARK"
            created = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created["verified"])
            restored_root = base / "restored-wall-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")
            reopened = NexusAPI(
                restored_root,
                auth_root=base / "restored-auth",
                trap_root=base / "restored-trap",
                stenographer_root=base / "restored-stenographer",
                guardian_root=base / "restored-guardian",
            )
            listing = reopened.handle({"operation": "wall.list", "order": "oldest"})
            self.assertEqual(listing["posts"][0]["post_ref"], post_ref)
            self.assertEqual(listing["posts"][0]["text"], "Leave this for the future.")
            self.assertEqual(listing["schema_version"], WALL_SCHEMA_VERSION)

    def test_wall_bounds_fail_without_persisting_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            oversized = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "x" * 513}
            )
            self.assertEqual(oversized["status"], "error")
            listing = api.handle({"operation": "wall.list"})
            self.assertEqual(listing["posts"], [])


if __name__ == "__main__":
    unittest.main()
