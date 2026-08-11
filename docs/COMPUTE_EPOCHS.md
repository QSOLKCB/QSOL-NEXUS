# NEXUS Compute Epochs & Temporal Compute Equality

PR #42 replaces the Council Chair's permanent 20B protected-small ceiling with a deterministic, versioned Compute Epoch policy while preserving the existing Council equality contract.

The governing principle is:

> **Time may enlarge the chair. It may not enlarge the vote.**

## Epoch policy v1

`nexus-compute-epoch-v1` uses an explicit UTC genesis and fixed-duration epochs:

```text
genesis:          2026-08-11T00:00:00Z
epoch duration:   1,461 days
scale factor:     2 / 1 per epoch
base small limit: 20,000 million parameters
metric:           declared total parameter count v1
```

For a Unix timestamp `t` at or after genesis:

```text
E(t) = floor((t - genesis) / epoch_duration_seconds)
```

For any numeric compute envelope with base value `L0`:

```text
L(E) = floor(L0 * 2^E)
```

No floating-point arithmetic is used.

The initial protected-small sequence is therefore:

```text
Epoch 0   <= 20B
Epoch 1   <= 40B
Epoch 2   <= 80B
Epoch 3   <= 160B
Epoch 4   <= 320B
```

The current Chair has one numeric size boundary: the Small-Mind Guarantee. Future numeric compute envelopes must use the same exact epoch transform rather than acquiring unrelated growth schedules. This preserves relative compute geometry when more boundaries are introduced later.

## What epochs may change

Compute Epochs may change only admission envelopes that are explicitly declared scale-dependent.

They do not change:

- the 3–5 public voting-seat limit;
- maximum closed-general or large-open-weight seat counts;
- one seat / one vote;
- vote weight `1`;
- epistemic privilege `none`;
- consensus arithmetic;
- evidence state;
- provider authority;
- citizenship authority;
- constitutional authority.

A model that was small enough in an earlier epoch does not become too small later. Epochs raise ceilings; they never create a minimum model size.

## Model metric v1

PR #42 intentionally keeps the already-audited PR #34 metric:

```text
declared total parameter count
```

This is versioned as `declared_total_parameter_count-v1` so a later amendment can introduce a better effective-inference-footprint metric without silently rewriting historical admission semantics.

MoE handling therefore remains the PR #34 rule for v1: total declared parameters, not active parameters per token.

## One epoch per Council request

A live Council request resolves the wall clock exactly once before provider admission begins.

That resolved epoch is stored in a request-local `ContextVar` for the complete operation. Validation, classification, returned Chair metadata and the durable epoch-admission receipt therefore see the same epoch even if a slow live inference call crosses an epoch boundary.

This prevents the pathological case:

```text
validation at epoch N
    -> long provider inference
summary at epoch N+1
```

from producing contradictory admission state.

## Durable admission receipt

Every successful public `council.run` creates a runtime-owned:

```text
council_epoch_admission_receipt
```

The receipt binds:

- the exact committed `council_session` ref;
- the resolved Compute Epoch;
- the effective protected-small threshold;
- the admitted seat classes;
- the equal vote and epistemic-privilege invariants.

`council.epoch.verify` reconstructs the seat class expected from the **recorded epoch**, checks the threshold against the pinned policy, verifies constitutional slot counts and equality fields, and cross-checks the receipt roster against the referenced Council session.

It does not consult the current wall clock during replay verification.

Thus a Council admitted in 2026 remains historically interpretable under Epoch 0 even if it is inspected in a much later epoch.

## Public runtime surface

PR #42 adds:

- `council.epoch.policy`
- `council.epoch.verify`

`system.health.compute_epoch` publishes the active policy and current resolved epoch.

`system.health.council_chair` retains the legacy `nexus-council-chair/1` primary schema for compatibility and adds the secondary extension marker:

```text
epoch_schema = nexus-council-chair-epoch/1
```

## Policy evolution

If model architecture eventually makes raw parameter count a poor compute proxy, NEXUS should introduce a new versioned metric or epoch policy. Historical v1 receipts must remain verifiable under v1.

Do not silently alter the meaning of an old epoch.

## Core invariant

> **Capability may grow. Access may expand. Authority does not.**
