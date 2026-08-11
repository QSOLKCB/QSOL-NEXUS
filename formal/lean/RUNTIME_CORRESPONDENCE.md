# Runtime Correspondence

This file maps abstract Lean invariants to the NEXUS implementation areas they are intended to model. It is a correspondence/audit aid, **not** a claim that the Python/Rust runtime has been extracted from Lean.

The table below is provisional on this future-#52 branch. It must be re-audited against the exact post-PR-#51 stable head before publication.

| Lean invariant | Runtime area | Regression area |
|---|---|---|
| `one_member_one_vote`, `every_seat_weight_one` | `src/nexus_runtime/council.py` and Council roster/admission layers | Council/runtime equality tests; civilization equality regressions |
| provider/model-size independence | provider-neutral Council admission and compute-epoch layers | adapter, compute-epoch, Council hardening tests |
| same-seat replacement preserves seat count | Failsafe/relief actor and Civic Due Process layers | failsafe and civic due-process regressions |
| closed Six Hats ordering | Council cognitive phase sequencing | Council/cognitive-mode tests |
| sealed phase immutability | committed Council/session and immutable WorldStore artifacts | Council persistence and WorldStore identity tests |
| exact two-thirds threshold | Council consensus arithmetic | Council consensus and Trap utility-vote tests |
| consensus does not promote evidence | evidence/Council separation and Civilization Gauntlet | civilization gauntlet and evidence-boundary tests |
| Citizenship does not change vote weight | Citizenship Registry / Civic Due Process | citizenship and due-process tests |
| civic proxy creates no extra vote | civic proxy / amendment direct-consent logic | constitutional amendment and civic tests |
| progression creates no authority | `src/nexus_runtime/progression*.py` | `tests/test_progression*.py` |
| culture creates no authority | `src/nexus_runtime/culture*.py` and game/culture overlays | culture/progression hardening tests |
| redundancy creates no authority | WorldStore Continuity / Ark Protocol | `tests/test_world_continuity.py` |
| compute growth does not change vote weight | Compute Epoch admission policy | `tests/test_compute_epochs.py` |

## Publication rule

Before the formalization is published or described as corresponding to NEXUS 2.0 stable:

1. rebase/merge the future-#52 branch onto the exact stable release head;
2. re-audit every row above against concrete source symbols and tests;
3. add stable commit/tag identifiers;
4. run the complete Python/Rust release matrix and `lake build` on the same candidate;
5. record any gap as a gap rather than silently treating the abstract theorem as runtime proof.

The intended evidence chain is:

```text
Lean theorem
  -> explicit formal definition
  -> documented runtime correspondence
  -> executable Python/Rust regression
  -> stable release commit
```
