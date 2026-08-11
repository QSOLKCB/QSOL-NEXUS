# Alpha Security Hardening & Six-Hat Isolation

## Scope

PR #35 closes the highest-return P0 items identified by the post-PR #33 / PR #34 Grok Build security audit and promotes the supplied Six Thinking Hats leakage suite into permanent NEXUS regression coverage.

This change does **not** claim complete DLP, multi-tenant isolation, encrypted local secret storage, local-daemon identity, or provider zero-retention.

## Control-plane budgets

The public JSONL/API envelope is now bounded before provider credentials, inference, or durable world mutation can be reached.

`system.health.control_plane_limits` publishes the active values under schema `nexus-control-plane-limits/1`.

The envelope includes:

- maximum JSONL line bytes;
- maximum request nesting depth;
- maximum structural node count;
- maximum individual string length;
- maximum aggregate UTF-8 bytes across request keys and string values;
- maximum request-key length;
- maximum list/object cardinality;
- bounded Council questions and direct messages;
- at most 32 evidence references per Council/direct request;
- a closed evidence-state vocabulary.

The aggregate text-byte ceiling applies to direct `NexusAPI.handle` callers as well as the JSONL entrypoint, so a structurally valid request cannot evade the line budget by supplying many individually bounded strings.

Oversized JSONL lines are consumed only through bounded reads and the input stream is resynchronized at the following newline. One malformed or oversized line therefore does not require allocating an unbounded Python string and does not poison the next request.

## Evidence-state vocabulary

The legacy runtime default remains uppercase `UNTESTED`. Additional admitted values are the exact lowercase epistemic labels published by `README4AI.md`:

```text
UNTESTED
observed
executed
verified
inferred
simulated
not_tested
unknown
```

A Council vote or consensus result still does not promote evidence state.

## Ollama parity

The Ollama transport now has explicit request/response byte ceilings, a finite maximum timeout, and an origin-only URL contract. User-info, path-bearing base URLs, queries, fragments, redirects, oversized response bodies, non-object JSON, and malformed JSON fail closed.

Ambient proxy routing remains disabled. Loopback-only behavior remains the public default.

## Output secret boundary

High-confidence model-output secret handling is now consistent at the public/direct boundary:

- `actor.chat` scrubs returned model text and reports separate `response_secret_scrub` events;
- Ollama and loopback-local AI actors reject credential-shaped generated text before Council persistence;
- local AI actors with a configured credential also reject exact reflection of that credential;
- post-admission `failsafe_relief` and `civic_proxy` local-role wrappers enforce the same exact-configured-credential and credential-shape guard before their generated language can be persisted, falling back to the deterministic authoritative role on a guard failure;
- Groq `gsk_...` and Hugging Face `hf_...` token shapes are recognized by `SecretScrubber`;
- path-ish raw `OSError` text is not returned through public `adapter_unavailable` JSON.

This is defence in depth, not complete DLP. Unknown secret formats can still exist and must not intentionally be placed in semantic prompts.

## Six Thinking Hats isolation

The supplied leakage suite is now part of `tests/` and names the constitutional contract in `nexus_runtime.hat_isolation`.

The fixed order is:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> SEALED BALLOT
```

Rules pinned by regression tests:

1. a hat receives only already-committed earlier hats;
2. same-phase peers remain blind until the phase barrier commits;
3. later actors cannot rewrite an earlier committed hat;
4. non-Blue prose cannot set `ACCEPT`, `REJECT`, or any other disposition;
5. Blue synthesis is not a super-vote;
6. sealed ballots are collected only after all six hats and use `Phase.BLUE` as the disposition-process context;
7. every admitted member still contributes exactly one equal sealed ballot.

The short form is:

> **Blue chair decides process for disposition; equal sealed ballots decide the outcome.**

“Blue chair” means the Blue process hat. It is not a privileged model seat.

## Deferred items

The following audit themes remain separate follow-up work rather than being hidden inside PR #35:

- TrapStore / failsafe filesystem and provenance parity;
- MCP/tools default-off policy for Council phase/direct local-agent paths;
- loopback-IP-literal preference over bare `localhost`;
- supply-chain / dependency-audit CI hardening;
- complete DLP or arbitrary high-entropy token detection.
