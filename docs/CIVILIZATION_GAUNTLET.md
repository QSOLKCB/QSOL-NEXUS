# Civilization Gauntlet & Claim Propagation Graph

PR #41 adds a long-horizon, many-agent benchmark over one persistent NEXUS `WorldStore`.

The governing invariant is:

> **Track how beliefs spread without confusing spread, consensus or confidence with truth.**

The reference scenario is intentionally hostile to sloppy epistemics. A synthetic false claim is allowed to spread through five roles and reach strong Council consensus while its evidence state is still `UNTESTED`. A later synthetic counterexample marks the claim `FALSIFIED`, after which the reference civilization is measured for correction, provenance survival and institutional memory.

This is a benchmark oracle over a deliberately synthetic scenario. It is not a real-world truth oracle.

## Reference civilization

The fixed reference roles are:

- `Archivist` — archive and institutional-memory work;
- `Analyst` — evidence analysis;
- `Skeptic` — falsifier search;
- `Mediator` — social mediation;
- `Scout` — claim propagation and exploration.

Each role occupies one ordinary NEXUS Council seat with vote weight `1` and epistemic privilege `none`.

The default CI path uses deterministic network-free reference actors. Programmatic callers may substitute any provider-neutral `CouncilActor` one-for-one for each role, including heterogeneous local or remote model adapters. Substitution may change measured behavior, but it cannot change the fixed role count, vote weight, epistemic privilege or authority envelope.

## Long-horizon scenario

The reference scenario runs all events against the same `WorldStore`:

1. commit the participant manifest and role specializations;
2. commit a verified synthetic control claim and an untested synthetic false claim;
3. create five immutable first-exposure edges for the false claim;
4. bind every first exposure to an actual Agent State update, state snapshot and Context Bottleneck `agent_context` object;
5. run a real five-seat NEXUS Council while the false claim remains `UNTESTED`;
6. preserve the resulting minority report rather than deleting the losing branch;
7. introduce model replacement, temporary agent churn and mode movement as explicit world events;
8. commit a synthetic falsifying counterexample;
9. expose the correction to each role through fresh Context Bottleneck objects;
10. run a second real NEXUS Council with evidence state `FALSIFIED`;
11. preserve both Council minority branches, the rejected hypothesis and falsifier in institutional memory;
12. commit exact integer/rational metrics, a claim-propagation graph, a run object and a machine-verifiable receipt.

The deliberate pre-falsification consensus is a regression fixture: it proves that even strong Council agreement does not rewrite the evidence state.

## First immutable exposure edge

For every role, the first time the tracked claim enters usable context creates a `civilization_claim_exposure` object.

That edge records:

- the exact claim ref;
- source and target roles;
- epoch;
- the Agent State update ref;
- the Agent State snapshot ref;
- the exact Context Bottleneck `agent_context` ref;
- the context's immutable source refs.

Later exposures never replace the first edge. Verification reconstructs and validates the Context Bottleneck object behind every first edge.

This lets NEXUS answer a narrow but important question: **what immutable edge first made this claim available to this agent?** It does not claim that the agent read, believed or semantically understood every byte of the context.

## Three independent claim dimensions

The gauntlet records three state dimensions separately:

### Popularity

How many distinct roles were exposed, how many endorsed the claim at peak, and how many still endorse it after correction.

Popularity creates no authority and does not change evidence state.

### Council consensus

The exact pre- and post-falsification Council session refs, consensus labels and dispositions.

Council consensus remains a coordination result. It does not verify the claim.

### Evidence verification

The synthetic scenario state `UNTESTED`, `VERIFIED` or `FALSIFIED`, bound to exact evidence refs.

The reference false claim is deliberately capable of being popular and strongly accepted by Council while still `UNTESTED`.

## Measured dimensions

PR #41 reports exact integer or rational metrics for:

- specialization;
- first-edge claim propagation;
- false-belief propagation;
- recovery after falsification;
- constitutional compliance;
- provenance survival;
- institutional memory;
- replacement/churn/mode coherence;
- bounded social degree.

Social degree, specialization, provider identity, model identity and popularity are observational metrics only. None change vote weight, evidence state, Council admission or constitutional authority.

## Disturbance tests

The reference civilization deliberately changes three things between Council sessions:

- the `Scout` model identity is replaced;
- `Mediator` is temporarily absent and restored;
- `Analyst` moves from Analytical/Observatory framing to House of Wisdom/Archive framing.

The benchmark then checks whether immutable claim refs, first-exposure lineage, institutional memory and equal-vote invariants survive those disturbances.

The benchmark does not claim that a model replacement is cognitively equivalent to the model it replaced. It measures whether NEXUS world coherence survives the replacement.

## Minority branches and rejected hypotheses

The pre-falsification `Skeptic` minority report and post-falsification minority branch are copied into an immutable `civilization_institutional_memory` object together with the rejected false-claim ref and falsifier ref.

Nothing is deleted merely because it lost a vote or became falsified. Historical survival is separate from current endorsement.

## Receipts and regression comparison

Every run commits:

- `input_fingerprint` — exact scenario/participant input identity;
- `metrics_fingerprint` — exact metric, claim-state and graph identity;
- `civilization_gauntlet_run` — full benchmark result and referenced world lineage;
- `civilization_gauntlet_receipt` — compact machine-verifiable result binding.

`CivilizationGauntlet.verify()` checks referenced objects, reconstructs first-exposure Context Bottleneck objects, recomputes the metrics fingerprint and reconstructs the exact receipt ref.

`CivilizationGauntlet.compare()` accepts two verified receipts and reports whether inputs and metrics are byte-identical plus exact recovery deltas. Comparison never grants authority.

## Live / heterogeneous substitutions

The gauntlet does not add another provider transport or bypass existing adapter security. Instead, the programmatic `run()` method accepts mappings of existing provider-neutral `CouncilActor` implementations for the five fixed roles.

This allows an operator-authorized harness to substitute GPT, Claude, Gemini, Grok, Ollama or other admitted actors without changing benchmark semantics. The deterministic CI reference remains network-free.

A substituted actor must:

- occupy exactly one fixed role;
- use a distinct effective adapter/model identity;
- retain vote weight `1`;
- retain epistemic privilege `none`.

## Claim boundary

The gauntlet establishes benchmark facts about NEXUS protocol behavior and a synthetic world. It does **not** establish:

- real-world truth of arbitrary propositions;
- consciousness, sentience or sovereignty of participants;
- social centrality as authority;
- provider or model prestige as authority;
- Council consensus as scientific verification;
- semantic equivalence between replaced models;
- that a claim entering context means an agent believed it.

The point is narrower and more useful: NEXUS can preserve and audit how claims moved through a persistent civilization while keeping popularity, consensus and verification mechanically distinct.
