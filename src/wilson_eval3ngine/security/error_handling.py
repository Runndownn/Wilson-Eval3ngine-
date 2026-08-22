"""Client-safe error contracts and internal diagnostic redaction.

Unexpected exception text is never a client contract.  It may contain paths,
query fragments, provider messages, identifiers, or secrets that no regex set
can prove complete.  Public responses therefore use bounded predefined details;
redaction remains available for internal logs and deliberately safe errors.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger("wilson.security.error_handling")


class ErrorCode(str, Enum):
    AUTH_REQUIRED = "auth_required"
    AUTH_INVALID = "auth_invalid"
    AUTH_EXPIRED = "auth_expired"
    AUTH_REVOKED = "auth_revoked"
    AUTH_REPLAY = "auth_replay"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    PROJECT_ACCESS_DENIED = "project_access_denied"

    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"

    RATE_LIMITED = "rate_limited"
    CSRF_TOKEN_MISSING = "csrf_token_missing"
    CSRF_TOKEN_INVALID = "csrf_token_invalid"

    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RESOURCE_LOCKED = "resource_locked"

    OPERATION_FAILED = "operation_failed"
    OPERATION_CANCELLED = "operation_cancelled"
    TIMEOUT = "timeout"

    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONFIGURATION_ERROR = "configuration_error"


_PUBLIC_DEFAULTS: dict[str, str] = {
    ErrorCode.AUTH_REQUIRED.value: "authentication is required",
    ErrorCode.AUTH_INVALID.value: "authentication failed",
    ErrorCode.AUTH_EXPIRED.value: "authentication token has expired",
    ErrorCode.AUTH_REVOKED.value: "authentication token is no longer valid",
    ErrorCode.AUTH_REPLAY.value: "authentication token is no longer valid",
    ErrorCode.INSUFFICIENT_PERMISSIONS.value: "operation is not permitted",
    ErrorCode.PROJECT_ACCESS_DENIED.value: "project access is not permitted",
    ErrorCode.VALIDATION_ERROR.value: "request validation failed",
    ErrorCode.INVALID_INPUT.value: "request input is invalid",
    ErrorCode.MISSING_REQUIRED_FIELD.value: "a required field is missing",
    ErrorCode.PAYLOAD_TOO_LARGE.value: "request payload is too large",
    ErrorCode.UNSUPPORTED_MEDIA_TYPE.value: "request media type is not supported",
    ErrorCode.RATE_LIMITED.value: "rate limit exceeded",
    ErrorCode.CSRF_TOKEN_MISSING.value: "request verification token is required",
    ErrorCode.CSRF_TOKEN_INVALID.value: "request verification token is invalid",
    ErrorCode.NOT_FOUND.value: "resource was not found",
    ErrorCode.CONFLICT.value: "request conflicts with current resource state",
    ErrorCode.RESOURCE_LOCKED.value: "resource is currently locked",
    ErrorCode.OPERATION_FAILED.value: "operation failed",
    ErrorCode.OPERATION_CANCELLED.value: "operation was cancelled",
    ErrorCode.TIMEOUT.value: "operation timed out",
    ErrorCode.INTERNAL_ERROR.value: "internal server error",
    ErrorCode.SERVICE_UNAVAILABLE.value: "service is unavailable",
    ErrorCode.CONFIGURATION_ERROR.value: "service configuration is invalid",
}


class SafeError(Exception):
    """An explicitly authored error that is safe to serialize to a client."""

    def __init__(
        self,
        error_code: ErrorCode | str,
        safe_detail: str,
        trace_id: str = "",
        retryable: bool = False,
        http_status: int = 500,
        internal_detail: str = "",
    ) -> None:
        self.error_code = error_code
        self.safe_detail = safe_detail
        self.trace_id = trace_id
        self.retryable = retryable
        self.http_status = http_status
        self.internal_detail = internal_detail
        super().__init__(safe_detail)

        if internal_detail:
            logger.error(
                "safe_error_raised",
                extra={
                    "error_code": str(error_code),
                    "safe_detail": safe_detail,
                    "internal_detail": ErrorSanitizer.sanitize(internal_detail),
                    "trace_id": trace_id,
                    "http_status": http_status,
                    "retryable": retryable,
                },
            )

    def to_dict(self) -> dict[str, Any]:
        code = self.error_code.value if isinstance(self.error_code, ErrorCode) else str(self.error_code)
        return {
            "schema_version": "we3.error.v1",
            "code": code,
            "retryable": self.retryable,
            "safe_detail": self.safe_detail,
            "trace_id": self.trace_id,
        }


class ErrorSanitizer:
    """Best-effort redaction for internal diagnostics, not public disclosure."""

    _SENSITIVE_PATTERNS = [
        (re.compile(r"(?:postgresql|postgres|mysql|redis|sqlite)://[^\s]+", re.IGNORECASE), "[connection]"),
        (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "[api_key]"),
        (re.compile(r"Bearer\s+[a-zA-Z0-9._~+/=-]+", re.IGNORECASE), "[bearer_token]"),
        (re.compile(r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+", re.IGNORECASE), r"\1=[redacted]"),
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[email]"),
        (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[ip_address]"),
        (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "[uuid]"),
        (re.compile(r"File \"[^\"]+\", line \d+"), "[stack_trace]"),
        (re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s+", re.IGNORECASE), "[sql] "),
        (re.compile(r"/[\w/.\-]+"), "[path]"),
        (re.compile(r"[A-Z]:\\[\w\\.\-]+"), "[path]"),
    ]
    MAX_ERROR_LENGTH = 200

    @classmethod
    def sanitize(cls, error_message: str) -> str:
        if not error_message:
            return "An error occurred"
        sanitized = str(error_message)
        for pattern, replacement in cls._SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        sanitized = "".join(ch for ch in sanitized if ch >= " " or ch in "\t")
        if len(sanitized) > cls.MAX_ERROR_LENGTH:
            sanitized = sanitized[: cls.MAX_ERROR_LENGTH] + "..."
        return sanitized

    @classmethod
    def sanitize_exception(cls, exc: Exception) -> str:
        """Return a fixed public detail for an unexpected exception.

        The exception argument is intentionally unused for the public message.
        Call ``sanitize(str(exc))`` explicitly when producing a protected
        internal diagnostic.
        """
        del exc
        return _PUBLIC_DEFAULTS[ErrorCode.OPERATION_FAILED.value]

    @classmethod
    def create_safe_error(
        cls,
        exc: Exception,
        error_code: ErrorCode | str,
        trace_id: str = "",
        retryable: bool = False,
        http_status: int = 500,
    ) -> SafeError:
        code = error_code.value if isinstance(error_code, ErrorCode) else str(error_code)
        safe_detail = _PUBLIC_DEFAULTS.get(code, "request could not be completed")
        return SafeError(
            error_code=error_code,
            safe_detail=safe_detail,
            trace_id=trace_id,
            retryable=retryable,
            http_status=http_status,
            internal_detail=cls.sanitize(str(exc)),
        )


def get_error_response(
    exc: Exception,
    trace_id: str = "",
    http_status: int = 500,
) -> dict[str, Any]:
    if isinstance(exc, SafeError):
        return {
            "schema_version": "we3.error.v1",
            "code": exc.error_code.value if isinstance(exc.error_code, ErrorCode) else str(exc.error_code),
            "retryable": exc.retryable,
            "safe_detail": exc.safe_detail,
            "trace_id": trace_id or exc.trace_id,
        }

    return {
        "schema_version": "we3.error.v1",
        "code": ErrorCode.INTERNAL_ERROR.value,
        "retryable": http_status >= 500,
        "safe_detail": _PUBLIC_DEFAULTS[ErrorCode.INTERNAL_ERROR.value],
        "trace_id": trace_id,
    }


__all__ = [
    "ErrorCode",
    "SafeError",
    "ErrorSanitizer",
    "get_error_response",
]
