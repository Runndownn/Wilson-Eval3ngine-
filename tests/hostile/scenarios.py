"""
Hostile test scenarios for TODO 50.

T7.1.6 - Validate interfaces against malformed data, concurrency,
stale state, active content, and authorization failures.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


# Test scenario categories
class HostileScenario:
    """Hostile test scenario descriptor."""
    MALFORMED_PAYLOAD = "malformed_payload"
    STALE_ETAG = "stale_etag"
    CONCURRENCY = "concurrency_collision"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_PARTITION = "network_partition"
    PAGINATION_EDGE = "pagination_edge"
    EXPORT_RACE = "export_race_condition"
    VERSION_SKEW = "version_skew"
    ACTIVE_CONTENT = "active_content_injection"


@dataclass(frozen=True, slots=True)
class HostileInput:
    """Malicious or malformed input for testing."""
    scenario_type: str
    payload: dict[str, Any]
    expected_status: int
    expected_exit_code: int | None = None
    safe_detail: str = ""


@dataclass(frozen=True, slots=True)
class TestAssertion:
    """Expected assertion for hostile test verification."""
    http_status: int | None = None
    exit_code: int | None = None
    audit_event: str | None = None
    artifact_exists: bool = False
    no_sensitive_data: bool = True


def make_malformed_experiment_manifest() -> HostileInput:
    """Create malformed experiment manifest for API testing."""
    return HostileInput(
        scenario_type=HostileScenario.MALFORMED_PAYLOAD,
        payload={
            "name": "test",
            # Missing required fields
            "dataset": {"dataset_id": "", "version": ""},
        },
        expected_status=422,
        safe_detail="validation_failed",
    )


def make_stale_etag_request(
    operation_id: str,
    stale_etag: str,
) -> HostileInput:
    """Create request with stale ETag for optimistic locking test."""
    return HostileInput(
        scenario_type=HostileScenario.STALE_ETAG,
        payload={
            "operation_id": operation_id,
            "if_match": stale_etag,
        },
        expected_status=412,
        safe_detail="stale_etag",
    )


def make_concurrent_update_request(
    operation_id: str,
    etag: str,
) -> HostileInput:
    """Create concurrent update request for race condition testing."""
    return HostileInput(
        scenario_type=HostileScenario.CONCURRENCY,
        payload={
            "operation_id": operation_id,
            "if_match": etag,
            "state": "cancelled",
        },
        expected_status=409,
        safe_detail="concurrent_modification",
    )


def make_idempotency_conflict_request(
    idempotency_key: str,
    body: dict[str, Any],
    different_body: dict[str, Any],
) -> HostileInput:
    """Create idempotency key reuse with different payload."""
    return HostileInput(
        scenario_type=HostileScenario.IDEMPOTENCY_CONFLICT,
        payload=body,
        expected_status=422,
        safe_detail="idempotency_key_reuse_with_different_payload",
    )


def make_active_content_payload() -> HostileInput:
    """Create payload with active HTML/JS for XSS testing."""
    return HostileInput(
        scenario_type=HostileScenario.ACTIVE_CONTENT,
        payload={
            "name": "<script>alert('xss')</script>",
            "description": "<img src=x onerror=alert(1)>",
        },
        expected_status=422,
        safe_detail="invalid_format",
    )


def compute_pagination_cursor(
    project_id: str,
    resource_type: str,
    resource_id: str,
) -> str:
    """Compute test pagination cursor for edge case testing."""
    raw = f"{project_id}:{resource_type}:{resource_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_export_race_request(
    export_id: str,
    access_revoked: bool = False,
) -> HostileInput:
    """Create export request that races with access revocation."""
    return HostileInput(
        scenario_type=HostileScenario.EXPORT_RACE,
        payload={
            "export_id": export_id,
            "access_revoked": access_revoked,
        },
        expected_status=403 if access_revoked else 202,
        safe_detail="access_denied" if access_revoked else "accepted",
    )


def make_network_timeout_request() -> HostileInput:
    """Create network timeout scenario for testing resilience."""
    return HostileInput(
        scenario_type=HostileScenario.NETWORK_TIMEOUT,
        payload={
            "operation": "export",
            "timeout_ms": 30000,
        },
        expected_status=504,
        safe_detail="timeout",
    )


def make_network_partition_request() -> HostileInput:
    """Create network partition scenario for testing resilience."""
    return HostileInput(
        scenario_type=HostileScenario.NETWORK_PARTITION,
        payload={
            "operation": "run",
            "partition_duration_ms": 5000,
        },
        expected_status=503,
        safe_detail="service_unavailable",
    )


def make_version_skew_payload(
    producer_version: str,
    consumer_version: str,
) -> HostileInput:
    """Create version skew scenario."""
    return HostileInput(
        scenario_type=HostileScenario.VERSION_SKEW,
        payload={
            "producer_version": producer_version,
            "consumer_version": consumer_version,
            "schema_version": f"we3.test_case.v{producer_version}",
        },
        expected_status=422,
        safe_detail="version_mismatch",
    )


__all__ = [
    "HostileScenario",
    "HostileInput",
    "TestAssertion",
    "make_malformed_experiment_manifest",
    "make_stale_etag_request",
    "make_concurrent_update_request",
    "make_idempotency_conflict_request",
    "make_active_content_payload",
    "compute_pagination_cursor",
    "make_export_race_request",
    "make_network_timeout_request",
    "make_network_partition_request",
    "make_version_skew_payload",
]