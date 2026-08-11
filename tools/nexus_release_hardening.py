#!/usr/bin/env python3
"""NEXUS 2.0 pre-Wall release-hardening runner.

PR #49 does not declare NEXUS stable. This tool turns the reviewed hardening
matrix into one reproducible command that checks matrix coverage, runs the full
Python regression suite, executes deterministic adversarial probes, validates
Rust TUI tests/check/format, and rehearses the one-command operator bootstrap
from a clean archive of the candidate tree.

The output is machine-readable and intentionally carries no governance,
evidence, or release authority by itself.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "release" / "hardening_matrix.json"
REPORT_SCHEMA = "nexus-release-hardening-report/1"
DEFAULT_SEED = "0x4E45585553"


@dataclass
class CheckResult:
    name: str
    status: str
    duration_seconds: float
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _run(
    name: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    timeout: int = 1200,
) -> CheckResult:
    started = time.monotonic()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=merged_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(name, "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    detail = proc.stdout
    if len(detail) > 24000:
        detail = f"[... {len(detail) - 24000} chars truncated ...]\n{detail[-24000:]}"
    return CheckResult(
        name,
        "pass" if proc.returncode == 0 else "fail",
        time.monotonic() - started,
        f"$ {' '.join(command)}\nexit={proc.returncode}\n{detail}",
    )


def _strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def _matrix_audit() -> CheckResult:
    started = time.monotonic()
    try:
        matrix = _strict_json(MATRIX_PATH)
        if not isinstance(matrix, dict):
            raise ValueError("hardening matrix must be an object")
        if matrix.get("schema") != "nexus-release-hardening-matrix/1":
            raise ValueError("unexpected hardening matrix schema")
        if matrix.get("stable_release") is not False:
            raise ValueError("PR #49 matrix must not declare stable release")
        if matrix.get("authority_effect") != "none":
            raise ValueError("hardening matrix cannot create authority")
        gates = matrix.get("gates")
        if not isinstance(gates, list) or not gates:
            raise ValueError("hardening matrix requires gates")
        seen: set[str] = set()
        matched: set[Path] = set()
        tests_root = ROOT / "tests"
        for gate in gates:
            if not isinstance(gate, dict) or gate.get("required") is not True:
                raise ValueError("every PR #49 gate must be a required object")
            gate_id = gate.get("id")
            if not isinstance(gate_id, str) or not gate_id or gate_id in seen:
                raise ValueError("hardening gate ids must be unique non-empty strings")
            seen.add(gate_id)
            patterns = gate.get("patterns")
            if not isinstance(patterns, list) or not patterns:
                raise ValueError(f"hardening gate {gate_id} has no test patterns")
            gate_matches: set[Path] = set()
            for pattern in patterns:
                if not isinstance(pattern, str) or "/" in pattern or "\\" in pattern:
                    raise ValueError(f"unsafe test pattern in gate {gate_id}")
                gate_matches.update(path for path in tests_root.glob(pattern) if path.is_file())
            if not gate_matches:
                raise ValueError(f"hardening gate {gate_id} matches no tests")
            matched.update(gate_matches)
        release_test = tests_root / "test_release_hardening.py"
        if release_test not in matched:
            raise ValueError("release composition test is not covered by the hardening matrix")
        detail = f"{len(seen)} required gates cover {len(matched)} test files"
        return CheckResult("matrix-audit", "pass", time.monotonic() - started, detail)
    except Exception as exc:
        return CheckResult("matrix-audit", "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")


def _operator_rehearsal() -> CheckResult:
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="nexus-release-operator-") as temporary:
            base = Path(temporary)
            archive_path = base / "candidate.tar"
            candidate = base / "candidate"
            candidate.mkdir()
            archived = subprocess.run(
                ["git", "archive", "--format=tar", f"--output={archive_path}", "HEAD"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            )
            if archived.returncode != 0:
                raise RuntimeError(f"git archive failed: {archived.stdout}")
            root = candidate.resolve()
            with tarfile.open(archive_path, "r") as archive:
                for member in archive.getmembers():
                    target = (candidate / member.name).resolve()
                    if target != root and root not in target.parents:
                        raise RuntimeError("candidate archive contains escaping path")
                archive.extractall(candidate)

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            commands = [
                ["./nexus", "setup", "--nick", "ReleaseProbe"],
                ["./nexus", "doctor"],
                ["./nexus", "demo"],
            ]
            transcript: list[str] = []
            for command in commands:
                proc = subprocess.run(
                    command,
                    cwd=candidate,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=900,
                    check=False,
                )
                transcript.append(f"$ {' '.join(command)}\nexit={proc.returncode}\n{proc.stdout}")
                if proc.returncode != 0:
                    raise RuntimeError("operator rehearsal failed\n" + "\n".join(transcript))
            return CheckResult(
                "fresh-archive-operator-rehearsal",
                "pass",
                time.monotonic() - started,
                "clean candidate archive completed setup, doctor and deterministic demo",
            )
    except Exception as exc:
        return CheckResult(
            "fresh-archive-operator-rehearsal",
            "fail",
            time.monotonic() - started,
            f"{type(exc).__name__}: {exc}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--skip-rust", action="store_true")
    parser.add_argument("--skip-operator", action="store_true")
    parser.add_argument("--iterations", type=int, default=128)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 4096:
        parser.error("--iterations must be between 1 and 4096")

    checks: list[CheckResult] = [_matrix_audit()]
    if checks[-1].passed:
        checks.append(
            _run(
                "full-python-regression",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                env={"PYTHONPATH": str(ROOT / "src")},
            )
        )
        checks.append(
            _run(
                "adversarial-probes",
                [
                    sys.executable,
                    "tools/nexus_adversary.py",
                    "--profile",
                    "probes",
                    "--seed",
                    DEFAULT_SEED,
                    "--iterations",
                    str(args.iterations),
                    "--json-out",
                    "/tmp/nexus-pr49-adversary.json",
                ],
                env={"PYTHONPATH": str(ROOT / "src")},
            )
        )
        if not args.skip_rust:
            checks.extend(
                [
                    _run("rust-tests", ["cargo", "test", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
                    _run("rust-check", ["cargo", "check", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
                    _run("rust-format", ["cargo", "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"]),
                ]
            )
        if not args.skip_operator:
            checks.append(_operator_rehearsal())

    passed = all(check.passed for check in checks)
    report = {
        "schema": REPORT_SCHEMA,
        "profile": "pre_wall",
        "matrix": str(MATRIX_PATH.relative_to(ROOT)),
        "stable_release": False,
        "authority_effect": "none",
        "passed": passed,
        "checks": [asdict(check) for check in checks],
        "post_wall_rule": "PR #51 must rerun the complete release-candidate matrix after PR #50",
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
