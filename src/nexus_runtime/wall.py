from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import stat
import threading
from typing import Any, Callable, Iterator

from .scrub import SecretScrubber
from .world import WorldObject, WorldStore


WALL_SCHEMA_VERSION = "nexus-bbs-wall/1"
WALL_POLICY_ID = "nexus-bbs-wall-social-memory-v1"
WALL_POST_OBJECT_TYPE = "nexus_wall_post"
WALL_TOMBSTONE_OBJECT_TYPE = "nexus_wall_tombstone"
WALL_RESERVED_OBJECT_TYPES = frozenset({WALL_POST_OBJECT_TYPE, WALL_TOMBSTONE_OBJECT_TYPE})
MAX_WALL_POST_CHARS = 512
MAX_WALL_REASON_CHARS = 256
MAX_WALL_LIST_LIMIT = 100
MAX_WALL_REBUILD_OBJECTS = 100_000

_PROVENANCE = {"actor": "nexus", "subsystem": "bbs_wall"}
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SCRUBBER = SecretScrubber()
_POST_FIELDS = {
    "schema_version",
    "sequence",
    "previous_event_ref",
    "created_at_utc",
    "author",
    "text",
    "evidence_effect",
    "authority_effect",
}
_TOMBSTONE_FIELDS = {
    "schema_version",
    "sequence",
    "previous_event_ref",
    "created_at_utc",
    "target_post_ref",
    "moderator_id",
    "reason",
    "display_effect",
    "evidence_effect",
    "authority_effect",
}


class WallError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def wall_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": WALL_SCHEMA_VERSION,
        "policy_id": WALL_POLICY_ID,
        "principle": "wall_post_is_social_memory_not_evidence",
        "tagline": "Leave a message. Someone may read it in a hundred years.",
        "append_only": True,
        "chronology_rule": "immutable sequence and predecessor lineage define Wall order; timestamps are descriptive metadata only",
        "tombstone_rule": "moderation appends an explicit tombstone; it never deletes or rewrites the immutable source post",
        "normal_display_hides_tombstoned_text": True,
        "original_object_remains_auditable": True,
        "identity_rule": "human/model labels are contextual identity labels, never rank, prestige, evidence weight or authority",
        "secret_scrubber_applies": True,
        "authority_invariants": {
            "vote_weight_created": 0,
            "council_seats_created": 0,
            "citizenship_effect": "none",
            "evidence_promoted": False,
            "tool_authority_created": False,
            "popularity_promotes_truth": False,
            "wall_post_is_council_input": False,
        },
        "evidence_effect": "none",
        "authority_effect": "none",
    }


def _identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise WallError("wall_invalid_identity", f"{field} must be a bounded identifier")
    if _SCRUBBER.scrub(value).changed:
        raise WallError("wall_invalid_identity", f"{field} must not contain credential-shaped material")
    return value


def _bounded_single_line(value: Any, *, field: str, limit: int, code: str) -> str:
    if not isinstance(value, str):
        raise WallError(code, f"{field} must be text")
    text = value.strip()
    if not text or len(text) > limit or "\n" in text or "\r" in text:
        raise WallError(code, f"{field} must be one non-empty line of at most {limit} characters")
    if _SCRUBBER.scrub(text).changed:
        raise WallError(code, f"{field} must not contain credential-shaped material")
    return text


def _utc_stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def _parse_stamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise WallError("wall_history_corrupt", "Wall timestamp must be RFC3339 UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise WallError("wall_history_corrupt", "Wall timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise WallError("wall_history_corrupt", "Wall timestamp is not timezone aware")
    return parsed.astimezone(timezone.utc)


class WallService:
    """Append-only BBS Wall over recognized immutable WorldStore history.

    The event chain is authoritative only for Wall chronology.  It creates no
    Council, evidence, civic or tool authority.  No mutable head/index is needed;
    every view is reconstructable from the recognized immutable object history.
    """

    def __init__(self, world: WorldStore, *, clock: Callable[[], datetime] | None = None) -> None:
        self.world = world
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._thread_lock = threading.RLock()
        self._lock_root = None if world.root is None else Path(world.root) / "wall"
        self._lock_path = None if self._lock_root is None else self._lock_root / "wall.lock"
        if self._lock_root is not None:
            self._prepare_lock_root()

    def _prepare_lock_root(self) -> None:
        assert self._lock_root is not None
        if self._lock_root.is_symlink() or (self._lock_root.exists() and not self._lock_root.is_dir()):
            raise WallError("wall_storage_unsafe", "Wall lock root must be a private directory")
        self._lock_root.mkdir(mode=0o700, parents=False, exist_ok=True)
        if os.name != "nt":
            self._lock_root.chmod(0o700)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return
            assert self._lock_root is not None
            if self._lock_root.is_symlink() or self._lock_path.is_symlink():
                raise WallError("wall_storage_unsafe", "Wall lock path must not be a symbolic link")
            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT
                flags |= getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(self._lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077):
                    raise WallError("wall_storage_unsafe", "Wall lock must be an owner-only regular file")
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
            except WallError:
                raise
            except OSError as exc:
                raise WallError("wall_storage_unavailable", "Wall lock could not be acquired") from exc
            finally:
                if descriptor is not None:
                    os.close(descriptor)

    def _snapshot_objects(self) -> dict[str, WorldObject]:
        continuity_lock = getattr(self.world, "_locked_continuity", None)
        resolve_head = getattr(self.world, "_resolve_head", None)
        history = getattr(self.world, "_history", None)
        valid_sources = getattr(self.world, "_valid_object_sources", None)
        quorum = getattr(self.world, "write_quorum", None)
        if all(callable(item) for item in (continuity_lock, resolve_head, history, valid_sources)) and isinstance(quorum, int):
            snapshot: dict[str, WorldObject] = {}
            with continuity_lock():
                head_ref, _ = resolve_head(require_chain=True)
                refs, _ = history(head_ref, require_manifest_quorum=False)
                if len(refs) > MAX_WALL_REBUILD_OBJECTS:
                    raise WallError("wall_history_too_large", "Wall rebuild object budget exceeded")
                for ref in sorted(refs):
                    sources = valid_sources(ref)
                    if len(sources) < quorum:
                        from .world_continuity import WorldContinuityError

                        raise WorldContinuityError(
                            "world_continuity_read_quorum_unavailable",
                            "recognized object does not currently have a verified read quorum",
                        )
                    snapshot[ref] = sources[0][1]
            return snapshot

        objects_dir = self.world.objects_dir
        if objects_dir is None:
            refs = sorted(getattr(self.world, "_objects", {}))
        else:
            entries = sorted(path for path in objects_dir.iterdir() if path.name.endswith(".json"))
            refs = [
                f"object:{path.name.removesuffix('.json')}"
                for path in entries
                if len(path.name.removesuffix(".json")) == 64
            ]
        if len(refs) > MAX_WALL_REBUILD_OBJECTS:
            raise WallError("wall_history_too_large", "Wall rebuild object budget exceeded")
        snapshot: dict[str, WorldObject] = {}
        for ref in refs:
            snapshot[ref] = self.world.inspect(ref)
        return snapshot

    @staticmethod
    def _validate_author(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            raise WallError("wall_history_corrupt", "Wall author must be an object")
        kind = value.get("kind")
        if kind == "human" and set(value) == {"kind", "author_id"}:
            return {"kind": "human", "author_id": _identity(value.get("author_id"), "author_id")}
        if kind == "model" and set(value) == {"kind", "author_id", "model_id"}:
            return {
                "kind": "model",
                "author_id": _identity(value.get("author_id"), "author_id"),
                "model_id": _identity(value.get("model_id"), "model_id"),
            }
        raise WallError("wall_history_corrupt", "Wall author schema is invalid")

    @classmethod
    def _validate_common(cls, obj: WorldObject, payload: dict[str, Any]) -> tuple[int, str | None, str]:
        if obj.provenance != _PROVENANCE:
            raise WallError("wall_history_corrupt", "Wall event provenance is invalid")
        if payload.get("schema_version") != WALL_SCHEMA_VERSION:
            raise WallError("wall_history_corrupt", "Wall event schema version is invalid")
        sequence = payload.get("sequence")
        if type(sequence) is not int or sequence < 1:
            raise WallError("wall_history_corrupt", "Wall event sequence is invalid")
        previous = payload.get("previous_event_ref")
        if previous is not None and not isinstance(previous, str):
            raise WallError("wall_history_corrupt", "Wall predecessor ref is invalid")
        stamp = payload.get("created_at_utc")
        _parse_stamp(stamp)
        if payload.get("evidence_effect") != "none" or payload.get("authority_effect") != "none":
            raise WallError("wall_history_corrupt", "Wall event must remain non-evidence and non-authoritative")
        return sequence, previous, stamp

    @classmethod
    def _validate_event(cls, obj: WorldObject) -> tuple[int, str | None, str]:
        payload = obj.payload
        if obj.object_type == WALL_POST_OBJECT_TYPE:
            if set(payload) != _POST_FIELDS:
                raise WallError("wall_history_corrupt", "Wall post closed schema is invalid")
            common = cls._validate_common(obj, payload)
            cls._validate_author(payload.get("author"))
            _bounded_single_line(
                payload.get("text"),
                field="text",
                limit=MAX_WALL_POST_CHARS,
                code="wall_history_corrupt",
            )
            return common
        if obj.object_type == WALL_TOMBSTONE_OBJECT_TYPE:
            if set(payload) != _TOMBSTONE_FIELDS:
                raise WallError("wall_history_corrupt", "Wall tombstone closed schema is invalid")
            common = cls._validate_common(obj, payload)
            if not isinstance(payload.get("target_post_ref"), str):
                raise WallError("wall_history_corrupt", "Wall tombstone target is invalid")
            _identity(payload.get("moderator_id"), "moderator_id")
            _bounded_single_line(
                payload.get("reason"),
                field="reason",
                limit=MAX_WALL_REASON_CHARS,
                code="wall_history_corrupt",
            )
            if payload.get("display_effect") != "hide_post_text":
                raise WallError("wall_history_corrupt", "Wall tombstone display effect is invalid")
            return common
        raise WallError("wall_history_corrupt", "unknown Wall event type")

    def _events(self) -> list[WorldObject]:
        snapshot = self._snapshot_objects()
        events = [
            obj
            for obj in snapshot.values()
            if obj.object_type in WALL_RESERVED_OBJECT_TYPES
        ]
        if len(events) > MAX_WALL_REBUILD_OBJECTS:
            raise WallError("wall_history_too_large", "Wall event budget exceeded")
        rows: list[tuple[int, WorldObject, str | None]] = []
        seen_sequences: set[int] = set()
        for obj in events:
            sequence, previous, _ = self._validate_event(obj)
            if sequence in seen_sequences:
                raise WallError("wall_history_fork", "multiple Wall events claim the same sequence")
            seen_sequences.add(sequence)
            rows.append((sequence, obj, previous))
        rows.sort(key=lambda item: item[0])
        expected_previous: str | None = None
        posts: set[str] = set()
        tombstoned: set[str] = set()
        for expected_sequence, (sequence, obj, previous) in enumerate(rows, start=1):
            if sequence != expected_sequence or previous != expected_previous:
                raise WallError("wall_history_corrupt", "Wall event lineage is not contiguous")
            if obj.object_type == WALL_POST_OBJECT_TYPE:
                posts.add(obj.object_id)
            else:
                target = obj.payload["target_post_ref"]
                if target not in posts:
                    raise WallError("wall_history_corrupt", "Wall tombstone must target an earlier valid post")
                if target in tombstoned:
                    raise WallError("wall_history_corrupt", "a Wall post may be tombstoned only once")
                tombstoned.add(target)
            expected_previous = obj.object_id
        return [item[1] for item in rows]

    def _create_event(self, object_type: str, fields: dict[str, Any]) -> WorldObject:
        events = self._events()
        previous = events[-1].object_id if events else None
        payload = {
            "schema_version": WALL_SCHEMA_VERSION,
            "sequence": len(events) + 1,
            "previous_event_ref": previous,
            "created_at_utc": _utc_stamp(self._clock()),
            **fields,
            "evidence_effect": "none",
            "authority_effect": "none",
        }
        obj = self.world.create_object(object_type, payload, _PROVENANCE)
        self._validate_event(obj)
        return obj

    def post_human(self, *, author_id: str, text: str) -> WorldObject:
        author_id = _identity(author_id, "author_id")
        text = _bounded_single_line(text, field="text", limit=MAX_WALL_POST_CHARS, code="wall_post_invalid")
        with self._locked():
            return self._create_event(
                WALL_POST_OBJECT_TYPE,
                {"author": {"kind": "human", "author_id": author_id}, "text": text},
            )

    def post_model(self, *, author_id: str, model_id: str, text: str) -> WorldObject:
        author_id = _identity(author_id, "author_id")
        model_id = _identity(model_id, "model_id")
        text = _bounded_single_line(text, field="text", limit=MAX_WALL_POST_CHARS, code="wall_post_invalid")
        with self._locked():
            return self._create_event(
                WALL_POST_OBJECT_TYPE,
                {
                    "author": {"kind": "model", "author_id": author_id, "model_id": model_id},
                    "text": text,
                },
            )

    def tombstone(self, *, moderator_id: str, post_ref: str, reason: str) -> WorldObject:
        moderator_id = _identity(moderator_id, "moderator_id")
        reason = _bounded_single_line(
            reason,
            field="reason",
            limit=MAX_WALL_REASON_CHARS,
            code="wall_tombstone_invalid",
        )
        if not isinstance(post_ref, str):
            raise WallError("wall_tombstone_invalid", "post_ref must be an object reference")
        with self._locked():
            events = self._events()
            posts = {obj.object_id for obj in events if obj.object_type == WALL_POST_OBJECT_TYPE}
            existing = {
                obj.payload["target_post_ref"]
                for obj in events
                if obj.object_type == WALL_TOMBSTONE_OBJECT_TYPE
            }
            if post_ref not in posts:
                raise WallError("wall_post_not_found", "Wall tombstone target is not a recognized Wall post")
            if post_ref in existing:
                raise WallError("wall_already_tombstoned", "Wall post already has a tombstone")
            previous = events[-1].object_id if events else None
            payload = {
                "schema_version": WALL_SCHEMA_VERSION,
                "sequence": len(events) + 1,
                "previous_event_ref": previous,
                "created_at_utc": _utc_stamp(self._clock()),
                "target_post_ref": post_ref,
                "moderator_id": moderator_id,
                "reason": reason,
                "display_effect": "hide_post_text",
                "evidence_effect": "none",
                "authority_effect": "none",
            }
            obj = self.world.create_object(WALL_TOMBSTONE_OBJECT_TYPE, payload, _PROVENANCE)
            self._validate_event(obj)
            return obj

    def inspect_event(self, event_ref: str) -> dict[str, Any]:
        try:
            obj = self.world.inspect(event_ref)
        except KeyError as exc:
            raise WallError("wall_event_not_found", "Wall event was not found") from exc
        if obj.object_type not in WALL_RESERVED_OBJECT_TYPES:
            raise WallError("wall_event_not_found", "object is not a Wall event")
        self._validate_event(obj)
        events = self._events()
        if event_ref not in {item.object_id for item in events}:
            raise WallError("wall_event_not_found", "Wall event is not in recognized Wall history")
        return obj.as_dict()

    def list_posts(
        self,
        *,
        limit: int = 20,
        order: str = "newest",
        author_id: str | None = None,
        since_seconds: int | None = None,
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_WALL_LIST_LIMIT:
            raise WallError("wall_invalid_limit", f"limit must be 1-{MAX_WALL_LIST_LIMIT}")
        if order not in {"newest", "oldest"}:
            raise WallError("wall_invalid_order", "order must be newest or oldest")
        if author_id is not None:
            author_id = _identity(author_id, "author_id")
        threshold: datetime | None = None
        if since_seconds is not None:
            if type(since_seconds) is not int or not 1 <= since_seconds <= 315_576_000:
                raise WallError("wall_invalid_since", "since_seconds must be 1..315576000")
            now = self._clock()
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            threshold = now.astimezone(timezone.utc) - timedelta(seconds=since_seconds)

        events = self._events()
        tombstones = {
            obj.payload["target_post_ref"]: obj
            for obj in events
            if obj.object_type == WALL_TOMBSTONE_OBJECT_TYPE
        }
        rows: list[dict[str, Any]] = []
        for obj in events:
            if obj.object_type != WALL_POST_OBJECT_TYPE:
                continue
            payload = obj.payload
            author = self._validate_author(payload["author"])
            if author_id is not None and author["author_id"] != author_id:
                continue
            if threshold is not None and _parse_stamp(payload["created_at_utc"]) < threshold:
                continue
            tombstone = tombstones.get(obj.object_id)
            rows.append(
                {
                    "sequence": payload["sequence"],
                    "post_ref": obj.object_id,
                    "created_at_utc": payload["created_at_utc"],
                    "author": author,
                    "text": "[tombstoned]" if tombstone is not None else payload["text"],
                    "tombstoned": tombstone is not None,
                    "tombstone_ref": None if tombstone is None else tombstone.object_id,
                    "tombstone_reason": None if tombstone is None else tombstone.payload["reason"],
                    "evidence_effect": "none",
                    "authority_effect": "none",
                }
            )
        total_filtered = len(rows)
        if order == "newest":
            rows.reverse()
        rows = rows[:limit]
        return {
            "schema_version": WALL_SCHEMA_VERSION,
            "posts": rows,
            "returned": len(rows),
            "matched_posts": total_filtered,
            "total_events": len(events),
            "total_tombstones": len(tombstones),
            "order": order,
            "evidence_effect": "none",
            "authority_effect": "none",
        }


__all__ = [
    "MAX_WALL_LIST_LIMIT",
    "MAX_WALL_POST_CHARS",
    "MAX_WALL_REASON_CHARS",
    "WALL_POLICY_ID",
    "WALL_POST_OBJECT_TYPE",
    "WALL_RESERVED_OBJECT_TYPES",
    "WALL_SCHEMA_VERSION",
    "WALL_TOMBSTONE_OBJECT_TYPE",
    "WallError",
    "WallService",
    "wall_policy_snapshot",
]
