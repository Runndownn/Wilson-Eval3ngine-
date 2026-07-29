"""OIDC authentication for Wilson Eval3ngine.

T6.1.1 - Implement OIDC, workload identity, and role mapping.
Provides JWT validation, JWKS caching, and role mapping for production authentication.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    """Configuration for OIDC authentication."""
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
    """JWKS client with caching and rotation support."""
    
    def __init__(self, settings: OIDCSettings, cache_ttl: int = 300):
        self._settings = settings
        self._cache_ttl = cache_ttl
        self._cached_keys: dict[str, Any] | None = None
        self._cache_entry: KeyCacheEntry | None = None
    
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
        """Verify and decode a JWT token.
        
        Validates issuer, audience, signature, and required claims.
        
        Raises:
            TokenValidationError: If any validation fails
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
            
            # Decode and verify
            payload = jwt.decode(
                token,
                key=key_pem,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
            )
            
            # Verify required claims
            self._validate_claims(payload)
            
            return payload
            
        except JWTError as e:
            raise TokenValidationError(f"JWT validation failed: {e}") from e
    
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
    
    def __init__(self, settings: OIDCSettings):
        self._jwks_client = JWKSClient(settings)
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
) -> OIDCAuthenticator:
    """Factory function to create OIDC authenticator."""
    settings = OIDCSettings(
        issuer=issuer,
        jwks_uri=jwks_uri,
        audience=audience,
    )
    return OIDCAuthenticator(settings)


__all__ = [
    "OIDCConfigurationError",
    "TokenValidationError",
    "OIDCSettings",
    "KeyCacheEntry",
    "JWKSClient",
    "RoleMapping",
    "OIDCAuthenticator",
    "create_oidc_authenticator",
]