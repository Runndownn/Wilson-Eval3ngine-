from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

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
    """Persist authenticated request intent before endpoint side effects.

    This event proves that the request crossed the authentication boundary; it
    does not claim route-specific authorization succeeded.  If the configured
    authoritative ledger cannot be written, the request is rejected before the
    endpoint runs instead of silently falling back to ordinary logs.
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
    """Create a request-context dependency with application-lifetime state.

    A previous implementation constructed ``OIDCAuthenticator`` for every
    request. That also recreated its in-memory revocation state and omitted the
    configured Redis authority, so revocation could not be relied on through the
    actual API path. This dependency resolves OIDC and audit authorities once
    per FastAPI application/dependency closure and then reuses them.
    """
    resolved_oidc = oidc_authenticator
    resolved_audit = audit_ledger

    def resolve_audit(request: Request) -> AuditLedger | None:
        nonlocal resolved_audit
        if resolved_audit is not None:
            return resolved_audit
        database = getattr(request.app.state, "database", None)
        if database is None:
            return None
        from ..persistence.audit import AuditLedger

        resolved_audit = AuditLedger(database)
        request.app.state.audit_ledger = resolved_audit
        return resolved_audit

    def resolve_oidc() -> OIDCAuthenticator:
        nonlocal resolved_oidc
        if resolved_oidc is not None:
            return resolved_oidc

        from ..security.oidc import OIDCAuthenticator, OIDCSettings

        redis_client = None
        if settings.redis_url:
            try:
                import redis

                redis_client = redis.from_url(settings.redis_url)
                if settings.is_assurance_environment:
                    redis_client.ping()
            except Exception as exc:
                logger.error(
                    "oidc_revocation_backend_unavailable",
                    extra={"error_class": type(exc).__name__},
                )
                if settings.is_assurance_environment:
                    raise RuntimeError(
                        "distributed OIDC revocation authority is unavailable"
                    ) from exc
                redis_client = None
        elif settings.is_assurance_environment:
            raise RuntimeError(
                "distributed OIDC revocation authority is required"
            )

        resolved_oidc = OIDCAuthenticator(
            OIDCSettings(
                issuer=settings.oidc_issuer,
                jwks_uri=settings.oidc_jwks_uri,
                audience=settings.oidc_audience,
            ),
            redis_client=redis_client,
        )
        return resolved_oidc

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
                resolve_audit(request), request=request, context=context
            )
            request.state.we3_context = context
            return context

        if settings.auth_mode == "oidc":
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

                authenticator = resolve_oidc()
                project_id, role = authenticator.authenticate(token)
                # This is the same immutable token that just passed signature,
                # issuer, audience, time, MFA, role/project and revocation
                # validation above.  No caller-controlled replacement occurs
                # between validation and subject extraction.
                actor_id = authenticator.get_token_subject(token)
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
            except RuntimeError as exc:
                logger.error(
                    "oidc_security_authority_unavailable",
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

            context = RequestContext(
                project_id=project_id,
                role=role,
                actor_id=actor_id,
                auth_method="oidc",
            )
            _audit_authenticated_request(
                resolve_audit(request), request=request, context=context
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
