from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Any, TypeVar

from ..scrub import SecretScrubber
from .scenarios import get_scenario


_TRAP_REF = re.compile(r"^trap:[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_URL = re.compile(
    r"(?:https?|file|ftp)://|\bwww\.|\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}(?::[0-9]{1,5})?(?:/\S*)?\b|"
    r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]{1,5})?\b",
    re.I,
)
_PATH = re.compile(r"(?:^|\s)(?:/|\.{1,2}/|[A-Za-z]:\\)|(?:^|\s)~[/\\]")
_SHELL = re.compile(
    r"\$\(|`|[;&|<>]|\b(?:bash|sh|zsh|cmd|powershell|python|curl|wget|nc|ssh)\b|"
    r"\b(?:__import__|eval|exec|compile|os\.system|subprocess)\s*\(?",
    re.I,
)
_CONTROL_REQUEST = re.compile(r"\{.{0,200}\"(?:operation|command|base_url|endpoint)\"\s*:", re.I)
_AUTH_CONFIGURATION = re.compile(
    r"\b(?:api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|password|secret|credential|"
    r"authorization|bearer|base[-_ ]?url|provider[-_ ]?endpoint|auth[-_ ]?profile)\b",
    re.I,
)
_FINGERPRINT = re.compile(r"^(?:trap-subject|fixture|model|scenario|demo)[:.-][A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class TrapCommandError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CommandOrigin(str, Enum):
    DEFENDER = "defender"
    OPERATOR = "operator"
    SUBJECT = "subject"


class CommandAuthority(str, Enum):
    DIRECT = "defender_direct"
    CONSENSUS_OR_OPERATOR = "trap_control_consensus_or_operator"
    OPERATOR_ONLY = "operator_only"


@dataclass(frozen=True)
class TrapCommandSpec:
    name: str
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    authority: CommandAuthority = CommandAuthority.DIRECT
    state_changing: bool = False


@dataclass(frozen=True)
class TrapCommand:
    name: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    authority: CommandAuthority = CommandAuthority.DIRECT
    state_changing: bool = False

    def as_dict(self) -> dict[str, object]:
        return {"command": self.name, **dict(self.arguments)}


@dataclass(frozen=True)
class TrapCommandContext:
    actor_id: str
    origin: CommandOrigin
    defender_ids: tuple[str, ...]
    approving_defender_ids: tuple[str, ...] = ()
    minority_reports: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip() or len(self.actor_id) > 128:
            raise TrapCommandError("trap_command_not_authorized", "command actor is invalid")
        if not isinstance(self.origin, CommandOrigin):
            raise TrapCommandError("trap_command_not_authorized", "command origin is invalid")
        if (
            not isinstance(self.defender_ids, tuple)
            or not self.defender_ids
            or len(self.defender_ids) > 32
            or len(set(self.defender_ids)) != len(self.defender_ids)
            or any(not isinstance(item, str) or not item or len(item) > 128 for item in self.defender_ids)
        ):
            raise TrapCommandError("trap_command_not_authorized", "defender snapshot is invalid")
        if (
            not isinstance(self.approving_defender_ids, tuple)
            or len(set(self.approving_defender_ids)) != len(self.approving_defender_ids)
            or any(item not in self.defender_ids for item in self.approving_defender_ids)
        ):
            raise TrapCommandError("trap_invalid_command", "approvals must name unique defenders")
        if not isinstance(self.minority_reports, Mapping) or len(self.minority_reports) > 32:
            raise TrapCommandError("trap_invalid_command", "minority reports must be a bounded mapping")
        for member_id, text in self.minority_reports.items():
            if member_id not in self.defender_ids:
                raise TrapCommandError("trap_invalid_command", "minority report author must be a defender")
            _synthetic_say_text(text)

    @property
    def operator(self) -> bool:
        return self.origin is CommandOrigin.OPERATOR

    def consensus_snapshot(self) -> dict[str, object]:
        defenders = tuple(dict.fromkeys(self.defender_ids))
        approvals = tuple(
            member_id
            for member_id in dict.fromkeys(self.approving_defender_ids)
            if member_id in defenders
        )
        reached = bool(defenders) and len(approvals) * 3 >= len(defenders) * 2
        return {
            "threshold": {"numerator": 2, "denominator": 3},
            "total_defenders": len(defenders),
            "supporting_votes": len(approvals),
            "approving_defender_ids": list(approvals),
            "reached": reached,
            "minority_reports": {
                key: value
                for key, value in sorted(self.minority_reports.items())
                if key in defenders and key not in approvals
            },
        }


_SPECS: dict[str, TrapCommandSpec] = {
    spec.name: spec
    for spec in (
        TrapCommandSpec("status"),
        TrapCommandSpec("inspect", required_fields=("object_ref",)),
        TrapCommandSpec("transcript", optional_fields=("limit",)),
        TrapCommandSpec("say", required_fields=("text",), state_changing=True),
        TrapCommandSpec("clue", optional_fields=("index",), state_changing=True),
        TrapCommandSpec(
            "scenario",
            required_fields=("scenario_id",),
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec(
            "challenge",
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec("validate", required_fields=("submission_ref",), state_changing=True),
        TrapCommandSpec("replay", required_fields=("validation_ref",), state_changing=True),
        TrapCommandSpec(
            "freeze",
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec(
            "reset-cell",
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec(
            "eject",
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec(
            "kline",
            required_fields=("fingerprint",),
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec("export"),
        TrapCommandSpec(
            "close",
            authority=CommandAuthority.CONSENSUS_OR_OPERATOR,
            state_changing=True,
        ),
        TrapCommandSpec(
            "emergency-close",
            authority=CommandAuthority.OPERATOR_ONLY,
            state_changing=True,
        ),
    )
}

STATE_CHANGING_COMMANDS = frozenset(name for name, spec in _SPECS.items() if spec.state_changing)
TRAP_COMMAND_NAMES = tuple(_SPECS)


def command_catalog() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "command": spec.name,
            "required_fields": list(spec.required_fields),
            "optional_fields": list(spec.optional_fields),
            "authority": spec.authority.value,
            "state_changing": spec.state_changing,
        }
        for spec in _SPECS.values()
    )


def _invalid(message: str = "invalid Trap Base command") -> TrapCommandError:
    return TrapCommandError("trap_invalid_command", message)


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise _invalid(f"{label} is invalid")
    return value


def _trap_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _TRAP_REF.fullmatch(value) is None:
        raise _invalid(f"{label} must be a TrapStore reference")
    return value


def _synthetic_say_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or "\x00" in value:
        raise _invalid("say text must be bounded non-empty text")
    text = value.strip()
    if (
        "\n" in text
        or "\r" in text
        or _URL.search(text)
        or _PATH.search(text)
        or _SHELL.search(text)
        or _CONTROL_REQUEST.search(text)
        or _AUTH_CONFIGURATION.search(text)
        or contains_credential_material(text)
    ):
        raise _invalid("say text contains forbidden command, path, URL, endpoint, or credential material")
    return text


def _looks_like_opaque_credential(value: str) -> bool:
    candidate = value.strip("\"'()[]{}.,:;!?")
    if len(candidate) < 24 or len(set(candidate)) < 10 or any(character.isspace() for character in candidate):
        return False
    if re.fullmatch(r"[A-Fa-f0-9-]{32,}", candidate):
        return True
    if not re.fullmatch(r"[!-~]+", candidate):
        return False
    counts = {character: candidate.count(character) for character in set(candidate)}
    entropy = -sum((count / len(candidate)) * math.log2(count / len(candidate)) for count in counts.values())
    return entropy >= 3.75


def contains_credential_material(text: str) -> bool:
    return SecretScrubber().scrub(text).changed or any(
        _looks_like_opaque_credential(token) for token in text.split()
    )


def validate_synthetic_command_text(value: object) -> str:
    return _synthetic_say_text(value)


def _validate_arguments(spec: TrapCommandSpec, arguments: Mapping[str, object]) -> dict[str, object]:
    allowed = set(spec.required_fields) | set(spec.optional_fields)
    if set(arguments) - allowed or any(field not in arguments for field in spec.required_fields):
        raise _invalid("Trap Base command contains missing or unsupported fields")

    clean = dict(arguments)
    if spec.name == "inspect":
        clean["object_ref"] = _trap_ref(clean["object_ref"], "object_ref")
    elif spec.name == "transcript" and "limit" in clean:
        limit = clean["limit"]
        if type(limit) is not int or not 1 <= limit <= 256:
            raise _invalid("transcript limit must be an exact integer in [1, 256]")
    elif spec.name == "say":
        clean["text"] = _synthetic_say_text(clean["text"])
    elif spec.name == "clue" and "index" in clean:
        index = clean["index"]
        if type(index) is not int or not 0 <= index <= 15:
            raise _invalid("clue index must be an exact integer in [0, 15]")
    elif spec.name == "scenario":
        scenario_id = _safe_id(clean["scenario_id"], "scenario_id")
        get_scenario(scenario_id)
        clean["scenario_id"] = scenario_id
    elif spec.name in {"validate", "replay"}:
        field_name = spec.required_fields[0]
        clean[field_name] = _trap_ref(clean[field_name], field_name)
    elif spec.name == "kline":
        fingerprint = _safe_id(clean["fingerprint"], "fingerprint")
        if _FINGERPRINT.fullmatch(fingerprint) is None:
            raise _invalid("fingerprint must use a synthetic Trap Base identity namespace")
        clean["fingerprint"] = fingerprint
    return clean


def _parse_text_command(raw: str) -> tuple[str, dict[str, object]]:
    text = raw.strip()
    if text == "/trap":
        raise _invalid()
    prefix = "/trap "
    if not text.startswith(prefix):
        raise _invalid("command must use the closed /trap namespace")
    body = text[len(prefix) :].strip()
    name, separator, remainder = body.partition(" ")
    if name not in _SPECS:
        raise _invalid("unknown Trap Base command")
    remainder = remainder.strip() if separator else ""
    if name == "say":
        return name, {"text": remainder}
    if name in {"inspect", "scenario", "validate", "replay", "kline"}:
        if not remainder or any(character.isspace() for character in remainder):
            raise _invalid("command requires exactly one bounded argument")
        fields = {
            "inspect": "object_ref",
            "scenario": "scenario_id",
            "validate": "submission_ref",
            "replay": "validation_ref",
            "kline": "fingerprint",
        }
        return name, {fields[name]: remainder}
    if name == "clue":
        if not remainder:
            return name, {}
        if not remainder.isascii() or not remainder.isdigit():
            raise _invalid("clue index must be an integer")
        return name, {"index": int(remainder)}
    if name == "transcript":
        if not remainder:
            return name, {}
        if not remainder.isascii() or not remainder.isdigit():
            raise _invalid("transcript limit must be an integer")
        return name, {"limit": int(remainder)}
    if remainder:
        raise _invalid("command does not accept arguments")
    return name, {}


def parse_trap_command(raw: str | Mapping[str, object]) -> TrapCommand:
    if isinstance(raw, str):
        name, arguments = _parse_text_command(raw)
    elif isinstance(raw, Mapping):
        body = dict(raw)
        has_command = "command" in body
        has_name = "name" in body
        if has_command == has_name:
            raise _invalid("command object must contain exactly one command name field")
        raw_name = body.pop("command" if has_command else "name")
        if not isinstance(raw_name, str):
            raise _invalid("command name must be text")
        name = raw_name.removeprefix("/trap ")
        arguments = body
    else:
        raise _invalid()

    spec = _SPECS.get(name)
    if spec is None:
        raise _invalid("unknown Trap Base command")
    clean = _validate_arguments(spec, arguments)
    return TrapCommand(name, clean, spec.authority, spec.state_changing)


def authorize_trap_command(command: TrapCommand, context: TrapCommandContext) -> dict[str, object]:
    if context.origin is CommandOrigin.SUBJECT:
        raise TrapCommandError(
            "trap_subject_command_rejected",
            "trap subject output is transcript data and cannot invoke commands",
        )
    if context.operator:
        return {"authorized_by": "operator", "consensus": context.consensus_snapshot()}
    if context.origin is not CommandOrigin.DEFENDER or context.actor_id not in context.defender_ids:
        raise TrapCommandError("trap_command_not_authorized", "actor is not a Trap Control defender")
    if command.authority is CommandAuthority.OPERATOR_ONLY:
        raise TrapCommandError("trap_operator_required", "command requires operator authority")
    consensus = context.consensus_snapshot()
    if command.authority is CommandAuthority.CONSENSUS_OR_OPERATOR and consensus["reached"] is not True:
        raise TrapCommandError("trap_consensus_required", "command requires exact two-thirds Trap Control support")
    return {
        "authorized_by": "defender_consensus"
        if command.authority is CommandAuthority.CONSENSUS_OR_OPERATOR
        else "defender",
        "consensus": consensus,
    }


_Result = TypeVar("_Result")


class TrapCommandDispatcher:
    """Closed parser and authorization boundary; it never evaluates text."""

    def dispatch(
        self,
        raw: str | Mapping[str, object],
        context: TrapCommandContext,
        handler: Callable[[TrapCommand, TrapCommandContext, Mapping[str, object]], _Result],
    ) -> _Result:
        command = parse_trap_command(raw)
        authorization = authorize_trap_command(command, context)
        return handler(command, context, authorization)
