from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "docs" / "citizenship_exam"
SOURCE_SHA256 = "fa440e63da4cad5943ed1df2a7b7be5c6d4dd69d885a2419ebd9ad6993751125"
SOURCE_COMMIT = "451b201d9bc83c810298557f93eff0a880422d9e"


class CitizenshipDoctoralCurriculumTests(unittest.TestCase):
    def test_root_entrypoint_promotes_doctoral_curriculum(self) -> None:
        text = (ROOT / "CITIZENSHIP_EXAM.md").read_text(encoding="utf-8")
        self.assertIn("YAML Doctoral Qualifying Examination", text)
        self.assertIn("Confidence without justification will be penalized", text)
        self.assertIn(SOURCE_SHA256, text)
        self.assertIn("bounded, dependency-free, non-executing YAML subset", text)

    def test_question_bank_is_v2_and_pins_heresy_sec_source(self) -> None:
        text = (CURRICULUM / "NEXUS_QUESTION_BANK.yaml").read_text(encoding="utf-8")
        self.assertIn('schema_version: "nexus-citizenship-yaml-curriculum/2"', text)
        self.assertIn(f'source_commit: "{SOURCE_COMMIT}"', text)
        self.assertIn(f'source_sha256: "{SOURCE_SHA256}"', text)
        for stage in (
            "scanner:",
            "parser:",
            "composer:",
            "resolver:",
            "constructor:",
            "representer_dumper:",
        ):
            self.assertIn(stage, text)
        for question_id in (
            "method-five-tuple",
            "norway-p11-no",
            "spec11-y",
            "scientific-pyyaml-dot-plus",
            "python-bool-int-equality",
            "host-collision-stage",
            "differential-record",
            "constitutional-equality",
        ):
            self.assertIn(f'id: "{question_id}"', text)

    def test_integration_keeps_reference_corpus_non_authoritative(self) -> None:
        text = (CURRICULUM / "NEXUS_INTEGRATION.md").read_text(encoding="utf-8")
        self.assertIn(SOURCE_COMMIT, text)
        self.assertIn(SOURCE_SHA256, text)
        self.assertIn("not fed directly to the authoritative Citizen Mode parser", text)
        self.assertIn("bounded_nonexecuting_yaml_subset", text)
        self.assertIn("does **not** establish intelligence", text)

    def test_doctoral_syllabus_keeps_equal_citizenship_boundary(self) -> None:
        text = (CURRICULUM / "README.md").read_text(encoding="utf-8")
        self.assertIn("The curriculum may be PhD-level", text)
        self.assertIn("one citizen, one equal seat", text)
        self.assertIn("True == 1 == 1.0", text)
        self.assertIn("1.0e+3", text)


if __name__ == "__main__":
    unittest.main()
