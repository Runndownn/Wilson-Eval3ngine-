"""Input validation and sanitization for Wilson Eval3ngine.

T6.1.4 - Implement comprehensive input validation at API boundary.

Security:
- Project ID format validation (prevents injection, path traversal)
- Idempotency key format validation
- Content-type validation
- Request body structure validation
- Safe error messages (never expose internal details)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("wilson.security.input_validation")


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, message: str, error_code: str = "validation_error"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ProjectIdValidator:
    """Validates project IDs against security requirements.

    Security:
    - Project IDs must be alphanumeric with underscores/hyphens only
    - Max length: 64 characters
    - Prevents SQL injection, path traversal, and other injection attacks
    - Format: ^[a-zA-Z0-9_-]{1,64}$
    """

    # Safe pattern: alphanumeric, underscore, hyphen, 1-64 chars
    _PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    MAX_LENGTH = 64

    @classmethod
    def validate(cls, project_id: str) -> str:
        """Validate a project ID.

        Args:
            project_id: The project ID to validate

        Returns:
            The validated project ID

        Raises:
            ValidationError: If the project ID is invalid
        """
        if not project_id:
            raise ValidationError("Project ID is required", "project_id_required")

        if not isinstance(project_id, str):
            raise ValidationError("Project ID must be a string", "project_id_type")

        if len(project_id) > cls.MAX_LENGTH:
            raise ValidationError(
                f"Project ID exceeds maximum length of {cls.MAX_LENGTH}",
                "project_id_too_long",
            )

        if not cls._PATTERN.match(project_id):
            raise ValidationError(
                "Project ID contains invalid characters. "
                "Only alphanumeric characters, underscores, and hyphens are allowed.",
                "project_id_invalid_chars",
            )

        # Additional check: prevent directory traversal patterns
        if ".." in project_id or "/" in project_id or "\\" in project_id:
            raise ValidationError(
                "Project ID contains path traversal characters",
                "project_id_path_traversal",
            )

        # Prevent SQL injection patterns
        sql_patterns = [
            "' OR ", "' OR'", "' OR 1=1",
            "'; DROP", "'; DELETE", "'; INSERT", "'; UPDATE",
            "UNION SELECT", "EXEC(", "--", "/*", "*/",
        ]
        lower_id = project_id.lower()
        for pattern in sql_patterns:
            if pattern.lower() in lower_id:
                raise ValidationError(
                    "Project ID contains prohibited SQL pattern",
                    "project_id_sql_injection",
                )

        return project_id

    @classmethod
    def sanitize(cls, project_id: str) -> str:
        """Sanitize a project ID by removing dangerous characters.

        This is a defense-in-depth measure; validation should still be performed.
        """
        if not project_id:
            return ""
        # Remove any characters not in the safe set
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", project_id)
        # Truncate to max length
        return sanitized[:cls.MAX_LENGTH]


class IdempotencyKeyValidator:
    """Validates idempotency keys for API requests.

    Security:
    - Keys must be alphanumeric with hyphens only
    - Max length: 128 characters
    - Prevents injection attacks through idempotency keys
    """

    _PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
    MAX_LENGTH = 128

    @classmethod
    def validate(cls, key: str) -> str:
        """Validate an idempotency key.

        Args:
            key: The idempotency key to validate

        Returns:
            The validated key

        Raises:
            ValidationError: If the key is invalid
        """
        if not key:
            raise ValidationError("Idempotency key is required", "idempotency_key_required")

        if not isinstance(key, str):
            raise ValidationError("Idempotency key must be a string", "idempotency_key_type")

        if len(key) > cls.MAX_LENGTH:
            raise ValidationError(
                f"Idempotency key exceeds maximum length of {cls.MAX_LENGTH}",
                "idempotency_key_too_long",
            )

        if not cls._PATTERN.match(key):
            raise ValidationError(
                "Idempotency key contains invalid characters",
                "idempotency_key_invalid",
            )

        return key


class ContentTypeValidator:
    """Validates content types for API requests.

    Security:
    - Ensures requests have expected content types
    - Prevents content-type confusion attacks
    - Rejects malformed content types
    """

    _ALLOWED_JSON_TYPES = {
        "application/json",
        "application/json; charset=utf-8",
        "application/json; charset=UTF-8",
    }
    _ALLOWED_FORM_TYPES = {
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }

    def validate_json(self, content_type: str) -> tuple[bool, str]:
        """Validate that content type is JSON.

        Args:
            content_type: The Content-Type header value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content_type:
            return False, "Content-Type header is required for JSON requests"

        # Normalize: strip charset and whitespace
        normalized = content_type.strip().lower()
        # Remove charset parameter for comparison
        if ";" in normalized:
            normalized = normalized.split(";")[0].strip()

        if normalized != "application/json":
            return False, "Content-Type must be application/json"

        return True, ""

    def validate_form(self, content_type: str) -> tuple[bool, str]:
        """Validate that content type is form data.

        Args:
            content_type: The Content-Type header value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content_type:
            return False, "Content-Type header is required for form requests"

        normalized = content_type.strip().lower()
        if ";" in normalized:
            normalized = normalized.split(";")[0].strip()

        if normalized not in self._ALLOWED_FORM_TYPES:
            return False, "Content-Type must be application/x-www-form-urlencoded or multipart/form-data"

        return True, ""


class InputSanitizer:
    """Sanitizes input strings to prevent injection attacks.

    Security:
    - Strips dangerous characters from user input
    - Escapes HTML entities
    - Truncates overly long strings
    - Removes null bytes
    """

    MAX_STRING_LENGTH = 10_000
    _HTML_ESCAPE_MAP = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    @classmethod
    def sanitize_string(cls, value: str, max_length: int | None = None) -> str:
        """Sanitize a string value.

        Args:
            value: The string to sanitize
            max_length: Maximum allowed length (default: MAX_STRING_LENGTH)

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return ""

        max_len = max_length if max_length is not None else cls.MAX_STRING_LENGTH

        # Remove null bytes
        sanitized = value.replace("\x00", "")

        # Truncate to max length
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len]

        # Escape HTML entities
        for char, escape in cls._HTML_ESCAPE_MAP.items():
            sanitized = sanitized.replace(char, escape)

        return sanitized

    @classmethod
    def sanitize_path_component(cls, value: str) -> str:
        """Sanitize a path component to prevent path traversal.

        Args:
            value: The path component to sanitize

        Returns:
            Sanitized path component (no traversal characters)
        """
        if not isinstance(value, str):
            return ""

        # Remove path traversal characters
        sanitized = value.replace("..", "").replace("/", "").replace("\\", "")
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        # Truncate
        return sanitized[:256]


class InputValidator:
    """Comprehensive input validator for API requests.

    Combines all validators and sanitizers into a single interface.
    """

    def __init__(self):
        self.project_validator = ProjectIdValidator()
        self.idempotency_validator = IdempotencyKeyValidator()
        self.content_type_validator = ContentTypeValidator()
        self.sanitizer = InputSanitizer()

    def validate_project_id(self, project_id: str) -> str:
        """Validate and return a safe project ID."""
        return self.project_validator.validate(project_id)

    def validate_idempotency_key(self, key: str) -> str:
        """Validate and return a safe idempotency key."""
        return self.idempotency_validator.validate(key)

    def validate_json_content_type(self, content_type: str) -> tuple[bool, str]:
        """Validate JSON content type."""
        return self.content_type_validator.validate_json(content_type)

    def validate_form_content_type(self, content_type: str) -> tuple[bool, str]:
        """Validate form content type."""
        return self.content_type_validator.validate_form(content_type)

    def sanitize(self, value: str, max_length: int | None = None) -> str:
        """Sanitize a string value."""
        return self.sanitizer.sanitize_string(value, max_length)


__all__ = [
    "ValidationError",
    "ProjectIdValidator",
    "IdempotencyKeyValidator",
    "ContentTypeValidator",
    "InputSanitizer",
    "InputValidator",
]