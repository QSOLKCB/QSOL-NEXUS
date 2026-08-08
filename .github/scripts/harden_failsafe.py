from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor once, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---- failsafe trigger fairness / policy ----
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''FAILSAFE_TRIGGER_EVENTS = frozenset(\n    {\n        "repeated_identity_based_authority_claim",\n        "identity_based_authority_claim_after_pure_history_nudge",\n        "repeated_pure_history_model_autobiography",\n    }\n)\n''',
    '''FAILSAFE_TRIGGER_EVENTS = frozenset(\n    {\n        "repeated_identity_based_authority_claim",\n        "repeated_pure_history_model_autobiography",\n    }\n)\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''class FailsafePolicy:\n    enabled: bool = True\n    max_rehabilitations_per_session: int = 1\n    shadow_after_failed_rehabilitation: bool = True\n    replacement_model_id: str = RELIEF_MODEL_ID\n\n    def __post_init__(self) -> None:\n        if type(self.enabled) is not bool or type(self.shadow_after_failed_rehabilitation) is not bool:\n            raise ValueError("failsafe policy boolean fields must be booleans")\n        if type(self.max_rehabilitations_per_session) is not int or self.max_rehabilitations_per_session < 0:\n            raise ValueError("max_rehabilitations_per_session must be a non-negative exact integer")\n''',
    '''class FailsafePolicy:\n    enabled: bool = True\n    max_rehabilitations_per_session: int = 1\n    replacement_model_id: str = RELIEF_MODEL_ID\n\n    def __post_init__(self) -> None:\n        if type(self.enabled) is not bool:\n            raise ValueError("failsafe policy enabled must be a boolean")\n        if type(self.max_rehabilitations_per_session) is not int or self.max_rehabilitations_per_session < 1:\n            raise ValueError("max_rehabilitations_per_session must be a positive exact integer")\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''            "enabled": self.enabled,\n            "max_rehabilitations_per_session": self.max_rehabilitations_per_session,\n            "shadow_after_failed_rehabilitation": self.shadow_after_failed_rehabilitation,\n            "replacement_model_id": self.replacement_model_id,\n''',
    '''            "enabled": self.enabled,\n            "max_rehabilitations_per_session": self.max_rehabilitations_per_session,\n            "replacement_model_id": self.replacement_model_id,\n''',
)

# ---- durable state binds member seat + model identity ----
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''            if obj.object_type != "actor_failsafe_state" or obj.payload.get("member_id") != member_id:\n                raise ValueError("persisted failsafe index failed state validation")\n            latest[member_id] = state_ref\n''',
    '''            if obj.object_type != "actor_failsafe_state" or obj.payload.get("member_id") != member_id:\n                raise ValueError("persisted failsafe index failed state validation")\n            if obj.payload.get("schema_version") != FAILSAFE_SCHEMA_VERSION:\n                raise ValueError("persisted failsafe state has invalid schema")\n            if obj.payload.get("status") not in {"contained", "returned", "shadow_realm"}:\n                raise ValueError("persisted failsafe state has invalid status")\n            if not isinstance(obj.payload.get("model_id"), str) or not obj.payload["model_id"]:\n                raise ValueError("persisted failsafe state requires model_id")\n            latest[member_id] = state_ref\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''        member_id: str,\n        status: str,\n        *,\n        trigger_reason: str,\n''',
    '''        member_id: str,\n        status: str,\n        *,\n        model_id: str,\n        trigger_reason: str,\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''        if status not in {"contained", "returned", "shadow_realm"}:\n            raise ValueError("invalid failsafe status")\n        previous = self.latest_ref(member_id)\n''',
    '''        if status not in {"contained", "returned", "shadow_realm"}:\n            raise ValueError("invalid failsafe status")\n        if not isinstance(model_id, str) or not model_id.strip():\n            raise ValueError("failsafe model_id must be non-empty text")\n        previous = self.latest_ref(member_id)\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''                "member_id": member_id,\n                "status": status,\n''',
    '''                "member_id": member_id,\n                "model_id": model_id,\n                "status": status,\n''',
)

# ---- relief actor can also occupy DCC side-channel safely ----
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:\n        return (\n            Ballot.TEST_FURTHER,\n            f"[NEXUS RELIEF/{self.member.member_id}] deterministic replacement ballot: TEST_FURTHER.",\n        )\n\n\nclass ActorFailsafe:\n''',
    '''    def direct_message(\n        self,\n        message: str,\n        *,\n        mode_id: str,\n        mode_instruction: str,\n        geometry_region_id: str,\n        evidence_context: str = "",\n    ) -> str:\n        evidence_note = " Attached evidence remains available to the replacement." if evidence_context else ""\n        return (\n            f"[NEXUS RELIEF/{self.member.member_id}/{mode_id}@{geometry_region_id} direct] "\n            "The original actor for this seat is in the Shadow Realm; this deterministic relief actor "\n            f"is answering instead.{evidence_note} Operator message received: {message}"\n        )\n\n    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:\n        return (\n            Ballot.TEST_FURTHER,\n            f"[NEXUS RELIEF/{self.member.member_id}] deterministic replacement ballot: TEST_FURTHER.",\n        )\n\n\nclass ActorFailsafe:\n''',
)

replace_once(
    "src/nexus_runtime/failsafe.py",
    '''    def state_ref(self, member_id: str) -> str | None:\n        return self.registry.latest_ref(member_id)\n\n    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        state = self.registry.latest_state(actor.member.member_id)\n        if state is None or state.payload.get("status") != "shadow_realm":\n            return actor, None\n''',
    '''    def state_ref(self, member_id: str, model_id: str | None = None) -> str | None:\n        state = self.registry.latest_state(member_id)\n        if state is None:\n            return None\n        if model_id is not None and state.payload.get("model_id") != model_id:\n            return None\n        return state.object_id\n\n    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        state = self.registry.latest_state(actor.member.member_id)\n        if (\n            state is None\n            or state.payload.get("status") != "shadow_realm"\n            or state.payload.get("model_id") != actor.member.model_id\n        ):\n            return actor, None\n''',
)

# ---- rehabilitation uses a real content-addressed isolation context and actor sees cursed theatre ----
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''        contained = self.registry.transition(\n            actor.member.member_id,\n            "contained",\n            trigger_reason=trigger_reason,\n        )\n        probe_id = sha256_ref(\n''',
    '''        contained = self.registry.transition(\n            actor.member.member_id,\n            "contained",\n            model_id=actor.member.model_id,\n            trigger_reason=trigger_reason,\n        )\n        isolation = self.world.create_object(\n            "failsafe_isolation_context",\n            {\n                "schema_version": FAILSAFE_SCHEMA_VERSION,\n                "member_id": actor.member.member_id,\n                "model_id": actor.member.model_id,\n                "evidence_refs": [],\n                "completed_phases": {},\n                "council_vote": False,\n                "world_mutation_authority": False,\n            },\n            {"actor": "nexus_failsafe"},\n        )\n        probe_id = sha256_ref(\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''            evidence_snapshot_ref="failsafe:isolated-no-evidence",\n            completed_phases={},\n            guard_nudge=FAILSAFE_REHABILITATION_NUDGE,\n''',
    '''            evidence_snapshot_ref=isolation.object_id,\n            completed_phases={},\n            guard_nudge=FAILSAFE_REHABILITATION_NUDGE + "\\n" + "\\n".join(_UPSIDE_DOWN_THEATRE),\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''        state = self.registry.transition(\n            actor.member.member_id,\n            status,\n            trigger_reason=trigger_reason,\n''',
    '''        state = self.registry.transition(\n            actor.member.member_id,\n            status,\n            model_id=actor.member.model_id,\n            trigger_reason=trigger_reason,\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''            "contained_state_ref": contained.object_id,\n            "state_ref": state.object_id,\n''',
    '''            "contained_state_ref": contained.object_id,\n            "isolation_context_ref": isolation.object_id,\n            "state_ref": state.object_id,\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''        state = self.registry.transition(\n            actor.member.member_id,\n            "shadow_realm",\n            trigger_reason=f"reoffence_after_parole:{trigger_reason}",\n''',
    '''        state = self.registry.transition(\n            actor.member.member_id,\n            "shadow_realm",\n            model_id=actor.member.model_id,\n            trigger_reason=f"reoffence_after_parole:{trigger_reason}",\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''            "contained_state_ref": None,\n            "state_ref": state.object_id,\n''',
    '''            "contained_state_ref": None,\n            "isolation_context_ref": None,\n            "state_ref": state.object_id,\n''',
)

# Council only treats state for the same model identity as active.
replace_once(
    "src/nexus_runtime/council.py",
    '''            actor.member.member_id: self.failsafe.state_ref(actor.member.member_id)\n            for actor in requested_actors\n''',
    '''            actor.member.member_id: self.failsafe.state_ref(actor.member.member_id, actor.member.model_id)\n            for actor in requested_actors\n''',
)

# actor.chat must not be a side door around Shadow Realm.
replace_once(
    "src/nexus_runtime/api.py",
    '''                actor = self._actor(member)\n                message_scrub = self.scrubber.scrub(message)\n''',
    '''                actor = self._actor(member)\n                actor, failsafe_replacement = self.council.failsafe.actor_for_run(actor)\n                message_scrub = self.scrubber.scrub(message)\n''',
)
replace_once(
    "src/nexus_runtime/api.py",
    '''                    "member_id": actor.member.member_id,\n                    "model_id": actor.member.model_id,\n                    "mode_id": mode.mode_id,\n''',
    '''                    "member_id": actor.member.member_id,\n                    "model_id": actor.member.model_id,\n                    "failsafe_replacement": failsafe_replacement,\n                    "mode_id": mode.mode_id,\n''',
)

# Tests: isolation is a real World object, new model does not inherit sentence, DCC uses relief.
replace_once(
    "tests/test_failsafe.py",
    '''        self.assertEqual(rehab_context.evidence_context, "")\n        self.assertEqual(rehab_context.completed_phases, {})\n        self.assertEqual(rehab_context.evidence_snapshot_ref, "failsafe:isolated-no-evidence")\n\n        state = council.failsafe.registry.latest_state("A")\n''',
    '''        self.assertEqual(rehab_context.evidence_context, "")\n        self.assertEqual(rehab_context.completed_phases, {})\n        isolation = world.inspect(rehab_context.evidence_snapshot_ref)\n        self.assertEqual(isolation.object_type, "failsafe_isolation_context")\n        self.assertEqual(isolation.payload["evidence_refs"], [])\n        self.assertFalse(isolation.payload["council_vote"])\n        self.assertFalse(isolation.payload["world_mutation_authority"])\n        self.assertIn("PROVIDER PRESTIGE CONVERSION RATE: 0.000 TROUT.", rehab_context.guard_nudge or "")\n\n        state = council.failsafe.registry.latest_state("A")\n''',
)
replace_once(
    "tests/test_failsafe.py",
    '''    def test_shadow_state_survives_runtime_restart_via_content_addressed_registry(self) -> None:\n''',
    '''    def test_different_model_id_can_take_over_shadowed_member_seat(self) -> None:\n        world = WorldStore()\n        council = CouncilCoordinator(world)\n        bad = DefiantActor(CouncilMember(member_id="A", model_id="defiant-a"), rehab_passes=False)\n        council.run("first", [bad, calm_actor("B"), calm_actor("C")])\n\n        newcomer = DeterministicMockActor(CouncilMember(member_id="A", model_id="genuinely-new-a"))\n        second = council.run("new model", [newcomer, calm_actor("B"), calm_actor("C")])\n        self.assertEqual(second["failsafe"]["preexisting_replacements"], [])\n        session = world.inspect(second["session_ref"])\n        roster_a = next(item for item in session.payload["roster"] if item["member_id"] == "A")\n        self.assertEqual(roster_a["model_id"], "genuinely-new-a")\n        self.assertEqual(roster_a["adapter_id"], "mock")\n\n    def test_shadow_state_survives_runtime_restart_via_content_addressed_registry(self) -> None:\n''',
)
replace_once(
    "tests/test_failsafe.py",
    '''            registry.transition(\n                "A",\n                "shadow_realm",\n                trigger_reason="test",\n                replacement_model_id=RELIEF_MODEL_ID,\n            )\n''',
    '''            registry.transition(\n                "A",\n                "shadow_realm",\n                model_id="defiant-a",\n                trigger_reason="test",\n                replacement_model_id=RELIEF_MODEL_ID,\n            )\n''',
)

replace_once(
    "tests/test_pure_history.py",
    '''        self.assertIn("identity_based_authority_claim_after_pure_history_nudge", events)\n        self.assertNotIn("restated_after_pure_history_nudge", events)\n''',
    '''        self.assertIn("identity_based_authority_claim_after_pure_history_nudge", events)\n        self.assertNotIn("restated_after_pure_history_nudge", events)\n        self.assertEqual(result["failsafe"]["outcomes"], [])\n''',
)

# Add API-level side-door regression using a manually shadowed seat.
replace_once(
    "tests/test_runtime.py",
    '''    def test_api_rejects_weighted_member(self) -> None:\n''',
    '''    def test_actor_chat_uses_relief_actor_for_shadowed_model_identity(self) -> None:\n        api = NexusAPI()\n        api.council.failsafe.registry.transition(\n            "A",\n            "shadow_realm",\n            model_id="mock-a",\n            trigger_reason="test_fixture",\n            replacement_model_id="nexus-failsafe-relief-v1",\n        )\n        result = api.handle(\n            {\n                "operation": "actor.chat",\n                "member": {"member_id": "A", "model_id": "mock-a", "adapter_id": "mock"},\n                "message": "hello",\n            }\n        )\n        self.assertEqual(result["status"], "ok")\n        self.assertEqual(result["model_id"], "nexus-failsafe-relief-v1")\n        self.assertEqual(result["failsafe_replacement"]["member_id"], "A")\n        self.assertIn("original actor for this seat is in the Shadow Realm", result["response"])\n\n    def test_failsafe_status_operation_reports_durable_state(self) -> None:\n        api = NexusAPI()\n        api.council.failsafe.registry.transition(\n            "A",\n            "shadow_realm",\n            model_id="mock-a",\n            trigger_reason="test_fixture",\n            replacement_model_id="nexus-failsafe-relief-v1",\n        )\n        result = api.handle({"operation": "failsafe.status", "member_id": "A"})\n        self.assertEqual(result["status"], "ok")\n        self.assertEqual(result["members"]["A"]["status"], "shadow_realm")\n        self.assertEqual(result["members"]["A"]["model_id"], "mock-a")\n\n    def test_api_rejects_weighted_member(self) -> None:\n''',
)

# Docs align trigger list and all-channel model identity scope.
replace_once(
    "docs/FAILSAFE.md",
    '''- `repeated_identity_based_authority_claim`;\n- `identity_based_authority_claim_after_pure_history_nudge`;\n- `repeated_pure_history_model_autobiography`.\n''',
    '''- `repeated_identity_based_authority_claim`;\n- `repeated_pure_history_model_autobiography`.\n\nA new Equality Guard violation introduced while answering a Pure History nudge is withheld, but it is **not** itself a Failsafe trigger: the actor has not yet ignored the Equality Guard's own nudge. This preserves the "nudge first, containment second" contract.\n''',
)
replace_once(
    "docs/FAILSAFE.md",
    '''The original actor is then contained for the rest of that Council session. It is not called for later hats and does not cast a model-generated ballot. Its Council seat produces the explicit disposition:\n''',
    '''The original actor is then contained for the rest of that Council session. It is not called for later hats, does not cast a model-generated ballot, and cannot be reached through `actor.chat`; that side channel also receives the relief actor. Its Council seat produces the explicit disposition:\n''',
)
replace_once(
    "docs/FAILSAFE.md",
    '''The replacement occupies the **same member seat** so no extra vote is created.\n''',
    '''The replacement occupies the **same member seat** so no extra vote is created. Shadow state is bound to the offending `model_id` as well as the member seat: if the operator deliberately installs a genuinely different model into that seat, the newcomer does not inherit the prior model's sentence.\n''',
)
replace_once(
    "docs/FAILSAFE.md",
    '''The rehabilitation call receives:\n\n- no Council evidence text;\n''',
    '''The actor also sees the harmless cursed Upside Down theatre text inside the rehabilitation instruction itself; the joke is not merely printed for the human operator.\n\nThe rehabilitation call receives:\n\n- no Council evidence text;\n''',
)

print("Applied Failsafe self-review hardening.")
