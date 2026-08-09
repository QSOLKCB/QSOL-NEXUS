from __future__ import annotations

import json
import unittest

from nexus_runtime.adapters.third_party import ThirdPartyTransport
from nexus_runtime.auth import SecretMaterial


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


if __name__ == "__main__":
    unittest.main()
