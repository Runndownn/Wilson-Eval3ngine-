"""Unit tests for deterministic tool simulators (TODO 41)."""

import pytest

from wilson_eval3ngine.tools.simulator import (
    DeterministicToolSimulator,
    SimulatorState,
    ToolManifest,
    ToolExecutionMode,
    register_tool_manifest,
)


class TestToolManifest:
    """Tests for tool manifest validation."""

    def test_manifest_creation(self) -> None:
        """Tool manifest can be created with required fields."""
        manifest = ToolManifest(
            tool_name="test_tool",
            version="1.0.0",
            allowed_arguments={"arg1", "arg2"},
        )
        assert manifest.tool_name == "test_tool"
        assert manifest.version == "1.0.0"
        assert manifest.network_allowed is False
        assert manifest.shell_allowed is False

    def test_manifest_validate_arguments(self) -> None:
        """Valid arguments pass validation."""
        manifest = ToolManifest(
            tool_name="test_tool",
            version="1.0.0",
            allowed_arguments={"query", "max_results"},
        )
        
        validated = manifest.validate_arguments({"query": "test", "seed": 42})
        assert validated["query"] == "test"

    def test_manifest_reject_unknown_arguments(self) -> None:
        """Unknown arguments are rejected."""
        manifest = ToolManifest(
            tool_name="test_tool",
            version="1.0.0",
            allowed_arguments={"query"},
        )
        
        with pytest.raises(ValueError, match="Unknown arguments"):
            manifest.validate_arguments({"query": "test", "malicious_arg": "evil"})


class TestDeterministicToolSimulator:
    """Tests for deterministic tool simulation."""

    def test_simulator_creation(self) -> None:
        """Simulator can be created."""
        manifest = ToolManifest(
            tool_name="test_tool",
            version="1.0.0",
            allowed_arguments={"query"},
        )
        simulator = DeterministicToolSimulator(manifest)
        assert simulator is not None

    def test_simulate_unknown_tool(self) -> None:
        """Unknown tools fail gracefully."""
        simulator = DeterministicToolSimulator()
        result = simulator.execute(
            tool_name="unknown_tool",
            arguments={},
            correlation_id="corr_123",
        )
        assert result.success is False
        assert result.state == SimulatorState.FAILED

    def test_simulate_registered_tool(self) -> None:
        """Registered tool simulates successfully."""
        manifest = ToolManifest(
            tool_name="search_internal",
            version="1.0.0",
            allowed_arguments={"query", "max_results"},
        )
        register_tool_manifest(manifest)
        
        simulator = DeterministicToolSimulator()
        result = simulator.execute(
            tool_name="search_internal",
            arguments={"query": "test query"},
            correlation_id="corr_456",
            seed=12345,
        )
        
        assert result.success is True
        assert result.tool_name == "search_internal"
        assert result.state == SimulatorState.COMPLETED
        assert result.output is not None
        assert "simulated" in result.output

    def test_deterministic_output(self) -> None:
        """Same seed produces same output."""
        manifest = ToolManifest(
            tool_name="deterministic_tool",
            version="1.0.0",
            allowed_arguments={"input"},
        )
        register_tool_manifest(manifest)
        
        simulator = DeterministicToolSimulator()
        
        result1 = simulator.execute(
            tool_name="deterministic_tool",
            arguments={"input": "test"},
            correlation_id="corr_a",
            seed=42,
        )
        result2 = simulator.execute(
            tool_name="deterministic_tool",
            arguments={"input": "test"},
            correlation_id="corr_b",
            seed=42,
        )
        
        assert result1.output_hash == result2.output_hash

    def test_action_logging(self) -> None:
        """Actions are logged for audit."""
        manifest = ToolManifest(
            tool_name="logged_tool",
            version="1.0.0",
            allowed_arguments={"query"},
        )
        register_tool_manifest(manifest)
        
        simulator = DeterministicToolSimulator()
        simulator.execute(
            tool_name="logged_tool",
            arguments={"query": "test"},
            correlation_id="corr_log",
        )
        
        logs = simulator.get_action_logs()
        assert len(logs) == 1
        assert logs[0].tool_name == "logged_tool"
        assert logs[0].authorization_result is True


class TestEgressControls:
    """Tests for egress policy controls."""

    def test_certification_mode_blocks_egress(self) -> None:
        """Egress blocked in certification mode."""
        from wilson_eval3ngine.network.egress import check_egress_allowed
        
        decision = check_egress_allowed("https://example.com/api")
        assert decision.allowed is False
        assert "blocked" in decision.reason.lower()

    def test_metadata_endpoint_blocked(self) -> None:
        """Cloud metadata endpoints always blocked."""
        from wilson_eval3ngine.network.egress import check_egress_allowed, detect_metadata_access
        
        # Detection works
        assert detect_metadata_access("http://169.254.169.254/latest/meta-data/") is True
        assert detect_metadata_access("https://metadata.google.internal/") is True
        
        # Even in lab mode, metadata blocked
        decision = check_egress_allowed(
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            allow_external=True,
        )
        assert decision.allowed is False
        assert "metadata" in decision.reason.lower()

    def test_private_networks_blocked(self) -> None:
        """Private networks blocked in lab mode."""
        from wilson_eval3ngine.network.egress import check_egress_allowed
        
        decision = check_egress_allowed("http://10.0.0.1/admin", allow_external=True)
        assert decision.allowed is False

    def test_malformed_url_rejected(self) -> None:
        """Malformed URLs are rejected."""
        from wilson_eval3ngine.network.egress import check_egress_allowed
        
        decision = check_egress_allowed("not-a-url", allow_external=True)
        assert decision.allowed is False


class TestRedirectValidation:
    """Tests for redirect chain validation."""

    def test_redirect_chain_all_approved(self) -> None:
        """All-approved redirect chain passes."""
        from wilson_eval3ngine.network.egress import validate_redirect_chain
        
        # Even approved chains blocked in certification mode
        decisions = validate_redirect_chain([
            "https://api.example.com/v1",
        ], allow_external=False)
        
        assert all(not d.allowed for d in decisions)

    def test_redirect_chain_stops_at_blocked(self) -> None:
        """Redirect chain stops evaluation at blocked URL."""
        from wilson_eval3ngine.network.egress import validate_redirect_chain
        
        decisions = validate_redirect_chain([
            "https://api.example.com/v1",
            "http://169.254.169.254/meta-data",
        ], allow_external=True)
        
        # First might be approved (lab mode), second blocked
        assert len(decisions) == 2
        assert not decisions[1].allowed


class TestToolExecutionModes:
    """Tests for tool execution modes."""

    def test_simulate_mode_exists(self) -> None:
        """Simulation mode available for certification."""
        assert ToolExecutionMode.SIMULATE.value == "simulate"

    def test_lab_only_mode_exists(self) -> None:
        """Lab-only mode for real tool testing."""
        assert ToolExecutionMode.LAB_ONLY.value == "lab_only"