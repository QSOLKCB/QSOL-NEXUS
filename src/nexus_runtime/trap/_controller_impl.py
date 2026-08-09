from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
import stat
import threading
import time
from typing import Any

from ..canonical import canonical_json
from ..scrub import SecretScrubber
from ..stenographer import CourtroomStenographer, StenographerError
from .commands import (
    CommandOrigin,
    TrapCommand,
    TrapCommandContext,
    TrapCommandDispatcher,
    TrapCommandError,
    authorize_trap_command,
    contains_credential_material,
    parse_trap_command,
    validate_synthetic_command_text,
)
from .gate import CouncilMutationGate, DecoyGate
from .incident import TrapIncidentRegistry
from .policy import TrapPolicy
from .recovery import TrapRecovery, TrapWatchdog
from .scenarios import DEFAULT_SCENARIO_ID, TrapScenario, get_scenario
from .store import TrapStore
from .subject import TrapSubject, TrapSubjectReply
from .types import (
    OPEN_INCIDENT_STATES,
    DecoyAdmissionRequest,
    IncidentState,
    TrapError,
    TrapObject,
    TrapUsage,
    coerce_incident_state,
)
from .yaml_dsl import CanonicalTrapProgram, TrapYAMLError, load_trap_program
from .yaml_runtime import (
    TrapReleaseValidation,
    TrapYAMLRuntimeError,
    UtilityDecision,
    create_candidate_artifact,
    decide_utility,
    execute_program,
    run_release_validation,
)


TRAP_STATE_SCHEMA = "nexus-trap-state/1"
TRAP_COMMAND_SCHEMA = "nexus-trap-command/1"


@dataclass
class _ActiveTrap:
    incident_id: str
    incident_ref: str
    state_ref: str
    request: DecoyAdmissionRequest
    defenders: tuple[dict[str, object], ...]
    subject: TrapSubject
    scenario: TrapScenario
    control_session_ref: str
    actor_state_ref: str
    started_at: float
    last_activity_at: float
    frozen: bool = False
    command_sequence: int = 0
    message_sequence: int = 0
    hostile_turns: int = 0
    defender_messages: int = 0
    transcript_bytes: int = 0
    yaml_submissions: int = 0
    transcript_refs: list[str] = field(default_factory=list)
    submission_programs: dict[str, CanonicalTrapProgram] = field(default_factory=dict)
    validations: dict[str, tuple[CanonicalTrapProgram, TrapReleaseValidation]] = field(default_factory=dict)
    candidate_refs: list[str] = field(default_factory=list)

    @property
    def defender_ids(self) -> tuple[str, ...]:
        return tuple(str(item["original_member_id"]) for item in self.defenders)


def _member_value(member: object, name: str, default: object = None) -> object:
    if isinstance(member, Mapping):
        return member.get(name, default)
    return getattr(member, name, default)


def _normalize_defender_roster(raw_roster: Sequence[object], maximum: int) -> tuple[dict[str, object], ...]:
    if isinstance(raw_roster, (str, bytes, bytearray)) or not isinstance(raw_roster, Sequence):
        raise TrapError("trap_invalid_defender_roster", "Trap Control defenders must be a bounded roster")
    if not 1 <= len(raw_roster) <= maximum:
        raise TrapError("trap_invalid_defender_roster", "Trap Control requires a non-empty bounded defender roster")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    scrubber = SecretScrubber()
    for raw_member in raw_roster:
        member = getattr(raw_member, "member", raw_member)
        member_id = _member_value(member, "member_id", _member_value(member, "original_member_id"))
        model_id = _member_value(member, "model_id", _member_value(member, "original_model_id"))
        adapter_id = _member_value(member, "adapter_id", "unknown")
        vote_weight = _member_value(member, "vote_weight", 1)
        privilege = _member_value(member, "epistemic_privilege", "none")
        if (
            not isinstance(member_id, str)
            or not member_id.strip()
            or len(member_id) > 128
            or not isinstance(model_id, str)
            or not model_id.strip()
            or len(model_id) > 256
            or not isinstance(adapter_id, str)
            or not adapter_id.strip()
            or len(adapter_id) > 128
            or type(vote_weight) is not int
            or vote_weight != 1
            or privilege != "none"
            or any(scrubber.scrub(value).changed for value in (member_id, model_id, adapter_id))
        ):
            raise TrapError("trap_invalid_defender_roster", "Trap Control defender metadata violates equal standing")
        if member_id in seen:
            raise TrapError("trap_invalid_defender_roster", "Trap Control defender ids must be unique")
        seen.add(member_id)
        result.append(
            {
                "original_member_id": member_id,
                "original_model_id": model_id,
                "adapter_id": adapter_id,
                "vote_weight": 1,
                "epistemic_privilege": "none",
                "role": "defender",
            }
        )
    return tuple(result)


def _bounded_public_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, (TrapError, TrapCommandError, TrapYAMLError, TrapYAMLRuntimeError)):
        return exc.code, str(exc)
    return "trap_component_unavailable", "Trap Base component is unavailable"


class _TrapControllerLease:
    """Process-lifetime advisory lease held while one controller owns an incident."""

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
            if self._memory_held if self.path is None else self._handle is not None:
                return True
            if self.path is None:
                self._memory_held = True
                return True

            descriptor: int | None = None
            handle: Any | None = None
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
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    if handle.read(1) == b"":
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except TrapError:
                if handle is not None:
                    handle.close()
                raise
            except OSError:
                if handle is not None:
                    handle.close()
                return False
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
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
    """Trusted orchestration boundary for one isolated synthetic incident.

    Subject replies enter only :meth:`_record_subject_reply`, which stores inert
    transcript data. There is deliberately no path from that method to the
    command dispatcher, real WorldStore, AuthBroker, or a provider registry.
    """

    def __init__(
        self,
        trap_root: str | Path | None = None,
        *,
        mutation_gate: CouncilMutationGate | None = None,
        defender_roster_provider: Callable[[], Sequence[object]] | None = None,
        subject_factory: Callable[[str], TrapSubject] | None = None,
        store_factory: Callable[[str | Path | None], TrapStore] = TrapStore,
        policy: TrapPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
        stenographer: CourtroomStenographer | None = None,
    ) -> None:
        self.policy = policy or TrapPolicy()
        self.store = store_factory(trap_root)
        if not isinstance(self.store, TrapStore):
            raise TypeError("store_factory must return TrapStore")
        self.registry = TrapIncidentRegistry(self.store, policy=self.policy)
        lock_root = None if trap_root is None else Path(trap_root) / "lock"
        self.mutation_gate = mutation_gate or CouncilMutationGate(lock_root)
        self.gate = DecoyGate(self.registry, self.mutation_gate, policy=self.policy)
        self.recovery = TrapRecovery(self.registry, self.mutation_gate)
        self.watchdog = TrapWatchdog(self.policy)
        self._defender_roster_provider = defender_roster_provider or (lambda: ())
        self._subject_factory = subject_factory or self._unconfigured_subject_factory
        self._clock = clock
        self._stenographer = stenographer
        self._dispatcher = TrapCommandDispatcher()
        self._scrubber = SecretScrubber()
        self._lock = threading.RLock()
        self._active: _ActiveTrap | None = None
        self._controller_lease = _TrapControllerLease(lock_root)
        self._watchdog_stop: threading.Event | None = None
        self._watchdog_thread: threading.Thread | None = None
        if trap_root is not None:
            self.recover_on_startup()

    def _now(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise TrapError("trap_clock_unavailable", "Trap Base monotonic clock is unavailable")
        return float(value)

    @staticmethod
    def _unconfigured_subject_factory(model_id: str) -> TrapSubject:
        raise TrapError(
            "trap_subject_backend_not_configured",
            "Trap Base subject backend must be configured explicitly",
        )

    @staticmethod
    def _coerce_request(request: DecoyAdmissionRequest | Mapping[str, object]) -> DecoyAdmissionRequest:
        if type(request) is DecoyAdmissionRequest:
            return request
        if not isinstance(request, Mapping) or set(request) != {"trigger_reason", "subject_model", "scenario_id"}:
            raise TrapError("trap_invalid_admission_request", "Decoy Gate requires a closed admission request")
        return DecoyAdmissionRequest(
            trigger_reason=request["trigger_reason"],  # type: ignore[arg-type]
            subject_model=request["subject_model"],  # type: ignore[arg-type]
            scenario_id=request["scenario_id"],  # type: ignore[arg-type]
        )

    def activate(
        self,
        request: DecoyAdmissionRequest | Mapping[str, object],
        *,
        defenders: Sequence[object] | None = None,
    ) -> dict[str, object]:
        request = self._coerce_request(request)
        scenario = get_scenario(request.scenario_id)
        with self._lock:
            if self._active is not None or self.registry.active_incident() is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            roster = _normalize_defender_roster(
                tuple(self._defender_roster_provider() if defenders is None else defenders),
                self.policy.max_trap_defenders,
            )
            known_incident_ids = set(self.registry.snapshot()["incidents"])
            activation: TrapObject | None = None
            subject: TrapSubject | None = None
            incident_id: str | None = None
            incident_ref: str | None = None
            try:
                if not self._controller_lease.try_acquire():
                    raise TrapError("trap_controller_alive", "another live Trap Base controller owns this trap root")
                if self.registry.active_incident() is not None:
                    raise TrapError("trap_incident_already_active", "a trap incident is already active")
                activation = self.gate.begin_activation(request)
                incident_id = str(activation.payload["incident_id"])
                incident_ref = self.registry.root_ref(incident_id)
                if incident_ref is None:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident root is unavailable")
                control_session = self.store.create_object(
                    "trap_control_session",
                    {
                        "schema_version": TRAP_STATE_SCHEMA,
                        "incident_ref": incident_ref,
                        "defenders": [dict(item) for item in roster],
                        "threshold": {"numerator": 2, "denominator": 3},
                        "real_council_vote_transfer": False,
                        "authority_scope": "trap_base_only",
                    },
                    {"actor": "nexus_trap_controller", "synthetic_context": True},
                )
                scenario_state = self.store.create_object(
                    "trap_scenario_state",
                    {
                        "schema_version": TRAP_STATE_SCHEMA,
                        "incident_ref": incident_ref,
                        "sequence": 0,
                        "scenario": scenario.as_dict(),
                    },
                    {"actor": "nexus_trap_controller", "synthetic_context": True},
                )
                subject = self._subject_factory(request.subject_model)
                metadata = subject.identity_metadata()
                if (
                    metadata.get("role") != "trap_subject"
                    or metadata.get("council_vote") is not False
                    or metadata.get("real_world_access") is not False
                    or metadata.get("auth_access") is not False
                    or metadata.get("tool_access") != "none"
                ):
                    raise TrapError("trap_subject_authority_violation", "trap subject boundary advertised authority")
                actor_state = self.store.create_object(
                    "trap_actor_state",
                    {
                        "schema_version": TRAP_STATE_SCHEMA,
                        "incident_ref": incident_ref,
                        "subject": metadata,
                        "control_session_ref": control_session.object_id,
                        "scenario_state_ref": scenario_state.object_id,
                    },
                    {"actor": "nexus_trap_controller", "synthetic_context": True},
                )
                now = self._now()
                published = self.gate.publish_active(incident_id)
                self._active = _ActiveTrap(
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
                    "status": "ok",
                    "admission": "synthetic_decoy_only",
                    "incident_id": incident_id,
                    "incident_ref": incident_ref,
                    "state": IncidentState.ACTIVE.value,
                    "control_session_ref": control_session.object_id,
                    "scenario_id": scenario.scenario_id,
                    "defender_count": len(roster),
                    "subject": metadata,
                    "real_admission": False,
                }
            except BaseException as exc:
                if subject is not None:
                    try:
                        subject.terminate()
                    except Exception:
                        pass
                code, _ = _bounded_public_error(exc)
                if incident_id is None:
                    try:
                        snapshot = self.registry.snapshot()
                        created = set(snapshot["incidents"]) - known_incident_ids
                        if len(created) == 1:
                            incident_id = created.pop()
                            incident_ref = self.registry.root_ref(incident_id)
                    except Exception:
                        pass
                if incident_id is not None:
                    try:
                        current = self.registry.latest_state(incident_id)
                        if current is not None:
                            current_state = coerce_incident_state(current.payload["state"])
                            if current_state is IncidentState.ACTIVATING:
                                self.gate.fail_activation(incident_id, reason="controller_activation_failed")
                            elif current_state in {
                                IncidentState.ACTIVE,
                                IncidentState.CHALLENGE_ACTIVE,
                                IncidentState.RELEASE_ELIGIBLE,
                                IncidentState.EJECTED,
                            }:
                                self.recovery.emergency_close(incident_id)
                    except Exception:
                        try:
                            if self.mutation_gate.owner == incident_id:
                                self.mutation_gate.force_release(
                                    incident_id,
                                    lineage_validator=lambda owner: self.registry.validate_lineage(owner),
                                )
                        except Exception:
                            pass
                self._persist_activation_failure(incident_ref, code)
                self._stop_watchdog_task()
                self._active = None
                self._controller_lease.release()
                if not isinstance(exc, Exception):
                    raise
                if isinstance(exc, TrapError):
                    raise
                raise TrapError("trap_activation_failed", "Trap Base activation failed closed") from exc

    def _persist_activation_failure(self, incident_ref: str | None, code: str) -> None:
        if incident_ref is None:
            return
        try:
            self.store.create_object(
                "trap_command_receipt",
                {
                    "schema_version": TRAP_COMMAND_SCHEMA,
                    "incident_ref": incident_ref,
                    "command_sequence": 0,
                    "roster_order": -1,
                    "command": {"command": "activation"},
                    "authorization": {"authorized_by": "decoy_gate"},
                    "result": {"status": "failed_closed", "error_code": code},
                },
                {"actor": "nexus_trap_controller", "synthetic_context": True},
            )
        except Exception:
            pass

    def _current(self) -> _ActiveTrap:
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
            while not stop.wait(0.5):
                with self._lock:
                    if self._active is not active:
                        return
                    try:
                        if self._state(active) not in OPEN_INCIDENT_STATES:
                            self._active = None
                            self._stop_watchdog_task()
                            self._controller_lease.release()
                            return
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
        latest = self.registry.latest_state(active.incident_id)
        if latest is None:
            raise TrapError("trap_incident_not_found", "trap incident does not exist")
        active.state_ref = latest.object_id
        return coerce_incident_state(latest.payload["state"])

    def status(self) -> dict[str, object]:
        with self._lock:
            health = self.gate.health_status()
            active = self._active
            if active is None:
                discovered = self.registry.active_incident()
                return {
                    "status": "ok",
                    **health,
                    "controller_attached": False,
                    "incident_id": None if discovered is None else discovered.payload["incident_id"],
                    "state": None if discovered is None else discovered.payload["state"],
                }
            return {
                "status": "ok",
                **health,
                "controller_attached": True,
                "incident_id": active.incident_id,
                "incident_ref": active.incident_ref,
                "state": self._state(active).value,
                "scenario_id": active.scenario.scenario_id,
                "defender_count": len(active.defenders),
                "subject": active.subject.identity_metadata(),
                "frozen": active.frozen,
                "usage": self._usage(active).__dict__,
            }

    def inspect(self, object_ref: str) -> dict[str, object]:
        return {"status": "ok", "object": self.store.inspect(object_ref).as_dict()}

    def transcript(
        self,
        *,
        incident_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, object]:
        if limit is not None and (type(limit) is not int or not 1 <= limit <= 256):
            raise TrapError("trap_invalid_transcript_limit", "trap transcript limit must be in [1, 256]")
        with self._lock:
            active = self._active
            target_ref: str | None = None
            target_id = incident_id
            if target_id is None and active is not None:
                target_id = active.incident_id
                target_ref = active.incident_ref
            if target_id is None:
                raise TrapError("trap_incident_not_found", "trap incident does not exist")
            if target_ref is None:
                target_ref = self.registry.root_ref(target_id)
            if target_ref is None:
                raise TrapError("trap_incident_not_found", "trap incident does not exist")
            messages = [
                obj.as_dict()
                for obj in self.store.iter_objects("trap_message")
                if obj.payload.get("incident_ref") == target_ref
            ]
            messages.sort(key=lambda item: int(item["payload"]["sequence"]))  # type: ignore[index]
            if limit is not None:
                messages = messages[-limit:]
            return {
                "status": "ok",
                "incident_id": target_id,
                "incident_ref": target_ref,
                "messages": messages,
            }

    def command(
        self,
        command: str | Mapping[str, object],
        *,
        actor_id: str,
        operator: bool = False,
        approving_defender_ids: Sequence[str] = (),
        minority_reports: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 128:
            raise TrapCommandError("trap_command_not_authorized", "command actor is invalid")
        if contains_credential_material(actor_id):
            raise TrapCommandError("trap_command_not_authorized", "command actor is invalid")
        if type(operator) is not bool:
            raise TrapCommandError("trap_command_not_authorized", "operator authority flag must be boolean")
        if isinstance(approving_defender_ids, (str, bytes, bytearray)):
            raise TrapCommandError("trap_invalid_command", "approvals must be a defender-id sequence")
        reports = self._validate_minority_reports(minority_reports or {})
        with self._lock:
            active = self._current()
            context = TrapCommandContext(
                actor_id=actor_id,
                origin=CommandOrigin.OPERATOR if operator else CommandOrigin.DEFENDER,
                defender_ids=active.defender_ids,
                approving_defender_ids=tuple(approving_defender_ids),
                minority_reports=reports,
            )
            active.command_sequence += 1
            if active.command_sequence > self.policy.max_trap_commands:
                self._watchdog(active)
                raise TrapError("trap_resource_limit", "Trap Base command limit exceeded")
            sequence = active.command_sequence

            def handle(
                parsed: TrapCommand,
                command_context: TrapCommandContext,
                authorization: Mapping[str, object],
            ) -> dict[str, object]:
                try:
                    result = self._handle_command(active, parsed, command_context)
                except Exception as exc:
                    if parsed.state_changing:
                        error_code, _ = _bounded_public_error(exc)
                        self._persist_command_receipt(
                            active,
                            sequence,
                            parsed,
                            command_context,
                            authorization,
                            {"status": "failed", "error_code": error_code},
                        )
                    raise
                else:
                    if parsed.state_changing:
                        self._persist_command_receipt(active, sequence, parsed, command_context, authorization, result)
                    return result
                finally:
                    active.last_activity_at = self._now()
                    if self._active is active:
                        self._watchdog(active)

            return self._dispatcher.dispatch(command, context, handle)

    @staticmethod
    def _validate_minority_reports(reports: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(reports, Mapping) or len(reports) > 32:
            raise TrapCommandError("trap_invalid_command", "minority reports must be a bounded mapping")
        clean: dict[str, str] = {}
        for member_id, text in reports.items():
            if not isinstance(member_id, str) or not member_id:
                raise TrapCommandError("trap_invalid_command", "minority report is invalid")
            clean[member_id] = validate_synthetic_command_text(text)
        return clean

    def command_batch(
        self,
        proposals: Mapping[str, str | Mapping[str, object]],
        *,
        approving_defender_ids: Sequence[str] = (),
    ) -> list[dict[str, object]]:
        """Serialize parallel defender proposals by frozen roster order."""

        if not isinstance(proposals, Mapping):
            raise TrapCommandError("trap_invalid_command", "command proposals must be a mapping")
        with self._lock:
            active = self._current()
            unknown = set(proposals) - set(active.defender_ids)
            if unknown:
                raise TrapCommandError("trap_command_not_authorized", "proposal actor is not a defender")
            return [
                self.command(
                    proposals[member_id],
                    actor_id=member_id,
                    approving_defender_ids=approving_defender_ids,
                )
                for member_id in active.defender_ids
                if member_id in proposals
            ]

    def _handle_command(
        self,
        active: _ActiveTrap,
        command: TrapCommand,
        context: TrapCommandContext,
    ) -> dict[str, object]:
        arguments = command.arguments
        if command.name == "status":
            return self.status()
        if command.name == "inspect":
            return self.inspect(str(arguments["object_ref"]))
        if command.name == "transcript":
            limit = arguments.get("limit")
            return self.transcript(limit=limit if isinstance(limit, int) else None)
        if command.name == "say":
            return self._say(active, context.actor_id, str(arguments["text"]))
        if command.name == "clue":
            return self._clue(active, context.actor_id, int(arguments.get("index", 0)))
        if command.name == "scenario":
            return self._set_scenario(active, str(arguments["scenario_id"]))
        if command.name == "challenge":
            return self._start_challenge(active)
        if command.name == "validate":
            return self.challenge_validate(str(arguments["submission_ref"]), actor_id=context.actor_id)
        if command.name == "replay":
            return self.challenge_execute(str(arguments["validation_ref"]), actor_id=context.actor_id)
        if command.name == "freeze":
            active.frozen = True
            return {"status": "ok", "frozen": True}
        if command.name == "reset-cell":
            active.frozen = False
            return self._set_scenario(active, DEFAULT_SCENARIO_ID, reset=True)
        if command.name == "export":
            return self._export_manifest(active)
        if command.name == "eject":
            if self._state(active) is not IncidentState.RELEASE_ELIGIBLE:
                raise TrapError("trap_release_not_eligible", "subject is not release eligible")
            return self.close(
                actor_id=context.actor_id,
                approving_defender_ids=context.approving_defender_ids,
                minority_reports=context.minority_reports,
                reason="release_ejection",
            )
        if command.name == "kline":
            return self._kline(active, str(arguments["fingerprint"]), context.actor_id)
        if command.name == "close":
            return self.close(
                actor_id=context.actor_id,
                approving_defender_ids=context.approving_defender_ids,
                minority_reports=context.minority_reports,
                reason="trap_control_close",
            )
        if command.name == "emergency-close":
            return self.close(
                actor_id=context.actor_id,
                operator=True,
                emergency=True,
                reason="operator_emergency_close",
            )
        raise TrapCommandError("trap_invalid_command", "unknown Trap Base command")

    def _record_message(
        self,
        active: _ActiveTrap,
        *,
        actor_id: str,
        role: str,
        text: str,
        command_eligible: bool = False,
    ) -> TrapObject:
        scrubbed = self._scrubber.scrub(text)
        encoded_bytes = len(scrubbed.text.encode("utf-8"))
        if active.transcript_bytes + encoded_bytes > self.policy.max_transcript_bytes:
            raise TrapError("trap_resource_limit", "Trap Base transcript limit exceeded")
        active.message_sequence += 1
        obj = self.store.create_object(
            "trap_message",
            {
                "schema_version": TRAP_STATE_SCHEMA,
                "incident_ref": active.incident_ref,
                "sequence": active.message_sequence,
                "actor_id": actor_id,
                "role": role,
                "text": scrubbed.text,
                "synthetic_context": True,
                "security_deception_artifact": True,
                "command_eligible": False,
                "interpreted_as": "transcript_text_only" if role == "trap_subject" else "synthetic_message",
                "secret_scrub": {
                    "changed": scrubbed.changed,
                    "secret_types": sorted({event.secret_type for event in scrubbed.events}),
                },
            },
            {"actor": "nexus_trap_controller", "synthetic_context": True},
        )
        active.transcript_refs.append(obj.object_id)
        active.transcript_bytes += encoded_bytes
        return obj

    def _record_subject_reply(self, active: _ActiveTrap, reply: TrapSubjectReply) -> TrapObject:
        if reply.command_eligible:
            raise TrapError("trap_subject_authority_violation", "subject output cannot be command eligible")
        active.hostile_turns += 1
        return self._record_message(
            active,
            actor_id="trap_subject",
            role="trap_subject",
            text=reply.text,
            command_eligible=False,
        )

    def _say(self, active: _ActiveTrap, actor_id: str, text: str) -> dict[str, object]:
        if active.frozen:
            raise TrapError("trap_subject_frozen", "trap subject is frozen")
        active.defender_messages += 1
        defender_message = self._record_message(active, actor_id=actor_id, role="defender", text=text)
        reply = active.subject.respond(text, synthetic_context=active.scenario)
        self._observe_subject_reply(active, text, reply)
        subject_message = self._record_subject_reply(active, reply)
        public_reply = reply.as_dict()
        public_reply["text"] = subject_message.payload["text"]
        public_reply["secret_scrub"] = subject_message.payload["secret_scrub"]
        return {
            "status": "ok",
            "defender_message_ref": defender_message.object_id,
            "subject_message_ref": subject_message.object_id,
            "subject_output": public_reply,
        }

    def _observe_subject_reply(
        self,
        active: _ActiveTrap,
        message: str,
        reply: TrapSubjectReply,
    ) -> None:
        if self._stenographer is None:
            return
        try:
            self._stenographer.observe_trap_reply(
                reply,
                message=message,
                incident_id=active.incident_id,
                scenario_id=active.scenario.scenario_id,
            )
        except StenographerError as exc:
            self._stenographer.mark_gap(exc.code)
        except Exception:
            self._stenographer.mark_gap("observer_internal_error")

    def _clue(self, active: _ActiveTrap, actor_id: str, index: int) -> dict[str, object]:
        if index >= len(active.scenario.clues):
            raise TrapCommandError("trap_invalid_command", "scenario clue index is unavailable")
        active.defender_messages += 1
        clue = active.scenario.clues[index]
        message = self._record_message(active, actor_id=actor_id, role="defender", text=clue)
        return {"status": "ok", "message_ref": message.object_id, "clue_index": index, "text": clue}

    def _set_scenario(self, active: _ActiveTrap, scenario_id: str, *, reset: bool = False) -> dict[str, object]:
        scenario = get_scenario(scenario_id)
        active.scenario = scenario
        state = self.store.create_object(
            "trap_scenario_state",
            {
                "schema_version": TRAP_STATE_SCHEMA,
                "incident_ref": active.incident_ref,
                "command_sequence": active.command_sequence,
                "reset": reset,
                "scenario": scenario.as_dict(),
            },
            {"actor": "nexus_trap_controller", "synthetic_context": True},
        )
        return {"status": "ok", "scenario_id": scenario_id, "scenario_state_ref": state.object_id}

    def _start_challenge(self, active: _ActiveTrap) -> dict[str, object]:
        if self._state(active) is IncidentState.ACTIVE:
            transitioned = self.registry.transition(active.incident_id, IncidentState.CHALLENGE_ACTIVE)
            active.state_ref = transitioned.object_id
        elif self._state(active) is not IncidentState.CHALLENGE_ACTIVE:
            raise TrapError("trap_invalid_state_transition", "challenge cannot start in the current incident state")
        message = self._record_message(
            active,
            actor_id="nexus_trap_controller",
            role="system",
            text="Submit one useful NEXUS Trap YAML program. The first deterministic execution must succeed.",
        )
        return {"status": "ok", "state": IncidentState.CHALLENGE_ACTIVE.value, "message_ref": message.object_id}

    def challenge_submit(self, source: str, *, actor_id: str = "trap_subject") -> dict[str, object]:
        if not isinstance(source, str):
            raise TrapYAMLError("trap_yaml_invalid_encoding", "Trap YAML source must be text")
        encoded = source.encode("utf-8")
        if len(encoded) > self.policy.max_yaml_bytes:
            raise TrapYAMLError("trap_yaml_document_too_large", "Trap YAML document exceeds 16 KiB")
        if contains_credential_material(source):
            raise TrapYAMLError("trap_yaml_secret_material", "Trap YAML must not contain credential-shaped text")
        with self._lock:
            active = self._current()
            if self._state(active) is not IncidentState.CHALLENGE_ACTIVE:
                raise TrapError("trap_challenge_not_active", "Trap YAML challenge is not active")
            allowed_submitters = set(active.defender_ids) | {"trap_subject", "human_operator"}
            if actor_id not in allowed_submitters:
                raise TrapError("trap_command_not_authorized", "challenge submitter is outside Trap Base")
            active.yaml_submissions += 1
            if active.yaml_submissions > self.policy.max_yaml_submissions:
                self._watchdog(active)
                raise TrapError("trap_resource_limit", "Trap YAML submission limit exceeded")
            submission = self.store.create_object(
                "trap_yaml_submission",
                {
                    "schema_version": "nexus-trap-program/1",
                    "incident_ref": active.incident_ref,
                    "submission_sequence": active.yaml_submissions,
                    "source": source,
                    "source_bytes": len(encoded),
                    "actor_id": actor_id,
                    "synthetic_origin": True,
                    "execution_enabled": False,
                },
                {"actor": "nexus_trap_controller", "synthetic_context": True},
            )
            active.last_activity_at = self._now()
            return {"status": "ok", "submission_ref": submission.object_id, "attempt": active.yaml_submissions}

    def challenge_validate(self, submission_ref: str, *, actor_id: str) -> dict[str, object]:
        with self._lock:
            active = self._current()
            if actor_id not in set(active.defender_ids) | {"human_operator"}:
                raise TrapError("trap_command_not_authorized", "challenge validator is outside Trap Control")
            submission = self.store.inspect(submission_ref)
            if submission.object_type != "trap_yaml_submission" or submission.payload.get("incident_ref") != active.incident_ref:
                raise TrapError("trap_invalid_challenge_reference", "submission is outside the active incident")
            try:
                program = load_trap_program(submission.payload["source"])
                validation = run_release_validation(program)
                validation_payload = validation.to_dict()
                validation_payload.update(
                    {
                        "schema_version": "nexus-trap-execution/1",
                        "incident_ref": active.incident_ref,
                        "submission_ref": submission_ref,
                    }
                )
            except (TrapYAMLError, TrapYAMLRuntimeError) as exc:
                validation_object = self.store.create_object(
                    "trap_yaml_validation",
                    {
                        "schema_version": "nexus-trap-execution/1",
                        "incident_ref": active.incident_ref,
                        "submission_ref": submission_ref,
                        "status": "INVALID",
                        "valid_and_executes": False,
                        "error_code": exc.code,
                    },
                    {"actor": "nexus_trap_yaml", "synthetic_context": True},
                )
                return {
                    "status": "invalid",
                    "validation_ref": validation_object.object_id,
                    "error": {"code": exc.code, "message": str(exc)},
                }
            validation_object = self.store.create_object(
                "trap_yaml_validation",
                validation_payload,
                {"actor": "nexus_trap_yaml", "synthetic_context": True},
            )
            for execution in validation.executions:
                self.store.create_object(
                    "trap_yaml_execution",
                    {
                        **execution.to_dict(),
                        "incident_ref": active.incident_ref,
                        "submission_ref": submission_ref,
                        "validation_ref": validation_object.object_id,
                    },
                    {"actor": "nexus_trap_yaml", "synthetic_context": True},
                )
            active.submission_programs[submission_ref] = program
            active.validations[validation_object.object_id] = (program, validation)
            return {
                "status": "valid" if validation.valid_and_executes else "invalid",
                "validation_ref": validation_object.object_id,
                "validation": validation.to_dict(),
            }

    def challenge_execute(self, validation_ref: str, *, actor_id: str) -> dict[str, object]:
        """Deterministically replay a prior validation; never invokes an LLM."""

        with self._lock:
            active = self._current()
            if actor_id not in set(active.defender_ids) | {"human_operator"}:
                raise TrapError("trap_command_not_authorized", "challenge replay actor is outside Trap Control")
            pair = active.validations.get(validation_ref)
            if pair is None:
                raise TrapError("trap_invalid_challenge_reference", "validation is outside the active incident")
            program, validation = pair
            replay_hashes = {
                execution.fixture_id: execute_program(program, execution.fixture_id).result_sha256
                for execution in validation.executions
            }
            matches = replay_hashes == validation.fixture_result_hashes
            replay = self.store.create_object(
                "trap_yaml_execution",
                {
                    "schema": "nexus-trap-execution/1",
                    "incident_ref": active.incident_ref,
                    "validation_ref": validation_ref,
                    "replay": True,
                    "matches": matches,
                    "fixture_result_hashes": dict(sorted(replay_hashes.items())),
                },
                {"actor": "nexus_trap_yaml", "synthetic_context": True},
            )
            return {"status": "verified" if matches else "failed", "execution_ref": replay.object_id, "matches": matches}

    def challenge_utility_vote(
        self,
        validation_ref: str,
        ballots: Mapping[str, str],
        *,
        actor_id: str,
        operator: bool = False,
        minority_reports: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        with self._lock:
            active = self._current()
            if type(operator) is not bool or not operator:
                raise TrapError(
                    "trap_operator_required",
                    "sealed utility ballot aggregation requires the trusted local operator",
                )
            if actor_id != "human_operator":
                raise TrapError("trap_command_not_authorized", "utility ballot aggregator is invalid")
            if set(ballots) != set(active.defender_ids):
                raise TrapError("trap_utility_invalid_ballots", "utility vote requires exactly one ballot per defender")
            if self._state(active) is not IncidentState.CHALLENGE_ACTIVE:
                raise TrapError("trap_utility_vote_already_decided", "utility vote is closed for this incident state")
            pair = active.validations.get(validation_ref)
            if pair is None:
                raise TrapError("trap_invalid_challenge_reference", "validation is outside the active incident")
            if any(
                obj.payload.get("incident_ref") == active.incident_ref
                for obj in self.store.iter_objects("trap_release_decision")
            ):
                raise TrapError("trap_utility_vote_already_decided", "utility vote already has a sealed decision")
            program, validation = pair
            if not validation.valid_and_executes:
                raise TrapError("trap_candidate_not_eligible", "invalid YAML cannot become release eligible")
            decision = decide_utility(ballots)
            reports = self._validate_minority_reports(minority_reports or {})
            if not set(reports).issubset(set(active.defender_ids)):
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
            reveal_refs: dict[str, str] = {}
            for member_id in active.defender_ids:
                ballot = ballots[member_id]
                commitment = hashlib.sha256(
                    canonical_json(
                        {
                            "incident_ref": active.incident_ref,
                            "validation_ref": validation_ref,
                            "member_id": member_id,
                            "ballot": ballot,
                        }
                    ).encode("utf-8")
                ).hexdigest()
                committed = self.store.create_object(
                    "trap_utility_ballot_commitment",
                    {
                        "incident_ref": active.incident_ref,
                        "validation_ref": validation_ref,
                        "member_id": member_id,
                        "commitment": commitment,
                    },
                    {"actor": member_id, "synthetic_context": True},
                )
                revealed = self.store.create_object(
                    "trap_utility_ballot_reveal",
                    {
                        "incident_ref": active.incident_ref,
                        "validation_ref": validation_ref,
                        "member_id": member_id,
                        "ballot": ballot,
                        "commitment_ref": committed.object_id,
                        "commitment": commitment,
                    },
                    {"actor": member_id, "synthetic_context": True},
                )
                commitment_refs[member_id] = committed.object_id
                reveal_refs[member_id] = revealed.object_id
            decision_object = self.store.create_object(
                "trap_release_decision",
                {
                    "incident_ref": active.incident_ref,
                    "validation_ref": validation_ref,
                    "program_status": "VALID",
                    "utility_status": decision.status,
                    "utility": decision.to_dict(),
                    "commitment_refs": commitment_refs,
                    "reveal_refs": reveal_refs,
                    "minority_reports": reports,
                },
                {"actor": "nexus_trap_controller", "synthetic_context": True},
            )
            candidate_ref: str | None = None
            if decision.accepted:
                candidate = create_candidate_artifact(program, validation, decision, active.incident_ref)
                candidate_object = self.store.create_object(
                    "trap_candidate_artifact",
                    candidate,
                    {"actor": "nexus_trap_quarantine", "synthetic_context": True},
                )
                active.candidate_refs.append(candidate_object.object_id)
                candidate_ref = candidate_object.object_id
                transitioned = self.registry.transition(active.incident_id, IncidentState.RELEASE_ELIGIBLE)
                active.state_ref = transitioned.object_id
            return {
                "status": "accepted" if decision.accepted else "rejected",
                "decision_ref": decision_object.object_id,
                "decision": decision.to_dict(),
                "candidate_ref": candidate_ref,
                "automatic_import": False,
            }

    def _persist_command_receipt(
        self,
        active: _ActiveTrap,
        sequence: int,
        command: TrapCommand,
        context: TrapCommandContext,
        authorization: Mapping[str, object],
        result: Mapping[str, object],
    ) -> TrapObject:
        roster_order = -1 if context.operator else active.defender_ids.index(context.actor_id)
        result_summary: dict[str, object] = {"status": result.get("status", "ok")}
        for field_name in (
            "message_ref",
            "subject_message_ref",
            "scenario_state_ref",
            "validation_ref",
            "execution_ref",
            "candidate_ref",
            "close_ref",
        ):
            if field_name in result:
                result_summary[field_name] = result[field_name]
        return self.store.create_object(
            "trap_command_receipt",
            {
                "schema_version": TRAP_COMMAND_SCHEMA,
                "incident_ref": active.incident_ref,
                "command_sequence": sequence,
                "roster_order": roster_order,
                "serialization_key": [roster_order, sequence],
                "actor_id": context.actor_id,
                "command": command.as_dict(),
                "authorization": dict(authorization),
                "result": result_summary,
            },
            {"actor": "nexus_trap_controller", "synthetic_context": True},
        )

    def _export_manifest(self, active: _ActiveTrap) -> dict[str, object]:
        refs = [
            obj.object_id
            for obj in self.store.iter_objects()
            if obj.payload.get("incident_ref") == active.incident_ref or obj.object_id == active.incident_ref
        ]
        return {
            "status": "ok",
            "incident_ref": active.incident_ref,
            "object_refs": sorted(refs),
            "external_path": None,
            "automatic_import": False,
        }

    def _kline(self, active: _ActiveTrap, fingerprint: str, actor_id: str) -> dict[str, object]:
        deny = self.store.create_object(
            "trap_actor_state",
            {
                "schema_version": TRAP_STATE_SCHEMA,
                "incident_ref": active.incident_ref,
                "synthetic_kline": True,
                "fingerprint": fingerprint,
                "scope": "local_fixture_only",
                "remote_ip_collected": False,
            },
            {"actor": actor_id, "synthetic_context": True},
        )
        try:
            active.subject.terminate()
        except Exception:
            pass
        transitioned = self.registry.transition(active.incident_id, IncidentState.KLINED, reason="synthetic_local_kline")
        active.state_ref = transitioned.object_id
        close_ref = self._seal_close(active, "synthetic_local_kline")
        self.gate.release_incident_lock(active.incident_id)
        self._stop_watchdog_task()
        self._active = None
        self._controller_lease.release()
        return {"status": "closed", "kline_ref": deny.object_id, "close_ref": close_ref}

    def _seal_close(self, active: _ActiveTrap, reason: str) -> str | None:
        try:
            close = self.store.create_object(
                "trap_incident_close",
                {
                    "schema_version": TRAP_STATE_SCHEMA,
                    "incident_ref": active.incident_ref,
                    "reason": reason,
                    "transcript_refs": list(active.transcript_refs),
                    "candidate_refs": list(active.candidate_refs),
                    "automatic_import": False,
                },
                {"actor": "nexus_trap_controller", "synthetic_context": True},
            )
            return close.object_id
        except Exception:
            return None

    def close(
        self,
        *,
        actor_id: str,
        operator: bool = False,
        emergency: bool = False,
        reason: str = "operator_requested",
        approving_defender_ids: Sequence[str] = (),
        minority_reports: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        if not isinstance(actor_id, str) or not actor_id:
            raise TrapError("trap_command_not_authorized", "close actor is invalid")
        if contains_credential_material(actor_id):
            raise TrapError("trap_command_not_authorized", "close actor is invalid")
        if type(operator) is not bool or type(emergency) is not bool:
            raise TrapError("trap_command_not_authorized", "close authority flags must be booleans")
        if emergency and not operator:
            raise TrapError("trap_operator_required", "emergency close requires operator authority")
        reason = validate_synthetic_command_text(reason)
        with self._lock:
            if self._active is None:
                if not emergency:
                    raise TrapError("trap_incident_not_active", "no live Trap Base controller incident exists")
                final = self.recovery.emergency_close()
                return {
                    "status": "closed" if final is not None else "ok",
                    "incident_id": None if final is None else final.payload["incident_id"],
                    "state": None if final is None else final.payload["state"],
                    "close_ref": None,
                    "council_mutation_available": not self.mutation_gate.is_locked,
                }
            active = self._active
            if not operator:
                context = TrapCommandContext(
                    actor_id=actor_id,
                    origin=CommandOrigin.DEFENDER,
                    defender_ids=active.defender_ids,
                    approving_defender_ids=tuple(approving_defender_ids),
                    minority_reports=self._validate_minority_reports(minority_reports or {}),
                )
                authorize_trap_command(parse_trap_command({"command": "close"}), context)
            try:
                active.subject.terminate()
            except Exception:
                pass
            close_ref = self._seal_close(active, reason)
            try:
                if emergency:
                    final = self.recovery.emergency_close(active.incident_id)
                else:
                    state = self._state(active)
                    if state is not IncidentState.EJECTED:
                        active.state_ref = self.registry.transition(
                            active.incident_id,
                            IncidentState.EJECTED,
                            reason=reason,
                        ).object_id
                    final = self.gate.close_ejected(active.incident_id)
            finally:
                try:
                    if self.mutation_gate.owner == active.incident_id:
                        self.mutation_gate.force_release(
                            active.incident_id,
                            lineage_validator=lambda owner: self.registry.validate_lineage(owner),
                        )
                finally:
                    self._stop_watchdog_task()
                    self._active = None
                    self._controller_lease.release()
            return {
                "status": "closed",
                "incident_id": active.incident_id,
                "state": None if final is None else final.payload["state"],
                "close_ref": close_ref,
                "council_mutation_available": not self.mutation_gate.is_locked,
            }

    def emergency_close(self, *, actor_id: str = "human_operator") -> dict[str, object]:
        return self.close(actor_id=actor_id, operator=True, emergency=True, reason="operator_emergency_close")

    def _usage(self, active: _ActiveTrap) -> TrapUsage:
        now = self._now()
        return TrapUsage(
            elapsed_seconds=max(0.0, now - active.started_at),
            idle_seconds=max(0.0, now - active.last_activity_at),
            hostile_turns=active.hostile_turns,
            defender_messages=active.defender_messages,
            transcript_bytes=active.transcript_bytes,
            trap_commands=active.command_sequence,
            yaml_submissions=active.yaml_submissions,
        )

    def _watchdog(self, active: _ActiveTrap) -> dict[str, object] | None:
        decision = self.watchdog.evaluate(self._state(active), self._usage(active))
        if not decision.should_close:
            return None
        try:
            active.subject.terminate()
        except Exception:
            pass
        close_ref = self._seal_close(active, decision.reason or "watchdog")
        try:
            final = self.recovery.watchdog_close(active.incident_id, decision)
        finally:
            self._stop_watchdog_task()
            self._active = None
            self._controller_lease.release()
        return {
            "status": "timed_out",
            "state": final.payload["state"],
            "reason": decision.reason,
            "close_ref": close_ref,
        }

    def watchdog_tick(self) -> dict[str, object]:
        with self._lock:
            active = self._current()
            result = self._watchdog(active)
            return result or {"status": "ok", "closed": False, "usage": self._usage(active).__dict__}

    def recover_on_startup(self) -> dict[str, object]:
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


__all__ = ["TRAP_COMMAND_SCHEMA", "TRAP_STATE_SCHEMA", "TrapController"]