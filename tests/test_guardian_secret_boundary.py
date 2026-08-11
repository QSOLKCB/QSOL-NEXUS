from __future__ import annotations

import json
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.guardian import GuardianError, GuardianStore


SYNTHETIC_SECRET = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"


def latest_substrate_event(api: NexusAPI) -> dict[str, object]:
    listed = api.handle(
        {
            "operation": "guardian.list",
            "record_type": "substrate_event",
            "limit": 10,
        }
    )
    if listed.get("status") != "ok" or not listed.get("records"):
        raise AssertionError(f"Guardian event unavailable: {listed!r}")
    return listed["records"][-1]


class GuardianSecretBoundaryTests(unittest.TestCase):
    def test_store_scrubs_all_string_values_before_persistence(self) -> None:
        store = GuardianStore()
        record = store.append(
            "repair_proposal",
            {
                "summary": f"repair notes contain {SYNTHETIC_SECRET}",
                "nested": {
                    "list": [
                        f"fixture token={SYNTHETIC_SECRET}",
                        "ordinary text",
                    ]
                },
            },
        )
        serialized = json.dumps(store.inspect(record.record_ref).payload, sort_keys=True)
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertIn("<REDACTED:OPENAI_STYLE_TOKEN:1>", serialized)

    def test_store_rejects_secret_bearing_object_keys(self) -> None:
        store = GuardianStore()
        with self.assertRaises(GuardianError) as caught:
            store.append(
                "substrate_event",
                {SYNTHETIC_SECRET: "a secret must never become a durable key"},
            )
        self.assertEqual(caught.exception.code, "guardian_secret_material")

    def test_public_repair_pipeline_cannot_persist_operator_secret(self) -> None:
        api = NexusAPI()
        failed = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "Riot",
                    "model_id": "mock-riot",
                    "adapter_id": "mock",
                    "profile": "balanced",
                },
                "mode": "anarchy",
            }
        )
        self.assertEqual(failed["status"], "error")
        self.assertTrue(failed["anarchy_guardian"]["accepted"])
        observation_ref = latest_substrate_event(api)["record_ref"]
        candidate = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": observation_ref,
                "expected_status": "ok",
            }
        )
        self.assertEqual(candidate["status"], "defect_candidate")

        proposal = api.handle(
            {
                "operation": "guardian.repair.propose",
                "defect_ref": candidate["defect_candidate_ref"],
                "summary": f"summary {SYNTHETIC_SECRET}",
                "invariant": f"invariant {SYNTHETIC_SECRET}",
                "regression_fixture": f"fixture {SYNTHETIC_SECRET}",
            }
        )
        self.assertEqual(proposal["status"], "proposed", proposal)
        stored = api.handle(
            {
                "operation": "guardian.inspect",
                "record_ref": proposal["repair_proposal_ref"],
            }
        )
        serialized = json.dumps(stored, sort_keys=True)
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertIn("<REDACTED:OPENAI_STYLE_TOKEN:1>", serialized)

    def test_reconciliation_metadata_is_also_secret_scrubbed(self) -> None:
        api = NexusAPI()
        failed = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "Riot",
                    "model_id": "mock-riot",
                    "adapter_id": "mock",
                    "profile": "balanced",
                },
                "mode": "anarchy",
            }
        )
        self.assertTrue(failed["anarchy_guardian"]["accepted"])
        observation_ref = latest_substrate_event(api)["record_ref"]
        reconciled = api.handle(
            {
                "operation": "guardian.reconcile",
                "observation_ref": observation_ref,
                "expected_status": "error",
                "expected_error_code": SYNTHETIC_SECRET,
            }
        )
        self.assertEqual(reconciled["status"], "defect_candidate")
        stored = api.handle(
            {
                "operation": "guardian.inspect",
                "record_ref": reconciled["reconciliation_ref"],
            }
        )
        serialized = json.dumps(stored, sort_keys=True)
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertIn("<REDACTED:OPENAI_STYLE_TOKEN:1>", serialized)


if __name__ == "__main__":
    unittest.main()
