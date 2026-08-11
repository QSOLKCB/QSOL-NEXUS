from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one match in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start_marker: str, end_marker: str, new_block: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    target.write_text(text[:start] + new_block + text[end:], encoding="utf-8")


# --- wall.py: identity parity, Unicode single-line validation, rootless store,
# and Wall-event-only rebuild budget.
replace_once("src/nexus_runtime/wall.py", "import re\n", "")
replace_once(
    "src/nexus_runtime/wall.py",
    'MAX_WALL_REBUILD_OBJECTS = 100_000\n\n_PROVENANCE = {"actor": "nexus", "subsystem": "bbs_wall"}\n_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")\n',
    'MAX_WALL_REBUILD_EVENTS = 100_000\n\n_PROVENANCE = {"actor": "nexus", "subsystem": "bbs_wall"}\n',
)
replace_once(
    "src/nexus_runtime/wall.py",
    '''def _identity(value: Any, field: str) -> str:\n    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:\n        raise WallError("wall_invalid_identity", f"{field} must be a bounded identifier")\n    if _SCRUBBER.scrub(value).changed:\n        raise WallError("wall_invalid_identity", f"{field} must not contain credential-shaped material")\n    return value\n''',
    '''def _identity(value: Any, field: str) -> str:\n    # CouncilMember's established runtime identity contract is deliberately\n    # provider-agnostic: identities are non-empty strings, not ASCII slugs.\n    # Preserve admitted labels exactly so Wall participation cannot silently\n    # narrow the identity space after a model/human is already admitted.\n    if not isinstance(value, str) or value == "":\n        raise WallError("wall_invalid_identity", f"{field} must be a non-empty runtime identifier")\n    if _SCRUBBER.scrub(value).changed:\n        raise WallError("wall_invalid_identity", f"{field} must not contain credential-shaped material")\n    return value\n''',
)
replace_once(
    "src/nexus_runtime/wall.py",
    '''def _bounded_single_line(value: Any, *, field: str, limit: int, code: str) -> str:\n    if not isinstance(value, str):\n        raise WallError(code, f"{field} must be text")\n    text = value.strip()\n    if not text or len(text) > limit or "\\n" in text or "\\r" in text:\n        raise WallError(code, f"{field} must be one non-empty line of at most {limit} characters")\n    if _SCRUBBER.scrub(text).changed:\n        raise WallError(code, f"{field} must not contain credential-shaped material")\n    return text\n''',
    '''def _bounded_single_line(value: Any, *, field: str, limit: int, code: str) -> str:\n    if not isinstance(value, str):\n        raise WallError(code, f"{field} must be text")\n    # Check the raw value before strip(): splitlines(keepends=True) recognizes\n    # CR/LF plus VT, FF, NEL and Unicode line/paragraph separators.  Checking\n    # before normalization also rejects a separator placed at either edge.\n    if value.splitlines(keepends=True) != [value]:\n        raise WallError(code, f"{field} must be one non-empty line of at most {limit} characters")\n    text = value.strip()\n    if not text or len(text) > limit:\n        raise WallError(code, f"{field} must be one non-empty line of at most {limit} characters")\n    if _SCRUBBER.scrub(text).changed:\n        raise WallError(code, f"{field} must not contain credential-shaped material")\n    return text\n''',
)
replace_between(
    "src/nexus_runtime/wall.py",
    "    def _snapshot_objects(self) -> dict[str, WorldObject]:\n",
    "\n    @staticmethod\n    def _validate_author",
    '''    def _snapshot_objects(self) -> dict[str, WorldObject]:\n        snapshot: dict[str, WorldObject] = {}\n\n        def admit_wall_object(obj: WorldObject) -> None:\n            if obj.object_type not in WALL_RESERVED_OBJECT_TYPES:\n                return\n            snapshot[obj.object_id] = obj\n            if len(snapshot) > MAX_WALL_REBUILD_EVENTS:\n                raise WallError("wall_history_too_large", "Wall event budget exceeded")\n\n        # ContinuityWorldStore intentionally supports root=None as the default\n        # ephemeral runtime.  Its continuity helpers exist but there is no HEAD\n        # to resolve, so treat it exactly like the in-memory WorldStore it is.\n        if self.world.root is None:\n            for ref in sorted(getattr(self.world, "_objects", {})):\n                admit_wall_object(self.world.inspect(ref))\n            return snapshot\n\n        continuity_lock = getattr(self.world, "_locked_continuity", None)\n        resolve_head = getattr(self.world, "_resolve_head", None)\n        history = getattr(self.world, "_history", None)\n        valid_sources = getattr(self.world, "_valid_object_sources", None)\n        quorum = getattr(self.world, "write_quorum", None)\n        if all(callable(item) for item in (continuity_lock, resolve_head, history, valid_sources)) and isinstance(quorum, int):\n            with continuity_lock():\n                head_ref, _ = resolve_head(require_chain=True)\n                refs, _ = history(head_ref, require_manifest_quorum=False)\n                for ref in sorted(refs):\n                    sources = valid_sources(ref)\n                    if len(sources) < quorum:\n                        from .world_continuity import WorldContinuityError\n\n                        raise WorldContinuityError(\n                            "world_continuity_read_quorum_unavailable",\n                            "recognized object does not currently have a verified read quorum",\n                        )\n                    admit_wall_object(sources[0][1])\n            return snapshot\n\n        objects_dir = self.world.objects_dir\n        if objects_dir is None:\n            refs = sorted(getattr(self.world, "_objects", {}))\n        else:\n            entries = sorted(path for path in objects_dir.iterdir() if path.name.endswith(".json"))\n            refs = [\n                f"object:{path.name.removesuffix('.json')}"\n                for path in entries\n                if len(path.name.removesuffix(".json")) == 64\n            ]\n        for ref in refs:\n            admit_wall_object(self.world.inspect(ref))\n        return snapshot\n''',
)
replace_once(
    "src/nexus_runtime/wall.py",
    '''        snapshot = self._snapshot_objects()\n        events = [\n            obj\n            for obj in snapshot.values()\n            if obj.object_type in WALL_RESERVED_OBJECT_TYPES\n        ]\n        if len(events) > MAX_WALL_REBUILD_OBJECTS:\n            raise WallError("wall_history_too_large", "Wall event budget exceeded")\n''',
    '''        snapshot = self._snapshot_objects()\n        events = list(snapshot.values())\n        if len(events) > MAX_WALL_REBUILD_EVENTS:\n            raise WallError("wall_history_too_large", "Wall event budget exceeded")\n''',
)
replace_once(
    "src/nexus_runtime/wall.py",
    '''    def _create_event(self, object_type: str, fields: dict[str, Any]) -> WorldObject:\n        events = self._events()\n        previous = events[-1].object_id if events else None\n''',
    '''    def _create_event(self, object_type: str, fields: dict[str, Any]) -> WorldObject:\n        events = self._events()\n        if len(events) >= MAX_WALL_REBUILD_EVENTS:\n            raise WallError("wall_history_too_large", "Wall event budget exceeded")\n        previous = events[-1].object_id if events else None\n''',
)
replace_once(
    "src/nexus_runtime/wall.py",
    '''        with self._locked():\n            events = self._events()\n            posts = {obj.object_id for obj in events if obj.object_type == WALL_POST_OBJECT_TYPE}\n''',
    '''        with self._locked():\n            events = self._events()\n            if len(events) >= MAX_WALL_REBUILD_EVENTS:\n                raise WallError("wall_history_too_large", "Wall event budget exceeded")\n            posts = {obj.object_id for obj in events if obj.object_type == WALL_POST_OBJECT_TYPE}\n''',
)

# --- wall_api.py: validate AI identities before inference and make health probe
# the actual immutable Wall history rather than advertising unconditional OK.
replace_once(
    "src/nexus_runtime/wall_api.py",
    '''        prompt = self.scrubber.scrub(raw_prompt)\n        actor = self._culture_actor(request.get("member"))\n        mode = get_mode("meme_casual")\n''',
    '''        prompt = self.scrubber.scrub(raw_prompt)\n        actor = self._culture_actor(request.get("member"))\n        for field, identity in (\n            ("member_id", actor.member.member_id),\n            ("model_id", actor.member.model_id),\n        ):\n            if not isinstance(identity, str) or identity == "" or self.scrubber.scrub(identity).changed:\n                raise WallError("wall_invalid_identity", f"{field} must be a non-secret runtime identifier")\n        mode = get_mode("meme_casual")\n''',
)
replace_once(
    "src/nexus_runtime/wall_api.py",
    '''    def handle(self, request: dict[str, Any]) -> dict[str, Any]:\n''',
    '''    def _wall_health_snapshot(self) -> dict[str, Any]:\n        policy = wall_policy_snapshot()\n        try:\n            listing = self.wall.list_posts(limit=1)\n        except WallError as exc:\n            return {\n                "status": "degraded",\n                "error_code": exc.code,\n                "policy": policy,\n                "authority_effect": "none",\n            }\n        except WorldContinuityError as exc:\n            return {\n                "status": "unavailable",\n                "error_code": exc.code,\n                "policy": policy,\n                "authority_effect": "none",\n            }\n        except (KeyError, OSError, TypeError, ValueError, RecursionError):\n            return {\n                "status": "unavailable",\n                "error_code": "wall_history_unavailable",\n                "policy": policy,\n                "authority_effect": "none",\n            }\n        return {\n            "status": "ok",\n            "recognized_events": listing["total_events"],\n            "recognized_posts": listing["matched_posts"],\n            "policy": policy,\n            "authority_effect": "none",\n        }\n\n    def handle(self, request: dict[str, Any]) -> dict[str, Any]:\n''',
)
replace_once(
    "src/nexus_runtime/wall_api.py",
    '''                "bbs_wall": {\n                    "status": "ok",\n                    "policy": wall_policy_snapshot(),\n                },\n''',
    '''                "bbs_wall": self._wall_health_snapshot(),\n''',
)

# --- Rust parser: remove suffix on a char boundary so malformed Unicode input
# returns an error instead of panicking the interactive TUI.
replace_once(
    "tui/src/lib.rs",
    '''fn wall_duration(raw: &str) -> Result<u64, String> {\n    if raw.len() < 2 {\n        return Err("Wall duration must look like 30m, 24h or 7d".to_string());\n    }\n    let (digits, suffix) = raw.split_at(raw.len() - 1);\n    let value = digits\n        .parse::<u64>()\n        .map_err(|_| "Wall duration must look like 30m, 24h or 7d".to_string())?;\n    if value == 0 {\n        return Err("Wall duration must be positive".to_string());\n    }\n    let multiplier = match suffix.to_ascii_lowercase().as_str() {\n        "m" => 60u64,\n        "h" => 3_600u64,\n        "d" => 86_400u64,\n        _ => return Err("Wall duration must use m, h or d".to_string()),\n    };\n''',
    '''fn wall_duration(raw: &str) -> Result<u64, String> {\n    let (suffix_index, suffix) = raw\n        .char_indices()\n        .next_back()\n        .ok_or_else(|| "Wall duration must look like 30m, 24h or 7d".to_string())?;\n    if suffix_index == 0 {\n        return Err("Wall duration must look like 30m, 24h or 7d".to_string());\n    }\n    let digits = &raw[..suffix_index];\n    let value = digits\n        .parse::<u64>()\n        .map_err(|_| "Wall duration must look like 30m, 24h or 7d".to_string())?;\n    if value == 0 {\n        return Err("Wall duration must be positive".to_string());\n    }\n    let multiplier = match suffix.to_ascii_lowercase() {\n        'm' => 60u64,\n        'h' => 3_600u64,\n        'd' => 86_400u64,\n        _ => return Err("Wall duration must use m, h or d".to_string()),\n    };\n''',
)

# --- Python regressions for every Codex review finding.
replace_once(
    "tests/test_wall.py",
    "import unittest\n",
    "import unittest\nfrom unittest.mock import patch\n",
)
insert_marker = '''    def test_human_posts_are_immutable_chronological_social_memory(self) -> None:\n'''
insert = '''    def test_default_ephemeral_runtime_supports_wall_history(self) -> None:\n        with tempfile.TemporaryDirectory() as temporary:\n            base = Path(temporary)\n            api = NexusAPI(\n                auth_root=base / "auth",\n                trap_root=base / "trap",\n                stenographer_root=base / "stenographer",\n            )\n            listing = api.handle({"operation": "wall.list"})\n            self.assertEqual(listing["status"], "ok")\n            self.assertEqual(listing["posts"], [])\n            posted = api.handle(\n                {"operation": "wall.post", "author_id": "Ephemeral Operator", "text": "Memory without a disk."}\n            )\n            self.assertEqual(posted["status"], "ok")\n            self.assertEqual(api.handle({"operation": "wall.list"})["posts"][0]["text"], "Memory without a disk.")\n\n    def test_runtime_identity_labels_preserve_unicode_spaces_slashes_and_colons(self) -> None:\n        with tempfile.TemporaryDirectory() as temporary:\n            api = self._api(Path(temporary))\n            human_id = "Trent / 操作者:1"\n            posted = api.handle({"operation": "wall.post", "author_id": human_id, "text": "Identity is a label, not a slug."})\n            self.assertEqual(posted["status"], "ok")\n            mine = api.handle({"operation": "wall.list", "author_id": human_id})\n            self.assertEqual(mine["posts"][0]["author"]["author_id"], human_id)\n\n            member = {\n                "member_id": "Alpha / Ω:seat",\n                "model_id": "mock/模型 alpha",\n                "adapter_id": "mock",\n                "profile": "balanced",\n            }\n            ai_post = api.handle({"operation": "wall.ai_post", "member": member, "prompt": "Leave a short note."})\n            self.assertEqual(ai_post["status"], "ok")\n            self.assertEqual(\n                ai_post["post"]["payload"]["author"],\n                {"kind": "model", "author_id": member["member_id"], "model_id": member["model_id"]},\n            )\n\n    def test_wall_rejects_all_python_line_boundaries_before_normalization(self) -> None:\n        separators = ("\\n", "\\r", "\\v", "\\f", "\\x1c", "\\x1d", "\\x1e", "\\x85", "\\u2028", "\\u2029")\n        for separator in separators:\n            with self.subTest(separator=repr(separator)):\n                world = WorldStore()\n                wall = WallService(world)\n                with self.assertRaises(WallError):\n                    wall.post_human(author_id="Trent", text=f"first{separator}spoofed")\n                posted = wall.post_human(author_id="Trent", text="safe")\n                with self.assertRaises(WallError):\n                    wall.tombstone(\n                        moderator_id="Trent",\n                        post_ref=posted.object_id,\n                        reason=f"moderation{separator}spoofed",\n                    )\n\n    def test_rebuild_budget_counts_only_wall_events(self) -> None:\n        world = WorldStore()\n        wall = WallService(world)\n        world.create_object("unrelated", {"n": 1}, {"actor": "test"})\n        world.create_object("unrelated", {"n": 2}, {"actor": "test"})\n        with patch("nexus_runtime.wall.MAX_WALL_REBUILD_EVENTS", 1):\n            first = wall.post_human(author_id="Trent", text="Only Wall events consume the cap.")\n            world.create_object("unrelated", {"n": 3}, {"actor": "test"})\n            listing = wall.list_posts()\n            self.assertEqual(listing["posts"][0]["post_ref"], first.object_id)\n            with self.assertRaisesRegex(WallError, "event budget"):\n                wall.post_human(author_id="Trent", text="This would exceed the Wall-event cap.")\n\n    def test_system_health_probes_wall_history_and_reports_forks(self) -> None:\n        with tempfile.TemporaryDirectory() as temporary:\n            base = Path(temporary)\n            api = NexusAPI(\n                auth_root=base / "auth",\n                trap_root=base / "trap",\n                stenographer_root=base / "stenographer",\n            )\n            posted = api.handle({"operation": "wall.post", "author_id": "Trent", "text": "canonical"})\n            legitimate = api.world.inspect(posted["post"]["object_id"])\n            forged_payload = deepcopy(legitimate.payload)\n            forged_payload["text"] = "fork"\n            api.world.create_object(\n                WALL_POST_OBJECT_TYPE,\n                forged_payload,\n                {"actor": "nexus", "subsystem": "bbs_wall"},\n            )\n            health = api.handle({"operation": "system.health"})\n            self.assertEqual(health["status"], "ok")\n            self.assertEqual(health["bbs_wall"]["status"], "degraded")\n            self.assertEqual(health["bbs_wall"]["error_code"], "wall_history_fork")\n\n'''
replace_once("tests/test_wall.py", insert_marker, insert + insert_marker)

# --- Rust regression: malformed Unicode suffix is an ordinary parse error.
replace_once(
    "tui/tests/wall.rs",
    '''    assert!(parse_input("/wall since yesterday").is_err());\n    assert!(command_completions("/wal").contains(&"/wall"));\n''',
    '''    assert!(parse_input("/wall since yesterday").is_err());\n    assert!(parse_input("/wall since 1é").is_err());\n    assert!(parse_input("/wall since １h").is_err());\n    assert!(command_completions("/wal").contains(&"/wall"));\n''',
)

print("PR #50 review fixes applied")
