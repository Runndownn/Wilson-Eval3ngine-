from __future__ import annotations

from dataclasses import dataclass
import logging

from fastapi import Header, HTTPException, status

from ..config import Settings

logger = logging.getLogger("wilson.api.auth")


@dataclass(frozen=True, slots=True)
class RequestContext:
    project_id: str
    role: str
    actor_id: str | None = None  # From OIDC token subject
    auth_method: str = "dev"  # "dev" or "oidc"


_ALLOWED_DEV_ROLES = {
    "viewer",
    "evaluation_engineer",
    "reviewer",
    "adjudicator",
    "project_admin",
    "release_authority",
    "signing_authority",
}


def make_context_dependency(settings: Settings):
    """Create FastAPI dependency for request context extraction.
    
    In production mode (auth_mode="oidc"), validates JWT tokens.
    In development mode (auth_mode="dev"), accepts header-based auth.
    """
    def get_context(
        authorization: str = Header(None),
        x_we3_project_id: str = Header(None),
        x_we3_role: str = Header("viewer"),
    ) -> RequestContext:
        if settings.auth_mode == "dev":
            # Development mode - header-based auth only
            if x_we3_role not in _ALLOWED_DEV_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "role_not_allowed",
                        "retryable": False,
                        "safe_detail": "role is not recognized",
                    },
                )
            logger.warning(
                "dev_auth_used",
                extra={"project_id": x_we3_project_id, "role": x_we3_role},
            )
            return RequestContext(
                project_id=x_we3_project_id or "default_project",
                role=x_we3_role,
                auth_method="dev",
            )
        
        if settings.auth_mode == "oidc":
            # Production OIDW authentication
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "missing_bearer_token",
                        "retryable": False,
                        "safe_detail": "authorization header required",
                    },
                )
            
            # Lazily import to avoid dependency in dev mode
            from ..security.oidc import OIDCAuthenticator, OIDCSettings, TokenValidationError
            
            token = authorization[7:]  # Strip "Bearer " prefix
            
            try:
                oidc_settings = OIDCSettings(
                    issuer=settings.oidc_issuer,
                    jwks_uri=settings.oidc_jwks_uri,
                    audience=settings.oidc_audience,
                )
                authenticator = OIDCAuthenticator(oidc_settings)
                project_id, role = authenticator.authenticate(token)
                # Lazy import to get subject without requiring jose at module load
                try:
                    import jose
                    jwt_header = jose.jwt.get_unverified_header(token)
                    actor_id = jwt_header.get("sub") if jwt_header else None
                except ImportError:
                    actor_id = None
            except ImportError as e:
                logger.error("oidc_dependency_missing", extra={"error": str(e)})
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail={
                        "code": "oidc_not_configured",
                        "retryable": False,
                        "safe_detail": "production OIDC adapter is not installed",
                    },
                )
            except TokenValidationError as e:
                logger.warning("oidc_token_invalid", extra={"error": str(e)})
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "invalid_token",
                        "retryable": False,
                        "safe_detail": "token validation failed",
                    },
                )
            
            return RequestContext(
                project_id=project_id,
                role=role,
                actor_id=actor_id,
                auth_method="oidc",
            )
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "unknown_auth_mode",
                "retryable": False,
                "safe_detail": f"authentication mode not implemented: {settings.auth_mode}",
            },
        )
    
    return get_context
