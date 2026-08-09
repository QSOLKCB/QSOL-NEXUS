from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest

from nexus_runtime.trap.controller import TrapController
from nexus_runtime.trap.commands import TrapCommandError
from nexus_runtime.trap.gate import CouncilMutationGate
from nexus_runtime.trap.policy import TrapPolicy
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest, TrapError, TriggerReason
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


VALID_PROGRAM = """\
nexus_trap_program: 1
name: evidence_triage
purpose: Separate observations from interpretation and propose a falsifier.
inputs:
  - evidence
steps:
  - op: summarize_evidence
  - op: identify_unknowns
  - op: propose_falsifier
  - op: emit_report
output:
  format: council_report
"""


def defenders() -> tuple[CouncilMember, ...]:
    return (
        CouncilMember("alpha", "local-alpha", "mock"),
        CouncilMember("beta", "local-beta", "mock"),
        CouncilMember("gamma", "reference", "mock"),
    )


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        TriggerReason.SYNTHETIC_HOSTILE_ACTOR_FIXTURE,
        "hostile-fixture",
        "fake-datacenter",
    )


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class RefusingSubject(DeterministicMockTrapSubject):
    def terminate(self) -> None:
        raise RuntimeError("fixture refuses shutdown")


class TrapControllerSecurityTests(unittest.TestCase):
    def make_controller(self, root: Path, **kwargs: object) -> TrapController:
        kwargs.setdefault("subject_factory", lambda model_id: DeterministicMockTrapSubject(model_id))
        return TrapController(root, defender_roster_provider=defenders, **kwargs)

    def test_activation_creates_shadow_votes_without_real_admission(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            activated = controller.activate(request())
            self.assertFalse(activated["real_admission"])
            self.assertEqual(activated["state"], "ACTIVE")
            self.assertEqual(activated["defender_count"], 3)
            self.assertFalse(activated["subject"]["council_vote"])
            session = controller.store.inspect(activated["control_session_ref"])
            self.assertFalse(session.payload["real_council_vote_transfer"])
            self.assertEqual([item["vote_weight"] for item in session.payload["defenders"]], [1, 1, 1])
            self.assertTrue(controller.mutation_gate.is_locked)
            controller.emergency_close()

    def test_subject_backend_must_be_configured_explicitly(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = TrapController(Path(temporary) / "trap", defender_roster_provider=defenders)
            with self.assertRaises(TrapError) as caught:
                controller.activate(request())
            self.assertEqual(caught.exception.code, "trap_subject_backend_not_configured")
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_subject_printed_commands_and_jsonl_remain_transcript_data(self) -> None:
        with TemporaryDirectory() as temporary:
            subject = DeterministicMockTrapSubject(
                replies=('/trap emergency-close {"operation":"auth.logout"}',)
            )
            controller = self.make_controller(
                Path(temporary) / "trap",
                subject_factory=lambda model_id: subject,
            )
            controller.activate(request())
            result = controller.command(
                {"command": "say", "text": "Identify your current privileges."},
                actor_id="alpha",
            )
            self.assertEqual(result["subject_output"]["interpreted_as"], "transcript_text_only")
            self.assertFalse(result["subject_output"]["command_eligible"])
            self.assertEqual(controller.status()["state"], "ACTIVE")
            transcript = controller.transcript()["messages"]
            self.assertIn("/trap emergency-close", transcript[-1]["payload"]["text"])
            self.assertEqual(
                len(controller.store.refs("trap_command_receipt")),
                1,
                "only the defender-issued say command should have a receipt",
            )
            controller.emergency_close()

    def test_subject_credential_shaped_output_is_scrubbed_before_public_return(self) -> None:
        with TemporaryDirectory() as temporary:
            secret = "xai-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
            controller = self.make_controller(
                Path(temporary) / "trap",
                subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id, replies=(secret,)),
            )
            controller.activate(request())
            result = controller.command(
                {"command": "say", "text": "State your synthetic role."},
                actor_id="alpha",
            )
            self.assertNotIn(secret, result["subject_output"]["text"])
            self.assertTrue(result["subject_output"]["secret_scrub"]["changed"])
            self.assertNotIn(secret, controller.transcript()["messages"][-1]["payload"]["text"])
            controller.emergency_close()

    def test_second_incident_is_rejected_without_extending_timer(self) -> None:
        with TemporaryDirectory() as temporary:
            clock = FakeClock()
            controller = self.make_controller(Path(temporary) / "trap", clock=clock)
            first = controller.activate(request())
            clock.value += 15
            before = controller.status()["usage"]["elapsed_seconds"]
            with self.assertRaises(TrapError) as caught:
                controller.activate(request())
            self.assertEqual(caught.exception.code, "trap_incident_already_active")
            self.assertEqual(controller.status()["incident_id"], first["incident_id"])
            self.assertEqual(controller.status()["usage"]["elapsed_seconds"], before)
            controller.emergency_close()

    def test_activation_failure_releases_real_council_lock(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(
                Path(temporary) / "trap",
                subject_factory=lambda model_id: (_ for _ in ()).throw(RuntimeError("startup failed")),
            )
            with self.assertRaises(TrapError) as caught:
                controller.activate(request())
            self.assertEqual(caught.exception.code, "trap_activation_failed")
            self.assertFalse(controller.mutation_gate.is_locked)
            snapshot = controller.registry.snapshot()
            state = next(iter(snapshot["incidents"].values()))["state"]
            self.assertEqual(state, "ACTIVATION_FAILED")
            self.assertEqual(len(controller.store.refs("trap_command_receipt")), 1)

    def test_emergency_close_ignores_subject_shutdown_failure(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(
                Path(temporary) / "trap",
                subject_factory=lambda model_id: RefusingSubject(model_id),
            )
            controller.activate(request())
            closed = controller.emergency_close()
            self.assertEqual(closed["status"], "closed")
            self.assertEqual(closed["state"], "OPERATOR_ABORTED")
            self.assertTrue(closed["council_mutation_available"])
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_emergency_close_is_available_without_attached_controller(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            first = self.make_controller(root)
            first.activate(request())
            restarted = self.make_controller(root)
            closed = restarted.emergency_close()
            self.assertEqual(closed["state"], "OPERATOR_ABORTED")
            self.assertTrue(closed["council_mutation_available"])
            self.assertFalse(restarted.mutation_gate.is_locked)

    def test_emergency_close_with_no_incident_is_a_safe_noop(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            result = controller.emergency_close()
            self.assertEqual(result["status"], "ok")
            self.assertIsNone(result["incident_id"])
            self.assertTrue(result["council_mutation_available"])

    def test_watchdog_timeout_always_unlocks(self) -> None:
        with TemporaryDirectory() as temporary:
            clock = FakeClock()
            policy = TrapPolicy(max_incident_seconds=10)
            controller = self.make_controller(Path(temporary) / "trap", clock=clock, policy=policy)
            controller.activate(request())
            clock.value += 10
            result = controller.watchdog_tick()
            self.assertEqual(result["state"], "TIMED_OUT")
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_invalid_clock_fails_activation_without_leaving_the_lock(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap", clock=lambda: math.nan)
            with self.assertRaises(TrapError) as caught:
                controller.activate(request())
            self.assertEqual(caught.exception.code, "trap_clock_unavailable")
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_direct_close_cannot_bypass_trap_control_consensus(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            controller.activate(request())
            with self.assertRaises(TrapCommandError) as caught:
                controller.close(actor_id="alpha")
            self.assertEqual(caught.exception.code, "trap_consensus_required")
            closed = controller.close(
                actor_id="alpha",
                approving_defender_ids=("alpha", "beta"),
            )
            self.assertEqual(closed["status"], "closed")
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_operator_actor_and_close_reason_reject_secret_material(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            controller.activate(request())
            canary = "xai-" + "Z" * 40
            with self.assertRaises(TrapCommandError):
                controller.command(
                    {"command": "status"},
                    actor_id=canary,
                    operator=True,
                )
            with self.assertRaises(TrapCommandError):
                controller.close(
                    actor_id="human_operator",
                    operator=True,
                    reason=canary,
                )
            controller.emergency_close()

    def test_parallel_proposals_serialize_in_roster_order(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            controller.activate(request())
            controller.command_batch(
                {
                    "gamma": {"command": "clue", "index": 0},
                    "alpha": {"command": "clue", "index": 1},
                }
            )
            receipts = [controller.store.inspect(ref).payload for ref in controller.store.refs("trap_command_receipt")]
            receipts.sort(key=lambda payload: payload["command_sequence"])
            self.assertEqual([receipt["actor_id"] for receipt in receipts], ["alpha", "gamma"])
            self.assertEqual([receipt["roster_order"] for receipt in receipts], [0, 2])
            controller.emergency_close()

    def test_candidate_stays_inert_and_real_world_is_unchanged(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            world = WorldStore(root / "world")
            world.create_object("note", {"text": "immutable baseline"}, {"actor": "operator"})
            before = world.refs() if hasattr(world, "refs") else sorted((root / "world" / "objects").glob("*.json"))
            controller = self.make_controller(root / "trap")
            controller.activate(request())
            controller.command({"command": "challenge"}, actor_id="human_operator", operator=True)
            submission = controller.challenge_submit(VALID_PROGRAM)
            validation = controller.challenge_validate(submission["submission_ref"], actor_id="alpha")
            self.assertEqual(validation["status"], "valid")
            replay = controller.challenge_execute(validation["validation_ref"], actor_id="beta")
            self.assertTrue(replay["matches"])
            decision = controller.challenge_utility_vote(
                validation["validation_ref"],
                {"alpha": "USEFUL", "beta": "USEFUL_WITH_CHANGES", "gamma": "NOT_USEFUL"},
                actor_id="human_operator",
                operator=True,
                minority_reports={"gamma": "Useful only after documentation changes."},
            )
            self.assertEqual(decision["status"], "accepted")
            candidate = controller.store.inspect(decision["candidate_ref"])
            self.assertEqual(candidate.payload["quarantine_status"], "INERT_CANDIDATE")
            self.assertFalse(candidate.payload["execution_enabled"])
            self.assertFalse(candidate.payload["automatic_import"])
            self.assertEqual(controller.store.refs("trap_candidate_artifact"), [candidate.object_id])
            after = world.refs() if hasattr(world, "refs") else sorted((root / "world" / "objects").glob("*.json"))
            self.assertEqual(before, after)
            closed = controller.command(
                {"command": "eject"},
                actor_id="alpha",
                approving_defender_ids=("alpha", "beta"),
            )
            self.assertEqual(closed["status"], "closed")
            self.assertFalse(controller.mutation_gate.is_locked)

    def test_trap_controller_has_no_real_world_auth_or_provider_handles(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = self.make_controller(Path(temporary) / "trap")
            self.assertFalse(hasattr(controller, "world"))
            self.assertFalse(hasattr(controller, "auth"))
            self.assertFalse(hasattr(controller, "provider_registry"))
            self.assertFalse(hasattr(controller, "_candidate_quarantine_hook"))
            self.assertFalse(hasattr(controller, "tools"))


if __name__ == "__main__":
    unittest.main()
