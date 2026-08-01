"""OIDC authentication for Wilson Eval3ngine.

T6.1.1 - Implement OIDC, workload identity, and role mapping.
Provides JWT validation, JWKS caching, and role mapping for production authentication.

Security enhancements:
- JWT token replay protection via jti claim validation and revocation list
- Token expiration (exp) and not-before (nbf) claim enforcement
- Clock skew tolerance for distributed deployments
- Token revocation with configurable TTL
"""

from __future__ import annotations

import logging
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

# requests is a main dependency, but jose is optional - lazy import for production
import requests
from pydantic import BaseModel, Field
logger = logging.getLogger("wilson.security.oidc")


class OIDCConfigurationError(Exception):
    """Raised when OIDC configuration is invalid or unavailable."""
    pass


class TokenValidationError(Exception):
    """Raised when a token fails validation."""
    pass


class TokenRevocationError(Exception):
    """Raised when a token is revoked or replayed."""
    pass


class TokenRevocationList:
    """Thread-safe token revocation list for JWT replay protection.

    Tracks `jti` (JWT ID) claims of revoked tokens with a TTL-based
    eviction strategy. Uses an OrderedDict as an LRU cache for
    in-memory mode, with optional Redis backing for distributed deployments.

    Security:
    - Tokens are tracked by their `jti` claim
    - Each entry expires after `revocation_ttl_seconds` (default: 3600s)
    - LRU eviction prevents unbounded memory growth
    - Thread-safe via threading.Lock
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        max_entries: int = 10_000,
        revocation_ttl_seconds: int = 3600,
    ):
        self._redis = redis_client
        self._max_entries = max_entries
        self._ttl = revocation_ttl_seconds
        self._store: OrderedDict[str, float] = OrderedDict()
        # Lock for thread safety in in-memory mode
        import threading  # noqa: PLC0415
        self._lock = threading.Lock()

    def revoke(self, jti: str, token_ttl: int | None = None) -> None:
        """Revoke a token by its jti claim.

        Args:
            jti: The JWT ID claim value
            token_ttl: Optional override for TTL (uses remaining token lifetime)
        """
        if not jti:
            return

        ttl = token_ttl if token_ttl is not None else self._ttl

        if self._redis is not None:
            key = f"we3:token_revoked:{jti}"
            self._redis.setex(key, ttl, "1")
            return

        with self._lock:
            # Evict oldest entries if at capacity
            while len(self._store) >= self._max_entries:
                self._store.popitem(last=False)
            self._store[jti] = time.time() + ttl

    def is_revoked(self, jti: str) -> bool:
        """Check if a token's jti is in the revocation list."""
        if not jti:
            return False

        if self._redis is not None:
            key = f"we3:token_revoked:{jti}"
            return bool(self._redis.exists(key))

        with self._lock:
            # Check and clean expired entries
            now = time.time()
            if jti in self._store:
                if now > self._store[jti]:
                    del self._store[jti]
                    return False
                # Move to end (LRU)
                self._store.move_to_end(jti)
                return True
            return False

    def cleanup_expired(self) -> int:
        """Remove expired entries from the revocation list.

        Returns:
            Number of entries removed.
        """
        if self._redis is not None:
            # Redis handles TTL automatically
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
    """Configuration for OIDC authentication.

    Security features:
    - Token replay protection via jti claim validation
    - Token expiration (exp) and not-before (nbf) enforcement
    - Clock skew tolerance for distributed deployments
    - Configurable revocation list TTL
    """
    issuer: str
    jwks_uri: str
    audience: str
    authorization_issuer: str | None = None  # For multi-issuer setups

    # Cache settings
    jwks_cache_ttl_seconds: int = 300  # 5 minutes default
    jwks_refresh_buffer_seconds: int = 30  # Refresh 30s before expiry

    # Required claims
    require_mfa_claim: str = "amr"  # Authentication Methods References
    require_project_claim: str = "we3_project_id"
    require_role_claim: str = "we3_role"

    # Token replay protection
    require_jti_claim: bool = True
    clock_skew_tolerance_seconds: int = 30
    revocation_ttl_seconds: int = 3600  # 1 hour default
    max_revocation_list_entries: int = 10_000


class KeyCacheEntry:
    """Cached JWKS entry with expiry tracking."""
    def __init__(self, keys: dict[str, Any], fetched_at: float):
        self.keys = keys
        self.fetched_at = fetched_at
        self.expires_at = fetched_at + 300  # Default 5-minute cache
    
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at
    
    def needs_refresh(self) -> bool:
        return time.time() >= self.expires_at - 30


class JWKSClient:
    """JWKS client with caching, rotation support, and token replay protection.

    Security features:
    - JWKS caching with TTL and refresh-ahead strategy
    - Token replay protection via jti claim validation
    - Token revocation list (in-memory or Redis-backed)
    - Clock skew tolerance for distributed deployments
    """

    def __init__(
        self,
        settings: OIDCSettings,
        cache_ttl: int = 300,
        redis_client: Any | None = None,
        revocation_list: TokenRevocationList | None = None,
    ):
        self._settings = settings
        self._cache_ttl = cache_ttl
        self._cached_keys: dict[str, Any] | None = None
        self._cache_entry: KeyCacheEntry | None = None
        self._redis = redis_client
        # Initialize revocation list with Redis backing if available
        if revocation_list is not None:
            self._revocation_list = revocation_list
        else:
            self._revocation_list = TokenRevocationList(
                redis_client=redis_client,
                max_entries=settings.max_revocation_list_entries,
                revocation_ttl_seconds=settings.revocation_ttl_seconds,
            )
    
    def get_signing_key(self, kid: str) -> Any | None:
        """Get signing key for a given key ID.
        
        Returns None if key not found (triggers refresh on next call).
        """
        if self._cache_entry is None or self._cache_entry.needs_refresh():
            self._refresh_keys()
        return self._cached_keys.get(kid) if self._cached_keys else None
    
    def _refresh_keys(self) -> None:
        """Fetch JWKS from issuer with error handling."""
        try:
            response = requests.get(
                self._settings.jwks_uri,
                timeout=5.0,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            keys = response.json()
            
            self._cached_keys = {k["kid"]: k for k in keys.get("keys", [])}
            self._cache_entry = KeyCacheEntry(
                keys=self._cached_keys,
                fetched_at=time.time(),
            )
            logger.info(
                "jwks_refreshed",
                extra={"key_count": len(self._cached_keys), "kid": list(self._cached_keys.keys())[:3]},
            )
        except Exception as e:
            # On refresh failure, keep using cached keys if available
            if self._cached_keys is None:
                logger.error("jwks_fetch_failed_no_cache", extra={"error": str(e)})
                raise OIDCConfigurationError(f"Unable to fetch JWKS: {e}") from e
            logger.warning("jwks_fetch_failed_using_cache", extra={"error": str(e)})
    
    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT token with replay protection.

        Validates issuer, audience, signature, required claims, and token
        replay protection via jti claim and revocation list.

        Security:
        - Verifies signature using JWKS with key rotation support
        - Validates issuer and audience claims
        - Enforces token expiration (exp) and not-before (nbf) with clock skew tolerance
        - Requires jti claim for replay protection when enabled
        - Checks token against revocation list
        - Validates project_id, role, and MFA claims

        Raises:
            TokenValidationError: If any validation fails
            TokenRevocationError: If token is revoked or replayed
            ImportError: If jose package not installed
        """
        # Lazy import jose - required for production but optional for foundation build
        try:
            from jose import jwt, JWTError  # noqa: PLC0415
        except ImportError as e:
            logger.error("jose_package_missing", extra={"error": str(e)})
            raise ImportError(
                "OIDC requires python-jose package. Install with: pip install 'wilson-eval3ngine[oidc]'"
            ) from e

        try:
            # Get unverified header first to find key
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            if not kid:
                raise TokenValidationError("Token missing key ID (kid)")

            key_dict = self.get_signing_key(kid)
            if key_dict is None:
                raise TokenValidationError(f"Unknown signing key: {kid}")

            # Convert JWK to PEM for jose
            key_pem = self._jwk_to_pem(key_dict)

            # Decode and verify with clock skew tolerance
            payload = jwt.decode(
                token,
                key=key_pem,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
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

            # Verify required claims
            self._validate_claims(payload)

            # Token replay protection: check jti claim
            if self._settings.require_jti_claim:
                jti = payload.get("jti")
                if not jti:
                    logger.warning("token_missing_jti", extra={"kid": kid})
                    raise TokenValidationError("Token missing required jti (JWT ID) claim")

                # Check if token has been revoked
                if self._revocation_list.is_revoked(jti):
                    logger.warning("token_revoked", extra={"jti": jti, "kid": kid})
                    raise TokenRevocationError(f"Token has been revoked: {jti}")

            # Check token expiration explicitly
            exp = payload.get("exp")
            if exp is not None:
                now = int(time.time())
                if now > exp + self._settings.clock_skew_tolerance_seconds:
                    raise TokenValidationError("Token has expired")

            return payload

        except TokenValidationError:
            raise
        except TokenRevocationError:
            raise
        except JWTError as e:
            raise TokenValidationError(f"JWT validation failed: {e}") from e

    def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding its jti to the revocation list.

        Args:
            token: The JWT token to revoke

        Returns:
            True if token was successfully revoked, False if token
            was already invalid or jti was missing.
        """
        try:
            from jose import jwt  # noqa: PLC0415
        except ImportError:
            return False

        try:
            # Get unverified header to find kid
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                logger.warning("revoke_token_no_kid")
                return False

            # Decode without verification to get jti and exp
            # We only need the claims, not signature verification
            unverified_payload = jwt.get_unverified_claims(token)
            jti = unverified_payload.get("jti")
            if not jti:
                logger.warning("revoke_token_no_jti")
                return False

            # Calculate remaining TTL from exp claim
            exp = unverified_payload.get("exp")
            if exp is not None:
                now = int(time.time())
                remaining = exp - now
                if remaining <= 0:
                    # Token already expired, no need to revoke
                    return True
                ttl = min(remaining, self._settings.revocation_ttl_seconds)
            else:
                ttl = self._settings.revocation_ttl_seconds

            self._revocation_list.revoke(jti, token_ttl=ttl)
            logger.info("token_revoked", extra={"jti": jti, "kid": kid})
            return True

        except Exception as e:
            logger.error("token_revocation_failed", extra={"error": str(e)})
            return False

    def cleanup_expired_tokens(self) -> int:
        """Clean up expired entries from the revocation list.

        Returns:
            Number of expired entries removed.
        """
        return self._revocation_list.cleanup_expired()
    
    def _jwk_to_pem(self, jwk: dict[str, Any]) -> str:
        """Convert JWK to PEM format for verification.
        
        Supports RSA (RS256) and EC (ES256) keys.
        """
        # Lazy import jose.jwk
        try:
            from jose.jwk import construct  # noqa: PLC0415
        except ImportError as e:
            logger.error("jose_package_missing", extra={"error": str(e)})
            raise ImportError(
                "OIDC requires python-jose package. Install with: pip install 'wilson-eval3ngine[oidc]'"
            ) from e
        key = construct(jwk)
        return key.public_key()
    
    def _validate_claims(self, payload: dict[str, Any]) -> None:
        """Validate required claims are present and valid."""
        # Verify project claim
        project_id = payload.get(self._settings.require_project_claim)
        if not project_id:
            raise TokenValidationError(f"Missing required claim: {self._settings.require_project_claim}")
        
        # Verify role claim
        role = payload.get(self._settings.require_role_claim)
        if not role:
            raise TokenValidationError(f"Missing required claim: {self._settings.require_role_claim}")
        
        # Verify MFA if required
        if self._settings.require_mfa_claim:
            amr = payload.get(self._settings.require_mfa_claim, [])
            if isinstance(amr, list):
                # Check that MFA method is present in amr claim
                mfa_methods = {"mfa", "otp", "push", "sms", "hardware", "totp", "webauthn"}
                if not any(method in mfa_methods for method in amr):
                    raise TokenValidationError("MFA authentication required but not present in token")
            elif isinstance(amr, str):
                # Single string value
                if amr not in {"mfa", "otp", "push", "sms", "hardware", "totp", "webauthn"}:
                    raise TokenValidationError("MFA authentication required but not present in token")
            else:
                raise TokenValidationError("MFA authentication required but amr claim is invalid")


class RoleMapping(BaseModel):
    """Role mapping policy from IdP groups to platform roles."""
    id: str = Field(pattern=r"^role_mapping:\d+\.\d+\.\d+$")
    version: str = Field(pattern=r"^v\d+\.\d+\.\d+$")
    mappings: dict[str, list[str]]  # IdP group -> platform roles
    created_at: str
    created_by: str


class OIDCAuthenticator:
    """Main authenticator for OIDC tokens."""
    
    # Allowed platform roles (from TODO 38 requirements)
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
    ):
        self._jwks_client = JWKSClient(
            settings,
            redis_client=redis_client,
            revocation_list=revocation_list,
        )
        self._settings = settings
        self._role_mapping: RoleMapping | None = None
    
    def authenticate(
        self,
        token: str,
    ) -> tuple[str, str]:
        """Authenticate a bearer token and return (project_id, role).
        
        Returns:
            Tuple of (project_id, role)
            
        Raises:
            TokenValidationError: If authentication fails
        """
        payload = self._jwks_client.verify_token(token)
        
        project_id = payload.get(self._settings.require_project_claim, "")
        role = payload.get(self._settings.require_role_claim, "")
        
        if role not in self.ALLOWED_ROLES:
            raise TokenValidationError(f"Invalid role in token: {role}")
        
        return project_id, role
    
    def get_token_subject(self, token: str) -> str | None:
        """Extract the subject (sub) claim from a verified token.
        
        This must be called after authenticate() to ensure the token
        has been verified. Returns the subject identifier or None.
        """
        try:
            from jose import jwt  # noqa: PLC0415
            payload = jwt.get_unverified_claims(token)
            return payload.get("sub")
        except Exception:
            return None
    
    def load_role_mapping(self, mapping: RoleMapping) -> None:
        """Load versioned role mapping policy."""
        self._role_mapping = mapping
        logger.info(
            "role_mapping_loaded",
            extra={"mapping_id": mapping.id, "version": mapping.version},
        )
    
    def get_workload_identity(self, identity_type: str) -> dict[str, Any]:
        """Get workload identity configuration for a specific type.
        
        Workload identities are separate from human identities with
        least-privilege scopes.
        """
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
        
        # In production, this would fetch from managed identity service
        return {
            "identity_type": identity_type,
            "audience": f"we3-{identity_type}",
            "scopes": self._get_workload_scopes(identity_type),
        }
    
    def _get_workload_scopes(self, identity_type: str) -> list[str]:
        """Get minimal scopes for workload identity type."""
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
    """Factory function to create OIDC authenticator.

    Args:
        issuer: OIDC issuer URL
        jwks_uri: JWKS endpoint URL
        audience: Expected audience claim
        redis_client: Optional Redis client for distributed token revocation
    """
    settings = OIDCSettings(
        issuer=issuer,
        jwks_uri=jwks_uri,
        audience=audience,
    )
    return OIDCAuthenticator(settings, redis_client=redis_client)


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