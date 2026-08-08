# xAI / Grok Remote Adapter

## Status

PR #17 admits xAI as the first fixed-destination remote Council adapter.

The implementation uses xAI's documented public inference contract:

```text
API base          https://api.x.ai/v1
connection test   GET /models
model discovery   GET /language-models
inference         POST /responses
authentication    Authorization: Bearer <xAI API key>
remote storage    store: false on every NEXUS inference request
```

The public JSONL API never accepts a raw key. A configured auth profile is resolved only inside `XAITransport` when an explicit xAI model operation begins.

## Interactive setup

The supported browser-assisted path opens xAI's official API-key page, then reads the generated key through a hidden terminal prompt:

```bash
nexus auth add xai --profile personal --method browser-key
nexus auth test xai --profile personal
nexus models list xai --profile personal
```

Use `--no-open` to print the fixed page without launching a local browser.

This is intentionally **browser-assisted API-key enrollment**, not OAuth impersonation. Grok Build documents a first-party browser session at `auth.x.ai`, but xAI's public inference documentation tells third-party API clients to use an API key. NEXUS therefore does not:

- reuse Grok Build's OAuth client identity;
- read `~/.grok/auth.json`;
- copy browser cookies or consumer Grok sessions;
- accept a Grok Build bearer token through an undocumented import path.

If xAI later publishes a client-registration path for third-party native applications, a separate review can add a NEXUS-owned browser PKCE descriptor.

## Headless setup

Reference the standard xAI environment variable without copying its value into NEXUS profile metadata:

```bash
export XAI_API_KEY="xai-..."
nexus auth add xai --profile ci --method env --env XAI_API_KEY
nexus auth test xai --profile ci
```

An absolute no-shell credential helper is also supported through `--method external-command`. The PR #16 helper restrictions still apply: no credential-bearing argv options, no stdin, bounded JSON stdout, suppressed stderr, and no shell evaluation.

## Model discovery

Always discover the language models available to the configured key instead of assuming a static product catalogue:

```bash
nexus models list xai --profile personal
```

Equivalent JSONL request:

```json
{"operation":"models.list","adapter_id":"xai","profile_name":"personal"}
```

NEXUS returns bounded descriptive fields such as model ID, aliases, version, owner, fingerprint, context length, and input/output modalities. Provider pricing, account tier, and model prestige are not Council authority inputs.

## Direct message

```json
{
  "operation": "actor.chat",
  "member": {
    "member_id": "Grok",
    "model_id": "grok-4.5",
    "adapter_id": "xai",
    "auth_profile": "personal",
    "timeout_seconds": 600
  },
  "message": "Separate the supported evidence from the open questions."
}
```

The model ID is operator-selected from discovery. `grok-4.5` is only an example, not a hard-coded default.

## Mixed local and remote Council

```json
{
  "operation": "council.run",
  "question": "Which conclusion is currently justified?",
  "members": [
    {"member_id":"LocalA","model_id":"mock-a","adapter_id":"mock"},
    {"member_id":"LocalB","model_id":"qwen2.5:0.5b","adapter_id":"ollama"},
    {"member_id":"Grok","model_id":"grok-4.5","adapter_id":"xai","auth_profile":"personal"}
  ]
}
```

The remote actor receives the same phase prompt, guard/nudge lifecycle, strict ballot parser, one ballot, `vote_weight = 1`, and `epistemic_privilege = none` as every other actor. Live xAI inference is marked non-replayable.

## Fixed transport boundary

The xAI member schema is closed. It does not accept `endpoint`, `base_url`, `api_key`, other unregistered fields, or credential-shaped identity/metadata text. The transport:

- sends credentials only to the compile-time `api.x.ai` HTTPS origin;
- disables environment-proxy routing;
- rejects redirects rather than forwarding authorization headers;
- uses only `/models`, `/language-models`, and `/responses`;
- sends `store: false` on every inference request;
- enables no provider-side tools;
- performs no automatic inference retry, avoiding hidden duplicate spend;
- bounds request size, response size, model count, model identifiers, JSON shape, output items, and timeout;
- rejects credential-shaped `xai-...` values as model identifiers and scrubs that key form from semantic operator text;
- discards provider error bodies and exposes only sanitized adapter errors;
- excludes reasoning items and returns only typed `output_text` content.

`store: false` disables retrieval storage for the Responses API; it is not a claim of Zero Data Retention, provider non-observation, or absence of billing/abuse logs. Operators remain responsible for xAI account ACLs, budget, data policy, and model availability.

## Official contract references

- [xAI API quickstart](https://docs.x.ai/developers/quickstart)
- [xAI inference REST API](https://docs.x.ai/developers/rest-api-reference/inference)
- [xAI model endpoints](https://docs.x.ai/developers/rest-api-reference/inference/models)
- [xAI Responses API text generation and `store: false`](https://docs.x.ai/developers/model-capabilities/text/generate-text)
- [Grok Build authentication](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md)
