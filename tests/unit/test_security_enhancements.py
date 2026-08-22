"""Regression tests for the API/security hardening contracts.

These tests intentionally distinguish revocation from bearer-token replay
resistance: a JWT ID and revocation authority can invalidate a token, but an
unrevoked bearer token is still reusable until expiry unless the deployment adds
sender-constrained authentication.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from wilson_eval3ngine.api.middleware import (
    CORSMiddleware,
    CSRFProtectionMiddleware,
    ContentTypeValidationMiddleware,
    RateLimitMiddleware,
    SECURITY_HEADERS,
)
from wilson_eval3ngine.security.csrf import CSRFProtection, CSRFValidationError
from wilson_eval3ngine.security.error_handling import (
    ErrorCode,
    ErrorSanitizer,
    SafeError,
    get_error_response,
)
from wilson_eval3ngine.security.input_validation import (
    ContentTypeValidator,
    IdempotencyKeyValidator,
    InputSanitizer,
    InputValidator,
    ProjectIdValidator,
    ValidationError,
)
from wilson_eval3ngine.security.oidc import TokenRevocationList, TokenValidationError
from wilson_eval3ngine.security.rate_limit import (
    RateLimitBackendUnavailable,
    RateLimiter,
    build_rate_limit_key,
)
from wilson_eval3ngine.security.secrets import SecretsManager, SecretValidationError


class TestTokenRevocationList:
    def test_revoke_and_check_token(self) -> None:
        revocations = TokenRevocationList()
        revocations.revoke("jti-123")
        assert revocations.is_revoked("jti-123") is True

    def test_non_revoked_token_not_detected(self) -> None:
        assert TokenRevocationList().is_revoked("jti-nonexistent") is False

    def test_revoked_token_expires(self) -> None:
        revocations = TokenRevocationList(revocation_ttl_seconds=1)
        revocations.revoke("jti-temp", token_ttl=1)
        assert revocations.is_revoked("jti-temp") is True
        time.sleep(1.1)
        assert revocations.is_revoked("jti-temp") is False

    def test_empty_jti_is_not_treated_as_revoked(self) -> None:
        revocations = TokenRevocationList()
        revocations.revoke("")
        assert revocations.is_revoked("") is False
        assert len(revocations._store) == 0

    def test_max_entries_is_bounded(self) -> None:
        revocations = TokenRevocationList(max_entries=5)
        for index in range(10):
            revocations.revoke(f"jti-{index}", token_ttl=3600)
        assert len(revocations._store) == 5
        assert revocations.is_revoked("jti-0") is False
        assert revocations.is_revoked("jti-9") is True

    def test_cleanup_expired_entries(self) -> None:
        revocations = TokenRevocationList(revocation_ttl_seconds=1)
        revocations.revoke("jti-a", token_ttl=1)
        revocations.revoke("jti-b", token_ttl=3600)
        time.sleep(1.1)
        assert revocations.cleanup_expired() == 1
        assert revocations.is_revoked("jti-b") is True

    def test_redis_backend_uses_bounded_jti_key(self) -> None:
        redis_client = MagicMock()
        redis_client.exists.return_value = 1
        revocations = TokenRevocationList(redis_client=redis_client)
        revocations.revoke("jti-redis")
        redis_client.setex.assert_called_once()
        assert revocations.is_revoked("jti-redis") is True
        redis_client.exists.assert_called_with("we3:token_revoked:jti-redis")

    def test_invalid_jti_is_rejected_before_backend_use(self) -> None:
        redis_client = MagicMock()
        revocations = TokenRevocationList(redis_client=redis_client)
        with pytest.raises(TokenValidationError):
            revocations.revoke("x" * 257)
        redis_client.setex.assert_not_called()


class TestRateLimiter:
    def test_in_memory_rate_limit_allows_under_limit(self) -> None:
        result = RateLimiter(default_limit=10, default_window=60).check("test-key")
        assert result.allowed is True
        assert result.remaining == 9
        assert result.backend == "memory"

    def test_in_memory_rate_limit_blocks_over_limit(self) -> None:
        limiter = RateLimiter(default_limit=2, default_window=60)
        limiter.check("test-key")
        limiter.check("test-key")
        result = limiter.check("test-key")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    def test_separate_keys_have_separate_windows(self) -> None:
        limiter = RateLimiter(default_limit=1, default_window=60)
        assert limiter.check("key-a").allowed is True
        assert limiter.check("key-b").allowed is True

    def test_window_resets(self) -> None:
        limiter = RateLimiter(default_limit=1, default_window=1)
        limiter.check("test-key")
        assert limiter.check("test-key").allowed is False
        time.sleep(1.1)
        assert limiter.check("test-key").allowed is True

    def test_redis_rate_limit_allows_and_blocks(self) -> None:
        redis_client = MagicMock()
        script = MagicMock(side_effect=([1, 9, 60], [0, 0, 30]))
        redis_client.register_script.return_value = script
        limiter = RateLimiter(redis_client=redis_client, default_limit=10)
        assert limiter.check("test-key").allowed is True
        blocked = limiter.check("test-key")
        assert blocked.allowed is False
        assert blocked.retry_after == 30
        assert blocked.backend == "redis"

    def test_development_can_fall_back_if_redis_init_fails(self) -> None:
        redis_client = MagicMock()
        redis_client.register_script.side_effect = Exception("Redis error")
        limiter = RateLimiter(redis_client=redis_client, default_limit=10)
        result = limiter.check("test-key")
        assert result.allowed is True
        assert result.backend == "memory"

    def test_assurance_mode_does_not_silently_fall_back(self) -> None:
        redis_client = MagicMock()
        redis_client.register_script.side_effect = Exception("Redis error")
        with pytest.raises(RateLimitBackendUnavailable):
            RateLimiter(redis_client=redis_client, fail_closed=True)

    def test_key_sanitization(self) -> None:
        safe_key = RateLimiter._sanitize_key("test; INJECT:KEY")
        assert ";" not in safe_key
        assert safe_key.startswith("we3:rl:")

    def test_pre_auth_key_does_not_disclose_raw_client_or_path(self) -> None:
        key = build_rate_limit_key("1.2.3.4", "/v1/experiments:run")
        assert "1.2.3.4" not in key
        assert "/v1/experiments:run" not in key
        assert "project:" not in key

    def test_verified_project_can_create_secondary_tenant_bucket(self) -> None:
        first = build_rate_limit_key("1.2.3.4", "/run", "proj_a")
        second = build_rate_limit_key("1.2.3.4", "/run", "proj_b")
        assert first != second
        assert "proj_a" in first

    def test_ip_anonymization(self) -> None:
        limiter = RateLimiter()
        assert limiter._anonymize_ip("192.168.1.100") == "192.168.1.0"
        assert limiter._anonymize_ip("2001:db8::1") == "2001:db8::"
        assert limiter._anonymize_ip("unknown") == "unknown"


class TestCSRFProtection:
    def test_generated_tokens_are_unique_and_two_part_compatible(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        first = csrf.generate_token()
        second = csrf.generate_token()
        assert first != second
        timestamp, proof = first.split(".", 1)
        assert timestamp.isdigit()
        assert ":" in proof

    def test_validate_token_success(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token = csrf.generate_token()
        assert csrf.validate_token(token, token) is True

    def test_missing_or_mismatched_double_submit_values_are_rejected(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token = csrf.generate_token()
        with pytest.raises(CSRFValidationError, match="missing from header"):
            csrf.validate_token("", token)
        with pytest.raises(CSRFValidationError, match="missing from cookie"):
            csrf.validate_token(token, "")
        with pytest.raises(CSRFValidationError, match="do not match"):
            csrf.validate_token(token, CSRFProtection(secret="different-secret").generate_token())

    def test_invalid_format_rejected(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        with pytest.raises(CSRFValidationError, match="format"):
            csrf.validate_token("invalid", "invalid")

    def test_legacy_expired_token_rejected(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        timestamp = str(int(time.time()) - 4000)
        signature = hmac.new(
            b"test-secret-key-12345", timestamp.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{timestamp}.{signature}"
        with pytest.raises(CSRFValidationError, match="expired"):
            csrf.validate_token(token, token)

    def test_legacy_future_token_rejected(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        timestamp = str(int(time.time()) + 100)
        signature = hmac.new(
            b"test-secret-key-12345", timestamp.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{timestamp}.{signature}"
        with pytest.raises(CSRFValidationError, match="future"):
            csrf.validate_token(token, token)

    def test_invalid_signature_rejected(self) -> None:
        csrf = CSRFProtection(secret="test-secret-key-12345")
        timestamp = str(int(time.time()))
        bad_signature = hmac.new(
            b"wrong-secret", timestamp.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{timestamp}.{bad_signature}"
        with pytest.raises(CSRFValidationError, match="signature"):
            csrf.validate_token(token, token)


class TestInputValidation:
    @pytest.mark.parametrize("project_id", ["proj_123", "my-project", "PROJECT-A"])
    def test_valid_project_ids(self, project_id: str) -> None:
        assert ProjectIdValidator.validate(project_id) == project_id

    @pytest.mark.parametrize(
        "project_id",
        ["", "a" * 65, "proj/../other", "proj;DROP"],
    )
    def test_invalid_project_ids(self, project_id: str) -> None:
        with pytest.raises(ValidationError):
            ProjectIdValidator.validate(project_id)

    def test_idempotency_key_bounds(self) -> None:
        assert IdempotencyKeyValidator.validate("abc-123") == "abc-123"
        assert IdempotencyKeyValidator.validate("key_456") == "key_456"
        for invalid in ("", "a" * 129, "key;injection"):
            with pytest.raises(ValidationError):
                IdempotencyKeyValidator.validate(invalid)

    def test_json_and_form_content_types(self) -> None:
        validator = ContentTypeValidator()
        assert validator.validate_json("application/json")[0] is True
        assert validator.validate_json("application/json; charset=utf-8")[0] is True
        assert validator.validate_json("text/html")[0] is False
        assert validator.validate_json("")[0] is False
        assert validator.validate_form("application/x-www-form-urlencoded")[0] is True
        assert validator.validate_form("multipart/form-data")[0] is True

    def test_string_and_path_sanitizers(self) -> None:
        assert "<script>" not in InputSanitizer.sanitize_string("<script>x</script>")
        assert "\x00" not in InputSanitizer.sanitize_string("hello\x00world")
        assert len(InputSanitizer.sanitize_string("a" * 20000)) <= InputSanitizer.MAX_STRING_LENGTH
        path = InputSanitizer.sanitize_path_component("../../../etc/passwd")
        assert ".." not in path and "/" not in path

    def test_composite_validator(self) -> None:
        validator = InputValidator()
        assert validator.validate_project_id("proj_test") == "proj_test"
        assert validator.validate_idempotency_key("key-123") == "key-123"
        assert validator.validate_json_content_type("application/json")[0] is True


class TestErrorHandling:
    @pytest.mark.parametrize(
        ("raw", "secret", "marker"),
        [
            ("/etc/passwd: error", "/etc/passwd", "[path]"),
            ("postgresql://user:pass@host/db", "user:pass", "[connection]"),
            ("sk-abc123def456ghi789jkl012mno345pqr678", "sk-abc", "[api_key]"),
            ("Bearer eyJhbGciOiJIUzI1NiJ9", "eyJhbGci", "[bearer_token]"),
            ("Contact user@example.com", "user@example.com", "[email]"),
            ("Connection from 192.168.1.100", "192.168.1.100", "[ip_address]"),
            ("Transaction 550e8400-e29b-41d4-a716-446655440000", "550e8400", "[uuid]"),
            ("SELECT * FROM users", "SELECT", "[sql]"),
        ],
    )
    def test_internal_diagnostic_redaction(
        self, raw: str, secret: str, marker: str
    ) -> None:
        result = ErrorSanitizer.sanitize(raw)
        assert secret not in result
        assert marker in result

    def test_long_internal_diagnostic_is_bounded(self) -> None:
        result = ErrorSanitizer.sanitize("A" * 500)
        assert len(result) <= ErrorSanitizer.MAX_ERROR_LENGTH + 3

    def test_safe_error_serialization_excludes_internal_detail(self) -> None:
        error = SafeError(
            error_code=ErrorCode.INTERNAL_ERROR,
            safe_detail="Something went wrong",
            trace_id="trc_123",
            retryable=True,
            internal_detail="Internal: /etc/passwd not found",
        )
        payload = error.to_dict()
        assert payload["safe_detail"] == "Something went wrong"
        assert "internal_detail" not in payload

    def test_unexpected_exception_returns_fixed_public_message(self) -> None:
        result = get_error_response(
            Exception("Error at /etc/passwd with SELECT query"),
            trace_id="trc_456",
        )
        assert result["code"] == ErrorCode.INTERNAL_ERROR.value
        assert result["safe_detail"] == "internal server error"
        assert result["trace_id"] == "trc_456"


class TestDevelopmentSecretsManager:
    def test_load_key_from_env(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"WE3_TEST_KEY": key}):
            manager = SecretsManager(env_var_name="WE3_TEST_KEY")
            assert manager.get_current_key_id() is not None

    def test_encrypt_decrypt_roundtrip_and_rotation(self) -> None:
        manager = SecretsManager()
        encrypted, old_key = manager.encrypt(b"sensitive data")
        assert manager.decrypt(encrypted, old_key) == b"sensitive data"
        result = manager.rotate_key()
        assert result.new_key_id != old_key
        assert manager.decrypt(encrypted, old_key) == b"sensitive data"

    def test_wrong_selected_key_fails(self) -> None:
        manager = SecretsManager()
        encrypted, _key_id = manager.encrypt(b"sensitive data")
        wrong = Fernet.generate_key().decode()
        wrong_id = manager._derive_key_id(wrong)
        manager._keyring[wrong_id] = Fernet(wrong.encode())
        with pytest.raises(SecretValidationError, match="(?i)decryption failed"):
            manager.decrypt(encrypted, wrong_id)

    def test_health_and_validation(self) -> None:
        manager = SecretsManager()
        assert manager.health_check()["status"] == "ok"
        assert manager.validate_key(Fernet.generate_key().decode()) is True
        assert manager.validate_key("invalid-key") is False

    def test_production_rejects_local_secret_manager(self) -> None:
        with pytest.raises(SecretValidationError, match="development-only"):
            SecretsManager(environment="production")


class TestSecurityHeaders:
    def test_hsts_and_cross_origin_headers(self) -> None:
        assert "preload" in SECURITY_HEADERS["Strict-Transport-Security"]
        assert SECURITY_HEADERS["Cross-Origin-Opener-Policy"] == "same-origin"
        assert SECURITY_HEADERS["Cross-Origin-Resource-Policy"] == "same-origin"
        assert SECURITY_HEADERS["Cross-Origin-Embedder-Policy"] == "require-corp"

    def test_browser_headers_are_restrictive(self) -> None:
        assert "geolocation=()" in SECURITY_HEADERS["Permissions-Policy"]
        assert "camera=()" in SECURITY_HEADERS["Permissions-Policy"]
        assert "frame-ancestors 'none'" in SECURITY_HEADERS["Content-Security-Policy"]
        assert "no-store" in SECURITY_HEADERS["Cache-Control"]
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"


class TestCORSMiddleware:
    def test_allowed_origin_gets_exact_cors_header(self) -> None:
        from starlette.responses import Response

        middleware = CORSMiddleware(
            app=MagicMock(), allowed_origins=["https://example.com"]
        )

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.headers = {"Origin": "https://example.com"}
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "https://example.com"

    def test_disallowed_origin_is_server_rejected(self) -> None:
        from starlette.responses import Response

        middleware = CORSMiddleware(
            app=MagicMock(), allowed_origins=["https://example.com"]
        )

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.headers = {"Origin": "https://evil.com"}
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 403
        assert response.headers.get("Access-Control-Allow-Origin") is None

    def test_valid_preflight_returns_204(self) -> None:
        middleware = CORSMiddleware(
            app=MagicMock(), allowed_origins=["https://example.com"]
        )
        request = MagicMock()
        request.method = "OPTIONS"
        request.headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        }
        response = asyncio.run(middleware.dispatch(request, MagicMock()))
        assert response.status_code == 204


class TestContentTypeValidationMiddleware:
    def _dispatch(self, method: str, path: str, content_type: str | None):
        from starlette.responses import Response

        middleware = ContentTypeValidationMiddleware(app=MagicMock())

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = method
        request.url.path = path
        request.headers = {} if content_type is None else {"Content-Type": content_type}
        return asyncio.run(middleware.dispatch(request, call_next))

    def test_json_content_type_accepted(self) -> None:
        assert self._dispatch("POST", "/v1/experiments:run", "application/json").status_code == 200

    def test_invalid_content_type_rejected(self) -> None:
        assert self._dispatch("POST", "/v1/experiments:run", "text/html").status_code == 415

    def test_get_has_no_content_type_requirement(self) -> None:
        assert self._dispatch("GET", "/v1/experiments:run", None).status_code == 200


class TestCSRFMiddleware:
    def test_bearer_header_auth_is_not_ambient_and_is_exempt(self) -> None:
        from starlette.responses import Response

        middleware = CSRFProtectionMiddleware(app=MagicMock(), auth_mode="oidc")

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/experiments:run"
        request.headers = {"Authorization": "Bearer valid-token"}
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_development_header_auth_is_exempt(self) -> None:
        from starlette.responses import Response

        middleware = CSRFProtectionMiddleware(app=MagicMock(), auth_mode="dev")

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/experiments:run"
        request.headers = {}
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200


class TestRateLimitMiddleware:
    def test_requests_under_limit_receive_headers(self) -> None:
        from starlette.responses import Response

        middleware = RateLimitMiddleware(
            app=MagicMock(), default_limit=100, default_window=60
        )

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/test_endpoint"
        request.headers = {}
        request.client.host = "192.168.1.1"
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    def test_requests_over_limit_receive_429(self) -> None:
        from starlette.responses import Response

        middleware = RateLimitMiddleware(
            app=MagicMock(), default_limit=1, default_window=60
        )

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/test_endpoint"
        request.headers = {"X-WE3-Project-ID": "attacker-selected-project"}
        request.client.host = "192.168.1.1"
        assert asyncio.run(middleware.dispatch(request, call_next)).status_code == 200
        # Changing an unauthenticated project header must not buy a fresh bucket.
        request.headers = {"X-WE3-Project-ID": "different-project"}
        assert asyncio.run(middleware.dispatch(request, call_next)).status_code == 429
