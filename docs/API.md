# NEXUS Reference Runtime API

## Status

The JSONL control API remains intentionally small and **mock-instantiation-only** while the provider-neutral actor boundary is tested separately with a real local Ollama integration.

Alpha4 adds **World Modes** and a deterministic **named-region Geometry Layer**. Authentication remains deferred.

Protocol identifier:

```text
nexus/0.3
```

Runtime identifier:

```text
2.0.0-alpha4
```

Current distinction:

```text
JSONL control API
  council.run -> mock actors only
  world modes -> analytical / historical / cultural / meme_casual
  geometry -> named-regions-v1
  network -> none

Python actor implementations
  mock   -> deterministic / network-free
  ollama -> local loopback integration fixture
```

The Ollama actor is not yet an operator-configurable provider in the JSONL API. Provider setup and authentication remain later milestones.

## Transport

The reference control transport is JSON Lines over standard input/output.

```text
future Rust TUI
     |
     | one JSON object per line
     v
python -m nexus_runtime
     |
     +-- one JSON response per line
```

This keeps the trusted control plane independent of HTTP and browser state. The local Ollama actor uses its own adapter boundary to reach an explicitly configured loopback Ollama service.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --demo
```

Persistent development world:

```bash
python -m nexus_runtime --world .nexus-world
```

## Health

Request:

```json
{"request_id":"1","operation":"system.health"}
```

Current response shape:

```json
{
  "request_id": "1",
  "status": "ok",
  "protocol": "nexus/0.3",
  "runtime_version": "2.0.0-alpha4",
  "network": "none",
  "adapters": ["mock"],
  "actor_backends_available": ["mock", "ollama"],
  "world_modes": ["analytical", "cultural", "historical", "meme_casual"],
  "geometry": "named-regions-v1"
}
```

`network: none` describes the JSONL control API's active posture. The separately tested Ollama actor can make loopback-only requests when explicitly constructed by integration code.

## Operations

Current control operations:

```text
system.health
system.operations
security.scrub_preview
world.create
world.inspect
world.modes
world.geometry
world.geometry.distance
receipt.verify
council.run
```

They are reference operations, not a declaration that the World Protocol is complete.

## World modes

Request:

```json
{"operation":"world.modes"}
```

Built-in modes:

```text
analytical  -> Observatory
historical  -> Archive
cultural    -> Agora
meme_casual -> Commons
```

A mode changes framing and context. It does **not** change:

- vote weight;
- evidence state;
- verification;
- secret handling;
- Equality Guard behavior;
- Council thresholds.

The selected mode is frozen into Council session identity.

## Geometry

Request:

```json
{"operation":"world.geometry"}
```

The initial geometry is a tiny deterministic named-region topology:

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /
                       \           /
                        COMMONS
                      Meme/Casual
                         (2,1)
```

The geometry is explicitly operational metadata, **not a claim that cognition or culture literally occupies Euclidean space**.

Distance request:

```json
{
  "operation":"world.geometry.distance",
  "source_region_id":"archive",
  "target_region_id":"commons"
}
```

returns the shortest adjacency hop count.

## Secret scrubber

`security.scrub_preview` lets the operator inspect high-confidence local redaction before semantic text becomes world/Council state.

Detected values are replaced by deterministic placeholders such as:

```text
<REDACTED:OPENAI_STYLE_TOKEN:1>
```

The placeholder contains no hash or encoded secret material. The scrubber remains defence in depth rather than complete DLP.

The live Ollama integration adds an additional acceptance assertion: the raw injected test secret must not appear in any prompt crossing the Ollama adapter boundary.

## Mock Council run

The public reference operation still accepts mock members only. Alpha4 adds the optional `mode` field:

```json
{
  "request_id": "c1",
  "operation": "council.run",
  "question": "Why does this joke work in one culture and fail in another?",
  "mode": "cultural",
  "members": [
    {"member_id":"A","model_id":"mock-a","profile":"balanced"},
    {"member_id":"B","model_id":"mock-b","profile":"skeptical"},
    {"member_id":"C","model_id":"mock-c","profile":"supportive"}
  ],
  "evidence_state": "UNTESTED"
}
```

If `mode` is omitted, NEXUS uses `analytical`.

A Council session now creates a content-addressed `world_presence` object containing:

```text
mode_id
mode_label
region_id
region_label
coordinates
member_ids
question_ref
geometry_id
```

The Council session references this presence object, so identical questions run in different modes have distinct lineage.

Attempting to supply a non-mock adapter through the JSONL operation is still rejected. The later provider-setup API will introduce an explicit configured-adapter path rather than overloading this fixture interface.

## Provider-neutral actor contract

Internally, the Council coordinator consumes a `CouncilActor` contract:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

`PhaseContext` now also carries:

```text
mode_id
mode_instruction
geometry_region_id
```

Adapters receive these values as context. The runtime remains authoritative about what mode is active and where the Council is placed.

The coordinator retains ownership of:

- roster and member IDs;
- fixed `vote_weight = 1`;
- `epistemic_privilege = none`;
- evidence snapshot;
- world mode identity;
- geometry placement;
- phase ordering;
- blind same-phase collection;
- Equality Guard;
- ballot count and tally;
- Council session persistence;
- receipt creation.

An adapter therefore supplies model content, not Council authority or world identity.

## Live Ollama integration fixture

The separate integration workflow creates:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier names and companies are fictional testing personas.

The integration test checks the local real-model boundary, Equality Guard, secret crossing, Council phase/ballot completeness, and non-replayable receipt marking.

World modes are propagated through the same `PhaseContext` seam, but alpha4 does not add a new expensive live-Ollama matrix for every mode. Deterministic mock tests cover mode and geometry invariants first.

## Exact consensus arithmetic

The default threshold remains the exact fraction:

```json
{"numerator":2,"denominator":3}
```

Support is evaluated using integer arithmetic equivalent to:

```text
supporting_votes * 3 >= total_votes * 2
```

Therefore 2–1 reaches consensus while 3–2 does not.

## World objects and receipts

`world.create` creates content-addressed development objects after recursive secret scrubbing of semantic payload/provenance strings. `world.inspect` retrieves an `object:<sha256>` reference.

Mock-only executions remain eligible for deterministic replay marking. A Council containing a live Ollama actor is explicitly marked:

```text
replayable: false
```

A Modelfile seed may improve fixture stability, but NEXUS does not treat that as a replay guarantee across Ollama/model/runtime versions.

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

Remote-provider authentication, rate-limit semantics, cloud HTTP errors, and account setup remain outside the alpha4 control API.
