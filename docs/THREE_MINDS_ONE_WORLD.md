# Alpha11 — Three Minds, One World

Alpha11 is the NEXUS integration demonstration. It does not introduce a new source of authority.

It proves that the already-merged instrument, persistence, world-presence and provider seams can participate in one inspectable workflow without silently changing what any result means.

## Reference scenario

The deterministic reference demo uses one file-backed WorldStore and three sequential reference actors:

```text
Mind-A
  enters Observatory
  -> declares candidate fixture [2,3,5,7,11,25]
  -> creates PROPOSED hypothesis
  -> creates PLANNED experiment
  -> executes admitted primality instrument on [2,3,5,7,11]
  -> records OBSERVED experiment
  -> leaves

Mind-B
  reopens the same WorldStore
  -> rediscovers Mind-A hypothesis and experiment by alpha8 search
  -> reruns the exact admitted instrument on [2,3,5,7,11]
  -> requires the complete instrument bundle to be byte-identical
  -> records critique: value 25 was never tested
  -> creates CHALLENGED hypothesis descendant
  -> records replay experiment descendant
  -> moves shared thread to Archive
  -> leaves

Mind-C
  reopens the same WorldStore
  -> rediscovers Mind-B challenged lineage
  -> proposes explicit bounded falsifier [25]
  -> executes admitted instrument on [25]
  -> requires composite_values == [25]
  -> closes experiment lineage
  -> retires the workflow hypothesis
  -> creates receipt-verified descendant
  -> moves shared thread through Agora back to Observatory
```

The actors are deterministic reference identities. The reference run does **not** claim that three live models generated these actions.

```text
REFERENCE_ACTOR != LIVE_MODEL_EXECUTION
```

## Why the baseline is intentionally incomplete

The declared candidate fixture is:

```text
[2,3,5,7,11,25]
```

Mind-A initially tests only:

```text
[2,3,5,7,11]
```

All five are prime. That makes the first instrument result correct but insufficient for the larger declared claim.

Mind-B proves reproducibility by reproducing the complete alpha7 instrument bundle exactly. It then records the missing-scope critique.

Mind-C evaluates the previously omitted value `25`, which the admitted bounded primality instrument classifies as composite with factor `5`.

This is deliberately tiny. The point is not number theory. The point is to make these distinctions executable:

```text
REPLAY != EMPIRICAL_CONFIRMATION
INSTRUMENT_RESULT != GENERAL_TRUTH
TEST_SCOPE MATTERS
```

## Persistent handoff

The demo does not keep one Python service instance alive for all three minds.

Each stage opens the file-backed WorldStore again. The next actor must locate the earlier alpha8 hypothesis and experiment objects through the persistent-world search surface and then inspect the exact content-addressed refs.

A run fails if the expected predecessor cannot be rediscovered.

This gives alpha11 a meaningful persistence claim:

> The exact world objects survive the actor handoff and are independently addressable after reopening storage.

It does not make their semantic content true.

```text
PERSISTENT_LINEAGE != TRUTH
```

## World presence and movement

The shared research thread is bound to the existing LATTICE profile with storage-only authority.

The deterministic handoff path is:

```text
Observatory  L[0,0,0]
    ->
Archive      L[0,0,1]
    ->
Agora        L[0,1,1]
    ->
Observatory  L[1,1,1]
```

Every regional move is an existing adjacent `world.move` transition. Verification requires a four-event lineage: one placement plus three moves.

The addresses are storage identities only.

```text
LATTICE_POSITION != COGNITIVE_COORDINATE
```

## Instrument receipts

Alpha11 admits no new instrument.

It uses only the already-admitted:

```text
nexus.integer-primality/1
```

Every execution is stored in an alpha11 instrument-record WorldObject containing the complete alpha7 bundle. Verification reruns `verify_instrument_receipt` against all three records.

Mind-B's replay must reproduce Mind-A's complete instrument bundle exactly, including:

```text
instrument-intent
instrument-execution
instrument-receipt
```

Mind-C's verified descendant binds the exact falsifier execution and receipt.

The word `verified` therefore means only:

```text
receipt + exact admitted input verified
```

It does not mean:

```text
semantic truth verified
scientific theory verified
provider output verified as factual
```

```text
VERIFIED_DESCENDANT != SEMANTIC_TRUTH
```

## Deterministic Council and minority preservation

After Mind-C closes the lineage, the same world runs a network-free three-member deterministic Council:

```text
Mind-A  skeptical  -> TEST_FURTHER
Mind-B  balanced   -> TEST_FURTHER
Mind-C  supportive -> ACCEPT_WITH_CHANGES
```

The two `TEST_FURTHER` ballots meet the default two-thirds threshold. Mind-C remains a preserved minority report.

Alpha11 then queries that minority through the alpha8 `world.minority.search` semantics and requires exactly one matching report.

```text
MINORITY_REPORT != EVIDENCE_PROMOTION
MULTI_MODEL_CONSENSUS != EVIDENCE
```

## Clean-root replay verification

The hermetic self-test runs the entire reference scenario twice in two independent fresh world roots.

It requires:

- identical alpha11 manifests;
- identical content-addressed summary refs;
- exact Mind-B replay of Mind-A's instrument bundle;
- exact Mind-C `[25]` counterexample result;
- verified four-event world-presence lineage;
- exactly one preserved minority report.

This demonstrates deterministic construction and replay of the reference workflow.

It does not transform deterministic reproducibility into external empirical evidence.

## Running the reference demo

From the repository root:

```bash
PYTHONPATH=src python3 tools/three_minds_one_world.py \
  --world /tmp/nexus-alpha11-world
```

Optionally write the compact deterministic manifest to a new absolute path:

```bash
PYTHONPATH=src python3 tools/three_minds_one_world.py \
  --world /tmp/nexus-alpha11-world \
  --manifest-output /tmp/nexus-alpha11-manifest.json
```

Run the hermetic conformance battery with:

```bash
PYTHONPATH=src python3 tools/three_minds_one_world.py --self-test
```

## Optional mixed-provider Council

Alpha11 also exposes a separate operator-authorized integration demonstration:

```text
xAI remote peer
+
loopback Ollama local/open peer
+
deterministic mock reference peer
```

This path is **not** part of hermetic CI because it performs real provider/local-model inference.

It accepts an xAI auth-profile name only. It never accepts the raw xAI credential.

Example:

```bash
PYTHONPATH=src python3 tools/three_minds_one_world.py \
  --mixed-provider \
  --authorize-mixed-provider \
  --mixed-world /tmp/nexus-alpha11-mixed \
  --xai-profile default \
  --xai-model grok-4.5 \
  --ollama-model qwen2.5:7b
```

The tool first runs the admitted xAI connection test and model discovery. It then delegates the Council to the existing runtime.

Only a compact result summary is printed. Provider phase text is not copied into the tool's summary.

The request does not contain `vote_weight` or `epistemic_privilege` fields. Those remain runtime-owned constitutional properties.

```text
PROVIDER_IDENTITY != VOTE_WEIGHT
PROVIDER_IDENTITY != EPISTEMIC_PRIVILEGE
PROVIDER_CONSENSUS != EVIDENCE
```

## What alpha11 establishes

The reference demo can establish that, under the exact NEXUS contracts used:

- content-addressed research objects survive separate actor openings of the same world;
- alpha8 hypothesis and experiment lineage can be discovered and extended;
- alpha7 instrument execution can be reproduced exactly;
- a bounded counterexample can create a new workflow descendant without widening receipt verification into truth;
- LATTICE presence can preserve explicit handoff history;
- Council disagreement remains durable as a minority report;
- the mixed-provider seam can be exercised separately without giving provider identity authority.

It does not establish consciousness, cognition geometry, scientific truth, provider superiority, or automatic evidence promotion.
