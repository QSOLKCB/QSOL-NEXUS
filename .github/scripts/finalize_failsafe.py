from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor once, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "src/nexus_runtime/failsafe.py",
    '''    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        state = self.registry.latest_state(actor.member.member_id)\n''',
    '''    def actor_for_run(self, actor: CouncilActor) -> tuple[CouncilActor, dict[str, Any] | None]:\n        if not self.policy.enabled:\n            return actor, None\n        state = self.registry.latest_state(actor.member.member_id)\n''',
)

replace_once(
    "tests/test_failsafe.py",
    '''from nexus_runtime.failsafe import FAILSAFE_SCHEMA_VERSION, FailsafeRegistry, RELIEF_MODEL_ID\n''',
    '''from nexus_runtime.failsafe import (\n    FAILSAFE_SCHEMA_VERSION,\n    ActorFailsafe,\n    FailsafePolicy,\n    FailsafeRegistry,\n    RELIEF_MODEL_ID,\n)\n''',
)

replace_once(
    "tests/test_failsafe.py",
    '''    def test_different_model_id_can_take_over_shadowed_member_seat(self) -> None:\n''',
    '''    def test_disabled_policy_does_not_activate_preexisting_shadow_substitution(self) -> None:\n        world = WorldStore()\n        enabled = ActorFailsafe(world)\n        enabled.registry.transition(\n            "A",\n            "shadow_realm",\n            model_id="mock-a",\n            trigger_reason="test_fixture",\n            replacement_model_id=RELIEF_MODEL_ID,\n        )\n        disabled = ActorFailsafe(world, policy=FailsafePolicy(enabled=False))\n        actor = calm_actor("A")\n        effective, replacement = disabled.actor_for_run(actor)\n        self.assertIs(effective, actor)\n        self.assertIsNone(replacement)\n\n    def test_different_model_id_can_take_over_shadowed_member_seat(self) -> None:\n''',
)

replace_once(
    "docs/FAILSAFE.md",
    '''Failsafe does not change the NEXUS Constitution:\n''',
    '''`FailsafePolicy(enabled=False)` disables both new containment and active Shadow-Realm substitution; persisted states remain inspectable history but do not control actor dispatch while the policy is disabled.\n\nFailsafe does not change the NEXUS Constitution:\n''',
)

print("Applied final Failsafe policy semantics fix.")
