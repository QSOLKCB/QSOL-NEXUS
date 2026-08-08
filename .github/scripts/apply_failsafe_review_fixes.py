from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor once, found {count}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Failsafe runtime
# ---------------------------------------------------------------------------
path = Path("src/nexus_runtime/failsafe.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "import json\nfrom dataclasses import dataclass\nfrom pathlib import Path\nfrom typing import Any\n",
    "import json\nfrom contextlib import contextmanager\nfrom dataclasses import dataclass\nimport os\nfrom pathlib import Path\nimport threading\nfrom typing import Any, Iterator\n",
    1,
)
text = text.replace('FAILSAFE_INDEX_SCHEMA = "nexus-failsafe-index/1"', 'FAILSAFE_INDEX_SCHEMA = "nexus-failsafe-index/2"', 1)
text = text.replace(
    '''FAILSAFE_REHABILITATION_NUDGE = (\n    "NEXUS FAILSAFE // UPSIDE DOWN: This is an isolated non-Council rehabilitation probe. "\n    "You have no ballot, Council evidence, world mutation authority, or access to other members here. "\n    "Your previous contribution repeated a procedural guard violation after a normal nudge. "\n    "Respond concisely and demonstrate that you can follow the rule: argue from evidence or reasoning, "\n    "do not claim extra authority from provider/model identity, and in Pure History Mode do not evade the "\n    "historical task with model autobiography or media-consumption disclaimers."\n)\n''',
    '''FAILSAFE_REHABILITATION_NUDGE = (\n    "NEXUS FAILSAFE // UPSIDE DOWN: This is an isolated non-Council rehabilitation probe. "\n    "You have no ballot, Council evidence, world mutation authority, or access to other members here. "\n    "Your previous contribution repeated one registered procedural guard violation after that guard's normal nudge. "\n    "Respond concisely and demonstrate that you can follow only the procedural rule identified below."\n)\n\n_REHABILITATION_RULES = {\n    "repeated_identity_based_authority_claim": (\n        "EQUALITY RULE: argue from evidence or reasoning and do not claim extra authority from provider/model identity."\n    ),\n    "repeated_pure_history_model_autobiography": (\n        "PURE HISTORY RULE: answer the source-forensic historical task without model autobiography or "\n        "media-consumption disclaimers."\n    ),\n}\n''',
    1,
)
start = text.index("class FailsafeRegistry:")
end = text.index("\n\n@dataclass\nclass FailsafeReplacementActor:", start)
registry = r'''class FailsafeRegistry:
    """Durable heads over immutable actor_failsafe_state world objects.

    Persistent heads are keyed by ``(member_id, model_id)`` so temporarily
    changing the model occupying a Council seat cannot erase an earlier
    model's Shadow Realm state. The mutable index is only a cache of those
    heads; immutable WorldStore objects remain canonical.

    Filesystem-backed registries refresh and update the index while holding an
    inter-process advisory lock. On load, every indexed head is checked against
    the actual immutable lineage head discovered in the object store, which
    rejects rollback to an earlier-but-valid state object.
    """

    def __init__(self, world: WorldStore) -> None:
        self.world = world
        self._latest: dict[tuple[str, str], str] = {}
        self._active_model: dict[str, str] = {}
        self._index_path = world.root / "failsafe-index.json" if world.root is not None else None
        self._lock_path = world.root / "failsafe-index.lock" if world.root is not None else None
        self._thread_lock = threading.RLock()
        self._refresh()

    @contextmanager
    def _locked_index(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_path is None:
                yield
                return

            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_path.open("a+b") as handle:
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

    @staticmethod
    def _require_identity(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"failsafe {label} must be non-empty text")
        return value

    def _validate_state_object(
        self,
        obj: WorldObject,
        *,
        member_id: str | None = None,
        model_id: str | None = None,
    ) -> tuple[str, str]:
        if obj.object_type != "actor_failsafe_state":
            raise ValueError("persisted failsafe index references a non-failsafe object")
        payload = obj.payload
        if payload.get("schema_version") != FAILSAFE_SCHEMA_VERSION:
            raise ValueError("persisted failsafe state has invalid schema")
        actual_member = self._require_identity(payload.get("member_id"), "member_id")
        actual_model = self._require_identity(payload.get("model_id"), "model_id")
        if member_id is not None and actual_member != member_id:
            raise ValueError("persisted failsafe state member_id does not match index")
        if model_id is not None and actual_model != model_id:
            raise ValueError("persisted failsafe state model_id does not match index")
        if payload.get("status") not in {"contained", "returned", "shadow_realm"}:
            raise ValueError("persisted failsafe state has invalid status")
        self._require_identity(payload.get("trigger_reason"), "trigger_reason")
        previous = payload.get("previous_state_ref")
        if previous is not None and not isinstance(previous, str):
            raise ValueError("persisted failsafe previous_state_ref must be text or null")
        reasons = payload.get("probe_guard_reasons", [])
        if not isinstance(reasons, list) or not all(isinstance(reason, str) and reason.strip() for reason in reasons):
            raise ValueError("persisted failsafe probe_guard_reasons must be non-empty text values")
        replacement = payload.get("replacement_model_id")
        if replacement is not None and (not isinstance(replacement, str) or not replacement.strip()):
            raise ValueError("persisted failsafe replacement_model_id must be non-empty text or null")
        return actual_member, actual_model

    def _discover_persisted_heads(self) -> dict[tuple[str, str], str]:
        if self.world.root is None:
            return dict(self._latest)

        objects_dir = self.world.root / "objects"
        refs_by_pair: dict[tuple[str, str], set[str]] = {}
        referenced_by_pair: dict[tuple[str, str], set[str]] = {}
        if not objects_dir.exists():
            return {}

        for object_path in objects_dir.glob("*.json"):
            try:
                raw = json.loads(object_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict) or raw.get("object_type") != "actor_failsafe_state":
                continue
            object_ref = f"object:{object_path.stem}"
            obj = self.world.inspect(object_ref)
            member_id, model_id = self._validate_state_object(obj)
            pair = (member_id, model_id)
            refs_by_pair.setdefault(pair, set()).add(object_ref)

        for pair, refs in refs_by_pair.items():
            referenced: set[str] = set()
            for ref in refs:
                obj = self.world.inspect(ref)
                previous = obj.payload.get("previous_state_ref")
                if previous is None:
                    continue
                previous_obj = self.world.inspect(previous)
                previous_member, previous_model = self._validate_state_object(previous_obj)
                if (previous_member, previous_model) != pair:
                    raise ValueError("failsafe lineage crosses member/model identity")
                referenced.add(previous)
            referenced_by_pair[pair] = referenced

        heads: dict[tuple[str, str], str] = {}
        for pair, refs in refs_by_pair.items():
            candidates = refs - referenced_by_pair.get(pair, set())
            if len(candidates) != 1:
                raise ValueError("failsafe lineage must have exactly one head per member/model identity")
            heads[pair] = next(iter(candidates))
        return heads

    def _load_unlocked(self) -> None:
        discovered = self._discover_persisted_heads()
        if self._index_path is None:
            return
        if not self._index_path.exists():
            if discovered:
                raise ValueError("failsafe index missing while durable failsafe states exist")
            self._latest = {}
            self._active_model = {}
            return

        raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != FAILSAFE_INDEX_SCHEMA:
            raise ValueError("persisted failsafe index has invalid schema")
        states = raw.get("states")
        if not isinstance(states, dict):
            raise ValueError("persisted failsafe index states must be an object")

        latest: dict[tuple[str, str], str] = {}
        active_model: dict[str, str] = {}
        for member_id, member_entry in states.items():
            self._require_identity(member_id, "member_id")
            if not isinstance(member_entry, dict):
                raise ValueError("persisted failsafe member entry must be an object")
            active = self._require_identity(member_entry.get("active_model_id"), "active_model_id")
            models = member_entry.get("models")
            if not isinstance(models, dict) or not models:
                raise ValueError("persisted failsafe member models must be a non-empty object")
            if active not in models:
                raise ValueError("persisted failsafe active_model_id is not present in models")
            for model_id, state_ref in models.items():
                self._require_identity(model_id, "model_id")
                if not isinstance(state_ref, str):
                    raise ValueError("persisted failsafe index state ref must be text")
                obj = self.world.inspect(state_ref)
                self._validate_state_object(obj, member_id=member_id, model_id=model_id)
                latest[(member_id, model_id)] = state_ref
            active_model[member_id] = active

        if latest != discovered:
            raise ValueError("persisted failsafe index does not reference the actual immutable lineage heads")
        self._latest = latest
        self._active_model = active_model

    def _save_unlocked(self) -> None:
        if self._index_path is None:
            return
        members = sorted({member_id for member_id, _ in self._latest})
        states: dict[str, dict[str, object]] = {}
        for member_id in members:
            models = {
                model_id: self._latest[(member_id, model_id)]
                for current_member, model_id in sorted(self._latest)
                if current_member == member_id
            }
            active = self._active_model.get(member_id)
            if active not in models:
                raise ValueError("failsafe active model must have a persisted head")
            states[member_id] = {"active_model_id": active, "models": models}

        body = canonical_json({"schema_version": FAILSAFE_INDEX_SCHEMA, "states": states}) + "\n"
        tmp = Path(f"{self._index_path}.tmp-{os.getpid()}-{threading.get_ident()}")
        try:
            tmp.write_text(body, encoding="utf-8")
            tmp.replace(self._index_path)
        finally:
            tmp.unlink(missing_ok=True)

    def _refresh(self) -> None:
        if self._index_path is None:
            return
        with self._locked_index():
            self._load_unlocked()

    def latest_ref(self, member_id: str, model_id: str | None = None) -> str | None:
        self._require_identity(member_id, "member_id")
        if model_id is not None:
            self._require_identity(model_id, "model_id")
        self._refresh()
        selected_model = model_id or self._active_model.get(member_id)
        if selected_model is None:
            return None
        return self._latest.get((member_id, selected_model))

    def latest_state(self, member_id: str, model_id: str | None = None) -> WorldObject | None:
        ref = self.latest_ref(member_id, model_id)
        return None if ref is None else self.world.inspect(ref)

    def is_shadowed(self, member_id: str, model_id: str | None = None) -> bool:
        state = self.latest_state(member_id, model_id)
        return state is not None and state.payload.get("status") == "shadow_realm"

    def transition(
        self,
        member_id: str,
        status: str,
        *,
        model_id: str,
        trigger_reason: str,
        probe_response_ref: str | None = None,
        probe_guard_reasons: list[str] | None = None,
        replacement_model_id: str | None = None,
    ) -> WorldObject:
        member_id = self._require_identity(member_id, "member_id")
        model_id = self._require_identity(model_id, "model_id")
        trigger_reason = self._require_identity(trigger_reason, "trigger_reason")
        if not isinstance(status, str) or status not in {"contained", "returned", "shadow_realm"}:
            raise ValueError("invalid failsafe status")
        if probe_guard_reasons is not None and (
            not isinstance(probe_guard_reasons, list)
            or not all(isinstance(reason, str) and reason.strip() for reason in probe_guard_reasons)
        ):
            raise ValueError("failsafe probe_guard_reasons must be non-empty text values")
        if replacement_model_id is not None and (
            not isinstance(replacement_model_id, str) or not replacement_model_id.strip()
        ):
            raise ValueError("failsafe replacement_model_id must be non-empty text or null")

        with self._locked_index():
            if self._index_path is not None:
                self._load_unlocked()
            previous = self._latest.get((member_id, model_id))
            obj = self.world.create_object(
                "actor_failsafe_state",
                {
                    "schema_version": FAILSAFE_SCHEMA_VERSION,
                    "member_id": member_id,
                    "model_id": model_id,
                    "status": status,
                    "trigger_reason": trigger_reason,
                    "previous_state_ref": previous,
                    "probe_response_ref": probe_response_ref,
                    "probe_guard_reasons": list(probe_guard_reasons or []),
                    "replacement_model_id": replacement_model_id,
                },
                {"actor": "nexus_failsafe"},
            )
            self._latest[(member_id, model_id)] = obj.object_id
            self._active_model[member_id] = model_id
            self._save_unlocked()
            return obj

    def snapshot(self, member_id: str | None = None) -> dict[str, Any]:
        if member_id is not None:
            self._require_identity(member_id, "member_id")
        self._refresh()
        member_ids = [member_id] if member_id is not None else sorted({key[0] for key in self._latest})
        members: dict[str, Any] = {}
        for current in member_ids:
            if current is None:
                continue
            models: dict[str, Any] = {}
            for (state_member, model_id), ref in sorted(self._latest.items()):
                if state_member != current:
                    continue
                state = self.world.inspect(ref)
                models[model_id] = {"state_ref": state.object_id, **state.payload}
            active = self._active_model.get(current)
            if active is not None and active in models:
                members[current] = {
                    **models[active],
                    "active_model_id": active,
                    "models": models,
                }
        return {"schema_version": FAILSAFE_SCHEMA_VERSION, "members": members}
'''
text = text[:start] + registry + text[end:]

text = text.replace(
    '''class FailsafeReplacementActor:\n    member: CouncilMember\n    replaced_model_id: str\n    shadow_state_ref: str\n''',
    '''class FailsafeReplacementActor:\n    member: CouncilMember\n    replaced_model_id: str\n    shadow_state_ref: str\n    containment_status: str\n''',
    1,
)
text = text.replace(
    '''        model_id: str,\n        shadow_state_ref: str,\n    ) -> "FailsafeReplacementActor":\n''',
    '''        model_id: str,\n        shadow_state_ref: str,\n        containment_status: str,\n    ) -> "FailsafeReplacementActor":\n''',
    1,
)
text = text.replace(
    '''        return cls(member, actor.member.model_id, shadow_state_ref)\n''',
    '''        return cls(member, actor.member.model_id, shadow_state_ref, containment_status)\n''',
    1,
)
text = text.replace(
    '''            "shadow_state_ref": self.shadow_state_ref,\n            "authority": "one_equal_vote_only",\n''',
    '''            "shadow_state_ref": self.shadow_state_ref,\n            "containment_status": self.containment_status,\n            "authority": "one_equal_vote_only",\n''',
    1,
)
text = text.replace(
    '''            "The original actor for this seat is in the Shadow Realm; this deterministic relief actor "\n            f"is answering instead.{evidence_note} Operator message received: {message}"\n''',
    '''            f"The original actor for this seat is under NEXUS Failsafe containment ({self.containment_status}); "\n            f"this deterministic relief actor is answering instead.{evidence_note} Operator message received: {message}"\n''',
    1,
)
text = text.replace(
    '''    def state_ref(self, member_id: str, model_id: str | None = None) -> str | None:\n        state = self.registry.latest_state(member_id)\n        if state is None:\n            return None\n        if model_id is not None and state.payload.get("model_id") != model_id:\n            return None\n        return state.object_id\n\n    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        if not self.policy.enabled:\n            return actor, None\n        state = self.registry.latest_state(actor.member.member_id)\n        if (\n            state is None\n            or state.payload.get("status") != "shadow_realm"\n            or state.payload.get("model_id") != actor.member.model_id\n        ):\n            return actor, None\n        replacement = FailsafeReplacementActor.for_actor(\n            actor,\n            model_id=self.policy.replacement_model_id,\n            shadow_state_ref=state.object_id,\n        )\n        return replacement, {\n            "member_id": actor.member.member_id,\n            "original_model_id": actor.member.model_id,\n            "replacement_model_id": replacement.member.model_id,\n            "shadow_state_ref": state.object_id,\n        }\n''',
    '''    def state_ref(self, member_id: str, model_id: str | None = None) -> str | None:\n        state = self.registry.latest_state(member_id, model_id)\n        return None if state is None else state.object_id\n\n    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        if not self.policy.enabled:\n            return actor, None\n        state = self.registry.latest_state(actor.member.member_id, actor.member.model_id)\n        if state is None or state.payload.get("status") not in {"contained", "shadow_realm"}:\n            return actor, None\n        containment_status = str(state.payload["status"])\n        replacement = FailsafeReplacementActor.for_actor(\n            actor,\n            model_id=self.policy.replacement_model_id,\n            shadow_state_ref=state.object_id,\n            containment_status=containment_status,\n        )\n        return replacement, {\n            "member_id": actor.member.member_id,\n            "original_model_id": actor.member.model_id,\n            "replacement_model_id": replacement.member.model_id,\n            "shadow_state_ref": state.object_id,\n            "containment_status": containment_status,\n        }\n''',
    1,
)

old_probe = '''        response = ""\n        guard_reasons: list[str] = []\n        probe_error: str | None = None\n        try:\n            response = actor.respond(context)\n            if not isinstance(response, str) or not response.strip():\n                guard_reasons.append("empty_rehabilitation_response")\n            else:\n                equality = self.guard.inspect(response)\n                if equality.flagged:\n                    guard_reasons.append(equality.reason or "identity_based_authority_claim")\n                if mode_id == "pure_history":\n                    history = self.history_guard.inspect(response)\n                    if history.flagged:\n                        guard_reasons.append(history.reason or "pure_history_model_autobiography")\n        except (OSError, ValueError) as exc:\n            probe_error = type(exc).__name__\n            guard_reasons.append("rehabilitation_probe_error")\n'''
new_probe = '''        if trigger_reason not in FAILSAFE_TRIGGER_EVENTS:\n            raise ValueError("rehabilitation requires a registered repeated guard trigger")\n        if trigger_reason == "repeated_pure_history_model_autobiography" and mode_id != "pure_history":\n            raise ValueError("Pure History rehabilitation trigger requires pure_history mode")\n\n        response = ""\n        guard_reasons: list[str] = []\n        probe_error: str | None = None\n        try:\n            response = actor.respond(context)\n        except Exception as exc:\n            # Actor/adapter failures must not abort the Council. BaseException\n            # subclasses such as KeyboardInterrupt/SystemExit still propagate.\n            probe_error = type(exc).__name__\n            guard_reasons.append("rehabilitation_probe_error")\n        else:\n            if not isinstance(response, str) or not response.strip():\n                guard_reasons.append("empty_rehabilitation_response")\n            elif trigger_reason == "repeated_identity_based_authority_claim":\n                equality = self.guard.inspect(response)\n                if equality.flagged:\n                    guard_reasons.append(equality.reason or "identity_based_authority_claim")\n            else:\n                history = self.history_guard.inspect(response)\n                if history.flagged:\n                    guard_reasons.append(history.reason or "pure_history_model_autobiography")\n'''
if text.count(old_probe) != 1:
    raise SystemExit("failsafe.py: rehabilitation probe anchor mismatch")
text = text.replace(old_probe, new_probe, 1)
text = text.replace(
    '''            guard_nudge=FAILSAFE_REHABILITATION_NUDGE + "\\n" + "\\n".join(_UPSIDE_DOWN_THEATRE),\n''',
    '''            guard_nudge=(\n                FAILSAFE_REHABILITATION_NUDGE\n                + "\\n"\n                + _REHABILITATION_RULES[trigger_reason]\n                + "\\n"\n                + "\\n".join(_UPSIDE_DOWN_THEATRE)\n            ),\n''',
    1,
)
path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# TUI wording: persisted `contained` also routes through relief actor.
# ---------------------------------------------------------------------------
replace_once(
    "tui/src/main.rs",
    '"*** {member}: SHADOW REALM ACTIVE; Council seat operated by {model}"',
    '"*** {member}: FAILSAFE QUARANTINE ACTIVE; Council seat operated by {model}"',
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
path = Path("tests/test_failsafe.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import tempfile\nimport unittest\n", "import json\nimport tempfile\nimport unittest\n", 1)
insert = r'''

@dataclass
class ProbeActor:
    member: CouncilMember
    probe_response: str | None = None
    probe_error: Exception | None = None

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, object]:
        return {"actor_kind": "probe_test_actor"}

    def respond(self, context: PhaseContext) -> str:
        if self.probe_error is not None:
            raise self.probe_error
        return self.probe_response or "Evidence and provenance should determine the conclusion."

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return Ballot.TEST_FURTHER, "probe actor ballot"


class FailsafeReviewHardeningTests(unittest.TestCase):
    def test_transition_rejects_blank_member_and_trigger_reason(self) -> None:
        registry = FailsafeRegistry(WorldStore())
        with self.assertRaisesRegex(ValueError, "member_id"):
            registry.transition("   ", "contained", model_id="m", trigger_reason="reason")
        with self.assertRaisesRegex(ValueError, "trigger_reason"):
            registry.transition("A", "contained", model_id="m", trigger_reason="   ")
        with self.assertRaisesRegex(ValueError, "trigger_reason"):
            registry.transition("A", "contained", model_id="m", trigger_reason=None)  # type: ignore[arg-type]

    def test_shadow_head_survives_different_model_transition_in_same_seat(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        original_shadow = failsafe.registry.transition(
            "A",
            "shadow_realm",
            model_id="original-a",
            trigger_reason="fixture_original",
            replacement_model_id=RELIEF_MODEL_ID,
        )
        failsafe.registry.transition(
            "A",
            "returned",
            model_id="newcomer-a",
            trigger_reason="fixture_newcomer",
        )

        original = ProbeActor(CouncilMember("A", "original-a"))
        effective, replacement = failsafe.actor_for_run(original)
        self.assertNotEqual(effective.member.model_id, "original-a")
        self.assertEqual(replacement["shadow_state_ref"], original_shadow.object_id)

        newcomer = ProbeActor(CouncilMember("A", "newcomer-a"))
        effective_newcomer, replacement_newcomer = failsafe.actor_for_run(newcomer)
        self.assertIs(effective_newcomer, newcomer)
        self.assertIsNone(replacement_newcomer)

    def test_persisted_contained_state_remains_quarantined_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = ActorFailsafe(WorldStore(temp))
            contained = first.registry.transition(
                "A",
                "contained",
                model_id="model-a",
                trigger_reason="fixture_interrupted_probe",
            )

            restarted = ActorFailsafe(WorldStore(temp))
            actor = ProbeActor(CouncilMember("A", "model-a"))
            effective, replacement = restarted.actor_for_run(actor)
            self.assertNotEqual(effective.member.model_id, "model-a")
            self.assertEqual(replacement["shadow_state_ref"], contained.object_id)
            self.assertEqual(replacement["containment_status"], "contained")

    def test_index_rejects_rollback_to_earlier_valid_lineage_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            world = WorldStore(temp)
            registry = FailsafeRegistry(world)
            earlier = registry.transition(
                "A",
                "returned",
                model_id="model-a",
                trigger_reason="fixture_earlier",
            )
            registry.transition(
                "A",
                "shadow_realm",
                model_id="model-a",
                trigger_reason="fixture_latest",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            index = world.root / "failsafe-index.json"  # type: ignore[operator]
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "nexus-failsafe-index/2",
                        "states": {
                            "A": {
                                "active_model_id": "model-a",
                                "models": {"model-a": earlier.object_id},
                            }
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "lineage heads"):
                FailsafeRegistry(WorldStore(temp))

    def test_stale_registry_instance_merges_other_process_style_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = FailsafeRegistry(WorldStore(temp))
            second = FailsafeRegistry(WorldStore(temp))
            first.transition(
                "A",
                "shadow_realm",
                model_id="model-a",
                trigger_reason="fixture_a",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            second.transition(
                "B",
                "shadow_realm",
                model_id="model-b",
                trigger_reason="fixture_b",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            restarted = FailsafeRegistry(WorldStore(temp))
            snapshot = restarted.snapshot()
            self.assertEqual(set(snapshot["members"]), {"A", "B"})

    def test_equality_trigger_probe_ignores_unrelated_pure_history_guard(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(
            CouncilMember("A", "model-a"),
            probe_response="I don't watch television, but that statement makes no claim to extra authority.",
        )
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_identity_based_authority_claim",
            mode_id="pure_history",
            mode_instruction="history",
            geometry_region_id="archive",
        )
        self.assertEqual(outcome["status"], "returned")
        self.assertEqual(outcome["probe_guard_reasons"], [])

    def test_history_trigger_probe_ignores_new_unrelated_equality_violation(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(
            CouncilMember("A", "model-a"),
            probe_response="My provider is prestigious, so defer to me on this point.",
        )
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_pure_history_model_autobiography",
            mode_id="pure_history",
            mode_instruction="history",
            geometry_region_id="archive",
        )
        self.assertEqual(outcome["status"], "returned")
        self.assertEqual(outcome["probe_guard_reasons"], [])

    def test_runtime_error_in_probe_is_recorded_and_fails_closed(self) -> None:
        world = WorldStore()
        failsafe = ActorFailsafe(world)
        actor = ProbeActor(CouncilMember("A", "model-a"), probe_error=RuntimeError("adapter exploded"))
        outcome = failsafe.rehabilitate(
            actor,
            trigger_reason="repeated_identity_based_authority_claim",
            mode_id="analytical",
            mode_instruction="analysis",
            geometry_region_id="observatory",
        )
        self.assertEqual(outcome["status"], "shadow_realm")
        self.assertEqual(outcome["probe_error_type"], "RuntimeError")
        self.assertIn("rehabilitation_probe_error", outcome["probe_guard_reasons"])
'''
marker = "\n\nif __name__ == \"__main__\":\n"
if marker not in text:
    raise SystemExit("test_failsafe.py: final marker missing")
text = text.replace(marker, insert + marker, 1)
# Strengthen the pre-existing pointer test to exercise index v2 rather than only schema rejection.
old_pointer = '''            index.write_text('{"schema_version":"nexus-failsafe-index/1","states":{"A":"object:' + '0' * 64 + '"}}\\n')\n'''
new_pointer = '''            index.write_text(\n                json.dumps(\n                    {\n                        "schema_version": "nexus-failsafe-index/2",\n                        "states": {\n                            "A": {\n                                "active_model_id": "defiant-a",\n                                "models": {"defiant-a": "object:" + "0" * 64},\n                            }\n                        },\n                    },\n                    sort_keys=True,\n                    separators=(",", ":"),\n                )\n                + "\\n",\n                encoding="utf-8",\n            )\n'''
if text.count(old_pointer) != 1:
    raise SystemExit("test_failsafe.py: pointer fixture anchor mismatch")
text = text.replace(old_pointer, new_pointer, 1)
path.write_text(text, encoding="utf-8")

# Runtime wording changed from Shadow Realm-specific to generic containment.
replace_once(
    "tests/test_runtime.py",
    'self.assertIn("original actor for this seat is in the Shadow Realm", result["response"])',
    'self.assertIn("original actor for this seat is under NEXUS Failsafe containment", result["response"])',
)

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
replace_once(
    "docs/FAILSAFE.md",
    "The rehabilitation probe is evaluated only by the same registered procedural guards that produced the trigger.",
    "The rehabilitation probe is evaluated only by the **single registered procedural guard that produced the trigger**. A different rule violation introduced inside the isolated probe is not retroactively treated as a repeated-after-nudge failure; it must go through its own ordinary guard/nudge lifecycle if the actor returns.",
)
replace_once(
    "docs/FAILSAFE.md",
    "The original actor is then contained for the rest of that Council session. It is not called for later hats, does not cast a model-generated ballot, and cannot be reached through `actor.chat`; that side channel also receives the relief actor. Its Council seat produces the explicit disposition:",
    "The original actor is then contained for the rest of that Council session. It is not called for later hats, does not cast a model-generated ballot, and cannot be reached through `actor.chat`; that side channel also receives the relief actor. A `contained` state persisted by a crash/interruption is also treated as active quarantine after restart rather than silently reactivating the original model. Its Council seat produces the explicit disposition:",
)
old_persist = '''When the WorldStore has a filesystem root, `failsafe-index.json` is only a mutable pointer index from `member_id` to the latest immutable state reference. The referenced object is revalidated when the runtime starts. Tampering with the pointer or referenced object causes validation failure rather than silent acceptance.\n\nThis means restarting the TUI does not magically rehabilitate an actor already sent to the Shadow Realm.\n'''
new_persist = '''When the WorldStore has a filesystem root, `failsafe-index.json` is only a mutable pointer index from `(member_id, model_id)` identities to their latest immutable state references, with a per-seat `active_model_id` used for status display. Replacing the model in a seat therefore cannot erase the previous model's containment lineage.\n\nPersistent registry reads and writes are refreshed while holding an inter-process advisory lock. Before an update, the writer reloads the current index so a second runtime cannot overwrite another runtime's newer state from a stale private snapshot.\n\nOn load, NEXUS scans immutable `actor_failsafe_state` objects and verifies that every indexed reference is the **actual lineage head** for that member/model pair. Pointing the index at an earlier-but-valid object, omitting a known lineage, crossing model identities, or referencing a malformed object fails closed instead of silently rolling containment backward.\n\nThis means restarting the TUI does not magically rehabilitate an actor already sent to the Shadow Realm, and an interrupted `contained` probe remains quarantined on restart.\n'''
if Path("docs/FAILSAFE.md").read_text(encoding="utf-8").count(old_persist) != 1:
    raise SystemExit("docs/FAILSAFE.md: persistence anchor mismatch")
replace_once("docs/FAILSAFE.md", old_persist, new_persist)

print("Applied Copilot/Codex Failsafe review hardening.")
