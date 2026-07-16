"""Security module for Wilson Eval3ngine.

Exports OIDC authentication, signing, database context, and authorization utilities.
T6.1 - Security & Identity foundation for production-grade platform.
"""

# Signing is always available
from .signing import (
    AuditCheckpoint,
    KeyInventory,
    KeyInventoryRecord,
    KeyPurpose,
    SignatureEnvelope,
    TrustRegistry,
    create_audit_checkpoint,
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

# OIDC requires optional dependency - lazy import to avoid hard dependency in foundation
def __getattr__(name: str):
    if name in (
        "OIDCConfigurationError",
        "TokenValidationError", 
        "OIDCSettings",
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
    "OIDCSettings",
    "JWKSClient",
    "RoleMapping",
    "OIDCAuthenticator",
    "create_oidc_authenticator",
    # Signing
    "SignatureEnvelope",
    "AuditCheckpoint",
    "KeyInventory",
    "KeyInventoryRecord",
    "KeyPurpose",
    "TrustRegistry",
    "create_audit_checkpoint",
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
]