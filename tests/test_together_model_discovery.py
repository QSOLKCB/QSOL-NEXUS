from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import SecretMaterial
from nexus_runtime.schema_migration import (
    SchemaMigrationError,
    build_migration_plan,
    classify_version_change,
    verify_migration_plan,
)
from nexus_runtime.world_continuity import WorldContinuityError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_MIGRATION_TOOL = ROOT / "tools" / "schema_migration.py"


class _FakeResponse:
    def __init__(self, value: object) -> None:
        self.raw = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, maximum: int = -1) -> bytes:
        return self.raw


class _FakeOpener:
    def __init__(self, value: object) -> None:
        self.value = value
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _FakeResponse:
        self.requests.append(request)
        return _FakeResponse(self.value)


class TogetherModelDiscoveryTests(unittest.TestCase):
    def test_models_endpoint_accepts_documented_top_level_array(self) -> None:
        opener = _FakeOpener(
            [
                {
                    "id": "openai/gpt-oss-20b",
                    "object": "model",
                    "created": 1692896905,
                    "type": "chat",
                    "display_name": "GPT-OSS 20B",
                    "organization": "OpenAI",
                },
                {
                    "id": "Qwen/Qwen3-235B-A22B-Instruct-2507-tput",
                    "object": "model",
                    "created": 1692896906,
                    "type": "chat",
                    "display_name": "Qwen",
                    "organization": "Qwen",
                },
            ]
        )
        transport = ThirdPartyTransport(
            "together",
            SecretMaterial("fixture-together-key-DO-NOT-PRINT"),
            _opener=opener,
        )
        models = transport.list_language_models()
        self.assertEqual(
            [item["id"] for item in models],
            ["Qwen/Qwen3-235B-A22B-Instruct-2507-tput", "openai/gpt-oss-20b"],
        )
        self.assertEqual(models[1]["type"], "chat")
        self.assertEqual(models[1]["display_name"], "GPT-OSS 20B")
        self.assertEqual(opener.requests[0].full_url, "https://api.together.ai/v1/models")


class SchemaMigrationCodexReviewTests(unittest.TestCase):
    """PR #63 review regressions live in an existing file to preserve the frozen 83-file inventory."""

    def test_major_downgrades_fail_closed_before_migration_classification(self) -> None:
        cases = (
            ("schema", "example/2", "example/1", "SCHEMA_DOWNGRADE_UNSUPPORTED"),
            ("protocol", "nexus/2.0", "nexus/1.99", "PROTOCOL_DOWNGRADE_UNSUPPORTED"),
            ("runtime", "3.0.0", "2.99.99", "RUNTIME_DOWNGRADE_UNSUPPORTED"),
        )
        for kind, source, target, expected in cases:
            with self.subTest(kind=kind):
                result = classify_version_change(kind, source, target)
                self.assertEqual(result["classification"], expected)
                self.assertFalse(result["migration_required"])
                self.assertFalse(result["adapter_required"])

    def test_runtime_prerelease_requires_full_semver_identifier_rules(self) -> None:
        invalid = (
            "1.2.3-a..b",
            "1.2.3-.",
            "1.2.3-01",
            "1.2.3-alpha.01",
        )
        for identity in invalid:
            with self.subTest(identity=identity):
                with self.assertRaises(SchemaMigrationError):
                    classify_version_change("runtime", identity, "1.2.3")

    def test_runtime_prerelease_direction_uses_semver_precedence(self) -> None:
        forward = (
            ("2.0.0-alpha", "2.0.0-alpha.1"),
            ("2.0.0-alpha.9", "2.0.0-alpha.10"),
            ("2.0.0-alpha.10", "2.0.0-beta"),
            ("2.0.0-beta", "2.0.0"),
        )
        for source, target in forward:
            with self.subTest(source=source, target=target):
                result = classify_version_change("runtime", source, target)
                self.assertEqual(result["classification"], "RUNTIME_FORWARD_CHANGE_VALIDATOR_OWNED")
                self.assertFalse(result["migration_required"])

        downgrade = classify_version_change("runtime", "2.0.0", "2.0.0-alpha")
        self.assertEqual(downgrade["classification"], "RUNTIME_DOWNGRADE_UNSUPPORTED")
        self.assertFalse(downgrade["migration_required"])

    def test_classification_declares_zero_evidence_effect(self) -> None:
        result = classify_version_change("protocol", "nexus/0.14", "nexus/0.15")
        self.assertEqual(result["authority_effect"], "none")
        self.assertEqual(result["evidence_effect"], "none")

    def test_plan_verification_is_json_type_sensitive(self) -> None:
        plan = build_migration_plan("protocol", "nexus/0.14", "nexus/0.15")
        for field, replacement in (
            ("automatic_execution", 0),
            ("migration_required", 1),
            ("adapter_required", 1),
            ("in_place_rewrite", 0),
        ):
            with self.subTest(field=field):
                tampered = copy.deepcopy(plan)
                tampered[field] = replacement
                with self.assertRaises(SchemaMigrationError):
                    verify_migration_plan(tampered)

    def test_cli_argument_failures_are_canonical_json_without_usage_stderr(self) -> None:
        cases = (
            ("classify", "--kind", "schema", "--source", "example/1"),
            ("classify", "--kind", "bogus", "--source", "example/1", "--target", "example/2"),
        )
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(SCHEMA_MIGRATION_TOOL), *args],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                decoded = json.loads(result.stdout)
                self.assertEqual(decoded["status"], "error")
                self.assertEqual(decoded["error"]["code"], "schema_migration_invalid_arguments")
                self.assertEqual(
                    result.stdout,
                    json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
                )


class UserModeCodexReviewTests(unittest.TestCase):
    """PR #64 review regressions also reuse this file to keep the 83-file inventory frozen."""

    @staticmethod
    def _definition(**overrides: str) -> dict[str, str]:
        request = {
            "operation": "world.mode.define",
            "mode_id": "user:codex_review",
            "label": "Codex Review",
            "description": "Bounded review framing.",
            "prompt_instruction": "Keep the review explicit and non-authoritative.",
            "region_id": "observatory",
        }
        request.update(overrides)
        return request

    @staticmethod
    def _members() -> list[dict[str, str]]:
        return [
            {"member_id": "A", "model_id": "mock-a"},
            {"member_id": "B", "model_id": "mock-b"},
            {"member_id": "C", "model_id": "mock-c"},
        ]

    def test_redaction_expansion_is_rejected_before_definition_persistence(self) -> None:
        secret = "sk-" + "A" * 20
        raw_label = "L" * 71 + secret
        self.assertLessEqual(len(raw_label), 96)
        with tempfile.TemporaryDirectory() as directory:
            api = NexusAPI(world_root=directory)
            denied = api.handle(
                self._definition(mode_id="user:redaction_bound", label=raw_label)
            )
            self.assertEqual(denied["status"], "error")
            self.assertEqual(denied["error"]["code"], "user_mode_invalid")
            self.assertEqual(
                api.handle({"operation": "world.mode.policy"})["defined_user_modes"],
                0,
            )

            restarted = NexusAPI(world_root=directory)
            policy = restarted.handle({"operation": "world.mode.policy"})
            self.assertEqual(policy["status"], "ok")
            self.assertEqual(policy["defined_user_modes"], 0)
            self.assertEqual(restarted.handle({"operation": "world.modes"})["status"], "ok")

    def test_custom_mode_council_proceeding_uses_contextual_mode_resolver(self) -> None:
        api = NexusAPI()
        defined = api.handle(self._definition(mode_id="user:proceedings"))
        self.assertEqual(defined["status"], "ok")
        run = api.handle(
            {
                "operation": "council.run",
                "question": "Can this custom-mode proceeding be observed?",
                "mode": "user:proceedings",
                "members": self._members(),
            }
        )
        self.assertEqual(run["status"], "ok")
        view = api.handle(
            {
                "operation": "council.proceedings.view",
                "session_ref": run["session_ref"],
                "source_mode_id": "user:proceedings",
            }
        )
        self.assertEqual(view["status"], "ok")
        self.assertEqual(view["source_mode_id"], "user:proceedings")
        self.assertEqual(view["source_region_id"], "observatory")
        self.assertEqual(view["access_tier"], "public_gallery")

    def test_receipt_verify_keeps_post_lookup_continuity_failure_structured(self) -> None:
        api = NexusAPI()
        self.assertEqual(api.handle(self._definition(mode_id="user:continuity"))["status"], "ok")
        run = api.handle(
            {
                "operation": "council.run",
                "question": "Keep continuity failure inside the API boundary.",
                "mode": "user:continuity",
                "members": self._members(),
            }
        )
        self.assertEqual(run["status"], "ok")
        with patch.object(
            api.user_modes,
            "receipt_definition_ref",
            side_effect=WorldContinuityError(
                "world_continuity_quorum_unavailable",
                "fixture continuity quorum unavailable",
            ),
        ):
            checked = api.handle(
                {"operation": "receipt.verify", "receipt_ref": run["receipt_ref"]}
            )
        self.assertEqual(checked["status"], "error")
        self.assertEqual(checked["error"]["code"], "world_continuity_quorum_unavailable")
        self.assertIn("continuity quorum unavailable", checked["error"]["message"])


if __name__ == "__main__":
    unittest.main()
