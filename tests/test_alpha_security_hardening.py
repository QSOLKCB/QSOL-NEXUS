from __future__ import annotations

from io import BytesIO, TextIOWrapper
import json
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.adapters.base import AdapterProtocolError
from nexus_runtime.adapters.ollama import (
    OLLAMA_MAX_RESPONSE_BYTES,
    OLLAMA_MAX_TIMEOUT_SECONDS,
    OllamaTransport,
)
from nexus_runtime.control_plane import (
    ALLOWED_EVIDENCE_STATES,
    MAX_EVIDENCE_REFS,
    MAX_JSONL_LINE_BYTES,
    MAX_REQUEST_DEPTH,
    MAX_REQUEST_KEY_CHARS,
    MAX_REQUEST_LIST_ITEMS,
    MAX_REQUEST_STRING_CHARS,
    MAX_REQUEST_TEXT_BYTES,
    RequestBudgetError,
    iter_bounded_jsonl_lines,
    validate_control_request,
)
from nexus_runtime.hardening import guard_model_text, sanitize_public_response
from nexus_runtime.local_roles import LocalRoleActor, LocalRoleRegistry
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.scrub import SecretScrubber
from nexus_runtime.types import CouncilMember


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        if limit < 0:
            return self.body
        return self.body[:limit]


class ControlPlaneBudgetTests(unittest.TestCase):
    def test_jsonl_reader_rejects_oversized_line_and_resynchronizes(self) -> None:
        raw = b"{" + b"x" * MAX_JSONL_LINE_BYTES + b"}\n" + b'{"operation":"system.health"}\n'
        stream = TextIOWrapper(BytesIO(raw), encoding="utf-8")
        records = list(iter_bounded_jsonl_lines(stream))
        self.assertIsNone(records[0].text)
        self.assertIn("byte limit", records[0].error or "")
        self.assertEqual(records[1].text, '{"operation":"system.health"}\n')

    def test_recursive_request_depth_is_bounded(self) -> None:
        value: object = "leaf"
        for _ in range(MAX_REQUEST_DEPTH + 1):
            value = {"x": value}
        with self.assertRaisesRegex(RequestBudgetError, "nesting depth"):
            validate_control_request({"operation": "world.create", "payload": value})

    def test_request_list_cardinality_is_bounded(self) -> None:
        with self.assertRaisesRegex(RequestBudgetError, "maximum item count"):
            validate_control_request(
                {"operation": "world.create", "payload": {"items": [0] * (MAX_REQUEST_LIST_ITEMS + 1)}}
            )

    def test_direct_api_request_has_aggregate_text_byte_budget(self) -> None:
        chunk = "x" * MAX_REQUEST_STRING_CHARS
        result = NexusAPI().handle(
            {
                "operation": "world.create",
                "object_type": "note",
                "payload": {"left": chunk, "right": chunk},
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid_request")
        self.assertIn("aggregate text byte limit", result["error"]["message"])

    def test_council_evidence_refs_are_capped_before_execution(self) -> None:
        result = NexusAPI().handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
                "evidence_refs": ["object:" + "0" * 64] * (MAX_EVIDENCE_REFS + 1),
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("at most", result["error"]["message"])

    def test_evidence_state_is_closed_to_machine_epistemic_vocabulary(self) -> None:
        self.assertIn("UNTESTED", ALLOWED_EVIDENCE_STATES)
        self.assertIn("verified", ALLOWED_EVIDENCE_STATES)
        validate_control_request(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
                "evidence_state": "verified",
            }
        )
        result = NexusAPI().handle(
            {
                "operation": "council.run",
                "question": "q",
                "members": [
                    {"member_id": "A", "model_id": "a"},
                    {"member_id": "B", "model_id": "b"},
                    {"member_id": "C", "model_id": "c"},
                ],
                "evidence_state": "TOTALLY_PROVEN_BECAUSE_I_SAID_SO",
            }
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("evidence_state must be one of", result["error"]["message"])

    def test_health_advertises_control_plane_limits(self) -> None:
        result = NexusAPI().handle({"operation": "system.health"})
        limits = result["control_plane_limits"]
        self.assertEqual(limits["schema"], "nexus-control-plane-limits/1")
        self.assertEqual(limits["max_jsonl_line_bytes"], MAX_JSONL_LINE_BYTES)
        self.assertEqual(limits["max_request_text_bytes"], MAX_REQUEST_TEXT_BYTES)
        self.assertEqual(limits["max_request_key_chars"], MAX_REQUEST_KEY_CHARS)
        self.assertEqual(limits["max_evidence_refs"], MAX_EVIDENCE_REFS)


class OutputBoundaryTests(unittest.TestCase):
    def test_scrubber_covers_groq_and_huggingface_shapes(self) -> None:
        groq = "gsk_" + "A" * 32
        hf = "hf_" + "B" * 32
        result = SecretScrubber().scrub(f"{groq} {hf}")
        self.assertNotIn(groq, result.text)
        self.assertNotIn(hf, result.text)
        self.assertIn("GROQ_API_KEY", result.text)
        self.assertIn("HUGGINGFACE_TOKEN", result.text)

    def test_actor_chat_scrubs_model_response_and_reports_response_events(self) -> None:
        secret = "gsk_" + "Z" * 32
        api = NexusAPI()
        with mock.patch(
            "nexus_runtime.mock.DeterministicMockActor.direct_message",
            return_value=f"accidental output {secret}",
        ):
            result = api.handle(
                {
                    "operation": "actor.chat",
                    "member": {"member_id": "A", "model_id": "mock-a", "adapter_id": "mock"},
                    "message": "hello",
                }
            )
        self.assertEqual(result["status"], "ok")
        self.assertNotIn(secret, json.dumps(result, sort_keys=True))
        self.assertTrue(result["response_secret_scrub"]["changed"])

    def test_local_output_guard_rejects_configured_or_shaped_secret_material(self) -> None:
        scrubber = SecretScrubber()
        with self.assertRaisesRegex(AdapterProtocolError, "configured credential"):
            guard_model_text(
                "echo local-secret-value",
                scrubber=scrubber,
                configured_secret="local-secret-value",
                label="local",
            )
        with self.assertRaisesRegex(AdapterProtocolError, "credential-shaped"):
            guard_model_text("echo " + "hf_" + "A" * 32, scrubber=scrubber, label="local")

    def test_post_admission_local_role_rejects_exact_credential_reflection(self) -> None:
        secret = "opaque-local-role-secret"
        registry = LocalRoleRegistry({"NEXUS_ROLE_SECRET": secret})
        registry.configure(
            "failsafe_relief",
            {
                "adapter_id": "openai_local",
                "endpoint": "http://127.0.0.1:8000",
                "model": "fixture",
                "credential_env": "NEXUS_ROLE_SECRET",
            },
        )
        wrapped = registry.wrap(
            "failsafe_relief",
            DeterministicMockActor(CouncilMember("A", "mock-a")),
        )
        self.assertIsInstance(wrapped, LocalRoleActor)
        assert isinstance(wrapped, LocalRoleActor)
        with mock.patch.object(
            wrapped.transport,
            "generate",
            return_value=f"accidental echo {secret}",
        ):
            response = wrapped.direct_message(
                "hello",
                mode_id="analytical",
                mode_instruction="keep claim boundaries explicit",
                geometry_region_id="observatory",
            )
        self.assertNotIn(secret, response)
        self.assertIn("received", response)
        self.assertEqual(wrapped.fallback_count, 1)

    def test_pathish_adapter_error_is_sanitized(self) -> None:
        result = sanitize_public_response(
            {
                "status": "error",
                "error": {
                    "code": "adapter_unavailable",
                    "message": "[Errno 13] Permission denied: '/home/operator/private/file'",
                },
            }
        )
        self.assertEqual(result["error"]["message"], "adapter or local storage operation is unavailable")
        self.assertNotIn("/home/operator", json.dumps(result))


class OllamaParityTests(unittest.TestCase):
    def test_ollama_requires_origin_only_url(self) -> None:
        for url in (
            "http://user:pass@127.0.0.1:11434",
            "http://127.0.0.1:11434/api",
            "http://127.0.0.1:11434/?query=1",
            "http://127.0.0.1:11434/#frag",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    OllamaTransport(base_url=url)

    def test_ollama_timeout_has_hard_upper_bound(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0"):
            OllamaTransport(timeout_seconds=OLLAMA_MAX_TIMEOUT_SECONDS + 1)

    def test_ollama_response_body_is_bounded(self) -> None:
        transport = OllamaTransport()
        body = b"x" * (OLLAMA_MAX_RESPONSE_BYTES + 1)
        transport._local_opener = mock.Mock()
        transport._local_opener.open.return_value = _Response(body)
        with self.assertRaisesRegex(AdapterProtocolError, "size limit"):
            transport.generate("model", "hello")


if __name__ == "__main__":
    unittest.main()
