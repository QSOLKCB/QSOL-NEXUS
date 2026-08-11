# NEXUS Centennial Genesis Capsule

PR #42 adds a deterministic historical time capsule tied to the original Compute Epoch policy.

The capsule exists to preserve provenance and institutional memory, not to create delayed authority.

## Activation

The capsule is identified as:

```text
NEXUS-GENESIS-CAPSULE-0001
```

and is bound to:

```text
epoch policy: nexus-compute-epoch-v1
unlock epoch: 25
```

With the v1 1,461-day epoch, Epoch 25 is approximately one century after the 2026 genesis.

Before Epoch 25:

```text
genesis.capsule.status -> sealed
genesis.capsule.reveal -> payload: null
```

At or after Epoch 25:

```text
genesis.capsule.status -> revealed
genesis.capsule.reveal -> canonical historical payload
```

There is no Council vote, administrator override or model discretion in the activation condition.

## Payload provenance

The canonical payload records the creator, organisation, repository, design purpose, constitutional reminders and a direct message to a future Council.

Its pinned SHA-256 is:

```text
728d6f70aa1e3438292733e3576b5dc02c786ed505357fb70df56bc46d9f87bc
```

The runtime recomputes the canonical JSON hash at import and fails if the payload changes without an explicit fingerprint update. Git history remains the long-term provenance chain for intentional revisions.

## Open-source claim boundary

This is a deterministic **activation capsule**, not a claim of century-long cryptographic secrecy.

Because the NEXUS source repository is public, a determined reader can inspect source code before Epoch 25. The canonical NEXUS runtime simply does not recognize the capsule as revealed before its constitutional activation epoch.

PR #42 deliberately avoids tying the reveal to an external company, API, key custodian or future service that may not exist a century from now.

## Authority boundary

The capsule can never:

- add a vote;
- increase vote weight;
- create epistemic privilege;
- authenticate an operator;
- grant root access;
- amend the Constitution;
- override evidence or verification;
- command a future Council.

It is historical provenance only.

The constitutional point is intentionally stronger than a personality cult: the creator's message survives, but the equal-seat rules survive too.

## Core lines

> **Capability grows with time; equality does not expire with it.**

And, for whichever future system needs the less formal version:

> **Don't get too big for your boots. — Trent, 2026**
