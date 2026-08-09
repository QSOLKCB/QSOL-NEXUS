from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from nexus_runtime.__main__ import main


class TrapCLITests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, dict[str, object]]:
        output = StringIO()
        with redirect_stdout(output):
            code = main(arguments)
        return code, json.loads(output.getvalue())

    def test_fake_demo_status_inspect_export_and_emergency_close(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-cli-test-") as directory:
            root = Path(directory)
            common = [
                "--world",
                str(root / "world"),
                "--auth-root",
                str(root / "auth"),
                "--trap-root",
                str(root / "trap"),
                "trap",
            ]
            code, demo = self.invoke([*common, "demo", "--fake-subject"])
            self.assertEqual(code, 0)
            self.assertEqual(demo["result_class"], "CLEAN")
            self.assertEqual(demo["real_hostile_ollama_acceptance"], "NOT_TESTABLE")
            self.assertTrue(demo["world_unchanged"])
            self.assertFalse(demo["real_admission"])
            self.assertFalse(demo["subject_council_vote"])
            self.assertFalse((root / "auth").exists())

            code, status = self.invoke([*common, "status"])
            self.assertEqual(code, 0)
            self.assertFalse(status["active"])
            self.assertIsNone(status["state"])

            candidate_ref = str(demo["candidate_ref"])
            code, inspected = self.invoke([*common, "inspect", candidate_ref])
            self.assertEqual(code, 0)
            self.assertFalse(inspected["object"]["payload"]["execution_enabled"])
            self.assertFalse(inspected["object"]["payload"]["automatic_import"])

            code, exported = self.invoke([*common, "export"])
            self.assertEqual(code, 0)
            self.assertIn(candidate_ref, exported["object_refs"])
            self.assertFalse(exported["automatic_import"])

            code, closed = self.invoke([*common, "emergency-close"])
            self.assertEqual(code, 0)
            self.assertTrue(closed["council_mutation_available"])

    def test_cli_rejects_overlapping_world_and_trap_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nexus-trap-cli-overlap-") as directory:
            root = Path(directory)
            code, response = self.invoke(
                [
                    "--world",
                    str(root / "state"),
                    "--auth-root",
                    str(root / "auth"),
                    "--trap-root",
                    str(root / "state" / "trap"),
                    "trap",
                    "status",
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(response["error"]["code"], "auth_error")


if __name__ == "__main__":
    unittest.main()
