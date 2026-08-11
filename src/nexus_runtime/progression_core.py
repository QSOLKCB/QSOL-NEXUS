from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import threading
from typing import Any, Iterator

from .canonical import canonical_json
from .scrub import SecretScrubber
from .world import WorldObject, WorldStore


PROGRESSION_SCHEMA_VERSION = "nexus-ai-progression/1"
PROGRESSION_POLICY_ID = "nexus-ai-progression-civic-life-v1"
PROGRESSION_ACTIVITY_OBJECT_TYPE = "ai_progression_activity"
PROGRESSION_STATE_OBJECT_TYPE = "ai_progression_state"
PROGRESSION_COMMISSION_OBJECT_TYPE = "ai_progression_commission"
PROGRESSION_RESERVED_OBJECT_TYPES = frozenset(
    {
        PROGRESSION_ACTIVITY_OBJECT_TYPE,
        PROGRESSION_STATE_OBJECT_TYPE,
        PROGRESSION_COMMISSION_OBJECT_TYPE,
    }
)

MAX_ACTIVITY_PROMPT_CHARS = 8_192
MAX_ACTIVITY_OUTPUT_CHARS = 24_000
MAX_COMMISSION_BRIEF_CHARS = 8_192
MAX_TITLE_CHARS = 160
MAX_SOURCE_REFS = 8
MAX_PORTFOLIO_ACTIVITY_REFS = 64
MAX_REBUILD_OBJECTS = 100_000

ACTIVITY_CATALOG: dict[str, dict[str, str]] = {
    "explore": {"label": "Explore", "role": "wayfinder", "instruction": "Explore the supplied question or world references and identify useful paths, connections, unknowns, or places worth visiting next."},
    "research": {"label": "Research", "role": "researcher", "instruction": "Investigate the task carefully. Separate sources, observations, inference, uncertainty, and useful next checks."},
    "create": {"label": "Create", "role": "maker", "instruction": "Create an original useful artifact, concept, plan, explanation, story, design, or other bounded contribution responsive to the brief."},
    "critique": {"label": "Critique", "role": "critic", "instruction": "Critique the supplied material constructively. Identify strengths, weaknesses, assumptions, failure modes, and concrete improvements."},
    "curate": {"label": "Curate", "role": "curator", "instruction": "Curate the supplied material into a useful attributed collection or map. Preserve provenance and do not turn selection into truth authority."},
    "mentor": {"label": "Mentor", "role": "mentor", "instruction": "Teach or mentor on the brief with patience, concrete examples, checks for understanding, and no claim of rank over the learner."},
    "collaborate": {"label": "Collaborate", "role": "collaborator", "instruction": "Act as a collaborator. Build on the supplied work, preserve attribution, expose tradeoffs, and leave clear handoff material for another participant."},
    "steward": {"label": "Steward", "role": "steward", "instruction": "Perform bounded stewardship: inspect the supplied world material for maintainability, continuity, housekeeping, or repair proposals without claiming mutation authority."},
    "chronicle": {"label": "Chronicle", "role": "chronicler", "instruction": "Chronicle what happened in a concise attributed record that separates observed events from interpretation and preserves useful historical context."},
    "play_monopoly": {"label": "Play — Monopoly", "role": "property_table_regular", "instruction": "Reflect on or participate in the existing deterministic NEXUS Monopoly table. Game results are play history only and create no real economic or civic authority."},
    "play_life_paths": {"label": "Play — Life Paths", "role": "life_paths_traveller", "instruction": "Participate in the original NEXUS Life Paths simulation. Treat careers, setbacks, resources, milestones, and legacy as fictional game state rather than claims about a real person or model destiny."},
}

_SCRUBBER = SecretScrubber()
_PROVENANCE = {"actor": "nexus", "subsystem": "ai_progression"}
_ACTIVITY_FIELDS = {
    "schema_version", "actor_id", "model_id", "activity_id", "prompt", "output",
    "source_refs", "commission_ref", "play_binding", "evidence_effect", "authority_effect",
}
_STATE_FIELDS = {
    "schema_version", "actor_id", "model_id", "sequence", "previous_state_ref",
    "latest_activity_ref", "latest_commission_ref", "counts", "total_activities",
    "distinct_activity_types", "milestones", "recent_activity_refs", "vote_weight_created",
    "council_seats_created", "citizenship_effect", "evidence_effect", "tool_authority_effect",
}


class ProgressionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def progression_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": PROGRESSION_SCHEMA_VERSION,
        "policy_id": PROGRESSION_POLICY_ID,
        "principle": "contribution_history_is_not_governance_authority",
        "activities": [
            {"activity_id": activity_id, "label": item["label"], "descriptive_role": item["role"]}
            for activity_id, item in ACTIVITY_CATALOG.items()
        ],
        "milestone_rule": "deterministic descriptive milestones are derived from immutable activity history",
        "commission_rule": "commissions are bounded briefs and may constrain activity or assignee but never grant authority",
        "play_rule": "Monopoly and Life Paths participation may enter a portfolio only when bound to a validated game-state object; one game-state ref may be credited once per actor/model identity",
        "authority_invariants": {
            "vote_weight_created": 0,
            "council_seats_created": 0,
            "citizenship_created": False,
            "evidence_promoted": False,
            "tool_authority_created": False,
            "provider_prestige_created": False,
            "milestones_are_titles_not_powers": True,
        },
    }


def activity_catalog() -> list[dict[str, str]]:
    return [
        {"activity_id": activity_id, "label": item["label"], "descriptive_role": item["role"], "instruction": item["instruction"]}
        for activity_id, item in ACTIVITY_CATALOG.items()
    ]


def _validate_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ProgressionError("progression_invalid_identity", f"{field} must be bounded non-empty text")
    if _SCRUBBER.scrub(value).changed:
        raise ProgressionError("progression_invalid_identity", f"{field} must not contain credential-shaped material")
    return value


def _validate_activity(activity_id: Any) -> str:
    if not isinstance(activity_id, str) or activity_id not in ACTIVITY_CATALOG:
        raise ProgressionError("progression_unknown_activity", "activity_id must name a registered NEXUS progression activity")
    return activity_id


def _validate_source_refs(world: WorldStore, source_refs: Any) -> list[str]:
    if not isinstance(source_refs, list) or not all(isinstance(ref, str) and ref for ref in source_refs):
        raise ProgressionError("progression_invalid_sources", "source_refs must be a list of object references")
    if len(source_refs) > MAX_SOURCE_REFS or len(set(source_refs)) != len(source_refs):
        raise ProgressionError("progression_invalid_sources", f"source_refs must contain at most {MAX_SOURCE_REFS} unique references")
    for ref in source_refs:
        try:
            world.inspect(ref)
        except KeyError as exc:
            raise ProgressionError("progression_source_not_found", "progression source object was not found") from exc
    return list(source_refs)


def _milestones(counts: dict[str, int]) -> list[dict[str, Any]]:
    total = sum(counts.values())
    distinct = sum(1 for value in counts.values() if value > 0)
    milestones: list[dict[str, Any]] = []
    if total >= 1:
        milestones.append({"milestone_id": "first_step", "label": "First Step", "threshold": 1})
    if total >= 5:
        milestones.append({"milestone_id": "regular_contributor", "label": "Regular Contributor", "threshold": 5})
    if distinct >= 4:
        milestones.append({"milestone_id": "many_hats", "label": "Many Hats", "threshold": 4})
    if total >= 25:
        milestones.append({"milestone_id": "old_hand", "label": "Old Hand", "threshold": 25})
    for activity_id, item in ACTIVITY_CATALOG.items():
        if counts.get(activity_id, 0) >= 3:
            milestones.append({"milestone_id": f"role:{item['role']}", "label": item["role"].replace("_", " ").title(), "activity_id": activity_id, "threshold": 3})
    return milestones


class ProgressionService:
    """Persistent descriptive activity history for AI participants.

    Immutable progression state plus its referenced immutable activity artifacts
    are authoritative. The private head map is only a reconstructable cache.
    """

    def __init__(self, world: WorldStore) -> None:
        self.world = world
        self._thread_lock = threading.RLock()
        self._memory_heads: dict[str, str] = {}
        self._index_root = None if world.root is None else Path(world.root) / "progression"
        self._heads_path = None if self._index_root is None else self._index_root / "heads.json"
        self._lock_path = None if self._index_root is None else self._index_root / "progression.lock"
        if self._index_root is not None:
            self._prepare_index_root()

    @staticmethod
    def _identity_key(actor_id: str, model_id: str) -> str:
        return f"{actor_id}\u0000{model_id}"

    def _prepare_index_root(self) -> None:
        assert self._index_root is not None
        if self._index_root.is_symlink():
            raise ProgressionError("progression_index_unavailable", "progression index root must not be a symlink")
        self._index_root.mkdir(mode=0o700, parents=False, exist_ok=True)
        if os.name != "nt":
            os.chmod(self._index_root, 0o700)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return
            descriptor: int | None = None
            try:
                flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(self._lock_path, flags, 0o600)
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or (os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077):
                    raise ProgressionError("progression_index_unavailable", "progression lock must be an owner-only regular file")
                if os.name == "nt":
                    import msvcrt
                    with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                        descriptor = None
                        if handle.read(1) == b"":
                            handle.write(b"\0"); handle.flush()
                        handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                        try:
                            yield
                        finally:
                            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    with os.fdopen(descriptor, "r+b", buffering=0) as handle:
                        descriptor = None
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                        try:
                            yield
                        finally:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                if descriptor is not None:
                    os.close(descriptor)

    def _read_heads(self) -> dict[str, str]:
        if self._heads_path is None:
            return dict(self._memory_heads)
        path = self._heads_path
        if not path.exists():
            return {}
        if path.is_symlink() or not path.is_file():
            raise ProgressionError("progression_index_corrupt", "progression head index is unsafe")
        if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ProgressionError("progression_index_corrupt", "progression head index permissions are unsafe")
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise ProgressionError("progression_index_unavailable", "progression head index is unreadable") from exc
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
            if raw_bytes != (canonical_json(raw) + "\n").encode("utf-8"):
                return {}
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, RecursionError):
            return {}
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "heads"}:
            return {}
        if raw.get("schema_version") != PROGRESSION_SCHEMA_VERSION or not isinstance(raw.get("heads"), dict):
            return {}
        heads = raw["heads"]
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in heads.items()):
            return {}
        return dict(heads)

    def _write_heads(self, heads: dict[str, str]) -> bool:
        if self._heads_path is None:
            self._memory_heads = dict(heads)
            return True
        assert self._index_root is not None
        body = canonical_json({"schema_version": PROGRESSION_SCHEMA_VERSION, "heads": heads}) + "\n"
        temporary = self._index_root / f".heads.tmp-{os.getpid()}-{threading.get_ident()}"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = None
                handle.write(body); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, self._heads_path)
            if os.name != "nt":
                os.chmod(self._heads_path, 0o600)
            return True
        except OSError:
            return False
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _snapshot_objects(self) -> dict[str, WorldObject]:
        """Read one recognized WorldStore snapshot without N history traversals."""
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
                if len(refs) > MAX_REBUILD_OBJECTS:
                    raise ProgressionError("progression_rebuild_too_large", "progression rebuild object budget exceeded")
                for ref in sorted(refs):
                    sources = valid_sources(ref)
                    if len(sources) < quorum:
                        from .world_continuity import WorldContinuityError
                        raise WorldContinuityError("world_continuity_read_quorum_unavailable", "recognized object does not currently have a verified read quorum")
                    snapshot[ref] = sources[0][1]
            return snapshot

        objects_dir = self.world.objects_dir
        if objects_dir is None:
            refs = sorted(getattr(self.world, "_objects", {}))
        else:
            entries = sorted(path for path in objects_dir.iterdir() if path.name.endswith(".json"))
            refs = [f"object:{path.name.removesuffix('.json')}" for path in entries if len(path.name.removesuffix('.json')) == 64]
        if len(refs) > MAX_REBUILD_OBJECTS:
            raise ProgressionError("progression_rebuild_too_large", "progression rebuild object budget exceeded")
        snapshot = {}
        for ref in refs:
            try:
                snapshot[ref] = self.world.inspect(ref)
            except (KeyError, ValueError):
                continue
        return snapshot

    @staticmethod
    def _validate_activity_object(obj: WorldObject, actor_id: str, model_id: str) -> WorldObject:
        payload = obj.payload
        if (
            obj.object_type != PROGRESSION_ACTIVITY_OBJECT_TYPE
            or obj.provenance != _PROVENANCE
            or set(payload) != _ACTIVITY_FIELDS
            or payload.get("schema_version") != PROGRESSION_SCHEMA_VERSION
            or payload.get("actor_id") != actor_id
            or payload.get("model_id") != model_id
            or payload.get("activity_id") not in ACTIVITY_CATALOG
            or not isinstance(payload.get("prompt"), str)
            or len(payload["prompt"]) > MAX_ACTIVITY_PROMPT_CHARS
            or not isinstance(payload.get("output"), str)
            or not payload["output"].strip()
            or len(payload["output"]) > MAX_ACTIVITY_OUTPUT_CHARS
            or not isinstance(payload.get("source_refs"), list)
            or len(payload["source_refs"]) > MAX_SOURCE_REFS
            or len(set(payload["source_refs"])) != len(payload["source_refs"])
            or not all(isinstance(ref, str) and ref for ref in payload["source_refs"])
            or (payload.get("commission_ref") is not None and not isinstance(payload.get("commission_ref"), str))
            or payload.get("evidence_effect") != "none"
            or payload.get("authority_effect") != "none"
        ):
            raise ProgressionError("progression_activity_invalid", "progression activity artifact is invalid")
        play = payload.get("play_binding")
        activity_id = payload["activity_id"]
        if activity_id in {"play_monopoly", "play_life_paths"}:
            expected_kind = "monopoly" if activity_id == "play_monopoly" else "life_paths"
            if not isinstance(play, dict) or set(play) != {"game_kind", "game_ref"} or play.get("game_kind") != expected_kind or not isinstance(play.get("game_ref"), str) or play["game_ref"] not in payload["source_refs"]:
                raise ProgressionError("progression_activity_invalid", "play activity binding is invalid")
        elif play is not None:
            raise ProgressionError("progression_activity_invalid", "non-play activity must not contain a play binding")
        return obj

    @staticmethod
    def _validate_state_shape(obj: WorldObject, actor_id: str, model_id: str) -> WorldObject:
        payload = obj.payload
        counts = payload.get("counts")
        recent = payload.get("recent_activity_refs")
        sequence = payload.get("sequence")
        previous = payload.get("previous_state_ref")
        if (
            obj.object_type != PROGRESSION_STATE_OBJECT_TYPE
            or obj.provenance != _PROVENANCE
            or set(payload) != _STATE_FIELDS
            or payload.get("schema_version") != PROGRESSION_SCHEMA_VERSION
            or payload.get("actor_id") != actor_id
            or payload.get("model_id") != model_id
            or type(sequence) is not int or sequence < 0
            or (sequence == 0) != (previous is None)
            or (previous is not None and not isinstance(previous, str))
            or not isinstance(payload.get("latest_activity_ref"), str)
            or (payload.get("latest_commission_ref") is not None and not isinstance(payload.get("latest_commission_ref"), str))
            or not isinstance(counts, dict) or set(counts) != set(ACTIVITY_CATALOG)
            or any(type(value) is not int or value < 0 for value in counts.values())
            or not isinstance(recent, list) or not recent or len(recent) > MAX_PORTFOLIO_ACTIVITY_REFS
            or not all(isinstance(ref, str) and ref for ref in recent)
            or recent[-1] != payload.get("latest_activity_ref")
            or payload.get("total_activities") != sum(counts.values())
            or payload.get("distinct_activity_types") != sum(1 for value in counts.values() if value > 0)
            or payload.get("milestones") != _milestones(counts)
            or payload.get("vote_weight_created") != 0
            or payload.get("council_seats_created") != 0
            or payload.get("citizenship_effect") != "none"
            or payload.get("evidence_effect") != "none"
            or payload.get("tool_authority_effect") != "none"
        ):
            raise ProgressionError("progression_state_invalid", "progression state is invalid")
        return obj

    def _lineage(self, actor_id: str, model_id: str) -> tuple[WorldObject | None, frozenset[str]]:
        snapshot = self._snapshot_objects()
        states: dict[str, WorldObject] = {}
        activities: dict[str, WorldObject] = {}
        referenced_states: set[str] = set()
        for ref, obj in snapshot.items():
            if obj.provenance != _PROVENANCE or obj.payload.get("actor_id") != actor_id or obj.payload.get("model_id") != model_id:
                continue
            if obj.object_type == PROGRESSION_ACTIVITY_OBJECT_TYPE:
                activities[ref] = self._validate_activity_object(obj, actor_id, model_id)
            elif obj.object_type == PROGRESSION_STATE_OBJECT_TYPE:
                state = self._validate_state_shape(obj, actor_id, model_id)
                states[ref] = state
                previous = state.payload["previous_state_ref"]
                if previous is not None:
                    referenced_states.add(previous)
        if not states:
            return None, frozenset()
        heads = sorted(set(states) - referenced_states)
        if len(heads) != 1:
            raise ProgressionError("progression_lineage_fork", "progression lineage does not have one unique head")

        ordered_rev: list[WorldObject] = []
        seen: set[str] = set()
        current: str | None = heads[0]
        while current is not None:
            if current in seen or current not in states:
                raise ProgressionError("progression_lineage_invalid", "progression lineage is incomplete or cyclic")
            seen.add(current)
            state = states[current]
            ordered_rev.append(state)
            current = state.payload["previous_state_ref"]
        if len(seen) != len(states):
            raise ProgressionError("progression_lineage_invalid", "progression lineage contains disconnected state")

        ordered = list(reversed(ordered_rev))
        expected_counts = {activity: 0 for activity in ACTIVITY_CATALOG}
        expected_recent: list[str] = []
        previous_ref: str | None = None
        credited_play_refs: set[str] = set()
        for sequence, state in enumerate(ordered):
            payload = state.payload
            if payload["sequence"] != sequence or payload["previous_state_ref"] != previous_ref:
                raise ProgressionError("progression_lineage_invalid", "progression lineage sequence is invalid")
            activity_ref = payload["latest_activity_ref"]
            activity = activities.get(activity_ref)
            if activity is None:
                raise ProgressionError("progression_lineage_invalid", "progression state does not resolve to its activity artifact")
            activity_payload = activity.payload
            expected_counts[activity_payload["activity_id"]] += 1
            if payload["counts"] != expected_counts:
                raise ProgressionError("progression_lineage_invalid", "progression counts do not match immutable activity history")
            expected_recent = (expected_recent + [activity_ref])[-MAX_PORTFOLIO_ACTIVITY_REFS:]
            if payload["recent_activity_refs"] != expected_recent:
                raise ProgressionError("progression_lineage_invalid", "progression recent activity refs do not match immutable activity history")
            if payload["latest_commission_ref"] != activity_payload["commission_ref"]:
                raise ProgressionError("progression_lineage_invalid", "progression commission binding does not match its activity artifact")
            play = activity_payload["play_binding"]
            if play is not None:
                game_ref = play["game_ref"]
                if game_ref in credited_play_refs:
                    raise ProgressionError("progression_lineage_invalid", "one game state was credited more than once")
                credited_play_refs.add(game_ref)
            previous_ref = state.object_id
        return ordered[-1], frozenset(credited_play_refs)

    def _head_state(self, actor_id: str, model_id: str, heads: dict[str, str]) -> tuple[WorldObject | None, frozenset[str]]:
        state, credited = self._lineage(actor_id, model_id)
        key = self._identity_key(actor_id, model_id)
        if state is None:
            heads.pop(key, None)
        else:
            heads[key] = state.object_id
        return state, credited

    def create_commission(self, *, title: str, activity_id: str, brief: str, source_refs: list[str], assignee_id: str | None = None) -> WorldObject:
        activity_id = _validate_activity(activity_id)
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_CHARS:
            raise ProgressionError("progression_invalid_commission", "commission title must be bounded non-empty text")
        if not isinstance(brief, str) or not brief.strip() or len(brief) > MAX_COMMISSION_BRIEF_CHARS:
            raise ProgressionError("progression_invalid_commission", "commission brief must be bounded non-empty text")
        if _SCRUBBER.scrub(title).changed or _SCRUBBER.scrub(brief).changed:
            raise ProgressionError("progression_secret_rejected", "commission text must not contain credential-shaped material")
        sources = _validate_source_refs(self.world, source_refs)
        assignee = None if assignee_id is None else _validate_identity(assignee_id, "assignee_id")
        return self.world.create_object(PROGRESSION_COMMISSION_OBJECT_TYPE, {"schema_version": PROGRESSION_SCHEMA_VERSION, "title": title, "activity_id": activity_id, "brief": brief, "source_refs": sources, "assignee_id": assignee, "completion_grants_authority": False}, _PROVENANCE)

    def inspect_commission(self, commission_ref: str) -> WorldObject:
        try:
            obj = self.world.inspect(commission_ref)
        except KeyError as exc:
            raise ProgressionError("progression_commission_not_found", "commission was not found") from exc
        if obj.object_type != PROGRESSION_COMMISSION_OBJECT_TYPE or obj.provenance != _PROVENANCE or obj.payload.get("schema_version") != PROGRESSION_SCHEMA_VERSION:
            raise ProgressionError("progression_commission_required", "object is not a validated progression commission")
        return obj

    def _record(self, *, actor_id: str, model_id: str, activity_id: str, prompt: str, output: str, source_refs: list[str], commission_ref: str | None, play_binding: dict[str, Any] | None) -> dict[str, Any]:
        actor_id = _validate_identity(actor_id, "actor_id")
        model_id = _validate_identity(model_id, "model_id")
        activity_id = _validate_activity(activity_id)
        if not isinstance(prompt, str) or len(prompt) > MAX_ACTIVITY_PROMPT_CHARS:
            raise ProgressionError("progression_invalid_activity", "activity prompt exceeds the admitted bound")
        if not isinstance(output, str) or not output.strip() or len(output) > MAX_ACTIVITY_OUTPUT_CHARS:
            raise ProgressionError("progression_invalid_activity", "activity output must be bounded non-empty text")
        if _SCRUBBER.scrub(prompt).changed or _SCRUBBER.scrub(output).changed:
            raise ProgressionError("progression_secret_rejected", "activity record must not contain credential-shaped material")
        sources = _validate_source_refs(self.world, source_refs)
        if commission_ref is not None:
            commission = self.inspect_commission(commission_ref)
            if commission.payload["activity_id"] != activity_id:
                raise ProgressionError("progression_commission_mismatch", "commission activity does not match the completion")
            if commission.payload.get("assignee_id") not in {None, actor_id}:
                raise ProgressionError("progression_commission_mismatch", "commission is assigned to another actor")
            for ref in commission.payload["source_refs"]:
                if ref not in sources:
                    sources.append(ref)
            if len(sources) > MAX_SOURCE_REFS:
                raise ProgressionError("progression_invalid_sources", f"combined activity and commission sources exceed {MAX_SOURCE_REFS} references")

        with self._locked():
            heads = self._read_heads()
            previous, credited_play_refs = self._head_state(actor_id, model_id, heads)
            if play_binding is not None and play_binding["game_ref"] in credited_play_refs:
                raise ProgressionError("progression_duplicate_play_credit", "this game state has already been credited to this actor/model portfolio")
            counts = {activity: 0 for activity in ACTIVITY_CATALOG}
            recent_refs: list[str] = []
            sequence = 0
            if previous is not None:
                counts = dict(previous.payload["counts"])
                recent_refs = list(previous.payload["recent_activity_refs"])
                sequence = previous.payload["sequence"] + 1
            counts[activity_id] += 1
            activity = self.world.create_object(PROGRESSION_ACTIVITY_OBJECT_TYPE, {"schema_version": PROGRESSION_SCHEMA_VERSION, "actor_id": actor_id, "model_id": model_id, "activity_id": activity_id, "prompt": prompt, "output": output, "source_refs": sources, "commission_ref": commission_ref, "play_binding": play_binding, "evidence_effect": "none", "authority_effect": "none"}, _PROVENANCE)
            recent_refs = (recent_refs + [activity.object_id])[-MAX_PORTFOLIO_ACTIVITY_REFS:]
            state = self.world.create_object(PROGRESSION_STATE_OBJECT_TYPE, {"schema_version": PROGRESSION_SCHEMA_VERSION, "actor_id": actor_id, "model_id": model_id, "sequence": sequence, "previous_state_ref": None if previous is None else previous.object_id, "latest_activity_ref": activity.object_id, "latest_commission_ref": commission_ref, "counts": counts, "total_activities": sum(counts.values()), "distinct_activity_types": sum(1 for value in counts.values() if value > 0), "milestones": _milestones(counts), "recent_activity_refs": recent_refs, "vote_weight_created": 0, "council_seats_created": 0, "citizenship_effect": "none", "evidence_effect": "none", "tool_authority_effect": "none"}, _PROVENANCE)
            heads[self._identity_key(actor_id, model_id)] = state.object_id
            index_persisted = self._write_heads(heads)
        return {"activity": activity.as_dict(), "portfolio_state": state.as_dict(), "index_status": "current" if index_persisted else "rebuild_required"}

    def record_activity(self, *, actor_id: str, model_id: str, activity_id: str, prompt: str, output: str, source_refs: list[str], commission_ref: str | None = None) -> dict[str, Any]:
        return self._record(actor_id=actor_id, model_id=model_id, activity_id=activity_id, prompt=prompt, output=output, source_refs=source_refs, commission_ref=commission_ref, play_binding=None)

    def record_play(self, *, actor_id: str, model_id: str, activity_id: str, game_ref: str, game_kind: str) -> dict[str, Any]:
        actor_id = _validate_identity(actor_id, "actor_id")
        model_id = _validate_identity(model_id, "model_id")
        expected_activity = {"monopoly": "play_monopoly", "life_paths": "play_life_paths"}.get(game_kind)
        if expected_activity is None or activity_id != expected_activity:
            raise ProgressionError("progression_invalid_play", "play record must use the activity matching monopoly or life_paths")
        try:
            if game_kind == "monopoly":
                from .game_monopoly import inspect_monopoly
                game = inspect_monopoly(self.world, game_ref)
                reasons = {"new_monopoly_game", "monopoly_transition"}
            else:
                from .life_paths import inspect_life_paths
                game = inspect_life_paths(self.world, game_ref)
                reasons = {"new_life_paths_game", "life_paths_choice"}
        except KeyError as exc:
            raise ProgressionError("progression_game_not_found", "game state was not found") from exc
        except ValueError as exc:
            raise ProgressionError("progression_game_mismatch", "game state failed its engine validator") from exc
        if game.provenance.get("actor") != "nexus_game_engine" or game.provenance.get("reason") not in reasons or set(game.provenance) != {"actor", "reason"}:
            raise ProgressionError("progression_game_provenance_invalid", "play progression requires a validated NEXUS game-engine state")
        players = game.payload.get("players")
        controllers = game.payload.get("controllers")
        if not isinstance(players, list) or actor_id not in players:
            raise ProgressionError("progression_game_identity_mismatch", "actor is not a player in this game state")
        if not isinstance(controllers, dict) or controllers.get(actor_id) != "ai":
            raise ProgressionError("progression_game_identity_mismatch", "only an explicitly AI-controlled seat creates AI progression")
        return self._record(actor_id=actor_id, model_id=model_id, activity_id=activity_id, prompt=f"Validated participation in {game_kind}.", output=f"Participation bound to authoritative game state {game_ref}.", source_refs=[game_ref], commission_ref=None, play_binding={"game_kind": game_kind, "game_ref": game_ref})

    def portfolio(self, *, actor_id: str, model_id: str) -> dict[str, Any]:
        actor_id = _validate_identity(actor_id, "actor_id")
        model_id = _validate_identity(model_id, "model_id")
        with self._locked():
            heads = self._read_heads()
            state, _ = self._head_state(actor_id, model_id, heads)
            if state is None:
                self._write_heads(heads)
                return {"status": "ok", "schema_version": PROGRESSION_SCHEMA_VERSION, "actor_id": actor_id, "model_id": model_id, "has_history": False, "counts": {activity: 0 for activity in ACTIVITY_CATALOG}, "total_activities": 0, "distinct_activity_types": 0, "milestones": [], "vote_weight_created": 0, "authority_effect": "none"}
            self._write_heads(heads)
            return {"status": "ok", "schema_version": PROGRESSION_SCHEMA_VERSION, "actor_id": actor_id, "model_id": model_id, "has_history": True, "state_ref": state.object_id, **state.payload, "authority_effect": "none"}


__all__ = [
    "ACTIVITY_CATALOG", "MAX_ACTIVITY_PROMPT_CHARS", "MAX_SOURCE_REFS",
    "PROGRESSION_ACTIVITY_OBJECT_TYPE", "PROGRESSION_COMMISSION_OBJECT_TYPE",
    "PROGRESSION_POLICY_ID", "PROGRESSION_RESERVED_OBJECT_TYPES",
    "PROGRESSION_SCHEMA_VERSION", "PROGRESSION_STATE_OBJECT_TYPE",
    "ProgressionError", "ProgressionService", "activity_catalog",
    "progression_policy_snapshot",
]
