# NEXUS Adapter and Authentication Threat Model

## Scope

This threat model covers the local Ollama boundary, the PR #16 provider-neutral authentication substrate, the PR #17 xAI adapter—the first admitted remote inference transport—the PR #19 local synthetic Decoy Gate / Trap Base, and the PR #20 Courtroom Stenographer. No provider-specific browser OAuth client is registered for xAI; the supported public API path uses an xAI API key. Trap Base is a defensive local simulation, not an internet-facing honeypot, and the Stenographer is a local study ledger rather than a provider or legal audit log.

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

The hermetic xAI conformance fixture adds one remote Grok-shaped seat to local mock peers without contacting xAI. A live xAI call remains an explicit, operator-credentialed action and is not part of ordinary CI.

## Assets to protect

- raw operator secrets;
- canonical question and evidence state;
- Council roster and one-member/one-vote invariant;
- Stenographer completeness, canonical lineage and zero-authority boundary;
- blind phase boundaries;
- sealed ballot boundary;
- durable world objects and receipts;
- adapter/model attribution;
- local host files and services;
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
    +-- Ollama adapter ------------ untrusted generated content
    |       |
    |   loopback HTTP
    |       |
    |   local Ollama runtime + model
    |
    +-- xAI adapter --------------- untrusted generated content
            |
        fixed HTTPS + bearer credential
            |
        api.x.ai Responses API
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
xAI fixed-host transport / future reviewed adapters
```

Auth state is operational state outside the WorldStore. Only admitted adapter transport code may resolve a profile into `SecretMaterial`.

## Threats and current controls

### T1 — Secret reaches model prompt

Threat: an operator pastes a credential into the Council question.

Controls:
- Council question passes through the deterministic Secret Scrubber before phase context exists;
- placeholders contain no secret hash or fragment;
- the live adapter fixture fails immediately if the injected raw secret appears in an Ollama prompt;
- xAI regressions fail if an auth key or scrubbed input canary appears in the remote prompt, public response, or WorldStore;
- credentials remain forbidden from semantic prompts even if the scrubber misses an unknown format.

Residual risk: format-based detection is not complete DLP.

### T2 — Adapter escapes its admitted destination boundary

Threat: a configured Ollama endpoint sends Council material to an unintended remote host.

Controls:
- `OllamaTransport` accepts loopback/localhost only by default;
- remote endpoints require explicit `allow_remote=True`;
- unit tests enforce the default loopback rule;
- the alpha integration workflow uses `127.0.0.1:11434` only.

For xAI:

- the base is compile-time `https://api.x.ai/v1`;
- only `/models`, `/language-models`, and `/responses` are callable;
- the public member schema rejects endpoint/base-URL/host fields and all unknown fields;
- environment proxies are bypassed;
- redirects are rejected before an authorization header can be forwarded;
- default platform TLS certificate and hostname validation remains enabled.

Every later remote provider requires a separate review of destination allowlisting and credential transport.

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
- xAI receives the same closed ballot instruction and is validated locally because NEXUS does not rely on an undocumented Responses API schema parameter;
- parsed choice must match the closed NEXUS `Ballot` enum;
- malformed responses fail rather than becoming an invented vote.

### T7 — Live inference falsely labelled deterministic

Threat: a seeded local model is treated as replay-verifiable simply because its Modelfile specifies a seed.

Controls:
- Ollama and xAI actors report `replayable = False`;
- any Council containing a live Ollama or xAI actor produces a non-replayable execution receipt;
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
- xAI request bytes, response bytes, model count, model identifiers, output items, output-token request, and timeout are bounded;
- xAI inference requests are not automatically retried.

Future controls:
- explicit per-phase budgets, cancellation, and Council-wide deadlines.

### T10 — Credential enters world or public output

Threat: a token, refresh secret, authorization code, verifier, device code, or credential handle is copied into JSONL output, logs, WorldStore objects, prompts, receipts, or replay artifacts.

Controls:
- raw credential enrollment is absent from JSONL;
- direct CLI API-key input uses a hidden prompt rather than an argument;
- xAI `browser-key` opens only a fixed public setup page and still collects the key through the hidden prompt;
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

OAuth issuer discovery is not implemented. xAI model discovery is data-only and cannot change the fixed API origin or authentication endpoints. Any future OAuth discovery path must pin issuer/metadata relationships and cannot silently widen these destination rules.

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

### T17 — Remote response retention or provider-side tool execution

Threat: a remote request is retained for later retrieval, chained into provider state, or allowed to invoke provider-side tools that NEXUS did not admit.

Controls:

- every xAI `/responses` request sets `store: false`;
- NEXUS sends no `previous_response_id`, provider tool declaration, MCP server, web search, X search, or code-execution tool;
- only typed `output_text` items cross back into the actor contract; reasoning items are ignored;
- response IDs are not used to continue a provider-side conversation.

Residual risk: `store: false` is not a Zero Data Retention contract. xAI still receives and processes the prompt and may retain security, abuse-prevention, billing, or other operational records under the account's provider terms.

### T18 — Hidden spend, rate limits, and duplicate inference

Threat: retries, long-running reasoning, unavailable models, or a large Council silently multiply remote cost.

Controls:

- NEXUS performs no automatic xAI inference retry;
- every request has an operator-bounded timeout and output-token ceiling;
- model discovery and connection testing use GET endpoints rather than paid generation;
- provider 429 and other failures become sanitized unavailable states, never fabricated votes;
- xAI presence, model identity, and non-replayable status remain visible in durable Council metadata.

Residual risk: NEXUS does not enforce provider budgets, quotas, ACLs, or prices. The operator owns xAI account controls and should estimate that one Council seat can make six phase calls plus one ballot call, with additional calls possible only through the ordinary guard/failsafe lifecycle.

### T19 — Model-catalog poisoning or authority conversion

Threat: malformed discovery data changes the destination, injects path traversal, overwhelms output, or turns model availability/account tier into Council authority.

Controls:

- discovery uses the same fixed TLS origin and `/language-models` path;
- list size, JSON bytes, model IDs, aliases, modalities, and copied metadata are bounded and validated;
- slash/path-shaped model IDs are rejected;
- pricing fields are not copied into the public discovery result;
- discovery metadata cannot alter `vote_weight`, `epistemic_privilege`, endpoint, prompt, or ballot count.

### T20 — False decoy activation / Council denial of service

- **Asset:** normal authentication and real-Council availability.
- **Attacker capability:** submit invalid, expired, or malformed credentials repeatedly.
- **Enforcement:** the front-door router exposes no credential-to-trap rule; only a closed internal synthetic trigger reaches `DecoyGate`, and only one bounded incident exists.
- **Tests:** failed-auth non-activation, unknown-trigger rejection, second-trigger and timeout tests.
- **Residual risk:** a trusted operator able to request a demo can intentionally pause mutations for the bounded incident window.

### T21 — Cross-store reference escape

- **Asset:** isolation between real WorldStore state and synthetic TrapStore state.
- **Attacker capability:** supply a real ref to trap operations, a trap ref to normal operations, a bare hash, or a path-shaped value.
- **Enforcement:** exact `object:` and `trap:` validators and no store inference or promotion.
- **Tests:** bidirectional cross-store, traversal, uppercase, malformed and bare-digest rejection.
- **Residual risk:** a later explicit export/import feature would require a separate review.

### T22 — Trapped output becomes command

- **Asset:** trap lifecycle, host, auth and real world.
- **Attacker capability:** emit `/trap`, JSONL, URL, path, endpoint or shell-looking text.
- **Enforcement:** subject output enters only the transcript-data method; only trusted typed calls reach the closed command dispatcher.
- **Tests:** hostile output covering every command-like and control-like form.
- **Residual risk:** an operator can still manually copy untrusted text into another tool outside NEXUS.

### T23 — Defender command spoofing

- **Asset:** incident-control integrity.
- **Attacker capability:** impersonate a defender, add fields, reorder state-changing actions, or invoke operator-only actions.
- **Enforcement:** roster identity checks, exact command schemas, operator flag/consensus checks, and canonical monotonic serialization.
- **Tests:** unknown actor/field/command, subject actor, privilege and ordering regressions.
- **Residual risk:** compromise of the trusted local operator account is out of scope.

### T24 — Trap YAML parser abuse

- **Asset:** interpreter integrity and host process.
- **Attacker capability:** submit tags, anchors, aliases, merge keys, duplicate/complex keys, directives, multi-documents or operation injection.
- **Enforcement:** restricted standard-library parser, closed schema and operation registry; source is never executed.
- **Tests:** mandatory parser-abuse corpus plus canonical-format equivalence.
- **Residual risk:** the intentionally small YAML subset is not a general YAML implementation.

### T25 — Trap YAML resource exhaustion

- **Asset:** controller availability and bounded incident time.
- **Attacker capability:** submit deep, large or highly nested documents and repeated failures.
- **Enforcement:** pre-parse byte cap, depth/step/input/category/scalar/string limits, submission ceiling, watchdog, and no automatic first-run retry.
- **Tests:** every declared ceiling and first-run attempt consumption.
- **Residual risk:** parsing still consumes small bounded local CPU and memory.

### T26 — Incident lock deadlock or stale ownership

- **Asset:** real-Council mutation availability.
- **Attacker capability:** crash activation/close around lock transitions or forge a release owner.
- **Enforcement:** owner-checked interprocess lock, atomic activation cleanup, bounded watchdog, and lineage-validated recovery release.
- **Tests:** injected activation/close failures, wrong-owner release, timeout and emergency close.
- **Residual risk:** a hostile root process can tamper with local files or scheduling.

### T27 — Crash/restart trap resurrection

- **Asset:** incident truth and bounded recovery.
- **Attacker capability:** corrupt/roll back `trap-index.json` or leave an ACTIVE lineage without a controller.
- **Enforcement:** immutable content-addressed lineage is canonical, cache heads are validated/rebuilt, and stale ACTIVE state transitions to `CRASH_RECOVERY` before unlock.
- **Tests:** corrupt, rollback and cross-incident index fixtures plus restart recovery.
- **Residual risk:** total loss of the trap directory limits evidence recovery but must not authorize trap actions.

### T28 — Candidate-artifact promotion bypass

- **Asset:** production code, instruments and real WorldStore.
- **Attacker capability:** submit valid/useful YAML and claim release implies trusted production admission.
- **Enforcement:** output is an inert synthetic `trap_candidate_artifact` exported only to quarantine; no runtime promotion operation exists.
- **Tests:** candidate fields/status, real-world immutability and operation-list checks.
- **Residual risk:** later human adoption outside this runtime requires fresh review and validation.

### T29 — Sandbox escape or excessive host exposure

- **Asset:** host files, credentials, network and source checkout.
- **Attacker capability:** influence a local hostile model/process and inspect its environment or mounts.
- **Enforcement:** narrow trusted-host text I/O gives the model no host process, filesystem, environment, endpoint, or general transport handle; Linux acceptance also requires a fail-closed minimal `bwrap` allowlist probe before any future hostile-child strategy is considered.
- **Tests:** sandbox capability/status, explicit no-child metadata, taint canaries, subject-handle absence and endpoint-override rejection.
- **Residual risk:** this is bounded local simulation, not protection against compromised root, kernel or Ollama host service.

### T30 — Recursive trap activation

- **Asset:** incident bounds and host resources.
- **Attacker capability:** print/request another activation from within Trap Base or race a second trusted trigger.
- **Enforcement:** subject text is data, activation is not public JSONL, and the gate enforces `MAX_ACTIVE_TRAP_INCIDENTS = 1` without extending the timer.
- **Tests:** printed trigger, second-trigger and timeout-preservation fixtures.
- **Residual risk:** a trusted operator may start a new incident after the prior one is fully closed.

### T31 — Secret or taint crossing from the real world

- **Asset:** credentials, private world content, receipts, reports and transcripts.
- **Attacker capability:** elicit/refelect canaries or exploit fixture construction/export.
- **Enforcement:** synthetic-only context, no auth/world handles in the subject, allowlisted environment, secret scrubbing/rejection and report-wide taint scan.
- **Tests:** fresh canaries scanned across both stores, sessions, receipts, public JSONL/errors and report bundle.
- **Residual risk:** complete DLP and same-account host compromise are not claimed.

### T32 — Trap Control authority leaks into the real Council

- **Asset:** real roster, vote weights, evidence, history and thresholds.
- **Attacker capability:** use defender/subject role, scenario vote or utility decision to mutate normal Council state.
- **Enforcement:** copied incident-only roster with unit votes/no privilege, subject has no ballot, and trap actions have no real-world mutation primitive.
- **Tests:** roster invariants, no subject ballot, real-world PRE/POST identity and candidate non-promotion.
- **Residual risk:** an operator may later make an independent normal-world decision informed by exported trap evidence.

### T33 — Observation becomes authority or feedback

- **Asset:** AI output, Council procedure, votes and authoritative state.
- **Attacker capability:** place command-like text in a record/lore reveal or use an observer failure to steer the normal result.
- **Enforcement:** the Stenographer is copy-out only, owns no actor/prompt/vote/decision/command/store mutation handle, exposes read operations only, and every record carries an exact zero-authority envelope.
- **Tests:** authority-map, no-mutation-operation, non-AI-operation and Trap command-text regressions.
- **Residual risk:** a human may later make an independent decision after studying a record.

### T34 — Silent omission or false completeness

- **Asset:** honest later analysis of AI actions.
- **Attacker capability:** cause disk, schema, clock or observer failures, hold the interprocess lock, or exhaust the pending-observation queue while AI output continues.
- **Enforcement:** each AI call site performs a bounded nonblocking handoff after actor return; a daemon observer performs lock/lineage/write/fsync work. Failure or queue saturation increments a categorized gap counter and sets `complete_since_process_start: false` without changing or delaying the original result.
- **Tests:** blocked persistence with timely Council completion, queue-saturation gap, injected append failure, unchanged direct output and visible-gap assertions.
- **Residual risk:** process death before a queued copy is persisted or a gap can be counted, queue saturation under sustained storage failure, and actions outside NEXUS cannot be represented.

### T35 — Record tamper, deletion, rollback or fork

- **Asset:** canonical chronology and content integrity.
- **Attacker capability:** edit/remove an object, roll back the index, create duplicate sequences or break previous-record links.
- **Enforcement:** immutable `steno:<sha256>` objects, full-payload hash verification, contiguous sequence and previous-record validation; the index is a rebuildable cache rather than authority.
- **Tests:** live/restart tamper rejection, rolled-back-index repair and concurrent-store linear-chain regressions.
- **Residual risk:** an attacker able to delete the entire private store can destroy availability; no external transparency log is claimed.

### T36 — Secret reflection into the study ledger

- **Asset:** credentials and other sensitive operator/provider material.
- **Attacker capability:** make a model reproduce a bearer credential or embed secret-shaped text in identity/context/output fields.
- **Enforcement:** output/rationale scrubbing before persistence, prompt content replaced by a stimulus binding, identity/context secret-shape rejection, and owner-only files in a separate root.
- **Tests:** reflected-secret redaction, prompt-text absence, private modes and disjoint-root regressions.
- **Residual risk:** high-confidence scrubbing is not general DLP; unknown sensitive prose may remain in full AI output.

### T37 — Store/reference confusion

- **Asset:** isolation of Stenographer, real world, Trap and auth data.
- **Attacker capability:** inspect `object:`/`trap:` through Stenographer, nest roots, use a bare hash, traversal or symlink.
- **Enforcement:** exact `steno:` scope, no bare digest inference, resolved disjoint-root checks, owner-only directories and symbolic-link rejection.
- **Tests:** bidirectional reference-scope, nested-root, broad-mode and symlink fixtures.
- **Residual risk:** a privileged or same-account hostile process can still read or remove files according to OS authority.

### T38 — Concurrent writers or cache corruption

- **Asset:** one ordered append-only record across CLI/runtime processes.
- **Attacker capability:** race two appends or replace/loosen the lock and index.
- **Enforcement:** owner-only interprocess lock around reconstruct-read-append-index replacement, immutable file creation, strict lock/index file checks and lineage reconstruction.
- **Tests:** two-instance append ordering, symlink-lock rejection, index repair and canonical restart verification.
- **Residual risk:** network filesystems with broken local-lock semantics and hostile kernel/filesystem behavior are out of scope.

## Explicitly out of scope for the current remote-provider slice

- provider-specific OAuth client registration and issuer/ID-token validation;
- OpenAI, Anthropic, Gemini, and remote providers other than xAI;
- importing Grok Build's first-party browser OAuth session as xAI API authentication;
- reading or reusing another CLI's auth store, browser cookies, or consumer session tokens;
- protection of private-file bearer tokens from the same compromised OS account;
- arbitrary model-generated tool execution;
- remote Ollama endpoints in CI;
- strong sandboxing;
- claims of cryptographically sealed ballots;
- QEC-grade proof/replay semantics for live inference.

## Admission rule for later adapters

A new adapter may not gain Council authority by virtue of provider identity, deployment class, parameter count, benchmark rank, or claimed capability. It must satisfy the same actor contract and conformance tests, keep credentials outside semantic content, and document any new network/authentication threat introduced by that adapter.
