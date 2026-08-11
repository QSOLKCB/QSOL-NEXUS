from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.scrub import SecretScrubber
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    path = ROOT / "tools" / "nexus_release_hardening.py"
    spec = importlib.util.spec_from_file_location("nexus_post_merge_audit_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load hardening runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARDENING = _load_runner()


class PostMergeGrokAuditClosureTests(unittest.TestCase):
    TOKEN_BODY = "abcdefghijklmnopqrstuvwxyz0123"

    def test_f1_tui_banner_uses_cargo_package_version_and_has_no_alpha_identity(self) -> None:
        source = (ROOT / "tui" / "src" / "main.rs").read_text(encoding="utf-8")
        self.assertIn('env!("CARGO_PKG_VERSION")', source)
        self.assertNotIn("NEXUS TUI 2.0 alpha", source)
        self.assertNotIn("alpha10.2", source)

    def test_f2_scrubber_blocks_uppercase_and_unicode_format_control_variants(self) -> None:
        scrubber = SecretScrubber()
        normal = scrubber.scrub("token sk-" + self.TOKEN_BODY)
        upper = scrubber.scrub("token SK-" + self.TOKEN_BODY)
        zwsp = scrubber.scrub("token sk\u200b-" + self.TOKEN_BODY)
        for result in (normal, upper, zwsp):
            self.assertTrue(result.changed)
            self.assertNotIn(self.TOKEN_BODY, result.text)
            self.assertIn("<REDACTED:OPENAI_STYLE_TOKEN:1>", result.text)
        self.assertNotIn("\u200b", zwsp.text)

    def test_f2_wall_and_council_never_persist_bypass_canaries(self) -> None:
        for text in ("token SK-" + self.TOKEN_BODY, "token sk\u200b-" + self.TOKEN_BODY):
            api = NexusAPI()
            posted = api.handle({"operation": "wall.post", "author_id": "operator", "text": text})
            self.assertEqual(posted["status"], "ok")
            self.assertTrue(posted["secret_scrub"]["changed"])
            self.assertNotIn(self.TOKEN_BODY, posted["post"]["payload"]["text"])

            world = WorldStore()
            actors = [
                DeterministicMockActor(CouncilMember(f"M{i}", f"m{i}"))
                for i in range(3)
            ]
            result = CouncilCoordinator(world).run(text, actors)
            stored = world.inspect(result["question_ref"]).payload["text"]
            self.assertNotIn(self.TOKEN_BODY, stored)
            self.assertTrue(result["secret_scrub"]["changed"])

    def test_f3_report_is_bound_to_exact_commit_and_tree(self) -> None:
        checks = [HARDENING.CheckResult(name, "pass", 0.0, "ok") for name in sorted(HARDENING.REQUIRED_CHECK_NAMES)]
        report = HARDENING._build_report(checks)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
        self.assertEqual(report["git_commit"], commit)
        self.assertEqual(report["git_tree"], tree)
        self.assertEqual(HARDENING._commit_binding(commit, commit, tree).status, "pass")
        self.assertEqual(HARDENING._commit_binding("0" * 40, commit, tree).status, "fail")

    def test_f4_matrix_intentionally_covers_full_python_test_inventory(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        detail = HARDENING._audit_matrix_data(matrix, ROOT / "tests")
        inventory = {path for path in (ROOT / "tests").glob("test_*.py") if path.is_file()}
        self.assertEqual(len(inventory), HARDENING.EXPECTED_PYTHON_TEST_FILES)
        self.assertIn(f"{len(inventory)}/{len(inventory)} test files", detail)
        self.assertIn("test_*.py", next(g for g in matrix["gates"] if g["id"] == "release_composition")["patterns"])

    def test_f5_candidate_metadata_uses_scope_vocabulary_and_new_sequence(self) -> None:
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        self.assertNotIn("base_feature_pr", candidate)
        self.assertEqual(candidate["feature_surface_through_pr"], 50)
        self.assertEqual(candidate["scope_through_pr"], 51)
        self.assertEqual(candidate["candidate_pr"], 52)
        self.assertEqual(candidate["post_stable"]["pr_53"], "Lean 4 Formal Verification")
        self.assertIn("Zenodo", candidate["post_stable"]["pr_54"])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("The alpha10.3 release-prep adds", readme)

    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        closure = matrix["post_merge_audit_closure"]
        self.assertTrue(closure["required_before_stable"])
        self.assertEqual(set(closure["finding_ids"]), HARDENING.REQUIRED_POST_MERGE_FINDING_IDS)
        self.assertEqual(closure["verification"], "tests/test_post_merge_grok_audit.py")


if __name__ == "__main__":
    unittest.main()
