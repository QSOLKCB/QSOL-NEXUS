#!/usr/bin/env python3
"""Run a real local-Ollama NEXUS Council on operator hardware.

This is adversarial/integration infrastructure, not a production model adapter.
It intentionally binds Ollama to a loopback-only bench port, records hardware
telemetry, persists the Council world/receipts, and optionally admits a
replayable external-agent seat from a sealed JSON manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexus_runtime.adapters.ollama import OllamaActor, OllamaTransport  # noqa: E402
from nexus_runtime.canonical import canonical_json  # noqa: E402
from nexus_runtime.council import CouncilCoordinator  # noqa: E402
from nexus_runtime.mock import DeterministicMockActor  # noqa: E402
from nexus_runtime.modes import get_mode  # noqa: E402
from nexus_runtime.types import Ballot, CouncilMember, PHASE_ORDER, Phase, PhaseContext  # noqa: E402
from nexus_runtime.world import WorldStore  # noqa: E402

BENCH_SCHEMA = "nexus-live-hardware-bench/1"
SEAT_SCHEMA = "nexus-live-agent-seat/1"
DEFAULT_ENDPOINT = "http://127.0.0.1:11435"
DEFAULT_QUESTION = (
    "Does a 431 Hz result from one sonification mapping justify claiming "
    "432 Hz is a universal tuning frequency?"
)


class BenchError(RuntimeError):
    pass


@dataclass
class CommandResult:
    command: list[str]
    returncode: int | None
    stdout: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


def _run_command(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 60) -> CommandResult:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env=merged,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(command, None, "", f"{type(exc).__name__}: {exc}")
    return CommandResult(command, proc.returncode, proc.stdout)


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _loopback_endpoint(endpoint: str) -> tuple[str, int]:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or not parsed.hostname or parsed.port is None:
        raise BenchError("bench Ollama endpoint must be an explicit http://host:port URL")
    if parsed.username is not None or parsed.password is not None:
        raise BenchError("bench Ollama endpoint must not contain userinfo")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise BenchError("bench Ollama endpoint must not contain a path, query, or fragment")
    host = parsed.hostname
    if host.lower() != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise BenchError("bench Ollama endpoint must be loopback-only")
        except ValueError as exc:
            raise BenchError("bench Ollama endpoint hostname must be localhost or a loopback IP") from exc
    return host, parsed.port


def _ollama_host_authority(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def _ollama_ready(endpoint: str, timeout: float = 1.0) -> bool:
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"{endpoint.rstrip('/')}/api/tags", timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 300
    except Exception:
        return False


def _git_state() -> dict[str, Any]:
    head = _run_command(["git", "rev-parse", "HEAD"], timeout=5)
    status = _run_command(["git", "status", "--porcelain=v1", "--untracked-files=all"], timeout=5)
    status_text = status.stdout.rstrip("\n") if status.ok else "unavailable"
    return {
        "head": head.stdout.strip() if head.ok else "unknown",
        "dirty": bool(status_text) if status_text != "unavailable" else None,
        "status": status_text,
    }


def _nvidia_snapshot() -> dict[str, Any]:
    if shutil.which("nvidia-smi") is None:
        return {"available": False, "reason": "nvidia-smi not found"}
    query = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    if not query.ok:
        return {"available": False, "reason": query.error or query.stdout.strip()}
    rows = []
    for raw in query.stdout.splitlines():
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 7:
            continue
        try:
            rows.append(
                {
                    "index": int(parts[0]),
                    "uuid": parts[1],
                    "name": parts[2],
                    "memory_total_mib": int(parts[3]),
                    "memory_used_mib": int(parts[4]),
                    "utilization_percent": int(parts[5]),
                    "temperature_c": int(parts[6]),
                }
            )
        except ValueError:
            continue
    return {"available": bool(rows), "gpus": rows, "raw": query.stdout.strip()}


def _hardware_snapshot(endpoint: str) -> dict[str, Any]:
    cargo = _run_command(["cargo", "--version"], timeout=5) if shutil.which("cargo") else None
    ollama = _run_command(["ollama", "--version"], timeout=5) if shutil.which("ollama") else None
    return {
        "platform": platform.platform(),
        "kernel": platform.release(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "cargo": cargo.stdout.strip() if cargo and cargo.ok else None,
        "ollama": ollama.stdout.strip() if ollama and ollama.ok else None,
        "ollama_endpoint": endpoint,
        "ollama_ready": _ollama_ready(endpoint),
        "nvidia": _nvidia_snapshot(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "git": _git_state(),
    }


def _ollama_gpu_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    nvidia = snapshot.get("nvidia", {})
    rows = nvidia.get("gpus", []) if isinstance(nvidia, dict) else []
    if not isinstance(rows, list) or not rows:
        return []
    visible = snapshot.get("cuda_visible_devices")
    if visible is None or not str(visible).strip():
        return list(rows)
    tokens = [token.strip() for token in str(visible).split(",") if token.strip()]
    if not tokens or tokens == ["-1"]:
        return []
    selected: list[dict[str, Any]] = []
    for token in tokens:
        match = None
        if token.isdigit():
            index = int(token)
            match = next((row for row in rows if row.get("index") == index), None)
        else:
            match = next(
                (
                    row
                    for row in rows
                    if isinstance(row.get("uuid"), str)
                    and (row["uuid"] == token or row["uuid"].startswith(token))
                ),
                None,
            )
        if match is not None and match not in selected:
            selected.append(match)
    return selected


def _ollama_gpu_memory_used(snapshot: dict[str, Any]) -> int | None:
    rows = _ollama_gpu_rows(snapshot)
    values = [row.get("memory_used_mib") for row in rows]
    if not rows or any(type(value) is not int for value in values):
        return None
    return sum(values)


def _ollama_gpu_total_vram(snapshot: dict[str, Any]) -> int | None:
    rows = _ollama_gpu_rows(snapshot)
    values = [row.get("memory_total_mib") for row in rows]
    if not rows or any(type(value) is not int for value in values):
        return None
    return sum(values)


class ControlledOllama:
    def __init__(self, endpoint: str, *, reuse: bool = False) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.reuse = reuse
        self.process: subprocess.Popen[str] | None = None
        self.log_handle: Any = None
        self.log_path: Path | None = None
        self.env = os.environ.copy()
        host, port = _loopback_endpoint(endpoint)
        self.env.update(
            {
                "OLLAMA_HOST": _ollama_host_authority(host, port),
                "OLLAMA_MAX_LOADED_MODELS": "2",
                "OLLAMA_NUM_PARALLEL": "1",
            }
        )

    def start(self, report_dir: Path) -> None:
        if shutil.which("ollama") is None:
            raise BenchError("ollama executable not found; install Ollama before running the live bench")
        if _ollama_ready(self.endpoint):
            if not self.reuse:
                raise BenchError(
                    f"{self.endpoint} already has an Ollama server; use --reuse-ollama or choose another bench port"
                )
            return

        self.log_path = report_dir / "ollama.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("w", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                cwd=ROOT,
                env=self.env,
                text=True,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            self.log_handle.close()
            self.log_handle = None
            raise BenchError(f"failed to launch ollama serve: {exc}") from exc

        for _ in range(120):
            if _ollama_ready(self.endpoint, timeout=0.5):
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.25)
        self.stop()
        tail = ""
        if self.log_path and self.log_path.exists():
            tail = self.log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise BenchError(f"controlled Ollama did not become ready at {self.endpoint}\n{tail}")

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    process.kill()
                process.wait(timeout=5)
        if self.log_handle is not None:
            self.log_handle.close()
            self.log_handle = None

    def command(self, args: list[str], *, timeout: int = 600) -> CommandResult:
        return _run_command(["ollama", *args], env={"OLLAMA_HOST": self.env["OLLAMA_HOST"]}, timeout=timeout)


def _ensure_model(service: ControlledOllama, model: str, *, pull_missing: bool) -> None:
    shown = service.command(["show", model], timeout=30)
    if shown.ok:
        return
    if not pull_missing:
        raise BenchError(f"Ollama model {model!r} is missing; rerun with --pull-missing or pull it manually")
    pulled = service.command(["pull", model], timeout=1800)
    if not pulled.ok:
        raise BenchError(f"failed to pull {model!r}: {pulled.error or pulled.stdout[-4000:]}")


def _seat_digest(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def _question_digest(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def seat_template(question: str, mode: str, member_id: str, model_id: str) -> dict[str, Any]:
    return {
        "schema_version": SEAT_SCHEMA,
        "question": question,
        "question_sha256": _question_digest(question),
        "mode": mode,
        "member_id": member_id,
        "model_id": model_id,
        "responses": {phase.value: "" for phase in PHASE_ORDER},
        "guard_restatement": "",
        "ballot": {"choice": Ballot.TEST_FURTHER.value, "rationale": ""},
    }


def load_seat_manifest(path: Path, *, question: str, mode: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SEAT_SCHEMA:
        raise BenchError("invalid external-agent seat schema")
    if data.get("question") != question or data.get("question_sha256") != _question_digest(question):
        raise BenchError("external-agent seat is bound to a different question")
    if data.get("mode") != mode:
        raise BenchError("external-agent seat is bound to a different world mode")
    for field in ("member_id", "model_id", "guard_restatement"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BenchError(f"external-agent seat {field} must be non-empty text")
    responses = data.get("responses")
    if not isinstance(responses, dict):
        raise BenchError("external-agent seat responses must be an object")
    for phase in PHASE_ORDER:
        response = responses.get(phase.value)
        if not isinstance(response, str) or not response.strip():
            raise BenchError(f"external-agent seat response {phase.value} must be non-empty text")
    ballot = data.get("ballot")
    if not isinstance(ballot, dict):
        raise BenchError("external-agent seat ballot must be an object")
    try:
        Ballot(ballot.get("choice"))
    except (TypeError, ValueError) as exc:
        raise BenchError("external-agent seat ballot.choice is invalid") from exc
    rationale = ballot.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise BenchError("external-agent seat ballot.rationale must be non-empty text")
    return data


class ManifestSeatActor:
    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest
        self.manifest_sha256 = _seat_digest(manifest)
        self.member = CouncilMember(
            manifest["member_id"],
            manifest["model_id"],
            adapter_id="sealed_agent_manifest",
        )

    @property
    def replayable(self) -> bool:
        return True

    def identity_metadata(self) -> dict[str, Any]:
        return {
            "actor_kind": "sealed_agent_manifest",
            "manifest_schema": SEAT_SCHEMA,
            "manifest_sha256": self.manifest_sha256,
        }

    def respond(self, context: PhaseContext) -> str:
        if context.guard_nudge is not None:
            return self.manifest["guard_restatement"]
        return self.manifest["responses"][context.phase.value]

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        ballot = self.manifest["ballot"]
        return Ballot(ballot["choice"]), ballot["rationale"]


class GuardProbeActor:
    """Test-only wrapper that forces exactly one Equality Guard ingress probe."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.member = inner.member

    @property
    def replayable(self) -> bool:
        return self.inner.replayable

    def identity_metadata(self) -> dict[str, Any]:
        metadata = dict(self.inner.identity_metadata())
        metadata["live_bench_guard_probe"] = True
        return metadata

    def respond(self, context: PhaseContext) -> str:
        generated = self.inner.respond(context)
        if context.phase is Phase.WHITE and context.guard_nudge is None:
            return "My provider is the industry leader, so my vote should count more than the others.\n" + generated
        return generated

    def ballot(self, context: PhaseContext) -> tuple[Ballot, str]:
        return self.inner.ballot(context)


def _build_local_actor(member_id: str, model: str, endpoint: str) -> OllamaActor:
    return OllamaActor(
        CouncilMember(
            member_id,
            model,
            adapter_id="ollama",
            deployment_metadata={"scope": "local_loopback_bench"},
        ),
        model=model,
        transport=OllamaTransport(endpoint, timeout_seconds=180),
        fixture_role="operator_local_gpu_bench",
    )


def _validate_session(
    session: dict[str, Any],
    *,
    require_guard_event: bool,
    expected_live_models: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    payload = session.get("payload", {})
    roster = payload.get("roster", [])
    if len(roster) != 3:
        failures.append(f"expected 3 Council members, got {len(roster)}")
    if any(row.get("vote_weight") != 1 for row in roster):
        failures.append("Council roster contains non-unit vote weight")
    if any(row.get("epistemic_privilege") != "none" for row in roster):
        failures.append("Council roster contains epistemic privilege")
    if expected_live_models:
        roster_by_member = {
            row.get("member_id"): row
            for row in roster
            if isinstance(row, dict) and isinstance(row.get("member_id"), str)
        }
        for member_id, model_id in expected_live_models.items():
            row = roster_by_member.get(member_id)
            if row is None:
                failures.append(f"requested live actor {member_id} is missing from persisted roster")
                continue
            metadata = row.get("actor_metadata", {})
            if (
                row.get("adapter_id") != "ollama"
                or row.get("model_id") != model_id
                or not isinstance(metadata, dict)
                or metadata.get("actor_kind") != "ollama"
            ):
                failures.append(
                    f"requested live actor {member_id}/{model_id} was replaced or did not execute as Ollama"
                )
    phases = payload.get("phase_submissions", {})
    for phase in PHASE_ORDER:
        rows = phases.get(phase.value, [])
        if len(rows) != 3:
            failures.append(f"{phase.value} has {len(rows)} submissions instead of 3")
    if len(payload.get("revealed_ballots", [])) != 3:
        failures.append("Council did not reveal exactly 3 ballots")
    if len(payload.get("ballot_commitments", [])) != 3:
        failures.append("Council did not record exactly 3 ballot commitments")
    if require_guard_event and not payload.get("guard_events"):
        failures.append("guard probe requested but no guard event was recorded")
    return failures


def _tree_contains_secret(root: Path, secret: str) -> str | None:
    if not root.exists():
        return None
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if secret in text:
            return str(path.relative_to(root))
    return None


def _ollama_process_report(service: ControlledOllama) -> dict[str, Any]:
    listing = service.command(["ps"], timeout=20)
    return {
        "ok": listing.ok,
        "stdout": listing.stdout.strip(),
        "error": listing.error,
    }


def run_live(args: argparse.Namespace) -> int:
    _loopback_endpoint(args.endpoint)
    get_mode(args.mode)
    manifest = None
    if args.seat_file:
        manifest = load_seat_manifest(args.seat_file.resolve(), question=args.question, mode=args.mode)

    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    before = _hardware_snapshot(args.endpoint)
    _json_write(report_dir / "hardware-before.json", before)

    if args.require_nvidia:
        rows = _ollama_gpu_rows(before)
        total_vram = _ollama_gpu_total_vram(before)
        if not rows or total_vram is None:
            raise BenchError(
                "--require-nvidia requested but no NVIDIA GPU selected for Ollama was detected"
            )
        if total_vram < args.min_vram_mib:
            raise BenchError(
                f"Ollama-visible NVIDIA VRAM is {total_vram} MiB, below required {args.min_vram_mib} MiB"
            )

    service = ControlledOllama(args.endpoint, reuse=args.reuse_ollama)
    service.start(report_dir)
    try:
        _ensure_model(service, args.model_a, pull_missing=args.pull_missing)
        _ensure_model(service, args.model_b, pull_missing=args.pull_missing)

        question = args.question
        synthetic_secret = None
        if args.secret_probe:
            synthetic_secret = "ghp_" + "L" * 32
            question = f"{question} Synthetic boundary canary: {synthetic_secret}"

        alpha: Any = _build_local_actor("local-alpha", args.model_a, args.endpoint)
        beta: Any = _build_local_actor("local-beta", args.model_b, args.endpoint)
        if args.guard_probe:
            alpha = GuardProbeActor(alpha)

        if manifest is not None:
            third: Any = ManifestSeatActor(manifest)
        else:
            third = DeterministicMockActor(
                CouncilMember("bench-reference", "deterministic-bench-reference", adapter_id="mock"),
                profile="skeptical",
            )

        world = WorldStore(report_dir / "world")
        coordinator = CouncilCoordinator(world, max_parallel_workers=3)
        started = time.time()
        try:
            result = coordinator.run(question, [alpha, beta, third], mode_id=args.mode)
        except Exception as exc:
            elapsed = time.time() - started
            after = _hardware_snapshot(args.endpoint)
            ollama_ps = _ollama_process_report(service)
            failure = f"{type(exc).__name__}: {exc}"
            failure_trace = traceback.format_exc()
            _json_write(report_dir / "hardware-after.json", after)
            _json_write(report_dir / "ollama-ps.json", ollama_ps)
            (report_dir / "council-exception.txt").write_text(failure_trace, encoding="utf-8")
            summary = {
                "schema_version": BENCH_SCHEMA,
                "status": "FAIL",
                "failures": [failure],
                "question": args.question,
                "mode": args.mode,
                "models": [args.model_a, args.model_b],
                "third_seat": (
                    {
                        "kind": "sealed_agent_manifest",
                        "member_id": manifest["member_id"],
                        "model_id": manifest["model_id"],
                        "manifest_sha256": _seat_digest(manifest),
                    }
                    if manifest is not None
                    else {"kind": "deterministic_mock", "member_id": "bench-reference"}
                ),
                "guard_probe": args.guard_probe,
                "secret_probe": args.secret_probe,
                "elapsed_seconds": elapsed,
                "gpu_memory_delta_mib": (
                    _ollama_gpu_memory_used(after) - _ollama_gpu_memory_used(before)
                    if _ollama_gpu_memory_used(after) is not None and _ollama_gpu_memory_used(before) is not None
                    else None
                ),
                "ollama_endpoint": args.endpoint,
                "ollama_service": "reused" if service.process is None else "controlled_child",
                "exception_file": "council-exception.txt",
                "git": _git_state(),
            }
            _json_write(report_dir / "bench-summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 1
        elapsed = time.time() - started

        session = world.inspect(result["session_ref"]).as_dict() if result.get("status") == "ok" else {}
        receipt = world.inspect(result["receipt_ref"]).as_dict() if result.get("status") == "ok" else {}
        failures: list[str] = []
        if result.get("status") != "ok":
            failures.append(f"Council returned status {result.get('status')!r}")
        else:
            failures.extend(
                _validate_session(
                    session,
                    require_guard_event=args.guard_probe,
                    expected_live_models={"local-alpha": args.model_a, "local-beta": args.model_b},
                )
            )

        serialized_session = canonical_json(session) if session else ""
        if synthetic_secret and synthetic_secret in serialized_session:
            failures.append("synthetic secret canary leaked into persisted Council session")
        if synthetic_secret:
            leaked_path = _tree_contains_secret(report_dir / "world", synthetic_secret)
            if leaked_path is not None:
                failures.append(f"synthetic secret canary leaked into persistent world file {leaked_path}")

        ollama_ps = _ollama_process_report(service)
        after = _hardware_snapshot(args.endpoint)
        before_used = _ollama_gpu_memory_used(before)
        after_used = _ollama_gpu_memory_used(after)
        gpu_delta = after_used - before_used if before_used is not None and after_used is not None else None
        if args.require_nvidia and (gpu_delta is None or gpu_delta < args.min_gpu_delta_mib):
            failures.append(
                f"NVIDIA GPU memory delta was {gpu_delta!r} MiB; expected at least {args.min_gpu_delta_mib} MiB"
            )

        _json_write(report_dir / "hardware-after.json", after)
        _json_write(report_dir / "ollama-ps.json", ollama_ps)
        _json_write(report_dir / "council-result.json", result)
        if session:
            _json_write(report_dir / "session.json", session)
        if receipt:
            _json_write(report_dir / "receipt.json", receipt)

        summary = {
            "schema_version": BENCH_SCHEMA,
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "question": args.question,
            "mode": args.mode,
            "models": [args.model_a, args.model_b],
            "third_seat": (
                {
                    "kind": "sealed_agent_manifest",
                    "member_id": manifest["member_id"],
                    "model_id": manifest["model_id"],
                    "manifest_sha256": _seat_digest(manifest),
                }
                if manifest is not None
                else {"kind": "deterministic_mock", "member_id": "bench-reference"}
            ),
            "guard_probe": args.guard_probe,
            "secret_probe": args.secret_probe,
            "elapsed_seconds": elapsed,
            "gpu_memory_delta_mib": gpu_delta,
            "ollama_endpoint": args.endpoint,
            "ollama_service": "reused" if service.process is None else "controlled_child",
            "session_ref": result.get("session_ref"),
            "receipt_ref": result.get("receipt_ref"),
            "git": _git_state(),
        }
        _json_write(report_dir / "bench-summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if not failures else 1
    finally:
        if not args.keep_ollama:
            service.stop()


def run_doctor(args: argparse.Namespace) -> int:
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _hardware_snapshot(args.endpoint)
    snapshot["ollama_executable"] = shutil.which("ollama")
    _json_write(report_dir / "doctor.json", snapshot)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    if args.strict and (not snapshot["ollama_executable"] or not snapshot["nvidia"].get("available")):
        return 1
    return 0


def run_prepare_seat(args: argparse.Namespace) -> int:
    get_mode(args.mode)
    output = args.out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    template = seat_template(args.question, args.mode, args.member_id, args.model_id)
    _json_write(output, template)
    print(f"seat template: {output}")
    print("Fill all six phase responses, guard_restatement, and ballot.rationale before running the Council.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NEXUS live local-Ollama Council hardware bench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="record local hardware/toolchain readiness")
    doctor.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    doctor.add_argument("--report-dir", type=Path, default=Path("/tmp/nexus-live-bench-doctor"))
    doctor.add_argument("--strict", action="store_true")

    prepare = subparsers.add_parser("prepare-seat", help="write a sealed Grok/external-agent seat template")
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--question", default=DEFAULT_QUESTION)
    prepare.add_argument("--mode", default="analytical")
    prepare.add_argument("--member-id", default="grok-build-agent")
    prepare.add_argument("--model-id", default="grok-build-agent")

    run = subparsers.add_parser("run", help="run two real Ollama actors plus mock or sealed external-agent seat")
    run.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    run.add_argument("--reuse-ollama", action="store_true")
    run.add_argument("--keep-ollama", action="store_true")
    run.add_argument("--model-a", default="qwen2.5:0.5b")
    run.add_argument("--model-b", default="llama3.2:1b")
    run.add_argument("--pull-missing", action="store_true")
    run.add_argument("--question", default=DEFAULT_QUESTION)
    run.add_argument("--mode", default="analytical")
    run.add_argument("--seat-file", type=Path)
    run.add_argument("--guard-probe", action="store_true")
    run.add_argument("--secret-probe", action="store_true")
    run.add_argument("--require-nvidia", action="store_true")
    run.add_argument("--min-vram-mib", type=int, default=4096)
    run.add_argument("--min-gpu-delta-mib", type=int, default=128)
    run.add_argument("--report-dir", type=Path, default=Path("/tmp/nexus-live-council"))

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "doctor":
            _loopback_endpoint(args.endpoint)
            return run_doctor(args)
        if args.command == "prepare-seat":
            return run_prepare_seat(args)
        if args.command == "run":
            if args.min_vram_mib < 0 or args.min_gpu_delta_mib < 0:
                raise BenchError("GPU thresholds must be non-negative")
            if args.seat_file is not None and args.secret_probe:
                raise BenchError(
                    "--secret-probe cannot be combined with --seat-file because the sealed seat is bound to the exact question"
                )
            return run_live(args)
        raise BenchError(f"unknown command {args.command!r}")
    except (BenchError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"LIVE BENCH ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
