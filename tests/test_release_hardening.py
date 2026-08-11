from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.culture import CULTURE_RESERVED_OBJECT_TYPES


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHardeningTests(unittest.TestCase):
    @staticmethod
    def _member() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    @staticmethod
    def _api(base: Path, world_name: str = "world"):
        return NexusAPI(
            base / world_name,
            auth_root=base / f"{world_name}-auth",
            trap_root=base / f"{world_name}-trap",
            stenographer_root=base / f"{world_name}-stenographer",
            guardian_root=base / f"{world_name}-guardian",
        )

    def test_release_surface_keeps_progression_culture_and_continuity_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            operations = set(api.handle({"operation": "system.operations"})["operations"])
            required = {
                "progression.policy",
                "progression.portfolio",
                "culture.policy",
                "culture.open_mic.perform",
                "long.shift.ai_act",
                "psyche.chess.ai_move",
                "world.continuity.policy",
                "world.continuity.scrub",
                "world.ark.create",
                "world.ark.verify",
                "world.recovery.restore",
            }
            self.assertTrue(required.issubset(operations))

            progression = api.handle({"operation": "progression.policy"})["policy"]["authority_invariants"]
            self.assertEqual(progression["vote_weight_created"], 0)
            self.assertEqual(progression["council_seats_created"], 0)
            self.assertFalse(progression["citizenship_created"])
            self.assertFalse(progression["evidence_promoted"])

            culture = api.handle({"operation": "culture.policy"})["policy"]["authority_invariants"]
            self.assertEqual(culture["vote_weight_created"], 0)
            self.assertFalse(culture["citizenship_created_or_revoked_by_performance"])
            self.assertFalse(culture["evidence_promoted"])
            self.assertFalse(culture["game_master_is_governor"])

            continuity = api.handle({"operation": "world.continuity.policy"})["policy"]
            self.assertEqual(continuity["authority_effect"], "none")
            self.assertIn("quorum", continuity["recognized_history_rule"])
            self.assertIn("new target", continuity["ark_rule"])

    def test_malformed_new_release_surfaces_fail_structured_without_world_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            before = api.world.status()["recognized_object_count"]
            malformed = [
                {
                    "operation": "culture.open_mic.perform",
                    "member": {},
                    "kind": [],
                    "prompt": {},
                    "mode": [],
                },
                {
                    "operation": "long.shift.new",
                    "seed": 7,
                    "players": "Alpha",
                    "human_players": [],
                },
                {
                    "operation": "psyche.chess.new",
                    "white_player": [],
                    "black_player": "Beta",
                    "human_players": [],
                },
                {"operation": "world.continuity.scrub", "repair": "yes"},
                {
                    "operation": "progression.play.record",
                    "member": self._member(),
                    "game_kind": "psyche_chess",
                    "game_ref": "object:" + "0" * 64,
                },
            ]
            for request in malformed:
                response = api.handle(request)
                self.assertEqual(response["status"], "error")
                self.assertIsInstance(response["error"]["code"], str)
                self.assertTrue(response["error"]["code"])
            after = api.world.status()["recognized_object_count"]
            self.assertEqual(after, before)

    def test_culture_secret_canary_never_enters_durable_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            canary = "NEXUS_PR49_PRIVATE_CANARY_7B42"
            prompt = (
                "Rant about printers.\n"
                "-----BEGIN PRIVATE KEY-----\n"
                f"{canary}\n"
                "-----END PRIVATE KEY-----"
            )
            response = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._member(),
                    "kind": "rant",
                    "prompt": prompt,
                    "mode": "anarchy",
                }
            )
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["secret_scrub"]["prompt_changed"])
            self.assertNotIn(canary, json.dumps(response, sort_keys=True))
            needle = canary.encode("utf-8")
            for path in base.rglob("*"):
                if path.is_file():
                    self.assertNotIn(needle, path.read_bytes(), str(path))

    def test_generic_world_create_cannot_forge_pr48_runtime_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in sorted(CULTURE_RESERVED_OBJECT_TYPES):
                response = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {"forged": True},
                    }
                )
                self.assertEqual(response["status"], "error", object_type)

    def test_representative_world_ark_round_trip_rebuilds_progression_from_immutable_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            performed = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._member(),
                    "kind": "rant",
                    "prompt": "Rant about deterministic printers forming a committee.",
                    "mode": "anarchy",
                }
            )
            self.assertEqual(performed["status"], "ok")
            created = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "release_rehearsal_note",
                    "payload": {"message": "survive the Ark"},
                }
            )
            self.assertEqual(created["status"], "ok")
            note_ref = created["object"]["object_id"]
            original = api.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(original["counts"]["perform_rant"], 1)
            self.assertEqual(original["vote_weight_created"], 0)

            ark = base / "NEXUS-ARK-PR49"
            created_ark = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created_ark["verified"])
            self.assertEqual(api.world.verify_ark(ark)["status"], "verified")

            restored_root = base / "restored-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")
            reopened = NexusAPI(
                restored_root,
                auth_root=base / "restored-auth",
                trap_root=base / "restored-trap",
                stenographer_root=base / "restored-stenographer",
                guardian_root=base / "restored-guardian",
            )
            inspected = reopened.handle({"operation": "world.inspect", "object_ref": note_ref})
            self.assertEqual(inspected["status"], "ok")
            rebuilt = reopened.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(rebuilt["counts"]["perform_rant"], 1)
            self.assertEqual(rebuilt["state_ref"], original["state_ref"])
            self.assertEqual(rebuilt["vote_weight_created"], 0)
            self.assertEqual(rebuilt["citizenship_effect"], "none")
            self.assertEqual(rebuilt["evidence_effect"], "none")

    def test_hardening_matrix_is_pre_wall_and_cannot_declare_stable_release(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["schema"], "nexus-release-hardening-matrix/1")
        self.assertEqual(matrix["milestone"], "PR #49")
        self.assertEqual(matrix["profile"], "pre_wall")
        self.assertFalse(matrix["stable_release"])
        self.assertEqual(matrix["authority_effect"], "none")
        self.assertIn("PR #51", matrix["post_wall_rule"])


if __name__ == "__main__":
    unittest.main()
