from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from nexus_runtime.operator_cli import (
    OPERATOR_CONFIG_SCHEMA,
    OperatorToolError,
    _ensure_private_directory,
    _load_config,
    _save_config,
    _source_newer_than_binary,
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
            with self.assertRaisesRegex(OperatorToolError, "invalid closed schema"):
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

    def test_invalid_operator_nickname_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = operator_paths(Path(temporary))
            with self.assertRaisesRegex(OperatorToolError, "operator nickname"):
                _save_config(paths, "not allowed because spaces")


if __name__ == "__main__":
    unittest.main()
