from pathlib import Path

path = Path('tools/nexus_adversary.py')
text = path.read_text(encoding='utf-8')
start = text.index('def _run_corpus(files: list[Path]) -> list[CheckResult]:')
end = text.index('\n\ndef _commit_id()', start)
new = r'''def _run_corpus(files: list[Path]) -> list[CheckResult]:
    results: list[CheckResult] = []
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

            results.append(_run_check(name, "corpus", execute))
    return results
'''
path.write_text(text[:start] + new + text[end:], encoding='utf-8')
print('Made JSONL corpus cases individually isolated and surfaced case names.')
