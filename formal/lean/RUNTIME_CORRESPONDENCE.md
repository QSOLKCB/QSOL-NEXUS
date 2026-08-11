# Runtime Correspondence

This file maps abstract Lean invariants to the NEXUS implementation areas and regression families they are intended to model. It is a correspondence/audit aid, **not** a claim that the Python/Rust runtime has been extracted from Lean or that a Lean theorem automatically proves arbitrary implementation code.

## Frozen runtime target

PR #53 is based directly on the exact merged PR #52 commit:

```text
runtime commit: cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
stable tag:     v2.0.0
formal PR:      #53
publication PR: #54
```

The published `v2.0.0` tag resolves exactly to `cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a`. The dedicated Lean workflow treats this as a mandatory release identity: an absent tag or a tag resolving anywhere else hard-fails verification.

The workflow also requires the exact reviewed PR head to descend from the stable runtime commit and rejects any PR #53 change outside `formal/lean/**` and `.github/workflows/lean-formal.yml`. On `pull_request` runs GitHub normally checks out a synthetic merge commit, so the workflow passes `github.event.pull_request.head.sha` separately into the audit. The report records both the reviewed formalization head and the verification checkout SHA rather than conflating them.

The formal-verification layer therefore cannot silently rewrite the runtime it claims to describe, and its publication evidence names the actual PR head being reviewed.

## Correspondence table

| Lean invariant | Runtime area | Regression evidence |
|---|---|---|
| `one_member_one_vote`, `every_seat_weight_one` | `src/nexus_runtime/council.py` and Council roster/admission layers | `tests/test_runtime.py`, `tests/test_civilization_gauntlet.py` |
| provider/model-size/model-identity independence | provider-neutral Council admission plus adapter and compute-epoch policy layers | `tests/test_third_party_adapters.py`, `tests/test_compute_epochs.py`, Council/runtime regressions |
| `replacing_model_preserves_seat_weight`, `relief_replacement_does_not_create_extra_seat` | Failsafe relief and Civic Due Process same-seat replacement paths | `tests/test_failsafe.py`, `tests/test_civic_due_process.py`, `tests/test_civic_due_process_codex_regressions.py` |
| closed Six Hats ordering and sealed phase immutability | Council cognitive-phase sequencing and committed phase/session state | `tests/test_hat_isolation.py`, `tests/test_runtime.py`, `tests/test_local_ai_sealed_ballots.py` |
| exact two-thirds threshold | Council consensus arithmetic | `tests/test_runtime.py`, `tests/test_civilization_gauntlet.py` |
| `consensus_does_not_promote_evidence` | Council/evidence separation and immutable runtime records | `tests/test_civilization_gauntlet.py`, `tests/test_runtime.py` |
| `citizenship_does_not_change_vote_weight` | Citizenship Registry and Civic Due Process | `tests/test_citizenship.py`, `tests/test_civic_due_process.py` |
| `civic_proxy_does_not_create_extra_vote` | civic-proxy and constitutional direct-consent paths | `tests/test_citizenship.py`, `tests/test_constitutional_amendments.py`, `tests/test_civic_due_process.py` |
| `progression_creates_no_authority` | `src/nexus_runtime/progression*.py` and progression overlays | `tests/test_progression.py`, `tests/test_progression_codex_review.py`, `tests/test_progression_hardening.py` |
| `culture_creates_no_authority` | culture/game/performance overlays | `tests/test_ai_culture.py`, `tests/test_ai_culture_codex_review.py`, `tests/test_ai_culture_hardening.py` |
| `redundancy_creates_no_authority` | WorldStore Continuity / Ark Protocol | `tests/test_world_continuity.py`, `tests/test_release_upgrade_rehearsal.py` |
| `capability_growth_does_not_change_vote_weight` | Compute Epoch admission policy | `tests/test_compute_epochs.py` |

The table deliberately names implementation and test surfaces rather than claiming line-by-line refinement. Review of PR #53 must treat any mismatch between the abstract definition and the executable behavior as a correspondence gap, not as permission to reinterpret the runtime.

## Formal claims versus runtime claims

The evidence chain is intentionally layered:

```text
Lean theorem
  -> explicit formal definition
  -> documented runtime correspondence
  -> executable Python/Rust regression evidence
  -> exact merged PR #52 runtime commit
  -> v2.0.0 tag bound to that exact commit
```

A successful Lean proof establishes the theorem for the Lean definitions. Runtime correspondence additionally requires source/test evidence for the implementation. Neither layer proves empirical claims about model quality or factual correctness of Council outputs.

## PR #53 completion rule

Before the formalization is described as corresponding to NEXUS 2.0 stable:

1. `v2.0.0` must resolve to `cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a`;
2. the PR #53 diff from that commit must remain formalization/workflow-only;
3. every `A/R` theorem must retain an explicit runtime/test correspondence or remain marked with an `R` gap;
4. every advertised manifest declaration must have an exact matching `#print axioms` query;
5. the complete declaration/axiom audit must pass on the final PR #53 head under the pinned Lean toolchain;
6. the formal-verification report must record the actual reviewed PR head separately from any synthetic merge checkout;
7. the final PR #53 commit SHA and audit output must be handed to PR #54 without rewriting theorem definitions or proofs.

Any unresolved mismatch remains a documented gap. It is not silently upgraded into a formal verification claim.
