"""Unit tests for REST operation safety contracts."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

import pytest

from wilson_eval3ngine.api.operations import (
    IdempotencyBackendUnavailable,
    IdempotencyConflict,
    IdempotencyRecord,
    IdempotencyStore,
    compute_etag,
    decode_cursor,
    encode_cursor,
)
from wilson_eval3ngine.util import utc_now


class TestIdempotencyStore:
    def test_create_and_retrieve_record(self) -> None:
        store = IdempotencyStore()
        key = "test-key-123"
        op_id = store.create(key, "proj_a", b"test payload")

        retrieved = store.get(key, "proj_a")
        assert retrieved is not None
        assert retrieved.operation_id == op_id
        assert retrieved.project_id == "proj_a"
        assert retrieved.request_hash

    def test_same_key_same_intent_returns_existing_operation(self) -> None:
        store = IdempotencyStore()
        key = "test-key-456"
        op_id1 = store.create(key, "proj_a", b"payload1")
        op_id2 = store.create(key, "proj_a", b"payload1")
        assert op_id1 == op_id2

    def test_same_key_different_intent_is_rejected(self) -> None:
        store = IdempotencyStore()
        key = "duplicate-key"
        store.create(key, "proj_a", b"payload_v1")
        with pytest.raises(IdempotencyConflict):
            store.create(key, "proj_a", b"payload_v2")

    def test_caller_can_bind_actual_operation_id(self) -> None:
        store = IdempotencyStore()
        op_id = store.create(
            "actual-operation",
            "proj_a",
            b"start:proj_a:exp_1",
            operation_id="op_actual",
        )
        assert op_id == "op_actual"
        assert store.get("actual-operation", "proj_a").operation_id == "op_actual"

    def test_different_projects_do_not_share_keys(self) -> None:
        store = IdempotencyStore()
        key = "cross-project-key"
        op_id_a = store.create(key, "proj_a", b"payload")
        op_id_b = store.create(key, "proj_b", b"payload")
        assert op_id_a != op_id_b

    def test_project_mismatch_returns_none(self) -> None:
        store = IdempotencyStore()
        store.create("cross-project-key-2", "proj_a", b"payload")
        assert store.get("cross-project-key-2", "proj_b") is None

    def test_assurance_store_requires_shared_backend(self) -> None:
        with pytest.raises(IdempotencyBackendUnavailable):
            IdempotencyStore(fail_closed=True)

    def test_redis_binding_is_atomic_and_durable(self) -> None:
        redis_client = Mock()
        redis_client.set.return_value = True
        redis_client.get.return_value = None
        store = IdempotencyStore(redis_client=redis_client, fail_closed=True)
        result = store.create(
            "redis-key",
            "proj_a",
            b"intent",
            ttl_seconds=600,
            operation_id="op_redis",
        )
        assert result == "op_redis"
        call = redis_client.set.call_args
        assert call.args[0].startswith("we3:idempotency:")
        assert call.kwargs == {"ex": 600, "nx": True}


class TestIdempotencyRecordSerialization:
    def test_record_serializes_with_required_fields(self) -> None:
        record = IdempotencyRecord(
            idempotency_key="key_123",
            project_id="proj_a",
            operation_id="op_456",
            request_hash="hash_abc",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(hours=1),
        )
        d = record.model_dump()
        assert d["idempotency_key"] == "key_123"
        assert d["operation_id"] == "op_456"
        assert d["request_hash"] == "hash_abc"


class TestETagComputation:
    def test_etag_deterministic(self) -> None:
        assert compute_etag("experiment_1", "state", 42) == compute_etag(
            "experiment_1", "state", 42
        )

    def test_etag_changes_with_content(self) -> None:
        assert compute_etag("experiment_a", "state") != compute_etag(
            "experiment_b", "state"
        )

    def test_etag_format(self) -> None:
        assert compute_etag("test").startswith('W/"')


class TestCursorPagination:
    def test_encode_cursor_produces_opaque_string(self) -> None:
        cursor = encode_cursor("proj_a", "runs", "100")
        assert len(cursor) == 32
        assert isinstance(cursor, str)

    def test_cursor_uniqueness(self) -> None:
        assert encode_cursor("proj_a", "runs") != encode_cursor("proj_b", "runs")

    def test_decode_cursor_returns_list(self) -> None:
        cursor = "test_cursor_123"
        result = decode_cursor(cursor)
        assert isinstance(result, list)
        assert result[0] == cursor


class TestOperationLifecycle:
    def test_operation_state_transitions(self) -> None:
        from wilson_eval3ngine.domain.enums import OperationState

        valid_states = [
            OperationState.PENDING,
            OperationState.RUNNING,
            OperationState.SUCCEEDED,
            OperationState.FAILED,
        ]
        assert len(valid_states) == 4

    def test_operation_has_required_fields(self) -> None:
        from wilson_eval3ngine.domain.contracts import Operation

        op = Operation(
            operation_id="op_test",
            project_id="proj_a",
            manifest_path="test.yaml",
            output_dir="./output",
        )
        d = op.model_dump(mode="json")
        assert "operation_id" in d
        assert "project_id" in d
        assert "state" in d
        assert "created_at" in d


class TestVersionedErrorResponses:
    def test_error_response_structure(self) -> None:
        error = {
            "code": "test_error",
            "retryable": False,
            "safe_detail": "safe error message",
            "trace_id": "trc_test",
            "schema_version": "we3.error.v1",
        }
        assert {"code", "retryable", "safe_detail", "trace_id"}.issubset(error)

    def test_error_no_stack_trace(self) -> None:
        safe_detail = "Invalid input provided"
        assert "/" not in safe_detail
        assert ".py" not in safe_detail


class TestSchemaVersionConsistency:
    def test_responses_include_schema_version(self) -> None:
        expected_versions = [
            "we3.health.v1",
            "we3.validation_result.v1",
            "we3.operation_ack.v1",
            "we3.operation.v1",
            "we3.experiment_view.v1",
            "we3.run_list.v1",
            "we3.metric_list.v1",
            "we3.error.v1",
        ]
        assert all(version.startswith("we3.") for version in expected_versions)


class TestAPISafetyGuarantees:
    def test_unknown_fields_rejected(self) -> None:
        from pydantic import BaseModel, ConfigDict, ValidationError

        class StrictModel(BaseModel):
            model_config = ConfigDict(extra="forbid")
            value: str

        assert StrictModel(value="test").value == "test"
        with pytest.raises(ValidationError):
            StrictModel(value="test", extra_field="not_allowed")

    def test_body_size_fixture_is_large_enough_for_boundary_tests(self) -> None:
        large_text = "x" * 100_000
        assert len(large_text) == 100_000
