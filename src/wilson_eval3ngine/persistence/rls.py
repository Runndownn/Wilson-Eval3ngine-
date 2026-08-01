"""Row-Level Security (RLS) enforcement for PostgreSQL multi-tenant isolation.

SEC-002: Authorization shall enforce project scope and role at API, database-row,
artifact-prefix, export, and hidden-set boundaries.

This module provides the application-level interface for setting the RLS session
context after OIDC authentication. The actual row-level filtering is enforced by
PostgreSQL policies (see migration 007_rls_policies.py).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("wilson.persistence.rls")


class RLSSessionContext:
    """Manages the PostgreSQL RLS session context.

    After OIDC authentication, the application sets the current project_id and
    system_admin flag in the database session. PostgreSQL RLS policies then
    enforce that all queries only access rows within the specified project scope.

    Usage:
        with rls_context(session, project_id="proj_123"):
            # All queries in this block are scoped to proj_123
            experiments = session.query(ExperimentRow).all()
    """

    # Session variable names (must match migration 007_rls_policies.py)
    PROJECT_ID_VAR = "we3.current_project_id"
    SYSTEM_ADMIN_VAR = "we3.is_system_admin"

    def __init__(self, session: Session, project_id: str, is_system_admin: bool = False):
        self._session = session
        self._project_id = project_id
        self._is_system_admin = is_system_admin
        self._applied = False

    def apply(self) -> None:
        """Apply the RLS context to the current session.

        This sets PostgreSQL session variables that RLS policies use to
        filter queries. Must be called before any data access.

        Note: In SQLite (used for testing), this is a no-op since SQLite
        does not support RLS. The application-level project scope filtering
        is used instead.
        """
        if self._applied:
            return

        # Check if we're using PostgreSQL
        bind = self._session.bind
        db_url = str(getattr(bind, "url", None) or getattr(getattr(bind, "engine", None), "url", None) or "sqlite:///")
        if not db_url.startswith("postgresql"):
            # SQLite mode - skip session variable setting
            # Application-level filtering is used instead
            self._applied = True
            logger.info(
                "rls_context_applied_sqlite",
                extra={
                    "project_id": self._project_id,
                    "is_system_admin": self._is_system_admin,
                    "note": "SQLite mode - application-level filtering only",
                },
            )
            return

        # PostgreSQL mode - set session variables for RLS
        self._session.execute(
            text(f"SET LOCAL {self.PROJECT_ID_VAR} = :project_id"),
            {"project_id": self._project_id},
        )

        admin_value = "true" if self._is_system_admin else "false"
        self._session.execute(
            text(f"SET LOCAL {self.SYSTEM_ADMIN_VAR} = :admin"),
            {"admin": admin_value},
        )

        self._applied = True
        logger.info(
            "rls_context_applied",
            extra={
                "project_id": self._project_id,
                "is_system_admin": self._is_system_admin,
            },
        )

    def clear(self) -> None:
        """Clear the RLS context from the session."""
        if not self._applied:
            return

        bind = self._session.bind
        db_url = str(getattr(bind, "url", None) or getattr(getattr(bind, "engine", None), "url", None) or "sqlite:///")
        if db_url.startswith("postgresql"):
            self._session.execute(text(f"SET LOCAL {self.PROJECT_ID_VAR} = NULL"))
            self._session.execute(text(f"SET LOCAL {self.SYSTEM_ADMIN_VAR} = 'false'"))

        self._applied = False
        logger.info("rls_context_cleared", extra={"project_id": self._project_id})


@contextmanager
def rls_context(
    session: Session,
    project_id: str,
    is_system_admin: bool = False,
) -> Generator[None, None, None]:
    """Context manager for RLS-scoped database operations.

    Args:
        session: SQLAlchemy session
        project_id: The project ID to scope queries to
        is_system_admin: If True, bypass project isolation (for admin operations)

    Example:
        with rls_context(session, project_id="proj_123"):
            experiments = session.query(ExperimentRow).all()
            # Only experiments from proj_123 are returned

    Raises:
        ValueError: If project_id is empty
    """
    if not project_id:
        raise ValueError("project_id must not be empty for RLS context")

    context = RLSSessionContext(session, project_id, is_system_admin)
    try:
        context.apply()
        yield
    finally:
        context.clear()


def verify_project_isolation(
    session: Session,
    project_id: str,
    other_project_id: str,
) -> bool:
    """Verify that project isolation is working correctly.

    This test function checks that data from other_project_id is not
    visible when the RLS context is set to project_id.

    Args:
        session: SQLAlchemy session
        project_id: The project to scope to
        other_project_id: A different project that should not be visible

    Returns:
        True if isolation is working correctly, False otherwise
    """
    from .database import ExperimentRow

    with rls_context(session, project_id):
        # Try to query experiments from another project
        other_experiments = (
            session.query(ExperimentRow)
            .filter(ExperimentRow.project_id == other_project_id)
            .all()
        )

        # Should return empty - isolation is working
        return len(other_experiments) == 0


def get_project_scope_filter(project_id: str) -> Any:
    """Get a SQLAlchemy filter for project-scoped queries.

    This provides an additional application-level filter on top of RLS.
    Use this when you need to ensure project isolation even if RLS is
    not enabled (e.g., in SQLite for testing).

    Args:
        project_id: The project ID to filter by

    Returns:
        A SQLAlchemy filter condition
    """
    from .database import ExperimentRow

    return ExperimentRow.project_id == project_id


def check_rls_enabled(session: Session) -> bool:
    """Check if RLS is enabled on the key tables.

    This is used during startup to verify that the database is properly
    configured for multi-tenant isolation.

    Returns:
        True if RLS is enabled on all project-scoped tables,
        False if not enabled or using SQLite (no RLS support)
    """
    # Check if we're using PostgreSQL
    bind = session.bind
    db_url = str(getattr(bind, "url", None) or getattr(getattr(bind, "engine", None), "url", None) or "sqlite:///")
    if not db_url.startswith("postgresql"):
        # SQLite doesn't support RLS
        return False

    # PostgreSQL: check for RLS policies
    result = session.execute(
        text("""
            SELECT COUNT(*) as policy_count
            FROM pg_policies
            WHERE tablename IN (
                'experiments', 'runs', 'classifications',
                'metric_snapshots', 'gate_decisions', 'audit_events',
                'jobs', 'review_tasks', 'review_assignments',
                'review_submissions', 'adjudications',
                'threshold_sets', 'overrides', 'reviewers'
            )
            AND policyname LIKE 'we3_%'
        """)
    )

    policy_count = result.scalar()
    return policy_count > 0


__all__ = [
    "RLSSessionContext",
    "rls_context",
    "verify_project_isolation",
    "get_project_scope_filter",
    "check_rls_enabled",
]
