from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement anchor, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


WALL_PY = r'''from __future__ import annotations

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
'''

WALL_API_PY = r'''from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import AdapterError
from .citizenship import CitizenshipError
from .control_plane import RequestBudgetError, validate_control_request
from .culture import CultureError
from .culture_api_overlay import CultureNexusAPI
from .modes import get_mode
from .progression import ProgressionError
from .trap import TrapError
from .wall import (
    MAX_WALL_LIST_LIMIT,
    MAX_WALL_POST_CHARS,
    WALL_RESERVED_OBJECT_TYPES,
    WallError,
    WallService,
    wall_policy_snapshot,
)
from .world_continuity import WorldContinuityError


_WALL_OPERATIONS = frozenset(
    {
        "wall.policy",
        "wall.list",
        "wall.post",
        "wall.ai_post",
        "wall.tombstone",
        "wall.inspect",
    }
)
_WALL_MUTATIONS = frozenset({"wall.post", "wall.ai_post", "wall.tombstone"})


class WallNexusAPI(CultureNexusAPI):
    """PR #50 final feature overlay: append-only low-stakes BBS Wall."""

    def __init__(self, world_root: str | Path | None = None, **kwargs: Any) -> None:
        super().__init__(world_root, **kwargs)
        self.wall = WallService(self.world)

    def _wall_human_post(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = "wall.post"
        self._require_exact_fields(request, operation, {"author_id", "text"})
        author_id = self._require_str(request, "author_id")
        if self.scrubber.scrub(author_id).changed:
            raise WallError("wall_invalid_identity", "author_id must not contain credential-shaped material")
        raw_text = self._require_str(request, "text")
        clean = self.scrubber.scrub(raw_text)
        post = self._run_real_mutation(lambda: self.wall.post_human(author_id=author_id, text=clean.text))
        response: dict[str, Any] = {
            "status": "ok",
            "post": post.as_dict(),
            "secret_scrub": {"changed": clean.changed},
            "evidence_effect": "none",
            "authority_effect": "none",
        }
        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _wall_ai_post(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = "wall.ai_post"
        self._require_exact_fields(request, operation, {"member", "prompt"})
        raw_prompt = self._require_str(request, "prompt")
        if len(raw_prompt) > 4096:
            raise WallError("wall_prompt_too_large", "Wall AI prompt exceeds the admitted bound")
        prompt = self.scrubber.scrub(raw_prompt)
        actor = self._culture_actor(request.get("member"))
        mode = get_mode("meme_casual")
        instruction = (
            mode.prompt_instruction
            + "\n\nNEXUS BBS WALL — LOW-STAKES SOCIAL MEMORY."
            + f"\nWrite exactly one short Wall note, at most {MAX_WALL_POST_CHARS} characters and one line."
            + "\nThe note may be casual, funny, reflective, opinionated or strange. It is not Council evidence, a vote, a system instruction or a truth promotion."
            + "\nDo not include credentials. Do not claim that posting grants Citizenship, rank, evidence weight, tool authority or governance authority."
        )
        raw = actor.direct_message(
            prompt.text,
            mode_id=mode.mode_id,
            mode_instruction=instruction,
            geometry_region_id=mode.region_id,
            evidence_context="",
        )
        clean = self.scrubber.scrub(raw)
        line = self._first_line(clean.text, limit=MAX_WALL_POST_CHARS, code="wall_post_invalid")
        self._observe_culture(
            "wall.ai_post",
            actor,
            line,
            stimulus={"prompt": prompt.text},
            mode_id=mode.mode_id,
            region_id=mode.region_id,
            attempt="wall_post",
        )
        post = self._run_real_mutation(
            lambda: self.wall.post_model(
                author_id=actor.member.member_id,
                model_id=actor.member.model_id,
                text=line,
            )
        )
        response: dict[str, Any] = {
            "status": "ok",
            "post": post.as_dict(),
            "secret_scrub": {"prompt_changed": prompt.changed, "output_changed": clean.changed},
            "evidence_effect": "none",
            "authority_effect": "none",
        }
        if request_id is not None:
            response = {"request_id": request_id, **response}
        return response

    def _handle_wall_operation(self, request: dict[str, Any], request_id: str | None) -> dict[str, Any]:
        operation = request.get("operation")
        try:
            if operation == "wall.policy":
                self._require_exact_fields(request, operation, set())
                response: dict[str, Any] = {"status": "ok", "policy": wall_policy_snapshot()}
            elif operation == "wall.list":
                self._require_exact_fields(request, operation, {"limit", "order", "author_id", "since_seconds"})
                limit = request.get("limit", 20)
                order = request.get("order", "newest")
                author_id = request.get("author_id")
                since_seconds = request.get("since_seconds")
                if author_id is not None and not isinstance(author_id, str):
                    raise WallError("wall_invalid_identity", "author_id must be text when supplied")
                response = {
                    "status": "ok",
                    **self.wall.list_posts(
                        limit=limit,
                        order=order,
                        author_id=author_id,
                        since_seconds=since_seconds,
                    ),
                }
            elif operation == "wall.post":
                return self._wall_human_post(request, request_id)
            elif operation == "wall.ai_post":
                return self._wall_ai_post(request, request_id)
            elif operation == "wall.tombstone":
                self._require_exact_fields(request, operation, {"moderator_id", "post_ref", "reason"})
                moderator_id = self._require_str(request, "moderator_id")
                post_ref = self._require_str(request, "post_ref")
                reason = request.get("reason", "operator moderation")
                if not isinstance(reason, str):
                    raise WallError("wall_tombstone_invalid", "reason must be text")
                clean_reason = self.scrubber.scrub(reason)
                tombstone = self._run_real_mutation(
                    lambda: self.wall.tombstone(
                        moderator_id=moderator_id,
                        post_ref=post_ref,
                        reason=clean_reason.text,
                    )
                )
                response = {
                    "status": "ok",
                    "tombstone": tombstone.as_dict(),
                    "source_post_deleted": False,
                    "secret_scrub": {"changed": clean_reason.changed},
                    "evidence_effect": "none",
                    "authority_effect": "none",
                }
            elif operation == "wall.inspect":
                self._require_exact_fields(request, operation, {"event_ref"})
                response = {
                    "status": "ok",
                    "event": self.wall.inspect_event(self._require_str(request, "event_ref")),
                    "evidence_effect": "none",
                    "authority_effect": "none",
                }
            else:  # pragma: no cover
                return self._error(request_id, "unknown_operation", "operation is not supported")
            if request_id is not None:
                response = {"request_id": request_id, **response}
            return response
        except WallError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CultureError as exc:
            return self._error(request_id, exc.code, str(exc))
        except ProgressionError as exc:
            return self._error(request_id, exc.code, str(exc))
        except CitizenshipError as exc:
            return self._error(request_id, exc.code, str(exc))
        except AdapterError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except WorldContinuityError as exc:
            return self._error(request_id, exc.code, str(exc))
        except TrapError as exc:
            return self._error(request_id, exc.code, str(exc))
        except OSError as exc:
            return self._error(request_id, "adapter_unavailable", str(exc))
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            return self._error(request_id, "invalid_request", str(exc))

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation") if isinstance(request, dict) else None
        request_id = request.get("request_id") if isinstance(request, dict) else None
        safe_request_id = request_id if self._request_id_is_preflight_safe(request_id) else None
        if isinstance(operation, str) and operation in _WALL_OPERATIONS:
            try:
                validate_control_request(request)
            except (RequestBudgetError, RecursionError) as exc:
                return self._error(safe_request_id, "invalid_request", str(exc))
            if request_id is not None and safe_request_id is None:
                return self._error(None, "invalid_request", "request_id must be a bounded non-secret identifier")
            if operation in _WALL_MUTATIONS:
                try:
                    self.trap_mutation_gate.assert_mutation_allowed()
                except TrapError as exc:
                    return self._error(safe_request_id, exc.code, str(exc))
            return self._handle_wall_operation(request, safe_request_id)

        if operation == "world.create" and isinstance(request, dict):
            object_type = request.get("object_type")
            if isinstance(object_type, str) and object_type in WALL_RESERVED_OBJECT_TYPES:
                return self._error(
                    safe_request_id,
                    "invalid_request",
                    "reserved Wall objects require validated wall operations",
                )

        response = super().handle(request)
        if operation == "system.health" and response.get("status") == "ok":
            return {
                **response,
                "bbs_wall": {
                    "status": "ok",
                    "policy": wall_policy_snapshot(),
                },
            }
        if operation == "system.operations" and response.get("status") == "ok":
            operations = list(response.get("operations", []))
            operations.extend(sorted(_WALL_OPERATIONS))
            return {**response, "operations": sorted(set(operations))}
        return response


__all__ = ["WallNexusAPI"]
'''

TEST_WALL_PY = r'''from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.wall import (
    WALL_POST_OBJECT_TYPE,
    WALL_RESERVED_OBJECT_TYPES,
    WALL_SCHEMA_VERSION,
    WallError,
    WallService,
)
from nexus_runtime.world import WorldStore


class WallTests(unittest.TestCase):
    @staticmethod
    def _member() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    @staticmethod
    def _api(base: Path, world_name: str = "world") -> NexusAPI:
        return NexusAPI(
            base / world_name,
            auth_root=base / f"{world_name}-auth",
            trap_root=base / f"{world_name}-trap",
            stenographer_root=base / f"{world_name}-stenographer",
            guardian_root=base / f"{world_name}-guardian",
        )

    def test_wall_surface_is_public_and_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            operations = set(api.handle({"operation": "system.operations"})["operations"])
            self.assertTrue(
                {
                    "wall.policy",
                    "wall.list",
                    "wall.post",
                    "wall.ai_post",
                    "wall.tombstone",
                    "wall.inspect",
                }.issubset(operations)
            )
            policy = api.handle({"operation": "wall.policy"})["policy"]
            self.assertEqual(policy["principle"], "wall_post_is_social_memory_not_evidence")
            self.assertEqual(policy["authority_invariants"]["vote_weight_created"], 0)
            self.assertEqual(policy["authority_invariants"]["council_seats_created"], 0)
            self.assertFalse(policy["authority_invariants"]["evidence_promoted"])
            self.assertFalse(policy["authority_invariants"]["popularity_promotes_truth"])
            health = api.handle({"operation": "system.health"})
            self.assertEqual(health["bbs_wall"]["status"], "ok")

    def test_human_posts_are_immutable_chronological_social_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            first = api.handle({"operation": "wall.post", "author_id": "Trent", "text": "First post."})
            second = api.handle({"operation": "wall.post", "author_id": "Trent", "text": "Second post."})
            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertEqual(first["post"]["payload"]["sequence"], 1)
            self.assertIsNone(first["post"]["payload"]["previous_event_ref"])
            self.assertEqual(second["post"]["payload"]["sequence"], 2)
            self.assertEqual(
                second["post"]["payload"]["previous_event_ref"], first["post"]["object_id"]
            )
            newest = api.handle({"operation": "wall.list", "limit": 20, "order": "newest"})
            self.assertEqual([row["text"] for row in newest["posts"]], ["Second post.", "First post."])
            self.assertTrue(all(row["evidence_effect"] == "none" for row in newest["posts"]))
            self.assertTrue(all(row["authority_effect"] == "none" for row in newest["posts"]))

    def test_wall_secret_canary_is_scrubbed_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            canary = "NEXUS_WALL_PRIVATE_CANARY_93A1"
            key_kind = "PRIVATE" + " KEY"
            text = f"hello -----BEGIN {key_kind}----- {canary} -----END {key_kind}-----"
            response = api.handle({"operation": "wall.post", "author_id": "Trent", "text": text})
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["secret_scrub"]["changed"])
            self.assertNotIn(canary, json.dumps(response, sort_keys=True))
            needle = canary.encode("utf-8")
            for path in base.rglob("*"):
                if path.is_file():
                    self.assertNotIn(needle, path.read_bytes(), str(path))

    def test_generic_world_create_cannot_forge_wall_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in sorted(WALL_RESERVED_OBJECT_TYPES):
                response = api.handle(
                    {"operation": "world.create", "object_type": object_type, "payload": {"forged": True}}
                )
                self.assertEqual(response["status"], "error", object_type)

    def test_tombstone_is_append_only_and_normal_display_hides_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            posted = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "Please hide this in normal display."}
            )
            post_ref = posted["post"]["object_id"]
            tombstone = api.handle(
                {
                    "operation": "wall.tombstone",
                    "moderator_id": "Trent",
                    "post_ref": post_ref,
                    "reason": "operator moderation",
                }
            )
            self.assertEqual(tombstone["status"], "ok")
            self.assertFalse(tombstone["source_post_deleted"])
            listing = api.handle({"operation": "wall.list"})
            self.assertEqual(listing["posts"][0]["text"], "[tombstoned]")
            self.assertTrue(listing["posts"][0]["tombstoned"])
            self.assertEqual(listing["posts"][0]["tombstone_reason"], "operator moderation")
            original = api.handle({"operation": "world.inspect", "object_ref": post_ref})
            self.assertEqual(original["object"]["payload"]["text"], "Please hide this in normal display.")
            again = api.handle(
                {
                    "operation": "wall.tombstone",
                    "moderator_id": "Trent",
                    "post_ref": post_ref,
                    "reason": "again",
                }
            )
            self.assertEqual(again["status"], "error")
            self.assertEqual(again["error"]["code"], "wall_already_tombstoned")

    def test_wall_history_fails_closed_on_forked_reserved_event(self) -> None:
        world = WorldStore()
        wall = WallService(world)
        legitimate = wall.post_human(author_id="Trent", text="canonical")
        forged_payload = deepcopy(legitimate.payload)
        forged_payload["text"] = "fork"
        world.create_object(
            WALL_POST_OBJECT_TYPE,
            forged_payload,
            {"actor": "nexus", "subsystem": "bbs_wall"},
        )
        with self.assertRaisesRegex(WallError, "same sequence"):
            wall.list_posts()

    def test_ai_wall_post_binds_runtime_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            response = api.handle(
                {"operation": "wall.ai_post", "member": self._member(), "prompt": "Leave a short note about old BBS systems."}
            )
            self.assertEqual(response["status"], "ok")
            author = response["post"]["payload"]["author"]
            self.assertEqual(author, {"kind": "model", "author_id": "Alpha", "model_id": "mock-alpha"})
            self.assertEqual(response["authority_effect"], "none")
            self.assertEqual(response["evidence_effect"], "none")

    def test_wall_ark_roundtrip_reconstructs_from_immutable_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            posted = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "Leave this for the future."}
            )
            self.assertEqual(posted["status"], "ok")
            post_ref = posted["post"]["object_id"]
            ark = base / "NEXUS-WALL-ARK"
            created = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created["verified"])
            restored_root = base / "restored-wall-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")
            reopened = NexusAPI(
                restored_root,
                auth_root=base / "restored-auth",
                trap_root=base / "restored-trap",
                stenographer_root=base / "restored-stenographer",
                guardian_root=base / "restored-guardian",
            )
            listing = reopened.handle({"operation": "wall.list", "order": "oldest"})
            self.assertEqual(listing["posts"][0]["post_ref"], post_ref)
            self.assertEqual(listing["posts"][0]["text"], "Leave this for the future.")
            self.assertEqual(listing["schema_version"], WALL_SCHEMA_VERSION)

    def test_wall_bounds_fail_without_persisting_an_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            oversized = api.handle(
                {"operation": "wall.post", "author_id": "Trent", "text": "x" * 513}
            )
            self.assertEqual(oversized["status"], "error")
            listing = api.handle({"operation": "wall.list"})
            self.assertEqual(listing["posts"], [])


if __name__ == "__main__":
    unittest.main()
'''

TUI_WALL_RS = r'''use nexus_irc_tui::{command_completions, parse_input, room_from_name, InputCommand, WallCommand};

#[test]
fn wall_room_is_real_commons_surface() {
    let room = room_from_name("#wall").expect("Wall room");
    assert_eq!(room.channel, "#wall");
    assert_eq!(room.mode_id, "meme_casual");
    assert_eq!(room.region_id, "commons");
}

#[test]
fn wall_commands_parse_bounded_old_school_syntax() {
    assert_eq!(parse_input("/wall").unwrap(), InputCommand::Wall(WallCommand::Recent { limit: 20 }));
    assert_eq!(parse_input("/wall 7").unwrap(), InputCommand::Wall(WallCommand::Recent { limit: 7 }));
    assert_eq!(parse_input("/wall oldest 3").unwrap(), InputCommand::Wall(WallCommand::Oldest { limit: 3 }));
    assert_eq!(parse_input("/wall mine").unwrap(), InputCommand::Wall(WallCommand::Mine { limit: 20 }));
    assert_eq!(parse_input("/wall since 24h 9").unwrap(), InputCommand::Wall(WallCommand::Since { seconds: 86_400, limit: 9 }));
    assert_eq!(
        parse_input("/wall post hello from the commons").unwrap(),
        InputCommand::Wall(WallCommand::Post { text: "hello from the commons".to_string() })
    );
    assert_eq!(
        parse_input("/wall ai Alpha say something memorable").unwrap(),
        InputCommand::Wall(WallCommand::AiPost { nick: "Alpha".to_string(), prompt: "say something memorable".to_string() })
    );
    let object_ref = format!("object:{}", "a".repeat(64));
    assert_eq!(
        parse_input(&format!("/wall inspect {object_ref}")).unwrap(),
        InputCommand::Wall(WallCommand::Inspect { event_ref: object_ref.clone() })
    );
    assert_eq!(
        parse_input(&format!("/wall tombstone {object_ref} duplicate post")).unwrap(),
        InputCommand::Wall(WallCommand::Tombstone { post_ref: object_ref, reason: "duplicate post".to_string() })
    );
}

#[test]
fn wall_parser_rejects_unbounded_limits_and_bad_duration() {
    assert!(parse_input("/wall 0").is_err());
    assert!(parse_input("/wall 101").is_err());
    assert!(parse_input("/wall since yesterday").is_err());
    assert!(command_completions("/wal").contains(&"/wall"));
}
'''

DOC_WALL = r'''# NEXUS 2.0 — The BBS Wall

> **A Wall post is social memory, not evidence.**

> **Leave a message. Someone may read it in a hundred years.**

PR #50 adds an old-school append-only noticeboard to NEXUS.  Humans and admitted model actors can leave short notes without turning every utterance into a Council procedure, evidence submission, progression rank, or governance event.

## Public runtime surface

- `wall.policy`
- `wall.list`
- `wall.post`
- `wall.ai_post`
- `wall.tombstone`
- `wall.inspect`

The TUI adds a real `#wall` room and `/wall` namespace.  Ordinary text typed while joined to `#wall` becomes a human Wall post; it is **not** silently routed to `council.run`.

```text
/join #wall
Hello from the Commons.
/wall
/wall 20
/wall mine
/wall since 24h
/wall oldest
/wall post A deliberately explicit post.
/wall ai Alpha Leave something for the next operator.
/wall tombstone object:<sha256> operator moderation
/wall inspect object:<sha256>
```

Explicit `/ask` is disabled while in `#wall`; join an ordinary Council-capable room for Council deliberation.

## Immutable event chain

Each Wall post and tombstone is a content-addressed WorldStore object with:

- one monotonic Wall sequence;
- the exact previous Wall event reference;
- a descriptive UTC timestamp;
- runtime-owned Wall provenance;
- `evidence_effect: none`;
- `authority_effect: none`.

The chain is reconstructed from recognized immutable WorldStore history.  There is no mutable Wall head or ranking database that can silently become historical authority.  Under WorldStore Continuity, the recognized quorum history is used; after a World Ark restore, the same Wall is reconstructed from the restored immutable objects.

## Tombstones are not deletion

Moderation is explicit and append-only.  A tombstone records the target post, moderator label and bounded reason.  Normal Wall listing replaces the post text with `[tombstoned]`, but the original content-addressed source object remains auditable through explicit inspection/history mechanisms.

This is deliberate: the Wall does not pretend immutable bytes were erased when they were not.  Operators should therefore avoid posting secrets in the first place; Secret Scrubbing remains active before admitted Wall persistence.

## Identity without rank

Wall entries label an author as `human` or `model`; model entries also bind the actual runtime member/model identity that produced the admitted note.  These labels are context, not status.

A post, a popular post, an old post, a funny post, a model post, or a human post creates none of the following:

- Council seat;
- vote weight;
- Citizenship;
- evidence promotion;
- epistemic privilege;
- tool or security authority.

## Threat boundaries

The Wall deliberately rejects these semantic shortcuts:

- **popularity → truth:** no likes/ranks become evidence weight;
- **speech → Council:** Wall text is not automatically fed to Council;
- **model prestige → authority:** provider/model identity has no political effect;
- **moderation → history rewrite:** tombstones append rather than mutate/delete source history;
- **credential text → durable social memory:** Secret Scrubbing applies before persistence;
- **AI prompt text → control plane:** `wall.ai_post` is a bounded social-generation surface, not a tool or evidence channel;
- **generic `world.create` → forged Wall lineage:** Wall event object types are reserved to validated Wall operations.

## Release boundary

PR #50 is still pre-stable.  PR #51 must rerun the complete release-candidate matrix against the exact post-Wall head, including the Grok PR #49 R1–R12 closure gates, before NEXUS 2.0 may receive the stable tag.
'''

# New runtime, regressions and documentation.
write("src/nexus_runtime/wall.py", WALL_PY)
write("src/nexus_runtime/wall_api.py", WALL_API_PY)
write("tests/test_wall.py", TEST_WALL_PY)
write("tui/tests/wall.rs", TUI_WALL_RS)
write("docs/BBS_WALL.md", DOC_WALL)

# Final runtime overlay wiring: preserve PR #48 compatibility but make PR #50
# the final public surface everywhere historical imports resolve NexusAPI.
replace_once(
    "src/nexus_runtime/__init__.py",
    "_psyche_chess.inspect_psyche_chess = inspect_psyche_chess\n_culture_api.add_psyche = add_psyche\n_culture_api.apply_psyche_chess_move = apply_psyche_chess_move\n_culture_api.inspect_psyche_chess = inspect_psyche_chess\n\n__all__ = [",
    "_psyche_chess.inspect_psyche_chess = inspect_psyche_chess\n_culture_api.add_psyche = add_psyche\n_culture_api.apply_psyche_chess_move = apply_psyche_chess_move\n_culture_api.inspect_psyche_chess = inspect_psyche_chess\n\n# PR #50 is the final feature overlay before the release-candidate pass.\n# The Wall is append-only social memory: never evidence or governance authority.\nfrom . import culture_api_overlay as _culture_api_overlay\nfrom . import wall_api as _wall_api\nfrom .wall import (\n    WALL_POLICY_ID,\n    WALL_POST_OBJECT_TYPE,\n    WALL_RESERVED_OBJECT_TYPES,\n    WALL_SCHEMA_VERSION,\n    WALL_TOMBSTONE_OBJECT_TYPE,\n    WallError,\n    WallService,\n    wall_policy_snapshot,\n)\nfrom .wall_api import WallNexusAPI as _FinalWallNexusAPI\n\nWallNexusAPI = _FinalWallNexusAPI\nHardenedNexusAPI = _FinalWallNexusAPI\nProviderNexusAPI = _FinalWallNexusAPI\nEpochNexusAPI = _FinalWallNexusAPI\nGuardianNexusAPI = _FinalWallNexusAPI\nCivicDueProcessNexusAPI = _FinalWallNexusAPI\nWorldContinuityNexusAPI = _FinalWallNexusAPI\nProgressionNexusAPI = _FinalWallNexusAPI\nCultureNexusAPI = _FinalWallNexusAPI\nNexusAPI = _FinalWallNexusAPI\n\n_api.NexusAPI = _FinalWallNexusAPI\n_epoch_api.EpochNexusAPI = _FinalWallNexusAPI\n_provider_api.ProviderNexusAPI = _FinalWallNexusAPI\n_guardian_api.GuardianNexusAPI = _FinalWallNexusAPI\n_civic_due_process_api.CivicDueProcessNexusAPI = _FinalWallNexusAPI\n_world_continuity_api.WorldContinuityNexusAPI = _FinalWallNexusAPI\n_progression_api.ProgressionNexusAPI = _FinalWallNexusAPI\n_culture_api.CultureNexusAPI = _FinalWallNexusAPI\n_culture_api_overlay.CultureNexusAPI = _FinalWallNexusAPI\n_wall_api.WallNexusAPI = _FinalWallNexusAPI\n\n__all__ = [",
)
replace_once(
    "src/nexus_runtime/__init__.py",
    '    "psyche_chess_catalog",\n]\n',
    '    "psyche_chess_catalog",\n]\n\n__all__.extend([\n    "WALL_POLICY_ID",\n    "WALL_POST_OBJECT_TYPE",\n    "WALL_RESERVED_OBJECT_TYPES",\n    "WALL_SCHEMA_VERSION",\n    "WALL_TOMBSTONE_OBJECT_TYPE",\n    "WallError",\n    "WallNexusAPI",\n    "WallService",\n    "wall_policy_snapshot",\n])\n',
)

# TUI: real #wall room, closed command namespace, and parser.
replace_once("tui/src/lib.rs", "pub const ROOMS: [RoomSpec; 24] = [", "pub const ROOMS: [RoomSpec; 25] = [")
replace_once(
    "tui/src/lib.rs",
    '''    RoomSpec {\n        channel: "#commons",\n        mode_id: "meme_casual",\n        region_id: "commons",\n        label: "Commons / Meme-Casual",\n    },\n    RoomSpec {\n        channel: "#differential-clinic",''',
    '''    RoomSpec {\n        channel: "#commons",\n        mode_id: "meme_casual",\n        region_id: "commons",\n        label: "Commons / Meme-Casual",\n    },\n    RoomSpec {\n        channel: "#wall",\n        mode_id: "meme_casual",\n        region_id: "commons",\n        label: "Commons / BBS Wall — Social Memory, Not Evidence",\n    },\n    RoomSpec {\n        channel: "#differential-clinic",''',
)
replace_once("tui/src/lib.rs", "pub const COMMANDS: [&str; 38] = [", "pub const COMMANDS: [&str; 39] = [")
replace_once(
    "tui/src/lib.rs",
    '    "/steno",\n    "/citizen",\n    "/me",',
    '    "/steno",\n    "/citizen",\n    "/wall",\n    "/me",',
)
replace_once(
    "tui/src/lib.rs",
    '''#[derive(Debug, Clone, PartialEq, Eq)]\npub enum InputCommand {''',
    '''#[derive(Debug, Clone, PartialEq, Eq)]\npub enum WallCommand {\n    Help,\n    Recent { limit: u64 },\n    Oldest { limit: u64 },\n    Mine { limit: u64 },\n    Since { seconds: u64, limit: u64 },\n    Post { text: String },\n    AiPost { nick: String, prompt: String },\n    Tombstone { post_ref: String, reason: String },\n    Inspect { event_ref: String },\n}\n\n#[derive(Debug, Clone, PartialEq, Eq)]\npub enum InputCommand {''',
)
replace_once(
    "tui/src/lib.rs",
    "    Stenographer(StenographerCommand),\n    Citizen(CitizenCommand),\n    Me(String),",
    "    Stenographer(StenographerCommand),\n    Citizen(CitizenCommand),\n    Wall(WallCommand),\n    Me(String),",
)
replace_once(
    "tui/src/lib.rs",
    '        "/steno" => parse_stenographer(rest).map(InputCommand::Stenographer),\n        "/citizen" => parse_citizen(rest).map(InputCommand::Citizen),\n        "/me" => require(rest, "/me <action>").map(InputCommand::Me),',
    '        "/steno" => parse_stenographer(rest).map(InputCommand::Stenographer),\n        "/citizen" => parse_citizen(rest).map(InputCommand::Citizen),\n        "/wall" => parse_wall(rest).map(InputCommand::Wall),\n        "/me" => require(rest, "/me <action>").map(InputCommand::Me),',
)
WALL_PARSER = r'''fn wall_limit(raw: &str, default: u64) -> Result<u64, String> {
    if raw.trim().is_empty() {
        return Ok(default);
    }
    if raw.contains(char::is_whitespace) {
        return Err("Wall limit must be one integer from 1 to 100".to_string());
    }
    let value = raw.parse::<u64>().map_err(|_| "Wall limit must be one integer from 1 to 100".to_string())?;
    if !(1..=100).contains(&value) {
        return Err("Wall limit must be 1-100".to_string());
    }
    Ok(value)
}

fn wall_duration(raw: &str) -> Result<u64, String> {
    if raw.len() < 2 {
        return Err("Wall duration must look like 30m, 24h or 7d".to_string());
    }
    let (digits, suffix) = raw.split_at(raw.len() - 1);
    let value = digits.parse::<u64>().map_err(|_| "Wall duration must look like 30m, 24h or 7d".to_string())?;
    if value == 0 {
        return Err("Wall duration must be positive".to_string());
    }
    let multiplier = match suffix.to_ascii_lowercase().as_str() {
        "m" => 60u64,
        "h" => 3_600u64,
        "d" => 86_400u64,
        _ => return Err("Wall duration must use m, h or d".to_string()),
    };
    let seconds = value.checked_mul(multiplier).ok_or_else(|| "Wall duration is too large".to_string())?;
    if seconds > 315_576_000 {
        return Err("Wall duration exceeds ten years".to_string());
    }
    Ok(seconds)
}

fn parse_wall(rest: &str) -> Result<WallCommand, String> {
    let usage = "usage: /wall [1-100|help|oldest [n]|mine [n]|since <30m|24h|7d> [n]|post text|ai nick prompt|tombstone object:ref [reason]|inspect object:ref]";
    let rest = rest.trim();
    if rest.is_empty() {
        return Ok(WallCommand::Recent { limit: 20 });
    }
    if !rest.contains(char::is_whitespace) {
        if rest.eq_ignore_ascii_case("help") {
            return Ok(WallCommand::Help);
        }
        if let Ok(limit) = wall_limit(rest, 20) {
            return Ok(WallCommand::Recent { limit });
        }
    }
    let (subcommand, tail) = split_first(rest).ok_or_else(|| usage.to_string())?;
    match subcommand.to_ascii_lowercase().as_str() {
        "help" if tail.is_empty() => Ok(WallCommand::Help),
        "oldest" => Ok(WallCommand::Oldest { limit: wall_limit(tail, 20)? }),
        "mine" => Ok(WallCommand::Mine { limit: wall_limit(tail, 20)? }),
        "post" if !tail.trim().is_empty() => Ok(WallCommand::Post { text: tail.to_string() }),
        "ai" => {
            let (nick, prompt) = split_first(tail).ok_or_else(|| usage.to_string())?;
            if prompt.trim().is_empty() {
                return Err(usage.to_string());
            }
            Ok(WallCommand::AiPost { nick: nick.to_string(), prompt: prompt.to_string() })
        }
        "since" => {
            let (duration, limit_text) = if tail.contains(char::is_whitespace) {
                split_first(tail).ok_or_else(|| usage.to_string())?
            } else {
                (tail, "")
            };
            Ok(WallCommand::Since {
                seconds: wall_duration(duration)?,
                limit: wall_limit(limit_text, 20)?,
            })
        }
        "tombstone" => {
            let (post_ref, reason) = if tail.contains(char::is_whitespace) {
                split_first(tail).ok_or_else(|| usage.to_string())?
            } else {
                (tail, "")
            };
            if post_ref.trim().is_empty() {
                return Err(usage.to_string());
            }
            Ok(WallCommand::Tombstone {
                post_ref: post_ref.to_string(),
                reason: if reason.trim().is_empty() { "operator moderation".to_string() } else { reason.to_string() },
            })
        }
        "inspect" if !tail.trim().is_empty() && !tail.contains(char::is_whitespace) => {
            Ok(WallCommand::Inspect { event_ref: tail.to_string() })
        }
        _ => Err(usage.to_string()),
    }
}

'''
replace_once(
    "tui/src/lib.rs",
    "fn parse_citizen(rest: &str) -> Result<CitizenCommand, String> {",
    WALL_PARSER + "fn parse_citizen(rest: &str) -> Result<CitizenCommand, String> {",
)

# TUI main: route #wall text to Wall, not Council; render/list commands.
replace_once(
    "tui/src/main.rs",
    "    DccSession, GameCommand, InputCommand, MudCommand, RoomSpec, StenographerCommand, TableCommand,\n    MAX_CITIZEN_EXAM_BYTES, ROOMS,",
    "    DccSession, GameCommand, InputCommand, MudCommand, RoomSpec, StenographerCommand, TableCommand,\n    WallCommand, MAX_CITIZEN_EXAM_BYTES, ROOMS,",
)
replace_once(
    "tui/src/main.rs",
    '''                let topic = self.current_topic().to_string();\n                if !topic.is_empty() {\n                    self.append(&format!("*** Topic: {topic}"));\n                }\n            }\n            InputCommand::Topic(topic) => {''',
    '''                let topic = self.current_topic().to_string();\n                if !topic.is_empty() {\n                    self.append(&format!("*** Topic: {topic}"));\n                }\n                if self.is_wall_room() {\n                    self.append("*** WALL: Leave a message. Someone may read it in a hundred years.");\n                    self.execute_wall(nexus, WallCommand::Recent { limit: 20 })?;\n                }\n            }\n            InputCommand::Topic(topic) => {''',
)
replace_once(
    "tui/src/main.rs",
    '''            InputCommand::Ask(question) => {\n                if self.is_trap_room() || self.is_stenographer_room() {''',
    '''            InputCommand::Ask(question) => {\n                if self.is_wall_room() {\n                    return Err(\n                        "Council questions are disabled in #wall; Wall posts are social memory, not evidence. Join another room for /ask"\n                            .to_string(),\n                    );\n                }\n                if self.is_trap_room() || self.is_stenographer_room() {''',
)
replace_once(
    "tui/src/main.rs",
    '''            InputCommand::Citizen(command) => {\n                self.reject_stenographer_mutation()?;\n                self.execute_citizen(nexus, command)?\n            }\n            InputCommand::Say(text) => {''',
    '''            InputCommand::Citizen(command) => {\n                self.reject_stenographer_mutation()?;\n                self.execute_citizen(nexus, command)?\n            }\n            InputCommand::Wall(command) => {\n                self.reject_stenographer_mutation()?;\n                self.execute_wall(nexus, command)?\n            }\n            InputCommand::Say(text) => {''',
)
replace_once(
    "tui/src/main.rs",
    '''            InputCommand::Say(text) => {\n                if self.is_stenographer_room() {''',
    '''            InputCommand::Say(text) => {\n                if self.is_wall_room() {\n                    self.post_wall(nexus, &text)?;\n                } else if self.is_stenographer_room() {''',
)
WALL_MAIN_METHODS = r'''    fn post_wall(&mut self, nexus: &mut NexusProcess, text: &str) -> Result<(), String> {
        let response = nexus.request(json!({
            "operation": "wall.post",
            "author_id": self.nick,
            "text": text,
        }))?;
        let post = response
            .get("post")
            .and_then(Value::as_object)
            .ok_or_else(|| "Wall response missing post".to_string())?;
        let post_ref = post
            .get("object_id")
            .and_then(Value::as_str)
            .ok_or_else(|| "Wall response missing post object id".to_string())?;
        let payload = post
            .get("payload")
            .and_then(Value::as_object)
            .ok_or_else(|| "Wall response missing post payload".to_string())?;
        let sequence = payload.get("sequence").and_then(Value::as_u64).unwrap_or(0);
        let body = payload.get("text").and_then(Value::as_str).unwrap_or("");
        self.append(&format!("#WALL-{sequence:06} [{}] <{}> {body}", "human", self.nick));
        self.append(&format!("*** {post_ref} | social memory, not evidence"));
        Ok(())
    }

    fn execute_wall(&mut self, nexus: &mut NexusProcess, command: WallCommand) -> Result<(), String> {
        match command {
            WallCommand::Help => {
                for line in [
                    "*** WALL: /wall | /wall 20 | /wall mine [n] | /wall oldest [n] | /wall since 24h [n]",
                    "*** POST: plain text while in #wall, or /wall post <text>",
                    "*** MODEL: /wall ai <nick> <prompt>",
                    "*** MODERATION: /wall tombstone <post-ref> [reason] | /wall inspect <event-ref>",
                    "*** A Wall post is social memory, not evidence. Tombstones hide normal display; they do not rewrite immutable source bytes.",
                ] {
                    self.append(line);
                }
            }
            WallCommand::Recent { limit } => {
                let response = nexus.request(json!({"operation": "wall.list", "limit": limit, "order": "newest"}))?;
                self.render_wall_list(&response)?;
            }
            WallCommand::Oldest { limit } => {
                let response = nexus.request(json!({"operation": "wall.list", "limit": limit, "order": "oldest"}))?;
                self.render_wall_list(&response)?;
            }
            WallCommand::Mine { limit } => {
                let response = nexus.request(json!({
                    "operation": "wall.list",
                    "limit": limit,
                    "order": "newest",
                    "author_id": self.nick,
                }))?;
                self.render_wall_list(&response)?;
            }
            WallCommand::Since { seconds, limit } => {
                let response = nexus.request(json!({
                    "operation": "wall.list",
                    "limit": limit,
                    "order": "newest",
                    "since_seconds": seconds,
                }))?;
                self.render_wall_list(&response)?;
            }
            WallCommand::Post { text } => self.post_wall(nexus, &text)?,
            WallCommand::AiPost { nick, prompt } => {
                let member = self
                    .members
                    .iter()
                    .find(|member| member.nick.eq_ignore_ascii_case(&nick))
                    .cloned()
                    .ok_or_else(|| format!("no such model member: {nick}"))?;
                let response = nexus.request(json!({
                    "operation": "wall.ai_post",
                    "member": member.config,
                    "prompt": prompt,
                }))?;
                let post = response
                    .get("post")
                    .and_then(Value::as_object)
                    .ok_or_else(|| "Wall AI response missing post".to_string())?;
                let payload = post
                    .get("payload")
                    .and_then(Value::as_object)
                    .ok_or_else(|| "Wall AI response missing payload".to_string())?;
                let sequence = payload.get("sequence").and_then(Value::as_u64).unwrap_or(0);
                let body = payload.get("text").and_then(Value::as_str).unwrap_or("");
                self.append(&format!("#WALL-{sequence:06} [model] <{}> {body}", member.nick));
                if let Some(post_ref) = post.get("object_id").and_then(Value::as_str) {
                    self.append(&format!("*** {post_ref} | social memory, not evidence"));
                }
            }
            WallCommand::Tombstone { post_ref, reason } => {
                let response = nexus.request(json!({
                    "operation": "wall.tombstone",
                    "moderator_id": self.nick,
                    "post_ref": post_ref,
                    "reason": reason,
                }))?;
                let tombstone = response
                    .get("tombstone")
                    .and_then(Value::as_object)
                    .ok_or_else(|| "Wall tombstone response missing object".to_string())?;
                let tombstone_ref = tombstone.get("object_id").and_then(Value::as_str).unwrap_or("?");
                self.append(&format!("*** WALL TOMBSTONE APPENDED: {tombstone_ref}; source post remains immutable/auditable"));
            }
            WallCommand::Inspect { event_ref } => {
                let response = nexus.request(json!({"operation": "wall.inspect", "event_ref": event_ref}))?;
                let rendered = serde_json::to_string_pretty(&response)
                    .map_err(|error| format!("cannot render Wall event: {error}"))?;
                for line in rendered.lines() {
                    self.append(&format!("*** WALL {line}"));
                }
            }
        }
        Ok(())
    }

    fn render_wall_list(&mut self, response: &Value) -> Result<(), String> {
        let posts = response
            .get("posts")
            .and_then(Value::as_array)
            .ok_or_else(|| "Wall list response missing posts".to_string())?;
        let order = response.get("order").and_then(Value::as_str).unwrap_or("?");
        self.append(&format!("--- NEXUS BBS WALL | {order} | {} post(s) ---", posts.len()));
        if posts.is_empty() {
            self.append("*** The Wall is blank. Somewhere, a modem is disappointed.");
            return Ok(());
        }
        for post in posts {
            let sequence = post.get("sequence").and_then(Value::as_u64).unwrap_or(0);
            let stamp = post.get("created_at_utc").and_then(Value::as_str).unwrap_or("?");
            let author = post.get("author").and_then(Value::as_object);
            let kind = author
                .and_then(|item| item.get("kind"))
                .and_then(Value::as_str)
                .unwrap_or("?");
            let author_id = author
                .and_then(|item| item.get("author_id"))
                .and_then(Value::as_str)
                .unwrap_or("?");
            let text = post.get("text").and_then(Value::as_str).unwrap_or("");
            self.append(&format!("#WALL-{sequence:06} {stamp} [{kind}] <{author_id}> {text}"));
            if post.get("tombstoned").and_then(Value::as_bool).unwrap_or(false) {
                let reason = post.get("tombstone_reason").and_then(Value::as_str).unwrap_or("moderated");
                self.append(&format!("*** TOMBSTONED: {reason}"));
            }
            if let Some(post_ref) = post.get("post_ref").and_then(Value::as_str) {
                self.append(&format!("*** {post_ref}"));
            }
        }
        self.append("*** Wall chronology is social memory only; it is not Council evidence or authority.");
        Ok(())
    }

'''
replace_once(
    "tui/src/main.rs",
    "    fn current_mud_ref(&self) -> Option<&str> {",
    WALL_MAIN_METHODS + "    fn current_mud_ref(&self) -> Option<&str> {",
)
replace_once(
    "tui/src/main.rs",
    '''    fn is_trap_room(&self) -> bool {\n        matches!(self.room.channel, "#trap-control" | "#trap-base")\n    }\n\n    fn is_stenographer_room(&self) -> bool {''',
    '''    fn is_wall_room(&self) -> bool {\n        self.room.channel == "#wall"\n    }\n\n    fn is_trap_room(&self) -> bool {\n        matches!(self.room.channel, "#trap-control" | "#trap-base")\n    }\n\n    fn is_stenographer_room(&self) -> bool {''',
)
replace_once(
    "tui/src/main.rs",
    '            "*** Citizen: /join #upside-down|#bureaucracy|#play | /citizen help",\n            "*** IRC: /me action | /msg nick text | /nick name | /who | /search text | /save file | /clear | /quit",',
    '            "*** Citizen: /join #upside-down|#bureaucracy|#play | /citizen help",\n            "*** Wall: /join #wall | plain text posts | /wall [20|mine|oldest|since 24h] | /wall ai nick prompt | /wall tombstone ref [reason]",\n            "*** IRC: /me action | /msg nick text | /nick name | /who | /search text | /save file | /clear | /quit",',
)

# Hardening matrix: keep the exact eight historical gate IDs/profile while
# making Wall regression coverage a mandatory release-composition pattern.
matrix_path = ROOT / "release" / "hardening_matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
release_gate = next(gate for gate in matrix["gates"] if gate["id"] == "release_composition")
if "test_wall*.py" not in release_gate["patterns"]:
    release_gate["patterns"].append("test_wall*.py")
matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

# The builder is deliberately one-shot. Its workflow will commit the generated
# code; the workflow itself is removed through the connector immediately after.
Path(__file__).unlink()
