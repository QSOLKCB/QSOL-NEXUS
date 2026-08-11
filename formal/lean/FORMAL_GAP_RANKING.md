# NEXUS Formal Gap Ranking

This file separates machine-checked protocol claims from unfinished proof obligations, runtime-correspondence work, empirical questions, and explicit non-claims.

The status vocabulary is intentionally terse and auditable:

- **A — formally established.** A Lean theorem is present and kernel-checked.
- **D — defined/targeted, proof outstanding.** The intended obligation is recorded but is not advertised as proved.
- **R — runtime correspondence pending.** The abstract theorem exists, but the exact NEXUS 2.0 stable source/test binding has not yet been frozen.
- **E — empirical.** The proposition is a matter for experiment or evaluation, not theorem proving from the present protocol definitions.
- **N — explicit non-claim.** NEXUS does not assert the proposition.

Statuses may be combined. `A/R`, for example, means the theorem is already proved in the abstract Lean model while the exact stable-runtime correspondence remains to be completed after NEXUS 2.0 is tagged.

## Current formally established surface

| Status | Obligation | Lean declaration |
|---|---|---|
| A | The formal model assumes neither AGI nor AGI existence. | `no_agi_assumption` |
| A | Council consensus is not assumed to be truth. | `consensus_is_not_assumed_truth` |
| A | Provider/model identity is not assumed to create authority. | `identity_is_not_assumed_authority` |
| A/R | Every admitted participant has vote weight exactly one. | `one_member_one_vote` |
| A/R | Provider identity cannot change vote weight. | `provider_independent_vote_weight` |
| A/R | Model parameter count cannot change vote weight. | `model_size_independent_vote_weight` |
| A/R | Model identity cannot change vote weight. | `model_identity_independent_vote_weight` |
| A/R | Model identity creates no epistemic privilege in the formal model. | `identity_creates_no_epistemic_privilege` |
| A/R | Replacing the model in one civic seat preserves seat weight. | `replacing_model_preserves_seat_weight` |
| A/R | Every Council roster seat has weight one. | `every_seat_weight_one` |
| A/R | Failsafe/same-seat relief replacement cannot create an extra seat. | `relief_replacement_does_not_create_extra_seat` |
| A/R | The White→Red→Black→Yellow→Green→Blue sequence is closed. | `six_hats_sequence_closed` |
| A/R | Sealing a hat phase preserves its payload hash. | `sealed_phase_payload_immutable` |
| A/R | Sealing a hat phase preserves its hat identity. | `sealed_phase_hat_immutable` |
| A/R | The two-thirds rule is the exact integer inequality `2*total ≤ 3*yes`. | `two_thirds_definition_is_exact` |
| A/R | Two of three votes meet the two-thirds threshold. | `two_of_three_meets_two_thirds` |
| A/R | One of three votes does not meet the threshold. | `one_of_three_does_not_meet_two_thirds` |
| A/R | A Council outcome alone does not promote evidence. | `consensus_does_not_promote_evidence` |
| A/R | Citizenship status does not change vote weight. | `citizenship_does_not_change_vote_weight` |
| A/R | Civic proxy substitution does not create another vote. | `civic_proxy_does_not_create_extra_vote` |
| A/R | Progression history creates no authority effect. | `progression_creates_no_authority` |
| A/R | Cultural activity creates no authority effect. | `culture_creates_no_authority` |
| A/R | WorldStore redundancy/quorum strength creates no authority effect. | `redundancy_creates_no_authority` |
| A/R | Compute-epoch capability growth does not change vote weight. | `capability_growth_does_not_change_vote_weight` |

## D — formal targets not yet advertised as proved

These are candidate obligations for the post-stable #52 formalization. Recording them here does **not** assert that they have already been proved.

| Status | Candidate obligation |
|---|---|
| D | A full Council session state machine admits only White→Red→Black→Yellow→Green→Blue transitions and cannot mutate committed earlier phases. |
| D | Sealed-ballot commitment/reveal correspondence preserves one-member/one-ballot cardinality. |
| D | Replay under a recorded compute epoch is invariant under later changes to the current epoch policy. |
| D | AI game progression credit requires a matching execution receipt for the claimed model, not merely an AI-labelled seat. |
| D | Content-addressed progression/culture history cannot create constitutional authority through reconstruction or replay. |
| D | WorldStore quorum selection and Ark restoration preserve selected immutable object identities under the formalized recovery model. |
| D | BBS Wall history, once #50 is stable, remains social memory and cannot directly transition evidence or governance authority. |

## R — stable-runtime correspondence work

The current branch was cut before #50 and #51. Therefore the exact post-release binding remains intentionally open.

| Status | Correspondence obligation |
|---|---|
| R | Rebase/update the Lean model against the exact NEXUS 2.0 stable commit. |
| R | Bind every `A/R` theorem to stable Python/Rust source locations. |
| R | Bind every `A/R` theorem to regression tests exercising the corresponding runtime invariant. |
| R | Record the final stable tag, stable commit SHA, and final #52 formalization SHA. |
| R | Re-run the theorem inventory and axiom audit on the final #52 head. |

An `A/R` item may be promoted to `A` in the publication-facing matrix only after this correspondence audit is complete.

## E — empirical questions, not Lean theorems

| Status | Empirical question |
|---|---|
| E | Does Six Hats improve answer quality for a particular task distribution? |
| E | Does a heterogeneous Council outperform a single model on a measured benchmark? |
| E | Does persistent civic/cultural history improve user experience or model cooperation? |
| E | Do psyche-out, game, or performance spaces improve creativity or engagement? |
| E | Does NEXUS produce better real-world decisions than an alternative orchestration protocol? |

These require experiments, datasets, metrics, and statistical analysis. They are not consequences of the present protocol definitions.

## N — explicit non-claims

| Status | Non-claim |
|---|---|
| N | NEXUS proves or creates AGI. |
| N | Council consensus is identical to truth. |
| N | A model is epistemically authoritative because of provider, price, size, openness, benchmark rank, or identity. |
| N | A successful Lean build proves every property of the complete Python/Rust implementation. |
| N | Formal verification of selected protocol invariants proves that model outputs are factually correct. |

## Status-transition discipline

The expected progression is bureaucratically explicit:

```text
D  --proof completed + audited-->  A/R
A/R --stable runtime correspondence frozen--> A
E  --experiment performed--> remains empirical, with evidence recorded elsewhere
N  --> remains a non-claim unless the project constitution is explicitly changed
```

No status is upgraded merely because documentation says so. `A` requires checked Lean source; runtime correspondence requires exact stable source/test references.
