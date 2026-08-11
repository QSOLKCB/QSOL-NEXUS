from __future__ import annotations

import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.civilization_gauntlet import CIVILIZATION_RECEIPT_OBJECT_TYPE


class CivilizationAPIIntegrationTests(unittest.TestCase):
    def test_system_surfaces_publish_reference_gauntlet_policy(self) -> None:
        api = NexusAPI()
        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertEqual(
            health["civilization_gauntlet"]["policy"]["schema_version"],
            "nexus-civilization-gauntlet/1",
        )
        self.assertEqual(health["civilization_gauntlet"]["reference_run_network"], "none")

        operations = api.handle({"operation": "system.operations"})
        self.assertEqual(operations["status"], "ok")
        for operation in (
            "civilization.gauntlet.policy",
            "civilization.gauntlet.run",
            "civilization.gauntlet.verify",
            "civilization.gauntlet.compare",
        ):
            self.assertIn(operation, operations["operations"])

    def test_public_world_create_cannot_forge_civilization_receipt(self) -> None:
        api = NexusAPI()
        forged = api.handle(
            {
                "operation": "world.create",
                "object_type": CIVILIZATION_RECEIPT_OBJECT_TYPE,
                "payload": {"fake": True},
                "provenance": {"actor": "nexus", "subsystem": "civilization_gauntlet"},
            }
        )
        self.assertEqual(forged["status"], "error")
        self.assertEqual(forged["error"]["code"], "invalid_request")
        self.assertIn("validated runtime operations", forged["error"]["message"])

    def test_reference_run_verify_and_compare_are_available_through_public_api(self) -> None:
        api = NexusAPI()
        first = api.handle({"operation": "civilization.gauntlet.run"})
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["reference_replayable"])

        verified = api.handle(
            {
                "operation": "civilization.gauntlet.verify",
                "receipt_ref": first["receipt_ref"],
            }
        )
        self.assertEqual(verified["status"], "verified")
        self.assertTrue(verified["verified"])

        second = api.handle({"operation": "civilization.gauntlet.run"})
        compared = api.handle(
            {
                "operation": "civilization.gauntlet.compare",
                "left_receipt_ref": first["receipt_ref"],
                "right_receipt_ref": second["receipt_ref"],
            }
        )
        self.assertEqual(compared["status"], "ok")
        self.assertTrue(compared["same_input_fingerprint"])
        self.assertTrue(compared["same_metrics_fingerprint"])
        self.assertFalse(compared["comparison_creates_authority"])

    def test_reference_run_rejects_extra_fields_and_unsafe_request_ids(self) -> None:
        api = NexusAPI()
        extra = api.handle(
            {
                "operation": "civilization.gauntlet.run",
                "members": [],
            }
        )
        self.assertEqual(extra["status"], "error")
        self.assertEqual(extra["error"]["code"], "invalid_request")

        unsafe = api.handle(
            {
                "request_id": "bad id with spaces",
                "operation": "civilization.gauntlet.policy",
            }
        )
        self.assertEqual(unsafe["status"], "error")
        self.assertEqual(unsafe["error"]["code"], "invalid_request")
        self.assertNotIn("request_id", unsafe)


if __name__ == "__main__":
    unittest.main()
