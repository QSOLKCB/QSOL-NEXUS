from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.stenographer import CourtroomStenographer
from nexus_runtime.types import CouncilMember


ROOT = Path(__file__).resolve().parents[1]


class StenographerCLITests(unittest.TestCase):
    def run_cli(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "nexus_runtime",
                "--stenographer-root",
                str(root),
                "stenographer",
                *arguments,
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_read_only_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stenographer"
            service = CourtroomStenographer(root)
            actor = DeterministicMockActor(
                CouncilMember("A", "mock-a", "mock")
            )
            record = service.record_text(
                "actor.direct_response",
                actor,
                "answer",
                stimulus={"message": "question"},
                mode_id="analytical",
                geometry_region_id="observatory",
                attempt="direct_response",
            )

            status = self.run_cli(root, "status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["record_count"], 1)

            inspect = self.run_cli(root, "inspect", record.record_ref)
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            self.assertEqual(
                json.loads(inspect.stdout)["record"]["record_ref"],
                record.record_ref,
            )

            export = self.run_cli(root, "export")
            self.assertEqual(export.returncode, 0, export.stderr)
            payload = json.loads(export.stdout)
            self.assertEqual(payload["record_refs"], [record.record_ref])
            self.assertTrue(payload["read_only"])

    @unittest.skipIf(os.name == "nt", "POSIX permission semantics")
    def test_cli_storage_error_is_sanitized_and_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "too-open"
            root.mkdir(mode=0o755)
            os.chmod(root, 0o755)
            result = self.run_cli(root, "status")
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload["error"]["code"],
                "stenographer_store_unavailable",
            )
            self.assertNotIn(str(root), result.stdout + result.stderr)

    def test_jsonl_startup_overlap_is_a_bounded_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nexus_runtime",
                    "--world",
                    str(base / "world"),
                    "--auth-root",
                    str(base / "auth"),
                    "--stenographer-root",
                    str(base / "world" / "stenographer"),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                input="",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error"]["code"], "auth_error")
            self.assertIn("disjoint", payload["error"]["message"])
            self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_stenographer_cli_resolves_environment_default_trap_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shared_root = base / "shared-trap-stenographer"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["NEXUS_TRAP_ROOT"] = str(shared_root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nexus_runtime",
                    "--auth-root",
                    str(base / "auth"),
                    "--stenographer-root",
                    str(shared_root),
                    "stenographer",
                    "status",
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error"]["code"], "auth_error")
            self.assertIn("trap storage and stenographer storage", payload["error"]["message"])
            self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
