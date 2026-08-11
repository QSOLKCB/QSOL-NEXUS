from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


runner = "tools/nexus_release_hardening.py"
replace_once(
    runner,
    '        "candidate-tree-unchanged",\n',
    '        "candidate-tree-unchanged",\n        "candidate-identity-unchanged",\n',
)
replace_once(
    runner,
    '''def _matrix_audit() -> CheckResult:\n''',
    '''def _identity_unchanged(expected_commit: str, expected_tree: str) -> CheckResult:\n    started = time.monotonic()\n    try:\n        current_commit, current_tree = _git_identity()\n    except Exception as exc:\n        return CheckResult(\n            "candidate-identity-unchanged",\n            "fail",\n            time.monotonic() - started,\n            f"final git identity unavailable: {type(exc).__name__}: {exc}",\n        )\n    if current_commit != expected_commit or current_tree != expected_tree:\n        return CheckResult(\n            "candidate-identity-unchanged",\n            "fail",\n            time.monotonic() - started,\n            (\n                "candidate identity changed during hardening: "\n                f"started commit={expected_commit} tree={expected_tree}; "\n                f"ended commit={current_commit} tree={current_tree}"\n            ),\n        )\n    return CheckResult(\n        "candidate-identity-unchanged",\n        "pass",\n        time.monotonic() - started,\n        f"candidate identity remained commit={current_commit}; tree={current_tree}",\n    )\n\n\ndef _matrix_audit() -> CheckResult:\n''',
)
replace_once(
    runner,
    '''    report = _build_report(checks, git_commit=git_commit, git_tree=git_tree)\n''',
    '''    checks.append(_identity_unchanged(git_commit, git_tree))\n\n    report = _build_report(checks, git_commit=git_commit, git_tree=git_tree)\n''',
)
replace_once(
    runner,
    '''PR #51 reruns that complete contract against the post-Wall feature surface,\nrehearses a clean operator archive, and emits a machine-readable candidate\nreport.''',
    '''PR #51 reran that complete contract against the post-Wall feature surface.\nPR #52 closes the hostile post-merge audit findings, revalidates candidate\nidentity before and after the matrix, and emits a machine-readable candidate\nreport.''',
)


tests = "tests/test_post_merge_grok_audit.py"
replace_once(
    tests,
    '''import unittest\n''',
    '''import unittest\nfrom unittest import mock\n''',
)
replace_once(
    tests,
    '''    def test_f3_ci_requires_github_sha_to_match_checked_commit(self) -> None:\n''',
    '''    def test_f3_final_identity_revalidation_rejects_commit_or_tree_drift(self) -> None:\n        commit = "1" * 40\n        tree = "2" * 40\n        with mock.patch.object(HARDENING, "_git_identity", return_value=(commit, tree)):\n            self.assertEqual(HARDENING._identity_unchanged(commit, tree).status, "pass")\n        with mock.patch.object(HARDENING, "_git_identity", return_value=("3" * 40, tree)):\n            changed_commit = HARDENING._identity_unchanged(commit, tree)\n        self.assertEqual(changed_commit.status, "fail")\n        self.assertIn("identity changed", changed_commit.detail)\n        with mock.patch.object(HARDENING, "_git_identity", return_value=(commit, "4" * 40)):\n            changed_tree = HARDENING._identity_unchanged(commit, tree)\n        self.assertEqual(changed_tree.status, "fail")\n        self.assertIn("identity changed", changed_tree.detail)\n\n    def test_f3_ci_requires_github_sha_to_match_checked_commit(self) -> None:\n''',
)
replace_once(
    tests,
    '''    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:\n''',
    '''    def test_release_surfaces_share_pr52_tag_gate_and_post_stable_sequence(self) -> None:\n        surfaces = {\n            "SECURITY.md": (ROOT / "SECURITY.md").read_text(encoding="utf-8"),\n            "HOWTO.md": (ROOT / "HOWTO.md").read_text(encoding="utf-8"),\n            "release notes": (ROOT / "docs" / "RELEASE_NOTES_2.0.0.md").read_text(encoding="utf-8"),\n            "changelog": (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),\n        }\n        for name, text in surfaces.items():\n            self.assertIn("PR #52", text, name)\n            self.assertNotIn("exact merged #51", text, name)\n        self.assertIn("exact merged PR #52", surfaces["SECURITY.md"])\n        self.assertIn("exact merged #52", surfaces["HOWTO.md"])\n        self.assertIn("exact merged PR #52", surfaces["release notes"])\n        self.assertIn("exact merged PR #52", surfaces["changelog"])\n        self.assertIn("PR #53 adds runnable Lean 4", surfaces["release notes"])\n        self.assertIn("PR #54 freezes", surfaces["release notes"])\n        self.assertIn("post-stable PR #53", surfaces["changelog"])\n        self.assertIn("PR #54", surfaces["changelog"])\n        for text in surfaces.values():\n            self.assertNotIn("post-stable PR #52", text)\n            self.assertNotIn("PR #52 adds runnable Lean 4", text)\n\n    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:\n''',
)


replace_once(
    "SECURITY.md",
    '''PR #51 aligns the intended `2.0.0` bits but does not self-authorize a stable release. The stable tag is permitted only from the exact merged #51 commit after full Python/Rust, adversarial/security, clean-archive bootstrap, WorldStore/Ark recovery, Grok R1-R12 closure, Wall-boundary, documentation-coupling, and review gates pass. The hardening report itself has `authority_effect: none` and `stable_release: false`.''',
    '''PR #51 aligned the intended `2.0.0` bits, but the hostile post-merge audit found release-blocking gaps and PR #52 is now the final pre-stable audit-closure candidate. The stable tag is permitted only from the exact merged PR #52 commit after full Python/Rust, adversarial/security, clean-archive bootstrap, WorldStore/Ark recovery, Grok R1-R12 closure, post-merge F1-F5/RACE1 closure, Wall-boundary, documentation-coupling, exact commit/tree identity revalidation, and review gates pass. The hardening report itself has `authority_effect: none` and `stable_release: false`.''',
)
replace_once(
    "HOWTO.md",
    '''The repository itself is the NEXUS 2.0 launcher. PR #45 introduced the operator tooling; PR #51 reconciles it with the final post-Wall release candidate.''',
    '''The repository itself is the NEXUS 2.0 launcher. PR #45 introduced the operator tooling; PR #51 reconciled it with the post-Wall release candidate, and PR #52 closes the hostile post-merge audit findings before stable release.''',
)
replace_once(
    "HOWTO.md",
    '''The current #51 branch identifies the intended stable bits as `2.0.0`, but the stable tag is not implied by a version string. Use `./nexus version` and `./nexus doctor` to verify the local checkout; the repository release is stable only once the exact merged #51 head is green and tagged `v2.0.0`.''',
    '''The current PR #52 candidate identifies the intended stable bits as `2.0.0`, but the stable tag is not implied by a version string. Use `./nexus version` and `./nexus doctor` to verify the local checkout; the repository release is stable only once the exact merged #52 head passes the complete commit/tree-bound release and review gates and is tagged `v2.0.0`.''',
)
replace_once(
    "docs/RELEASE_NOTES_2.0.0.md",
    '''These are the final release-candidate notes for the intended `v2.0.0` bits. They become stable release notes only when the exact merged PR #51 commit passes the complete release/review gate and is tagged `v2.0.0`.''',
    '''These are the final release-candidate notes for the intended `v2.0.0` bits. They become stable release notes only when the exact merged PR #52 commit passes the complete commit/tree-bound release and review gate and is tagged `v2.0.0`.''',
)
replace_once(
    "docs/RELEASE_NOTES_2.0.0.md",
    '''PR #49 created the eight-gate hardening harness. An independent Grok audit found R1-R12; surviving findings were fixed before the Wall and pinned as release-blocking regressions. PR #50 then passed the post-Wall matrix plus Codex review fixes. PR #51 reruns that complete contract against the exact intended stable tree.''',
    '''PR #49 created the eight-gate hardening harness. An independent Grok audit found R1-R12; surviving findings were fixed before the Wall and pinned as release-blocking regressions. PR #50 then passed the post-Wall matrix plus Codex review fixes. PR #51 reran that complete contract, and a hostile post-merge Grok audit then exposed F1-F5 plus RACE1. PR #52 closes those findings, inventories the full Python test-module surface, binds the report to the exact candidate commit/tree, and revalidates that identity after the long matrix before any stable tag is allowed.''',
)
replace_once(
    "docs/RELEASE_NOTES_2.0.0.md",
    '''PR #52 adds runnable Lean 4 formal verification for selected constitutional/protocol invariants against the exact stable runtime. PR #53 freezes the reviewed proof sources, stable software identity, build/test records, hashes, reproduction instructions, and Zenodo DOI.''',
    '''PR #53 adds runnable Lean 4 formal verification for selected constitutional/protocol invariants against the exact stable runtime. PR #54 freezes the reviewed proof sources, stable software identity, build/test records, hashes, reproduction instructions, and Zenodo DOI.''',
)
replace_once(
    "CHANGELOG.md",
    '''- reserve post-stable PR #52 for runnable Lean 4 protocol formalization and PR #53 for reproducibility packaging plus Zenodo publication.''',
    '''- close the hostile post-merge Grok F1-F5/RACE1 audit in PR #52, including exact commit/tree report binding, final identity revalidation, full Python test-module inventory coverage, stronger durable secret scrubbing, and synchronized release-tag instructions;\n- reserve post-stable PR #53 for runnable Lean 4 protocol formalization and PR #54 for reproducibility packaging plus Zenodo publication.''',
)
replace_once(
    "CHANGELOG.md",
    '''**Release rule:** this entry describes the intended stable bits. NEXUS 2.0 is not a tagged stable release until PR #51 is merged with every required release/review gate green and that exact commit is tagged `v2.0.0`.''',
    '''**Release rule:** this entry describes the intended stable bits. NEXUS 2.0 is not a tagged stable release until PR #52 is merged with every required commit/tree-bound release and review gate green and that exact merged PR #52 commit is tagged `v2.0.0`.''',
)
