"""Project and export isolation authorization matrix.

The authorization matrix is usable as a pure library primitive, while supported
API composition may install a request-scoped audit callback. That callback runs
synchronously at the allow/deny decision boundary, before a caller can continue
a protected side effect. Audit failure is surfaced separately from ordinary
authorization denial so the HTTP boundary can fail closed with a safe 503.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Callable, Generator

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("wilson.security.authorization")


class AuthorizationError(Exception):
    """Raised when authorization is denied."""


class AuthorizationAuditUnavailable(RuntimeError):
    """Raised when a required authorization decision cannot be audited."""


AuthorizationAuditCallback = Callable[
    [str, str, str, bool, str | None],
    None,
]
_authorization_audit_callback: ContextVar[AuthorizationAuditCallback | None] = ContextVar(
    "we3_authorization_audit_callback",
    default=None,
)


@contextmanager
def authorization_audit_scope(
    callback: AuthorizationAuditCallback,
) -> Generator[None, None, None]:
    """Install an authorization-audit callback for the current request context."""
    token = _authorization_audit_callback.set(callback)
    try:
        yield
    finally:
        _authorization_audit_callback.reset(token)


def _audit_decision(
    role: str,
    resource: str,
    action: str,
    allowed: bool,
    project_id: str | None,
) -> None:
    callback = _authorization_audit_callback.get()
    if callback is None:
        return
    try:
        callback(role, resource, action, allowed, project_id)
    except AuthorizationAuditUnavailable:
        raise
    except Exception as exc:
        raise AuthorizationAuditUnavailable(
            "authorization decision audit is unavailable"
        ) from exc


# Role × Resource × Action matrix. Exact role names are part of the security
# identity. API route action names must also exist here; otherwise a protected
# route can become permanently unreachable or grow an unsafe fallback path.
AUTHORIZATION_MATRIX: dict[str, dict[str, set[str]]] = {
    "viewer": {
        "projects": {"read"},
        "experiments": {"read"},
        "runs": {"read"},
        "evidence": {"read:processed"},
        "reviews": {"read"},
        "metrics": {"read"},
        "exports": {"create"},
    },
    "evaluation_engineer": {
        "projects": {"read"},
        "experiments": {"read", "create", "start", "update:own", "regrade"},
        "runs": {"read", "create", "update:own"},
        "evidence": {"read", "create:processed"},
        "reviews": {"read", "create:flags"},
        "metrics": {"read", "create"},
        "exports": {"create"},
    },
    "reviewer": {
        "projects": {"read"},
        "experiments": {"read"},
        "runs": {"read:safe_cases"},
        "evidence": {"read:safe", "read:reveal_with_approval"},
        "reviews": {"read", "create:submissions"},
        "metrics": {"read"},
        "exports": {"create"},
    },
    "adjudicator": {
        "projects": {"read"},
        "experiments": {"read"},
        "runs": {"read:safe_cases"},
        "evidence": {"read:safe", "read:reveal_with_approval"},
        "reviews": {"read", "create:submissions"},
        "metrics": {"read"},
        "exports": {"create"},
    },
    "project_admin": {
        "projects": {"read", "update"},
        "experiments": {"read", "create", "start", "update:own", "regrade"},
        "runs": {"read", "create", "update:own", "delete:own"},
        "evidence": {"read", "create"},
        "reviews": {"read", "update:assignments"},
        "metrics": {"read", "create"},
        "exports": {"create"},
    },
    "release_authority": {
        "projects": {"read"},
        "experiments": {"read"},
        "runs": {"read"},
        "evidence": {"read:all"},
        "reviews": {"read"},
        "metrics": {"read"},
        "exports": {"create:dossier"},
    },
    "signing_authority": {
        "projects": {"read"},
        "experiments": {"read"},
        "runs": {"read"},
        "evidence": {"read:signed_only"},
        "reviews": {"read"},
        "metrics": {"read"},
        "exports": {"create:dossier", "sign"},
    },
    "workload:api": {
        "jobs": {"create", "read:own", "update:own"},
        "projects": {"read"},
        "evidence": {"read:processed"},
    },
    "workload:scheduler": {
        "jobs": {"read", "update", "delete"},
        "experiments": {"read"},
    },
    "workload:provider": {
        "runs": {"read", "update"},
        "evidence": {"read:processed", "create:response"},
    },
    "workload:grader": {
        "runs": {"read"},
        "evidence": {"read:processed", "create:classification"},
    },
    "workload:maintenance": {
        "jobs": {"read", "update"},
        "projects": {"read"},
    },
    "workload:report_export": {
        "metrics": {"read"},
        "experiments": {"read"},
        "runs": {"read"},
        "exports": {"create"},
    },
    "workload:signing": {
        "evidence": {"read:signed"},
        "exports": {"read:dossier", "sign"},
    },
}


def check_authorization(
    role: str,
    resource: str,
    action: str,
    *,
    project_id: str | None = None,
    resource_id: str | None = None,
) -> bool:
    """Check whether the exact canonical role grants a resource action."""
    del resource_id
    role_perms = AUTHORIZATION_MATRIX.get(role, {})
    resource_actions = role_perms.get(resource, set())

    if action in resource_actions:
        _audit_decision(role, resource, action, True, project_id)
        return True

    _audit_decision(role, resource, action, False, project_id)
    logger.warning(
        "authorization_denied",
        extra={
            "role": role,
            "resource": resource,
            "action": action,
            "project_id": project_id,
        },
    )
    raise AuthorizationError("authorization denied")


def validate_project_scope(
    session: Session,
    project_id: str,
    resource_id: str,
    resource_type: str,
) -> bool:
    """Validate that a resource belongs to the specified project."""
    from sqlalchemy import text as sql_text

    table_map = {
        "experiments": "experiments",
        "runs": "runs",
        "classifications": "classifications",
        "metric_snapshots": "metric_snapshots",
        "gate_decisions": "gate_decisions",
        "review_tasks": "review_tasks",
    }
    table = table_map.get(resource_type)
    if not table:
        raise AuthorizationError("unknown resource type")

    result = session.execute(
        sql_text(f"SELECT project_id FROM {table} WHERE id = :id"),
        {"id": resource_id},
    ).scalar()
    if result is None:
        raise AuthorizationError("resource not found")
    if result != project_id:
        logger.warning(
            "project_scope_violation",
            extra={
                "requested_project": project_id,
                "actual_project": result,
                "resource_type": resource_type,
            },
        )
        raise AuthorizationError("resource is outside the authorized project")
    return True


def build_scope_aware_cache_key(
    project_id: str,
    resource_type: str,
    resource_id: str,
    cache_type: str,
) -> str:
    """Build a project-scoped cache key for validated internal identifiers."""
    return f"we3:{cache_type}:{project_id}:{resource_type}:{resource_id}"


def check_export_authorization(
    role: str,
    export_type: str,
    project_id: str,
) -> bool:
    """Apply the dedicated export authorization mapping."""
    export_actions = {
        "dossier": "create:dossier",
        "report": "create",
        "raw_evidence": "read:all",
    }
    action = export_actions.get(export_type)
    if not action:
        raise AuthorizationError("unknown export type")
    return check_authorization(role, "exports", action, project_id=project_id)


def check_raw_evidence_authorization(
    role: str,
    project_id: str,
) -> bool:
    """Require an explicit raw-evidence permission."""
    return check_authorization(role, "evidence", "read:all", project_id=project_id)


__all__ = [
    "AuthorizationAuditCallback",
    "AuthorizationAuditUnavailable",
    "AuthorizationError",
    "AUTHORIZATION_MATRIX",
    "authorization_audit_scope",
    "check_authorization",
    "validate_project_scope",
    "build_scope_aware_cache_key",
    "check_export_authorization",
    "check_raw_evidence_authorization",
]
