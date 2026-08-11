from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from nexus_runtime.guardian import GuardianError, GuardianStore
from nexus_runtime.guardian_api import GuardianNexusAPI


class GuardianLockingTests(unittest.TestCase):
    def test_two_store_instances_serialize_one_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "guardian"
            first = GuardianStore(root)
            second = GuardianStore(root)
            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def append(store: GuardianStore, label: str) -> None:
                try:
                    barrier.wait(timeout=5)
                    store.append(
                        "substrate_event",
                        {
                            "operation": "actor.chat",
                            "mode_id": "anarchy",
                            "region_id": "commons",
                            "room": "#anarchy",
                            "observed_status": "error",
                            "request_shape_fingerprint": f"guardian_request_shape:{label}",
                            "speech_is_misconduct": False,
                            "hostile_actor_classification": None,
                            "citizenship_effect": "none",
                            "vote_effect": "none",
                            "evidence_effect": "none",
                            "error_code": "fixture",
                            "error_message": label,
                        },
                    )
                except BaseException as exc:  # pragma: no cover - assertion reports captured failure
                    errors.append(exc)

            threads = [
                threading.Thread(target=append, args=(first, "a")),
                threading.Thread(target=append, args=(second, "b")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            self.assertFalse(errors, errors)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            verified = GuardianStore(root).verify()
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["record_count"], 2)

    def test_guardian_initialization_failure_is_fail_passive(self) -> None:
        with mock.patch(
            "nexus_runtime.guardian_api.GuardianOfSubstrate",
            side_effect=GuardianError(
                "guardian_store_unavailable",
                "synthetic unavailable Guardian fixture",
            ),
        ):
            api = GuardianNexusAPI()

        result = api.handle(
            {
                "operation": "actor.chat",
                "member": {
                    "member_id": "Riot",
                    "model_id": "mock-riot",
                    "adapter_id": "mock",
                    "profile": "balanced",
                },
                "message": "I shall overthrow the filing cabinet.",
                "mode": "anarchy",
            }
        )
        self.assertEqual(result["status"], "ok", result)
        self.assertFalse(result["anarchy_guardian"]["recorded"])
        self.assertEqual(
            result["anarchy_guardian"]["gap_code"],
            "guardian_store_unavailable",
        )

        health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertEqual(
            health["guardian_of_the_substrate"]["status"],
            "unavailable",
        )
        self.assertEqual(
            health["guardian_of_the_substrate"]["ledger"][
                "substrate_availability_effect"
            ],
            "none",
        )

        guardian_status = api.handle({"operation": "guardian.status"})
        self.assertEqual(guardian_status["status"], "error")
        self.assertEqual(
            guardian_status["error"]["code"],
            "guardian_store_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
