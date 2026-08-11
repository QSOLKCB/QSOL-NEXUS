# Theorem Inventory

Every item below is intended to be kernel-checked with no `sorry`, `admit`, or user-declared `axiom`.

| Theorem | Module | Claim |
|---|---|---|
| `one_member_one_vote` | `Nexus.Basic` | Every participant's constitutional vote weight is exactly 1. |
| `provider_independent_vote_weight` | `Nexus.Basic` | Changing provider identity does not change vote weight. |
| `model_size_independent_vote_weight` | `Nexus.Basic` | Changing declared parameter count does not change vote weight. |
| `model_identity_independent_vote_weight` | `Nexus.Basic` | Changing model identity does not change vote weight. |
| `identity_creates_no_epistemic_privilege` | `Nexus.Basic` | Participant identity creates no epistemic privilege. |
| `replacing_model_preserves_seat_weight` | `Nexus.Identity` | Same-seat model replacement preserves seat weight. |
| `every_seat_weight_one` | `Nexus.Council` | Every roster seat maps to weight 1. |
| `relief_replacement_does_not_create_extra_seat` | `Nexus.Council` | Replacement preserves roster cardinality. |
| `six_hats_sequence_closed` | `Nexus.SixHats` | WHITE → RED → BLACK → YELLOW → GREEN → BLUE → stop. |
| `sealed_phase_payload_immutable` | `Nexus.SixHats` | Sealing a phase does not alter its payload hash. |
| `sealed_phase_hat_immutable` | `Nexus.SixHats` | Sealing a phase does not alter its hat identity. |
| `two_thirds_definition_is_exact` | `Nexus.Consensus` | The threshold is encoded as exact integer inequality `2*total ≤ 3*yes`. |
| `two_of_three_meets_two_thirds` | `Nexus.Consensus` | 2/3 satisfies the threshold. |
| `one_of_three_does_not_meet_two_thirds` | `Nexus.Consensus` | 1/3 does not satisfy the threshold. |
| `consensus_does_not_promote_evidence` | `Nexus.Evidence` | Council outcome alone leaves evidence state unchanged. |
| `citizenship_does_not_change_vote_weight` | `Nexus.Citizenship` | Citizenship status does not alter vote weight. |
| `civic_proxy_does_not_create_extra_vote` | `Nexus.Citizenship` | Proxy substitution preserves roster cardinality. |
| `progression_creates_no_authority` | `Nexus.Progression` | Progression activity count has zero authority effect. |
| `culture_creates_no_authority` | `Nexus.Culture` | Cultural participation has zero authority effect. |
| `redundancy_creates_no_authority` | `Nexus.WorldStore` | Replica count/quorum strength has zero authority effect. |
| `capability_growth_does_not_change_vote_weight` | `Nexus.ComputeEpoch` | Compute-epoch growth does not change voting weight. |

This inventory is deliberately narrower than “NEXUS is formally verified.” It states exactly which abstract protocol invariants are presently represented in Lean.
