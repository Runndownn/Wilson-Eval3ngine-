from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

try:
    from uuid import uuid7  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Python < 3.14 compatibility
    uuid7 = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    value = uuid7() if uuid7 is not None else uuid4()
    return f"{prefix}_{value.hex}"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def sha256_hex(value: bytes | str | Any) -> str:
    if isinstance(value, str):
        payload = value.encode("utf-8")
    elif isinstance(value, bytes):
        payload = value
    else:
        payload = canonical_json(value)
    return sha256(payload).hexdigest()
