#!/usr/bin/env python3
"""NEXUS 2.0 pre-Wall release-hardening runner.

PR #49 established the pre-Wall baseline. This runner remains the executable
hardening contract carried forward through the pre-stable line. It audits the
matrix, runs the full regression/adversarial/Rust suite, rehearses operator
bootstrap from a clean candidate archive, and emits a machine-readable report.

The output carries no governance, evidence, or release authority by itself.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "release" / "hardening_matrix.json"
REPORT_SCHEMA = "nexus-release-hardening-report/1"
DEFAULT_SEED = "0x4E45585553"
REQUIRED_GATE_IDS = frozenset(
    {
        "adapter_and_credentials",
        "council_and_authority",
        "operator_bootstrap",
        "worldstore_and_ark",
        "progression_and_civic_life",
        "culture_rpg_and_psyche_chess",
        "trap_and_civic_durability",
        "release_composition",
    }
)
REQUIRED_REHEARSALS: dict[str, tuple[str, ...]] = {
    "fresh_archive_operator_bootstrap": (
        "archive candidate tree into a clean temporary directory",
        "./nexus setup --nick ReleaseProbe",
        "./nexus doctor",
        "./nexus demo",
    ),
    "representative_world_ark_round_trip": (
        "create persistent world state including AI progression/culture history",
        "create and verify a World Ark",
        "restore into a new empty target",
        "reopen NEXUS without mutable progression cache",
        "reconstruct the same portfolio from immutable restored history",
    ),
}
REQUIRED_GROK_FINDING_IDS = frozenset(f"R{index}" for index in range(1, 13))
REQUIRED_CHECK_NAMES = frozenset(
    {
        "candidate-tree-clean",
        "matrix-audit",
        "full-python-regression",
        "adversarial-probes",
        "rust-tests",
        "rust-check",
        "rust-format",
        "fresh-archive-operator-rehearsal",
        "candidate-tree-unchanged",
    }
)
_REHEARSAL_ENV_KEYS = frozenset(
    {
        "PATH",
        "USER",
        "USERNAME",
        "LOGNAME",
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "COLORTERM",
        "CI",
        "GITHUB_ACTIONS",
        "RUNNER_OS",
        "RUNNER_ARCH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
    }
)
_GENERATED_PYTHON_CACHE_SUFFIXES = frozenset({".pyc", ".pyo"})


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


def _audit_matrix_data(matrix: Any, tests_root: Path) -> str:
    if not isinstance(matrix, dict):
        raise ValueError("hardening matrix must be an object")
    if matrix.get("schema") != "nexus-release-hardening-matrix/1":
        raise ValueError("unexpected hardening matrix schema")
    if matrix.get("stable_release") is not False:
        raise ValueError("pre-stable hardening matrix must not declare stable release")
    if matrix.get("authority_effect") != "none":
        raise ValueError("hardening matrix cannot create authority")
    gates = matrix.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("hardening matrix requires gates")

    seen: set[str] = set()
    matched: set[Path] = set()
    for gate in gates:
        if not isinstance(gate, dict) or gate.get("required") is not True:
            raise ValueError("every hardening gate must be a required object")
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
            pattern_matches = {path for path in tests_root.glob(pattern) if path.is_file()}
            if not pattern_matches:
                raise ValueError(
                    f"hardening gate {gate_id} pattern {pattern!r} matches no tests"
                )
            gate_matches.update(pattern_matches)
        matched.update(gate_matches)

    if seen != REQUIRED_GATE_IDS:
        missing = sorted(REQUIRED_GATE_IDS - seen)
        extra = sorted(seen - REQUIRED_GATE_IDS)
        raise ValueError(
            "hardening gate inventory mismatch; "
            f"missing={missing or 'none'} extra={extra or 'none'}"
        )

    rehearsals = matrix.get("rehearsals")
    if not isinstance(rehearsals, list):
        raise ValueError("hardening matrix requires rehearsals")
    observed_rehearsals: dict[str, tuple[str, ...]] = {}
    for rehearsal in rehearsals:
        if not isinstance(rehearsal, dict) or rehearsal.get("required") is not True:
            raise ValueError("every hardening rehearsal must be a required object")
        rehearsal_id = rehearsal.get("id")
        sequence = rehearsal.get("sequence")
        if (
            not isinstance(rehearsal_id, str)
            or not rehearsal_id
            or rehearsal_id in observed_rehearsals
            or not isinstance(sequence, list)
            or not all(isinstance(step, str) and step for step in sequence)
        ):
            raise ValueError("hardening rehearsal ids/sequences are invalid")
        observed_rehearsals[rehearsal_id] = tuple(sequence)
    if observed_rehearsals != REQUIRED_REHEARSALS:
        raise ValueError("hardening rehearsal inventory or sequence mismatch")

    closure = matrix.get("external_audit_closure")
    if not isinstance(closure, dict) or closure.get("required_before_stable") is not True:
        raise ValueError("Grok PR49 external audit closure must remain release-blocking")
    finding_ids = closure.get("finding_ids")
    if not isinstance(finding_ids, list) or set(finding_ids) != REQUIRED_GROK_FINDING_IDS:
        raise ValueError("Grok PR49 finding inventory mismatch")
    if closure.get("status") != "resolved_in_pre_stable_line":
        raise ValueError("Grok PR49 findings must remain resolved before stable release")
    verification = closure.get("verification")
    if verification != "tests/test_release_hardening_grok_audit.py":
        raise ValueError("Grok PR49 audit closure verification target mismatch")

    release_test = tests_root / "test_release_hardening.py"
    grok_test = tests_root / "test_release_hardening_grok_audit.py"
    if release_test not in matched or grok_test not in matched:
        raise ValueError("release composition tests are not covered by the hardening matrix")
    return (
        f"{len(seen)} required gates cover {len(matched)} test files; "
        f"{len(observed_rehearsals)} required rehearsals and 12/12 Grok findings pinned"
    )


def _matrix_audit() -> CheckResult:
    started = time.monotonic()
    try:
        detail = _audit_matrix_data(_strict_json(MATRIX_PATH), ROOT / "tests")
        return CheckResult("matrix-audit", "pass", time.monotonic() - started, detail)
    except Exception as exc:
        return CheckResult("matrix-audit", "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")


def _parse_porcelain_paths(output: str) -> list[str]:
    """Extract every affected path from `git status --porcelain=v1 -z`.

    The newline fallback exists for unit-test fixtures and older callers. NUL
    mode avoids C-style quoting and carries rename/copy source paths as a
    second token, which prevents the post-run pycache exception from hiding a
    rename into or out of a source path.
    """

    if "\0" not in output:
        paths: list[str] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            body = line[3:] if len(line) >= 3 and line[2] == " " else line
            if " -> " in body:
                left, right = body.split(" -> ", 1)
                paths.extend([left.strip('"'), right.strip('"')])
            else:
                paths.append(body.strip('"'))
        return paths

    tokens = output.split("\0")
    paths = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4 or token[2] != " ":
            raise ValueError("unexpected git porcelain entry")
        status = token[:2]
        paths.append(token[3:])
        if "R" in status or "C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise ValueError("git porcelain rename/copy entry is incomplete")
            paths.append(tokens[index])
            index += 1
    return paths


def _is_generated_python_cache_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    return "__pycache__" in pure.parts and pure.suffix in _GENERATED_PYTHON_CACHE_SUFFIXES


def _worktree_audit(name: str, *, allow_generated_python_cache: bool = False) -> CheckResult:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git status failed: {proc.stdout}")
        dirty = [path for path in _parse_porcelain_paths(proc.stdout) if path]
        if allow_generated_python_cache:
            dirty = [path for path in dirty if not _is_generated_python_cache_path(path)]
        dirty = sorted(set(dirty))
        if dirty:
            preview = "\n".join(dirty[:20])
            if len(dirty) > 20:
                preview += f"\n... {len(dirty) - 20} additional entries"
            raise RuntimeError(
                "release hardening requires a clean candidate worktree so all checks and git archive test the same HEAD:\n"
                + preview
            )
        detail = "candidate worktree matches HEAD with no tracked or unignored untracked changes"
        if allow_generated_python_cache:
            detail += "; only generated tracked Python __pycache__ bytecode churn is ignored after execution"
        return CheckResult(name, "pass", time.monotonic() - started, detail)
    except Exception as exc:
        return CheckResult(name, "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")


def _clean_rehearsal_env(
    source: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> dict[str, str]:
    """Create an allowlisted environment for clean-archive execution."""

    original = os.environ if source is None else source
    env = {key: value for key, value in original.items() if key in _REHEARSAL_ENV_KEYS}
    selected_home = str(home) if home is not None else original.get("HOME")
    if selected_home:
        env["HOME"] = selected_home
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    return env


def _trusted_rustup_home() -> Path | None:
    """Resolve rustup's active home without inheriting RUSTUP_HOME blindly."""

    rustup = shutil.which("rustup")
    if rustup is None:
        return None
    try:
        proc = subprocess.run(
            [rustup, "show", "home"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    path = Path(proc.stdout.strip())
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            return None
        if os.name != "nt" and path.stat().st_uid != os.getuid():
            return None
    except OSError:
        return None
    return path


def _within(root: Path, candidate: Path) -> bool:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def _validated_archive_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    root = destination.resolve()
    members: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts:
            raise RuntimeError("candidate archive contains an escaping path")
        target = destination.joinpath(*name.parts)
        if not _within(root, target):
            raise RuntimeError("candidate archive contains an escaping path")
        if member.isdev() or member.isfifo():
            raise RuntimeError("candidate archive contains a special device/FIFO entry")
        if member.issym() or member.islnk():
            link = PurePosixPath(member.linkname)
            if link.is_absolute():
                raise RuntimeError("candidate archive contains an absolute link target")
            if member.issym():
                link_target = target.parent.joinpath(*link.parts)
            else:
                link_target = destination.joinpath(*link.parts)
            if not _within(root, link_target):
                raise RuntimeError("candidate archive contains an escaping link target")
        members.append(member)
    return members


def _safe_extract_candidate_archive(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = _validated_archive_members(archive, destination)
        if hasattr(tarfile, "data_filter"):
            archive.extractall(destination, members=members, filter="data")
        else:  # pragma: no cover - supported CI is Python >=3.11 with modern tarfile
            if any(member.issym() or member.islnk() for member in members):
                raise RuntimeError("legacy Python tar extraction refuses archive links")
            archive.extractall(destination, members=members)


def _operator_rehearsal() -> CheckResult:
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="nexus-release-operator-") as temporary:
            base = Path(temporary)
            archive_path = base / "candidate.tar"
            candidate = base / "candidate"
            candidate.mkdir(mode=0o700)
            rehearsal_home = base / "home"
            rehearsal_home.mkdir(mode=0o700)
            cargo_home = rehearsal_home / ".cargo"
            cargo_home.mkdir(mode=0o700)
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
            _safe_extract_candidate_archive(archive_path, candidate)

            env = _clean_rehearsal_env(home=rehearsal_home)
            env["CARGO_HOME"] = str(cargo_home)
            trusted_rustup = _trusted_rustup_home()
            if trusted_rustup is not None:
                env["RUSTUP_HOME"] = str(trusted_rustup)
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
                "clean candidate archive completed setup, doctor and deterministic demo under an allowlisted environment and safe tar extraction",
            )
    except Exception as exc:
        return CheckResult(
            "fresh-archive-operator-rehearsal",
            "fail",
            time.monotonic() - started,
            f"{type(exc).__name__}: {exc}",
        )


def _adversarial_probes(iterations: int) -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="nexus-adversary-report-") as temporary:
        report_path = Path(temporary) / "report.json"
        return _run(
            "adversarial-probes",
            [
                sys.executable,
                "tools/nexus_adversary.py",
                "--profile",
                "probes",
                "--seed",
                DEFAULT_SEED,
                "--iterations",
                str(iterations),
                "--json-out",
                str(report_path),
            ],
            env={"PYTHONPATH": str(ROOT / "src")},
        )


def _skipped(name: str, reason: str) -> CheckResult:
    return CheckResult(name, "skip", 0.0, reason)


def _not_run(name: str, reason: str) -> CheckResult:
    return CheckResult(name, "not_run", 0.0, reason)


def _build_report(checks: list[CheckResult]) -> dict[str, Any]:
    observed_names = {check.name for check in checks}
    not_run_required = sorted(REQUIRED_CHECK_NAMES - observed_names)
    rendered_checks = list(checks)
    rendered_checks.extend(
        _not_run(name, "not run because an earlier required hardening gate stopped execution")
        for name in not_run_required
    )
    skipped_required = sorted(
        check.name
        for check in rendered_checks
        if check.name in REQUIRED_CHECK_NAMES and check.status == "skip"
    )
    failed_required = sorted(
        check.name
        for check in rendered_checks
        if check.name in REQUIRED_CHECK_NAMES and check.status == "fail"
    )
    complete = not skipped_required and not not_run_required
    passed = complete and not failed_required and all(check.passed for check in rendered_checks)
    if failed_required:
        status = "failed"
    elif skipped_required or not_run_required:
        status = "incomplete"
    elif passed:
        status = "passed"
    else:
        status = "failed"
    return {
        "schema": REPORT_SCHEMA,
        "profile": "pre_wall",
        "matrix": str(MATRIX_PATH.relative_to(ROOT)),
        "stable_release": False,
        "authority_effect": "none",
        "status": status,
        "complete": complete,
        "passed": passed,
        "failed_required_checks": failed_required,
        "skipped_required_checks": skipped_required,
        "missing_required_checks": not_run_required,
        "not_run_required_checks": not_run_required,
        "checks": [asdict(check) for check in rendered_checks],
        "post_wall_rule": "PR #51 must rerun the complete release-candidate matrix after PR #50 and verify 12/12 Grok PR49 findings remain closed",
    }


def _write_report(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError("refusing symlinked hardening report output")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--skip-rust", action="store_true")
    parser.add_argument("--skip-operator", action="store_true")
    parser.add_argument("--iterations", type=int, default=128)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 4096:
        parser.error("--iterations must be between 1 and 4096")

    checks: list[CheckResult] = [_worktree_audit("candidate-tree-clean")]
    if checks[-1].passed:
        checks.append(_matrix_audit())
    if checks[-1].name == "matrix-audit" and checks[-1].passed:
        checks.append(
            _run(
                "full-python-regression",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                env={"PYTHONPATH": str(ROOT / "src")},
            )
        )
        checks.append(_adversarial_probes(args.iterations))
        if args.skip_rust:
            reason = "required Rust hardening check skipped by explicit local diagnostic flag"
            checks.extend(
                [
                    _skipped("rust-tests", reason),
                    _skipped("rust-check", reason),
                    _skipped("rust-format", reason),
                ]
            )
        else:
            checks.extend(
                [
                    _run("rust-tests", ["cargo", "test", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
                    _run("rust-check", ["cargo", "check", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
                    _run("rust-format", ["cargo", "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"]),
                ]
            )
        if args.skip_operator:
            checks.append(
                _skipped(
                    "fresh-archive-operator-rehearsal",
                    "required operator rehearsal skipped by explicit local diagnostic flag",
                )
            )
        else:
            checks.append(_operator_rehearsal())
        checks.append(
            _worktree_audit(
                "candidate-tree-unchanged",
                allow_generated_python_cache=True,
            )
        )

    report = _build_report(checks)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out is not None:
        _write_report(args.json_out, rendered)
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
