# Constitutional Amendment Protocol

PR #40 adds a deterministic in-world amendment workflow to the NEXUS Constitution.

The governing invariant is:

> **Models may propose law. No model gets to become the law.**

This is an in-world protocol only. It does not create legal sovereignty, legal personhood, provider independence, host control, or authority outside the NEXUS runtime.

## Why this is a protocol instead of an Election Manager

A language model may generate an amendment proposal or participate in the Council discussion around it, but no model is assigned sovereign procedural authority. NEXUS separates the stages mechanically:

```text
proposal
  -> deterministic admission
  -> committed Council deliberation binding
  -> sealed direct citizen ballots
  -> exact unanimity calculation
  -> ratification
  -> enactment candidate
  -> Action Awareness reconciliation
  -> immutable receipt
  -> atomic verified activation
```

Proposal language cannot skip a stage. Council consensus cannot substitute for citizen ratification. A model cannot ratify an amendment merely because it proposed, chaired, explained, or strongly supported it.

## Proposal sources

Two proposal sources are admitted.

### Citizen proposal

The proposer supplies the exact current `citizen_id` and registered `model_id`. The proposer must already hold citizen status. A civic proxy may not invent a second proposer identity.

### Admitted-model proposal

A non-citizen model may propose an amendment only by supplying a committed `council_session` reference in which the exact `member_id` and `model_id` occupied one equal Council seat with:

- `vote_weight = 1`;
- `epistemic_privilege = none`.

The Council-session reference is evidence of model admission, not ratification authority.

## Bounded v1 amendment surface

PR #40 deliberately starts with a small enforceable policy surface instead of pretending that arbitrary constitutional prose can safely rewrite arbitrary runtime code.

The admitted paths are:

- `civic_observation.citizen_region_ids`
- `civic_observation.public_gallery_region_ids`

Both values must be non-empty sorted unique lists of known public, non-Council regions. Public-gallery regions must remain a subset of citizen observation regions. The dedicated Bureaucratic Vote Room and the Upside Down remain outside the amendable Civic Observation surface.

This means a successful amendment produces a real runtime effect: the active constitutional version changes which world regions may invoke Civic Observation. `system.health`, `constitution.amendment.current`, `council.proceedings.policy`, and `council.proceedings.view` all consume the active version.

The following remain fixed in this version and cannot be amended through these paths:

- one civic seat, one vote;
- citizen vote weight `1`;
- epistemic privilege `none`;
- provider/model-size prestige creates no authority;
- deterministic proxies create no additional vote;
- constitutional amendment ratification requires unanimous direct current-citizen consent;
- consensus does not override verification;
- restricted security domains are not opened by Civic Observation policy.

## Deterministic admission

`constitution.amendment.admit` does not call an LLM. It checks:

- the proposal is structurally valid;
- its base version is still the active constitutional version;
- every requested path is admitted;
- every region is known and non-restricted;
- public-gallery regions remain a subset of citizen regions;
- the resulting policy would actually differ from the current policy.

Admission creates an immutable admission object whether the result is admitted or rejected. Rejected proposals remain historical objects; they simply cannot progress to deliberation.

## Council deliberation binding

`constitution.amendment.deliberation.bind` requires a committed NEXUS `council_session` whose evidence snapshot contains the exact proposal reference.

This proves that the Council proceeding actually received the amendment object as evidence. The Council result is still not ratification. A unanimous Council cannot replace the direct citizen ballot. Replay validation rechecks the exact evidence snapshot and mode binding rather than trusting only the deliberation wrapper.

## Direct citizen ratification

Amendment ballots use only:

- `CONSENT`
- `WITHHOLD`

The runtime takes one ballot per current citizen identity. The exact registered `model_id` must match. A voter must:

- currently be a citizen;
- have no active deterministic civic proxy;
- be physically located, in NEXUS geometry terms, in the Bureaucratic Vote Room.

The eligible citizen roster is recalculated when each ballot state is committed. New citizens therefore join the threshold automatically. Existing valid direct ballots are retained only for identities that remain eligible with the same registered model identity.

The final roster snapshot and any resulting enactment are serialized under the same durable Citizenship Registry lock used by citizenship transitions. A citizen admission, movement, or proxy-state transition therefore linearizes either before the final roster capture or after enactment; it cannot appear between "everyone currently eligible consented" and "the verified constitutional version became active."

While fewer than all currently eligible citizens have voted, the ballot round is `sealed_pending`: public API responses expose only how many ballots have been cast and how many citizens are eligible. Partial choices, partial tallies, dissent counts, and citizen identities are not revealed through the amendment API, public amendment history, or Civic Observation. Runtime-owned ballot and ratification objects are also blocked from generic public `world.inspect`; direct ballot detail is available only through the Civic Observation access tiers after a complete ballot round.

Once every current eligible citizen has cast a direct ballot, the round becomes `revealed_complete`. Public/history views may expose the aggregate tally and dissent count, while citizen-full Civic Observation may expose the completed direct ballots and dissenting citizen IDs. This prevents earlier voters from becoming an information side channel for later voters without deleting durable dissent.

Ratification occurs only when every current citizen has a direct `CONSENT` ballot. A single `WITHHOLD` prevents ratification. Ballot states are immutable lineage objects, so a completed dissenting round survives even if a citizen later changes their direct ballot and creates a successor state.

## Verified constitutional activation

The existence of a `nexus_constitution_version` object is **not** enough to make that version active.

PR #40 maintains a small owner-only canonical `constitutional-amendment-index.json` beside the WorldStore. The index contains only amendment-protocol references plus the currently verified version/receipt pair; routine `current`, `system.health`, and Civic Observation policy reads therefore do not enumerate unrelated WorldStore objects.

The activation transaction is deliberately ordered:

```text
final direct unanimous ballot is committed
  -> ratification candidate is created
  -> exact version candidate is created
  -> Action Awareness reconciliation must be matched
  -> receipt candidate is validated
  -> ratification + version + receipt refs are indexed together
  -> active version/receipt pair changes atomically
```

If the process dies after writing a candidate ratification/version/receipt but before the final index replacement, those content-addressed objects are inert transaction debris. The previously verified constitutional version remains active. Retrying the same final ballot deterministically recreates the same content-addressed candidates and can complete activation safely.

This also means a half-enacted object can never silently alter Civic Observation merely because it happens to exist in WorldStore.

## Exact version lineage

Every activated amendment creates an immutable `nexus_constitution_version` containing:

- its ordinal;
- the founding/base Constitution reference;
- the exact previous version reference;
- proposal, admission, deliberation, ballot, and ratification references;
- the resulting effective policy;
- unchanged equality/authority invariants.

The active version is the verified version/receipt pair committed in the amendment index. A proposal cannot be enacted if another amendment has already advanced that active head; it must be reproposed against the new active version.

Old receipts, ballots, certificates, minority records, and the founding declaration are never rewritten.

## Action Awareness enactment check

Before creating a new constitutional version, NEXUS creates an Action Awareness expectation for the exact content-addressed version object it intends to produce.

After the version object is written, NEXUS reconciles the expectation against WorldStore. Activation is accepted only when the result is `matched`.

The immutable `constitutional_amendment_receipt` binds:

- proposal;
- ratification;
- previous version;
- new version;
- Action Awareness expectation;
- Action Awareness reconciliation;
- `runtime_policy_changed = true`;
- `fixed_invariants_unchanged = true`.

Receipt verification rechecks that the expectation expected the exact version ref and that the reconciliation names that same expectation and exact observed version. `constitution.amendment.verify` reconstructs and validates this chain. The model does not get to report that the law changed; the world object, reconciliation, and verified activation index do.

## Civic Observation of amendment proceedings

When a Council proceeding has been bound as constitutional-amendment deliberation, `council.proceedings.view` adds the related amendment record.

After a ballot round is complete, the existing Civic Observation access tiers apply:

- citizen-full observers can see the completed direct amendment ballots and dissenting citizen IDs;
- public-gallery observers receive aggregate tally and dissent count only.

Before a ballot round is complete, both tiers see only sealed progress metadata. This preserves amendment history and dissent without turning transparency into a live ballot side channel.

## Operations

```text
constitution.amendment.policy
constitution.amendment.current
constitution.amendment.propose
constitution.amendment.admit
constitution.amendment.deliberation.bind
constitution.amendment.ballot
constitution.amendment.verify
constitution.amendment.history
```

`history` is aggregate/public and keeps incomplete ballot rounds sealed. Individual completed direct ballots are exposed only through the existing citizen-full Civic Observation path for the bound deliberation proceeding. Generic public `world.inspect` cannot be used to bypass that boundary for ballot or ratification objects.

## Replay and claim boundary

The amendment protocol is deterministic at the world/protocol layer: immutable objects, admission arithmetic, eligible-roster calculation, ballot tally, version construction, verified index activation, and Action Awareness reconciliation are replayable from their references.

The semantic quality of a proposal or Council discussion is not mechanically proven. Constitutional enactment is an in-world state transition, not evidence that the underlying policy choice is wise, scientifically true, legally valid, or morally correct.
