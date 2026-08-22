from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from fastapi import Header, HTTPException, Request, status

from ..config import Settings
from ..security.input_validation import ProjectIdValidator, ValidationError

if TYPE_CHECKING:
    from ..persistence.audit import AuditLedger
    from ..security.oidc import OIDCAuthenticator

logger = logging.getLogger("wilson.api.auth")


@dataclass(frozen=True, slots=True)
class RequestContext:
    project_id: str
    role: str
    actor_id: str | None = None
    auth_method: str = "dev"


_ALLOWED_DEV_ROLES = {
    "viewer",
    "evaluation_engineer",
    "reviewer",
    "adjudicator",
    "project_admin",
    "release_authority",
}


def _audit_authenticated_request(
    audit_ledger: AuditLedger | None,
    *,
    request: Request,
    context: RequestContext,
) -> None:
    """Persist the authenticated request boundary before endpoint side effects.

    This is deliberately an authentication/audit event, not a statement that
    route-specific authorization succeeded. Endpoint authorization remains the
    responsibility of the route/service policy. A configured ledger failure is
    surfaced to the caller so a state-changing request cannot continue while
    the authoritative API audit trail is unavailable.
    """
    if audit_ledger is None:
        return

    actor_id = context.actor_id or f"{context.auth_method}:{context.role}"
    try:
        audit_ledger.append(
            project_id=context.project_id,
            event_type="api_request_authenticated",
            aggregate_type="api_route",
            aggregate_id=request.url.path,
            actor_id=actor_id,
            payload={
                "method": request.method,
                "auth_method": context.auth_method,
                "role": context.role,
            },
        )
    except Exception as exc:
        logger.error(
            "api_audit_persistence_failed",
            extra={"error_class": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "audit_unavailable",
                "retryable": True,
                "safe_detail": "security audit persistence is unavailable",
                "schema_version": "we3.error.v1",
            },
        ) from exc


def make_context_dependency(
    settings: Settings,
    *,
    oidc_authenticator: OIDCAuthenticator | None = None,
    audit_ledger: AuditLedger | None = None,
):
    """Create the request-context dependency using long-lived security state.

    Production OIDC composition must inject one authenticator for the lifetime
    of the application. That preserves JWKS cache and revocation state across
    requests and allows the authenticator to share the authoritative Redis
    backend used by the deployment. Development mode remains header based but
    validates the project identifier before it becomes security context.
    """

    def get_context(
        request: Request,
        authorization: str | None = Header(None),
        x_we3_project_id: str | None = Header(None),
        x_we3_role: str = Header("viewer"),
    ) -> RequestContext:
        if settings.auth_mode == "dev":
            if x_we3_role not in _ALLOWED_DEV_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "role_not_allowed",
                        "retryable": False,
                        "safe_detail": "role is not recognized",
                        "schema_version": "we3.error.v1",
                    },
                )
            try:
                project_id = ProjectIdValidator.validate(
                    x_we3_project_id or "default_project"
                )
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "invalid_project_id",
                        "retryable": False,
                        "safe_detail": "project identifier is invalid",
                        "schema_version": "we3.error.v1",
                    },
                ) from exc

            context = RequestContext(
                project_id=project_id,
                role=x_we3_role,
                actor_id=f"dev:{x_we3_role}",
                auth_method="dev",
            )
            logger.warning(
                "dev_auth_used",
                extra={"project_id": project_id, "role": x_we3_role},
            )
            _audit_authenticated_request(
                audit_ledger,
                request=request,
                context=context,
            )
            request.state.we3_context = context
            return context

        if settings.auth_mode == "oidc":
            if oidc_authenticator is None:
                logger.error("oidc_authenticator_missing_from_application_composition")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "oidc_unavailable",
                        "retryable": True,
                        "safe_detail": "authentication service is unavailable",
                        "schema_version": "we3.error.v1",
                    },
                )
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "missing_bearer_token",
                        "retryable": False,
                        "safe_detail": "authorization header required",
                        "schema_version": "we3.error.v1",
                    },
                )

            token = authorization[7:]
            if not token or len(token) > 16_384:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "invalid_token",
                        "retryable": False,
                        "safe_detail": "token validation failed",
                        "schema_version": "we3.error.v1",
                    },
                )

            try:
                from ..security.oidc import (
                    TokenRevocationError,
                    TokenValidationError,
                )

                project_id, role = oidc_authenticator.authenticate(token)
                actor_id = oidc_authenticator.get_token_subject(token)
                project_id = ProjectIdValidator.validate(project_id)
            except ImportError as exc:
                logger.error(
                    "oidc_dependency_missing",
                    extra={"error_class": type(exc).__name__},
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "oidc_unavailable",
                        "retryable": True,
                        "safe_detail": "authentication service is unavailable",
                        "schema_version": "we3.error.v1",
                    },
                ) from exc
            except TokenRevocationError as exc:
                logger.warning("oidc_token_revoked")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "token_revoked",
                        "retryable": False,
                        "safe_detail": "token is no longer valid",
                        "schema_version": "we3.error.v1",
                    },
                ) from exc
            except (TokenValidationError, ValidationError) as exc:
                logger.warning(
                    "oidc_token_invalid",
                    extra={"error_class": type(exc).__name__},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "invalid_token",
                        "retryable": False,
                        "safe_detail": "token validation failed",
                        "schema_version": "we3.error.v1",
                    },
                ) from exc

            context = RequestContext(
                project_id=project_id,
                role=role,
                actor_id=actor_id,
                auth_method="oidc",
            )
            _audit_authenticated_request(
                audit_ledger,
                request=request,
                context=context,
            )
            request.state.we3_context = context
            return context

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "unknown_auth_mode",
                "retryable": False,
                "safe_detail": "authentication mode is not supported",
                "schema_version": "we3.error.v1",
            },
        )

    return get_context


__all__ = ["RequestContext", "make_context_dependency"]
