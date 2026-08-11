from __future__ import annotations

import unittest

from nexus_runtime import NexusAPI


class CivicDueProcessHardeningTests(unittest.TestCase):
    def test_unhashable_world_object_type_stays_inside_structured_error_boundary(self) -> None:
        api = NexusAPI()
        response = api.handle(
            {
                "operation": "world.create",
                "message": {},
                "seed": "x",
                "evidence_refs": 1.5,
                "object_type": {"text": 1.5},
            }
        )
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error"]["code"], "invalid_request")

    def test_reserved_type_precheck_requires_text_before_membership_test(self) -> None:
        api = NexusAPI()
        for object_type in ([], {}, 1.5, True, None):
            with self.subTest(object_type=object_type):
                response = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {},
                    }
                )
                self.assertEqual(response["status"], "error")
                self.assertEqual(response["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
