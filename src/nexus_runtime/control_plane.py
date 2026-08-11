from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, BinaryIO, Iterator, TextIO


MAX_JSONL_LINE_BYTES = 1 * 1024 * 1024
MAX_REQUEST_DEPTH = 24
MAX_REQUEST_NODES = 8192
MAX_REQUEST_STRING_CHARS = 512 * 1024
MAX_REQUEST_LIST_ITEMS = 256
MAX_REQUEST_OBJECT_FIELDS = 256
MAX_REQUEST_KEY_CHARS = 256
MAX_QUESTION_CHARS = 32 * 1024
MAX_DIRECT_MESSAGE_CHARS = 32 * 1024
MAX_EVIDENCE_REFS = 32

# UNTESTED is the legacy runtime default. The remaining values mirror the
# machine-manifest epistemic vocabulary without allowing arbitrary durable
# labels to enter evidence snapshots.
ALLOWED_EVIDENCE_STATES = frozenset(
    {
        "UNTESTED",
        "OBSERVED",
        "EXECUTED",
        "VERIFIED",
        "INFERRED",
        "SIMULATED",
        "NOT_TESTED",
        "UNKNOWN",
    }
)


class RequestBudgetError(ValueError):
    """Public request exceeded a deterministic control-plane budget."""


@dataclass(frozen=True)
class BoundedLine:
    text: str | None
    error: str | None = None


def _walk_request(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_REQUEST_NODES:
            raise RequestBudgetError("request exceeds the maximum structural node count")
        if depth > MAX_REQUEST_DEPTH:
            raise RequestBudgetError("request exceeds the maximum nesting depth")

        if item is None or type(item) in {bool, int}:
            continue
        if type(item) is float:
            if not math.isfinite(item):
                raise RequestBudgetError("request numeric values must be finite")
            continue
        if isinstance(item, str):
            if len(item) > MAX_REQUEST_STRING_CHARS:
                raise RequestBudgetError("request string exceeds the maximum character limit")
            continue
        if isinstance(item, list):
            if len(item) > MAX_REQUEST_LIST_ITEMS:
                raise RequestBudgetError("request list exceeds the maximum item count")
            stack.extend((child, depth + 1) for child in reversed(item))
            continue
        if isinstance(item, dict):
            if len(item) > MAX_REQUEST_OBJECT_FIELDS:
                raise RequestBudgetError("request object exceeds the maximum field count")
            for key, child in reversed(tuple(item.items())):
                if not isinstance(key, str) or not key or len(key) > MAX_REQUEST_KEY_CHARS:
                    raise RequestBudgetError("request object keys must be bounded non-empty text")
                stack.append((child, depth + 1))
            continue
        raise RequestBudgetError("request contains a value outside the admitted JSON type set")


def validate_control_request(request: Any) -> None:
    if not isinstance(request, dict):
        raise RequestBudgetError("request must be a JSON object")
    _walk_request(request)

    operation = request.get("operation")
    if isinstance(operation, str):
        if operation == "council.run":
            question = request.get("question")
            if isinstance(question, str) and len(question) > MAX_QUESTION_CHARS:
                raise RequestBudgetError("Council question exceeds the maximum character limit")
            evidence_refs = request.get("evidence_refs", [])
            if isinstance(evidence_refs, list) and len(evidence_refs) > MAX_EVIDENCE_REFS:
                raise RequestBudgetError(
                    f"council.run permits at most {MAX_EVIDENCE_REFS} evidence references"
                )
            evidence_state = request.get("evidence_state", "UNTESTED")
            if isinstance(evidence_state, str) and evidence_state not in ALLOWED_EVIDENCE_STATES:
                allowed = ", ".join(sorted(ALLOWED_EVIDENCE_STATES))
                raise RequestBudgetError(f"evidence_state must be one of: {allowed}")
        elif operation == "actor.chat":
            message = request.get("message")
            if isinstance(message, str) and len(message) > MAX_DIRECT_MESSAGE_CHARS:
                raise RequestBudgetError("actor.chat message exceeds the maximum character limit")
            evidence_refs = request.get("evidence_refs", [])
            if isinstance(evidence_refs, list) and len(evidence_refs) > MAX_EVIDENCE_REFS:
                raise RequestBudgetError(
                    f"actor.chat permits at most {MAX_EVIDENCE_REFS} evidence references"
                )


def _consume_binary_remainder(stream: BinaryIO) -> None:
    while True:
        chunk = stream.readline(MAX_JSONL_LINE_BYTES + 1)
        if not chunk or chunk.endswith(b"\n"):
            return


def _consume_text_remainder(stream: TextIO) -> None:
    while True:
        chunk = stream.readline(MAX_JSONL_LINE_BYTES + 1)
        if not chunk or chunk.endswith("\n"):
            return


def iter_bounded_jsonl_lines(stream: TextIO) -> Iterator[BoundedLine]:
    """Yield bounded UTF-8 JSONL records without ever reading an unlimited line."""

    binary = getattr(stream, "buffer", None)
    if binary is not None:
        while True:
            raw = binary.readline(MAX_JSONL_LINE_BYTES + 1)
            if raw == b"":
                return
            if len(raw) > MAX_JSONL_LINE_BYTES:
                if not raw.endswith(b"\n"):
                    _consume_binary_remainder(binary)
                yield BoundedLine(None, "request line exceeds the JSONL byte limit")
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                yield BoundedLine(None, "request line is not valid UTF-8")
                continue
            yield BoundedLine(text)
        return

    while True:
        text = stream.readline(MAX_JSONL_LINE_BYTES + 1)
        if text == "":
            return
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_JSONL_LINE_BYTES or len(text) > MAX_JSONL_LINE_BYTES:
            if not text.endswith("\n"):
                _consume_text_remainder(stream)
            yield BoundedLine(None, "request line exceeds the JSONL byte limit")
            continue
        yield BoundedLine(text)


def control_plane_policy_snapshot() -> dict[str, object]:
    return {
        "schema": "nexus-control-plane-limits/1",
        "max_jsonl_line_bytes": MAX_JSONL_LINE_BYTES,
        "max_request_depth": MAX_REQUEST_DEPTH,
        "max_request_nodes": MAX_REQUEST_NODES,
        "max_request_string_chars": MAX_REQUEST_STRING_CHARS,
        "max_request_list_items": MAX_REQUEST_LIST_ITEMS,
        "max_request_object_fields": MAX_REQUEST_OBJECT_FIELDS,
        "max_question_chars": MAX_QUESTION_CHARS,
        "max_direct_message_chars": MAX_DIRECT_MESSAGE_CHARS,
        "max_evidence_refs": MAX_EVIDENCE_REFS,
        "allowed_evidence_states": sorted(ALLOWED_EVIDENCE_STATES),
    }
