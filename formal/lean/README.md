# NEXUS Lean 4 Formalization

This directory is a runnable Lean 4 project for selected NEXUS protocol invariants.

It is intentionally **not** a proof that NEXUS answers are true, that Six Hats improves model quality, that consensus is correct, or that AGI exists. It formalizes protocol properties around bounded, fallible participants.

## Reproduce

Install `elan` using the official Lean installation instructions, then from this directory run:

```bash
lake build
```

The checked-in `lean-toolchain` pins the exact Lean release. Lake will use that toolchain automatically.

A successful build checks every theorem imported by `Nexus.lean`.

## Proof-hole policy

The formalization is intended to contain no `sorry`, `admit`, or user-declared `axiom`. CI scans for those tokens before building and also invokes Lean's checker through the official Lean GitHub action.

## Current scope

The initial theorem set covers:

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

See `THEOREMS.md`, `ASSUMPTIONS_AND_NONCLAIMS.md`, and `RUNTIME_CORRESPONDENCE.md`.

## Release status

This branch is an early future-PR-#52 work branch cut after merged PR #49. It is runnable now, but the runtime-correspondence table must be re-audited against the exact stable NEXUS 2.0 head after PR #50 (Wall) and PR #51 (final release-candidate pass) land.
