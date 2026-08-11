# NEXUS 2.0.0 Release Notes

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
