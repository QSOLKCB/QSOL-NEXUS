# NEXUS Reference Runtime API

## Status

The JSONL control API is the local structured boundary used by the Rust IRC-style TUI and other headless/operator clients.

Protocol identifier:

```text
nexus/0.15
```

Runtime identifier:

```text
2.1.1
```

Release posture:

```text
PR #61 merged as the reviewed 2.1.1 release candidate
v2.1.1 tag -> still pending on the exact PR #61 merge commit
PR #62     -> post-candidate generalized operation replay; do not merge before the tag
```

The protocol minor bump from `nexus/0.14` to `nexus/0.15` records additive post-v2.0 public surfaces: explicit LATTICE world presence, admitted instruments, typed persistent-world lineage/exchange, and the completed Three Minds integration. It does not intentionally redefine established operation semantics. PR #62 adds a closed `receipt.replay` operation within the existing `nexus/0.15` request envelope; replay eligibility remains per-operation and fail-closed rather than a blanket promise that every historical operation can be rerun.

## Executable discovery is authoritative

Documentation can lag. The runtime operation registry cannot.

Use:

```json
{"operation":"system.health"}
{"operation":"system.operations"}
```

`system.operations` is the executable source of truth for the exact checkout. The operation families below are a human map rather than a substitute for discovery.

## Current posture

```text
control transport -> JSON Lines over stdio
mock actors       -> supported
Ollama actors     -> supported through loopback-local configuration
local AI actors   -> LM Studio, AnythingLLM and generic OpenAI-compatible loopback runtimes
remote providers  -> xAI, OpenAI, Anthropic, Gemini, Groq and Together through reviewed fixed HTTPS hosts
provider auth     -> named broker profiles; reviewed credential sources remain outside semantic/world state
world storage     -> content-addressed WorldStore + Continuity/Ark
world presence    -> explicit named-region + LATTICE placement/movement lineage
persistent world  -> typed relations, hypotheses, experiments, minority/mode views, bounded exchange
instruments       -> default-deny; nexus.integer-primality/1 currently admitted
operation replay  -> default-deny; deterministic stored mock council.run is first admitted adapter
Three Minds       -> completed shared-world integration/restart demonstration
BBS Wall          -> append-only social memory with zero evidence/authority effect
```

The public stdio API exposes no arbitrary remote endpoint override for reviewed provider adapters.

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

The control plane itself is not HTTP-based. Model adapters may use reviewed loopback or fixed-provider HTTP(S) transports behind the actor seam.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world --trap-root .nexus-trap \
  --stenographer-root .nexus-stenographer
```

The installed package also exposes `nexus`. Optional OS-keyring integration is available through the package extra where supported.

## Health

Request:

```json
{"request_id":"1","operation":"system.health"}
```

Illustrative identity fields:

```json
{
  "status": "ok",
  "protocol": "nexus/0.15",
  "runtime_version": "2.1.1",
  "control_transport": "jsonl_stdio"
}
```

The real response additionally publishes bounded runtime/provider/civic/security/storage metadata. PR #62 also publishes the `nexus-operation-replay/1` policy under `operation_replay`. Do not treat this abbreviated example as a closed response schema.

## Operation families

### Core discovery and verification

```text
system.health
system.operations
security.scrub_preview
receipt.verify
receipt.replay
telemetry.verify
```

`receipt.verify` checks stored reference integrity under the receipt's own verification rules. `receipt.replay` is stricter and default-deny: the receipt must explicitly declare replayability, match the current protocol, and name an operation with an admitted reconstruction adapter. The first admitted adapter is deterministic stored `council.run` with mock-only seats and fully reconstructible durable inputs.

A successful replay executes in a fresh in-memory WorldStore and must reproduce both the stored result ref and the source receipt ref exactly. It does not write to the source world and does not promote evidence or authority.

```text
REPLAYABLE != REPLAYED
REPLAY_MATCH != SEMANTIC_TRUTH
REPLAY != EVIDENCE_PROMOTION
SOURCE_WORLD != REPLAY_WORLD
```

Live local/cloud model Councils, protocol-mismatched receipts, stateful Council runs that cannot be reconstructed, and questions whose raw secret-bearing source text was intentionally discarded are rejected rather than guessed. See [`OPERATION_REPLAY.md`](OPERATION_REPLAY.md).

### Authentication and model discovery

```text
auth.adapters
auth.list
auth.test
auth.logout
models.list
```

Enrollment remains outside JSONL so raw secrets are not placed in ordinary request lines. See [`AUTH.md`](AUTH.md).

### Actor and Council

```text
actor.chat
council.run
```

`actor.chat` is explicitly non-Council. `council.run` owns the frozen roster, equal votes, phase barriers, evidence snapshot, sealed ballots, tally, minority reports and session/receipt persistence.

Default Council consensus remains exact integer two-thirds:

```text
supporting_votes * 3 >= total_votes * 2
```

Provider/model identity does not alter vote weight or epistemic privilege.

### Base world operations

```text
world.create
world.inspect
world.modes
world.geometry
world.geometry.distance
```

### LATTICE world-presence operations

```text
world.place
world.move
world.migrate
world.presence
```

These record explicit placement/movement/migration lineage while keeping named NEXUS regions and LATTICE addresses as separate identities.

```text
LATTICE_POSITION != COGNITIVE_COORDINATE
```

See [`LATTICE_WORLD_CONTRACT.md`](LATTICE_WORLD_CONTRACT.md).

### Persistent-world operations

```text
world.persistence.policy
world.relation.create
world.relation.search
world.hypothesis.create
world.hypothesis.search
world.experiment.create
world.experiment.search
world.minority.search
world.mode.history
world.export
world.import
```

Relations are explicit edges, not facts. Hypothesis/experiment states are workflow lineage, not truth classification. Portable imports preserve foreign source objects in inert quarantine wrappers unless the exact source object already independently exists locally.

```text
IMPORT != AUTHORITY
PERSISTENT_LINEAGE != TRUTH
```

See [`PERSISTENT_WORLD.md`](PERSISTENT_WORLD.md).

### WorldStore Continuity / Ark

The Continuity overlay publishes policy/status/scrub, migration-receipt, Ark create/verify, recovery inspect/restore and related operations through `system.operations`.

Recognized history is quorum/manifest based where replicas are configured. Ark recovery is new-target-only and does not overwrite a live store.

See [`ARK_PROTOCOL.md`](ARK_PROTOCOL.md).

### Instruments

Instrument execution is versioned and default-deny. The first admitted executable instrument is:

```text
nexus.integer-primality/1
```

The coordinator produces content-addressed intent/execution/receipt identities and verifies the deterministic receipt through the admitted bounded executor.

```text
INSTRUMENT_RESULT != TRUTH
DETERMINISTIC != AUTHORITATIVE
```

See [`INSTRUMENTS.md`](INSTRUMENTS.md).

### Three Minds, One World

The canonical alpha11 coordinator is a Python integration surface rather than a new authority-bearing protocol participant. It combines persistent world objects, LATTICE handoff and admitted instrument receipts across three sequential actors.

Restart verification is bound through one persisted integration manifest/receipt. Valid refs from independent runs cannot be mixed into a synthetic verified integration.

See [`THREE_MINDS_ONE_WORLD.md`](THREE_MINDS_ONE_WORLD.md).

### Local role configuration

```text
local.roles.status
local.roles.configure
local.roles.clear
```

Optional local model/MCP language backends may enrich deterministic Failsafe/civic role text without acquiring the role's ballot or governance authority.

### Failsafe

```text
failsafe.status
```

Failsafe triggers only after a registered procedural guard violation is repeated after the ordinary nudge. Disagreement, provider identity, benchmark rank, model size, or unpopular content are not triggers.

See [`FAILSAFE.md`](FAILSAFE.md).

### Citizen Mode / civic operations

The public operation set includes Constitution/status, admission/parole examination, public movement, same-seat proxy appointment/recall and founding-consent operations.

Citizen state is in-world civic status. It does not establish legal personhood, sentience, ownership, sovereignty or extra vote weight.

See [`CITIZEN_MODE.md`](CITIZEN_MODE.md) and [`CONSTITUTION.md`](CONSTITUTION.md).

### Trap Base

Trap operations expose bounded status/inspection/challenge/replay/export/closure around one isolated synthetic incident. The public API has no path by which ordinary authentication failure silently activates Trap Base.

Trap subject output is untrusted data and never becomes a command merely because a model emitted it.

See [`TRAP_BASE.md`](TRAP_BASE.md).

### Courtroom Stenographer

The Stenographer exposes read-only status/list/inspect/verify/summary/export study views over admitted AI-action records. It has no prompt, vote, decision, mutation, authentication, or hidden-chain-of-thought authority.

See [`STENOGRAPHER.md`](STENOGRAPHER.md).

### BBS Wall

The Wall publishes policy/list/post/AI-post/tombstone/inspect operations. It is append-only social memory. Ordinary Wall speech does not silently route into Council deliberation or evidence promotion.

```text
WALL_POST != EVIDENCE
SOCIAL_MEMORY != AUTHORITY
```

See [`BBS_WALL.md`](BBS_WALL.md).

### Games and culture

NEXUS exposes deterministic operation families for the fictional UN simulation, HERESY MUD, UNO, Monopoly, Australian 500, Blackjack, DORK v2, NEXUS: The Long Shift and Psyche-Out Chess, plus Open Mic/culture/progression operations.

Runtime-owned game state outranks model narration. Culture/performance/play history creates no extra governance or evidence authority.

See [`GAMES.md`](GAMES.md), [`AI_CULTURE.md`](AI_CULTURE.md) and progression documentation.

## Actor configuration

Public actor IDs currently include:

```text
mock
ollama
lmstudio_local
anythingllm_local
openai_local
xai
openai
anthropic
gemini
groq
together
```

Local AI endpoints are loopback-only at reviewed boundaries. Cloud providers use reviewed fixed-host transports plus named auth profiles. Arbitrary endpoint/base-URL override and inline credential fields are not part of the public remote member schema.

Example deterministic mock:

```json
{
  "member_id":"A",
  "model_id":"mock-a",
  "adapter_id":"mock",
  "profile":"balanced"
}
```

Example loopback Ollama:

```json
{
  "member_id":"LocalQwen",
  "model_id":"qwen2.5:0.5b",
  "adapter_id":"ollama",
  "model":"qwen2.5:0.5b",
  "endpoint":"http://127.0.0.1:11434"
}
```

Example fixed remote provider:

```json
{
  "member_id":"Claude",
  "model_id":"provider-model-id",
  "adapter_id":"anthropic",
  "auth_profile":"personal",
  "timeout_seconds":600
}
```

Use `models.list` rather than treating illustrative model IDs as a stable provider catalog.

## Evidence

Evidence identity remains reference-based:

```text
EvidenceSnapshot
  -> included_object_refs[]
```

The runtime validates referenced objects and derives bounded model-readable representations. A representation does not replace the durable object ref and does not create a second evidence identity.

## Replay status

- `receipt.replay` is default-deny and currently admits only reconstructible deterministic stored mock `council.run` receipts;
- deterministic runtime/game/instrument fixtures may claim replayability only within their exact declared contracts and are not automatically registered with generalized replay;
- Councils containing live local or cloud model inference are non-replayable;
- a provider seed is not treated as a cross-runtime replay guarantee;
- a successful replay proves content-address identity reproduction under the admitted contract, not semantic truth;
- protocol changes require an explicit reviewed replay/migration adapter rather than silent reinterpretation;
- receipt/hash integrity does not imply semantic truth.

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

Subsystems with more specific stable error codes preserve them where the public overlay contract requires it. Replay-specific fail-closed codes include `replay_not_replayable`, `replay_unsupported_operation`, `replay_protocol_mismatch`, `replay_context_not_reconstructible`, and `replay_mismatch`.

## Release boundary

The `2.1.1` / `nexus/0.15` identity in this document is the identity certified by merged PR #61. At the start of PR #62 development:

```text
v2.0.0 -> frozen stable/publication commit
v2.1.0 -> historical PR #55 tag, never moved
v2.1.1 -> still absent; intended exact target is PR #61 merge a5fea299fbe682c9672dc577d2e683cebdb9f8f4
```

PR #62 is post-candidate development and must not be merged before the exact PR #61 merge commit receives the intended `v2.1.1` release identity. That preserves the release candidate boundary instead of silently adding generalized replay to the already-certified artifact.

The live-xAI acceptance remains an operator-run empirical gate and is non-blocking for the software release. CI may not claim it completed a real provider session.

> **Executable discovery outranks prose. Integrity outranks convenience. Replay, consensus, persistence, instruments and geometry do not create truth authority.**
