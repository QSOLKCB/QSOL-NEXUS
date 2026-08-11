from __future__ import annotations

import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.agent_state import (
    AGENT_STATE_SCHEMA_VERSION,
    CONTEXT_BOTTLENECK_SCHEMA_VERSION,
    LANE_ORDER,
    MAX_CONTEXT_CHARS,
    publish_agent_state_update,
)
from nexus_runtime.world import WorldStore


class AgentStatePolicyTests(unittest.TestCase):
    def test_health_and_operations_publish_agent_state_contract(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        policy = health["agent_state"]
        self.assertEqual(policy["schema_version"], AGENT_STATE_SCHEMA_VERSION)
        self.assertEqual(policy["context_schema_version"], CONTEXT_BOTTLENECK_SCHEMA_VERSION)
        self.assertEqual(
            [item["lane"] for item in policy["lanes"]],
            list(LANE_ORDER),
        )
        self.assertFalse(policy["concurrency_contract"]["completion_order_is_semantic_authority"])
        self.assertFalse(policy["authority_invariants"]["context_router_is_model"])
        self.assertFalse(policy["authority_invariants"]["context_router_has_vote"])

        operations = api.handle({"operation": "system.operations"})["operations"]
        for operation in (
            "agent.state.policy",
            "agent.state.publish",
            "agent.state.snapshot",
            "agent.context.build",
            "agent.context.verify",
        ):
            self.assertIn(operation, operations)

        direct = api.handle({"operation": "agent.state.policy"})
        self.assertEqual(direct["status"], "ok")
        self.assertEqual(direct["policy"], policy)

    def test_runtime_agent_state_objects_cannot_be_forged(self) -> None:
        api = NexusAPI()
        for object_type in ("agent_state_update", "agent_state_snapshot", "agent_context"):
            with self.subTest(object_type=object_type):
                result = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {},
                        "provenance": {"actor": "nexus"},
                    }
                )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "invalid_request")
                self.assertIn("runtime-owned", result["error"]["message"])


class AgentStateValidationOwnershipTests(unittest.TestCase):
    def test_shared_publish_path_owns_identity_lane_and_source_ref_validation(self) -> None:
        world = WorldStore()
        with self.assertRaisesRegex(ValueError, "credential-shaped"):
            publish_agent_state_update(
                world,
                actor_id="sk-" + ("A" * 24),
                lane="memory",
                content="state",
                source_refs=[],
            )
        with self.assertRaisesRegex(ValueError, "lane must be one of"):
            publish_agent_state_update(
                world,
                actor_id="Alpha",
                lane="invented_lane",
                content="state",
                source_refs=[],
            )
        with self.assertRaisesRegex(ValueError, "source_refs must be a list"):
            publish_agent_state_update(
                world,
                actor_id="Alpha",
                lane="memory",
                content="state",
                source_refs="not-a-list",
            )


class AgentStateSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()

    def _source(self, label: str) -> str:
        result = self.api.handle(
            {
                "operation": "world.create",
                "object_type": "agent_state_fixture",
                "payload": {"label": label},
                "provenance": {"actor": "test"},
            }
        )
        self.assertEqual(result["status"], "ok")
        return result["object"]["object_id"]

    def _publish(
        self,
        lane: str,
        *,
        actor_id: str = "Alpha",
        content: str | None = None,
        source_refs: list[str] | None = None,
    ) -> dict:
        result = self.api.handle(
            {
                "operation": "agent.state.publish",
                "actor_id": actor_id,
                "lane": lane,
                "content": content or f"{lane} state",
                "source_refs": source_refs or [],
            }
        )
        self.assertEqual(result["status"], "ok")
        return result

    def test_snapshot_is_independent_of_module_completion_order(self) -> None:
        safety = self._publish("safety_control", source_refs=[self._source("safety")])
        memory = self._publish("memory", source_refs=[self._source("memory")])
        goals = self._publish("goals", source_refs=[self._source("goals")])
        refs = [safety["update_ref"], memory["update_ref"], goals["update_ref"]]

        forward = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": refs,
            }
        )
        reverse = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": list(reversed(refs)),
            }
        )
        self.assertEqual(forward["snapshot_ref"], reverse["snapshot_ref"])
        self.assertEqual(forward["snapshot"], reverse["snapshot"])
        self.assertEqual(
            [item["lane"] for item in forward["snapshot"]["updates"]],
            ["safety_control", "memory", "goals"],
        )
        self.assertFalse(forward["snapshot"]["completion_order_has_authority"])

    def test_partial_fast_snapshot_does_not_wait_for_or_leak_future_slow_state(self) -> None:
        safety = self._publish(
            "safety_control",
            content="Fast safety result is available now.",
            source_refs=[self._source("fast")],
        )
        early_snapshot = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": [safety["update_ref"]],
            }
        )
        early_context = self.api.handle(
            {
                "operation": "agent.context.build",
                "snapshot_ref": early_snapshot["snapshot_ref"],
            }
        )
        self.assertEqual(early_context["status"], "ok")
        early_ref = early_context["context_ref"]
        early_content = early_context["context"]["content"]
        self.assertIn("Fast safety result is available now.", early_content)
        self.assertNotIn("Slow reflective goal", early_content)

        goals = self._publish(
            "goals",
            content="Slow reflective goal arrived later.",
            source_refs=[self._source("slow")],
        )
        later_snapshot = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": [goals["update_ref"], safety["update_ref"]],
            }
        )
        later_context = self.api.handle(
            {
                "operation": "agent.context.build",
                "snapshot_ref": later_snapshot["snapshot_ref"],
            }
        )
        self.assertIn("Slow reflective goal arrived later.", later_context["context"]["content"])

        rebuilt_early = self.api.handle(
            {
                "operation": "agent.context.build",
                "snapshot_ref": early_snapshot["snapshot_ref"],
            }
        )
        self.assertEqual(rebuilt_early["context_ref"], early_ref)
        self.assertEqual(rebuilt_early["context"]["content"], early_content)

    def test_duplicate_lane_and_cross_identity_snapshot_fail_closed(self) -> None:
        first = self._publish("memory", content="first")
        second = self._publish("memory", content="second")
        duplicate_lane = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": [first["update_ref"], second["update_ref"]],
            }
        )
        self.assertEqual(duplicate_lane["status"], "error")
        self.assertEqual(duplicate_lane["error"]["code"], "agent_state_lane_conflict")

        beta = self._publish("goals", actor_id="Beta")
        mixed = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": [first["update_ref"], beta["update_ref"]],
            }
        )
        self.assertEqual(mixed["status"], "error")
        self.assertEqual(mixed["error"]["code"], "agent_state_identity_mismatch")

    def test_future_or_missing_source_ref_is_not_admitted(self) -> None:
        result = self.api.handle(
            {
                "operation": "agent.state.publish",
                "actor_id": "Alpha",
                "lane": "world_observation",
                "content": "I claim a future object already exists.",
                "source_refs": ["object:" + ("0" * 64)],
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "agent_state_source_not_found")


class DeterministicContextBottleneckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()

    def _publish(self, lane: str, content: str) -> str:
        result = self.api.handle(
            {
                "operation": "agent.state.publish",
                "actor_id": "Alpha",
                "lane": lane,
                "content": content,
                "source_refs": [],
            }
        )
        self.assertEqual(result["status"], "ok")
        return result["update_ref"]

    def test_full_context_is_bounded_reconstructible_and_has_no_authority(self) -> None:
        refs = [self._publish(lane, lane + ": " + ("x" * 8_000)) for lane in LANE_ORDER]
        snapshot = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": list(reversed(refs)),
            }
        )
        built = self.api.handle(
            {
                "operation": "agent.context.build",
                "snapshot_ref": snapshot["snapshot_ref"],
            }
        )
        self.assertEqual(built["status"], "ok")
        context = built["context"]
        self.assertLessEqual(context["context_chars"], MAX_CONTEXT_CHARS)
        self.assertEqual(context["selected_update_refs"], snapshot["snapshot"]["update_refs"])
        self.assertTrue(context["all_selected_updates_represented"])
        self.assertFalse(context["completion_order_has_authority"])
        self.assertEqual(context["epistemic_privilege"], "none")
        self.assertEqual(context["vote_weight_created"], 0)

        for lane in LANE_ORDER:
            self.assertIn(f"lane={lane}", context["content"])
        self.assertIn("[excerpt truncated]", context["content"])

        verification = self.api.handle(
            {
                "operation": "agent.context.verify",
                "context_ref": built["context_ref"],
            }
        )
        self.assertEqual(verification["status"], "verified")
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["reconstructed_context_ref"], built["context_ref"])
        self.assertFalse(verification["model_inference_used"])

    def test_context_object_is_safe_for_existing_model_evidence_renderer(self) -> None:
        update = self._publish("world_observation", "Observed immutable world state.")
        snapshot = self.api.handle(
            {
                "operation": "agent.state.snapshot",
                "actor_id": "Alpha",
                "update_refs": [update],
            }
        )
        built = self.api.handle(
            {
                "operation": "agent.context.build",
                "snapshot_ref": snapshot["snapshot_ref"],
            }
        )
        rendered = self.api.council.build_evidence_context([built["use_as_evidence_ref"]])
        self.assertIn("NEXUS deterministic Agent State context.", rendered)
        self.assertIn("Observed immutable world state.", rendered)
        self.assertNotIn("evidence excerpt truncated", rendered)


if __name__ == "__main__":
    unittest.main()
