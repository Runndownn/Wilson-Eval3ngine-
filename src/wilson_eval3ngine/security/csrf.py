"""CSRF token primitive for future ambient-cookie authentication paths.

Current production API authentication uses explicit bearer headers and therefore
does not rely on CSRF tokens. If cookie/session credentials are introduced,
this primitive provides a double-submit token with an HMAC-authenticated
issuance time and random nonce. The HMAC secret must be bound during application
composition in staging/production.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time

logger = logging.getLogger("wilson.security.csrf")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class CSRFValidationError(Exception):
    """Raised when CSRF token validation fails."""


class CSRFProtection:
    """HMAC-authenticated double-submit CSRF token primitive."""

    TOKEN_TTL_SECONDS: int = 3600
    TIMESTAMP_LENGTH: int = 10

    def __init__(self, secret: str | None = None):
        if not secret:
            secret = os.environ.get("WE3_CSRF_SECRET")
        if not secret:
            secret = self._generate_dev_secret()
            logger.warning("csrf_secret_not_set_using_dev_default")
        if len(secret.encode("utf-8")) < 16:
            logger.warning("csrf_secret_shorter_than_recommended_minimum")
        self._secret = secret.encode("utf-8")

    @staticmethod
    def _generate_dev_secret() -> str:
        return os.urandom(32).hex()

    def generate_token(self) -> str:
        """Return a two-part token while binding a unique nonce under the HMAC.

        Earlier releases exposed ``timestamp.signature``. Keeping two
        dot-separated fields avoids breaking clients that split on the final dot,
        while the new second field is ``nonce:signature`` and therefore unique
        for every issuance even inside the same second.
        """
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)
        signed_part = f"{timestamp}.{nonce}"
        return f"{timestamp}.{nonce}:{self._sign(signed_part)}"

    def validate_token(self, header_token: str, cookie_token: str) -> bool:
        if not header_token:
            raise CSRFValidationError("CSRF token missing from header")
        if not cookie_token:
            raise CSRFValidationError("CSRF token missing from cookie")
        if len(header_token) > 512 or len(cookie_token) > 512:
            raise CSRFValidationError("Invalid CSRF token format")
        if not hmac.compare_digest(header_token, cookie_token):
            raise CSRFValidationError("CSRF tokens do not match")
        self._validate_signature(header_token)
        return True

    def _sign(self, value: str) -> str:
        return hmac.new(
            self._secret,
            value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _validate_signature(self, token: str) -> None:
        parts = token.split(".")
        if len(parts) != 2:
            raise CSRFValidationError("Invalid CSRF token format")
        timestamp_str, proof = parts

        if ":" in proof:
            nonce, provided_signature = proof.split(":", 1)
            if not _NONCE.fullmatch(nonce):
                raise CSRFValidationError("Invalid CSRF token format")
            signed_part = f"{timestamp_str}.{nonce}"
        else:
            # Legacy deterministic token emitted by earlier source revisions.
            # Current generation never uses this form.
            provided_signature = proof
            signed_part = timestamp_str

        if len(timestamp_str) != self.TIMESTAMP_LENGTH or not timestamp_str.isdigit():
            raise CSRFValidationError("Invalid token timestamp")
        timestamp = int(timestamp_str)
        now = int(time.time())
        if now - timestamp > self.TOKEN_TTL_SECONDS:
            raise CSRFValidationError("CSRF token has expired")
        if timestamp > now + 30:
            raise CSRFValidationError("CSRF token timestamp is in the future")

        expected_signature = self._sign(signed_part)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise CSRFValidationError("Invalid CSRF token signature")


def get_csrf_token_endpoint():
    """Compatibility dependency factory for applications that issue CSRF tokens."""
    from fastapi import Request

    def generate_csrf_token(request: Request) -> str:
        del request
        return CSRFProtection().generate_token()

    return generate_csrf_token


__all__ = [
    "CSRFProtection",
    "CSRFValidationError",
    "get_csrf_token_endpoint",
]
