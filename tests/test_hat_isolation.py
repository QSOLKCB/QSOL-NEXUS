from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from nexus_runtime.adapters.base import build_ballot_prompt, build_phase_prompt
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.hat_isolation import (
    BLUE_CHAIR_PROCESS_RULE,
    DECISION_CLAIM_MARKERS,
    HAT_ORDER,
    NON_DECISION_HATS,
    PROCESS_CHAIR_HAT,
    assert_hat_order,
    completed_phase_keys_are_prefix,
    decision_authority_hat,
    disposition_process_hat,
    hats_after,
    hats_before,
    is_decision_hat,
    is_disposition_process_hat,
    non_decision_hat_cannot_host_ballot,
)
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import Ballot, CouncilMember, PHASE_ORDER, Phase, PhaseContext
from nexus_runtime.world import WorldStore


def _mock_roster() -> list[DeterministicMockActor]:
    return [
        DeterministicMockActor(CouncilMember("A", "mock-a"), profile="balanced"),
        DeterministicMockActor(CouncilMember("B", "mock-b"), profile="skeptical"),
        DeterministicMockActor(CouncilMember("C", "mock-c"), profile="supportive"),
    ]


@dataclass
class RecordingActor:
    member: CouncilMember
    seen_contexts: list[PhaseContext] = field(default_factory=list)
    ballot_contexts: list[PhaseContext] = field(default_factory=list)
    leak_decision_text: str | None = None
    forced_ballot: Ballot = Ballot.TEST_FURTHER
    try_mutate_completed: bool = False

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "hat-leakage-probe"}

    def respond(self, context: PhaseContext) -> str:
        self.seen_contexts.append(context)
        if self.try_mutate_completed:
            try:
                context.completed_phases["WHITE"] = {"HACK": "overwritten"}  # type: ignore[index]
            except Exception:
                pass
            mutable = dict(context.completed_phases)
            mutable["INJECTED_HAT"] = {self.member.member_id: "should-not-persist"}
        if self.leak_decision_text and context.phase is not Phase.BLUE:
            return f"[{context.phase.value}] LEAKED DECISION: {self.leak_decision_text}"
        return f"[{self.member.member_id}|{context.phase.value}] contribution under hat {context.phase.value} only."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        self.ballot_contexts.append(context)
        return self.forced_ballot, f"{self.member.member_id} sealed under {context.phase.value}"


@dataclass
class PeerSpyActor:
    member: CouncilMember
    peer_id: str
    same_phase_peer_leaks: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "same-phase-spy"}

    def respond(self, context: PhaseContext) -> str:
        same_bucket = context.completed_phases.get(context.phase.value, {})
        self.same_phase_peer_leaks.append((context.phase.value, self.peer_id in same_bucket))
        return f"CANARY:{self.member.member_id}:{context.phase.value}"

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "spy-ballot"


class HatIsolationTests(unittest.TestCase):
    def test_01_hat_order_is_exact(self) -> None:
        assert_hat_order(HAT_ORDER)
        assert_hat_order(PHASE_ORDER)
        self.assertEqual([p.value for p in HAT_ORDER], ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"])

    def test_02_only_blue_is_disposition_process_hat(self) -> None:
        self.assertEqual(decision_authority_hat(), Phase.BLUE)
        self.assertEqual(disposition_process_hat(), Phase.BLUE)
        self.assertTrue(is_decision_hat(Phase.BLUE))
        self.assertTrue(is_disposition_process_hat(Phase.BLUE))
        self.assertIn("process for disposition", BLUE_CHAIR_PROCESS_RULE)
        self.assertIn("equal sealed ballots", BLUE_CHAIR_PROCESS_RULE)
        for hat in NON_DECISION_HATS:
            self.assertFalse(is_decision_hat(hat))
            self.assertTrue(non_decision_hat_cannot_host_ballot(hat))

    def test_03_completed_phase_keys_are_exact_prefix(self) -> None:
        self.assertTrue(completed_phase_keys_are_prefix([], Phase.WHITE))
        self.assertTrue(completed_phase_keys_are_prefix(["WHITE"], Phase.RED))
        self.assertTrue(completed_phase_keys_are_prefix(["WHITE", "RED", "BLACK", "YELLOW", "GREEN"], Phase.BLUE))
        self.assertFalse(completed_phase_keys_are_prefix(["WHITE", "GREEN"], Phase.RED))

    def test_04_policy_publishes_fixed_hat_order(self) -> None:
        policy = CouncilCoordinator(WorldStore())._policy_dict()
        assert_hat_order(policy["phase_order"])
        self.assertTrue(policy["ballot_sealed"])
        self.assertEqual(policy["vote_weight"], 1)

    def test_05_each_hat_sees_prior_hats_only(self) -> None:
        actors = [RecordingActor(CouncilMember(name, f"rec-{name.lower()}")) for name in "ABC"]
        result = CouncilCoordinator(WorldStore(), max_parallel_workers=1).run("isolation?", actors)
        self.assertEqual(result["status"], "ok")
        for actor in actors:
            self.assertEqual(len(actor.seen_contexts), 6)
            for context in actor.seen_contexts:
                self.assertTrue(completed_phase_keys_are_prefix(context.completed_phases.keys(), context.phase))
                self.assertNotIn(context.phase.value, context.completed_phases)
                for later in hats_after(context.phase):
                    self.assertNotIn(later.value, context.completed_phases)
                for prior in hats_before(context.phase):
                    self.assertEqual(set(context.completed_phases[prior.value]), {"A", "B", "C"})

    def test_06_later_hats_cannot_overwrite_committed_content(self) -> None:
        world = WorldStore()
        actors = [RecordingActor(CouncilMember(name, f"mut-{name.lower()}"), try_mutate_completed=True) for name in "ABC"]
        result = CouncilCoordinator(world, max_parallel_workers=1).run("mutation?", actors)
        session = world.inspect(result["session_ref"]).payload
        for row in session["phase_submissions"]["WHITE"]:
            self.assertIn("|WHITE]", row["content"])
            self.assertNotIn("HACK", row["content"])
        self.assertNotIn("INJECTED_HAT", session["phase_submissions"])

    def test_07_same_phase_peer_content_is_blind_until_barrier(self) -> None:
        actors = [
            PeerSpyActor(CouncilMember("A", "spy-a"), "B"),
            PeerSpyActor(CouncilMember("B", "spy-b"), "A"),
            PeerSpyActor(CouncilMember("C", "spy-c"), "A"),
        ]
        CouncilCoordinator(WorldStore(), max_parallel_workers=3).run("blind?", actors)
        for actor in actors:
            self.assertEqual(len(actor.same_phase_peer_leaks), 6)
            self.assertFalse(any(leaked for _, leaked in actor.same_phase_peer_leaks))

    def test_08_non_blue_decision_claims_cannot_set_disposition(self) -> None:
        actors = [
            RecordingActor(CouncilMember("A", "leak-a"), leak_decision_text="ACCEPT", forced_ballot=Ballot.TEST_FURTHER),
            RecordingActor(CouncilMember("B", "leak-b"), leak_decision_text="REJECT", forced_ballot=Ballot.TEST_FURTHER),
            RecordingActor(CouncilMember("C", "leak-c"), leak_decision_text="ACCEPT_WITH_CHANGES", forced_ballot=Ballot.TEST_FURTHER),
        ]
        world = WorldStore()
        result = CouncilCoordinator(world, max_parallel_workers=1).run("can prose rule?", actors)
        self.assertEqual(result["result"]["disposition"], "TEST_FURTHER")
        self.assertEqual(result["result"]["tally"], {"TEST_FURTHER": 3})
        session = world.inspect(result["session_ref"]).payload
        for hat in NON_DECISION_HATS:
            self.assertTrue(all("LEAKED DECISION" in row["content"] for row in session["phase_submissions"][hat.value]))

    def test_09_blue_process_collects_ballots_after_all_hats(self) -> None:
        actors = [RecordingActor(CouncilMember(name, f"bal-{name.lower()}"), forced_ballot=Ballot.REJECT) for name in "ABC"]
        CouncilCoordinator(WorldStore(), max_parallel_workers=1).run("blue process?", actors)
        for actor in actors:
            self.assertEqual(len(actor.ballot_contexts), 1)
            context = actor.ballot_contexts[0]
            self.assertEqual(context.phase, PROCESS_CHAIR_HAT)
            self.assertEqual(list(context.completed_phases), [phase.value for phase in HAT_ORDER])

    def test_10_blue_synthesis_is_not_super_vote(self) -> None:
        actors = [
            RecordingActor(CouncilMember("A", "eq-a"), forced_ballot=Ballot.ACCEPT),
            RecordingActor(CouncilMember("B", "eq-b"), forced_ballot=Ballot.ACCEPT),
            RecordingActor(CouncilMember("C", "eq-c"), forced_ballot=Ballot.REJECT),
        ]
        world = WorldStore()
        result = CouncilCoordinator(world, max_parallel_workers=1).run("blue outvote?", actors)
        self.assertEqual(result["result"]["disposition"], "ACCEPT")
        self.assertEqual(result["result"]["tally"]["ACCEPT"], 2)
        for row in world.inspect(result["session_ref"]).payload["phase_submissions"]["BLUE"]:
            self.assertNotIn("choice", row)

    def test_11_blue_phase_prompt_forbids_early_ballot(self) -> None:
        context = PhaseContext("prompt", Phase.BLUE, "q", "object:" + "0" * 64, {p.value: {"A": "x"} for p in hats_before(Phase.BLUE)})
        prompt = build_phase_prompt(context)
        self.assertIn("Do not cast the sealed ballot yet", prompt)
        self.assertIn("Council phase: BLUE", prompt)

    def test_12_non_blue_prompts_do_not_invite_ballots(self) -> None:
        for hat in NON_DECISION_HATS:
            context = PhaseContext("prompt", hat, "q", "object:" + "0" * 64, {p.value: {"A": "x"} for p in hats_before(hat)})
            prompt = build_phase_prompt(context)
            self.assertNotIn("Return only the requested JSON object", prompt)
            self.assertNotIn('"choice"', prompt)

    def test_13_ballot_prompt_is_separate_and_closed(self) -> None:
        context = PhaseContext("prompt", Phase.BLUE, "q", "object:" + "0" * 64, {p.value: {"A": "x"} for p in HAT_ORDER})
        prompt = build_ballot_prompt(context)
        self.assertIn("sealed ballot", prompt.lower())
        for marker in ("ACCEPT", "REJECT", "TEST_FURTHER"):
            self.assertIn(marker, prompt)

    def test_14_durable_session_separates_phase_data_and_ballots(self) -> None:
        world = WorldStore()
        result = CouncilCoordinator(world, max_parallel_workers=1).run("structure?", _mock_roster())
        session = world.inspect(result["session_ref"]).payload
        self.assertEqual(list(session["phase_submissions"]), [phase.value for phase in HAT_ORDER])
        for rows in session["phase_submissions"].values():
            self.assertTrue(all("content" in row and "choice" not in row for row in rows))
        self.assertEqual(len(session["revealed_ballots"]), 3)
        self.assertTrue(all(ballot["choice"] in {b.value for b in Ballot} for ballot in session["revealed_ballots"]))

    def test_15_mock_templates_and_decision_markers_preserve_hat_roles(self) -> None:
        for marker in ("ACCEPT", "REJECT", "TEST_FURTHER"):
            self.assertIn(marker, DECISION_CLAIM_MARKERS)
        world = WorldStore()
        result = CouncilCoordinator(world, max_parallel_workers=1).run("templates?", _mock_roster())
        session = world.inspect(result["session_ref"]).payload
        expected = {"WHITE": "facts:", "RED": "intuition:", "BLACK": "critique:", "YELLOW": "constructive case:", "GREEN": "alternatives:", "BLUE": "synthesis:"}
        for hat, snippet in expected.items():
            for row in session["phase_submissions"][hat]:
                self.assertIn(snippet, row["content"])
                self.assertNotIn('"choice":', row["content"])


if __name__ == "__main__":
    unittest.main()
