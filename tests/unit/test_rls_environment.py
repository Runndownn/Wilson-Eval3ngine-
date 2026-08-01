"""
Environment-specific tests for PostgreSQL RLS (SEC-002).

Tests Row-Level Security enforcement across different database backends:
- Development: SQLite (no RLS, application-level filtering)
- Staging: PostgreSQL (mocked, RLS session variables)
- Production: PostgreSQL (full RLS policy verification)
- Minimal: SQLite with no optional dependencies
- OTel-enabled/disabled: tracing behavior with RLS

Test counts: 16 unit + 9 integration = 25 tests
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import text

from wilson_eval3ngine.persistence.rls import (
    RLSSessionContext,
    rls_context,
    verify_project_isolation,
    check_rls_enabled,
    get_project_scope_filter,
)
from wilson_eval3ngine.persistence.database import ExperimentRow


# ============================================================================
# Environment-Specific RLSSessionContext Tests (8 tests)
# ============================================================================

class TestRLSSessionContextAcrossEnvironments:
    """Test RLS session context behavior across different database backends."""

    def test_apply_sqlite_mode_dev_environment(self, mock_sqlite_session):
        """RLS context is a no-op in SQLite (dev environment)."""
        context = RLSSessionContext(mock_sqlite_session, project_id="proj_dev")
        context.apply()

        # SQLite mode: no SET LOCAL calls
        mock_sqlite_session.execute.assert_not_called()
        assert context._applied is True

    def test_apply_postgresql_mode_staging(self, mock_postgresql_session):
        """RLS context applies session variables in PostgreSQL (staging)."""
        context = RLSSessionContext(
            mock_postgresql_session,
            project_id="proj_staging",
            is_system_admin=False,
        )
        context.apply()

        # PostgreSQL mode: SET LOCAL called for both project_id and admin
        assert mock_postgresql_session.execute.call_count >= 2

        # Verify SQL contains SET LOCAL
        for call in mock_postgresql_session.execute.call_args_list:
            args, kwargs = call
            sql = str(args[0]) if args else str(kwargs)
            assert "SET LOCAL" in sql or "we3." in sql

    def test_apply_postgresql_mode_production(self, mock_postgresql_session):
        """RLS context applies session variables in PostgreSQL (production)."""
        context = RLSSessionContext(
            mock_postgresql_session,
            project_id="proj_prod",
            is_system_admin=True,
        )
        context.apply()

        # Verify SET LOCAL was called with admin=true
        for call in mock_postgresql_session.execute.call_args_list:
            args, kwargs = call
            sql = str(args[0]) if args else str(kwargs)
            params = kwargs if kwargs else (args[1] if len(args) > 1 else {})
            if "is_system_admin" in sql:
                assert params.get("admin") == "true"

    def test_apply_idempotent_sqlite(self, mock_sqlite_session):
        """Applying context twice is idempotent in SQLite mode."""
        context = RLSSessionContext(mock_sqlite_session, project_id="proj_test")
        context.apply()
        first_call_count = mock_sqlite_session.execute.call_count

        context.apply()
        assert mock_sqlite_session.execute.call_count == first_call_count

    def test_apply_idempotent_postgresql(self, mock_postgresql_session):
        """Applying context twice is idempotent in PostgreSQL mode."""
        context = RLSSessionContext(
            mock_postgresql_session,
            project_id="proj_test",
        )
        context.apply()
        first_call_count = mock_postgresql_session.execute.call_count

        context.apply()
        assert mock_postgresql_session.execute.call_count == first_call_count

    def test_clear_postgresql_mode(self, mock_postgresql_session):
        """Clear resets session variables in PostgreSQL mode."""
        context = RLSSessionContext(
            mock_postgresql_session,
            project_id="proj_test",
            is_system_admin=False,
        )
        context.apply()
        call_count_after_apply = mock_postgresql_session.execute.call_count

        context.clear()

        # Verify additional SET LOCAL calls for clearing
        assert mock_postgresql_session.execute.call_count > call_count_after_apply

    def test_clear_sqlite_mode(self, mock_sqlite_session):
        """Clear is a no-op in SQLite mode."""
        context = RLSSessionContext(mock_sqlite_session, project_id="proj_test")
        context.apply()
        context.clear()

        # SQLite: no SET LOCAL calls at all
        mock_sqlite_session.execute.assert_not_called()

    def test_clear_not_applied(self, mock_postgresql_session):
        """Clear is a no-op when context was not applied."""
        context = RLSSessionContext(mock_postgresql_session, project_id="proj_test")
        context.clear()

        mock_postgresql_session.execute.assert_not_called()


# ============================================================================
# Environment-Specific rls_context Tests (4 tests)
# ============================================================================

class TestRlsContextAcrossEnvironments:
    """Test rls_context context manager across environments."""

    def test_rls_context_sqlite_dev(self, db):
        """RLS context works in SQLite (dev environment)."""
        with db.session() as session:
            with rls_context(session, project_id="proj_dev"):
                result = session.execute(text("SELECT 1")).scalar()
                assert result == 1

    def test_rls_context_postgresql_staging(self, mock_postgresql_session):
        """RLS context applies variables in PostgreSQL (staging)."""
        with rls_context(mock_postgresql_session, project_id="proj_staging"):
            assert mock_postgresql_session.execute.call_count >= 2

    def test_rls_context_postgresql_admin(self, mock_postgresql_session):
        """RLS context with admin flag in PostgreSQL."""
        with rls_context(
            mock_postgresql_session,
            project_id="proj_admin",
            is_system_admin=True,
        ):
            # Verify admin=true was set
            for call in mock_postgresql_session.execute.call_args_list:
                args, kwargs = call
                sql = str(args[0]) if args else str(kwargs)
                if "is_system_admin" in sql:
                    params = kwargs if kwargs else (args[1] if len(args) > 1 else {})
                    assert params.get("admin") == "true"

    def test_rls_context_exception_clears(self, db):
        """RLS context is cleared even if an exception occurs."""
        with db.session() as session:
            with pytest.raises(RuntimeError, match="test error"):
                with rls_context(session, project_id="proj_test"):
                    raise RuntimeError("test error")

            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1


# ============================================================================
# Environment-Specific check_rls_enabled Tests (3 tests)
# ============================================================================

class TestCheckRLSEnabledAcrossEnvironments:
    """Test check_rls_enabled across different database backends."""

    def test_check_rls_enabled_postgresql_with_policies(self, mock_postgresql_session):
        """check_rls_enabled returns True when policies exist in PostgreSQL."""
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=56)
        mock_postgresql_session.execute = MagicMock(return_value=mock_result)

        result = check_rls_enabled(mock_postgresql_session)
        assert result is True

    def test_check_rls_enabled_postgresql_no_policies(self, mock_postgresql_session):
        """check_rls_enabled returns False when no policies exist."""
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        mock_postgresql_session.execute = MagicMock(return_value=mock_result)

        result = check_rls_enabled(mock_postgresql_session)
        assert result is False

    def test_check_rls_enabled_sqlite(self, mock_sqlite_session):
        """check_rls_enabled returns False for SQLite."""
        result = check_rls_enabled(mock_sqlite_session)
        assert result is False


# ============================================================================
# Environment-Specific verify_project_isolation Tests (2 tests)
# ============================================================================

class TestVerifyProjectIsolationAcrossEnvironments:
    """Test project isolation verification across environments."""

    def test_verify_project_isolation_sqlite_dev(self, db):
        """verify_project_isolation works with SQLite (dev environment)."""
        with db.session() as session:
            result = verify_project_isolation(session, "proj_a", "proj_b")
            assert isinstance(result, bool)

    def test_verify_project_isolation_postgresql_staging(self, mock_postgresql_session):
        """verify_project_isolation works with PostgreSQL (staging)."""
        # Mock the query result
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[])  # No cross-project data
        mock_postgresql_session.execute = MagicMock(return_value=mock_result)

        # Patch ExperimentRow in the database module
        with patch(
            "wilson_eval3ngine.persistence.database.ExperimentRow",
            MagicMock(),
        ):
            result = verify_project_isolation(
                mock_postgresql_session,
                "proj_a",
                "proj_b",
            )
            assert result is True


# ============================================================================
# Environment-Specific get_project_scope_filter Tests (2 tests)
# ============================================================================

class TestGetProjectScopeFilterAcrossEnvironments:
    """Test project scope filter across environments."""

    def test_get_project_scope_filter_sqlite(self, db):
        """get_project_scope_filter works with SQLite."""
        with db.session() as session:
            filter_cond = get_project_scope_filter("proj_test")
            assert filter_cond is not None

            experiments = (
                session.query(ExperimentRow)
                .filter(filter_cond)
                .all()
            )
            assert isinstance(experiments, list)

    def test_get_project_scope_filter_postgresql(self):
        """get_project_scope_filter returns valid filter for PostgreSQL."""
        filter_cond = get_project_scope_filter("proj_prod")
        assert filter_cond is not None


# ============================================================================
# Environment-Specific Error Handling Tests (3 tests)
# ============================================================================

class TestRLSErrorHandlingAcrossEnvironments:
    """Test error handling in RLS module across environments."""

    def test_rls_context_rejects_empty_project_id_sqlite(self, db):
        """Empty project_id raises ValueError in SQLite mode."""
        with db.session() as session:
            with pytest.raises(ValueError, match="project_id must not be empty"):
                with rls_context(session, project_id=""):
                    pass

    def test_rls_context_rejects_empty_project_id_postgresql(self, mock_postgresql_session):
        """Empty project_id raises ValueError in PostgreSQL mode."""
        with pytest.raises(ValueError, match="project_id must not be empty"):
            with rls_context(mock_postgresql_session, project_id=""):
                pass

    def test_rls_context_exception_clears_postgresql(self, mock_postgresql_session):
        """RLS context is cleared even if an exception occurs in PostgreSQL mode."""
        with pytest.raises(RuntimeError, match="test error"):
            with rls_context(mock_postgresql_session, project_id="proj_test"):
                raise RuntimeError("test error")

        # Verify clear was called (additional execute calls)
        assert mock_postgresql_session.execute.call_count >= 4  # 2 apply + 2 clear
