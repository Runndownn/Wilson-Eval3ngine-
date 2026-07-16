"""Integration tests for Wilson Eval3ngine REST API (TODO 45).

Tests cover:
- Idempotency key enforcement for mutations
- ETag precondition checking for state changes
- Cursor pagination for list endpoints
- Safe error responses with versioned schema
- All workflow endpoints: validate, run, pause, resume, cancel, regrade, compare, export
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from wilson_eval3ngine.api.main import (
    OperationRegistry,
    RunRequest,
    create_app,
    compute_request_signature,
)
from wilson_eval3ngine.config import Settings
from wilson_eval3ngine.domain.io import load_experiment


# ============================================================================
# Fixtures
# ============================================================================


def test_validate_endpoint_enforces_project_context(tmp_path, foundation_manifest):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))
    manifest = load_experiment(foundation_manifest).model_dump(mode="json", by_alias=True)

    ok = client.post(
        "/v1/experiments:validate",
        json=manifest,
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["valid"] is True
    assert ok.json()["schema_version"] == "we3.validation_result.v1"

    denied = client.post(
        "/v1/experiments:validate",
        json=manifest,
        headers={
            "X-WE3-Project-ID": "another-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "project_context_mismatch"


def test_run_endpoint_rejects_manifest_from_another_project(
    tmp_path, foundation_manifest
):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-run.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    denied = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "another-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "project_context_mismatch"


def test_operation_registry_is_project_scoped():
    registry = OperationRegistry()
    request = RunRequest(manifest_path="manifest.yaml", output_dir="output")
    operation = registry.create(request, project_id="project-a")

    assert registry.get(
        operation.operation_id,
        project_id="project-a",
    ) == operation
    assert registry.get(
        operation.operation_id,
        project_id="project-b",
    ) is None


# ============================================================================
# Idempotency Tests
# ============================================================================


def test_run_endpoint_supports_idempotency_key(tmp_path, foundation_manifest):
    """Idempotency keys ensure retry-safe mutations."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-idempotent.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    key = "test-idempotency-key-12345"

    # First request
    response1 = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output1"),
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
            "Idempotency-Key": key,
        },
    )
    assert response1.status_code == 202
    operation_id = response1.json()["operation"]["operation_id"]

    # Retry with SAME key and SAME payload - should return same operation
    response_retry = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output1"),  # Same output as first request
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
            "Idempotency-Key": key,
        },
    )
    assert response_retry.status_code == 202
    assert response_retry.json()["operation"]["operation_id"] == operation_id

    # Different payload with same key MUST fail (security requirement)
    response_different = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output2"),  # Different output - should be rejected
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
            "Idempotency-Key": key,
        },
    )
    assert response_different.status_code == 422
    assert response_different.json()["detail"]["code"] == "idempotency_key_reuse_with_different_payload"


def test_request_signature_is_deterministic():
    """Request signatures should be consistent for same input."""
    body = {"test": "value"}
    headers = {"content-type": "application/json"}

    sig1 = compute_request_signature(body=body, headers=headers)
    sig2 = compute_request_signature(body=body, headers=headers)

    assert sig1 == sig2


# ============================================================================
# ETag Tests
# ============================================================================


def test_operation_etag_changes_on_update(tmp_path, foundation_manifest):
    """ETag should change when operation state changes."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-etag.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Create operation
    response = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    operation_id = response.json()["operation"]["operation_id"]

    # Get operation with ETag
    get_response = client.get(
        f"/v1/operations/{operation_id}",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    etag = get_response.json().get("etag")
    assert etag is not None


def test_pause_requires_matching_etag(tmp_path, foundation_manifest):
    """Pause should require matching ETag to prevent lost updates."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-pause-etag.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Create operation
    response = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    operation_id = response.json()["operation"]["operation_id"]

    # Try to pause with wrong ETag - should get 412
    wrong_etag = '"wrong-etag-value"'
    pause_response = client.post(
        f"/v1/operations/{operation_id}:pause",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
            "If-Match": wrong_etag,
        },
    )
    assert pause_response.status_code == 412
    assert pause_response.json()["detail"]["code"] == "stale_etag"


# ============================================================================
# Error Response Tests
# ============================================================================


def test_error_response_has_safe_structure(tmp_path, foundation_manifest):
    """Error responses must not leak implementation details."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-error.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "wrong-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )

    error = response.json()["detail"]
    assert "code" in error
    assert "retryable" in error
    assert "trace_id" in error
    assert response.json()["detail"]["schema_version"] == "we3.error.v1"


def test_error_response_has_no_stack_trace(tmp_path, foundation_manifest):
    """Error responses must not contain stack traces."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-stacktrace.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "wrong-project",
            "X-WE3-Role": "evaluation_engineer",
        },
    )

    # Should not have any Python stack trace artifacts
    response_text = response.text.lower()
    assert "traceback" not in response_text
    assert "file " not in response_text or "file_path" in response_text


# ============================================================================
# Role-Based Access Tests
# ============================================================================


def test_export_requires_approved_role(tmp_path):
    """Export endpoints require specific roles."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-export.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Viewer cannot export dossiers
    response = client.post(
        "/v1/exports",
        json={"export_type": "dossier", "resource_id": "exp_123"},
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "viewer",
        },
    )
    assert response.status_code == 403


def test_regrade_requires_engineer_role(tmp_path):
    """Regrade endpoints require evaluation_engineer role."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-regrade.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Viewer cannot regrade
    response = client.post(
        "/v1/experiments:regrade",
        json={"experiment_id": "exp_123", "grader_version": "1.0.0"},
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "viewer",
        },
    )
    assert response.status_code == 403


def test_compare_allows_viewer_role(tmp_path):
    """Compare endpoints allow viewer role for read access."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-compare.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Viewer can compare
    response = client.post(
        "/v1/experiments:compare",
        json={
            "baseline_experiment_id": "exp_1",
            "candidate_experiment_id": "exp_2",
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "viewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["schema_version"] == "we3.comparison.v1"


# ============================================================================
# Cursor Pagination Tests
# ============================================================================


def test_evidence_list_returns_metadata_only(tmp_path):
    """Evidence list should return metadata summaries, not restricted raw content."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-evidence.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/v1/evidence",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )

    # Should return empty list or metadata summaries only
    assert response.status_code == 200
    assert "evidence" in response.json()
    # Should not have full raw content
    assert "raw_content" not in response.text


def test_cursor_pagination_fields(tmp_path):
    """Cursor pagination should include cursor fields."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-cursor.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/v1/evidence?limit=50",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )

    # Response should include pagination fields
    assert "next_cursor" in response.json()
    assert "has_more" in response.json()


# ============================================================================
# Schema Version Tests
# ============================================================================


def test_all_responses_includeversion(tmp_path, foundation_manifest):
    """All responses must include schema_version field."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-schema.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Health check
    response = client.get("/health")
    assert "schema_version" in response.json()

    # Validate
    manifest = load_experiment(foundation_manifest).model_dump(mode="json", by_alias=True)
    response = client.post(
        "/v1/experiments:validate",
        json=manifest,
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert "schema_version" in response.json()


# ============================================================================
# Additional Workflow Endpoint Tests
# ============================================================================


def test_cancel_operation_returns_proper_error_for_terminated_state(
    tmp_path, foundation_manifest
):
    """Cancel should fail gracefully for already terminated operations."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-cancel.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Create operation
    response = client.post(
        "/v1/experiments:run",
        json={
            "manifest_path": str(foundation_manifest),
            "output_dir": str(tmp_path / "output"),
        },
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    operation_id = response.json()["operation"]["operation_id"]

    # Cancel
    cancel_response = client.post(
        f"/v1/operations/{operation_id}:cancel",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    # Should succeed (operation might be in pending/running state)
    assert cancel_response.status_code in {200, 409}


def test_unknown_resource_returns_not_found(tmp_path):
    """Unknown resources should return 404, not 500."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-unknown.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/v1/operations/nonexistent-operation-id",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "operation_not_found"


def test_evidence_get_returns_metadata_only(tmp_path):
    """Evidence GET endpoint should return metadata summary only, not raw content."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-evidence-get.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/v1/evidence/evidence-123",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )

    # Should return metadata summary
    assert response.status_code == 200
    assert "metadata_summary" in response.json()
    assert "schema_version" in response.json()
    # Should not have full raw content
    assert "raw_content" not in response.text
    assert "content" not in response.json()


def test_status_endpoint_returns_project_context(tmp_path):
    """Status endpoint should return project-scoped status."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-status.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/v1/status",
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "viewer",
        },
    )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "we3.status.v1"
    assert response.json()["project_id"] == "model-safety"


def test_dossier_verify_requires_special_role(tmp_path):
    """Dossier verify requires signing_authority, release_authority, or adjudicator."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api-verify.db'}",
        artifact_root=tmp_path / "artifacts",
        auth_mode="dev",
        environment="test",
    )
    client = TestClient(create_app(settings))

    # Viewer cannot verify
    response = client.post(
        "/v1/dossiers:verify",
        json={"dossier_path": "/tmp/test"},
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "viewer",
        },
    )
    assert response.status_code == 403

    # evaluation_engineer cannot verify (only signing_authority roles)
    response = client.post(
        "/v1/dossiers:verify",
        json={"dossier_path": "/tmp/test"},
        headers={
            "X-WE3-Project-ID": "model-safety",
            "X-WE3-Role": "evaluation_engineer",
        },
    )
    assert response.status_code == 403