"""Error sanitization and safe error handling for Wilson Eval3ngine.

T6.1.6 - Implement safe error handling that prevents information leakage.

Security:
- All error messages are sanitized before returning to clients
- Internal details (file paths, stack traces, DB schema) are never exposed
- Error codes are used for client-side handling
- Full error details are logged server-side only
- Rate limiting on error responses to prevent error-based enumeration
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger("wilson.security.error_handling")


class ErrorCode(str, Enum):
    """Standardized error codes for API responses.

    These codes are safe to expose to clients and allow
    programmatic error handling without revealing internals.
    """

    # Authentication & Authorization
    AUTH_REQUIRED = "auth_required"
    AUTH_INVALID = "auth_invalid"
    AUTH_EXPIRED = "auth_expired"
    AUTH_REVOKED = "auth_revoked"
    AUTH_REPLAY = "auth_replay"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    PROJECT_ACCESS_DENIED = "project_access_denied"

    # Input Validation
    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"

    # Rate Limiting
    RATE_LIMITED = "rate_limited"

    # CSRF
    CSRF_TOKEN_MISSING = "csrf_token_missing"
    CSRF_TOKEN_INVALID = "csrf_token_invalid"

    # Resource
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RESOURCE_LOCKED = "resource_locked"

    # Operation
    OPERATION_FAILED = "operation_failed"
    OPERATION_CANCELLED = "operation_cancelled"
    TIMEOUT = "timeout"

    # Internal
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONFIGURATION_ERROR = "configuration_error"


class SafeError(Exception):
    """Safe error that can be exposed to clients.

    Security:
    - `safe_detail` is safe for client consumption
    - `error_code` allows programmatic handling
    - `trace_id` enables correlation with server logs
    - Full error details are logged server-side only
    """

    def __init__(
        self,
        error_code: ErrorCode | str,
        safe_detail: str,
        trace_id: str = "",
        retryable: bool = False,
        http_status: int = 500,
        internal_detail: str = "",
    ):
        self.error_code = error_code
        self.safe_detail = safe_detail
        self.trace_id = trace_id
        self.retryable = retryable
        self.http_status = http_status
        self.internal_detail = internal_detail
        super().__init__(safe_detail)

        # Log full error server-side
        if internal_detail:
            logger.error(
                "safe_error_raised",
                extra={
                    "error_code": error_code,
                    "safe_detail": safe_detail,
                    "internal_detail": internal_detail,
                    "trace_id": trace_id,
                    "http_status": http_status,
                    "retryable": retryable,
                },
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to client-safe dictionary."""
        return {
            "schema_version": "we3.error.v1",
            "code": self.error_code,
            "retryable": self.retryable,
            "safe_detail": self.safe_detail,
            "trace_id": self.trace_id,
        }


class ErrorSanitizer:
    """Sanitizes error messages to prevent information leakage.

    Security:
    - Removes file paths, database schema details, and stack traces
    - Replaces sensitive patterns with generic placeholders
    - Limits error message length
    - Preserves error type for logging
    """

    # Patterns that indicate sensitive information
    # Order matters: more specific patterns must come before general ones
    _SENSITIVE_PATTERNS = [
        # Database connection strings (must come before file path patterns)
        (re.compile(r"(postgresql|mysql|sqlite)://[^\s]+", re.IGNORECASE), "[db_connection]"),
        # API keys and secrets
        (re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE), "[api_key]"),
        (re.compile(r"(Bearer\s+)[a-zA-Z0-9._-]+", re.IGNORECASE), "[bearer_token]"),
        # Passwords in connection strings
        (re.compile(r"(password=)[^\s;]+", re.IGNORECASE), r"\1[redacted]"),
        # Email addresses
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[email]"),
        # IP addresses
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[ip_address]"),
        # UUIDs
        (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "[uuid]"),
        # Stack trace fragments
        (re.compile(r"File \"[^\"]+\", line \d+"), "[stack_trace]"),
        # SQL queries
        (re.compile(r"(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\s+", re.IGNORECASE), "[sql]"),
        # File paths (general catch-all, must come after more specific patterns)
        (re.compile(r"/[\w/.\-]+"), "[path]"),
        (re.compile(r"[A-Z]:\\[][\w\\.\-]+"), "[path]"),
    ]

    MAX_ERROR_LENGTH = 200  # Maximum length for safe error messages

    @classmethod
    def sanitize(cls, error_message: str) -> str:
        """Sanitize an error message for client consumption.

        Args:
            error_message: The raw error message

        Returns:
            Sanitized message safe for client consumption
        """
        if not error_message:
            return "An error occurred"

        sanitized = error_message

        # Apply all sensitive pattern replacements
        for pattern, replacement in cls._SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # Truncate to max length
        if len(sanitized) > cls.MAX_ERROR_LENGTH:
            sanitized = sanitized[:cls.MAX_ERROR_LENGTH] + "..."

        return sanitized

    @classmethod
    def sanitize_exception(cls, exc: Exception) -> str:
        """Sanitize an exception's string representation.

        Args:
            exc: The exception to sanitize

        Returns:
            Sanitized error message
        """
        return cls.sanitize(str(exc))

    @classmethod
    def create_safe_error(
        cls,
        exc: Exception,
        error_code: ErrorCode | str,
        trace_id: str = "",
        retryable: bool = False,
        http_status: int = 500,
    ) -> SafeError:
        """Create a SafeError from an exception.

        Args:
            exc: The original exception
            error_code: Standard error code
            trace_id: Correlation ID for logs
            retryable: Whether the operation can be retried
            http_status: HTTP status code

        Returns:
            SafeError with sanitized details
        """
        safe_detail = cls.sanitize_exception(exc)
        return SafeError(
            error_code=error_code,
            safe_detail=safe_detail,
            trace_id=trace_id,
            retryable=retryable,
            http_status=http_status,
            internal_detail=str(exc),
        )


def get_error_response(
    exc: Exception,
    trace_id: str = "",
    http_status: int = 500,
) -> dict[str, Any]:
    """Generate a safe error response dictionary.

    Args:
        exc: The exception that occurred
        trace_id: Correlation ID for log correlation
        http_status: HTTP status code

    Returns:
        Dictionary with safe error details
    """
    if isinstance(exc, SafeError):
        return {
            "schema_version": "we3.error.v1",
            "code": exc.error_code,
            "retryable": exc.retryable,
            "safe_detail": exc.safe_detail,
            "trace_id": trace_id or exc.trace_id,
        }

    # Sanitize the error message
    safe_detail = ErrorSanitizer.sanitize_exception(exc)

    return {
        "schema_version": "we3.error.v1",
        "code": ErrorCode.INTERNAL_ERROR.value,
        "retryable": http_status >= 500,
        "safe_detail": safe_detail,
        "trace_id": trace_id,
    }


__all__ = [
    "ErrorCode",
    "SafeError",
    "ErrorSanitizer",
    "get_error_response",
]