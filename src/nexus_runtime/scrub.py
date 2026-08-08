from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ScrubEvent:
    secret_type: str
    placeholder: str


@dataclass(frozen=True)
class ScrubResult:
    text: str
    events: tuple[ScrubEvent, ...]

    @property
    def changed(self) -> bool:
        return bool(self.events)


@dataclass(frozen=True)
class _Pattern:
    name: str
    regex: re.Pattern[str]
    secret_group: str = "secret"


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        "PRIVATE_KEY",
        re.compile(
            r"(?P<secret>-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----)",
            re.I | re.S,
        ),
    ),
    _Pattern("GITHUB_TOKEN", re.compile(r"(?P<secret>gh[pousr]_[A-Za-z0-9]{20,})")),
    _Pattern("OPENAI_STYLE_TOKEN", re.compile(r"(?P<secret>sk-[A-Za-z0-9_-]{20,})")),
    _Pattern("STRIPE_SECRET", re.compile(r"(?P<secret>(?:sk|rk)_live_[A-Za-z0-9]{16,})")),
    _Pattern("SLACK_TOKEN", re.compile(r"(?P<secret>xox[baprs]-[A-Za-z0-9-]{16,})")),
    _Pattern("GOOGLE_API_KEY", re.compile(r"(?P<secret>AIza[0-9A-Za-z_-]{30,})")),
    _Pattern("AWS_ACCESS_KEY", re.compile(r"(?P<secret>(?:AKIA|ASIA)[A-Z0-9]{16})")),
    _Pattern(
        "JWT",
        re.compile(r"(?P<secret>eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"),
    ),
    _Pattern(
        "BEARER_TOKEN",
        re.compile(r"(?i)(?:authorization\s*:\s*)?bearer\s+(?P<secret>[A-Za-z0-9._~+/=-]{16,})"),
    ),
    _Pattern(
        "ASSIGNED_SECRET",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|refresh[_-]?token|password|passwd|secret|token)\b"
            r"\s*[:=]\s*[\"']?(?P<secret>[A-Za-z0-9._~+/=-]{12,})[\"']?"
        ),
    ),
    _Pattern(
        "URL_CREDENTIAL",
        re.compile(r"(?i)https?://[^\s/:@]+:(?P<secret>[^\s/@]{8,})@"),
    ),
)


class SecretScrubber:
    """Deterministic, local, high-confidence redaction for semantic user text.

    Placeholders are assigned by secret type and first appearance order. Repeated
    occurrences of the same secret in one scrub operation receive the same
    placeholder. No secret hash or secret material is included in the output.
    """

    def __init__(self, patterns: Iterable[_Pattern] = _PATTERNS) -> None:
        self._patterns = tuple(patterns)

    def scrub(self, text: str) -> ScrubResult:
        if not isinstance(text, str):
            raise TypeError("SecretScrubber accepts text only")

        seen: dict[tuple[str, str], str] = {}
        counters: dict[str, int] = {}
        events: list[ScrubEvent] = []
        output = text

        for pattern in self._patterns:
            def replace(match: re.Match[str], *, _pattern: _Pattern = pattern) -> str:
                secret = match.group(_pattern.secret_group)
                key = (_pattern.name, secret)
                placeholder = seen.get(key)
                if placeholder is None:
                    counters[_pattern.name] = counters.get(_pattern.name, 0) + 1
                    placeholder = f"<REDACTED:{_pattern.name}:{counters[_pattern.name]}>"
                    seen[key] = placeholder
                    events.append(ScrubEvent(_pattern.name, placeholder))

                start, end = match.span(_pattern.secret_group)
                whole = match.group(0)
                relative_start = start - match.start(0)
                relative_end = end - match.start(0)
                return whole[:relative_start] + placeholder + whole[relative_end:]

            output = pattern.regex.sub(replace, output)

        return ScrubResult(output, tuple(events))
