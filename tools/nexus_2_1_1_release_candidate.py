#!/usr/bin/env python3
"""Exact-commit NEXUS 2.1.1 release-candidate verifier.

This runner verifies a candidate. It does not create or move tags, publish a
release, close the live-xAI empirical gate, or grant semantic/governance
authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = ROOT / "release" / "nexus_2_1_1_candidate.json"
MATRIX_PATH = ROOT / "release" / "nexus_2_1_1_matrix.json"
REPORT_SCHEMA = "nexus-release-candidate-2-1-1-report/1"
TARGET_VERSION = "2.1.1"
TARGET_PROTOCOL = "nexus/0.15"
TARGET_TAG = "v2.1.1"
HISTORICAL_TAG = "v2.1.0"
HISTORICAL_TAG_COMMIT = "839303ea512631e527073682343341742cead975"
PR60_MERGE = "80cda46e614f44b47861471cb329e29a348cab43"
V2_0_TAG = "v2.0.0"
V2_0_COMMIT = "cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a"
V2_0_DOI = "10.5281/zenodo.21895577"
EXPECTED_TEST_FILE_COUNT = 83
EXPECTED_CONTRACTS = {
    "contracts/instrument-admission.json": "nexus-instrument-admission-contract/1",
    "contracts/persistent-world.json": "nexus-persistent-world-contract/1",
    "contracts/alpha9-remote-operator.json": "nexus-alpha9-remote-operator-contract/1",
    "contracts/three-minds-one-world.json": "nexus-three-minds-one-world-contract/2",
}
TEST_PATTERNS = (
    "test_world_lattice.py",
    "test_instruments.py",
    "test_three_minds_demo.py",
    "test_release_hardening.py",
    "test_release_hardening_grok_audit.py",
    "test_post_merge_grok_audit.py",
    "test_release_upgrade_rehearsal.py",
    "test_release_candidate.py",
)


@dataclass
class CheckResult:
    name: str
    status: str
    duration_seconds: float
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            if key in output:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            output[key] = value
        return output

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def _git(*args: str, allow_failure: bool = False) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 and not allow_failure:
        raise ValueError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise ValueError(f"git merge-base failed: {proc.stderr.strip()}")


def _tracked_status() -> str:
    return _git("status", "--porcelain=v1", "--untracked-files=no")


def _tree_clean(label: str) -> str:
    dirty = _tracked_status()
    if dirty:
        raise ValueError(f"{label}: tracked candidate bytes differ from HEAD:\n{dirty}")
    return f"{label}: tracked candidate tree matches HEAD"


def _identity() -> tuple[str, str]:
    return _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")


def _commit_binding(expected: str | None) -> str:
    commit, tree = _identity()
    if expected is not None and commit != expected:
        raise ValueError(f"checked-out HEAD {commit} does not match expected candidate {expected}")
    return f"candidate commit={commit}; tree={tree}"


def _identity_unchanged(commit: str, tree: str, expected: str | None) -> str:
    current_commit, current_tree = _identity()
    if expected is not None and current_commit != expected:
        raise ValueError("candidate HEAD changed during release verification")
    if current_commit != commit or current_tree != tree:
        raise ValueError(
            "candidate identity changed during release verification: "
            f"start={commit}/{tree} end={current_commit}/{current_tree}"
        )
    return f"candidate identity unchanged: {current_commit}/{current_tree}"


def _parse_runtime_identity() -> tuple[str, str]:
    source = (ROOT / "src" / "nexus_runtime" / "version.py").read_text(encoding="utf-8")
    protocol = re.search(r'^PROTOCOL_VERSION\s*=\s*"([^"]+)"', source, flags=re.MULTILINE)
    runtime = re.search(r'^RUNTIME_VERSION\s*=\s*"([^"]+)"', source, flags=re.MULTILINE)
    if protocol is None or runtime is None:
        raise ValueError("cannot parse runtime/protocol identity")
    return protocol.group(1), runtime.group(1)


def _version_alignment() -> str:
    protocol, runtime = _parse_runtime_identity()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "tui" / "Cargo.lock").read_text(encoding="utf-8"))
    manifest = _strict_json(ROOT / "README4AI.md")

    python_version = str(pyproject["project"]["version"])
    rust_version = str(cargo["package"]["version"])
    lock_versions = [
        str(package.get("version"))
        for package in lock.get("package", [])
        if package.get("name") == "nexus-irc-tui"
    ]
    expected = {TARGET_VERSION}
    actual_versions = {runtime, python_version, rust_version, *lock_versions}
    if actual_versions != expected or len(lock_versions) != 1:
        raise ValueError(
            "2.1.1 executable identity mismatch: "
            f"runtime={runtime} python={python_version} rust={rust_version} lock={lock_versions}"
        )
    if protocol != TARGET_PROTOCOL:
        raise ValueError(f"protocol identity mismatch: {protocol}")
    release = manifest.get("release_identity")
    if not isinstance(release, dict):
        raise ValueError("README4AI release_identity missing")
    for key in ("runtime", "python_package", "rust_tui"):
        if release.get(key) != TARGET_VERSION:
            raise ValueError(f"README4AI release_identity.{key} mismatch")
    if release.get("protocol") != TARGET_PROTOCOL:
        raise ValueError("README4AI protocol mismatch")
    if release.get("release_posture") != "release_candidate_2_1_1":
        raise ValueError("README4AI release posture mismatch")
    return f"runtime/python/rust/lock={TARGET_VERSION}; protocol={TARGET_PROTOCOL}"


def _tag_identity() -> str:
    stable = _git("rev-parse", f"{V2_0_TAG}^{{commit}}")
    historical = _git("rev-parse", f"{HISTORICAL_TAG}^{{commit}}")
    if stable != V2_0_COMMIT:
        raise ValueError(f"{V2_0_TAG} moved: {stable}")
    if historical != HISTORICAL_TAG_COMMIT:
        raise ValueError(f"{HISTORICAL_TAG} moved: {historical}")
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{TARGET_TAG}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if proc.returncode == 0:
        raise ValueError(f"{TARGET_TAG} already exists during release-candidate review")
    if proc.returncode not in {1, 128}:
        raise ValueError(f"could not determine whether {TARGET_TAG} exists")
    return f"{V2_0_TAG}->{stable}; {HISTORICAL_TAG}->{historical}; {TARGET_TAG}=absent"


def _candidate_contract() -> str:
    candidate = _strict_json(CANDIDATE_PATH)
    matrix = _strict_json(MATRIX_PATH)
    if candidate.get("schema") != "nexus-release-candidate-2-1-1/1":
        raise ValueError("unexpected 2.1.1 candidate schema")
    if matrix.get("schema") != "nexus-release-matrix-2-1-1/1":
        raise ValueError("unexpected 2.1.1 matrix schema")
    for obj, label in ((candidate, "candidate"), (matrix, "matrix")):
        if obj.get("target_version") != TARGET_VERSION or obj.get("target_tag") != TARGET_TAG:
            raise ValueError(f"{label} target identity mismatch")
        if obj.get("protocol") != TARGET_PROTOCOL:
            raise ValueError(f"{label} protocol mismatch")
        if obj.get("stable_release") is not False or obj.get("release_authority") is not False:
            raise ValueError(f"{label} cannot self-declare release authority")
        if obj.get("authority_effect") != "none":
            raise ValueError(f"{label} cannot create authority")
    base = candidate.get("candidate_base")
    if not isinstance(base, dict) or base.get("merge_commit") != PR60_MERGE:
        raise ValueError("candidate is not bound to merged PR #60")
    historical = candidate.get("historical_v2_1_0_tag")
    if not isinstance(historical, dict):
        raise ValueError("candidate lacks historical v2.1.0 tag record")
    if historical.get("commit") != HISTORICAL_TAG_COMMIT or historical.get("move_or_rewrite") != "forbidden":
        raise ValueError("historical v2.1.0 tag policy mismatch")
    hardening = candidate.get("extension_hardening")
    if not isinstance(hardening, dict) or hardening.get("merge_commit") != PR60_MERGE:
        raise ValueError("candidate extension-hardening merge identity mismatch")
    if hardening.get("artifact_digest") != "sha256:16674e62495ed5b66f69269ec2e5fb9cdb300b39bf2b45212f00085daa83ffbb":
        raise ValueError("candidate extension-hardening artifact digest mismatch")
    if matrix.get("expected_python_test_files") != EXPECTED_TEST_FILE_COUNT:
        raise ValueError("2.1.1 matrix Python test inventory mismatch")
    actual_count = len(list((ROOT / "tests").glob("test_*.py")))
    if actual_count != EXPECTED_TEST_FILE_COUNT:
        raise ValueError(f"Python test-file inventory drift: expected {EXPECTED_TEST_FILE_COUNT}, found {actual_count}")
    return "2.1.1 candidate/matrix identities and zero-authority boundaries valid"


def _publication_and_extension_history() -> str:
    identity = (ROOT / "publication" / "nexus-2.0-formalization" / "IDENTITY.env").read_text(encoding="utf-8")
    required = (
        f"NEXUS_STABLE_TAG={V2_0_TAG}",
        f"NEXUS_STABLE_COMMIT={V2_0_COMMIT}",
        f"ZENODO_DOI={V2_0_DOI}",
    )
    for line in required:
        if line not in identity:
            raise ValueError(f"frozen publication identity drift: missing {line}")
    head = _git("rev-parse", "HEAD")
    if not _is_ancestor(PR60_MERGE, head):
        raise ValueError("merged PR #60 is not an ancestor of the release candidate")
    for relative, schema in EXPECTED_CONTRACTS.items():
        value = _strict_json(ROOT / relative)
        if value.get("schema") != schema:
            raise ValueError(f"extension contract schema drift: {relative}")
        if value.get("authority_effect") != "none":
            raise ValueError(f"extension contract authority drift: {relative}")
    return f"v2.0 publication frozen; PR60 {PR60_MERGE} is ancestor; extension contracts intact"


def _run(name: str, command: list[str], *, timeout: int = 1800) -> CheckResult:
    started = time.monotonic()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(name, "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    output = proc.stdout
    if len(output) > 24000:
        output = f"[... {len(output) - 24000} chars truncated ...]\n{output[-24000:]}"
    return CheckResult(
        name,
        "pass" if proc.returncode == 0 else "fail",
        time.monotonic() - started,
        f"$ {' '.join(command)}\nexit={proc.returncode}\n{output}",
    )


def _internal(name: str, callback) -> CheckResult:
    started = time.monotonic()
    try:
        detail = callback()
    except Exception as exc:
        return CheckResult(name, "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    return CheckResult(name, "pass", time.monotonic() - started, str(detail))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path = path.expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"report target already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            if os.name != "nt":
                os.fchmod(handle.fileno(), stat.S_IRUSR | stat.S_IWUSR)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def run_candidate(expect_commit: str | None) -> dict[str, Any]:
    start_commit, start_tree = _identity()
    checks: list[CheckResult] = [
        _internal("candidate-tree-clean-before", lambda: _tree_clean("before")),
        _internal("candidate-commit-binding", lambda: _commit_binding(expect_commit)),
        _internal("candidate-contract", _candidate_contract),
        _internal("version-alignment", _version_alignment),
        _internal("tag-identity", _tag_identity),
        _internal("publication-and-extension-history", _publication_and_extension_history),
        _run("readme-contract", [sys.executable, "tools/validate_readme_contract.py", "--mode", "contract"]),
    ]

    for pattern in TEST_PATTERNS:
        checks.append(
            _run(
                f"python:{pattern}",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"],
            )
        )

    checks.extend(
        [
            _run("alpha9-self-test", [sys.executable, "tools/live_xai_acceptance.py", "--self-test"]),
            _run("rust-test-locked", ["cargo", "test", "--locked", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
            _run("rust-check-locked", ["cargo", "check", "--locked", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
            _run("rust-format", ["cargo", "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"], timeout=300),
            _internal("candidate-tree-clean-after", lambda: _tree_clean("after")),
            _internal(
                "candidate-identity-unchanged",
                lambda: _identity_unchanged(start_commit, start_tree, expect_commit),
            ),
        ]
    )

    passed = all(check.passed for check in checks)
    return {
        "schema": REPORT_SCHEMA,
        "target_version": TARGET_VERSION,
        "target_tag": TARGET_TAG,
        "protocol": TARGET_PROTOCOL,
        "git_commit": start_commit,
        "git_tree": start_tree,
        "candidate_pr": 61,
        "candidate_base_merge": PR60_MERGE,
        "historical_v2_1_0_tag": {
            "tag": HISTORICAL_TAG,
            "commit": HISTORICAL_TAG_COMMIT,
            "moved": False,
        },
        "checks": [asdict(check) for check in checks],
        "failed_required_checks": [check.name for check in checks if not check.passed],
        "complete": passed,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "stable_release": False,
        "release_authority": False,
        "tag_created": False,
        "live_xai_acceptance_closed": False,
        "authority_effect": "none",
    }


def _self_test(expect_commit: str | None) -> None:
    _tree_clean("self-test")
    _commit_binding(expect_commit)
    _candidate_contract()
    _version_alignment()
    _tag_identity()
    _publication_and_extension_history()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-commit")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            _self_test(args.expect_commit)
            print("NEXUS 2.1.1 release-candidate self-test: ok")
            return 0
        report = run_candidate(args.expect_commit)
        if args.json_out is not None:
            _write_report(args.json_out, report)
        print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    except (FileExistsError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"NEXUS 2.1.1 RELEASE CANDIDATE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
