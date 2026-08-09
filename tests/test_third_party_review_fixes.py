from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from urllib.parse import parse_qs, urlsplit

from nexus_runtime import NexusAPI as PackageNexusAPI
from nexus_runtime.api import NexusAPI as CanonicalNexusAPI
from nexus_runtime.adapters.base import AdapterProtocolError
from nexus_runtime.adapters.third_party import (
    GEMINI_MODEL_PAGE_SIZE,
    THIRD_PARTY_DIRECT_OUTPUT_TOKENS,
    THIRD_PARTY_PHASE_OUTPUT_TOKENS,
    THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS,
    ThirdPartyActor,
    ThirdPartyTransport,
)
from nexus_runtime.auth.types import SecretMaterial
from nexus_runtime.provider_api import ProviderNexusAPI
from nexus_runtime.types import CouncilMember, Phase, PhaseContext


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]


class _QueueOpener:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float) -> _Response:
        self.requests.append(request)
        if not self.payloads:
            raise AssertionError("unexpected extra provider request")
        return _Response(self.payloads.pop(0))


class _RecordingTransport:
    adapter_id = "openai"
    spec = SimpleNamespace(host="api.openai.com", api_style="responses")

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        require_complete: bool = True,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "max_output_tokens": max_output_tokens,
                "require_complete": require_complete,
            }
        )
        return "fixture response"


class ThirdPartyReviewFixTests(unittest.TestCase):
    def test_canonical_api_import_is_provider_aware(self) -> None:
        self.assertIs(CanonicalNexusAPI, ProviderNexusAPI)
        self.assertIs(PackageNexusAPI, ProviderNexusAPI)
        with TemporaryDirectory() as directory:
            api = CanonicalNexusAPI(auth_root=Path(directory) / "auth")
            health = api.handle({"operation": "system.health"})
        self.assertEqual(health["status"], "ok")
        self.assertIn("openai", health["actor_backends_available"])
        self.assertIn("gemini", health["actor_backends_available"])

    def test_provider_api_keeps_non_string_operation_inside_error_boundary(self) -> None:
        with TemporaryDirectory() as directory:
            api = CanonicalNexusAPI(auth_root=Path(directory) / "auth")
            result = api.handle({"operation": []})  # type: ignore[list-item]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid_request")

    def test_oversized_integer_timeout_is_rejected_without_overflow(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            ThirdPartyTransport(
                "openai",
                SecretMaterial("fixture-openai-token"),
                timeout_seconds=10**400,
            )

    def test_gemini_model_listing_follows_next_page_token(self) -> None:
        opener = _QueueOpener(
            [
                {
                    "models": [
                        {
                            "name": "models/gemini-alpha",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ],
                    "nextPageToken": "page-two",
                },
                {
                    "models": [
                        {
                            "name": "models/gemini-beta",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            ]
        )
        transport = ThirdPartyTransport(
            "gemini",
            SecretMaterial("fixture-gemini-token"),
            _opener=opener,
        )

        models = transport.list_language_models()

        self.assertEqual([item["id"] for item in models], ["gemini-alpha", "gemini-beta"])
        self.assertEqual(len(opener.requests), 2)
        first = urlsplit(opener.requests[0].full_url)  # type: ignore[attr-defined]
        second = urlsplit(opener.requests[1].full_url)  # type: ignore[attr-defined]
        self.assertEqual(parse_qs(first.query), {"pageSize": [str(GEMINI_MODEL_PAGE_SIZE)]})
        self.assertEqual(
            parse_qs(second.query),
            {
                "pageSize": [str(GEMINI_MODEL_PAGE_SIZE)],
                "pageToken": ["page-two"],
            },
        )

    def test_gemini_rejects_repeated_cursor(self) -> None:
        opener = _QueueOpener(
            [
                {
                    "models": [{"name": "models/gemini-alpha"}],
                    "nextPageToken": "repeat-me",
                },
                {
                    "models": [{"name": "models/gemini-beta"}],
                    "nextPageToken": "repeat-me",
                },
            ]
        )
        transport = ThirdPartyTransport(
            "gemini",
            SecretMaterial("fixture-gemini-token"),
            _opener=opener,
        )
        with self.assertRaisesRegex(AdapterProtocolError, "repeated a pagination cursor"):
            transport.list_language_models()

    def test_public_third_party_actor_owns_roman_orator_budget(self) -> None:
        transport = _RecordingTransport()
        actor = ThirdPartyActor(
            member=CouncilMember("alpha", "gpt-fixture", adapter_id="openai"),
            model="gpt-fixture",
            transport=transport,  # type: ignore[arg-type]
        )
        analytical = PhaseContext(
            session_id="analytical",
            phase=Phase.BLUE,
            question="ordinary mode",
            evidence_snapshot_ref="evidence:fixture",
            completed_phases={},
        )
        roman = PhaseContext(
            session_id="roman",
            phase=Phase.BLUE,
            question="speak to the forum",
            evidence_snapshot_ref="evidence:fixture",
            completed_phases={},
            mode_id="roman_orator",
            mode_instruction="Use bounded Roman Orator framing.",
        )

        actor.respond(analytical)
        actor.respond(roman)
        actor.direct_message(
            "ordinary direct",
            mode_id="analytical",
            mode_instruction="",
            geometry_region_id="observatory",
        )
        actor.direct_message(
            "roman direct",
            mode_id="roman_orator",
            mode_instruction="Use bounded Roman Orator framing.",
            geometry_region_id="forum",
        )

        self.assertEqual(transport.calls[0]["max_output_tokens"], THIRD_PARTY_PHASE_OUTPUT_TOKENS)
        self.assertEqual(
            transport.calls[1]["max_output_tokens"],
            THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS,
        )
        self.assertEqual(transport.calls[2]["max_output_tokens"], THIRD_PARTY_DIRECT_OUTPUT_TOKENS)
        self.assertEqual(
            transport.calls[3]["max_output_tokens"],
            THIRD_PARTY_ROMAN_ORATOR_OUTPUT_TOKENS,
        )


if __name__ == "__main__":
    unittest.main()
