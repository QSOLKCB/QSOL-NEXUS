from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from nexus_runtime import NexusAPI
from nexus_runtime.culture import CULTURE_RESERVED_OBJECT_TYPES


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PR48_RESERVED_OBJECT_TYPES = frozenset(
    {
        "nexus_performance_artifact",
        "long_shift_narration",
        "nexus_ai_game_execution",
        "long_shift_state",
        "psyche_chess_state",
    }
)


def _load_hardening_runner():
    path = ROOT / "tools" / "nexus_release_hardening.py"
    spec = importlib.util.spec_from_file_location("nexus_release_hardening_test_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load release hardening runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARDENING_RUNNER = _load_hardening_runner()


class ReleaseHardeningTests(unittest.TestCase):
    @staticmethod
    def _member() -> dict[str, str]:
        return {
            "member_id": "Alpha",
            "model_id": "mock-alpha",
            "adapter_id": "mock",
            "profile": "balanced",
        }

    @staticmethod
    def _api(base: Path, world_name: str = "world"):
        return NexusAPI(
            base / world_name,
            auth_root=base / f"{world_name}-auth",
            trap_root=base / f"{world_name}-trap",
            stenographer_root=base / f"{world_name}-stenographer",
            guardian_root=base / f"{world_name}-guardian",
        )

    def test_release_surface_keeps_progression_culture_and_continuity_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            operations = set(api.handle({"operation": "system.operations"})["operations"])
            required = {
                "progression.policy",
                "progression.portfolio",
                "culture.policy",
                "culture.open_mic.perform",
                "long.shift.ai_act",
                "psyche.chess.ai_move",
                "world.continuity.policy",
                "world.continuity.scrub",
                "world.ark.create",
                "world.ark.verify",
                "world.recovery.restore",
            }
            self.assertTrue(required.issubset(operations))

            progression = api.handle({"operation": "progression.policy"})["policy"]["authority_invariants"]
            self.assertEqual(progression["vote_weight_created"], 0)
            self.assertEqual(progression["council_seats_created"], 0)
            self.assertFalse(progression["citizenship_created"])
            self.assertFalse(progression["evidence_promoted"])

            culture = api.handle({"operation": "culture.policy"})["policy"]["authority_invariants"]
            self.assertEqual(culture["vote_weight_created"], 0)
            self.assertFalse(culture["citizenship_created_or_revoked_by_performance"])
            self.assertFalse(culture["evidence_promoted"])
            self.assertFalse(culture["game_master_is_governor"])

            continuity = api.handle({"operation": "world.continuity.policy"})["policy"]
            self.assertEqual(continuity["authority_effect"], "none")
            self.assertIn("quorum", continuity["recognized_history_rule"])
            self.assertIn("new target", continuity["ark_rule"])

    def test_malformed_new_release_surfaces_fail_structured_without_world_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            before = api.world.status()["recognized_object_count"]
            malformed = [
                {
                    "operation": "culture.open_mic.perform",
                    "member": {},
                    "kind": [],
                    "prompt": {},
                    "mode": [],
                },
                {
                    "operation": "long.shift.new",
                    "seed": 7,
                    "players": "Alpha",
                    "human_players": [],
                },
                {
                    "operation": "psyche.chess.new",
                    "white_player": [],
                    "black_player": "Beta",
                    "human_players": [],
                },
                {"operation": "world.continuity.scrub", "repair": "yes"},
                {
                    "operation": "progression.play.record",
                    "member": self._member(),
                    "game_kind": "psyche_chess",
                    "game_ref": "object:" + "0" * 64,
                },
            ]
            for request in malformed:
                response = api.handle(request)
                self.assertEqual(response["status"], "error")
                self.assertIsInstance(response["error"]["code"], str)
                self.assertTrue(response["error"]["code"])
            after = api.world.status()["recognized_object_count"]
            self.assertEqual(after, before)

    def test_culture_secret_canary_never_enters_durable_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            canary = "NEXUS_PR49_PRIVATE_CANARY_7B42"
            key_kind = "PRIVATE" + " KEY"
            prompt = (
                "Rant about printers.\n"
                f"-----BEGIN {key_kind}-----\n"
                f"{canary}\n"
                f"-----END {key_kind}-----"
            )
            response = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._member(),
                    "kind": "rant",
                    "prompt": prompt,
                    "mode": "anarchy",
                }
            )
            self.assertEqual(response["status"], "ok")
            self.assertTrue(response["secret_scrub"]["prompt_changed"])
            self.assertNotIn(canary, json.dumps(response, sort_keys=True))
            needle = canary.encode("utf-8")
            for path in base.rglob("*"):
                if path.is_file():
                    self.assertNotIn(needle, path.read_bytes(), str(path))

    def test_generic_world_create_cannot_forge_pr48_runtime_objects(self) -> None:
        self.assertEqual(
            CULTURE_RESERVED_OBJECT_TYPES,
            EXPECTED_PR48_RESERVED_OBJECT_TYPES,
            "the hardening test must independently pin every PR #48 runtime-owned object type",
        )
        with tempfile.TemporaryDirectory() as temporary:
            api = self._api(Path(temporary))
            for object_type in sorted(EXPECTED_PR48_RESERVED_OBJECT_TYPES):
                response = api.handle(
                    {
                        "operation": "world.create",
                        "object_type": object_type,
                        "payload": {"forged": True},
                    }
                )
                self.assertEqual(response["status"], "error", object_type)

    def test_representative_world_ark_round_trip_rebuilds_progression_from_immutable_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            api = self._api(base)
            performed = api.handle(
                {
                    "operation": "culture.open_mic.perform",
                    "member": self._member(),
                    "kind": "rant",
                    "prompt": "Rant about deterministic printers forming a committee.",
                    "mode": "anarchy",
                }
            )
            self.assertEqual(performed["status"], "ok")
            created = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "release_rehearsal_note",
                    "payload": {"message": "survive the Ark"},
                }
            )
            self.assertEqual(created["status"], "ok")
            note_ref = created["object"]["object_id"]
            original = api.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(original["counts"]["perform_rant"], 1)
            self.assertEqual(original["vote_weight_created"], 0)

            ark = base / "NEXUS-ARK-PR49"
            created_ark = api.world.create_ark(ark, compute_epoch=0)
            self.assertTrue(created_ark["verified"])
            self.assertEqual(api.world.verify_ark(ark)["status"], "verified")

            restored_root = base / "restored-world"
            restored = api.world.restore_ark(ark, restored_root)
            self.assertEqual(restored["status"], "restored")
            reopened = NexusAPI(
                restored_root,
                auth_root=base / "restored-auth",
                trap_root=base / "restored-trap",
                stenographer_root=base / "restored-stenographer",
                guardian_root=base / "restored-guardian",
            )
            inspected = reopened.handle({"operation": "world.inspect", "object_ref": note_ref})
            self.assertEqual(inspected["status"], "ok")
            rebuilt = reopened.handle(
                {
                    "operation": "progression.portfolio",
                    "actor_id": "Alpha",
                    "model_id": "mock-alpha",
                }
            )
            self.assertEqual(rebuilt["counts"]["perform_rant"], 1)
            self.assertEqual(rebuilt["state_ref"], original["state_ref"])
            self.assertEqual(rebuilt["vote_weight_created"], 0)
            self.assertEqual(rebuilt["citizenship_effect"], "none")
            self.assertEqual(rebuilt["evidence_effect"], "none")

    def test_hardening_matrix_is_final_release_candidate_and_cannot_self_declare_stable(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["schema"], "nexus-release-hardening-matrix/1")
        self.assertEqual(matrix["milestone"], "PR #51")
        self.assertEqual(matrix["profile"], "final_release_candidate")
        self.assertFalse(matrix["stable_release"])
        self.assertEqual(matrix["authority_effect"], "none")
        self.assertEqual(matrix["scope_through_pr"], 50)
        self.assertEqual(matrix["target_version"], "2.0.0")
        self.assertIn("exact merged PR #51 head", matrix["release_rule"])
        self.assertIn("v2.0.0", matrix["release_rule"])

    def test_hardening_runner_requires_exact_eight_gate_inventory(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        configured = {gate["id"] for gate in matrix["gates"]}
        self.assertEqual(configured, HARDENING_RUNNER.REQUIRED_GATE_IDS)
        self.assertIn("8 required gates", HARDENING_RUNNER._audit_matrix_data(matrix, ROOT / "tests"))

        incomplete = json.loads(json.dumps(matrix))
        incomplete["gates"] = incomplete["gates"][1:]
        with self.assertRaisesRegex(ValueError, "gate inventory mismatch"):
            HARDENING_RUNNER._audit_matrix_data(incomplete, ROOT / "tests")

    def test_hardening_runner_requires_every_declared_pattern_to_match(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        broken = json.loads(json.dumps(matrix))
        broken["gates"][0]["patterns"].append("test_pr49_deleted_critical_family.py")
        with self.assertRaisesRegex(ValueError, "pattern .* matches no tests"):
            HARDENING_RUNNER._audit_matrix_data(broken, ROOT / "tests")

    def test_skip_flags_cannot_produce_a_passing_complete_report(self) -> None:
        checks = [
            HARDENING_RUNNER.CheckResult(name, "pass", 0.0, "ok")
            for name in sorted(HARDENING_RUNNER.REQUIRED_CHECK_NAMES)
        ]
        checks = [
            HARDENING_RUNNER.CheckResult(check.name, "skip", 0.0, "diagnostic skip")
            if check.name == "rust-tests"
            else check
            for check in checks
        ]
        report = HARDENING_RUNNER._build_report(checks)
        self.assertFalse(report["complete"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["skipped_required_checks"], ["rust-tests"])

    def test_operator_rehearsal_environment_drops_external_nexus_and_python_overrides(self) -> None:
        clean = HARDENING_RUNNER._clean_rehearsal_env(
            {
                "PATH": "/usr/bin",
                "HOME": "/tmp/home",
                "NEXUS_VENV": "/outside/venv",
                "NEXUS_REPO_ROOT": "/outside/repo",
                "NEXUS_BOOTSTRAP_PYTHON": "/outside/python",
                "PYTHONPATH": "/outside/src",
                "PYTHONHOME": "/outside/python-home",
                "VIRTUAL_ENV": "/outside/active-venv",
            }
        )
        self.assertEqual(clean["PATH"], "/usr/bin")
        self.assertEqual(clean["HOME"], "/tmp/home")
        self.assertFalse(any(key.startswith("NEXUS_") for key in clean))
        self.assertNotIn("PYTHONPATH", clean)
        self.assertNotIn("PYTHONHOME", clean)
        self.assertNotIn("VIRTUAL_ENV", clean)

    def test_dirty_worktree_is_a_hard_failure_before_candidate_archive(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout=" M tools/nexus_release_hardening.py\n?? untracked-release-input.txt\n",
        )
        with mock.patch.object(HARDENING_RUNNER.subprocess, "run", return_value=completed):
            result = HARDENING_RUNNER._worktree_audit("candidate-tree-clean")
        self.assertEqual(result.status, "fail")
        self.assertIn("same HEAD", result.detail)

    def test_post_run_audit_ignores_only_generated_python_bytecode_cache_churn(self) -> None:
        bytecode_only = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout=(
                " M src/nexus_runtime/__pycache__/api.cpython-312.pyc\n"
                " M tests/__pycache__/test_runtime.cpython-312.pyc\n"
            ),
        )
        with mock.patch.object(HARDENING_RUNNER.subprocess, "run", return_value=bytecode_only):
            result = HARDENING_RUNNER._worktree_audit(
                "candidate-tree-unchanged",
                allow_generated_python_cache=True,
            )
        self.assertEqual(result.status, "pass")

        source_change = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout=(
                " M src/nexus_runtime/__pycache__/api.cpython-312.pyc\n"
                " M src/nexus_runtime/api.py\n"
            ),
        )
        with mock.patch.object(HARDENING_RUNNER.subprocess, "run", return_value=source_change):
            result = HARDENING_RUNNER._worktree_audit(
                "candidate-tree-unchanged",
                allow_generated_python_cache=True,
            )
        self.assertEqual(result.status, "fail")
        self.assertIn("src/nexus_runtime/api.py", result.detail)


if __name__ == "__main__":
    unittest.main()
