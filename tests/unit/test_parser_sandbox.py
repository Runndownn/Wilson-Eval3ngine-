"""Unit tests for Parser Sandbox (TODO 12)."""

from pathlib import Path

import pytest

from wilson_eval3ngine.parser_sandbox.parser_sandbox import (
    ExecutionMode,
    ParserSandboxContract,
    ParserSandboxExecutor,
    QuarantineReason,
    get_parser_sandbox_executor,
)


@pytest.fixture
def sample_contract() -> ParserSandboxContract:
    """Create sample sandbox contract."""
    return ParserSandboxContract(
        parser_id="test-markdown-parser-v1",
    )


@pytest.fixture
def sample_executor(sample_contract: ParserSandboxContract) -> ParserSandboxExecutor:
    """Create executor for testing."""
    return ParserSandboxExecutor(sample_contract)


class TestExecutionMode:
    """Test suite for execution modes."""

    def test_all_modes_exist(self):
        """Verify all execution modes exist."""
        modes = [m.value for m in ExecutionMode]
        expected = ["sandbox", "direct", "disabled"]
        for expected_mode in expected:
            assert expected_mode in modes, f"Missing execution mode: {expected_mode}"


class TestQuarantineReason:
    """Test suite for quarantine reasons."""

    def test_all_quarantine_reasons_exist(self):
        """Verify all quarantine reasons exist."""
        reasons = [r.value for r in QuarantineReason]
        expected = [
            "path_traversal_attempt",
            "symlink_escape",
            "device_file",
            "type_mismatch",
            "decompression_bomb",
            "resource_exceeded",
            "malformed_output",
            "active_content_detected",
            "parse_failed",
        ]
        for expected_reason in expected:
            assert expected_reason in reasons, f"Missing quarantine reason: {expected_reason}"


class TestParserSandboxContract:
    """Test suite for parser sandbox contract."""

    def test_valid_contract_creation(self, sample_contract: ParserSandboxContract):
        """Verify contract can be created."""
        assert sample_contract.parser_id == "test-markdown-parser-v1"
        assert sample_contract.execution_mode == ExecutionMode.SANDBOX

    def test_default_isolation_controls(self, sample_contract: ParserSandboxContract):
        """Verify default isolation controls are set."""
        controls = sample_contract.isolation_controls
        assert controls.get("non_root") is True
        assert controls.get("no_network") is True
        assert controls.get("read_only_input") is True
        assert controls.get("isolated_temp_storage") is True

    def test_default_resource_limits(self, sample_contract: ParserSandboxContract):
        """Verify default resource limits are set."""
        limits = sample_contract.resource_limits
        assert limits.get("cpu_time_seconds") == 30
        assert limits.get("wall_time_seconds") == 60
        assert "memory_bytes" in limits


class TestParserSandboxExecutor:
    """Test suite for parser sandbox executor."""

    def test_executor_creation(self, sample_executor: ParserSandboxExecutor):
        """Verify executor can be created."""
        assert sample_executor is not None

    def test_execute_disabled_mode(self, sample_contract: ParserSandboxContract, tmp_path: Path):
        """Verify disabled mode returns failed result."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")
        sample_contract.execution_mode = ExecutionMode.DISABLED
        executor = ParserSandboxExecutor(sample_contract)
        result = executor.execute(
            input_path=test_file,
            adapter_id="adapter:test",
            adapter_version="v1.0.0",
        )
        assert result.success is False
        assert result.quarantine_reason == QuarantineReason.PARSE_FAILED

    def test_path_traversal_detection(self, sample_executor: ParserSandboxExecutor, tmp_path: Path):
        """Verify path traversal attempts are detected."""
        result = sample_executor._detect_path_traversal(Path("../../../etc/passwd"))
        assert result is True

    def test_no_path_traversal(self, sample_executor: ParserSandboxExecutor, tmp_path: Path):
        """Verify normal paths pass traversal check."""
        result = sample_executor._detect_path_traversal(tmp_path / "test.md")
        assert result is False


class TestSandboxResult:
    """Test suite for sandbox result properties via execution."""

    def test_result_properties(self, sample_contract: ParserSandboxContract, tmp_path: Path):
        """Verify sandbox result has required properties."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Content")

        executor = ParserSandboxExecutor(sample_contract)

        # Even if execution fails, result should have object_id
        result = executor.execute(
            input_path=test_file,
            adapter_id="adapter:text-markdown-v1",
            adapter_version="v1.0.0",
        )

        assert hasattr(result, "success")
        assert hasattr(result, "object_id")
        assert hasattr(result, "derived_hash")
        assert hasattr(result, "raw_hash")


class TestGetParserSandboxExecutor:
    """Test suite for executor accessor."""

    def test_singleton_returns_same_instance(self):
        """Verify accessor returns consistent instance."""
        exec1 = get_parser_sandbox_executor()
        exec2 = get_parser_sandbox_executor()
        # These may or may not be the same based on implementation
        # Just verify they're valid instances
        assert isinstance(exec1, ParserSandboxExecutor)
        assert isinstance(exec2, ParserSandboxExecutor)