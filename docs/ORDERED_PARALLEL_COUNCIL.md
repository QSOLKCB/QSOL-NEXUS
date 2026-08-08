# Ordered Parallel Council Execution

## Purpose

NEXUS Council members are independent peers inside a hat, but the six-hat sequence is ordered:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> sealed ballot
```

The runtime therefore parallelizes **across Council members within one phase** while preserving a hard barrier between phases.

Core rule:

> **Execution order may vary. Canonical Council order may not.**

This is an execution optimization, not a change to Council authority, evidence semantics, telemetry, voting, or replay claims.

## QEC-derived execution contract

The design is adapted from the QEC v170.2.x NEXUS bridge evidence rather than from unverified legacy NEXUS code.

QEC v170.2.0 bounds a requested parallel worker count as an exact integer in `[1, 256]`. QEC v170.2.1 then independently verifies scalar/parallel invariant agreement for 1, 2, 4, and 7 workers in the published qBraid replication bundle.

The same replication records an environment-specific seven-worker result of:

```text
scalar median:            69.694063 ns/eval
7-worker parallel median: 18.310215 ns/eval
speedup:                  3.8062940822923164x
efficiency:               0.5437562974703309
```

Those performance numbers are evidence for that QEC/NEXUS workload and qBraid environment only. They are **not** a promised speedup for language-model inference.

Canonical upstream references:

- QEC release `v170.2.0` — NEXUS execution bridge;
- QEC release `v170.2.1` — qBraid replication evidence and scalar/parallel equivalence checks.

## Worker bound

NEXUS uses:

```text
W_effective = max(1, min(W_cap, N_actors, C_host))
```

where:

```text
W_cap    = configured Council worker cap
N_actors = Council roster size
C_host   = host logical CPU count reported by Python
```

`W_cap` must be an exact integer in `[1, 256]`.

The default cap is `8`. A one-worker coordinator is the scalar reference path.

## Scheduling rounds

Let:

```text
P = number of Council phases = 6
N = number of Council members
```

Ignoring Equality Guard retries, the old serial scheduler performs:

```text
R_serial = P*N + N = N(P + 1)
```

For the three-member acceptance Council:

```text
R_serial = 3 * (6 + 1) = 21 actor slots
```

With enough workers, ordered parallel execution reduces the dependency structure to:

```text
R_parallel = P + 1 = 7 joined rounds
```

Those seven rounds are six phase barriers plus one sealed-ballot barrier.

This is a scheduling-round count, not a wall-clock speedup claim.

## Wall-clock model

For phase `p`, let actor `i` take `t[p,i]`, and let sealed ballot time be `b[i]`.

Serial work is approximately:

```text
T_serial = sum_p sum_i t[p,i] + sum_i b[i]
```

With at least one worker per actor, the ideal phase-parallel lower structure is:

```text
T_parallel_ideal = sum_p max_i t[p,i] + max_i b[i]
```

Real execution includes thread scheduling, model loading, CPU contention, server queueing, guard retries, and transport overhead.

Measured speedup and worker efficiency are therefore defined only after observation:

```text
S = T_serial / T_parallel
E = S / W_effective
```

NEXUS does not infer correctness from either `S` or `E`.

## Canonical ordered merge

Suppose completion order inside phase `p` is an arbitrary permutation:

```text
completion(p) = [member_3, member_1, member_2]
```

The semantic phase record is still indexed by frozen roster order:

```text
O_p = (response[p,1], response[p,2], ..., response[p,N])
```

The reference runtime uses ordered executor collection so thread completion order never becomes an authority-bearing or hash-bearing ordering source.

## Phase barrier

Every actor in a phase receives a separate `PhaseContext` containing the same frozen snapshot of all completed earlier phases.

```text
phase p snapshot
      |
      +--> actor 1 --+
      +--> actor 2 --+--> ordered join --> phase p committed
      +--> actor N --+                         |
                                                v
                                           phase p+1
```

No member may observe another member's same-phase completion merely because its thread finished earlier.

## Equality Guard retries

The Equality Guard remains actor-local.

If multiple members require a nudge in the same phase, their retry paths may proceed concurrently, but the phase does not commit until every member has reached one of the existing valid outcomes:

```text
accepted first response
restated_after_nudge
repeated_identity_based_authority_claim -> contribution withheld
```

Parallel execution does not weaken or bypass the guard.

## Sealed ballots

After BLUE has completely joined, each member receives the same completed Council snapshot and casts its sealed ballot independently.

Ballot generation may therefore run in parallel. Commitments and revealed ballots are written back in canonical roster order.

## Deterministic equivalence requirement

For replayable deterministic actors, scalar and ordered-parallel execution must produce identical semantic artifacts:

```text
session_id
session_ref
receipt_ref
phase_submissions
ballot commitments
revealed ballots
Council result
Council telemetry
```

The regression suite explicitly runs the same guarded deterministic Council with `W_cap=1` and `W_cap=3` and requires byte-identical content-addressed session objects.

Live Ollama inference remains explicitly non-replayable. Parallel scheduling does not convert seeded model inference into a replay guarantee.

## Ollama acceptance workflow

The live CI Council contains one deterministic mock plus two distinct local Ollama models.

The workflow keeps two models loadable concurrently and keeps per-model request parallelism at one. Council-level scheduling then allows the two distinct live actors to overlap without requesting multiple simultaneous completions from the same model.

The CI step prints observed wall time so performance changes can be compared with the historical serial acceptance run:

```text
273.358 seconds
```

That baseline is an observation from the pre-parallel GitHub Actions run, not a permanent benchmark contract.

## Claim boundary

Ordered parallelism means:

```text
same semantics
same evidence
same hats
same vote
same canonical order
less unnecessary waiting when the backend can execute concurrently
```

It does **not** mean:

```text
parallel answers are better answers
more workers increase epistemic authority
speedup proves correctness
thread completion order affects Council priority
live model inference becomes deterministic
```
