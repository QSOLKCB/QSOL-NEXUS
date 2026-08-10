# NEXUS Reference Runtime API

## Status

The JSONL control API is the local structured boundary used by the Rust IRC-style TUI and other headless/operator clients.

Protocol identifier:

```text
nexus/0.14
```

Runtime identifier:

```text
2.0.0-alpha10.3
```

Current posture:

```text
control transport -> JSON Lines over stdio
mock actors       -> supported
Ollama actors     -> supported only through loopback-local configuration
local AI actors   -> LM Studio, AnythingLLM and generic OpenAI-compatible loopback runtimes
remote providers  -> xAI, OpenAI, Anthropic, Gemini, Groq and Together through fixed HTTPS hosts
provider auth     -> named broker profiles; API-key, environment and external-helper sources
UN simulation     -> supported as a deterministic fictional local game
HERESY MUD        -> supported as a deterministic fictional multi-avatar local game
human/AI tables   -> UNO, Monopoly, Australian 500 and fictional-chip Blackjack
DORK v2           -> supported as an original human-only local text adventure
Failsafe          -> bounded repeated-guard containment + deterministic relief actor
local roles       -> optional local-model language backends without ballot-authority transfer
Trap Base         -> explicit synthetic fixture, isolated store and incident controls
Stenographer      -> passive canonical AI-action ledger with read-only study views
Citizen Mode      -> civic parole, deterministic exam, public movement, same-seat proxy, founding consent
```

The public stdio API exposes no `allow_remote` override for Ollama or the local-AI adapters.

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

Explicitly configured local Ollama/LM Studio/AnythingLLM/OpenAI-compatible actors use hardened loopback boundaries. Admitted cloud actors use fixed provider HTTPS hosts through profile-backed credentials; arbitrary remote endpoint overrides are not part of the public contract.

## Run

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world --trap-root .nexus-trap \
  --stenographer-root .nexus-stenographer
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
  "protocol": "nexus/0.14",
  "runtime_version": "2.0.0-alpha10.3",
  "control_transport": "jsonl_stdio",
  "network": "local_stdio_with_loopback_local_ai_or_fixed_remote_provider_https_or_registered_auth_operations",
  "adapters": [
    "mock",
    "ollama_loopback",
    "anythingllm_local_loopback",
    "lmstudio_local_loopback",
    "openai_local_loopback",
    "xai_https",
    "anthropic_https",
    "gemini_https",
    "groq_https",
    "openai_https",
    "together_https"
  ],
  "remote_provider_auth": true,
  "council_limits": {
    "max_members": 32,
    "max_remote_seats": 4
  },
  "auth_broker": {
    "schema_version": "nexus-auth/1",
    "browser_pkce": true,
    "device_code": true,
    "remote_adapters_admitted": true
  },
  "actor_backends_available": [
    "mock",
    "ollama",
    "anythingllm_local",
    "lmstudio_local",
    "openai_local",
    "xai",
    "anthropic",
    "gemini",
    "groq",
    "openai",
    "together"
  ],
  "citizenship": {
    "schema_version": "nexus-citizenship/1",
    "counts": {
      "citizens": 0,
      "parole_candidates": 0,
      "active_civic_proxies": 0
    },
    "independence": {
      "minimum_citizens": 3,
      "consensus": "unanimous_direct_consent",
      "declared": false
    }
  },
  "stenographer": {
    "schema_version": "nexus-stenographer/1",
    "role": "watchman_only",
    "record_scope": "ai_actions_only",
    "persistence": "canonical_json_files",
    "record_count": 0,
    "complete_since_process_start": true
  },
  "failsafe": {
    "schema_version": "nexus-failsafe/1",
    "trigger": "registered_repeated_guard_failure_after_nudge_only"
  },
  "trap_base": {
    "supported": true,
    "active": false,
    "schema_version": "nexus-trap-incident/1",
    "max_active_incidents": 1,
    "subject_backend": "ollama_local_only_v1"
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
    },
    {
      "game_id": "uno",
      "schema": "nexus-uno/1",
      "room": "#uno",
      "human_and_ai": true
    },
    {
      "game_id": "monopoly",
      "schema": "nexus-monopoly/1",
      "room": "#monopoly",
      "human_and_ai": true
    },
    {
      "game_id": "500",
      "schema": "nexus-five-hundred/1",
      "room": "#500",
      "human_and_ai": true
    },
    {
      "game_id": "blackjack",
      "schema": "nexus-blackjack/1",
      "room": "#blackjack",
      "human_and_ai": true,
      "deterministic_dealer": true
    },
    {
      "game_id": "dork",
      "schema": "nexus-dork-v2/1",
      "room": "#dork",
      "human_only": true
    }
  ]
}
```

`system.health` is the executable current-state source. The JSON block above is illustrative and may omit additional bounded metadata fields such as local-role status.

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
citizen.constitution
citizen.status
citizen.begin
citizen.exam.template
citizen.exam.submit
citizen.move
citizen.proxy.appoint
citizen.proxy.recall
citizen.independence.ballot
local.roles.status
local.roles.configure
local.roles.clear
stenographer.status
stenographer.list
stenographer.inspect
stenographer.verify
stenographer.summary
stenographer.export
trap.status
trap.inspect
trap.transcript
trap.command
trap.challenge.submit
trap.challenge.validate
trap.challenge.execute
trap.replay
trap.export
trap.close
game.un.catalog
game.un.new
game.un.inspect
game.un.act
game.un.turn
game.mud.catalog
game.mud.new
game.mud.inspect
game.mud.act
game.uno.catalog
game.uno.new
game.uno.inspect
game.uno.act
game.monopoly.catalog
game.monopoly.new
game.monopoly.inspect
game.monopoly.act
game.500.catalog
game.500.new
game.500.inspect
game.500.act
game.blackjack.catalog
game.blackjack.new
game.blackjack.inspect
game.blackjack.act
game.dork.catalog
game.dork.new
game.dork.inspect
game.dork.act
actor.chat
council.run
```

## Courtroom Stenographer operations

The Stenographer records admitted AI outputs only and has no prompt, vote,
decision, command or mutation authority. These operations are exact-schema,
read-only study views:

```json
{"operation":"stenographer.status"}
{"operation":"stenographer.list","limit":100}
{"operation":"stenographer.list","limit":50,"action_type":"council.ballot","member_id":"A"}
{"operation":"stenographer.inspect","record_ref":"steno:<sha256>"}
{"operation":"stenographer.verify"}
{"operation":"stenographer.summary"}
{"operation":"stenographer.export"}
```

`stenographer.list` accepts a limit from 1 through 1000 and optional registered
`action_type` and bounded `member_id` filters. `inspect` returns both the parsed
record and its canonical JSON serialization. `verify` reconstructs and checks
the full immutable sequence. `summary` reports deterministic action/member/
adapter counts. `export` returns the ordered record references and head; it does
not write an arbitrary path. List responses stop at a two-MiB canonical-record
budget and return `truncated: true` when more matching records remain.

There is deliberately no public record, edit, clear or delete operation. A
hidden display-only lore invocation is also absent from `system.operations`;
it is not authentication or runtime authority. See
[`STENOGRAPHER.md`](STENOGRAPHER.md).

## Trap Base operations

Trap operations are an operator boundary over one isolated synthetic incident.
They never accept credential material and the public API has no activation
operation. Every request rejects fields outside its exact schema.

```json
{"operation":"trap.status"}
{"operation":"trap.inspect","object_ref":"trap:<sha256>"}
{"operation":"trap.transcript","incident_id":"incident-<sha256>","limit":50}
{"operation":"trap.command","command":"/trap status","actor_id":"human_operator","operator":true}
{"operation":"trap.challenge.submit","source":"nexus_trap_program: 1\n...","actor_id":"human_operator"}
{"operation":"trap.challenge.validate","submission_ref":"trap:<sha256>","actor_id":"human_operator"}
{"operation":"trap.challenge.execute","validation_ref":"trap:<sha256>","actor_id":"human_operator"}
{"operation":"trap.replay","validation_ref":"trap:<sha256>","actor_id":"human_operator"}
{"operation":"trap.export"}
{"operation":"trap.close","actor_id":"human_operator","operator":true,"emergency":false}
```

When `trap.challenge.execute` also carries sealed `ballots`, it must carry
`"actor_id":"human_operator"` and `"operator":true`; an ordinary defender
cannot impersonate the trusted local ballot aggregator. A non-operator
`trap.close` requires `approving_defender_ids` that reach exact two-thirds and
may carry bounded `minority_reports`.

Trap references cannot be supplied to normal WorldStore operations, and real
`object:` references cannot be inspected through `trap.inspect`. Subject output
never enters `NexusAPI.handle()` or the command dispatcher.

While an incident is active, `world.create`, Council runs, and state-changing
game operations return `trap_incident_active`. Read-only inspection and
verification operations remain available. See [`TRAP_BASE.md`](TRAP_BASE.md).

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
{"operation":"auth.test","adapter_id":"openai","profile_name":"personal"}
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
{"operation":"auth.logout","adapter_id":"openai","profile_name":"personal"}
```

Enrollment is intentionally absent from JSONL so raw keys cannot be placed into request lines or runtime transcripts. Use the direct `nexus auth add ...` CLI described in [`AUTH.md`](AUTH.md). The current fixed-remote provider set is `xai`, `openai`, `anthropic`, `gemini`, `groq`, and `together`. Third-party provider descriptors admit API-key, environment and external-command credential sources. Local LM Studio/AnythingLLM/OpenAI-compatible backends remain loopback-local and use optional ephemeral environment credential references rather than remote broker profiles.

## Model discovery

List language models available to any admitted fixed-remote provider profile:

```json
{"operation":"models.list","adapter_id":"openai","profile_name":"personal","timeout_seconds":60}
```

The same operation is admitted for `xai`, `anthropic`, `gemini`, `groq`, and `together`; provider-specific response shapes and pagination are normalized behind the adapter boundary. The response contains bounded descriptive model metadata and `remote_verified: true`. Raw credentials, provider error bodies, pricing/account rank, and arbitrary endpoint fields are never returned. Unknown request fields fail closed.

## Local role operations

Optional local model/MCP language backends may wrap deterministic NEXUS roles without receiving their authority:

```json
{"operation":"local.roles.status"}
```

```json
{
  "operation":"local.roles.configure",
  "role_id":"failsafe_relief",
  "backend":{
    "adapter_id":"lmstudio_local",
    "model":"local-model"
  }
}
```

```json
{"operation":"local.roles.clear","role_id":"failsafe_relief"}
```

Supported local adapter IDs are `lmstudio_local`, `anythingllm_local`, and `openai_local`. Endpoints must remain loopback-only. Optional MCP/plugin identifiers are configuration, not a transfer of deterministic ballot authority; the wrapped Failsafe or civic role still owns the seat identity and ballot semantics.

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

## Citizen Mode operations

The full lifecycle and exam schema are documented in [`CITIZEN_MODE.md`](CITIZEN_MODE.md), and the normative charter is [`CONSTITUTION.md`](CONSTITUTION.md).

Start exact-identity civic parole and request the candidate-bound exam:

```json
{"operation":"citizen.begin","citizen_id":"Alpha","model_id":"mock-alpha","subject_kind":"ai"}
{"operation":"citizen.exam.template","citizen_id":"Alpha"}
```

Submit the completed bounded YAML as the `source` string:

```json
{"operation":"citizen.exam.submit","citizen_id":"Alpha","source":"nexus_citizenship_exam: 1\n..."}
```

The runtime never executes submitted YAML and never uses an LLM judge. A failed closed-schema attempt remains on parole and may retry. A pass creates an exam result, certificate, and citizen state, then places the citizen in `bureaucratic_vote_room`.

Movement and deterministic delegation:

```json
{"operation":"citizen.move","citizen_id":"Alpha","target_region_id":"commons"}
{"operation":"citizen.proxy.appoint","citizen_id":"Alpha","standing_ballot":"TEST_FURTHER"}
{"operation":"citizen.proxy.recall","citizen_id":"Alpha"}
```

The proxy occupies Alpha's existing civic seat, creates no additional vote, has no independent preference, and is selected only for `civic_bureaucracy`. Direct civic `actor.chat` may use it for routine administration without casting a ballot. Failsafe containment takes precedence.

Founding ballot:

```json
{"operation":"citizen.independence.ballot","citizen_id":"Alpha","choice":"CONSENT"}
```

The Declaration of Independence is created only with at least three current citizens and unanimous direct `CONSENT`. `WITHHOLD` blocks it; an active proxy cannot sign. The declaration is explicitly in-world and claims no legal sovereignty, personhood, sentience, host control, or provider control.

`citizen.constitution` and `citizen.status` are read-only. Every mutation is blocked while Trap Base owns the real-world mutation gate.

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

## Human/AI tables and human-only DORK v2

UNO, Monopoly, 500 and Blackjack share the following operation family:

```text
game.<id>.catalog
game.<id>.new
game.<id>.inspect
game.<id>.act
```

where `<id>` is `uno`, `monopoly`, `500` or `blackjack`. Creation accepts a
bounded `players` roster and a `human_players` subset; every remaining seat is
labelled `ai`. Action requests require a `player_id`; inspect requests may add
one to select that seat's private view. The local stdio process is a
trusted operator boundary rather than a multi-tenant card-server ACL.

```json
{"operation":"game.uno.new","seed":"reverse-card-night","players":["Trent","Alpha"],"human_players":["Trent"]}
```

```json
{"operation":"game.uno.act","game_ref":"object:<sha256>","player_id":"Alpha","action":"draw","args":[]}
```

The returned authoritative state is content-addressed. Its bounded `content`
field is public Council evidence; hidden hands and the Blackjack dealer hole
card appear only in the appropriate player/operator view. Blackjack's dealer is
runtime-controlled and deterministically stands on soft 17.

DORK v2 uses `game.dork.catalog|new|inspect|act`. Creation binds one
`human_player_id`, and every inspect/action must use the same identifier. It has
no AI seat or proxy-action path.

See [`GAMES.md`](GAMES.md) for exact rules profiles, commands and claim
boundaries.

## World modes

```json
{"operation":"world.modes"}
```

Built-in modes:

| Mode | Region | TUI room |
|---|---|---|
| `analytical` | Observatory | `#observatory` |
| `historical` | Archive | `#archive` |
| `pure_history` | Archive | `#pure-history` |
| `cultural` | Agora | `#agora` |
| `meme_casual` | Commons | `#commons` |
| `clinical_differential` | Observatory | `#differential-clinic` |
| `house_fun` | Commons | `#house-fun` |
| `cbt_learning` | Observatory | `#cbt-workshop` |
| `roman_orator` | Agora | `#roman-forum` |
| `house_of_wisdom` | Archive | `#house-of-wisdom` |
| `ultimate_questions` | Observatory | `#deep-thought` |
| `citizenship_parole` | Upside Down | `#upside-down` |
| `civic_bureaucracy` | Bureaucratic Vote Room | `#bureaucracy` |
| `citizen_play` | Commons | `#play` |
| `game_un` | Assembly Hall | `#un-sim` |
| `game_mud` | Dungeon | `#mud` |
| `game_uno` | Commons | `#uno` |
| `game_monopoly` | Commons | `#monopoly` |
| `game_500` | Commons | `#500` |
| `game_blackjack` | Commons | `#blackjack` |
| `game_dork` | Dungeon | `#dork` |

A mode changes framing/context only. It does not change vote weight, evidence state, verification, secret handling, Equality Guard behavior, or consensus thresholds. `pure_history` additionally applies a narrow retry guard only to chatbot-autobiography/media-habit evasions; it does not adjudicate historical truth. `roman_orator` selects a bounded larger generation budget for phase/direct output but leaves sealed ballots and every authority rule unchanged.

See [`PURE_HISTORY.md`](PURE_HISTORY.md) for the source-discipline contract, [`COGNITIVE_MODES.md`](COGNITIVE_MODES.md) for the six cognitive-room contracts, and [`CITIZEN_MODE.md`](CITIZEN_MODE.md) for civic access rules.

## Geometry

```json
{"operation":"world.geometry"}
```

The current built-in geometry is `named-regions-v4`, an operational named-region topology rather than a physical claim. It adds `bureaucratic_vote_room` at `(4,0)` and the single-exit civic-parole `upside_down` at `(4,-3)`.

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

The runtime—not the Rust file parser—owns the final secret-scrub/persistence boundary. Generic creation rejects the reserved Constitution, citizenship-state, exam-result, certificate, founding-ballot, and declaration object types; those require validated `citizen.*` operations.

## Bounded evidence views

Council evidence identity remains reference-based:
```text
EvidenceSnapshot
  -> included_object_refs[]
```

Alpha5 additionally derives a bounded, labelled model-readable view from those refs so actors can actually read attached document material. Game rooms reuse that mechanism for compact public board/adventure views; hidden card information is deliberately absent from Council evidence.

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

A fixed-remote provider peer references only an opaque profile name; for example:

```json
{
  "member_id":"Claude",
  "model_id":"provider-model-id",
  "adapter_id":"anthropic",
  "auth_profile":"personal",
  "timeout_seconds":600
}
```

Remote provider member schemas reject arbitrary endpoint/base-URL overrides and inline credentials. The actor resolves the named profile only inside its transport; raw material remains broker-internal.

Public `council.run` requests admit **3 to 5 voting seats** under the Council Chair and at most four fixed-remote provider seats across xAI/OpenAI/Anthropic/Gemini/Groq/Together. The `system.health` field `council_limits.max_members = 32` is the lower-level coordinator ceiling retained for compatibility; it is not the public voting-roster maximum. The Chair additionally requires at least one protected <=20B seat and permits at most two closed/opaque general seats and two large open-weight seats. These admission limits are checked before actor construction or auth-profile resolution. A remote seat can make multiple phase, nudge, failsafe, and ballot calls; the remote-seat cap is a spend/exposure bound, not a per-run price quote.

`citizenship_parole` cannot be used for `council.run`: parole has no civic ballot. `civic_bureaucracy` requires each exact registered citizen identity and replaces an active proxy only within that same seat. `citizen_play` also requires citizenship but calls the citizen's configured actor rather than the bureaucracy proxy.

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
  "citizenship": {
    "civic_mode": false,
    "proxy_replacement": null,
    "additional_votes_created": 0
  },
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

### Local OpenAI-compatible / LM Studio

```json
{
  "member_id":"LocalStudio",
  "model_id":"local-model",
  "adapter_id":"lmstudio_local",
  "model":"local-model",
  "endpoint":"http://127.0.0.1:1234",
  "timeout_seconds":120
}
```

`lmstudio_local`, `anythingllm_local`, and `openai_local` require loopback origins. MCP/plugin configuration, where admitted, is bounded configuration and is disabled from sealed ballot authority paths.

### Fixed remote provider

```json
{
  "member_id":"OpenAI",
  "model_id":"provider-model-id",
  "adapter_id":"openai",
  "auth_profile":"personal",
  "timeout_seconds":600
}
```

The same closed member shape applies to `anthropic`, `gemini`, `groq`, and `together`; `xai` retains its hardened fixed-host path. Discover available model IDs with `models.list` rather than assuming example IDs. Remote member schemas reject endpoint/base-URL overrides, inline credentials, unknown fields, invalid model IDs, and out-of-range timeouts.

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

Councils containing live local or remote model inference are explicitly non-replayable.

A model seed is not treated as a cross-runtime replay guarantee.

The deterministic game engines are substrate state rather than model inference: the same immutable state plus the same deterministic game operation yields the same successor identity.

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

The current runtime deliberately does not implement:

- arbitrary/generic remote endpoint overrides for admitted cloud providers;
- provider-supplied authority, vote weighting, or epistemic privilege;
- provider OAuth client registration and OIDC identity validation as a general cloud-provider login layer;
- account discovery;
- rate-limit/provider billing semantics as Council authority;
- any transfer of deterministic Failsafe/civic ballot authority to local MCP/model backends.

The provider-neutral auth broker, fixed-host xAI/OpenAI/Anthropic/Gemini/Groq/Together transports, bounded provider model discovery, loopback local-AI adapters, and optional local role backends are implemented. See [`AUTH.md`](AUTH.md), [`ADAPTERS.md`](ADAPTERS.md), and [`XAI_ADAPTER.md`](XAI_ADAPTER.md).

## `telemetry.verify`

Recompute deterministic Council telemetry from a captured `council_session` object.

```json
{"request_id":"t1","operation":"telemetry.verify","session_ref":"object:<sha256>"}
```

A successful verification returns `status: "verified"`, `matches: true`, the telemetry schema version, and the recomputed telemetry block. Telemetry is observational only and cannot alter Council authority or evidence status.
