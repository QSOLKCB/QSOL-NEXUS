# Action Awareness & World Reconciliation

PR #37 adds a deterministic grounding layer between what an agent expects an action to do and what NEXUS can actually observe in the persistent world.

The governing principle is:

> **World state outranks model self-report.**

This is inspired by the Action Awareness idea in *Project Sid: Many-agent simulations toward AI civilization* (arXiv:2411.00114v1), where agents compare expected action outcomes with observed outcomes to reduce downstream error accumulation. NEXUS adapts that idea to its content-addressed world rather than copying the paper's agent architecture.

## Scope

The first version intentionally covers one narrow, auditable action class:

```text
expected content-addressed world-object creation
```

It does not claim to verify arbitrary real-world effects, remote-provider side effects, browser actions, shell commands, or generalized operation replay.

## Operations

The hardened runtime exposes:

```text
action.awareness.policy
action.awareness.expect_create
action.awareness.reconcile
```

`system.health.action_awareness` publishes the same machine-readable policy under schema `nexus-action-awareness/1`.

## Expectation

Before an ordinary `world.create`, an actor can register the exact scrubbed object identity it expects to exist afterwards:

```json
{
  "operation": "action.awareness.expect_create",
  "actor_id": "Alpha",
  "action_label": "create a grounded observation",
  "object_type": "observation_note",
  "payload": {
    "claim": "world state wins"
  },
  "provenance": {
    "actor": "Alpha"
  }
}
```

NEXUS does **not** create the expected object. It computes the content-addressed object reference that the requested type, payload and provenance would have if the later world mutation produces exactly that state, then commits a runtime-owned `action_expectation` object.

The expectation therefore records intent without pretending the intent succeeded.

## Action

The ordinary mutation remains separate:

```json
{
  "operation": "world.create",
  "object_type": "observation_note",
  "payload": {
    "claim": "world state wins"
  },
  "provenance": {
    "actor": "Alpha"
  }
}
```

The expectation and actual mutation pass through the same Secret Scrubber semantics, so their content-address identities are comparable after sanitization.

## Reconciliation

NEXUS then reconciles the expectation against its own WorldStore:

```json
{
  "operation": "action.awareness.reconcile",
  "expectation_ref": "object:<64 lowercase hex>"
}
```

If `observed_object_ref` is omitted, the runtime directly checks whether the exact expected object exists.

An operator may instead supply a specific observed object reference:

```json
{
  "operation": "action.awareness.reconcile",
  "expectation_ref": "object:<64 lowercase hex>",
  "observed_object_ref": "object:<64 lowercase hex>"
}
```

This is useful when an action produced a different world object and the caller wants an explicit expected-versus-observed comparison.

The closed outcomes are:

```text
matched   — the observed object is exactly the expected content-addressed object
diverged  — a supplied observed object exists but has a different identity
missing   — the exact expected object does not exist and no alternative observation was supplied
```

## Immutable lineage

Both `action_expectation` and `action_reconciliation` are runtime-owned world-object types. Public `world.create` cannot forge them.

A reconciliation records:

- the immutable expectation ref;
- the expected object ref;
- the observed object ref when one exists;
- the closed reconciliation outcome;
- whether the exact identity matched;
- that the result came from WorldStore observation rather than model self-report;
- that no observed object was mutated;
- that no evidence state was promoted.

Repeated identical expectations produce the same content-addressed expectation reference.

## Why this matters for many-agent systems

A hallucinated success can poison later agent state: one agent says an action happened, later reasoning assumes it happened, and other agents can inherit the false premise. Action Awareness introduces a boring mechanical checkpoint before that narrative becomes trusted world state.

In NEXUS terms:

```text
INTENT
  ↓
EXPECTED WORLD OBJECT
  ↓
ACTION
  ↓
WORLD OBSERVATION
  ↓
RECONCILIATION
  ↓
MATCHED / DIVERGED / MISSING
```

The model may explain the result. It does not get to choose the result.

## Authority boundary

Action Awareness is grounding, not governance.

It does not change:

```text
vote_weight
epistemic_privilege
Council seat count
consensus arithmetic
evidence state
Citizenship status
observed world objects
```

A `matched` reconciliation means only that a specific expected content-addressed world object exists. It does not prove the truth of the object's semantic claims.

That distinction is deliberate:

> **Existence is an observation. Truth still requires evidence.**
