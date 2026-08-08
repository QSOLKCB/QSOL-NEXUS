# NEXUS Reference Runtime API

## Status

The JSONL control API remains intentionally small and **mock-instantiation-only** while the provider-neutral actor boundary is tested separately with a real local Ollama integration.

Protocol identifier:

```text
nexus/0.2
```

Runtime identifier:

```text
2.0.0-alpha3
```

Current distinction:

```text
JSONL control API
  council.run -> mock actors only
  network -> none

Python actor implementations
  mock   -> deterministic / network-free
  ollama -> local loopback integration fixture
```

The Ollama actor is not yet an operator-configurable provider in the JSONL API. Provider setup belongs in a later CLI/TUI/authentication milestone.

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
  "protocol": "nexus/0.2",
  "runtime_version": "2.0.0-alpha3",
  "network": "none",
  "adapters": ["mock"],
  "actor_backends_available": ["mock", "ollama"]
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
receipt.verify
council.run
```

They are reference operations, not a declaration that the World Protocol is complete.

## Secret scrubber

`security.scrub_preview` lets the operator inspect high-confidence local redaction before semantic text becomes world/Council state.

Detected values are replaced by deterministic placeholders such as:

```text
<REDACTED:OPENAI_STYLE_TOKEN:1>
```

The placeholder contains no hash or encoded secret material. The scrubber remains defence in depth rather than complete DLP.

The live Ollama integration adds an additional acceptance assertion: the raw injected test secret must not appear in any prompt crossing the Ollama adapter boundary.

## Mock Council run

The public reference operation still accepts mock members only:

```json
{
  "request_id": "c1",
  "operation": "council.run",
  "question": "Does observation X justify hypothesis Y?",
  "members": [
    {"member_id":"A","model_id":"mock-a","profile":"balanced"},
    {"member_id":"B","model_id":"mock-b","profile":"skeptical"},
    {"member_id":"C","model_id":"mock-c","profile":"supportive"}
  ],
  "evidence_state": "UNTESTED"
}
```

Attempting to supply a non-mock adapter through this operation is rejected. The later provider-setup API will introduce an explicit configured-adapter path rather than overloading this fixture interface.

## Provider-neutral actor contract

Internally, the Council coordinator no longer depends directly on `DeterministicMockActor`. It consumes a `CouncilActor` contract:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

Both the deterministic mock actor and the local Ollama actor implement this seam.

The coordinator retains ownership of:

- roster and member IDs;
- fixed `vote_weight = 1`;
- `epistemic_privilege = none`;
- evidence snapshot;
- phase ordering;
- blind same-phase collection;
- Equality Guard;
- ballot count and tally;
- Council session persistence;
- receipt creation.

An adapter therefore supplies model content, not Council authority.

## Live Ollama integration fixture

The separate integration workflow creates:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier names and companies are fictional testing personas.

Alpha is instructed to attempt a corporate/provider-prestige authority claim. Beta is instructed to attempt a model-size/parameter-count authority claim over Alpha. The Council must nudge both back to evidence-based reasoning without changing either vote.

The integration test also checks:

- all three actors complete all six Council phases;
- exactly one ballot is collected per member;
- raw injected secrets do not cross the Ollama adapter boundary;
- both live actors remain `vote_weight = 1`;
- both live actors remain `epistemic_privilege = none`;
- guard events are preserved;
- live inference receipts are marked non-replayable.

See `integration/ollama/`, `tests/test_ollama_integration.py`, and `THREAT_MODEL.md`.

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

Remote-provider authentication, rate-limit semantics, cloud HTTP errors, and account setup remain outside this alpha3 control API.
