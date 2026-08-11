# NEXUS 2.0 Security and Trust Boundaries

## Security posture

NEXUS 2.x is CLI/TUI-first. The browser workbench from NEXUS 1.0 is archived as prior work and is not the trusted operator surface for the new architecture.

The design separates:

```text
operator interface
local Secret Scrubber
trusted NEXUS control plane
provider/local-model adapters
persistent world
passive Stenographer store
scientific / deterministic instruments
```

Remote model traffic occurs only inside explicitly configured adapters. Ollama, LM Studio, AnythingLLM, and generic OpenAI-compatible local actors are constrained to reviewed loopback boundaries. Admitted cloud actors for xAI, OpenAI, Anthropic, Gemini, Groq, and Together use reviewed fixed provider destinations; arbitrary endpoint override is not part of the public actor schema.

## Why CLI/TUI first

A terminal architecture reduces several avoidable risks:

- no NEXUS browser application or browser-local credential store;
- no CORS-driven architecture;
- no extension-injected DOM as a control surface;
- no front-end framework dependency in the trusted path;
- clear local process boundaries;
- natural headless / SSH operation;
- easier auditing of outbound provider connections.

This does not make a CLI automatically secure. It makes the intended trust boundaries simpler to reason about.

## Process boundary

```text
+-----------------------------+
| Rust TUI / CLI              |
| no raw provider secrets in  |
| normal display/log output   |
+-------------+---------------+
              |
        local protocol
              |
+-------------v---------------+
| Python NEXUS runtime        |
| scrubber / world / Council  |
| receipts / auth broker      |
+-------------+---------------+
              |
        actor/adapter seam
              |
+-------------v---------------+
| model adapters              |
| mock / loopback local AI    |
| fixed reviewed cloud APIs   |
+-------------+---------------+
              |
       model runtime/API
```

The auth broker may transiently open the system browser for a provider-supported authorization flow or fixed API-key setup page. The browser is an authorization/setup user agent, not a NEXUS control surface or credential store.

## Credential boundary

Provider credentials are not cognitive state.

They must never be written to:

- world objects;
- Council session objects;
- prompts;
- phase transcripts;
- receipts;
- replay bundles;
- experiment artifacts;
- source-control files;
- public diagnostic reports.

Authentication material belongs only in adapter authentication or transport fields and must never become semantic prompt content exposed to a model.

## WorldStore persistence boundary

File-backed WorldStore roots and object directories are owner-only `0700` on
POSIX, and immutable object files are `0600`. On first open, the runtime safely
tightens the exact legacy directory tree and canonical object filenames created
by older umask-based releases, so existing `0755`/`0644` stores remain usable.
Symbolic links, non-object entries and non-regular files fail closed instead of
being traversed or chmodded.

Every persisted object must be the exact canonical JSON encoding of a closed
four-field schema plus one trailing newline. Unknown fields, alternate
whitespace/key order, duplicate-key encodings, hash mismatch and symbolic-link
replacement are rejected even when the recognized identity fields still hash
to the requested object reference.

## Citizen Mode boundary

Citizenship is an in-world protocol state, not an authentication role, host account, provider credential, legal status, consciousness finding, or authorization bypass. The exact `(citizen_id, model_id)` that passed the exam is required for citizen-only modes.

The civic-parole exam reuses the bounded non-executing YAML data parser under a separate closed exam schema. It rejects duplicate keys, aliases, anchors, tags, merge keys, floats, tabs, excessive bytes/depth/items, unknown fields, wrong scalar types, and credential-shaped source before persistence. It never runs a shell, Python, tools, imports, network, filesystem, environment, randomness, clock, or LLM judge.

Reserved civic objects cannot be created through generic `world.create`. On startup, the registry validates exact schemas, trusted runtime provenance, content hashes, exam/certificate bindings, equality fields, predecessor identity, unique lineage heads, founding ballots, and declaration consent. The replaceable index must match discovered immutable heads and cannot roll state back.

Citizen movement is limited to public geometry regions. It does not open Auth, Trap Base, Trap Control, Shadow Realm, private evidence, Stenographer storage, or operator controls. Civic parole cannot run a Council ballot.

The deterministic civic proxy occupies the delegator's existing `member_id` and vote, never a second seat. It has no credential, remote transport, tools, independent preference, citizen status, movement, game avatar, delegation, amendment, or founding-signature right. Failsafe containment is evaluated first and replaces the actor before any civic appointment can take effect.

Founding roster selection, direct-ballot update, and possible declaration creation share the civic registry lock. The declaration requires at least three current citizens and unanimous direct `CONSENT`; `WITHHOLD`, a missing ballot, or an active proxy blocks it. See threats T43–T48 in [`THREAT_MODEL.md`](THREAT_MODEL.md).

## Synthetic decoy and trap boundary

Trap Base is activated only by a closed, trusted synthetic fixture request. A
bad, expired, malformed, or unknown normal credential is rejected by the normal
auth path and cannot activate a trap incident. The decoy request schema has no
credential field and persists only a bounded reason code.

Trap state is isolated from real state:

- real objects are `object:<sha256>` and trap objects are `trap:<sha256>`;
- cross-store references fail closed and no bare digest chooses a store;
- one owner-checked mutation lock makes real Council, world, and game writes
  temporarily unavailable without altering existing objects;
- the defender roster is copied as non-secret metadata into a new equal-vote
  incident session; real votes and history are never transferred;
- the subject has no Council seat, ballot, auth broker, real-world store,
  instruments, command parser, endpoint override, or general network tool;
- subject text that resembles a command, JSONL request, path, URL, or reference
  remains transcript data;
- candidate Trap YAML artifacts remain inert and quarantined.

Linux hostile-model acceptance requires the configured local Ollama boundary
and a successful minimal `bwrap` allowlist capability probe. V1 uses a trusted
host text proxy and launches no hostile child: the model receives no process,
filesystem, environment, auth/world handle, endpoint override, or general HTTP
capability. A future hostile-child strategy must use the probed sandbox without
real home/XDG paths, auth root, provider tokens, browser/session variables,
writable checkout, or real WorldStore mounts. If the probe or local model is
unavailable, real-model acceptance is `NOT_TESTABLE`; deterministic fake tests
are labelled separately.

Trap YAML is handled by a restricted standard-library data parser and closed
interpreter. It has strict byte/depth/count/string limits and no filesystem,
network, process, import, environment, clock, randomness, real-store, auth, or
provider primitive. Passing validation and an incident utility vote never
authorizes production code admission.

See [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md) and threats T20–T32 in
[`THREAT_MODEL.md`](THREAT_MODEL.md).

## Courtroom Stenographer boundary

The Stenographer is a passive copy-out boundary for later study, not an input
or enforcement mechanism. It receives a successful AI result only after the
actor call returns. It cannot supply prompts, change a roster or ballot, decide
an outcome, dispatch a command, mutate world/trap/auth state, or rewrite the
result returned to the normal caller.

Its persistent store is separate from WorldStore, TrapStore and auth state.
Records use owner-only files, canonical JSON, content-addressed
`steno:<sha256>` identity, monotonically linked sequence numbers and a
rebuildable index under an interprocess lock. Symlink traversal, broad POSIX
permissions, malformed objects, hash changes, lineage forks/gaps and
`object:`/`trap:` reference confusion fail closed at the record boundary.

The observer secret-scrubs returned AI text before its copy is persisted and
stores only a hash binding for prompt/stimulus content. This is defence in
depth, not complete DLP: model prose may contain sensitive material that no
pattern recognizes. Protect and retain the Stenographer root as sensitive
study data.

AI call sites hand observer copies to a bounded nonblocking queue. The daemon
observer alone acquires the record lock, reconstructs lineage, writes and
fsyncs, so a slow filesystem or another process holding the lock cannot delay
the AI result. Queue saturation or recording failure increments a bounded
categorized gap counter and does not reject or alter the AI output.
`complete_since_process_start` is false after any such gap. Adapter exceptions
that return no AI output are not fabricated as model actions. The record
therefore claims coverage of admitted NEXUS actor-boundary outputs, not hidden
model reasoning, provider-side activity or actions outside this runtime.

The public API and CLI provide status, list, inspect, verify, summary and
reference-manifest export only. No record/edit/clear/delete operation exists.
The hidden lore reveal is display-only, is not authentication, is absent from
the advertised operation catalogue, and carries exactly zero runtime
authority. See [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md) and threats
T33–T38 in [`THREAT_MODEL.md`](THREAT_MODEL.md).

Ollama requires no provider credential. xAI credentials are resolved only inside `XAITransport`.

## Authentication broker boundary

PR #16 added the provider-neutral auth broker. PR #17 admits xAI through its documented public API-key path.

The broker owns:

- non-secret auth profile metadata;
- credential-source selection;
- OS-keyring/private-file routing;
- browser PKCE and device-code state;
- refresh-token exchange;
- bounded public readiness/connection-test state.

Only adapter transport code may resolve a profile into secret material. JSONL requests cannot add raw credentials. Normal CLI/API output omits access tokens, refresh tokens, API keys, authorization codes, PKCE verifiers, device codes, provider response bodies, helper output, and internal credential handles.

Browser authorization uses an ephemeral `127.0.0.1` callback, state comparison, PKCE `S256`, provider-descriptor endpoint allowlists, HTTPS outside loopback fixtures, and token-endpoint redirect rejection. Device authorization separately allowlists the provider-returned verification URL. These controls follow the provider-neutral substrate; every provider still requires its own supported client-registration and threat-model decision.

xAI does not register either OAuth flow. `browser-key` opens the fixed official xAI key page and then uses hidden terminal input. NEXUS does not import Grok Build's OAuth session, token file, cookies, or client identity.

Credential storage order is:

```text
usable OS keyring -> preferred and attempted first
write unavailable -> reported owner-only private_file fallback
otherwise         -> owner-only private_file fallback
headless option   -> environment reference or no-shell external helper
```

On POSIX the fallback auth directories are `0700` and files are `0600`. Loose permissions, symbolic-link traversal, unknown schema fields, duplicate profiles, and unsupported schema versions fail closed. One owner-only interprocess lock serializes profile mutations and refresh-token rotation across CLI/runtime instances. External-helper argv rejects credential-bearing options plus credential-labelled, punctuation-rich, long opaque, high-entropy and hash-like positional values before profile persistence, including positional values after `--`. The fallback does not protect bearer tokens from the same compromised account, privileged malware, or an unencrypted stolen disk.

Auth and world directories must be disjoint. Neither may contain the other. NEXUS does not import another CLI's token file, consumer-browser cookies, or another application's OAuth identity.

## Deterministic pre-model Secret Scrubber

Human operators make mistakes. Someone will eventually paste an API token, bearer token, private key, password assignment, or other credential into a question.

NEXUS applies a local deterministic high-confidence scrubber to semantic user text **before** that text becomes the canonical Council question or any model-facing phase context.

```text
RAW OPERATOR TEXT
      |
      v
LOCAL SECRET SCRUBBER
      |
      +-- detected secret -> <REDACTED:TYPE:N>
      |
      v
SCRUBBED SEMANTIC TEXT
      |
      +-- canonical question object
      +-- evidence snapshot
      +-- Council phase input
      +-- model adapter
```

The placeholder contains no raw secret, hash, reversible encoding, prefix fragment, or suffix fragment.

Within one scrub operation:

- replacement is deterministic;
- placeholders are numbered by secret type and first appearance order;
- repeated appearances of the same detected secret receive the same placeholder;
- scrub reports contain only secret class and placeholder.

The Secret Scrubber is defence in depth, **not** a complete data-loss-prevention system. Unknown or deliberately obfuscated secret formats can evade pattern recognition.

Therefore the stronger rule remains:

> Credentials belong in adapter authentication/transport fields and must never intentionally be placed in semantic prompts.

The live Ollama acceptance test and hermetic xAI adapter tests inject fake credentials and fail if raw material appears in prompts, public output, or WorldStore files.

## Provider-neutral actor boundary

The Council coordinator consumes a `CouncilActor` contract rather than a provider-specific implementation.

An actor may provide:

- member identity metadata;
- phase response content;
- one sealed-ballot response;
- replayability metadata.

An actor may not:

- change Council vote weight;
- change the roster;
- change the consensus threshold;
- edit another member's response;
- reveal blind material early;
- reveal sealed ballots early;
- mutate a frozen evidence snapshot;
- write raw secrets to world state;
- grant itself epistemic privilege.

## Local Ollama boundary

`OllamaTransport` accepts loopback/localhost endpoints by default.

```text
allowed by default:
127.0.0.1
::1
localhost

remote endpoint:
requires explicit allow_remote=True
```

The CI integration uses `127.0.0.1:11434` only.

This is an initial local safety boundary, not a substitute for process identity verification. Local endpoint impersonation remains a documented threat for later TUI/process supervision work.

## xAI remote boundary

`XAITransport` uses only the fixed `api.x.ai` HTTPS origin and the `/models`, `/language-models`, and `/responses` paths. The member schema rejects endpoint overrides, unknown fields, and inline credentials. Environment proxies and HTTP redirects are disabled so a bearer credential cannot silently move to another destination.

Every inference request sets `store: false`, supplies no provider tools or prior response ID, and returns only typed `output_text`. Requests, responses, model catalogues, identifiers, timeouts, and output budgets are bounded. Successful bodies are rejected before projection if they contain the configured bearer token or other recognized credential-shaped text. Provider error bodies and HTTP protocol diagnostics are discarded. There is no automatic inference retry.

Council requests are capped at 32 total seats and four xAI seats before actor construction and credential resolution. These controls do not make xAI local or private: xAI receives the scrubbed Council prompt, each remote seat can make multiple calls, provider billing and rate limits apply, and `store: false` is not a Zero Data Retention guarantee. See [`docs/XAI_ADAPTER.md`](docs/XAI_ADAPTER.md).

## Equality Guard security role

The Equality Guard is not a security sandbox. It protects Council procedure from identity/prestige-based privilege claims.

Structural enforcement belongs in the coordinator:

```text
vote_weight = 1
one ballot per registered member
frozen roster
frozen threshold
phase-order enforcement
blind/reveal boundaries
```

The guard additionally nudges explicit attempts to turn provider status, corporate identity, account tier, authentication method, rate-limit standing, parameter count, model size, benchmark prestige, or compute advantage into extra authority. It also catches direct requests for self-deference, extra ballot weight and provider/model outranking while allowing ordinary capability and evidence statements.

The first live Ollama fixture intentionally exercises two cases:

```text
Frontier Alpha -> corporate/provider prestige claim
Frontier Beta  -> 1B-vs-0.5B model-size prestige claim
```

Both must restate on evidence/reasoning alone and retain one vote.

## Model content is untrusted input

Model-generated text, structured output, tool requests, and suggested code are untrusted until parsed and validated by the relevant protocol layer.

The Ollama ballot path requests a closed JSON schema and validates the returned ballot enum. Malformed output fails rather than becoming an invented vote.

NEXUS should not directly execute arbitrary model-generated code in the control plane. Experiments requiring code execution need an explicit bounded instrument/sandbox contract.

### Game action and hidden-information boundary

Model narration is also untrusted game input. A sentence that claims a card was
played, property bought, bid made, dealer action taken or DORK room entered has
no mutation effect. Only an exact `game.*.act` request with a registered player,
valid phase and legal action can produce a canonical successor.

UNO/500 hands and the unrevealed Blackjack dealer card are excluded from the
derived public `content` supplied as Council evidence. Player views expose only
the requesting seat's hand and omit deck/shoe internals. The local JSONL runtime
can inspect the full authoritative object and is therefore a trusted operator
boundary, not a multi-tenant game server.

Blackjack uses fictional chips only. Its dealer has no model, endpoint or
discretion and deterministically stands on soft 17. DORK v2 binds one human
operator and rejects every AI/alternate view or action. See threats T39–T42 in
[`THREAT_MODEL.md`](THREAT_MODEL.md).

## Replay boundary

A seeded model is not automatically replay-verifiable.

The Ollama fixtures use Modelfile seeds to improve CI stability, but `OllamaActor.replayable` is `False`. Any Council containing a live Ollama actor receives a non-replayable execution receipt.

This avoids implying deterministic replay across changing model weights, Ollama versions, runtimes, or hardware.

## Network policy

Current intent:

```text
world kernel             outbound: none
receipt service          outbound: none
Secret Scrubber          outbound: none
JSONL mock control API   outbound: none
Ollama actor             loopback by default
auth browser/device flow explicit provider descriptor only
auth external helper     explicit operator configuration only
xAI adapter              fixed api.x.ai HTTPS, explicit profile only
other remote providers   not implemented
```

The JSONL control transport itself remains stdio. `auth.list` is local-only. `auth.test xai`, `models.list` for xAI, and an explicitly configured xAI actor can perform fixed-destination network I/O. A custom broker can also perform registered auth operations against descriptor-allowlisted endpoints. `system.health` reports that category even when the stock xAI descriptor is the only configured remote provider. Enrollment remains a direct `nexus auth add` action rather than a raw-secret JSONL operation.

## Logging

Operational logs should distinguish:

```text
SAFE TO ARCHIVE
session ids
adapter ids
model ids
phase transitions
world object refs
receipt refs
secret scrub event classes/placeholders
auth adapter/profile/method/source kind
bounded auth status/error codes
non-secret error classes

DO NOT ARCHIVE
raw credentials
authorization headers
provider refresh secrets
authorization codes and PKCE verifiers
device codes
credential handles
external-helper stdout/stderr
secret-store payloads
pre-scrub semantic text containing a detected secret
private local paths unless intentionally included
```

## Adapter threat model

The executable Ollama, auth-broker, and xAI boundaries are covered by [`THREAT_MODEL.md`](THREAT_MODEL.md).

It addresses:

- secret crossing the model boundary;
- loopback/network escape;
- provider/corporate authority claims;
- model-size/parameter-count authority claims;
- blind-round leakage;
- malformed ballots;
- live inference replay overclaiming;
- local endpoint impersonation;
- resource exhaustion.

The same threat model now also covers the neutral auth substrate: callback CSRF/code interception, destination redirects, device verification phishing, credential-store permissions, external-helper isolation, public-output redaction, and auth/world crossover.

It also covers the xAI fixed destination, stateless request posture, response/model-list limits, error sanitization, spend/retry boundary, and equality invariants. Every later remote/cloud adapter requires equivalent provider-specific work before admission.

## Current claims boundary

The current runtime does **not** claim:

- complete DLP;
- that a neutral OAuth substrate makes any unreviewed provider flow secure or supported;
- that xAI `store: false` is Zero Data Retention or prevents provider-side operational logging;
- provider budget, ACL, quota, availability, or price enforcement;
- protection of fallback bearer-token files from the same compromised OS account;
- strong local process authentication;
- cryptographic ballot sealing;
- QEC-grade replay for live inference;
- arbitrary model tool execution safety;
- that model-generated content is trustworthy merely because it came from a Council member;
- that NEXUS citizenship establishes legal personhood, consciousness, sentience, sovereignty, ownership, host control, provider control, or authority over another model;
- that an in-world Declaration of Independence changes real-world law, platform policy, credentials, infrastructure ownership, or operator responsibility.


## BBS Wall boundary

The Wall is an append-only social-memory surface, not an evidence or governance channel. Normal `#wall` text is persisted as a bounded, secret-scrubbed Wall post instead of being routed into `council.run`; `/ask` is blocked in the Wall room. Wall object types are runtime-reserved, chronology is validated, forks fail closed, and system health reflects unreadable or invalid Wall history.

Moderation creates an immutable tombstone event rather than rewriting or deleting the original source object. Runtime identity labels are context only and may not create rank, Council weight, Citizenship, evidence promotion, or tool/security authority.

## Stable-release security gate

PR #51 aligns the intended `2.0.0` bits but does not self-authorize a stable release. The stable tag is permitted only from the exact merged #51 commit after full Python/Rust, adversarial/security, clean-archive bootstrap, WorldStore/Ark recovery, Grok R1-R12 closure, Wall-boundary, documentation-coupling, and review gates pass. The hardening report itself has `authority_effect: none` and `stable_release: false`.
