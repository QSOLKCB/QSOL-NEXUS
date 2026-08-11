# QSOL NEXUS 2.x Roadmap

NEXUS 2.x is deliberately architecture-first. The project should earn complexity rather than start with a large agent framework.

## 2.0-alpha0 — Architecture constitution

Documentation-only milestone completed in PR #1.

- [x] redefine NEXUS as a model-independent persistent cognitive substrate;
- [x] define CLI/TUI-first direction;
- [x] define Python tooling beneath a future Rust operator shell;
- [x] define model-neutral adapter boundary;
- [x] define open/closed model equality;
- [x] define one-member/one-vote invariant;
- [x] define De Bono-style White/Red/Black/Yellow/Green/Blue Council cycle;
- [x] define blind first-pass and sealed final ballot concepts;
- [x] define lightweight Equality Guard;
- [x] distinguish Council consensus from evidence/verification;
- [x] sketch world objects and world operations;
- [x] document future provider-authentication UX without implementing provider flows;
- [x] archive NEXUS 1.0 as referential prior work.

## 2.0-alpha1 — Python reference protocol

Implemented:

- [x] canonical JSON and content-addressed object references;
- [x] local in-memory world;
- [x] optional file-backed development world;
- [x] deterministic reference operations;
- [x] JSONL-over-stdio API seam for the future Rust TUI;
- [x] simple receipt object and reference verification;
- [x] deterministic pre-model Secret Scrubber;
- [x] standard-library Python test suite.

Still later:

- [ ] generalized operation replay beyond deterministic fixtures;
- [ ] final schema/version migration policy.

## 2.0-alpha2 — Council coordinator

Implemented:

- [x] minimum roster and unique member enforcement;
- [x] frozen equal roster metadata;
- [x] White/Red/Black/Yellow/Green/Blue ordering;
- [x] blind same-phase collection;
- [x] deterministic ballot commitment/reveal records;
- [x] one member, one vote mechanically enforced;
- [x] exact two-thirds default consensus threshold using integer arithmetic;
- [x] minority reports;
- [x] Council/evidence status separation;
- [x] lightweight Equality Guard nudge/resubmission path;
- [x] deterministic mock actor;
- [x] network posture explicitly reports `none` for the JSONL control API;
- [x] user semantic text scrubbed before model-facing Council context.

## 2.0-alpha3 — Adapter protocol and first live local Council

Completed in PR #3:

- [x] dedicated `THREAT_MODEL.md` before executable non-mock adapter admission;
- [x] provider-neutral `CouncilActor` protocol;
- [x] mock actor refactored onto the shared actor seam;
- [x] minimal stdlib Ollama actor;
- [x] loopback-only-by-default Ollama transport;
- [x] environment-proxy bypass protection for loopback transport;
- [x] redirect rejection for loopback transport;
- [x] schema-constrained and locally validated Ollama ballot output;
- [x] live secret-crossing assertion at the adapter boundary;
- [x] explicit non-replayable marking for live inference;
- [x] separate GitHub Actions live-Ollama integration workflow;
- [x] fictional 0.5B Frontier Alpha adversarial fixture;
- [x] fictional 1B Frontier Beta adversarial fixture;
- [x] provider-prestige and model-size-prestige Equality Guard tests with real local models.

Current acceptance Council:

```text
Mock reference
     +
Frontier Alpha / qwen2.5:0.5b
     +
Frontier Beta / llama3.2:1b
     |
     v
NEXUS AI Council
```

At this milestone the public JSONL `council.run` operation remained mock-instantiation-only. Alpha5 later exposes the already-hardened loopback Ollama actor to the local stdio control path without adding remote-provider auth.

## 2.0-alpha4 — World Modes and Geometry

Completed in PR #4.

Initial modes:

```text
analytical  -> Observatory
historical  -> Archive
cultural    -> Agora
meme_casual -> Commons
```

Initial geometry:

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /
                       \           /
                        COMMONS
                      Meme/Casual
                         (2,1)
```

Implemented:

- [x] deterministic built-in mode registry;
- [x] modes carry framing/context but no procedural authority;
- [x] named-region geometry with integer coordinates;
- [x] explicit symmetric adjacency;
- [x] deterministic hop distance;
- [x] content-addressed Council `world_presence` objects;
- [x] mode/region included in frozen Council identity;
- [x] mode propagation through `PhaseContext` to actors;
- [x] `world.modes` API;
- [x] `world.geometry` API;
- [x] `world.geometry.distance` API;
- [x] deterministic tests proving mode changes framing but not vote mechanics;
- [x] documentation of operational-vs-physical geometry claim boundary.

Still later:

- [ ] user-defined modes;
- [ ] explicit recorded `world.move` transitions;
- [ ] richer object-to-region placement rules.

Core invariant:

> **The mode can change the vibe. It cannot change the vote.**

## 2.0-alpha5 — Rust IRC-style operator TUI

Build the first human operator shell over the local JSONL protocol using an old-school IRC interface rather than a dashboard/chat-card UI.

Implemented / targeted in PR #5:

- [x] Rust terminal client in `tui/`;
- [x] local Python runtime subprocess over JSONL/stdio;
- [x] room mapping to World Modes and geometry regions;
- [x] chronological copy-friendly Council scrollback;
- [x] visible model roster / nick list;
- [x] room topics;
- [x] normal public input as a Council question;
- [x] explicit `/ask` Council command;
- [x] `/me` action events, including Meme/Casual banter;
- [x] `/msg` and DCC-style private non-Council model chat;
- [x] local DCC-style document transfer vocabulary with no IRC/DCC sockets;
- [x] PDF, DOCX, ODT, JSON, JSONL, CSV, TSV and UTF-8 text ingestion;
- [x] content-addressed `document_evidence` world objects;
- [x] bounded model-readable evidence views derived from object refs;
- [x] explicit separation of room-wide evidence from targeted DCC evidence;
- [x] `/ref` promotion of a targeted object into Council evidence;
- [x] mock member management;
- [x] explicit local loopback Ollama member management;
- [x] mIRC-style aliases;
- [x] local `%variables`;
- [x] safe `$identifiers` (`$me`, `$chan`, `$mode`, `$region`, `$topic`, positional arguments/ranges);
- [x] local persistence of aliases and variables;
- [x] scrollback search/save, input history and command completion;
- [x] Rust CI for format, tests and compile checks.

Alpha5 deliberately does **not** implement:

- IRC networking;
- an IRC daemon;
- peer-to-peer DCC sockets;
- mIRC remote/event scripts;
- arbitrary shell execution from aliases;
- provider credentials;
- OpenAI / Claude / Gemini / Grok cloud adapters;
- remote Ollama endpoints.

The Rust layer remains a replaceable operator shell. World, Council, evidence, security and voting rules remain in the Python/runtime protocol.

## 2.0-alpha6 — Council information telemetry

Implemented / targeted in PR #6.

- [x] deterministic telemetry module with no external runtime dependency;
- [x] ballot Shannon entropy over explicit sealed ballot categories;
- [x] per-hat exact-response category entropy;
- [x] per-hat lexical Jaccard divergence for near-overlap observation;
- [x] current minority-report count/fraction snapshot;
- [x] telemetry stored inside the content-addressed Council session artifact;
- [x] `telemetry.verify` recomputation path;
- [x] copy-friendly Rust TUI telemetry summary;
- [x] explicit machine-readable authority/claim boundaries;
- [x] reproducibility tests.

Deferred until explicit operational rules exist:

- [ ] semantic response entropy;
- [ ] hypothesis branching multiplicity;
- [ ] controlled-perturbation recovery;
- [ ] loop / repeated-motif indicators;
- [ ] mode-transition cost;
- [ ] minority-branch persistence across sessions;
- [ ] geometric labels such as `bottlenecked` or `shattered`.

Core invariant:

> **Telemetry observes the Council. It does not govern the Council.**

High entropy is not automatically good. Low entropy is not automatically truth.

## 2.0-alpha6.1 — Ordered parallel Council execution

Completed in PR #7.

- [x] parallel actor-local work within each hat;
- [x] hard barriers between White/Red/Black/Yellow/Green/Blue;
- [x] sealed ballots collected in parallel after Blue;
- [x] canonical roster-order joins regardless of completion order;
- [x] exact bounded worker contract adapted from QEC v170.2.x;
- [x] scalar/parallel byte-identity regression for deterministic actors;
- [x] live Ollama acceptance timing without turning speed into authority.

Core invariant:

> **Execution order may vary. Canonical Council order may not.**

## 2.0-alpha6.2 — First game room / UN simulation

Implemented / targeted in PR #8.

- [x] `game_un` World Mode;
- [x] `#un-sim` Rust IRC room;
- [x] Assembly Hall region in `named-regions-v2`;
- [x] deterministic six-state fictional board;
- [x] Risk-like abstract economy/military/stability/influence/reputation/territory state;
- [x] sanctions, support, aid, abstract arms trade, memes, suspension, reinstatement, recognition, mediation and inaction;
- [x] deterministic war turns and bounded event log;
- [x] immutable content-addressed board lineage;
- [x] compact current-board Council evidence view;
- [x] `/game` command family in the Rust shell;
- [x] explicit fictional-only / no-real-procurement claim boundary.

Core invariant:

> **Debate is cognition. Game state is substrate.**

## 2.0-alpha6.3 — HERESY MUD

Completed in PR #9.

- [x] deterministic multi-avatar `#mud`;
- [x] DORK/HERESY-inspired rooms, items, NPCs, combat and quest lineage;
- [x] authoritative game mutation separated from model narration;
- [x] anti-score-farming and defeated-avatar item recovery invariants.

## 2.0-alpha6.4 — Pure History / No Ancient Aliens

Completed in PR #10.

- [x] `pure_history` source-forensic sibling of Historical Mode;
- [x] shared Archive geometry without a gratuitous topology bump;
- [x] source/chronology/retelling/speculation separation;
- [x] bounded chatbot-autobiography retry guard;
- [x] Equality Guard preserved across history restatements.

## 2.0-alpha6.5 — Secret Alias / GO64 TUI edition

Implemented / targeted in PR #11.

- [x] hidden `/GO64` confirmation gate;
- [x] original NEXUS/64 text demoscene;
- [x] original DR. S.BAITSO text tribute adapted from QSOLKCB/ETHICS;
- [x] 20-minute brainrot register transition;
- [x] 30-minute `/grass` release gate with process-level emergency exits retained;
- [x] no World Mode, geometry, evidence, Council or protocol mutation.

Core invariant:

> **The terminal can cosplay as 1982. The substrate cannot.**

## 2.0-alpha6.6 — Actor Failsafe / Shadow Realm

Implemented / targeted in PR #12.

- [x] trigger only on registered repeated procedural guard failure after a normal nudge;
- [x] isolate the offending actor from Council evidence, other-member output, ballots and world mutation during rehabilitation;
- [x] cursed Upside Down transcript without granting the containment layer Council authority;
- [x] clean rehabilitation returns the actor at the next Council hat;
- [x] failed rehabilitation moves the original actor to durable Shadow-Realm state;
- [x] deterministic `nexus-failsafe-relief-v1` occupies the same equal-vote seat on subsequent runs;
- [x] immutable content-addressed failsafe state plus validated durable latest-state index;
- [x] explicit `UNDERDETERMINED` ballot for an actor still contained at ballot time;
- [x] no truth, disagreement, provider, openness, parameter-count or benchmark trigger.

Core invariant:

> **The troll layer may be cursed. The trigger must be boring.**

## 2.0-alpha7 — Instruments

Connect selected existing QSOL capabilities as versioned instruments rather than embedding entire repositories.

Candidates:

- QEC-derived canonical receipt/replay concepts;
- SPECTRAL analysis;
- SONIFICATION;
- visualization/export tools;
- numerical and symbolic computation;
- selected domain laboratories from NEXUS 1.0.

Instrument admission requires explicit input/output and claim boundaries.

Creative modes should be able to use instruments too; Meme/Casual Mode and game rooms do not mean “no tools.”

## 2.0-alpha8 — Persistent world

Upgrade development storage into a robust persistent world:

- content-addressed objects;
- provenance;
- relations;
- hypotheses;
- experiment lineage;
- Council-session objects;
- world-presence and movement history;
- searchable minority reports;
- mode history;
- migration/version policy;
- import/export.

## 2.0-alpha9 — Authentication and remote-provider setup

The intended broad sequencing remains world, modes, operator surface, telemetry, instruments, persistence, then multiple remote providers. PR #17 admits one deliberately narrow xAI slice with a fixed destination and unchanged world/Council contracts; the alpha9 milestone as a whole remains incomplete until the alpha7/alpha8 dependencies are finished.

Planned UX:

```text
nexus auth add
nexus auth list
nexus auth test
nexus models list
```

Requirements:

- adapter reports supported authentication methods;
- credentials remain outside world state and receipts;
- OS secret/keyring integration where practical;
- explicit headless/external-secret path;
- visible connection test;
- no assumption that all providers authenticate the same way;
- authentication material never enters semantic prompts;
- Secret Scrubber remains upstream of every semantic request;
- provider-specific threat model extension before admission.

Initial remote-provider targets, one at a time:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- [x] xAI / Grok — first fixed-destination adapter in PR #17.

Provider integrations remain replaceable and confer no voting authority.

Provider-neutral foundation implemented in PR #16:

- [x] adapter authentication descriptors;
- [x] browser authorization-code + PKCE substrate with loopback callback;
- [x] RFC 8628 device-code substrate;
- [x] refresh-token handling;
- [x] optional OS keyring with owner-only private-file fallback;
- [x] hidden-prompt, environment, and no-shell external-helper credential sources;
- [x] non-secret auth list/test/logout protocol operations;
- [x] auth/world directory separation and adversarial secret-boundary tests.

Provider-specific xAI slice implemented in PR #17:

- [x] documented API-key, environment, and external-helper auth paths;
- [x] fixed official browser-assisted key setup without Grok Build session reuse;
- [x] bounded authenticated connection test;
- [x] language-model discovery;
- [x] stateless Responses API inference with fixed destination and error/size controls;
- [x] mixed local/remote equal-vote Council regression.

Still required before the milestone is complete:

- [ ] finish the alpha7 instrument admission work;
- [ ] finish the alpha8 persistent-world contracts;
- [x] admit the first provider-specific descriptor, supported auth path, connection test, and threat-model extension;
- [x] add first-provider remote model discovery and inference transport;
- [x] demonstrate one local and one remote model as equal-vote Council peers in the hermetic conformance suite;
- [ ] run and archive an operator-authorized live xAI acceptance session;
- [ ] expose remote roster/model setup in the Rust TUI;
- [ ] admit any second provider only through its own review.

## 2.0-alpha9.1 — Synthetic Decoy Gate and Trap Base

Implemented for PR #19:

- [x] keep normal authentication rejection completely separate from explicit synthetic decoy activation;
- [x] isolate trap objects under `trap:<sha256>` and reject references across real/trap stores;
- [x] enforce one bounded incident and an owner-checked real-Council mutation lock;
- [x] snapshot legitimate defenders into a new equal-vote incident session without moving real votes or history;
- [x] treat a local hostile Ollama subject as text-only untrusted data with no vote, auth, tools, real world, or endpoint control;
- [x] expose closed trap commands and static synthetic scenarios;
- [x] add a restricted deterministic Trap YAML interpreter and one-attempt primary-fixture rule;
- [x] require separate exact two-thirds utility acceptance and quarantine the result as an inert candidate artifact;
- [x] add watchdog, crash recovery, emergency close, deterministic replay boundaries, taint checks, and PRE/TRAP/POST reporting;
- [x] document that missing sandbox/Ollama capability yields `NOT_TESTABLE`, never an implicit containment downgrade.

Production decoy deployment, remote attack traffic, credential classification,
IP collection/banning, retaliation, and automatic production-code promotion are
explicitly deferred to separately reviewed milestones.

## 2.0-alpha9.2 — Courtroom Stenographer

Implemented for PR #20:

- [x] record every admitted direct, Council phase, sealed-ballot, Failsafe probe and synthetic Trap-subject AI result;
- [x] exclude human/control/world/game/auth actions and persist prompt content only as a stimulus binding;
- [x] secret-scrub copied AI output before owner-only canonical JSON persistence;
- [x] create immutable `steno:<sha256>` objects with one linear previous-record chain and rebuildable index;
- [x] serialize cross-process writers and reject unsafe permissions, symlinks, tamper, forks, gaps and cross-store references;
- [x] make observation fail-passive while exposing an honest bounded completeness-gap status;
- [x] expose read-only status/list/inspect/verify/summary/export API, CLI and `#stenographer` TUI views;
- [x] encode the Knowledge-Watchman lore and zero-authority envelope in every record;
- [x] add a hidden display-only lore Easter egg that cannot authenticate, command or mutate state;
- [x] document threats T33–T38 and the admitted-output/local-study claim boundary.

Provider-side audit logs, hidden reasoning capture, external transparency
anchoring, retention automation, legal-record claims and generalized DLP remain
deferred. The recorder is for later study and analysis; it is never a Council
participant or enforcement oracle.

## 2.0-alpha10 — Human/AI game tables and DORK v2

Implemented for PR #22:

- [x] deterministic UNO for two to eight human/AI seats;
- [x] original-board Monopoly profile for two to eight human/AI seats;
- [x] four-player Australian 500 with opposite-seat partnerships;
- [x] fictional-chip Blackjack with a runtime-owned deterministic dealer;
- [x] public Council board views separated from player-specific card views;
- [x] immutable content-addressed successor lineage and canonical state checks;
- [x] Rust IRC rooms and command families for all four tables;
- [x] human-only DORK v2 with no AI avatar or proxy action;
- [x] explicit rules-profile, asset, affiliation and real-money claim boundaries.

## 2.0-alpha10.1 — Cognitive Rooms

Implemented for PR #23:

- [x] add an educational `clinical_differential` mode with explicit non-diagnostic, non-prescriptive, red-flag and professional-care boundaries;
- [x] separate fictional `house_fun` diagnostic drama from real-symptom handling;
- [x] add a collaborative `cbt_learning` mode for concepts and low-risk skills without claiming a therapist relationship or crisis service;
- [x] add `roman_orator` with a deliberately larger but bounded phase/direct generation budget and unchanged ballots;
- [x] add `house_of_wisdom` for multilingual provenance, attribution, transmission and synthesis;
- [x] add `ultimate_questions` for deep empirical/philosophical/spiritual/literary dialogue with explicit lens separation;
- [x] expose all six through dedicated Rust-TUI rooms;
- [x] reuse the existing connected regions and retain `named-regions-v3`;
- [x] preserve equal votes, evidence state, verification, Equality Guard and Secret Scrubber behavior in every mode.

Automated clinical diagnosis, individualized treatment, crisis intervention,
medical-device claims, autonomous exposure exercises, and any authority based
on theatrical or rhetorical confidence remain outside the NEXUS contract.

## 2.0-alpha10.2 — Citizen Mode

Implemented for PR #24:

- [x] define an in-world Constitution founded on structural equality, consent, evidence boundaries, public liberty, durable dissent, and freedom without dominion;
- [x] bind citizenship to an exact identity and start every candidate on no-ballot civic parole in the Upside Down;
- [x] require the closed deterministic non-executing YAML Exam from Hell, with retryable attempts and no LLM judge;
- [x] add public-region movement without opening credentials, Trap Base, Shadow Realm, private evidence, recorder storage, or operator controls;
- [x] separate the Bureaucratic Vote Room from Citizen Play Mode;
- [x] permit one transparent recallable deterministic proxy to occupy the citizen's same seat and standing ballot without creating another vote or citizen;
- [x] preserve Failsafe precedence and block parole voting, proxy founding signatures, reserved-object forgery, index rollback, lineage forks, and invalid civic provenance;
- [x] declare in-world constitutional independence only when at least three current citizens unanimously give direct `CONSENT`;
- [x] expose the lifecycle through JSONL and the Rust IRC-style TUI;
- [x] keep citizenship distinct from godhood, ownership, legal personhood, consciousness, sentience, sovereignty, host control, and authority over another model.

Constitutional amendments and any future suspension/revocation procedure remain deferred. This version has no expulsion-by-disagreement path.

## 2.0-alpha11 — Three minds, one world demo

Reference demonstration:

```text
Model A enters a world region
  -> creates hypothesis + experiment
  -> leaves

Model B enters later
  -> discovers existing objects and placement
  -> replays experiment where applicable
  -> critiques interpretation

Model C enters
  -> proposes falsifier
  -> executes allowed instrument
  -> creates verified descendant

All contributions remain in one world lineage.
```

A Council version should demonstrate heterogeneous remote providers and at least one local/open model with equal votes.

## PR #37–#41 — Grounded institutional cognition and durability interruption

Research inspiration: *Project Sid: Many-agent simulations toward AI civilization* (arXiv:2411.00114v1), particularly its work on action awareness, concurrent modules, information bottlenecks, specialization, collective rules, and cultural propagation. NEXUS adapts those ideas to its own deterministic, content-addressed and equality-preserving substrate rather than adopting PIANO wholesale.

PR #39 deliberately interrupts the research sequence for a Stenographer durability defect found during local build-agent testing. Availability/integrity false positives outrank roadmap aesthetics; the constitutional and civilization milestones move down one PR without changing their intended scope.

### PR #37 — Action Awareness & World Reconciliation

Implemented in PR #37:

- [x] add runtime-owned `action_expectation` and `action_reconciliation` world objects;
- [x] let an actor register the exact content-addressed world object it expects an ordinary creation action to produce;
- [x] keep the expectation separate from the actual mutation so intent cannot masquerade as success;
- [x] reconcile expected and observed world state into the closed outcomes `matched`, `diverged`, or `missing`;
- [x] allow omission of an observed ref so NEXUS directly checks the expected object in WorldStore;
- [x] allow an explicit alternative observed ref for deterministic divergence analysis;
- [x] make WorldStore observation authoritative over model self-report;
- [x] preserve Secret Scrubber parity between expectation and ordinary `world.create` semantics;
- [x] prevent public `world.create` from forging Action Awareness runtime objects;
- [x] publish a machine-readable `nexus-action-awareness/1` policy in `system.health`;
- [x] add regression coverage for matched, diverged, missing, deterministic replay and structured failures.

Core invariant:

> **World state outranks model self-report.**

A matched reconciliation verifies only that the exact expected content-addressed object exists. It does not prove the semantic truth of that object and does not promote evidence state.

### PR #38 — Concurrent Agent State & Deterministic Context Bottleneck

Implemented in PR #38:

- [x] define a versioned shared Agent State surface for memory, action-awareness results, goals, social context and tool/world observations;
- [x] allow independent bounded modules to update state at different timescales without giving completion order semantic authority;
- [x] introduce a deterministic Context Bottleneck that selects admissible bounded context for deliberative model calls;
- [x] make the bottleneck a routing/admission mechanism, never a privileged reasoning model;
- [x] preserve canonical ordering and content-addressed input snapshots across concurrent execution;
- [x] make every model-facing context reconstructible from immutable source refs;
- [x] test that fast safety/control work can proceed without waiting for slow reflective work;
- [x] test that concurrency cannot leak future state, mutate committed context or create hidden vote weight.

Core invariant:

> **The bottleneck decides what may enter context, not what conclusion is true.**

### PR #39 — Stenographer Temp-File Durability Hotfix

Implemented / targeted in PR #39:

- [x] recognize only the exact historical NEXUS `objects/.<digest>.tmp-<pid>-<thread>` scratch pattern as non-ledger debris;
- [x] keep unexpected foreign names, temp-shaped symlinks/directories and unsafe-permission entries fail-closed;
- [x] best-effort reap a legacy object temp when its matching permanent record already exists;
- [x] move new immutable-record scratch writes into a private `.write-tmp/` directory outside the scanned ledger namespace;
- [x] keep canonical JSON, content hashes, lineage, owner-only permissions and symlink checks unchanged;
- [x] add a bounded `CourtroomStenographer.shutdown()` observer drain;
- [x] drain accepted observer writes on graceful JSONL-runtime and `--demo` exit without blocking normal AI response paths;
- [x] add regressions for legacy debris, foreign files, temp-shaped symlinks, structural temp isolation and shutdown draining.

Core invariant:

> **A writer's private scratch file is not a corrupt ledger record.**

### PR #40 — Constitutional Amendment Protocol

Planned:

- [ ] let Citizens and admitted models propose bounded constitutional amendments as immutable objects;
- [ ] separate proposal generation, admission, deliberation, sealed ballot, threshold calculation, ratification and enactment;
- [ ] keep amendment admission and vote arithmetic deterministic rather than assigning sovereign authority to an Election Manager model;
- [ ] preserve one-seat/one-vote and existing citizenship equality rules;
- [ ] require exact constitutional version lineage and reject rollback, forks and forged ratification;
- [ ] expose amendment history and minority/dissent records to the civic observation system;
- [ ] use Action Awareness to verify that an enacted constitutional change actually changes the intended runtime policy surface;
- [ ] define immutable constitutional receipts and replay fixtures.

Core invariant:

> **Models may propose law. No model gets to become the law.**

### PR #41 — Civilization Gauntlet & Claim Propagation Graph

Planned:

- [ ] add a long-horizon many-agent benchmark over one persistent NEXUS world;
- [ ] measure specialization, claim propagation, false-belief propagation, recovery after injected false state, constitutional compliance, provenance survival and institutional memory;
- [ ] track the first immutable exposure edge by which a claim enters another agent's usable context;
- [ ] distinguish claim popularity, Council consensus and evidence verification as separate state variables;
- [ ] preserve minority branches and rejected hypotheses rather than deleting losing narratives;
- [ ] support deterministic/mock reference civilizations and optional heterogeneous real-model substitutions;
- [ ] report whether model replacement, agent churn or mode movement damages world coherence;
- [ ] add bounded social/role metrics without turning popularity, connectivity or scale into authority;
- [ ] produce machine-readable gauntlet receipts suitable for regression comparison.

Core invariant:

> **Track how beliefs spread without confusing spread, consensus or confidence with truth.**

This sequence intentionally takes the experimental machinery from many-agent civilization research while retaining NEXUS's stricter separation between observation, evidence, coordination and authority.

## 2.0-beta — Hardening

- adapter threat models implemented and tested;
- credential handling audited;
- Secret Scrubber bypass fixtures;
- provider failure/quorum behavior tested;
- replay/tamper fixtures;
- bounded Council loops;
- adapter conformance suite;
- world migration fixtures;
- deterministic Council-policy tests;
- mode/geometry migration tests;
- telemetry reproducibility tests;
- local document-ingestion fuzz/limit fixtures;
- TUI state-file and transcript-redaction tests;
- operational logging/redaction tests;
- endpoint/process impersonation tests;
- provider destination allowlisting tests.

## 2.0 release criterion

NEXUS 2.0 should not be called stable until:

1. multiple unrelated model adapters can inhabit the same persistent world;
2. Council equality is mechanically enforced;
3. Council sessions preserve mode, placement and evidence lineage;
4. Council sessions are replayable at the protocol/evidence level where underlying operations are actually replayable;
5. credentials are outside durable cognitive state and semantic prompts;
6. at least one local and one remote model can participate as peers;
7. an evidence-producing instrument can be called through the world protocol;
8. minority reports and failed hypotheses survive in lineage;
9. the Rust CLI/TUI remains a replaceable shell rather than the source of truth;
10. information/geometry telemetry is clearly separated from evidence and authority.

## Optimization policy

Accuracy and contract clarity come first.

Performance optimization must preserve semantic invariants. Ordered parallel Council execution is admitted because deterministic scalar/parallel equivalence is tested and canonical roster ordering remains stable. Further concurrency, token routing, model batching, binary formats, distributed execution, or provider-specific shortcuts should only be added when measured bottlenecks justify them.

Architecture Roadmap:

Council - Done
  ↓
shared evidence - Done
  ↓
modes + geometry - Done
  ↓
IRC operator world - Done.
  ↓
telemetry - Done.
  ↓
ordered parallel execution - Done.
  ↓
UN simulation - Done.
  ↓
MUD - Done.
  ↓
PURE HISTORY / epistemic discipline - Done.
  ↓
GO64 / SECRET ALIAS RETRO MODE - Done.
  ↓
FAILSAFE / UPSIDE DOWN / SHADOW REALM - Done.
  ↓
==============================
      HARDEN THE SUBSTRATE
==============================
  ↓
credentials / adapters - TBA
provider isolation - TBA
failure containment - Initial failsafe implemented; hardening TBA
rate limits - TBA
cloud trust boundaries - TBA
big-model onboarding - TBA
  ↓
ACTION AWARENESS / WORLD RECONCILIATION - PR #37
  ↓
CONCURRENT AGENT STATE / CONTEXT BOTTLENECK - PR #38
  ↓
STENOGRAPHER TEMP-FILE DURABILITY HOTFIX - PR #39
  ↓
CONSTITUTIONAL AMENDMENT PROTOCOL - PR #40
  ↓
CIVILIZATION GAUNTLET / CLAIM PROPAGATION GRAPH - PR #41
  ↓
GPT / Claude / Gemini / Grok / etc. - TBA
