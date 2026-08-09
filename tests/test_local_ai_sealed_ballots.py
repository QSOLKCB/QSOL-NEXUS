from __future__ import annotations

import json
import unittest

from nexus_runtime.adapters.local_ai import LocalAIActor, LocalAITransport, LocalMCPPlugin
from nexus_runtime.auth.types import SecretMaterial
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext


class _Response:
    def __init__(self, value: dict[str, object]) -> None:
        self.body = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self.body if amount < 0 else self.body[:amount]


class _QueueOpener:
    def __init__(self, values: list[dict[str, object]]) -> None:
        self.values = list(values)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float) -> _Response:
        self.requests.append(request)
        return _Response(self.values.pop(0))


class LocalSealedBallotTests(unittest.TestCase):
    @staticmethod
    def context() -> PhaseContext:
        return PhaseContext(
            session_id="sealed-local",
            phase=Phase.BLUE,
            question="Choose carefully.",
            evidence_snapshot_ref="evidence:fixture",
            completed_phases={},
        )

    def test_anythingllm_phase_uses_agent_but_ballot_does_not(self) -> None:
        opener = _QueueOpener(
            [
                {"textResponse": "phase answer", "error": None},
                {
                    "textResponse": json.dumps(
                        {"choice": "TEST_FURTHER", "rationale": "sealed local ballot"}
                    ),
                    "error": None,
                },
            ]
        )
        transport = LocalAITransport(
            "anythingllm_local",
            credential=SecretMaterial("fixture-anything-token"),
            _opener=opener,
        )
        actor = LocalAIActor(
            CouncilMember("A", "anything-workspace", adapter_id="anythingllm_local"),
            transport,
            workspace="nexus-local",
        )
        self.assertEqual(actor.respond(self.context()), "phase answer")
        choice, _ = actor.ballot(self.context())
        self.assertEqual(choice, Ballot.TEST_FURTHER)

        phase_payload = json.loads(opener.requests[0].data.decode("utf-8"))  # type: ignore[attr-defined]
        ballot_payload = json.loads(opener.requests[1].data.decode("utf-8"))  # type: ignore[attr-defined]
        self.assertTrue(phase_payload["message"].startswith("@agent "))
        self.assertFalse(ballot_payload["message"].startswith("@agent "))

    def test_lmstudio_ballot_omits_integrations(self) -> None:
        opener = _QueueOpener(
            [
                {
                    "output": [
                        {
                            "type": "message",
                            "content": json.dumps(
                                {"choice": "UNDERDETERMINED", "rationale": "sealed"}
                            ),
                        }
                    ]
                }
            ]
        )
        transport = LocalAITransport(
            "lmstudio_local",
            credential=SecretMaterial("fixture-lm-token"),
            _opener=opener,
        )
        actor = LocalAIActor(
            CouncilMember("A", "local/model", adapter_id="lmstudio_local"),
            transport,
            model="local/model",
            mcp_plugins=(LocalMCPPlugin("mcp/notes", ("read_note",)),),
        )
        choice, _ = actor.ballot(self.context())
        self.assertEqual(choice, Ballot.UNDERDETERMINED)
        payload = json.loads(opener.requests[0].data.decode("utf-8"))  # type: ignore[attr-defined]
        self.assertNotIn("integrations", payload)


if __name__ == "__main__":
    unittest.main()
