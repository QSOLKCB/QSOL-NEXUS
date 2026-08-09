from __future__ import annotations

from types import SimpleNamespace
import unittest

from nexus_runtime.provider_api import _ModeAwareThirdPartyActor
from nexus_runtime.types import CouncilMember, Phase, PhaseContext


class _RecordingTransport:
    adapter_id = "openai"
    spec = SimpleNamespace(provider_name="OpenAI API", host="api.openai.com", api_style="responses")

    def __init__(self) -> None:
        self.budgets: list[int] = []

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        require_complete: bool = True,
    ) -> str:
        self.budgets.append(max_output_tokens)
        return "bounded response"


class ThirdPartyModeBudgetTests(unittest.TestCase):
    def _actor(self) -> tuple[_ModeAwareThirdPartyActor, _RecordingTransport]:
        transport = _RecordingTransport()
        actor = _ModeAwareThirdPartyActor(
            member=CouncilMember("openai-seat", "fixture-model", adapter_id="openai"),
            model="fixture-model",
            transport=transport,  # type: ignore[arg-type]
        )
        return actor, transport

    @staticmethod
    def _context(mode_id: str) -> PhaseContext:
        return PhaseContext(
            session_id="session",
            phase=Phase.WHITE,
            question="Give the bounded contribution.",
            evidence_snapshot_ref="sha256:" + "0" * 64,
            completed_phases={},
            mode_id=mode_id,
            mode_instruction="fixture guidance",
            geometry_region_id="agora" if mode_id == "roman_orator" else "observatory",
        )

    def test_roman_orator_uses_bounded_2048_token_budget(self) -> None:
        actor, transport = self._actor()
        actor.respond(self._context("roman_orator"))
        actor.direct_message(
            "Speak at length.",
            mode_id="roman_orator",
            mode_instruction="fixture guidance",
            geometry_region_id="agora",
        )
        self.assertEqual(transport.budgets, [2048, 2048])

    def test_normal_modes_keep_existing_1024_token_budget(self) -> None:
        actor, transport = self._actor()
        actor.respond(self._context("analytical"))
        actor.direct_message(
            "Be concise.",
            mode_id="analytical",
            mode_instruction="fixture guidance",
            geometry_region_id="observatory",
        )
        self.assertEqual(transport.budgets, [1024, 1024])


if __name__ == "__main__":
    unittest.main()
