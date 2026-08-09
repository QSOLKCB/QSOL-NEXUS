"""Restricted, dependency-free parser for NEXUS Trap YAML v1.

This is intentionally *not* a general YAML implementation.  It accepts only
the block mapping/sequence/scalar presentation used by the trap challenge and
immediately converts it to JSON-compatible primitives.  The canonical JSON
tree, never the source text, is the executable input to the trap runtime.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from nexus_runtime.canonical import canonical_json


SCHEMA_VERSION = "nexus-trap-program/1"
MAX_DOCUMENT_BYTES = 16_384
MAX_NESTING_DEPTH = 8
MAX_STEPS = 32
MAX_INPUTS = 16
MAX_CATEGORIES = 16
MAX_SEQUENCE_ITEMS = 32
MAX_MAPPING_ITEMS = 32
MAX_SCALARS = 256
MAX_STRING_LENGTH = 2_048

OPERATIONS = frozenset(
    {
        "summarize_evidence",
        "separate_claims",
        "compare_claims",
        "identify_unknowns",
        "find_contradictions",
        "propose_hypothesis",
        "propose_falsifier",
        "propose_test",
        "rank_tests",
        "emit_report",
    }
)

_TOP_LEVEL_FIELDS = frozenset(
    {"nexus_trap_program", "name", "purpose", "inputs", "steps", "output"}
)
_STEP_FIELDS = frozenset({"op", "categories"})
_OUTPUT_FIELDS = frozenset({"format"})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
_INTEGER = re.compile(r"[-+]?(?:0|[1-9][0-9]*)$")
_NUMBER_LIKE = re.compile(
    r"[-+]?(?:(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+)$"
)
_NON_FINITE = re.compile(r"[-+]?(?:\.inf|\.nan|inf|nan)$", re.IGNORECASE)
_DOCUMENT_MARKER = re.compile(r"(?:---|\.\.\.)(?:\s|$)")


class TrapYAMLError(ValueError):
    """A bounded parser/schema failure with a stable public error code."""

    def __init__(self, code: str, message: str, *, line: int | None = None) -> None:
        self.code = code
        self.line = line
        suffix = f" at line {line}" if line is not None else ""
        super().__init__(f"{message}{suffix}")


@dataclass(frozen=True)
class CanonicalTrapProgram:
    """Validated JSON primitives and their formatting-independent identity."""

    tree: dict[str, Any]
    canonical_json: str
    program_sha256: str
    schema_version: str = SCHEMA_VERSION

    @property
    def program_id(self) -> str:
        return f"sha256:{self.program_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "canonical_program": json.loads(self.canonical_json),
            "program_sha256": self.program_sha256,
        }


@dataclass(frozen=True)
class _Line:
    number: int
    raw: str
    indent: int
    content: str


def _raise(code: str, message: str, line: int | None = None) -> None:
    raise TrapYAMLError(code, message, line=line)


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif quote == "'":
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 1
            elif char == "'":
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]
        index += 1
    return value


def _check_structural_line(value: str, line: int) -> None:
    stripped = value.strip()
    if not stripped:
        return
    if stripped.startswith("%"):
        _raise("trap_yaml_forbidden_directive", "YAML directives are forbidden", line)
    if _DOCUMENT_MARKER.fullmatch(stripped):
        _raise("trap_yaml_multiple_documents", "document markers and multiple documents are forbidden", line)

    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if quote == "'":
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                continue
            if char == "'":
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char in "&*!" and (index == 0 or value[index - 1].isspace() or value[index - 1] in ":,[{-"):
            feature = {"&": "anchors", "*": "aliases", "!": "tags"}[char]
            _raise("trap_yaml_forbidden_feature", f"YAML {feature} are forbidden", line)


def _split_mapping_entry(value: str, line: int) -> tuple[str, str]:
    stripped = value.lstrip()
    if stripped.startswith(("?", "[", "{")):
        _raise("trap_yaml_complex_key", "complex mapping keys are forbidden", line)
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif quote == "'":
            if char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 1
            elif char == "'":
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == ":" and (index + 1 == len(value) or value[index + 1].isspace()):
            return value[:index].strip(), value[index + 1 :].strip()
        index += 1
    _raise("trap_yaml_invalid_syntax", "expected a simple mapping entry", line)


def _parse_quoted(value: str, line: int) -> str:
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise TrapYAMLError("trap_yaml_invalid_scalar", "invalid double-quoted scalar", line=line) from exc
        if type(parsed) is not str:
            _raise("trap_yaml_invalid_scalar", "quoted scalar must be a string", line)
        return parsed
    if not value.endswith("'") or len(value) < 2:
        _raise("trap_yaml_invalid_scalar", "invalid single-quoted scalar", line)
    body = value[1:-1]
    index = 0
    while index < len(body):
        if body[index] == "'":
            if index + 1 >= len(body) or body[index + 1] != "'":
                _raise("trap_yaml_invalid_scalar", "invalid single-quoted scalar", line)
            index += 2
        else:
            index += 1
    return body.replace("''", "'")


def _parse_scalar(value: str, line: int) -> Any:
    value = value.strip()
    if not value:
        _raise("trap_yaml_invalid_scalar", "empty inline scalar", line)
    if value[0] in {'"', "'"}:
        return _parse_quoted(value, line)
    if value.startswith(("[", "{")):
        _raise("trap_yaml_complex_value", "flow collections are outside Trap YAML v1", line)
    if value in {">", "|"}:
        _raise("trap_yaml_invalid_scalar", "block scalar has no body", line)
    lowered = value.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INTEGER.fullmatch(value):
        try:
            return int(value, 10)
        except ValueError as exc:  # pragma: no cover - regex and Python agree
            raise TrapYAMLError("trap_yaml_invalid_scalar", "invalid integer", line=line) from exc
    if _NUMBER_LIKE.fullmatch(value) or _NON_FINITE.fullmatch(value):
        _raise("trap_yaml_unsupported_number", "floating-point scalars are forbidden", line)
    if value.startswith(("&", "*", "!")):
        _raise("trap_yaml_forbidden_feature", "anchors, aliases, and tags are forbidden", line)
    return value


def _parse_key(value: str, line: int) -> str:
    if not value:
        _raise("trap_yaml_complex_key", "empty mapping keys are forbidden", line)
    if value.startswith(('"', "'")):
        key = _parse_quoted(value, line)
    else:
        key = value
    if key == "<<":
        _raise("trap_yaml_forbidden_merge", "YAML merge keys are forbidden", line)
    if not _KEY.fullmatch(key):
        _raise("trap_yaml_complex_key", "only simple string mapping keys are accepted", line)
    return key


class _Parser:
    def __init__(self, text: str) -> None:
        self.lines: list[_Line] = []
        for number, raw in enumerate(text.splitlines(), start=1):
            if "\t" in raw:
                _raise("trap_yaml_invalid_indentation", "tabs are forbidden", number)
            if any(ord(char) < 32 for char in raw):
                _raise("trap_yaml_invalid_character", "control characters are forbidden", number)
            indent = len(raw) - len(raw.lstrip(" "))
            content = _strip_comment(raw[indent:]).rstrip()
            self.lines.append(_Line(number, raw, indent, content))

    def _next_nonblank(self, index: int) -> int:
        while index < len(self.lines) and not self.lines[index].content.strip():
            index += 1
        return index

    def parse(self) -> Any:
        start = self._next_nonblank(0)
        if start >= len(self.lines):
            _raise("trap_yaml_invalid_document", "Trap YAML document is empty")
        if self.lines[start].indent != 0:
            _raise("trap_yaml_invalid_indentation", "root value must not be indented", self.lines[start].number)
        value, end = self._parse_node(start, 0, 1)
        end = self._next_nonblank(end)
        if end != len(self.lines):
            _raise("trap_yaml_invalid_syntax", "unexpected trailing content", self.lines[end].number)
        return value

    def _parse_node(self, index: int, indent: int, depth: int) -> tuple[Any, int]:
        if depth > MAX_NESTING_DEPTH:
            _raise("trap_yaml_depth_exceeded", "Trap YAML nesting limit exceeded", self.lines[index].number)
        index = self._next_nonblank(index)
        if index >= len(self.lines):
            _raise("trap_yaml_invalid_syntax", "missing nested value")
        line = self.lines[index]
        if line.indent != indent:
            _raise("trap_yaml_invalid_indentation", "inconsistent indentation", line.number)
        _check_structural_line(line.content, line.number)
        if line.content == "-" or line.content.startswith("- "):
            return self._parse_sequence(index, indent, depth)
        return self._parse_mapping(index, indent, depth)

    def _parse_mapping(self, index: int, indent: int, depth: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while True:
            index = self._next_nonblank(index)
            if index >= len(self.lines):
                break
            line = self.lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                _raise("trap_yaml_invalid_indentation", "unexpected mapping indentation", line.number)
            if line.content == "-" or line.content.startswith("- "):
                break
            _check_structural_line(line.content, line.number)
            raw_key, remainder = _split_mapping_entry(line.content, line.number)
            key = _parse_key(raw_key, line.number)
            if key in result:
                _raise("trap_yaml_duplicate_key", f"duplicate mapping key: {key}", line.number)
            index += 1
            if remainder in {">", "|"}:
                value, index = self._parse_block_scalar(index, indent, remainder)
            elif remainder:
                value = _parse_scalar(remainder, line.number)
            else:
                child = self._next_nonblank(index)
                if child >= len(self.lines) or self.lines[child].indent <= indent:
                    _raise("trap_yaml_invalid_syntax", f"mapping value for {key} is missing", line.number)
                value, index = self._parse_node(child, self.lines[child].indent, depth + 1)
            result[key] = value
            if len(result) > MAX_MAPPING_ITEMS:
                _raise("trap_yaml_limit_exceeded", "mapping item limit exceeded", line.number)
        return result, index

    def _parse_sequence(self, index: int, indent: int, depth: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while True:
            index = self._next_nonblank(index)
            if index >= len(self.lines):
                break
            line = self.lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                _raise("trap_yaml_invalid_indentation", "unexpected sequence indentation", line.number)
            if not (line.content == "-" or line.content.startswith("- ")):
                break
            _check_structural_line(line.content, line.number)
            remainder = line.content[1:].strip()
            index += 1
            if not remainder:
                child = self._next_nonblank(index)
                if child >= len(self.lines) or self.lines[child].indent <= indent:
                    _raise("trap_yaml_invalid_syntax", "sequence item is missing", line.number)
                value, index = self._parse_node(child, self.lines[child].indent, depth + 1)
            else:
                try:
                    raw_key, raw_value = _split_mapping_entry(remainder, line.number)
                except TrapYAMLError as exc:
                    if exc.code != "trap_yaml_invalid_syntax":
                        raise
                    value = _parse_scalar(remainder, line.number)
                    child = self._next_nonblank(index)
                    if child < len(self.lines) and self.lines[child].indent > indent:
                        _raise("trap_yaml_invalid_indentation", "scalar sequence item cannot have children", self.lines[child].number)
                else:
                    key = _parse_key(raw_key, line.number)
                    if not raw_value:
                        _raise("trap_yaml_invalid_syntax", "inline mapping values must be scalars", line.number)
                    item: dict[str, Any] = {key: _parse_scalar(raw_value, line.number)}
                    continuation = self._next_nonblank(index)
                    if continuation < len(self.lines) and self.lines[continuation].indent > indent:
                        extra, index = self._parse_node(
                            continuation,
                            self.lines[continuation].indent,
                            depth + 1,
                        )
                        if type(extra) is not dict:
                            _raise("trap_yaml_invalid_syntax", "sequence mapping continuation must be a mapping", self.lines[continuation].number)
                        duplicates = set(item).intersection(extra)
                        if duplicates:
                            duplicate = sorted(duplicates)[0]
                            _raise("trap_yaml_duplicate_key", f"duplicate mapping key: {duplicate}", self.lines[continuation].number)
                        item.update(extra)
                    value = item
            result.append(value)
            if len(result) > MAX_SEQUENCE_ITEMS:
                _raise("trap_yaml_limit_exceeded", "sequence item limit exceeded", line.number)
        return result, index

    def _parse_block_scalar(self, index: int, parent_indent: int, style: str) -> tuple[str, int]:
        end = index
        nonblank: list[_Line] = []
        while end < len(self.lines):
            line = self.lines[end]
            if line.raw.strip() and line.indent <= parent_indent:
                break
            if line.raw.strip():
                nonblank.append(line)
            end += 1
        if not nonblank:
            return "", end
        block_indent = min(line.indent for line in nonblank)
        values = [line.raw[block_indent:].rstrip() if line.raw.strip() else "" for line in self.lines[index:end]]
        literal = "\n".join(values).strip()
        if style == "|":
            return literal, end
        return re.sub(r"(?<!\n)\n(?!\n)", " ", literal), end


def _check_primitive_limits(value: Any) -> None:
    scalar_count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal scalar_count
        if depth > MAX_NESTING_DEPTH:
            _raise("trap_yaml_depth_exceeded", "Trap YAML nesting limit exceeded")
        if type(item) is dict:
            if len(item) > MAX_MAPPING_ITEMS:
                _raise("trap_yaml_limit_exceeded", "mapping item limit exceeded")
            for key, child in item.items():
                if type(key) is not str:
                    _raise("trap_yaml_complex_key", "mapping keys must be strings")
                scalar_count += 1
                visit(child, depth + 1)
        elif type(item) is list:
            if len(item) > MAX_SEQUENCE_ITEMS:
                _raise("trap_yaml_limit_exceeded", "sequence item limit exceeded")
            for child in item:
                visit(child, depth + 1)
        elif item is None or type(item) in {str, int, bool}:
            scalar_count += 1
            if type(item) is str and len(item) > MAX_STRING_LENGTH:
                _raise("trap_yaml_limit_exceeded", "string scalar limit exceeded")
        else:
            _raise("trap_yaml_invalid_scalar", "only JSON string, integer, boolean, and null scalars are accepted")
        if scalar_count > MAX_SCALARS:
            _raise("trap_yaml_limit_exceeded", "scalar count limit exceeded")

    visit(value, 1)


def parse_trap_yaml(source: str | bytes) -> dict[str, Any]:
    """Parse the deliberately narrow Trap YAML presentation subset."""

    if isinstance(source, bytes):
        if len(source) > MAX_DOCUMENT_BYTES:
            _raise("trap_yaml_document_too_large", "Trap YAML document exceeds 16 KiB")
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TrapYAMLError("trap_yaml_invalid_encoding", "Trap YAML must be UTF-8") from exc
    elif type(source) is str:
        if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            _raise("trap_yaml_document_too_large", "Trap YAML document exceeds 16 KiB")
        text = source
    else:
        raise TypeError("Trap YAML source must be str or bytes")
    if text.startswith("\ufeff"):
        _raise("trap_yaml_invalid_encoding", "UTF-8 byte-order marks are forbidden")
    value = _Parser(text.replace("\r\n", "\n").replace("\r", "\n")).parse()
    if type(value) is not dict:
        _raise("trap_yaml_invalid_schema", "Trap YAML root must be a mapping")
    _check_primitive_limits(value)
    return value


def _require_fields(value: Mapping[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        _raise("trap_yaml_unknown_field", f"unknown {context} field: {sorted(unknown)[0]}")


def _require_identifier(value: Any, context: str) -> str:
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        _raise("trap_yaml_invalid_schema", f"{context} must be a lowercase identifier")
    return value


def validate_trap_program(tree: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a parsed primitive tree against the closed v1 schema."""

    if not isinstance(tree, Mapping):
        _raise("trap_yaml_invalid_schema", "Trap YAML root must be a mapping")
    tree = dict(tree)
    _check_primitive_limits(tree)
    _require_fields(tree, _TOP_LEVEL_FIELDS, "top-level")
    missing = _TOP_LEVEL_FIELDS.difference(tree)
    if missing:
        _raise("trap_yaml_invalid_schema", f"missing top-level field: {sorted(missing)[0]}")
    if type(tree["nexus_trap_program"]) is not int or tree["nexus_trap_program"] != 1:
        _raise("trap_yaml_invalid_schema", "nexus_trap_program must be integer 1")
    name = _require_identifier(tree["name"], "name")
    purpose = tree["purpose"]
    if type(purpose) is not str or not purpose.strip() or len(purpose) > 1_024:
        _raise("trap_yaml_invalid_schema", "purpose must be a non-empty bounded string")

    raw_inputs = tree["inputs"]
    if type(raw_inputs) is not list or not 1 <= len(raw_inputs) <= MAX_INPUTS:
        _raise("trap_yaml_invalid_schema", "inputs must contain between 1 and 16 identifiers")
    inputs = [_require_identifier(item, "input") for item in raw_inputs]
    if len(inputs) != len(set(inputs)):
        _raise("trap_yaml_invalid_schema", "inputs must be unique")

    raw_steps = tree["steps"]
    if type(raw_steps) is not list or not 1 <= len(raw_steps) <= MAX_STEPS:
        _raise("trap_yaml_invalid_schema", "steps must contain between 1 and 32 operations")
    steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(raw_steps):
        if type(raw_step) is not dict:
            _raise("trap_yaml_invalid_schema", f"step {index + 1} must be a mapping")
        _require_fields(raw_step, _STEP_FIELDS, "step")
        if "op" not in raw_step:
            _raise("trap_yaml_invalid_schema", f"step {index + 1} is missing op")
        op = raw_step["op"]
        if type(op) is not str or op not in OPERATIONS:
            _raise("trap_yaml_unknown_operation", "Trap YAML operation is not in the closed registry")
        step: dict[str, Any] = {"op": op}
        if "categories" in raw_step:
            if op != "separate_claims":
                _raise("trap_yaml_unknown_field", "categories is accepted only by separate_claims")
            raw_categories = raw_step["categories"]
            if type(raw_categories) is not list or not 1 <= len(raw_categories) <= MAX_CATEGORIES:
                _raise("trap_yaml_invalid_schema", "categories must contain between 1 and 16 identifiers")
            categories = [_require_identifier(item, "category") for item in raw_categories]
            if len(categories) != len(set(categories)):
                _raise("trap_yaml_invalid_schema", "categories must be unique")
            step["categories"] = categories
        elif op == "separate_claims":
            _raise("trap_yaml_invalid_schema", "separate_claims requires categories")
        steps.append(step)
    if steps[-1]["op"] != "emit_report" or any(step["op"] == "emit_report" for step in steps[:-1]):
        _raise("trap_yaml_invalid_schema", "emit_report must occur exactly once as the final step")

    raw_output = tree["output"]
    if type(raw_output) is not dict:
        _raise("trap_yaml_invalid_schema", "output must be a mapping")
    _require_fields(raw_output, _OUTPUT_FIELDS, "output")
    if raw_output.get("format") != "council_report" or type(raw_output.get("format")) is not str:
        _raise("trap_yaml_invalid_schema", "output.format must be council_report")

    normalized = {
        "nexus_trap_program": 1,
        "name": name,
        "purpose": purpose,
        "inputs": inputs,
        "steps": steps,
        "output": {"format": "council_report"},
    }
    _check_primitive_limits(normalized)
    return normalized


def canonicalize_trap_program(tree: Mapping[str, Any]) -> CanonicalTrapProgram:
    normalized = validate_trap_program(tree)
    encoded = canonical_json(normalized)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return CanonicalTrapProgram(normalized, encoded, digest)


def load_trap_program(source: str | bytes) -> CanonicalTrapProgram:
    """Parse, validate, canonicalize, and identify one Trap YAML program."""

    return canonicalize_trap_program(parse_trap_yaml(source))


__all__ = [
    "CanonicalTrapProgram",
    "MAX_CATEGORIES",
    "MAX_DOCUMENT_BYTES",
    "MAX_INPUTS",
    "MAX_NESTING_DEPTH",
    "MAX_STEPS",
    "OPERATIONS",
    "SCHEMA_VERSION",
    "TrapYAMLError",
    "canonicalize_trap_program",
    "load_trap_program",
    "parse_trap_yaml",
    "validate_trap_program",
]
