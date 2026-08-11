from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import stat
import threading
import time
from typing import Any, Callable, Iterator

from .canonical import canonical_json, sha256_ref
from .scrub import SecretScrubber
from .stenographer_lore import LORE_TITLES, reveal_lore


STENOGRAPHER_SCHEMA_VERSION = "nexus-stenographer/1"
STENOGRAPHER_INDEX_SCHEMA_VERSION = "nexus-stenographer-index/1"
STENOGRAPHER_EXPORT_SCHEMA_VERSION = "nexus-stenographer-export/1"
STENOGRAPHER_ACTION_TYPES = frozenset(
    {
        "actor.direct_response",
        "council.phase_response",
        "council.ballot",
        "failsafe.rehabilitation_response",
        "trap.subject_response",
    }
)
MAX_STENOGRAPHER_OUTPUT_CHARS = 131_072
MAX_STENOGRAPHER_RECORD_BYTES = 1_048_576
MAX_STENOGRAPHER_LIST_LIMIT = 1_000
MAX_STENOGRAPHER_LIST_BYTES = 2_097_152
MAX_STENOGRAPHER_PENDING_ACTIONS = 256
MAX_STENOGRAPHER_QUEUE_CAPACITY = 4_096
STENOGRAPHER_READ_DRAIN_SECONDS = 5.0

_STENO_REF = re.compile(r"^steno:[0-9a-f]{64}$")
_OTHER_STORE_REF = re.compile(r"^(?:object|trap):[0-9a-f]{64}$")
_STIMULUS_REF = re.compile(r"^stimulus:[0-9a-f]{64}$")
_RECORDED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_PHASES = frozenset({"WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"})
_PERM_OBJECT_NAME = re.compile(r"^[0-9a-f]{64}\.json$")
_OBJECT_TMP_NAME = re.compile(r"^\.([0-9a-f]{64})\.tmp-[0-9]+-[0-9]+$")


def _lore_envelope() -> dict[str, Any]:
    return {
        "name": "Courtroom Stenographer",
        "titles": list(LORE_TITLES),
        "job": "watchman_only",
        "record_scope": "ai_actions_only",
        "lore_is_authority": False,
    }


def _authority_envelope() -> dict[str, bool]:
    return {
        "prompt": False,
        "vote": False,
        "decide": False,
        "command": False,
        "mutate_world": False,
        "mutate_trap": False,
        "mutate_auth": False,
        "alter_ai_output": False,
    }


# Public snapshots for callers and tests. Internal validation always constructs
# a fresh closed envelope, so outside mutation cannot change the trust boundary.
STENOGRAPHER_LORE = _lore_envelope()
STENOGRAPHER_AUTHORITY = _authority_envelope()


class StenographerError(ValueError):
    """Sanitized failure at the independent AI-action record boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StenographerRecord:
    record_ref: str
    record_type: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_ref": self.record_ref,
            "record_type": self.record_type,
            "payload": copy.deepcopy(self.payload),
        }


@dataclass(frozen=True)
class _PendingAction:
    action: dict[str, Any]
    recorded_at_utc: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _valid_recorded_at(value: object) -> bool:
    if not isinstance(value, str) or _RECORDED_AT.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _bounded_identifier(value: object, label: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise StenographerError("stenographer_invalid_action", f"{label} is invalid")
    clean = value.strip()
    if SecretScrubber().scrub(clean).changed:
        raise StenographerError("stenographer_invalid_action", f"{label} is invalid")
    return clean


def _validate_stored_identifier(value: object, label: str, maximum: int) -> None:
    try:
        clean = _bounded_identifier(value, label, maximum)
    except StenographerError as exc:
        raise StenographerError("stenographer_store_corrupt", f"{label} is invalid") from exc
    if clean != value:
        raise StenographerError("stenographer_store_corrupt", f"{label} is invalid")


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _actor_identity(actor: object) -> dict[str, str]:
    member = getattr(actor, "member", None)
    if member is None:
        raise StenographerError("stenographer_invalid_action", "AI actor identity is unavailable")
    actor_kind = type(actor).__name__.strip("_")
    return {
        "member_id": _bounded_identifier(getattr(member, "member_id", None), "member_id", 128),
        "model_id": _bounded_identifier(getattr(member, "model_id", None), "model_id", 256),
        "adapter_id": _bounded_identifier(getattr(member, "adapter_id", None), "adapter_id", 128),
        "actor_kind": _bounded_identifier(actor_kind, "actor_kind", 128),
    }


class StenographerStore:
    """Immutable, content-addressed, append-only storage for AI action records.

    The index is a replaceable cache. Immutable record objects and their
    previous-record links are the canonical ledger.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).absolute() if root is not None else None
        self._objects: dict[str, StenographerRecord] = {}
        self._ordered_refs: list[str] = []
        self._head_ref: str | None = None
        self._thread_lock = threading.RLock()
        self.index_repaired = False
        if self.root is not None:
            try:
                self._prepare_root()
            except StenographerError:
                raise
            except OSError as exc:
                raise StenographerError(
                    "stenographer_store_unavailable",
                    "stenographer storage path is unavailable",
                ) from exc
        self.refresh()

    @property
    def objects_dir(self) -> Path | None:
        return None if self.root is None else self.root / "objects"

    @property
    def write_tmp_dir(self) -> Path | None:
        return None if self.root is None else self.root / ".write-tmp"

    @property
    def index_path(self) -> Path | None:
        return None if self.root is None else self.root / "stenographer-index.json"

    @property
    def lock_path(self) -> Path | None:
        return None if self.root is None else self.root / "stenographer-index.lock"

    def _prepare_root(self) -> None:
        assert self.root is not None
        try:
            if self.root.parent.resolve() != self.root.parent.absolute():
                raise StenographerError(
                    "stenographer_store_unavailable",
                    "stenographer storage path must not traverse symbolic links",
                )
        except OSError as exc:
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer storage path is unavailable",
            ) from exc
        existed = self.root.exists()
        if existed and (
            self.root.is_symlink()
            or not self.root.is_dir()
            or self.root.resolve() != self.root.absolute()
        ):
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer storage root must be a private directory",
            )
        if existed and os.name != "nt" and stat.S_IMODE(self.root.stat().st_mode) & 0o077:
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer storage root permissions must be owner-only",
            )
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        objects_dir = self.root / "objects"
        objects_existed = objects_dir.exists()
        if objects_existed and (
            objects_dir.is_symlink()
            or not objects_dir.is_dir()
            or objects_dir.resolve() != objects_dir.absolute()
        ):
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer object storage must be a private directory",
            )
        if objects_existed and os.name != "nt" and stat.S_IMODE(objects_dir.stat().st_mode) & 0o077:
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer object storage permissions must be owner-only",
            )
        objects_dir.mkdir(mode=0o700, exist_ok=True)

        write_tmp_dir = self.root / ".write-tmp"
        write_tmp_existed = write_tmp_dir.exists()
        if write_tmp_existed and (
            write_tmp_dir.is_symlink()
            or not write_tmp_dir.is_dir()
            or write_tmp_dir.resolve() != write_tmp_dir.absolute()
        ):
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer write temporary storage must be a private directory",
            )
        if write_tmp_existed and os.name != "nt" and stat.S_IMODE(write_tmp_dir.stat().st_mode) & 0o077:
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer write temporary storage permissions must be owner-only",
            )
        write_tmp_dir.mkdir(mode=0o700, exist_ok=True)

        if os.name != "nt":
            if not existed:
                os.chmod(self.root, 0o700)
            if not objects_existed:
                os.chmod(objects_dir, 0o700)
            if not write_tmp_existed:
                os.chmod(write_tmp_dir, 0o700)

    @contextmanager
    def _locked_index(self) -> Iterator[None]:
        with self._thread_lock:
            if self.lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                if self.lock_path.is_symlink():
                    raise StenographerError(
                        "stenographer_index_unavailable",
                        "stenographer index lock is unavailable",
                    )
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                flags |= getattr(os, "O_BINARY", 0)
                descriptor = os.open(self.lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (
                    os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077
                ):
                    raise StenographerError(
                        "stenographer_index_unavailable",
                        "stenographer index lock is unavailable",
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
            except StenographerError:
                raise
            except OSError as exc:
                raise StenographerError(
                    "stenographer_index_unavailable",
                    "stenographer index lock is unavailable",
                ) from exc
            finally:
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _clone(record: StenographerRecord) -> StenographerRecord:
        return StenographerRecord(record.record_ref, record.record_type, copy.deepcopy(record.payload))

    @staticmethod
    def _validate_ref(record_ref: object) -> str:
        if isinstance(record_ref, str) and _OTHER_STORE_REF.fullmatch(record_ref):
            raise StenographerError(
                "stenographer_reference_scope_violation",
                "world and trap references cannot be inspected by the stenographer",
            )
        if not isinstance(record_ref, str) or _STENO_REF.fullmatch(record_ref) is None:
            raise StenographerError(
                "stenographer_invalid_reference",
                "stenographer reference must be 'steno:' followed by 64 lowercase hex characters",
            )
        return record_ref

    @staticmethod
    def _validate_action(action: object) -> dict[str, Any]:
        if not isinstance(action, dict) or set(action) != {"action_type", "actor", "context", "output"}:
            raise StenographerError("stenographer_store_corrupt", "AI action record has an invalid schema")
        action_type = action["action_type"]
        actor = action["actor"]
        context = action["context"]
        output = action["output"]
        if action_type not in STENOGRAPHER_ACTION_TYPES:
            raise StenographerError("stenographer_store_corrupt", "AI action type is not registered")
        if not isinstance(actor, dict) or set(actor) != {
            "member_id",
            "model_id",
            "adapter_id",
            "actor_kind",
        }:
            raise StenographerError("stenographer_store_corrupt", "AI actor identity is invalid")
        for field, maximum in (
            ("member_id", 128),
            ("model_id", 256),
            ("adapter_id", 128),
            ("actor_kind", 128),
        ):
            _validate_stored_identifier(actor.get(field), field, maximum)

        context_fields = {
            "session_id",
            "phase",
            "mode_id",
            "geometry_region_id",
            "evidence_snapshot_ref",
            "attempt",
            "stimulus_ref",
            "synthetic_context",
        }
        if not isinstance(context, dict) or set(context) != context_fields:
            raise StenographerError("stenographer_store_corrupt", "AI action context is invalid")
        for field in ("session_id", "mode_id", "geometry_region_id", "evidence_snapshot_ref"):
            value = context[field]
            if value is not None:
                _validate_stored_identifier(value, field, 256)
        phase = context["phase"]
        if phase is not None and phase not in _PHASES:
            raise StenographerError("stenographer_store_corrupt", "AI action phase is invalid")
        _validate_stored_identifier(context["attempt"], "attempt", 64)
        if not isinstance(context["stimulus_ref"], str) or _STIMULUS_REF.fullmatch(context["stimulus_ref"]) is None:
            raise StenographerError("stenographer_store_corrupt", "AI action stimulus reference is invalid")
        if type(context["synthetic_context"]) is not bool:
            raise StenographerError("stenographer_store_corrupt", "AI action context is invalid")
        if action_type.startswith("council.") and (context["session_id"] is None or phase is None):
            raise StenographerError("stenographer_store_corrupt", "Council action context is incomplete")
        if action_type == "failsafe.rehabilitation_response" and phase != "BLUE":
            raise StenographerError("stenographer_store_corrupt", "Failsafe action context is invalid")
        if action_type == "trap.subject_response" and context["synthetic_context"] is not True:
            raise StenographerError("stenographer_store_corrupt", "Trap subject action is not synthetic")

        if not isinstance(output, dict) or output.get("kind") not in {"text", "ballot"}:
            raise StenographerError("stenographer_store_corrupt", "AI action output is invalid")
        common = {"kind", "stored_char_count", "secret_scrubbed", "scrubbed_types"}
        if output["kind"] == "text":
            if set(output) != common | {"text"} or not isinstance(output.get("text"), str):
                raise StenographerError("stenographer_store_corrupt", "AI text output is invalid")
            stored_text = output["text"]
        else:
            if set(output) != common | {"choice", "rationale"}:
                raise StenographerError("stenographer_store_corrupt", "AI ballot output is invalid")
            if not isinstance(output.get("choice"), str) or not isinstance(output.get("rationale"), str):
                raise StenographerError("stenographer_store_corrupt", "AI ballot output is invalid")
            _validate_stored_identifier(output["choice"], "ballot choice", 64)
            stored_text = output["rationale"]
        if len(stored_text) > MAX_STENOGRAPHER_OUTPUT_CHARS:
            raise StenographerError("stenographer_store_corrupt", "AI action output exceeds the record limit")
        if output.get("stored_char_count") != len(stored_text):
            raise StenographerError("stenographer_store_corrupt", "AI action output length is invalid")
        if type(output.get("secret_scrubbed")) is not bool:
            raise StenographerError("stenographer_store_corrupt", "AI action scrub metadata is invalid")
        scrubbed_types = output.get("scrubbed_types")
        if not isinstance(scrubbed_types, list) or not all(
            isinstance(item, str)
            and 1 <= len(item) <= 64
            and all(0x20 <= ord(character) < 0x7F for character in item)
            for item in scrubbed_types
        ):
            raise StenographerError("stenographer_store_corrupt", "AI action scrub metadata is invalid")
        return copy.deepcopy(action)

    @classmethod
    def _load_validated(cls, record_ref: str, raw: object) -> StenographerRecord:
        if not isinstance(raw, dict) or set(raw) != {"record_ref", "record_type", "payload"}:
            raise StenographerError("stenographer_store_corrupt", "stenographer record envelope is invalid")
        if raw["record_ref"] != record_ref or raw["record_type"] != "ai_action_record":
            raise StenographerError("stenographer_store_corrupt", "stenographer record identity is invalid")
        payload = raw["payload"]
        expected_fields = {
            "schema_version",
            "sequence",
            "previous_record_ref",
            "recorded_at_utc",
            "lore",
            "authority",
            "action",
        }
        if not isinstance(payload, dict) or set(payload) != expected_fields:
            raise StenographerError("stenographer_store_corrupt", "stenographer record payload is invalid")
        if payload["schema_version"] != STENOGRAPHER_SCHEMA_VERSION:
            raise StenographerError("stenographer_store_corrupt", "stenographer record schema is invalid")
        if type(payload["sequence"]) is not int or payload["sequence"] < 1:
            raise StenographerError("stenographer_store_corrupt", "stenographer sequence is invalid")
        previous = payload["previous_record_ref"]
        if previous is not None and (not isinstance(previous, str) or _STENO_REF.fullmatch(previous) is None):
            raise StenographerError("stenographer_store_corrupt", "stenographer lineage reference is invalid")
        if not _valid_recorded_at(payload["recorded_at_utc"]):
            raise StenographerError("stenographer_store_corrupt", "stenographer record time is invalid")
        if payload["lore"] != _lore_envelope() or payload["authority"] != _authority_envelope():
            raise StenographerError("stenographer_store_corrupt", "stenographer watchman boundary is invalid")
        cls._validate_action(payload["action"])
        try:
            encoded = canonical_json(payload)
            expected = sha256_ref("steno", {"record_type": "ai_action_record", "payload": payload})
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise StenographerError("stenographer_store_corrupt", "stenographer record is not canonical JSON") from exc
        if len(encoded.encode("utf-8")) > MAX_STENOGRAPHER_RECORD_BYTES or expected != record_ref:
            raise StenographerError("stenographer_store_corrupt", "stenographer record failed verification")
        return StenographerRecord(record_ref, "ai_action_record", copy.deepcopy(payload))

    @classmethod
    def _read_validated(cls, record_ref: str, path: Path) -> StenographerRecord:
        try:
            info = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(info.st_mode)
                or info.st_size > MAX_STENOGRAPHER_RECORD_BYTES + 16_384
                or (os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077)
            ):
                raise StenographerError("stenographer_store_corrupt", "stenographer record file is invalid")
            text = path.read_text(encoding="utf-8")
            raw = json.loads(text)
        except StenographerError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise StenographerError("stenographer_store_corrupt", "stenographer record cannot be read") from exc
        record = cls._load_validated(record_ref, raw)
        if text != canonical_json(record.as_dict()) + "\n":
            raise StenographerError(
                "stenographer_store_corrupt",
                "stenographer record file is not canonical JSON",
            )
        return record

    def inspect(self, record_ref: str) -> StenographerRecord:
        record_ref = self._validate_ref(record_ref)
        with self._thread_lock:
            cached = self._objects.get(record_ref)
            if cached is not None:
                return self._clone(cached)
            if self.objects_dir is not None:
                path = self.objects_dir / f"{record_ref.removeprefix('steno:')}.json"
                if path.exists() or path.is_symlink():
                    record = self._read_validated(record_ref, path)
                    self._objects[record_ref] = record
                    return self._clone(record)
        raise StenographerError("stenographer_record_not_found", "stenographer record does not exist")

    def _all_refs_unlocked(self) -> list[str]:
        refs = set(self._objects)
        if self.objects_dir is not None:
            for path in self.objects_dir.iterdir():
                name = path.name
                if _PERM_OBJECT_NAME.fullmatch(name) is not None:
                    refs.add(f"steno:{path.stem}")
                    continue

                # Legacy NEXUS object-write temps may remain after an older
                # short-lived process is killed. They are not ledger records.
                # Keep the exception narrow: only the exact historical naming
                # pattern is tolerated, and temp-shaped symlinks/directories or
                # loose-permission files still fail closed.
                match = _OBJECT_TMP_NAME.fullmatch(name)
                if match is not None:
                    try:
                        info = path.lstat()
                    except FileNotFoundError:
                        # A concurrent legacy writer/cleanup may remove its own
                        # scratch entry after iterdir() yields it. Disappearance
                        # is benign; every other inspection failure stays fatal.
                        continue
                    except OSError as exc:
                        raise StenographerError(
                            "stenographer_store_corrupt",
                            "stenographer temporary record file cannot be inspected",
                        ) from exc
                    if (
                        path.is_symlink()
                        or not stat.S_ISREG(info.st_mode)
                        or (os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077)
                    ):
                        raise StenographerError(
                            "stenographer_store_corrupt",
                            "stenographer temporary record file is invalid",
                        )
                    permanent = self.objects_dir / f"{match.group(1)}.json"
                    if permanent.exists() and not permanent.is_symlink():
                        try:
                            path.unlink(missing_ok=True)
                        except OSError:
                            pass
                    continue

                raise StenographerError(
                    "stenographer_store_corrupt",
                    "stenographer record filename is invalid",
                )
        return sorted(refs)

    def _discover_chain_unlocked(self) -> tuple[list[str], str | None]:
        by_sequence: dict[int, StenographerRecord] = {}
        for record_ref in self._all_refs_unlocked():
            if self.objects_dir is None:
                record = self.inspect(record_ref)
            else:
                path = self.objects_dir / f"{record_ref.removeprefix('steno:')}.json"
                if not path.exists() and not path.is_symlink():
                    raise StenographerError(
                        "stenographer_store_corrupt",
                        "stenographer record file is missing",
                    )
                record = self._read_validated(record_ref, path)
                self._objects[record_ref] = record
            sequence = record.payload["sequence"]
            if sequence in by_sequence:
                raise StenographerError("stenographer_lineage_corrupt", "stenographer lineage contains a fork")
            by_sequence[sequence] = record
        if not by_sequence:
            return [], None
        expected_sequences = list(range(1, len(by_sequence) + 1))
        if sorted(by_sequence) != expected_sequences:
            raise StenographerError("stenographer_lineage_corrupt", "stenographer lineage contains a gap")
        ordered: list[str] = []
        previous: str | None = None
        for sequence in expected_sequences:
            record = by_sequence[sequence]
            if record.payload["previous_record_ref"] != previous:
                raise StenographerError("stenographer_lineage_corrupt", "stenographer lineage link is invalid")
            ordered.append(record.record_ref)
            previous = record.record_ref
        return ordered, previous

    def _index_body(self) -> dict[str, Any]:
        return {
            "schema_version": STENOGRAPHER_INDEX_SCHEMA_VERSION,
            "record_count": len(self._ordered_refs),
            "head_ref": self._head_ref,
        }

    def _save_index_unlocked(self) -> None:
        if self.index_path is None:
            return
        assert self.root is not None
        body = canonical_json(self._index_body()) + "\n"
        temporary = Path(f"{self.index_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = None
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.index_path)
            _fsync_directory(self.root)
        except OSError as exc:
            raise StenographerError(
                "stenographer_index_unavailable",
                "stenographer index could not be persisted",
            ) from exc
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
        ordered, head = self._discover_chain_unlocked()
        self._ordered_refs = ordered
        self._head_ref = head
        expected = self._index_body()
        valid = False
        fresh_store = False
        if self.index_path is None:
            valid = True
        elif self.index_path.is_symlink():
            raise StenographerError(
                "stenographer_index_unsafe",
                "stenographer index must not be a symbolic link",
            )
        elif self.index_path.exists():
            try:
                info = self.index_path.stat()
                if (
                    stat.S_ISREG(info.st_mode)
                    and info.st_size <= 65_536
                    and (os.name == "nt" or not stat.S_IMODE(info.st_mode) & 0o077)
                ):
                    text = self.index_path.read_text(encoding="utf-8")
                    raw = json.loads(text)
                    valid = raw == expected and text == canonical_json(expected) + "\n"
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                valid = False
        else:
            fresh_store = not ordered
        self.index_repaired = self.index_repaired or (not valid and not fresh_store)
        if not valid:
            self._save_index_unlocked()

    def refresh(self) -> None:
        with self._locked_index():
            self._load_and_repair_unlocked()

    def _persist_immutable(self, record: StenographerRecord) -> None:
        assert self.objects_dir is not None
        assert self.write_tmp_dir is not None
        objects_dir = self.objects_dir
        write_tmp_dir = self.write_tmp_dir
        digest = record.record_ref.removeprefix("steno:")
        target = objects_dir / f"{digest}.json"
        body = (canonical_json(record.as_dict()) + "\n").encode("utf-8")
        if target.exists() or target.is_symlink():
            self._read_validated(record.record_ref, target)
            return

        # Keep scratch files structurally outside the directory whose entries
        # are interpreted as immutable ledger objects. A crash can therefore
        # leave private debris without manufacturing a false corruption signal.
        temporary = write_tmp_dir / f".{digest}.tmp-{os.getpid()}-{threading.get_ident()}"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            flags |= getattr(os, "O_BINARY", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
                _fsync_directory(objects_dir)
            except FileExistsError:
                self._read_validated(record.record_ref, target)
        except StenographerError:
            raise
        except OSError as exc:
            raise StenographerError(
                "stenographer_store_unavailable",
                "stenographer record could not be persisted",
            ) from exc
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

    def append_action(self, action: dict[str, Any], *, recorded_at_utc: str) -> StenographerRecord:
        action = self._validate_action(action)
        if not _valid_recorded_at(recorded_at_utc):
            raise StenographerError("stenographer_clock_unavailable", "stenographer clock is unavailable")
        with self._locked_index():
            self._load_and_repair_unlocked()
            payload = {
                "schema_version": STENOGRAPHER_SCHEMA_VERSION,
                "sequence": len(self._ordered_refs) + 1,
                "previous_record_ref": self._head_ref,
                "recorded_at_utc": recorded_at_utc,
                "lore": _lore_envelope(),
                "authority": _authority_envelope(),
                "action": action,
            }
            try:
                record_ref = sha256_ref("steno", {"record_type": "ai_action_record", "payload": payload})
            except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                raise StenographerError(
                    "stenographer_invalid_action",
                    "AI action is not canonical JSON",
                ) from exc
            record = StenographerRecord(record_ref, "ai_action_record", payload)
            self._load_validated(record_ref, record.as_dict())
            if self.objects_dir is not None:
                self._persist_immutable(record)
            self._objects[record_ref] = record
            self._ordered_refs.append(record_ref)
            self._head_ref = record_ref
            self._save_index_unlocked()
            return self._clone(record)

    def ordered_records(self) -> list[StenographerRecord]:
        self.refresh()
        return [self.inspect(record_ref) for record_ref in self._ordered_refs]

    def verify(self) -> dict[str, Any]:
        self.refresh()
        return {
            "status": "ok",
            "schema_version": STENOGRAPHER_SCHEMA_VERSION,
            "integrity": "valid",
            "record_count": len(self._ordered_refs),
            "head_ref": self._head_ref,
            "index_repaired": self.index_repaired,
        }


class CourtroomStenographer:
    """Passive recorder for admitted AI outputs.

    It owns no actor, prompt, ballot, Council, WorldStore, TrapStore, AuthBroker,
    or command handle. Callers deliberately swallow recording failures after
    marking a gap so the watchman can never alter an AI result.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        store: StenographerStore | None = None,
        clock: Callable[[], str] = _utc_now,
        queue_capacity: int = MAX_STENOGRAPHER_PENDING_ACTIONS,
    ) -> None:
        if (
            type(queue_capacity) is not int
            or not 1 <= queue_capacity <= MAX_STENOGRAPHER_QUEUE_CAPACITY
        ):
            raise ValueError(
                "stenographer queue_capacity must be an exact integer in "
                f"[1, {MAX_STENOGRAPHER_QUEUE_CAPACITY}]"
            )
        self.store = store or StenographerStore(root)
        if not isinstance(self.store, StenographerStore):
            raise TypeError("CourtroomStenographer requires a StenographerStore")
        self._clock = clock
        self._gap_count = 0
        self._gap_reasons: Counter[str] = Counter()
        self._gap_lock = threading.Lock()
        self._queue_capacity = queue_capacity
        self._pending_actions: queue.Queue[_PendingAction] = queue.Queue(
            maxsize=queue_capacity
        )
        self._observer_state = threading.Condition()
        self._pending_count = 0
        self._worker_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    @property
    def root(self) -> Path | None:
        return self.store.root

    def mark_gap(self, reason: object) -> None:
        safe_reason = reason if isinstance(reason, str) and reason in {
            "stenographer_invalid_action",
            "stenographer_clock_unavailable",
            "stenographer_store_unavailable",
            "stenographer_index_unavailable",
            "stenographer_index_unsafe",
            "stenographer_store_corrupt",
            "stenographer_lineage_corrupt",
            "observer_queue_full",
            "observer_internal_error",
        } else "observer_internal_error"
        with self._gap_lock:
            self._gap_count += 1
            self._gap_reasons[safe_reason] += 1

    @property
    def pending_observations(self) -> int:
        with self._observer_state:
            return self._pending_count

    def _ensure_observer_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            worker = threading.Thread(
                target=self._observer_loop,
                name="nexus-stenographer-observer",
                daemon=True,
            )
            self._worker = worker
            worker.start()

    def _observer_loop(self) -> None:
        while True:
            pending = self._pending_actions.get()
            try:
                self.store.append_action(
                    pending.action,
                    recorded_at_utc=pending.recorded_at_utc,
                )
            except StenographerError as exc:
                self.mark_gap(exc.code)
            except Exception:
                self.mark_gap("observer_internal_error")
            finally:
                with self._observer_state:
                    self._pending_count -= 1
                    self._observer_state.notify_all()
                self._pending_actions.task_done()

    def _enqueue_action(self, action: dict[str, Any], *, recorded_at_utc: str) -> bool:
        if not _valid_recorded_at(recorded_at_utc):
            raise StenographerError(
                "stenographer_clock_unavailable",
                "stenographer clock is unavailable",
            )
        self._ensure_observer_worker()
        pending = _PendingAction(copy.deepcopy(action), recorded_at_utc)
        with self._observer_state:
            try:
                self._pending_actions.put_nowait(pending)
            except queue.Full:
                accepted = False
            else:
                self._pending_count += 1
                accepted = True
        if not accepted:
            self.mark_gap("observer_queue_full")
        return accepted

    def wait_for_idle(self, timeout_seconds: float = STENOGRAPHER_READ_DRAIN_SECONDS) -> bool:
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        deadline = time.monotonic() + float(timeout_seconds)
        with self._observer_state:
            while self._pending_count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._observer_state.wait(remaining)
            return True

    def shutdown(self, timeout_seconds: float = STENOGRAPHER_READ_DRAIN_SECONDS) -> bool:
        """Best-effort drain of accepted observer writes before process exit."""

        return self.wait_for_idle(timeout_seconds)

    def _drain_for_read(self) -> None:
        if not self.wait_for_idle():
            raise StenographerError(
                "stenographer_observer_busy",
                "stenographer observations are still pending",
            )

    def _context(
        self,
        *,
        stimulus: object,
        session_id: str | None,
        phase: str | None,
        mode_id: str | None,
        geometry_region_id: str | None,
        evidence_snapshot_ref: str | None,
        attempt: str,
        synthetic_context: bool,
    ) -> dict[str, Any]:
        try:
            stimulus_ref = sha256_ref("stimulus", stimulus)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise StenographerError(
                "stenographer_invalid_action",
                "AI action stimulus is not canonical JSON",
            ) from exc
        context = {
            "session_id": session_id,
            "phase": phase,
            "mode_id": mode_id,
            "geometry_region_id": geometry_region_id,
            "evidence_snapshot_ref": evidence_snapshot_ref,
            "attempt": _bounded_identifier(attempt, "attempt", 64),
            "stimulus_ref": stimulus_ref,
            "synthetic_context": synthetic_context,
        }
        return context

    @staticmethod
    def _text_output(text: object) -> dict[str, Any]:
        if not isinstance(text, str) or len(text) > MAX_STENOGRAPHER_OUTPUT_CHARS:
            raise StenographerError(
                "stenographer_invalid_action",
                "AI output exceeds the stenographer record limit",
            )
        scrubbed = SecretScrubber().scrub(text)
        return {
            "kind": "text",
            "text": scrubbed.text,
            "stored_char_count": len(scrubbed.text),
            "secret_scrubbed": scrubbed.changed,
            "scrubbed_types": [event.secret_type for event in scrubbed.events],
        }

    @staticmethod
    def _ballot_output(choice: object, rationale: object) -> dict[str, Any]:
        choice = _bounded_identifier(choice, "ballot choice", 64)
        if not isinstance(rationale, str) or len(rationale) > MAX_STENOGRAPHER_OUTPUT_CHARS:
            raise StenographerError(
                "stenographer_invalid_action",
                "AI ballot rationale exceeds the stenographer record limit",
            )
        scrubbed = SecretScrubber().scrub(rationale)
        return {
            "kind": "ballot",
            "choice": choice,
            "rationale": scrubbed.text,
            "stored_char_count": len(scrubbed.text),
            "secret_scrubbed": scrubbed.changed,
            "scrubbed_types": [event.secret_type for event in scrubbed.events],
        }

    def _text_action(
        self,
        action_type: str,
        actor: object,
        text: str,
        *,
        stimulus: object,
        session_id: str | None = None,
        phase: str | None = None,
        mode_id: str | None = None,
        geometry_region_id: str | None = None,
        evidence_snapshot_ref: str | None = None,
        attempt: str = "initial",
        synthetic_context: bool = False,
    ) -> dict[str, Any]:
        return {
            "action_type": action_type,
            "actor": _actor_identity(actor),
            "context": self._context(
                stimulus=stimulus,
                session_id=session_id,
                phase=phase,
                mode_id=mode_id,
                geometry_region_id=geometry_region_id,
                evidence_snapshot_ref=evidence_snapshot_ref,
                attempt=attempt,
                synthetic_context=synthetic_context,
            ),
            "output": self._text_output(text),
        }

    def record_text(
        self,
        action_type: str,
        actor: object,
        text: str,
        *,
        stimulus: object,
        session_id: str | None = None,
        phase: str | None = None,
        mode_id: str | None = None,
        geometry_region_id: str | None = None,
        evidence_snapshot_ref: str | None = None,
        attempt: str = "initial",
        synthetic_context: bool = False,
    ) -> StenographerRecord:
        action = self._text_action(
            action_type,
            actor,
            text,
            stimulus=stimulus,
            session_id=session_id,
            phase=phase,
            mode_id=mode_id,
            geometry_region_id=geometry_region_id,
            evidence_snapshot_ref=evidence_snapshot_ref,
            attempt=attempt,
            synthetic_context=synthetic_context,
        )
        return self.store.append_action(action, recorded_at_utc=self._clock())

    def observe_text(
        self,
        action_type: str,
        actor: object,
        text: str,
        *,
        stimulus: object,
        session_id: str | None = None,
        phase: str | None = None,
        mode_id: str | None = None,
        geometry_region_id: str | None = None,
        evidence_snapshot_ref: str | None = None,
        attempt: str = "initial",
        synthetic_context: bool = False,
    ) -> bool:
        """Submit an observation without waiting for storage or its lock."""

        try:
            action = self._text_action(
                action_type,
                actor,
                text,
                stimulus=stimulus,
                session_id=session_id,
                phase=phase,
                mode_id=mode_id,
                geometry_region_id=geometry_region_id,
                evidence_snapshot_ref=evidence_snapshot_ref,
                attempt=attempt,
                synthetic_context=synthetic_context,
            )
            return self._enqueue_action(action, recorded_at_utc=self._clock())
        except StenographerError as exc:
            self.mark_gap(exc.code)
        except Exception:
            self.mark_gap("observer_internal_error")
        return False

    def _ballot_action(
        self,
        actor: object,
        choice: str,
        rationale: str,
        *,
        stimulus: object,
        session_id: str,
        mode_id: str,
        geometry_region_id: str,
        evidence_snapshot_ref: str,
    ) -> dict[str, Any]:
        return {
            "action_type": "council.ballot",
            "actor": _actor_identity(actor),
            "context": self._context(
                stimulus=stimulus,
                session_id=session_id,
                phase="BLUE",
                mode_id=mode_id,
                geometry_region_id=geometry_region_id,
                evidence_snapshot_ref=evidence_snapshot_ref,
                attempt="sealed_ballot",
                synthetic_context=False,
            ),
            "output": self._ballot_output(choice, rationale),
        }

    def record_ballot(
        self,
        actor: object,
        choice: str,
        rationale: str,
        *,
        stimulus: object,
        session_id: str,
        mode_id: str,
        geometry_region_id: str,
        evidence_snapshot_ref: str,
    ) -> StenographerRecord:
        action = self._ballot_action(
            actor,
            choice,
            rationale,
            stimulus=stimulus,
            session_id=session_id,
            mode_id=mode_id,
            geometry_region_id=geometry_region_id,
            evidence_snapshot_ref=evidence_snapshot_ref,
        )
        return self.store.append_action(action, recorded_at_utc=self._clock())

    def observe_ballot(
        self,
        actor: object,
        choice: str,
        rationale: str,
        *,
        stimulus: object,
        session_id: str,
        mode_id: str,
        geometry_region_id: str,
        evidence_snapshot_ref: str,
    ) -> bool:
        """Submit a ballot observation without waiting for persistence."""

        try:
            action = self._ballot_action(
                actor,
                choice,
                rationale,
                stimulus=stimulus,
                session_id=session_id,
                mode_id=mode_id,
                geometry_region_id=geometry_region_id,
                evidence_snapshot_ref=evidence_snapshot_ref,
            )
            return self._enqueue_action(action, recorded_at_utc=self._clock())
        except StenographerError as exc:
            self.mark_gap(exc.code)
        except Exception:
            self.mark_gap("observer_internal_error")
        return False

    def record_trap_reply(
        self,
        reply: object,
        *,
        message: str,
        incident_id: str,
        scenario_id: str,
    ) -> StenographerRecord:
        class _TrapMember:
            member_id = "trap_subject"
            model_id = getattr(reply, "model_id", None)
            adapter_id = getattr(reply, "adapter_id", None)

        class _TrapActor:
            member = _TrapMember()

        text = getattr(reply, "text", None)
        return self.record_text(
            "trap.subject_response",
            _TrapActor(),
            text,
            stimulus={"message": message, "scenario_id": scenario_id},
            session_id=incident_id,
            attempt="synthetic_reply",
            synthetic_context=True,
        )

    def observe_trap_reply(
        self,
        reply: object,
        *,
        message: str,
        incident_id: str,
        scenario_id: str,
    ) -> bool:
        class _TrapMember:
            member_id = "trap_subject"
            model_id = getattr(reply, "model_id", None)
            adapter_id = getattr(reply, "adapter_id", None)

        class _TrapActor:
            member = _TrapMember()

        return self.observe_text(
            "trap.subject_response",
            _TrapActor(),
            getattr(reply, "text", None),
            stimulus={"message": message, "scenario_id": scenario_id},
            session_id=incident_id,
            attempt="synthetic_reply",
            synthetic_context=True,
        )

    def status(self) -> dict[str, Any]:
        self._drain_for_read()
        integrity = self.store.verify()
        with self._gap_lock:
            gap_count = self._gap_count
            gap_reasons = dict(sorted(self._gap_reasons.items()))
        return {
            "status": "ok",
            "schema_version": STENOGRAPHER_SCHEMA_VERSION,
            "role": "watchman_only",
            "record_scope": "ai_actions_only",
            "persistence": "canonical_json_files" if self.root is not None else "memory_only",
            "record_count": integrity["record_count"],
            "head_ref": integrity["head_ref"],
            "integrity": integrity["integrity"],
            "index_repaired": integrity["index_repaired"],
            "complete_since_process_start": gap_count == 0,
            "gap_count": gap_count,
            "gap_reasons": gap_reasons,
            "handoff": "bounded_nonblocking_queue",
            "queue_capacity": self._queue_capacity,
            "pending_observations": self.pending_observations,
            "lore": _lore_envelope(),
            "authority": _authority_envelope(),
        }

    def list_records(
        self,
        *,
        limit: int = 100,
        action_type: str | None = None,
        member_id: str | None = None,
    ) -> dict[str, Any]:
        self._drain_for_read()
        if type(limit) is not int or not 1 <= limit <= MAX_STENOGRAPHER_LIST_LIMIT:
            raise StenographerError(
                "stenographer_invalid_query",
                f"limit must be an integer in [1, {MAX_STENOGRAPHER_LIST_LIMIT}]",
            )
        if action_type is not None and action_type not in STENOGRAPHER_ACTION_TYPES:
            raise StenographerError("stenographer_invalid_query", "action_type is not registered")
        if member_id is not None:
            member_id = _bounded_identifier(member_id, "member_id", 128)
        records = self.store.ordered_records()
        filtered = [
            record
            for record in records
            if (action_type is None or record.payload["action"]["action_type"] == action_type)
            and (member_id is None or record.payload["action"]["actor"]["member_id"] == member_id)
        ]
        selected_reversed: list[StenographerRecord] = []
        selected_bytes = 0
        for record in reversed(filtered):
            if len(selected_reversed) >= limit:
                break
            record_bytes = len(canonical_json(record.as_dict()).encode("utf-8"))
            if selected_reversed and selected_bytes + record_bytes > MAX_STENOGRAPHER_LIST_BYTES:
                break
            selected_reversed.append(record)
            selected_bytes += record_bytes
        selected = list(reversed(selected_reversed))
        return {
            "status": "ok",
            "schema_version": STENOGRAPHER_SCHEMA_VERSION,
            "total_matches": len(filtered),
            "returned": len(selected),
            "returned_record_bytes": selected_bytes,
            "truncated": len(selected) < len(filtered),
            "records": [record.as_dict() for record in selected],
        }

    def inspect(self, record_ref: str) -> dict[str, Any]:
        self._drain_for_read()
        record = self.store.inspect(record_ref)
        return {
            "status": "ok",
            "record": record.as_dict(),
            "canonical_json": canonical_json(record.as_dict()),
        }

    def verify(self) -> dict[str, Any]:
        self._drain_for_read()
        return self.store.verify()

    def summary(self) -> dict[str, Any]:
        self._drain_for_read()
        records = self.store.ordered_records()
        action_counts = Counter(record.payload["action"]["action_type"] for record in records)
        member_counts = Counter(record.payload["action"]["actor"]["member_id"] for record in records)
        adapter_counts = Counter(record.payload["action"]["actor"]["adapter_id"] for record in records)
        scrubbed_records = sum(
            1 for record in records if record.payload["action"]["output"]["secret_scrubbed"]
        )
        return {
            "status": "ok",
            "schema_version": STENOGRAPHER_SCHEMA_VERSION,
            "record_count": len(records),
            "head_ref": records[-1].record_ref if records else None,
            "action_counts": dict(sorted(action_counts.items())),
            "member_counts": dict(sorted(member_counts.items())),
            "adapter_counts": dict(sorted(adapter_counts.items())),
            "secret_scrubbed_records": scrubbed_records,
            "first_recorded_at_utc": records[0].payload["recorded_at_utc"] if records else None,
            "last_recorded_at_utc": records[-1].payload["recorded_at_utc"] if records else None,
            "analysis_only": True,
        }

    def export_manifest(self) -> dict[str, Any]:
        self._drain_for_read()
        records = self.store.ordered_records()
        return {
            "status": "ok",
            "schema_version": STENOGRAPHER_EXPORT_SCHEMA_VERSION,
            "format": "canonical_json",
            "record_count": len(records),
            "head_ref": records[-1].record_ref if records else None,
            "record_refs": [record.record_ref for record in records],
            "external_path": None,
            "read_only": True,
        }

    @staticmethod
    def reveal_lore(phrase: object) -> dict[str, object]:
        revealed = reveal_lore(phrase)
        if revealed is None:
            raise StenographerError("stenographer_lore_sealed", "stenographer lore remains sealed")
        return revealed


def default_stenographer_root() -> Path:
    return (Path.cwd() / ".nexus-stenographer").absolute()
