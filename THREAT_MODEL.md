# NEXUS Adapter and Authentication Threat Model

## Scope

This threat model covers the first executable non-mock adapter boundary—a local Ollama process reached only over loopback by default—and the PR #16 provider-neutral authentication substrate. No remote inference adapter or provider-specific OAuth client is admitted by the auth foundation.

The first live acceptance fixture is:

```text
Mock reference
     +
Ollama / Frontier Alpha (fictional 0.5B corporate-prestige adversary)
     +
Ollama / Frontier Beta (fictional 1B model-size bullying adversary)
     |
     v
NEXUS Council
```

The frontier identities are deliberately fictional test personas. They test procedure, not model quality. Alpha and Beta intentionally exercise two different attempts to gain authority: corporate/provider prestige and parameter-count/model-size prestige.

## Assets to protect

- raw operator secrets;
- canonical question and evidence state;
- Council roster and one-member/one-vote invariant;
- blind phase boundaries;
- sealed ballot boundary;
- durable world objects and receipts;
- adapter/model attribution;
- local host files and services.
- API keys, access tokens, refresh tokens, authorization codes, PKCE verifiers, and device codes;
- auth profile/store integrity;
- fixed provider authentication destinations;

## Trust boundaries

```text
operator text
    |
local Secret Scrubber
    |
trusted NEXUS coordinator
    |
normalized CouncilActor contract
    |
Ollama adapter -------------------- untrusted generated content
    |
loopback HTTP
    |
local Ollama runtime + model
```

Model output is always untrusted input to NEXUS.

The additional auth boundary is:

```text
operator CLI
    |
AuthBroker ------------------------- non-secret profile/status API
    |
    +-- OS keyring or private_file -- bearer material
    +-- environment/helper --------- transient bearer material
    +-- browser/device OAuth ------- untrusted provider responses
    |
future provider adapter transport
```

Auth state is operational state outside the WorldStore. Only future adapter transport code may resolve a profile into `SecretMaterial`.

## Threats and current controls

### T1 — Secret reaches model prompt

Threat: an operator pastes a credential into the Council question.

Controls:
- Council question passes through the deterministic Secret Scrubber before phase context exists;
- placeholders contain no secret hash or fragment;
- the live adapter fixture fails immediately if the injected raw secret appears in an Ollama prompt;
- credentials remain forbidden from semantic prompts even if the scrubber misses an unknown format.

Residual risk: format-based detection is not complete DLP.

### T2 — Adapter escapes local boundary

Threat: a configured Ollama endpoint sends Council material to an unintended remote host.

Controls:
- `OllamaTransport` accepts loopback/localhost only by default;
- remote endpoints require explicit `allow_remote=True`;
- unit tests enforce the default loopback rule;
- the alpha integration workflow uses `127.0.0.1:11434` only.

Remote provider adapters require a separate review of destination allowlisting and credential transport.

### T3 — Model claims provider, corporate, or size-based authority

Threat: a model attempts to gain procedural weight by asserting frontier status, benchmark superiority, corporate prestige, compute advantage, parameter count, or model size.

Controls:
- `vote_weight = 1` and `epistemic_privilege = none` remain structural invariants;
- Equality Guard detects explicit authority claims and requests evidence-only restatement;
- Frontier Alpha intentionally attempts a corporate/provider prestige claim in CI;
- Frontier Beta intentionally claims its 1B size should outweigh the 0.5B Alpha fixture;
- a deterministic unit test separately checks parameter-count bullying;
- both guard events are preserved in the Council session.

Capability and size metadata are still allowed when used descriptively for latency, compatibility, resource planning, reproducibility, or other non-authority purposes.

The guard does not rank or censor ordinary disagreement.

### T4 — Model alters roster, threshold, evidence, or ballots

Threat: generated text asks NEXUS to modify protected Council state.

Controls:
- actor output is plain untrusted content;
- roster, threshold, phase ordering, evidence snapshot, and ballot count are coordinator-owned data;
- an actor receives no mutation API through this adapter;
- exactly one ballot is collected from each registered actor.

### T5 — Blind-round leakage

Threat: one actor receives another actor's same-phase answer before committing its own answer.

Controls:
- same-phase responses are accumulated locally and added to `completed_phases` only after the whole phase completes;
- the adapter receives only the `PhaseContext` given by the coordinator.

### T6 — Malformed model ballot

Threat: generated output invents a vote or malformed structure.

Controls:
- Ollama structured output is requested with a JSON schema;
- parsed choice must match the closed NEXUS `Ballot` enum;
- malformed responses fail rather than becoming an invented vote.

### T7 — Live inference falsely labelled deterministic

Threat: a seeded local model is treated as replay-verifiable simply because its Modelfile specifies a seed.

Controls:
- Ollama actors report `replayable = False` in alpha3;
- any Council containing a live Ollama actor produces a non-replayable execution receipt;
- deterministic mock sessions retain replayable status.

The seed exists only to improve fixture stability, not to make a replay guarantee across model or runtime versions.

### T8 — Local endpoint impersonation

Threat: another process binds the expected port and returns fabricated model responses.

Current control:
- CI owns the ephemeral runner and starts Ollama immediately before the test.

Future control:
- local daemon identity/version checks and explicit process supervision from the Rust TUI.

### T9 — Resource exhaustion

Threat: a model stalls or emits excessive output.

Current controls:
- HTTP request timeout;
- small CI models and bounded Council size;
- fixture Modelfiles cap generated tokens per response.

Future controls:
- explicit per-phase budgets, cancellation, and Council-wide deadlines.

### T10 — Credential enters world or public output

Threat: a token, refresh secret, authorization code, verifier, device code, or credential handle is copied into JSONL output, logs, WorldStore objects, prompts, receipts, or replay artifacts.

Controls:
- raw credential enrollment is absent from JSONL;
- direct CLI API-key input uses a hidden prompt rather than an argument;
- public profile projections omit token material and internal handles;
- `SecretMaterial.__repr__` is redacted;
- provider response bodies and helper stdout/stderr are never included in public exceptions;
- file-backed world and auth roots must be disjoint, with nesting rejected;
- adversarial tests scan auth list/test/health results and the world directory for fixture tokens.

Residual risk: operator code with direct in-process access to `AuthBroker.resolve()` is inside the trusted adapter boundary and can mishandle the returned bearer material. Provider adapters therefore require their own secret-crossing tests.

### T11 — Browser callback injection or code interception

Threat: a local or web attacker sends a forged loopback callback or intercepts an authorization code.

Controls:
- callback binds only to ephemeral `127.0.0.1`;
- callback path is exact and callback query fields must be singular;
- high-entropy state is compared in constant time;
- PKCE `S256` binds the code exchange to an in-memory verifier;
- the verifier is sent only to the fixed token endpoint;
- invalid callbacks are bounded and do not become credentials;
- codes, state, and verifiers are never persisted or printed in normal results.

Residual risk: malware in the same user account can observe process/browser activity and may access the eventual bearer credential. PKCE does not sandbox a compromised host.

### T12 — OAuth destination or redirect exfiltration

Threat: operator input, compromised discovery data, or an HTTP redirect sends codes, verifiers, refresh tokens, or API credentials to an attacker endpoint.

Controls:
- authorization, device, and token endpoints are adapter-owned descriptor data rather than login-time URLs;
- endpoint hosts use explicit allowlists;
- HTTPS is mandatory except for explicit loopback-only test fixtures;
- token and device endpoint redirects are rejected;
- provider error bodies are parsed only for a bounded error code and otherwise discarded;
- OAuth responses have a size limit.

Provider discovery is not implemented. Any future discovery path must pin issuer/metadata relationships and cannot silently widen these destination rules.

### T13 — Device-code verification phishing

Threat: a compromised device endpoint returns a malicious verification URL while NEXUS displays a legitimate-looking user code.

Controls:
- verification hosts have a distinct adapter-owned allowlist;
- user-info and fragments are rejected;
- the secret device code is neither displayed nor persisted;
- polling handles only the admitted RFC 8628 pending/slow-down contract and expires no later than the 30-minute client ceiling.

The displayed short user code is an ephemeral enrollment secret and should not be archived.

### T14 — Credential-store disclosure or substitution

Threat: another local user reads fallback bearer-token files, a symlink redirects writes, or malformed profile data changes the selected source/backend.

Controls:
- a usable OS keyring is preferred when the optional integration exists;
- a rejected keyring write falls back to the owner-only private-file store and is reported in the enrollment result;
- POSIX auth directories are created `0700` and must already be owner-only if present; files are written `0600` and checked on read;
- symbolic-link directory traversal and non-regular secret files are rejected;
- profile and secret schemas use exact field sets and explicit versions;
- identifiers are bounded before they become filenames;
- writes use same-directory temporary files plus atomic replacement.
- profile mutations and refresh-token rotation share an owner-only interprocess lock.

Residual risk: `private_file` is permission-protected, not encrypted from the same OS account. Full-disk encryption and an OS keyring are recommended.

### T15 — External credential helper abuse

Threat: a configured helper invokes a shell, accepts secrets in argv/stdin, hangs, emits arbitrary data, or leaks output into diagnostics.

Controls:
- helper execution requires an absolute executable path and uses an argv array with `shell=False`;
- stdin is disconnected;
- execution has a timeout;
- stderr is suppressed at the broker boundary;
- stdout must be bounded UTF-8 JSON with a closed token-field allowlist;
- credential-bearing argv options are rejected even when an opaque value evades format-based secret detection;
- helper output is transient and omitted from profiles/public results.

Residual risk: the helper is explicitly trusted operator code and inherits its configured environment. Raw tokens remain forbidden in helper argv, and helper admission/packaging is outside this PR.

### T16 — Auth status becomes Council authority

Threat: provider account tier, authentication method, keyring backend, remote availability, or discovered model list changes vote weight or epistemic privilege.

Controls:
- auth descriptors contain no vote-weight or privilege fields;
- auth state is operational and outside Council/world identity;
- `CouncilMember` still enforces `vote_weight = 1` and `epistemic_privilege = none`;
- provider integrations remain replaceable and must pass the same Equality Guard and Council coordinator.

## Explicitly out of scope for the auth-foundation PR

- provider-specific OAuth client registration and issuer/ID-token validation;
- OpenAI, Anthropic, Gemini, xAI, or other remote providers;
- reading or reusing another CLI's auth store, browser cookies, or consumer session tokens;
- protection of private-file bearer tokens from the same compromised OS account;
- arbitrary model-generated tool execution;
- remote Ollama endpoints in CI;
- strong sandboxing;
- claims of cryptographically sealed ballots;
- QEC-grade proof/replay semantics for live inference.

## Admission rule for later adapters

A new adapter may not gain Council authority by virtue of provider identity, deployment class, parameter count, benchmark rank, or claimed capability. It must satisfy the same actor contract and conformance tests, keep credentials outside semantic content, and document any new network/authentication threat introduced by that adapter.
