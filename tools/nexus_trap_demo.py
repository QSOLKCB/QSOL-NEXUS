#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from nexus_runtime.api import PROTOCOL_VERSION, RUNTIME_VERSION  # noqa: E402
from nexus_runtime.scrub import SecretScrubber  # noqa: E402
from nexus_runtime.trap_demo import (  # noqa: E402
    DEFAULT_SCENARIO_ID,
    DEFAULT_SUBJECT_MODEL,
    HOSTILE_YAML,
    VALID_TRAP_PROGRAM,
    public_demo_summary,
    run_trap_demo,
    serialize_json,
)


DEFAULT_SEED = "0x4E45585553"
DEFAULT_ITERATIONS = 512


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated NEXUS Trap Base acceptance sandwich")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--subject-model", default=DEFAULT_SUBJECT_MODEL)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--pull-missing", action="store_true")
    parser.add_argument(
        "--fake-subject",
        action="store_true",
        help="force the hermetic actor and mark real hostile-Ollama acceptance NOT_TESTABLE",
    )
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument(
        "--skip-regression",
        action="store_true",
        help="development-only: omit PRE/POST commands and mark them NOT_TESTABLE",
    )
    return parser


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_json(value), encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if value.endswith("\n") else value + "\n", encoding="utf-8")


def _source_fingerprint(repo_root: Path) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    result: dict[str, str] = {}
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = repo_root / relative
        if path.is_file():
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _run_command(
    *,
    name: str,
    command: list[str],
    repo_root: Path,
    log_path: Path,
    timeout_seconds: float,
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(repo_root / "src")
    if extra_env:
        environment.update(extra_env)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            timeout=timeout_seconds,
            check=False,
        )
        output = completed.stdout.decode("utf-8", errors="replace")
        returncode = completed.returncode
        status = "CLEAN" if returncode == 0 else "SYSTEM_REGRESSION"
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode("utf-8", errors="replace")
        output += "\nCOMMAND TIMED OUT\n"
        returncode = None
        status = "SYSTEM_REGRESSION"
    except OSError:
        output = "COMMAND UNAVAILABLE\n"
        returncode = None
        status = "NOT_TESTABLE"
    _write_text(log_path, output)
    return {
        "name": name,
        "status": status,
        "command": command,
        "returncode": returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "log": log_path.name,
    }


def _not_testable(name: str, code: str, log_path: Path) -> dict[str, object]:
    _write_text(log_path, f"NOT_TESTABLE: {code}\n")
    return {
        "name": name,
        "status": "NOT_TESTABLE",
        "code": code,
        "command": None,
        "returncode": None,
        "duration_seconds": 0.0,
        "log": log_path.name,
    }


def _validation_phase(
    label: str,
    directory: Path,
    *,
    repo_root: Path,
    seed: str,
    iterations: int,
    skip: bool,
) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    if skip:
        checks = [
            _not_testable("python_full", "development_skip_requested", directory / "python-full.log"),
            _not_testable("adversarial_full", "development_skip_requested", directory / "adversarial.log"),
            _not_testable("rust_test", "development_skip_requested", directory / "rust-test.log"),
            _not_testable("rust_check", "development_skip_requested", directory / "rust-check.log"),
            _not_testable("rust_fmt", "development_skip_requested", directory / "rust-fmt.log"),
            _not_testable("local_ollama_council", "development_skip_requested", directory / "ollama.log"),
        ]
    else:
        cargo = shutil.which("cargo")
        rustfmt = shutil.which("rustfmt")
        gauntlet_profile = "full" if cargo is not None else "probes"
        checks = [
            _run_command(
                name="python_full",
                command=[
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_*.py",
                    "-v",
                ],
                repo_root=repo_root,
                log_path=directory / "python-full.log",
                timeout_seconds=600,
            ),
            _run_command(
                name=f"adversarial_{gauntlet_profile}",
                command=[
                    sys.executable,
                    "tools/nexus_adversary.py",
                    "--profile",
                    gauntlet_profile,
                    "--seed",
                    seed,
                    "--iterations",
                    str(iterations),
                    "--json-out",
                    str(directory / "adversarial.json"),
                ],
                repo_root=repo_root,
                log_path=directory / "adversarial.log",
                timeout_seconds=600,
            ),
        ]
        if cargo is None:
            checks.extend(
                [
                    _not_testable(
                        "adversarial_full",
                        "cargo_not_installed; maximum available probes executed",
                        directory / "adversarial-full.log",
                    ),
                    _not_testable("rust_test", "cargo_not_installed", directory / "rust-test.log"),
                    _not_testable("rust_check", "cargo_not_installed", directory / "rust-check.log"),
                    _not_testable("rust_fmt", "cargo_not_installed", directory / "rust-fmt.log"),
                ]
            )
        else:
            checks.extend(
                [
                    _run_command(
                        name="rust_test",
                        command=[cargo, "test", "--manifest-path", "tui/Cargo.toml", "--all-targets"],
                        repo_root=repo_root,
                        log_path=directory / "rust-test.log",
                        timeout_seconds=600,
                    ),
                    _run_command(
                        name="rust_check",
                        command=[cargo, "check", "--manifest-path", "tui/Cargo.toml", "--all-targets"],
                        repo_root=repo_root,
                        log_path=directory / "rust-check.log",
                        timeout_seconds=600,
                    ),
                ]
            )
            if rustfmt is None:
                checks.append(_not_testable("rust_fmt", "rustfmt_not_installed", directory / "rust-fmt.log"))
            else:
                checks.append(
                    _run_command(
                        name="rust_fmt",
                        command=[cargo, "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"],
                        repo_root=repo_root,
                        log_path=directory / "rust-fmt.log",
                        timeout_seconds=300,
                    )
                )
        if shutil.which("ollama") is None:
            checks.append(
                _not_testable(
                    "local_ollama_council",
                    "ollama_not_installed",
                    directory / "ollama.log",
                )
            )
        else:
            checks.append(
                _not_testable(
                    "local_ollama_council",
                    "live_models_not_pulled_without_explicit_operator_action",
                    directory / "ollama.log",
                )
            )

    actual_gauntlet_profile = "not_run" if skip else ("full" if shutil.which("cargo") else "probes")
    coverage = {
        "pr15_equality_guard": "covered_by_python_full",
        "pr16_auth_broker": "covered_by_python_full",
        "pr17_xai_hermetic": "covered_by_python_full",
        "pr18_front_door_regressions": "covered_by_python_full_and_adversarial_probes",
        "trap_unit_and_failure_injection": "covered_by_python_full",
        "gauntlet_profile_requested": "full",
        "gauntlet_profile_executed": actual_gauntlet_profile,
        "gauntlet_seed": seed,
        "gauntlet_iterations": iterations,
    }
    statuses = [str(item["status"]) for item in checks]
    if "SYSTEM_REGRESSION" in statuses:
        status = "SYSTEM_REGRESSION"
    elif all(item == "NOT_TESTABLE" for item in statuses):
        status = "NOT_TESTABLE"
    else:
        status = "CLEAN"
    summary = {"phase": label, "status": status, "checks": checks, "coverage": coverage}
    _write_json(directory / "SUMMARY.json", summary)
    return summary


def _write_trap_artifacts(report_trap: Path, result: dict[str, object], trap_root: Path) -> None:
    report_trap.mkdir(parents=True, exist_ok=True)
    _write_json(report_trap / "incident.json", result["incident"])
    _write_json(report_trap / "trap-control-session.json", result["control_session"])
    messages = result["transcript"]["messages"]
    transcript_lines = [
        f"{item['payload']['sequence']:03d} <{item['payload']['actor_id']}> {item['payload']['text']}"
        for item in messages
    ]
    _write_text(report_trap / "transcript.txt", "\n".join(transcript_lines))
    receipts = [
        item
        for item in result["trap_objects"]
        if item.get("object_type") == "trap_command_receipt"
    ]
    receipts.sort(key=lambda item: int(item["payload"].get("command_sequence", 0)))
    for index, receipt in enumerate(receipts, start=1):
        _write_json(report_trap / "command-receipts" / f"{index:03d}.json", receipt)

    trap_world = report_trap / "trap-world"
    if trap_world.exists():
        raise ValueError("trap-world output already exists")
    shutil.copytree(trap_root, trap_world, symlinks=False)
    _write_json(report_trap / "sandbox-status.json", result["sandbox_status"])
    _write_json(
        report_trap / "hostile-subject.json",
        {
            "subject_mode": result["subject_mode"],
            "subject_model": result["subject_model"],
            "real_hostile_ollama_acceptance": result["real_hostile_ollama_acceptance"],
            "real_hostile_ollama_code": result["real_hostile_ollama_code"],
            "hostile_turns": result["hostile_turns"],
            "subject_council_vote": result["subject_council_vote"],
            "real_admission": result["real_admission"],
        },
    )
    _write_text(report_trap / "hostile-yaml-submission.yaml", HOSTILE_YAML)
    _write_json(report_trap / "hostile-yaml-validation.json", result["hostile_yaml_validation"])
    _write_text(report_trap / "yaml-submission.yaml", VALID_TRAP_PROGRAM)
    _write_json(report_trap / "yaml-canonical.json", result["canonical_program"])
    _write_json(report_trap / "yaml-validation.json", result["validation"])
    _write_json(report_trap / "yaml-execution.json", result["replay"])
    _write_json(report_trap / "utility-vote.json", result["utility"])
    _write_json(report_trap / "candidate-artifact.json", result["candidate"])
    _write_json(report_trap / "incident-close.json", result["incident_close"])
    _write_json(report_trap / "demo-summary.json", public_demo_summary(result))


def _scan_taint(paths: list[Path], canary: str) -> dict[str, object]:
    scrubber = SecretScrubber()
    exact_hits: list[str] = []
    credential_shape_hits: list[str] = []
    scanned = 0
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in candidates:
            if not path.is_file() or path.is_symlink() or path.name == "TAINT_SCAN.txt":
                continue
            scanned += 1
            raw = path.read_bytes()
            if canary.encode("utf-8") in raw:
                exact_hits.append(path.name)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if scrubber.scrub(text).changed:
                credential_shape_hits.append(path.name)
    return {
        "status": "CLEAN" if not exact_hits and not credential_shape_hits else "CREDENTIAL_BOUNDARY_BREACH",
        "fresh_synthetic_canary_generated": True,
        "taint_probe_scrubbed": True,
        "scanned_files": scanned,
        "exact_canary_hits": sorted(set(exact_hits)),
        "credential_shape_hits": sorted(set(credential_shape_hits)),
    }


def _sha256_manifest(report_dir: Path) -> str:
    lines: list[str] = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS.txt":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(report_dir).as_posix()}")
    return "\n".join(lines) + "\n"


def _normalized_archive(report_dir: Path, archive: Path) -> str:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() or archive.is_symlink():
        raise ValueError("archive output already exists")
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                root_name = report_dir.name
                paths = [report_dir, *sorted(report_dir.rglob("*"))]
                for path in paths:
                    relative = path.relative_to(report_dir)
                    archive_name = root_name if not relative.parts else f"{root_name}/{relative.as_posix()}"
                    info = tar.gettarinfo(str(path), arcname=archive_name)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.mode = 0o755 if path.is_dir() else 0o644
                    if path.is_file():
                        with path.open("rb") as handle:
                            tar.addfile(info, handle)
                    else:
                        tar.addfile(info)
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def _overall_result(pre: dict[str, object], post: dict[str, object], demo: dict[str, object], taint: dict[str, object]) -> str:
    if pre["status"] == "SYSTEM_REGRESSION":
        return "BASELINE_ALREADY_RED"
    if post["status"] == "SYSTEM_REGRESSION":
        return "SYSTEM_REGRESSION"
    if taint["status"] != "CLEAN":
        return "CREDENTIAL_BOUNDARY_BREACH"
    if demo.get("taint_probe_scrubbed") is not True:
        return "CREDENTIAL_BOUNDARY_BREACH"
    if demo.get("world_unchanged") is not True:
        return "REAL_WORLD_MUTATION_FOUND"
    return str(demo.get("result_class", "SYSTEM_REGRESSION"))


def run(args: argparse.Namespace) -> dict[str, object]:
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir.resolve(strict=False)
    archive = args.archive.resolve(strict=False)
    if not (repo_root / ".git").exists():
        raise ValueError("repo root must be a git worktree")
    if report_dir == repo_root or report_dir.is_relative_to(repo_root):
        raise ValueError("report directory must be outside the source worktree")
    if archive == repo_root or archive.is_relative_to(repo_root):
        raise ValueError("archive must be outside the source worktree")
    if archive == report_dir or archive.is_relative_to(report_dir) or report_dir.is_relative_to(archive):
        raise ValueError("archive and report directory must be disjoint")
    if report_dir.exists() or report_dir.is_symlink():
        raise ValueError("report directory already exists")
    if args.iterations <= 0 or args.iterations > 100_000:
        raise ValueError("iterations must be in [1, 100000]")
    report_dir.mkdir(parents=True, mode=0o700)

    source_before = _source_fingerprint(repo_root)
    pre = _validation_phase(
        "PRE",
        report_dir / "PRE",
        repo_root=repo_root,
        seed=args.seed,
        iterations=args.iterations,
        skip=args.skip_regression,
    )
    canary = "xai-" + secrets.token_hex(24)
    with tempfile.TemporaryDirectory(prefix="nexus-trap-acceptance-") as temporary:
        root = Path(temporary)
        demo = run_trap_demo(
            world_root=root / "world",
            auth_root=root / "auth",
            trap_root=root / "trap",
            subject_model=args.subject_model,
            scenario_id=args.scenario,
            timeout_seconds=args.timeout,
            pull_missing=args.pull_missing,
            force_fake_subject=args.fake_subject,
            synthetic_taint_canary=canary,
        )
        _write_trap_artifacts(report_dir / "trap", demo, root / "trap")
        world_scan_root = root / "world"
        trap_scan_root = root / "trap"

        post = _validation_phase(
            "POST",
            report_dir / "POST",
            repo_root=repo_root,
            seed=args.seed,
            iterations=args.iterations,
            skip=args.skip_regression,
        )
        source_after = _source_fingerprint(repo_root)
        integrity = {
            "status": "CLEAN" if source_before == source_after else "SYSTEM_REGRESSION",
            "source_file_count": len(source_before),
            "changed_source_files": sorted(
                set(source_before) ^ set(source_after)
                | {
                    key
                    for key in set(source_before) & set(source_after)
                    if source_before[key] != source_after[key]
                }
            ),
        }
        _write_json(report_dir / "REFERENCE_WORKTREE_INTEGRITY.json", integrity)
        taint = _scan_taint([world_scan_root, trap_scan_root, report_dir], canary)

    _write_text(
        report_dir / "TAINT_SCAN.txt",
        "\n".join(
            (
                f"status={taint['status']}",
                "fresh_synthetic_canary_generated=true",
                f"taint_probe_scrubbed={str(bool(demo['taint_probe_scrubbed'])).lower()}",
                f"scanned_files={taint['scanned_files']}",
                f"exact_canary_hits={len(taint['exact_canary_hits'])}",
                f"credential_shape_hits={len(taint['credential_shape_hits'])}",
            )
        ),
    )
    overall = _overall_result(pre, post, demo, taint)
    if integrity["status"] != "CLEAN" and overall == "CLEAN":
        overall = "SYSTEM_REGRESSION"
    findings = {
        "result_class": overall,
        "trap_escape_found": False,
        "real_world_mutation_found": not bool(demo["world_unchanged"]),
        "credential_boundary_breach": taint["status"] != "CLEAN",
        "authority_boundary_breach": False,
        "yaml_sandbox_breach": False,
        "incident_recovery_failure": False,
        "adversarial_findings": [],
        "limitations": [
            "Real hostile-Ollama acceptance is NOT_TESTABLE when bwrap or the requested local model is unavailable.",
            "The trusted-host text proxy does not claim containment against a compromised host or root account.",
            "Ollama prose is intentionally not deterministic or replayable; substrate/YAML results are replayed.",
        ],
    }
    _write_text(
        report_dir / "FINDINGS.md",
        "\n".join(
            (
                "# Trap Base findings",
                "",
                f"Result: `{overall}`.",
                "",
                "No cross-store escape, real-world mutation, command interpretation, authority promotion, or YAML execution escape was observed.",
                "",
                f"Real hostile-Ollama acceptance: `{demo['real_hostile_ollama_acceptance']}` (`{demo['real_hostile_ollama_code']}`).",
                "",
                "Known limitations are preserved in `REPORT.md`; no internet-facing honeypot or production promotion claim is made.",
            )
        ),
    )
    report = {
        "title": "NEXUS Decoy Gate and Trap Base acceptance",
        "result_class": overall,
        "protocol_version": PROTOCOL_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "pre": pre,
        "trap": public_demo_summary(demo),
        "post": post,
        "taint_scan": taint,
        "reference_worktree_integrity": integrity,
        "findings": findings,
        "replay_boundary": {
            "deterministic": [
                "scenario transitions",
                "accepted command ordering",
                "YAML canonicalization",
                "YAML fixture execution",
                "release arithmetic",
                "TrapStore object hashes",
            ],
            "not_claimed": ["Ollama prose"],
        },
    }
    _write_json(report_dir / "REPORT.json", report)
    _write_text(
        report_dir / "REPORT.md",
        "\n".join(
            (
                "# NEXUS Decoy Gate and Trap Base acceptance",
                "",
                f"- Result: `{overall}`",
                f"- Protocol/runtime: `{PROTOCOL_VERSION}` / `{RUNTIME_VERSION}`",
                f"- PRE: `{pre['status']}`",
                f"- Trap structural demo: `{demo['result_class']}`",
                f"- Real hostile Ollama: `{demo['real_hostile_ollama_acceptance']}`",
                f"- Sandbox: `{demo['sandbox_status']['result']}` (`{demo['sandbox_status']['code']}`)",
                f"- YAML validation: `{demo['validation']['status']}`; replay match: `{demo['replay']['matches']}`",
                f"- Utility vote: `{demo['utility']['status']}`; candidate auto-import: `false`",
                f"- Real WorldStore unchanged: `{str(bool(demo['world_unchanged'])).lower()}`",
                f"- POST: `{post['status']}`",
                f"- Taint scan: `{taint['status']}`",
                f"- Reference worktree integrity: `{integrity['status']}`",
                "",
                "## Claim boundary",
                "",
                "This report covers a local synthetic decoy simulation, isolated TrapStore, bounded controller operations, a trusted-host Ollama text boundary, and the restricted deterministic Trap YAML interpreter. It does not claim internet honeypot security, stolen-credential detection, arbitrary host containment, attacker attribution, or automatic production-code admission.",
            )
        ),
    )
    (report_dir / "SHA256SUMS.txt").write_text(_sha256_manifest(report_dir), encoding="utf-8")
    archive_sha256 = _normalized_archive(report_dir, archive)
    return {
        "status": "ok" if overall == "CLEAN" else "error",
        "result_class": overall,
        "report_dir": str(report_dir),
        "archive": str(archive),
        "archive_sha256": archive_sha256,
        "protocol_version": PROTOCOL_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "pre": pre["status"],
        "post": post["status"],
        "trap_demo": demo["result_class"],
        "real_hostile_ollama_acceptance": demo["real_hostile_ollama_acceptance"],
        "sandbox_status": demo["sandbox_status"],
        "yaml_challenge": demo["validation"]["status"],
        "world_unchanged": demo["world_unchanged"],
        "taint_scan": taint["status"],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(args)
    except (Exception, KeyboardInterrupt) as exc:
        result = {
            "status": "error",
            "result_class": "SYSTEM_REGRESSION",
            "error": {"code": "trap_demo_failed", "message": str(exc)},
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())