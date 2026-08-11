from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "tools" / "nexus_adversary_compare.py"


def report(
    rows: list[tuple[str, str]],
    *,
    profile: str = "full",
    seed: int = 1234,
    iterations: int = 512,
) -> dict:
    return {
        "schema_version": "nexus-adversarial-gauntlet/1",
        "profile": profile,
        "seed": seed,
        "iterations": iterations,
        "results": [{"name": name, "status": status} for name, status in rows],
    }


class AdversarialToolTests(unittest.TestCase):
    def run_compare(self, baseline: dict, candidate: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline_path = root / "baseline.json"
            candidate_path = root / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(COMPARE), str(baseline_path), str(candidate_path)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

    def test_comparator_allows_existing_failure_without_new_regression(self) -> None:
        result = self.run_compare(
            report([("known-hole", "fail"), ("stable", "pass")]),
            report([("known-hole", "fail"), ("stable", "pass")]),
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NO NEW FAILURES OR CHECK LOSS", result.stdout)

    def test_comparator_returns_nonzero_for_new_failure(self) -> None:
        result = self.run_compare(
            report([("stable", "pass")]),
            report([("stable", "fail")]),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("NEW FAILURES", result.stdout)
        self.assertIn("stable", result.stdout)

    def test_comparator_returns_nonzero_when_candidate_drops_a_check(self) -> None:
        result = self.run_compare(
            report([("keep-me", "pass"), ("stable", "pass")]),
            report([("stable", "pass")]),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("MISSING CHECKS", result.stdout)
        self.assertIn("keep-me", result.stdout)

    def test_comparator_reports_fixed_failure(self) -> None:
        result = self.run_compare(
            report([("known-hole", "fail")]),
            report([("known-hole", "pass")]),
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("FIXED", result.stdout)
        self.assertIn("known-hole", result.stdout)

    def test_comparator_rejects_mismatched_fuzz_configuration(self) -> None:
        result = self.run_compare(
            report([("malformed-request-fuzz", "fail")], seed=1, iterations=512),
            report([("malformed-request-fuzz", "pass")], seed=2, iterations=32),
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INCOMPATIBLE CONFIGURATION", result.stdout)

    def test_comparator_rejects_missing_configuration_metadata(self) -> None:
        baseline = report([("stable", "pass")])
        candidate = report([("stable", "pass")])
        baseline.pop("seed")
        candidate.pop("seed")
        result = self.run_compare(baseline, candidate)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INCOMPATIBLE CONFIGURATION", result.stdout)

    def test_missing_failed_check_is_not_reported_fixed(self) -> None:
        result = self.run_compare(
            report([("known-hole", "fail"), ("stable", "pass")]),
            report([("stable", "pass")]),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("MISSING CHECKS", result.stdout)
        fixed_section = result.stdout.split("FIXED:", 1)
        if len(fixed_section) == 2:
            self.assertNotIn("known-hole", fixed_section[1].split("MISSING CHECKS:", 1)[0])

    def test_runner_rejects_missing_corpus_path_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_path = root / "gauntlet.json"
            missing = root / "does-not-exist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "nexus_adversary.py"),
                    "--profile",
                    "probes",
                    "--iterations",
                    "1",
                    "--no-default-corpus",
                    "--corpus",
                    str(missing),
                    "--json-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            row = next(item for item in payload["results"] if item["name"] == "corpus-configuration")
            self.assertEqual(row["status"], "fail")

    def test_runner_rejects_string_contains_expectation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corpus = root / "bad.jsonl"
            report_path = root / "gauntlet.json"
            corpus.write_text(
                json.dumps(
                    {
                        "name": "bad-contains",
                        "request": {"operation": "definitely.not.an.operation"},
                        "expect": {"contains": "error"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "nexus_adversary.py"),
                    "--profile",
                    "probes",
                    "--iterations",
                    "1",
                    "--no-default-corpus",
                    "--corpus",
                    str(corpus),
                    "--json-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            row = next(item for item in payload["results"] if "bad-contains" in item["name"])
            self.assertEqual(row["status"], "fail")
            self.assertIn("expect.contains must be an array", row["detail"])

    def test_runner_records_dirty_worktree(self) -> None:
        marker = ROOT / f".nexus-gauntlet-dirty-test-{os.getpid()}-{uuid.uuid4().hex}"
        try:
            marker.write_text("dirty\n", encoding="utf-8")
            with tempfile.TemporaryDirectory() as temp:
                report_path = Path(temp) / "gauntlet.json"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "nexus_adversary.py"),
                        "--profile",
                        "probes",
                        "--iterations",
                        "1",
                        "--no-default-corpus",
                        "--json-out",
                        str(report_path),
                    ],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertTrue(payload["worktree"]["dirty"])
                self.assertIn(marker.name, payload["worktree"]["status"])
        finally:
            marker.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
