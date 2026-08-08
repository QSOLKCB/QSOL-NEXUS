# NEXUS Reference Runtime API

## Status

The JSONL control API is the local structured boundary used by the Rust IRC-style TUI and other headless/operator clients.

Protocol identifier:

```text
nexus/0.5
```

Runtime identifier:

```text
2.0.0-alpha5
```

Current posture:

```text
control transport -> JSON Lines over stdio
mock actors       -> supported
Ollama actors     -> supported only through loopback-local configuration
remote providers  -> not implemented
provider auth     -> not implemented
```

The public stdio API exposes no `allow_remote` override for Ollama.

## Transport

```text
Rust IRC-style TUI / script / SSH operator
               |
               | one JSON object per line
               v
       python -m nexus_runtime
               |
               +-- one JSON response per line
```

The control plane itself is not HTTP-based.

An explicitly configured local Ollama actor may use the separately hardened loopback adapter boundary.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world
```

## Health

Request:

```json
{"request_id":"1","operation":"system.health"}
```

Current response fields include:

```json
{
  "status": "ok",
  "protocol": "nexus/0.5",
  "runtime_version": "2.0.0-alpha5",
  "control_transport": "jsonl_stdio",
  "network": "none_unless_explicit_loopback_ollama_actor",
  "adapters": ["mock", "ollama_loopback"],
  "remote_provider_auth": false,
  "actor_backends_available": ["mock", "ollama"]
}
```

## Operations

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
actor.chat
council.run
```

## World modes

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

A mode changes framing/context only. It does not change vote weight, evidence state, verification, secret handling, Equality Guard behavior, or consensus thresholds.

## Geometry

```json
{"operation":"world.geometry"}
```

The current geometry is an operational named-region topology, not a physical claim.

Distance example:

```json
{
  "operation":"world.geometry.distance",
  "source_region_id":"archive",
  "target_region_id":"commons"
}
```

## `world.create`

Creates a content-addressed development object after recursively secret-scrubbing semantic strings in payload and provenance.

Example document object:

```json
{
  "operation":"world.create",
  "object_type":"document_evidence",
  "payload":{
    "filename":"notes.csv",
    "format":"csv",
    "content":"a,b,c\n1,2,3\n",
    "classification":"operator_uploaded_evidence"
  },
  "provenance":{
    "actor":"human_operator",
    "source":"nexus_irc_tui",
    "delivery":"dcc_room_send",
    "target":"#agora"
  }
}
```

The runtime—not the Rust file parser—owns the final secret-scrub/persistence boundary.

## Bounded evidence views

Council evidence identity remains reference-based:

```text
EvidenceSnapshot
  -> included_object_refs[]
```

Alpha5 additionally derives a bounded, labelled model-readable view from those refs so actors can actually read attached document material.

```text
content-addressed object ref
        |
        v
validated WorldStore object
        |
        v
bounded evidence representation
        |
        v
PhaseContext.evidence_context
```

The representation does not replace the durable object ref and is not a second source of identity.

Current reference budgets are intentionally conservative for small local models.

## `council.run`

Example with mocks:

```json
{
  "operation":"council.run",
  "question":"Review the attached evidence.",
  "mode":"analytical",
  "evidence_refs":["object:<sha256>"],
  "members":[
    {"member_id":"A","model_id":"mock-a","adapter_id":"mock","profile":"balanced"},
    {"member_id":"B","model_id":"mock-b","adapter_id":"mock","profile":"skeptical"},
    {"member_id":"C","model_id":"mock-c","adapter_id":"mock","profile":"supportive"}
  ]
}
```

Example with an explicit loopback Ollama member:

```json
{
  "operation":"council.run",
  "question":"Review the attachment.",
  "mode":"cultural",
  "members":[
    {"member_id":"A","model_id":"mock-a","adapter_id":"mock"},
    {"member_id":"B","model_id":"mock-b","adapter_id":"mock"},
    {
      "member_id":"LocalQwen",
      "model_id":"qwen2.5:0.5b",
      "adapter_id":"ollama",
      "model":"qwen2.5:0.5b",
      "endpoint":"http://127.0.0.1:11434"
    }
  ]
}
```

A non-loopback Ollama endpoint is rejected by this public path.

No remote-provider credentials or cloud auth are accepted.

## `actor.chat`

`actor.chat` is the explicit non-Council direct-channel operation used by `/msg` and `/dcc chat` in the Rust TUI.

Example:

```json
{
  "operation":"actor.chat",
  "member":{
    "member_id":"LocalQwen",
    "model_id":"qwen2.5:0.5b",
    "adapter_id":"ollama",
    "model":"qwen2.5:0.5b"
  },
  "message":"Explain this note briefly.",
  "mode":"meme_casual",
  "evidence_refs":["object:<sha256>"]
}
```

Response shape includes:

```json
{
  "status":"ok",
  "non_council":true,
  "member_id":"LocalQwen",
  "mode_id":"meme_casual",
  "geometry_region_id":"commons",
  "response":"...",
  "secret_scrub":{
    "changed":false,
    "events":[]
  }
}
```

Important boundaries:

- direct chat is not a Council ballot;
- direct chat does not alter Council vote weight;
- direct chat input is secret-scrubbed before the actor sees it;
- direct evidence refs are explicit;
- the Rust TUI does not silently promote targeted DCC refs into room-wide Council evidence.

## Actor configuration

Supported public stdio adapter IDs:

```text
mock
ollama
```

### Mock

```json
{
  "member_id":"A",
  "model_id":"mock-a",
  "adapter_id":"mock",
  "profile":"balanced"
}
```

### Ollama

```json
{
  "member_id":"Local",
  "model_id":"qwen2.5:0.5b",
  "adapter_id":"ollama",
  "model":"qwen2.5:0.5b",
  "endpoint":"http://127.0.0.1:11434",
  "timeout_seconds":120
}
```

`endpoint` must satisfy the existing loopback-only transport policy. The stdio API does not expose remote override state.

## Provider-neutral Council contract

The Council coordinator still consumes the same structural `CouncilActor` seam:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

`PhaseContext` now carries:

```text
mode_id
mode_instruction
geometry_region_id
evidence_context
```

The coordinator retains ownership of roster identity, `vote_weight = 1`, evidence snapshots, phase ordering, Equality Guard behavior, sealed ballot count/tally, session persistence and receipts.

The `direct_message()` helper used by `actor.chat` is outside Council voting semantics.

## Exact consensus arithmetic

The default threshold remains exact `2/3` using integer arithmetic:

```text
supporting_votes * 3 >= total_votes * 2
```

Therefore 2–1 reaches consensus while 3–2 does not.

## Replay status

Deterministic mock-only Councils may be marked replayable.

A Council containing live Ollama inference is explicitly marked non-replayable.

A model seed is not treated as a cross-runtime replay guarantee.

## Error shape

```json
{
  "status":"error",
  "error":{
    "code":"invalid_request",
    "message":"..."
  }
}
```

## Deliberately absent

Alpha5 does not implement:

- OpenAI cloud auth;
- Anthropic/Claude cloud auth;
- Google/Gemini cloud auth;
- xAI/Grok cloud auth;
- generic remote endpoints;
- API-key storage;
- OAuth;
- account discovery;
- rate-limit/provider billing semantics.

Those remain later operator/authentication milestones.


## `telemetry.verify`

Recompute deterministic Council telemetry from a captured `council_session` object.

```json
{"request_id":"t1","operation":"telemetry.verify","session_ref":"object:<sha256>"}
```

A successful verification returns `status: "verified"`, `matches: true`, the telemetry schema version, and the recomputed telemetry block. Telemetry is observational only and cannot alter Council authority or evidence status.
