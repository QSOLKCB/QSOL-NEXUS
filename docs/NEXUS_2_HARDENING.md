# NEXUS 2.0 Hardening — PR #49

> **Historical-to-final note:** PR #49 established the pre-Wall baseline. PR #51 reruns the same hardened contract as a final release-candidate profile scoped through merged PR #50.

PR #49 is the formal **pre-Wall hardening baseline** for NEXUS 2.0.

It runs only after the complete foundation through PR #48 exists: Council, persistence, operator tooling, continuity/Ark recovery, Citizenship/Civic Due Process, AI Progression & Civic Life, The Long Shift, Open Mic and Psyche-Out Chess.

> **Hardening verifies boundaries. It does not create authority.**

PR #49 does **not** declare NEXUS 2.0 stable. PR #50 still adds the BBS Wall, and PR #51 must rerun the complete release-candidate matrix against that final feature surface before the stable tag.

## Machine-readable matrix

The authoritative PR #49 test inventory is:

```text
release/hardening_matrix.json
```

Schema:

```text
nexus-release-hardening-matrix/1
```

The matrix is intentionally closed around eight required gates:

1. adapter and credential boundaries;
2. Council and authority invariants;
3. operator bootstrap;
4. WorldStore Continuity / Ark durability;
5. AI Progression & Civic Life;
6. AI culture, RPG and Psyche-Out Chess;
7. Trap Base / civic durability;
8. release composition.

`tools/nexus_release_hardening.py` pins the exact eight gate IDs in code. Deleting or replacing a required gate therefore fails the audit even when the surviving gates still have valid tests.

Every declared test pattern must also match at least one real test file independently. A gate does not remain green merely because some other pattern in that gate still matches. This prevents a future refactor from silently deleting a named critical regression family while leaving a stale green “hardening” label behind.

## One-command hardening runner

Run:

```bash
PYTHONPATH=src python3 tools/nexus_release_hardening.py \
  --iterations 128 \
  --json-out /tmp/nexus-release-hardening.json
```

The runner performs:

- clean candidate-worktree audit;
- hardening-matrix integrity/coverage audit;
- complete Python `unittest` regression suite;
- deterministic NEXUS adversarial probes;
- Rust TUI tests;
- Rust compile/check;
- `cargo fmt --check`;
- fresh candidate archive operator rehearsal;
- final worktree audit proving the checked candidate remained aligned with `HEAD`.

The machine-readable result uses:

```text
nexus-release-hardening-report/1
```

The report records test results only. It is not evidence promotion, constitutional authority, a Council vote, or permission to call an unreleased build stable.

Required checks may be deliberately skipped for local diagnostics with `--skip-rust` or `--skip-operator`, but such a run is explicitly recorded as `status: incomplete`, `complete: false`, and `passed: false`, and exits unsuccessfully. Skip flags therefore cannot manufacture a valid pre-Wall hardening result.

## Candidate identity and clean-worktree rule

PR #49 requires the working tree to match `HEAD` before the release matrix begins.

This prevents one report from running Python/Rust/adversarial checks against local tracked edits or untracked release inputs while `git archive HEAD` rehearses a different committed candidate. The runner checks the worktree again after the matrix to catch test-time mutation of tracked or unignored files.

Ignored build/cache artifacts remain governed by their existing repository rules; they do not redefine the candidate source tree.

## Fresh candidate operator rehearsal

PR #49 deliberately tests more than the current working directory.

The hardening runner creates a clean `git archive` of the exact candidate tree in an isolated temporary directory and executes:

```text
./nexus setup --nick ReleaseProbe
./nexus doctor
./nexus demo
```

This exercises the reviewed PR #45 bootstrap path with no pre-existing `.venv`, operator config, WorldStore, Trap Base or Stenographer state from the development checkout.

Before executing the archived candidate, the rehearsal strips inherited `NEXUS_*` path/bootstrap overrides plus `PYTHONPATH`, `PYTHONHOME` and `VIRTUAL_ENV`. In particular, an external `NEXUS_VENV` cannot cause the candidate to reuse an already-installed runtime from another checkout.

The rehearsal verifies that the candidate can bootstrap its local environment, build the TUI, pass Doctor, and execute a deterministic mock Council demo through the supported one-command operator surface.

It does not contact a cloud model provider and does not claim live-provider acceptance.

## Representative persistent-world recovery rehearsal

`tests/test_release_hardening.py` creates representative durable state using the public PR #48 runtime, including:

- an Open Mic performance;
- its immutable AI progression activity/state lineage;
- an ordinary persistent WorldStore object.

The test then:

1. creates and verifies a World Ark;
2. restores the Ark into a **new** target;
3. opens a fresh NEXUS runtime over the restored target;
4. verifies the ordinary object survives;
5. reconstructs the exact AI progression state from restored immutable history even though mutable progression cache files were not the authority being archived.

This is specifically meant to catch cross-feature failures where WorldStore recovery succeeds at the byte level but higher-level history can no longer be reconstructed.

## New PR #49 release-composition attacks

PR #49 adds dedicated regressions for:

- expected progression/culture/continuity operations disappearing from the final public runtime overlay;
- progression, culture or Ark policy accidentally acquiring governance/evidence authority;
- malformed new culture/progression/continuity operations mutating WorldStore before failing;
- credential-shaped material entering durable culture state;
- generic `world.create` forging PR #48 runtime-owned culture/game/execution objects;
- the test independently pinning the complete PR #48 reserved-object literal set rather than trusting the production set it is policing;
- Ark restore failing to reconstruct a progression portfolio from immutable history;
- the hardening matrix itself falsely declaring a stable release;
- missing required gate IDs or individual test-pattern families;
- required skip flags being misreported as a passing complete run;
- inherited NEXUS/Python environment overrides contaminating the clean operator rehearsal;
- dirty working trees making ordinary checks and the archived bootstrap target different candidates.

These tests supplement rather than replace the feature-specific tests added in PRs #1–#48.

## Existing hardening families retained

The formal matrix deliberately reuses the existing executable regressions for:

- provider fixed-destination and local-loopback boundaries;
- authentication storage and credential isolation;
- Secret Scrubber output/input boundaries;
- one-seat/one-vote and sealed Council mechanics;
- bounded control-plane requests and timeouts;
- ordered parallel Council equivalence;
- launcher path/symlink/config permission protections;
- WorldStore quorum, HEAD rollback, scrub, repair, Ark tamper detection and non-destructive restore;
- Stenographer fail-passive durability;
- Guardian zero-authority observation;
- Trap Base mutation locking and crash recovery;
- Civic Due Process and Citizenship persistence;
- progression lineage/cache/commission/play attribution;
- Long Shift deterministic replay and execution receipts;
- Open Mic performance/evidence separation;
- Psyche-Out Chess legality, untrusted banter and model-execution attribution.

Hardening is therefore a **composition test over the accumulated architecture**, not a replacement implementation of those subsystems.

## Failure policy

A PR #49 hardening failure means the candidate is not ready to establish the pre-Wall baseline.

Failures must not be hidden by:

- deleting a matrix gate;
- deleting one declared critical test pattern while leaving sibling patterns green;
- skipping required Rust/operator checks and reporting a complete pass;
- running different release checks against different candidate trees;
- weakening a constitutional invariant;
- turning an integrity failure into a warning merely to make CI green;
- inventing WorldStore history to remain writable;
- silently disabling a Secret Scrubber or provider boundary;
- labeling stochastic/live behavior replayable when it is not.

A test may be corrected when the test itself encoded an obsolete or invalid contract, but the reason must be reviewable in the PR.

## Post-Wall requirement

PR #50 intentionally adds one final social-world feature after this hardening baseline.

Therefore:

> **PR #51 MUST rerun the complete release-candidate matrix against the exact post-Wall stable candidate.**

A green PR #49 is necessary but not sufficient for NEXUS 2.0 stable.
