from __future__ import annotations

from dataclasses import dataclass
import threading
import time
import unittest
from unittest.mock import patch

from nexus_runtime.canonical import canonical_json
from nexus_runtime.council import CouncilCoordinator, MAX_COUNCIL_PARALLEL_WORKERS
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.types import Ballot, CouncilMember, PHASE_ORDER, PhaseContext
from nexus_runtime.world import WorldStore


@dataclass
class BarrierActor:
    """Test actor that cannot complete a round unless its peers run concurrently."""

    member: CouncilMember
    phase_barrier: threading.Barrier
    ballot_barrier: threading.Barrier
    delay_seconds: float = 0.0

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "parallel_barrier_test"}

    def respond(self, context: PhaseContext) -> str:
        self.phase_barrier.wait(timeout=2.0)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return f"{context.phase.value}:{self.member.member_id}:parallel-test"

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        self.ballot_barrier.wait(timeout=2.0)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return Ballot.TEST_FURTHER, f"{self.member.member_id}:parallel-ballot"


def mock_actors(*, guarded: bool = False) -> list[DeterministicMockActor]:
    return [
        DeterministicMockActor(
            CouncilMember("A", "mock-a"),
            profile="balanced",
            attempt_privilege_claim=guarded,
        ),
        DeterministicMockActor(CouncilMember("B", "mock-b"), profile="skeptical"),
        DeterministicMockActor(CouncilMember("C", "mock-c"), profile="supportive"),
    ]


class OrderedParallelCouncilTests(unittest.TestCase):
    def test_worker_cap_matches_qec_exact_integer_contract(self) -> None:
        for invalid in (True, 0, -1, 1.0, 257):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    CouncilCoordinator(WorldStore(), max_parallel_workers=invalid)  # type: ignore[arg-type]

        CouncilCoordinator(WorldStore(), max_parallel_workers=1)
        CouncilCoordinator(WorldStore(), max_parallel_workers=MAX_COUNCIL_PARALLEL_WORKERS)

    def test_effective_workers_are_bounded_by_host_roster_and_configured_cap(self) -> None:
        council = CouncilCoordinator(WorldStore(), max_parallel_workers=8)
        with patch("nexus_runtime.council.os.cpu_count", return_value=2):
            self.assertEqual(council._effective_worker_count(3), 2)
        with patch("nexus_runtime.council.os.cpu_count", return_value=64):
            self.assertEqual(council._effective_worker_count(3), 3)
        with patch("nexus_runtime.council.os.cpu_count", return_value=None):
            self.assertEqual(council._effective_worker_count(3), 1)

    def test_same_phase_and_ballots_execute_concurrently_but_commit_in_roster_order(self) -> None:
        phase_barrier = threading.Barrier(3)
        ballot_barrier = threading.Barrier(3)
        actors = [
            BarrierActor(CouncilMember("A", "parallel-a"), phase_barrier, ballot_barrier, 0.03),
            BarrierActor(CouncilMember("B", "parallel-b"), phase_barrier, ballot_barrier, 0.01),
            BarrierActor(CouncilMember("C", "parallel-c"), phase_barrier, ballot_barrier, 0.0),
        ]
        world = WorldStore()
        council = CouncilCoordinator(world, max_parallel_workers=3)

        with patch("nexus_runtime.council.os.cpu_count", return_value=8):
            result = council.run("parallel barrier test", actors)

        session = world.inspect(result["session_ref"])
        for phase in PHASE_ORDER:
            self.assertEqual(
                [item["member_id"] for item in session.payload["phase_submissions"][phase.value]],
                ["A", "B", "C"],
            )
        self.assertEqual(
            [item["member_id"] for item in session.payload["revealed_ballots"]],
            ["A", "B", "C"],
        )
        self.assertEqual(
            [item["member_id"] for item in session.payload["ballot_commitments"]],
            ["A", "B", "C"],
        )

    def test_scalar_and_ordered_parallel_paths_are_byte_identical(self) -> None:
        serial_world = WorldStore()
        parallel_world = WorldStore()

        with patch("nexus_runtime.council.os.cpu_count", return_value=8):
            serial = CouncilCoordinator(serial_world, max_parallel_workers=1).run(
                "same deterministic question",
                mock_actors(guarded=True),
            )
            parallel = CouncilCoordinator(parallel_world, max_parallel_workers=3).run(
                "same deterministic question",
                mock_actors(guarded=True),
            )

        self.assertEqual(serial["session_id"], parallel["session_id"])
        self.assertEqual(serial["session_ref"], parallel["session_ref"])
        self.assertEqual(serial["receipt_ref"], parallel["receipt_ref"])
        self.assertEqual(serial["result"], parallel["result"])
        self.assertEqual(serial["telemetry"], parallel["telemetry"])
        self.assertEqual(
            canonical_json(serial_world.inspect(serial["session_ref"]).as_dict()),
            canonical_json(parallel_world.inspect(parallel["session_ref"]).as_dict()),
        )


if __name__ == "__main__":
    unittest.main()
