from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from nexus_runtime import PROTOCOL_VERSION, RUNTIME_VERSION

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertEqual(candidate["base_feature_pr"], 50)
        self.assertEqual(candidate["base_feature_merge"], "1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b")
        self.assertEqual(candidate["candidate_pr"], 51)
        self.assertIn("PR #50 — The BBS Wall — MERGED", sequence)
        self.assertIn("PR #52 — Lean 4 Formal Verification", sequence)
        self.assertIn("PR #53 — Formalization + Reproducibility + Zenodo Publication", sequence)
        self.assertIn("LEAN 4 FORMAL VERIFICATION - PR #52", roadmap)
        self.assertIn("ZENODO - PR #53", roadmap)

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
        self.assertNotIn("remote providers other than xAI", threat)
        self.assertNotIn("when the executable protocol is implemented", claims)
        self.assertNotIn("version: 2.0.0-alpha0", citation)
        self.assertNotIn("documentation-only", citation)
        self.assertIn("version: 2.0.0", citation)
        self.assertIn("## BBS Wall", architecture)
        self.assertIn("### T54 — Release paperwork declares stable without the tested stable head", threat)

    def test_release_matrix_is_final_rc_scoped_through_wall_and_covers_contract(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["milestone"], "PR #51")
        self.assertEqual(matrix["profile"], "final_release_candidate")
        self.assertEqual(matrix["scope_through_pr"], 50)
        self.assertEqual(matrix["target_version"], "2.0.0")
        self.assertFalse(matrix["stable_release"])
        release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
        self.assertIn("test_wall*.py", release_gate["patterns"])
        self.assertIn("test_release_candidate.py", release_gate["patterns"])
        self.assertEqual(set(matrix["external_audit_closure"]["finding_ids"]), {f"R{i}" for i in range(1, 13)})

    def test_release_docs_and_wall_claims_are_coupled(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        ai = json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))
        notes = (ROOT / "docs" / "RELEASE_NOTES_2.0.0.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("status:          release candidate", readme)
        self.assertEqual(ai["bbs_wall"]["evidence_effect"], "none")
        self.assertEqual(ai["bbs_wall"]["authority_effect"], "none")
        self.assertIn("social memory", notes)
        self.assertIn("no unresolved substantive release-blocking review thread", checklist)


if __name__ == "__main__":
    unittest.main()
