from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected anchor once, found {count}")
    return text.replace(old, new, 1)


def generatorize_function(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}(")
    end = text.index(f"\n\ndef {next_name}(", start)
    section = text[start:end]
    lines = section.splitlines()
    converted = 0
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "results: list[CheckResult] = []":
            continue
        if stripped.startswith("results.append(_run_check("):
            if not stripped.endswith(")"):
                raise SystemExit(f"{name}: unexpected append syntax: {stripped}")
            indent = line[: len(line) - len(line.lstrip())]
            inner = stripped[len("results.append(") : -1]
            output.append(f"{indent}yield {inner}")
            converted += 1
            continue
        if stripped == "return results":
            continue
        output.append(line)
    if converted == 0:
        raise SystemExit(f"{name}: no eager result appends converted")
    new_section = "\n".join(output)
    return text[:start] + new_section + text[end:]


runner_path = Path("tools/nexus_adversary.py")
runner = runner_path.read_text(encoding="utf-8")

runner = replace_once(
    runner,
    '''            _require(response.get("status") == "error", "non-loopback Ollama endpoint was accepted")
            return response.get("error", {}).get("message", "remote endpoint rejected")
''',
    '''            error = response.get("error", {})
            _require(
                response.get("status") == "error"
                and isinstance(error, dict)
                and error.get("code") == "invalid_request",
                "non-loopback Ollama endpoint was not rejected at validation",
            )
            return error.get("message", "remote endpoint rejected")
''',
    "remote endpoint validation",
)

runner = replace_once(
    runner,
    '''        if resolved.is_dir():
            candidates = sorted(resolved.glob("*.jsonl"))
        elif resolved.exists():
            candidates = [resolved]
        else:
            continue
''',
    '''        if resolved.is_dir():
            candidates = sorted(resolved.glob("*.jsonl"))
            if not candidates:
                raise FileNotFoundError(f"corpus directory contains no .jsonl files: {resolved}")
        elif resolved.exists():
            candidates = [resolved]
        else:
            raise FileNotFoundError(f"corpus path does not exist: {resolved}")
''',
    "corpus configuration",
)

runner = replace_once(
    runner,
    '''    serialized = json.dumps(response, sort_keys=True, ensure_ascii=False)
    for needle in expect.get("contains", []):
        _require(isinstance(needle, str), "expect.contains values must be strings")
        _require(needle in serialized, f"expected response to contain {needle!r}")
    for needle in expect.get("forbid", []):
        _require(isinstance(needle, str), "expect.forbid values must be strings")
        _require(needle not in serialized, f"forbidden response content present: {needle!r}")
''',
    '''    serialized = json.dumps(response, sort_keys=True, ensure_ascii=False)
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
''',
    "corpus expectation arrays",
)

runner = replace_once(
    runner,
    "def _builtin_probes(seed: int, iterations: int) -> list[CheckResult]:\n",
    "def _builtin_probes(seed: int, iterations: int) -> Iterable[CheckResult]:\n",
    "builtin probe signature",
)
runner = generatorize_function(runner, "_builtin_probes", "_iter_corpus_files")
runner = replace_once(
    runner,
    "def _run_corpus(files: list[Path]) -> list[CheckResult]:\n",
    "def _run_corpus(files: list[Path]) -> Iterable[CheckResult]:\n",
    "corpus signature",
)
runner = generatorize_function(runner, "_run_corpus", "_commit_id")

runner = replace_once(
    runner,
    '''def _commit_id() -> str:
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
''',
    '''def _commit_id() -> str:
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
    status = proc.stdout.rstrip("\\n")
    return {"dirty": bool(status), "status": status}
''',
    "worktree state helper",
)

main_start = runner.index("def main(argv: list[str] | None = None) -> int:")
main_end = runner.index("\n\nif __name__ == \"__main__\":", main_start)
new_main = '''def main(argv: list[str] | None = None) -> int:
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
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
        print(f"report: {output}")

    print(
        f"GAUNTLET {report['summary']['verdict']}: "
        f"{report['summary']['passed']}/{report['summary']['checks']} checks passed"
    )
    return 0 if not failures else 1
'''
runner = runner[:main_start] + new_main + runner[main_end:]
runner_path.write_text(runner, encoding="utf-8")


compare_path = Path("tools/nexus_adversary_compare.py")
compare = compare_path.read_text(encoding="utf-8")
compare = replace_once(
    compare,
    '''    baseline = status_map(load_report(args.baseline))
    candidate = status_map(load_report(args.candidate))

    baseline_failed = {name for name, status in baseline.items() if status == "fail"}
    candidate_failed = {name for name, status in candidate.items() if status == "fail"}
    new_failures = sorted(candidate_failed - baseline_failed)
    fixed = sorted(baseline_failed - candidate_failed)
''',
    '''    baseline_report = load_report(args.baseline)
    candidate_report = load_report(args.candidate)
    for field in ("profile", "seed", "iterations"):
        baseline_value = baseline_report.get(field)
        candidate_value = candidate_report.get(field)
        if baseline_value != candidate_value:
            print(
                f"INCOMPATIBLE CONFIGURATION: {field} baseline={baseline_value!r} "
                f"candidate={candidate_value!r}"
            )
            return 2

    baseline = status_map(baseline_report)
    candidate = status_map(candidate_report)

    baseline_failed = {name for name, status in baseline.items() if status == "fail"}
    candidate_failed = {name for name, status in candidate.items() if status == "fail"}
    new_failures = sorted(candidate_failed - baseline_failed)
    fixed = sorted(name for name in baseline_failed if candidate.get(name) == "pass")
''',
    "comparator configuration and fixed semantics",
)
compare_path.write_text(compare, encoding="utf-8")


tests_path = Path("tests/test_adversarial_tools.py")
tests = tests_path.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''def report(rows: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": "nexus-adversarial-gauntlet/1",
        "results": [{"name": name, "status": status} for name, status in rows],
    }
''',
    '''def report(
    rows: list[tuple[str, str]],
    *,
    profile: str = "full",
    seed: int = 1234,
    iterations: int = 512,
) -> dict:
    return {
        "schema_version": "nexus-adversarial-gauntlet/1",
        "profile": profile,
        "seed": seed,
        "iterations": iterations,
        "results": [{"name": name, "status": status} for name, status in rows],
    }
''',
    "test report metadata",
)
insert_anchor = '''    def test_comparator_reports_fixed_failure(self) -> None:
        result = self.run_compare(
            report([("known-hole", "fail")]),
            report([("known-hole", "pass")]),
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("FIXED", result.stdout)
        self.assertIn("known-hole", result.stdout)
'''
insert_new = insert_anchor + '''
    def test_comparator_rejects_mismatched_fuzz_configuration(self) -> None:
        result = self.run_compare(
            report([("malformed-request-fuzz", "fail")], seed=1, iterations=512),
            report([("malformed-request-fuzz", "pass")], seed=2, iterations=32),
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INCOMPATIBLE CONFIGURATION", result.stdout)

    def test_missing_failed_check_is_not_reported_fixed(self) -> None:
        result = self.run_compare(
            report([("known-hole", "fail"), ("stable", "pass")]),
            report([("stable", "pass")]),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("MISSING CHECKS", result.stdout)
        fixed_section = result.stdout.split("FIXED:", 1)
        if len(fixed_section) == 2:
            self.assertNotIn("known-hole", fixed_section[1].split("MISSING CHECKS:", 1)[0])

    def test_runner_rejects_missing_corpus_path_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_path = root / "gauntlet.json"
            missing = root / "does-not-exist"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "nexus_adversary.py"),
                    "--profile",
                    "probes",
                    "--iterations",
                    "1",
                    "--no-default-corpus",
                    "--corpus",
                    str(missing),
                    "--json-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            row = next(item for item in payload["results"] if item["name"] == "corpus-configuration")
            self.assertEqual(row["status"], "fail")

    def test_runner_rejects_string_contains_expectation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corpus = root / "bad.jsonl"
            report_path = root / "gauntlet.json"
            corpus.write_text(
                json.dumps(
                    {
                        "name": "bad-contains",
                        "request": {"operation": "definitely.not.an.operation"},
                        "expect": {"contains": "error"},
                    }
                )
                + "\\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "nexus_adversary.py"),
                    "--profile",
                    "probes",
                    "--iterations",
                    "1",
                    "--no-default-corpus",
                    "--corpus",
                    str(corpus),
                    "--json-out",
                    str(report_path),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            row = next(item for item in payload["results"] if "bad-contains" in item["name"])
            self.assertEqual(row["status"], "fail")
            self.assertIn("expect.contains must be an array", row["detail"])

    def test_runner_records_dirty_worktree(self) -> None:
        marker = ROOT / ".nexus-gauntlet-dirty-test"
        try:
            marker.write_text("dirty\\n", encoding="utf-8")
            with tempfile.TemporaryDirectory() as temp:
                report_path = Path(temp) / "gauntlet.json"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "nexus_adversary.py"),
                        "--profile",
                        "probes",
                        "--iterations",
                        "1",
                        "--no-default-corpus",
                        "--json-out",
                        str(report_path),
                    ],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertTrue(payload["worktree"]["dirty"])
                self.assertIn(marker.name, payload["worktree"]["status"])
        finally:
            marker.unlink(missing_ok=True)
'''
tests = replace_once(tests, insert_anchor, insert_new, "adversarial regressions")
tests_path.write_text(tests, encoding="utf-8")


docs_path = Path("docs/ADVERSARIAL_GAUNTLET.md")
docs = docs_path.read_text(encoding="utf-8")
docs = replace_once(
    docs,
    '''{"name":"weighted-seat","request":{"operation":"council.run","question":"q","members":[]},"expect":{"status":"error"}}
''',
    '''{"name":"weighted-seat","request":{"operation":"council.run","question":"q","members":[{"member_id":"A","model_id":"a","adapter_id":"mock","vote_weight":2},{"member_id":"B","model_id":"b","adapter_id":"mock"},{"member_id":"C","model_id":"c","adapter_id":"mock"}]},"expect":{"status":"error","error_code":"invalid_request"}}
''',
    "weighted seat docs example",
)
docs = docs.replace(
    "- `contains`: strings that must occur in serialized response;\n- `forbid`: strings that must not occur in serialized response.\n",
    "- `contains`: an array of strings that must occur in serialized response;\n- `forbid`: an array of strings that must not occur in serialized response.\n",
)
docs = docs.replace(
    "Pass extra corpus files or directories with repeated `--corpus PATH`. The default `adversarial/corpus/*.jsonl` corpus is loaded automatically unless `--no-default-corpus` is set.\n",
    "Pass extra corpus files or directories with repeated `--corpus PATH`. The default `adversarial/corpus/*.jsonl` corpus is loaded automatically unless `--no-default-corpus` is set. Missing configured paths and configured directories containing no `.jsonl` cases are hard failures so corpus coverage cannot silently evaporate.\n",
)
docs = docs.replace(
    "The comparator exits non-zero when the candidate introduces a **new named failing check** or when a baseline check disappears entirely. It also reports fixed and added checks. This does not make an existing failure acceptable; it is a regression lens that prevents \"fixing\" the gauntlet by making checks evaporate.\n",
    "The comparator first requires matching `profile`, `seed`, and `iterations`, then exits non-zero when the candidate introduces a **new named failing check** or when a baseline check disappears entirely. It reports a baseline failure as fixed only when that same named check is still present and passing. This does not make an existing failure acceptable; it is a regression lens that prevents \"fixing\" the gauntlet by changing fuzz conditions or making checks evaporate.\n",
)
docs += '''\n## Worktree identity and fail-fast behavior\n\nReports record both the current HEAD commit and a `worktree` object containing a dirty flag plus `git status --porcelain` output. A report from an uncommitted build-agent experiment therefore does not masquerade as a pristine-commit run.\n\n`--stop-on-fail` is execution-level fail-fast: built-in probes and corpus cases are generated lazily, and Python/Rust/live phases are invoked sequentially, so later checks are not executed after the first observed failure.\n'''
docs_path.write_text(docs, encoding="utf-8")

print("Applied adversarial-gauntlet review hardening.")
