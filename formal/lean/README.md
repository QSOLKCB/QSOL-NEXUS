# NEXUS Lean 4 Formalization

This directory is a runnable Lean 4 project for selected NEXUS protocol invariants.

It is intentionally **not** a proof that NEXUS answers are true, that Six Hats improves model quality, that consensus is correct, or that AGI exists. It formalizes protocol properties around bounded, fallible participants.

## Reproduce

Install `elan` using the official Lean installation instructions, then from this directory run:

```bash
lake build
```

The checked-in `lean-toolchain` pins the exact Lean release. Lake will use that toolchain automatically.

For the full declaration/axiom audit, run:

```bash
bash audit.sh
```

That command checks manifest completeness, rejects proof holes and project-defined axiom/constant declarations, builds the project, compiles the aggregate theorem module, runs `#print axioms` across every advertised theorem, validates the imported-axiom allowlist, and writes `formal-verification-report.txt`.

## Bureaucratic proof surface

The project maintains four separate records rather than collapsing everything into a single “verified” claim:

- `THEOREMS_AND_LEMMAS.md` — exhaustive human-readable declaration inventory with full signatures;
- `AUDIT_MANIFEST.tsv` — machine-readable declaration ledger checked against the Lean source;
- `FORMAL_GAP_RANKING.md` — `A / D / R / E / N` status matrix separating proved, outstanding, correspondence, empirical, and explicit non-claims;
- `AXIOM_AUDIT.md` — proof-hole and axiom trust boundary, backed by `Nexus/AxiomAudit.lean`.

Current declaration count:

- **24 theorems**
- **0 lemmas**

CI fails if the Lean theorem/lemma set and `AUDIT_MANIFEST.tsv` drift apart.

## Proof-hole policy

The formalization is intended to contain no `sorry`, `admit`, project-defined `axiom`, or bare project-defined `constant` used in place of a proof. CI scans for those forms before accepting the formal audit.

`Nexus/AxiomAudit.lean` additionally asks Lean to print the dependency axioms for every advertised theorem. The current compact constitutional layer admits only empty dependency sets or Lean's standard `propext`, `Classical.choice`, and `Quot.sound` dependencies; the audit runner rejects anything else pending explicit review.

## Current scope

The initial theorem set covers:

- explicit non-assumption of AGI, consensus-as-truth, and identity-as-authority;
- one member = one vote;
- provider/model-size/model-identity independence of vote weight;
- same-seat replacement without seat creation;
- closed Six Hats sequencing;
- immutable sealed phase identity/payload;
- exact integer two-thirds threshold examples and definition;
- consensus/evidence separation;
- Citizenship and proxy non-expansion of voting weight;
- progression/culture/redundancy creating no authority;
- temporal compute growth not changing vote weight.

See `THEOREMS_AND_LEMMAS.md`, `FORMAL_GAP_RANKING.md`, `AXIOM_AUDIT.md`, `ASSUMPTIONS_AND_NONCLAIMS.md`, and `RUNTIME_CORRESPONDENCE.md`.

## PR #53 runtime boundary

PR #53 is the post-release-line formal-verification layer. This branch is based **directly** on the exact merged PR #52 commit:

```text
cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
```

That commit is the repository's designated `v2.0.0` stable-tag candidate. At creation of this PR #53 branch, the `v2.0.0` tag had not yet been published, so the formalization does not pretend otherwise. Before PR #53 is marked ready for final merge, the tag-binding gate must confirm that `v2.0.0` resolves to that exact commit.

The Lean source was transplanted from the parked `agent/pr52-lean4-formal-verification` work after PR #52 displaced the original numbering. The parked branch's final Lean CI was green before transplant. PR #53 preserves that proof surface and rebinds its documentation and CI to the merged #52 runtime.

Items proved in the abstract model but still awaiting the final stable-tag/runtime correspondence freeze remain marked `A/R`. They are not promoted to plain `A` merely because the source compiles.

PR #53 does **not** change NEXUS runtime semantics. Its dedicated workflow rejects branch changes outside `formal/lean/**` and `.github/workflows/lean-formal.yml` relative to the exact merged PR #52 runtime base.
