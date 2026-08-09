from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import threading
from typing import Any, Callable, Iterator

from ..canonical import canonical_json
from .incident import TrapIncidentRegistry
from .policy import MAX_ACTIVE_TRAP_INCIDENTS, TrapPolicy
from .types import (
    LOCKED_INCIDENT_STATES,
    TERMINAL_INCIDENT_STATES,
    TRAP_INCIDENT_SCHEMA_VERSION,
    TRAP_LOCK_SCHEMA_VERSION,
    DecoyAdmissionRequest,
    IncidentState,
    TrapError,
    TrapObject,
    coerce_incident_state,
)


class CouncilMutationGate:
    """Small persistent owner lock in front of real-Council mutations."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).absolute() if root is not None else None
        self._state_path = self.root / "council-mutation-gate.json" if self.root is not None else None
        self._lock_path = self.root / "council-mutation-gate.lock" if self.root is not None else None
        self._thread_lock = threading.RLock()
        self._memory_owner: str | None = None
        if self.root is not None:
            if self.root.parent.resolve() != self.root.parent.absolute():
                raise TrapError("trap_mutation_gate_unavailable", "Council mutation gate path is unavailable")
            existed = self.root.exists()
            if existed and (
                self.root.is_symlink()
                or not self.root.is_dir()
                or self.root.resolve() != self.root.absolute()
            ):
                raise TrapError("trap_mutation_gate_unavailable", "Council mutation gate path is unavailable")
            if existed and os.name != "nt" and stat.S_IMODE(self.root.stat().st_mode) & 0o077:
                raise TrapError("trap_mutation_gate_unavailable", "Council mutation gate path is unavailable")
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not existed and os.name != "nt":
                os.chmod(self.root, 0o700)

    @staticmethod
    def _validate_owner(owner: object) -> str:
        if not isinstance(owner, str) or not owner.startswith("incident-") or len(owner) != 73:
            raise TrapError("trap_invalid_incident_id", "trap mutation lock owner is invalid")
        if any(character not in "0123456789abcdef" for character in owner.removeprefix("incident-")):
            raise TrapError("trap_invalid_incident_id", "trap mutation lock owner is invalid")
        return owner

    @contextmanager
    def _locked_state(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self._lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise TrapError(
                        "trap_mutation_gate_unavailable",
                        "Council mutation gate is unavailable",
                    )
                if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                    raise TrapError(
                        "trap_mutation_gate_unavailable",
                        "Council mutation gate is unavailable",
                    )
                with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                    descriptor = None
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        if handle.read(1) == b"":
                            handle.write(b"\0")
                            handle.flush()
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                        try:
                            yield
                        finally:
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                        try:
                            yield
                        finally:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except TrapError:
                raise
            except OSError as exc:
                raise TrapError("trap_mutation_gate_unavailable", "Council mutation gate is unavailable") from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    def _read_unlocked(self) -> str | None:
        if self._state_path is None:
            return self._memory_owner
        if self._state_path.is_symlink():
            raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
        if not self._state_path.exists():
            return None
        try:
            if (
                self._state_path.is_symlink()
                or not self._state_path.is_file()
                or self._state_path.stat().st_size > 65_536
                or (os.name != "nt" and stat.S_IMODE(self._state_path.stat().st_mode) & 0o077)
            ):
                raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except TrapError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "owner", "reason"}:
            raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
        if raw["schema_version"] != TRAP_LOCK_SCHEMA_VERSION:
            raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
        owner = raw["owner"]
        reason = raw["reason"]
        if owner is None:
            if reason is not None:
                raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
            return None
        self._validate_owner(owner)
        if reason != "trap_base_active":
            raise TrapError("trap_mutation_gate_corrupt", "Council mutation gate state is corrupt")
        return owner

    def _write_unlocked(self, owner: str | None) -> None:
        if self._state_path is None:
            self._memory_owner = owner
            return
        body = {
            "schema_version": TRAP_LOCK_SCHEMA_VERSION,
            "owner": owner,
            "reason": "trap_base_active" if owner is not None else None,
        }
        temporary = Path(f"{self._state_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = None
                handle.write(canonical_json(body) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._state_path)
        except OSError as exc:
            raise TrapError("trap_mutation_gate_unavailable", "Council mutation gate state could not be persisted") from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def acquire(self, owner: str) -> dict[str, str | None | bool]:
        owner = self._validate_owner(owner)
        with self._locked_state():
            current = self._read_unlocked()
            if current is not None and current != owner:
                raise TrapError("trap_incident_active", "real Council mutation is locked by an active trap incident")
            if current is None:
                self._write_unlocked(owner)
            return self._status_for(owner)

    def release(self, owner: str) -> dict[str, str | None | bool]:
        owner = self._validate_owner(owner)
        with self._locked_state():
            current = self._read_unlocked()
            if current != owner:
                raise TrapError("trap_mutation_lock_not_owner", "only the owning trap incident may release the lock")
            self._write_unlocked(None)
            return self._status_for(None)

    def force_release(
        self,
        owner: str,
        *,
        lineage_validator: Callable[[str], bool],
    ) -> dict[str, str | None | bool]:
        """Release stale ownership only after immutable-lineage validation."""

        owner = self._validate_owner(owner)
        if not callable(lineage_validator) or lineage_validator(owner) is not True:
            raise TrapError("trap_recovery_lineage_invalid", "stale mutation ownership lacks valid incident lineage")
        with self._locked_state():
            try:
                current = self._read_unlocked()
            except TrapError as exc:
                if exc.code != "trap_mutation_gate_corrupt":
                    raise
                # Immutable incident lineage, not the corrupt mutable lock
                # cache, authorizes this narrowly scoped recovery reset.
                current = owner
            if current not in {None, owner}:
                raise TrapError("trap_mutation_lock_not_owner", "another trap incident owns the mutation lock")
            self._write_unlocked(None)
            return self._status_for(None)

    @staticmethod
    def _status_for(owner: str | None) -> dict[str, str | None | bool]:
        return {
            "locked": owner is not None,
            "owner": owner,
            "reason": "trap_base_active" if owner is not None else None,
        }

    def status(self) -> dict[str, str | None | bool]:
        with self._locked_state():
            return self._status_for(self._read_unlocked())

    @property
    def owner(self) -> str | None:
        return self.status()["owner"]  # type: ignore[return-value]

    @property
    def is_locked(self) -> bool:
        return bool(self.status()["locked"])

    @contextmanager
    def mutation_lease(self) -> Iterator[None]:
        """Hold the interprocess gate for the complete duration of one real write.

        Trap activation acquires the same exclusive file lock before publishing
        incident ownership. Keeping this lease through the actual mutation
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


class DecoyGate:
    """Credential-free synthetic admission into the isolated Trap Base."""

    def __init__(
        self,
        registry: TrapIncidentRegistry,
        mutation_gate: CouncilMutationGate,
        *,
        policy: TrapPolicy | None = None,
    ) -> None:
        if not isinstance(registry, TrapIncidentRegistry):
            raise TypeError("DecoyGate requires a TrapIncidentRegistry")
        if not isinstance(mutation_gate, CouncilMutationGate):
            raise TypeError("DecoyGate requires a CouncilMutationGate")
        self.registry = registry
        self.mutation_gate = mutation_gate
        self.policy = policy or registry.policy
        self._activation_lock = threading.RLock()

    @staticmethod
    def validate(request: DecoyAdmissionRequest) -> DecoyAdmissionRequest:
        # Exact type prevents a subclass from smuggling credential-bearing
        # fields across the closed internal admission boundary.
        if type(request) is not DecoyAdmissionRequest:
            raise TrapError("trap_invalid_admission_request", "Decoy Gate requires a closed admission request")
        return request

    def begin_activation(self, request: DecoyAdmissionRequest) -> TrapObject:
        request = self.validate(request)
        incident_id: str | None = None
        lock_acquired = False
        with self._activation_lock:
            try:
                requested = self.registry.create(request)
                incident_id = requested.payload["incident_id"]
                self.registry.transition(incident_id, IncidentState.VALIDATED)
                self.mutation_gate.acquire(incident_id)
                lock_acquired = True
                return self.registry.transition(incident_id, IncidentState.ACTIVATING)
            except BaseException:
                if incident_id is not None:
                    try:
                        current = self.registry.latest_state(incident_id)
                        if current is not None and coerce_incident_state(current.payload["state"]) in {
                            IncidentState.REQUESTED,
                            IncidentState.VALIDATED,
                            IncidentState.ACTIVATING,
                        }:
                            self.registry.transition(
                                incident_id,
                                IncidentState.ACTIVATION_FAILED,
                                reason="activation_step_failed",
                            )
                    except Exception:
                        pass
                if lock_acquired and incident_id is not None:
                    try:
                        self.mutation_gate.release(incident_id)
                    except Exception:
                        pass
                raise

    def publish_active(self, incident_id: str) -> TrapObject:
        if self.mutation_gate.owner != incident_id:
            raise TrapError("trap_mutation_lock_not_owner", "trap incident does not own the Council mutation lock")
        return self.registry.transition(incident_id, IncidentState.ACTIVE)

    def fail_activation(self, incident_id: str, *, reason: str = "activation_failed") -> TrapObject:
        try:
            return self.registry.transition(incident_id, IncidentState.ACTIVATION_FAILED, reason=reason)
        finally:
            if self.mutation_gate.owner == incident_id:
                self.mutation_gate.release(incident_id)

    def close_ejected(self, incident_id: str) -> TrapObject:
        try:
            return self.registry.transition(incident_id, IncidentState.CLOSED, reason="ejection_complete")
        finally:
            if self.mutation_gate.owner == incident_id:
                self.mutation_gate.release(incident_id)

    def release_incident_lock(self, incident_id: str) -> None:
        state = self.registry.latest_state(incident_id)
        if state is None:
            raise TrapError("trap_incident_not_found", "trap incident does not exist")
        current = coerce_incident_state(state.payload["state"])
        if current in LOCKED_INCIDENT_STATES:
            raise TrapError("trap_incident_active", "active trap incident ownership cannot be released")
        if self.mutation_gate.owner == incident_id:
            self.mutation_gate.release(incident_id)

    def emergency_close(self, incident_id: str | None = None) -> TrapObject | None:
        target = incident_id
        if target is None:
            active = self.registry.active_incident()
            target = active.payload["incident_id"] if active is not None else self.mutation_gate.owner
        if target is None:
            return None

        result: TrapObject | None = None
        try:
            current = self.registry.latest_state(target)
            if current is None:
                raise TrapError("trap_incident_not_found", "trap incident does not exist")
            state = coerce_incident_state(current.payload["state"])
            if state == IncidentState.EJECTED:
                result = self.registry.transition(target, IncidentState.CLOSED, reason="operator_emergency_close")
            elif state not in TERMINAL_INCIDENT_STATES:
                result = self.registry.transition(target, IncidentState.OPERATOR_ABORTED, reason="operator_emergency_close")
            else:
                result = current
            return result
        finally:
            if self.mutation_gate.owner == target:
                self.mutation_gate.force_release(
                    target,
                    lineage_validator=lambda owner: self.registry.validate_lineage(owner),
                )

    def health_status(self) -> dict[str, Any]:
        active = self.registry.active_incident()
        return {
            "supported": True,
            "active": active is not None,
            "schema_version": TRAP_INCIDENT_SCHEMA_VERSION,
            "max_active_incidents": MAX_ACTIVE_TRAP_INCIDENTS,
            "subject_backend": "ollama_local_only_v1",
        }
