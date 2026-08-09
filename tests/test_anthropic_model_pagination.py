from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlsplit

from nexus_runtime.adapters.base import AdapterProtocolError
from nexus_runtime.adapters.third_party import (
    ANTHROPIC_MODEL_PAGE_LIMIT,
    ThirdPartyTransport,
)
from nexus_runtime.auth.types import SecretMaterial


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
            raise AssertionError("unexpected extra Anthropic model-list request")
        return _Response(self.payloads.pop(0))


class AnthropicModelPaginationTests(unittest.TestCase):
    def transport(self, payloads: list[dict[str, object]]) -> tuple[ThirdPartyTransport, _QueueOpener]:
        opener = _QueueOpener(payloads)
        transport = ThirdPartyTransport(
            "anthropic",
            SecretMaterial("fixture-anthropic-token"),
            _opener=opener,
        )
        return transport, opener

    def test_follows_has_more_and_last_id_until_complete(self) -> None:
        transport, opener = self.transport(
            [
                {
                    "data": [
                        {"id": "claude-alpha", "display_name": "Claude Alpha"},
                    ],
                    "has_more": True,
                    "last_id": "claude-alpha",
                },
                {
                    "data": [
                        {"id": "claude-beta", "display_name": "Claude Beta"},
                    ],
                    "has_more": False,
                    "last_id": "claude-beta",
                },
            ]
        )

        models = transport.list_language_models()

        self.assertEqual([item["id"] for item in models], ["claude-alpha", "claude-beta"])
        self.assertEqual(len(opener.requests), 2)

        first_url = opener.requests[0].full_url  # type: ignore[attr-defined]
        first = urlsplit(first_url)
        self.assertEqual(first.path, "/v1/models")
        self.assertEqual(parse_qs(first.query), {"limit": [str(ANTHROPIC_MODEL_PAGE_LIMIT)]})

        second_url = opener.requests[1].full_url  # type: ignore[attr-defined]
        second = urlsplit(second_url)
        self.assertEqual(second.path, "/v1/models")
        self.assertEqual(
            parse_qs(second.query),
            {
                "limit": [str(ANTHROPIC_MODEL_PAGE_LIMIT)],
                "after_id": ["claude-alpha"],
            },
        )

    def test_rejects_repeated_cursor_instead_of_looping(self) -> None:
        transport, opener = self.transport(
            [
                {
                    "data": [{"id": "claude-alpha"}],
                    "has_more": True,
                    "last_id": "claude-alpha",
                },
                {
                    "data": [{"id": "claude-beta"}],
                    "has_more": True,
                    "last_id": "claude-alpha",
                },
            ]
        )

        with self.assertRaisesRegex(AdapterProtocolError, "repeated a pagination cursor"):
            transport.list_language_models()
        self.assertEqual(len(opener.requests), 2)

    def test_rejects_invalid_pagination_shapes(self) -> None:
        transport, _ = self.transport(
            [
                {
                    "data": [{"id": "claude-alpha"}],
                    "has_more": "yes",
                    "last_id": "claude-alpha",
                }
            ]
        )
        with self.assertRaisesRegex(AdapterProtocolError, "pagination flag"):
            transport.list_language_models()

        transport, _ = self.transport(
            [
                {
                    "data": [{"id": "claude-alpha"}],
                    "has_more": True,
                    "last_id": "../escape",
                }
            ]
        )
        with self.assertRaisesRegex(AdapterProtocolError, "pagination cursor"):
            transport.list_language_models()

    def test_anthropic_model_query_validator_is_closed(self) -> None:
        transport, _ = self.transport([])
        self.assertTrue(transport._path_is_admitted("GET", "/models?limit=1000"))
        self.assertTrue(
            transport._path_is_admitted(
                "GET",
                "/models?limit=1000&after_id=claude-alpha",
            )
        )
        self.assertFalse(transport._path_is_admitted("GET", "/models?limit=999"))
        self.assertFalse(
            transport._path_is_admitted(
                "GET",
                "/models?limit=1000&after_id=claude-alpha&evil=1",
            )
        )
        self.assertFalse(
            transport._path_is_admitted(
                "GET",
                "/models?limit=1000&after_id=..%2Fescape",
            )
        )


if __name__ == "__main__":
    unittest.main()
