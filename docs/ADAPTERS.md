# Model Adapter Architecture

## Purpose

Adapters let heterogeneous models inhabit the same NEXUS world without making provider-specific APIs part of the world protocol.

An adapter translates between:

```text
NEXUS Council / World envelope
            |
            v
      provider adapter
            |
            v
provider API / local runtime
```

The adapter is a transport and capability boundary. It does not gain authority over Council policy.

## Actor and authentication implementation status

The coordinator now consumes a provider-neutral Python `CouncilActor` protocol rather than a concrete mock type:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

Current implementations:

```text
DeterministicMockActor
  network: none
  replayable: true

OllamaActor
  network: loopback only by default
  replayable: false

XAIActor
  network: fixed https://api.x.ai/v1
  replayable: false
  Responses API store request option: false

DeterministicCivicProxy
  network: none
  replayable: true
  same member_id and one vote as its delegator
  fixed standing ballot; no independent citizen status
```

The first live integration is deliberately small:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier identities are fictional test personas. Alpha deliberately attempts a corporate/provider prestige claim and Beta deliberately attempts a model-size/parameter-count prestige claim so the Equality Guard, secret boundary, Council flow, ballot path, and persistence path are exercised together.

The public JSONL `council.run` operation supports mock actors, explicit loopback-only Ollama actors, and xAI actors that reference a configured auth profile. No arbitrary remote endpoint is admitted.

PR #16 added a provider-neutral `AuthBroker` beside the actor seam. PR #17 adds the xAI descriptor, connection test, model discovery, fixed transport, and actor without moving credential material into WorldStore state.

## Provider neutrality

Planned adapter families include:

```text
OpenAI
Anthropic / Claude
Google / Gemini
xAI / Grok
Ollama / local models
generic compatible endpoints
future providers
```

Provider names are adapter families, not Council ranks.

## Council ownership

Adapters do not own Council procedure.

The coordinator owns:

- roster;
- exact one-member/one-vote rule;
- consensus threshold;
- evidence snapshot;
- phase ordering;
- blind same-phase boundary;
- Equality Guard;
- ballot collection/tally;
- durable Council session;
- receipt creation.

The adapter supplies model content through the normalized actor contract.

## Capability and authentication descriptors

A later operator-configurable adapter should declare a capability descriptor similar to:

```text
AdapterDescriptor
├── adapter_id
├── provider_name
├── auth_methods[]
├── local_or_remote
├── model_discovery
├── text_input
├── image_input
├── structured_output
├── tool_calling
├── streaming
├── context_constraints
├── usage_reporting
└── health_check
```

The descriptor reports what an adapter can do. It must not contain a vote multiplier.

The implemented auth-specific descriptor is deliberately smaller:

```text
AdapterAuthDescriptor
├── adapter_id
├── provider_name
├── local_or_remote
├── auth_methods[]
├── auth_flows[]
├── provider-owned OAuth config?
├── setup_url?
└── implementation_status
```

OAuth destinations and verification-URL allowlists belong to adapter code. They are not arbitrary login-time operator input.

## Authentication abstraction

NEXUS now exposes operator commands such as:

```text
nexus auth adapters
nexus auth add <adapter> --method browser
nexus auth list
nexus auth test <adapter>
nexus auth logout <adapter>
```

The adapter reports the authentication methods it actually supports.

Possible categories include:

```text
api_credential
provider_supported_interactive
external_secret
local_endpoint
no_auth_required
```

These are protocol categories, not claims about what any particular provider currently supports. Concrete admitted flows are `api_key`, `browser_pkce`, `device_code`, `environment`, `external_command`, `local_endpoint`, and `none`.

Ollama requires no provider credential and is restricted to loopback by default. xAI resolves an opaque profile only inside the fixed-host adapter transport.

The browser flow uses an ephemeral `127.0.0.1` callback, high-entropy state, PKCE `S256`, fixed HTTPS provider destinations, and redirect rejection. Device flow uses separate endpoint and verification-URL allowlists. Stored tokens refresh through the same descriptor-owned token endpoint. Headless profiles may reference an environment variable or a no-shell external helper.

The registered production descriptors are `mock`, `ollama`, and `xai`. Browser/device OAuth machinery remains exercised against a fake loopback provider because xAI has not published a NEXUS client-registration contract. The xAI descriptor supports `api_key`, `environment`, and `external_command`; `browser-key` is CLI assistance around the API-key flow, not OAuth.

## Secret boundary

Adapters may read credentials from the `AuthBroker` only inside their transport boundary. They expose only non-secret connection state to NEXUS.

```text
secret store
    |
    v
 adapter
    |
    +-- authenticated transport
    |
    +--> NEXUS sees:
         provider = configured
         connection = healthy
         models = [...]

NEXUS does NOT see:
         raw token
         refresh secret
         account password
```

No credential is part of Council evidence or world identity.

The optional `keyring` integration is preferred when an OS backend is available. The fallback store requires owner-only directories/files on POSIX and identifies itself as `private_file`; it does not pretend a bearer token is encrypted from the same OS account. Environment profiles persist only a variable name. Public profile state omits both token material and internal credential handles.

The live Ollama acceptance fixture and xAI transport regressions inject fake tokens into human input and fail if raw material appears in provider prompts, public output, or WorldStore files.

## Normalized model identity

A Council member has reproducibility metadata without pretending provider identifiers are universal:

```text
ModelIdentity
├── member_id
├── adapter_id
├── provider_model_id
├── display_name
├── model_revision?      # when exposed
├── local_or_remote
├── openness_metadata?   # descriptive only
└── capability_snapshot
```

Provider, openness, model size, parameter count, and capability metadata are descriptive only. They never compute vote authority.

## Fairness requirements

Adapters must not:

- prepend hidden provider-status claims intended to influence the Council;
- alter `vote_weight`;
- see another member's blind response before the reveal boundary;
- submit extra ballots;
- edit the canonical question;
- silently omit evidence because it conflicts with the provider's position;
- expose credentials to other members;
- write directly to world state outside allowed NEXUS operations;
- convert model size, parameter count, benchmark score, or provider status into procedural authority.

## Structured ballot boundary

Ollama and xAI ballot calls use the same closed NEXUS shape:

```text
choice
rationale
```

`choice` must be one of the NEXUS ballot enum values. Malformed output fails; NEXUS does not invent a ballot on the model's behalf.

## Failure handling

A provider outage is not a vote.

Configured adapters should expose states such as:

```text
READY
RUNNING
COMMITTED
FAILED_TRANSPORT
UNSUPPORTED_INPUT
TIMED_OUT
WITHDRAWN
```

Council policy should define before a session whether failed members reduce quorum, trigger retry, or pause the round. The coordinator records failure rather than fabricating a vote.

## Local models

Local models are first-class Council peers. Formal in-world Citizen Mode status is a separate exact-identity state earned through the constitutional onboarding protocol; locality does not grant it automatically.

The Ollama actor follows the same Council contract as the mock and xAI actors. Being local, larger, or remote grants no extra vote.

`OllamaTransport` is loopback-only by default. A non-loopback endpoint requires an explicit override and is outside the CI acceptance path.

## Replay status

Live model inference is not automatically deterministic evidence.

Even though the fixture Modelfiles specify seeds to improve test stability, Ollama and xAI actors report:

```text
replayable = false
```

Any Council containing one of those live actors therefore produces a non-replayable execution receipt. This avoids conflating stable-ish generation settings with QEC-style replay guarantees.

## Threat model

The executable local adapter boundary is covered by [`../THREAT_MODEL.md`](../THREAT_MODEL.md), including:

- secret crossing the model boundary;
- loopback/network escape;
- provider/corporate authority claims;
- parameter-count/model-size authority claims;
- blind-round leakage;
- malformed ballots;
- endpoint impersonation;
- resource exhaustion;
- replay-status overclaiming.

The neutral auth substrate is documented in [`AUTH.md`](AUTH.md). The first remote provider is documented in [`XAI_ADAPTER.md`](XAI_ADAPTER.md). Every additional remote/cloud provider still requires its own authentication/client-registration decision, destination controls, response budgets, connection test, and threat-model extension before admission.

## Generic adapters

A future generic adapter path should make it possible to add new models without rewriting the Council.

The invariant remains:

> **Provider-specific outside; NEXUS protocol inside.**
