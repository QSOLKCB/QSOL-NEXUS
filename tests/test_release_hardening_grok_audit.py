from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import tomllib
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load_hardening_runner():
    path = ROOT / "tools" / "nexus_release_hardening.py"
    spec = importlib.util.spec_from_file_location("nexus_release_hardening_grok_test_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load release hardening runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARDENING_RUNNER = _load_hardening_runner()


class GrokPR49AuditClosureTests(unittest.TestCase):
    def test_hard_failure_is_failed_and_not_run_checks_are_explicit(self) -> None:
        report = HARDENING_RUNNER._build_report(
            [
                HARDENING_RUNNER.CheckResult(
                    "candidate-tree-clean",
                    "fail",
                    0.0,
                    "dirty tree",
                )
            ]
        )
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["passed"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["failed_required_checks"], ["candidate-tree-clean"])
        self.assertIn("matrix-audit", report["not_run_required_checks"])
        by_name = {item["name"]: item for item in report["checks"]}
        self.assertEqual(by_name["matrix-audit"]["status"], "not_run")

    def test_diagnostic_skip_remains_incomplete_not_failed(self) -> None:
        checks = [
            HARDENING_RUNNER.CheckResult(name, "pass", 0.0, "ok")
            for name in sorted(HARDENING_RUNNER.REQUIRED_CHECK_NAMES)
        ]
        checks = [
            HARDENING_RUNNER.CheckResult(item.name, "skip", 0.0, "diagnostic")
            if item.name == "rust-tests"
            else item
            for item in checks
        ]
        report = HARDENING_RUNNER._build_report(checks)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["failed_required_checks"], [])
        self.assertEqual(report["skipped_required_checks"], ["rust-tests"])

    def test_matrix_pins_rehearsals_and_all_twelve_grok_findings(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        detail = HARDENING_RUNNER._audit_matrix_data(matrix, ROOT / "tests")
        self.assertIn("2 required rehearsals", detail)
        self.assertIn("12/12 Grok findings", detail)
        self.assertEqual(
            set(matrix["external_audit_closure"]["finding_ids"]),
            HARDENING_RUNNER.REQUIRED_GROK_FINDING_IDS,
        )
        self.assertTrue(matrix["external_audit_closure"]["required_before_stable"])

        broken = json.loads(json.dumps(matrix))
        broken["rehearsals"][0]["sequence"][-1] = "pretend demo passed"
        with self.assertRaisesRegex(ValueError, "rehearsal inventory or sequence mismatch"):
            HARDENING_RUNNER._audit_matrix_data(broken, ROOT / "tests")

    def test_allowlisted_rehearsal_environment_drops_injection_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            source = {
                "PATH": "/usr/bin:/bin",
                "HOME": "/outside/home",
                "USER": "release",
                "LANG": "C.UTF-8",
                "LD_PRELOAD": "/tmp/evil.so",
                "LD_LIBRARY_PATH": "/tmp/evil",
                "DYLD_INSERT_LIBRARIES": "/tmp/evil.dylib",
                "PYTHONSTARTUP": "/tmp/startup.py",
                "PYTHONUSERBASE": "/tmp/python-user",
                "PYTHONPATH": "/tmp/python-path",
                "PIP_INDEX_URL": "https://evil.invalid/simple",
                "PIP_REQUIRE_VIRTUALENV": "1",
                "RUSTUP_HOME": "/tmp/rustup",
                "CARGO_HOME": "/tmp/cargo",
                "CARGO_TARGET_DIR": "/tmp/target",
                "NEXUS_VENV": "/tmp/nexus-venv",
                "SSL_CERT_FILE": "/tmp/fake-ca.pem",
            }
            clean = HARDENING_RUNNER._clean_rehearsal_env(source, home=home)
            self.assertEqual(clean["PATH"], "/usr/bin:/bin")
            self.assertEqual(clean["HOME"], str(home))
            self.assertEqual(clean["USER"], "release")
            for key in (
                "LD_PRELOAD",
                "LD_LIBRARY_PATH",
                "DYLD_INSERT_LIBRARIES",
                "PYTHONSTARTUP",
                "PYTHONUSERBASE",
                "PYTHONPATH",
                "PIP_INDEX_URL",
                "PIP_REQUIRE_VIRTUALENV",
                "RUSTUP_HOME",
                "CARGO_HOME",
                "CARGO_TARGET_DIR",
                "NEXUS_VENV",
                "SSL_CERT_FILE",
            ):
                self.assertNotIn(key, clean)
            self.assertEqual(clean["PYTHONNOUSERSITE"], "1")
            self.assertEqual(clean["PYTHONSAFEPATH"], "1")
            self.assertEqual(clean["PIP_CONFIG_FILE"], os.devnull)

    def test_porcelain_rename_cannot_hide_non_cache_source_change(self) -> None:
        output = (
            "R  src/nexus_runtime/__pycache__/api.cpython-312.pyc\0"
            "src/nexus_runtime/api.py\0"
        )
        paths = HARDENING_RUNNER._parse_porcelain_paths(output)
        self.assertEqual(
            paths,
            [
                "src/nexus_runtime/__pycache__/api.cpython-312.pyc",
                "src/nexus_runtime/api.py",
            ],
        )
        survivors = [
            path for path in paths if not HARDENING_RUNNER._is_generated_python_cache_path(path)
        ]
        self.assertEqual(survivors, ["src/nexus_runtime/api.py"])
        self.assertTrue(
            HARDENING_RUNNER._is_generated_python_cache_path(
                "tests/__pycache__/test_runtime.cpython-312.pyo"
            )
        )

    def test_safe_tar_extraction_rejects_escaping_link_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "hostile.tar"
            destination = base / "candidate"
            destination.mkdir()
            with tarfile.open(archive_path, "w") as archive:
                link = tarfile.TarInfo("link")
                link.type = tarfile.SYMTYPE
                link.linkname = "../escape"
                archive.addfile(link)
            with self.assertRaisesRegex(RuntimeError, "escaping link target"):
                HARDENING_RUNNER._safe_extract_candidate_archive(archive_path, destination)

    def test_adversarial_probe_report_uses_private_random_temp_directory(self) -> None:
        observed: dict[str, Path] = {}

        def fake_run(name, command, **kwargs):
            self.assertEqual(name, "adversarial-probes")
            index = command.index("--json-out")
            path = Path(command[index + 1])
            observed["path"] = path
            self.assertNotEqual(str(path), "/tmp/nexus-pr49-adversary.json")
            self.assertTrue(path.parent.name.startswith("nexus-adversary-report-"))
            self.assertTrue(path.parent.is_dir())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            return HARDENING_RUNNER.CheckResult(name, "pass", 0.0, "ok")

        with mock.patch.object(HARDENING_RUNNER, "_run", side_effect=fake_run):
            result = HARDENING_RUNNER._adversarial_probes(8)
        self.assertTrue(result.passed)
        self.assertIn("path", observed)
        self.assertFalse(observed["path"].parent.exists())

    def test_workflow_uses_runner_temp_uploads_report_and_uses_shallow_checkout(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-hardening.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("${{ runner.temp }}", workflow)
        self.assertIn("${{ github.run_id }}", workflow)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", workflow)
        self.assertNotIn("/tmp/nexus-release-hardening.json", workflow)
        self.assertNotIn("fetch-depth: 0", workflow)
        self.assertIn("fetch-depth: 1", workflow)

    def test_rust_toolchain_is_pinned_to_pr49_reviewed_version(self) -> None:
        with (ROOT / "rust-toolchain.toml").open("rb") as handle:
            toolchain = tomllib.load(handle)["toolchain"]
        self.assertEqual(toolchain["channel"], "1.97.1")
        self.assertEqual(toolchain["profile"], "minimal")
        self.assertIn("rustfmt", toolchain["components"])

    def test_guardian_matrix_explicitly_covers_anarchy_guardian(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        gate = next(item for item in matrix["gates"] if item["id"] == "worldstore_and_ark")
        self.assertIn("test_anarchy_guardian.py", gate["patterns"])

    @unittest.skipIf(os.name == "nt", "symbolic-link semantics differ on Windows CI")
    def test_report_writer_refuses_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            victim = base / "victim.json"
            victim.write_text("keep me\n", encoding="utf-8")
            link = base / "report.json"
            link.symlink_to(victim)
            with self.assertRaisesRegex(RuntimeError, "symlinked hardening report"):
                HARDENING_RUNNER._write_report(link, "{}\n")
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep me\n")


if __name__ == "__main__":
    unittest.main()
