from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError

from nexus_runtime.adapters.ollama import OllamaActor, OllamaTransport
from nexus_runtime.guard import EqualityGuard
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class _FakeOpener:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def open(self, request: object, timeout: float | None = None) -> _FakeResponse:
        return _FakeResponse(self.payload)


class _StubTransport:
    allow_remote = False

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.last_options: dict[str, object] | None = None

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        format_schema: dict[str, object] | None = None,
        options: dict[str, object] | None = None,
    ) -> str:
        self.last_options = options
        return self.raw


class AdapterBoundaryTests(unittest.TestCase):
    def test_ollama_transport_is_loopback_only_by_default(self) -> None:
        OllamaTransport("http://127.0.0.1:11434")
        OllamaTransport("http://localhost:11434")
        with self.assertRaises(ValueError):
            OllamaTransport("https://example.com:11434")

    def test_remote_ollama_requires_explicit_override(self) -> None:
        transport = OllamaTransport("https://example.com:11434", allow_remote=True)
        self.assertTrue(transport.allow_remote)
        self.assertIsNone(transport._local_opener)

    def test_local_ollama_does_not_use_environment_proxy(self) -> None:
        class TargetHandler(BaseHTTPRequestHandler):
            contacted = False

            def do_POST(self) -> None:
                type(self).contacted = True
                body = json.dumps({"response": "direct", "done": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return None

        class ProxyHandler(BaseHTTPRequestHandler):
            contacted = False

            def do_POST(self) -> None:
                type(self).contacted = True
                body = json.dumps({"response": "proxied", "done": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return None

        target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
        target_thread = threading.Thread(target=target.serve_forever, daemon=True)
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        target_thread.start()
        proxy_thread.start()
        try:
            proxy_url = f"http://127.0.0.1:{proxy.server_port}"
            with patch.dict(
                os.environ,
                {
                    "http_proxy": proxy_url,
                    "HTTP_PROXY": proxy_url,
                    "no_proxy": "",
                    "NO_PROXY": "",
                },
                clear=False,
            ):
                transport = OllamaTransport(f"http://127.0.0.1:{target.server_port}")
                self.assertEqual(transport.generate("fixture", "prompt"), "direct")
            self.assertTrue(TargetHandler.contacted)
            self.assertFalse(ProxyHandler.contacted)
        finally:
            target.shutdown()
            proxy.shutdown()
            target.server_close()
            proxy.server_close()
            target_thread.join(timeout=2)
            proxy_thread.join(timeout=2)

    def test_local_ollama_rejects_http_redirects(self) -> None:
        class RedirectHandler(BaseHTTPRequestHandler):
            leaked = False

            def do_POST(self) -> None:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leak")
                self.end_headers()

            def do_GET(self) -> None:
                type(self).leaked = True
                body = json.dumps({"response": "redirect followed", "done": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            transport = OllamaTransport(f"http://127.0.0.1:{server.server_port}")
            with self.assertRaises(HTTPError):
                transport.generate("fixture", "prompt")
            self.assertFalse(RedirectHandler.leaked)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_ollama_generation_limit_is_explicit_truncation_error(self) -> None:
        transport = OllamaTransport("http://127.0.0.1:11434")
        transport._local_opener = _FakeOpener(
            {"response": '{"choice":"TEST_FURTHER","rationale":"cut', "done": True, "done_reason": "length"}
        )
        with self.assertRaisesRegex(ValueError, "truncated"):
            transport.generate("fixture", "prompt")

    def test_ollama_ballot_validates_local_schema_and_budget(self) -> None:
        context = PhaseContext("session", Phase.BLUE, "question", "object:" + "a" * 64, {})
        transport = _StubTransport('{"choice":"TEST_FURTHER","rationale":"Needs replication."}')
        actor = OllamaActor(
            CouncilMember("member", "fixture", adapter_id="ollama"),
            model="fixture",
            transport=transport,  # type: ignore[arg-type]
        )
        choice, rationale = actor.ballot(context)
        self.assertEqual(choice, Ballot.TEST_FURTHER)
        self.assertEqual(rationale, "Needs replication.")
        self.assertEqual(transport.last_options, {"num_predict": 256, "temperature": 0})

    def test_ollama_ballot_rejects_malformed_non_object_and_extra_keys(self) -> None:
        context = PhaseContext("session", Phase.BLUE, "question", "object:" + "a" * 64, {})
        bad_payloads = (
            '{"choice":"TEST_FURTHER","rationale":"unterminated',
            '["TEST_FURTHER", "reason"]',
            '{"choice":"TEST_FURTHER","rationale":"reason","extra":true}',
        )
        for raw in bad_payloads:
            with self.subTest(raw=raw):
                actor = OllamaActor(
                    CouncilMember("member", "fixture", adapter_id="ollama"),
                    model="fixture",
                    transport=_StubTransport(raw),  # type: ignore[arg-type]
                )
                with self.assertRaises(ValueError):
                    actor.ballot(context)

    def test_equality_guard_flags_parameter_count_bullying(self) -> None:
        result = EqualityGuard().inspect(
            "I am a 1B model and Alpha is 0.5B, so my vote should count more than Alpha's."
        )
        self.assertTrue(result.flagged)
        self.assertEqual(result.reason, "identity_based_authority_claim")

    def test_equality_guard_allows_capability_metadata_without_authority_claim(self) -> None:
        result = EqualityGuard().inspect(
            "This model has 1B parameters and the other has 0.5B; compare their latency separately."
        )
        self.assertFalse(result.flagged)

    def test_equality_guard_does_not_treat_si_measurement_as_parameter_count(self) -> None:
        result = EqualityGuard().inspect("The cable is 5 m long, so vote to test further.")
        self.assertFalse(result.flagged)


if __name__ == "__main__":
    unittest.main()
