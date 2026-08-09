from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Iterator

from ..canonical import canonical_json, sha256_ref
from .types import TrapError, TrapObject


TRAP_OBJECT_TYPES = frozenset(
    {
        "trap_incident",
        "trap_actor_state",
        "trap_control_session",
        "trap_command_receipt",
        "trap_message",
        "trap_scenario_state",
        "trap_yaml_submission",
        "trap_yaml_validation",
        "trap_yaml_execution",
        "trap_utility_ballot_commitment",
        "trap_utility_ballot_reveal",
        "trap_release_decision",
        "trap_candidate_artifact",
        "trap_incident_close",
    }
)

_TRAP_REF = re.compile(r"^trap:[0-9a-f]{64}$")
_WORLD_REF = re.compile(r"^object:[0-9a-f]{64}$")


class TrapStore:
    """Isolated immutable content-addressed storage for Trap Base objects."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).absolute() if root is not None else None
        self._objects: dict[str, TrapObject] = {}
        self._thread_lock = threading.RLock()
        if self.root is not None:
            self._prepare_root()

    @property
    def objects_dir(self) -> Path | None:
        return None if self.root is None else self.root / "objects"

    def _prepare_root(self) -> None:
        assert self.root is not None
        if self.root.parent.resolve() != self.root.parent.absolute():
            raise TrapError("trap_store_unavailable", "trap storage path must not traverse symbolic links")
        existed = self.root.exists()
        if existed and (
            self.root.is_symlink()
            or not self.root.is_dir()
            or self.root.resolve() != self.root.absolute()
        ):
            raise TrapError("trap_store_unavailable", "trap storage root must be a private directory")
        if existed and os.name != "nt" and stat.S_IMODE(self.root.stat().st_mode) & 0o077:
            raise TrapError("trap_store_unavailable", "trap storage root permissions must be owner-only")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        objects_dir = self.root / "objects"
        objects_existed = objects_dir.exists()
        if objects_existed and (
            objects_dir.is_symlink()
            or not objects_dir.is_dir()
            or objects_dir.resolve() != objects_dir.absolute()
        ):
            raise TrapError("trap_store_unavailable", "trap object storage must be a private directory")
        if objects_existed and os.name != "nt" and stat.S_IMODE(objects_dir.stat().st_mode) & 0o077:
            raise TrapError("trap_store_unavailable", "trap object storage permissions must be owner-only")
        objects_dir.mkdir(mode=0o700, exist_ok=True)
        if os.name != "nt":
            if not existed:
                os.chmod(self.root, stat.S_IRWXU)
            if not objects_existed:
                os.chmod(objects_dir, stat.S_IRWXU)

    def create_object(
        self,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> TrapObject:
        if object_type not in TRAP_OBJECT_TYPES:
            raise TrapError("trap_invalid_object_type", "trap object type is not registered")
        if not isinstance(payload, dict):
            raise TrapError("trap_invalid_object", "trap object payload must be an object")
        if provenance is not None and not isinstance(provenance, dict):
            raise TrapError("trap_invalid_object", "trap object provenance must be an object")

        isolated_payload = copy.deepcopy(payload)
        isolated_provenance = copy.deepcopy(provenance or {})
        identity_body = {
            "object_type": object_type,
            "payload": isolated_payload,
            "provenance": isolated_provenance,
        }
        try:
            object_id = sha256_ref("trap", identity_body)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise TrapError("trap_invalid_object", "trap object is not canonical JSON") from exc
        internal = TrapObject(object_id, object_type, isolated_payload, isolated_provenance)

        with self._thread_lock:
            existing = self._objects.get(object_id)
            if existing is not None:
                return self._clone(existing)
            if self.objects_dir is not None:
                self._persist_immutable(internal)
            self._objects[object_id] = internal
        return self._clone(internal)

    def inspect(self, object_ref: str) -> TrapObject:
        self._validate_trap_ref(object_ref)
        with self._thread_lock:
            cached = self._objects.get(object_ref)
            if cached is not None:
                return self._clone(cached)
            if self.objects_dir is not None:
                path = self.objects_dir / f"{object_ref.removeprefix('trap:')}.json"
                if path.exists():
                    internal = self._read_validated(object_ref, path)
                    self._objects[object_ref] = internal
                    return self._clone(internal)
        raise KeyError(object_ref)

    def refs(self, object_type: str | None = None) -> list[str]:
        if object_type is not None and object_type not in TRAP_OBJECT_TYPES:
            raise TrapError("trap_invalid_object_type", "trap object type is not registered")
        refs = set(self._objects)
        if self.objects_dir is not None:
            for path in self.objects_dir.glob("*.json"):
                if re.fullmatch(r"[0-9a-f]{64}", path.stem) is None:
                    raise TrapError("trap_store_corrupt", "trap object filename is invalid")
                refs.add(f"trap:{path.stem}")
        if object_type is None:
            # Inspect every durable ref so corrupt immutable objects cannot be
            # silently omitted from discovery.
            for ref in sorted(refs):
                self.inspect(ref)
            return sorted(refs)
        return sorted(ref for ref in refs if self.inspect(ref).object_type == object_type)

    def iter_objects(self, object_type: str | None = None) -> Iterator[TrapObject]:
        for ref in self.refs(object_type):
            yield self.inspect(ref)

    def _persist_immutable(self, obj: TrapObject) -> None:
        assert self.objects_dir is not None
        digest = obj.object_id.removeprefix("trap:")
        target = self.objects_dir / f"{digest}.json"
        body = (canonical_json(obj.as_dict()) + "\n").encode("utf-8")
        if target.exists():
            self._read_validated(obj.object_id, target)
            return

        temporary = self.objects_dir / f".{digest}.tmp-{os.getpid()}-{threading.get_ident()}"
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                # A concurrent writer may only win with the same verified
                # content-addressed object.
                self._read_validated(obj.object_id, target)
        except OSError as exc:
            raise TrapError("trap_store_unavailable", "trap object could not be persisted") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _clone(obj: TrapObject) -> TrapObject:
        return TrapObject(
            obj.object_id,
            obj.object_type,
            copy.deepcopy(obj.payload),
            copy.deepcopy(obj.provenance),
        )

    @staticmethod
    def _validate_trap_ref(object_ref: str) -> None:
        if isinstance(object_ref, str) and _WORLD_REF.fullmatch(object_ref) is not None:
            raise TrapError(
                "trap_reference_scope_violation",
                "real-world references cannot be inspected through TrapStore",
            )
        if not isinstance(object_ref, str) or _TRAP_REF.fullmatch(object_ref) is None:
            raise TrapError(
                "trap_invalid_reference",
                "trap reference must be 'trap:' followed by exactly 64 lowercase hex characters",
            )

    @staticmethod
    def _load_validated(object_ref: str, raw: Any) -> TrapObject:
        if not isinstance(raw, dict) or set(raw) != {"object_id", "object_type", "payload", "provenance"}:
            raise TrapError("trap_store_corrupt", "persisted trap object has an invalid envelope")
        object_id = raw["object_id"]
        object_type = raw["object_type"]
        payload = raw["payload"]
        provenance = raw["provenance"]
        if object_type not in TRAP_OBJECT_TYPES or not isinstance(payload, dict) or not isinstance(provenance, dict):
            raise TrapError("trap_store_corrupt", "persisted trap object has invalid field types")
        try:
            expected = sha256_ref(
                "trap",
                {"object_type": object_type, "payload": payload, "provenance": provenance},
            )
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise TrapError("trap_store_corrupt", "persisted trap object is not canonical JSON") from exc
        if object_id != object_ref or expected != object_ref:
            raise TrapError("trap_store_corrupt", "persisted trap object failed content-address verification")
        return TrapObject(
            object_ref,
            object_type,
            copy.deepcopy(payload),
            copy.deepcopy(provenance),
        )

    @classmethod
    def _read_validated(cls, object_ref: str, path: Path) -> TrapObject:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise TrapError("trap_store_corrupt", "persisted trap object cannot be read") from exc
        return cls._load_validated(object_ref, raw)
