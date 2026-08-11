from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from nexus_runtime.operator_cli import (
    OPERATOR_CONFIG_SCHEMA,
    OperatorToolError,
    _build_tui,
    _doctor,
    _ensure_private_directory,
    _load_config,
    _save_config,
    _source_newer_than_binary,
    _version,
    operator_paths,
)


class OperatorToolingTests(unittest.TestCase):
    def test_default_paths_preserve_existing_local_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths = operator_paths(root)
            self.assertEqual(paths.venv, root / ".venv")
            self.assertEqual(paths.world, root / ".nexus-world")
            self.assertEqual(paths.trap, root / ".nexus-trap")
            self.assertEqual(paths.stenographer, root / ".nexus-stenographer")
            self.assertEqual(paths.config, root / ".nexus" / "operator.json")
            self.assertEqual(paths.tui_binary, root / "tui" / "target" / "release" / "nexus")

    @unittest.skipIf(os.name == "nt", "POSIX executable-bit contract")
    def test_repo_root_launcher_is_executable_and_valid_bash(self) -> None:
        launcher = Path(__file__).resolve().parents[1] / "nexus"
        self.assertTrue(launcher.is_file())
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertEqual(launcher.read_text(encoding="utf-8").splitlines()[0], "#!/usr/bin/env bash")
        checked = subprocess.run(
            ["bash", "-n", str(launcher)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX launcher contract")
    def test_paths_command_is_observational_on_fresh_clone(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "nexus"
        with tempfile.TemporaryDirectory() as temporary:
            missing_venv = Path(temporary) / "must-not-be-created"
            environment = dict(os.environ)
            environment["NEXUS_VENV"] = str(missing_venv)
            environment["NEXUS_BOOTSTRAP_PYTHON"] = sys.executable
            completed = subprocess.run(
                [str(launcher), "paths", "--json"],
                cwd=repo,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["venv"], str(missing_venv))
            self.assertFalse(missing_venv.exists())

    @unittest.skipIf(os.name == "nt", "POSIX launcher contract")
    def test_launcher_resolves_real_repo_and_ignores_caller_pythonpath(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary)
            malicious = outside / "nexus_runtime"
            malicious.mkdir()
            (malicious / "__init__.py").write_text("\n", encoding="utf-8")
            (malicious / "operator_cli.py").write_text(
                "print('CALLER_CONTROLLED_OPERATOR_EXECUTED')\n",
                encoding="utf-8",
            )
            launcher_link = outside / "nexus-link"
            launcher_link.symlink_to(repo / "nexus")
            missing_venv = outside / "read-only-venv"
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(outside)
            environment["NEXUS_VENV"] = str(missing_venv)
            environment["NEXUS_BOOTSTRAP_PYTHON"] = sys.executable
            completed = subprocess.run(
                [str(launcher_link), "paths", "--json"],
                cwd=outside,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("CALLER_CONTROLLED_OPERATOR_EXECUTED", completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertEqual(Path(payload["repo"]), repo)
            self.assertFalse(missing_venv.exists())

    @unittest.skipIf(os.name == "nt", "POSIX launcher contract")
    def test_launcher_rejects_overlapping_venv_before_creation(self) -> None:
        source_launcher = Path(__file__).resolve().parents[1] / "nexus"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "nexus"
            launcher.write_text(source_launcher.read_text(encoding="utf-8"), encoding="utf-8")
            launcher.chmod(0o755)
            world = root / ".nexus-world"
            world.mkdir(mode=0o700)
            forbidden = world / "python-env"
            environment = dict(os.environ)
            environment["NEXUS_VENV"] = str(forbidden)
            environment["NEXUS_BOOTSTRAP_PYTHON"] = sys.executable
            completed = subprocess.run(
                [str(launcher), "demo"],
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("overlaps world storage", completed.stderr)
            self.assertFalse(forbidden.exists())
            self.assertEqual(list(world.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX launcher contract")
    def test_launcher_rejects_symlinked_default_venv_before_creation(self) -> None:
        source_launcher = Path(__file__).resolve().parents[1] / "nexus"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "nexus"
            launcher.write_text(source_launcher.read_text(encoding="utf-8"), encoding="utf-8")
            launcher.chmod(0o755)
            world = root / ".nexus-world"
            world.mkdir(mode=0o700)
            (root / ".venv").symlink_to(world, target_is_directory=True)
            environment = dict(os.environ)
            environment.pop("NEXUS_VENV", None)
            environment["NEXUS_BOOTSTRAP_PYTHON"] = sys.executable
            completed = subprocess.run(
                [str(launcher), "demo"],
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("refusing symlinked virtualenv path", completed.stderr)
            self.assertEqual(list(world.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX launcher contract")
    def test_launcher_rejects_reused_incompatible_venv_python(self) -> None:
        source_launcher = Path(__file__).resolve().parents[1] / "nexus"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "nexus"
            launcher.write_text(source_launcher.read_text(encoding="utf-8"), encoding="utf-8")
            launcher.chmod(0o755)
            venv = root / "external-venv"
            (venv / "bin").mkdir(parents=True)
            fake_python = venv / "bin" / "python"
            fake_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_python.chmod(0o755)
            environment = dict(os.environ)
            environment["NEXUS_VENV"] = str(venv)
            environment["NEXUS_BOOTSTRAP_PYTHON"] = sys.executable
            completed = subprocess.run(
                [str(launcher), "demo"],
                cwd=root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("existing virtualenv must use Python 3.11 or newer", completed.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX permission contract")
    def test_private_directory_is_owner_only_and_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "private"
            _ensure_private_directory(private)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)

            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(OperatorToolError, "symlinked private directory"):
                _ensure_private_directory(link)

    @unittest.skipIf(os.name == "nt", "POSIX permission contract")
    def test_operator_config_is_closed_owner_only_and_contains_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            _save_config(paths, "Trent")
            raw = json.loads(paths.config.read_text(encoding="utf-8"))
            self.assertEqual(
                raw,
                {
                    "schema_version": OPERATOR_CONFIG_SCHEMA,
                    "nick": "Trent",
                },
            )
            self.assertEqual(stat.S_IMODE(paths.config.stat().st_mode), 0o600)
            serialized = paths.config.read_text(encoding="utf-8").lower()
            for forbidden in ("token", "password", "api_key", "credential", "secret"):
                self.assertNotIn(forbidden, serialized)
            self.assertEqual(_load_config(paths)["nick"], "Trent")

    @unittest.skipIf(os.name == "nt", "POSIX permission contract")
    def test_operator_config_with_loose_permissions_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            _save_config(paths, "Trent")
            paths.config.chmod(0o644)
            with self.assertRaisesRegex(OperatorToolError, "0600"):
                _load_config(paths)

    def test_operator_config_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            _ensure_private_directory(paths.config_dir)
            paths.config.write_text(
                json.dumps(
                    {
                        "schema_version": OPERATOR_CONFIG_SCHEMA,
                        "nick": "Trent",
                        "api_key": "absolutely-not",
                    }
                ),
                encoding="utf-8",
            )
            if os.name != "nt":
                paths.config.chmod(0o600)
            with self.assertRaisesRegex(OperatorToolError, "invalid closed schema"):
                _load_config(paths)

    @unittest.skipIf(os.name == "nt", "POSIX special-file contract")
    def test_operator_config_rejects_broken_symlink_and_fifo_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            _ensure_private_directory(paths.config_dir)
            paths.config.symlink_to(paths.config_dir / "missing-target")
            with self.assertRaisesRegex(OperatorToolError, "symlinked operator config"):
                _load_config(paths)
            paths.config.unlink()
            os.mkfifo(paths.config, mode=0o600)
            with self.assertRaisesRegex(OperatorToolError, "regular file"):
                _load_config(paths)

    def test_tui_staleness_is_derived_from_source_not_operator_opinion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = operator_paths(root)
            paths.tui_manifest.parent.mkdir(parents=True)
            paths.tui_manifest.write_text('[package]\nname="nexus"\nversion="1"\n', encoding="utf-8")
            source = root / "tui" / "src" / "main.rs"
            source.parent.mkdir(parents=True)
            source.write_text("fn main() {}\n", encoding="utf-8")
            paths.tui_binary.parent.mkdir(parents=True)
            paths.tui_binary.write_text("binary\n", encoding="utf-8")

            now = time.time_ns()
            old = now - 10_000_000
            os.utime(paths.tui_manifest, ns=(old, old))
            os.utime(source, ns=(old, old))
            os.utime(paths.tui_binary, ns=(now, now))
            self.assertFalse(_source_newer_than_binary(paths))

            newer = now + 10_000_000
            os.utime(source, ns=(newer, newer))
            self.assertTrue(_source_newer_than_binary(paths))

    def test_cargo_build_pins_target_directory_to_launched_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = operator_paths(root)
            paths.tui_manifest.parent.mkdir(parents=True)
            paths.tui_manifest.write_text('[package]\nname="nexus"\nversion="1"\n', encoding="utf-8")

            def fake_run(command: list[str], **_: object) -> mock.Mock:
                paths.tui_binary.parent.mkdir(parents=True, exist_ok=True)
                paths.tui_binary.write_text("binary\n", encoding="utf-8")
                result = mock.Mock()
                result.returncode = 0
                return result

            with mock.patch("nexus_runtime.operator_cli._cargo", return_value="cargo"), mock.patch(
                "nexus_runtime.operator_cli.subprocess.run", side_effect=fake_run
            ) as run:
                self.assertTrue(_build_tui(paths))
            command = run.call_args.args[0]
            self.assertIn("--target-dir", command)
            target_index = command.index("--target-dir") + 1
            self.assertEqual(Path(command[target_index]), root / "tui" / "target")
            self.assertEqual(paths.tui_binary, Path(command[target_index]) / "release" / "nexus")

    def test_read_only_version_and_doctor_never_start_runtime_health(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = operator_paths(root)
            for private in (paths.world, paths.trap, paths.stenographer, paths.config_dir):
                _ensure_private_directory(private)
            paths.python.parent.mkdir(parents=True, exist_ok=True)
            try:
                paths.python.symlink_to(Path(sys.executable))
            except OSError:
                self.skipTest("cannot create interpreter symlink")
            paths.runtime_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            paths.tui_manifest.parent.mkdir(parents=True, exist_ok=True)
            paths.tui_manifest.write_text('[package]\nname="nexus"\nversion="1"\n', encoding="utf-8")
            paths.tui_binary.parent.mkdir(parents=True, exist_ok=True)
            paths.tui_binary.write_text("binary\n", encoding="utf-8")
            now = time.time_ns()
            os.utime(paths.tui_manifest, ns=(now - 10_000_000, now - 10_000_000))
            os.utime(paths.tui_binary, ns=(now, now))

            with mock.patch("nexus_runtime.operator_cli._health") as health:
                with redirect_stdout(io.StringIO()):
                    _version(paths, as_json=True)
                    _doctor(paths, fix=False)
                health.assert_not_called()

    def test_doctor_fails_when_tui_needs_build_and_cargo_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = operator_paths(root)
            for private in (paths.world, paths.trap, paths.stenographer, paths.config_dir):
                _ensure_private_directory(private)
            paths.python.parent.mkdir(parents=True, exist_ok=True)
            try:
                paths.python.symlink_to(Path(sys.executable))
            except OSError:
                self.skipTest("cannot create interpreter symlink")
            paths.runtime_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            paths.tui_manifest.parent.mkdir(parents=True, exist_ok=True)
            paths.tui_manifest.write_text('[package]\nname="nexus"\nversion="1"\n', encoding="utf-8")
            output = io.StringIO()
            with mock.patch(
                "nexus_runtime.operator_cli._cargo",
                side_effect=OperatorToolError("cargo unavailable"),
            ), redirect_stdout(output):
                result = _doctor(paths, fix=False)
            self.assertEqual(result, 2)
            self.assertIn("[FAIL] Rust TUI", output.getvalue())
            self.assertIn("cargo unavailable", output.getvalue())

    def test_invalid_operator_nickname_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            with self.assertRaisesRegex(OperatorToolError, "operator nickname"):
                _save_config(paths, "not allowed because spaces")


if __name__ == "__main__":
    unittest.main()
