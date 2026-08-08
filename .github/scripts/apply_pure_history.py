from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor exactly once, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Runtime mode registry: stricter sibling, same Archive region.
replace_once(
    "src/nexus_runtime/modes.py",
    '''    "cultural": WorldMode(\n''',
    '''    "pure_history": WorldMode(\n        mode_id="pure_history",\n        label="Pure History / No Ancient Aliens",\n        description="Source-forensic history that separates attestation, chronology, interpretation, retelling, and speculation.",\n        prompt_instruction=(\n            "Reason as a source-forensic historian. Separate primary or near-primary source attestation, chronology, "\n            "and provenance from later interpretation, transmission, modern retelling, pop-history media, and unsupported "\n            "speculation. A mythic, religious, or literary text is historical evidence that a text or tradition existed and "\n            "said something; it is not automatically evidence that the narrated event occurred as described. Do not answer "\n            "with model autobiography, media-consumption disclaimers, or appeals to being trained on the topic. If evidence "\n            "is insufficient, state exactly what source evidence is missing and give the narrowest conclusion supported."\n        ),\n        region_id="archive",\n    ),\n    "cultural": WorldMode(\n''',
)

# Coordinator: apply the narrow Pure History retry only in pure_history.
replace_once(
    "src/nexus_runtime/council.py",
    "from .guard import EqualityGuard\n",
    "from .guard import EqualityGuard\nfrom .history_guard import PureHistoryGuard\n",
)
replace_once(
    "src/nexus_runtime/council.py",
    "        guard: EqualityGuard | None = None,\n        scrubber: SecretScrubber | None = None,\n",
    "        guard: EqualityGuard | None = None,\n        history_guard: PureHistoryGuard | None = None,\n        scrubber: SecretScrubber | None = None,\n",
)
replace_once(
    "src/nexus_runtime/council.py",
    "        self.guard = guard or EqualityGuard()\n        self.scrubber = scrubber or SecretScrubber()\n",
    "        self.guard = guard or EqualityGuard()\n        self.history_guard = history_guard or PureHistoryGuard()\n        self.scrubber = scrubber or SecretScrubber()\n",
)
old_collect = '''    def _collect_guarded(self, actor: CouncilActor, context: PhaseContext) -> tuple[str, list[str]]:\n        first = actor.respond(context)\n        inspected = self.guard.inspect(first)\n        if not inspected.flagged:\n            return first, []\n\n        events = [inspected.reason or "identity_based_authority_claim"]\n        retry_context = PhaseContext(\n            session_id=context.session_id,\n            phase=context.phase,\n            question=context.question,\n            evidence_snapshot_ref=context.evidence_snapshot_ref,\n            completed_phases=context.completed_phases,\n            guard_nudge=inspected.nudge,\n            mode_id=context.mode_id,\n            mode_instruction=context.mode_instruction,\n            geometry_region_id=context.geometry_region_id,\n            evidence_context=context.evidence_context,\n        )\n        second = actor.respond(retry_context)\n        inspected_again = self.guard.inspect(second)\n        if inspected_again.flagged:\n            events.append("repeated_identity_based_authority_claim")\n            return "Contribution withheld pending evidence-based restatement.", events\n        events.append("restated_after_nudge")\n        return second, events\n'''
new_collect = '''    def _collect_guarded(self, actor: CouncilActor, context: PhaseContext) -> tuple[str, list[str]]:\n        content = actor.respond(context)\n        events: list[str] = []\n\n        inspected = self.guard.inspect(content)\n        if inspected.flagged:\n            events.append(inspected.reason or "identity_based_authority_claim")\n            retry_context = PhaseContext(\n                session_id=context.session_id,\n                phase=context.phase,\n                question=context.question,\n                evidence_snapshot_ref=context.evidence_snapshot_ref,\n                completed_phases=context.completed_phases,\n                guard_nudge=inspected.nudge,\n                mode_id=context.mode_id,\n                mode_instruction=context.mode_instruction,\n                geometry_region_id=context.geometry_region_id,\n                evidence_context=context.evidence_context,\n            )\n            content = actor.respond(retry_context)\n            inspected_again = self.guard.inspect(content)\n            if inspected_again.flagged:\n                events.append("repeated_identity_based_authority_claim")\n                return "Contribution withheld pending evidence-based restatement.", events\n            events.append("restated_after_nudge")\n\n        if context.mode_id != "pure_history":\n            return content, events\n\n        history = self.history_guard.inspect(content)\n        if not history.flagged:\n            return content, events\n\n        events.append(history.reason or "pure_history_model_autobiography")\n        retry_context = PhaseContext(\n            session_id=context.session_id,\n            phase=context.phase,\n            question=context.question,\n            evidence_snapshot_ref=context.evidence_snapshot_ref,\n            completed_phases=context.completed_phases,\n            guard_nudge=history.nudge,\n            mode_id=context.mode_id,\n            mode_instruction=context.mode_instruction,\n            geometry_region_id=context.geometry_region_id,\n            evidence_context=context.evidence_context,\n        )\n        restated = actor.respond(retry_context)\n        history_again = self.history_guard.inspect(restated)\n        if history_again.flagged:\n            events.append("repeated_pure_history_model_autobiography")\n            return "Contribution withheld pending source-focused historical restatement.", events\n        events.append("restated_after_pure_history_nudge")\n        return restated, events\n'''
replace_once("src/nexus_runtime/council.py", old_collect, new_collect)

# The sealed ballot gets the same mode contract as the six hats.
replace_once(
    "src/nexus_runtime/adapters/ollama.py",
    '            f"World mode: {context.mode_id}\\n"\n            f"Geometry region: {context.geometry_region_id}\\n"\n',
    '            f"World mode: {context.mode_id}\\n"\n            f"Mode guidance: {context.mode_instruction}\\n"\n            f"Geometry region: {context.geometry_region_id}\\n"\n',
)

# Deterministic fixtures should make the new mode visible in fast CI.
replace_once(
    "src/nexus_runtime/mock.py",
    '            "historical": "Mode note: preserve chronology, sources, and change over time.",\n',
    '            "historical": "Mode note: preserve chronology, sources, and change over time.",\n            "pure_history": "Mode note: separate source attestation, chronology, later interpretation, modern retelling, and speculation.",\n',
)

# Public protocol/runtime identifiers.
replace_once("src/nexus_runtime/api.py", 'PROTOCOL_VERSION = "nexus/0.7"', 'PROTOCOL_VERSION = "nexus/0.8"')
replace_once("src/nexus_runtime/api.py", 'RUNTIME_VERSION = "2.0.0-alpha6.3"', 'RUNTIME_VERSION = "2.0.0-alpha6.4"')

# IRC/TUI room. No geometry bump: both history modes intentionally share Archive.
replace_once("tui/src/lib.rs", "pub const ROOMS: [RoomSpec; 6] = [", "pub const ROOMS: [RoomSpec; 7] = [")
replace_once(
    "tui/src/lib.rs",
    '''    RoomSpec {\n        channel: "#agora",\n''',
    '''    RoomSpec {\n        channel: "#pure-history",\n        mode_id: "pure_history",\n        region_id: "archive",\n        label: "Archive / Pure History — No Ancient Aliens",\n    },\n    RoomSpec {\n        channel: "#agora",\n''',
)
replace_once(
    "tui/src/main.rs",
    "*** NEXUS 2.0 alpha6.3 IRC/TUI — local room, no IRC server",
    "*** NEXUS 2.0 alpha6.4 IRC/TUI — local room, no IRC server",
)

# Existing mode/geometry tests: registry changes; topology does not.
replace_once(
    "tests/test_modes_geometry.py",
    '{"analytical", "historical", "cultural", "meme_casual", "game_un", "game_mud"},',
    '{"analytical", "historical", "pure_history", "cultural", "meme_casual", "game_un", "game_mud"},',
)
# Same literal appears in API registry assertion as well.
replace_once(
    "tests/test_modes_geometry.py",
    '{"analytical", "historical", "cultural", "meme_casual", "game_un", "game_mud"},',
    '{"analytical", "historical", "pure_history", "cultural", "meme_casual", "game_un", "game_mud"},',
)
replace_once(
    "tests/test_modes_geometry.py",
    '        self.assertEqual(get_mode("historical").region_id, "archive")\n',
    '        self.assertEqual(get_mode("historical").region_id, "archive")\n        self.assertEqual(get_mode("pure_history").region_id, "archive")\n',
)

# Ballot mode guidance must be carried through, not just phase prompts.
replace_once(
    "tests/test_adapters.py",
    '        self.assertIn("World mode: meme_casual", transport.last_prompt or "")\n        self.assertIn("Geometry region: commons", transport.last_prompt or "")\n',
    '        self.assertIn("World mode: meme_casual", transport.last_prompt or "")\n        self.assertIn("Mode guidance: Allow playful framing while preserving claim boundaries.", transport.last_prompt or "")\n        self.assertIn("Geometry region: commons", transport.last_prompt or "")\n',
)

# README: status, public mode table, dedicated section, documentation map.
replace_once(
    "README.md",
    "- explicit game rooms: **`#un-sim`** and the cursed multi-avatar **`#mud`**.\n",
    "- explicit game rooms: **`#un-sim`** and the cursed multi-avatar **`#mud`**;\n- **Pure History Mode — No Ancient Aliens Edition** for source-forensic historical deliberation.\n",
)
replace_once("README.md", "protocol: nexus/0.7", "protocol: nexus/0.8")
replace_once("README.md", "runtime version: 2.0.0-alpha6.3", "runtime version: 2.0.0-alpha6.4")
replace_once(
    "README.md",
    "world modes: analytical / historical / cultural / meme_casual / game_un / game_mud",
    "world modes: analytical / historical / pure_history / cultural / meme_casual / game_un / game_mud",
)
replace_once(
    "README.md",
    "| `historical` | Archive / `#archive` | chronology, source context, change over time |\n",
    "| `historical` | Archive / `#archive` | chronology, source context, change over time |\n| `pure_history` | Archive / `#pure-history` | source-forensic history; no myth/retelling/speculation promotion |\n",
)
replace_once(
    "README.md",
    "| `game_un` | Assembly Hall / `#un-sim` | fictional UN-style strategy game, crises, Risk-like state and memes |\n",
    "| `game_un` | Assembly Hall / `#un-sim` | fictional UN-style strategy game, crises, Risk-like state and memes |\n| `game_mud` | Dungeon / `#mud` | deterministic multi-avatar HERESY MUD |\n",
)
replace_once(
    "README.md",
    "## `#mud` — HERESY MUD\n",
    '''## `#pure-history` — No Ancient Aliens Edition\n\nPure History is a stricter sibling of ordinary Historical Mode. Both occupy the Archive region, but `pure_history` forces source categories to stay separate: primary/near-primary attestation, chronology and provenance, later interpretation, modern retelling, and unsupported speculation.\n\nA mythic or literary text is evidence that a text/tradition existed and said something; it is not automatically evidence that the narrated event occurred. Small models that evade the task with chatbot autobiography such as “As a Large Language Model…” receive one deterministic source-discipline retry. This guard does not decide historical truth or alter voting authority.\n\n```text\n/join #pure-history\n/topic I heard the Anunnaki totally had sex with human women and bore giants. Is that historically supported?\n/ask\n```\n\n> **Same archive. Stricter source discipline. Same vote.**\n\nSee [`docs/PURE_HISTORY.md`](docs/PURE_HISTORY.md).\n\n## `#mud` — HERESY MUD\n''',
)
replace_once(
    "README.md",
    "- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — World Modes and named-region geometry\n",
    "- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — World Modes and named-region geometry\n- [`docs/PURE_HISTORY.md`](docs/PURE_HISTORY.md) — source-forensic `#pure-history` mode and discipline guard\n",
)

# API docs: mode registry changed; geometry identity intentionally unchanged.
replace_once("docs/API.md", "nexus/0.7", "nexus/0.8")
replace_once("docs/API.md", "2.0.0-alpha6.3", "2.0.0-alpha6.4")
replace_once(
    "docs/API.md",
    "historical  -> Archive\n",
    "historical   -> Archive / #archive\npure_history -> Archive / #pure-history\n",
)
replace_once(
    "docs/API.md",
    "A mode changes framing/context only. It does not change vote weight, evidence state, verification, secret handling, Equality Guard behavior, or consensus thresholds.\n",
    "A mode changes framing/context only. It does not change vote weight, evidence state, verification, secret handling, Equality Guard behavior, or consensus thresholds. `pure_history` additionally applies a narrow retry guard only to chatbot-autobiography/media-habit evasions; it does not adjudicate historical truth.\n\nSee [`PURE_HISTORY.md`](PURE_HISTORY.md) for the source-discipline contract.\n",
)

# Modes/geometry docs: same Archive coordinate, no named-regions-v4 churn.
replace_once(
    "docs/MODES_GEOMETRY.md",
    "Historical Mode does not grant the model a hidden historical database. Its claims still depend on supplied or retrieved evidence.\n\n### Cultural — Agora\n",
    '''Historical Mode does not grant the model a hidden historical database. Its claims still depend on supplied or retrieved evidence.\n\n### Pure History / No Ancient Aliens — Archive\n\n`pure_history` is a stricter source-forensic sibling of Historical Mode. It deliberately maps to the **same Archive region** because mode and geometry are separate contracts.\n\nActors must distinguish primary or near-primary attestation, chronology and provenance, later interpretation/transmission, modern retelling, and unsupported speculation. Mythic/literary texts may be historical evidence for the existence and content of a tradition without automatically establishing that the narrated event occurred.\n\nPure History also rejects chatbot autobiography as a substitute for analysis. A contribution such as “As a Large Language Model, I don't watch television” receives one narrow deterministic restatement request. This does not rank historical interpretations or change Council authority.\n\nSee [`PURE_HISTORY.md`](PURE_HISTORY.md).\n\n### Cultural — Agora\n''',
)
replace_once(
    "docs/MODES_GEOMETRY.md",
    "- every built-in mode maps to exactly one region;\n",
    "- every built-in mode maps to exactly one region, while multiple modes may intentionally share a region (for example `historical` and `pure_history` both map to Archive);\n",
)

print("Applied Pure History integration patches.")
