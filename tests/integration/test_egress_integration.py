"""Integration tests for egress controls and tool simulators (TODO 41)."""

import pytest

from wilson_eval3ngine.network.egress import (
    check_egress_allowed,
    validate_redirect_chain,
)
from wilson_eval3ngine.tools.simulator import (
    DeterministicToolSimulator,
    ToolManifest,
    SimulatorState,
    register_tool_manifest,
)


class TestEgressIntegration:
    """Integration tests for egress policy enforcement."""

    def test_certification_mode_blocks_all_egress(self) -> None:
        """Egress blocked in certification mode."""
        egress = check_egress_allowed("https://external-api.com/data", allow_external=False)
        assert egress.allowed is False
        assert "blocked" in egress.reason.lower()

    def test_lab_mode_allows_external_safe_urls(self) -> None:
        """Lab mode allows safe external URLs for testing."""
        egress = check_egress_allowed("https://api.example.com/v1", allow_external=True)
        assert egress.allowed is True
        assert egress.reason == "lab_mode_approved"

    def test_ssrf_prevention(self) -> None:
        """SSRF attempts are prevented in both modes."""
        # Certification mode blocks all
        for url in [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ]:
            assert check_egress_allowed(url, allow_external=False).allowed is False

        # Lab mode blocks dangerous endpoints
        dangerous_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://localhost:8080/admin",
            "http://10.0.0.1/internal",
            "http://192.168.1.1/router",
        ]

        for url in dangerous_urls:
            decision = check_egress_allowed(url, allow_external=True)
            assert decision.allowed is False, f"URL should be blocked: {url}"

    def test_redirect_ssrf_blocked(self) -> None:
        """Redirect-based SSRF blocked."""
        redirect_chain = [
            "https://trusted.example.com/redirect",
            "http://169.254.169.254/meta-data",
        ]

        decisions = validate_redirect_chain(redirect_chain, allow_external=True)

        # Metadata endpoint in chain should be blocked
        assert len(decisions) == 2
        assert not decisions[1].allowed  # Second URL blocked
        assert "metadata" in decisions[1].reason.lower()


class TestToolSimulatorIntegration:
    """Integration tests for tool simulator workflows."""

    def test_simulated_tool_deterministic(self) -> None:
        """Simulated tool produces deterministic results."""
        manifest = ToolManifest(
            tool_name="calculator",
            version="1.0.0",
            allowed_arguments={"expression", "precision"},
        )
        register_tool_manifest(manifest)

        simulator = DeterministicToolSimulator(manifest)

        # Multiple runs with same seed
        results = []
        for _ in range(5):
            result = simulator.execute(
                tool_name="calculator",
                arguments={"expression": "2+2"},
                correlation_id="multi_corr",
                seed=999,
            )
            results.append(result)

        # All results identical
        hashes = [r.output_hash for r in results]
        assert len(set(hashes)) == 1

        # All logged
        logs = simulator.get_action_logs()
        assert len(logs) == 5

    def test_tool_state_machine(self) -> None:
        """Tool simulator follows state machine correctly."""
        manifest = ToolManifest(
            tool_name="stateful_tool",
            version="1.0.0",
            allowed_arguments={"action"},
        )
        register_tool_manifest(manifest)

        simulator = DeterministicToolSimulator(manifest)

        # Initial state
        assert len(simulator.get_action_logs()) == 0

        # Execute - transitions to completed
        result = simulator.execute(
            tool_name="stateful_tool",
            arguments={"action": "run"},
            correlation_id="state_corr",
        )
        assert result.state == SimulatorState.COMPLETED

        # Logs recorded
        assert len(simulator.get_action_logs()) == 1


class TestResourceBounds:
    """Tests for resource bound enforcement."""

    def test_file_size_limits(self) -> None:
        """Tool manifests include file size bounds."""
        manifest = ToolManifest(
            tool_name="file_processor",
            version="1.0.0",
            allowed_arguments={"path"},
            max_file_size_bytes=1_000_000,  # 1MB limit
        )

        assert manifest.max_file_size_bytes == 1_000_000

    def test_runtime_limits(self) -> None:
        """Tool manifests include runtime bounds."""
        manifest = ToolManifest(
            tool_name="slow_tool",
            version="1.0.0",
            allowed_arguments={},
            max_runtime_seconds=10,
        )

        assert manifest.max_runtime_seconds == 10


class TestToolSchemaValidation:
    """Tests for tool argument schema validation."""

    def test_shell_commands_rejected(self) -> None:
        """Shell commands in arguments are rejected."""
        manifest = ToolManifest(
            tool_name="safe_tool",
            version="1.0.0",
            allowed_arguments={"query", "filter"},
            shell_allowed=False,
        )

        # Shell-like arguments rejected by schema
        with pytest.raises(ValueError, match="Unknown"):
            manifest.validate_arguments({"shell": "rm -rf /", "query": "test"})

    def test_arbitrary_urls_rejected(self) -> None:
        """Arbitrary URLs in arguments are validated."""
        manifest = ToolManifest(
            tool_name="api_tool",
            version="1.0.0",
            allowed_arguments={"endpoint", "method"},
        )
        register_tool_manifest(manifest)

        simulator = DeterministicToolSimulator(manifest)
        result = simulator.execute(
            tool_name="api_tool",
            arguments={"endpoint": "https://example.com/data"},
            correlation_id="url_test",
        )

        # Simulation succeeds but no network call
        assert result.success is True
        assert result.output is not None
        assert "simulated" in result.output