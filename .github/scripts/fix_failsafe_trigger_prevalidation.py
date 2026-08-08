from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor once, found {count}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/nexus_runtime/failsafe.py",
    '''    ) -> dict[str, Any]:\n        contained = self.registry.transition(\n''',
    '''    ) -> dict[str, Any]:\n        if trigger_reason not in FAILSAFE_TRIGGER_EVENTS:\n            raise ValueError("rehabilitation requires a registered repeated guard trigger")\n        if trigger_reason == "repeated_pure_history_model_autobiography" and mode_id != "pure_history":\n            raise ValueError("Pure History rehabilitation trigger requires pure_history mode")\n\n        contained = self.registry.transition(\n''',
)
replace_once(
    "src/nexus_runtime/failsafe.py",
    '''\n        if trigger_reason not in FAILSAFE_TRIGGER_EVENTS:\n            raise ValueError("rehabilitation requires a registered repeated guard trigger")\n        if trigger_reason == "repeated_pure_history_model_autobiography" and mode_id != "pure_history":\n            raise ValueError("Pure History rehabilitation trigger requires pure_history mode")\n\n        response = ""\n''',
    '''\n        response = ""\n''',
)
replace_once(
    "tests/test_failsafe.py",
    '''    def test_runtime_error_in_probe_is_recorded_and_fails_closed(self) -> None:\n''',
    '''    def test_unregistered_trigger_is_rejected_before_any_state_is_persisted(self) -> None:\n        world = WorldStore()\n        failsafe = ActorFailsafe(world)\n        actor = ProbeActor(CouncilMember("A", "model-a"))\n        with self.assertRaisesRegex(ValueError, "registered repeated guard trigger"):\n            failsafe.rehabilitate(\n                actor,\n                trigger_reason="not_a_registered_trigger",\n                mode_id="analytical",\n                mode_instruction="analysis",\n                geometry_region_id="observatory",\n            )\n        self.assertEqual(failsafe.status_snapshot()["members"], {})\n\n    def test_runtime_error_in_probe_is_recorded_and_fails_closed(self) -> None:\n''',
)
print("Moved rehabilitation trigger validation before durable containment.")
