"""OIDC bearer-token authentication for Wilson Eval3ngine.

The OIDC boundary validates issuer, audience, signing algorithm/key identity,
time claims, project/role/MFA claims, token subject, and JWT ID.  Revocation can
use Redis as a distributed authority; a caller that needs multi-worker security
must provide that authority through application composition rather than relying
on the bounded in-process fallback.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger("wilson.security.oidc")

_JTI = re.compile(r"^[A-Za-z0-9._~-]{1,256}$")
_SUBJECT = re.compile(r"^[^\x00-\x1f\x7f]{1,512}$")


class OIDCConfigurationError(Exception):
    """Raised when OIDC configuration or key material is unavailable/invalid."""


class TokenValidationError(Exception):
    """Raised when a token fails authentication validation."""


class TokenRevocationError(Exception):
    """Raised when a token has been explicitly revoked."""


class TokenRevocationList:
    """Bounded in-memory or Redis-backed JWT-ID revocation state."""

    def __init__(
        self,
        redis_client: Any | None = None,
        max_entries: int = 10_000,
        revocation_ttl_seconds: int = 3600,
    ) -> None:
        if max_entries <= 0 or revocation_ttl_seconds <= 0:
            raise ValueError("revocation limits must be positive")
        self._redis = redis_client
        self._max_entries = max_entries
        self._ttl = revocation_ttl_seconds
        self._store: OrderedDict[str, float] = OrderedDict()
        import threading

        self._lock = threading.Lock()

    @staticmethod
    def _validate_jti(jti: str) -> str:
        if not isinstance(jti, str) or not _JTI.fullmatch(jti):
            raise TokenValidationError("JWT ID claim has invalid format")
        return jti

    @classmethod
    def _redis_key(cls, jti: str) -> str:
        return f"we3:token_revoked:{cls._validate_jti(jti)}"

    def revoke(self, jti: str, token_ttl: int | None = None) -> None:
        if not jti:
            return
        jti = self._validate_jti(jti)
        ttl = token_ttl if token_ttl is not None else self._ttl
        if ttl <= 0:
            return

        if self._redis is not None:
            self._redis.setex(self._redis_key(jti), int(ttl), "1")
            return

        with self._lock:
            while len(self._store) >= self._max_entries:
                self._store.popitem(last=False)
            self._store[jti] = time.time() + ttl

    def is_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        jti = self._validate_jti(jti)

        if self._redis is not None:
            return bool(self._redis.exists(self._redis_key(jti)))

        with self._lock:
            now = time.time()
            expiry = self._store.get(jti)
            if expiry is None:
                return False
            if now > expiry:
                del self._store[jti]
                return False
            self._store.move_to_end(jti)
            return True

    def cleanup_expired(self) -> int:
        if self._redis is not None:
            return 0
        now = time.time()
        removed = 0
        with self._lock:
            expired = [jti for jti, expiry in self._store.items() if now > expiry]
            for jti in expired:
                del self._store[jti]
                removed += 1
        return removed


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    issuer: str
    jwks_uri: str
    audience: str
    authorization_issuer: str | None = None

    jwks_cache_ttl_seconds: int = 300
    jwks_refresh_buffer_seconds: int = 30

    require_mfa_claim: str = "amr"
    require_project_claim: str = "we3_project_id"
    require_role_claim: str = "we3_role"
    require_subject_claim: str = "sub"
    require_jti_claim: bool = True
    require_exp_claim: bool = True
    require_iat_claim: bool = True

    allowed_algorithms: tuple[str, ...] = ("RS256", "ES256")
    clock_skew_tolerance_seconds: int = 30
    revocation_ttl_seconds: int = 3600
    max_revocation_list_entries: int = 10_000
    max_jwks_keys: int = 64


class KeyCacheEntry:
    """Cached JWKS entry with bounded freshness."""

    def __init__(
        self,
        keys: dict[str, Any],
        fetched_at: float,
        ttl_seconds: int = 300,
        refresh_buffer_seconds: int = 30,
    ) -> None:
        self.keys = keys
        self.fetched_at = fetched_at
        self.expires_at = fetched_at + ttl_seconds
        self.refresh_buffer_seconds = min(refresh_buffer_seconds, ttl_seconds)

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def needs_refresh(self) -> bool:
        return time.time() >= self.expires_at - self.refresh_buffer_seconds


class JWKSClient:
    """JWKS verifier with bounded cache and distributed revocation support."""

    def __init__(
        self,
        settings: OIDCSettings,
        cache_ttl: int | None = None,
        redis_client: Any | None = None,
        revocation_list: TokenRevocationList | None = None,
    ) -> None:
        self._settings = settings
        self._cache_ttl = cache_ttl or settings.jwks_cache_ttl_seconds
        self._cached_keys: dict[str, Any] | None = None
        self._cache_entry: KeyCacheEntry | None = None
        self._redis = redis_client
        self._revocation_list = revocation_list or TokenRevocationList(
            redis_client=redis_client,
            max_entries=settings.max_revocation_list_entries,
            revocation_ttl_seconds=settings.revocation_ttl_seconds,
        )

    def get_signing_key(self, kid: str) -> Any | None:
        if not isinstance(kid, str) or not kid or len(kid) > 256:
            raise TokenValidationError("Token signing key ID is invalid")
        if self._cache_entry is None or self._cache_entry.needs_refresh():
            self._refresh_keys()
        return self._cached_keys.get(kid) if self._cached_keys else None

    def _refresh_keys(self) -> None:
        try:
            response = requests.get(
                self._settings.jwks_uri,
                timeout=5.0,
                headers={"Accept": "application/json"},
                allow_redirects=False,
            )
            response.raise_for_status()
            document = response.json()
            raw_keys = document.get("keys", []) if isinstance(document, dict) else []
            if not isinstance(raw_keys, list) or not raw_keys:
                raise OIDCConfigurationError("JWKS document contains no keys")
            if len(raw_keys) > self._settings.max_jwks_keys:
                raise OIDCConfigurationError("JWKS document exceeds key-count limit")

            keys: dict[str, Any] = {}
            for item in raw_keys:
                if not isinstance(item, dict):
                    raise OIDCConfigurationError("JWKS key is not an object")
                kid = item.get("kid")
                if not isinstance(kid, str) or not kid or len(kid) > 256:
                    raise OIDCConfigurationError("JWKS key has invalid kid")
                if kid in keys:
                    raise OIDCConfigurationError("JWKS contains duplicate kid")
                keys[kid] = item

            self._cached_keys = keys
            self._cache_entry = KeyCacheEntry(
                keys=keys,
                fetched_at=time.time(),
                ttl_seconds=self._cache_ttl,
                refresh_buffer_seconds=self._settings.jwks_refresh_buffer_seconds,
            )
            logger.info("jwks_refreshed", extra={"key_count": len(keys)})
        except Exception as exc:
            # Refresh-ahead may use a still-valid cache. Once the cache expires,
            # continuing indefinitely with stale key material would defeat key
            # rotation/revocation, so verification fails closed.
            if self._cache_entry is not None and not self._cache_entry.is_expired():
                logger.warning(
                    "jwks_refresh_failed_using_unexpired_cache",
                    extra={"error_class": type(exc).__name__},
                )
                return
            logger.error(
                "jwks_fetch_failed_no_valid_cache",
                extra={"error_class": type(exc).__name__},
            )
            if isinstance(exc, OIDCConfigurationError):
                raise
            raise OIDCConfigurationError("Unable to refresh OIDC signing keys") from exc

    def _validate_key_algorithm(self, header: dict[str, Any], jwk: dict[str, Any]) -> str:
        algorithm = header.get("alg")
        if algorithm not in self._settings.allowed_algorithms:
            raise TokenValidationError("Token signing algorithm is not allowed")
        declared = jwk.get("alg")
        if declared and declared != algorithm:
            raise TokenValidationError("Token algorithm does not match signing key")
        kty = jwk.get("kty")
        if algorithm.startswith("RS") and kty != "RSA":
            raise TokenValidationError("RSA token requires RSA signing key")
        if algorithm.startswith("ES") and kty != "EC":
            raise TokenValidationError("EC token requires EC signing key")
        return str(algorithm)

    def verify_token(self, token: str) -> dict[str, Any]:
        try:
            from jose import JWTError, jwt
        except ImportError as exc:
            logger.error("jose_package_missing")
            raise ImportError(
                "OIDC requires python-jose; install the oidc dependency set"
            ) from exc

        try:
            header = jwt.get_unverified_header(token)
            if not isinstance(header, dict):
                raise TokenValidationError("Token header is invalid")
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise TokenValidationError("Token missing key ID")

            key_dict = self.get_signing_key(kid)
            if key_dict is None:
                # One immediate refresh handles normal key rotation without
                # accepting an unknown key from an old cache.
                self._cache_entry = None
                self._refresh_keys()
                key_dict = self._cached_keys.get(kid) if self._cached_keys else None
            if key_dict is None:
                raise TokenValidationError("Unknown token signing key")

            algorithm = self._validate_key_algorithm(header, key_dict)
            key_pem = self._jwk_to_pem(key_dict)
            payload = jwt.decode(
                token,
                key=key_pem,
                algorithms=[algorithm],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                options={
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "leeway": self._settings.clock_skew_tolerance_seconds,
                },
            )
            if not isinstance(payload, dict):
                raise TokenValidationError("Token payload is invalid")
            self._validate_claims(payload)

            jti = payload.get("jti")
            if self._settings.require_jti_claim:
                if not isinstance(jti, str):
                    raise TokenValidationError("Token missing required JWT ID")
                TokenRevocationList._validate_jti(jti)
                if self._revocation_list.is_revoked(jti):
                    logger.warning(
                        "token_revoked",
                        extra={"jti_sha256": hashlib.sha256(jti.encode()).hexdigest()[:16]},
                    )
                    raise TokenRevocationError("Token has been revoked")

            return payload
        except (TokenValidationError, TokenRevocationError, OIDCConfigurationError):
            raise
        except JWTError as exc:
            raise TokenValidationError("JWT validation failed") from exc
        except (TypeError, ValueError) as exc:
            raise TokenValidationError("JWT claims are invalid") from exc

    def revoke_token(self, token: str) -> bool:
        """Verify and revoke a token for its complete remaining lifetime."""
        try:
            payload = self.verify_token(token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not isinstance(jti, str) or not isinstance(exp, (int, float)):
                return False
            remaining = int(exp - time.time()) + self._settings.clock_skew_tolerance_seconds
            if remaining <= 0:
                return True
            # Never cap this to the default revocation TTL. Doing so could make
            # a long-lived token valid again while its signed exp is still live.
            self._revocation_list.revoke(jti, token_ttl=remaining)
            logger.info(
                "token_revoked",
                extra={"jti_sha256": hashlib.sha256(jti.encode()).hexdigest()[:16]},
            )
            return True
        except TokenRevocationError:
            return True
        except Exception as exc:
            logger.error(
                "token_revocation_failed",
                extra={"error_class": type(exc).__name__},
            )
            return False

    def cleanup_expired_tokens(self) -> int:
        return self._revocation_list.cleanup_expired()

    def _jwk_to_pem(self, jwk: dict[str, Any]) -> Any:
        try:
            from jose.jwk import construct
        except ImportError as exc:
            raise ImportError(
                "OIDC requires python-jose; install the oidc dependency set"
            ) from exc
        return construct(jwk).public_key()

    def _validate_claims(self, payload: dict[str, Any]) -> None:
        project_id = payload.get(self._settings.require_project_claim)
        if not isinstance(project_id, str) or not project_id:
            raise TokenValidationError(
                f"Missing required claim: {self._settings.require_project_claim}"
            )
        role = payload.get(self._settings.require_role_claim)
        if not isinstance(role, str) or not role:
            raise TokenValidationError(
                f"Missing required claim: {self._settings.require_role_claim}"
            )

        subject = payload.get(self._settings.require_subject_claim)
        if not isinstance(subject, str) or not _SUBJECT.fullmatch(subject):
            raise TokenValidationError(
                f"Missing or invalid required claim: {self._settings.require_subject_claim}"
            )

        if self._settings.require_exp_claim:
            exp = payload.get("exp")
            if not isinstance(exp, (int, float)):
                raise TokenValidationError("Missing or invalid required claim: exp")
        if self._settings.require_iat_claim:
            iat = payload.get("iat")
            if not isinstance(iat, (int, float)):
                raise TokenValidationError("Missing or invalid required claim: iat")
            now = time.time()
            if iat > now + self._settings.clock_skew_tolerance_seconds:
                raise TokenValidationError("Token issued-at time is in the future")

        if self._settings.require_jti_claim:
            jti = payload.get("jti")
            if not isinstance(jti, str):
                raise TokenValidationError("Missing required claim: jti")
            TokenRevocationList._validate_jti(jti)

        if self._settings.require_mfa_claim:
            amr = payload.get(self._settings.require_mfa_claim, [])
            accepted = {"mfa", "otp", "push", "sms", "hardware", "totp", "webauthn"}
            if isinstance(amr, list):
                methods = {item for item in amr if isinstance(item, str)}
                if not methods.intersection(accepted):
                    raise TokenValidationError("MFA authentication is required")
            elif isinstance(amr, str):
                if amr not in accepted:
                    raise TokenValidationError("MFA authentication is required")
            else:
                raise TokenValidationError("MFA claim is invalid")


class RoleMapping(BaseModel):
    """Role mapping policy from IdP groups to platform roles."""

    id: str = Field(pattern=r"^role_mapping:\d+\.\d+\.\d+$")
    version: str = Field(pattern=r"^v\d+\.\d+\.\d+$")
    mappings: dict[str, list[str]]
    created_at: str
    created_by: str


class OIDCAuthenticator:
    """Application-lifetime authenticator for verified bearer identities."""

    ALLOWED_ROLES = frozenset({
        "viewer",
        "evaluation_engineer",
        "reviewer",
        "adjudicator",
        "project_admin",
        "release_authority",
        "signing_authority",
        "system_admin",
    })

    def __init__(
        self,
        settings: OIDCSettings,
        redis_client: Any | None = None,
        revocation_list: TokenRevocationList | None = None,
    ) -> None:
        self._jwks_client = JWKSClient(
            settings,
            redis_client=redis_client,
            revocation_list=revocation_list,
        )
        self._settings = settings
        self._role_mapping: RoleMapping | None = None

    def authenticate_context(self, token: str) -> tuple[str, str, str]:
        payload = self._jwks_client.verify_token(token)
        project_id = str(payload.get(self._settings.require_project_claim, ""))
        role = str(payload.get(self._settings.require_role_claim, ""))
        subject = str(payload.get(self._settings.require_subject_claim, ""))
        if role not in self.ALLOWED_ROLES:
            raise TokenValidationError("Invalid role in token")
        if not subject:
            raise TokenValidationError("Token subject is missing")
        return project_id, role, subject

    def authenticate(self, token: str) -> tuple[str, str]:
        project_id, role, _subject = self.authenticate_context(token)
        return project_id, role

    def get_token_subject(self, token: str) -> str | None:
        """Verify the token and return its subject.

        Retained for compatibility. New request composition should use
        ``authenticate_context`` so a token is verified once.
        """
        try:
            _project_id, _role, subject = self.authenticate_context(token)
            return subject
        except (TokenValidationError, TokenRevocationError, OIDCConfigurationError):
            return None

    def revoke_token(self, token: str) -> bool:
        return self._jwks_client.revoke_token(token)

    def load_role_mapping(self, mapping: RoleMapping) -> None:
        self._role_mapping = mapping
        logger.info(
            "role_mapping_loaded",
            extra={"mapping_id": mapping.id, "version": mapping.version},
        )

    def get_workload_identity(self, identity_type: str) -> dict[str, Any]:
        allowed_types = {
            "api",
            "scheduler",
            "provider_executor",
            "grader",
            "maintenance",
            "report_export",
            "signing",
        }
        if identity_type not in allowed_types:
            raise ValueError(f"Unknown workload identity type: {identity_type}")
        return {
            "identity_type": identity_type,
            "audience": f"we3-{identity_type}",
            "scopes": self._get_workload_scopes(identity_type),
        }

    def _get_workload_scopes(self, identity_type: str) -> list[str]:
        scopes_map = {
            "api": ["read:basic", "write:self"],
            "scheduler": ["write:jobs", "read:experiments"],
            "provider_executor": ["write:attempts", "read:experiments"],
            "grader": ["read:responses", "write:evidence"],
            "maintenance": ["write:jobs", "write:cleanup"],
            "report_export": ["read:metrics", "read:reports"],
            "signing": ["signing:sign", "read:dossiers"],
        }
        return scopes_map.get(identity_type, [])


def create_oidc_authenticator(
    issuer: str,
    jwks_uri: str,
    audience: str,
    redis_client: Any | None = None,
) -> OIDCAuthenticator:
    return OIDCAuthenticator(
        OIDCSettings(issuer=issuer, jwks_uri=jwks_uri, audience=audience),
        redis_client=redis_client,
    )


__all__ = [
    "OIDCConfigurationError",
    "TokenValidationError",
    "TokenRevocationError",
    "OIDCSettings",
    "KeyCacheEntry",
    "TokenRevocationList",
    "JWKSClient",
    "RoleMapping",
    "OIDCAuthenticator",
    "create_oidc_authenticator",
]
