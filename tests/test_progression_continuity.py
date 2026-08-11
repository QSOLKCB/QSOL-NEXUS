from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nexus_runtime.progression import ProgressionError, ProgressionService
from nexus_runtime.world import WorldStore
from nexus_runtime.world_continuity import ContinuityWorldStore


class ProgressionContinuityTests(unittest.TestCase):
    def test_rebuild_uses_recognized_continuity_history_when_primary_copy_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ContinuityWorldStore(
                root / "primary",
                replica_roots=[root / "mirror-a", root / "mirror-b"],
                write_quorum=2,
            )
            service = ProgressionService(store)
            recorded = service.record_activity(
                actor_id="Alpha",
                model_id="mock-alpha",
                activity_id="chronicle",
                prompt="Chronicle one event.",
                output="A bounded chronicle.",
                source_refs=[],
            )
            state_ref = recorded["portfolio_state"]["object_id"]

            primary_state = (
                root
                / "primary"
                / "objects"
                / f"{state_ref.removeprefix('object:')}.json"
            )
            primary_state.unlink()
            (root / "primary" / "progression" / "heads.json").unlink()

            reopened = ContinuityWorldStore(
                root / "primary",
                replica_roots=[root / "mirror-a", root / "mirror-b"],
                write_quorum=2,
            )
            portfolio = ProgressionService(reopened).portfolio(
                actor_id="Alpha",
                model_id="mock-alpha",
            )
            self.assertEqual(portfolio["state_ref"], state_ref)
            self.assertEqual(portfolio["counts"]["chronicle"], 1)

    def test_direct_service_cannot_expand_commission_sources_past_policy_limit(self) -> None:
        world = WorldStore()
        service = ProgressionService(world)
        refs = [
            world.create_object("note", {"index": index}, {"actor": "test"}).object_id
            for index in range(16)
        ]
        commission = service.create_commission(
            title="Too many together",
            activity_id="research",
            brief="Use the first source set.",
            source_refs=refs[:8],
            assignee_id="Alpha",
        )
        with self.assertRaisesRegex(ProgressionError, "combined activity and commission"):
            service.record_activity(
                actor_id="Alpha",
                model_id="mock-alpha",
                activity_id="research",
                prompt="Use another source set too.",
                output="This must not be committed.",
                source_refs=refs[8:],
                commission_ref=commission.object_id,
            )

    def test_malformed_semantic_state_fails_as_progression_corruption(self) -> None:
        world = WorldStore()
        forged = world.create_object(
            "ai_progression_state",
            {
                "schema_version": "nexus-ai-progression/1",
                "actor_id": "Alpha",
                "model_id": "mock-alpha",
                "sequence": True,
                "previous_state_ref": None,
                "counts": {},
            },
            {"actor": "nexus", "subsystem": "ai_progression"},
        )
        self.assertTrue(forged.object_id.startswith("object:"))
        service = ProgressionService(world)
        with self.assertRaisesRegex(ProgressionError, "progression state is invalid"):
            service.portfolio(actor_id="Alpha", model_id="mock-alpha")


if __name__ == "__main__":
    unittest.main()
