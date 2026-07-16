"""Production-hardened PostgreSQL session context and RLS utilities.

T3.1.2 - Enforce project keys, row-level security, and database authorization.
Provides fail-closed session context binding with audit trail.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("wilson.security.context")

# Session setting key for project context
PROJECT_CONTEXT_KEY = "we3.project_id"


class ProjectContextError(Exception):
    """Raised when project context cannot be established or is invalid."""
    pass


def bind_project_context(
    session: Session,
    project_id: str,
    actor_id: str,
    *,
    fail_closed: bool = True,
) -> str:
    """Bind project context to database session.

    Args:
        session: SQLAlchemy session to bind context to
        project_id: Verified project identifier to bind
        actor_id: Identity of the caller for audit
        fail_closed: If True, reject operations when context cannot be set

    Returns:
        The project_id that was bound

    Raises:
        ProjectContextError: If context cannot be set and fail_closed=True
    """
    if not project_id or len(project_id) > 160:
        raise ProjectContextError(f"invalid project_id: {project_id!r}")

    try:
        # Set transaction-local context (fail-closed if operation fails)
        session.execute(text(f"SET LOCAL {PROJECT_CONTEXT_KEY} = :pid"), {"pid": project_id})
        # Verify the setting took effect
        result = session.execute(text(f"SELECT current_setting('{PROJECT_CONTEXT_KEY}', true)")).scalar()
        if result is None and fail_closed:
            logger.warning(
                "project_context_validation_failed",
                extra={"actor_id": actor_id, "required_key": PROJECT_CONTEXT_KEY}
            )
            raise ProjectContextError("project context not set - RLS may be bypassed")

        logger.info(
            "project_context_bound",
            extra={
                "project_id": project_id,
                "actor_id": actor_id,
                "fail_closed": fail_closed,
            },
        )
        # Audit event for context binding (defense-in-depth)
        _audit_context_binding(session, project_id, actor_id)
        return project_id
    except ProjectContextError:
        raise
    except Exception as e:
        if fail_closed:
            logger.error("project_context_bind_error", extra={"error": str(e), "actor_id": actor_id})
            raise ProjectContextError(f"failed to bind project context: {e}") from e
        logger.warning("project_context_bind_failed", extra={"error": str(e), "actor_id": actor_id})
        return project_id


def _audit_context_binding(session: Session, project_id: str, actor_id: str) -> None:
    """Internal: Log context binding audit event."""
    # In production, this would write to audit_events table
    # For now, structured log with correlation capability
    logger.info(
        "audit_event",
        extra={
            "event_type": "context_bound",
            "project_id": project_id,
            "actor_id": actor_id,
            "resource": "database_session",
        },
    )


@contextmanager
def project_context(
    session: Session,
    project_id: str,
    actor_id: str,
) -> Iterator[Session]:
    """Context manager for project-scoped database operations.

    Usage:
        with project_context(session, "proj_test", "user_123") as scoped_session:
            repo.create_experiment(scoped_session, ...)

    Args:
        session: SQLAlchemy session
        project_id: Verified project identifier
        actor_id: Caller identity for audit

    Yields:
        The same session with project context bound
    """
    bind_project_context(session, project_id, actor_id)
    try:
        yield session
    finally:
        # Reset is automatic at transaction end with SET LOCAL
        pass


def validate_context_bound(session: Session, actor_id: str) -> bool:
    """Verify that project context is bound in this session.

    Used for defense-in-depth checks before sensitive operations.

    Args:
        session: SQLAlchemy session to check
        actor_id: Caller identity for audit

    Returns:
        True if context is properly bound

    Raises:
        ProjectContextError: If context is not bound
    """
    result = session.execute(text(f"SELECT current_setting('{PROJECT_CONTEXT_KEY}', true)")).scalar()
    if result is None:
        logger.warning(
            "project_context_validation_failed",
            extra={"actor_id": actor_id, "required_key": PROJECT_CONTEXT_KEY}
        )
        raise ProjectContextError(
            "project context not bound - database operation rejected",
        )
    return True


def enforce_rls_on_tables(session: Session) -> None:
    """Verify RLS is enabled on all required tables.

    Should be called during application startup in production.
    """
    rls_check_sql = text("""
        SELECT tablename, rowsecurity
        FROM pg_tables
        WHERE tablename IN ('experiments', 'runs', 'classifications',
                           'metric_snapshots', 'gate_decisions',
                           'audit_events', 'jobs')
        AND rowsecurity = false
    """)
    disabled = session.execute(rls_check_sql).fetchall()
    if disabled:
        table_names = [row[0] for row in disabled]
        raise RuntimeError(f"RLS not enabled on tables: {table_names}")
    logger.info("rls_policy_verified", extra={"tables": 7})


# Role constants for database access
class DatabaseRole:
    """Database role identifiers for RLS enforcement."""
    APPLICATION = "app_user"
    MIGRATION = "migration_owner"
    ADMINISTRATIVE = "administrative"
    READ_ONLY = "readonly"


def assert_application_role(session: Session) -> None:
    """Assert that the current connection is using an application role.

    Prevents accidental use of migration or administrative roles in normal operations.
    """
    role_sql = text("SELECT current_user")
    current_user = session.execute(role_sql).scalar()
    if current_user in (DatabaseRole.MIGRATION, DatabaseRole.ADMINISTRATIVE):
        raise RuntimeError(
            f"connection using privileged role {current_user} - use application role instead"
        )


__all__ = [
    "PROJECT_CONTEXT_KEY",
    "ProjectContextError",
    "bind_project_context",
    "project_context",
    "validate_context_bound",
    "enforce_rls_on_tables",
    "DatabaseRole",
    "assert_application_role",
]