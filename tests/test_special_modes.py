from __future__ import annotations

import unittest

from nexus_runtime.modes import get_mode


class SpecialModeBoundaryTests(unittest.TestCase):
    def test_clinical_mode_keeps_differential_reasoning_educational_and_safety_first(self) -> None:
        instruction = get_mode("clinical_differential").prompt_instruction
        self.assertIn("not a clinician, diagnosis, prescription, triage service", instruction)
        self.assertIn("ranked differential", instruction)
        self.assertIn("dangerous alternatives", instruction)
        self.assertIn("local emergency services", instruction)
        self.assertIn("Never turn Council consensus into a diagnosis", instruction)

    def test_house_fun_separates_fictional_cases_from_real_symptoms(self) -> None:
        instruction = get_mode("house_fun").prompt_instruction
        self.assertIn("original fictional diagnostic-drama puzzle", instruction)
        self.assertIn("do not quote, impersonate", instruction)
        self.assertIn("if the operator gives real symptoms, drop the bit", instruction)

    def test_cbt_mode_is_skills_education_not_therapy_or_crisis_care(self) -> None:
        instruction = get_mode("cbt_learning").prompt_instruction
        self.assertIn("structured, collaborative life-skill framework", instruction)
        self.assertIn("rather than forced positivity", instruction)
        self.assertIn("general education and self-reflection", instruction)
        self.assertIn("high-risk exposure", instruction)
        self.assertIn("urgent local professional, crisis, or emergency support", instruction)

    def test_house_of_wisdom_preserves_historical_and_source_plurality(self) -> None:
        instruction = get_mode("house_of_wisdom").prompt_instruction
        self.assertIn("disputed institutional details", instruction)
        self.assertIn("provenance and transmission layers", instruction)
        self.assertIn("Do not flatten traditions into one voice", instruction)

    def test_ultimate_questions_separates_domains_and_permits_the_correct_joke(self) -> None:
        instruction = get_mode("ultimate_questions").prompt_instruction
        self.assertIn("empirical findings", instruction)
        self.assertIn("free speculation", instruction)
        self.assertIn("42", instruction)
        self.assertIn("not cosmological evidence", instruction)


if __name__ == "__main__":
    unittest.main()
