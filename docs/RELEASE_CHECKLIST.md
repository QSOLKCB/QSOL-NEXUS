# NEXUS 2.0 Stable Release Checklist

This checklist is intentionally stricter than “CI is green.” A hardening report verifies a candidate; it does not create release authority.

## Candidate identity

- [ ] PR #50 is merged and the release candidate descends from merge commit `1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b`.
- [ ] Runtime, Python package, Rust TUI, API docs, README, README4AI, and citation metadata identify intended version `2.0.0`.
- [ ] Control protocol remains deliberately identified as `nexus/0.14`.
- [ ] `release/release_candidate.json` matches the intended tag `v2.0.0` and still says `stable_release: false`.

## Documentation reconciliation

- [ ] `ARCHITECTURE.md` describes the implemented Rust TUI, provider federation, WorldStore Continuity/Ark, progression/culture, and BBS Wall.
- [ ] `SECURITY.md` and `THREAT_MODEL.md` describe the current adapter set and Wall/release threats rather than the xAI-only alpha slice.
- [ ] `CLAIMS.md` includes the Wall/progression/culture evidence boundary.
- [ ] `HOWTO.md` documents the current launcher, Wall, and Ark/recovery posture.
- [ ] `README.md` and strict-JSON `README4AI.md` pass their synchronization contract.
- [ ] `ROADMAP.md` and `docs/RELEASE_SEQUENCE.md` preserve #52 Lean / #53 Zenodo as post-stable phases.
- [ ] Historical `archives/v1.0.0/` material remains historical and is not rewritten to impersonate 2.0 documentation.

## Required automated gates

- [ ] candidate-tree pre-audit passes;
- [ ] exact eight-gate matrix audit passes and covers the release-candidate regression family;
- [ ] Grok PR #49 R1-R12 closure remains 12/12 pinned;
- [ ] full Python regression suite passes;
- [ ] 30/30 deterministic adversarial probes pass;
- [ ] Rust all-target tests pass under the pinned release-validation toolchain;
- [ ] `cargo check --all-targets` passes;
- [ ] `cargo fmt --check` passes;
- [ ] clean candidate archive completes `./nexus setup --nick ReleaseProbe -> doctor -> demo` under the allowlisted environment;
- [ ] post-run candidate-tree audit passes;
- [ ] no required check is failed, skipped, missing, or `not_run`.

## Runtime/recovery gates

- [ ] Wall default ephemeral runtime, Unicode/parser boundaries, chronology, tombstones, health, and authority separation regressions pass;
- [ ] representative progression/culture state survives verified Ark create/verify/restore and reconstructs from immutable restored history;
- [ ] Guardian/Failsafe/Citizenship/Trap/Stenographer authority boundaries remain green;
- [ ] provider/credential and fixed-destination tests remain green.

## Review gate

- [ ] PR #51 is reviewed on its exact current head;
- [ ] no unresolved substantive release-blocking review thread remains;
- [ ] any review fix has been revalidated by the complete exact-head matrix.

## Stable tag gate

Only when every item above is satisfied:

1. merge PR #51;
2. rerun/verify the complete matrix against the exact merged commit where applicable;
3. create tag `v2.0.0` pointing to that exact green commit;
4. create the stable GitHub release from the same tag/commit;
5. record the stable tag and commit for PR #52 Lean correspondence and PR #53 publication chain of custody.

> **Do not move the tag to make paperwork match. Make the paperwork match the tested commit.**
