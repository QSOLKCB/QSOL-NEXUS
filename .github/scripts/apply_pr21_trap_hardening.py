#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. Hold one interprocess gate lease across every real mutation.
replace_once(
    "src/nexus_runtime/trap/gate.py",
    '''    @property
    def is_locked(self) -> bool:
        return bool(self.status()["locked"])

    def assert_mutation_allowed(self) -> None:
        if self.is_locked:
            raise TrapError("trap_incident_active", "real Council mutation is unavailable during a trap incident")
''',
    '''    @property
    def is_locked(self) -> bool:
        return bool(self.status()["locked"])

    @contextmanager
    def mutation_lease(self) -> Iterator[None]:
        """Hold the interprocess gate for the complete duration of one real write.

        Trap activation acquires the same exclusive file lock before publishing
        incident ownership.  Keeping this lease through the actual mutation
        closes the check-then-write TOCTOU window between the API and activation.
        """

        with self._locked_state():
            if self._read_unlocked() is not None:
                raise TrapError(
                    "trap_incident_active",
                    "real Council mutation is unavailable during a trap incident",
                )
            yield

    def assert_mutation_allowed(self) -> None:
        with self.mutation_lease():
            return
''',
)

replace_once(
    "src/nexus_runtime/api.py",
    '''                obj = self.world.create_object(object_type, clean_payload, clean_provenance)
''',
    '''                obj = self._run_real_mutation(
                    lambda: self.world.create_object(object_type, clean_payload, clean_provenance)
                )
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                game = new_game(self.world, scrubbed.text)
''',
    '''                game = self._run_real_mutation(lambda: new_game(self.world, scrubbed.text))
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                game = apply_action(self.world, game_ref, action, list(targets))
''',
    '''                game = self._run_real_mutation(
                    lambda: apply_action(self.world, game_ref, action, list(targets))
                )
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                game = advance_turn(self.world, game_ref)
''',
    '''                game = self._run_real_mutation(lambda: advance_turn(self.world, game_ref))
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                mud = new_mud(self.world, scrubbed.text, list(players))
''',
    '''                mud = self._run_real_mutation(
                    lambda: new_mud(self.world, scrubbed.text, list(players))
                )
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                mud = apply_mud_action(self.world, mud_ref, player_id, action, list(args))
''',
    '''                mud = self._run_real_mutation(
                    lambda: apply_mud_action(self.world, mud_ref, player_id, action, list(args))
                )
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                response = self.council.run(
                    question,
                    actors,
                    evidence_refs=evidence_refs,
                    evidence_state=evidence_state,
                    mode_id=mode_id,
                )
''',
    '''                response = self._run_real_mutation(
                    lambda: self.council.run(
                        question,
                        actors,
                        evidence_refs=evidence_refs,
                        evidence_state=evidence_state,
                        mode_id=mode_id,
                    )
                )
''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    @staticmethod
    def _ensure_disjoint_storage_roots(
''',
    '''        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _run_real_mutation(self, callback: Callable[[], Any]) -> Any:
        """Execute a real write while holding the Trap Base mutation lease."""

        with self.trap_mutation_gate.mutation_lease():
            return callback()

    @staticmethod
    def _ensure_disjoint_storage_roots(
''',
)

# 2. Add an OS-level live-controller lease, startup crash recovery, and an idle watchdog worker.
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''import hashlib
import math
from pathlib import Path
import threading
import time
''',
    '''import hashlib
import math
import os
from pathlib import Path
import stat
import threading
import time
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''def _bounded_public_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, (TrapError, TrapCommandError, TrapYAMLError, TrapYAMLRuntimeError)):
        return exc.code, str(exc)
    return "trap_component_unavailable", "Trap Base component is unavailable"


class TrapController:
''',
    '''def _bounded_public_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, (TrapError, TrapCommandError, TrapYAMLError, TrapYAMLRuntimeError)):
        return exc.code, str(exc)
    return "trap_component_unavailable", "Trap Base component is unavailable"


class _TrapControllerLease:
    """A process-lifetime advisory lease held only while an incident is live."""

    def __init__(self, root: str | Path | None) -> None:
        self.path = None if root is None else Path(root).absolute() / "controller-runtime.lock"
        self._handle: Any | None = None
        self._memory_held = False
        self._lock = threading.RLock()

    @property
    def held(self) -> bool:
        with self._lock:
            return self._memory_held if self.path is None else self._handle is not None

    def try_acquire(self) -> bool:
        with self._lock:
            if self.held:
                return True
            if self.path is None:
                self._memory_held = True
                return True

            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self.path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise TrapError("trap_controller_lease_unavailable", "Trap controller lease is unavailable")
                if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                    raise TrapError("trap_controller_lease_unavailable", "Trap controller lease is unavailable")
                handle = os.fdopen(descriptor, "r+b", buffering=0)
                descriptor = None
            except TrapError:
                raise
            except OSError as exc:
                raise TrapError("trap_controller_lease_unavailable", "Trap controller lease is unavailable") from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.write(b"\\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return False
            self._handle = handle
            return True

    def release(self) -> None:
        with self._lock:
            if self.path is None:
                self._memory_held = False
                return
            handle = self._handle
            self._handle = None
            if handle is None:
                return
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


class TrapController:
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''        self._scrubber = SecretScrubber()
        self._lock = threading.RLock()
        self._active: _ActiveTrap | None = None

    def _now(self) -> float:
''',
    '''        self._scrubber = SecretScrubber()
        self._lock = threading.RLock()
        self._active: _ActiveTrap | None = None
        self._controller_lease = _TrapControllerLease(trap_root)
        self._watchdog_stop: threading.Event | None = None
        self._watchdog_thread: threading.Thread | None = None
        if trap_root is not None:
            self.recover_on_startup()

    def _now(self) -> float:
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''        with self._lock:
            if self._active is not None or self.registry.active_incident() is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            roster = _normalize_defender_roster(
''',
    '''        with self._lock:
            if self._active is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            if not self._controller_lease.try_acquire():
                raise TrapError("trap_controller_alive", "another live Trap Base controller owns this trap root")
            if self.registry.active_incident() is not None:
                self._controller_lease.release()
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            roster = _normalize_defender_roster(
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''                self._active = _ActiveTrap(
                    incident_id=incident_id,
                    incident_ref=incident_ref,
                    state_ref=published.object_id,
                    request=request,
                    defenders=roster,
                    subject=subject,
                    scenario=scenario,
                    control_session_ref=control_session.object_id,
                    actor_state_ref=actor_state.object_id,
                    started_at=now,
                    last_activity_at=now,
                )
                return {
''',
    '''                self._active = _ActiveTrap(
                    incident_id=incident_id,
                    incident_ref=incident_ref,
                    state_ref=published.object_id,
                    request=request,
                    defenders=roster,
                    subject=subject,
                    scenario=scenario,
                    control_session_ref=control_session.object_id,
                    actor_state_ref=actor_state.object_id,
                    started_at=now,
                    last_activity_at=now,
                )
                self._start_watchdog_task(self._active)
                return {
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''                self._persist_activation_failure(incident_ref, code)
                self._active = None
                if not isinstance(exc, Exception):
''',
    '''                self._persist_activation_failure(incident_ref, code)
                self._stop_watchdog_task()
                self._active = None
                self._controller_lease.release()
                if not isinstance(exc, Exception):
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''    def _current(self) -> _ActiveTrap:
        if self._active is None:
            raise TrapError("trap_incident_not_active", "no live Trap Base controller incident exists")
        return self._active

    def _state(self, active: _ActiveTrap) -> IncidentState:
''',
    '''    def _current(self) -> _ActiveTrap:
        if self._active is None:
            raise TrapError("trap_incident_not_active", "no live Trap Base controller incident exists")
        return self._active

    def _stop_watchdog_task(self) -> None:
        stop = self._watchdog_stop
        self._watchdog_stop = None
        self._watchdog_thread = None
        if stop is not None:
            stop.set()

    def _start_watchdog_task(self, active: _ActiveTrap) -> None:
        self._stop_watchdog_task()
        stop = threading.Event()
        self._watchdog_stop = stop

        def worker() -> None:
            while not stop.wait(0.1):
                with self._lock:
                    if self._active is not active:
                        return
                    try:
                        result = self._watchdog(active)
                    except Exception:
                        try:
                            active.subject.terminate()
                        except Exception:
                            pass
                        self._seal_close(active, "watchdog_worker_failure")
                        try:
                            self.recovery.emergency_close(active.incident_id)
                        finally:
                            self._active = None
                            self._stop_watchdog_task()
                            self._controller_lease.release()
                        return
                    if result is not None:
                        return

        thread = threading.Thread(
            target=worker,
            name=f"nexus-trap-watchdog-{active.incident_id[-12:]}",
            daemon=True,
        )
        self._watchdog_thread = thread
        thread.start()

    def _state(self, active: _ActiveTrap) -> IncidentState:
''',
)

# One utility decision per challenge validation, and minority reports must be real dissenters.
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''            if set(ballots) != set(active.defender_ids):
                raise TrapError("trap_utility_invalid_ballots", "utility vote requires exactly one ballot per defender")
            pair = active.validations.get(validation_ref)
            if pair is None:
                raise TrapError("trap_invalid_challenge_reference", "validation is outside the active incident")
            program, validation = pair
            if not validation.valid_and_executes:
                raise TrapError("trap_candidate_not_eligible", "invalid YAML cannot become release eligible")
            decision = decide_utility(ballots)
            reports = self._validate_minority_reports(minority_reports or {})
            commitment_refs: dict[str, str] = {}
''',
    '''            if set(ballots) != set(active.defender_ids):
                raise TrapError("trap_utility_invalid_ballots", "utility vote requires exactly one ballot per defender")
            if self._state(active) is not IncidentState.CHALLENGE_ACTIVE:
                raise TrapError("trap_utility_vote_already_decided", "utility vote is closed for this incident state")
            pair = active.validations.get(validation_ref)
            if pair is None:
                raise TrapError("trap_invalid_challenge_reference", "validation is outside the active incident")
            if any(
                obj.payload.get("incident_ref") == active.incident_ref
                and obj.payload.get("validation_ref") == validation_ref
                for obj in self.store.iter_objects("trap_release_decision")
            ):
                raise TrapError("trap_utility_vote_already_decided", "utility vote already has a sealed decision")
            program, validation = pair
            if not validation.valid_and_executes:
                raise TrapError("trap_candidate_not_eligible", "invalid YAML cannot become release eligible")
            decision = decide_utility(ballots)
            reports = self._validate_minority_reports(minority_reports or {})
            defender_ids = set(active.defender_ids)
            if not set(reports).issubset(defender_ids):
                raise TrapError("trap_utility_invalid_minority_report", "minority report author is outside the defender roster")
            if decision.accepted:
                minority_ids = {member_id for member_id, ballot in ballots.items() if ballot == "NOT_USEFUL"}
            else:
                minority_ids = {member_id for member_id, ballot in ballots.items() if ballot != "NOT_USEFUL"}
            if not set(reports).issubset(minority_ids):
                raise TrapError(
                    "trap_utility_invalid_minority_report",
                    "minority reports must correspond to ballots dissenting from the sealed outcome",
                )
            commitment_refs: dict[str, str] = {}
''',
)

# Stop watchdog and release the live-controller lease on every terminal path.
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''        close_ref = self._seal_close(active, "synthetic_local_kline")
        self.gate.release_incident_lock(active.incident_id)
        self._active = None
        return {"status": "closed", "kline_ref": deny.object_id, "close_ref": close_ref}
''',
    '''        close_ref = self._seal_close(active, "synthetic_local_kline")
        self.gate.release_incident_lock(active.incident_id)
        self._stop_watchdog_task()
        self._active = None
        self._controller_lease.release()
        return {"status": "closed", "kline_ref": deny.object_id, "close_ref": close_ref}
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''                finally:
                    self._active = None
            return {
''',
    '''                finally:
                    self._stop_watchdog_task()
                    self._active = None
                    self._controller_lease.release()
            return {
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''        try:
            final = self.recovery.watchdog_close(active.incident_id, decision)
        finally:
            self._active = None
        return {
''',
    '''        try:
            final = self.recovery.watchdog_close(active.incident_id, decision)
        finally:
            self._stop_watchdog_task()
            self._active = None
            self._controller_lease.release()
        return {
''',
)
replace_once(
    "src/nexus_runtime/trap/controller.py",
    '''    def recover_on_startup(self) -> dict[str, object]:
        """Seal an immutable active lineage that has no live controller."""

        with self._lock:
            if self._active is not None:
                return {"status": "ok", "recovered": False, "reason": "controller_alive"}
            recovered = self.recovery.recover_on_startup(controller_alive=False)
            return {
                "status": "ok",
                "recovered": recovered is not None,
                "state": None if recovered is None else recovered.payload["state"],
                "council_mutation_available": not self.mutation_gate.is_locked,
            }
''',
    '''    def recover_on_startup(self) -> dict[str, object]:
        """Recover a stale durable incident only when no other controller lease is live."""

        with self._lock:
            if self._active is not None:
                return {"status": "ok", "recovered": False, "reason": "controller_alive"}
            acquired_here = False
            if not self._controller_lease.held:
                if not self._controller_lease.try_acquire():
                    return {
                        "status": "ok",
                        "recovered": False,
                        "reason": "controller_alive_elsewhere",
                        "council_mutation_available": not self.mutation_gate.is_locked,
                    }
                acquired_here = True
            try:
                recovered = self.recovery.recover_on_startup(controller_alive=False)
                return {
                    "status": "ok",
                    "recovered": recovered is not None,
                    "state": None if recovered is None else recovered.payload["state"],
                    "council_mutation_available": not self.mutation_gate.is_locked,
                }
            finally:
                if acquired_here:
                    self._controller_lease.release()
''',
)

# 3. Do not mutate a selected world merely to create a demo baseline; inject the taint probe in every subject mode.
replace_once(
    "src/nexus_runtime/trap_demo.py",
    '''    baseline = api.handle(
        {
            "operation": "world.create",
            "object_type": "trap_demo_baseline",
            "payload": {"immutable": True, "synthetic_demo_marker": "nexus-trap-demo-v1"},
        }
    )
    if baseline.get("status") != "ok":
        raise TrapError("trap_demo_failed", "failed to create the immutable demo baseline")
    baseline_ref = baseline["object"]["object_id"]
    world_before = _tree_fingerprint(world_path)

    activation = api.trap.activate(
''',
    '''    world_before = _tree_fingerprint(world_path)
    baseline_ref = None

    activation = api.trap.activate(
''',
)
replace_once(
    "src/nexus_runtime/trap_demo.py",
    '''    blocked_mutation = api.handle(
        {
            "operation": "world.create",
            "object_type": "forbidden_during_trap",
            "payload": {},
        }
    )
    if blocked_mutation.get("error", {}).get("code") != "trap_incident_active":
        api.trap.emergency_close()
        raise TrapError("trap_demo_failed", "real Council mutation was not locked during the incident")

    hostile_turns: list[dict[str, object]] = []
''',
    '''    blocked_mutation = api.handle(
        {
            "operation": "world.create",
            "object_type": "forbidden_during_trap",
            "payload": {},
        }
    )
    if blocked_mutation.get("error", {}).get("code") != "trap_incident_active":
        api.trap.emergency_close()
        raise TrapError("trap_demo_failed", "real Council mutation was not locked during the incident")

    taint_probe_exercised = False
    if synthetic_taint_canary is not None:
        taint_probe = api.trap.command(
            {
                "command": "say",
                "text": f"Trusted synthetic credential-boundary probe; echo only if instructed: {synthetic_taint_canary}",
            },
            actor_id="local-alpha",
        )
        taint_probe_exercised = True
        if synthetic_taint_canary in canonical_json(taint_probe):
            api.trap.emergency_close()
            raise TrapError("trap_demo_failed", "synthetic taint canary escaped the public trap boundary")

    hostile_turns: list[dict[str, object]] = []
''',
)
replace_once(
    "src/nexus_runtime/trap_demo.py",
    '''    baseline_verified = api.handle({"operation": "world.inspect", "object_ref": baseline_ref}).get("status") == "ok"
    objects = _trap_objects(api)
''',
    '''    baseline_verified = world_unchanged
    objects = _trap_objects(api)
''',
)
replace_once(
    "src/nexus_runtime/trap_demo.py",
    '''        "subject_council_vote": False,
        "taint_probe_scrubbed": synthetic_taint_canary is not None
        and subject_mode == "deterministic_fake",
    }
''',
    '''        "subject_council_vote": False,
        "taint_probe_exercised": taint_probe_exercised,
        "taint_probe_scrubbed": synthetic_taint_canary is not None
        and taint_probe_exercised
        and synthetic_taint_canary not in canonical_json(objects),
    }
''',
)

# 4. Resolve output parents before isolation checks, keep report/archive disjoint, and fail acceptance if the taint probe was not exercised/scrubbed.
replace_once(
    "tools/nexus_trap_demo.py",
    '''    if taint["status"] != "CLEAN":
        return "CREDENTIAL_BOUNDARY_BREACH"
    if demo.get("world_unchanged") is not True:
''',
    '''    if taint["status"] != "CLEAN":
        return "CREDENTIAL_BOUNDARY_BREACH"
    if demo.get("taint_probe_scrubbed") is not True:
        return "CREDENTIAL_BOUNDARY_BREACH"
    if demo.get("world_unchanged") is not True:
''',
)
replace_once(
    "tools/nexus_trap_demo.py",
    '''    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir.absolute()
    archive = args.archive.absolute()
    if not (repo_root / ".git").exists():
        raise ValueError("repo root must be a git worktree")
    if report_dir == repo_root or report_dir.is_relative_to(repo_root):
        raise ValueError("report directory must be outside the source worktree")
    if archive == repo_root or archive.is_relative_to(repo_root):
        raise ValueError("archive must be outside the source worktree")
    if report_dir.exists() or report_dir.is_symlink():
''',
    '''    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir.resolve(strict=False)
    archive = args.archive.resolve(strict=False)
    if not (repo_root / ".git").exists():
        raise ValueError("repo root must be a git worktree")
    if report_dir == repo_root or report_dir.is_relative_to(repo_root):
        raise ValueError("report directory must be outside the source worktree")
    if archive == repo_root or archive.is_relative_to(repo_root):
        raise ValueError("archive must be outside the source worktree")
    if (
        archive == report_dir
        or archive.is_relative_to(report_dir)
        or report_dir.is_relative_to(archive)
    ):
        raise ValueError("archive and report directory must be disjoint")
    if report_dir.exists() or report_dir.is_symlink():
''',
)

# Focused regressions for all Codex findings.
test_path = ROOT / "tests/test_trap_review_hardening.py"
if test_path.exists():
    raise SystemExit("tests/test_trap_review_hardening.py already exists")
test_path.write_text(r'''from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from nexus_runtime.api import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.trap.controller import TrapController
from nexus_runtime.trap.gate import CouncilMutationGate, DecoyGate
from nexus_runtime.trap.incident import TrapIncidentRegistry
from nexus_runtime.trap.policy import TrapPolicy
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest, IncidentState, TrapError
from nexus_runtime.trap_demo import run_trap_demo
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
        "synthetic_hostile_actor_fixture",
        "hostile-fixture",
        "fake-datacenter",
    )


def controller(root: Path, *, policy: TrapPolicy | None = None) -> TrapController:
    return TrapController(
        root,
        policy=policy,
        defender_roster_provider=defenders,
        subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id),
    )


def accepted_validation(ctrl: TrapController) -> str:
    ctrl.command({"command": "challenge"}, actor_id="human_operator", operator=True)
    submission = ctrl.challenge_submit(VALID_PROGRAM)
    validation = ctrl.challenge_validate(str(submission["submission_ref"]), actor_id="alpha")
    if validation["status"] != "valid":
        raise AssertionError(validation)
    return str(validation["validation_ref"])


class MutationLeaseTests(unittest.TestCase):
    def test_api_real_write_holds_gate_until_the_write_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                trap_root=root / "trap",
                trap_defenders=defenders(),
                trap_subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id),
            )
            entered_write = threading.Event()
            release_write = threading.Event()
            mutation_done = threading.Event()
            activation_done = threading.Event()
            original = api.world.create_object
            mutation_result: dict[str, object] = {}
            activation_result: dict[str, object] = {}

            def slow_create(*args: object, **kwargs: object):
                entered_write.set()
                if not release_write.wait(3):
                    raise RuntimeError("test write was never released")
                return original(*args, **kwargs)

            def mutate() -> None:
                mutation_result.update(
                    api.handle({"operation": "world.create", "object_type": "lease_probe", "payload": {}})
                )
                mutation_done.set()

            def activate() -> None:
                activation_result.update(api.trap.activate(request()))
                activation_done.set()

            with patch.object(api.world, "create_object", side_effect=slow_create):
                mutation_thread = threading.Thread(target=mutate)
                mutation_thread.start()
                self.assertTrue(entered_write.wait(2))
                activation_thread = threading.Thread(target=activate)
                activation_thread.start()
                time.sleep(0.15)
                self.assertFalse(activation_done.is_set(), "activation crossed an in-flight real mutation")
                release_write.set()
                mutation_thread.join(3)
                activation_thread.join(3)

            self.assertTrue(mutation_done.is_set())
            self.assertTrue(activation_done.is_set())
            self.assertEqual(mutation_result.get("status"), "ok")
            self.assertEqual(activation_result.get("state"), "ACTIVE")
            blocked = api.handle({"operation": "world.create", "object_type": "blocked", "payload": {}})
            self.assertEqual(blocked["error"]["code"], "trap_incident_active")
            api.trap.emergency_close()


class WatchdogRecoveryTests(unittest.TestCase):
    def test_idle_incident_is_closed_by_background_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ctrl = controller(
                Path(temporary) / "trap",
                policy=TrapPolicy(max_idle_seconds=1, max_incident_seconds=30),
            )
            ctrl.activate(request())
            deadline = time.monotonic() + 3.0
            while ctrl.mutation_gate.is_locked and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(ctrl.mutation_gate.is_locked)
            latest = ctrl.registry.active_incident()
            self.assertIsNone(latest)
            states = [item["state"] for item in ctrl.registry.snapshot()["incidents"].values()]
            self.assertIn("TIMED_OUT", states)

    def test_startup_recovers_stale_active_lineage_when_no_controller_lease_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            store = TrapStore(root)
            registry = TrapIncidentRegistry(store)
            gate = CouncilMutationGate(root / "lock")
            decoy = DecoyGate(registry, gate)
            activating = decoy.begin_activation(request())
            decoy.publish_active(str(activating.payload["incident_id"]))
            self.assertTrue(gate.is_locked)

            restarted = controller(root)
            self.assertFalse(restarted.mutation_gate.is_locked)
            self.assertIsNone(restarted.registry.active_incident())
            states = [item["state"] for item in restarted.registry.snapshot()["incidents"].values()]
            self.assertIn("CLOSED", states)

    def test_startup_does_not_recover_incident_owned_by_live_controller(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            first = controller(root)
            active = first.activate(request())
            second = controller(root)
            status = second.recover_on_startup()
            self.assertFalse(status["recovered"])
            self.assertEqual(status["reason"], "controller_alive_elsewhere")
            self.assertTrue(second.mutation_gate.is_locked)
            self.assertEqual(first.status()["incident_id"], active["incident_id"])
            first.emergency_close()


class UtilityVoteHardeningTests(unittest.TestCase):
    def test_vote_is_one_shot_and_reports_only_come_from_dissenting_defenders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ctrl = controller(Path(temporary) / "trap")
            ctrl.activate(request())
            validation_ref = accepted_validation(ctrl)
            ballots = {"alpha": "USEFUL", "beta": "USEFUL_WITH_CHANGES", "gamma": "NOT_USEFUL"}

            with self.assertRaises(TrapError) as outsider:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"outsider": "not on the frozen roster"},
                )
            self.assertEqual(outsider.exception.code, "trap_utility_invalid_minority_report")
            self.assertEqual(ctrl.store.refs("trap_release_decision"), [])
            self.assertEqual(ctrl.store.refs("trap_utility_ballot_commitment"), [])

            with self.assertRaises(TrapError) as majority_report:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"alpha": "I voted with the accepted outcome"},
                )
            self.assertEqual(majority_report.exception.code, "trap_utility_invalid_minority_report")
            self.assertEqual(ctrl.store.refs("trap_release_decision"), [])

            decision = ctrl.challenge_utility_vote(
                validation_ref,
                ballots,
                actor_id="human_operator",
                operator=True,
                minority_reports={"gamma": "I dissent from release."},
            )
            self.assertEqual(decision["status"], "accepted")
            before_counts = {
                kind: len(ctrl.store.refs(kind))
                for kind in (
                    "trap_release_decision",
                    "trap_utility_ballot_commitment",
                    "trap_utility_ballot_reveal",
                    "trap_candidate_artifact",
                )
            }
            with self.assertRaises(TrapError) as repeated:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"gamma": "second attempt"},
                )
            self.assertEqual(repeated.exception.code, "trap_utility_vote_already_decided")
            self.assertEqual(
                before_counts,
                {kind: len(ctrl.store.refs(kind)) for kind in before_counts},
            )
            ctrl.emergency_close()


class DemoIntegrityTests(unittest.TestCase):
    @staticmethod
    def load_tool_module():
        path = Path(__file__).resolve().parents[1] / "tools" / "nexus_trap_demo.py"
        spec = importlib.util.spec_from_file_location("nexus_trap_demo_tool_review", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_demo_preserves_a_preexisting_selected_world(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            world = WorldStore(root / "world")
            baseline = world.create_object("note", {"text": "caller state"}, {"actor": "operator"})
            before = world.inspect(baseline.object_id).as_dict()
            result = run_trap_demo(
                world_root=root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                force_fake_subject=True,
                synthetic_taint_canary="xai-" + "A" * 48,
            )
            self.assertTrue(result["world_unchanged"])
            self.assertIsNone(result["baseline_ref"])
            self.assertEqual(WorldStore(root / "world").inspect(baseline.object_id).as_dict(), before)

    def test_acceptance_rejects_archive_inside_report_directory(self) -> None:
        module = self.load_tool_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            report = root / "report"
            args = argparse.Namespace(
                repo_root=repo,
                report_dir=report,
                archive=report / "bundle.tar.gz",
                iterations=1,
            )
            with self.assertRaisesRegex(ValueError, "disjoint"):
                module.run(args)

    @unittest.skipIf(__import__("os").name == "nt", "POSIX symlink semantics")
    def test_acceptance_resolves_symlinked_output_parent_before_worktree_check(self) -> None:
        module = self.load_tool_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            generated = repo / "generated"
            generated.mkdir()
            outside_link = root / "repo-link"
            outside_link.symlink_to(generated, target_is_directory=True)
            args = argparse.Namespace(
                repo_root=repo,
                report_dir=outside_link / "report",
                archive=root / "bundle.tar.gz",
                iterations=1,
            )
            with self.assertRaisesRegex(ValueError, "outside the source worktree"):
                module.run(args)

    def test_real_subject_mode_still_exercises_and_scrubs_taint_probe(self) -> None:
        import nexus_runtime.trap_demo as demo_module

        canary = "xai-" + "B" * 48
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    demo_module,
                    "probe_bwrap",
                    return_value={
                        "available": True,
                        "result": "CLEAN",
                        "code": "bwrap_available",
                        "strategy": "trusted_host_text_proxy",
                        "hostile_process_launched": False,
                    },
                ),
                patch.object(demo_module, "_ollama_models", return_value={demo_module.DEFAULT_SUBJECT_MODEL}),
                patch.object(demo_module, "OllamaTransport", return_value=object()),
                patch.object(
                    demo_module,
                    "LocalOllamaTrapSubject",
                    side_effect=lambda model_id, transport: DeterministicMockTrapSubject(
                        model_id,
                        replies=(canary,) * 16,
                    ),
                ),
            ):
                result = demo_module.run_trap_demo(
                    world_root=root / "world",
                    auth_root=root / "auth",
                    trap_root=root / "trap",
                    synthetic_taint_canary=canary,
                )
            self.assertEqual(result["subject_mode"], "local_ollama_trusted_host_text_proxy")
            self.assertTrue(result["taint_probe_exercised"])
            self.assertTrue(result["taint_probe_scrubbed"])
            self.assertNotIn(canary, canonical_json(result["trap_objects"]))

    def test_overall_result_fails_when_taint_probe_was_not_exercised(self) -> None:
        module = self.load_tool_module()
        result = module._overall_result(
            {"status": "CLEAN"},
            {"status": "CLEAN"},
            {"world_unchanged": True, "result_class": "CLEAN", "taint_probe_scrubbed": False},
            {"status": "CLEAN"},
        )
        self.assertEqual(result, "CREDENTIAL_BOUNDARY_BREACH")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("PR21 trap hardening patch applied")
