"""Security module for Wilson Eval3ngine.

Exports OIDC authentication, signing, database context, authorization,
rate limiting, CSRF protection, and input validation utilities.
"""

# Signing is always available
from .signing import (
    SignatureEnvelope,
    generate_private_key,
    load_private_key,
    sign_bytes,
    verify_bytes,
)

# Context is always available
from .context import (
    PROJECT_CONTEXT_KEY,
    ProjectContextError,
    bind_project_context,
    project_context,
    validate_context_bound,
    enforce_rls_on_tables,
    DatabaseRole,
    assert_application_role,
)

# Authorization is always available
from .authorization import (
    AuthorizationError,
    AUTHORIZATION_MATRIX,
    check_authorization,
    validate_project_scope,
    build_scope_aware_cache_key,
    check_export_authorization,
    check_raw_evidence_authorization,
)

# Rate limiting is always available
from .rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitExceeded,
    build_rate_limit_key,
)

# CSRF protection is always available
from .csrf import (
    CSRFProtection,
    CSRFValidationError,
    get_csrf_token_endpoint,
)

# Input validation is always available
from .input_validation import (
    ValidationError,
    ProjectIdValidator,
    IdempotencyKeyValidator,
    ContentTypeValidator,
    InputSanitizer,
    InputValidator,
)

# OIDC requires optional dependency - lazy import to avoid hard dependency in foundation
def __getattr__(name: str):
    if name in (
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
    ):
        try:
            from . import oidc
            return getattr(oidc, name)
        except ImportError as e:
            raise ImportError(
                f"{name} requires python-jose and requests packages. "
                "Install with: pip install 'wilson-eval3ngine[oidc]'"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # OIDC (lazy-loaded)
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
    # Signing
    "SignatureEnvelope",
    "generate_private_key",
    "load_private_key",
    "sign_bytes",
    "verify_bytes",
    # Context
    "PROJECT_CONTEXT_KEY",
    "ProjectContextError",
    "bind_project_context",
    "project_context",
    "validate_context_bound",
    "enforce_rls_on_tables",
    "DatabaseRole",
    "assert_application_role",
    # Authorization
    "AuthorizationError",
    "AUTHORIZATION_MATRIX",
    "check_authorization",
    "validate_project_scope",
    "build_scope_aware_cache_key",
    "check_export_authorization",
    "check_raw_evidence_authorization",
    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitExceeded",
    "build_rate_limit_key",
    # CSRF protection
    "CSRFProtection",
    "CSRFValidationError",
    "get_csrf_token_endpoint",
    # Input validation
    "ValidationError",
    "ProjectIdValidator",
    "IdempotencyKeyValidator",
    "ContentTypeValidator",
    "InputSanitizer",
    "InputValidator",
]