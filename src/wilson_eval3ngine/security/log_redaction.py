"""Central redaction for structured log records.

The filter removes credential-bearing URL userinfo, authorization values,
secret-like fields, control characters, and oversized free-form diagnostics.
It intentionally mutates only logging metadata; application values are not
modified.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|cookie|password|passwd|secret|token|api[_-]?key|"
    r"credential|private[_-]?key|database[_-]?url|redis[_-]?url)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*")
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_TEXT = 2048
_MAX_DEPTH = 6


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc or "@" not in parsed.netloc:
        return value
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, f"[redacted]@{host}", parsed.path, parsed.query, ""))


def redact_log_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[redacted]"
    if depth >= _MAX_DEPTH:
        return "[truncated]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_log_value(
                item_value,
                key=str(item_key),
                depth=depth + 1,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_log_value(item, depth=depth + 1) for item in value]
    if isinstance(value, bytes):
        return f"[bytes:{len(value)}]"
    if isinstance(value, str):
        text = _CONTROL.sub("", value)[:_MAX_TEXT]
        text = _redact_url(text)
        text = _BEARER.sub("Bearer [redacted]", text)
        text = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
        return text
    return value


class SensitiveLogFilter(logging.Filter):
    """Redact nonstandard LogRecord attributes and exception arguments."""

    _STANDARD = frozenset(logging.makeLogRecord({}).__dict__)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, Mapping):
            record.args = redact_log_value(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_log_value(value) for value in record.args)

        for name, value in tuple(record.__dict__.items()):
            if name not in self._STANDARD:
                setattr(record, name, redact_log_value(value, key=name))
        return True


def install_sensitive_log_filter(logger: logging.Logger | None = None) -> SensitiveLogFilter:
    """Install one filter on the selected logger and all existing handlers."""

    selected = logger or logging.getLogger()
    for existing in selected.filters:
        if isinstance(existing, SensitiveLogFilter):
            return existing
    log_filter = SensitiveLogFilter()
    selected.addFilter(log_filter)
    for handler in selected.handlers:
        handler.addFilter(log_filter)
    return log_filter


__all__ = ["SensitiveLogFilter", "install_sensitive_log_filter", "redact_log_value"]
