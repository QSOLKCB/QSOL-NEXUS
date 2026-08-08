# NEXUS Reference Runtime API

## Status

The JSONL control API is the local structured boundary used by the Rust IRC-style TUI and other headless/operator clients.

Protocol identifier:

```text
nexus/0.10
```

Runtime identifier:

```text
2.0.0-alpha9.0
```

Current posture:

```text
control transport -> JSON Lines over stdio
mock actors       -> supported
Ollama actors     -> supported only through loopback-local configuration
xAI actors        -> supported through a configured profile and fixed api.x.ai HTTPS transport
UN simulation     -> supported as a deterministic fictional local game
HERESY MUD        -> supported as a deterministic fictional multi-avatar local game
Failsafe          -> bounded repeated-guard containment + deterministic relief actor
remote providers  -> xAI admitted; other providers not implemented
provider auth     -> xAI API key, environment, or external helper
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

An explicitly configured local Ollama actor may use the separately hardened loopback adapter boundary. Explicit xAI operations may use the fixed remote HTTPS adapter boundary.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world
```

The installed package also exposes `nexus`. Add the optional OS-keyring integration with `python -m pip install -e '.[keyring]'`.

## Health

Request:

```json
{"request_id":"1","operation":"system.health"}
```

Current response fields include:

```json
{
  "status": "ok",
  "protocol": "nexus/0.10",
  "runtime_version": "2.0.0-alpha9.0",
  "control_transport": "jsonl_stdio",
  "network": "local_stdio_with_explicit_loopback_ollama_or_fixed_xai_https",
  "adapters": ["mock", "ollama_loopback", "xai_https"],
  "remote_provider_auth": true,
  "auth_broker": {
    "schema_version": "nexus-auth/1",
    "browser_pkce": true,
    "device_code": true,
    "remote_adapters_admitted": true
  },
  "actor_backends_available": ["mock", "ollama", "xai"],
  "failsafe": {
    "schema_version": "nexus-failsafe/1",
    "trigger": "registered_repeated_guard_failure_after_nudge_only"
  },
  "games": [
    {
      "game_id": "un_sim",
      "schema": "nexus-un-sim/1",
      "room": "#un-sim",
      "fictional_only": true
    },
    {
      "game_id": "mud",
      "schema": "nexus-cursed-mud/1",
      "room": "#mud",
      "fictional_only": true
    }
  ]
}
```

## Operations

```text
system.health
system.operations
auth.adapters
auth.list
auth.test
auth.logout
models.list
security.scrub_preview
world.create
world.inspect
world.modes
world.geometry
world.geometry.distance
receipt.verify
telemetry.verify
failsafe.status
game.un.catalog
game.un.new
game.un.inspect
game.un.act
game.un.turn
game.mud.catalog
game.mud.new
game.mud.inspect
game.mud.act
actor.chat
council.run
```

## Authentication operations

Authentication profiles are operational state outside the WorldStore. The JSONL protocol never accepts or returns a raw API key, access token, refresh token, authorization code, PKCE verifier, device code, or credential handle.

List adapter-declared auth methods:

```json
{"operation":"auth.adapters"}
```

List non-secret profiles:

```json
{"operation":"auth.list"}
```

Resolve a profile and, when the adapter registers one, run its bounded provider connection test:

```json
{"operation":"auth.test","adapter_id":"provider","profile_name":"personal"}
```

If the auth substrate can resolve the profile but no provider-specific connection tester is registered, the response is explicit:

```json
{
  "status": "ready",
  "adapter_id": "provider",
  "profile_name": "personal",
  "credential": "available",
  "remote_verified": false,
  "code": "provider_test_not_registered"
}
```

Explicitly remove a profile and any broker-stored credential:

```json
{"operation":"auth.logout","adapter_id":"provider","profile_name":"personal"}
```

Enrollment is intentionally absent from JSONL so raw keys cannot be placed into request lines or runtime transcripts. Use the direct `nexus auth add ...` CLI described in [`AUTH.md`](AUTH.md). The runtime registers `mock`, loopback `ollama`, and fixed-remote `xai` descriptors.

## Model discovery

List language models available to an xAI profile:

```json
{"operation":"models.list","adapter_id":"xai","profile_name":"personal","timeout_seconds":60}
```

The response contains bounded descriptive model metadata and `remote_verified: true`. Raw credentials, provider error bodies, pricing/account rank, and arbitrary endpoint fields are never returned. Unknown request fields fail closed.

## Failsafe status

Inspect current actor containment state:

```json
{"operation":"failsafe.status"}
```

Optionally filter by Council member seat:

```json
{"operation":"failsafe.status","member_id":"Grok"}
```

Failsafe triggers only after a registered procedural guard violation is repeated after its ordinary nudge. The isolated rehabilitation probe receives no Council evidence or completed phase material and has no ballot or world mutation authority. A clean probe returns the actor at the next hat; failure records `shadow_realm` and causes `nexus-failsafe-relief-v1` to occupy the same equal-vote seat on later Council runs.

See [`FAILSAFE.md`](FAILSAFE.md).

## Fictional UN simulation game

The local protocol exposes the deterministic `#un-sim` engine:

```text
game.un.catalog
game.un.new
game.un.inspect
game.un.act
game.un.turn
```

Create a seeded board:

```json
{"operation":"game.un.new","seed":"friday-night"}
```

A successful response returns a content-addressed `game_ref` and the full fictional game state.

Inspect it:

```json
{"operation":"game.un.inspect","game_ref":"object:<sha256>"}
```

Apply an action:

```json
{
  "operation":"game.un.act",
  "game_ref":"object:<sha256>",
  "action":"meme",
  "targets":["troutistan","bananovia"]
}
```

Advance a turn:

```json
{"operation":"game.un.turn","game_ref":"object:<sha256>"}
```

Each action or turn returns a new immutable state linked to its predecessor through `previous_state_ref`.

Initial action IDs are:

```text
sanction
support
aid
arms
meme
suspend
reinstate
recognize
mediate
do_nothing
```

The game accepts only its fixed fictional country IDs. `arms` is an abstract integer-resource operation and contains no real weapon type, supplier, quantity, delivery route, price or procurement procedure.

Each game state also stores a compact deterministic `content` board view. When the game ref is attached as Council evidence, the generic evidence path uses that view so every Council member can read current wars, all countries and current statistics without consuming the per-object evidence budget on older event history.

See [`UN_SIM.md`](UN_SIM.md).

## HERESY MUD

The local protocol exposes the deterministic multi-avatar `#mud` engine:

```text
game.mud.catalog
game.mud.new
game.mud.inspect
game.mud.act
```

Create one shared dungeon state:

```json
{"operation":"game.mud.new","seed":"beige-night","players":["Trent","Alpha","Grok"]}
```

Inspect a player's current view:

```json
{"operation":"game.mud.inspect","mud_ref":"object:<sha256>","player_id":"Trent"}
```

Apply an authoritative action:

```json
{"operation":"game.mud.act","mud_ref":"object:<sha256>","player_id":"Grok","action":"go","args":["north"]}
```

Movement, loot, combat, `shitpost`, and `ratio` transitions are deterministic and content-addressed. Narration never mutates the dungeon. Item score is a one-time acquisition award, defeated avatars drop held items into their current room, and defeating the Dependency Dragon only drops the Crown; the quest becomes complete when a player subsequently takes `zero_dependency_crown`.

See [`MUD.md`](MUD.md).

## World modes

```json
{"operation":"world.modes"}
```

Built-in modes:

```text
analytical  -> Observatory
historical   -> Archive / #archive
pure_history -> Archive / #pure-history
cultural    -> Agora
meme_casual -> Commons
game_un     -> Assembly Hall / #un-sim
game_mud    -> Dungeon / #mud
```

A mode changes framing/context only. It does not change vote weight, evidence state, verification, secret handling, Equality Guard behavior, or consensus thresholds. `pure_history` additionally applies a narrow retry guard only to chatbot-autobiography/media-habit evasions; it does not adjudicate historical truth.

See [`PURE_HISTORY.md`](PURE_HISTORY.md) for the source-discipline contract.

## Geometry

```json
{"operation":"world.geometry"}
```

The current built-in geometry is `named-regions-v3`, an operational named-region topology rather than a physical claim. It includes the Assembly Hall used by `game_un` and the Dungeon region used by `game_mud`.

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

Alpha5 additionally derives a bounded, labelled model-readable view from those refs so actors can actually read attached document material. Alpha6.3 reuses that same generic mechanism for the compact current `#un-sim` board and `#mud` dungeon views.

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

An xAI peer references only an opaque profile name:

```json
{
  "member_id":"Grok",
  "model_id":"grok-4.5",
  "adapter_id":"xai",
  "auth_profile":"personal",
  "timeout_seconds":600
}
```

`council.run` accepts no credential or remote-endpoint fields. The xAI actor resolves the profile only inside its transport; raw material remains broker-internal.

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
xai
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

### xAI

```json
{
  "member_id":"Grok",
  "model_id":"grok-4.5",
  "adapter_id":"xai",
  "auth_profile":"personal",
  "timeout_seconds":600
}
```

The xAI member schema is closed. It rejects `endpoint`, `base_url`, inline key/token fields, unknown fields, invalid model IDs, and timeouts above 3600 seconds. Discover the available model IDs first with `models.list`; the example model is not a hard-coded default.

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

`PhaseContext` carries:

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

The UN simulation engine is deterministic game state rather than model inference: the same immutable state plus the same deterministic game operation yields the same successor identity.

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

The current local runtime does not implement:

- provider-specific OpenAI cloud auth/transport;
- provider-specific Anthropic/Claude cloud auth/transport;
- provider-specific Google/Gemini cloud auth/transport;
- generic remote endpoints;
- provider model discovery beyond xAI;
- provider OAuth client registration and OIDC identity validation, including a NEXUS-owned xAI browser client;
- account discovery;
- rate-limit/provider billing semantics.

The neutral auth broker, xAI API-key setup, fixed xAI transport, browser PKCE substrate, device code, and headless credential sources are implemented. See [`AUTH.md`](AUTH.md) and [`XAI_ADAPTER.md`](XAI_ADAPTER.md).

## `telemetry.verify`

Recompute deterministic Council telemetry from a captured `council_session` object.

```json
{"request_id":"t1","operation":"telemetry.verify","session_ref":"object:<sha256>"}
```

A successful verification returns `status: "verified"`, `matches: true`, the telemetry schema version, and the recomputed telemetry block. Telemetry is observational only and cannot alter Council authority or evidence status.
