# Provider-Neutral Authentication Foundation

## Status

PR #16 introduced the provider-neutral substrate. PR #17 uses it to admit the first fixed-destination remote adapter: xAI / Grok.

Implemented now:

- adapter-owned authentication descriptors;
- browser authorization-code flow with PKCE `S256` and a loopback callback;
- OAuth device authorization for headless hosts;
- refresh-token rotation;
- cross-process serialization of profile mutations and refresh-token rotation;
- hidden-prompt API credential storage;
- environment-backed credentials;
- no-shell external credential helpers;
- OS keyring use when the optional keyring backend is available;
- an owner-only private-file fallback;
- non-secret `auth.adapters`, `auth.list`, `auth.test`, and `auth.logout` JSONL operations;
- a conventional `nexus auth ...` command surface.

Implemented for xAI in PR #17:

- API-key, environment, and external-helper profiles;
- a browser-assisted API-key setup page plus hidden terminal input;
- an authenticated bounded connection test;
- language-model discovery;
- fixed-host Responses API inference with `store: false`;
- direct-message and equal-vote Council actor wiring.

Still not implemented:

- any remote provider other than xAI;
- a provider-registered NEXUS OAuth client;
- reuse of another CLI's login session;
- consumer-browser cookie or session-token scraping.

`system.health` now reports `remote_provider_auth: true` and `remote_adapters_admitted: true` because xAI is admitted.

## Operator commands

Install the package and, where supported, the optional OS-keyring integration:

```bash
python -m pip install -e '.[keyring]'
```

Inspect the currently registered adapters and their non-secret capabilities:

```bash
nexus auth adapters
nexus auth list
```

Profiles use the same provider-neutral commands:

```bash
nexus auth add <adapter> --profile personal --method browser
nexus auth add <adapter> --profile ssh --method device
nexus auth add <adapter> --profile ci --method env --env PROVIDER_API_KEY
nexus auth add <adapter> --profile corp --method external-command \
  --command /absolute/path/to/credential-helper
nexus auth test <adapter> --profile personal
nexus auth logout <adapter> --profile personal
```

xAI's supported interactive path is browser-assisted API-key enrollment:

```bash
nexus auth add xai --profile personal --method browser-key
```

This opens `https://console.x.ai/team/default/api-keys` and reads the generated key through the same hidden prompt as `--method api-key`. It does not run browser OAuth.

`--method api-key` reads from a hidden terminal prompt. There is deliberately no `--api-key VALUE` argument because command-line arguments are commonly retained in shell history and exposed through process inspection.

The JSONL control protocol does not accept raw credentials and does not expose `auth.add`. Interactive enrollment belongs to the direct operator CLI. JSONL clients may inspect adapters/profiles, request a bounded connection test, and explicitly remove a profile.

## Descriptor contract

Each adapter declares only the methods it actually supports:

```text
AdapterAuthDescriptor
├── adapter_id
├── provider_name
├── local_or_remote
├── auth_methods[]
├── auth_flows[]
├── provider-owned OAuth endpoint configuration?
└── implementation_status
```

Authentication method categories remain:

```text
api_credential
provider_supported_interactive
external_secret
local_endpoint
no_auth_required
```

Concrete flows are:

```text
api_key
browser_pkce
device_code
environment
external_command
local_endpoint
none
```

The descriptor has no vote-weight or epistemic-privilege field. Provider identity, authentication method, account tier, model size, and model availability remain operational metadata only.

## Browser flow

The browser flow follows the native-application pattern:

1. bind an ephemeral callback listener to `127.0.0.1`;
2. generate a high-entropy `state` and PKCE verifier;
3. send only the `S256` challenge to an adapter-owned HTTPS authorization endpoint;
4. open the system browser, or print the URL for manual opening;
5. accept only the exact callback path and matching state;
6. exchange the code directly with the adapter-owned token endpoint using the verifier;
7. reject token-endpoint redirects;
8. store token material through the selected credential backend;
9. refresh expiring tokens through the same fixed token endpoint, preserving prior scopes when the provider omits an unchanged `scope` field.

Provider endpoints are code-owned descriptor data, not arbitrary values supplied during login. HTTPS is mandatory except for explicit loopback-only fixtures. OAuth response bodies, authorization codes, PKCE verifiers, access tokens, refresh tokens, and credential handles are absent from public results and error messages.

This implements [RFC 7636 PKCE](https://www.rfc-editor.org/info/rfc7636/) and follows the loopback/native-app posture in [RFC 8252](https://www.rfc-editor.org/info/rfc8252/). It is an OAuth substrate, not a claim that every provider exposes the same browser flow.

## Device flow

The headless path implements the [RFC 8628 device authorization grant](https://www.rfc-editor.org/info/rfc8628/):

- device and token endpoints are fixed by the adapter descriptor;
- the provider-returned verification URL must match a separate descriptor allowlist;
- `authorization_pending` and `slow_down` are handled without exposing response bodies;
- the device code is never printed or persisted;
- the short user code and verification URL are displayed only for the active enrollment;
- polling expires on the provider-supplied deadline with a hard 30-minute client ceiling.

## Credential sources and storage

Stored credentials first attempt the OS keyring when the optional `keyring` integration finds an available backend. Supported native services include macOS Keychain, Freedesktop Secret Service/KWallet, and Windows Credential Locker. See the [keyring project documentation](https://keyring.readthedocs.io/).

If no usable OS keyring is installed—or an enrolled keyring rejects the actual credential write—NEXUS falls back to an explicitly identified private-file backend and reports that fallback in the enrollment result:

```text
auth directory: 0700 on POSIX
profile file:   0600 on POSIX
secret files:   0600 on POSIX
```

Auth directories are created owner-only; an existing directory with group/other permissions is rejected rather than silently chmodded. Files with group/other permissions, symbolic-link traversal, unknown fields, duplicate profiles, or unsupported schema versions fail closed. The private-file fallback protects against other ordinary OS users; it does not protect a bearer token from the same compromised account, privileged malware, or an unencrypted stolen disk. Full-disk encryption remains recommended.

Profile load-modify-save transactions and refresh-token read-refresh-write transactions share one owner-only `auth.lock`. The lock is re-entrant within a process and advisory across processes, preventing concurrent CLI/runtime instances from losing profiles or submitting the same rotating refresh token twice.

Operational overrides:

```text
NEXUS_AUTH_ROOT              dedicated absolute auth directory
NEXUS_AUTH_FORCE_FILE_STORE  set to 1 to bypass optional keyring discovery
```

Auth storage and file-backed world storage must be disjoint directories. NEXUS rejects either directory being nested inside the other.

Environment profiles persist only the variable name. External-command profiles persist only the helper invocation; the helper must be an absolute executable path, runs with `shell=False`, receives no stdin, and must emit one bounded JSON object:

```json
{
  "access_token": "...",
  "refresh_token": "... optional ...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "scope": "models.read inference"
}
```

Raw tokens must never be placed in helper arguments. Credential-bearing options such as `--token`, `--api-key`, `--password`, and their inline-value forms are rejected before argv is persisted. Helper stdout is parsed as secret material and never copied into normal output; stderr is suppressed at the broker boundary.

## Grok Build relationship

The operator experience is intentionally similar to coding CLIs that open a browser. xAI documents browser sessions for [Grok Build authentication](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md), while its [public API quickstart](https://docs.x.ai/developers/quickstart) documents API-key authentication for inference clients.

NEXUS copies the browser-assisted interaction pattern, not Grok Build's credentials. It does not read `~/.grok/auth.json`, copy browser cookies, use another application's OAuth client identity, or send Grok Build bearer material to the xAI adapter. PR #17 therefore uses the documented API-key path. A future browser-PKCE change still requires a provider-supported NEXUS client-registration path.

## Public-output boundary

Safe public auth state includes:

```text
adapter id
profile name
auth method / flow
credential source kind
non-secret backend name
configured / ready / unavailable status
bounded provider connection-test code
```

Public state excludes:

```text
access and refresh tokens
API keys
authorization codes
PKCE verifiers
device codes
credential handles
token endpoint response bodies
helper stdout/stderr
```

Only adapter transport code may call `AuthBroker.resolve()` and receive `SecretMaterial`. `SecretMaterial.__repr__` is redacted. Auth profile files are operational configuration, never WorldStore objects, evidence, prompts, transcripts, receipts, replay bundles, or experiment artifacts.

## Provider admission checklist

A later remote adapter remains inadmissible until its PR supplies:

- a provider-specific descriptor and fixed destination allowlists;
- an officially supported auth/client-registration path;
- an authenticated connection test with bounded public output;
- model discovery or an explicit model allowlist;
- adapter transport budgets, timeout, redirect, and error contracts;
- refresh and logout behavior;
- provider-specific threat-model coverage;
- tests proving credentials do not enter prompts, world objects, receipts, logs, or exceptions;
- `replayable = false` for live remote inference;
- the unchanged one-member/one-vote and `epistemic_privilege = none` invariants.

The xAI implementation and its provider-specific checklist are documented in [`XAI_ADAPTER.md`](XAI_ADAPTER.md).
