# NEXUS 2.0 Release Sequence

This file records the final numbered sequence agreed after PR #46 merged. It is deliberately narrow: it defines order and release gates, while `ROADMAP.md` retains the broader architectural history.

```text
PR #47 — AI Progression & Civic Life
        ↓
PR #48 — NEXUS 2.0 Hardening
        ↓
PR #49 — The BBS Wall
        ↓
PR #50 — Documentation, Release Candidate & Stable Release Prep
        ↓
NEXUS 2.0 STABLE RELEASE
        ↓
PR #51 — Formalization & Zenodo Publication
```

## PR #47 — AI Progression & Civic Life

Give AI inhabitants persistent non-voting things to do in the world:

- Explore, Research, Create, Critique, Curate, Mentor, Collaborate, Steward and Chronicle;
- bounded commissions;
- immutable activity portfolios;
- descriptive milestones and roles with zero authority effect;
- validated Monopoly economic play using the existing deterministic NEXUS table;
- original NEXUS Life Paths long-horizon choice simulation;
- persistent play/activity lineage protected by WorldStore Continuity.

Gate:

> **Contribution history is not governance authority.**

## PR #48 — NEXUS 2.0 Hardening

Run the formal pre-release hardening matrix against the complete foundation through #47:

- adapter and credential threat-model audit;
- Secret Scrubber bypass/fuzz fixtures;
- provider isolation, destination and failure behavior;
- replay/tamper/migration fixtures;
- Council loop and deterministic-policy bounds;
- TUI state/transcript/redaction checks;
- operator bootstrap/doctor/path/symlink hardening;
- WorldStore quorum/scrub/Ark/recovery corruption fixtures;
- progression lineage/index/commission/play attribution hardening;
- representative pre-beta world upgrade/recovery rehearsal.

PR #48 is not itself the stable release. It establishes a reviewed hardening baseline before the last social-world feature and final release candidate pass.

## PR #49 — The BBS Wall

Add the post-hardening social memory surface:

- old-school BBS-style public Wall;
- short bounded chronological notes from humans and models;
- immutable WorldStore-backed history;
- contextual identity labels only, never rank;
- Wall speech is social memory, not evidence;
- no Council vote, consensus or truth promotion;
- moderation through explicit historical records/tombstones where policy permits.

Gate:

> **The Wall remembers speech. It does not turn speech into truth.**

Because #49 changes the final stable feature surface after the main hardening pass, PR #50 MUST rerun the complete release-candidate regression matrix rather than relying solely on #48 results.

## PR #50 — Documentation, Release Candidate & Stable Release Prep

Update and reconcile all stable-release documentation and machine-readable contracts, including at minimum:

- `README.md`;
- `README4AI.md`;
- `ROADMAP.md`;
- operator/HOWTO material;
- architecture and threat-model docs;
- Ark/recovery docs;
- Progression/Life Paths docs;
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
- final check that #49 introduced no regression against #48's hardening guarantees.

Only after PR #50 is merged and the release-candidate head is green should NEXUS 2.0 be tagged/released as stable.

## PR #51 — Formalization & Zenodo Publication

This is explicitly **post-release** work.

After the stable 2.0 release exists:

- freeze the released source/version identity;
- formalize the architecture and protocol description;
- prepare archival metadata;
- bind the exact release/tag/commit and relevant checksums;
- publish the formal NEXUS 2.0 record on Zenodo;
- record the resulting DOI back into project documentation in a later archival/documentation change if required.

Zenodo formalization documents the released system. It MUST NOT silently redefine the already-released runtime or constitutional contract.

## Release principle

> **Build the life of the world, harden the substrate, add the social wall, document the exact thing we are shipping, release it, then archive what actually shipped.**
