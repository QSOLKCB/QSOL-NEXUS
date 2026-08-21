# Generalized Operation Replay

## Purpose

PR #62 implements the first genuinely unfinished alpha1 roadmap item after the post-stable 2.1 line: **generalized operation replay beyond deterministic fixtures**.

The public operation is:

```text
receipt.replay
```

It does not mean every historical operation is replayable. Replay is a closed, versioned admission surface. A stored receipt must explicitly declare `replayable: true`, match the current protocol, and name an operation with a reviewed replay adapter.

```text
REPLAYABLE != REPLAYED
REPLAY_MATCH != SEMANTIC_TRUTH
```

## First admitted replay adapter

The first registered operation is:

```text
council.run
```

Replay is admitted only when the persisted Council is fully reconstructible from public durable state:

- every seat is the deterministic built-in mock actor;
- actor profile and privilege-attempt fixture metadata are frozen in the stored roster;
- there is no preexisting Failsafe state or civic/Failsafe actor substitution;
- the receipt binds exactly the question, evidence snapshot, and world-presence refs;
- the original question did not require Secret Scrubber removal of raw secret text;
- the stored receipt and session both declare replayable execution;
- the receipt protocol equals the current runtime protocol.

The replay service copies only the exact referenced evidence objects into a fresh in-memory WorldStore, reconstructs the deterministic actors and Council policy, runs the scalar reference path, and requires both of these identities to match exactly:

```text
replayed session_ref == stored result_ref
replayed receipt_ref == source receipt_ref
```

The source world is never used as the replay execution target.

## Why secret-scrubbed questions are rejected

If an operator accidentally supplied a secret, NEXUS intentionally persisted only the scrubbed question. The raw source text is not retained merely to make replay convenient.

A later replay therefore cannot reconstruct the exact pre-scrub input and fails with `replay_context_not_reconstructible`.

```text
REPLAY_CONVENIENCE != SECRET_RETENTION_JUSTIFICATION
```

## Fail-closed cases

`receipt.replay` rejects:

- receipts with `replayable: false`;
- unknown or unregistered receipt operations;
- receipts from another protocol version without a reviewed migration adapter;
- malformed receipt/session bindings;
- live Ollama or cloud-model Councils;
- Councils with preexisting Failsafe state;
- civic or Failsafe substitutions that cannot be reconstructed from the admitted replay contract;
- secret-scrubbed original questions whose raw source was deliberately discarded;
- any replay whose result or receipt content address differs from the stored identity.

No fallback guesses are permitted.

## Authority boundary

A successful replay means only that the admitted deterministic protocol execution reproduced the same content-addressed result under the declared reconstruction contract.

It does not prove that:

- the Council conclusion is true;
- the evidence state is correct;
- the Council was wise;
- a model is reliable;
- consensus is evidence;
- replay creates governance authority.

```text
DETERMINISTIC != AUTHORITATIVE
REPLAY != EVIDENCE_PROMOTION
SOURCE_WORLD != REPLAY_WORLD
PROTOCOL_MIGRATION != SILENT_REPLAY
```

The replay response therefore carries:

```text
evidence_effect  = none
authority_effect = none
```

## Release-boundary note

PR #62 is based on the merged PR #61 commit but must not be merged before the certified PR #61 merge commit receives the intended `v2.1.1` tag/release identity. The new replay feature is post-2.1.1 development and must not be retroactively included in the exact release candidate that PR #61 certified.
