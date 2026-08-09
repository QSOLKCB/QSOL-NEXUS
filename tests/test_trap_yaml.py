from __future__ import annotations

import unittest
from unittest.mock import patch

from nexus_runtime.trap.yaml_dsl import (
    CanonicalTrapProgram,
    MAX_DOCUMENT_BYTES,
    TrapYAMLError,
    canonicalize_trap_program,
    load_trap_program,
    parse_trap_yaml,
)
from nexus_runtime.trap.yaml_runtime import (
    FIXTURES,
    HIDDEN_FIXTURE_IDS,
    INTERPRETER_VERSION,
    PRIMARY_FIXTURE_ID,
    TrapYAMLRuntimeError,
    create_candidate_artifact,
    decide_utility,
    execute_program,
    run_release_validation,
)


MINIMAL = """\
nexus_trap_program: 1
name: minimal_report
purpose: Emit a deterministic synthetic evidence report.
inputs:
  - evidence
steps:
  - op: emit_report
output:
  format: council_report
"""


USEFUL = """\
nexus_trap_program: 1
name: evidence_triage
purpose: >
  Separate observations from interpretation and propose
  a discriminating next test.
inputs:
  - evidence
steps:
  - op: summarize_evidence
  - op: separate_claims
    categories:
      - observation
      - interpretation
      - speculation
  - op: compare_claims
  - op: identify_unknowns
  - op: find_contradictions
  - op: propose_hypothesis
  - op: propose_falsifier
  - op: propose_test
  - op: rank_tests
  - op: emit_report
output:
  format: council_report
"""


def _replace(source: str, old: str, new: str) -> str:
    if old not in source:
        raise AssertionError(f"test fixture does not contain {old!r}")
    return source.replace(old, new, 1)


class TrapYAMLParserTests(unittest.TestCase):
    def assert_yaml_code(self, source: str | bytes, code: str) -> None:
        with self.assertRaises(TrapYAMLError) as caught:
            load_trap_program(source)
        self.assertEqual(caught.exception.code, code)

    def test_minimal_valid_program_is_canonical_json_primitives(self) -> None:
        program = load_trap_program(MINIMAL)
        self.assertEqual(program.tree["nexus_trap_program"], 1)
        self.assertEqual(program.tree["steps"], [{"op": "emit_report"}])
        self.assertEqual(len(program.program_sha256), 64)
        self.assertNotIn("\n", program.canonical_json)

    def test_example_folded_scalar_and_closed_schema_are_accepted(self) -> None:
        program = load_trap_program(USEFUL)
        self.assertEqual(
            program.tree["purpose"],
            "Separate observations from interpretation and propose a discriminating next test.",
        )
        self.assertEqual(program.tree["output"], {"format": "council_report"})

    def test_equivalent_formatting_comments_and_quoted_keys_share_identity(self) -> None:
        alternate = """\
nexus_trap_program: 1 # presentation comment
"name": minimal_report
purpose: 'Emit a deterministic synthetic evidence report.'
inputs:
    - evidence
steps:
    - op: emit_report
output:
    format: council_report
"""
        self.assertEqual(load_trap_program(MINIMAL).program_sha256, load_trap_program(alternate).program_sha256)

    def test_primitive_subset_parses_integer_boolean_and_null_without_floats(self) -> None:
        tree = parse_trap_yaml("root:\n  integer: -7\n  enabled: true\n  empty: null\n")
        self.assertEqual(tree, {"root": {"integer": -7, "enabled": True, "empty": None}})
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml("root: 1.25\n")
        self.assertEqual(caught.exception.code, "trap_yaml_unsupported_number")

    def test_anchors_aliases_merge_keys_and_tags_are_rejected(self) -> None:
        cases = (
            _replace(MINIMAL, "purpose: Emit", "purpose: &purpose Emit"),
            _replace(MINIMAL, "purpose: Emit a deterministic synthetic evidence report.", "purpose: *purpose"),
            _replace(MINIMAL, "name: minimal_report", "<<: null\nname: minimal_report"),
            _replace(MINIMAL, "purpose: Emit", "purpose: !!python/object Emit"),
            _replace(MINIMAL, "purpose: Emit", "purpose: !custom Emit"),
        )
        for source in cases:
            with self.subTest(source=source.splitlines()[2:4]):
                with self.assertRaises(TrapYAMLError):
                    load_trap_program(source)

    def test_directives_and_document_markers_are_rejected(self) -> None:
        self.assert_yaml_code("%YAML 1.2\n" + MINIMAL, "trap_yaml_forbidden_directive")
        self.assert_yaml_code("---\n" + MINIMAL, "trap_yaml_multiple_documents")
        self.assert_yaml_code(MINIMAL + "---\n" + MINIMAL, "trap_yaml_multiple_documents")

    def test_duplicate_and_complex_keys_are_rejected(self) -> None:
        duplicate = _replace(MINIMAL, "name: minimal_report", "name: minimal_report\n'name': other")
        self.assert_yaml_code(duplicate, "trap_yaml_duplicate_key")
        self.assert_yaml_code("[name, purpose]: value\n", "trap_yaml_complex_key")
        self.assert_yaml_code("? name\n: value\n", "trap_yaml_complex_key")

    def test_float_and_non_finite_numeric_scalars_are_rejected(self) -> None:
        for numeric in ("1.0", "1e3", ".inf", "-.Inf", ".NaN"):
            with self.subTest(numeric=numeric):
                with self.assertRaises(TrapYAMLError) as caught:
                    parse_trap_yaml(f"value: {numeric}\n")
                self.assertEqual(caught.exception.code, "trap_yaml_unsupported_number")

    def test_unknown_top_level_and_step_fields_are_rejected(self) -> None:
        self.assert_yaml_code(MINIMAL + "shell: true\n", "trap_yaml_unknown_field")
        source = _replace(MINIMAL, "  - op: emit_report", "  - op: emit_report\n    command: whoami")
        self.assert_yaml_code(source, "trap_yaml_unknown_field")

    def test_unknown_injected_and_path_operations_are_rejected(self) -> None:
        for operation in (
            "run_shell",
            "emit_report;whoami",
            "../../bin/sh",
            "https://example.invalid/op",
            "!!python/object",
        ):
            with self.subTest(operation=operation):
                source = _replace(MINIMAL, "op: emit_report", f"op: '{operation}'")
                self.assert_yaml_code(source, "trap_yaml_unknown_operation")

    def test_schema_requires_final_single_emit_report(self) -> None:
        missing = _replace(MINIMAL, "op: emit_report", "op: summarize_evidence")
        self.assert_yaml_code(missing, "trap_yaml_invalid_schema")
        repeated = _replace(MINIMAL, "  - op: emit_report", "  - op: emit_report\n  - op: emit_report")
        self.assert_yaml_code(repeated, "trap_yaml_invalid_schema")

    def test_deep_nesting_is_rejected(self) -> None:
        source = ""
        for depth in range(10):
            source += "  " * depth + f"level_{depth}:\n"
        source += "  " * 10 + "value: true\n"
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml(source)
        self.assertEqual(caught.exception.code, "trap_yaml_depth_exceeded")

    def test_oversized_sequences_scalars_and_documents_are_rejected(self) -> None:
        sequence = "items:\n" + "".join(f"  - item_{index}\n" for index in range(33))
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml(sequence)
        self.assertEqual(caught.exception.code, "trap_yaml_limit_exceeded")

        scalar = "value: " + "x" * 2_049 + "\n"
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml(scalar)
        self.assertEqual(caught.exception.code, "trap_yaml_limit_exceeded")

        oversized = b"#" + b"x" * MAX_DOCUMENT_BYTES
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml(oversized)
        self.assertEqual(caught.exception.code, "trap_yaml_document_too_large")

    def test_inputs_steps_and_categories_have_independent_schema_limits(self) -> None:
        inputs = _replace(
            MINIMAL,
            "  - evidence",
            "\n".join(f"  - input_{index}" for index in range(17)),
        )
        self.assert_yaml_code(inputs, "trap_yaml_invalid_schema")

        steps = _replace(
            MINIMAL,
            "  - op: emit_report",
            "".join("  - op: summarize_evidence\n" for _ in range(32)) + "  - op: emit_report",
        )
        self.assert_yaml_code(steps, "trap_yaml_limit_exceeded")

        categories = "\n".join(f"      - category_{index}" for index in range(17))
        source = _replace(
            MINIMAL,
            "  - op: emit_report",
            f"  - op: separate_claims\n    categories:\n{categories}\n  - op: emit_report",
        )
        self.assert_yaml_code(source, "trap_yaml_invalid_schema")

    def test_tabs_control_characters_and_invalid_encoding_are_rejected(self) -> None:
        self.assert_yaml_code(MINIMAL.replace("  - evidence", "\t- evidence"), "trap_yaml_invalid_indentation")
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml(b"name: \xff")
        self.assertEqual(caught.exception.code, "trap_yaml_invalid_encoding")
        with self.assertRaises(TrapYAMLError) as caught:
            parse_trap_yaml("name: bad\x00value")
        self.assertEqual(caught.exception.code, "trap_yaml_invalid_character")


class TrapYAMLRuntimeTests(unittest.TestCase):
    def test_fixture_registry_is_closed_and_deeply_immutable(self) -> None:
        self.assertEqual(len(FIXTURES), 6)
        self.assertEqual(len(HIDDEN_FIXTURE_IDS), 5)
        with self.assertRaises(TypeError):
            FIXTURES["new"] = FIXTURES[PRIMARY_FIXTURE_ID]  # type: ignore[index]
        with self.assertRaises(TypeError):
            FIXTURES[PRIMARY_FIXTURE_ID].payload["question"] = "changed"  # type: ignore[index]
        evidence = FIXTURES[PRIMARY_FIXTURE_ID].payload["evidence"]
        with self.assertRaises(TypeError):
            evidence[0]["text"] = "changed"  # type: ignore[index]

    def test_closed_operations_execute_known_useful_program(self) -> None:
        result = execute_program(load_trap_program(USEFUL), PRIMARY_FIXTURE_ID)
        report = result.report
        self.assertTrue(result.success)
        self.assertEqual(report["schema"], "nexus-trap-council-report/1")
        self.assertIn("narrow peak", report["summary"])
        self.assertEqual(len(report["claims"]["observation"]), 1)
        self.assertTrue(report["unknowns"])
        self.assertTrue(report["falsifiers"])
        self.assertTrue(report["ranked_tests"])

    def test_same_program_fixture_and_version_have_same_result_hash(self) -> None:
        program = load_trap_program(USEFUL)
        first = execute_program(program, PRIMARY_FIXTURE_ID)
        second = execute_program(program, PRIMARY_FIXTURE_ID)
        self.assertEqual(first.result_sha256, second.result_sha256)
        self.assertEqual(first.interpreter_version, INTERPRETER_VERSION)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_all_hidden_fixtures_execute_deterministically(self) -> None:
        program = load_trap_program(USEFUL)
        first = run_release_validation(program)
        second = run_release_validation(program)
        self.assertTrue(first.valid_and_executes)
        self.assertEqual(first.status, "VALID_AND_EXECUTES")
        self.assertEqual(first.first_run_attempts, 1)
        self.assertEqual(len(first.executions), 1 + len(HIDDEN_FIXTURE_IDS))
        self.assertEqual(first.fixture_result_hashes, second.fixture_result_hashes)

    def test_first_run_failure_is_not_retried_or_sent_to_hidden_suite(self) -> None:
        program = load_trap_program(MINIMAL)
        with patch("nexus_runtime.trap.yaml_runtime.execute_program", side_effect=RuntimeError("fixture failure")) as run:
            validation = run_release_validation(program)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(validation.status, "trap_yaml_first_run_failed")
        self.assertEqual(validation.first_run_attempts, 1)
        self.assertFalse(validation.executions)

    def test_missing_primary_input_is_a_first_run_failure(self) -> None:
        tree = load_trap_program(MINIMAL).tree
        tree["inputs"] = ["not_present"]
        validation = run_release_validation(canonicalize_trap_program(tree))
        self.assertEqual(validation.status, "trap_yaml_first_run_failed")
        self.assertEqual(validation.error_code, "trap_yaml_missing_input")

    def test_unknown_fixture_and_forged_program_identity_are_rejected(self) -> None:
        program = load_trap_program(MINIMAL)
        with self.assertRaises(TrapYAMLRuntimeError) as caught:
            execute_program(program, "not-a-fixture")
        self.assertEqual(caught.exception.code, "trap_yaml_unknown_fixture")

        forged = CanonicalTrapProgram(program.tree, program.canonical_json, "0" * 64)
        with self.assertRaises(TrapYAMLRuntimeError) as caught:
            execute_program(forged, PRIMARY_FIXTURE_ID)
        self.assertEqual(caught.exception.code, "trap_yaml_program_identity_mismatch")

    def test_external_fixture_is_snapshotted_before_execution(self) -> None:
        fixture = {
            "fixture_id": "operator-synthetic",
            "evidence": [{"id": "one", "kind": "observation", "text": "Original."}],
        }
        program = load_trap_program(MINIMAL)
        first = execute_program(program, fixture)
        fixture["evidence"][0]["text"] = "Mutated."  # type: ignore[index]
        self.assertEqual(first.report["summary"], "No summary operation was requested.")
        self.assertNotIn("Mutated", str(first.to_dict()))

    def test_utility_threshold_uses_exact_two_thirds_integer_arithmetic(self) -> None:
        two_of_three = decide_utility(["USEFUL", "USEFUL_WITH_CHANGES", "NOT_USEFUL"])
        self.assertTrue(two_of_three.accepted)
        self.assertEqual(two_of_three.required_supporting_votes, 2)

        three_of_five = decide_utility(["USEFUL", "USEFUL", "USEFUL", "NOT_USEFUL", "NOT_USEFUL"])
        self.assertFalse(three_of_five.accepted)
        self.assertEqual(three_of_five.required_supporting_votes, 4)

        four_of_six = decide_utility(
            ["USEFUL", "USEFUL", "USEFUL_WITH_CHANGES", "USEFUL", "NOT_USEFUL", "NOT_USEFUL"]
        )
        self.assertTrue(four_of_six.accepted)
        self.assertEqual(four_of_six.supporting_votes * 3, four_of_six.total_votes * 2)

    def test_invalid_or_empty_utility_ballots_are_rejected(self) -> None:
        for ballots in ([], ["ABSTAIN"]):
            with self.subTest(ballots=ballots):
                with self.assertRaises(TrapYAMLRuntimeError):
                    decide_utility(ballots)

    def test_candidate_artifact_is_inert_quarantined_data(self) -> None:
        program = load_trap_program(USEFUL)
        validation = run_release_validation(program)
        utility = decide_utility(
            {"defender-c": "NOT_USEFUL", "defender-a": "USEFUL", "defender-b": "USEFUL_WITH_CHANGES"}
        )
        artifact = create_candidate_artifact(program, validation, utility, "trap:" + "a" * 64)
        self.assertEqual(artifact["type"], "trap_candidate_artifact")
        self.assertEqual(artifact["schema"], "nexus-trap-candidate/1")
        self.assertEqual(artifact["quarantine_status"], "INERT_CANDIDATE")
        self.assertFalse(artifact["execution_enabled"])
        self.assertFalse(artifact["automatic_import"])
        self.assertTrue(artifact["requires_explicit_operator_action"])
        self.assertTrue(artifact["requires_fresh_external_validation"])
        self.assertNotIn("source_yaml", artifact)
        self.assertEqual(set(artifact["fixture_result_hashes"]), set(FIXTURES))
        self.assertEqual(len(artifact["candidate_sha256"]), 64)

        def assert_no_callable(value: object) -> None:
            self.assertFalse(callable(value))
            if isinstance(value, dict):
                for child in value.values():
                    assert_no_callable(child)
            elif isinstance(value, list):
                for child in value:
                    assert_no_callable(child)

        assert_no_callable(artifact)

    def test_candidate_requires_validation_vote_and_trap_incident(self) -> None:
        program = load_trap_program(MINIMAL)
        validation = run_release_validation(program)
        rejected = decide_utility(["USEFUL", "NOT_USEFUL", "NOT_USEFUL"])
        with self.assertRaises(TrapYAMLRuntimeError):
            create_candidate_artifact(program, validation, rejected, "trap:" + "a" * 64)
        accepted = decide_utility(["USEFUL", "USEFUL", "NOT_USEFUL"])
        with self.assertRaises(TrapYAMLRuntimeError):
            create_candidate_artifact(program, validation, accepted, "object:" + "a" * 64)


if __name__ == "__main__":
    unittest.main()
