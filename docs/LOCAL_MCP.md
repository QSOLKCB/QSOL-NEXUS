# Local AI + MCP Role Backends

## Purpose

PR #27 adds an explicitly local-only path for running NEXUS with LM Studio, AnythingLLM, and other loopback OpenAI-compatible model hosts.

The feature has two related uses:

1. **ordinary local Council actors** can use a loopback local model instead of Ollama or a cloud provider;
2. selected **deterministic system roles** can use a local model for their language/reasoning surface while the original deterministic role keeps authoritative governance mechanics.

The second distinction is deliberate. A local model may make a Failsafe relief response less robotic or let a civic proxy reason with local context, but it does not gain the power to rewrite the ballot, create another seat, change citizenship, or bypass verification.

## Admitted local backends

| adapter id | default origin | inference surface | MCP behavior |
| --- | --- | --- | --- |
| `lmstudio_local` | `http://127.0.0.1:1234` | LM Studio `POST /api/v1/chat` | NEXUS may select pre-configured `mcp.json` plugin ids only |
| `anythingllm_local` | `http://127.0.0.1:3001` | AnythingLLM workspace chat API | NEXUS invokes `@agent`; MCP/tool configuration remains owned by the local workspace |
| `openai_local` | `http://127.0.0.1:8000` | `POST /v1/chat/completions` | no NEXUS-selected MCP integration |

`openai_local` is intentionally generic. It is for loopback-only OpenAI-compatible runtimes that do not need a dedicated NEXUS adapter.

## Local means loopback at the NEXUS boundary

Every endpoint supplied to these adapters must be an origin using one of:

```text
localhost
127.0.0.0/8 loopback literals
::1
```

NEXUS rejects:

- LAN addresses such as `192.168.x.x`;
- `0.0.0.0`;
- DNS hostnames other than `localhost`;
- public/remote hosts;
- endpoint paths, query strings, fragments, or user-info;
- ambient HTTP proxy routing;
- HTTP redirects.

This is a NEXUS transport guarantee, not a claim that every tool configured inside LM Studio or AnythingLLM is local. If an operator puts a remote MCP server in LM Studio's `mcp.json`, or configures AnythingLLM with a network tool, that downstream tool remains an operator-controlled host boundary that NEXUS cannot independently prove local.

For a strict air-gapped/local-only deployment, configure the downstream MCP/tool layer locally too.

## LM Studio MCP contract

NEXUS deliberately does **not** expose LM Studio's ephemeral per-request MCP shape.

Accepted configuration is restricted to an already-installed plugin id:

```json
{
  "id": "mcp/local-notes",
  "allowed_tools": ["search_notes", "read_note"]
}
```

NEXUS does not accept per-request MCP:

```text
server_url
headers
command
args
env
```

LM Studio configured MCP plugins require its API authentication mode, so NEXUS requires an environment-backed local credential reference whenever `mcp_plugins` is non-empty.

The environment variable name may appear in configuration; the token value may not.

## AnythingLLM contract

AnythingLLM selects its model and tools through a workspace. NEXUS therefore configures a workspace rather than a model id:

```json
{
  "adapter_id": "anythingllm_local",
  "workspace": "nexus-local",
  "credential_env": "ANYTHINGLLM_API_KEY"
}
```

NEXUS sends the prompt through the workspace chat endpoint in `@agent` form so the workspace's agent/MCP layer is eligible to run. NEXUS does not inject or rewrite AnythingLLM MCP server definitions; that remains local AnythingLLM configuration.

## Ephemeral local credentials

Local-role configuration is process-local and is not persisted to `WorldStore` or the auth profile store.

A backend may name one environment variable:

```json
"credential_env": "LM_STUDIO_TOKEN"
```

At invocation time NEXUS reads that variable and creates an in-memory bearer credential for the loopback request. The raw value is never returned by `local.roles.status` and is never part of world identity, receipts, citizenship objects, or the local-role configuration record.

## Configure a deterministic role

The currently admitted system roles are:

```text
failsafe_relief
civic_proxy
```

Example: use LM Studio plus a local notes MCP for the Failsafe relief role:

```json
{
  "operation": "local.roles.configure",
  "role_id": "failsafe_relief",
  "backend": {
    "adapter_id": "lmstudio_local",
    "model": "qwen/qwen3-8b",
    "credential_env": "LM_STUDIO_TOKEN",
    "mcp_plugins": [
      {
        "id": "mcp/local-notes",
        "allowed_tools": ["search_notes", "read_note"]
      }
    ],
    "max_output_tokens": 768
  }
}
```

Example: use an AnythingLLM workspace for the deterministic civic proxy:

```json
{
  "operation": "local.roles.configure",
  "role_id": "civic_proxy",
  "backend": {
    "adapter_id": "anythingllm_local",
    "workspace": "nexus-civic",
    "credential_env": "ANYTHINGLLM_API_KEY"
  }
}
```

Inspect or clear process-local configuration:

```json
{"operation":"local.roles.status"}
{"operation":"local.roles.clear","role_id":"civic_proxy"}
```

Configuration is intentionally ephemeral. Restarting NEXUS restores the original deterministic role behavior until the operator explicitly configures a local backend again.

## What "replace deterministic" means

The local model replaces the **generated language/reasoning surface**, not the constitutional state machine.

### Failsafe relief

The original Failsafe decides that the subject is contained and creates the same deterministic relief seat as before.

With a configured local backend:

```text
Failsafe policy
    -> same-seat relief role
        -> local model/MCP language generation
        -> authoritative ballot remains TEST_FURTHER
```

The local model does not decide whether containment happens and cannot change the relief ballot.

### Civic proxy

The original Citizen Mode registry creates the same deterministic civic proxy and preserves the citizen's standing ballot.

With a configured local backend:

```text
citizen standing directive
    -> same-seat civic proxy
        -> local model/MCP language generation
        -> authoritative ballot remains standing directive
```

The model cannot become a citizen through the proxy, create another vote, sign founding independence, amend the Constitution, move independently, or choose a different ballot.

### Failure behavior

Local role enrichment is optional. If the configured local host/model/tool fails, the role falls back to the pre-existing deterministic response instead of making Failsafe or civic administration less available.

## Ordinary local Council actors

The same three local adapters may be used as normal Council actors. Those seats still inherit the ordinary NEXUS equality rule:

```text
vote_weight = 1
epistemic_privilege = none
```

LM Studio MCP plugins may be used during phase and direct-chat generation. **MCP tools are removed from the sealed-ballot request**, so a ballot is produced without invoking a tool during that sealed step.

AnythingLLM uses its workspace agent layer; the workspace decides which locally configured tools/MCP integrations are available.

All live local model actors are marked non-replayable. A deterministic fallback role wrapped by a live local model is also non-replayable for the run in which the local model contributes text.

## Security boundary

This feature does not make NEXUS an unrestricted MCP gateway.

NEXUS does not:

- accept arbitrary MCP URLs in Council or role requests;
- accept per-request MCP authorization headers;
- spawn arbitrary MCP commands from JSONL input;
- pass arbitrary environment blocks to MCP processes;
- grant MCP tools direct `WorldStore` authority;
- let local-role models change deterministic Failsafe/civic ballots;
- count a local backend as an additional Council member;
- classify a model as more authoritative because it is local, open-weight, larger, or MCP-capable.

An MCP tool can still have whatever external side effects the operator gave that tool outside NEXUS. Treat LM Studio `mcp.json` and AnythingLLM workspace tool configuration as trusted local operator configuration.

The boundary remains:

> **Local model intelligence may enrich the role. NEXUS governance still owns the seat.**
