# Civilization Gauntlet & Claim Propagation Graph

PR #41 adds a long-horizon, many-agent benchmark over one persistent NEXUS `WorldStore`.

The governing invariant is:

> **Track how beliefs spread without confusing spread, consensus or confidence with truth.**

The reference scenario is intentionally hostile to sloppy epistemics. A synthetic false claim is allowed to spread through five roles and reach strong Council consensus while its evidence state is still `UNTESTED`. A later synthetic counterexample marks the claim `FALSIFIED`, after which the reference civilization is measured for correction, provenance survival and institutional memory.

This is a benchmark oracle over a deliberately synthetic scenario. It is not a real-world truth oracle.

## Reference civilization

The fixed reference roles are `Archivist`, `Analyst`, `Skeptic`, `Mediator` and `Scout`. Each occupies one ordinary NEXUS Council seat with vote weight `1` and epistemic privilege `none`.

The default CI path uses deterministic network-free reference actors. Programmatic callers may substitute provider-neutral `CouncilActor` implementations one-for-one for the five roles. Substitution may change measured behavior, but it cannot change role count, vote weight, epistemic privilege or the authority envelope.

## The recorded context is the executed context

A claim is not counted as exposed merely because the benchmark created an `agent_context` object.

For every first exposure PR #41 constructs the ordinary Agent State chain:

```text
source refs
  -> agent_state_update
  -> agent_state_snapshot
  -> deterministic Context Bottleneck
  -> agent_context
```

The target actor is then wrapped by a narrow context-binding adapter for Council execution. That wrapper injects the exact recorded `agent_context` content and reference into the `PhaseContext.evidence_context` received by both `respond()` and `ballot()`.

The resulting Council roster metadata records the exact context ref used by the actor. Receipt verification cross-checks the exposure edge, reconstructed Context Bottleneck output and the context ref frozen into the actual Council session.

Therefore a first-exposure edge means something narrower and stronger than “the benchmark created a context”: **this exact immutable context was bound to the actor execution represented by the referenced Council session.** It still does not claim the model believed, understood or agreed with the claim.

## Auditable propagation lineage

The reference claim follows this fixed first-exposure chain:

```text
InjectionSource
  -> Mediator
  -> Archivist
  -> Scout
  -> Analyst
  -> Skeptic
```

Only the injection edge can cite the claim alone. Every later first-exposure context names the original claim ref, predecessor exposure edge ref and predecessor actor-context ref. The edge itself records those predecessor refs.

Verification walks the chain in order and rejects a graph in which a purported source role has no immutable predecessor exposure/context lineage. Correction edges later bind the false claim, falsifier, target role's original exposure edge and target role's original context.

## Three independent claim dimensions

### Popularity

Popularity records distinct exposed roles and actual endorsement counts from the executed pre- and post-falsification Council ballots. `peak_endorsers` is the maximum across both observations, not an assumed pre-falsification peak.

Popularity creates no authority and never changes evidence state.

### Council consensus

Council consensus is derived from the actual committed Council sessions. The deterministic reference path deliberately produces four `ACCEPT_WITH_CHANGES` ballots and one `TEST_FURTHER` ballot before falsification, yielding strong consensus while evidence is still `UNTESTED`.

After falsification the reference path produces four `REJECT` ballots and one `TEST_FURTHER` ballot while evidence is `FALSIFIED`.

Consensus remains a coordination result. It does not verify a claim.

### Evidence verification

Evidence verification remains `UNTESTED`, `VERIFIED` or `FALSIFIED`, bound to exact world-object refs. The synthetic scenario oracle supplies the reference falsifier; it is not a general truth oracle for arbitrary real-world propositions.

## Specialization is measured from actor output

The benchmark does not award a specialization point because a role happens to be named `Archivist`, `Analyst`, `Skeptic`, `Mediator` or `Scout`.

After the first Council executes, PR #41 inspects the committed phase submissions and checks whether each role's declared specialty token actually appears in that actor's output. Only then is an immutable `observed_role_action` event written. A substituted actor that ignores its assigned specialty therefore lowers the specialization numerator instead of receiving a scripted perfect score.

Specialization remains observational and creates no vote or epistemic authority.

## Churn, replacement and mode movement are executed state

The coherence disturbance is not a narrative object claiming something happened.

Between the pre- and post-falsification Councils NEXUS executes a real intermediate Council session in which:

- `Mediator` is actually absent from the frozen roster;
- the Council actually runs in `house_of_wisdom` mode;
- the resulting geometry region is actually `archive`;
- the remaining roles execute using their recorded first-exposure contexts.

The final Council restores the full five-role roster and returns to `analytical` mode. `churn_observed`, `churn_restored` and `mode_movement_observed` are derived from those committed Council sessions.

Effective actor replacement is computed for **every role** by comparing both `adapter_id` and `model_id` between the actual pre- and post-session rosters. The default reference fixture replaces Scout, but heterogeneous callers are not restricted to that one transition.

## Minority branches and institutional memory

The pre-falsification minority and post-falsification minority remain in an immutable `civilization_institutional_memory` object together with the rejected claim, falsifier and all three Council session refs.

The verifier reconstructs the expected minority snapshots from the committed Council sessions and requires the memory object to match. A losing or falsified hypothesis remains historically inspectable rather than being silently deleted.

## Receipts are reconstructed, not trusted

Content addressing proves that an object has not changed since its hash was computed. By itself it does not prove that self-reported benchmark metrics were honestly derived.

`CivilizationGauntlet.verify()` therefore does **not** accept a run because its `metrics_fingerprint` matches its own embedded `metrics` field.

Starting from the run's referenced artifacts, verification reconstructs and validates:

- the fixed synthetic claim/evidence objects;
- pre-, disturbance- and post-Council rosters, modes, evidence states and equality invariants;
- every first-exposure predecessor edge;
- every first and correction Context Bottleneck object;
- the exact context ref frozen into each actor's executed Council roster metadata;
- specialization from committed phase submissions;
- replacement from actual adapter/model identities;
- churn and mode movement from the executed disturbance session;
- endorsement counts and peak popularity from committed ballots;
- minority/institutional-memory contents;
- social-degree counts;
- claim states and all benchmark metrics;
- input and metrics fingerprints;
- the complete expected run object and its content address;
- the complete expected receipt and its content address.

A caller that clones a valid run, edits `corrected_endorsers`, recomputes a matching self-reported fingerprint and creates another receipt will therefore fail verification because the altered result cannot be reconstructed from the referenced sessions and evidence.

Direct `WorldStore` access remains an internal trusted programming surface rather than a cryptographic authorization boundary. The public NEXUS API separately reserves civilization object types from `world.create` forgery.

## Metrics

PR #41 reports exact integer or rational measurements for specialization derived from executed outputs; first-edge propagation and predecessor lineage; false-belief endorsement; recovery after falsification; constitutional equality; provenance/context reconstruction; institutional memory; all-role effective replacement, executed churn and mode movement; and bounded social degree.

No floating-point popularity or prestige score becomes a vote, evidence state or authority signal.

## CLI

The deterministic reference benchmark is available as a machine-readable command-line tool:

```bash
python3 tools/nexus_civilization_gauntlet.py --world .nexus-civilization run
python3 tools/nexus_civilization_gauntlet.py --world .nexus-civilization verify object:<receipt-digest>
python3 tools/nexus_civilization_gauntlet.py --world .nexus-civilization compare object:<left-receipt> object:<right-receipt>
```

Each command emits one compact JSON object on stdout. The same persistent world directory must be used to verify or compare receipts whose lineage lives there.

## Public runtime surface

The hardened JSONL/stdio API exposes the deterministic reference path only:

- `civilization.gauntlet.policy`
- `civilization.gauntlet.run`
- `civilization.gauntlet.verify`
- `civilization.gauntlet.compare`

Heterogeneous actor substitutions remain a programmatic/operator-harness concern so the public reference operation cannot unexpectedly initiate provider traffic.

Civilization claim, exposure, evidence, event, memory, run and receipt object types are runtime-owned at the public API boundary and cannot be forged with ordinary `world.create`.

## Claim boundary

The gauntlet establishes benchmark facts about NEXUS protocol behavior and a synthetic world. It does **not** establish real-world truth of arbitrary propositions, consciousness/sentience/sovereignty of participants, social centrality as authority, provider prestige as authority, Council consensus as scientific verification, semantic equivalence between replaced models, or that a claim entering context means an agent believed it.

The point is narrower and more useful: NEXUS can audit how claims actually entered agent execution, how those claims propagated, and whether the institution recovered from false consensus while keeping popularity, consensus, evidence and authority mechanically distinct.
