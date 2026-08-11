# NEXUS 2.0 Release Sequence

This file records the final numbered sequence agreed after PR #49 merged. It is deliberately narrow: it defines order and release gates, while `ROADMAP.md` retains the broader architectural history.

```text
PR #47 — AI Progression & Civic Life — MERGED
        ↓
PR #48 — AI Culture, Performance & Psyche-Out Play — MERGED
        ↓
PR #49 — NEXUS 2.0 Hardening — MERGED
        ↓
PR #50 — The BBS Wall — MERGED
        ↓
PR #51 — Documentation, Release Candidate & Stable Release Prep — MERGED
        ↓
PR #52 — Post-Merge Grok Audit Closure — THIS RELEASE CANDIDATE
        ↓
NEXUS 2.0 STABLE RELEASE
        ↓
PR #53 — Lean 4 Formal Verification
        ↓
PR #54 — Formalization + Reproducibility + Zenodo Publication
```

## PR #47 — AI Progression & Civic Life

Merged foundation for persistent non-voting AI life in NEXUS:

- Explore, Research, Create, Critique, Curate, Mentor, Collaborate, Steward and Chronicle;
- bounded commissions;
- immutable activity portfolios;
- descriptive milestones and roles with zero authority effect;
- validated Monopoly economic play using the existing deterministic NEXUS table;
- original NEXUS Life Paths long-horizon choice simulation;
- persistent play/activity lineage protected by WorldStore Continuity.

Gate:

> **Contribution history is not governance authority.**

## PR #48 — AI Culture, Performance & Psyche-Out Play

Merged culture layer adding original AI-first comedy/science-fiction roleplay, Open Mic performance, and Psyche-Out Chess while preserving the authority boundary.

Gate:

> **Freedom to perform is not freedom to rewrite authority.**

## PR #49 — NEXUS 2.0 Hardening

Merged pre-release hardening baseline covering the complete feature surface through #48, including adapter/credential boundaries, operator bootstrap, WorldStore/Ark recovery, progression/culture/play provenance, adversarial testing, and a machine-readable pre-Wall release-hardening gate.

PR #49 is not itself the stable release. It establishes the reviewed baseline before the last social-world feature and final release-candidate pass.

Gate:

> **Hardening verifies boundaries. It does not create authority.**

## PR #50 — The BBS Wall

Merged post-hardening social memory surface:

- old-school BBS-style public Wall;
- short bounded chronological notes from humans and models;
- immutable WorldStore-backed history;
- contextual identity labels only, never rank;
- Wall speech is social memory, not evidence;
- no Council vote, consensus or truth promotion;
- moderation through explicit historical records/tombstones where policy permits.

Gate:

> **The Wall remembers speech. It does not turn speech into truth.**

Because #50 changes the final stable feature surface after the main hardening pass, PR #51 MUST rerun the complete release-candidate regression matrix rather than relying solely on #49 results.

## PR #51 — Documentation, Release Candidate & Stable Release Prep

Update and reconcile all stable-release documentation and machine-readable contracts, including at minimum:

- `README.md`;
- `README4AI.md`;
- `ROADMAP.md`;
- operator/HOWTO material;
- architecture and threat-model docs;
- Ark/recovery docs;
- Progression/Life Paths docs;
- AI culture/performance/RPG/Psyche-Out Chess docs;
- BBS Wall docs;
- version/release notes and compatibility statements.

Then run the final release candidate rehearsal against the exact intended stable head:

- full Python regression suite;
- Rust TUI tests and formatting;
- adversarial/security gauntlets;
- README dual-surface contract;
- fresh clone -> `./nexus` bootstrap/doctor/TUI launch;
- representative persistent-world upgrade;
- Ark creation, verification and non-destructive restore;
- final check that #50 introduced no regression against #49's hardening guarantees.

PR #51 merged successfully and produced a green candidate, but the subsequent hostile post-merge Grok audit found release-blocking gaps outside the prior test boundary. Stable release therefore remains withheld until PR #52 closes those findings and re-certifies the exact candidate.

## PR #52 — Post-Merge Grok Audit Closure

A hostile audit of the exact merged PR #51 commit found defects that existing green CI did not cover. Stable release is therefore deferred until this closure PR is reviewed and green.

Required closure:

- derive the operator-visible Rust TUI version from Cargo package metadata;
- harden Secret Scrubbing against case variants and Unicode `Cf` / zero-width prefix splitting before Wall/Council persistence;
- bind the machine-readable hardening report to exact Git commit and tree identities;
- intentionally inventory the complete Python test-module surface;
- align release-candidate metadata vocabulary and remove residual present-tense alpha wording;
- eliminate the fixed dirty-marker race observed under concurrent audit execution;
- rerun the complete release-candidate matrix on the exact PR #52 head.

Gate:

> **An external audit finding outranks the planned sequence. Fix the candidate before proving the candidate.**

Only the exact merged PR #52 commit may become `v2.0.0`, and only after the complete matrix/review gate passes.

## PR #53 — Lean 4 Formal Verification

This is explicitly **post-stable-release verification work**. The previously parked Lean work is retained, but its PR number moves because the post-merge audit closure consumed #52.

After the NEXUS 2.0 stable tag and commit exist:

- rebase/update the formalization against the exact stable runtime head;
- ship a complete runnable Lean project, not isolated snippets;
- pin the Lean toolchain and compiler release identity;
- formalize selected constitutional and protocol invariants;
- maintain an explicit theorem inventory, axiom audit and formal-gap ranking;
- maintain assumptions and non-claims;
- map formal theorems to the stable Python/Rust implementation and regression tests;
- prohibit `sorry`, `admit`, or user-declared axioms as substitutes for advertised proofs;
- require `lake build` to machine-check the complete selected theorem surface in CI.

The intended claim remains narrow:

> **Selected constitutional and protocol invariants of NEXUS 2.0 are machine-checked in Lean 4 against an explicit formal model, with correspondence to the tested stable runtime.**

PR #53 MUST leave the reviewed runnable Lean source available for independent reproduction.

## PR #54 — Formalization + Reproducibility + Zenodo Publication

This is the archival/publication phase. It MUST package the reviewed artifacts rather than silently rewriting them.

The final publication bundle must include the NEXUS 2.0 stable tag/commit, stable source, runnable Lean 4 source from reviewed PR #53, pinned toolchain/Lake metadata, theorem inventory, assumptions/non-claims, axiom audit, formal-gap ranking, runtime correspondence, Lean verification record, final hardening/test summaries, reproduction instructions, SHA-256 manifest, Zenodo metadata and DOI.

A recipient should be able to run `cd LEAN4 && lake build` without editing theorem sources. PR #54 must record the exact NEXUS stable commit and exact PR #53 formalization commit.

## Release principle

> **Build the life and culture of the world, harden the substrate, add the social wall, document the candidate, close independent audit findings before release, prove selected invariants against the stable system, then archive the software + runnable proofs + reproducibility record together.**
