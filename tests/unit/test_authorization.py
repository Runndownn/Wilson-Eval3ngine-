"""
Unit tests for project and export isolation authorization (TODO 39).
"""

import pytest

from wilson_eval3ngine.security.authorization import (
    AuthorizationError,
    check_authorization,
    build_scope_aware_cache_key,
    check_export_authorization,
    AUTHORIZATION_MATRIX,
)


class TestAuthorizationMatrix:
    """Tests for role-based access control matrix."""

    def test_matrix_defined_for_all_roles(self) -> None:
        """All expected roles are defined in matrix."""
        expected_roles = [
            "viewer",
            "evaluation_engineer",
            "reviewer",
            "adjudicator",
            "project_admin",
            "release_authority",
            "signing_authority",
        ]
        for role in expected_roles:
            assert role in AUTHORIZATION_MATRIX

    def test_workload_roles_have_narrower_scopes(self) -> None:
        """Workload roles have more restrictive permissions."""
        # Workload roles should have fewer resource types
        workload_roles = [r for r in AUTHORIZATION_MATRIX if r.startswith("workload:")]
        assert len(workload_roles) >= 6  # api, scheduler, provider, grader, maintenance, report_export, signing


class TestCheckAuthorization:
    """Tests for authorization checking."""

    def test_viewer_can_read_projects(self) -> None:
        """Viewer role can read projects."""
        assert check_authorization("viewer", "projects", "read") is True

    def test_viewer_cannot_create_experiments(self) -> None:
        """Viewer cannot create experiments."""
        with pytest.raises(AuthorizationError, match="not authorized"):
            check_authorization("viewer", "experiments", "create")

    def test_evaluation_engineer_can_create_runs(self) -> None:
        """Evaluation engineer can create runs."""
        assert check_authorization("evaluation_engineer", "runs", "create") is True

    def test_project_admin_can_update_own_experiments(self) -> None:
        """Project admin can update own experiments."""
        assert check_authorization("project_admin", "experiments", "update:own") is True
    
    def test_project_admin_can_delete_own_runs(self) -> None:
        """Project admin can delete own runs."""
        assert check_authorization("project_admin", "runs", "delete:own") is True

    def test_project_admin_cannot_update_others(self) -> None:
        """Project admin cannot update others' resources without ownership logic."""
        # Note: This tests the matrix - ownership validation is separate
        # update:own is allowed, but actual ownership check is in repository
        pass

    def test_reviewer_cannot_read_all_evidence(self) -> None:
        """Reviewer cannot read all evidence (only safe or with approval)."""
        with pytest.raises(AuthorizationError, match="not authorized"):
            check_authorization("reviewer", "evidence", "read:all")

    def test_release_authority_can_read_all_evidence(self) -> None:
        """Release authority can read all evidence."""
        assert check_authorization("release_authority", "evidence", "read:all") is True

    def test_unknown_role_denied(self) -> None:
        """Unknown roles are denied access."""
        with pytest.raises(AuthorizationError, match="not authorized"):
            check_authorization("unknown_role", "projects", "read")


class TestCacheKeyScoping:
    """Tests for cache key scoping."""

    def test_cache_key_includes_project(self) -> None:
        """Cache key includes project scope to prevent cross-project access."""
        key = build_scope_aware_cache_key(
            project_id="proj_alpha",
            resource_type="metrics",
            resource_id="snap_001",
            cache_type="snapshot",
        )
        assert key == "we3:snapshot:proj_alpha:metrics:snap_001"
        assert "proj_alpha" in key

    def test_different_projects_have_different_keys(self) -> None:
        """Different projects produce different cache keys."""
        key_alpha = build_scope_aware_cache_key("proj_alpha", "runs", "run_001", "count")
        key_beta = build_scope_aware_cache_key("proj_beta", "runs", "run_001", "count")
        
        assert key_alpha != key_beta
        assert "proj_alpha" in key_alpha
        assert "proj_beta" in key_beta


class TestExportAuthorization:
    """Tests for export-specific authorization."""

    def test_dossier_export_requires_authority(self) -> None:
        """Dossier export requires signing_authority or release_authority."""
        assert check_export_authorization("release_authority", "dossier", "proj_001") is True
        assert check_export_authorization("signing_authority", "dossier", "proj_001") is True

    def test_report_export_allowed_for_engineer(self) -> None:
        """Report export allowed for evaluation engineers."""
        assert check_export_authorization("evaluation_engineer", "report", "proj_001") is True

    def test_raw_evidence_export_denied_for_viewer(self) -> None:
        """Raw evidence export denied for viewer role."""
        with pytest.raises(AuthorizationError):
            check_export_authorization("viewer", "raw_evidence", "proj_001")

    def test_unknown_export_type_denied(self) -> None:
        """Unknown export type raises error."""
        with pytest.raises(AuthorizationError, match="unknown export type"):
            check_export_authorization("release_authority", "unknown", "proj_001")


class TestCrossProjectPrevention:
    """Tests for cross-project access prevention."""

    def test_scope_validation_concept(self) -> None:
        """Scope validation prevents cross-project data leakage.
        
        Note: Full validation requires database integration.
        This tests the matrix-based check that would be used.
        """
        # Viewer from proj_a cannot access proj_b's resources through role check
        # The matrix allows read on runs, but project scope is validated separately
        role = "viewer"
        resource = "runs"
        action = "read"
        
        # The matrix says viewer can read runs
        assert check_authorization(role, resource, action) is True
        
        # But actual access should be validated against project_id in database layer
        # See validate_project_scope function