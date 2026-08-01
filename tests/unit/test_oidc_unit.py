"""Unit tests for OIDC module - covers all code paths.

Tests cover:
- JWKS refresh failure with and without cache
- Token verification (JWT decode, claims validation)
- JWK to PEM conversion
- MFA claim validation (list, string, invalid)
- get_token_subject error handling
- create_oidc_authenticator factory
- Workload identity configuration
- Role mapping
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, mock_open
import sys

import pytest

from wilson_eval3ngine.security.oidc import (
    OIDCConfigurationError,
    TokenValidationError,
    OIDCSettings,
    JWKSClient,
    RoleMapping,
    OIDCAuthenticator,
    create_oidc_authenticator,
)


class TestJWKSClientRefreshFailure:
    """Tests for JWKS client refresh failure handling."""

    def test_refresh_failure_no_cache_raises(self) -> None:
        """JWKS refresh failure with no cache raises OIDCConfigurationError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        with patch("wilson_eval3ngine.security.oidc.requests.get") as mock_get:
            mock_get.side_effect = ConnectionError("Network error")
            with pytest.raises(OIDCConfigurationError, match="Unable to fetch JWKS"):
                client._refresh_keys()

    def test_refresh_failure_with_cache_warns(self) -> None:
        """JWKS refresh failure with cache keeps using cached keys."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        with patch("wilson_eval3ngine.security.oidc.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"keys": [{"kid": "test-key", "kty": "RSA"}]}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            client._refresh_keys()

        with patch("wilson_eval3ngine.security.oidc.requests.get") as mock_get:
            mock_get.side_effect = ConnectionError("Network error")
            client._refresh_keys()

        assert client._cached_keys is not None
        assert "test-key" in client._cached_keys

    def test_get_signing_key_triggers_refresh(self) -> None:
        """get_signing_key triggers refresh when cache is stale."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings, cache_ttl=0)

        with patch("wilson_eval3ngine.security.oidc.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"keys": [{"kid": "key1", "kty": "RSA"}]}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.get_signing_key("key1")
            assert result is not None
            assert result["kid"] == "key1"

    def test_get_signing_key_returns_none_for_unknown(self) -> None:
        """get_signing_key returns None for unknown key ID."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        with patch("wilson_eval3ngine.security.oidc.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"keys": [{"kid": "key1", "kty": "RSA"}]}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.get_signing_key("unknown-key")
            assert result is None


class TestTokenVerification:
    """Tests for JWT token verification."""

    def _make_mock_jose(self, header=None, decode_result=None, decode_error=None):
        """Create a mock jose module."""
        mock_jwt = MagicMock()
        mock_jwt.get_unverified_header.return_value = header or {}
        if decode_error:
            from jose import JWTError
            mock_jwt.decode.side_effect = decode_error
        else:
            mock_jwt.decode.return_value = decode_result or {}
        mock_jwt.get_unverified_claims.return_value = {"sub": "user_123"}
        return mock_jwt

    def test_verify_token_missing_kid(self) -> None:
        """Token without kid raises TokenValidationError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        mock_jwt = self._make_mock_jose(header={})

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt, JWTError=Exception)}):
            with pytest.raises(TokenValidationError, match="Token missing key ID"):
                client.verify_token("fake.token.here")

    def test_verify_token_unknown_key(self) -> None:
        """Token with unknown key ID raises TokenValidationError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)
        client._cached_keys = {}

        mock_jwt = self._make_mock_jose(header={"kid": "unknown"})

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt, JWTError=Exception)}):
            with pytest.raises(TokenValidationError, match="Unknown signing key"):
                client.verify_token("fake.token.here")

    def test_verify_token_jwt_error(self) -> None:
        """JWT decode error raises TokenValidationError."""
        from jose import JWTError

        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)
        client._cached_keys = {"test-key": {"kid": "test-key", "kty": "RSA"}}

        mock_jwt = self._make_mock_jose(
            header={"kid": "test-key"},
            decode_error=JWTError("Invalid token")
        )

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt, JWTError=JWTError)}):
            with patch.object(client, "_jwk_to_pem", return_value="fake-pem"):
                with pytest.raises(TokenValidationError, match="JWT validation failed"):
                    client.verify_token("fake.token.here")

    def test_jwk_to_pem_import_error(self) -> None:
        """JWK to PEM conversion raises ImportError when jose is missing."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        # Simulate jose not being available
        with patch.dict(sys.modules, {"jose": None, "jose.jwk": None}):
            with pytest.raises(ImportError, match="OIDC requires python-jose"):
                client._jwk_to_pem({"kid": "test", "kty": "RSA"})

    def test_jwk_to_pem_success(self) -> None:
        """JWK to PEM conversion succeeds with valid jose."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        mock_jwk_module = MagicMock()
        mock_key = MagicMock()
        mock_key.public_key.return_value = "fake-pem-string"
        mock_jwk_module.construct.return_value = mock_key

        with patch.dict(sys.modules, {"jose.jwk": mock_jwk_module}):
            result = client._jwk_to_pem({"kid": "test", "kty": "RSA"})
            assert result == "fake-pem-string"

    def test_verify_token_jose_missing(self) -> None:
        """Missing jose package raises ImportError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)

        with patch.dict(sys.modules, {"jose": None}):
            with pytest.raises(ImportError, match="OIDC requires python-jose"):
                client.verify_token("fake.token.here")

    def test_verify_token_success(self) -> None:
        """Successful token verification returns payload."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        client = JWKSClient(settings)
        client._cached_keys = {"test-key": {"kid": "test-key", "kty": "RSA"}}

        mock_payload = {
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": ["mfa"],
            "jti": "test-jti-12345",
        }

        mock_jwt = self._make_mock_jose(
            header={"kid": "test-key"},
            decode_result=mock_payload
        )

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt, JWTError=Exception)}):
            with patch.object(client, "_jwk_to_pem", return_value="fake-pem"):
                result = client.verify_token("fake.token.here")
                assert result == mock_payload


class TestClaimValidation:
    """Tests for JWT claim validation."""

    def _get_client(self) -> JWKSClient:
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        return JWKSClient(settings)

    def test_validate_claims_missing_project(self) -> None:
        """Missing project claim raises TokenValidationError."""
        client = self._get_client()
        with pytest.raises(TokenValidationError, match="Missing required claim"):
            client._validate_claims({"we3_role": "viewer"})

    def test_validate_claims_missing_role(self) -> None:
        """Missing role claim raises TokenValidationError."""
        client = self._get_client()
        with pytest.raises(TokenValidationError, match="Missing required claim"):
            client._validate_claims({"we3_project_id": "proj_test"})

    def test_validate_claims_mfa_list_valid(self) -> None:
        """MFA claim as list with valid method passes."""
        client = self._get_client()
        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": ["pwd", "mfa"],
        })

    def test_validate_claims_mfa_list_invalid(self) -> None:
        """MFA claim as list without valid method raises."""
        client = self._get_client()
        with pytest.raises(TokenValidationError, match="MFA authentication required"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": ["pwd"],
            })

    def test_validate_claims_mfa_string_valid(self) -> None:
        """MFA claim as string with valid method passes."""
        client = self._get_client()
        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": "mfa",
        })

    def test_validate_claims_mfa_string_invalid(self) -> None:
        """MFA claim as string with invalid method raises."""
        client = self._get_client()
        with pytest.raises(TokenValidationError, match="MFA authentication required"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": "pwd",
            })

    def test_validate_claims_mfa_invalid_type(self) -> None:
        """MFA claim with invalid type raises."""
        client = self._get_client()
        with pytest.raises(TokenValidationError, match="amr claim is invalid"):
            client._validate_claims({
                "we3_project_id": "proj_test",
                "we3_role": "viewer",
                "amr": 123,
            })

    def test_validate_claims_no_mfa_required(self) -> None:
        """Claims validation passes when MFA is not required."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
            require_mfa_claim="",
        )
        client = JWKSClient(settings)
        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
        })


class TestOIDCAuthenticator:
    """Tests for OIDCAuthenticator."""

    def test_authenticate_success(self) -> None:
        """Successful authentication returns (project_id, role)."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        mock_payload = {
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": ["mfa"],
            "jti": "test-jti-12345",
        }

        with patch.object(auth._jwks_client, "verify_token", return_value=mock_payload):
            project_id, role = auth.authenticate("fake.token.here")
            assert project_id == "proj_test"
            assert role == "viewer"

    def test_authenticate_invalid_role(self) -> None:
        """Invalid role raises TokenValidationError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        mock_payload = {
            "we3_project_id": "proj_test",
            "we3_role": "superadmin",
        }

        with patch.object(auth._jwks_client, "verify_token", return_value=mock_payload):
            with pytest.raises(TokenValidationError, match="Invalid role"):
                auth.authenticate("fake.token.here")

    def test_get_token_subject_success(self) -> None:
        """get_token_subject returns subject from token."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        mock_jwt = MagicMock()
        mock_jwt.get_unverified_claims.return_value = {"sub": "user_123"}

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt)}):
            result = auth.get_token_subject("fake.token.here")
            assert result == "user_123"

    def test_get_token_subject_error(self) -> None:
        """get_token_subject returns None on error."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        mock_jwt = MagicMock()
        mock_jwt.get_unverified_claims.side_effect = Exception("Decode error")

        with patch.dict(sys.modules, {"jose": MagicMock(jwt=mock_jwt)}):
            result = auth.get_token_subject("fake.token.here")
            assert result is None

    def test_load_role_mapping(self) -> None:
        """Role mapping is loaded successfully."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        mapping = RoleMapping(
            id="role_mapping:1.0.0",
            version="v1.0.0",
            mappings={"group:admins": ["system_admin"]},
            created_at="2026-01-01T00:00:00Z",
            created_by="system",
        )
        auth.load_role_mapping(mapping)
        assert auth._role_mapping is mapping

    def test_get_workload_identity_api(self) -> None:
        """Workload identity for API type returns correct config."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        result = auth.get_workload_identity("api")
        assert result["identity_type"] == "api"
        assert result["audience"] == "we3-api"
        assert "read:basic" in result["scopes"]
        assert "write:self" in result["scopes"]

    def test_get_workload_identity_all_types(self) -> None:
        """All workload identity types return valid config."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        for identity_type in ["api", "scheduler", "provider_executor", "grader",
                              "maintenance", "report_export", "signing"]:
            result = auth.get_workload_identity(identity_type)
            assert result["identity_type"] == identity_type
            assert result["audience"] == f"we3-{identity_type}"
            assert len(result["scopes"]) > 0

    def test_get_workload_identity_invalid_type(self) -> None:
        """Invalid workload identity type raises ValueError."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        with pytest.raises(ValueError, match="Unknown workload identity type"):
            auth.get_workload_identity("invalid_type")

    def test_get_workload_scopes_unknown_type(self) -> None:
        """Unknown workload type returns empty scopes."""
        settings = OIDCSettings(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        auth = OIDCAuthenticator(settings)

        result = auth._get_workload_scopes("unknown_type")
        assert result == []


class TestCreateOIDCAuthenticator:
    """Tests for create_oidc_authenticator factory."""

    def test_create_oidc_authenticator(self) -> None:
        """Factory creates OIDCAuthenticator with correct settings."""
        auth = create_oidc_authenticator(
            issuer="https://idp.example.com",
            jwks_uri="https://idp.example.com/.well-known/jwks.json",
            audience="test-audience",
        )
        assert isinstance(auth, OIDCAuthenticator)
        assert auth._settings.issuer == "https://idp.example.com"
        assert auth._settings.audience == "test-audience"


class TestRoleMappingValidation:
    """Tests for RoleMapping model validation."""

    def test_role_mapping_valid(self) -> None:
        """Valid role mapping is created successfully."""
        mapping = RoleMapping(
            id="role_mapping:1.0.0",
            version="v1.0.0",
            mappings={"group:admins": ["system_admin"]},
            created_at="2026-01-01T00:00:00Z",
            created_by="system",
        )
        assert mapping.id == "role_mapping:1.0.0"
        assert mapping.version == "v1.0.0"

    def test_role_mapping_invalid_id(self) -> None:
        """Invalid role mapping ID raises validation error."""
        with pytest.raises(Exception):
            RoleMapping(
                id="invalid_id",
                version="v1.0.0",
                mappings={},
                created_at="2026-01-01T00:00:00Z",
                created_by="system",
            )

    def test_role_mapping_invalid_version(self) -> None:
        """Invalid version raises validation error."""
        with pytest.raises(Exception):
            RoleMapping(
                id="role_mapping:1.0.0",
                version="invalid",
                mappings={},
                created_at="2026-01-01T00:00:00Z",
                created_by="system",
            )
