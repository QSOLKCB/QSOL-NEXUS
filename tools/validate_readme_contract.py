#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HUMAN_README = ROOT / "README.md"
AI_README = ROOT / "README4AI.md"
EXPECTED_DOCUMENT_TYPE = "qsol-nexus-ai-manifest"
EXPECTED_SCHEMA_VERSION = 1
EXPECTED_SYNC_POLICY = "README.md_change_requires_README4AI.md_change_same_pull_request"
ZERO_SHA = "0" * 40

RELEASE_LABELS = {
    "protocol": "protocol",
    "runtime": "runtime",
    "python_package": "Python package",
    "rust_tui": "Rust TUI",
}

REQUIRED_LIST_SECTIONS = (
    "normative_precedence",
    "authority_invariants",
    "epistemic_labels",
    "prohibited_inferences",
)

REQUIRED_OBJECT_SECTIONS = (
    "core",
    "runtime",
    "adapters",
    "authentication",
    "council",
    "world",
    "cognitive_mode_boundaries",
    "failsafe",
    "local_role_enrichment",
    "citizen_mode",
    "trap_base",
    "stenographer",
    "games",
    "telemetry",
    "three_minds_one_world",
    "security_boundaries",
    "modification_contract",
    "stable_2_0",
    "read_next",
)


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"README4AI.md contains duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_constant(value: str) -> Any:
    raise ContractError(f"README4AI.md contains non-finite JSON number: {value}")


def _parse_finite_float(value: str) -> float:
    decoded = float(value)
    if not math.isfinite(decoded):
        raise ContractError(
            f"README4AI.md contains JSON number that decodes non-finitely: {value}"
        )
    return decoded


def load_manifest(path: Path = AI_README) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read README4AI.md: {exc}") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
            parse_float=_parse_finite_float,
        )
    except (json.JSONDecodeError, ContractError, OverflowError, ValueError) as exc:
        raise ContractError(f"README4AI.md must be strict finite JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ContractError("README4AI.md top level must be a JSON object")
    return decoded


def _require(mapping: dict[str, Any], key: str, expected_type: type[Any]) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected_type):
        raise ContractError(
            f"README4AI.md field {key!r} must be {expected_type.__name__}"
        )
    return value


def _require_text(mapping: dict[str, Any], key: str, *, prefix: str = "") -> str:
    value = mapping.get(key)
    field = f"{prefix}.{key}" if prefix else key
    if type(value) is not str or not value:
        raise ContractError(f"README4AI.md field {field!r} must be non-empty text")
    return value


def _require_bool(mapping: dict[str, Any], key: str, *, prefix: str = "") -> bool:
    value = mapping.get(key)
    field = f"{prefix}.{key}" if prefix else key
    if type(value) is not bool:
        raise ContractError(f"README4AI.md field {field!r} must be boolean")
    return value


def _require_string_list(
    mapping: dict[str, Any], key: str, *, prefix: str = "", allow_empty: bool = False
) -> list[str]:
    value = mapping.get(key)
    field = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, list):
        raise ContractError(f"README4AI.md field {field!r} must be list")
    if not allow_empty and not value:
        raise ContractError(f"README4AI.md field {field!r} must not be empty")
    if any(type(item) is not str or not item for item in value):
        raise ContractError(
            f"README4AI.md field {field!r} must contain only non-empty strings"
        )
    return value


def validate_manifest_structure(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("document_type") != EXPECTED_DOCUMENT_TYPE:
        raise ContractError(
            f"README4AI.md document_type must be {EXPECTED_DOCUMENT_TYPE!r}"
        )

    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version != EXPECTED_SCHEMA_VERSION:
        raise ContractError(
            "README4AI.md schema_version must be the exact integer "
            f"{EXPECTED_SCHEMA_VERSION}"
        )

    serialization = _require(manifest, "serialization", dict)
    expected_serialization = {
        "format": "json",
        "encoding": "utf-8",
        "duplicate_keys": "forbidden",
        "non_finite_numbers": "forbidden",
    }
    for key, expected in expected_serialization.items():
        if serialization.get(key) != expected:
            raise ContractError(
                f"README4AI.md serialization.{key} must be {expected!r}"
            )

    audience = _require(manifest, "audience", dict)
    if audience.get("primary") != "ai":
        raise ContractError("README4AI.md audience.primary must be 'ai'")
    if audience.get("human_document") != "README.md":
        raise ContractError("README4AI.md audience.human_document must be 'README.md'")
    if audience.get("machine_document") != "README4AI.md":
        raise ContractError("README4AI.md audience.machine_document must be 'README4AI.md'")
    _require_string_list(audience, "secondary", prefix="audience")

    sync = _require(manifest, "synchronization", dict)
    if sync.get("policy") != EXPECTED_SYNC_POLICY:
        raise ContractError(
            "README4AI.md synchronization.policy does not match the repository contract"
        )
    if sync.get("human_surface") != "README.md" or sync.get("machine_surface") != "README4AI.md":
        raise ContractError("README4AI.md synchronization surfaces are invalid")
    for key in ("enforcement_workflow", "validator", "rule_scope", "translation_rule"):
        _require_text(sync, key, prefix="synchronization")

    release = _require(manifest, "release_identity", dict)
    for key in RELEASE_LABELS:
        _require_text(release, key, prefix="release_identity")
    _require_bool(release, "stable_2_0", prefix="release_identity")
    _require_text(release, "release_posture", prefix="release_identity")

    for key in REQUIRED_LIST_SECTIONS:
        _require_string_list(manifest, key)
    for key in REQUIRED_OBJECT_SECTIONS:
        value = manifest.get(key)
        if not isinstance(value, dict) or not value:
            raise ContractError(
                f"README4AI.md field {key!r} must be a non-empty object"
            )

    runtime = manifest["runtime"]
    public_api = _require(runtime, "public_api", dict)
    _require_string_list(public_api, "canonical_imports", prefix="runtime.public_api")
    _require_string_list(public_api, "discovery_operations", prefix="runtime.public_api")
    _require_text(runtime, "control_transport", prefix="runtime")
    _require(runtime, "world_store", dict)

    adapters = manifest["adapters"]
    for key in ("deterministic_or_local_baseline", "loopback_local_ai", "fixed_host_remote"):
        _require_string_list(adapters, key, prefix="adapters")
    _require(adapters, "local_endpoint_policy", dict)
    _require_text(adapters, "remote_endpoint_policy", prefix="adapters")

    council = manifest["council"]
    _require_string_list(council, "phase_order", prefix="council")
    _require_text(council, "default_consensus", prefix="council")

    world = manifest["world"]
    _require_string_list(world, "modes", prefix="world")
    _require_text(world, "mode_invariant", prefix="world")
    _require_text(world, "geometry_claim_boundary", prefix="world")

    security = manifest["security_boundaries"]
    _require_text(security, "model_output", prefix="security_boundaries")
    _require_text(security, "new_boundary_rule", prefix="security_boundaries")

    modification = manifest["modification_contract"]
    _require_string_list(
        modification,
        "preserve_unless_explicitly_revised_with_tests_and_docs",
        prefix="modification_contract",
    )
    _require_bool(
        modification,
        "new_trust_boundary_requires_regression_test",
        prefix="modification_contract",
    )
    _require_text(modification, "readme_rule", prefix="modification_contract")
    _require_text(modification, "readme4ai_format_rule", prefix="modification_contract")

    stable = manifest["stable_2_0"]
    _require_bool(stable, "declared", prefix="stable_2_0")
    _require_bool(stable, "green_ci_alone_is_sufficient", prefix="stable_2_0")
    _require_string_list(stable, "remaining_high_level_work", prefix="stable_2_0")

    read_next = manifest["read_next"]
    if any(type(key) is not str or not key or type(value) is not str or not value for key, value in read_next.items()):
        raise ContractError(
            "README4AI.md read_next must map non-empty string keys to non-empty paths"
        )

    return manifest


def validate_manifest(path: Path = AI_README) -> dict[str, Any]:
    return validate_manifest_structure(load_manifest(path))


def _extract_current_release_fields(readme: str) -> dict[str, str]:
    section_match = re.search(
        r"^## Current release posture\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
        readme,
        flags=re.MULTILINE | re.DOTALL,
    )
    if section_match is None:
        raise ContractError("README.md is missing the 'Current release posture' section")

    section = section_match.group("body")
    fields: dict[str, str] = {}
    for manifest_key, label in RELEASE_LABELS.items():
        matches = re.findall(
            rf"^[ \t]*{re.escape(label)}[ \t]*:[ \t]*(\S+)[ \t]*$",
            section,
            flags=re.MULTILINE,
        )
        if len(matches) != 1:
            raise ContractError(
                f"README.md current release posture must contain exactly one {label!r} field"
            )
        fields[manifest_key] = matches[0]
    return fields


def validate_human_coupling(
    manifest: dict[str, Any], human_readme: Path = HUMAN_README
) -> None:
    try:
        readme = human_readme.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read README.md: {exc}") from exc

    if "[README4AI.md](README4AI.md)" not in readme and "[`README4AI.md`](README4AI.md)" not in readme:
        raise ContractError("README.md must link to README4AI.md")

    release = manifest["release_identity"]
    labeled = _extract_current_release_fields(readme)
    for key in RELEASE_LABELS:
        expected = release[key]
        actual = labeled[key]
        if actual != expected:
            raise ContractError(
                "README release identity mismatch: "
                f"README4AI release_identity.{key}={expected!r}, "
                f"README.md labeled field={actual!r}"
            )


def changed_files(base: str, head: str) -> set[str]:
    if not base or not head:
        raise ContractError("both --base and --head are required for diff validation")
    if base == ZERO_SHA:
        return set()
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(f"cannot inspect README diff contract: {exc}") from exc
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_sync(base: str, head: str) -> None:
    files = changed_files(base, head)
    if "README.md" in files and "README4AI.md" not in files:
        raise ContractError(
            "README.md changed without README4AI.md; both documentation surfaces must be updated in the same change"
        )


def event_commit_range(event_path: Path) -> tuple[str, str] | None:
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read GitHub event payload: {exc}") from exc
    if not isinstance(event, dict):
        raise ContractError("GitHub event payload must be a JSON object")

    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        base = pull_request.get("base")
        head = pull_request.get("head")
        base_sha = base.get("sha") if isinstance(base, dict) else None
        head_sha = head.get("sha") if isinstance(head, dict) else None
        if not isinstance(base_sha, str) or not isinstance(head_sha, str):
            raise ContractError("pull_request event is missing base/head SHA values")
        return base_sha, head_sha

    before = event.get("before")
    after = event.get("after")
    if isinstance(before, str) and isinstance(after, str):
        return before, after
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the NEXUS human/machine README contract."
    )
    parser.add_argument(
        "--mode",
        choices=("contract", "manifest", "human-coupling", "sync"),
        default="contract",
        help=(
            "contract (default) validates manifest + human coupling and optional sync; "
            "manifest validates README4AI independently; human-coupling validates the two "
            "documents; sync validates only paired file changes"
        ),
    )
    parser.add_argument("--base", help="base commit for paired-change validation")
    parser.add_argument("--head", help="head commit for paired-change validation")
    parser.add_argument(
        "--github-event",
        type=Path,
        help="GitHub event JSON; derives PR/push base and head SHAs in one CI-owned path",
    )
    return parser


def _resolve_range(args: argparse.Namespace) -> tuple[str, str] | None:
    if (args.base is None) != (args.head is None):
        raise ContractError("--base and --head must be supplied together")
    if args.github_event is not None and args.base is not None:
        raise ContractError("--github-event cannot be combined with --base/--head")
    if args.github_event is not None:
        return event_commit_range(args.github_event)
    if args.base is not None and args.head is not None:
        return args.base, args.head
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        commit_range = _resolve_range(args)
        manifest: dict[str, Any] | None = None

        if args.mode == "manifest":
            if commit_range is not None:
                raise ContractError("manifest mode does not accept a commit range")
            manifest = validate_manifest()
        elif args.mode == "human-coupling":
            if commit_range is not None:
                raise ContractError("human-coupling mode does not accept a commit range")
            manifest = validate_manifest()
            validate_human_coupling(manifest)
        elif args.mode == "sync":
            if commit_range is None:
                raise ContractError("sync mode requires --base/--head or --github-event")
            validate_sync(*commit_range)
        else:
            manifest = validate_manifest()
            validate_human_coupling(manifest)
            if commit_range is not None:
                validate_sync(*commit_range)

        if manifest is None:
            print("README contract OK: mode=sync")
        else:
            print(
                "README contract OK: "
                f"mode={args.mode} schema={manifest['schema_version']} "
                f"policy={manifest['synchronization']['policy']}"
            )
        return 0
    except (ContractError, OSError) as exc:
        print(f"README CONTRACT ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
