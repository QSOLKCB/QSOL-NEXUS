from __future__ import annotations

import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.action_awareness import ACTION_AWARENESS_SCHEMA_VERSION


class ActionAwarenessPolicyTests(unittest.TestCase):
    def test_health_and_operations_publish_action_awareness_contract(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        policy = health["action_awareness"]
        self.assertEqual(policy["schema_version"], ACTION_AWARENESS_SCHEMA_VERSION)
        self.assertEqual(policy["principle"], "world_state_over_model_self_report")
        self.assertTrue(policy["deterministic_observation"])
        self.assertFalse(policy["model_self_report_is_authoritative"])
        self.assertFalse(policy["authority_invariants"]["model_may_declare_its_own_success"])

        operations = api.handle({"operation": "system.operations"})["operations"]
        self.assertIn("action.awareness.policy", operations)
        self.assertIn("action.awareness.expect_create", operations)
        self.assertIn("action.awareness.reconcile", operations)

        direct = api.handle({"operation": "action.awareness.policy"})
        self.assertEqual(direct["status"], "ok")
        self.assertEqual(direct["policy"], policy)

    def test_runtime_action_objects_cannot_be_forged_through_world_create(self) -> None:
        api = NexusAPI()
        for object_type in ("action_expectation", "action_reconciliation"):
            with self.subTest(object_type=object_type):
                result = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {},
                        "provenance": {"actor": "nexus", "subsystem": "action_awareness"},
                    }
                )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["code"], "invalid_request")
                self.assertIn("runtime-owned", result["error"]["message"])


class ActionAwarenessReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = NexusAPI()

    def _expect(self, value: int = 7) -> dict[str, object]:
        result = self.api.handle(
            {
                "operation": "action.awareness.expect_create",
                "actor_id": "Alpha",
                "action_label": "create a grounded observation",
                "object_type": "observation_note",
                "payload": {"value": value, "claim": "world state wins"},
                "provenance": {"actor": "Alpha"},
            }
        )
        self.assertEqual(result["status"], "ok")
        return result

    def test_missing_expected_object_is_reported_without_model_judgment(self) -> None:
        expected = self._expect()
        result = self.api.handle(
            {
                "operation": "action.awareness.reconcile",
                "expectation_ref": expected["expectation_ref"],
            }
        )
        self.assertEqual(result["status"], "ok")
        reconciliation = result["reconciliation"]
        self.assertEqual(reconciliation["outcome"], "missing")
        self.assertFalse(reconciliation["matched"])
        self.assertTrue(reconciliation["world_observation_only"])
        self.assertFalse(reconciliation["model_self_report_used"])
        self.assertFalse(reconciliation["evidence_state_promoted"])

    def test_exact_world_create_reconciles_as_matched(self) -> None:
        expected = self._expect()
        created = self.api.handle(
            {
                "operation": "world.create",
                "object_type": "observation_note",
                "payload": {"value": 7, "claim": "world state wins"},
                "provenance": {"actor": "Alpha"},
            }
        )
        self.assertEqual(created["status"], "ok")
        self.assertEqual(
            created["object"]["object_id"],
            expected["expectation"]["expected_object"]["object_ref"],
        )

        result = self.api.handle(
            {
                "operation": "action.awareness.reconcile",
                "expectation_ref": expected["expectation_ref"],
            }
        )
        reconciliation = result["reconciliation"]
        self.assertEqual(reconciliation["outcome"], "matched")
        self.assertTrue(reconciliation["matched"])
        self.assertEqual(
            reconciliation["observed_object_ref"],
            created["object"]["object_id"],
        )

    def test_explicit_different_observation_reconciles_as_diverged(self) -> None:
        expected = self._expect(value=7)
        actual = self.api.handle(
            {
                "operation": "world.create",
                "object_type": "observation_note",
                "payload": {"value": 8, "claim": "world state wins"},
                "provenance": {"actor": "Alpha"},
            }
        )
        result = self.api.handle(
            {
                "operation": "action.awareness.reconcile",
                "expectation_ref": expected["expectation_ref"],
                "observed_object_ref": actual["object"]["object_id"],
            }
        )
        reconciliation = result["reconciliation"]
        self.assertEqual(reconciliation["outcome"], "diverged")
        self.assertFalse(reconciliation["matched"])
        self.assertEqual(
            reconciliation["observed_object_ref"],
            actual["object"]["object_id"],
        )
        self.assertEqual(
            self.api.handle(
                {
                    "operation": "world.inspect",
                    "object_ref": actual["object"]["object_id"],
                }
            )["object"]["payload"]["value"],
            8,
        )

    def test_repeated_expectation_is_content_addressed_and_deterministic(self) -> None:
        first = self._expect()
        second = self._expect()
        self.assertEqual(first["expectation_ref"], second["expectation_ref"])

    def test_unknown_expectation_stays_inside_structured_error_boundary(self) -> None:
        result = self.api.handle(
            {
                "operation": "action.awareness.reconcile",
                "expectation_ref": "object:" + ("0" * 64),
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "action_expectation_not_found")

    def test_unknown_explicit_observation_stays_structured(self) -> None:
        expected = self._expect()
        result = self.api.handle(
            {
                "operation": "action.awareness.reconcile",
                "expectation_ref": expected["expectation_ref"],
                "observed_object_ref": "object:" + ("f" * 64),
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "action_observation_not_found")


if __name__ == "__main__":
    unittest.main()
