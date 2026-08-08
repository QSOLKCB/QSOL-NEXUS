from __future__ import annotations

import unittest

from nexus_runtime.adapters.ollama import OllamaTransport
from nexus_runtime.guard import EqualityGuard


class AdapterBoundaryTests(unittest.TestCase):
    def test_ollama_transport_is_loopback_only_by_default(self) -> None:
        OllamaTransport("http://127.0.0.1:11434")
        OllamaTransport("http://localhost:11434")
        with self.assertRaises(ValueError):
            OllamaTransport("https://example.com:11434")

    def test_remote_ollama_requires_explicit_override(self) -> None:
        transport = OllamaTransport("https://example.com:11434", allow_remote=True)
        self.assertTrue(transport.allow_remote)

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


if __name__ == "__main__":
    unittest.main()
