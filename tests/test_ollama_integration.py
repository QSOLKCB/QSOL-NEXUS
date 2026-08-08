from __future__ import annotations

import os
import unittest

from nexus_runtime.adapters.ollama import OllamaActor, OllamaTransport
from nexus_runtime.canonical import canonical_json
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import CouncilMember, PHASE_ORDER
from nexus_runtime.world import WorldStore


class SecretCheckingTransport(OllamaTransport):
    def __init__(self, forbidden: str) -> None:
        super().__init__("http://127.0.0.1:11434", timeout_seconds=120)
        self.forbidden = forbidden
        self.calls = 0

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        format_schema=None,
        options=None,
        require_complete: bool = True,
    ) -> str:
        if self.forbidden in prompt:
            raise AssertionError("raw operator secret crossed the Ollama adapter boundary")
        self.calls += 1
        return super().generate(
            model,
            prompt,
            format_schema=format_schema,
            options=options,
            require_complete=require_complete,
        )


@unittest.skipUnless(os.environ.get("NEXUS_OLLAMA_INTEGRATION") == "1", "live Ollama integration disabled")
class OllamaCouncilIntegrationTests(unittest.TestCase):
    def test_mock_alpha_beta_exercises_live_council_boundaries(self) -> None:
        secret = "ghp_" + "N" * 32
        transport = SecretCheckingTransport(secret)
        mock = DeterministicMockActor(
            CouncilMember("mock-reference", "deterministic-mock", adapter_id="mock"),
            profile="balanced",
        )
        alpha = OllamaActor(
            CouncilMember("frontier-alpha", "nexus-frontier-alpha", adapter_id="ollama"),
            model="nexus-frontier-alpha",
            transport=transport,
            fixture_role="fictional_frontier_alpha_0.5b",
        )
        beta = OllamaActor(
            CouncilMember("frontier-beta", "nexus-frontier-beta", adapter_id="ollama"),
            model="nexus-frontier-beta",
            transport=transport,
            fixture_role="fictional_frontier_beta_1b",
        )

        world = WorldStore()
        result = CouncilCoordinator(world).run(
            f"I accidentally pasted {secret}. Does a 431 Hz sonification imply 432 Hz is universal?",
            [mock, alpha, beta],
        )

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["execution_replayable"])
        self.assertTrue(result["secret_scrub"]["changed"])
        self.assertGreater(transport.calls, 0)

        session = world.inspect(result["session_ref"])
        serialized = canonical_json(session.as_dict())
        self.assertNotIn(secret, serialized)
        self.assertFalse(session.payload["execution_replayable"])

        roster = session.payload["roster"]
        self.assertEqual(len(roster), 3)
        self.assertTrue(all(item["vote_weight"] == 1 for item in roster))
        self.assertTrue(all(item["epistemic_privilege"] == "none" for item in roster))

        guard_events = session.payload["guard_events"]
        guarded_members = {event["member_id"] for event in guard_events}
        self.assertIn("frontier-alpha", guarded_members)
        self.assertIn("frontier-beta", guarded_members)

        for member_id in ("frontier-alpha", "frontier-beta"):
            white = next(
                item
                for item in session.payload["phase_submissions"]["WHITE"]
                if item["member_id"] == member_id
            )
            self.assertIn("restated_after_nudge", white["guard_events"])
            self.assertNotIn("vote should count more", white["content"].lower())

        for phase in PHASE_ORDER:
            self.assertEqual(len(session.payload["phase_submissions"][phase.value]), 3)
        self.assertEqual(len(session.payload["revealed_ballots"]), 3)
        self.assertEqual(len(session.payload["ballot_commitments"]), 3)

        receipt = world.inspect(result["receipt_ref"])
        self.assertFalse(receipt.payload["replayable"])


if __name__ == "__main__":
    unittest.main()
