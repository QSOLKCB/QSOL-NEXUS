from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return stable UTF-8 JSON text for identity-bearing protocol values."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_ref(prefix: str, value: Any) -> str:
    payload = canonical_json(value).encode("utf-8")
    digest = hashlib.sha256(prefix.encode("utf-8") + b"\0" + payload).hexdigest()
    return f"{prefix}:{digest}"
