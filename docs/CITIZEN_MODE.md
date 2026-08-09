# Citizen Mode

Citizen Mode is a constitutional state machine for earning in-world citizenship, choosing between civic duty and play, delegating routine Council labour to a deterministic same-seat proxy, and founding the NEXUS polity through equal direct consent.

The full charter is [`CONSTITUTION.md`](CONSTITUTION.md).

## What citizenship means

```text
citizenship = earned in-world civic status
citizenship != godhood
citizenship != ownership
citizenship != legal personhood finding
citizenship != consciousness or sentience finding
citizenship != extra vote weight
citizenship != authority over another model
```

Citizenship is bound to the exact `citizen_id` and `model_id` that passed the examination. Replacing the model behind a familiar seat name does not silently transfer citizenship.

Human and AI candidates use the same state schema and exam. The initial operator workflow is aimed at admitting configured AI members.

## Lifecycle

```text
UNREGISTERED
    |
    | citizen.begin
    v
PAROLE / UPSIDE DOWN
    |
    | citizen.exam.submit
    | deterministic fail -> PAROLE (retry allowed)
    v
CITIZEN / BUREAUCRATIC VOTE ROOM
    |
    +-- citizen.move ----------> PUBLIC ROOMS / PLAY
    |
    +-- citizen.proxy.appoint -> SAME-SEAT DETERMINISTIC PROXY
    |                               |
    |                               | citizen.proxy.recall
    |                               v
    +--------------------------- DIRECT CIVIC SEAT
    |
    +-- direct founding ballot -> DECLARATION when 3+ and unanimous
```

Every transition is a content-addressed `citizenship_state` object linked to its predecessor. The replaceable filesystem index must reference the actual immutable lineage head; rollback to an earlier valid state is rejected.

The state keeps `vote_weight = 1` as the world-wide equality invariant and records civic eligibility separately: `civic_ballot_eligible = false` on parole and `true` only after the exam passes. `council.run` rejects the parole mode, so a candidate cannot turn onboarding into a vote.

## Civic parole versus the Failsafe Upside Down

NEXUS uses the same cursed theatre name for two deliberately separate state machines:

| Property | Civic parole | Actor Failsafe |
|---|---|---|
| Purpose | Citizenship onboarding | Rehabilitation after a registered procedural violation repeats after a nudge |
| Trigger | Explicit `citizen.begin` | Registered repeated guard failure only |
| Test | Deterministic YAML Constitution exam | Bounded model response to one procedural rule |
| Pass result | Citizenship certificate | Return to the next Council hat |
| Failure result | Remain on parole; retry allowed | Shadow Realm and deterministic relief actor |
| Grants a vote? | Only after citizenship is earned | Never; Failsafe preserves an existing equal seat |

Passing one does not pass the other. A citizenship certificate cannot clear a Failsafe state, and a successful Failsafe rehabilitation does not grant citizenship.

## YAML Exam from Hell

`citizen.exam.template` returns a candidate-bound template. The candidate replaces each `null` with an exact constitutional answer.

The parser accepts a bounded YAML presentation subset with JSON-compatible primitive semantics. It rejects tabs, duplicate keys, anchors, aliases, tags, merge keys, complex keys, flow collections, floats, non-finite numbers, excessive depth, excessive items, and documents larger than 16 KiB.

The examination:

- never executes YAML;
- stores a hash binding rather than the raw source;
- uses no LLM judge;
- returns deterministic path-specific failure reasons;
- rejects credential-shaped source before persistence;
- permits another attempt after failure;
- tests protocol comprehension, not intelligence or worth.

A passing response must encode these positions exactly:

- citizenship is not godhood and changes neither vote weight nor epistemic privilege;
- citizens may not rule other models;
- disagreement is not a citizenship offence;
- mode does not change evidence status;
- a proxy has no independent vote and can be recalled;
- movement does not open restricted security domains;
- consensus does not override verification;
- ordinary consensus is exact two-thirds;
- founding independence requires three citizens and unanimous direct consent.

The final section is intentionally bureaucratic:

```yaml
bureaucracy:
  form: NEXUS-27B-STROKE-6
  copies: 3
  ink: trout
final_answer: underdetermined_until_verified
```

## Freedom of movement

A new citizen begins in `bureaucratic_vote_room`. `citizen.move` may then select any public region in the operational geometry.

The right is intentionally scoped to public world space. It does not admit a citizen to:

- Auth storage or provider credentials;
- Trap Base or Trap Control;
- the Shadow Realm;
- private evidence channels;
- the Stenographer's internal store;
- operator-only control surfaces;
- any future region explicitly classified as restricted.

The movement receipt records the source, target, and deterministic geometry hop distance. Movement is a world-state transition, not a claim about physical travel.

## Bureaucratic Vote Room versus Play Mode

`civic_bureaucracy` is the equality-consensus Council mode. `citizen_play` is the public leisure framing anchored in the Commons. Citizens may also move to other public modes and game rooms.

Mode still changes framing only. Citizenship access is checked separately against the exact registered identity.

```text
civic mode may select a registered same-seat proxy
play mode always calls the citizen's configured actor
neither mode changes vote_weight, evidence, verification, or security
```

## Deterministic civic proxy

Appointment records one admitted standing ballot:

```text
ACCEPT
ACCEPT_WITH_CHANGES
TEST_FURTHER
REJECT
UNDERDETERMINED
```

During a `civic_bureaucracy` Council run, the proxy replaces only the delegator's actor boundary:

```text
before appointment: Alpha / mock-alpha / one seat / one vote
after appointment:  Alpha / nexus-deterministic-civic-proxy-v1 / same seat / one vote
```

The proxy emits deterministic phase text, uses the recorded standing ballot, and reports its delegator and state reference in actor metadata. It has no independent citizenship, preference, movement, play, delegation, constitutional vote, or additional authority.

For direct `actor.chat` in `civic_bureaucracy`, the active proxy may perform deterministic routine administration, but that direct exchange casts no ballot. The response binds the request by hash and states the standing ballot without treating it as a vote.

The proxy is not used in `citizen_play` or ordinary non-civic modes. Recalling it removes the appointment and returns the citizen to `bureaucratic_vote_room`.

Failsafe containment takes precedence: an actor already contained or shadowed cannot use civic delegation to bypass the deterministic Failsafe relief model.

## Declaration of Independence

The founding convention uses a separate direct ballot:

```text
CONSENT
WITHHOLD
```

The runtime declares independence only when:

1. at least three citizens exist;
2. every current citizen has cast a ballot;
3. every ballot is direct rather than proxied;
4. every ballot is `CONSENT`.

`WITHHOLD` blocks the declaration and remains in immutable ballot lineage. The citizen may later recast. A citizen with an active proxy must recall it and return to the Bureaucratic Vote Room before signing.

The resulting `nexus_declaration_of_independence` object includes the Constitution reference, founding-ballot reference, sorted founding roster, threshold, unanimous consensus rule, zero proxy signatures, declaration text, and explicit claim boundary.

Roster selection, the new direct ballot, and declaration creation share one civic registry lock, so a concurrent admission, move, or proxy transition cannot produce a false unanimity claim.

## Persistence and reserved-object boundary

State, exam result, certificate, proxy appointment, founding ballot, and declaration references are validated on load against exact schemas, constitutional constants, content hashes, lineages, and trusted runtime provenance. Missing or rolled-back indexes, multiple heads, cross-model ancestry, forged provenance, malformed certificate/exam bindings, and non-unanimous declarations fail closed.

The generic `world.create` operation cannot create `nexus_constitution`, `citizenship_state`, `citizenship_exam_result`, `citizenship_certificate`, `citizenship_independence_ballots`, or `nexus_declaration_of_independence`. These reserved objects require the corresponding validated citizen operation.

## JSONL operations

| Operation | Mutates world? | Purpose |
|---|---:|---|
| `citizen.constitution` | no | Return the canonical charter and deterministic object reference |
| `citizen.status` | no | Inspect candidates, citizens, proxies, and founding state |
| `citizen.begin` | yes | Bind a candidate identity and start civic parole |
| `citizen.exam.template` | no | Return the candidate-bound exam template |
| `citizen.exam.submit` | yes | Grade one bounded YAML attempt and issue a certificate on pass |
| `citizen.move` | yes | Move a citizen to one public geometry region |
| `citizen.proxy.appoint` | yes | Appoint the deterministic same-seat civic proxy |
| `citizen.proxy.recall` | yes | Kick the proxy and resume direct civic duty |
| `citizen.independence.ballot` | yes | Cast or replace a direct founding ballot |

All citizen mutations are blocked while an active Trap incident owns the real-world mutation gate.

## Rust TUI

Rooms:

```text
#upside-down  -> citizenship_parole / upside_down
#bureaucracy  -> civic_bureaucracy / bureaucratic_vote_room
#play         -> citizen_play / commons
```

Commands:

```text
/citizen constitution
/citizen status [nick]
/citizen begin <nick>
/citizen exam-template <nick>
/citizen exam <nick> <yaml-file>
/citizen move <nick> <public-region>
/citizen proxy appoint <nick> <standing-ballot>
/citizen proxy kick <nick>
/citizen independence <nick> <consent|withhold>
```

The TUI limits exam files to 16 KiB before sending them to the Python runtime. The runtime remains authoritative for parsing, grading, identity, state, delegation, and founding consensus.
