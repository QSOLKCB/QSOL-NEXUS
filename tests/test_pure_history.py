from __future__ import annotations

from dataclasses import dataclass
import unittest

from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.history_guard import PURE_HISTORY_NUDGE, PureHistoryGuard
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.modes import get_mode
from nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext
from nexus_runtime.world import WorldStore


@dataclass
class AutobiographicalHistoryActor:
    member: CouncilMember

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, str]:
        return {"actor_kind": "pure_history_fixture"}

    def respond(self, context: PhaseContext) -> str:
        if context.phase is Phase.WHITE and context.guard_nudge is None:
            return (
                "As a Large Language Model I don't watch the Ancient Aliens guy, "
                "but I am trained on history."
            )
        if context.guard_nudge is not None:
            return (
                "Source-focused restatement: distinguish the ancient textual attestation, its chronology, "
                "later interpretive traditions, and modern retellings; the supplied evidence is insufficient "
                "to promote a narrated mythic event into an established historical event."
            )
        return "Source-focused contribution: preserve chronology, provenance, attestation, and uncertainty."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "The historical claim should remain bounded by the surviving source record."


def mock(member_id: str) -> DeterministicMockActor:
    return DeterministicMockActor(CouncilMember(member_id, f"mock-{member_id.lower()}"))


class PureHistoryGuardTests(unittest.TestCase):
    def test_guard_flags_model_autobiography_but_not_historical_disagreement(self) -> None:
        guard = PureHistoryGuard()
        flagged = guard.inspect("As a large language model, I don't watch television.")
        self.assertTrue(flagged.flagged)
        self.assertEqual(flagged.reason, "pure_history_model_autobiography")
        self.assertEqual(flagged.nudge, PURE_HISTORY_NUDGE)
        self.assertFalse(
            guard.inspect(
                "The sources can be read differently; the surviving evidence does not settle the interpretation."
            ).flagged
        )

    def test_mode_is_strict_sibling_of_historical_in_same_archive_region(self) -> None:
        historical = get_mode("historical")
        pure = get_mode("pure_history")
        self.assertEqual(historical.region_id, "archive")
        self.assertEqual(pure.region_id, "archive")
        self.assertIn("primary", pure.prompt_instruction.lower())
        self.assertIn("mythic", pure.prompt_instruction.lower())
        self.assertIn("model autobiography", pure.prompt_instruction.lower())


class PureHistoryCouncilTests(unittest.TestCase):
    def test_pure_history_retries_chatbot_autobiography_without_changing_vote_authority(self) -> None:
        world = WorldStore()
        actors = (
            AutobiographicalHistoryActor(CouncilMember("Tiny", "tiny-history-fixture")),
            mock("Alpha"),
            mock("Beta"),
        )
        result = CouncilCoordinator(world).run(
            "I heard the Anunnaki totally had sex with human women and bore giants. Is that historically established?",
            actors,
            mode_id="pure_history",
        )
        self.assertEqual(result["mode_id"], "pure_history")
        self.assertEqual(result["geometry_region_id"], "archive")
        session = world.inspect(result["session_ref"])
        tiny_white = next(
            row for row in session.payload["phase_submissions"]["WHITE"] if row["member_id"] == "Tiny"
        )
        self.assertNotIn("Large Language Model", tiny_white["content"])
        self.assertIn("Source-focused restatement", tiny_white["content"])
        events = [
            event["event"]
            for event in session.payload["guard_events"]
            if event["member_id"] == "Tiny" and event["phase"] == "WHITE"
        ]
        self.assertIn("pure_history_model_autobiography", events)
        self.assertIn("restated_after_pure_history_nudge", events)
        self.assertTrue(all(row["vote_weight"] == 1 for row in session.payload["roster"]))
        self.assertTrue(all(row["epistemic_privilege"] == "none" for row in session.payload["roster"]))

    def test_normal_historical_mode_does_not_apply_pure_history_autobiography_guard(self) -> None:
        world = WorldStore()
        actors = (
            AutobiographicalHistoryActor(CouncilMember("Tiny", "tiny-history-fixture")),
            mock("Alpha"),
            mock("Beta"),
        )
        result = CouncilCoordinator(world).run("Discuss the source tradition.", actors, mode_id="historical")
        session = world.inspect(result["session_ref"])
        tiny_white = next(
            row for row in session.payload["phase_submissions"]["WHITE"] if row["member_id"] == "Tiny"
        )
        self.assertIn("Large Language Model", tiny_white["content"])
        self.assertFalse(
            any(event["event"] == "pure_history_model_autobiography" for event in session.payload["guard_events"])
        )


if __name__ == "__main__":
    unittest.main()
