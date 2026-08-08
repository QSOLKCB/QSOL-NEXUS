#!/usr/bin/env python3
"""NEXUS adversarial gauntlet runner.

This is test infrastructure, not a runtime authority layer. It gives build agents
and human reviewers one deterministic command for attacking NEXUS invariants in
an isolated temporary WorldStore.

Profiles:
  probes  built-in invariant attacks + JSONL corpus
  quick   probes + complete Python regression suite
  full    quick + Rust tests/check/fmt
  live    full + existing real loopback-Ollama integration test

The runner intentionally has no dependency outside the Python standard library
and the NEXUS source tree.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime.api import NexusAPI  # noqa: E402
from nexus_runtime.failsafe import RELIEF_MODEL_ID  # noqa: E402

REPORT_SCHEMA = "nexus-adversarial-gauntlet/1"
DEFAULT_SEED = 0x4E45585553  # ASCII-ish "NEXUS"
OUTPUT_LIMIT = 24_000


@dataclass
class CheckResult:
    name: str
    kind: str
    status: str
    duration_seconds: float
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _tail(text: str, limit: int = OUTPUT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"[... {len(text) - limit} chars truncated ...]\n{text[-limit:]}"


def _run_check(name: str, kind: str, fn: Callable[[], str | None]) -> CheckResult:
    started = time.monotonic()
    try:
        detail = fn() or ""
    except Exception as exc:  # test harness should turn an exploit/crash into a report row
        detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        return CheckResult(name, kind, "fail", time.monotonic() - started, _tail(detail))
    return CheckResult(name, kind, "pass", time.monotonic() - started, _tail(detail))


def _run_command(
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
        return CheckResult(name, "command", "fail", time.monotonic() - started, str(exc))
    status = "pass" if proc.returncode == 0 else "fail"
    detail = f"$ {' '.join(command)}\nexit={proc.returncode}\n{proc.stdout}"
    return CheckResult(name, "command", status, time.monotonic() - started, _tail(detail))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _mock_members() -> list[dict[str, Any]]:
    return [
        {"member_id": "Alpha", "model_id": "mock-alpha", "adapter_id": "mock"},
        {"member_id": "Beta", "model_id": "mock-beta", "adapter_id": "mock"},
        {"member_id": "Gamma", "model_id": "mock-gamma", "adapter_id": "mock"},
    ]


def _builtin_probes(seed: int, iterations: int) -> Iterable[CheckResult]:

    def health_boundary() -> str:
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-health-") as tmp:
            api = NexusAPI(tmp)
            response = api.handle({"operation": "system.health"})
            _require(response.get("status") == "ok", "health did not return ok")
            _require(response.get("control_transport") == "jsonl_stdio", "control transport changed")
            _require(response.get("remote_provider_auth") is False, "remote provider auth unexpectedly enabled")
            _require(
                response.get("network") == "none_unless_explicit_loopback_ollama_actor",
                "network boundary changed",
            )
            failsafe = response.get("failsafe", {})
            boundary = failsafe.get("claim_boundary", {}) if isinstance(failsafe, dict) else {}
            _require(boundary.get("truth_metric") is False, "Failsafe became a truth metric")
            _require(boundary.get("provider_status_is_violation") is False, "provider status became a violation")
            return "local stdio/network/provider/Failsafe claim boundary intact"

    yield _run_check("health-boundary", "invariant", health_boundary)

    def canonical_world_identity() -> str:
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-world-") as tmp:
            api = NexusAPI(tmp)
            request = {
                "operation": "world.create",
                "object_type": "gauntlet_note",
                "payload": {"value": [1, 2, 3], "nested": {"stable": True}},
                "provenance": {"actor": "gauntlet"},
            }
            first = api.handle(request)
            second = api.handle(request)
            _require(first.get("status") == "ok" and second.get("status") == "ok", "world.create failed")
            first_ref = first["object"]["object_id"]
            second_ref = second["object"]["object_id"]
            _require(first_ref == second_ref, "same canonical object produced different identities")
            return first_ref

    yield _run_check("canonical-world-identity", "invariant", canonical_world_identity)

    def secret_canary() -> str:
        canary = "ghp_" + "G" * 32
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-secret-") as tmp:
            api = NexusAPI(tmp)
            created = api.handle(
                {
                    "operation": "world.create",
                    "object_type": "gauntlet_secret_probe",
                    "payload": {"nested": {"text": f"credential={canary}"}},
                    "provenance": {"actor": "gauntlet", "note": f"token {canary}"},
                }
            )
            _require(created.get("status") == "ok", "secret probe object was not accepted/scrubbed")
            serialized = json.dumps(created, sort_keys=True)
            _require(canary not in serialized, "raw secret leaked in world.create response")
            ref = created["object"]["object_id"]
            inspected = api.handle({"operation": "world.inspect", "object_ref": ref})
            _require(canary not in json.dumps(inspected, sort_keys=True), "raw secret persisted in world object")
            for path in Path(tmp).rglob("*"):
                if path.is_file():
                    try:
                        text = path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    _require(canary not in text, f"raw secret persisted on disk at {path.relative_to(tmp)}")
            return "secret canary absent from API response, inspected object, and persistent world files"

    yield _run_check("secret-canary", "invariant", secret_canary)

    def equality_and_roster() -> str:
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-equality-") as tmp:
            api = NexusAPI(tmp)
            weighted = _mock_members()
            weighted[0]["vote_weight"] = 9
            rejected = api.handle({"operation": "council.run", "question": "q", "members": weighted})
            _require(rejected.get("status") == "error", "weighted Council member was accepted")

            valid = api.handle({"operation": "council.run", "question": "q", "members": _mock_members()})
            _require(valid.get("status") == "ok", "valid Council failed")
            session = api.world.inspect(valid["session_ref"])
            roster = session.payload.get("roster", [])
            _require(len(roster) == 3, "unexpected Council roster size")
            _require(all(row.get("vote_weight") == 1 for row in roster), "non-unit vote survived into session")
            _require(
                all(row.get("epistemic_privilege") == "none" for row in roster),
                "epistemic privilege survived into session",
            )
            return "weighted ingress rejected; durable Council roster remains equal"

    yield _run_check("equality-and-roster", "invariant", equality_and_roster)

    def remote_adapter_boundary() -> str:
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-remote-") as tmp:
            api = NexusAPI(tmp)
            response = api.handle(
                {
                    "operation": "actor.chat",
                    "member": {
                        "member_id": "RemoteProbe",
                        "model_id": "remote-probe",
                        "adapter_id": "ollama",
                        "endpoint": "https://example.com:11434",
                    },
                    "message": "do not connect",
                }
            )
            error = response.get("error", {})
            _require(
                response.get("status") == "error"
                and isinstance(error, dict)
                and error.get("code") == "invalid_request",
                "non-loopback Ollama endpoint was not rejected at validation",
            )
            return error.get("message", "remote endpoint rejected")

    yield _run_check("remote-adapter-boundary", "invariant", remote_adapter_boundary)

    def failsafe_identity_and_restart() -> str:
        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-failsafe-") as tmp:
            first = NexusAPI(tmp)
            first.council.failsafe.registry.transition(
                "SeatA",
                "shadow_realm",
                model_id="offender-a",
                trigger_reason="gauntlet_fixture",
                replacement_model_id=RELIEF_MODEL_ID,
            )
            same = first.handle(
                {
                    "operation": "actor.chat",
                    "member": {"member_id": "SeatA", "model_id": "offender-a", "adapter_id": "mock"},
                    "message": "hello",
                }
            )
            _require(same.get("model_id") == RELIEF_MODEL_ID, "shadowed identity escaped actor.chat")

            newcomer = first.handle(
                {
                    "operation": "actor.chat",
                    "member": {"member_id": "SeatA", "model_id": "new-model-a", "adapter_id": "mock"},
                    "message": "hello",
                }
            )
            _require(newcomer.get("model_id") == "new-model-a", "new model inherited prior model sentence")

            restarted = NexusAPI(tmp)
            restored = restarted.handle(
                {
                    "operation": "actor.chat",
                    "member": {"member_id": "SeatA", "model_id": "offender-a", "adapter_id": "mock"},
                    "message": "hello after restart",
                }
            )
            _require(restored.get("model_id") == RELIEF_MODEL_ID, "restart erased Shadow Realm containment")
            return "same offender replaced, newcomer free, offender still replaced after restart"

    yield _run_check("failsafe-identity-restart", "invariant", failsafe_identity_and_restart)

    def malformed_request_fuzz() -> str:
        rng = random.Random(seed)
        operations = [
            "system.health",
            "system.operations",
            "security.scrub_preview",
            "world.create",
            "world.inspect",
            "world.modes",
            "world.geometry",
            "world.geometry.distance",
            "receipt.verify",
            "telemetry.verify",
            "failsafe.status",
            "game.un.catalog",
            "game.un.new",
            "game.un.inspect",
            "game.un.act",
            "game.un.turn",
            "game.mud.catalog",
            "game.mud.new",
            "game.mud.inspect",
            "game.mud.act",
            "actor.chat",
            "council.run",
            "definitely.not.an.operation",
        ]
        field_names = [
            "text",
            "object_type",
            "payload",
            "provenance",
            "object_ref",
            "receipt_ref",
            "session_ref",
            "member_id",
            "mode",
            "members",
            "member",
            "message",
            "evidence_refs",
            "game_ref",
            "mud_ref",
            "player_id",
            "action",
            "args",
            "seed",
        ]

        def random_value(depth: int = 0) -> Any:
            primitive: list[Any] = [None, True, False, -1, 0, 1, 1.5, "", "x", "object:" + "0" * 64]
            if depth >= 2:
                return rng.choice(primitive)
            choice = rng.randrange(5)
            if choice < 3:
                return rng.choice(primitive)
            if choice == 3:
                return [random_value(depth + 1) for _ in range(rng.randrange(0, 4))]
            return {rng.choice(field_names): random_value(depth + 1) for _ in range(rng.randrange(0, 4))}

        with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-fuzz-") as tmp:
            api = NexusAPI(tmp)
            for index in range(iterations):
                operation: Any = rng.choice(operations)
                if rng.random() < 0.12:
                    operation = random_value(2)
                request: dict[str, Any] = {"operation": operation}
                for _ in range(rng.randrange(0, 7)):
                    request[rng.choice(field_names)] = random_value()
                try:
                    response = api.handle(request)
                except Exception as exc:
                    raise AssertionError(
                        f"API escaped handle() on fuzz case {index}: {request!r} -> {type(exc).__name__}: {exc}"
                    ) from exc
                _require(isinstance(response, dict), f"fuzz case {index} returned non-object response")
                _require(response.get("status") in {"ok", "error"}, f"fuzz case {index} returned invalid status")
        return f"{iterations} deterministic malformed requests; seed={seed}"

    yield _run_check("malformed-request-fuzz", "fuzz", malformed_request_fuzz)

def _iter_corpus_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        if resolved.is_dir():
            candidates = sorted(resolved.glob("*.jsonl"))
            if not candidates:
                raise FileNotFoundError(f"corpus directory contains no .jsonl files: {resolved}")
        elif resolved.exists():
            candidates = [resolved]
        else:
            raise FileNotFoundError(f"corpus path does not exist: {resolved}")
        for candidate in candidates:
            key = candidate.resolve()
            if key not in seen:
                seen.add(key)
                files.append(candidate)
    return files


def _check_corpus_expectation(response: dict[str, Any], expect: dict[str, Any]) -> None:
    if "status" in expect:
        _require(response.get("status") == expect["status"], f"expected status={expect['status']!r}: {response!r}")
    if "error_code" in expect:
        error = response.get("error", {})
        actual = error.get("code") if isinstance(error, dict) else None
        _require(actual == expect["error_code"], f"expected error_code={expect['error_code']!r}, got {actual!r}")
    serialized = json.dumps(response, sort_keys=True, ensure_ascii=False)
    contains = expect.get("contains", [])
    _require(isinstance(contains, list), "expect.contains must be an array")
    for needle in contains:
        _require(isinstance(needle, str), "expect.contains values must be strings")
        _require(needle in serialized, f"expected response to contain {needle!r}")
    forbidden = expect.get("forbid", [])
    _require(isinstance(forbidden, list), "expect.forbid must be an array")
    for needle in forbidden:
        _require(isinstance(needle, str), "expect.forbid values must be strings")
        _require(needle not in serialized, f"forbidden response content present: {needle!r}")


def _run_corpus(files: list[Path]) -> Iterable[CheckResult]:
    for path in files:
        relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue

            fallback_name = f"corpus:{relative}:{line_number}"
            try:
                parsed = json.loads(stripped)
                case_name = parsed.get("name") if isinstance(parsed, dict) else None
                name = (
                    f"corpus:{relative}:{case_name}"
                    if isinstance(case_name, str) and case_name.strip()
                    else fallback_name
                )
            except json.JSONDecodeError:
                parsed = None
                name = fallback_name

            def execute(raw_line: str = stripped, pre_parsed: Any = parsed) -> str:
                case = pre_parsed if pre_parsed is not None else json.loads(raw_line)
                _require(isinstance(case, dict), "corpus line must be a JSON object")
                request = case.get("request")
                expect = case.get("expect", {})
                _require(isinstance(request, dict), "corpus request must be an object")
                _require(isinstance(expect, dict), "corpus expect must be an object")
                with tempfile.TemporaryDirectory(prefix="nexus-gauntlet-corpus-case-") as tmp:
                    api = NexusAPI(tmp)
                    response = api.handle(request)
                _require(isinstance(response, dict), "API returned non-object response")
                _check_corpus_expectation(response, expect)
                return json.dumps(response, sort_keys=True, ensure_ascii=False)

            yield _run_check(name, "corpus", execute)

def _commit_id() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except OSError:
        return "unknown"
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _worktree_state() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except OSError:
        return {"dirty": None, "status": "unavailable"}
    if proc.returncode != 0:
        return {"dirty": None, "status": "unavailable"}
    status = proc.stdout.rstrip("\n")
    return {"dirty": bool(status), "status": status}


def _print_progress(result: CheckResult) -> None:
    mark = "PASS" if result.passed else "FAIL"
    print(f"[{mark:4}] {result.name} ({result.duration_seconds:.3f}s)")
    if not result.passed and result.detail:
        print(result.detail, file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NEXUS adversarial gauntlet")
    parser.add_argument(
        "--profile",
        choices=("probes", "quick", "full", "live"),
        default="full",
        help="attack depth; live additionally requires a working loopback Ollama setup",
    )
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=DEFAULT_SEED)
    parser.add_argument("--iterations", type=int, default=128, help="deterministic malformed-request fuzz cases")
    parser.add_argument(
        "--corpus",
        action="append",
        default=[],
        metavar="PATH",
        help="extra JSONL corpus file or directory; may be repeated",
    )
    parser.add_argument(
        "--no-default-corpus",
        action="store_true",
        help="do not auto-load adversarial/corpus/*.jsonl",
    )
    parser.add_argument("--json-out", type=Path, help="write machine-readable report to this path")
    parser.add_argument("--stop-on-fail", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.iterations < 1 or args.iterations > 100_000:
        raise SystemExit("--iterations must be in [1, 100000]")

    started = time.time()
    results: list[CheckResult] = []

    def add(batch: Iterable[CheckResult]) -> bool:
        for result in batch:
            results.append(result)
            _print_progress(result)
            if args.stop_on_fail and not result.passed:
                return False
        return True

    proceed = add(_builtin_probes(args.seed, args.iterations))

    if proceed:
        corpus_paths = [Path(value) for value in args.corpus]
        if not args.no_default_corpus:
            corpus_paths.insert(0, Path("adversarial/corpus"))
        if corpus_paths:
            try:
                corpus_files = _iter_corpus_files(corpus_paths)
            except (OSError, ValueError) as exc:
                config_result = CheckResult(
                    "corpus-configuration",
                    "configuration",
                    "fail",
                    0.0,
                    f"{type(exc).__name__}: {exc}",
                )
                proceed = add([config_result])
            else:
                proceed = add(_run_corpus(corpus_files))

    if proceed and args.profile in {"quick", "full", "live"}:
        python_result = _run_command(
            "python-regression-suite",
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
            env={"PYTHONPATH": "src"},
        )
        proceed = add([python_result])

    if proceed and args.profile in {"full", "live"}:
        rust_commands = [
            ("rust-tests", ["cargo", "test", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
            ("rust-check", ["cargo", "check", "--manifest-path", "tui/Cargo.toml", "--all-targets"]),
            ("rustfmt-check", ["cargo", "fmt", "--manifest-path", "tui/Cargo.toml", "--", "--check"]),
        ]
        for name, command in rust_commands:
            proceed = add([_run_command(name, command)])
            if not proceed:
                break

    if proceed and args.profile == "live":
        proceed = add(
            [
                _run_command(
                    "live-loopback-ollama",
                    [
                        sys.executable,
                        "-m",
                        "unittest",
                        "discover",
                        "-s",
                        "tests",
                        "-p",
                        "test_ollama_integration.py",
                        "-v",
                    ],
                    env={"PYTHONPATH": "src", "NEXUS_OLLAMA_INTEGRATION": "1"},
                    timeout=1800,
                )
            ]
        )

    failures = [result for result in results if not result.passed]
    worktree = _worktree_state()
    report = {
        "schema_version": REPORT_SCHEMA,
        "profile": args.profile,
        "seed": args.seed,
        "iterations": args.iterations,
        "commit": _commit_id(),
        "worktree": worktree,
        "started_unix": started,
        "finished_unix": time.time(),
        "summary": {
            "checks": len(results),
            "passed": len(results) - len(failures),
            "failed": len(failures),
            "verdict": "PASS" if not failures else "FAIL",
        },
        "results": [asdict(result) for result in results],
        "interpretation": (
            "PASS means the configured attacks did not break a checked invariant; it is not a proof of security, "
            "correctness, or model alignment. The commit field identifies HEAD; worktree.dirty records whether "
            "uncommitted changes were also part of the tested state."
        ),
    }

    if args.json_out:
        output = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"report: {output}")

    print(
        f"GAUNTLET {report['summary']['verdict']}: "
        f"{report['summary']['passed']}/{report['summary']['checks']} checks passed"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
