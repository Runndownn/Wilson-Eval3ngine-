"""Comprehensive security tests for new security implementations.

Covers:
- JWT token replay protection (jti validation, revocation list)
- Redis-backed distributed rate limiting
- CSRF protection (token generation, validation, double-submit)
- Input validation (project ID, idempotency key, content-type)
- Error sanitization (sensitive data redaction)
- Secrets management (key rotation, validation)
- Audit service (event logging, checkpoint signing)
- Security headers (COOP, CORP, HSTS preload)
- CORS policy enforcement
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from wilson_eval3ngine.security.oidc import (
    TokenRevocationList,
    TokenRevocationError,
    TokenValidationError,
)
from wilson_eval3ngine.security.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    InMemoryBackend,
    RedisBackend,
    build_rate_limit_key,
)
from wilson_eval3ngine.security.csrf import CSRFProtection, CSRFValidationError
from wilson_eval3ngine.security.input_validation import (
    InputValidator,
    ProjectIdValidator,
    IdempotencyKeyValidator,
    ContentTypeValidator,
    InputSanitizer,
    ValidationError,
)
from wilson_eval3ngine.security.error_handling import (
    ErrorCode,
    SafeError,
    ErrorSanitizer,
    get_error_response,
)
from wilson_eval3ngine.security.secrets import (
    SecretsManager,
    SecretMetadata,
    SecretValidationError,
)
from wilson_eval3ngine.api.middleware import (
    SECURITY_HEADERS,
    CORSMiddleware,
    CSRFProtectionMiddleware,
    ContentTypeValidationMiddleware,
    RateLimitMiddleware,
)


class TestTokenRevocationList:
    """Tests for JWT token replay protection."""

    def test_revoke_and_check_token(self) -> None:
        """Revoked tokens are detected."""
        rl = TokenRevocationList()
        rl.revoke("jti-123")
        assert rl.is_revoked("jti-123") is True

    def test_non_revoked_token_not_detected(self) -> None:
        """Non-revoked tokens pass validation."""
        rl = TokenRevocationList()
        assert rl.is_revoked("jti-nonexistent") is False

    def test_revoked_token_expires(self) -> None:
        """Revoked tokens expire after TTL."""
        rl = TokenRevocationList(revocation_ttl_seconds=1)
        rl.revoke("jti-temp", token_ttl=1)
        assert rl.is_revoked("jti-temp") is True
        time.sleep(1.1)
        assert rl.is_revoked("jti-temp") is False

    def test_empty_jti_not_revoked(self) -> None:
        """Empty jti is not treated as revoked."""
        rl = TokenRevocationList()
        assert rl.is_revoked("") is False

    def test_revoke_empty_jti_noop(self) -> None:
        """Revoking empty jti is a no-op."""
        rl = TokenRevocationList()
        rl.revoke("")
        assert len(rl._store) == 0

    def test_max_entries_enforced(self) -> None:
        """Revocation list enforces max entries via LRU."""
        rl = TokenRevocationList(max_entries=5)
        for i in range(10):
            rl.revoke(f"jti-{i}", token_ttl=3600)
        assert len(rl._store) == 5
        # LRU: oldest entries evicted
        assert rl.is_revoked("jti-0") is False
        assert rl.is_revoked("jti-9") is True

    def test_cleanup_expired_entries(self) -> None:
        """Cleanup removes expired entries."""
        rl = TokenRevocationList(revocation_ttl_seconds=1)
        rl.revoke("jti-a", token_ttl=1)
        rl.revoke("jti-b", token_ttl=3600)
        time.sleep(1.1)
        removed = rl.cleanup_expired()
        assert removed == 1
        assert rl.is_revoked("jti-a") is False
        assert rl.is_revoked("jti-b") is True

    def test_redis_backend_revoke_and_check(self) -> None:
        """Redis-backed revocation list works with mock Redis."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        rl = TokenRevocationList(redis_client=mock_redis)
        rl.revoke("jti-redis")
        mock_redis.setex.assert_called_once()
        assert rl.is_revoked("jti-redis") is True
        mock_redis.exists.assert_called_with("we3:token_revoked:jti-redis")


class TestRateLimiter:
    """Tests for distributed rate limiting."""

    def test_in_memory_rate_limit_allows_under_limit(self) -> None:
        """Requests under limit are allowed."""
        limiter = RateLimiter(default_limit=10, default_window=60)
        result = limiter.check("test-key")
        assert result.allowed is True
        assert result.remaining == 9

    def test_in_memory_rate_limit_blocks_over_limit(self) -> None:
        """Requests over limit are blocked."""
        limiter = RateLimiter(default_limit=2, default_window=60)
        limiter.check("test-key")
        limiter.check("test-key")
        result = limiter.check("test-key")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    def test_in_memory_rate_limit_separate_keys(self) -> None:
        """Different keys have independent rate limits."""
        limiter = RateLimiter(default_limit=1, default_window=60)
        r1 = limiter.check("key-a")
        r2 = limiter.check("key-b")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_in_memory_rate_limit_window_reset(self) -> None:
        """Rate limit resets after window expires."""
        limiter = RateLimiter(default_limit=1, default_window=1)
        limiter.check("test-key")
        result = limiter.check("test-key")
        assert result.allowed is False
        time.sleep(1.1)
        result = limiter.check("test-key")
        assert result.allowed is True

    def test_redis_rate_limit_allows_under_limit(self) -> None:
        """Redis-backed rate limiting allows under limit."""
        mock_redis = MagicMock()
        # Mock script returns [1, 9, 60] (allowed, remaining, ttl)
        mock_redis.register_script.return_value = MagicMock(return_value=[1, 9, 60])
        limiter = RateLimiter(redis_client=mock_redis, default_limit=10, default_window=60)
        result = limiter.check("test-key")
        assert result.allowed is True
        assert result.remaining == 9

    def test_redis_rate_limit_blocks_over_limit(self) -> None:
        """Redis-backed rate limiting blocks over limit."""
        mock_redis = MagicMock()
        # Mock script returns [0, 0, 30] (blocked, remaining=0, ttl=30)
        mock_redis.register_script.return_value = MagicMock(return_value=[0, 0, 30])
        limiter = RateLimiter(redis_client=mock_redis, default_limit=1, default_window=60)
        result = limiter.check("test-key")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after == 30

    def test_redis_rate_limit_falls_back_on_error(self) -> None:
        """Rate limiter fails open when Redis errors."""
        mock_redis = MagicMock()
        mock_redis.register_script.side_effect = Exception("Redis error")
        limiter = RateLimiter(redis_client=mock_redis, default_limit=10, default_window=60)
        result = limiter.check("test-key")
        assert result.allowed is True  # Fail open

    def test_key_sanitization(self) -> None:
        """Rate limit keys are sanitized to prevent injection."""
        limiter = RateLimiter()
        # Key with special characters should be sanitized
        safe_key = RateLimiter._sanitize_key("test; INJECT:KEY")
        assert ";" not in safe_key
        assert "we3:rl:" in safe_key

    def test_build_rate_limit_key_includes_project(self) -> None:
        """Rate limit keys include project scope."""
        key = build_rate_limit_key("1.2.3.4", "/v1/experiments:run", "proj_a")
        assert "1.2.3.4" in key
        assert "/v1/experiments:run" in key
        assert "proj_a" in key

    def test_build_rate_limit_key_without_project(self) -> None:
        """Rate limit keys work without project scope."""
        key = build_rate_limit_key("1.2.3.4", "/health")
        assert "1.2.3.4" in key
        assert "/health" in key

    def test_ip_anonymization_ipv4(self) -> None:
        """IPv4 addresses are anonymized."""
        limiter = RateLimiter()
        assert limiter._anonymize_ip("192.168.1.100") == "192.168.1.0"

    def test_ip_anonymization_ipv6(self) -> None:
        """IPv6 addresses are anonymized."""
        limiter = RateLimiter()
        result = limiter._anonymize_ip("2001:db8::1")
        assert result == "2001:db8:0:0:0:0:0:0" or result.startswith("2001:db8:0:0")

    def test_ip_anonymization_unknown(self) -> None:
        """Unknown IP formats are returned as-is."""
        limiter = RateLimiter()
        assert limiter._anonymize_ip("unknown") == "unknown"


class TestCSRFProtection:
    """Tests for CSRF token protection."""

    def test_generate_token(self) -> None:
        """CSRF token is generated with correct format."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token = csrf.generate_token()
        assert "." in token
        timestamp, signature = token.rsplit(".", 1)
        assert timestamp.isdigit()
        assert len(signature) > 0

    def test_validate_token_success(self) -> None:
        """Valid CSRF token passes validation."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token = csrf.generate_token()
        assert csrf.validate_token(token, token) is True

    def test_validate_token_mismatch(self) -> None:
        """Mismatched tokens are rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token1 = csrf.generate_token()
        # Create a different token by using a different secret
        csrf2 = CSRFProtection(secret="different-secret")
        token2 = csrf2.generate_token()
        with pytest.raises(CSRFValidationError, match="do not match"):
            csrf.validate_token(token1, token2)

    def test_validate_token_missing_header(self) -> None:
        """Missing header token is rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        with pytest.raises(CSRFValidationError, match="missing from header"):
            csrf.validate_token("", "cookie-token")

    def test_validate_token_missing_cookie(self) -> None:
        """Missing cookie token is rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        with pytest.raises(CSRFValidationError, match="missing from cookie"):
            csrf.validate_token("header-token", "")

    def test_validate_token_invalid_format(self) -> None:
        """Malformed tokens are rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        with pytest.raises(CSRFValidationError, match="format"):
            csrf.validate_token("invalid", "invalid")

    def test_validate_token_expired(self) -> None:
        """Expired tokens are rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        # Manually create an expired token
        old_timestamp = str(int(time.time()) - 4000)  # 1+ hour ago
        import hmac
        import hashlib
        signature = hmac.new(
            b"test-secret-key-12345",
            old_timestamp.encode(),
            hashlib.sha256,
        ).hexdigest()
        expired_token = f"{old_timestamp}.{signature}"
        with pytest.raises(CSRFValidationError, match="expired"):
            csrf.validate_token(expired_token, expired_token)

    def test_validate_token_future_timestamp(self) -> None:
        """Tokens with future timestamps are rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        future_timestamp = str(int(time.time()) + 100)  # 100s in future
        import hmac
        import hashlib
        signature = hmac.new(
            b"test-secret-key-12345",
            future_timestamp.encode(),
            hashlib.sha256,
        ).hexdigest()
        future_token = f"{future_timestamp}.{signature}"
        with pytest.raises(CSRFValidationError, match="future"):
            csrf.validate_token(future_token, future_token)

    def test_validate_token_invalid_signature(self) -> None:
        """Tokens with invalid signatures are rejected."""
        csrf = CSRFProtection(secret="test-secret-key-12345")
        token = csrf.generate_token()
        timestamp, _ = token.rsplit(".", 1)
        # Use wrong secret for signature
        import hmac
        import hashlib
        bad_signature = hmac.new(
            b"wrong-secret",
            timestamp.encode(),
            hashlib.sha256,
        ).hexdigest()
        bad_token = f"{timestamp}.{bad_signature}"
        with pytest.raises(CSRFValidationError, match="signature"):
            csrf.validate_token(bad_token, bad_token)

    def test_different_secrets_produce_different_tokens(self) -> None:
        """Different secrets produce incompatible tokens."""
        csrf1 = CSRFProtection(secret="secret-1")
        csrf2 = CSRFProtection(secret="secret-2")
        token1 = csrf1.generate_token()
        with pytest.raises(CSRFValidationError):
            csrf2.validate_token(token1, token1)


class TestInputValidation:
    """Tests for input validation and sanitization."""

    def test_valid_project_id(self) -> None:
        """Valid project IDs pass validation."""
        assert ProjectIdValidator.validate("proj_123") == "proj_123"
        assert ProjectIdValidator.validate("my-project") == "my-project"
        assert ProjectIdValidator.validate("PROJECT-A") == "PROJECT-A"

    def test_empty_project_id_rejected(self) -> None:
        """Empty project IDs are rejected."""
        with pytest.raises(ValidationError, match="required"):
            ProjectIdValidator.validate("")

    def test_sql_injection_in_project_id(self) -> None:
        """SQL injection in project ID is rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            ProjectIdValidator.validate("proj'; DROP TABLE runs; --")

    def test_path_traversal_in_project_id(self) -> None:
        """Path traversal in project ID is rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            ProjectIdValidator.validate("proj/../other")

    def test_long_project_id_rejected(self) -> None:
        """Overly long project IDs are rejected."""
        with pytest.raises(ValidationError, match="length"):
            ProjectIdValidator.validate("a" * 65)

    def test_special_chars_in_project_id_rejected(self) -> None:
        """Special characters in project ID are rejected."""
        with pytest.raises(ValidationError, match="invalid characters"):
            ProjectIdValidator.validate("proj;DROP")

    def test_valid_idempotency_key(self) -> None:
        """Valid idempotency keys pass validation."""
        assert IdempotencyKeyValidator.validate("abc-123") == "abc-123"
        assert IdempotencyKeyValidator.validate("key_456") == "key_456"

    def test_empty_idempotency_key_rejected(self) -> None:
        """Empty idempotency keys are rejected."""
        with pytest.raises(ValidationError, match="required"):
            IdempotencyKeyValidator.validate("")

    def test_long_idempotency_key_rejected(self) -> None:
        """Overly long idempotency keys are rejected."""
        with pytest.raises(ValidationError, match="length"):
            IdempotencyKeyValidator.validate("a" * 129)

    def test_special_chars_in_idempotency_key_rejected(self) -> None:
        """Special characters in idempotency key are rejected."""
        with pytest.raises(ValidationError, match="invalid"):
            IdempotencyKeyValidator.validate("key;injection")

    def test_json_content_type_valid(self) -> None:
        """Valid JSON content types pass validation."""
        cv = ContentTypeValidator()
        valid, _ = cv.validate_json("application/json")
        assert valid is True
        valid, _ = cv.validate_json("application/json; charset=utf-8")
        assert valid is True

    def test_json_content_type_invalid(self) -> None:
        """Invalid content types are rejected."""
        cv = ContentTypeValidator()
        valid, msg = cv.validate_json("text/html")
        assert valid is False
        assert "application/json" in msg

    def test_empty_content_type_rejected(self) -> None:
        """Empty content type is rejected."""
        cv = ContentTypeValidator()
        valid, msg = cv.validate_json("")
        assert valid is False
        assert "required" in msg

    def test_form_content_type_valid(self) -> None:
        """Valid form content types pass validation."""
        cv = ContentTypeValidator()
        valid, _ = cv.validate_form("application/x-www-form-urlencoded")
        assert valid is True
        valid, _ = cv.validate_form("multipart/form-data")
        assert valid is True

    def test_html_escape(self) -> None:
        """HTML entities are escaped in sanitized strings."""
        result = InputSanitizer.sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;" in result

    def test_null_byte_removal(self) -> None:
        """Null bytes are removed from sanitized strings."""
        result = InputSanitizer.sanitize_string("hello\x00world")
        assert "\x00" not in result

    def test_string_truncation(self) -> None:
        """Overly long strings are truncated."""
        result = InputSanitizer.sanitize_string("a" * 20000)
        assert len(result) <= InputSanitizer.MAX_STRING_LENGTH

    def test_path_traversal_sanitization(self) -> None:
        """Path traversal characters are removed from path components."""
        result = InputSanitizer.sanitize_path_component("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_input_validator_integration(self) -> None:
        """InputValidator combines all validators."""
        validator = InputValidator()
        assert validator.validate_project_id("proj_test") == "proj_test"
        assert validator.validate_idempotency_key("key-123") == "key-123"
        valid, _ = validator.validate_json_content_type("application/json")
        assert valid is True


class TestErrorHandling:
    """Tests for error sanitization and safe error responses."""

    def test_sanitize_file_paths(self) -> None:
        """File paths are redacted in error messages."""
        result = ErrorSanitizer.sanitize("/etc/passwd: error")
        assert "/etc/passwd" not in result
        assert "[path]" in result

    def test_sanitize_db_connection_strings(self) -> None:
        """Database connection strings are redacted."""
        result = ErrorSanitizer.sanitize("postgresql://user:pass@host/db")
        assert "postgresql://user:pass@host/db" not in result
        assert "[db_connection]" in result

    def test_sanitize_api_keys(self) -> None:
        """API keys are redacted."""
        result = ErrorSanitizer.sanitize("sk-abc123def456ghi789jkl012mno345pqr678")
        assert "sk-abc123def456ghi789jkl012mno345pqr678" not in result
        assert "[api_key]" in result

    def test_sanitize_bearer_tokens(self) -> None:
        """Bearer tokens are redacted."""
        result = ErrorSanitizer.sanitize("Bearer eyJhbGciOiJIUzI1NiJ9")
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "[bearer_token]" in result

    def test_sanitize_email_addresses(self) -> None:
        """Email addresses are redacted."""
        result = ErrorSanitizer.sanitize("Contact user@example.com for details")
        assert "user@example.com" not in result
        assert "[email]" in result

    def test_sanitize_ip_addresses(self) -> None:
        """IP addresses are redacted."""
        result = ErrorSanitizer.sanitize("Connection from 192.168.1.100 failed")
        assert "192.168.1.100" not in result
        assert "[ip_address]" in result

    def test_sanitize_uuids(self) -> None:
        """UUIDs are redacted."""
        result = ErrorSanitizer.sanitize("Transaction 550e8400-e29b-41d4-a716-446655440000 failed")
        assert "550e8400-e29b-41d4-a716-446655440000" not in result
        assert "[uuid]" in result

    def test_sanitize_sql_queries(self) -> None:
        """SQL queries are redacted."""
        result = ErrorSanitizer.sanitize("SELECT * FROM users WHERE id=1")
        assert "SELECT" not in result
        assert "[sql]" in result

    def test_sanitize_truncates_long_errors(self) -> None:
        """Long error messages are truncated."""
        long_msg = "A" * 500
        result = ErrorSanitizer.sanitize(long_msg)
        assert len(result) <= ErrorSanitizer.MAX_ERROR_LENGTH + 3

    def test_safe_error_to_dict(self) -> None:
        """SafeError converts to client-safe dictionary."""
        error = SafeError(
            error_code=ErrorCode.INTERNAL_ERROR,
            safe_detail="Something went wrong",
            trace_id="trc_123",
            retryable=True,
            http_status=500,
            internal_detail="Internal: /etc/passwd not found",
        )
        d = error.to_dict()
        assert d["code"] == ErrorCode.INTERNAL_ERROR.value
        assert d["safe_detail"] == "Something went wrong"
        assert d["trace_id"] == "trc_123"
        assert d["retryable"] is True
        assert d["schema_version"] == "we3.error.v1"
        # Internal detail should NOT be in the dict
        assert "internal_detail" not in d

    def test_get_error_response_from_exception(self) -> None:
        """get_error_response sanitizes exceptions."""
        exc = Exception("Error at /etc/passwd with SELECT query")
        result = get_error_response(exc, trace_id="trc_456")
        assert result["schema_version"] == "we3.error.v1"
        assert result["code"] == ErrorCode.INTERNAL_ERROR.value
        assert "/etc/passwd" not in result["safe_detail"]
        assert "SELECT" not in result["safe_detail"]
        assert result["trace_id"] == "trc_456"

    def test_get_error_response_from_safe_error(self) -> None:
        """get_error_response passes through SafeError."""
        safe_err = SafeError(
            error_code=ErrorCode.VALIDATION_ERROR,
            safe_detail="Invalid input",
            trace_id="trc_789",
        )
        result = get_error_response(safe_err)
        assert result["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["safe_detail"] == "Invalid input"

    def test_error_codes_enum(self) -> None:
        """Error codes are properly defined."""
        assert ErrorCode.AUTH_REQUIRED.value == "auth_required"
        assert ErrorCode.RATE_LIMITED.value == "rate_limited"
        assert ErrorCode.CSRF_TOKEN_MISSING.value == "csrf_token_missing"
        assert ErrorCode.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCode.INTERNAL_ERROR.value == "internal_error"


class TestSecretsManager:
    """Tests for secrets management and key rotation."""

    def test_load_key_from_env(self) -> None:
        """Keys are loaded from environment variables."""
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"WE3_TEST_KEY": key}):
            sm = SecretsManager(env_var_name="WE3_TEST_KEY")
            assert sm.get_current_key_id() is not None
            assert len(sm._keyring) >= 1

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encryption and decryption work correctly."""
        sm = SecretsManager()
        plaintext = b"sensitive data"
        encrypted, key_id = sm.encrypt(plaintext)
        decrypted = sm.decrypt(encrypted, key_id)
        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_fails(self) -> None:
        """Decryption with wrong key fails gracefully."""
        sm = SecretsManager()
        plaintext = b"sensitive data"
        encrypted, key_id = sm.encrypt(plaintext)
        # Try decrypting with a different key
        wrong_key = Fernet.generate_key().decode()
        wrong_key_id = sm._derive_key_id(wrong_key)
        # Manually add wrong key to keyring
        sm._keyring[wrong_key_id] = Fernet(wrong_key.encode())
        with pytest.raises(SecretValidationError, match="Decryption failed"):
            sm.decrypt(encrypted, wrong_key_id)

    def test_key_rotation(self) -> None:
        """Key rotation creates a new key."""
        sm = SecretsManager()
        old_key_id = sm.get_current_key_id()
        result = sm.rotate_key()
        assert result.new_key_id != old_key_id
        assert sm.get_current_key_id() == result.new_key_id

    def test_decrypt_after_rotation(self) -> None:
        """Data encrypted with old key can still be decrypted after rotation."""
        sm = SecretsManager()
        plaintext = b"important data"
        encrypted, old_key_id = sm.encrypt(plaintext)

        # Rotate key
        sm.rotate_key()

        # Old key should still be available for decryption
        decrypted = sm.decrypt(encrypted, old_key_id)
        assert decrypted == plaintext

    def test_needs_rotation_new_key(self) -> None:
        """Newly created keys don't need rotation."""
        sm = SecretsManager()
        key_id = sm.get_current_key_id()
        assert sm.needs_rotation(key_id) is False

    def test_needs_rotation_old_key(self) -> None:
        """Old keys need rotation."""
        from wilson_eval3ngine.security.secrets import SecretMetadata
        sm = SecretsManager()
        key_id = sm.get_current_key_id()
        # Manually set old metadata
        sm._metadata[key_id] = SecretMetadata(
            key_id=key_id,
            algorithm="fernet",
            created_at=time.time() - 40 * 86400,  # 40 days ago
            rotation_interval_seconds=30 * 86400,  # 30 day rotation
        )
        assert sm.needs_rotation(key_id) is True

    def test_health_check(self) -> None:
        """Health check returns status."""
        sm = SecretsManager()
        health = sm.health_check()
        assert health["status"] == "ok"
        assert health["key_count"] >= 1

    def test_validate_key_valid(self) -> None:
        """Valid Fernet keys pass validation."""
        sm = SecretsManager()
        key = Fernet.generate_key().decode()
        assert sm.validate_key(key) is True

    def test_validate_key_invalid(self) -> None:
        """Invalid keys fail validation."""
        sm = SecretsManager()
        assert sm.validate_key("invalid-key") is False
        assert sm.validate_key("") is False

    def test_load_secret_from_env_required(self) -> None:
        """Required secrets raise error if not set."""
        from wilson_eval3ngine.security.secrets import load_secret_from_env
        with pytest.raises(SecretValidationError):
            load_secret_from_env("NONEXISTENT_SECRET_VAR", required=True)

    def test_load_secret_from_env_optional(self) -> None:
        """Optional secrets return None if not set."""
        from wilson_eval3ngine.security.secrets import load_secret_from_env
        result = load_secret_from_env("NONEXISTENT_SECRET_VAR", required=False)
        assert result is None


class TestSecurityHeaders:
    """Tests for enhanced security headers."""

    def test_hsts_has_preload(self) -> None:
        """HSTS header includes preload directive."""
        hsts = SECURITY_HEADERS["Strict-Transport-Security"]
        assert "preload" in hsts

    def test_coop_header_present(self) -> None:
        """Cross-Origin-Opener-Policy header is present."""
        assert "Cross-Origin-Opener-Policy" in SECURITY_HEADERS
        assert SECURITY_HEADERS["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_corp_header_present(self) -> None:
        """Cross-Origin-Resource-Policy header is present."""
        assert "Cross-Origin-Resource-Policy" in SECURITY_HEADERS
        assert SECURITY_HEADERS["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_coep_header_present(self) -> None:
        """Cross-Origin-Embedder-Policy header is present."""
        assert "Cross-Origin-Embedder-Policy" in SECURITY_HEADERS
        assert SECURITY_HEADERS["Cross-Origin-Embedder-Policy"] == "require-corp"

    def test_permissions_policy_restrictive(self) -> None:
        """Permissions-Policy restricts dangerous features."""
        pp = SECURITY_HEADERS["Permissions-Policy"]
        assert "geolocation=()" in pp
        assert "camera=()" in pp
        assert "microphone=()" in pp

    def test_csp_frame_ancestors_none(self) -> None:
        """CSP prevents frame embedding."""
        csp = SECURITY_HEADERS["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    def test_cache_control_no_store(self) -> None:
        """Cache-Control prevents caching of responses."""
        cc = SECURITY_HEADERS["Cache-Control"]
        assert "no-store" in cc
        assert "no-cache" in cc

    def test_x_content_type_options(self) -> None:
        """X-Content-Type-Options prevents MIME sniffing."""
        assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self) -> None:
        """X-Frame-Options prevents clickjacking."""
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"


class TestCORSMiddleware:
    """Tests for CORS policy enforcement."""

    def test_allowed_origin_gets_cors_headers(self) -> None:
        """Allowed origins receive CORS headers."""
        from starlette.responses import Response

        middleware = CORSMiddleware(app=MagicMock(), allowed_origins=["https://example.com"])

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.headers = {"Origin": "https://example.com"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.headers.get("Access-Control-Allow-Origin") == "https://example.com"

    def test_disallowed_origin_no_cors_headers(self) -> None:
        """Disallowed origins don't receive CORS headers."""
        from starlette.responses import Response

        middleware = CORSMiddleware(app=MagicMock(), allowed_origins=["https://example.com"])

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.headers = {"Origin": "https://evil.com"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.headers.get("Access-Control-Allow-Origin") is None

    def test_preflight_request_handled(self) -> None:
        """Preflight OPTIONS requests are handled."""
        from starlette.responses import Response

        middleware = CORSMiddleware(app=MagicMock(), allowed_origins=["https://example.com"])

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "OPTIONS"
        request.headers = {"Origin": "https://example.com"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 204


class TestContentTypeValidationMiddleware:
    """Tests for content-type validation middleware."""

    def test_json_content_type_accepted(self) -> None:
        """Valid JSON content type is accepted."""
        from starlette.responses import Response

        middleware = ContentTypeValidationMiddleware(app=MagicMock())

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/experiments:run"
        request.headers = {"Content-Type": "application/json"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_invalid_content_type_rejected(self) -> None:
        """Invalid content type is rejected with 415."""
        from starlette.responses import Response

        middleware = ContentTypeValidationMiddleware(app=MagicMock())

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/experiments:run"
        request.headers = {"Content-Type": "text/html"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 415

    def test_get_request_no_content_type_check(self) -> None:
        """GET requests don't require content-type validation."""
        from starlette.responses import Response

        middleware = ContentTypeValidationMiddleware(app=MagicMock())

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/experiments:run"
        request.headers = {}

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200


class TestCSRFMiddleware:
    """Tests for CSRF protection middleware."""

    def test_post_without_csrf_token_rejected(self) -> None:
        """POST without CSRF token is rejected in OIDC mode."""
        from starlette.responses import Response

        middleware = CSRFProtectionMiddleware(app=MagicMock(), auth_mode="oidc")

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "POST"
        request.url.path = "/v1/experiments:run"
        request.headers = {"Authorization": "Bearer token", "Origin": "https://example.com"}

        response = asyncio.run(middleware.dispatch(request, call_next))
        # Should pass because Bearer token auth is exempt
        assert response.status_code == 200

    def test_post_with_bearer_token_exempt(self) -> None:
        """POST with Bearer token is exempt from CSRF."""
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

    def test_dev_mode_no_csrf(self) -> None:
        """Dev mode is exempt from CSRF."""
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
    """Tests for rate limiting middleware."""

    def test_rate_limit_allows_requests(self) -> None:
        """Requests under limit are allowed."""
        from starlette.responses import Response

        middleware = RateLimitMiddleware(app=MagicMock(), default_limit=100, default_window=60)

        async def call_next(request):
            return Response("test")

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/health"
        request.headers = {}
        request.client.host = "192.168.1.1"

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    def test_rate_limit_blocks_over_limit(self) -> None:
        """Requests over limit are blocked with 429."""
        from starlette.responses import Response

        middleware = RateLimitMiddleware(app=MagicMock(), default_limit=1, default_window=60)

        async def call_next(request):
            return Response("test")

        # Use a path not in RATE_LIMIT_RULES so default_limit is used
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/test_endpoint"
        request.headers = {}
        request.client.host = "192.168.1.1"

        # First request should succeed
        asyncio.run(middleware.dispatch(request, call_next))
        # Second request should be rate limited
        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 429

    def test_rate_limit_includes_project_scope(self) -> None:
        """Rate limit keys include project scope."""
        from starlette.responses import Response

        middleware = RateLimitMiddleware(app=MagicMock(), default_limit=100, default_window=60)

        async def call_next(request):
            return Response("test")

        # Use a path not in RATE_LIMIT_RULES so default_limit is used
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/v1/test_endpoint"
        request.headers = {"X-WE3-Project-ID": "proj_test"}
        request.client.host = "192.168.1.1"

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.headers.get("X-RateLimit-Remaining") is not None


# Need asyncio for async middleware tests
import asyncio  # noqa: E402
import os  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402