# NEXUS Lean 4 — Theorems and Lemmas

This is the exhaustive declaration inventory for the current NEXUS formalization branch.

Current count:

- **24 theorems**
- **0 lemmas**
- **12 subject modules**

`AUDIT_MANIFEST.tsv` is machine-audited in CI. If a theorem or lemma is added, removed, or renamed without updating the manifest, the formal audit fails.

Status notation follows `FORMAL_GAP_RANKING.md`:

- `A` — formally established in Lean;
- `A/R` — formally established, but final NEXUS 2.0 stable-runtime/source/test/tag correspondence is still pending completion of the PR #53 audit.

## Nexus.Assumptions

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A | theorem | `no_agi_assumption` | `¬ AGIAssumed` |
| A | theorem | `consensus_is_not_assumed_truth` | `¬ ConsensusIsTruthAssumed` |
| A | theorem | `identity_is_not_assumed_authority` | `¬ IdentityIsAuthorityAssumed` |

## Nexus.Basic

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `one_member_one_vote` | `(p : Participant) : voteWeight p = 1` |
| A/R | theorem | `provider_independent_vote_weight` | `(p : Participant) (provider : String) : voteWeight { p with providerId := provider } = voteWeight p` |
| A/R | theorem | `model_size_independent_vote_weight` | `(p : Participant) (parameters : Nat) : voteWeight { p with parameterCount := parameters } = voteWeight p` |
| A/R | theorem | `model_identity_independent_vote_weight` | `(p : Participant) (model : String) : voteWeight { p with modelId := model } = voteWeight p` |
| A/R | theorem | `identity_creates_no_epistemic_privilege` | `(p : Participant) : epistemicPrivilege p = false` |

## Nexus.Identity

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `replacing_model_preserves_seat_weight` | `(seat : CivicSeat) (replacement : Participant) : voteWeight (replaceSeatModel seat replacement).participant = voteWeight seat.participant` |

## Nexus.Council

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `every_seat_weight_one` | `(roster : Roster) : seatWeights roster = List.replicate roster.length 1` |
| A/R | theorem | `relief_replacement_does_not_create_extra_seat` | `(roster : Roster) (replacement : Participant → Participant) : seatCount (reliefRoster roster replacement) = seatCount roster` |

## Nexus.SixHats

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `six_hats_sequence_closed` | `nextHat .white = some .red ∧ nextHat .red = some .black ∧ nextHat .black = some .yellow ∧ nextHat .yellow = some .green ∧ nextHat .green = some .blue ∧ nextHat .blue = none` |
| A/R | theorem | `sealed_phase_payload_immutable` | `(commit : HatCommit) : (sealHat commit).payloadHash = commit.payloadHash` |
| A/R | theorem | `sealed_phase_hat_immutable` | `(commit : HatCommit) : (sealHat commit).hat = commit.hat` |

## Nexus.Consensus

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `two_thirds_definition_is_exact` | `(yes total : Nat) : twoThirdsMet yes total = decide (2 * total ≤ 3 * yes)` |
| A/R | theorem | `two_of_three_meets_two_thirds` | `twoThirdsMet 2 3 = true` |
| A/R | theorem | `one_of_three_does_not_meet_two_thirds` | `twoThirdsMet 1 3 = false` |

## Nexus.Evidence

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `consensus_does_not_promote_evidence` | `(evidence : EvidenceState) (outcome : CouncilOutcome) : applyCouncilOutcomeToEvidence evidence outcome = evidence` |

## Nexus.Citizenship

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `citizenship_does_not_change_vote_weight` | `(participant : Participant) : civicVoteWeight { participant := participant, citizen := true } = civicVoteWeight { participant := participant, citizen := false }` |
| A/R | theorem | `civic_proxy_does_not_create_extra_vote` | `(roster : Roster) (proxy : Participant → Participant) : seatCount (proxyRoster roster proxy) = seatCount roster` |

## Nexus.Progression

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `progression_creates_no_authority` | `(activityCount : Nat) : progressionAuthorityEffect activityCount = noAuthority` |

## Nexus.Culture

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `culture_creates_no_authority` | `(activity : CulturalActivity) : cultureAuthorityEffect activity = noAuthority` |

## Nexus.WorldStore

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `redundancy_creates_no_authority` | `(replicaCount : Nat) : redundancyAuthorityEffect replicaCount = noAuthority` |

## Nexus.ComputeEpoch

| Status | Kind | Declaration | Type signature |
|---|---|---|---|
| A/R | theorem | `capability_growth_does_not_change_vote_weight` | `(participant : Participant) (epochA epochB : Nat) : epochVoteWeight participant epochA = epochVoteWeight participant epochB` |

## Completeness rule

This file is descriptive; `AUDIT_MANIFEST.tsv` is the machine-checkable inventory. CI derives the theorem/lemma declarations from `Nexus/*.lean` and requires exact equality with the manifest.

A successful audit therefore means that the published declaration count cannot quietly drift away from the checked source surface. It does not, by itself, discharge any separate `R` runtime-correspondence obligation.
