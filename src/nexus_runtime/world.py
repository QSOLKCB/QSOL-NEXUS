from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import stat
import threading
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json, sha256_ref


_OBJECT_REF = re.compile(r"^object:[0-9a-f]{64}$")
_OBJECT_FILENAME = re.compile(r"^[0-9a-f]{64}\.json$")


@dataclass(frozen=True)
class WorldObject:
    object_id: str
    object_type: str
    payload: dict[str, Any]
    provenance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "payload": copy.deepcopy(self.payload),
            "provenance": copy.deepcopy(self.provenance),
        }


class WorldStore:
    """Content-addressed world storage with optional private file persistence."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).absolute() if root is not None else None
        self._objects: dict[str, WorldObject] = {}
        self._thread_lock = threading.RLock()
        if self.root is not None:
            self._prepare_root()

    @property
    def objects_dir(self) -> Path | None:
        return None if self.root is None else self.root / "objects"

    def _prepare_root(self) -> None:
        assert self.root is not None
        if self.root.parent.resolve() != self.root.parent.absolute():
            raise ValueError("world storage path must not traverse symbolic links")

        existed = self.root.exists()
        if self.root.is_symlink() or (existed and (not self.root.is_dir() or self.root.resolve() != self.root.absolute())):
            raise ValueError("world storage root must be a private directory")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

        objects_dir = self.root / "objects"
        objects_existed = objects_dir.exists()
        if objects_dir.is_symlink() or (
            objects_existed and (not objects_dir.is_dir() or objects_dir.resolve() != objects_dir.absolute())
        ):
            raise ValueError("world object storage must be a private directory")
        objects_dir.mkdir(mode=0o700, exist_ok=True)

        if os.name != "nt":
            # Earlier NEXUS versions created these paths under the process
            # umask, commonly as 0755/0644. Tighten that exact, already-
            # validated directory tree in place so upgrades remain readable.
            os.chmod(self.root, stat.S_IRWXU, follow_symlinks=False)
            os.chmod(objects_dir, stat.S_IRWXU, follow_symlinks=False)
            self._migrate_legacy_object_permissions(objects_dir)

    @staticmethod
    def _migrate_legacy_object_permissions(objects_dir: Path) -> None:
        for path in objects_dir.iterdir():
            if path.is_symlink() or _OBJECT_FILENAME.fullmatch(path.name) is None:
                raise ValueError("world object storage contains an unsafe entry")
            descriptor: int | None = None
            try:
                flags = os.O_RDONLY
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(path, flags)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("persisted world object must be a regular file")
                os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
            except OSError as exc:
                raise OSError("world object permissions could not be migrated") from exc
            finally:
                if descriptor is not None:
                    os.close(descriptor)

    def create_object(
        self,
        object_type: str,
        payload: dict[str, Any],
        provenance: dict[str, Any] | None = None,
    ) -> WorldObject:
        isolated_payload = copy.deepcopy(payload)
        isolated_provenance = copy.deepcopy(provenance or {})
        identity_body = {
            "object_type": object_type,
            "payload": isolated_payload,
            "provenance": isolated_provenance,
        }
        object_id = sha256_ref("object", identity_body)
        internal = WorldObject(object_id, object_type, isolated_payload, isolated_provenance)

        with self._thread_lock:
            if self.objects_dir is not None:
                self._persist_immutable(internal)
            self._objects[object_id] = internal
        return self._clone(internal)

    def inspect(self, object_ref: str) -> WorldObject:
        self._validate_object_ref(object_ref)
        with self._thread_lock:
            if object_ref in self._objects:
                return self._clone(self._objects[object_ref])
            if self.objects_dir is not None:
                digest = object_ref.removeprefix("object:")
                path = self.objects_dir / f"{digest}.json"
                if path.is_symlink():
                    raise ValueError("persisted world object must not be a symbolic link")
                if path.exists():
                    internal = self._read_validated(object_ref, path)
                    self._objects[object_ref] = internal
                    return self._clone(internal)
        raise KeyError(object_ref)

    def create_evidence_snapshot(
        self,
        question_ref: str,
        included_object_refs: list[str] | None = None,
        evidence_state: str = "UNTESTED",
    ) -> WorldObject:
        return self.create_object(
            "evidence_snapshot",
            {
                "question_ref": question_ref,
                "included_object_refs": list(included_object_refs or []),
                "evidence_state": evidence_state,
            },
            {"actor": "nexus"},
        )

    def _persist_immutable(self, obj: WorldObject) -> None:
        assert self.objects_dir is not None
        digest = obj.object_id.removeprefix("object:")
        target = self.objects_dir / f"{digest}.json"
        body = (canonical_json(obj.as_dict()) + "\n").encode("utf-8")

        if target.is_symlink():
            raise ValueError("persisted world object must not be a symbolic link")
        if target.exists():
            self._read_validated(obj.object_id, target)
            return

        temporary = self.objects_dir / f".{digest}.tmp-{os.getpid()}-{threading.get_ident()}"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                if os.name != "nt":
                    os.fchmod(handle.fileno(), stat.S_IRUSR | stat.S_IWUSR)
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                self._read_validated(obj.object_id, target)
        except OSError as exc:
            raise OSError("world object could not be persisted") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @classmethod
    def _read_validated(cls, object_ref: str, path: Path) -> WorldObject:
        if path.is_symlink():
            raise ValueError("persisted world object must not be a symbolic link")
        descriptor: int | None = None
        try:
            flags = os.O_RDONLY
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(path, flags)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("persisted world object must be a regular file")
            if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("persisted world object permissions must be owner-only")
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = None
                encoded = handle.read()
            decoded = encoded.decode("utf-8")
            raw = json.loads(decoded)
            try:
                canonical = (canonical_json(raw) + "\n").encode("utf-8")
            except (TypeError, ValueError, RecursionError) as exc:
                raise ValueError("persisted world object is not canonical JSON") from exc
            if encoded != canonical:
                raise ValueError("persisted world object is not canonical JSON")
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("persisted world object cannot be decoded") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        return cls._load_validated(object_ref, raw)

    @staticmethod
    def _clone(obj: WorldObject) -> WorldObject:
        return WorldObject(
            obj.object_id,
            obj.object_type,
            copy.deepcopy(obj.payload),
            copy.deepcopy(obj.provenance),
        )

    @staticmethod
    def _validate_object_ref(object_ref: str) -> None:
        if not isinstance(object_ref, str) or _OBJECT_REF.fullmatch(object_ref) is None:
            raise ValueError("object_ref must be 'object:' followed by exactly 64 lowercase hex characters")

    @staticmethod
    def _load_validated(object_ref: str, raw: Any) -> WorldObject:
        if not isinstance(raw, dict):
            raise ValueError("persisted world object must be a JSON object")
        expected_fields = {"object_id", "object_type", "payload", "provenance"}
        if set(raw) != expected_fields:
            raise ValueError("persisted world object schema is invalid")
        try:
            object_id = raw["object_id"]
            object_type = raw["object_type"]
            payload = raw["payload"]
            provenance = raw["provenance"]
        except KeyError as exc:
            raise ValueError(f"persisted world object missing field: {exc.args[0]}") from exc
        if not isinstance(object_type, str) or not isinstance(payload, dict) or not isinstance(provenance, dict):
            raise ValueError("persisted world object has invalid field types")
        expected = sha256_ref(
            "object",
            {"object_type": object_type, "payload": payload, "provenance": provenance},
        )
        if object_id != object_ref or expected != object_ref:
            raise ValueError("persisted world object failed content-address verification")
        return WorldObject(
            object_ref,
            object_type,
            copy.deepcopy(payload),
            copy.deepcopy(provenance),
        )
