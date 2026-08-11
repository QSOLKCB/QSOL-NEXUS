# NEXUS Lean 4 Axiom Audit

This document defines the trust boundary for the advertised PR #53 theorem surface.

## Policy

The NEXUS formalization must not make an advertised theorem compile by introducing:

- `sorry`;
- `admit`;
- project-defined `axiom` declarations;
- project-defined bare `constant` declarations used as unproved assumptions.

CI scans the Lean source for those proof-hole/declaration forms before accepting the build.

The formal package also includes `Nexus/AxiomAudit.lean`, which runs Lean's own `#print axioms` command for every theorem listed in `AUDIT_MANIFEST.tsv`.

For this compact constitutional layer, the only imported logical dependencies permitted by the audit runner are:

- no axioms;
- `propext`;
- `Classical.choice`;
- `Quot.sound`.

These are Lean's standard logical/kernel-facing dependencies, not NEXUS-specific assumptions. Any additional dependency printed by an advertised theorem causes `audit.sh` to fail until it is reviewed and the trust boundary is explicitly reconsidered.

## Current observed dependency profile

On the parked branch's final audited 24-theorem surface under Lean 4.33.0:

- **19 theorems depend on no axioms**;
- **5 theorems depend only on `propext`**;
- **0 theorems currently depend on `Classical.choice`**;
- **0 theorems currently depend on `Quot.sound`**;
- **0 advertised theorems depend on a NEXUS-defined axiom**;
- **0 proof holes are present**.

The five observed `propext` users are:

1. `Nexus.no_agi_assumption`
2. `Nexus.consensus_is_not_assumed_truth`
3. `Nexus.identity_is_not_assumed_authority`
4. `Nexus.relief_replacement_does_not_create_extra_seat`
5. `Nexus.civic_proxy_does_not_create_extra_vote`

This profile is observational, not hard-coded as a theorem claim. PR #53 CI regenerates the audit from the transplanted source; PR #54 publication must regenerate/archive the output from the exact reviewed final PR #53 head.

## Advertised declarations

The current audit covers all **24 theorem declarations** in the project:

1. `Nexus.no_agi_assumption`
2. `Nexus.consensus_is_not_assumed_truth`
3. `Nexus.identity_is_not_assumed_authority`
4. `Nexus.one_member_one_vote`
5. `Nexus.provider_independent_vote_weight`
6. `Nexus.model_size_independent_vote_weight`
7. `Nexus.model_identity_independent_vote_weight`
8. `Nexus.identity_creates_no_epistemic_privilege`
9. `Nexus.replacing_model_preserves_seat_weight`
10. `Nexus.every_seat_weight_one`
11. `Nexus.relief_replacement_does_not_create_extra_seat`
12. `Nexus.six_hats_sequence_closed`
13. `Nexus.sealed_phase_payload_immutable`
14. `Nexus.sealed_phase_hat_immutable`
15. `Nexus.two_thirds_definition_is_exact`
16. `Nexus.two_of_three_meets_two_thirds`
17. `Nexus.one_of_three_does_not_meet_two_thirds`
18. `Nexus.consensus_does_not_promote_evidence`
19. `Nexus.citizenship_does_not_change_vote_weight`
20. `Nexus.civic_proxy_does_not_create_extra_vote`
21. `Nexus.progression_creates_no_authority`
22. `Nexus.culture_creates_no_authority`
23. `Nexus.redundancy_creates_no_authority`
24. `Nexus.capability_growth_does_not_change_vote_weight`

The manifest/audit runner requires exact equality between this checked theorem/lemma surface and the machine-readable declaration inventory. An unlisted theorem or a stale manifest entry fails the audit.

## Reproduce the audit

From `formal/lean/` with the pinned Lean toolchain available:

```bash
bash audit.sh
```

The command performs, in order:

1. proof-hole and project-defined axiom/constant source scan;
2. exact theorem/lemma manifest synchronization;
3. `lake build`;
4. direct compilation of `Nexus/Main.lean`;
5. direct compilation of `Nexus/AxiomAudit.lean`;
6. rejection of `sorryAx`;
7. imported-axiom allowlist validation;
8. generation of `formal-verification-report.txt`.

## Runtime and publication binding

The PR #53 formal branch is based directly on merged PR #52 runtime commit:

```text
cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
```

Its expected stable tag is `v2.0.0`. Axiom correctness and runtime correspondence are distinct checks: an axiom-clean theorem can still retain `A/R` status until the runtime source/test/tag binding is complete.

PR #54 must archive the final PR #53 axiom-audit output together with:

- the exact final PR #53 commit SHA;
- the exact NEXUS 2.0 stable tag and runtime commit;
- the pinned Lean version;
- the official Lean release asset digest;
- the theorem/lemma inventory;
- the final stable NEXUS 2.0 runtime correspondence.

The intended publication claim is therefore not merely “the files compiled once.” It is:

> The advertised theorem surface is enumerated, proof-hole scanned, kernel-checked, axiom-dependency audited, and bound to exact formalization, toolchain, and runtime identities.
