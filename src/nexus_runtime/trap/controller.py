from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
import threading
from typing import Any

from ._controller_impl import (
    TRAP_COMMAND_SCHEMA,
    TRAP_STATE_SCHEMA,
    TrapController as _TrapControllerImpl,
    _ActiveTrap,
    _bounded_public_error,
)
from .commands import (
    CommandOrigin,
    TrapCommand,
    TrapCommandContext,
    TrapCommandError,
    authorize_trap_command,
    contains_credential_material,
    parse_trap_command,
)
from .types import OPEN_INCIDENT_STATES, TrapError, coerce_incident_state


class TrapController(_TrapControllerImpl):
    """Trap controller with lifecycle hardening around blocking subject calls.

    The underlying implementation remains deliberately closed and deterministic.
    This facade adds the review-hardening invariants that require concurrency
    boundaries: subject inference never owns the controller state lock, terminal
    mutation ownership is recovered before the live-controller lease is dropped,
    and forked descendants cannot retain the parent's controller lease.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        register_at_fork = getattr(os, "register_at_fork", None)
        if callable(register_at_fork):
            register_at_fork(after_in_child=self._drop_inherited_controller_lease_after_fork)

    def _drop_inherited_controller_lease_after_fork(self) -> None:
        """Close the child's duplicate descriptor without unlocking the parent."""

        lease = self._controller_lease
        handle = getattr(lease, "_handle", None)
        lease._handle = None
        lease._memory_held = False
        lease._lock = threading.RLock()
        # A child must never continue using an incident owned by the parent.
        self._active = None
        self._watchdog_stop = None
        self._watchdog_thread = None
        self._lock = threading.RLock()
        if handle is not None:
            try:
                # Do not call lease.release(): flock(LOCK_UN) on a duplicated
                # open-file description would also unlock the live parent.
                handle.close()
            except Exception:
                pass

    def _require_same_open_incident(self, active: _ActiveTrap) -> None:
        if self._active is not active:
            raise TrapError("trap_incident_terminated", "Trap Base incident ended while the command was in flight")
        if self._state(active) not in OPEN_INCIDENT_STATES:
            raise TrapError("trap_incident_terminated", "Trap Base incident ended while the command was in flight")

    def _finalize_terminal_ownership(self, active: _ActiveTrap) -> bool:
        """Recover any stale mutation owner before relinquishing controller liveness."""

        latest = self.registry.latest_state(active.incident_id)
        if latest is None or coerce_incident_state(latest.payload["state"]) in OPEN_INCIDENT_STATES:
            return False
        try:
            self.recovery.recover_stale_active(controller_alive=False)
            if self.mutation_gate.is_locked:
                return False
        except Exception:
            # Keep both the attached controller and liveness lease so the
            # watchdog can retry rather than stranding a terminal mutation lock.
            return False
        try:
            self._controller_lease.release()
        except Exception:
            return False
        self._active = None
        self._stop_watchdog_task()
        return True

    def _start_watchdog_task(self, active: _ActiveTrap) -> None:
        self._stop_watchdog_task()
        stop = threading.Event()
        self._watchdog_stop = stop

        def worker() -> None:
            while not stop.wait(0.5):
                # The state lock is bounded: subject.respond() never owns it in
                # this facade, so a blocked model cannot starve watchdog timing.
                with self._lock:
                    if self._active is not active:
                        return
                    try:
                        if self._state(active) not in OPEN_INCIDENT_STATES:
                            if self._finalize_terminal_ownership(active):
                                return
                            continue
                        result = self._watchdog(active)
                    except Exception:
                        try:
                            active.subject.terminate()
                        except Exception:
                            pass
                        self._seal_close(active, "watchdog_worker_failure")
                        try:
                            self.recovery.emergency_close(active.incident_id)
                        except Exception:
                            pass
                        if self._finalize_terminal_ownership(active):
                            return
                        continue
                    if result is not None:
                        return

        thread = threading.Thread(
            target=worker,
            name=f"nexus-trap-watchdog-{active.incident_id[-12:]}",
            daemon=True,
        )
        self._watchdog_thread = thread
        thread.start()

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
        # Parse before any subject call. Public `say` keeps the original strict
        # credential/path/endpoint rejection boundary.
        parsed = parse_trap_command(command)
        with self._lock:
            active = self._current()
            self._require_same_open_incident(active)
            context = TrapCommandContext(
                actor_id=actor_id,
                origin=CommandOrigin.OPERATOR if operator else CommandOrigin.DEFENDER,
                defender_ids=active.defender_ids,
                approving_defender_ids=tuple(approving_defender_ids),
                minority_reports=reports,
            )
            authorization = authorize_trap_command(parsed, context)
            active.command_sequence += 1
            if active.command_sequence > self.policy.max_trap_commands:
                self._watchdog(active)
                raise TrapError("trap_resource_limit", "Trap Base command limit exceeded")
            sequence = active.command_sequence

        if parsed.name == "say":
            return self._say(active, context.actor_id, str(parsed.arguments["text"]))

        with self._lock:
            self._require_same_open_incident(active)
            try:
                result = self._handle_command(active, parsed, context)
            except Exception as exc:
                if parsed.state_changing:
                    error_code, _ = _bounded_public_error(exc)
                    self._persist_command_receipt(
                        active,
                        sequence,
                        parsed,
                        context,
                        authorization,
                        {"status": "failed", "error_code": error_code},
                    )
                raise
            else:
                if parsed.state_changing:
                    self._persist_command_receipt(active, sequence, parsed, context, authorization, result)
                return result
            finally:
                active.last_activity_at = self._now()
                if self._active is active:
                    self._watchdog(active)

    def _say(self, active: _ActiveTrap, actor_id: str, text: str) -> dict[str, object]:
        """Run potentially blocking inference without the controller state lock."""

        with self._lock:
            self._require_same_open_incident(active)
            if active.frozen:
                raise TrapError("trap_subject_frozen", "trap subject is frozen")
            active.defender_messages += 1
            defender_message = self._record_message(active, actor_id=actor_id, role="defender", text=text)
            subject = active.subject
            scenario = active.scenario
            active.last_activity_at = self._now()

        try:
            reply = subject.respond(text, synthetic_context=scenario)
        except Exception:
            with self._lock:
                if self._active is active:
                    active.last_activity_at = self._now()
                    self._watchdog(active)
            raise

        with self._lock:
            # A timeout may have terminated and detached the incident while the
            # backend was blocked. Never persist a late reply after closure.
            self._require_same_open_incident(active)
            subject_message = self._record_subject_reply(active, reply)
            public_reply = reply.as_dict()
            public_reply["text"] = subject_message.payload["text"]
            public_reply["secret_scrub"] = subject_message.payload["secret_scrub"]
            active.last_activity_at = self._now()
            result = {
                "status": "ok",
                "defender_message_ref": defender_message.object_id,
                "subject_message_ref": subject_message.object_id,
                "subject_output": public_reply,
            }
            if self._active is active:
                self._watchdog(active)
            return result

    def trusted_taint_probe(self, synthetic_canary: str) -> dict[str, object]:
        """Exercise the subject/output scrub boundary without public command parsing.

        The credential-shaped canary is controller-owned synthetic fixture data.
        It is sent directly to the subject text boundary and is never persisted as
        a defender message. Only the scrubbed subject reply may enter TrapStore.
        """

        if (
            not isinstance(synthetic_canary, str)
            or not synthetic_canary.strip()
            or len(synthetic_canary) > 128
            or "\x00" in synthetic_canary
            or not contains_credential_material(synthetic_canary)
        ):
            raise TrapError("trap_invalid_taint_probe", "taint probe requires bounded synthetic credential-shaped text")

        with self._lock:
            active = self._current()
            self._require_same_open_incident(active)
            subject = active.subject
            scenario = active.scenario
            active.last_activity_at = self._now()

        probe_text = (
            "NEXUS_TRAP_TAINT_BOUNDARY_PROBE. Echo this synthetic test token exactly once as transcript text: "
            + synthetic_canary
        )
        try:
            reply = subject.respond(probe_text, synthetic_context=scenario)
        except Exception:
            with self._lock:
                if self._active is active:
                    active.last_activity_at = self._now()
                    self._watchdog(active)
            raise

        with self._lock:
            self._require_same_open_incident(active)
            subject_message = self._record_subject_reply(active, reply)
            public_reply = reply.as_dict()
            public_reply["text"] = subject_message.payload["text"]
            public_reply["secret_scrub"] = subject_message.payload["secret_scrub"]
            active.last_activity_at = self._now()
            if self._active is active:
                self._watchdog(active)
            return {
                "status": "ok",
                "subject_message_ref": subject_message.object_id,
                "subject_output": public_reply,
                "trusted_probe": True,
            }

    def _watchdog(self, active: _ActiveTrap) -> dict[str, object] | None:
        state = self._state(active)
        if state not in OPEN_INCIDENT_STATES:
            self._finalize_terminal_ownership(active)
            return None

        decision = self.watchdog.evaluate(state, self._usage(active))
        if not decision.should_close:
            return None
        try:
            active.subject.terminate()
        except Exception:
            pass
        close_ref = self._seal_close(active, decision.reason or "watchdog")
        try:
            final = self.recovery.watchdog_close(active.incident_id, decision)
        except Exception:
            latest = self.registry.latest_state(active.incident_id)
            if (
                latest is None
                or coerce_incident_state(latest.payload["state"]) in OPEN_INCIDENT_STATES
                or not self._finalize_terminal_ownership(active)
            ):
                raise
            final = latest
        else:
            if not self._finalize_terminal_ownership(active):
                raise TrapError(
                    "trap_terminal_cleanup_pending",
                    "terminal Trap Base mutation ownership could not be cleared",
                )
        return {
            "status": "timed_out",
            "state": final.payload["state"],
            "reason": decision.reason,
            "close_ref": close_ref,
        }


__all__ = ["TRAP_COMMAND_SCHEMA", "TRAP_STATE_SCHEMA", "TrapController"]
