"""
Integration tests for OIDC authentication (SEC-001).

Tests the full authentication flow from API endpoint through OIDC token
validation, including MFA enforcement, role mapping, and error handling.
Requires python-jose optional dependency.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Skip tests if optional OIDC dependency not available
pytest.importorskip("jose", reason="python-jose required for OIDC integration tests")

from wilson_eval3ngine.api.main import create_app
from wilson_eval3ngine.config import Settings
from wilson_eval3ngine.security.oidc import (
    OIDCSettings,
    OIDCAuthenticator,
    TokenValidationError,
)


class TestOIDCAPIIntegration:
    """Integration tests for OIDC authentication through the API."""

    def test_oidc_mode_rejects_dev_headers(self, tmp_path) -> None:
        """OIDC mode does not accept development header authentication."""
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'oidc-test.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="oidc",
            environment="test",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )
        client = TestClient(create_app(settings))

        # Dev headers should not work in OIDC mode
        response = client.post(
            "/v1/experiments:validate",
            json={"experiment": {"schema_version": "we3.experiment.v1"}},
            headers={
                "X-WE3-Project-ID": "model-safety",
                "X-WE3-Role": "evaluation_engineer",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "missing_bearer_token"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_oidc_mode_accepts_valid_bearer_token(
        self, mock_verify: Mock, tmp_path
    ) -> None:
        """Valid OIDC bearer token is accepted in production mode."""
        mock_verify.return_value = {
            "we3_project_id": "model-safety",
            "we3_role": "evaluation_engineer",
            "sub": "user_123",
            "amr": ["pwd", "mfa"],
        }

        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'oidc-valid.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="oidc",
            environment="test",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/v1/experiments:validate",
            json={"experiment": {"schema_version": "we3.experiment.v1"}},
            headers={
                "Authorization": "Bearer valid-oidc-token",
            },
        )
        # Should not get 401 - token was accepted
        assert response.status_code != 401

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_oidc_mode_rejects_invalid_role(self, mock_verify: Mock, tmp_path) -> None:
        """Token with invalid role is rejected."""
        mock_verify.return_value = {
            "we3_project_id": "model-safety",
            "we3_role": "superadmin",  # Not in allowed roles
            "sub": "user_123",
            "amr": ["pwd", "mfa"],
        }

        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'oidc-bad-role.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="oidc",
            environment="test",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/v1/experiments:validate",
            json={"experiment": {"schema_version": "we3.experiment.v1"}},
            headers={
                "Authorization": "Bearer invalid-role-token",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_token"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_oidc_mode_rejects_missing_project_claim(
        self, mock_verify: Mock, tmp_path
    ) -> None:
        """Token missing project claim is rejected."""
        mock_verify.side_effect = TokenValidationError("Missing required claim: we3_project_id")

        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'oidc-no-project.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="oidc",
            environment="test",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/v1/experiments:validate",
            json={"experiment": {"schema_version": "we3.experiment.v1"}},
            headers={
                "Authorization": "Bearer no-project-token",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_token"

    @patch("wilson_eval3ngine.security.oidc.JWKSClient.verify_token")
    def test_oidc_mode_rejects_missing_role_claim(
        self, mock_verify: Mock, tmp_path
    ) -> None:
        """Token missing role claim is rejected."""
        mock_verify.side_effect = TokenValidationError("Missing required claim: we3_role")

        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'oidc-no-role.db'}",
            artifact_root=tmp_path / "artifacts",
            auth_mode="oidc",
            environment="test",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/v1/experiments:validate",
            json={"experiment": {"schema_version": "we3.experiment.v1"}},
            headers={
                "Authorization": "Bearer no-role-token",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_token"


class TestMFAValidation:
    """Tests for MFA claim validation in OIDC tokens."""

    def test_mfa_required_with_valid_amr(self) -> None:
        """Token with valid MFA in amr claim passes validation."""
        from wilson_eval3ngine.security.oidc import JWKSClient

        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        client = JWKSClient(settings)

        # Should not raise
        client._validate_claims({
            "we3_project_id": "proj_test",
            "we3_role": "viewer",
            "amr": ["pwd", "mfa"],
        })

    def test_mfa_required_without_amr(self) -> None:
        """Token without amr claim fails MFA validation."""
        from wilson_eval3ngine.security.oidc import JWKSClient

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

    def test_mfa_required_with_non_mfa_amr(self) -> None:
        """Token with only non-MFA amr methods fails validation."""
        from wilson_eval3ngine.security.oidc import JWKSClient

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


class TestWorkloadIdentityIntegration:
    """Tests for workload identity in production OIDC mode."""

    def test_workload_identity_audience_isolation(self) -> None:
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

    def test_workload_identity_scopes_are_minimal(self) -> None:
        """Workload identities have minimal required scopes."""
        settings = OIDCSettings(
            issuer="https://auth.example.com",
            jwks_uri="https://auth.example.com/.well-known/jwks.json",
            audience="wilson-eval3ngine",
        )
        authenticator = OIDCAuthenticator(settings)

        # Grader should only have evidence write scope, not provider credentials
        grader_identity = authenticator.get_workload_identity("grader")
        assert "read:responses" in grader_identity["scopes"]
        assert "write:evidence" in grader_identity["scopes"]
        # Should NOT have provider or admin scopes
        assert "write:provider_credentials" not in grader_identity["scopes"]
        assert "system_admin" not in grader_identity["scopes"]


class TestOIDCProductionValidation:
    """Tests for production OIDC configuration validation."""

    def test_production_validation_requires_oidc_issuer(self) -> None:
        """Production mode requires OIDC issuer configuration."""
        from wilson_eval3ngine.config import Settings

        settings = Settings(
            database_url="postgresql://localhost/we3",
            artifact_root="/var/we3/artifacts",
            auth_mode="oidc",
            environment="production",
            oidc_issuer="",  # Missing!
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )

        with pytest.raises(ValueError, match="WE3_OIDC_ISSUER"):
            settings.validate_for_production()

    def test_production_validation_requires_jwks_uri(self) -> None:
        """Production mode requires JWKS URI configuration."""
        from wilson_eval3ngine.config import Settings

        settings = Settings(
            database_url="postgresql://localhost/we3",
            artifact_root="/var/we3/artifacts",
            auth_mode="oidc",
            environment="production",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="",  # Missing!
            oidc_audience="wilson-eval3ngine",
        )

        with pytest.raises(ValueError, match="WE3_OIDC_JWKS_URI"):
            settings.validate_for_production()

    def test_production_validation_rejects_dev_mode(self) -> None:
        """Production mode rejects development header authentication."""
        from wilson_eval3ngine.config import Settings

        settings = Settings(
            database_url="postgresql://localhost/we3",
            artifact_root="/var/we3/artifacts",
            auth_mode="dev",  # Not allowed in production!
            environment="production",
        )

        with pytest.raises(ValueError, match="development header authentication"):
            settings.validate_for_production()

    def test_production_validation_rejects_sqlite(self) -> None:
        """Production mode rejects SQLite database."""
        from wilson_eval3ngine.config import Settings

        settings = Settings(
            database_url="sqlite:///./var/we3.db",  # Not allowed in production!
            artifact_root="/var/we3/artifacts",
            auth_mode="oidc",
            environment="production",
            oidc_issuer="https://auth.example.com",
            oidc_jwks_uri="https://auth.example.com/.well-known/jwks.json",
            oidc_audience="wilson-eval3ngine",
        )

        with pytest.raises(ValueError, match="PostgreSQL"):
            settings.validate_for_production()
