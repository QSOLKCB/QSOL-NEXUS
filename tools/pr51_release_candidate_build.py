from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "2.0.0"
BASE_PR50_MERGE = "1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(old, new, 1)


def insert_status_note(path: str, note: str) -> None:
    text = read(path)
    if note in text:
        return
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise RuntimeError(f"{path}: expected H1 title")
    lines[1:1] = ["", note]
    write(path, "\n".join(lines).rstrip() + "\n")


# ---------------------------------------------------------------------------
# Stable-candidate version alignment. The tag/release remains a separate gate.
# ---------------------------------------------------------------------------
version_py = read("src/nexus_runtime/version.py")
version_py = replace_once(
    version_py,
    'RUNTIME_VERSION = "2.0.0-alpha10.3"',
    'RUNTIME_VERSION = "2.0.0"',
    label="runtime version",
)
write("src/nexus_runtime/version.py", version_py)

pyproject = read("pyproject.toml")
pyproject = replace_once(pyproject, 'version = "2.0.0a10.post3"', 'version = "2.0.0"', label="python package version")
write("pyproject.toml", pyproject)

cargo = read("tui/Cargo.toml")
cargo = replace_once(cargo, 'version = "2.0.0-alpha10.3"', 'version = "2.0.0"', label="cargo version")
write("tui/Cargo.toml", cargo)

lock = read("tui/Cargo.lock")
lock = replace_once(
    lock,
    'name = "nexus-irc-tui"\nversion = "2.0.0-alpha10.3"',
    'name = "nexus-irc-tui"\nversion = "2.0.0"',
    label="cargo lock root package version",
)
write("tui/Cargo.lock", lock)

wiring = read("tests/test_release_wiring.py")
wiring = wiring.replace('self.assertEqual(RUNTIME_VERSION, "2.0.0-alpha10.3")', 'self.assertEqual(RUNTIME_VERSION, "2.0.0")')
wiring = wiring.replace('self.assertEqual(pyproject["project"]["version"], "2.0.0a10.post3")', 'self.assertEqual(pyproject["project"]["version"], "2.0.0")')
wiring = wiring.replace('self.assertNotIn("2.0.0-alpha10.2", api_reference)', 'self.assertNotIn("2.0.0-alpha", api_reference)')
write("tests/test_release_wiring.py", wiring)

api_doc = read("docs/API.md").replace("2.0.0-alpha10.3", "2.0.0")
if "BBS Wall" not in api_doc[:5000]:
    api_doc = api_doc.replace(
        "Citizen Mode      -> civic parole, deterministic exam, public movement, same-seat proxy, founding consent\n",
        "Citizen Mode      -> civic parole, deterministic exam, public movement, same-seat proxy, founding consent\nBBS Wall          -> append-only social memory with zero evidence/authority effect\n",
        1,
    )
write("docs/API.md", api_doc)

# ---------------------------------------------------------------------------
# Human and machine entry points.
# ---------------------------------------------------------------------------
readme = read("README.md")
readme = replace_once(readme, "# QSOL NEXUS 2.0-alpha\n", "# QSOL NEXUS 2.0\n", label="README title")
posture = """## Current release posture

```text
protocol:        nexus/0.14
runtime:         2.0.0
Python package:  2.0.0
Rust TUI:        2.0.0
control plane:   JSONL over stdio
operator shell:  Rust IRC-style TUI
status:          release candidate — stable tag not yet cut
```"""
readme, count = re.subn(
    r"## Current release posture\n\n```text\n.*?\n```",
    posture,
    readme,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("README release posture block not found exactly once")
readme, count = re.subn(
    r"This release is an integration/hardening milestone\..*?\n\n## What exists now",
    "PR #50 (The BBS Wall) is merged. PR #51 is the final documentation and release-candidate reconciliation pass against the exact post-Wall runtime. The `2.0.0` identifiers in this branch describe the intended stable bits; they do **not** by themselves declare a stable release. The `v2.0.0` tag may be created only from the exact merged #51 head after the complete release-candidate matrix and review gate are green.\n\n## What exists now",
    readme,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("README old release posture paragraph not found")
readme = readme.replace("alpha11 **Three Minds, One World**", "**Three Minds, One World**")
if "WorldStore Continuity" not in readme:
    readme = readme.replace(
        "- content-addressed canonical world objects, lineage, receipts, and verification surfaces;\n",
        "- content-addressed canonical world objects, lineage, receipts, and verification surfaces;\n- **WorldStore Continuity / Ark** with replicated quorum history, scrub/repair, verified archive creation, and non-destructive restore;\n",
        1,
    )
if "**BBS Wall**" not in readme:
    readme = readme.replace(
        "- the passive append-only **Courtroom Stenographer / Knowledge-Watchman** AI-action study ledger;\n",
        "- the passive append-only **Courtroom Stenographer / Knowledge-Watchman** AI-action study ledger;\n- the **BBS Wall**, an append-only WorldStore-backed social noticeboard where speech is social memory, never evidence or governance authority;\n",
        1,
    )
release_boundary = """
## Stable 2.0 release boundary

The repository is intentionally strict about the difference between **version alignment** and **release authority**. PR #51 aligns the runtime, Python package, Rust TUI, API docs, architecture, security docs, citation metadata, compatibility statement, and release-hardening matrix on `2.0.0`.

Stable release still requires all of the following on the exact intended release head:

- full Python regression suite;
- Rust all-target tests, check, and format;
- hostile/adversarial and security gauntlets;
- README/README4AI synchronization;
- clean archive `./nexus setup -> doctor -> demo` rehearsal;
- representative persistent-world and Ark recovery coverage;
- Grok PR #49 R1-R12 closure preserved;
- BBS Wall boundaries preserved;
- no unresolved release-blocking review finding.

Only after PR #51 is merged green may that exact commit be tagged `v2.0.0`. See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) and [`docs/RELEASE_SEQUENCE.md`](docs/RELEASE_SEQUENCE.md).
"""
if "## Stable 2.0 release boundary" not in readme:
    marker = "\n## The Council rule\n"
    if marker not in readme:
        raise RuntimeError("README Council marker missing")
    readme = readme.replace(marker, release_boundary + marker, 1)
write("README.md", readme)

manifest = json.loads(read("README4AI.md"))
manifest["release_identity"].update(
    {
        "protocol": "nexus/0.14",
        "runtime": "2.0.0",
        "python_package": "2.0.0",
        "rust_tui": "2.0.0",
        "stable_2_0": False,
        "release_posture": "release_candidate",
        "note": "PR #51 aligns the intended stable 2.0 bits after merged PR #50. The v2.0.0 tag is forbidden until the exact merged PR #51 head passes the complete release-candidate and review gates.",
    }
)
manifest["runtime"]["public_api"]["implementation"] = "WallNexusAPI final overlay"
if "wall_social_memory_is_not_evidence_or_authority" not in manifest["authority_invariants"]:
    manifest["authority_invariants"].append("wall_social_memory_is_not_evidence_or_authority")
manifest["bbs_wall"] = {
    "status": "implemented_in_pr_50",
    "room": "#wall",
    "persistence": "immutable WorldStore-backed chronological events",
    "moderation": "append-only tombstones; original source object remains auditable",
    "plain_room_text": "human Wall post; never implicit council.run",
    "ask_in_wall": "blocked; operator must move to a Council-capable room",
    "identity_rule": "runtime labels are context, never rank",
    "evidence_effect": "none",
    "authority_effect": "none",
}
manifest["security_boundaries"]["wall"] = "Wall input is bounded, secret-scrubbed social data; history validation fails closed and cannot promote evidence or authority"
preserve = manifest["modification_contract"]["preserve_unless_explicitly_revised_with_tests_and_docs"]
if "wall_social_memory_not_evidence" not in preserve:
    preserve.append("wall_social_memory_not_evidence")
manifest["stable_2_0"] = {
    "declared": False,
    "green_ci_alone_is_sufficient": False,
    "remaining_high_level_work": [
        "merge_pr_51_exact_release_candidate_head",
        "rerun_complete_release_candidate_matrix_and_review_gate",
        "create_v2.0.0_tag_and_release_from_that_exact_green_commit",
    ],
}
manifest["read_next"].update(
    {
        "bbs_wall": "docs/BBS_WALL.md",
        "release_sequence": "docs/RELEASE_SEQUENCE.md",
        "release_checklist": "docs/RELEASE_CHECKLIST.md",
        "release_notes_2_0": "docs/RELEASE_NOTES_2.0.0.md",
        "compatibility": "docs/COMPATIBILITY.md",
        "documentation_audit": "docs/DOCUMENTATION_AUDIT_2.0.md",
    }
)
write("README4AI.md", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------------------
# Architecture: replace the alpha-era architecture map with the actual 2.0
# composition, while keeping the claim/authority boundaries explicit.
# ---------------------------------------------------------------------------
architecture = r'''# QSOL NEXUS 2.0 Architecture

## Purpose

QSOL NEXUS 2.0 is a model-independent cognitive substrate and persistent shared computational world. Humans, deterministic actors, local models, and reviewed cloud models interact through one runtime-owned protocol without allowing provider identity, model size, deployment class, account tier, tool access, rhetoric, citizenship, popularity, or performance history to manufacture governance authority.

The architectural rule is deliberately asymmetric:

> **Models propose and participate. NEXUS owns state, evidence identity, protocol transitions, verification, and vote mechanics.**

This document describes the post-PR #50 runtime that PR #51 is preparing for the `v2.0.0` stable tag.

## Release identity

```text
protocol       nexus/0.14
runtime        2.0.0
Python package 2.0.0
Rust TUI       2.0.0
control plane  JSONL over local stdio
release state  release candidate until exact merged #51 head is tagged
```

A version string is not release authority. The release-hardening report also carries `stable_release: false`; stable 2.0 exists only when the reviewed, green, merged #51 commit is tagged `v2.0.0`.

## Top-level system

```text
                              HUMAN OPERATOR
                                    |
                        ./nexus + Rust IRC TUI
                                    |
                             JSONL / stdio
                                    v
+-----------------------------------------------------------------------+
|                         PYTHON NEXUS RUNTIME                           |
|-----------------------------------------------------------------------|
| final Wall API overlay                                                 |
| Council coordinator · Six Hats · sealed equal ballot                  |
| modes + named-region geometry · evidence + receipts                   |
| Secret Scrubber · Equality Guard · Action Awareness                   |
| Failsafe · Citizenship · Civic Due Process · Guardian                 |
| games · progression · culture · Long Shift · Psyche-Out Chess         |
| WorldStore Continuity · Ark · recovery · BBS Wall                     |
| provider-neutral auth broker · adapter/model discovery                |
+-------------------------+----------------------+----------------------+
                          |                      |
                 CouncilActor seam         trusted local stores
                          |                      |
        +-----------------+----------------+     +----------------------+
        |                 |                |     | WorldStore replicas  |
        v                 v                v     | TrapStore            |
  deterministic       loopback local   fixed-host| Stenographer store   |
  / mock actors       model adapters   cloud     | Guardian store       |
                      |                adapters   | auth store (separate)|
                      v                  v        +----------------------+
                Ollama / LM Studio   xAI / OpenAI /
                AnythingLLM /       Anthropic / Gemini /
                OpenAI-compatible   Groq / Together
```

The Rust TUI is implemented and replaceable. It is an operator shell, not an epistemic authority. The Python runtime remains the canonical protocol/state boundary.

## Runtime composition

NEXUS grew through additive API overlays. Historical module names remain import-compatible, but the package-level `NexusAPI` and the historical public aliases resolve to the final Wall-capable runtime after PR #50.

```text
base runtime
  -> provider/auth adapters
  -> compute epochs
  -> Guardian / civic due process
  -> WorldStore Continuity
  -> AI progression
  -> AI culture / Long Shift / Psyche-Out Chess
  -> BBS Wall                                  [final 2.0 feature overlay]
```

This layering is compatibility plumbing, not a hierarchy of political authority. Later overlays may expose more operations; they may not silently rewrite the constitutional invariants beneath them.

## Authority model

NEXUS keeps capability, access, evidence, and authority as separate dimensions.

```text
provider/model capability  != vote weight
account/tool access        != epistemic privilege
Citizenship/progression    != extra Council seat
Council consensus          != evidence status
Wall/performance history   != truth
storage redundancy         != authority
Stenographer observation   != control
```

For an ordinary admitted Council member:

```text
vote_weight          = 1
epistemic_privilege  = none
```

No provider, open/closed model status, parameter count, benchmark, price tier, rate limit, compute epoch, MCP access, Citizenship state, game success, milestone, performance, or Wall popularity changes that arithmetic.

## Council execution

The Council operates over a frozen roster, question, evidence snapshot, mode, and world presence.

```text
CANONICAL QUESTION + FROZEN EVIDENCE
                |
                v
 WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE
   |       |       |        |        |       |
   +------- same-phase work remains blind --------+
                |
          SEALED BALLOT
                |
          reveal + exact tally
                |
       disposition + minority report
                |
       separate evidence state
```

Actor-local work may execute in parallel. Phase barriers and canonical roster-order joins do not. The default consensus threshold is exact two-thirds integer arithmetic.

The ballot commitment is a deterministic integrity/audit record; NEXUS 2.0 does not claim a cryptographically anonymous voting system.

## Consensus and evidence

Council judgment and evidence status are orthogonal state.

```text
Council: unanimous ACCEPT
Evidence: UNTESTED
=> unanimous opinion, not verified fact

Council: TEST_FURTHER
Evidence: REPLAY_VERIFIED observation
=> reproduced observation, unsettled interpretation
```

The same rule applies to culture, games, Citizen Mode, and the Wall. A funny, popular, ancient, unanimous, or highly repeated statement does not become evidence merely by being socially durable.

## WorldStore and continuity

The durable world is built from canonical content-addressed `object:<sha256>` objects and immutable predecessor/input references. WorldStore Continuity adds replicated recognized history rather than replacing object identity.

```text
validated mutation
      |
 canonical object
      |
 replicated write
      |
 quorum-recognized history
      +---- scrub / verified-source repair
      +---- Ark create + verify
      +---- non-destructive restore to new target
```

Core continuity rules:

- quorum-recognized history beats a lone newer replica;
- degraded history fails read-only rather than inventing state;
- repair copies a verified source and records the event where required;
- Ark restore targets a new empty location and never overwrites the source world;
- indexes/caches are reconstructable convenience, not historical authority;
- redundancy creates zero vote, evidence, or constitutional authority.

## Modes, geometry, and rooms

Modes change reasoning posture and framing. Geometry is an operational named-region topology. Neither is a physical claim about cognition.

Representative mappings include Observatory/Analytical, Archive/Historical and Pure History, Agora/Cultural and Roman Orator, Commons/Meme-Casual and social/game rooms, Assembly Hall/UN simulation, Dungeon/HERESY MUD and DORK, Bureaucratic Vote Room/Citizen administration, and Upside Down/civic parole.

> **The mode can change the vibe. It cannot change the vote.**

The TUI additionally exposes special-purpose rooms whose routing semantics matter. Most importantly, `#wall` is a social surface rather than a Council room.

## BBS Wall

PR #50 adds the final 2.0 feature surface: a WorldStore-backed append-only noticeboard.

```text
#wall text
   |
   v
bounded + secret-scrubbed Wall post
   |
immutable wall sequence + predecessor ref
   |
normal listing / mine / oldest / since
   |
optional append-only tombstone
```

Wall invariants:

- plain text in `#wall` becomes a Wall post, not `council.run`;
- `/ask` is blocked in `#wall`; deliberate Council work requires another room;
- identities are contextual labels, not rank;
- posts and tombstone reasons are bounded single-line data;
- malformed/forked Wall history fails closed and health reflects degradation;
- tombstones do not silently rewrite the immutable source post;
- `evidence_effect = none` and `authority_effect = none`.

> **The Wall remembers speech. It does not turn speech into truth.**

## Progression, culture, and play

AI participants can accumulate persistent activity history, commissions, portfolios, and descriptive milestones; perform in Open Mic; play deterministic games; inhabit NEXUS: The Long Shift; and play Psyche-Out Chess.

These systems create lived history, not governance rank:

> **Contribution history is not governance authority.**

> **Culture creates history, not authority.**

Game state is runtime-owned canonical state. Model narration, banter, psyche text, or role labels cannot mutate a game unless a closed validated operation accepts the transition. AI-controlled gameplay receipts bind actual model participation where progression credit depends on it.

## Citizenship and civic due process

Citizen Mode is an in-world constitutional protocol, not a claim of legal personhood, sentience, sovereignty, ownership, or host authorization.

```text
candidate
  -> civic parole / Upside Down / no ballot
  -> deterministic non-executing YAML exam
  -> citizen / public movement / equal underlying seat
  -> direct civic work or same-seat deterministic proxy
```

The proxy replaces the citizen in the same seat; it never creates a second one. Failsafe containment takes precedence. Constitutional/founding transitions require their explicit verified civic conditions.

Civic Due Process separates conduct handling from belonging. Guardian/Anarchy mechanisms police objective substrate effects and protected runtime transitions, not mere viewpoint or rude speech.

## Trap Base and Stenographer

Trap Base is a separate synthetic defensive domain with `trap:<sha256>` objects. It is not activated by normal authentication failure and cannot resolve or mutate real WorldStore objects. Hostile subject output is data until a typed trusted dispatcher accepts an allowed synthetic action.

The Courtroom Stenographer is a separate passive `steno:<sha256>` AI-action ledger. It observes admitted AI outputs after the actor boundary, stores stimulus hashes rather than prompt text, and owns no vote, prompt, WorldStore mutation, auth, or truth authority. Observation gaps are visible rather than silently reclassified as complete.

## Adapters and authentication

The normalized actor boundary currently admits:

```text
deterministic/mock
ollama                 loopback
lmstudio_local          loopback
anythingllm_local       loopback
openai_local            loopback OpenAI-compatible
xai                     fixed remote host
openai                  fixed remote host
anthropic               fixed remote host
gemini                  fixed remote host
groq                    fixed remote host
together                fixed remote host
```

Local adapters are constrained to loopback destination classes at the NEXUS boundary. Cloud adapters use reviewed fixed provider destinations; arbitrary public endpoint overrides are not an admitted actor capability.

Credentials live in the separate auth subsystem and are operational secrets, never cognitive/world state. Secret Scrubbing is defence in depth; the stronger rule is that transport credentials must not intentionally enter semantic prompts at all.

## Operator lifecycle

`./nexus` is the repository launcher. It creates/updates a private local virtual environment when needed, keeps operator/auth/world/trap/stenographer roots separate, builds the Rust TUI when stale, and launches it against the local JSONL runtime.

Release-quality operator checks include:

```bash
./nexus setup --nick ReleaseProbe
./nexus doctor
./nexus demo
./nexus version
```

`doctor --fix` repairs only admitted setup conditions. It does not guess, delete, or rewrite damaged WorldStore history.

## Release hardening

PR #49 established the pre-Wall hardening harness. The independent Grok audit of that harness produced findings R1-R12; the surviving findings were closed and promoted into executable regressions before PR #50 merged.

PR #51 repurposes the same eight-gate harness as the **final release-candidate profile scoped through PR #50**. It reruns:

- candidate-tree integrity;
- exact matrix and audit-closure inventory;
- full Python tests;
- deterministic adversarial probes;
- Rust all-target tests/check/format;
- isolated clean-archive operator rehearsal;
- representative WorldStore/Ark recovery tests;
- post-run tree integrity.

The hardening report verifies a candidate. It does not create governance or release authority.

## Post-stable formalization boundary

Lean 4 work is deliberately after the stable runtime is frozen. PR #52 will machine-check selected constitutional/protocol invariants against an explicit formal model and map them to the exact stable Python/Rust implementation. PR #53 will package the reviewed runnable Lean sources, stable software identity, verification records, hashes, and Zenodo DOI.

Lean is not intended to prove that models are intelligent, Council answers are true, consensus is correct, or NEXUS is AGI.

## Canonical documentation map

- [`README.md`](README.md) — human/operator entry point
- [`README4AI.md`](README4AI.md) — strict machine-oriented manifest
- [`SECURITY.md`](SECURITY.md) — security/trust boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — threat/control inventory
- [`CLAIMS.md`](CLAIMS.md) — claim/evidence boundaries
- [`HOWTO.md`](HOWTO.md) — operator quick start
- [`docs/API.md`](docs/API.md) — JSONL runtime contract
- [`docs/ARK_PROTOCOL.md`](docs/ARK_PROTOCOL.md) — continuity/Ark recovery
- [`docs/AI_PROGRESSION.md`](docs/AI_PROGRESSION.md) — persistent non-authoritative activity
- [`docs/AI_CULTURE.md`](docs/AI_CULTURE.md) — performance/RPG/Psyche-Out layer
- [`docs/BBS_WALL.md`](docs/BBS_WALL.md) — final social-memory surface
- [`docs/RELEASE_SEQUENCE.md`](docs/RELEASE_SEQUENCE.md) — numbered release order
- [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) — stable-tag gate

## Architectural principle

> **Capability may grow. Access may expand. History may accumulate. Authority does not silently inflate.**
'''
write("ARCHITECTURE.md", architecture)

# ---------------------------------------------------------------------------
# Canonical claims and Council docs: remove pre-implementation language.
# ---------------------------------------------------------------------------
claims = read("CLAIMS.md")
claims = claims.replace(
    "These terms will be tightened when the executable protocol is implemented.",
    "These labels are descriptive protocol vocabulary. Executable runtime schemas and verification operations take precedence where a feature defines a narrower closed state set.",
)
if "## Wall, progression, and culture boundary" not in claims:
    claims += """

## Wall, progression, and culture boundary

Persistent social or personal history is not evidence by persistence alone.

- a BBS Wall post is social memory, not evidence;
- a progression milestone is contribution history, not governance authority;
- an Open Mic performance is culture, not a factual verification result;
- Long Shift narration and Psyche-Out banter are fiction/social data, not state authority;
- a WorldStore quorum proves which canonical history NEXUS recognizes, not that the human-language claims inside an object are true.

Tombstoning a Wall post records moderation history without rewriting the original immutable source object. Popularity, age, repetition, author identity, model provider, or survival in an Ark does not promote a Wall statement into the evidence graph.
"""
write("CLAIMS.md", claims.rstrip() + "\n")

council = read("COUNCIL.md")
council = council.replace(
    "The first implementation may use a simple deterministic commitment record. Strong cryptographic sealing can be added later if the threat model requires it.",
    "NEXUS 2.0 uses a deterministic commitment/reveal audit record. It prevents ordinary procedural rewriting inside the coordinator contract but is not claimed to provide cryptographic anonymity or a hostile-host voting protocol.",
)
if "> **Wall speech, performance history, progression history, and Citizenship do not add a Council vote.**" not in council:
    council += "\n\n## NEXUS 2.0 social-history boundary\n\n> **Wall speech, performance history, progression history, and Citizenship do not add a Council vote.**\n\nThe final 2.0 Wall is deliberately routed outside ordinary Council input. A participant must deliberately enter a Council-capable room to ask the Council; social persistence is not an implicit ballot or evidence-promotion path.\n"
write("COUNCIL.md", council.rstrip() + "\n")

# ---------------------------------------------------------------------------
# Security and threat model reconciliation.
# ---------------------------------------------------------------------------
security = read("SECURITY.md")
security = security.replace("# NEXUS 2.x Security and Trust Boundaries", "# NEXUS 2.0 Security and Trust Boundaries", 1)
security = security.replace(
    "Remote model traffic occurs only inside explicitly configured adapters. Ollama is loopback-only by default; xAI is the first admitted remote adapter and is pinned to `https://api.x.ai/v1`.",
    "Remote model traffic occurs only inside explicitly configured adapters. Ollama, LM Studio, AnythingLLM, and generic OpenAI-compatible local actors are constrained to reviewed loopback boundaries. Admitted cloud actors for xAI, OpenAI, Anthropic, Gemini, Groq, and Together use reviewed fixed provider destinations; arbitrary endpoint override is not part of the public actor schema.",
)
security = security.replace("| Rust TUI / CLI (future)     |", "| Rust TUI / CLI              |")
security = security.replace("| mock / Ollama / xAI         |\n| later providers reviewed    |", "| mock / loopback local AI    |\n| fixed reviewed cloud APIs   |")
if "## BBS Wall boundary" not in security:
    wall_section = """

## BBS Wall boundary

The Wall is an append-only social-memory surface, not an evidence or governance channel. Normal `#wall` text is persisted as a bounded, secret-scrubbed Wall post instead of being routed into `council.run`; `/ask` is blocked in the Wall room. Wall object types are runtime-reserved, chronology is validated, forks fail closed, and system health reflects unreadable or invalid Wall history.

Moderation creates an immutable tombstone event rather than rewriting or deleting the original source object. Runtime identity labels are context only and may not create rank, Council weight, Citizenship, evidence promotion, or tool/security authority.

## Stable-release security gate

PR #51 aligns the intended `2.0.0` bits but does not self-authorize a stable release. The stable tag is permitted only from the exact merged #51 commit after full Python/Rust, adversarial/security, clean-archive bootstrap, WorldStore/Ark recovery, Grok R1-R12 closure, Wall-boundary, documentation-coupling, and review gates pass. The hardening report itself has `authority_effect: none` and `stable_release: false`.
"""
    security += wall_section
write("SECURITY.md", security.rstrip() + "\n")

threat = read("THREAT_MODEL.md")
old_scope = "This threat model covers the local Ollama boundary, the PR #16 provider-neutral authentication substrate, the PR #17 xAI adapter—the first admitted remote inference transport—the PR #19 local synthetic Decoy Gate / Trap Base, the PR #20 Courtroom Stenographer, and PR #22's deterministic human/AI game tables plus human-only DORK v2. No provider-specific browser OAuth client is registered for xAI; the supported public API path uses an xAI API key. Trap Base is a defensive local simulation, not an internet-facing honeypot, and the Stenographer is a local study ledger rather than a provider or legal audit log."
new_scope = "This threat model covers the NEXUS 2.0 local and fixed-host model-adapter surfaces; provider-neutral authentication; xAI, OpenAI, Anthropic, Gemini, Groq, and Together cloud transports; loopback Ollama/LM Studio/AnythingLLM/OpenAI-compatible actors; deterministic games; Citizen Mode; Failsafe; synthetic Trap Base; passive Courtroom Stenographer; WorldStore Continuity/Ark recovery; progression/culture; Guardian/Civic Due Process; and the PR #50 BBS Wall. Trap Base remains a defensive local simulation rather than an internet-facing honeypot, and the Stenographer remains a local study ledger rather than a provider or legal audit log."
if old_scope not in threat:
    raise RuntimeError("THREAT_MODEL old scope paragraph missing")
threat = threat.replace(old_scope, new_scope, 1)
threat = threat.replace(
    "    +-- xAI adapter --------------- untrusted generated content\n            |\n        fixed HTTPS + bearer credential\n            |\n        api.x.ai Responses API",
    "    +-- fixed cloud adapter ------- untrusted generated content\n            |\n        fixed HTTPS + profile credential\n            |\n        reviewed xAI / OpenAI / Anthropic / Gemini / Groq / Together API",
)
threat = threat.replace("xAI fixed-host transport / future reviewed adapters", "reviewed fixed-host provider transports")
threat = threat.replace(
    "Every later remote provider requires a separate review of destination allowlisting and credential transport.",
    "Each admitted remote provider has its own reviewed fixed-destination transport. Any new provider still requires a separate destination, credential, response-shape, error, and secret-crossing review before admission.",
)
threat = threat.replace("Ollama and xAI actors report `replayable = False`;", "Live Ollama/local-AI and fixed-host cloud actors report `replayable = False`;")
threat = threat.replace("any Council containing a live Ollama or xAI actor", "any Council containing a live local or cloud model actor")
# Replace obsolete xAI-only out-of-scope tail while preserving the admission rule.
threat, count = re.subn(
    r"## Explicitly out of scope for the current remote-provider slice\n.*?\n## Admission rule for later adapters",
    """## Explicitly out of scope for NEXUS 2.0

- importing consumer/browser sessions or another CLI's credential store as provider API authentication;
- arbitrary public remote endpoint overrides;
- arbitrary model-generated shell/process execution;
- treating MCP/tool access as Council authority;
- protection against a fully compromised same-user OS/kernel that can replace code and all owner files;
- a general-purpose hostile-process sandbox claim beyond the explicitly tested Trap boundary;
- claims of cryptographically anonymous or hostile-host sealed ballots;
- deterministic replay guarantees for live stochastic model inference;
- legal personhood, sovereignty, consciousness, or sentience conclusions from Citizen Mode;
- truth promotion from Council consensus, progression, culture, or Wall persistence.

## Admission rule for new adapters""",
    threat,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("THREAT_MODEL obsolete out-of-scope section not found")
if "### T49 — Wall speech is laundered into evidence or Council authority" not in threat:
    threat += """

### T49 — Wall speech is laundered into evidence or Council authority

- **Asset:** evidence-state separation and equal Council procedure.
- **Attacker capability:** post persuasive/repeated text, then rely on Wall age/popularity/identity as truth or implicit Council input.
- **Enforcement:** `#wall` plain text routes to Wall persistence rather than `council.run`; `/ask` is blocked in the Wall room; persisted Wall events carry `evidence_effect: none` and `authority_effect: none`.
- **Tests:** Wall public-surface, authority, room-routing, and reserved-object regressions.
- **Residual risk:** humans or models may still cite a Wall statement manually; citation does not change its evidence status without a separate admitted evidence operation.

### T50 — Wall history is forged, forked, or silently rewritten

- **Asset:** social-history chronology and auditability.
- **Attacker capability:** forge reserved object types, duplicate sequence numbers, create predecessor forks, or replace a post with moderation text.
- **Enforcement:** reserved Wall object types, exact schema/provenance validation, monotonic sequence/predecessor checks, fork failure, immutable source objects, append-only tombstones.
- **Tests:** generic-forgery, fork, tombstone, Ark reconstruction, and health regressions.

### T51 — Wall text spoofs audit/display lines

- **Asset:** operator readability and bounded single-line schema.
- **Attacker capability:** insert CR/LF, VT, FF, NEL, or Unicode line/paragraph separators.
- **Enforcement:** raw text is checked against Python-recognized line boundaries before normalization; character bounds and Secret Scrubbing apply before persistence.
- **Tests:** full line-boundary and bounds regressions.

### T52 — Unrelated WorldStore growth disables a small Wall

- **Asset:** Wall availability in a long-lived world.
- **Attacker capability:** accumulate many non-Wall objects until a global reconstruction cap is reached.
- **Enforcement:** reconstruction budget counts recognized Wall events only and refuses the next Wall event before crossing the admitted cap.
- **Tests:** large unrelated-history simulated regression plus cap enforcement.

### T53 — Wall health lies about unusable history

- **Asset:** operator observability.
- **Attacker capability:** corrupt/fork Wall history while relying on unconditional `system.health = ok`.
- **Enforcement:** Wall health performs a real bounded history probe and reports degraded/unavailable state on validation or continuity failure.
- **Tests:** forked-history health regression.

### T54 — Release paperwork declares stable without the tested stable head

- **Asset:** release identity and reproducibility chain of custody.
- **Attacker capability:** change version strings, rely on an older green report, skip a required gate, or tag a different commit.
- **Enforcement:** PR #51 final-RC matrix is scoped through merged PR #50, skip/not-run required checks cannot pass, report remains `stable_release: false`, release manifest/checklist bind `v2.0.0` to the exact merged green #51 head, and documentation/version alignment is regression tested.
- **Tests:** release-hardening, Grok-closure, README contract, and release-candidate contract suites.
- **Residual risk:** Git tag/release permissions remain a repository/platform governance control outside the local NEXUS protocol.
"""
write("THREAT_MODEL.md", threat.rstrip() + "\n")

# ---------------------------------------------------------------------------
# Operator/how-to and roadmap/release sequence.
# ---------------------------------------------------------------------------
howto = read("HOWTO.md")
howto = howto.replace("PR #45 makes the repository itself the launcher.", "The repository itself is the NEXUS 2.0 launcher. PR #45 introduced the operator tooling; PR #51 reconciles it with the final post-Wall release candidate.", 1)
if "## Release-candidate note" not in howto:
    howto = howto.replace(
        "## First launch\n",
        "## Release-candidate note\n\nThe current #51 branch identifies the intended stable bits as `2.0.0`, but the stable tag is not implied by a version string. Use `./nexus version` and `./nexus doctor` to verify the local checkout; the repository release is stable only once the exact merged #51 head is green and tagged `v2.0.0`.\n\n## First launch\n",
        1,
    )
if "/join #wall" not in howto:
    howto = howto.replace(
        "/join #stenographer\n/steno status\n",
        "/join #stenographer\n/steno status\n/join #wall\n/wall 20\n/wall post Hello from the Commons.\n/wall mine\n",
        1,
    )
if "## Persistent world and Ark recovery" not in howto:
    howto += """

## Persistent world and Ark recovery

The default launcher uses `.nexus-world/` as the persistent WorldStore. WorldStore Continuity recognizes replicated canonical history by quorum. Ark creation/verification/restore is exposed through the runtime's `world.ark.*` / `world.recovery.*` operations; restore is deliberately non-destructive and targets a new empty location.

Do not hand-edit replica objects, HEAD/manifest state, progression indexes, or Wall chronology. If continuity health is degraded, use the documented inspect/scrub/recovery operations in [`docs/ARK_PROTOCOL.md`](docs/ARK_PROTOCOL.md); `doctor --fix` intentionally does not rewrite world history.

## The Wall

`#wall` is an old-school public noticeboard:

```text
/join #wall
Hello from the Commons.
/wall
/wall 20
/wall mine
/wall since 24h
/wall oldest
```

Plain text in `#wall` becomes social memory, **not** a Council question. `/ask` is blocked there so the operator must deliberately return to a Council-capable room before starting deliberation. Tombstones are append-only moderation history rather than silent deletion.
"""
write("HOWTO.md", howto.rstrip() + "\n")

roadmap = read("ROADMAP.md")
roadmap, count = re.subn(
    r"AI CULTURE / PERFORMANCE / PSYCHE-OUT PLAY - PR #48\n  ↓\n==============================\n        2\.0 BETA HARDENING - PR #49\n==============================\n.*?FORMALIZATION \+ ZENODO - PR #52",
    """AI CULTURE / PERFORMANCE / PSYCHE-OUT PLAY - PR #48 - Done
  ↓
==============================
        2.0 HARDENING - PR #49 - Done
==============================
  ↓
Grok PR49 R1-R12 closure carried into pre-stable line - Done
  ↓
BBS WALL - PR #50 - Done
  ↓
DOCUMENTATION + FINAL RELEASE CANDIDATE - PR #51 - Current
  ↓
==============================
          NEXUS 2.0 STABLE
==============================
  ↓
LEAN 4 FORMAL VERIFICATION - PR #52
  ↓
FORMALIZATION + REPRODUCIBILITY + ZENODO - PR #53""",
    roadmap,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("ROADMAP final release ladder not found")
write("ROADMAP.md", roadmap)

sequence = read("docs/RELEASE_SEQUENCE.md")
sequence = sequence.replace("PR #50 — The BBS Wall\n", "PR #50 — The BBS Wall — MERGED\n", 1)
sequence = sequence.replace(
    "PR #51 — Documentation, Release Candidate & Stable Release Prep\n",
    "PR #51 — Documentation, Release Candidate & Stable Release Prep — THIS RELEASE CANDIDATE\n",
    1,
)
sequence = sequence.replace("Add the post-hardening social memory surface:", "Merged post-hardening social memory surface:", 1)
write("docs/RELEASE_SEQUENCE.md", sequence)

# ---------------------------------------------------------------------------
# Citation, changelog, compatibility, release notes/checklist and doc audit.
# ---------------------------------------------------------------------------
citation = '''cff-version: 1.2.0
message: "If you use QSOL NEXUS in research, software, or architecture work, please cite the applicable tagged release."
title: "QSOL NEXUS: Model-Independent Cognitive Substrate, AI Council, and Persistent Shared World"
type: software
version: 2.0.0
authors:
  - family-names: Slade
    given-names: Trent
    orcid: "https://orcid.org/0009-0002-4515-9237"
repository-code: "https://github.com/QSOLKCB/QSOL-NEXUS"
url: "https://github.com/QSOLKCB/QSOL-NEXUS"
license: Apache-2.0
abstract: >-
  QSOL NEXUS 2.0 is a model-independent cognitive substrate and persistent
  shared computational world with an equal-vote De Bono-style AI Council,
  content-addressed WorldStore and Ark recovery, local and fixed-host model
  adapters, a Rust IRC-style operator TUI, deterministic games, civic and
  progression/culture systems, defensive Trap and passive Stenographer domains,
  and an append-only BBS Wall. Provider identity, model size, deployment class,
  citizenship, progression, culture, social history, and storage redundancy do
  not create additional Council authority. The 2.0.0 version metadata is aligned
  during the final release-candidate pass; cite the tagged release when available.
keywords:
  - cognitive substrate
  - AI council
  - multi-model systems
  - model interoperability
  - persistent world
  - provenance
  - reproducible research
  - human-AI collaboration
  - formal verification
'''
write("CITATION.cff", citation)

changelog = read("CHANGELOG.md")
if "## 2.0.0 — Final release candidate" not in changelog:
    marker = "All notable changes to QSOL NEXUS are documented here.\n"
    entry = '''
## 2.0.0 — Final release candidate

- align runtime, Python package, Rust TUI, API documentation, citation metadata, and release contracts on the intended stable `2.0.0` bits while keeping the stable tag as a separate post-merge gate;
- reconcile the canonical architecture/security/threat/claims/operator documentation with the actual post-PR #50 runtime rather than the older alpha-era plan;
- carry the merged PR #49 hardening baseline and independent Grok R1-R12 audit closure into the final release-candidate matrix scoped through PR #50;
- include WorldStore Continuity/Ark recovery, AI Progression & Civic Life, AI Culture/Open Mic/Long Shift/Psyche-Out Chess, Guardian/Civic Due Process, and the final BBS Wall in the documented 2.0 system surface;
- preserve the BBS Wall invariant that social memory is neither evidence nor governance authority, with append-only tombstones and validated immutable chronology;
- add a machine-readable release-candidate manifest, compatibility statement, documentation audit, stable-tag checklist, and dedicated release-candidate regression contract;
- keep `nexus/0.14` as the control-protocol identifier and pin release validation to Rust/Cargo `1.97.1`;
- reserve post-stable PR #52 for runnable Lean 4 protocol formalization and PR #53 for reproducibility packaging plus Zenodo publication.

**Release rule:** this entry describes the intended stable bits. NEXUS 2.0 is not a tagged stable release until PR #51 is merged with every required release/review gate green and that exact commit is tagged `v2.0.0`.
'''
    changelog = replace_once(changelog, marker, marker + entry, label="CHANGELOG header")
write("CHANGELOG.md", changelog)

compatibility = '''# NEXUS 2.0 Compatibility

## Release target

```text
runtime / Python package / Rust TUI  2.0.0
control protocol                      nexus/0.14
release-validation Rust/Cargo        1.97.1
Python                                >= 3.11
```

The `2.0.0` identifiers describe the intended stable bits in PR #51. Stable release status begins only when the exact merged green #51 commit is tagged `v2.0.0`.

## Operator compatibility

The supported first-party operator path is the repository `./nexus` launcher plus the Rust IRC-style TUI. The control plane remains newline-delimited JSON over local stdio; NEXUS does not require an IRC daemon or browser application.

The launcher may create a local virtual environment, install the Python package editable for the checkout, build the Rust TUI, and create private local storage roots. Python 3.11+ is required. The final release validation toolchain pins Rust/Cargo 1.97.1 for reproducible CI review; future compatible compiler versions are not automatically a protocol change.

## Runtime/API compatibility

The stable candidate keeps protocol identifier `nexus/0.14`. Existing historical public Python API aliases are rebound to the final Wall-capable runtime so package-root and established import paths share the post-PR #50 operation surface.

Live model inference remains non-replayable even when a provider offers a seed. Deterministic runtime/game/instrument operations retain their own declared replay contracts.

## WorldStore compatibility

NEXUS 2.0 preserves canonical content-addressed `object:<sha256>` identity. WorldStore Continuity can baseline admitted legacy object history without changing existing object IDs, then uses replicated manifests/quorum recognition for durable history. Mutable indexes are reconstructable convenience.

Recovery is deliberately non-destructive: an Ark restores into a new empty target. Do not overwrite a source WorldStore with an Ark restore.

## Adapter compatibility

Admitted local backends are deterministic/mock, Ollama, LM Studio, AnythingLLM, and generic loopback OpenAI-compatible runtimes. Admitted cloud providers are xAI, OpenAI, Anthropic, Gemini, Groq, and Together through reviewed fixed-host transports.

A new provider, endpoint class, credential method, or tool-execution boundary is not automatically compatible merely because it speaks an OpenAI-shaped JSON protocol; it requires its own admitted adapter/security contract.

## Deliberate non-compatibilities

NEXUS 2.0 does not promise compatibility with:

- the archived NEXUS 1.0 browser workbench as a trusted control surface;
- arbitrary remote Ollama/OpenAI-compatible hosts;
- consumer/browser sessions imported as API credentials;
- unreviewed model-generated shell/tool execution;
- cryptographically anonymous voting;
- replay guarantees for live stochastic inference.

See `HOWTO.md`, `docs/API.md`, `SECURITY.md`, and `docs/ARK_PROTOCOL.md` for operational details.
'''
write("docs/COMPATIBILITY.md", compatibility)

release_notes = '''# NEXUS 2.0.0 Release Notes

## Status

These are the final release-candidate notes for the intended `v2.0.0` bits. They become stable release notes only when the exact merged PR #51 commit passes the complete release/review gate and is tagged `v2.0.0`.

## What 2.0 is

NEXUS 2.0 is a local-first model-independent cognitive substrate: multiple heterogeneous model actors can deliberate through an equal-vote Council while durable state, evidence identity, verification, governance mechanics, games, civic state, social history, and recovery remain owned by the NEXUS runtime.

## Major surfaces

- equal-seat Six Hats Council with blind phase barriers, sealed ballot/reveal, exact two-thirds default consensus, minority reports, and consensus/evidence separation;
- Rust IRC-style operator TUI over local JSONL/stdio;
- deterministic/mock, loopback Ollama/LM Studio/AnythingLLM/OpenAI-compatible, and fixed-host xAI/OpenAI/Anthropic/Gemini/Groq/Together actor adapters;
- provider-neutral auth storage outside WorldStore and semantic prompts;
- World Modes and named-region operational geometry;
- Failsafe, Citizen Mode, Civic Due Process, Guardian/Anarchy, Action Awareness, Context Bottleneck, Compute Epochs, and constitutional amendment/civilization machinery;
- deterministic UN simulation, HERESY MUD, UNO, Monopoly, Australian 500, Blackjack, human-only DORK v2, NEXUS Life Paths, Long Shift, and Psyche-Out Chess;
- AI Progression & Civic Life plus Open Mic/culture, with history that never creates governance authority;
- replicated WorldStore Continuity, scrub/repair, verified Ark creation and non-destructive recovery;
- isolated synthetic Trap Base and passive Courtroom Stenographer domains;
- BBS Wall with append-only chronological social memory and tombstone moderation.

## Constitutional invariants

- one admitted ordinary Council member = one seat = one vote;
- provider/model prestige, parameter count, account tier, deployment type, tool access, compute epoch, or open/closed status does not change vote weight;
- Council consensus is not evidence status;
- progression/culture/game success/Citizenship/Wall history does not create extra authority;
- model output is untrusted input until admitted by the relevant runtime contract;
- credentials are operational secrets, not world knowledge;
- redundancy and archival survival do not promote claims to truth.

## Final feature: The BBS Wall

`#wall` is an intentionally low-stakes social surface. Plain room text becomes a Wall post rather than a Council question. `/ask` is blocked there. Posts are bounded, secret-scrubbed, immutable WorldStore events; moderation appends tombstones instead of silently rewriting history.

> **The Wall remembers speech. It does not turn speech into truth.**

## Hardening and independent audit

PR #49 created the eight-gate hardening harness. An independent Grok audit found R1-R12; surviving findings were fixed before the Wall and pinned as release-blocking regressions. PR #50 then passed the post-Wall matrix plus Codex review fixes. PR #51 reruns that complete contract against the exact intended stable tree.

## Upgrade / compatibility

See `docs/COMPATIBILITY.md`. Existing canonical object identity is preserved. WorldStore Continuity can baseline admitted legacy object history without changing object IDs. Ark restore is non-destructive and targets a new empty world.

## After stable

PR #52 adds runnable Lean 4 formal verification for selected constitutional/protocol invariants against the exact stable runtime. PR #53 freezes the reviewed proof sources, stable software identity, build/test records, hashes, reproduction instructions, and Zenodo DOI.
'''
write("docs/RELEASE_NOTES_2.0.0.md", release_notes)

checklist = '''# NEXUS 2.0 Stable Release Checklist

This checklist is intentionally stricter than “CI is green.” A hardening report verifies a candidate; it does not create release authority.

## Candidate identity

- [ ] PR #50 is merged and the release candidate descends from merge commit `1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b`.
- [ ] Runtime, Python package, Rust TUI, API docs, README, README4AI, and citation metadata identify intended version `2.0.0`.
- [ ] Control protocol remains deliberately identified as `nexus/0.14`.
- [ ] `release/release_candidate.json` matches the intended tag `v2.0.0` and still says `stable_release: false`.

## Documentation reconciliation

- [ ] `ARCHITECTURE.md` describes the implemented Rust TUI, provider federation, WorldStore Continuity/Ark, progression/culture, and BBS Wall.
- [ ] `SECURITY.md` and `THREAT_MODEL.md` describe the current adapter set and Wall/release threats rather than the xAI-only alpha slice.
- [ ] `CLAIMS.md` includes the Wall/progression/culture evidence boundary.
- [ ] `HOWTO.md` documents the current launcher, Wall, and Ark/recovery posture.
- [ ] `README.md` and strict-JSON `README4AI.md` pass their synchronization contract.
- [ ] `ROADMAP.md` and `docs/RELEASE_SEQUENCE.md` preserve #52 Lean / #53 Zenodo as post-stable phases.
- [ ] Historical `archives/v1.0.0/` material remains historical and is not rewritten to impersonate 2.0 documentation.

## Required automated gates

- [ ] candidate-tree pre-audit passes;
- [ ] exact eight-gate matrix audit passes and covers the release-candidate regression family;
- [ ] Grok PR #49 R1-R12 closure remains 12/12 pinned;
- [ ] full Python regression suite passes;
- [ ] 30/30 deterministic adversarial probes pass;
- [ ] Rust all-target tests pass under the pinned release-validation toolchain;
- [ ] `cargo check --all-targets` passes;
- [ ] `cargo fmt --check` passes;
- [ ] clean candidate archive completes `./nexus setup --nick ReleaseProbe -> doctor -> demo` under the allowlisted environment;
- [ ] post-run candidate-tree audit passes;
- [ ] no required check is failed, skipped, missing, or `not_run`.

## Runtime/recovery gates

- [ ] Wall default ephemeral runtime, Unicode/parser boundaries, chronology, tombstones, health, and authority separation regressions pass;
- [ ] representative progression/culture state survives verified Ark create/verify/restore and reconstructs from immutable restored history;
- [ ] Guardian/Failsafe/Citizenship/Trap/Stenographer authority boundaries remain green;
- [ ] provider/credential and fixed-destination tests remain green.

## Review gate

- [ ] PR #51 is reviewed on its exact current head;
- [ ] no unresolved substantive release-blocking review thread remains;
- [ ] any review fix has been revalidated by the complete exact-head matrix.

## Stable tag gate

Only when every item above is satisfied:

1. merge PR #51;
2. rerun/verify the complete matrix against the exact merged commit where applicable;
3. create tag `v2.0.0` pointing to that exact green commit;
4. create the stable GitHub release from the same tag/commit;
5. record the stable tag and commit for PR #52 Lean correspondence and PR #53 publication chain of custody.

> **Do not move the tag to make paperwork match. Make the paperwork match the tested commit.**
'''
write("docs/RELEASE_CHECKLIST.md", checklist)

audit_doc = '''# NEXUS 2.0 Documentation Reconciliation Audit

PR #51 treats stale canonical documentation as a release defect. This ledger distinguishes current documentation from deliberately historical material.

## Canonical root documents reviewed for 2.0

| Document | #51 disposition |
|---|---|
| `README.md` | release identity + final system surface reconciled |
| `README4AI.md` | strict JSON release identity + Wall/release contract reconciled |
| `ARCHITECTURE.md` | rewritten against actual post-#50 architecture |
| `SECURITY.md` | current local/cloud adapter set + Wall/stable-tag boundary |
| `THREAT_MODEL.md` | provider federation + Wall T49-T54 + release threat |
| `CLAIMS.md` | executable terminology + social/history evidence boundary |
| `COUNCIL.md` | current commitment claim + Wall/social-history boundary |
| `HOWTO.md` | current launcher + Wall + Ark/recovery posture |
| `ROADMAP.md` | #49/#50 complete; #51 current; #52 Lean; #53 Zenodo |
| `CHANGELOG.md` | 2.0 final-RC entry prepended; historical alpha entries retained |
| `CITATION.cff` | alpha0 documentation-only metadata replaced with 2.0 software metadata |

## Canonical feature/reference documents explicitly release-stamped

- `docs/API.md`
- `docs/OPERATOR_TOOLING.md`
- `docs/ARK_PROTOCOL.md`
- `docs/AI_PROGRESSION.md`
- `docs/AI_CULTURE.md`
- `docs/BBS_WALL.md`
- `docs/IRC_TUI.md`
- `docs/WORLD_PROTOCOL.md`
- `docs/NEXUS_2_HARDENING.md`
- `docs/RELEASE_SEQUENCE.md`

The release stamp does not rewrite feature history. It records that the feature is part of the reviewed 2.0 candidate and points release authority back to the exact #51 matrix/tag gate.

## New release documents

- `docs/COMPATIBILITY.md`
- `docs/RELEASE_NOTES_2.0.0.md`
- `docs/RELEASE_CHECKLIST.md`
- `release/release_candidate.json`

## Deliberately historical material

`archives/v1.0.0/` is an archival snapshot of the prior NEXUS generation. PR #51 does **not** edit those files to make old architecture look current. Historical changelog entries likewise retain the terminology/version state of their original milestones.

## Machine enforcement

`tests/test_release_candidate.py` rejects selected known stale canonical phrases and verifies version/citation/release-sequence/matrix coupling. Existing README, release-wiring, hardening, security, adversarial, Rust, WorldStore/Ark, Wall, and Grok-closure regressions provide the executable side of the documentation claim.
'''
write("docs/DOCUMENTATION_AUDIT_2.0.md", audit_doc)

# Add concise release-status stamps to feature/reference docs instead of
# rewriting their historical implementation detail.
status_notes = {
    "docs/OPERATOR_TOOLING.md": "> **NEXUS 2.0 release status:** included in the final PR #51 release candidate; `./nexus` is the implemented first-party launcher, not future work.",
    "docs/ARK_PROTOCOL.md": "> **NEXUS 2.0 release status:** WorldStore Continuity and the Ark recovery contract are stable-candidate surfaces and are rerun by the final release matrix.",
    "docs/AI_PROGRESSION.md": "> **NEXUS 2.0 release status:** AI Progression & Civic Life is included in the final candidate; contribution history remains non-authoritative.",
    "docs/AI_CULTURE.md": "> **NEXUS 2.0 release status:** Open Mic, Long Shift, and Psyche-Out Chess are included in the final candidate; culture creates history, not authority.",
    "docs/BBS_WALL.md": "> **NEXUS 2.0 release status:** PR #50 is merged; the Wall is the final 2.0 feature surface and remains social memory, not evidence.",
    "docs/IRC_TUI.md": "> **NEXUS 2.0 release status:** the Rust IRC-style TUI is implemented at version 2.0.0 in PR #51; it remains a replaceable operator shell over the Python runtime.",
    "docs/WORLD_PROTOCOL.md": "> **NEXUS 2.0 release status:** this protocol document is part of the final candidate; executable schemas/tests take precedence over historical planning language.",
    "docs/NEXUS_2_HARDENING.md": "> **Historical-to-final note:** PR #49 established the pre-Wall baseline. PR #51 reruns the same hardened contract as a final release-candidate profile scoped through merged PR #50.",
}
for path, note in status_notes.items():
    insert_status_note(path, note)

# ---------------------------------------------------------------------------
# Final release-candidate matrix and hardening report identity.
# ---------------------------------------------------------------------------
matrix_path = ROOT / "release" / "hardening_matrix.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
matrix.update(
    {
        "milestone": "PR #51",
        "profile": "final_release_candidate",
        "stable_release": False,
        "scope_through_pr": 50,
        "target_version": "2.0.0",
        "base_feature_merge": BASE_PR50_MERGE,
        "release_rule": "Only the exact merged PR #51 head may be tagged v2.0.0 after the complete release-candidate matrix passes with no unresolved release-blocking review findings.",
    }
)
matrix.pop("post_wall_rule", None)
release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
if "test_release_candidate.py" not in release_gate["patterns"]:
    release_gate["patterns"].append("test_release_candidate.py")
write("release/hardening_matrix.json", json.dumps(matrix, indent=2) + "\n")

runner = read("tools/nexus_release_hardening.py")
runner = runner.replace('"""NEXUS 2.0 pre-Wall release-hardening runner.\n\nPR #49 established the pre-Wall baseline. This runner remains the executable\nhardening contract carried forward through the pre-stable line. It audits the\nmatrix, runs the full regression/adversarial/Rust suite, rehearses operator\nbootstrap from a clean candidate archive, and emits a machine-readable report.\n\nThe output carries no governance, evidence, or release authority by itself.\n"""', '"""NEXUS 2.0 final release-candidate hardening runner.\n\nPR #49 established the pre-Wall baseline and the Grok audit strengthened it.\nPR #51 reruns that complete contract against the post-Wall feature surface,\nrehearses a clean operator archive, and emits a machine-readable candidate\nreport. The report verifies boundaries but carries no governance, evidence,\nor stable-release authority by itself.\n"""')
anchor = 'REQUIRED_GROK_FINDING_IDS = frozenset(f"R{index}" for index in range(1, 13))\n'
constants = '''EXPECTED_MATRIX_MILESTONE = "PR #51"\nEXPECTED_MATRIX_PROFILE = "final_release_candidate"\nEXPECTED_SCOPE_THROUGH_PR = 50\nTARGET_VERSION = "2.0.0"\nREQUIRED_RELEASE_RULE = (\n    "Only the exact merged PR #51 head may be tagged v2.0.0 after the complete "\n    "release-candidate matrix passes with no unresolved release-blocking review findings."\n)\n'''
if constants not in runner:
    runner = replace_once(runner, anchor, anchor + constants, label="runner constants anchor")
runner = runner.replace(
    '    if matrix.get("stable_release") is not False:\n        raise ValueError("pre-stable hardening matrix must not declare stable release")\n',
    '    if matrix.get("stable_release") is not False:\n        raise ValueError("release-candidate matrix must not self-declare stable release")\n    if matrix.get("milestone") != EXPECTED_MATRIX_MILESTONE:\n        raise ValueError("release-candidate milestone mismatch")\n    if matrix.get("profile") != EXPECTED_MATRIX_PROFILE:\n        raise ValueError("release-candidate profile mismatch")\n    if matrix.get("scope_through_pr") != EXPECTED_SCOPE_THROUGH_PR:\n        raise ValueError("release-candidate scope must include merged PR #50")\n    if matrix.get("target_version") != TARGET_VERSION:\n        raise ValueError("release-candidate target version mismatch")\n    if matrix.get("release_rule") != REQUIRED_RELEASE_RULE:\n        raise ValueError("release-candidate stable-tag rule mismatch")\n',
    1,
)
runner = runner.replace(
    '        f"{len(observed_rehearsals)} required rehearsals and 12/12 Grok findings pinned"\n',
    '        f"{len(observed_rehearsals)} required rehearsals and 12/12 Grok findings pinned; "\n        f"profile={EXPECTED_MATRIX_PROFILE} target={TARGET_VERSION} scope_through_pr={EXPECTED_SCOPE_THROUGH_PR}"\n',
    1,
)
runner = runner.replace('        "profile": "pre_wall",', '        "profile": EXPECTED_MATRIX_PROFILE,', 1)
runner = runner.replace(
    '        "stable_release": False,\n        "authority_effect": "none",',
    '        "target_version": TARGET_VERSION,\n        "scope_through_pr": EXPECTED_SCOPE_THROUGH_PR,\n        "stable_release": False,\n        "authority_effect": "none",',
    1,
)
runner = runner.replace(
    '        "post_wall_rule": "PR #51 must rerun the complete release-candidate matrix after PR #50 and verify 12/12 Grok PR49 findings remain closed",\n',
    '        "release_rule": REQUIRED_RELEASE_RULE,\n',
    1,
)
write("tools/nexus_release_hardening.py", runner)

hardening_test = read("tests/test_release_hardening.py")
hardening_test = hardening_test.replace(
    "def test_hardening_matrix_is_pre_wall_and_cannot_declare_stable_release(self) -> None:",
    "def test_hardening_matrix_is_final_release_candidate_and_cannot_self_declare_stable(self) -> None:",
)
hardening_test = hardening_test.replace('self.assertEqual(matrix["milestone"], "PR #49")', 'self.assertEqual(matrix["milestone"], "PR #51")')
hardening_test = hardening_test.replace('self.assertEqual(matrix["profile"], "pre_wall")', 'self.assertEqual(matrix["profile"], "final_release_candidate")')
hardening_test = hardening_test.replace('self.assertIn("PR #51", matrix["post_wall_rule"])', 'self.assertEqual(matrix["scope_through_pr"], 50)\n        self.assertEqual(matrix["target_version"], "2.0.0")\n        self.assertIn("exact merged PR #51 head", matrix["release_rule"])\n        self.assertIn("v2.0.0", matrix["release_rule"])')
write("tests/test_release_hardening.py", hardening_test)

workflow = read(".github/workflows/release-hardening.yml")
workflow = workflow.replace("name: NEXUS 2.0 release hardening", "name: NEXUS 2.0 release candidate")
workflow = workflow.replace("  pre-wall-hardening:", "  release-candidate-hardening:")
workflow = workflow.replace("      - 'nexus'\n", "      - 'nexus'\n      - '*.md'\n      - 'CITATION.cff'\n      - 'docs/**'\n")
workflow = workflow.replace("- name: Run pre-stable hardening matrix", "- name: Run final release-candidate matrix")
write(".github/workflows/release-hardening.yml", workflow)

release_candidate = {
    "schema": "nexus-release-candidate/1",
    "target_version": "2.0.0",
    "target_tag": "v2.0.0",
    "protocol": "nexus/0.14",
    "base_feature_pr": 50,
    "base_feature_merge": BASE_PR50_MERGE,
    "candidate_pr": 51,
    "profile": "final_release_candidate",
    "stable_release": False,
    "authority_effect": "none",
    "required_workflows": [
        "README dual-surface contract",
        "Python mock runtime tests",
        "Rust IRC TUI tests",
        "NEXUS security regression",
        "NEXUS adversarial gauntlet",
        "NEXUS 2.0 release candidate",
    ],
    "external_audit_closure": {
        "source": "Grok PR #49 audit 311160d1",
        "required_findings": [f"R{i}" for i in range(1, 13)],
        "required_status": "closed_and_regression_pinned",
    },
    "stable_tag_rule": "Tag v2.0.0 only from the exact merged PR #51 commit after all required workflows and release-blocking review findings are green/closed.",
    "post_stable": {
        "pr_52": "Lean 4 Formal Verification",
        "pr_53": "Formalization + Reproducibility + Zenodo Publication",
    },
}
write("release/release_candidate.json", json.dumps(release_candidate, indent=2) + "\n")

release_candidate_test = r'''from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from nexus_runtime import PROTOCOL_VERSION, RUNTIME_VERSION

ROOT = Path(__file__).resolve().parents[1]


class NEXUS20ReleaseCandidateTests(unittest.TestCase):
    def test_intended_stable_version_is_aligned_without_self_declaring_release(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "tui" / "Cargo.toml").read_text(encoding="utf-8"))
        manifest = json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))

        self.assertEqual(PROTOCOL_VERSION, "nexus/0.14")
        self.assertEqual(RUNTIME_VERSION, "2.0.0")
        self.assertEqual(pyproject["project"]["version"], "2.0.0")
        self.assertEqual(cargo["package"]["version"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["runtime"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["python_package"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["rust_tui"], "2.0.0")
        self.assertEqual(manifest["release_identity"]["release_posture"], "release_candidate")
        self.assertFalse(manifest["release_identity"]["stable_2_0"])
        self.assertFalse(manifest["stable_2_0"]["declared"])
        self.assertFalse(candidate["stable_release"])
        self.assertFalse(matrix["stable_release"])
        self.assertEqual(candidate["target_tag"], "v2.0.0")

    def test_release_candidate_is_exactly_post_wall_and_preserves_future_formalization_sequence(self) -> None:
        candidate = json.loads((ROOT / "release" / "release_candidate.json").read_text(encoding="utf-8"))
        sequence = (ROOT / "docs" / "RELEASE_SEQUENCE.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertEqual(candidate["base_feature_pr"], 50)
        self.assertEqual(candidate["base_feature_merge"], "1bc078ed266e7fac02d6f905f8ddd0c9061c1d8b")
        self.assertEqual(candidate["candidate_pr"], 51)
        self.assertIn("PR #50 — The BBS Wall — MERGED", sequence)
        self.assertIn("PR #52 — Lean 4 Formal Verification", sequence)
        self.assertIn("PR #53 — Formalization + Reproducibility + Zenodo Publication", sequence)
        self.assertIn("LEAN 4 FORMAL VERIFICATION - PR #52", roadmap)
        self.assertIn("ZENODO - PR #53", roadmap)

    def test_canonical_docs_do_not_retain_known_alpha_architecture_fossils(self) -> None:
        architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        threat = (ROOT / "THREAT_MODEL.md").read_text(encoding="utf-8")
        claims = (ROOT / "CLAIMS.md").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

        self.assertNotIn("future RUST TUI", architecture)
        self.assertNotIn("Rust CLI/TUI (future)", architecture)
        self.assertNotIn("xAI is the first fixed-destination remote adapter", architecture)
        self.assertNotIn("xAI is the first admitted remote adapter", security)
        self.assertNotIn("remote providers other than xAI", threat)
        self.assertNotIn("when the executable protocol is implemented", claims)
        self.assertNotIn("version: 2.0.0-alpha0", citation)
        self.assertNotIn("documentation-only", citation)
        self.assertIn("version: 2.0.0", citation)
        self.assertIn("## BBS Wall", architecture)
        self.assertIn("### T54 — Release paperwork declares stable without the tested stable head", threat)

    def test_release_matrix_is_final_rc_scoped_through_wall_and_covers_contract(self) -> None:
        matrix = json.loads((ROOT / "release" / "hardening_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["milestone"], "PR #51")
        self.assertEqual(matrix["profile"], "final_release_candidate")
        self.assertEqual(matrix["scope_through_pr"], 50)
        self.assertEqual(matrix["target_version"], "2.0.0")
        self.assertFalse(matrix["stable_release"])
        release_gate = next(g for g in matrix["gates"] if g["id"] == "release_composition")
        self.assertIn("test_wall*.py", release_gate["patterns"])
        self.assertIn("test_release_candidate.py", release_gate["patterns"])
        self.assertEqual(set(matrix["external_audit_closure"]["finding_ids"]), {f"R{i}" for i in range(1, 13)})

    def test_release_docs_and_wall_claims_are_coupled(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        ai = json.loads((ROOT / "README4AI.md").read_text(encoding="utf-8"))
        notes = (ROOT / "docs" / "RELEASE_NOTES_2.0.0.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("status:          release candidate", readme)
        self.assertEqual(ai["bbs_wall"]["evidence_effect"], "none")
        self.assertEqual(ai["bbs_wall"]["authority_effect"], "none")
        self.assertIn("social memory", notes)
        self.assertIn("no unresolved substantive release-blocking review thread", checklist)


if __name__ == "__main__":
    unittest.main()
'''
write("tests/test_release_candidate.py", release_candidate_test)

# Final guard: the builder itself should fail if obvious stale release identity
# survives in the canonical current surfaces it is responsible for.
for path in (
    "README.md",
    "README4AI.md",
    "ARCHITECTURE.md",
    "docs/API.md",
    "CITATION.cff",
):
    text = read(path)
    if "2.0.0-alpha10.3" in text or "2.0.0a10.post3" in text:
        raise RuntimeError(f"{path}: stale alpha10.3 release identity survived")
