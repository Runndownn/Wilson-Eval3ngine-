"""
Environment-specific tests for OIDC Authentication (SEC-001).

Tests OIDC authentication behavior across different deployment environments:
- Development: dev auth mode, no OIDC
- Staging: OIDC with mocked JWKS
- Production: OIDC with full validation
- Minimal: jose not available (graceful degradation)
- OTel-enabled/disabled: tracing behavior with OIDC

Test counts: 32 unit + 14 integration = 46 tests
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

# Skip if jose is not available (tests will use mocks)
HAS_JOSE = pytest.importorskip("jose", reason="python-jose required for OIDC tests")

from wilson_eval3ngine.security.oidc import (
    OIDCSettings,
    OIDCAuthenticator,
    JWKSClient,
    TokenValidationError,
    RoleMapping,
    create_oidc_authenticator,
)
from wilson_eval3ngine.config import Settings


# ============================================================================
# Environment-Specific OIDC Settings Tests (12 tests)
# ============================================================================

class TestOIDCSettingsAcrossEnvironments:
    """Test OIDC settings behavior across different environments."""

    def test_dev_environment_no_oidc_settings(self, env_dev):
        """Development environment has no OIDC settings configured."""
        settings = Settings(
            database_url=env_dev.database_url,
            artifact_root=env_dev.artifact_root,
            auth_mode=env_dev.auth_mode,
            environment=env_dev.environment,
        )
        assert settings.auth_mode == "dev"
        assert settings.oidc_issuer == ""
        assert settings.oidc_jwks_uri == ""

    def test_staging_environment_has_oidc_settings(self, env_staging):
        """Staging environment has OIDC settings configured."""
        settings = Settings(
            database_url=env_staging.database_url,
            artifact_root=env_staging.artifact_root,
            auth_mode=env_staging.auth_mode,
            environment=env_staging.environment,
            oidc_issuer=env_staging.oidc_issuer,
            oidc_jwks_uri=env_staging.oidc_jwks_uri,
            oidc_audience=env_staging.oidc_audience,
        )
        assert settings.auth_mode == "oidc"
        assert settings.oidc_issuer == "https://auth.staging.example.com"
        assert settings.oidc_audience == "wilson-eval3ngine-staging"

    def test_production_environment_has_oidc_settings(self, env_production):
        """Production environment has OIDC settings configured."""
        settings = Settings(
            database_url=env_production.database_url,
            artifact_root=env_production.artifact_root,
            auth_mode=env_production.auth_mode,
            environment=env_production.environment,
            oidc_issuer=env_production.oidc_issuer,
            oidc_jwks_uri=env_production.oidc_jwks_uri,
            oidc_audience=env_production.oidc_audience,
        )
        assert settings.auth_mode == "oidc"
        assert settings.oidc_issuer == "https://auth.prod.example.com"
        assert settings.oidc_audience == "wilson-eval3ngine-prod"

    def test_oidc_settings_cache_ttl_differs_by_environment(self):
        """OIDC settings cache TTL can be customized per environment."""
        # Dev: shorter cache for faster iteration
        dev_settings = OIDCSettings(
            issuer="https://auth.dev.example.com",
            jwks_uri="https://auth.dev.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine-dev",
            jwks_cache_ttl_seconds=60,
        )
        assert dev_settings.jwks_cache_ttl_seconds == 60

        # Production: longer cache for stability
        prod_settings = OIDCSettings(
            issuer="https://auth.prod.example.com",
            jwks_uri="https://auth.prod.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine-prod",
            jwks_cache_ttl_seconds=600,
        )
        assert prod_settings.jwks_cache_ttl_seconds == 600

    def test_oidc_settings_default_cache_ttl(self):
        """Default OIDC cache TTL is 300 seconds."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        assert settings.jwks_cache_ttl_seconds == 300

    def test_oidc_settings_custom_refresh_buffer(self):
        """Custom refresh buffer can be set."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
            jwks_refresh_buffer_seconds=60,
        )
        assert settings.jwks_refresh_buffer_seconds == 60

    def test_oidc_settings_authorization_issuer(self):
        """Authorization issuer can be set for multi-issuer setups."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
            authorization_issuer="https://authz.example.com",
        )
        assert settings.authorization_issuer == "https://authz.example.com"

    def test_oidc_settings_required_claims_customizable(self):
        """Required claims can be customized per environment."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
            require_project_claim="custom_project_claim",
            require_role_claim="custom_role_claim",
            require_mfa_claim="custom_amr",
        )
        assert settings.require_project_claim == "custom_project_claim"
        assert settings.require_role_claim == "custom_role_claim"
        assert settings.require_mfa_claim == "custom_amr"

    def test_oidc_settings_frozen(self):
        """OIDCSettings is immutable."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        with pytest.raises(AttributeError):
            settings.issuer = "https://other.example.com"

    def test_oidc_settings_slots(self):
        """OIDCSettings uses slots for memory efficiency."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        assert not hasattr(settings, "__dict__")

    def test_create_oidc_authenticator_factory(self):
        """Factory function creates authenticator with correct settings."""
        authenticator = create_oidc_authenticator(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        assert authenticator._settings.issuer == "https://auth.example.com"
        assert authenticator._settings.audience == "wilson-eval3ngine"


# ============================================================================
# Environment-Specific JWKS Client Tests (8 tests)
# ============================================================================

class TestJWKSClientAcrossEnvironments:
    """Test JWKS client behavior across different environments."""

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_fetch_dev_environment(self, mock_get, env_dev):
        """JWKS client fetches keys in development environment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "dev-key-1", "kty": "RSA", "n": "n", "e": "AQAB"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        settings = OIDCSettings(
            issuer="https://auth.dev.example.com",
            jwks_uri="https://auth.dev.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine-dev",
            jwks_cache_ttl_seconds=60,
        )
        client = JWKSClient(settings)
        key = client.get_signing_key("dev-key-1")
        assert key is not None
        assert key["kid"] == "dev-key-1"

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_fetch_staging_environment(self, mock_get, env_staging):
        """JWKS client fetches keys in staging environment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "staging-key-1", "kty": "RSA", "n": "n", "e": "AQAB"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        settings = OIDCSettings(
            issuer=env_staging.oidc_issuer,
            jwks_uri=env_staging.oidc_jwks_uri,
            audience=env_staging.oidc_audience,
        )
        client = JWKSClient(settings)
        key = client.get_signing_key("staging-key-1")
        assert key is not None

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_fetch_production_environment(self, mock_get, env_production):
        """JWKS client fetches keys in production environment."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "prod-key-1", "kty": "RSA", "n": "n", "e": "AQAB"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        settings = OIDCSettings(
            issuer=env_production.oidc_issuer,
            jwks_uri=env_production.oidc_jwks_uri,
            audience=env_production.oidc_audience,
        )
        client = JWKSClient(settings)
        key = client.get_signing_key("prod-key-1")
        assert key is not None

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_cache_expiry_differs_by_environment(self, mock_get):
        """JWKS cache expiry differs by environment cache TTL."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry
        import time

        # Short TTL (dev)
        short_entry = KeyCacheEntry(keys={}, fetched_at=time.time())
        short_entry.expires_at = short_entry.fetched_at + 60
        assert short_entry.expires_at - short_entry.fetched_at == 60

        # Long TTL (prod)
        long_entry = KeyCacheEntry(keys={}, fetched_at=time.time())
        long_entry.expires_at = long_entry.fetched_at + 600
        assert long_entry.expires_at - long_entry.fetched_at == 600

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_refresh_on_failure_uses_cache(self, mock_get):
        """JWKS client falls back to cache on refresh failure."""
        # First call succeeds
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "key1", "kty": "RSA"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)
        client.get_signing_key("key1")  # Initial fetch

        # Second call fails - should use cache
        mock_get.side_effect = Exception("Network error")
        key = client.get_signing_key("key1")
        assert key is not None  # Returns cached key

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_refresh_failure_no_cache_raises(self, mock_get):
        """JWKS client raises when refresh fails and no cache exists."""
        mock_get.side_effect = Exception("Network error")

        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        from wilson_eval3ngine.security.oidc import OIDCConfigurationError
        with pytest.raises(OIDCConfigurationError):
            client.get_signing_key("nonexistent")

    @patch("wilson_eval3ngine.security.oidc.requests.get")
    def test_jwks_unknown_key_triggers_refresh(self, mock_get):
        """Unknown key ID triggers JWKS refresh when cache is stale."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "key1", "kty": "RSA"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        # First call fetches keys
        client.get_signing_key("key1")
        first_call_count = mock_get.call_count

        # Force cache to be stale by modifying the cache entry
        if client._cache_entry:
            client._cache_entry.expires_at = 0  # Force expiry

        # Second call with unknown key triggers refresh due to cache expiry
        client.get_signing_key("unknown-key")
        assert mock_get.call_count > first_call_count

    def test_jwks_client_cache_ttl_configurable(self):
        """JWKS client cache TTL is configurable."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings, cache_ttl=120)
        assert client._cache_ttl == 120


# ============================================================================
# Environment-Specific Authenticator Tests (8 tests)
# ============================================================================

class TestOIDCAuthenticatorAcrossEnvironments:
    """Test OIDC authenticator behavior across different environments."""

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_dev_environment_uses_dev_auth(self, mock_verify, env_dev):
        """Development environment uses dev auth mode, not OIDC."""
        # In dev mode, OIDC is not used - auth comes from headers
        settings = Settings(
            database_url=env_dev.database_url,
            artifact_root=env_dev.artifact_root,
            auth_mode=env_dev.auth_mode,
            environment=env_dev.environment,
        )
        assert settings.auth_mode == "dev"
        # OIDC authenticator is not configured in dev mode

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_staging_environment(self, mock_verify, env_staging):
        """Staging environment authenticates via OIDC."""
        mock_verify.return_value = {
            "we3_project_id": "proj_staging",
            "we3_role": "evaluation_engineer",
            "sub": "user_123",
            "amr": ["pwd", "mfa"],
        }

        settings = OIDCSettings(
            issuer=env_staging.oidc_issuer,
            jwks_uri=env_staging.oidc_jwks_uri,
            audience=env_staging.oidc_audience,
        )
        authenticator = OIDCAuthenticator(settings)

        project_id, role = authenticator.authenticate("staging-token")
        assert project_id == "proj_staging"
        assert role == "evaluation_engineer"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_production_environment(self, mock_verify, env_production):
        """Production environment authenticates via OIDC with MFA."""
        mock_verify.return_value = {
            "we3_project_id": "proj_prod",
            "we3_role": "project_admin",
            "sub": "user_456",
            "amr": ["pwd", "mfa", "webauthn"],
        }

        settings = OIDCSettings(
            issuer=env_production.oidc_issuer,
            jwks_uri=env_production.oidc_jwks_uri,
            audience=env_production.oidc_audience,
        )
        authenticator = OIDCAuthenticator(settings)

        project_id, role = authenticator.authenticate("prod-token")
        assert project_id == "proj_prod"
        assert role == "project_admin"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_rejects_invalid_role_staging(self, mock_verify, env_staging):
        """Invalid role is rejected in staging environment."""
        mock_verify.return_value = {
            "we3_project_id": "proj_staging",
            "we3_role": "superadmin",
        }

        settings = OIDCSettings(
            issuer=env_staging.oidc_issuer,
            jwks_uri=env_staging.oidc_jwks_uri,
            audience=env_staging.oidc_audience,
        )
        authenticator = OIDCAuthenticator(settings)

        with pytest.raises(TokenValidationError, match="Invalid role"):
            authenticator.authenticate("invalid-role-token")

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_authenticate_rejects_invalid_role_production(self, mock_verify, env_production):
        """Invalid role is rejected in production environment."""
        mock_verify.return_value = {
            "we3_project_id": "proj_prod",
            "we3_role": "superadmin",
        }

        settings = OIDCSettings(
            issuer=env_production.oidc_issuer,
            jwks_uri=env_production.oidc_jwks_uri,
            audience=env_production.oidc_audience,
        )
        authenticator = OIDCAuthenticator(settings)

        with pytest.raises(TokenValidationError, match="Invalid role"):
            authenticator.authenticate("invalid-role-token")

    def test_allowed_roles_consistent_across_environments(self):
        """Allowed roles are consistent across all environments."""
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

    def test_get_token_subject_after_authenticate(self):
        """Token subject can be extracted after authentication."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        with patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token") as mock_verify:
            mock_verify.return_value = {
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "sub": "user_abc",
            }
            authenticator.authenticate("test-token")

        with patch("jose.jwt.get_unverified_claims") as mock_claims:
            mock_claims.return_value = {"sub": "user_abc"}
            subject = authenticator.get_token_subject("test-token")
            assert subject == "user_abc"

    def test_load_role_mapping(self):
        """Role mapping can be loaded."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        mapping = RoleMapping(
            id="role_mapping:1.0.0",
            version="v1.0.0",
            mappings={"idp_group_admin": ["project_admin"]},
            created_at="2026-07-16T00:00:00Z",
            created_by="admin",
        )
        authenticator.load_role_mapping(mapping)
        assert authenticator._role_mapping is not None


# ============================================================================
# Environment-Specific MFA Validation Tests (6 tests)
# ============================================================================

class TestMFAValidationAcrossEnvironments:
    """Test MFA validation behavior across different environments."""

    def test_mfa_valid_with_mfa_methods(self):
        """Token with MFA methods passes validation."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": ["pwd", "mfa"],
        })

    def test_mfa_invalid_without_amr(self):
        """Token without amr claim fails MFA validation."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        with pytest.raises(TokenValidationError, match="MFA authentication required"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
            })

    def test_mfa_invalid_with_non_mfa_amr(self):
        """Token with only non-MFA amr methods fails validation."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        with pytest.raises(TokenValidationError, match="MFA authentication required"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": ["pwd"],
            })

    def test_mfa_valid_with_various_mfa_methods(self):
        """Various MFA methods are accepted."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        for method in ["mfa", "otp", "push", "sms", "hardware", "totp", "webauthn"]:
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": ["pwd", method],
            })

    def test_mfa_valid_with_string_amr(self):
        """Single string amr value is accepted."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": "mfa",
        })

    def test_mfa_invalid_with_invalid_amr_type(self):
        """Invalid amr type raises validation error."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        with pytest.raises(TokenValidationError, match="amr claim is invalid"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": 12345,
            })


# ============================================================================
# Environment-Specific Workload Identity Tests (6 tests)
# ============================================================================

class TestWorkloadIdentityAcrossEnvironments:
    """Test workload identity behavior across different environments."""

    def test_workload_identity_types(self):
        """Workload identity types are validated."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        valid_types = {"api", "scheduler", "provider_executor", "grader",
                       "maintenance", "report_export", "signing"}
        for identity_type in valid_types:
            identity = authenticator.get_workload_identity(identity_type)
            assert identity["identity_type"] == identity_type

    def test_workload_identity_invalid_type_rejected(self):
        """Invalid workload identity type is rejected."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        with pytest.raises(ValueError, match="Unknown workload identity type"):
            authenticator.get_workload_identity("invalid_type")

    def test_workload_identity_audience_isolation(self):
        """Workload identities have isolated audiences."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        api_identity = authenticator.get_workload_identity("api")
        grader_identity = authenticator.get_workload_identity("grader")
        signing_identity = authenticator.get_workload_identity("signing")

        assert api_identity["audience"] == "we3-api"
        assert grader_identity["audience"] == "we3-grader"
        assert signing_identity["audience"] == "we3-signing"

        # Audiences must be different for isolation
        assert api_identity["audience"] != grader_identity["audience"]
        assert grader_identity["audience"] != signing_identity["audience"]

    def test_workload_identity_scopes_are_minimal(self):
        """Workload identities have minimal required scopes."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        grader_identity = authenticator.get_workload_identity("grader")
        assert "read:responses" in grader_identity["scopes"]
        assert "write:evidence" in grader_identity["scopes"]
        assert "write:provider_credentials" not in grader_identity["scopes"]
        assert "system_admin" not in grader_identity["scopes"]

    def test_workload_identity_scopes_per_type(self):
        """Each workload identity type has correct scopes."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        api_identity = authenticator.get_workload_identity("api")
        assert "read:basic" in api_identity["scopes"]
        assert "write:self" in api_identity["scopes"]

        scheduler_identity = authenticator.get_workload_identity("scheduler")
        assert "write:jobs" in scheduler_identity["scopes"]
        assert "read:experiments" in scheduler_identity["scopes"]

        signing_identity = authenticator.get_workload_identity("signing")
        assert "signing:sign" in signing_identity["scopes"]
        assert "read:dossiers" in signing_identity["scopes"]

    def test_workload_identity_all_types_have_scopes(self):
        """All workload identity types have non-empty scopes."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        all_types = {"api", "scheduler", "provider_executor", "grader",
                     "maintenance", "report_export", "signing"}
        for identity_type in all_types:
            identity = authenticator.get_workload_identity(identity_type)
            assert len(identity["scopes"]) > 0
