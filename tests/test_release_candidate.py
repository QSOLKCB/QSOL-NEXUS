from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib
import unittest
from unittest import mock

from nexus_runtime import PROTOCOL_VERSION, RUNTIME_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _load_release_runner():
    path = ROOT / "tools" / "nexus_2_1_1_release_candidate.py"
    spec = importlib.util.spec_from_file_location("nexus_2_1_1_release_candidate_test_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load NEXUS 2.1.1 release-candidate runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RELEASE_RUNNER = _load_release_runner()


class HistoricalNEXUS20ReleaseTests(unittest.TestCase):
    def test_v2_0_release_metadata_remains_historical_and_frozen(self) -> None:
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        identity = (ROOT / "publication" / "nexus-2.0-formalization" / "IDENTITY.env").read_text(encoding="utf-8")

        self.assertEqual(candidate["target_version"], "2.0.0")
        self.assertEqual(candidate["target_tag"], "v2.0.0")
        self.assertEqual(candidate["candidate_pr"], 52)
        self.assertFalse(candidate["stable_release"])
        self.assertEqual(matrix["target_version"], "2.0.0")
        self.assertEqual(matrix["milestone"], "PR #52")
        self.assertFalse(matrix["stable_release"])
        self.assertIn(
            "NEXUS_STABLE_COMMIT=cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a",
            identity,
        )
        self.assertIn("ZENODO_DOI=10.5281/zenodo.21895577", identity)

    def test_v2_0_historical_hardening_inventory_remains_pinned(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["profile"], "final_release_candidate")
        self.assertEqual(matrix["scope_through_pr"], 51)
        self.assertEqual(matrix["expected_python_test_files"], 83)
        release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
        self.assertIn("test_wall*.py", release_gate["patterns"])
        self.assertIn("test_release_candidate.py", release_gate["patterns"])
        self.assertIn("test_release_upgrade_rehearsal.py", release_gate["patterns"])
        self.assertEqual(
            set(matrix["external_audit_closure"]["finding_ids"]),
            {f"R{i}" for i in range(1, 13)},
        )


class NEXUS211ReleaseCandidateTests(unittest.TestCase):
    @staticmethod
    def _candidate() -> dict:
        return json.loads((ROOT / "release" / "nexus_2_1_1_candidate.json").read_text(encoding="utf-8"))

    @staticmethod
    def _matrix() -> dict:
        return json.loads((ROOT / "release" / "nexus_2_1_1_matrix.json").read_text(encoding="utf-8"))

    @staticmethod
    def _manifest() -> dict:
        return json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))

    def test_current_executable_release_identity_is_aligned(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        lock = tomllib.loads((ROOT / "tui" / "Cargo.lock").read_text(encoding="utf-8"))
        manifest = self._manifest()
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

        self.assertEqual(PROTOCOL_VERSION, "nexus/0.15")
        self.assertEqual(RUNTIME_VERSION, "2.1.1")
        self.assertEqual(pyproject["project"]["version"], "2.1.1")
        self.assertEqual(cargo["package"]["version"], "2.1.1")
        local_lock = [
            package for package in lock["package"] if package.get("name") == "nexus-irc-tui"
        ]
        self.assertEqual(len(local_lock), 1)
        self.assertEqual(local_lock[0]["version"], "2.1.1")
        self.assertEqual(manifest["release_identity"]["protocol"], "nexus/0.15")
        self.assertEqual(manifest["release_identity"]["runtime"], "2.1.1")
        self.assertEqual(manifest["release_identity"]["python_package"], "2.1.1")
        self.assertEqual(manifest["release_identity"]["rust_tui"], "2.1.1")
        self.assertEqual(
            manifest["release_identity"]["release_posture"],
            "release_candidate_2_1_1",
        )
        self.assertTrue(manifest["release_identity"]["stable_2_0"])
        self.assertRegex(citation, r"(?m)^version:\s*2\.1\.1\s*$")

    def test_candidate_preserves_historical_tags_and_pr60_provenance(self) -> None:
        candidate = self._candidate()
        self.assertEqual(candidate["candidate_pr"], 61)
        self.assertEqual(candidate["target_version"], "2.1.1")
        self.assertEqual(candidate["target_tag"], "v2.1.1")
        self.assertEqual(candidate["protocol"], "nexus/0.15")
        self.assertFalse(candidate["stable_release"])
        self.assertFalse(candidate["release_authority"])
        self.assertEqual(
            candidate["candidate_base"]["merge_commit"],
            "80cda46e614f44b47861471cb329e29a348cab43",
        )
        historical = candidate["historical_v2_1_0_tag"]
        self.assertEqual(
            historical["commit"],
            "839303ea512631e527073682343341742cead975",
        )
        self.assertEqual(historical["move_or_rewrite"], "forbidden")
        self.assertFalse(historical["release_target"])
        hardening = candidate["extension_hardening"]
        self.assertEqual(hardening["artifact_id"], 9421970922)
        self.assertEqual(
            hardening["artifact_digest"],
            "sha256:16674e62495ed5b66f69269ec2e5fb9cdb300b39bf2b45212f00085daa83ffbb",
        )
        self.assertFalse(candidate["empirical_gates"]["blocking_for_2_1_1_software_release"])
        self.assertFalse(candidate["empirical_gates"]["live_success_claimed_by_ci"])

    def test_protocol_bump_is_explicitly_additive_not_breaking(self) -> None:
        candidate = self._candidate()
        change = candidate["protocol_change"]
        self.assertEqual(change["from"], "nexus/0.14")
        self.assertEqual(change["to"], "nexus/0.15")
        self.assertEqual(change["classification"], "additive_minor_protocol_surface")
        self.assertFalse(change["breaking_change_claimed"])

    def test_release_matrix_requires_identity_history_rust_and_integrity_gates(self) -> None:
        matrix = self._matrix()
        self.assertEqual(matrix["candidate_pr"], 61)
        self.assertEqual(matrix["target_version"], "2.1.1")
        self.assertEqual(matrix["target_tag"], "v2.1.1")
        self.assertEqual(matrix["protocol"], "nexus/0.15")
        self.assertEqual(matrix["expected_python_test_files"], 83)
        gate_ids = {gate["id"] for gate in matrix["required_gates"]}
        self.assertEqual(
            gate_ids,
            {
                "release_identity",
                "post_stable_extension",
                "historical_release_regression",
                "rust_release_surface",
                "candidate_integrity",
            },
        )
        integrity = next(g for g in matrix["required_gates"] if g["id"] == "candidate_integrity")
        self.assertIn("candidate_tree_clean_after", integrity["checks"])
        self.assertIn("candidate_identity_unchanged", integrity["checks"])
        rust = next(g for g in matrix["required_gates"] if g["id"] == "rust_release_surface")
        self.assertIn("cargo_test_locked", rust["checks"])
        self.assertIn("cargo_check_locked", rust["checks"])

    def test_human_and_machine_release_docs_record_tag_archaeology_and_gate(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        manifest = self._manifest()
        notes = (ROOT / "docs" / "RELEASE_NOTES_2.1.1.md").read_text(encoding="utf-8")
        compatibility = (ROOT / "docs" / "COMPATIBILITY.md").read_text(encoding="utf-8")
        sequence = (ROOT / "docs" / "RELEASE_SEQUENCE.md").read_text(encoding="utf-8")

        for text in (readme, notes, compatibility, sequence):
            self.assertIn("v2.1.0", text)
            self.assertIn("839303ea512631e527073682343341742cead975", text)
            self.assertIn("v2.1.1", text)
        self.assertIn("tag not created by this PR", readme)
        self.assertIn("Only the exact reviewed-and-green merged PR #61 commit", notes)
        self.assertEqual(
            manifest["post_stable_extension"]["v2_1_0_tag"]["move"],
            "forbidden",
        )
        self.assertFalse(manifest["release_candidate_2_1_1"]["tag_created_in_pr"])
        self.assertFalse(manifest["release_candidate_2_1_1"]["release_authority"])

    def test_operator_architecture_and_security_docs_match_current_candidate(self) -> None:
        howto = (ROOT / "HOWTO.md").read_text(encoding="utf-8")
        architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        for text in (howto, architecture, security):
            self.assertIn("2.1.1", text)
            self.assertIn("nexus/0.15", text)
            self.assertIn("v2.0.0", text)
            self.assertIn("historical", text.casefold())
        self.assertIn("PR #61", howto)
        self.assertIn("PR #61", architecture)
        self.assertIn("PR #61", security)
        self.assertNotIn("current PR #52 candidate", howto.casefold())
        self.assertNotIn("release state  release candidate until exact merged #52", architecture)
        self.assertNotIn("PR #52 is now the final pre-stable", security)

    def test_release_runner_is_exact_commit_lockfile_strict_and_non_authoritative(self) -> None:
        source = (ROOT / "tools" / "nexus_2_1_1_release_candidate.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "nexus-2.1.1-release-candidate.yml").read_text(encoding="utf-8")
        certified = "a5fea299fbe682c9672dc577d2e683cebdb9f8f4"
        self.assertIn('TARGET_TAG = "v2.1.1"', source)
        self.assertIn('HISTORICAL_TAG = "v2.1.0"', source)
        self.assertIn('"test", "--locked"', source)
        self.assertIn('"check", "--locked"', source)
        self.assertIn('"release_authority": False', source)
        self.assertIn('"tag_created": False', source)
        self.assertIn('--expect-commit "$NEXUS_211_EXPECT"', workflow)
        self.assertNotIn('--expect-commit "$GITHUB_SHA"', workflow)
        self.assertIn(f"NEXUS_211_CERTIFIED_MERGE: {certified}", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("fetch-tags: true", workflow)
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", workflow)

    def test_candidate_workflow_uses_event_range_readme_contract_and_candidate_lifecycle(self) -> None:
        source = (ROOT / "tools" / "nexus_2_1_1_release_candidate.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "nexus-2.1.1-release-candidate.yml").read_text(encoding="utf-8")
        certified = "a5fea299fbe682c9672dc577d2e683cebdb9f8f4"
        self.assertIn("uses: ./.github/actions/readme-contract", workflow)
        self.assertNotIn("tools/validate_readme_contract.py", source)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("  push:\n    branches:\n      - main", workflow)
        self.assertIn("github.event.pull_request.number == 61", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn(f"ref: ${{{{ github.event_name == 'workflow_dispatch' && '{certified}' || github.sha }}}}", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$NEXUS_211_EXPECT"', workflow)
        self.assertIn('test "$NEXUS_211_EXPECT" = "$NEXUS_211_CERTIFIED_MERGE"', workflow)

    def test_release_runner_rejects_dirty_post_run_tree(self) -> None:
        with mock.patch.object(RELEASE_RUNNER, "_tracked_status", return_value=" M tui/Cargo.lock"):
            with self.assertRaisesRegex(ValueError, "tracked candidate bytes differ from HEAD"):
                RELEASE_RUNNER._tree_clean("after")

    def test_release_runner_rejects_commit_or_tree_drift(self) -> None:
        original_commit = "a" * 40
        original_tree = "b" * 40
        with mock.patch.object(RELEASE_RUNNER, "_identity", return_value=("c" * 40, original_tree)):
            with self.assertRaisesRegex(ValueError, "candidate HEAD changed"):
                RELEASE_RUNNER._identity_unchanged(original_commit, original_tree, original_commit)
        with mock.patch.object(RELEASE_RUNNER, "_identity", return_value=(original_commit, "d" * 40)):
            with self.assertRaisesRegex(ValueError, "candidate identity changed"):
                RELEASE_RUNNER._identity_unchanged(original_commit, original_tree, original_commit)

    def test_extension_hardening_workflow_verifies_historical_pr60_after_version_bump(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "extension-hardening.yml").read_text(encoding="utf-8")
        self.assertIn("git worktree add --detach", workflow)
        self.assertIn("80cda46e614f44b47861471cb329e29a348cab43", workflow)
        self.assertIn("historical-pr60-merge", workflow)

    def test_v2_0_workflow_verifies_frozen_release_commit_in_detached_worktree(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-hardening.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("fetch-tags: true", workflow)
        self.assertIn("git worktree add --detach", workflow)
        self.assertIn("cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a", workflow)
        self.assertIn('cd "$HARDENING_ROOT"', workflow)
        self.assertIn('--expect-commit "$HARDENING_EXPECT"', workflow)
        self.assertNotIn('--expect-commit "$GITHUB_SHA"', workflow)


if __name__ == "__main__":
    unittest.main()
