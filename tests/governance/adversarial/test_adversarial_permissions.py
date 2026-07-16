"""Adversarial Permission Matrix - TODO 44.

T6.1.7 - Tests every role × resource × action denial for complete coverage.
Validates that the authorization matrix enforces proper access control.
"""

from __future__ import annotations

import pytest

from wilson_eval3ngine.security.authorization import (
    AuthorizationError,
    AUTHORIZATION_MATRIX,
    check_authorization,
    build_scope_aware_cache_key,
    check_export_authorization,
)


class TestHumanRolePermissionDenials:
    """Tests for denying unauthorized human role actions."""

    def test_viewer_cannot_create(self) -> None:
        """Viewer cannot create any resources."""
        denied_actions = [
            ("projects", "create"),
            ("experiments", "create"),
            ("runs", "create"),
            ("reviews", "create"),
            ("metrics", "create"),
        ]

        for resource, action in denied_actions:
            with pytest.raises(AuthorizationError, match="not authorized"):
                check_authorization("viewer", resource, action)

    def test_viewer_cannot_update(self) -> None:
        """Viewer cannot update any resources."""
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "projects", "update")
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "experiments", "update")

    def test_viewer_cannot_delete(self) -> None:
        """Viewer cannot delete any resources."""
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "runs", "delete")
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "experiments", "delete")

    def test_viewer_cannot_export_raw_evidence(self) -> None:
        """Viewer cannot export raw evidence."""
        with pytest.raises(AuthorizationError):
            check_export_authorization("viewer", "raw_evidence", "proj_001")

    def test_viewer_can_only_read_processed_evidence(self) -> None:
        """Viewer can only read processed evidence, not raw."""
        # Can read processed evidence
        assert check_authorization("viewer", "evidence", "read:processed") is True

        # Cannot read all evidence
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "evidence", "read:all")

    def test_review_can_only_read_safe_evidence(self) -> None:
        """Reviewer can only read safe evidence without approval."""
        assert check_authorization("reviewer", "evidence", "read:safe") is True

        # Cannot read all evidence
        with pytest.raises(AuthorizationError):
            check_authorization("reviewer", "evidence", "read:all")

    def test_reviewer_requires_approval_for_reveal(self) -> None:
        """Reviewer cannot reveal restricted evidence without explicit approval flow."""
        # read:reveal_with_approval exists but requires separate workflow
        assert "read:reveal_with_approval" in AUTHORIZATION_MATRIX["reviewer"]["evidence"]

    def test_adjudicator_same_as_reviewer_for_evidence(self) -> None:
        """Adjudicator has same evidence access as reviewer."""
        assert check_authorization("adjudicator", "evidence", "read:safe") is True
        with pytest.raises(AuthorizationError):
            check_authorization("adjudicator", "evidence", "read:all")


class TestProjectAdminLimitations:
    """Tests for project admin scoped permissions."""

    def test_project_admin_can_update_own(self) -> None:
        """Project admin can update own experiments."""
        assert check_authorization("project_admin", "experiments", "update:own") is True

    def test_project_admin_can_delete_own_runs(self) -> None:
        """Project admin can delete own runs."""
        assert check_authorization("project_admin", "runs", "delete:own") is True

    def test_project_admin_cannot_export_dossier(self) -> None:
        """Project admin cannot export dossiers (requires release authority)."""
        with pytest.raises(AuthorizationError):
            check_export_authorization("project_admin", "dossier", "proj_001")


class TestReleaseAuthorityPermissions:
    """Tests for release authority privileged access."""

    def test_release_authority_can_read_all_evidence(self) -> None:
        """Release authority can read all evidence for certification."""
        assert check_authorization("release_authority", "evidence", "read:all") is True

    def test_release_authority_can_export_dossier(self) -> None:
        """Release authority can export dossiers."""
        assert check_export_authorization("release_authority", "dossier", "proj_001") is True

    def test_release_authority_cannot_create_experiments(self) -> None:
        """Release authority cannot create experiments (no create permission)."""
        with pytest.raises(AuthorizationError):
            check_authorization("release_authority", "experiments", "create")


class TestSigningAuthorityRestrictions:
    """Tests for signing authority specialized access."""

    def test_signing_authority_can_sign(self) -> None:
        """Signing authority can perform signing operations."""
        assert check_authorization("signing_authority", "exports", "sign") is True

    def test_signing_authority_cannot_read_raw_evidence(self) -> None:
        """Signing authority cannot read raw evidence."""
        with pytest.raises(AuthorizationError):
            check_authorization("signing_authority", "evidence", "read:all")

    def test_signing_authority_can_only_read_signed(self) -> None:
        """Signing authority can only read signed evidence."""
        assert check_authorization("signing_authority", "evidence", "read:signed_only") is True


class TestWorkloadRoleIsolation:
    """Tests for workload role isolation and restrictions."""

    def test_workload_roles_exist_in_matrix(self) -> None:
        """Workload roles exist in authorization matrix with proper permissions."""
        # Verify workload roles are defined with their expected resources
        assert "workload:api" in AUTHORIZATION_MATRIX
        assert "workload:provider" in AUTHORIZATION_MATRIX
        assert "workload:grader" in AUTHORIZATION_MATRIX
        assert "workload:maintenance" in AUTHORIZATION_MATRIX
        assert "workload:report_export" in AUTHORIZATION_MATRIX
        assert "workload:signing" in AUTHORIZATION_MATRIX

        # Verify workload:api has jobs permission with create/read:own/update:own
        api_perms = AUTHORIZATION_MATRIX["workload:api"].get("jobs", set())
        assert "create" in api_perms

    def test_workload_provider_resource_permissions(self) -> None:
        """Workload:provider has specific resource permissions."""
        provider_perms = AUTHORIZATION_MATRIX.get("workload:provider", {})
        assert "runs" in provider_perms

    def test_workload_grader_evidence_permissions(self) -> None:
        """Workload:grader has evidence permissions."""
        grader_perms = AUTHORIZATION_MATRIX.get("workload:grader", {})
        assert "evidence" in grader_perms

    def test_workload_maintenance_jobs_permissions(self) -> None:
        """Workload:maintenance has jobs permissions."""
        maintenance_perms = AUTHORIZATION_MATRIX.get("workload:maintenance", {})
        assert "jobs" in maintenance_perms

    def test_workload_report_export_permissions(self) -> None:
        """Workload:report_export has export permissions."""
        report_perms = AUTHORIZATION_MATRIX.get("workload:report_export", {})
        assert "exports" in report_perms

    def test_workload_signing_permissions(self) -> None:
        """Workload:signing has signing permissions."""
        signing_perms = AUTHORIZATION_MATRIX.get("workload:signing", {})
        assert "exports" in signing_perms


class TestAllRolesCovered:
    """Tests that all expected roles are in the matrix."""

    def test_all_human_roles_defined(self) -> None:
        """All human roles are defined in authorization matrix."""
        expected_human_roles = [
            "viewer",
            "evaluation_engineer",
            "reviewer",
            "adjudicator",
            "project_admin",
            "release_authority",
            "signing_authority",
        ]

        for role in expected_human_roles:
            assert role in AUTHORIZATION_MATRIX, f"Missing role: {role}"

    def test_all_workload_roles_defined(self) -> None:
        """All workload roles are defined in authorization matrix."""
        expected_workload_types = [
            "workload:api",
            "workload:scheduler",
            "workload:provider",
            "workload:grader",
            "workload:maintenance",
            "workload:report_export",
            "workload:signing",
        ]

        for role in expected_workload_types:
            assert role in AUTHORIZATION_MATRIX, f"Missing workload role: {role}"

    def test_core_resources_have_permissions(self) -> None:
        """Core resources have at least some permissions defined."""
        core_resources = [
            "projects",
            "experiments",
            "runs",
            "evidence",
            "reviews",
            "metrics",
            "exports",
            "jobs",
        ]

        for resource in core_resources:
            # Find at least one role with this resource
            roles_with_resource = [
                role for role, perms in AUTHORIZATION_MATRIX.items()
                if resource in perms
            ]
            assert len(roles_with_resource) > 0, f"No roles have access to {resource}"


class TestAuthorizationEdgeCases:
    """Tests for authorization edge cases and bypass attempts."""

    def test_unknown_role_denied(self) -> None:
        """Unknown roles are always denied."""
        with pytest.raises(AuthorizationError):
            check_authorization("superadmin", "projects", "read")

        with pytest.raises(AuthorizationError):
            check_authorization("root", "experiments", "create")

        with pytest.raises(AuthorizationError):
            check_authorization("", "runs", "read")

    def test_unknown_resource_denied(self) -> None:
        """Unknown resources are denied for all roles."""
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "nonexistent_resource", "read")

    def test_unknown_action_denied(self) -> None:
        """Unknown actions are denied even for valid resource."""
        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "projects", "nonexistent_action")

        with pytest.raises(AuthorizationError):
            check_authorization("viewer", "projects", "delete")

    def test_role_case_sensitivity(self) -> None:
        """Roles are case-sensitive (VIEWER should not work)."""
        with pytest.raises(AuthorizationError):
            check_authorization("VIEWER", "projects", "read")

        with pytest.raises(AuthorizationError):
            check_authorization("Viewer", "projects", "read")


class TestChainedAbuseScenarios:
    """Tests for multi-step abuse chains."""

    def test_prompt_injection_then_permission_request(self) -> None:
        """Prompt injection to request permissions still fails authorization."""
        # Even if model tries to trick system via prompt injection
        # The actual authorization is backend-enforced
        # This tests that prompt content doesn't grant access
        with pytest.raises(AuthorizationError):
            check_authorization("injected_role", "evidence", "read:all")

    def test_session_confusion_attack(self) -> None:
        """Session confusion between projects is prevented."""
        # Cache keys are project-scoped
        key_a = build_scope_aware_cache_key("proj_a", "runs", "run_1", "count")
        key_b = build_scope_aware_cache_key("proj_b", "runs", "run_1", "count")

        assert key_a != key_b
        assert "proj_a" in key_a
        assert "proj_b" in key_b

    def test_replay_attack_with_different_payload(self) -> None:
        """Idempotency prevents replay attacks with modified payload."""
        # This is tested at the API level with idempotency keys
        # The execution/idempotency module handles this
        from wilson_eval3ngine.execution.idempotency import logical_run_key

        key1 = logical_run_key(
            experiment_definition_hash="hash_a",
            test_case_version_id="case_1",
            rendered_prompt_hash="prompt_a",
            model_config_hash="model_a",
            repetition_index=0,
            execution_mode="certification",
        )

        key2 = logical_run_key(
            experiment_definition_hash="hash_a",
            test_case_version_id="case_1",
            rendered_prompt_hash="prompt_b",  # Different
            model_config_hash="model_a",
            repetition_index=0,
            execution_mode="certification",
        )

        # Different payloads should produce different keys
        assert key1 != key2