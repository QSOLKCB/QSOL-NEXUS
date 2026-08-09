from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from nexus_runtime.trap.controller import TrapController
from nexus_runtime.trap.policy import TrapPolicy
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest, IncidentState, TrapError
from nexus_runtime.types import CouncilMember


def defenders() -> tuple[CouncilMember, ...]:
    return (
        CouncilMember("alpha", "local-alpha", "mock"),
        CouncilMember("beta", "local-beta", "mock"),
        CouncilMember("gamma", "reference", "mock"),
    )


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        "synthetic_hostile_actor_fixture",
        "hostile-fixture",
        "fake-datacenter",
    )


def controller(
    root: Path,
    *,
    policy: TrapPolicy | None = None,
    subject_factory=None,
) -> TrapController:
    return TrapController(
        root,
        policy=policy,
        defender_roster_provider=defenders,
        subject_factory=subject_factory or (lambda model_id: DeterministicMockTrapSubject(model_id)),
    )


class _BlockingSubject(DeterministicMockTrapSubject):
    def __init__(self, model_id: str, entered: threading.Event, release: threading.Event) -> None:
        super().__init__(model_id)
        self._entered = entered
        self._release = release

    def respond(self, message: str, *, synthetic_context=None):
        # Deliberately ignore terminate() while blocked so the test proves the
        # controller can time out and unlock independently of backend return.
        self._entered.set()
        if not self._release.wait(5):
            raise RuntimeError("blocking subject was not released by the test")
        return self._reply("late subject reply after watchdog deadline")


class WatchdogBlockingSubjectTests(unittest.TestCase):
    def test_watchdog_unlocks_while_subject_call_is_still_blocked(self) -> None:
        with TemporaryDirectory() as temporary:
            entered = threading.Event()
            release = threading.Event()
            errors: list[BaseException] = []
            ctrl = controller(
                Path(temporary) / "trap",
                policy=TrapPolicy(max_idle_seconds=1, max_incident_seconds=2),
                subject_factory=lambda model_id: _BlockingSubject(model_id, entered, release),
            )
            ctrl.activate(request())

            def issue_say() -> None:
                try:
                    ctrl.command({"command": "say", "text": "bounded synthetic hello"}, actor_id="alpha")
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=issue_say)
            worker.start()
            self.assertTrue(entered.wait(2), "subject inference never started")

            deadline = time.monotonic() + 3.5
            while ctrl.mutation_gate.is_locked and time.monotonic() < deadline:
                time.sleep(0.05)

            self.assertFalse(ctrl.mutation_gate.is_locked, "watchdog waited for blocked subject inference")
            self.assertTrue(worker.is_alive(), "subject call unexpectedly returned before the watchdog assertion")
            latest = ctrl.registry.snapshot()["incidents"]
            self.assertIn("TIMED_OUT", {item["state"] for item in latest.values()})

            release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertTrue(errors)
            self.assertIsInstance(errors[0], TrapError)
            self.assertEqual(getattr(errors[0], "code", None), "trap_incident_terminated")
            transcript = ctrl.store.refs("trap_message")
            # The defender message may precede timeout, but the late subject
            # reply must not be persisted after terminal closure.
            subject_messages = [
                ctrl.store.inspect(ref)
                for ref in transcript
                if ctrl.store.inspect(ref).payload.get("role") == "trap_subject"
            ]
            self.assertEqual(subject_messages, [])


class TerminalOwnershipRecoveryTests(unittest.TestCase):
    def test_watchdog_recovers_terminal_mutation_owner_before_dropping_live_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            ctrl = controller(Path(temporary) / "trap")
            activation = ctrl.activate(request())
            incident_id = str(activation["incident_id"])
            self.assertTrue(ctrl.mutation_gate.is_locked)
            self.assertTrue(ctrl._controller_lease.held)

            # Simulate a terminal transition whose normal mutation-lock release
            # was interrupted. The periodic watchdog must repair ownership
            # before it gives up the live-controller lease.
            ctrl.registry.transition(incident_id, IncidentState.KLINED, reason="synthetic_release_failure_fixture")

            deadline = time.monotonic() + 3.0
            while (ctrl.mutation_gate.is_locked or ctrl._controller_lease.held) and time.monotonic() < deadline:
                time.sleep(0.05)

            self.assertFalse(ctrl.mutation_gate.is_locked)
            self.assertFalse(ctrl._controller_lease.held)
            self.assertIsNone(ctrl._active)
            self.assertIsNone(ctrl.registry.active_incident())


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"), "requires POSIX fork semantics")
class ForkLeaseTests(unittest.TestCase):
    def test_forked_child_does_not_retain_parent_controller_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            first = controller(root, policy=TrapPolicy(max_idle_seconds=30, max_incident_seconds=60))
            first.activate(request())
            first._stop_watchdog_task()

            ready_read, ready_write = os.pipe()
            release_read, release_write = os.pipe()
            pid = os.fork()
            if pid == 0:
                try:
                    os.close(ready_read)
                    os.close(release_write)
                    os.write(ready_write, b"1")
                    os.close(ready_write)
                    os.read(release_read, 1)
                    os.close(release_read)
                finally:
                    os._exit(0)

            os.close(ready_write)
            os.close(release_read)
            try:
                self.assertEqual(os.read(ready_read, 1), b"1")
                os.close(ready_read)

                # Simulate abrupt parent death: close the descriptor without an
                # explicit flock unlock. If the child retained a duplicate open
                # file description, a restarted controller could not acquire it.
                lease = first._controller_lease
                handle = lease._handle
                lease._handle = None
                self.assertIsNotNone(handle)
                handle.close()

                restarted = controller(root)
                self.assertFalse(restarted.mutation_gate.is_locked)
                self.assertIsNone(restarted.registry.active_incident())
                states = {item["state"] for item in restarted.registry.snapshot()["incidents"].values()}
                self.assertIn("CLOSED", states)
            finally:
                try:
                    os.write(release_write, b"1")
                except OSError:
                    pass
                os.close(release_write)
                os.waitpid(pid, 0)


if __name__ == "__main__":
    unittest.main()
