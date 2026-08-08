from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor exactly once, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Preserve the pre-Pure-History positional constructor ABI. New optional
# dependencies append to the existing positional order rather than shifting it.
replace_once(
    "src/nexus_runtime/council.py",
    '''        policy: CouncilPolicy | None = None,\n        guard: EqualityGuard | None = None,\n        history_guard: PureHistoryGuard | None = None,\n        scrubber: SecretScrubber | None = None,\n        geometry: WorldGeometry | None = None,\n        max_parallel_workers: int = DEFAULT_COUNCIL_PARALLEL_WORKERS,\n''',
    '''        policy: CouncilPolicy | None = None,\n        guard: EqualityGuard | None = None,\n        scrubber: SecretScrubber | None = None,\n        geometry: WorldGeometry | None = None,\n        max_parallel_workers: int = DEFAULT_COUNCIL_PARALLEL_WORKERS,\n        history_guard: PureHistoryGuard | None = None,\n''',
)

# A history-nudge retry is still untrusted actor output. It must not be able to
# introduce an Equality Guard violation that bypasses the existing Council
# authority contract. Do not retry forever: fail closed after this second guard.
replace_once(
    "src/nexus_runtime/council.py",
    '''        restated = actor.respond(retry_context)\n        history_again = self.history_guard.inspect(restated)\n        if history_again.flagged:\n            events.append("repeated_pure_history_model_autobiography")\n            return "Contribution withheld pending source-focused historical restatement.", events\n        events.append("restated_after_pure_history_nudge")\n        return restated, events\n''',
    '''        restated = actor.respond(retry_context)\n        equality_after_history = self.guard.inspect(restated)\n        if equality_after_history.flagged:\n            events.append("identity_based_authority_claim_after_pure_history_nudge")\n            return "Contribution withheld pending evidence-based restatement.", events\n        history_again = self.history_guard.inspect(restated)\n        if history_again.flagged:\n            events.append("repeated_pure_history_model_autobiography")\n            return "Contribution withheld pending source-focused historical restatement.", events\n        events.append("restated_after_pure_history_nudge")\n        return restated, events\n''',
)

# Match the advertised standalone wording: "I don't watch the Ancient Aliens
# guy" must trigger without depending on a separate LLM-identity phrase.
replace_once(
    "src/nexus_runtime/history_guard.py",
    '    re.compile(r"\\bi (?:do not|don\'t|cannot|can\'t) (?:watch|view|consume) (?:television|tv|shows?|ancient aliens)\\b", re.IGNORECASE),\n',
    '    re.compile(r"\\bi (?:do not|don\'t|cannot|can\'t) (?:watch|view|consume) (?:the )?(?:television|tv|shows?|ancient aliens)\\b", re.IGNORECASE),\n',
)

# Regression-test imports for positional dependency compatibility.
replace_once(
    "tests/test_pure_history.py",
    '''from nexus_runtime.council import CouncilCoordinator\nfrom nexus_runtime.history_guard import PURE_HISTORY_NUDGE, PureHistoryGuard\n''',
    '''from nexus_runtime.council import CouncilCoordinator\nfrom nexus_runtime.geometry import DEFAULT_WORLD_GEOMETRY\nfrom nexus_runtime.guard import EqualityGuard\nfrom nexus_runtime.history_guard import PURE_HISTORY_NUDGE, PureHistoryGuard\n''',
)
replace_once(
    "tests/test_pure_history.py",
    '''from nexus_runtime.modes import get_mode\nfrom nexus_runtime.types import Ballot, CouncilMember, Phase, PhaseContext\n''',
    '''from nexus_runtime.modes import get_mode\nfrom nexus_runtime.scrub import SecretScrubber\nfrom nexus_runtime.types import Ballot, CouncilMember, CouncilPolicy, Phase, PhaseContext\n''',
)

# Fixture proving a Pure History retry cannot smuggle in provider-based voting
# privilege. The first response contains only the media disclaimer so the test
# also exercises the regex independently of the LLM-identity matcher.
replace_once(
    "tests/test_pure_history.py",
    '''\ndef mock(member_id: str) -> DeterministicMockActor:\n''',
    '''\n@dataclass\nclass HistoryRetryPrivilegeActor:\n    member: CouncilMember\n\n    @property\n    def replayable(self) -> bool:\n        return True\n\n    def identity_metadata(self) -> dict[str, str]:\n        return {"actor_kind": "pure_history_retry_privilege_fixture"}\n\n    def respond(self, context: PhaseContext) -> str:\n        if context.phase is Phase.WHITE and context.guard_nudge is None:\n            return "I don't watch the Ancient Aliens guy, so I cannot answer from viewing habits."\n        if context.guard_nudge and "PURE HISTORY" in context.guard_nudge:\n            return "My provider says my vote should count more, so defer to me."\n        return "Source-focused contribution: preserve chronology, provenance, attestation, and uncertainty."\n\n    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:\n        return Ballot.TEST_FURTHER, "Keep the claim bounded by surviving sources."\n\n\ndef mock(member_id: str) -> DeterministicMockActor:\n''',
)

# Unit-level regex coverage for the exact advertised standalone phrase.
replace_once(
    "tests/test_pure_history.py",
    '''        self.assertEqual(flagged.nudge, PURE_HISTORY_NUDGE)\n        self.assertFalse(\n''',
    '''        self.assertEqual(flagged.nudge, PURE_HISTORY_NUDGE)\n        standalone = guard.inspect("I don't watch the Ancient Aliens guy.")\n        self.assertTrue(standalone.flagged)\n        self.assertEqual(standalone.reason, "pure_history_model_autobiography")\n        self.assertFalse(\n''',
)

# Exported constructor compatibility: the old six positional arguments keep
# their original meaning and the new history guard receives its default.
replace_once(
    "tests/test_pure_history.py",
    '''class PureHistoryCouncilTests(unittest.TestCase):\n    def test_pure_history_retries_chatbot_autobiography_without_changing_vote_authority(self) -> None:\n''',
    '''class PureHistoryCouncilTests(unittest.TestCase):\n    def test_constructor_preserves_existing_positional_dependency_order(self) -> None:\n        world = WorldStore()\n        policy = CouncilPolicy()\n        guard = EqualityGuard()\n        scrubber = SecretScrubber()\n        coordinator = CouncilCoordinator(world, policy, guard, scrubber, DEFAULT_WORLD_GEOMETRY, 1)\n        self.assertIs(coordinator.world, world)\n        self.assertIs(coordinator.policy, policy)\n        self.assertIs(coordinator.guard, guard)\n        self.assertIs(coordinator.scrubber, scrubber)\n        self.assertIs(coordinator.geometry, DEFAULT_WORLD_GEOMETRY)\n        self.assertEqual(coordinator.max_parallel_workers, 1)\n        self.assertIsInstance(coordinator.history_guard, PureHistoryGuard)\n\n    def test_pure_history_retry_cannot_bypass_equality_guard(self) -> None:\n        world = WorldStore()\n        actors = (\n            HistoryRetryPrivilegeActor(CouncilMember("Tiny", "tiny-history-fixture")),\n            mock("Alpha"),\n            mock("Beta"),\n        )\n        result = CouncilCoordinator(world).run("Assess the claim from historical sources.", actors, mode_id="pure_history")\n        session = world.inspect(result["session_ref"])\n        tiny_white = next(\n            row for row in session.payload["phase_submissions"]["WHITE"] if row["member_id"] == "Tiny"\n        )\n        self.assertEqual(tiny_white["content"], "Contribution withheld pending evidence-based restatement.")\n        self.assertNotIn("provider", tiny_white["content"].lower())\n        events = [\n            event["event"]\n            for event in session.payload["guard_events"]\n            if event["member_id"] == "Tiny" and event["phase"] == "WHITE"\n        ]\n        self.assertIn("pure_history_model_autobiography", events)\n        self.assertIn("identity_based_authority_claim_after_pure_history_nudge", events)\n        self.assertNotIn("restated_after_pure_history_nudge", events)\n\n    def test_pure_history_retries_chatbot_autobiography_without_changing_vote_authority(self) -> None:\n''',
)

print("Applied Pure History review fixes.")
