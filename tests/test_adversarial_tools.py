from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "tools" / "nexus_adversary_compare.py"


def report(rows: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": "nexus-adversarial-gauntlet/1",
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


if __name__ == "__main__":
    unittest.main()
