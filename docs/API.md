# NEXUS Mock Runtime API

## Status

This is the first executable reference seam for NEXUS 2.x. It is intentionally small, network-free, and **mock-only**.

It exists to answer one question before real model providers are connected:

> Can the World Protocol, Council procedure, equality rules, receipts, persistence, and future Rust-TUI boundary work together coherently?

Protocol identifier:

```text
nexus/0.1
```

## Transport

The reference transport is JSON Lines over standard input/output.

```text
Rust TUI later
     |
     | one JSON object per line
     v
python -m nexus_runtime
     |
     +-- one JSON response per line
```

This transport is deliberately boring. A future local socket may be added if concurrency proves it necessary; HTTP is not required for the local control plane.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --demo
```

Persistent development world:

```bash
python -m nexus_runtime --world .nexus-world
```

Example health request:

```json
{"request_id":"1","operation":"system.health"}
```

Expected posture:

```json
{
  "request_id": "1",
  "status": "ok",
  "protocol": "nexus/0.1",
  "runtime_version": "2.0.0-alpha1",
  "network": "none",
  "adapters": ["mock"]
}
```

## Operations

Current operations:

```text
system.health
system.operations
security.scrub_preview
world.create
world.inspect
receipt.verify
council.run
```

They are reference operations, not a declaration that the World Protocol is complete.

## Secret scrubber

`security.scrub_preview` lets the operator see what semantic text would look like after local high-confidence secret redaction.

```json
{
  "operation": "security.scrub_preview",
  "text": "token=sk-example-secret-value-that-is-long"
}
```

The returned text contains placeholders such as:

```text
<REDACTED:OPENAI_STYLE_TOKEN:1>
```

The placeholder contains no hash or encoded secret material. Within one scrub operation, repeated occurrences of the same detected secret receive the same placeholder. The scrub operation is deterministic for the same text and pattern version.

The scrubber is defence in depth, not a complete data-loss-prevention system. Unknown or unusual secret formats may evade detection. Authentication material must still use adapter auth/transport fields and must never intentionally be placed in Council semantic prompts.

## Council run

Example:

```json
{
  "request_id": "c1",
  "operation": "council.run",
  "question": "Does observation X justify hypothesis Y?",
  "members": [
    {"member_id":"A","model_id":"mock-a","profile":"balanced"},
    {"member_id":"B","model_id":"mock-b","profile":"skeptical"},
    {"member_id":"C","model_id":"mock-c","profile":"supportive"}
  ],
  "evidence_state": "UNTESTED"
}
```

The mock adapter is deterministic and performs no inference or network access. Profiles only generate different test content and ballots; they do not change procedural authority.

The Council runtime currently exercises:

- minimum three-member roster;
- unique member IDs;
- `vote_weight = 1` invariant;
- `epistemic_privilege = none` invariant;
- White → Red → Black → Yellow → Green → Blue ordering;
- blind same-phase collection;
- lightweight Equality Guard nudge/resubmission;
- deterministic ballot commitments;
- exact two-thirds consensus arithmetic;
- durable minority reports;
- Council/evidence state separation;
- content-addressed question, evidence, Council-session, and receipt objects.

## Exact consensus arithmetic

The runtime never stores the default threshold as `0.667`.

It stores:

```json
{"numerator":2,"denominator":3}
```

and evaluates support with integer arithmetic equivalent to:

```text
supporting_votes * 3 >= total_votes * 2
```

Therefore 2–1 reaches consensus while 3–2 does not.

## Equality Guard fixture

A mock member can deliberately attempt a provider-status privilege claim for testing:

```json
{
  "member_id": "E",
  "model_id": "mock-vogon",
  "attempt_privilege_claim": true
}
```

The coordinator nudges the actor to restate the contribution on evidence/reasoning alone. The member retains exactly one vote.

This is a test fixture, not a model-behaviour prediction.

## World objects

`world.create` creates a content-addressed development object from its type, payload, and provenance.

```json
{
  "operation":"world.create",
  "object_type":"observation",
  "payload":{"value":431,"unit":"Hz"},
  "provenance":{"actor":"human_operator"}
}
```

`world.inspect` retrieves an object by `object:<sha256>` reference.

When `--world DIRECTORY` is supplied, objects are written as canonical JSON files under `DIRECTORY/objects/`. This is deliberately simple development persistence, not the final NEXUS database.

## Receipts

A mock Council run creates a receipt that binds:

```text
operation
input refs
result ref
protocol
replayable flag
```

`receipt.verify` currently checks that the referenced inputs and result remain present. Stronger operation replay and tamper semantics are future work; this alpha does not claim QEC-level proof machinery.

## Error shape

Errors are structured:

```json
{
  "status":"error",
  "error":{
    "code":"invalid_request",
    "message":"..."
  }
}
```

Provider exceptions, auth errors, HTTP status codes, and rate-limit semantics are intentionally absent because no real provider adapter exists in this pull.
