"""Project and export isolation authorization matrix.

T6.1.2 - Enforce end-to-end project and export isolation.
Provides role-based access control and scope validation for all boundaries.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("wilson.security.authorization")


class AuthorizationError(Exception):
    """Raised when authorization is denied."""


# Role × Resource × Action matrix. Role names are canonical identities; in
# particular, workload prefixes are security-significant and must not be
# stripped before lookup.
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
        "experiments": {"read", "create", "update:own"},
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
        "experiments": {"read", "create", "update:own"},
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
    # Workload roles are intentionally narrower and retain their workload:
    # namespace to prevent accidental equivalence with a human role.
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
    """Check whether the exact canonical role grants a resource action.

    Workload role prefixes are part of the authorization identity. Unknown roles,
    including identities that merely share a suffix with a known workload role,
    fail closed.
    """
    del resource_id
    role_perms = AUTHORIZATION_MATRIX.get(role, {})
    resource_actions = role_perms.get(resource, set())

    if action in resource_actions:
        return True

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
    """Validate that a resource belongs to the specified project.

    The table identifier is selected exclusively from a closed mapping before it
    is interpolated into SQL; all data values remain bound parameters.
    """
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

    query = sql_text(f"SELECT project_id FROM {table} WHERE id = :id")
    result = session.execute(query, {"id": resource_id}).scalar()

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
    "AuthorizationError",
    "AUTHORIZATION_MATRIX",
    "check_authorization",
    "validate_project_scope",
    "build_scope_aware_cache_key",
    "check_export_authorization",
    "check_raw_evidence_authorization",
]
