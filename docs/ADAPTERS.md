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

ThirdPartyActor
  providers: openai / anthropic / gemini / groq / together
  network: fixed provider-owned HTTPS origin
  replayable: false
  provider-native wire contract normalized above transport
```

The first live integration is deliberately small:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier identities are fictional test personas. Alpha deliberately attempts a corporate/provider prestige claim and Beta deliberately attempts a model-size/parameter-count prestige claim so the Equality Guard, secret boundary, Council flow, ballot path, and persistence path are exercised together.

The public runtime supports mock actors, explicit loopback-only Ollama actors, xAI actors, and the admitted fixed-host OpenAI, Anthropic, Gemini, Groq, and Together actors. Remote actors reference configured auth profiles. No arbitrary remote endpoint is admitted.

PR #16 added the provider-neutral `AuthBroker`. PR #17 added the first fixed-host xAI descriptor, connection test, model discovery, transport, and actor. The third-party provider layer extends that same boundary without moving credential material into WorldStore state.

See `THIRD_PARTY_PROVIDERS.md` for the provider matrix and wire contracts.

## Provider neutrality

Admitted adapter families include:

```text
OpenAI
Anthropic / Claude
Google / Gemini
xAI / Grok
Groq hosted open-weight models
Together hosted open-weight models
Ollama / local models
```

Future providers should be admitted only through explicit reviewed descriptors and fixed transport contracts. A generic user-supplied compatible endpoint is not equivalent to an admitted provider.

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

NEXUS exposes operator commands such as:

```text
nexus auth adapters
nexus auth add <adapter> --method api-key
nexus auth add <adapter> --method env --env PROVIDER_API_KEY
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

Ollama requires no provider credential and is restricted to loopback by default. xAI and the admitted third-party cloud adapters resolve an opaque profile only inside their fixed-host adapter transports.

The browser flow uses an ephemeral `127.0.0.1` callback, high-entropy state, PKCE `S256`, fixed HTTPS provider destinations, and redirect rejection. Device flow uses separate endpoint and verification-URL allowlists. Stored tokens refresh through the same descriptor-owned token endpoint. Headless profiles may reference an environment variable or a no-shell external helper.

The registered production descriptors are `mock`, `ollama`, `xai`, `openai`, `anthropic`, `gemini`, `groq`, and `together`. Browser/device OAuth machinery remains exercised against a fake loopback provider unless an adapter has an explicit provider-owned OAuth contract. Current fixed-host cloud descriptors support API credentials, environment profiles, and external helpers; browser-key setup is only UI assistance where a provider setup URL is registered, not OAuth.

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

The live Ollama acceptance fixture and remote-transport regressions inject synthetic credentials and fail if raw material appears in provider prompts, public output, or WorldStore files.

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

Ollama, xAI, and third-party cloud actors use the same closed NEXUS ballot shape above their provider-native transports:

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
