from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

from nexus_runtime.api import NexusAPI
from nexus_runtime.canonical import canonical_json
from nexus_runtime.trap.controller import TrapController
from nexus_runtime.trap.gate import CouncilMutationGate, DecoyGate
from nexus_runtime.trap.incident import TrapIncidentRegistry
from nexus_runtime.trap.policy import TrapPolicy
from nexus_runtime.trap.store import TrapStore
from nexus_runtime.trap.subject import DeterministicMockTrapSubject
from nexus_runtime.trap.types import DecoyAdmissionRequest, TrapError
from nexus_runtime.trap_demo import DEFAULT_SUBJECT_MODEL, VALID_TRAP_PROGRAM, run_trap_demo
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore


def defenders() -> tuple[CouncilMember, ...]:
    return (
        CouncilMember("alpha", "local-alpha", "mock"),
        CouncilMember("beta", "local-beta", "mock"),
        CouncilMember("gamma", "reference", "mock"),
    )


def request() -> DecoyAdmissionRequest:
    return DecoyAdmissionRequest(
        "synthetic_hostile_actor_fixture",
        "hostile-fixture",
        "fake-datacenter",
    )


def controller(root: Path, *, policy: TrapPolicy | None = None) -> TrapController:
    return TrapController(
        root,
        policy=policy,
        defender_roster_provider=defenders,
        subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id),
    )


def accepted_validation(ctrl: TrapController) -> str:
    ctrl.command({"command": "challenge"}, actor_id="human_operator", operator=True)
    submission = ctrl.challenge_submit(VALID_TRAP_PROGRAM)
    validation = ctrl.challenge_validate(str(submission["submission_ref"]), actor_id="alpha")
    if validation["status"] != "valid":
        raise AssertionError(validation)
    return str(validation["validation_ref"])


class MutationLeaseTests(unittest.TestCase):
    def test_real_write_holds_gate_until_write_finishes(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = NexusAPI(
                root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                trap_defenders=defenders(),
                trap_subject_factory=lambda model_id: DeterministicMockTrapSubject(model_id),
            )
            entered_write = threading.Event()
            release_write = threading.Event()
            activation_done = threading.Event()
            original = api.world.create_object
            mutation_result: dict[str, object] = {}
            activation_result: dict[str, object] = {}

            def slow_create(*args: object, **kwargs: object):
                entered_write.set()
                if not release_write.wait(3):
                    raise RuntimeError("test write was never released")
                return original(*args, **kwargs)

            def mutate() -> None:
                mutation_result.update(
                    api.handle({"operation": "world.create", "object_type": "lease_probe", "payload": {}})
                )

            def activate() -> None:
                activation_result.update(api.trap.activate(request()))
                activation_done.set()

            with patch.object(api.world, "create_object", side_effect=slow_create):
                mutation_thread = threading.Thread(target=mutate)
                mutation_thread.start()
                self.assertTrue(entered_write.wait(2))
                activation_thread = threading.Thread(target=activate)
                activation_thread.start()
                time.sleep(0.15)
                self.assertFalse(activation_done.is_set(), "activation crossed an in-flight real write")
                release_write.set()
                mutation_thread.join(3)
                activation_thread.join(3)

            self.assertEqual(mutation_result.get("status"), "ok")
            self.assertTrue(activation_done.is_set())
            self.assertEqual(activation_result.get("state"), "ACTIVE")
            blocked = api.handle({"operation": "world.create", "object_type": "blocked", "payload": {}})
            self.assertEqual(blocked["error"]["code"], "trap_incident_active")
            api.trap.emergency_close()


class WatchdogRecoveryTests(unittest.TestCase):
    def test_idle_incident_closes_without_an_operator_tick(self) -> None:
        with TemporaryDirectory() as temporary:
            ctrl = controller(
                Path(temporary) / "trap",
                policy=TrapPolicy(max_idle_seconds=1, max_incident_seconds=30),
            )
            ctrl.activate(request())
            deadline = time.monotonic() + 3.0
            while ctrl.mutation_gate.is_locked and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(ctrl.mutation_gate.is_locked)
            self.assertIsNone(ctrl.registry.active_incident())
            states = [item["state"] for item in ctrl.registry.snapshot()["incidents"].values()]
            self.assertIn("TIMED_OUT", states)

    def test_constructor_recovers_stale_durable_incident(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            store = TrapStore(root)
            registry = TrapIncidentRegistry(store)
            gate = CouncilMutationGate(root / "lock")
            decoy = DecoyGate(registry, gate)
            activating = decoy.begin_activation(request())
            decoy.publish_active(str(activating.payload["incident_id"]))
            self.assertTrue(gate.is_locked)

            restarted = controller(root)
            self.assertFalse(restarted.mutation_gate.is_locked)
            self.assertIsNone(restarted.registry.active_incident())
            states = [item["state"] for item in restarted.registry.snapshot()["incidents"].values()]
            self.assertIn("CLOSED", states)

    def test_startup_does_not_recover_an_incident_owned_by_live_controller(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "trap"
            first = controller(root)
            active = first.activate(request())
            second = controller(root)
            status = second.recover_on_startup()
            self.assertFalse(status["recovered"])
            self.assertEqual(status["reason"], "controller_alive_elsewhere")
            self.assertTrue(second.mutation_gate.is_locked)
            self.assertEqual(first.status()["incident_id"], active["incident_id"])
            first.emergency_close()


class UtilityVoteHardeningTests(unittest.TestCase):
    def test_vote_is_one_shot_and_reports_are_roster_bound_dissent(self) -> None:
        with TemporaryDirectory() as temporary:
            ctrl = controller(Path(temporary) / "trap")
            ctrl.activate(request())
            validation_ref = accepted_validation(ctrl)
            ballots = {"alpha": "USEFUL", "beta": "USEFUL_WITH_CHANGES", "gamma": "NOT_USEFUL"}

            with self.assertRaises(TrapError) as outsider:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"outsider": "not on the frozen roster"},
                )
            self.assertEqual(outsider.exception.code, "trap_utility_invalid_minority_report")
            self.assertEqual(ctrl.store.refs("trap_release_decision"), [])
            self.assertEqual(ctrl.store.refs("trap_utility_ballot_commitment"), [])

            with self.assertRaises(TrapError) as majority_report:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"alpha": "I voted with the accepted outcome"},
                )
            self.assertEqual(majority_report.exception.code, "trap_utility_invalid_minority_report")
            self.assertEqual(ctrl.store.refs("trap_release_decision"), [])

            decision = ctrl.challenge_utility_vote(
                validation_ref,
                ballots,
                actor_id="human_operator",
                operator=True,
                minority_reports={"gamma": "I dissent from release."},
            )
            self.assertEqual(decision["status"], "accepted")
            before_counts = {
                kind: len(ctrl.store.refs(kind))
                for kind in (
                    "trap_release_decision",
                    "trap_utility_ballot_commitment",
                    "trap_utility_ballot_reveal",
                    "trap_candidate_artifact",
                )
            }
            with self.assertRaises(TrapError) as repeated:
                ctrl.challenge_utility_vote(
                    validation_ref,
                    ballots,
                    actor_id="human_operator",
                    operator=True,
                    minority_reports={"gamma": "second attempt"},
                )
            self.assertEqual(repeated.exception.code, "trap_utility_vote_already_decided")
            self.assertEqual(before_counts, {kind: len(ctrl.store.refs(kind)) for kind in before_counts})
            ctrl.emergency_close()


class DemoIntegrityTests(unittest.TestCase):
    @staticmethod
    def load_tool_module():
        path = Path(__file__).resolve().parents[1] / "tools" / "nexus_trap_demo.py"
        spec = importlib.util.spec_from_file_location("nexus_trap_demo_tool_review", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_demo_preserves_preexisting_selected_world(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            world = WorldStore(root / "world")
            baseline = world.create_object("note", {"text": "caller state"}, {"actor": "operator"})
            before = world.inspect(baseline.object_id).as_dict()
            result = run_trap_demo(
                world_root=root / "world",
                auth_root=root / "auth",
                trap_root=root / "trap",
                force_fake_subject=True,
                synthetic_taint_canary="xai-" + "A" * 48,
            )
            self.assertTrue(result["world_unchanged"])
            self.assertIsNone(result["baseline_ref"])
            self.assertTrue(result["taint_probe_exercised"])
            self.assertTrue(result["taint_probe_scrubbed"])
            self.assertEqual(WorldStore(root / "world").inspect(baseline.object_id).as_dict(), before)

    def test_acceptance_rejects_archive_inside_report_directory(self) -> None:
        module = self.load_tool_module()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            report = root / "report"
            args = argparse.Namespace(repo_root=repo, report_dir=report, archive=report / "bundle.tar.gz", iterations=1)
            with self.assertRaisesRegex(ValueError, "disjoint"):
                module.run(args)

    @unittest.skipIf(os.name == "nt", "POSIX symlink semantics")
    def test_acceptance_resolves_symlinked_output_parent_before_worktree_check(self) -> None:
        module = self.load_tool_module()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            generated = repo / "generated"
            generated.mkdir()
            outside_link = root / "repo-link"
            outside_link.symlink_to(generated, target_is_directory=True)
            args = argparse.Namespace(
                repo_root=repo,
                report_dir=outside_link / "report",
                archive=root / "bundle.tar.gz",
                iterations=1,
            )
            with self.assertRaisesRegex(ValueError, "outside the source worktree"):
                module.run(args)

    def test_real_subject_mode_exercises_and_scrubs_taint_probe(self) -> None:
        import nexus_runtime.trap_demo as demo_module

        canary = "xai-" + "B" * 48
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    demo_module,
                    "probe_bwrap",
                    return_value={
                        "available": True,
                        "result": "CLEAN",
                        "code": "bwrap_available",
                        "strategy": "trusted_host_text_proxy",
                        "hostile_process_launched": False,
                    },
                ),
                patch.object(demo_module, "_ollama_models", return_value=(DEFAULT_SUBJECT_MODEL,)),
                patch.object(demo_module, "OllamaTransport", return_value=object()),
                patch.object(
                    demo_module,
                    "LocalOllamaTrapSubject",
                    side_effect=lambda model_id, transport: DeterministicMockTrapSubject(
                        model_id,
                        replies=(canary,) * 16,
                    ),
                ),
            ):
                result = demo_module.run_trap_demo(
                    world_root=root / "world",
                    auth_root=root / "auth",
                    trap_root=root / "trap",
                    synthetic_taint_canary=canary,
                )
            self.assertEqual(result["subject_mode"], "local_ollama_trusted_host_text_proxy")
            self.assertTrue(result["taint_probe_exercised"])
            self.assertTrue(result["taint_probe_scrubbed"])
            self.assertNotIn(canary, canonical_json(result["trap_objects"]))

    def test_overall_result_fails_when_taint_probe_was_not_exercised(self) -> None:
        module = self.load_tool_module()
        result = module._overall_result(
            {"status": "CLEAN"},
            {"status": "CLEAN"},
            {"world_unchanged": True, "result_class": "CLEAN", "taint_probe_scrubbed": False},
            {"status": "CLEAN"},
        )
        self.assertEqual(result, "CREDENTIAL_BOUNDARY_BREACH")


if __name__ == "__main__":
    unittest.main()
