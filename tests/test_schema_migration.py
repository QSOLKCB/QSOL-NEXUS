from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from nexus_runtime.schema_migration import (
    SCHEMA_MIGRATION_PLAN_SCHEMA,
    SCHEMA_MIGRATION_POLICY_ID,
    SchemaMigrationError,
    build_migration_plan,
    classify_version_change,
    schema_migration_policy_snapshot,
    verify_migration_plan,
)
from nexus_runtime.version import PROTOCOL_VERSION, RUNTIME_VERSION


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "schema_migration.py"


class SchemaMigrationPolicyTests(unittest.TestCase):
    def test_policy_separates_runtime_protocol_and_schema_identity(self) -> None:
        policy = schema_migration_policy_snapshot()
        self.assertEqual(policy["schema"], SCHEMA_MIGRATION_POLICY_ID)
        self.assertEqual(policy["current_runtime"], RUNTIME_VERSION)
        self.assertEqual(policy["current_protocol"], PROTOCOL_VERSION)
        self.assertEqual(policy["registered_adapters"], [])
        self.assertFalse(policy["automatic_execution"])
        self.assertEqual(policy["authority_effect"], "none")
        self.assertEqual(policy["evidence_effect"], "none")
        self.assertIn("SAME_MAJOR != AUTOMATIC_COMPATIBILITY", policy["boundaries"])
        self.assertIn("MIGRATION != REWRITE", policy["boundaries"])

    def test_exact_identity_is_only_generic_compatible_case(self) -> None:
        for kind, identity in (
            ("schema", "nexus-persistent-world-export/1"),
            ("protocol", PROTOCOL_VERSION),
            ("runtime", RUNTIME_VERSION),
        ):
            with self.subTest(kind=kind):
                result = classify_version_change(kind, identity, identity)
                self.assertEqual(result["classification"], "EXACT_IDENTITY")
                self.assertTrue(result["compatible_by_generic_policy"])
                self.assertFalse(result["migration_required"])
                self.assertFalse(result["automatic_execution"])

    def test_schema_major_change_requires_exact_reviewed_adapter(self) -> None:
        result = classify_version_change(
            "schema",
            "nexus-persistent-world-export/1",
            "nexus-persistent-world-export/2",
        )
        self.assertEqual(result["classification"], "SCHEMA_MAJOR_MIGRATION_REQUIRED")
        self.assertFalse(result["compatible_by_generic_policy"])
        self.assertTrue(result["migration_required"])
        self.assertTrue(result["adapter_required"])
        self.assertIsNone(result["registered_adapter"])

    def test_schema_family_change_is_not_laundered_as_migration(self) -> None:
        result = classify_version_change("schema", "family-a/1", "family-b/1")
        self.assertEqual(result["classification"], "SCHEMA_FAMILY_INCOMPATIBLE")
        self.assertFalse(result["migration_required"])
        self.assertFalse(result["compatible_by_generic_policy"])

    def test_protocol_minor_change_is_review_required_not_automatic_compatibility(self) -> None:
        forward = classify_version_change("protocol", "nexus/0.14", "nexus/0.15")
        self.assertEqual(forward["classification"], "PROTOCOL_MINOR_FORWARD_REVIEW_REQUIRED")
        self.assertFalse(forward["compatible_by_generic_policy"])
        self.assertTrue(forward["adapter_required"])

        backward = classify_version_change("protocol", "nexus/0.15", "nexus/0.14")
        self.assertEqual(backward["classification"], "PROTOCOL_DOWNGRADE_UNSUPPORTED")
        self.assertFalse(backward["migration_required"])

    def test_runtime_forward_change_does_not_claim_artifact_migration(self) -> None:
        result = classify_version_change("runtime", "2.1.0", "2.1.1")
        self.assertEqual(result["classification"], "RUNTIME_FORWARD_CHANGE_VALIDATOR_OWNED")
        self.assertFalse(result["compatible_by_generic_policy"])
        self.assertFalse(result["migration_required"])
        self.assertEqual(result["validator_precedence"], "subsystem_validator")

    def test_runtime_major_change_requires_review_without_generic_adapter(self) -> None:
        result = classify_version_change("runtime", "2.1.1", "3.0.0")
        self.assertEqual(result["classification"], "RUNTIME_MAJOR_REVIEW_REQUIRED")
        self.assertTrue(result["migration_required"])
        self.assertTrue(result["adapter_required"])
        self.assertIsNone(result["registered_adapter"])

    def test_malformed_and_ambiguous_identities_fail_closed(self) -> None:
        cases = (
            ("schema", "example/01", "example/1"),
            ("schema", "Example/1", "example/1"),
            ("protocol", "nexus/00.15", "nexus/0.15"),
            ("protocol", "other/0.15", "nexus/0.15"),
            ("runtime", "2.01.1", "2.1.1"),
            ("runtime", "v2.1.1", "2.1.1"),
        )
        for kind, source, target in cases:
            with self.subTest(kind=kind, source=source):
                with self.assertRaises(SchemaMigrationError):
                    classify_version_change(kind, source, target)

    def test_plan_is_deterministic_source_preserving_and_inert(self) -> None:
        source_ref = "object:" + "a" * 64
        first = build_migration_plan(
            "schema",
            "nexus-example/1",
            "nexus-example/2",
            source_ref=source_ref,
        )
        second = build_migration_plan(
            "schema",
            "nexus-example/1",
            "nexus-example/2",
            source_ref=source_ref,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], SCHEMA_MIGRATION_PLAN_SCHEMA)
        self.assertEqual(first["source_ref"], source_ref)
        self.assertEqual(first["source_preservation"], "required")
        self.assertFalse(first["in_place_rewrite"])
        self.assertFalse(first["automatic_execution"])
        self.assertEqual(first["authority_effect"], "none")
        self.assertEqual(first["evidence_effect"], "none")
        self.assertTrue(first["plan_ref"].startswith("schema-migration-plan:"))

    def test_plan_verification_recomputes_policy_and_rejects_tamper(self) -> None:
        plan = build_migration_plan("protocol", "nexus/0.14", "nexus/0.15")
        verified = verify_migration_plan(plan)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["plan_ref"], plan["plan_ref"])
        self.assertFalse(verified["automatic_execution"])

        tampered = copy.deepcopy(plan)
        tampered["compatible_by_generic_policy"] = True
        with self.assertRaises(SchemaMigrationError):
            verify_migration_plan(tampered)

    def test_source_ref_must_be_exact_content_address_shape(self) -> None:
        for invalid in ("object:../escape", "object:" + "A" * 64, "receipt:" + "a" * 64):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SchemaMigrationError):
                    build_migration_plan("schema", "nexus-example/1", "nexus-example/2", source_ref=invalid)


class SchemaMigrationCLITests(unittest.TestCase):
    def _run(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=ROOT,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_policy_and_plan_are_canonical_json(self) -> None:
        policy = self._run("policy")
        self.assertEqual(policy.returncode, 0, policy.stderr)
        decoded = json.loads(policy.stdout)
        self.assertEqual(decoded["schema"], SCHEMA_MIGRATION_POLICY_ID)
        self.assertEqual(policy.stdout, json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

        plan = self._run(
            "plan",
            "--kind",
            "schema",
            "--source",
            "nexus-example/1",
            "--target",
            "nexus-example/2",
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertTrue(json.loads(plan.stdout)["plan_ref"].startswith("schema-migration-plan:"))

    def test_cli_verify_rejects_duplicate_keys_and_never_executes(self) -> None:
        duplicate = '{"schema":"x","schema":"y"}'
        result = self._run("verify", stdin=duplicate)
        self.assertEqual(result.returncode, 2)
        decoded = json.loads(result.stdout)
        self.assertEqual(decoded["status"], "error")
        self.assertIn("duplicate JSON key", decoded["error"]["message"])


if __name__ == "__main__":
    unittest.main()
