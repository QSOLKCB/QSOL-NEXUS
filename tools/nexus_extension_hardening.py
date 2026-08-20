#!/usr/bin/env python3
"""Post-stable NEXUS extension hardening for the PR #55-#59 line.

This runner is deliberately separate from the frozen NEXUS 2.0 publication
chain. It proves that the post-v2.0 extension line is coherent enough to earn a
separately reviewed 2.1 release-identity candidate. A green report does not move
tags, bump versions, publish a release, close empirical gates, or create any
semantic/governance authority.
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
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "release" / "post_stable_extension_matrix.json"
CANDIDATE_PATH = ROOT / "release" / "post_stable_extension_candidate.json"
PUBLICATION_IDENTITY_PATH = ROOT / "publication" / "nexus-2.0-formalization" / "IDENTITY.env"
REPORT_SCHEMA = "nexus-post-stable-extension-hardening-report/1"
EXPECTED_MATRIX_SCHEMA = "nexus-post-stable-extension-matrix/1"
EXPECTED_CANDIDATE_SCHEMA = "nexus-post-stable-extension-candidate/1"
EXPECTED_PHASE = "2.1-pre-release-extension-hardening"
EXPECTED_PROFILE = "post_stable_extension_hardening"
EXPECTED_TARGET_VERSION = "2.1.0"
EXPECTED_CURRENT_VERSION = "2.0.0"
EXPECTED_TEST_FILE_COUNT = 83
EXPECTED_STABLE_TAG = "v2.0.0"
EXPECTED_STABLE_COMMIT = "cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a"
EXPECTED_FORMALIZATION_PR = 53
EXPECTED_PUBLICATION_PR = 54
EXPECTED_PUBLICATION_DOI = "10.5281/zenodo.21895577"
EXPECTED_STABLE_BASELINE = {
    "tag": EXPECTED_STABLE_TAG,
    "commit": EXPECTED_STABLE_COMMIT,
    "formalization_pr": EXPECTED_FORMALIZATION_PR,
    "publication_pr": EXPECTED_PUBLICATION_PR,
    "publication_doi": EXPECTED_PUBLICATION_DOI,
    "immutable": True,
}
EXPECTED_EXTENSION_BASELINE = "0b2a3ee467faad89e5a56b51779dc20ba13ad75d"
EXPECTED_EXTENSION_CHAIN = (
    (55, "839303ea512631e527073682343341742cead975"),
    (56, "c42414024a25e785dd29f406a829e3e02a8239bc"),
    (57, "f4c717bcab0e03811856d5061677678b35044ca1"),
    (58, "3244d439192769908fa74eac69a0c430ce5814ae"),
    (59, "0b2a3ee467faad89e5a56b51779dc20ba13ad75d"),
)
EXPECTED_GATE_IDS = frozenset(
    {
        "lattice_world_presence",
        "instrument_and_persistent_world",
        "remote_operator",
        "three_minds_integration",
        "inherited_v2_0_baseline",
        "release_composition",
    }
)
ALLOWED_RUNNER_CHECKS = frozenset(
    {
        "extension_merge_chain",
        "contract_bundle",
        "alpha9_self_test",
        "rust_remote_operator",
        "rust_format",
        "stable_tag_binding",
        "frozen_2_0_release_metadata",
        "candidate_contract",
        "candidate_tree_clean",
        "candidate_commit_binding",
        "candidate_tree_unchanged",
        "candidate_identity_unchanged",
    }
)
EXPECTED_CONTRACT_SCHEMAS = {
    "contracts/instrument-admission.json": "nexus-instrument-admission-contract/1",
    "contracts/persistent-world.json": "nexus-persistent-world-contract/1",
    "contracts/alpha9-remote-operator.json": "nexus-alpha9-remote-operator-contract/1",
    "contracts/three-minds-one-world.json": "nexus-three-minds-one-world-contract/2",
}
REQUIRED_BOUNDARIES = frozenset(
    {
        "V2_0_STABLE != POST_STABLE_EXTENSION_HEAD",
        "HARDENING_PASS != RELEASE_AUTHORITY",
        "VERSION_TARGET != VERSION_BUMP_AUTHORITY",
        "INSTRUMENT_RESULT != TRUTH",
        "PERSISTENT_LINEAGE != TRUTH",
        "IMPORT != AUTHORITY",
        "REMOTE_MODEL != PRIVILEGED_MODEL",
        "MULTI_MODEL_CONSENSUS != EVIDENCE",
        "LATTICE_POSITION != COGNITIVE_COORDINATE",
        "LIVE_ACCEPTANCE != SCIENTIFIC_VALIDATION",
    }
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
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def _run(
    name: str,
    command: list[str],
    *,
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
            cwd=ROOT,
            env=merged_env,
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


def _internal(name: str, callback: Callable[[], Any]) -> CheckResult:
    started = time.monotonic()
    try:
        detail = callback()
    except Exception as exc:
        return CheckResult(name, "fail", time.monotonic() - started, f"{type(exc).__name__}: {exc}")
    return CheckResult(name, "pass", time.monotonic() - started, str(detail))


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _git_is_ancestor(ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise ValueError(f"git merge-base failed: {proc.stderr.strip()}")


def _current_versions() -> dict[str, str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
    version_text = (ROOT / "src" / "nexus_runtime" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^RUNTIME_VERSION\s*=\s*"([^"]+)"', version_text, flags=re.MULTILINE)
    if match is None:
        raise ValueError("could not parse RUNTIME_VERSION")
    return {
        "runtime": match.group(1),
        "python_package": str(pyproject["project"]["version"]),
        "rust_tui": str(cargo["package"]["version"]),
    }


def _tracked_status() -> str:
    return _git("status", "--porcelain=v1", "--untracked-files=no")


def _candidate_tree_clean() -> str:
    status = _tracked_status()
    if status:
        raise ValueError(f"candidate worktree has tracked changes before hardening:\n{status}")
    return "tracked candidate tree is clean before extension hardening"


def _candidate_commit_binding(expect_commit: str | None) -> str:
    head = _git("rev-parse", "HEAD")
    if expect_commit is not None and head != expect_commit:
        raise ValueError(f"checked-out HEAD {head} does not match expected candidate {expect_commit}")
    return f"candidate commit={head}"


def _candidate_tree_unchanged() -> str:
    status = _tracked_status()
    if status:
        raise ValueError(f"matrix commands mutated tracked candidate bytes:\n{status}")
    return "tracked candidate tree remained clean after extension hardening"


def _candidate_identity_unchanged(
    initial_commit: str,
    initial_tree: str,
    expect_commit: str | None,
) -> str:
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if head != initial_commit:
        raise ValueError(f"candidate HEAD changed during hardening: {initial_commit} -> {head}")
    if tree != initial_tree:
        raise ValueError(f"candidate committed tree changed during hardening: {initial_tree} -> {tree}")
    if expect_commit is not None and head != expect_commit:
        raise ValueError(f"post-run HEAD {head} does not match expected candidate {expect_commit}")
    return f"candidate identity unchanged; commit={head}; tree={tree}"


def _audit_candidate(candidate: Any) -> str:
    if not isinstance(candidate, dict) or candidate.get("schema") != EXPECTED_CANDIDATE_SCHEMA:
        raise ValueError("unexpected post-stable extension candidate schema")
    if candidate.get("phase") != EXPECTED_PHASE:
        raise ValueError("extension candidate phase mismatch")
    if candidate.get("target_version") != EXPECTED_TARGET_VERSION:
        raise ValueError("extension target version mismatch")
    if candidate.get("current_runtime_version") != EXPECTED_CURRENT_VERSION:
        raise ValueError("extension current runtime version mismatch")
    if candidate.get("version_bump_status") != "deferred_until_extension_hardening_green":
        raise ValueError("extension version bump must remain deferred until hardening is green")
    if candidate.get("stable_release") is not False or candidate.get("release_authority") is not False:
        raise ValueError("extension hardening candidate cannot self-declare release authority")
    if candidate.get("authority_effect") != "none":
        raise ValueError("extension candidate cannot create authority")
    if candidate.get("stable_baseline") != EXPECTED_STABLE_BASELINE:
        raise ValueError("extension candidate frozen stable/publication identity mismatch")
    if candidate.get("extension_baseline_head") != EXPECTED_EXTENSION_BASELINE:
        raise ValueError("extension baseline head mismatch")
    chain = candidate.get("extension_merge_chain")
    if not isinstance(chain, list) or len(chain) != len(EXPECTED_EXTENSION_CHAIN):
        raise ValueError("extension merge chain has unexpected length")
    actual_chain = []
    for item in chain:
        if not isinstance(item, dict):
            raise ValueError("extension merge chain entries must be objects")
        actual_chain.append((item.get("pr"), item.get("merge_commit")))
    if tuple(actual_chain) != EXPECTED_EXTENSION_CHAIN:
        raise ValueError("extension merge chain identity mismatch")
    boundaries = candidate.get("boundaries")
    if not isinstance(boundaries, list) or frozenset(boundaries) != REQUIRED_BOUNDARIES:
        raise ValueError("extension candidate boundary inventory mismatch")
    empirical = candidate.get("empirical_gates")
    if not isinstance(empirical, dict) or empirical.get("live_xai_acceptance") != "operator-run-required":
        raise ValueError("live xAI empirical gate must remain operator-run-required")
    if empirical.get("live_success_claimed_by_ci") is not False:
        raise ValueError("CI cannot claim live xAI success")
    versions = _current_versions()
    if set(versions.values()) != {EXPECTED_CURRENT_VERSION}:
        raise ValueError(f"version bump happened before extension hardening: {versions}")
    return f"candidate contract valid; frozen publication DOI={EXPECTED_PUBLICATION_DOI}; target={EXPECTED_TARGET_VERSION}"


def _audit_matrix(matrix: Any, candidate: Any) -> str:
    if not isinstance(matrix, dict) or matrix.get("schema") != EXPECTED_MATRIX_SCHEMA:
        raise ValueError("unexpected extension hardening matrix schema")
    if matrix.get("phase") != EXPECTED_PHASE or matrix.get("profile") != EXPECTED_PROFILE:
        raise ValueError("extension hardening matrix phase/profile mismatch")
    if matrix.get("target_version") != EXPECTED_TARGET_VERSION:
        raise ValueError("extension hardening matrix target version mismatch")
    if matrix.get("current_runtime_version") != EXPECTED_CURRENT_VERSION:
        raise ValueError("extension hardening matrix current version mismatch")
    if matrix.get("version_bump_authorized") is not False:
        raise ValueError("hardening matrix cannot authorize a version bump")
    if matrix.get("stable_release") is not False or matrix.get("release_authority") is not False:
        raise ValueError("hardening matrix cannot self-declare release authority")
    if matrix.get("authority_effect") != "none":
        raise ValueError("hardening matrix cannot create authority")
    if matrix.get("expected_python_test_files") != EXPECTED_TEST_FILE_COUNT:
        raise ValueError("extension matrix Python test inventory count mismatch")
    actual_test_count = len(list((ROOT / "tests").glob("test_*.py")))
    if actual_test_count != EXPECTED_TEST_FILE_COUNT:
        raise ValueError(
            f"Python test inventory drift: expected {EXPECTED_TEST_FILE_COUNT}, found {actual_test_count}"
        )
    if matrix.get("extension_baseline_head") != EXPECTED_EXTENSION_BASELINE:
        raise ValueError("extension matrix baseline head mismatch")
    if matrix.get("extension_prs") != [item[0] for item in EXPECTED_EXTENSION_CHAIN]:
        raise ValueError("extension matrix PR inventory mismatch")
    if matrix.get("stable_baseline") != EXPECTED_STABLE_BASELINE:
        raise ValueError("extension matrix frozen stable/publication identity mismatch")
    if candidate.get("stable_baseline") != matrix.get("stable_baseline"):
        raise ValueError("candidate/matrix frozen stable publication identity disagreement")
    if matrix.get("contract_schemas") != EXPECTED_CONTRACT_SCHEMAS:
        raise ValueError("extension matrix contract schema inventory mismatch")
    boundaries = matrix.get("required_boundaries")
    if not isinstance(boundaries, list) or frozenset(boundaries) != REQUIRED_BOUNDARIES:
        raise ValueError("extension matrix boundary inventory mismatch")

    gates = matrix.get("gates")
    if not isinstance(gates, list):
        raise ValueError("extension matrix requires gates")
    seen: set[str] = set()
    runner_checks: set[str] = set()
    matched_tests: set[Path] = set()
    for gate in gates:
        if not isinstance(gate, dict) or gate.get("required") is not True:
            raise ValueError("every extension hardening gate must be required")
        gate_id = gate.get("id")
        if not isinstance(gate_id, str) or not gate_id or gate_id in seen:
            raise ValueError("extension hardening gate ids must be unique non-empty strings")
        seen.add(gate_id)
        patterns = gate.get("python_patterns")
        checks = gate.get("runner_checks")
        if not isinstance(patterns, list) or not isinstance(checks, list) or (not patterns and not checks):
            raise ValueError(f"gate {gate_id} requires python patterns and/or runner checks")
        for pattern in patterns:
            if not isinstance(pattern, str) or "/" in pattern or "\\" in pattern:
                raise ValueError(f"unsafe Python test pattern in gate {gate_id}")
            paths = {path for path in (ROOT / "tests").glob(pattern) if path.is_file()}
            if not paths:
                raise ValueError(f"gate {gate_id} pattern {pattern!r} matches no tests")
            matched_tests.update(paths)
        for check in checks:
            if check not in ALLOWED_RUNNER_CHECKS:
                raise ValueError(f"gate {gate_id} contains unknown runner check: {check}")
            runner_checks.add(check)
    if seen != EXPECTED_GATE_IDS:
        raise ValueError(f"extension hardening gate inventory mismatch: {sorted(seen)}")
    if runner_checks != ALLOWED_RUNNER_CHECKS:
        raise ValueError("extension hardening runner-check inventory mismatch")
    if candidate.get("extension_baseline_head") != matrix.get("extension_baseline_head"):
        raise ValueError("candidate/matrix extension baseline disagreement")
    return f"matrix valid; gates={len(gates)}; matched_extension_tests={len(matched_tests)}; total_python_tests={actual_test_count}"


def _stable_tag_binding() -> str:
    actual = _git("rev-parse", f"{EXPECTED_STABLE_TAG}^{{commit}}")
    if actual != EXPECTED_STABLE_COMMIT:
        raise ValueError(f"{EXPECTED_STABLE_TAG} resolves to {actual}, expected {EXPECTED_STABLE_COMMIT}")
    return f"{EXPECTED_STABLE_TAG} -> {actual}"


def _extension_merge_chain() -> str:
    head = _git("rev-parse", "HEAD")
    previous: str | None = None
    for pr_number, commit in EXPECTED_EXTENSION_CHAIN:
        _git("cat-file", "-e", f"{commit}^{{commit}}")
        if not _git_is_ancestor(commit, head):
            raise ValueError(f"merged PR #{pr_number} commit {commit} is not an ancestor of candidate HEAD")
        if previous is not None and not _git_is_ancestor(previous, commit):
            raise ValueError(f"extension merge chain is not monotonic at PR #{pr_number}")
        previous = commit
    if previous != EXPECTED_EXTENSION_BASELINE:
        raise ValueError("extension baseline is not the final merge in the pinned chain")
    return " -> ".join(f"PR#{pr}:{commit[:12]}" for pr, commit in EXPECTED_EXTENSION_CHAIN)


def _parse_identity_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"malformed publication identity line: {line!r}")
        key, value = line.split("=", 1)
        if key in result:
            raise ValueError(f"duplicate publication identity key: {key}")
        result[key] = value
    return result


def _frozen_2_0_release_metadata() -> str:
    candidate = _strict_json(ROOT / "release" / "release_candidate.json")
    matrix = _strict_json(ROOT / "release" / "hardening_matrix.json")
    if candidate.get("target_version") != "2.0.0" or candidate.get("target_tag") != EXPECTED_STABLE_TAG:
        raise ValueError("historical 2.0 candidate metadata was repurposed by the extension line")
    if candidate.get("candidate_pr") != 52:
        raise ValueError("historical 2.0 candidate PR identity changed")
    if matrix.get("target_version") != "2.0.0" or matrix.get("milestone") != "PR #52":
        raise ValueError("historical 2.0 hardening matrix identity changed")

    identity = _parse_identity_env(PUBLICATION_IDENTITY_PATH)
    required_identity = {
        "NEXUS_STABLE_TAG": EXPECTED_STABLE_TAG,
        "NEXUS_STABLE_COMMIT": EXPECTED_STABLE_COMMIT,
        "ZENODO_DOI": EXPECTED_PUBLICATION_DOI,
    }
    for key, expected in required_identity.items():
        if identity.get(key) != expected:
            raise ValueError(f"frozen publication identity mismatch for {key}: {identity.get(key)!r}")
    return (
        "historical 2.0 candidate/matrix and publication identity remain frozen; "
        f"formalization_pr={EXPECTED_FORMALIZATION_PR}; publication_pr={EXPECTED_PUBLICATION_PR}; "
        f"doi={EXPECTED_PUBLICATION_DOI}"
    )


def _contract_bundle() -> str:
    for relative, schema in EXPECTED_CONTRACT_SCHEMAS.items():
        value = _strict_json(ROOT / relative)
        if not isinstance(value, dict) or value.get("schema") != schema:
            raise ValueError(f"contract schema mismatch: {relative}")
        if value.get("authority_effect") != "none":
            raise ValueError(f"contract attempts authority escalation: {relative}")

    instruments = _strict_json(ROOT / "contracts" / "instrument-admission.json")
    if instruments.get("admission") != "default_deny":
        raise ValueError("instrument admission is no longer default-deny")
    if instruments.get("candidates_not_admitted") != [
        "qsol.qec-receipt-replay/1",
        "qsol.spectral-analysis/1",
        "qsol.sonification/1",
        "nexus.symbolic-numeric/1",
    ]:
        raise ValueError("instrument candidate admission drifted during extension hardening")

    persistent = _strict_json(ROOT / "contracts" / "persistent-world.json")
    foundation = persistent.get("storage_foundation")
    if not isinstance(foundation, dict) or foundation.get("no_second_database") is not True:
        raise ValueError("persistent-world contract no longer preserves one canonical storage foundation")

    alpha9 = _strict_json(ROOT / "contracts" / "alpha9-remote-operator.json")
    credential = alpha9.get("credential_boundary")
    if not isinstance(credential, dict) or credential.get("raw_credentials_in_tui") != "reject":
        raise ValueError("alpha9 credential boundary drifted")
    live = alpha9.get("live_acceptance")
    if not isinstance(live, dict) or live.get("real_network_default") != "disabled":
        raise ValueError("alpha9 live network default must remain disabled")

    alpha11 = _strict_json(ROOT / "contracts" / "three-minds-one-world.json")
    canonical = alpha11.get("canonical_implementation")
    if not isinstance(canonical, dict) or canonical.get("parallel_reimplementation") is not False:
        raise ValueError("alpha11 canonical implementation boundary drifted")

    lattice_source = (ROOT / "src" / "nexus_runtime" / "world_lattice.py").read_text(encoding="utf-8")
    if 'WORLD_LATTICE_POLICY_ID = "nexus-world-lattice/1"' not in lattice_source:
        raise ValueError("world LATTICE policy identity drifted")
    if '"authority_effect": "none"' not in lattice_source:
        raise ValueError("world LATTICE zero-authority marker is missing")
    return "post-stable contract bundle preserves default-deny, quarantine, credential, LATTICE, and alpha11 boundaries"


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path = path.expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"report output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
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


def run_hardening(expect_commit: str | None) -> dict[str, Any]:
    matrix = _strict_json(MATRIX_PATH)
    candidate = _strict_json(CANDIDATE_PATH)
    initial_commit = _git("rev-parse", "HEAD")
    initial_tree = _git("rev-parse", "HEAD^{tree}")
    checks: list[CheckResult] = []

    checks.append(_internal("candidate-tree-clean", _candidate_tree_clean))
    checks.append(_internal("candidate-commit-binding", lambda: _candidate_commit_binding(expect_commit)))
    checks.append(_internal("candidate-contract", lambda: _audit_candidate(candidate)))
    checks.append(_internal("matrix-audit", lambda: _audit_matrix(matrix, candidate)))
    checks.append(_internal("stable-tag-binding", _stable_tag_binding))
    checks.append(_internal("extension-merge-chain", _extension_merge_chain))
    checks.append(_internal("frozen-2.0-release-metadata", _frozen_2_0_release_metadata))
    checks.append(_internal("contract-bundle", _contract_bundle))

    python_env = {"PYTHONPATH": "src"}
    patterns: list[str] = []
    for gate in matrix["gates"]:
        for pattern in gate["python_patterns"]:
            if pattern not in patterns:
                patterns.append(pattern)
    for pattern in patterns:
        checks.append(
            _run(
                f"python:{pattern}",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"],
                env=python_env,
            )
        )

    checks.append(
        _run(
            "alpha9-self-test",
            [sys.executable, "tools/live_xai_acceptance.py", "--self-test"],
            env=python_env,
        )
    )
    checks.append(
        _run(
            "rust-remote-operator",
            [
                "cargo",
                "test",
                "--locked",
                "--manifest-path",
                "tui/Cargo.toml",
                "--bin",
                "nexus-remote-setup",
            ],
            timeout=1200,
        )
    )
    checks.append(
        _run(
            "rust-format",
            ["cargo", "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"],
            timeout=300,
        )
    )

    checks.append(_internal("candidate-tree-unchanged", _candidate_tree_unchanged))
    checks.append(
        _internal(
            "candidate-identity-unchanged",
            lambda: _candidate_identity_unchanged(initial_commit, initial_tree, expect_commit),
        )
    )

    passed = all(check.passed for check in checks)
    report = {
        "schema": REPORT_SCHEMA,
        "phase": EXPECTED_PHASE,
        "profile": EXPECTED_PROFILE,
        "target_version": EXPECTED_TARGET_VERSION,
        "current_runtime_version": EXPECTED_CURRENT_VERSION,
        "git_commit": initial_commit,
        "git_tree": initial_tree,
        "stable_baseline": candidate["stable_baseline"],
        "extension_baseline_head": candidate["extension_baseline_head"],
        "extension_merge_chain": candidate["extension_merge_chain"],
        "checks": [asdict(check) for check in checks],
        "failed_required_checks": [check.name for check in checks if not check.passed],
        "complete": passed,
        "passed": passed,
        "status": "passed" if passed else "failed",
        "version_bump_authorized": False,
        "release_authority": False,
        "stable_release": False,
        "live_xai_acceptance_closed": False,
        "next_phase_if_green": candidate["next_phase_if_green"],
        "boundaries": candidate["boundaries"],
        "authority_effect": "none",
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-commit", help="require checked-out HEAD to equal this exact commit")
    parser.add_argument("--json-out", type=Path, help="write the canonical report to a new owner-only JSON file")
    parser.add_argument("--self-test", action="store_true", help="run only static candidate/matrix/identity audits")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            candidate = _strict_json(CANDIDATE_PATH)
            matrix = _strict_json(MATRIX_PATH)
            _candidate_tree_clean()
            _candidate_commit_binding(args.expect_commit)
            _audit_candidate(candidate)
            _audit_matrix(matrix, candidate)
            _stable_tag_binding()
            _extension_merge_chain()
            _frozen_2_0_release_metadata()
            _contract_bundle()
            print("NEXUS post-stable extension hardening self-test: ok")
            return 0

        report = run_hardening(args.expect_commit)
        if args.json_out is not None:
            _write_report(args.json_out, report)
        print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    except (FileExistsError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"NEXUS EXTENSION HARDENING ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
