from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected anchor once, found {count}")
    return text.replace(old, new, 1)


bench_path = Path("tools/nexus_live_council_bench.py")
bench = bench_path.read_text(encoding="utf-8")

bench = replace_once(
    bench,
    "from nexus_runtime.mock import DeterministicMockActor  # noqa: E402\n",
    "from nexus_runtime.mock import DeterministicMockActor  # noqa: E402\nfrom nexus_runtime.modes import get_mode  # noqa: E402\n",
    "mode import",
)

bench = replace_once(
    bench,
    '''def _loopback_endpoint(endpoint: str) -> tuple[str, int]:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or not parsed.hostname or parsed.port is None:
        raise BenchError("bench Ollama endpoint must be an explicit http://host:port URL")
    host = parsed.hostname
    if host.lower() != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise BenchError("bench Ollama endpoint must be loopback-only")
        except ValueError as exc:
            raise BenchError("bench Ollama endpoint hostname must be localhost or a loopback IP") from exc
    return host, parsed.port
''',
    '''def _loopback_endpoint(endpoint: str) -> tuple[str, int]:
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
''',
    "endpoint validation and authority",
)

bench = replace_once(
    bench,
    '''            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
''',
    '''            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
''',
    "nvidia query",
)
bench = replace_once(
    bench,
    '''        if len(parts) != 5:
            continue
        try:
            rows.append(
                {
                    "name": parts[0],
                    "memory_total_mib": int(parts[1]),
                    "memory_used_mib": int(parts[2]),
                    "utilization_percent": int(parts[3]),
                    "temperature_c": int(parts[4]),
                }
            )
''',
    '''        if len(parts) != 7:
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
''',
    "nvidia row parsing",
)
bench = replace_once(
    bench,
    '''        "nvidia": _nvidia_snapshot(),
        "git": _git_state(),
''',
    '''        "nvidia": _nvidia_snapshot(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "git": _git_state(),
''',
    "hardware cuda visibility",
)
bench = replace_once(
    bench,
    '''def _first_gpu_used(snapshot: dict[str, Any]) -> int | None:
    nvidia = snapshot.get("nvidia", {})
    rows = nvidia.get("gpus", []) if isinstance(nvidia, dict) else []
    if not rows:
        return None
    value = rows[0].get("memory_used_mib")
    return value if type(value) is int else None
''',
    '''def _ollama_gpu_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
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
''',
    "gpu selection helpers",
)
bench = replace_once(
    bench,
    '''                "OLLAMA_HOST": f"{host}:{port}",
''',
    '''                "OLLAMA_HOST": _ollama_host_authority(host, port),
''',
    "ipv6 ollama host",
)

bench = replace_once(
    bench,
    '''def _validate_session(session: dict[str, Any], *, require_guard_event: bool) -> list[str]:
    failures: list[str] = []
    payload = session.get("payload", {})
    roster = payload.get("roster", [])
''',
    '''def _validate_session(
    session: dict[str, Any],
    *,
    require_guard_event: bool,
    expected_live_models: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    payload = session.get("payload", {})
    roster = payload.get("roster", [])
''',
    "session validator signature",
)
bench = replace_once(
    bench,
    '''    if any(row.get("epistemic_privilege") != "none" for row in roster):
        failures.append("Council roster contains epistemic privilege")
    phases = payload.get("phase_submissions", {})
''',
    '''    if any(row.get("epistemic_privilege") != "none" for row in roster):
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
''',
    "session live actor validation",
)

bench = replace_once(
    bench,
    '''def run_live(args: argparse.Namespace) -> int:
    _loopback_endpoint(args.endpoint)
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    before = _hardware_snapshot(args.endpoint)
''',
    '''def run_live(args: argparse.Namespace) -> int:
    _loopback_endpoint(args.endpoint)
    get_mode(args.mode)
    manifest = None
    if args.seat_file:
        manifest = load_seat_manifest(args.seat_file.resolve(), question=args.question, mode=args.mode)

    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    before = _hardware_snapshot(args.endpoint)
''',
    "preflight validation",
)
bench = replace_once(
    bench,
    '''        nvidia = before.get("nvidia", {})
        rows = nvidia.get("gpus", []) if isinstance(nvidia, dict) else []
        if not rows:
            raise BenchError("--require-nvidia requested but no NVIDIA GPU was detected")
        if rows[0]["memory_total_mib"] < args.min_vram_mib:
            raise BenchError(
                f"GPU has {rows[0]['memory_total_mib']} MiB VRAM, below required {args.min_vram_mib} MiB"
            )
''',
    '''        rows = _ollama_gpu_rows(before)
        total_vram = _ollama_gpu_total_vram(before)
        if not rows or total_vram is None:
            raise BenchError(
                "--require-nvidia requested but no NVIDIA GPU selected for Ollama was detected"
            )
        if total_vram < args.min_vram_mib:
            raise BenchError(
                f"Ollama-visible NVIDIA VRAM is {total_vram} MiB, below required {args.min_vram_mib} MiB"
            )
''',
    "gpu preflight",
)
bench = replace_once(
    bench,
    '''        manifest = None
        if args.seat_file:
            manifest = load_seat_manifest(args.seat_file.resolve(), question=args.question, mode=args.mode)
            third: Any = ManifestSeatActor(manifest)
        else:
''',
    '''        if manifest is not None:
            third: Any = ManifestSeatActor(manifest)
        else:
''',
    "reuse prevalidated manifest",
)
bench = replace_once(
    bench,
    '''            failures.extend(_validate_session(session, require_guard_event=args.guard_probe))
''',
    '''            failures.extend(
                _validate_session(
                    session,
                    require_guard_event=args.guard_probe,
                    expected_live_models={"local-alpha": args.model_a, "local-beta": args.model_b},
                )
            )
''',
    "validate requested live models",
)
bench = bench.replace("_first_gpu_used(after) - _first_gpu_used(before)", "_ollama_gpu_memory_used(after) - _ollama_gpu_memory_used(before)")
bench = bench.replace("_first_gpu_used(after) is not None and _first_gpu_used(before) is not None", "_ollama_gpu_memory_used(after) is not None and _ollama_gpu_memory_used(before) is not None")
bench = replace_once(
    bench,
    '''        before_used = _first_gpu_used(before)
        after_used = _first_gpu_used(after)
''',
    '''        before_used = _ollama_gpu_memory_used(before)
        after_used = _ollama_gpu_memory_used(after)
''',
    "gpu delta",
)
bench = replace_once(
    bench,
    '''def run_prepare_seat(args: argparse.Namespace) -> int:
    output = args.out.resolve()
''',
    '''def run_prepare_seat(args: argparse.Namespace) -> int:
    get_mode(args.mode)
    output = args.out.resolve()
''',
    "prepare mode validation",
)

bench_path.write_text(bench, encoding="utf-8")


test_path = Path("tests/test_live_council_bench.py")
tests = test_path.read_text(encoding="utf-8")

tests = replace_once(
    tests,
    '''    def test_loopback_endpoint_accepts_dedicated_bench_port(self) -> None:
        self.assertEqual(bench._loopback_endpoint("http://127.0.0.1:11435"), ("127.0.0.1", 11435))
        self.assertEqual(bench._loopback_endpoint("http://localhost:11435"), ("localhost", 11435))
''',
    '''    def test_loopback_endpoint_accepts_dedicated_bench_port(self) -> None:
        self.assertEqual(bench._loopback_endpoint("http://127.0.0.1:11435"), ("127.0.0.1", 11435))
        self.assertEqual(bench._loopback_endpoint("http://localhost:11435"), ("localhost", 11435))
        self.assertEqual(bench._loopback_endpoint("http://[::1]:11435/"), ("::1", 11435))
        self.assertEqual(bench._ollama_host_authority("::1", 11435), "[::1]:11435")
''',
    "endpoint acceptance tests",
)
tests = replace_once(
    tests,
    '''            "http://example.com:11435",
        ):
''',
    '''            "http://example.com:11435",
            "http://127.0.0.1:11435/foo",
            "http://127.0.0.1:11435/?query=1",
            "http://127.0.0.1:11435/#fragment",
        ):
''',
    "endpoint rejection tests",
)

insert_anchor = '''    def test_run_rejects_remote_endpoint_before_hardware_probe(self) -> None:
        with mock.patch.object(bench, "_hardware_snapshot", side_effect=AssertionError("must not probe")):
            rc = bench.main(["run", "--endpoint", "http://example.com:11435"])
        self.assertEqual(rc, 2)
'''
insert_new = insert_anchor + '''
    def test_run_rejects_mode_and_seat_before_start_or_pull(self) -> None:
        with mock.patch.object(bench.ControlledOllama, "start", side_effect=AssertionError("must not start")), mock.patch.object(
            bench, "_ensure_model", side_effect=AssertionError("must not pull")
        ), mock.patch.object(bench, "_hardware_snapshot", side_effect=AssertionError("must not probe")):
            rc = bench.main(["run", "--mode", "definitely_not_a_mode", "--pull-missing"])
        self.assertEqual(rc, 2)

        manifest = self.complete_manifest(question="q", mode="pure_history")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "seat.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.object(bench.ControlledOllama, "start", side_effect=AssertionError("must not start")), mock.patch.object(
                bench, "_ensure_model", side_effect=AssertionError("must not pull")
            ), mock.patch.object(bench, "_hardware_snapshot", side_effect=AssertionError("must not probe")):
                rc = bench.main(["run", "--question", "q", "--mode", "analytical", "--seat-file", str(path), "--pull-missing"])
        self.assertEqual(rc, 2)

    def test_gpu_accounting_respects_cuda_visible_devices(self) -> None:
        snapshot = {
            "cuda_visible_devices": "1",
            "nvidia": {
                "gpus": [
                    {"index": 0, "uuid": "GPU-zero", "memory_total_mib": 8192, "memory_used_mib": 7000},
                    {"index": 1, "uuid": "GPU-one", "memory_total_mib": 16384, "memory_used_mib": 512},
                ]
            },
        }
        rows = bench._ollama_gpu_rows(snapshot)
        self.assertEqual([row["index"] for row in rows], [1])
        self.assertEqual(bench._ollama_gpu_total_vram(snapshot), 16384)
        self.assertEqual(bench._ollama_gpu_memory_used(snapshot), 512)

        snapshot["cuda_visible_devices"] = "GPU-zero"
        self.assertEqual([row["index"] for row in bench._ollama_gpu_rows(snapshot)], [0])
'''
tests = replace_once(tests, insert_anchor, insert_new, "preflight/gpu tests")

old_session = '''                "roster": [
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                    {"vote_weight": 1, "epistemic_privilege": "none"},
                ],
'''
new_session = '''                "roster": [
                    {
                        "member_id": "local-alpha",
                        "model_id": "model-a",
                        "adapter_id": "ollama",
                        "actor_metadata": {"actor_kind": "ollama"},
                        "vote_weight": 1,
                        "epistemic_privilege": "none",
                    },
                    {
                        "member_id": "local-beta",
                        "model_id": "model-b",
                        "adapter_id": "ollama",
                        "actor_metadata": {"actor_kind": "ollama"},
                        "vote_weight": 1,
                        "epistemic_privilege": "none",
                    },
                    {
                        "member_id": "bench-reference",
                        "model_id": "deterministic-bench-reference",
                        "adapter_id": "mock",
                        "actor_metadata": {"actor_kind": "mock"},
                        "vote_weight": 1,
                        "epistemic_privilege": "none",
                    },
                ],
'''
tests = replace_once(tests, old_session, new_session, "session fixture roster")
tests = replace_once(
    tests,
    '''        self.assertEqual(bench._validate_session(session, require_guard_event=True), [])
        session["payload"]["roster"][0]["vote_weight"] = 2
        failures = bench._validate_session(session, require_guard_event=True)
        self.assertTrue(any("vote weight" in failure for failure in failures))
''',
    '''        expected = {"local-alpha": "model-a", "local-beta": "model-b"}
        self.assertEqual(
            bench._validate_session(session, require_guard_event=True, expected_live_models=expected),
            [],
        )
        session["payload"]["roster"][0]["vote_weight"] = 2
        failures = bench._validate_session(
            session,
            require_guard_event=True,
            expected_live_models=expected,
        )
        self.assertTrue(any("vote weight" in failure for failure in failures))

        session["payload"]["roster"][0]["vote_weight"] = 1
        session["payload"]["roster"][0]["adapter_id"] = "failsafe_replacement"
        session["payload"]["roster"][0]["model_id"] = "nexus-failsafe-relief-v1"
        session["payload"]["roster"][0]["actor_metadata"] = {"actor_kind": "failsafe_replacement"}
        failures = bench._validate_session(
            session,
            require_guard_event=True,
            expected_live_models=expected,
        )
        self.assertTrue(any("was replaced" in failure for failure in failures))
''',
    "session replacement regression",
)

test_path.write_text(tests, encoding="utf-8")
print("Applied live hardware bench review fixes.")
