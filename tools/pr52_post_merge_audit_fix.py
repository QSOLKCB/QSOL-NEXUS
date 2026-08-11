from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path.relative_to(ROOT)}: expected one match, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all_required(path: Path, old: str, new: str, *, minimum: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < minimum:
        raise SystemExit(f"{path.relative_to(ROOT)}: expected >= {minimum} matches, found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# F1: operator-visible release identity must come from Cargo package metadata.
# ---------------------------------------------------------------------------
main_rs = ROOT / "tui" / "src" / "main.rs"
replace_once(
    main_rs,
    '        app.append("*** NEXUS TUI 2.0 alpha10.2 — local room, no IRC server");',
    '        app.append(&format!("*** NEXUS TUI {} — local room, no IRC server", env!("CARGO_PKG_VERSION")));',
)

# ---------------------------------------------------------------------------
# F2: Secret Scrubber handles case variants and Unicode Cf/zero-width evasion.
# ---------------------------------------------------------------------------
scrub = ROOT / "src" / "nexus_runtime" / "scrub.py"
replace_once(scrub, "import re\n", "import re\nimport unicodedata\n")
replace_once(
    scrub,
    '_Pattern("OPENAI_STYLE_TOKEN", re.compile(r"(?P<secret>sk-[A-Za-z0-9_-]{20,})")),',
    '_Pattern("OPENAI_STYLE_TOKEN", re.compile(r"(?P<secret>sk-[A-Za-z0-9_-]{20,})", re.I)),',
)
old_scrub_method = '''    def scrub(self, text: str) -> ScrubResult:\n        if not isinstance(text, str):\n            raise TypeError("SecretScrubber accepts text only")\n\n        seen: dict[tuple[str, str], str] = {}\n        counters: dict[str, int] = {}\n        events: list[ScrubEvent] = []\n        output = text\n\n        for pattern in self._patterns:\n            def replace(match: re.Match[str], *, _pattern: _Pattern = pattern) -> str:\n                secret = match.group(_pattern.secret_group)\n                key = (_pattern.name, secret)\n                placeholder = seen.get(key)\n                if placeholder is None:\n                    counters[_pattern.name] = counters.get(_pattern.name, 0) + 1\n                    placeholder = f"<REDACTED:{_pattern.name}:{counters[_pattern.name]}>"\n                    seen[key] = placeholder\n                    events.append(ScrubEvent(_pattern.name, placeholder))\n\n                start, end = match.span(_pattern.secret_group)\n                whole = match.group(0)\n                relative_start = start - match.start(0)\n                relative_end = end - match.start(0)\n                return whole[:relative_start] + placeholder + whole[relative_end:]\n\n            output = pattern.regex.sub(replace, output)\n\n        return ScrubResult(output, tuple(events))\n'''
new_scrub_method = '''    def _scrub_patterns(self, text: str) -> ScrubResult:\n        seen: dict[tuple[str, str], str] = {}\n        counters: dict[str, int] = {}\n        events: list[ScrubEvent] = []\n        output = text\n\n        for pattern in self._patterns:\n            def replace(match: re.Match[str], *, _pattern: _Pattern = pattern) -> str:\n                secret = match.group(_pattern.secret_group)\n                key = (_pattern.name, secret)\n                placeholder = seen.get(key)\n                if placeholder is None:\n                    counters[_pattern.name] = counters.get(_pattern.name, 0) + 1\n                    placeholder = f"<REDACTED:{_pattern.name}:{counters[_pattern.name]}>"\n                    seen[key] = placeholder\n                    events.append(ScrubEvent(_pattern.name, placeholder))\n\n                start, end = match.span(_pattern.secret_group)\n                whole = match.group(0)\n                relative_start = start - match.start(0)\n                relative_end = end - match.start(0)\n                return whole[:relative_start] + placeholder + whole[relative_end:]\n\n            output = pattern.regex.sub(replace, output)\n\n        return ScrubResult(output, tuple(events))\n\n    def scrub(self, text: str) -> ScrubResult:\n        if not isinstance(text, str):\n            raise TypeError("SecretScrubber accepts text only")\n\n        direct = self._scrub_patterns(text)\n\n        # Unicode format controls (category Cf) can visually split a credential\n        # prefix without changing what a human sees.  If stripping those controls\n        # reveals a high-confidence credential pattern, persist only the scrubbed\n        # normalized form.  Ordinary text is left byte-for-byte alone.\n        normalized = "".join(char for char in text if unicodedata.category(char) != "Cf")\n        if normalized != text:\n            normalized_result = self._scrub_patterns(normalized)\n            if normalized_result.changed:\n                return normalized_result\n\n        return direct\n'''
replace_once(scrub, old_scrub_method, new_scrub_method)

# ---------------------------------------------------------------------------
# F3/F4: commit-bound report + complete test-module inventory + new final RC.
# ---------------------------------------------------------------------------
runner = ROOT / "tools" / "nexus_release_hardening.py"
replace_once(runner, 'EXPECTED_MATRIX_MILESTONE = "PR #51"', 'EXPECTED_MATRIX_MILESTONE = "PR #52"')
replace_once(runner, "EXPECTED_SCOPE_THROUGH_PR = 50", "EXPECTED_SCOPE_THROUGH_PR = 51")
replace_once(
    runner,
    '''REQUIRED_GROK_FINDING_IDS = frozenset(f"R{index}" for index in range(1, 13))\nEXPECTED_MATRIX_MILESTONE = "PR #52"''',
    '''REQUIRED_GROK_FINDING_IDS = frozenset(f"R{index}" for index in range(1, 13))\nREQUIRED_POST_MERGE_FINDING_IDS = frozenset({"F1", "F2", "F3", "F4", "F5", "RACE1"})\nEXPECTED_PYTHON_TEST_FILES = 81\nEXPECTED_MATRIX_MILESTONE = "PR #52"''',
)
replace_once(
    runner,
    '''REQUIRED_RELEASE_RULE = (\n    "Only the exact merged PR #51 head may be tagged v2.0.0 after the complete "\n    "release-candidate matrix passes with no unresolved release-blocking review findings."\n)''',
    '''REQUIRED_RELEASE_RULE = (\n    "Only the exact merged PR #52 head may be tagged v2.0.0 after the complete "\n    "release-candidate matrix passes with no unresolved release-blocking review findings."\n)''',
)
replace_once(
    runner,
    '        "candidate-tree-clean",\n        "matrix-audit",',
    '        "candidate-tree-clean",\n        "candidate-commit-binding",\n        "matrix-audit",',
)
replace_once(
    runner,
    '''    if matrix.get("release_rule") != REQUIRED_RELEASE_RULE:\n        raise ValueError("release-candidate stable-tag rule mismatch")\n    if matrix.get("authority_effect") != "none":''',
    '''    if matrix.get("release_rule") != REQUIRED_RELEASE_RULE:\n        raise ValueError("release-candidate stable-tag rule mismatch")\n    if matrix.get("expected_python_test_files") != EXPECTED_PYTHON_TEST_FILES:\n        raise ValueError("release-candidate Python test inventory count mismatch")\n    if matrix.get("authority_effect") != "none":''',
)
replace_once(
    runner,
    '''    if seen != REQUIRED_GATE_IDS:\n        missing = sorted(REQUIRED_GATE_IDS - seen)\n        extra = sorted(seen - REQUIRED_GATE_IDS)\n        raise ValueError(\n            "hardening gate inventory mismatch; "\n            f"missing={missing or 'none'} extra={extra or 'none'}"\n        )\n\n    rehearsals = matrix.get("rehearsals")''',
    '''    if seen != REQUIRED_GATE_IDS:\n        missing = sorted(REQUIRED_GATE_IDS - seen)\n        extra = sorted(seen - REQUIRED_GATE_IDS)\n        raise ValueError(\n            "hardening gate inventory mismatch; "\n            f"missing={missing or 'none'} extra={extra or 'none'}"\n        )\n\n    full_inventory = {path for path in tests_root.glob("test_*.py") if path.is_file()}\n    if len(full_inventory) != EXPECTED_PYTHON_TEST_FILES:\n        raise ValueError(\n            f"Python test inventory changed: expected {EXPECTED_PYTHON_TEST_FILES}, found {len(full_inventory)}"\n        )\n    if matched != full_inventory:\n        missing_from_matrix = sorted(path.name for path in full_inventory - matched)\n        extra_matches = sorted(path.name for path in matched - full_inventory)\n        raise ValueError(\n            "hardening matrix must intentionally cover the complete Python test inventory; "\n            f"missing={missing_from_matrix or 'none'} extra={extra_matches or 'none'}"\n        )\n\n    rehearsals = matrix.get("rehearsals")''',
)
replace_once(
    runner,
    '''    if closure.get("status") != "resolved_in_pre_stable_line":\n        raise ValueError("Grok PR49 findings must remain resolved before stable release")\n    verification = closure.get("verification")\n    if verification != "tests/test_release_hardening_grok_audit.py":\n        raise ValueError("Grok PR49 audit closure verification target mismatch")\n\n    release_test = tests_root / "test_release_hardening.py"''',
    '''    if closure.get("status") != "resolved_in_pre_stable_line":\n        raise ValueError("Grok PR49 findings must remain resolved before stable release")\n    verification = closure.get("verification")\n    if verification != "tests/test_release_hardening_grok_audit.py":\n        raise ValueError("Grok PR49 audit closure verification target mismatch")\n\n    post_merge = matrix.get("post_merge_audit_closure")\n    if not isinstance(post_merge, dict) or post_merge.get("required_before_stable") is not True:\n        raise ValueError("post-merge Grok audit closure must remain release-blocking")\n    post_ids = post_merge.get("finding_ids")\n    if not isinstance(post_ids, list) or set(post_ids) != REQUIRED_POST_MERGE_FINDING_IDS:\n        raise ValueError("post-merge Grok finding inventory mismatch")\n    if post_merge.get("status") != "resolved_in_pr52":\n        raise ValueError("post-merge Grok findings must be resolved in PR #52")\n    if post_merge.get("verification") != "tests/test_post_merge_grok_audit.py":\n        raise ValueError("post-merge Grok audit verification target mismatch")\n\n    release_test = tests_root / "test_release_hardening.py"''',
)
replace_once(
    runner,
    '''        f"{len(seen)} required gates cover {len(matched)} test files; "\n        f"{len(observed_rehearsals)} required rehearsals and 12/12 Grok findings pinned; "''',
    '''        f"{len(seen)} required gates cover {len(matched)}/{EXPECTED_PYTHON_TEST_FILES} test files; "\n        f"{len(observed_rehearsals)} required rehearsals, 12/12 Grok PR49 findings and 6/6 post-merge findings pinned; "''',
)
# Insert git identity helpers before matrix audit.
replace_once(
    runner,
    '''def _matrix_audit() -> CheckResult:\n''',
    '''def _git_identity() -> tuple[str, str]:\n    def rev_parse(spec: str) -> str:\n        proc = subprocess.run(\n            ["git", "rev-parse", spec],\n            cwd=ROOT,\n            text=True,\n            stdout=subprocess.PIPE,\n            stderr=subprocess.STDOUT,\n            timeout=120,\n            check=False,\n        )\n        value = proc.stdout.strip()\n        if proc.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:\n            raise RuntimeError(f"could not resolve git identity for {spec}: {proc.stdout}")\n        return value\n\n    return rev_parse("HEAD"), rev_parse("HEAD^{tree}")\n\n\ndef _commit_binding(expected_commit: str | None, git_commit: str, git_tree: str) -> CheckResult:\n    started = time.monotonic()\n    if expected_commit is not None and expected_commit != git_commit:\n        return CheckResult(\n            "candidate-commit-binding",\n            "fail",\n            time.monotonic() - started,\n            f"expected commit {expected_commit} but checked out {git_commit}; tree={git_tree}",\n        )\n    expectation = expected_commit if expected_commit is not None else "current HEAD"\n    return CheckResult(\n        "candidate-commit-binding",\n        "pass",\n        time.monotonic() - started,\n        f"report bound to commit {git_commit}; tree={git_tree}; expected={expectation}",\n    )\n\n\ndef _matrix_audit() -> CheckResult:\n''',
)
# _build_report acquires/records immutable git identity.
replace_once(
    runner,
    'def _build_report(checks: list[CheckResult]) -> dict[str, Any]:\n    observed_names = {check.name for check in checks}',
    'def _build_report(\n    checks: list[CheckResult],\n    *,\n    git_commit: str | None = None,\n    git_tree: str | None = None,\n) -> dict[str, Any]:\n    if git_commit is None or git_tree is None:\n        git_commit, git_tree = _git_identity()\n    observed_names = {check.name for check in checks}',
)
replace_once(
    runner,
    '        "target_version": TARGET_VERSION,\n        "scope_through_pr": EXPECTED_SCOPE_THROUGH_PR,',
    '        "target_version": TARGET_VERSION,\n        "git_commit": git_commit,\n        "git_tree": git_tree,\n        "scope_through_pr": EXPECTED_SCOPE_THROUGH_PR,',
)
replace_once(
    runner,
    '    parser.add_argument("--iterations", type=int, default=128)\n    args = parser.parse_args()',
    '    parser.add_argument("--iterations", type=int, default=128)\n    parser.add_argument("--expect-commit")\n    args = parser.parse_args()',
)
replace_once(
    runner,
    '''    checks: list[CheckResult] = [_worktree_audit("candidate-tree-clean")]\n    if checks[-1].passed:\n        checks.append(_matrix_audit())\n    if checks[-1].name == "matrix-audit" and checks[-1].passed:''',
    '''    try:\n        git_commit, git_tree = _git_identity()\n    except Exception as exc:\n        print(json.dumps({"status": "failed", "error": f"git identity unavailable: {exc}"}, indent=2))\n        return 1\n\n    checks: list[CheckResult] = [_worktree_audit("candidate-tree-clean")]\n    if checks[-1].passed:\n        checks.append(_commit_binding(args.expect_commit, git_commit, git_tree))\n    if checks[-1].name == "candidate-commit-binding" and checks[-1].passed:\n        checks.append(_matrix_audit())\n    if checks[-1].name == "matrix-audit" and checks[-1].passed:''',
)
replace_once(
    runner,
    '    report = _build_report(checks)\n',
    '    report = _build_report(checks, git_commit=git_commit, git_tree=git_tree)\n',
)

# Matrix is now PR52 and intentionally inventories every test module.
matrix_path = ROOT / "release" / "hardening_matrix.json"
matrix = load_json(matrix_path)
matrix["milestone"] = "PR #52"
matrix["scope_through_pr"] = 51
matrix["expected_python_test_files"] = 81
release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
for pattern in ("test_*.py", "test_post_merge_grok_audit.py"):
    if pattern not in release_gate["patterns"]:
        release_gate["patterns"].append(pattern)
matrix["post_merge_audit_closure"] = {
    "source": "Grok hostile post-merge NEXUS 2.0 audit of dae8e418fd126b4d6e1ae3ce5191dd922013b5f9",
    "required_before_stable": True,
    "finding_ids": ["F1", "F2", "F3", "F4", "F5", "RACE1"],
    "status": "resolved_in_pr52",
    "verification": "tests/test_post_merge_grok_audit.py",
}
matrix["release_rule"] = (
    "Only the exact merged PR #52 head may be tagged v2.0.0 after the complete "
    "release-candidate matrix passes with no unresolved release-blocking review findings."
)
write_json(matrix_path, matrix)

candidate_path = ROOT / "release" / "release_candidate.json"
candidate = load_json(candidate_path)
candidate.pop("base_feature_pr", None)
candidate["feature_surface_through_pr"] = 50
candidate["scope_through_pr"] = 51
candidate["prior_candidate_merge"] = "dae8e418fd126b4d6e1ae3ce5191dd922013b5f9"
candidate["candidate_pr"] = 52
candidate["stable_tag_rule"] = (
    "Tag v2.0.0 only from the exact merged PR #52 commit after all required workflows, "
    "the post-merge Grok audit closure, and release-blocking review findings are green/closed."
)
candidate["post_stable"] = {
    "pr_53": "Lean 4 Formal Verification",
    "pr_54": "Formalization + Reproducibility + Zenodo Publication",
}
write_json(candidate_path, candidate)

# ---------------------------------------------------------------------------
# F5 + sequencing: the audit becomes #52; Lean and publication move to #53/#54.
# ---------------------------------------------------------------------------
readme = ROOT / "README.md"
replace_once(
    readme,
    "PR #50 (The BBS Wall) is merged. PR #51 is the final documentation and release-candidate reconciliation pass against the exact post-Wall runtime. The `2.0.0` identifiers in this branch describe the intended stable bits; they do **not** by themselves declare a stable release. The `v2.0.0` tag may be created only from the exact merged #51 head after the complete release-candidate matrix and review gate are green.",
    "PR #50 (The BBS Wall) and PR #51 (documentation/final-RC reconciliation) are merged. A hostile post-merge Grok audit found release-identity, secret-scrubbing, report-binding, matrix-inventory and metadata gaps, so PR #52 is the new final pre-stable audit-closure candidate. The `2.0.0` identifiers describe the intended stable bits; they do **not** by themselves declare a stable release. The `v2.0.0` tag may be created only from the exact merged #52 head after the complete release-candidate matrix and review gate are green.",
)
replace_once(
    readme,
    "The repository is intentionally strict about the difference between **version alignment** and **release authority**. PR #51 aligns the runtime, Python package, Rust TUI, API docs, architecture, security docs, citation metadata, compatibility statement, and release-hardening matrix on `2.0.0`.",
    "The repository is intentionally strict about the difference between **version alignment** and **release authority**. PR #51 aligned the release surfaces on `2.0.0`; PR #52 closes the independent post-merge audit findings and becomes the exact candidate that must earn the stable tag.",
)
replace_once(
    readme,
    "Only after PR #51 is merged green may that exact commit be tagged `v2.0.0`.",
    "Only after PR #52 is reviewed, merged, and green may that exact commit be tagged `v2.0.0`.",
)
replace_once(
    readme,
    "The alpha10.3 release-prep adds `tests/test_release_wiring.py`, which explicitly checks that the architecture is actually connected: public API identity, full health backend roster, local-role operations, version alignment, and hostile numeric timeout boundaries.",
    "The release-wiring regression `tests/test_release_wiring.py` explicitly checks that the architecture is actually connected: public API identity, full health backend roster, local-role operations, version alignment, and hostile numeric timeout boundaries.",
)

readme_ai_path = ROOT / "README4AI.md"
readme_ai = load_json(readme_ai_path)
readme_ai["release_identity"]["note"] = (
    "PR #51 aligned the intended stable 2.0 bits after merged PR #50. A hostile post-merge Grok audit then made PR #52 the final pre-stable audit-closure candidate. The v2.0.0 tag is forbidden until the exact merged PR #52 head passes the complete release-candidate, post-merge audit, and review gates."
)
readme_ai["stable_2_0"]["remaining_high_level_work"] = [
    "merge_pr_52_post_merge_audit_closure_head",
    "rerun_complete_release_candidate_matrix_and_review_gate_on_exact_pr52_head",
    "create_v2.0.0_tag_and_release_from_that_exact_green_commit",
]
write_json(readme_ai_path, readme_ai)

architecture = ROOT / "ARCHITECTURE.md"
replace_all_required(architecture, "exact merged #51 head", "exact merged #52 head")
replace_all_required(architecture, "merged #51 commit", "merged #52 commit")

# Canonical release sequence rewritten to make the deferral explicit.
sequence_path = ROOT / "docs" / "RELEASE_SEQUENCE.md"
sequence = sequence_path.read_text(encoding="utf-8")
sequence = sequence.replace(
    "PR #51 — Documentation, Release Candidate & Stable Release Prep — THIS RELEASE CANDIDATE\n        ↓\nNEXUS 2.0 STABLE RELEASE\n        ↓\nPR #52 — Lean 4 Formal Verification\n        ↓\nPR #53 — Formalization + Reproducibility + Zenodo Publication",
    "PR #51 — Documentation, Release Candidate & Stable Release Prep — MERGED\n        ↓\nPR #52 — Post-Merge Grok Audit Closure — THIS RELEASE CANDIDATE\n        ↓\nNEXUS 2.0 STABLE RELEASE\n        ↓\nPR #53 — Lean 4 Formal Verification\n        ↓\nPR #54 — Formalization + Reproducibility + Zenodo Publication",
)
if "PR #52 — Post-Merge Grok Audit Closure" not in sequence:
    raise SystemExit("release sequence top block did not update")
old_lean_section = sequence[sequence.index("## PR #52 — Lean 4 Formal Verification"):sequence.index("## Release principle")]
new_sections = '''## PR #52 — Post-Merge Grok Audit Closure\n\nA hostile audit of the exact merged PR #51 commit found defects that existing green CI did not cover. Stable release is therefore deferred until this closure PR is reviewed and green.\n\nRequired closure:\n\n- derive the operator-visible Rust TUI version from Cargo package metadata;\n- harden Secret Scrubbing against case variants and Unicode `Cf` / zero-width prefix splitting before Wall/Council persistence;\n- bind the machine-readable hardening report to exact Git commit and tree identities;\n- intentionally inventory the complete Python test-module surface;\n- align release-candidate metadata vocabulary and remove residual present-tense alpha wording;\n- eliminate the fixed dirty-marker race observed under concurrent audit execution;\n- rerun the complete release-candidate matrix on the exact PR #52 head.\n\nGate:\n\n> **An external audit finding outranks the planned sequence. Fix the candidate before proving the candidate.**\n\nOnly the exact merged PR #52 commit may become `v2.0.0`, and only after the complete matrix/review gate passes.\n\n## PR #53 — Lean 4 Formal Verification\n\nThis is explicitly **post-stable-release verification work**. The previously parked Lean work is retained, but its PR number moves because the post-merge audit closure consumed #52.\n\nAfter the NEXUS 2.0 stable tag and commit exist:\n\n- rebase/update the formalization against the exact stable runtime head;\n- ship a complete runnable Lean project, not isolated snippets;\n- pin the Lean toolchain and compiler release identity;\n- formalize selected constitutional and protocol invariants;\n- maintain an explicit theorem inventory, axiom audit and formal-gap ranking;\n- maintain assumptions and non-claims;\n- map formal theorems to the stable Python/Rust implementation and regression tests;\n- prohibit `sorry`, `admit`, or user-declared axioms as substitutes for advertised proofs;\n- require `lake build` to machine-check the complete selected theorem surface in CI.\n\nThe intended claim remains narrow:\n\n> **Selected constitutional and protocol invariants of NEXUS 2.0 are machine-checked in Lean 4 against an explicit formal model, with correspondence to the tested stable runtime.**\n\nPR #53 MUST leave the reviewed runnable Lean source available for independent reproduction.\n\n## PR #54 — Formalization + Reproducibility + Zenodo Publication\n\nThis is the archival/publication phase. It MUST package the reviewed artifacts rather than silently rewriting them.\n\nThe final publication bundle must include the NEXUS 2.0 stable tag/commit, stable source, runnable Lean 4 source from reviewed PR #53, pinned toolchain/Lake metadata, theorem inventory, assumptions/non-claims, axiom audit, formal-gap ranking, runtime correspondence, Lean verification record, final hardening/test summaries, reproduction instructions, SHA-256 manifest, Zenodo metadata and DOI.\n\nA recipient should be able to run `cd LEAN4 && lake build` without editing theorem sources. PR #54 must record the exact NEXUS stable commit and exact PR #53 formalization commit.\n\n'''
sequence = sequence.replace(old_lean_section, new_sections)
sequence_path.write_text(sequence, encoding="utf-8")

roadmap = ROOT / "ROADMAP.md"
text = roadmap.read_text(encoding="utf-8")
old = '''Only after PR #51 is merged and the release-candidate head is green should NEXUS 2.0 be tagged/released as stable.\n\n## PR #52 — Lean 4 Formal Verification\n\nPost-stable verification only:\n\n- freeze the exact NEXUS 2.0 stable tag and commit as the runtime correspondence target;\n- rebase/update the parked Lean project against that exact stable runtime;\n- ship runnable Lean source with pinned toolchain/Lake metadata;\n- formalize selected constitutional and protocol invariants;\n- maintain theorem/lemma inventory, assumptions/non-claims, axiom audit and formal-gap ranking;\n- map each advertised theorem to the tested Python/Rust runtime surface;\n- require the complete selected theorem surface to pass `lake build` with no `sorry`, `admit`, or user-declared proof-substitute axioms.\n\nPR #52 proves the selected formal obligations. It does not publish or silently redefine the already-released runtime.\n\n## PR #53 — Formalization + Reproducibility + Zenodo Publication\n\nArchival/publication phase only:\n\n- package the exact NEXUS 2.0 stable source/tag/commit identity;\n- include the reviewed runnable Lean source from the final PR #52 head without rewriting proofs;\n- bind exact release, formalization, toolchain and checksum identities;\n- include theorem inventory, assumptions/non-claims, axiom audit, formal-gap ranking and runtime correspondence;\n- include final release-hardening/test evidence and reproduction instructions;\n- generate a SHA-256 manifest for the publication payload;\n- publish the reproducibility/formalization record on Zenodo and record the final DOI.\n\nZenodo formalization documents the released system and reviewed proof package. It must not silently redefine either artifact.\n'''
new = '''PR #51 was merged and then subjected to a hostile post-merge Grok audit. Because that audit found release-blocking defects not covered by the green candidate matrix, stable release is deferred to PR #52.\n\n## PR #52 — Post-Merge Grok Audit Closure\n\nFinal pre-stable correction and re-certification only:\n\n- close the operator-visible TUI identity contradiction;\n- harden Secret Scrubbing against case and Unicode-format-control evasions on durable Council/Wall paths;\n- bind hardening reports to exact commit and tree SHA;\n- make the matrix intentionally cover the complete Python test-module inventory;\n- align release-candidate metadata and remove residual alpha-era present-tense wording;\n- eliminate the concurrent dirty-marker race;\n- rerun the complete final release-candidate matrix against the exact candidate head.\n\nOnly after PR #52 is reviewed, merged and green may its exact merge commit be tagged `v2.0.0`.\n\n## PR #53 — Lean 4 Formal Verification\n\nPost-stable verification only. The parked Lean work survives unchanged in purpose; only its planned PR number moves.\n\n- freeze the exact NEXUS 2.0 stable tag and commit as the runtime correspondence target;\n- rebase/update the parked Lean project against that exact stable runtime;\n- ship runnable Lean source with pinned toolchain/Lake metadata;\n- formalize selected constitutional and protocol invariants;\n- maintain theorem/lemma inventory, assumptions/non-claims, axiom audit and formal-gap ranking;\n- map each advertised theorem to the tested Python/Rust runtime surface;\n- require the complete selected theorem surface to pass `lake build` with no `sorry`, `admit`, or user-declared proof-substitute axioms.\n\n## PR #54 — Formalization + Reproducibility + Zenodo Publication\n\nArchival/publication phase only:\n\n- package the exact NEXUS 2.0 stable source/tag/commit identity;\n- include the reviewed runnable Lean source from the final PR #53 head without rewriting proofs;\n- bind exact release, formalization, toolchain and checksum identities;\n- include theorem inventory, assumptions/non-claims, axiom audit, formal-gap ranking and runtime correspondence;\n- include final release-hardening/test evidence and reproduction instructions;\n- generate a SHA-256 manifest for the publication payload;\n- publish the reproducibility/formalization record on Zenodo and record the final DOI.\n\nZenodo formalization documents the released system and reviewed proof package. It must not silently redefine either artifact.\n'''
if old not in text:
    raise SystemExit("ROADMAP post-stable block changed unexpectedly")
text = text.replace(old, new, 1)
text = text.replace(
    "15. the complete PR #51 release-candidate matrix passes again after the BBS Wall is present.",
    "15. the complete PR #51 release-candidate matrix passes after the BBS Wall is present;\n16. the post-merge Grok findings are closed in PR #52 and the commit-bound complete matrix passes again on that exact head.",
    1,
)
text = text.replace(
    "DOCUMENTATION + FINAL RELEASE CANDIDATE - PR #51 - Current\n  ↓\n==============================\n          NEXUS 2.0 STABLE\n==============================\n  ↓\nLEAN 4 FORMAL VERIFICATION - PR #52\n  ↓\nFORMALIZATION + REPRODUCIBILITY + ZENODO - PR #53",
    "DOCUMENTATION + FINAL RELEASE CANDIDATE - PR #51 - Done\n  ↓\nPOST-MERGE GROK AUDIT CLOSURE - PR #52 - Current\n  ↓\n==============================\n          NEXUS 2.0 STABLE\n==============================\n  ↓\nLEAN 4 FORMAL VERIFICATION - PR #53\n  ↓\nFORMALIZATION + REPRODUCIBILITY + ZENODO - PR #54",
    1,
)
roadmap.write_text(text, encoding="utf-8")

checklist = ROOT / "docs" / "RELEASE_CHECKLIST.md"
text = checklist.read_text(encoding="utf-8")
text = text.replace("preserve #52 Lean / #53 Zenodo", "preserve #53 Lean / #54 Zenodo")
text = text.replace("- [ ] PR #51 is reviewed on its exact current head;", "- [ ] PR #52 is reviewed on its exact current head;")
text = text.replace("1. merge PR #51;", "1. merge PR #52;")
text = text.replace("for PR #52 Lean correspondence and PR #53 publication chain of custody", "for PR #53 Lean correspondence and PR #54 publication chain of custody")
insert = "- [ ] the post-merge Grok F1-F5 + RACE1 closure remains 6/6 pinned;\n- [ ] the machine-readable report records exact `git_commit` and `git_tree` identities and the CI expected commit matches checkout HEAD;\n- [ ] the hardening matrix intentionally covers the complete expected Python test-module inventory;\n"
needle = "- [ ] Grok PR #49 R1-R12 closure remains 12/12 pinned;\n"
if needle not in text:
    raise SystemExit("release checklist Grok line missing")
text = text.replace(needle, needle + insert, 1)
checklist.write_text(text, encoding="utf-8")

# SECURITY: state what the strengthened scrubber does, while retaining the
# honest incomplete-DLP boundary.
security = ROOT / "SECURITY.md"
needle = "Authentication material belongs only in adapter authentication or transport fields and must never become semantic prompt content exposed to a model.\n"
addition = "\nBefore durable Council/Wall semantic persistence, the deterministic scrubber now treats high-confidence token prefixes case-insensitively where appropriate and performs a second detection pass with Unicode `Cf` format controls removed, blocking zero-width prefix splitting such as `sk\\u200b-...`. This remains defence in depth rather than general DLP: unknown secret formats still require operator discipline and provider-specific transport boundaries.\n"
text = security.read_text(encoding="utf-8")
if needle not in text:
    raise SystemExit("SECURITY credential boundary insertion point missing")
security.write_text(text.replace(needle, needle + addition, 1), encoding="utf-8")

# Fix concurrent local-audit dirty-marker race.
adversarial_tests = ROOT / "tests" / "test_adversarial_tools.py"
replace_once(adversarial_tests, "import json\n", "import json\nimport os\nimport uuid\n")
replace_once(
    adversarial_tests,
    '        marker = ROOT / ".nexus-gauntlet-dirty-test"',
    '        marker = ROOT / f".nexus-gauntlet-dirty-test-{os.getpid()}-{uuid.uuid4().hex}"',
)

# Existing release tests move with the final candidate.
release_tests = ROOT / "tests" / "test_release_candidate.py"
text = release_tests.read_text(encoding="utf-8")
text = text.replace('self.assertEqual(candidate["base_feature_pr"], 50)', 'self.assertEqual(candidate["feature_surface_through_pr"], 50)\n        self.assertEqual(candidate["scope_through_pr"], 51)')
text = text.replace('self.assertEqual(candidate["candidate_pr"], 51)', 'self.assertEqual(candidate["candidate_pr"], 52)')
text = text.replace('"PR #52 — Lean 4 Formal Verification"', '"PR #53 — Lean 4 Formal Verification"')
text = text.replace('"PR #53 — Formalization + Reproducibility + Zenodo Publication"', '"PR #54 — Formalization + Reproducibility + Zenodo Publication"')
text = text.replace('"## PR #52 — Lean 4 Formal Verification"', '"## PR #53 — Lean 4 Formal Verification"')
text = text.replace('"## PR #53 — Formalization + Reproducibility + Zenodo Publication"', '"## PR #54 — Formalization + Reproducibility + Zenodo Publication"')
text = text.replace('"LEAN 4 FORMAL VERIFICATION - PR #52"', '"LEAN 4 FORMAL VERIFICATION - PR #53"')
text = text.replace('"ZENODO - PR #53"', '"ZENODO - PR #54"')
text = text.replace('self.assertEqual(matrix["milestone"], "PR #51")', 'self.assertEqual(matrix["milestone"], "PR #52")')
text = text.replace('self.assertEqual(matrix["scope_through_pr"], 50)', 'self.assertEqual(matrix["scope_through_pr"], 51)')
text = text.replace('self.assertIn("exact merged PR #51 commit must pass the complete final release-candidate matrix", readme)', 'self.assertIn("exact merged #52 head after the complete release-candidate matrix", readme)')
release_tests.write_text(text, encoding="utf-8")

hardening_tests = ROOT / "tests" / "test_release_hardening.py"
text = hardening_tests.read_text(encoding="utf-8")
text = text.replace('self.assertEqual(matrix["milestone"], "PR #51")', 'self.assertEqual(matrix["milestone"], "PR #52")')
text = text.replace('self.assertEqual(matrix["scope_through_pr"], 50)', 'self.assertEqual(matrix["scope_through_pr"], 51)')
text = text.replace('self.assertIn("exact merged PR #51 head", matrix["release_rule"])', 'self.assertIn("exact merged PR #52 head", matrix["release_rule"])')
hardening_tests.write_text(text, encoding="utf-8")

# Dedicated regression ledger for every post-merge finding.
post_test = ROOT / "tests" / "test_post_merge_grok_audit.py"
if post_test.exists():
    raise SystemExit("post-merge Grok audit test already exists")
post_test.write_text(r'''from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from nexus_runtime import NexusAPI
from nexus_runtime.council import CouncilCoordinator
from nexus_runtime.mock import DeterministicMockActor
from nexus_runtime.scrub import SecretScrubber
from nexus_runtime.types import CouncilMember
from nexus_runtime.world import WorldStore

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    path = ROOT / "tools" / "nexus_release_hardening.py"
    spec = importlib.util.spec_from_file_location("nexus_post_merge_audit_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load hardening runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARDENING = _load_runner()


class PostMergeGrokAuditClosureTests(unittest.TestCase):
    TOKEN_BODY = "abcdefghijklmnopqrstuvwxyz0123"

    def test_f1_tui_banner_uses_cargo_package_version_and_has_no_alpha_identity(self) -> None:
        source = (ROOT / "tui" / "src" / "main.rs").read_text(encoding="utf-8")
        self.assertIn('env!("CARGO_PKG_VERSION")', source)
        self.assertNotIn("NEXUS TUI 2.0 alpha", source)
        self.assertNotIn("alpha10.2", source)

    def test_f2_scrubber_blocks_uppercase_and_unicode_format_control_variants(self) -> None:
        scrubber = SecretScrubber()
        normal = scrubber.scrub("token sk-" + self.TOKEN_BODY)
        upper = scrubber.scrub("token SK-" + self.TOKEN_BODY)
        zwsp = scrubber.scrub("token sk\u200b-" + self.TOKEN_BODY)
        for result in (normal, upper, zwsp):
            self.assertTrue(result.changed)
            self.assertNotIn(self.TOKEN_BODY, result.text)
            self.assertIn("<REDACTED:OPENAI_STYLE_TOKEN:1>", result.text)
        self.assertNotIn("\u200b", zwsp.text)

    def test_f2_wall_and_council_never_persist_bypass_canaries(self) -> None:
        for text in ("token SK-" + self.TOKEN_BODY, "token sk\u200b-" + self.TOKEN_BODY):
            api = NexusAPI()
            posted = api.handle({"operation": "wall.post", "author_id": "operator", "text": text})
            self.assertEqual(posted["status"], "ok")
            self.assertTrue(posted["secret_scrub"]["changed"])
            self.assertNotIn(self.TOKEN_BODY, posted["post"]["payload"]["text"])

            world = WorldStore()
            actors = [
                DeterministicMockActor(CouncilMember(f"M{i}", f"m{i}"))
                for i in range(3)
            ]
            result = CouncilCoordinator(world).run(text, actors)
            stored = world.inspect(result["question_ref"]).payload["text"]
            self.assertNotIn(self.TOKEN_BODY, stored)
            self.assertTrue(result["secret_scrub"]["changed"])

    def test_f3_report_is_bound_to_exact_commit_and_tree(self) -> None:
        checks = [HARDENING.CheckResult(name, "pass", 0.0, "ok") for name in sorted(HARDENING.REQUIRED_CHECK_NAMES)]
        report = HARDENING._build_report(checks)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
        self.assertEqual(report["git_commit"], commit)
        self.assertEqual(report["git_tree"], tree)
        self.assertEqual(HARDENING._commit_binding(commit, commit, tree).status, "pass")
        self.assertEqual(HARDENING._commit_binding("0" * 40, commit, tree).status, "fail")

    def test_f4_matrix_intentionally_covers_full_python_test_inventory(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        detail = HARDENING._audit_matrix_data(matrix, ROOT / "tests")
        inventory = {path for path in (ROOT / "tests").glob("test_*.py") if path.is_file()}
        self.assertEqual(len(inventory), HARDENING.EXPECTED_PYTHON_TEST_FILES)
        self.assertIn(f"{len(inventory)}/{len(inventory)} test files", detail)
        self.assertIn("test_*.py", next(g for g in matrix["gates"] if g["id"] == "release_composition")["patterns"])

    def test_f5_candidate_metadata_uses_scope_vocabulary_and_new_sequence(self) -> None:
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        self.assertNotIn("base_feature_pr", candidate)
        self.assertEqual(candidate["feature_surface_through_pr"], 50)
        self.assertEqual(candidate["scope_through_pr"], 51)
        self.assertEqual(candidate["candidate_pr"], 52)
        self.assertEqual(candidate["post_stable"]["pr_53"], "Lean 4 Formal Verification")
        self.assertIn("Zenodo", candidate["post_stable"]["pr_54"])
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("The alpha10.3 release-prep adds", readme)

    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        closure = matrix["post_merge_audit_closure"]
        self.assertTrue(closure["required_before_stable"])
        self.assertEqual(set(closure["finding_ids"]), HARDENING.REQUIRED_POST_MERGE_FINDING_IDS)
        self.assertEqual(closure["verification"], "tests/test_post_merge_grok_audit.py")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

# Remove the one-shot fixer itself from the final tree.  The workflow file is
# removed separately through the connector because Actions tokens cannot modify
# workflow definitions.
Path(__file__).unlink()
