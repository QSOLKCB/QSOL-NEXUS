from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tomllib
import unittest
from unittest import mock

from nexus_runtime import PROTOCOL_VERSION, RUNTIME_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _load_extension_hardener():
    path = ROOT / "tools" / "nexus_extension_hardening.py"
    spec = importlib.util.spec_from_file_location("nexus_extension_hardening_test_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load extension hardening runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXTENSION_HARDENER = _load_extension_hardener()


class NEXUS20ReleaseCandidateTests(unittest.TestCase):
    def test_intended_stable_version_is_aligned_without_self_declaring_release(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))

        self.assertEqual(PROTOCOL_VERSION, "nexus/0.14")
        self.assertEqual(RUNTIME_VERSION, "2.0.0")
        self.assertEqual(pyproject["project"]["version"], "2.0.0")
        self.assertEqual(cargo["package"]["version"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["runtime"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["python_package"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["rust_tui"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["release_posture"], "release_candidate")
        self.assertFalse(manifest["release_identity"]["stable_2_0"])
        self.assertFalse(manifest["stable_2_0"]["declared"])
        self.assertFalse(candidate["stable_release"])
        self.assertFalse(matrix["stable_release"])
        self.assertEqual(candidate["target_tag"], "v2.0.0")

    def test_release_candidate_is_exactly_post_wall_and_preserves_future_formalization_sequence(self) -> None:
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        sequence = (ROOT / "docs" / "RELEASE_SEQUENCE.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertEqual(candidate["feature_surface_through_pr"], 50)
        self.assertEqual(candidate["scope_through_pr"], 51)
        self.assertEqual(candidate["base_feature_merge"], "1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b")
        self.assertEqual(candidate["candidate_pr"], 52)
        self.assertIn("PR #50 — The BBS Wall — MERGED", sequence)
        self.assertIn("PR #53 — Lean 4 Formal Verification", sequence)
        self.assertIn("PR #54 — Formalization + Reproducibility + Zenodo Publication", sequence)
        self.assertIn("## PR #53 — Lean 4 Formal Verification", roadmap)
        self.assertIn("## PR #54 — Formalization + Reproducibility + Zenodo Publication", roadmap)
        self.assertIn("LEAN 4 FORMAL VERIFICATION - PR #53", roadmap)
        self.assertIn("ZENODO - PR #54", roadmap)

    def test_canonical_docs_do_not_retain_known_alpha_architecture_fossils(self) -> None:
        architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        threat = (ROOT / "THREAT_MODEL.md").read_text(encoding="utf-8")
        claims = (ROOT / "CLAIMS.md").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

        self.assertNotIn("future RUST TUI", architecture)
        self.assertNotIn("Rust CLI/TUI (future)", architecture)
        self.assertNotIn("xAI is the first fixed-destination remote adapter", architecture)
        self.assertNotIn("xAI is the first admitted remote adapter", security)
        self.assertNotIn("other remote providers   not implemented", security)
        self.assertIn("api.openai.com", security)
        self.assertIn("api.anthropic.com", security)
        self.assertIn("generativelanguage.googleapis.com", security)
        self.assertIn("api.groq.com", security)
        self.assertIn("api.together.ai", security)
        self.assertNotIn("remote providers other than xAI", threat)
        self.assertNotIn("when the executable protocol is implemented", claims)
        self.assertNotIn("version: 2.0.0-alpha0", citation)
        self.assertNotIn("documentation-only", citation)
        self.assertIn("version: 2.0.0", citation)
        self.assertIn("## BBS Wall", architecture)
        self.assertIn("### T54 — Release paperwork declares stable without the tested stable head", threat)

    def test_release_matrix_is_final_rc_scoped_through_wall_and_covers_contract(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["milestone"], "PR #52")
        self.assertEqual(matrix["profile"], "final_release_candidate")
        self.assertEqual(matrix["scope_through_pr"], 51)
        self.assertEqual(matrix["target_version"], "2.0.0")
        self.assertFalse(matrix["stable_release"])
        release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
        self.assertIn("test_wall*.py", release_gate["patterns"])
        self.assertIn("test_release_candidate.py", release_gate["patterns"])
        self.assertIn("test_release_upgrade_rehearsal.py", release_gate["patterns"])
        rehearsal_ids = {item["id"] for item in matrix["rehearsals"]}
        self.assertIn("representative_pre_beta_upgrade_ark_round_trip", rehearsal_ids)
        self.assertEqual(set(matrix["external_audit_closure"]["finding_ids"]), {f"R{i}" for i in range(1, 13)})

    def test_release_docs_and_wall_claims_are_coupled(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        ai = json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))
        notes = (ROOT / "docs" / "RELEASE_NOTES_2.0.0.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("status:          release candidate", readme)
        self.assertNotIn("broader instrument layer, persistent-world/migration hardening", readme)
        self.assertIn("exact merged #52 head after the complete release-candidate matrix", readme)
        self.assertEqual(ai["bbs_wall"]["evidence_effect"], "none")
        self.assertEqual(ai["bbs_wall"]["authority_effect"], "none")
        self.assertIn("social memory", notes)
        self.assertIn("no unresolved substantive release-blocking review thread", checklist)


class PostStableExtensionHardeningTests(unittest.TestCase):
    @staticmethod
    def _candidate() -> dict:
        return json.loads((ROOT / "release" / "post_stable_extension_candidate.json").read_text(encoding="utf-8"))

    @staticmethod
    def _matrix() -> dict:
        return json.loads((ROOT / "release" / "post_stable_extension_matrix.json").read_text(encoding="utf-8"))

    def test_frozen_publication_identity_is_exact_in_candidate_and_matrix(self) -> None:
        candidate = self._candidate()
        matrix = self._matrix()
        expected = EXTENSION_HARDENER.EXPECTED_STABLE_BASELINE
        self.assertEqual(candidate["stable_baseline"], expected)
        self.assertEqual(matrix["stable_baseline"], expected)
        EXTENSION_HARDENER._audit_candidate(candidate)
        EXTENSION_HARDENER._audit_matrix(matrix, candidate)

        for field, bad_value in (
            ("formalization_pr", 530),
            ("publication_pr", 540),
            ("publication_doi", "10.5281/zenodo.00000000"),
            ("immutable", False),
        ):
            with self.subTest(field=field):
                bad_candidate = copy.deepcopy(candidate)
                bad_candidate["stable_baseline"][field] = bad_value
                with self.assertRaisesRegex(ValueError, "frozen stable/publication identity"):
                    EXTENSION_HARDENER._audit_candidate(bad_candidate)

                bad_matrix = copy.deepcopy(matrix)
                bad_matrix["stable_baseline"][field] = bad_value
                with self.assertRaisesRegex(ValueError, "frozen stable/publication identity"):
                    EXTENSION_HARDENER._audit_matrix(bad_matrix, candidate)

    def test_post_run_tracked_mutation_fails_closed(self) -> None:
        with mock.patch.object(EXTENSION_HARDENER, "_tracked_status", return_value=" M tui/Cargo.lock"):
            with self.assertRaisesRegex(ValueError, "mutated tracked candidate bytes"):
                EXTENSION_HARDENER._candidate_tree_unchanged()

    def test_post_run_head_or_tree_change_fails_closed(self) -> None:
        initial_commit = "a" * 40
        initial_tree = "b" * 40

        def changed_head(*args: str) -> str:
            if args == ("rev-parse", "HEAD"):
                return "c" * 40
            if args == ("rev-parse", "HEAD^{tree}"):
                return initial_tree
            raise AssertionError(args)

        with mock.patch.object(EXTENSION_HARDENER, "_git", side_effect=changed_head):
            with self.assertRaisesRegex(ValueError, "HEAD changed during hardening"):
                EXTENSION_HARDENER._candidate_identity_unchanged(initial_commit, initial_tree, initial_commit)

        def changed_tree(*args: str) -> str:
            if args == ("rev-parse", "HEAD"):
                return initial_commit
            if args == ("rev-parse", "HEAD^{tree}"):
                return "d" * 40
            raise AssertionError(args)

        with mock.patch.object(EXTENSION_HARDENER, "_git", side_effect=changed_tree):
            with self.assertRaisesRegex(ValueError, "committed tree changed during hardening"):
                EXTENSION_HARDENER._candidate_identity_unchanged(initial_commit, initial_tree, initial_commit)

    def test_rust_hardening_is_lockfile_strict_and_post_run_checks_are_required(self) -> None:
        source = (ROOT / "tools" / "nexus_extension_hardening.py").read_text(encoding="utf-8")
        self.assertIn('"test",\n                "--locked",', source)
        matrix = self._matrix()
        release_gate = next(gate for gate in matrix["gates"] if gate["id"] == "release_composition")
        self.assertIn("candidate_tree_unchanged", release_gate["runner_checks"])
        self.assertIn("candidate_identity_unchanged", release_gate["runner_checks"])


if __name__ == "__main__":
    unittest.main()
