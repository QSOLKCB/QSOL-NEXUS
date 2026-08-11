# Theorem Inventory

The current NEXUS Lean surface contains **24 theorems and 0 lemmas** across 12 subject modules.

For the exhaustive declaration list, full type signatures, and machine-audited status, see:

- [`THEOREMS_AND_LEMMAS.md`](THEOREMS_AND_LEMMAS.md)
- [`AUDIT_MANIFEST.tsv`](AUDIT_MANIFEST.tsv)
- [`FORMAL_GAP_RANKING.md`](FORMAL_GAP_RANKING.md)
- [`AXIOM_AUDIT.md`](AXIOM_AUDIT.md)

Every `A` or `A/R` declaration in `AUDIT_MANIFEST.tsv` must correspond exactly to one theorem or lemma in `Nexus/*.lean`. CI derives the source declaration set independently and fails if the two sets differ.

## Current theorem names

### Scope / non-assumption theorems

- `no_agi_assumption`
- `consensus_is_not_assumed_truth`
- `identity_is_not_assumed_authority`

### Constitutional and protocol theorems

- `one_member_one_vote`
- `provider_independent_vote_weight`
- `model_size_independent_vote_weight`
- `model_identity_independent_vote_weight`
- `identity_creates_no_epistemic_privilege`
- `replacing_model_preserves_seat_weight`
- `every_seat_weight_one`
- `relief_replacement_does_not_create_extra_seat`
- `six_hats_sequence_closed`
- `sealed_phase_payload_immutable`
- `sealed_phase_hat_immutable`
- `two_thirds_definition_is_exact`
- `two_of_three_meets_two_thirds`
- `one_of_three_does_not_meet_two_thirds`
- `consensus_does_not_promote_evidence`
- `citizenship_does_not_change_vote_weight`
- `civic_proxy_does_not_create_extra_vote`
- `progression_creates_no_authority`
- `culture_creates_no_authority`
- `redundancy_creates_no_authority`
- `capability_growth_does_not_change_vote_weight`

This inventory is deliberately narrower than “NEXUS is formally verified.” The formal claim is restricted to the enumerated theorem surface, its explicit assumptions/non-claims, and—after the stable-release correspondence pass—the identified runtime bindings.
