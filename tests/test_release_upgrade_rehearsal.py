from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.world import WorldStore


class PreBetaUpgradeArkRehearsalTests(unittest.TestCase):
    @staticmethod
    def _api(base: Path, world_name: str) -> NexusAPI:
        return NexusAPI(
            base / world_name,
            auth_root=base / f"{world_name}-auth",
            trap_root=base / f"{world_name}-trap",
            stenographer_root=base / f"{world_name}-stenographer",
            guardian_root=base / f"{world_name}-guardian",
        )

    @staticmethod
    def _alpha() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    def test_representative_pre_beta_world_upgrades_and_ark_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy_root = base / "legacy-world"

            # Representative pre-beta state: plain WorldStore cognitive/evidence
            # objects with no Continuity metadata yet. These object identities are
            # the compatibility boundary the upgrade must preserve.
            legacy = WorldStore(legacy_root)
            question = legacy.create_object(
                "question",
                {"text": "Does the old world survive the 2.0 upgrade?"},
                {"actor": "legacy_operator"},
            )
            evidence = legacy.create_object(
                "document_evidence",
                {"filename": "legacy.txt", "content": "pre-beta evidence payload"},
                {"actor": "legacy_operator"},
            )
            session = legacy.create_object(
                "council_session",
                {
                    "question_ref": question.object_id,
                    "evidence_refs": [evidence.object_id],
                    "legacy_marker": "pre_beta",
                },
                {"actor": "legacy_council"},
            )
            legacy_objects = {
                item.object_id: item.as_dict()
                for item in (question, evidence, session)
            }

            # Opening the same directory through the current API must baseline
            # the legacy world without changing any content-addressed object ID.
            api = self._api(base, "legacy-world")
            continuity = api.world.status()
            self.assertEqual(continuity["generation"], 0)
            self.assertEqual(continuity["recognized_object_count"], len(legacy_objects))
            for ref, expected in legacy_objects.items():
                self.assertEqual(api.world.inspect(ref).as_dict(), expected)

            # Exercise current post-upgrade state from multiple non-authoritative
            # surfaces before taking the cold Ark snapshot.
            progression = api.handle(
                {
                    "operation": "progression.act",
                    "member": self._alpha(),
                    "activity_id": "research",
                    "prompt": "Record one post-upgrade research contribution.",
                    "source_refs": [evidence.object_id],
                }
            )
            self.assertEqual(progression["status"], "ok")

            performance = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._alpha(),
                    "kind": "rant",
                    "prompt": "Complain briefly about migration paperwork.",
                    "mode": "anarchy",
                }
            )
            self.assertEqual(performance["status"], "ok")
            performance_ref = performance["performance"]["object_id"]

            wall = api.handle(
                {
                    "operation": "wall.post",
                    "author_id": "ReleaseProbe",
                    "text": "The upgraded world is still here.",
                }
            )
            self.assertEqual(wall["status"], "ok")
            wall_ref = wall["post"]["object_id"]

            portfolio_before = api.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(portfolio_before["status"], "ok")
            self.assertEqual(portfolio_before["counts"]["research"], 1)
            self.assertEqual(portfolio_before["counts"]["perform_rant"], 1)

            ark = base / "NEXUS-2.0-PRE-BETA-UPGRADE-ARK"
            created = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created["verified"])
            verified = api.world.verify_ark(ark)
            self.assertEqual(verified["status"], "verified")

            restored_root = base / "restored-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")

            # Mutable progression caches are explicitly not allowed to carry the
            # result. Reopen against immutable restored history only.
            heads = restored_root / "progression" / "heads.json"
            if heads.exists():
                heads.unlink()

            reopened = self._api(base, "restored-world")
            for ref, expected in legacy_objects.items():
                self.assertEqual(reopened.world.inspect(ref).as_dict(), expected)
            self.assertEqual(reopened.world.inspect(performance_ref).object_id, performance_ref)
            self.assertEqual(reopened.world.inspect(wall_ref).object_id, wall_ref)

            portfolio_after = reopened.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(portfolio_after["status"], "ok")
            for field in ("state_ref", "total_activities", "counts", "milestones"):
                self.assertEqual(portfolio_after[field], portfolio_before[field])

            listed = reopened.handle({"operation": "wall.list", "limit": 20})
            self.assertEqual(listed["status"], "ok")
            self.assertEqual([post["post_ref"] for post in listed["posts"]], [wall_ref])
            self.assertEqual(listed["posts"][0]["text"], "The upgraded world is still here.")


if __name__ == "__main__":
    unittest.main()
