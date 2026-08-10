from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_readme_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_readme_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import machinery guard
    raise RuntimeError("cannot load README contract validator")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ReadmeManifestContractTests(unittest.TestCase):
    def test_repository_manifest_passes_strict_structure_validation(self) -> None:
        manifest = validator.validate_manifest()
        self.assertEqual(manifest["document_type"], "qsol-nexus-ai-manifest")
        self.assertIs(type(manifest["schema_version"]), int)

    def test_schema_version_rejects_bool_and_float_equal_to_one(self) -> None:
        manifest = validator.load_manifest()
        for bad_value in (True, 1.0):
            with self.subTest(value=bad_value):
                mutated = deepcopy(manifest)
                mutated["schema_version"] = bad_value
                with self.assertRaises(validator.ContractError):
                    validator.validate_manifest_structure(mutated)

    def test_required_sections_require_consumable_container_shapes(self) -> None:
        manifest = validator.load_manifest()
        for key, bad_value in (
            ("authority_invariants", None),
            ("security_boundaries", "not-an-object"),
            ("modification_contract", []),
        ):
            with self.subTest(key=key):
                mutated = deepcopy(manifest)
                mutated[key] = bad_value
                with self.assertRaises(validator.ContractError):
                    validator.validate_manifest_structure(mutated)

    def test_valid_exponent_that_decodes_to_infinity_is_rejected(self) -> None:
        with self.assertRaises(validator.ContractError):
            validator._parse_finite_float("1e999")

    def test_manifest_mode_is_independent_of_human_readme_coupling(self) -> None:
        with mock.patch.object(
            validator,
            "validate_human_coupling",
            side_effect=AssertionError("human coupling should not run"),
        ):
            self.assertEqual(validator.main(["--mode", "manifest"]), 0)


class ReadmeHumanCouplingTests(unittest.TestCase):
    def test_release_matching_uses_labeled_current_release_fields(self) -> None:
        manifest = validator.load_manifest()
        mutated = deepcopy(manifest)
        mutated["release_identity"]["runtime"] = "old-runtime"
        human = """# Example

## Current release posture

```text
protocol:        nexus/0.14
runtime:         current-runtime
Python package:  2.0.0a10.post3
Rust TUI:        2.0.0-alpha10.3
```

Historical note: old-runtime existed previously.

[README4AI.md](README4AI.md)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text(human, encoding="utf-8")
            with self.assertRaisesRegex(
                validator.ContractError, "README release identity mismatch"
            ):
                validator.validate_human_coupling(mutated, path)

    def test_current_repository_human_and_machine_release_fields_match(self) -> None:
        manifest = validator.validate_manifest()
        validator.validate_human_coupling(manifest)


class ReadmeSyncAuditTests(unittest.TestCase):
    def test_changed_files_does_not_filter_out_git_type_changes(self) -> None:
        completed = types.SimpleNamespace(stdout="README.md\n")
        with mock.patch.object(validator.subprocess, "run", return_value=completed) as run:
            files = validator.changed_files("a" * 40, "b" * 40)
        command = run.call_args.args[0]
        self.assertNotIn("--diff-filter=ACMRD", command)
        self.assertNotIn("--diff-filter", command)
        self.assertEqual(files, {"README.md"})

    def test_github_event_range_is_derived_for_pr_and_push(self) -> None:
        events = (
            (
                {
                    "pull_request": {
                        "base": {"sha": "a" * 40},
                        "head": {"sha": "b" * 40},
                    }
                },
                ("a" * 40, "b" * 40),
            ),
            (
                {"before": "c" * 40, "after": "d" * 40},
                ("c" * 40, "d" * 40),
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event.json"
            for event, expected in events:
                with self.subTest(event=event):
                    path.write_text(json.dumps(event), encoding="utf-8")
                    self.assertEqual(validator.event_commit_range(path), expected)


if __name__ == "__main__":
    unittest.main()
