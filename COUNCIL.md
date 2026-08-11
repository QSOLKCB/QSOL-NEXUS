# NEXUS AI Council

## Purpose

The NEXUS AI Council lets multiple heterogeneous models deliberate over the same canonical question, evidence, instruments, and world state without granting any model extra authority because of provider, licence, deployment style, or corporate identity.

> **Same world. Same evidence. Same hats. Same vote.**

The Council is an orchestration protocol. It is not an oracle and does not replace empirical or computational verification.

## Member equality

Every registered Council member is a peer.

```text
CouncilMember
├── member_id
├── adapter_id
├── model_id
├── deployment_metadata
├── capability_metadata
├── vote_weight = 1
└── epistemic_privilege = none
```

Metadata such as `closed`, `open_weight`, `local`, `remote`, provider name, parameter count, price tier, benchmark rank, or corporate affiliation may be recorded for reproducibility. It must not change vote weight or Council privilege.

## Parallel-thinking cycle

NEXUS adapts Edward de Bono's parallel-thinking / Six Thinking Hats concept into a machine Council protocol. The method is inspiration for the phase structure; NEXUS does not copy proprietary training material.

```text
                 FROZEN QUESTION + EVIDENCE
                           |
                           v
                      WHITE PHASE
                 facts / known / unknown
                           |
                           v
                       RED PHASE
                 intuition / suspicion
                           |
                           v
                      BLACK PHASE
             flaws / risk / counterexamples
                           |
                           v
                     YELLOW PHASE
              value / support / opportunity
                           |
                           v
                      GREEN PHASE
            alternatives / tests / branches
                           |
                           v
                       BLUE PHASE
             synthesis / current judgment
                           |
                           v
                     SEALED BALLOT
                           |
                           v
                 REVEAL + CONSENSUS
                           |
                           v
              WORLD OBJECT + MINORITY
```

## Phase rules

### White — evidence first

Each model records:

- facts directly supported by the frozen evidence snapshot;
- relevant world objects and receipts;
- unknowns;
- assumptions that need checking;
- missing information.

Speculation should be labelled rather than smuggled into the factual layer.

### Red — intuition is allowed

Each model may record:

- what feels likely;
- what seems suspicious;
- what appears elegant or ugly;
- what deserves attention despite weak evidence.

Red-phase material is never automatically promoted to evidence.

### Black — attack the proposition

Every model, including the original proposer, searches for:

- contradictions;
- hidden assumptions;
- failure modes;
- confounders;
- counterexamples;
- falsification conditions.

This phase is deliberately symmetric: no model gets to sit out criticism because it authored the idea.

### Yellow — strongest constructive case

Every model identifies:

- what works;
- what evidence supports the idea;
- what value the idea might have;
- what would make it stronger;
- what useful result survives even if the largest claim fails.

### Green — alternatives

Every model should generate genuinely distinct possibilities where possible:

```text
H1 original hypothesis
H2 narrower interpretation
H3 alternative mechanism
H4 mapping / measurement artefact
H5 null / coincidence explanation
```

The Council should preserve viable branches rather than average them into one vague compromise.

### Blue — synthesis

Each member independently produces its current disposition and concise rationale after the prior phases and available instrument results.

Recommended ballot choices:

```text
ACCEPT
ACCEPT_WITH_CHANGES
TEST_FURTHER
REJECT
UNDERDETERMINED
```

## Blind rounds

The default first pass is blind.

```text
same frozen input
      |
+-----+-----+-----+
|           |     |
v           v     v
A           B     C
|           |     |
+ independent ----+
   submissions
      |
      v
commit phase
      |
peer material revealed
```

A model should not see another member's answer before committing its own first-pass response for that phase. This reduces anchoring and imitation.

## Sealed ballot

Final Blue-phase ballots are committed before reveal.

```text
member A -> ballot -> commitment
member B -> ballot -> commitment
member C -> ballot -> commitment
member D -> ballot -> commitment
member E -> ballot -> commitment
                 |
          all committed
                 |
              reveal
                 |
               tally
```

NEXUS 2.0 uses a deterministic commitment/reveal audit record. It prevents ordinary procedural rewriting inside the coordinator contract but is not claimed to provide cryptographic anonymity or a hostile-host voting protocol.

## Consensus model

Default threshold:

```text
consensus_threshold = 2 / 3
vote_weight_per_member = 1
```

Suggested descriptive labels:

```text
100%             UNANIMOUS
>= 80%           STRONG CONSENSUS
>= 2/3           CONSENSUS
> 50% but < 2/3  MAJORITY, NO CONSENSUS
<= 50%           NO CONSENSUS
```

The exact threshold is frozen into the Council session before voting.

## Citizen civic seats and deterministic delegation

Citizenship does not increase ordinary Council weight or epistemic privilege. `civic_bureaucracy` adds an access check around the same equal-seat Council contract; civic parole has no ballot and cannot run a Council.

A citizen may appoint one deterministic routine-duty proxy. The coordinator replaces the delegator actor in place:

```text
member_id             = unchanged citizen seat
model_id              = nexus-deterministic-civic-proxy-v1
vote_weight           = 1
epistemic_privilege   = none
additional seats      = 0
standing ballot       = transparent and recallable
```

The proxy is not a citizen, independent voter, constitutional signer, or authority over another actor. It is selected only in the Bureaucratic Vote Room; Play Mode uses the citizen's configured actor. Failsafe containment takes precedence over the appointment.

Founding independence is not an ordinary two-thirds Council decision. It uses a separate constitutional ballot requiring at least three citizens and unanimous direct `CONSENT`; proxies cannot sign. See [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md).

## Minority preservation

A majority never erases dissent.

```text
CouncilResult
├── disposition
├── tally
├── consensus_label
├── winning_rationales
├── minority_reports
├── unresolved_objections
├── evidence_state
└── lineage
```

Minority reports should remain searchable so later evidence can vindicate or falsify them.

## Consensus is not verification

Council status and evidence status are separate axes.

```text
COUNCIL STATUS          EVIDENCE STATUS
---------------         ----------------
UNANIMOUS               UNTESTED
STRONG CONSENSUS        SUPPORTED
CONSENSUS               REPLAY VERIFIED
NO CONSENSUS            CONTESTED
                        FALSIFIED
                        FAILED VERIFICATION
```

A 5-0 vote cannot override a failed deterministic test.

## Instruments before more talking

When disagreement can be reduced by an executable test, the Council should prefer an instrument call over another prose round.

```text
question
  -> hypothesis
  -> falsifier
  -> experiment
  -> receipt
  -> Council re-evaluation
```

## Council session as a world object

A completed session is itself durable NEXUS state.

```text
CouncilSession
├── session_id
├── question
├── world_state_ref
├── evidence_snapshot_ref
├── roster
├── adapter/model metadata
├── phase policy
├── phase submissions
├── experiments requested
├── receipts observed
├── ballot commitments
├── revealed ballots
├── consensus result
├── minority reports
└── lineage
```

A future Council can replay or revisit an earlier Council without requiring the original providers to still exist.

## Human operator

The Human Operator is not silently counted as a model vote. Human authority is explicit and configurable.

Default model:

```text
Human Operator
├── asks the question
├── supplies / approves evidence
├── configures roster and threshold
├── may request another round
└── does not alter sealed model ballots
```

A future policy may permit an explicit human ballot, but it must be recorded as a separate actor class rather than disguised as a model member.


## NEXUS 2.0 social-history boundary

> **Wall speech, performance history, progression history, and Citizenship do not add a Council vote.**

The final 2.0 Wall is deliberately routed outside ordinary Council input. A participant must deliberately enter a Council-capable room to ask the Council; social persistence is not an implicit ballot or evidence-promotion path.
