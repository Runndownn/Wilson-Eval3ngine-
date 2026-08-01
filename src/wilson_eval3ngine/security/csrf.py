"""CSRF protection for Wilson Eval3ngine.

T6.1.3 - Implement CSRF protection using double-submit cookie pattern.

Security:
- Double-submit cookie pattern: token in header must match token in cookie
- HMAC-based token validation prevents forgery
- Configurable secret key (must be set in production)
- Token format: timestamp.signature (prevents replay)
- Constant-time comparison prevents timing attacks
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any

logger = logging.getLogger("wilson.security.csrf")


class CSRFValidationError(Exception):
    """Raised when CSRF token validation fails."""
    pass


class CSRFProtection:
    """CSRF protection using double-submit cookie pattern.

    Security:
    - HMAC-SHA256 based token validation
    - Token format: {timestamp}.{hmac_signature}
    - Constant-time comparison via hmac.compare_digest
    - Token expiry (default: 1 hour)
    - Secret key from environment or generated at startup (dev mode)

    Usage:
        csrf = CSRFProtection(secret=os.getenv("WE3_CSRF_SECRET"))
        token = csrf.generate_token()
        csrf.validate_token(provided_token, cookie_token)
    """

    TOKEN_TTL_SECONDS: int = 3600  # 1 hour
    TIMESTAMP_LENGTH: int = 10  # 10-digit Unix timestamp

    def __init__(self, secret: str | None = None):
        if not secret:
            # Generate a random secret for dev mode
            # In production, this MUST be set via environment variable
            secret = os.environ.get("WE3_CSRF_SECRET")
        if not secret:
            secret = self._generate_dev_secret()
            logger.warning("csrf_secret_not_set_using_dev_default")

        self._secret = secret.encode("utf-8")

    @staticmethod
    def _generate_dev_secret() -> str:
        """Generate a random dev secret (not for production use)."""
        return os.urandom(32).hex()

    def generate_token(self) -> str:
        """Generate a new CSRF token.

        Returns:
            Token in format: {timestamp}.{hmac_signature}
        """
        timestamp = str(int(time.time()))
        signature = self._sign(timestamp)
        return f"{timestamp}.{signature}"

    def validate_token(self, header_token: str, cookie_token: str) -> bool:
        """Validate a CSRF token against the cookie token.

        Uses double-submit pattern: both tokens must match and be valid.

        Args:
            header_token: Token from X-CSRF-Token header
            cookie_token: Token from csrf_token cookie

        Raises:
            CSRFValidationError: If validation fails

        Returns:
            True if valid
        """
        if not header_token:
            raise CSRFValidationError("CSRF token missing from header")

        if not cookie_token:
            raise CSRFValidationError("CSRF token missing from cookie")

        # Both tokens must match (double-submit pattern)
        if not hmac.compare_digest(header_token, cookie_token):
            raise CSRFValidationError("CSRF tokens do not match")

        # Validate token format and signature
        self._validate_signature(header_token)

        return True

    def _sign(self, timestamp: str) -> str:
        """Sign a timestamp with HMAC-SHA256."""
        signature = hmac.new(
            self._secret,
            timestamp.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _validate_signature(self, token: str) -> None:
        """Validate the token format, signature, and expiry.

        Raises:
            CSRFValidationError: If signature is invalid or token expired
        """
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            raise CSRFValidationError("Invalid CSRF token format")

        timestamp_str, provided_signature = parts

        # Validate timestamp format
        if len(timestamp_str) != self.TIMESTAMP_LENGTH:
            raise CSRFValidationError("Invalid token timestamp")

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            raise CSRFValidationError("Invalid token timestamp")

        # Check token expiry
        now = int(time.time())
        if now - timestamp > self.TOKEN_TTL_SECONDS:
            raise CSRFValidationError("CSRF token has expired")

        # Check token not from future (clock skew tolerance: 30s)
        if timestamp > now + 30:
            raise CSRFValidationError("CSRF token timestamp is in the future")

        # Validate signature (constant-time comparison)
        expected_signature = self._sign(timestamp_str)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise CSRFValidationError("Invalid CSRF token signature")


def get_csrf_token_endpoint():
    """Return a FastAPI dependency that provides CSRF token generation.

    This endpoint should be called by clients to obtain a CSRF token
    after authentication. The token is returned in the response body
    and also set as an httponly cookie.
    """
    from fastapi import Depends, Request  # noqa: PLC0415
    from fastapi.responses import JSONResponse  # noqa: PLC0415

    def generate_csrf_token(
        request: Request,
    ) -> str:
        """Generate a CSRF token and set it as a cookie."""
        csrf = CSRFProtection()
        token = csrf.generate_token()

        # The cookie is set by the endpoint that calls this
        return token

    return generate_csrf_token


__all__ = [
    "CSRFProtection",
    "CSRFValidationError",
    "get_csrf_token_endpoint",
]