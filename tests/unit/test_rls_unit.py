"""Unit tests for RLS module - covers PostgreSQL-specific code paths.

Tests cover:
- KeyCacheEntry.is_expired and needs_refresh (from oidc module)
- RLSSessionContext with PostgreSQL mode (mocked)
- check_rls_enabled with PostgreSQL mode (mocked)
- RLSSessionContext.clear with PostgreSQL mode
- Error handling paths
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from wilson_eval3ngine.persistence.rls import (
    RLSSessionContext,
    rls_context,
    verify_project_isolation,
    check_rls_enabled,
    get_project_scope_filter,
)
from wilson_eval3ngine.persistence.database import Database, ExperimentRow


class TestKeyCacheEntry:
    """Tests for KeyCacheEntry cache expiry logic (from oidc module)."""

    def test_is_expired_true(self) -> None:
        """Cache entry is expired when current time exceeds expiry."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry

        entry = KeyCacheEntry(keys={}, fetched_at=time.time() - 400)
        assert entry.is_expired() is True

    def test_is_expired_false(self) -> None:
        """Cache entry is not expired when within TTL."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry

        entry = KeyCacheEntry(keys={}, fetched_at=time.time())
        assert entry.is_expired() is False

    def test_needs_refresh_true(self) -> None:
        """Cache entry needs refresh when within buffer of expiry."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry

        entry = KeyCacheEntry(keys={}, fetched_at=time.time() - 275)
        assert entry.needs_refresh() is True

    def test_needs_refresh_false(self) -> None:
        """Cache entry does not need refresh when fresh."""
        from wilson_eval3ngine.security.oidc import KeyCacheEntry

        entry = KeyCacheEntry(keys={}, fetched_at=time.time())
        assert entry.needs_refresh() is False


class TestRLSSessionContextPostgreSQL:
    """Tests for RLS session context with PostgreSQL mode (mocked)."""

    def _make_pg_session(self) -> MagicMock:
        """Create a mock session that reports PostgreSQL."""
        session = MagicMock()
        session.bind = MagicMock()
        session.bind.url = MagicMock()
        session.bind.url.__str__ = MagicMock(return_value="postgresql://user:pass@localhost/db")
        return session

    def test_apply_postgresql_mode(self) -> None:
        """RLS context applies session variables in PostgreSQL mode."""
        session = self._make_pg_session()

        context = RLSSessionContext(session, project_id="proj_test", is_system_admin=False)
        context.apply()

        # Verify SET LOCAL was called for both project_id and admin
        assert session.execute.call_count >= 2
        # Check the SQL contains SET LOCAL
        for call in session.execute.call_args_list:
            args, kwargs = call
            sql = str(args[0]) if args else str(kwargs)
            assert "SET LOCAL" in sql or "we3." in sql

    def test_apply_postgresql_admin_mode(self) -> None:
        """RLS context sets admin=true in PostgreSQL mode."""
        session = self._make_pg_session()

        context = RLSSessionContext(session, project_id="proj_admin", is_system_admin=True)
        context.apply()

        # Verify SET LOCAL was called with admin=true
        for call in session.execute.call_args_list:
            args, kwargs = call
            sql = str(args[0]) if args else str(kwargs)
            params = kwargs if kwargs else (args[1] if len(args) > 1 else {})
            if "is_system_admin" in sql:
                assert params.get("admin") == "true"

    def test_apply_idempotent(self) -> None:
        """Applying context twice is idempotent."""
        session = self._make_pg_session()

        context = RLSSessionContext(session, project_id="proj_test")
        context.apply()
        first_call_count = session.execute.call_count

        context.apply()
        assert session.execute.call_count == first_call_count

    def test_clear_postgresql_mode(self) -> None:
        """Clear resets session variables in PostgreSQL mode."""
        session = self._make_pg_session()

        context = RLSSessionContext(session, project_id="proj_test", is_system_admin=False)
        context.apply()
        call_count_after_apply = session.execute.call_count

        context.clear()

        # Verify additional SET LOCAL calls for clearing
        assert session.execute.call_count > call_count_after_apply

    def test_clear_not_applied(self) -> None:
        """Clear is a no-op when context was not applied."""
        session = self._make_pg_session()

        context = RLSSessionContext(session, project_id="proj_test")
        context.clear()

        assert session.execute.call_count == 0


class TestCheckRLSEnabled:
    """Tests for check_rls_enabled with PostgreSQL mode."""

    def test_check_rls_enabled_postgresql_with_policies(self) -> None:
        """check_rls_enabled returns True when policies exist in PostgreSQL."""
        session = MagicMock()
        session.bind = MagicMock()
        session.bind.url = MagicMock()
        session.bind.url.__str__ = MagicMock(return_value="postgresql://user:pass@localhost/db")

        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=56)
        session.execute = MagicMock(return_value=mock_result)

        result = check_rls_enabled(session)
        assert result is True

    def test_check_rls_enabled_postgresql_no_policies(self) -> None:
        """check_rls_enabled returns False when no policies exist."""
        session = MagicMock()
        session.bind = MagicMock()
        session.bind.url = MagicMock()
        session.bind.url.__str__ = MagicMock(return_value="postgresql://user:pass@localhost/db")

        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        session.execute = MagicMock(return_value=mock_result)

        result = check_rls_enabled(session)
        assert result is False

    def test_check_rls_enabled_sqlite(self) -> None:
        """check_rls_enabled returns False for SQLite."""
        session = MagicMock()
        session.bind = MagicMock()
        session.bind.url = MagicMock()
        session.bind.url.__str__ = MagicMock(return_value="sqlite:///test.db")

        result = check_rls_enabled(session)
        assert result is False


class TestVerifyProjectIsolation:
    """Tests for verify_project_isolation function."""

    def test_verify_project_isolation_sqlite(self, db) -> None:
        """verify_project_isolation works with SQLite (no RLS)."""
        with db.session() as session:
            result = verify_project_isolation(session, "proj_a", "proj_b")
            assert isinstance(result, bool)


class TestGetProjectScopeFilter:
    """Tests for get_project_scope_filter function."""

    def test_get_project_scope_filter(self, db) -> None:
        """get_project_scope_filter returns a valid SQLAlchemy filter."""
        with db.session() as session:
            filter_cond = get_project_scope_filter("proj_test")
            assert filter_cond is not None

            experiments = (
                session.query(ExperimentRow)
                .filter(filter_cond)
                .all()
            )
            assert isinstance(experiments, list)


class TestRLSErrorHandling:
    """Tests for error handling in RLS module."""

    def test_rls_context_exception_clears(self, db) -> None:
        """RLS context is cleared even if an exception occurs."""
        with db.session() as session:
            with pytest.raises(RuntimeError, match="test error"):
                with rls_context(session, project_id="proj_test"):
                    raise RuntimeError("test error")

            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1

    def test_rls_context_rejects_empty_project_id(self, db) -> None:
        """Empty project_id raises ValueError."""
        with db.session() as session:
            with pytest.raises(ValueError, match="project_id must not be empty"):
                with rls_context(session, project_id=""):
                    pass
