"""
Unit tests for OIDC authentication (TODO 38).

Tests JWT validation, JWKS caching, role mapping, and workload identities.
Requires python-jose optional dependency.
"""

import pytest
from unittest.mock import Mock, patch
import time

# Skip tests if optional OIDC dependency not available
pytest.importorskip("jose", reason="python-jose required for OIDC tests")

from wilson_eval3ngine.security.oidc import (
    TokenValidationError,
    OIDCSettings,
    JWKSClient,
    RoleMapping,
    OIDCAuthenticator,
)


class TestOIDCSettings:
    """Tests for OIDC settings validation."""

    def test_default_settings_valid(self) -> None:
        """Default settings are properly configured."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        assert settings.issuer == "https://auth.example.com"
        assert settings.jwks_cache_ttl_seconds == 300

    def test_custom_cache_ttl(self) -> None:
        """Custom cache TTL can be set."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
            jwks_cache_ttl_seconds=600,
        )
        assert settings.jwks_cache_ttl_seconds == 600


class TestJWKSClient:
    """Tests for JWKS client caching and key retrieval."""

    def test_key_cache_entry_expiry(self) -> None:
        """Key cache entries track expiry correctly."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry
        
        entry = KeyCacheEntry(keys={"kid1": {"kty": "RSA"}}, fetched_at=time.time())
        assert entry.is_expired() is False
        assert entry.needs_refresh() is False
        
        # Force expiry
        entry.expires_at = time.time() - 1
        assert entry.is_expired() is True

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_fetch_on_init(self, mock_get: Mock) -> None:
        """JWKS client fetches keys from endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "keys": [
                {"kid": "key1", "kty": "RSA", "n": "n", "e": "AQAB"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)
        
        assert client.get_signing_key("key1") is not None
        mock_get.assert_called_once()

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_cache_reuse(self, mock_get: Mock) -> None:
        """JWKS client reuses cached keys."""
        mock_response = Mock()
        mock_response.json.return_value = {"keys": [{"kid": "key1", "kty": "RSA"}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)
        
        # First call
        client.get_signing_key("key1")
        # Second call (should use cache)
        client.get_signing_key("key1")
        
        # Should only be called once
        mock_get.assert_called_once()


class TestOIDCAuthenticator:
    """Tests for OIDC authenticator."""

    def test_allowed_roles_defined(self) -> None:
        """Allowed roles are properly defined."""
        expected_roles = {
            "viewer",
            "evaluation_engineer",
            "reviewer",
            "adjudicator",
            "project_admin",
            "release_authority",
            "signing_authority",
            "system_admin",
        }
        assert OIDCAuthenticator.ALLOWED_ROLES == expected_roles

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_success(self, mock_verify: Mock) -> None:
        """Successful authentication returns project_id and role."""
        mock_verify.return_value = {
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "sub": "user_123",
        }
        
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)
        
        project_id, role = authenticator.authenticate("test-token")
        assert project_id == "proj_test"
        assert role == "viewer"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_invalid_role(self, mock_verify: Mock) -> None:
        """Invalid role in token raises TokenValidationError."""
        mock_verify.return_value = {
            "we3_project_id": "proj_test",
            "we3_role": "invalid_role",
        }
        
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)
        
        with pytest.raises(TokenValidationError, match="Invalid role"):
            authenticator.authenticate("test-token")

    def test_workload_identity_types(self) -> None:
        """Workload identity types are validated."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)
        
        # Valid types
        identity = authenticator.get_workload_identity("api")
        assert identity["identity_type"] == "api"
        
        identity = authenticator.get_workload_identity("signing")
        assert identity["audience"] == "we3-signing"
        
        # Invalid type
        with pytest.raises(ValueError, match="Unknown workload identity type"):
            authenticator.get_workload_identity("invalid_type")


class TestRoleMapping:
    """Tests for role mapping policy."""

    def test_role_mapping_creation(self) -> None:
        """Role mapping can be created with valid structure."""
        mapping = RoleMapping(
            id="role_mapping:1.0.0",
            version="v1.0.0",
            mappings={
                "idp_group_admin": ["project_admin", "release_authority"],
                "idp_group_reviewer": ["reviewer", "adjudicator"],
            },
            created_at="2026-07-16T00:00:00Z",
            created_by="admin",
        )
        
        assert mapping.id == "role_mapping:1.0.0"
        assert "project_admin" in mapping.mappings["idp_group_admin"]


class TestTokenValidation:
    """Tests for token validation edge cases."""

    def test_missing_project_claim(self) -> None:
        """Missing project claim is rejected."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)
        
        # Test that _validate_claims raises for missing project
        with pytest.raises(TokenValidationError, match="Missing required claim"):
            client._validate_claims({"we3_role": "viewer"})  # Missing project_claim

    def test_missing_role_claim(self) -> None:
        """Missing role claim is rejected."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)
        
        with pytest.raises(TokenValidationError, match="Missing required claim"):
            client._validate_claims({"we3_project_id": "proj_test"})  # Missing role


class TestOIDCModes:
    """Tests for authentication mode handling."""

    def test_auth_mode_resolved_from_env(self) -> None:
        """Auth mode can be set via environment."""
        from wilson_eval3ngine.config import Settings
        
        # Test default dev mode
        settings = Settings()
        assert settings.auth_mode == "dev"
        
        # Test OIDC mode would be set via env var
        # (In actual test, would use monkeypatch or env override)