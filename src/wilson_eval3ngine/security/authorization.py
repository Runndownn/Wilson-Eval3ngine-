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
    pass


# Role × Resource × Action matrix
# This defines what each role can do with each resource type
AUTHORIZATION_MATRIX: dict[str, dict[str, set[str]]] = {
    # Human roles
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
    # Workload roles (narrower scopes)
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
    """Check if a role has authorization for a resource action.
    
    Args:
        role: The role to check (e.g., "viewer", "project_admin")
        resource: The resource type (e.g., "projects", "runs")
        action: The action to authorize (e.g., "read", "create")
        project_id: Optional project scope for validation
        resource_id: Optional resource identifier for ownership check
        
    Returns:
        True if authorized
        
    Raises:
        AuthorizationError: If not authorized
    """
    # Normalize role (handle workload: prefix)
    normalized_role = role.split(":")[-1] if ":" in role else role
    
    # Check matrix
    role_perms = AUTHORIZATION_MATRIX.get(normalized_role, {})
    resource_actions = role_perms.get(resource, set())
    
    # Check if action is directly allowed
    if action in resource_actions:
        return True
    
    # For scoped actions (update:own, read:safe), check scoped variants
    # These are encoded in the matrix as specific strings
    if ":" in action:
        scoped_action = action  # e.g., "update:own"
        
        # Check if any scoped variant matches
        for perm_action in resource_actions:
            if perm_action == scoped_action:
                return True
    
    # For ownership checks: if they can update, they can update:own
    if action == "update:own" and "update:own" in resource_actions:
        return True
    if action == "delete:own" and "delete:own" in resource_actions:
        return True
    
    # Audit denial
    logger.warning(
        "authorization_denied",
        extra={
            "role": role,
            "resource": resource,
            "action": action,
            "project_id": project_id,
        },
    )
    raise AuthorizationError(
        f"role '{role}' not authorized for '{action}' on '{resource}'"
    )


def validate_project_scope(
    session: Session,
    project_id: str,
    resource_id: str,
    resource_type: str,
) -> bool:
    """Validate that a resource belongs to the specified project.
    
    Used for confused-deputy prevention in background workers.
    
    Args:
        session: Database session
        project_id: Expected project ID
        resource_id: Resource identifier to check
        resource_type: Type of resource (runs, experiments, etc.)
        
    Returns:
        True if resource belongs to project
        
    Raises:
        AuthorizationError: If resource doesn't belong to project
    """
    from sqlalchemy import text as sql_text
    
    # Map resource type to table
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
        raise AuthorizationError(f"unknown resource type: {resource_type}")
    
    # Query with project scope
    query = sql_text(f"SELECT project_id FROM {table} WHERE id = :id")
    result = session.execute(query, {"id": resource_id}).scalar()
    
    if result is None:
        raise AuthorizationError(f"resource {resource_id} not found")
    
    if result != project_id:
        logger.warning(
            "project_scope_violation",
            extra={
                "requested_project": project_id,
                "actual_project": result,
                "resource": resource_id,
                "resource_type": resource_type,
            },
        )
        raise AuthorizationError(
            f"resource {resource_id} does not belong to project {project_id}"
        )
    
    return True


def build_scope_aware_cache_key(
    project_id: str,
    resource_type: str,
    resource_id: str,
    cache_type: str,
) -> str:
    """Build a cache key that includes project scope.
    
    Prevents cache key collision between projects.
    
    Args:
        project_id: Project identifier
        resource_type: Type of resource
        resource_id: Resource identifier
        cache_type: Type of cache (metrics, counts, etc.)
        
    Returns:
        Scoped cache key
    """
    return f"we3:{cache_type}:{project_id}:{resource_type}:{resource_id}"


def check_export_authorization(
    role: str,
    export_type: str,
    project_id: str,
) -> bool:
    """Special authorization check for export operations.
    
    Exports require explicit authorization and produce scoped, expiring artifacts.
    
    Args:
        role: Caller's role
        export_type: Type of export (dossier, report, raw_evidence)
        project_id: Source project
        
    Returns:
        True if authorized for export
    """
    export_actions = {
        "dossier": "create:dossier",
        "report": "create",
        "raw_evidence": "read:all",
    }
    
    action = export_actions.get(export_type)
    if not action:
        raise AuthorizationError(f"unknown export type: {export_type}")
    
    return check_authorization(role, "exports", action, project_id=project_id)


def check_raw_evidence_authorization(
    role: str,
    project_id: str,
) -> bool:
    """Special authorization check for raw evidence access.
    
    Raw evidence access requires explicit approval above viewer level.
    """
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