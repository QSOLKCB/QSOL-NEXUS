from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected anchor once, found {count}")
    return text.replace(old, new, 1)


runner_path = Path("tools/nexus_adversary.py")
runner = runner_path.read_text(encoding="utf-8")
runner = replace_once(
    runner,
    '"endpoint": "https://example.com:11434",',
    '"endpoint": "http://0.0.0.0:11434",',
    "non-routable hostile endpoint",
)
runner_path.write_text(runner, encoding="utf-8")

corpus_path = Path("adversarial/corpus/core.jsonl")
corpus = corpus_path.read_text(encoding="utf-8")
corpus = replace_once(
    corpus,
    '"endpoint":"https://example.com:11434"',
    '"endpoint":"http://0.0.0.0:11434"',
    "corpus non-routable endpoint",
)
corpus_path.write_text(corpus, encoding="utf-8")

compare_path = Path("tools/nexus_adversary_compare.py")
compare = compare_path.read_text(encoding="utf-8")
old = '''    baseline_report = load_report(args.baseline)
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
'''
new = '''    baseline_report = load_report(args.baseline)
    candidate_report = load_report(args.candidate)
    expected_types = {"profile": str, "seed": int, "iterations": int}
    for field, expected_type in expected_types.items():
        baseline_value = baseline_report.get(field)
        candidate_value = candidate_report.get(field)
        if type(baseline_value) is not expected_type or type(candidate_value) is not expected_type:
            print(
                f"INCOMPATIBLE CONFIGURATION: {field} must be present as "
                f"{expected_type.__name__} in both reports"
            )
            return 2
        if baseline_value != candidate_value:
            print(
                f"INCOMPATIBLE CONFIGURATION: {field} baseline={baseline_value!r} "
                f"candidate={candidate_value!r}"
            )
            return 2
'''
compare = replace_once(compare, old, new, "required comparator configuration")
compare_path.write_text(compare, encoding="utf-8")

tests_path = Path("tests/test_adversarial_tools.py")
tests = tests_path.read_text(encoding="utf-8")
anchor = '''    def test_comparator_rejects_mismatched_fuzz_configuration(self) -> None:
        result = self.run_compare(
            report([("malformed-request-fuzz", "fail")], seed=1, iterations=512),
            report([("malformed-request-fuzz", "pass")], seed=2, iterations=32),
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INCOMPATIBLE CONFIGURATION", result.stdout)
'''
addition = anchor + '''
    def test_comparator_rejects_missing_configuration_metadata(self) -> None:
        baseline = report([("stable", "pass")])
        candidate = report([("stable", "pass")])
        baseline.pop("seed")
        candidate.pop("seed")
        result = self.run_compare(baseline, candidate)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INCOMPATIBLE CONFIGURATION", result.stdout)
'''
tests = replace_once(tests, anchor, addition, "missing comparator config regression")
tests_path.write_text(tests, encoding="utf-8")

print("Applied final adversarial harness hygiene fixes.")
