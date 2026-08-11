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
    '''        "candidate-tree-unchanged",
    }
)
''',
    '''        "candidate-tree-unchanged",
        "candidate-identity-unchanged",
    }
)
''',
)
replace_once(
    runner,
    '''def _matrix_audit() -> CheckResult:
''',
    '''def _identity_unchanged(expected_commit: str, expected_tree: str) -> CheckResult:
    started = time.monotonic()
    try:
        current_commit, current_tree = _git_identity()
    except Exception as exc:
        return CheckResult(
            "candidate-identity-unchanged",
            "fail",
            time.monotonic() - started,
            f"final git identity unavailable: {type(exc).__name__}: {exc}",
        )
    if current_commit != expected_commit or current_tree != expected_tree:
        return CheckResult(
            "candidate-identity-unchanged",
            "fail",
            time.monotonic() - started,
            (
                "candidate identity changed during hardening: "
                f"started commit={expected_commit} tree={expected_tree}; "
                f"ended commit={current_commit} tree={current_tree}"
            ),
        )
    return CheckResult(
        "candidate-identity-unchanged",
        "pass",
        time.monotonic() - started,
        f"candidate identity remained commit={current_commit}; tree={current_tree}",
    )


def _matrix_audit() -> CheckResult:
''',
)
replace_once(
    runner,
    '''    report = _build_report(checks, git_commit=git_commit, git_tree=git_tree)
''',
    '''    checks.append(_identity_unchanged(git_commit, git_tree))

    report = _build_report(checks, git_commit=git_commit, git_tree=git_tree)
''',
)
replace_once(
    runner,
    '''PR #51 reruns that complete contract against the post-Wall feature surface,
rehearses a clean operator archive, and emits a machine-readable candidate
report.''',
    '''PR #51 reran that complete contract against the post-Wall feature surface.
PR #52 closes the hostile post-merge audit findings, revalidates candidate
identity before and after the matrix, and emits a machine-readable candidate
report.''',
)


tests = "tests/test_post_merge_grok_audit.py"
replace_once(
    tests,
    '''import unittest
''',
    '''import unittest
from unittest import mock
''',
)
replace_once(
    tests,
    '''    def test_f3_ci_requires_github_sha_to_match_checked_commit(self) -> None:
''',
    '''    def test_f3_final_identity_revalidation_rejects_commit_or_tree_drift(self) -> None:
        commit = "1" * 40
        tree = "2" * 40
        with mock.patch.object(HARDENING, "_git_identity", return_value=(commit, tree)):
            self.assertEqual(HARDENING._identity_unchanged(commit, tree).status, "pass")
        with mock.patch.object(HARDENING, "_git_identity", return_value=("3" * 40, tree)):
            changed_commit = HARDENING._identity_unchanged(commit, tree)
        self.assertEqual(changed_commit.status, "fail")
        self.assertIn("identity changed", changed_commit.detail)
        with mock.patch.object(HARDENING, "_git_identity", return_value=(commit, "4" * 40)):
            changed_tree = HARDENING._identity_unchanged(commit, tree)
        self.assertEqual(changed_tree.status, "fail")
        self.assertIn("identity changed", changed_tree.detail)

    def test_f3_ci_requires_github_sha_to_match_checked_commit(self) -> None:
''',
)
replace_once(
    tests,
    '''    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:
''',
    '''    def test_release_surfaces_share_pr52_tag_gate_and_post_stable_sequence(self) -> None:
        surfaces = {
            "SECURITY.md": (ROOT / "SECURITY.md").read_text(encoding="utf-8"),
            "HOWTO.md": (ROOT / "HOWTO.md").read_text(encoding="utf-8"),
            "release notes": (ROOT / "docs" / "RELEASE_NOTES_2.0.0.md").read_text(encoding="utf-8"),
            "changelog": (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        }
        for name, text in surfaces.items():
            self.assertIn("PR #52", text, name)
            self.assertNotIn("exact merged #51", text, name)
        self.assertIn("exact merged PR #52", surfaces["SECURITY.md"])
        self.assertIn("exact merged #52", surfaces["HOWTO.md"])
        self.assertIn("exact merged PR #52", surfaces["release notes"])
        self.assertIn("exact merged PR #52", surfaces["changelog"])
        self.assertIn("PR #53 adds runnable Lean 4", surfaces["release notes"])
        self.assertIn("PR #54 freezes", surfaces["release notes"])
        self.assertIn("post-stable PR #53", surfaces["changelog"])
        self.assertIn("PR #54", surfaces["changelog"])
        for text in surfaces.values():
            self.assertNotIn("post-stable PR #52", text)
            self.assertNotIn("PR #52 adds runnable Lean 4", text)

    def test_post_merge_finding_inventory_is_machine_pinned(self) -> None:
''',
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
    '''- close the hostile post-merge Grok F1-F5/RACE1 audit in PR #52, including exact commit/tree report binding, final identity revalidation, full Python test-module inventory coverage, stronger durable secret scrubbing, and synchronized release-tag instructions;
- reserve post-stable PR #53 for runnable Lean 4 protocol formalization and PR #54 for reproducibility packaging plus Zenodo publication.''',
)
replace_once(
    "CHANGELOG.md",
    '''**Release rule:** this entry describes the intended stable bits. NEXUS 2.0 is not a tagged stable release until PR #51 is merged with every required release/review gate green and that exact commit is tagged `v2.0.0`.''',
    '''**Release rule:** this entry describes the intended stable bits. NEXUS 2.0 is not a tagged stable release until PR #52 is merged with every required commit/tree-bound release and review gate green and that exact merged PR #52 commit is tagged `v2.0.0`.''',
)
