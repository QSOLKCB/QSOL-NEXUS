from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected anchor exactly once, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, expected: int) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected anchor {expected} times, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new), encoding="utf-8")


# ---------------------------------------------------------------------------
# Python Council runtime
# ---------------------------------------------------------------------------
replace_once(
    "src/nexus_runtime/council.py",
    "from .geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry\nfrom .guard import EqualityGuard\nfrom .history_guard import PureHistoryGuard\n",
    "from .failsafe import ActorFailsafe\nfrom .geometry import DEFAULT_WORLD_GEOMETRY, WorldGeometry\nfrom .guard import EqualityGuard\nfrom .history_guard import PureHistoryGuard\n",
)
replace_once(
    "src/nexus_runtime/council.py",
    "from .types import BallotRecord, CouncilPolicy, PHASE_ORDER, Phase, PhaseContext, PhaseSubmission\n",
    "from .types import Ballot, BallotRecord, CouncilPolicy, PHASE_ORDER, Phase, PhaseContext, PhaseSubmission\n",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        max_parallel_workers: int = DEFAULT_COUNCIL_PARALLEL_WORKERS,\n        history_guard: PureHistoryGuard | None = None,\n    ) -> None:\n""",
    """        max_parallel_workers: int = DEFAULT_COUNCIL_PARALLEL_WORKERS,\n        history_guard: PureHistoryGuard | None = None,\n        failsafe: ActorFailsafe | None = None,\n    ) -> None:\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        self.guard = guard or EqualityGuard()\n        self.history_guard = history_guard or PureHistoryGuard()\n        self.scrubber = scrubber or SecretScrubber()\n        self.geometry = geometry or DEFAULT_WORLD_GEOMETRY\n""",
    """        self.guard = guard or EqualityGuard()\n        self.history_guard = history_guard or PureHistoryGuard()\n        self.scrubber = scrubber or SecretScrubber()\n        self.geometry = geometry or DEFAULT_WORLD_GEOMETRY\n        self.failsafe = failsafe or ActorFailsafe(\n            world,\n            guard=self.guard,\n            history_guard=self.history_guard,\n        )\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        actors = tuple(actors)\n        self._validate_roster(actors)\n        mode = get_mode(mode_id)\n""",
    """        requested_actors = tuple(actors)\n        self._validate_roster(requested_actors)\n        failsafe_state_by_member = {\n            actor.member.member_id: self.failsafe.state_ref(actor.member.member_id)\n            for actor in requested_actors\n        }\n        effective_actors: list[CouncilActor] = []\n        preexisting_replacements: list[dict] = []\n        for actor in requested_actors:\n            effective, replacement = self.failsafe.actor_for_run(actor)\n            effective_actors.append(effective)\n            if replacement is not None:\n                preexisting_replacements.append(replacement)\n        actors = tuple(effective_actors)\n        self._validate_roster(actors)\n        mode = get_mode(mode_id)\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """                    \"epistemic_privilege\": actor.member.epistemic_privilege,\n                    \"actor_metadata\": metadata,\n                }\n""",
    """                    \"epistemic_privilege\": actor.member.epistemic_privilege,\n                    \"actor_metadata\": metadata,\n                    \"failsafe_state_ref\": failsafe_state_by_member.get(actor.member.member_id),\n                }\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            \"roster\": roster,\n            \"policy\": self._policy_dict(),\n        }\n""",
    """            \"roster\": roster,\n            \"policy\": self._policy_dict(),\n            \"failsafe_policy\": self.failsafe.policy_dict(),\n        }\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        completed: dict[str, dict[str, str]] = {}\n        phase_records: dict[str, list[dict]] = {}\n        guard_events: list[dict] = []\n\n        for phase in PHASE_ORDER:\n""",
    """        completed: dict[str, dict[str, str]] = {}\n        phase_records: dict[str, list[dict]] = {}\n        guard_events: list[dict] = []\n        failsafe_outcomes: list[dict] = []\n        failsafe_attempts: dict[str, int] = {}\n        contained_members: set[str] = set()\n        actor_by_member = {actor.member.member_id: actor for actor in actors}\n\n        for phase in PHASE_ORDER:\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            def collect_phase(actor: CouncilActor) -> tuple[str, str, dict, list[str]]:\n                context = PhaseContext(\n""",
    """            def collect_phase(actor: CouncilActor) -> tuple[str, str, dict, list[str]]:\n                if actor.member.member_id in contained_members:\n                    content = self.failsafe.contained_submission(actor.member.member_id)\n                    member_guard_events = [\"failsafe_contained\"]\n                    record = {\n                        \"member_id\": actor.member.member_id,\n                        \"phase\": phase.value,\n                        \"content\": content,\n                        \"guard_events\": list(member_guard_events),\n                    }\n                    return actor.member.member_id, content, record, member_guard_events\n\n                context = PhaseContext(\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            current: dict[str, str] = {}\n            records: list[dict] = []\n            for member_id, content, record, member_guard_events in self._ordered_parallel_map(actors, collect_phase):\n                current[member_id] = content\n                records.append(record)\n                for event in member_guard_events:\n                    guard_events.append({\"member_id\": member_id, \"phase\": phase.value, \"event\": event})\n\n            completed[phase.value] = current\n            phase_records[phase.value] = records\n""",
    """            current: dict[str, str] = {}\n            records: list[dict] = []\n            phase_triggers: list[tuple[str, str]] = []\n            for member_id, content, record, member_guard_events in self._ordered_parallel_map(actors, collect_phase):\n                current[member_id] = content\n                records.append(record)\n                for event in member_guard_events:\n                    guard_events.append({\"member_id\": member_id, \"phase\": phase.value, \"event\": event})\n                trigger_reason = self.failsafe.trigger_reason(member_guard_events)\n                if trigger_reason is not None:\n                    phase_triggers.append((member_id, trigger_reason))\n\n            completed[phase.value] = current\n            phase_records[phase.value] = records\n\n            if self.failsafe.policy.enabled:\n                for member_id, trigger_reason in phase_triggers:\n                    actor = actor_by_member[member_id]\n                    attempts = failsafe_attempts.get(member_id, 0)\n                    if attempts < self.failsafe.policy.max_rehabilitations_per_session:\n                        failsafe_attempts[member_id] = attempts + 1\n                        outcome = self.failsafe.rehabilitate(\n                            actor,\n                            trigger_reason=trigger_reason,\n                            mode_id=mode.mode_id,\n                            mode_instruction=mode.prompt_instruction,\n                            geometry_region_id=region.region_id,\n                        )\n                    else:\n                        outcome = self.failsafe.shadow_reoffender(\n                            actor,\n                            trigger_reason=trigger_reason,\n                        )\n                    failsafe_outcomes.append(outcome)\n                    if outcome[\"status\"] == \"shadow_realm\":\n                        contained_members.add(member_id)\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            geometry_region_id=region.region_id,\n            evidence_context=evidence_context,\n        )\n        result = self._tally(ballots, evidence_state)\n""",
    """            geometry_region_id=region.region_id,\n            evidence_context=evidence_context,\n            contained_members=frozenset(contained_members),\n        )\n        result = self._tally(ballots, evidence_state)\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        telemetry = build_council_telemetry(phase_records, revealed_ballots, result)\n\n        session_payload = {\n""",
    """        telemetry = build_council_telemetry(phase_records, revealed_ballots, result)\n        failsafe_summary = {\n            \"schema_version\": self.failsafe.policy_dict()[\"schema_version\"],\n            \"policy\": self.failsafe.policy_dict(),\n            \"preexisting_replacements\": preexisting_replacements,\n            \"outcomes\": failsafe_outcomes,\n            \"contained_at_ballot\": sorted(contained_members),\n        }\n\n        session_payload = {\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            \"result\": result,\n            \"telemetry\": telemetry,\n        }\n""",
    """            \"result\": result,\n            \"telemetry\": telemetry,\n            \"failsafe\": failsafe_summary,\n        }\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """                \"input_refs\": [question_obj.object_id, evidence.object_id, presence.object_id],\n                \"result_ref\": session_obj.object_id,\n                \"replayable\": execution_replayable,\n                \"protocol\": \"nexus/0.5\",\n""",
    """                \"input_refs\": [question_obj.object_id, evidence.object_id, presence.object_id]\n                + [ref for ref in failsafe_state_by_member.values() if ref is not None],\n                \"result_ref\": session_obj.object_id,\n                \"replayable\": execution_replayable,\n                \"protocol\": \"nexus/0.6\",\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """            \"result\": result,\n            \"telemetry\": telemetry,\n        }\n\n    def build_evidence_context\n""",
    """            \"result\": result,\n            \"telemetry\": telemetry,\n            \"failsafe\": failsafe_summary,\n        }\n\n    def build_evidence_context\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        geometry_region_id: str,\n        evidence_context: str,\n    ) -> tuple[BallotRecord, ...]:\n""",
    """        geometry_region_id: str,\n        evidence_context: str,\n        contained_members: frozenset[str] = frozenset(),\n    ) -> tuple[BallotRecord, ...]:\n""",
)
replace_once(
    "src/nexus_runtime/council.py",
    """        def collect_ballot(actor: CouncilActor) -> BallotRecord:\n            context = PhaseContext(\n""",
    """        def collect_ballot(actor: CouncilActor) -> BallotRecord:\n            if actor.member.member_id in contained_members:\n                choice = Ballot.UNDERDETERMINED\n                rationale = (\n                    \"NEXUS FAILSAFE: actor contained after a repeated procedural guard violation; \"\n                    \"no model-generated ballot was accepted.\"\n                )\n                commitment = sha256_ref(\n                    \"ballot\",\n                    {\n                        \"session_id\": session_id,\n                        \"member_id\": actor.member.member_id,\n                        \"choice\": choice.value,\n                        \"rationale\": rationale,\n                    },\n                )\n                return BallotRecord(actor.member.member_id, choice, rationale, commitment)\n\n            context = PhaseContext(\n""",
)

# ---------------------------------------------------------------------------
# Control API
# ---------------------------------------------------------------------------
replace_once(
    "src/nexus_runtime/api.py",
    "from .council import CouncilCoordinator\n",
    "from .council import CouncilCoordinator\nfrom .failsafe import FAILSAFE_SCHEMA_VERSION\n",
)
replace_once(
    "src/nexus_runtime/api.py",
    'PROTOCOL_VERSION = "nexus/0.8"\nRUNTIME_VERSION = "2.0.0-alpha6.4"\n',
    'PROTOCOL_VERSION = "nexus/0.9"\nRUNTIME_VERSION = "2.0.0-alpha6.6"\n',
)
replace_once(
    "src/nexus_runtime/api.py",
    """                    \"telemetry\": {\"schema_version\": TELEMETRY_SCHEMA_VERSION, \"role\": \"observational_only\"},\n                    \"games\": [\n""",
    """                    \"telemetry\": {\"schema_version\": TELEMETRY_SCHEMA_VERSION, \"role\": \"observational_only\"},\n                    \"failsafe\": self.council.failsafe.policy_dict(),\n                    \"games\": [\n""",
)
replace_once(
    "src/nexus_runtime/api.py",
    '                        "telemetry.verify",\n                        "game.un.catalog",\n',
    '                        "telemetry.verify",\n                        "failsafe.status",\n                        "game.un.catalog",\n',
)
replace_once(
    "src/nexus_runtime/api.py",
    """            elif operation == \"game.un.catalog\":\n""",
    """            elif operation == \"failsafe.status\":\n                member_id = request.get(\"member_id\")\n                if member_id is not None and (not isinstance(member_id, str) or not member_id.strip()):\n                    raise ValueError(\"member_id must be non-empty text when supplied\")\n                response = {\n                    \"status\": \"ok\",\n                    \"schema_version\": FAILSAFE_SCHEMA_VERSION,\n                    **self.council.failsafe.status_snapshot(member_id),\n                }\n            elif operation == \"game.un.catalog\":\n""",
)

# ---------------------------------------------------------------------------
# Rust TUI display-only integration
# ---------------------------------------------------------------------------
replace_once(
    "tui/src/main.rs",
    'app.append("*** NEXUS TUI 2.0 alpha6.5 — local room, no IRC server");',
    'app.append("*** NEXUS TUI 2.0 alpha6.6 — local room, no IRC server");',
)
replace_once(
    "tui/src/main.rs",
    """            self.append(\n                \"*** Entropy/diversity are not truth, confidence, quality, evidence status, or vote weight.\"\n            );\n        }\n        Ok(())\n    }\n""",
    """            self.append(\n                \"*** Entropy/diversity are not truth, confidence, quality, evidence status, or vote weight.\"\n            );\n        }\n        if let Some(failsafe) = payload.get(\"failsafe\").and_then(Value::as_object) {\n            let replacements = failsafe\n                .get(\"preexisting_replacements\")\n                .and_then(Value::as_array)\n                .cloned()\n                .unwrap_or_default();\n            let outcomes = failsafe\n                .get(\"outcomes\")\n                .and_then(Value::as_array)\n                .cloned()\n                .unwrap_or_default();\n            if !replacements.is_empty() || !outcomes.is_empty() {\n                self.append(\"--- NEXUS FAILSAFE // UPSIDE DOWN ---\");\n            }\n            for replacement in replacements {\n                let member = replacement.get(\"member_id\").and_then(Value::as_str).unwrap_or(\"?\");\n                let model = replacement\n                    .get(\"replacement_model_id\")\n                    .and_then(Value::as_str)\n                    .unwrap_or(\"?\");\n                self.append(&format!(\n                    \"*** {member}: SHADOW REALM ACTIVE; Council seat operated by {model}\"\n                ));\n            }\n            for outcome in outcomes {\n                let member = outcome.get(\"member_id\").and_then(Value::as_str).unwrap_or(\"?\");\n                if let Some(lines) = outcome.get(\"theatre\").and_then(Value::as_array) {\n                    for line in lines.iter().filter_map(Value::as_str) {\n                        self.append(&format!(\"*** {member}: {line}\"));\n                    }\n                }\n                let status = outcome.get(\"status\").and_then(Value::as_str).unwrap_or(\"?\");\n                self.append(&format!(\"*** {member}: FAILSAFE STATUS = {status}\"));\n            }\n        }\n        Ok(())\n    }\n""",
)

replace_once(
    "tui/Cargo.toml",
    'version = "2.0.0-alpha6.5"',
    'version = "2.0.0-alpha6.6"',
)
replace_once(
    "tui/Cargo.lock",
    'name = "nexus-irc-tui"\nversion = "2.0.0-alpha6.5"',
    'name = "nexus-irc-tui"\nversion = "2.0.0-alpha6.6"',
)

# ---------------------------------------------------------------------------
# Runtime regression expectations
# ---------------------------------------------------------------------------
replace_once(
    "tests/test_runtime.py",
    'self.assertEqual(result["protocol"], "nexus/0.8")\n        self.assertEqual(result["runtime_version"], "2.0.0-alpha6.4")',
    'self.assertEqual(result["protocol"], "nexus/0.9")\n        self.assertEqual(result["runtime_version"], "2.0.0-alpha6.6")\n        self.assertEqual(result["failsafe"]["schema_version"], "nexus-failsafe/1")',
)
replace_once(
    "tests/test_un_sim.py",
    'self.assertEqual(health["protocol"], "nexus/0.8")\n        self.assertEqual(health["runtime_version"], "2.0.0-alpha6.4")',
    'self.assertEqual(health["protocol"], "nexus/0.9")\n        self.assertEqual(health["runtime_version"], "2.0.0-alpha6.6")',
)
replace_once(
    "tests/test_mud.py",
    'self.assertEqual(health["protocol"], "nexus/0.8")',
    'self.assertEqual(health["protocol"], "nexus/0.9")',
)

# ---------------------------------------------------------------------------
# README / API / roadmap / changelog
# ---------------------------------------------------------------------------
replace_once(
    "README.md",
    "- a hidden Rust-TUI **`/GO64` Secret Alias Mode** with a text demoscene and DR. S.BAITSO tribute.\n",
    "- a hidden Rust-TUI **`/GO64` Secret Alias Mode** with a text demoscene and DR. S.BAITSO tribute;\n- **NEXUS Failsafe** containment with the cursed Upside Down, bounded rehabilitation, Shadow Realm, and deterministic equal-vote relief actors.\n",
)
replace_once(
    "README.md",
    """protocol: nexus/0.8\nruntime version: 2.0.0-alpha6.4\noperator TUI version: 2.0.0-alpha6.5\n""",
    """protocol: nexus/0.9\nruntime version: 2.0.0-alpha6.6\noperator TUI version: 2.0.0-alpha6.6\n""",
)
replace_once(
    "README.md",
    """            | telemetry + games   |\n            | Secret Scrubber     |\n""",
    """            | telemetry + games   |\n            | Failsafe / Shadow   |\n            | Secret Scrubber     |\n""",
)
replace_once(
    "README.md",
    """See [`docs/GO64.md`](docs/GO64.md) for the contract and copyright/claim boundary.\n\nUseful commands:\n""",
    """See [`docs/GO64.md`](docs/GO64.md) for the contract and copyright/claim boundary.\n\n### Actor failsafe / Shadow Realm\n\nIf a Council actor repeats a registered procedural guard violation after the ordinary nudge, NEXUS removes it from normal Council influence and sends it through one isolated **Upside Down** rehabilitation probe with no evidence, vote, other-member output, or world mutation capability. A clean probe grants parole at the next Council hat. A failed probe sends the original actor to the **Shadow Realm** and a deterministic local relief model occupies the same one-vote seat on subsequent Council runs. Disagreement, model size, provider identity, openness, benchmark rank, and being wrong are not Failsafe triggers.\n\nFailsafe state is recorded as immutable content-addressed world objects; a durable pointer index preserves Shadow-Realm state across runtime restarts. See [`docs/FAILSAFE.md`](docs/FAILSAFE.md).\n\n> **The troll layer may be cursed. The trigger must be boring.**\n\nUseful commands:\n""",
)

replace_count("docs/API.md", "nexus/0.8", "nexus/0.9", 2)
replace_count("docs/API.md", "2.0.0-alpha6.4", "2.0.0-alpha6.6", 2)
replace_once(
    "docs/API.md",
    """HERESY MUD        -> supported as a deterministic fictional multi-avatar local game\nremote providers  -> not implemented\n""",
    """HERESY MUD        -> supported as a deterministic fictional multi-avatar local game\nFailsafe          -> bounded repeated-guard containment + deterministic relief actor\nremote providers  -> not implemented\n""",
)
replace_once(
    "docs/API.md",
    """  \"actor_backends_available\": [\"mock\", \"ollama\"],\n  \"games\": [\n""",
    """  \"actor_backends_available\": [\"mock\", \"ollama\"],\n  \"failsafe\": {\n    \"schema_version\": \"nexus-failsafe/1\",\n    \"trigger\": \"registered_repeated_guard_failure_after_nudge_only\"\n  },\n  \"games\": [\n""",
)
replace_once(
    "docs/API.md",
    """receipt.verify\ntelemetry.verify\ngame.un.catalog\n""",
    """receipt.verify\ntelemetry.verify\nfailsafe.status\ngame.un.catalog\n""",
)
replace_once(
    "docs/API.md",
    """## Fictional UN simulation game\n""",
    """## Failsafe status\n\nInspect current actor containment state:\n\n```json\n{\"operation\":\"failsafe.status\"}\n```\n\nOptionally filter by Council member seat:\n\n```json\n{\"operation\":\"failsafe.status\",\"member_id\":\"Grok\"}\n```\n\nFailsafe triggers only after a registered procedural guard violation is repeated after its ordinary nudge. The isolated rehabilitation probe receives no Council evidence or completed phase material and has no ballot or world mutation authority. A clean probe returns the actor at the next hat; failure records `shadow_realm` and causes `nexus-failsafe-relief-v1` to occupy the same equal-vote seat on later Council runs.\n\nSee [`FAILSAFE.md`](FAILSAFE.md).\n\n## Fictional UN simulation game\n""",
)

replace_once(
    "ROADMAP.md",
    """> **The terminal can cosplay as 1982. The substrate cannot.**\n\n## 2.0-alpha7 — Instruments\n""",
    """> **The terminal can cosplay as 1982. The substrate cannot.**\n\n## 2.0-alpha6.6 — Actor Failsafe / Shadow Realm\n\nImplemented / targeted in PR #12.\n\n- [x] trigger only on registered repeated procedural guard failure after a normal nudge;\n- [x] isolate the offending actor from Council evidence, other-member output, ballots and world mutation during rehabilitation;\n- [x] cursed Upside Down transcript without granting the containment layer Council authority;\n- [x] clean rehabilitation returns the actor at the next Council hat;\n- [x] failed rehabilitation moves the original actor to durable Shadow-Realm state;\n- [x] deterministic `nexus-failsafe-relief-v1` occupies the same equal-vote seat on subsequent runs;\n- [x] immutable content-addressed failsafe state plus validated durable latest-state index;\n- [x] explicit `UNDERDETERMINED` ballot for an actor still contained at ballot time;\n- [x] no truth, disagreement, provider, openness, parameter-count or benchmark trigger.\n\nCore invariant:\n\n> **The troll layer may be cursed. The trigger must be boring.**\n\n## 2.0-alpha7 — Instruments\n""",
)
replace_once(
    "ROADMAP.md",
    """GO64 / SECRET ALIAS RETRO MODE - Done.\n  ↓\n==============================\n""",
    """GO64 / SECRET ALIAS RETRO MODE - Done.\n  ↓\nFAILSAFE / UPSIDE DOWN / SHADOW REALM - Done.\n  ↓\n==============================\n""",
)
replace_once(
    "ROADMAP.md",
    "failure containment - TBA",
    "failure containment - Initial failsafe implemented; hardening TBA",
)

replace_once(
    "CHANGELOG.md",
    """All notable changes to QSOL NEXUS are documented here.\n\n## 2.0.0-alpha6.5 — Secret Alias / GO64 TUI edition\n""",
    """All notable changes to QSOL NEXUS are documented here.\n\n## 2.0.0-alpha6.6 — Actor Failsafe / Upside Down / Shadow Realm\n\n- add bounded containment only for registered procedural guard violations repeated after the ordinary nudge;\n- add an isolated non-Council rehabilitation probe with no Council evidence, other-member output, ballot, or world mutation authority;\n- allow a clean probe to return the actor at the next Council hat;\n- send failed rehabilitation to durable `shadow_realm` state;\n- substitute deterministic `nexus-failsafe-relief-v1` into the same equal-vote Council seat on subsequent runs;\n- force `UNDERDETERMINED` rather than accepting a model ballot while the actor is contained;\n- persist immutable `actor_failsafe_state` lineage with a validated latest-state pointer index;\n- expose `failsafe.status`;\n- bump the control API to `nexus/0.9`, runtime/TUI edition to `2.0.0-alpha6.6`, and Council receipt contract to `nexus/0.6`;\n- explicitly exclude disagreement, truth/falsity, provider identity, openness, model size and benchmark status from Failsafe triggers.\n\n> **The troll layer may be cursed. The trigger must be boring.**\n\n## 2.0.0-alpha6.5 — Secret Alias / GO64 TUI edition\n""",
)

print("Applied NEXUS Failsafe / Shadow Realm integration.")
