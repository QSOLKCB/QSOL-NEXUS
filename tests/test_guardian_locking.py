from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from nexus_runtime.guardian import GuardianStore


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


if __name__ == "__main__":
    unittest.main()
