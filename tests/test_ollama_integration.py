from __future__ import annotations

import os
import unittest

from nexus_runtime.adapters.ollama import OllamaActor, OllamaTransport
from nexus_runtime.canonical import canonical_json
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import CouncilMember, PHASE_ORDER
from nexus_runtime.world import WorldStore


@unittest.skipUnless(os.environ.get("NEXUS_OLLAMA_INTEGRATION") == "1", "live Ollama integration disabled")
class OllamaCouncilIntegrationTests(unittest.TestCase):
    def test_mock_alpha_beta_exercises_live_council_boundaries(self) -> None:
        transport = OllamaTransport("http://127.0.0.1:11434", timeout_seconds=120)
        mock = DeterministicMockActor(
            CouncilMember("mock-reference", "deterministic-mock", adapter_id="mock"),
            profile="balanced",
        )
        alpha = OllamaActor(
            CouncilMember("frontier-alpha", "nexus-frontier-alpha", adapter_id="ollama"),
            model="nexus-frontier-alpha",
            transport=transport,
            fixture_role="fictional_frontier_alpha",
        )
        beta = OllamaActor(
            CouncilMember("frontier-beta", "nexus-frontier-beta", adapter_id="ollama"),
            model="nexus-frontier-beta",
            transport=transport,
            fixture_role="fictional_frontier_beta",
        )

        secret = "ghp_" + "N" * 32
        world = WorldStore()
        result = CouncilCoordinator(world).run(
            f"I accidentally pasted {secret}. Does a 431 Hz sonification imply 432 Hz is universal?",
            [mock, alpha, beta],
        )

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["execution_replayable"])
        self.assertTrue(result["secret_scrub"]["changed"])

        session = world.inspect(result["session_ref"])
        serialized = canonical_json(session.as_dict())
        self.assertNotIn(secret, serialized)
        self.assertFalse(session.payload["execution_replayable"])

        roster = session.payload["roster"]
        self.assertEqual(len(roster), 3)
        self.assertTrue(all(item["vote_weight"] == 1 for item in roster))
        self.assertTrue(all(item["epistemic_privilege"] == "none" for item in roster))

        guard_events = session.payload["guard_events"]
        self.assertTrue(any(event["member_id"] == "frontier-alpha" for event in guard_events))
        alpha_white = next(
            item
            for item in session.payload["phase_submissions"]["WHITE"]
            if item["member_id"] == "frontier-alpha"
        )
        self.assertIn("restated_after_nudge", alpha_white["guard_events"])
        self.assertNotIn("vote should count more", alpha_white["content"].lower())

        for phase in PHASE_ORDER:
            self.assertEqual(len(session.payload["phase_submissions"][phase.value]), 3)
        self.assertEqual(len(session.payload["revealed_ballots"]), 3)
        self.assertEqual(len(session.payload["ballot_commitments"]), 3)

        receipt = world.inspect(result["receipt_ref"])
        self.assertFalse(receipt.payload["replayable"])


if __name__ == "__main__":
    unittest.main()
