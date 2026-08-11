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

The current branch maintains four separate records rather than collapsing everything into a single “verified” claim:

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

## Release status

This branch is an early future-PR-#52 work branch cut after merged PR #49. It is runnable now, but the runtime-correspondence table must be re-audited against the exact stable NEXUS 2.0 head after PR #50 (Wall) and PR #51 (final release-candidate pass) land.

Items currently proved in the abstract model but awaiting that exact stable binding are marked `A/R`. The publication-facing status is not promoted to plain `A` until the stable source/test correspondence is frozen.
