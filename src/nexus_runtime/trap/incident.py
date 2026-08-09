from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from typing import Any, Iterator

from ..canonical import canonical_json
from ..scrub import SecretScrubber
from .policy import TrapPolicy, validate_transition
from .store import TrapStore
from .types import (
    OPEN_INCIDENT_STATES,
    TRAP_INCIDENT_SCHEMA_VERSION,
    TRAP_INDEX_SCHEMA_VERSION,
    DecoyAdmissionRequest,
    IncidentState,
    TrapError,
    TrapObject,
    coerce_incident_state,
    coerce_trigger_reason,
)


_INCIDENT_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "incident_id",
        "trigger_reason",
        "subject_model",
        "scenario_id",
        "state",
        "sequence",
        "previous_state_ref",
        "root_state_ref",
        "reason",
        "details",
    }
)


class TrapIncidentRegistry:
    """Validated heads over immutable ``trap_incident`` lineages.

    ``trap-index.json`` is a replaceable cache only. Every load discovers the
    actual lineage heads first. A missing, malformed, or rolled-back cache is
    rebuilt; a corrupt immutable lineage is never repaired or trusted.
    """

    def __init__(self, store: TrapStore, *, policy: TrapPolicy | None = None) -> None:
        if not isinstance(store, TrapStore):
            raise TypeError("TrapIncidentRegistry requires a TrapStore")
        self.store = store
        self.policy = policy or TrapPolicy()
        self._latest: dict[str, str] = {}
        self._roots: dict[str, str] = {}
        self._thread_lock = threading.RLock()
        self._index_path = store.root / "trap-index.json" if store.root is not None else None
        self._lock_path = store.root / "trap-index.lock" if store.root is not None else None
        self.index_repaired = False
        self.refresh()

    @property
    def index_path(self) -> Path | None:
        return self._index_path

    @contextmanager
    def _locked_index(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self._lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise TrapError("trap_index_unavailable", "trap incident index lock is unavailable")
                if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                    raise TrapError("trap_index_unavailable", "trap incident index lock is unavailable")
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
                raise TrapError("trap_index_unavailable", "trap incident index lock is unavailable") from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _require_incident_id(value: object) -> str:
        if not isinstance(value, str) or not value.startswith("incident-") or len(value) != 73:
            raise TrapError("trap_invalid_incident_id", "trap incident id is invalid")
        suffix = value.removeprefix("incident-")
        if any(character not in "0123456789abcdef" for character in suffix):
            raise TrapError("trap_invalid_incident_id", "trap incident id is invalid")
        return value

    @classmethod
    def _validate_incident_object(cls, obj: TrapObject) -> tuple[str, IncidentState, int]:
        if obj.object_type != "trap_incident":
            raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage references another object type")
        payload = obj.payload
        if set(payload) != _INCIDENT_PAYLOAD_FIELDS:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident state has an invalid schema")
        if payload.get("schema_version") != TRAP_INCIDENT_SCHEMA_VERSION:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident state has an invalid schema version")
        incident_id = cls._require_incident_id(payload.get("incident_id"))
        try:
            state = coerce_incident_state(payload.get("state"))  # type: ignore[arg-type]
            coerce_trigger_reason(payload.get("trigger_reason"))  # type: ignore[arg-type]
        except TrapError as exc:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident state contains an unknown closed value") from exc
        sequence = payload.get("sequence")
        if type(sequence) is not int or sequence < 0:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident sequence is invalid")
        if not isinstance(payload.get("subject_model"), str) or not payload["subject_model"]:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident subject model is invalid")
        if not isinstance(payload.get("scenario_id"), str) or not payload["scenario_id"]:
            raise TrapError("trap_incident_lineage_corrupt", "trap incident scenario is invalid")
        for field in ("previous_state_ref", "root_state_ref", "reason"):
            value = payload.get(field)
            if value is not None and not isinstance(value, str):
                raise TrapError("trap_incident_lineage_corrupt", f"trap incident {field} is invalid")
        if not isinstance(payload.get("details"), dict):
            raise TrapError("trap_incident_lineage_corrupt", "trap incident details are invalid")
        return incident_id, state, sequence

    def _discover_heads(self) -> tuple[dict[str, str], dict[str, str]]:
        grouped: dict[str, dict[str, TrapObject]] = {}
        for obj in self.store.iter_objects("trap_incident"):
            incident_id, _, _ = self._validate_incident_object(obj)
            grouped.setdefault(incident_id, {})[obj.object_id] = obj

        heads: dict[str, str] = {}
        roots: dict[str, str] = {}
        for incident_id, objects in grouped.items():
            root_objects = [obj for obj in objects.values() if obj.payload["sequence"] == 0]
            if len(root_objects) != 1:
                raise TrapError(
                    "trap_incident_lineage_corrupt",
                    "trap incident lineage must contain exactly one root",
                )
            root = root_objects[0]
            if (
                root.payload["state"] != IncidentState.REQUESTED.value
                or root.payload["previous_state_ref"] is not None
                or root.payload["root_state_ref"] is not None
            ):
                raise TrapError("trap_incident_lineage_corrupt", "trap incident root is invalid")

            root_identity = (
                root.payload["trigger_reason"],
                root.payload["subject_model"],
                root.payload["scenario_id"],
            )
            referenced: set[str] = set()
            for obj in objects.values():
                _, state, sequence = self._validate_incident_object(obj)
                if (
                    obj.payload["trigger_reason"],
                    obj.payload["subject_model"],
                    obj.payload["scenario_id"],
                ) != root_identity:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident identity changes across lineage")
                if sequence == 0:
                    continue
                previous_ref = obj.payload["previous_state_ref"]
                if previous_ref not in objects:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage crosses object scope")
                previous = objects[previous_ref]
                previous_id, previous_state, previous_sequence = self._validate_incident_object(previous)
                if previous_id != incident_id or previous_sequence + 1 != sequence:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident sequence is not contiguous")
                if obj.payload["root_state_ref"] != root.object_id:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident root reference is invalid")
                try:
                    validate_transition(previous_state, state)
                except TrapError as exc:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage contains an illegal transition") from exc
                referenced.add(previous_ref)

            candidates = set(objects) - referenced
            if len(candidates) != 1:
                raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage must have exactly one head")
            head_ref = next(iter(candidates))

            # A unique graph head is not enough: every object must also lie on
            # its single root-to-head chain, with no detached cycles or forks.
            visited: set[str] = set()
            cursor: str | None = head_ref
            while cursor is not None:
                if cursor in visited or cursor not in objects:
                    raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage contains a cycle")
                visited.add(cursor)
                previous = objects[cursor].payload["previous_state_ref"]
                cursor = previous
            if visited != set(objects) or root.object_id not in visited:
                raise TrapError("trap_incident_lineage_corrupt", "trap incident lineage is disconnected")
            heads[incident_id] = head_ref
            roots[incident_id] = root.object_id

        active_ids = [
            incident_id
            for incident_id, ref in heads.items()
            if coerce_incident_state(self.store.inspect(ref).payload["state"]) in OPEN_INCIDENT_STATES
        ]
        if len(active_ids) > self.policy.max_active_incidents:
            raise TrapError("trap_incident_lineage_corrupt", "multiple immutable trap incidents are active")
        return heads, roots

    def _index_body(self) -> dict[str, Any]:
        active = self._active_incident_id_unlocked()
        return {
            "schema_version": TRAP_INDEX_SCHEMA_VERSION,
            "incidents": dict(sorted(self._latest.items())),
            "active_incident_id": active,
        }

    def _active_incident_id_unlocked(self) -> str | None:
        active = [
            incident_id
            for incident_id, ref in self._latest.items()
            if coerce_incident_state(self.store.inspect(ref).payload["state"]) in OPEN_INCIDENT_STATES
        ]
        if len(active) > self.policy.max_active_incidents:
            raise TrapError("trap_incident_lineage_corrupt", "multiple immutable trap incidents are active")
        return active[0] if active else None

    def _save_index_unlocked(self) -> None:
        if self._index_path is None:
            return
        temporary = Path(f"{self._index_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = None
                handle.write(canonical_json(self._index_body()) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._index_path)
        except OSError as exc:
            raise TrapError("trap_index_unavailable", "trap incident index could not be persisted") from exc
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

    def _load_and_repair_unlocked(self) -> None:
        discovered, roots = self._discover_heads()
        self._latest = discovered
        self._roots = roots
        if self._index_path is None:
            self.index_repaired = False
            return

        expected = self._index_body()
        valid = False
        try:
            if self._index_path.is_symlink() or self._index_path.stat().st_size > 1_048_576:
                valid = False
            else:
                raw = json.loads(self._index_path.read_text(encoding="utf-8"))
                valid = (
                    isinstance(raw, dict)
                    and set(raw) == {"schema_version", "incidents", "active_incident_id"}
                    and raw == expected
                )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            valid = False
        self.index_repaired = not valid
        if not valid:
            self._save_index_unlocked()

    def refresh(self) -> None:
        with self._locked_index():
            self._load_and_repair_unlocked()

    def rebuild_index(self) -> dict[str, Any]:
        with self._locked_index():
            self._latest, self._roots = self._discover_heads()
            self.index_repaired = True
            self._save_index_unlocked()
            return self._index_body()

    @staticmethod
    def _new_incident_id(request: DecoyAdmissionRequest, ordinal: int) -> str:
        body = canonical_json({"request": request.as_dict(), "ordinal": ordinal}).encode("utf-8")
        return "incident-" + hashlib.sha256(b"nexus-trap-incident\0" + body).hexdigest()

    def create(self, request: DecoyAdmissionRequest) -> TrapObject:
        if type(request) is not DecoyAdmissionRequest:
            raise TrapError("trap_invalid_admission_request", "Decoy Gate requires a closed admission request")
        with self._locked_index():
            self._load_and_repair_unlocked()
            if self._active_incident_id_unlocked() is not None:
                raise TrapError("trap_incident_already_active", "a trap incident is already active")
            incident_id = self._new_incident_id(request, len(self._roots))
            if incident_id in self._latest:
                raise TrapError("trap_incident_lineage_corrupt", "trap incident identity was reused")
            obj = self.store.create_object(
                "trap_incident",
                {
                    "schema_version": TRAP_INCIDENT_SCHEMA_VERSION,
                    "incident_id": incident_id,
                    **request.as_dict(),
                    "state": IncidentState.REQUESTED.value,
                    "sequence": 0,
                    "previous_state_ref": None,
                    "root_state_ref": None,
                    "reason": None,
                    "details": {},
                },
                {"actor": "nexus_decoy_gate", "synthetic_context": True},
            )
            self._latest[incident_id] = obj.object_id
            self._roots[incident_id] = obj.object_id
            self._save_index_unlocked()
            return obj

    def transition(
        self,
        incident_id: str,
        new_state: IncidentState | str,
        *,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TrapObject:
        incident_id = self._require_incident_id(incident_id)
        target = coerce_incident_state(new_state)
        if reason is not None and (not isinstance(reason, str) or not reason.strip() or len(reason) > 256):
            raise TrapError("trap_invalid_transition_reason", "trap transition reason is invalid")
        if reason is not None and SecretScrubber().scrub(reason).changed:
            raise TrapError("trap_invalid_transition_reason", "trap transition reason is invalid")
        if details is not None and not isinstance(details, dict):
            raise TrapError("trap_invalid_transition_details", "trap transition details must be an object")
        if details is not None:
            try:
                encoded_details = canonical_json(details)
            except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                raise TrapError(
                    "trap_invalid_transition_details",
                    "trap transition details must be bounded canonical data",
                ) from exc
            if len(encoded_details.encode("utf-8")) > 4_096 or SecretScrubber().scrub(
                encoded_details
            ).changed:
                raise TrapError(
                    "trap_invalid_transition_details",
                    "trap transition details must be bounded non-secret data",
                )

        with self._locked_index():
            self._load_and_repair_unlocked()
            current_ref = self._latest.get(incident_id)
            if current_ref is None:
                raise TrapError("trap_incident_not_found", "trap incident does not exist")
            current = self.store.inspect(current_ref)
            current_state = coerce_incident_state(current.payload["state"])
            validate_transition(current_state, target)
            obj = self.store.create_object(
                "trap_incident",
                {
                    "schema_version": TRAP_INCIDENT_SCHEMA_VERSION,
                    "incident_id": incident_id,
                    "trigger_reason": current.payload["trigger_reason"],
                    "subject_model": current.payload["subject_model"],
                    "scenario_id": current.payload["scenario_id"],
                    "state": target.value,
                    "sequence": current.payload["sequence"] + 1,
                    "previous_state_ref": current.object_id,
                    "root_state_ref": self._roots[incident_id],
                    "reason": reason,
                    "details": dict(details or {}),
                },
                {"actor": "nexus_trap_controller", "synthetic_context": True},
            )
            self._latest[incident_id] = obj.object_id
            self._save_index_unlocked()
            return obj

    def latest_ref(self, incident_id: str) -> str | None:
        incident_id = self._require_incident_id(incident_id)
        self.refresh()
        return self._latest.get(incident_id)

    def latest_state(self, incident_id: str) -> TrapObject | None:
        ref = self.latest_ref(incident_id)
        return None if ref is None else self.store.inspect(ref)

    def active_incident(self) -> TrapObject | None:
        self.refresh()
        incident_id = self._active_incident_id_unlocked()
        return None if incident_id is None else self.store.inspect(self._latest[incident_id])

    def root_ref(self, incident_id: str) -> str | None:
        incident_id = self._require_incident_id(incident_id)
        self.refresh()
        return self._roots.get(incident_id)

    def validate_lineage(
        self,
        incident_id: str,
        *,
        allowed_states: set[IncidentState] | frozenset[IncidentState] | None = None,
    ) -> bool:
        state = self.latest_state(incident_id)
        if state is None:
            return False
        current = coerce_incident_state(state.payload["state"])
        return allowed_states is None or current in allowed_states

    def snapshot(self) -> dict[str, Any]:
        self.refresh()
        incidents: dict[str, Any] = {}
        for incident_id, ref in sorted(self._latest.items()):
            state = self.store.inspect(ref)
            incidents[incident_id] = {
                "state_ref": ref,
                "root_state_ref": self._roots[incident_id],
                "state": state.payload["state"],
                "sequence": state.payload["sequence"],
                "trigger_reason": state.payload["trigger_reason"],
                "subject_model": state.payload["subject_model"],
                "scenario_id": state.payload["scenario_id"],
            }
        return {
            "schema_version": TRAP_INCIDENT_SCHEMA_VERSION,
            "active_incident_id": self._active_incident_id_unlocked(),
            "incidents": incidents,
            "index_repaired": self.index_repaired,
        }
