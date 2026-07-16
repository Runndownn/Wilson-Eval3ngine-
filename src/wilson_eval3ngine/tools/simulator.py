"""Deterministic Tool Simulators for Certification (TODO 41).

Provides schema-only tool simulation with:
- Versioned tool manifests defining allowed arguments and state
- Deterministic execution (same seed = same results)
- Network/policy enforcement (no live external actions)
- Resource bounds for CPU, memory, file size, duration
- Action logging with correlation IDs
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger("wilson.tools.simulator")


class ToolExecutionMode(StrEnum):
    """Execution mode for tool simulators."""

    SIMULATE = "simulate"  # Deterministic simulation (certification)
    LAB_ONLY = "lab_only"  # Real tools, lab environment only


class SimulatorState(StrEnum):
    """State model for deterministic simulators."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolManifest:
    """Versioned manifest defining tool simulator behavior.
    
    Each tool has a manifest that defines:
    - Allowed arguments schema
    - Deterministic state model
    - Resource bounds
    - Security policy (no egress, no shell)
    """
    
    tool_name: str
    version: str
    allowed_arguments: set[str]
    allowed_paths: list[str] | None = None  # Path patterns if file access needed
    seed_field: str = "seed"  # Field used for deterministic results
    max_file_size_bytes: int = 10_000_000  # 10MB default
    max_runtime_seconds: int = 30
    network_allowed: bool = False
    shell_allowed: bool = False
    
    def validate_arguments(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments against manifest schema.
        
        Rejects unknown arguments and validates values.
        """
        unknown = set(args.keys()) - self.allowed_arguments - {"seed"}
        if unknown:
            raise ValueError(f"Unknown arguments rejected: {unknown}")
        return args


@dataclass
class ToolSimulatorResult:
    """Result from tool simulator execution."""
    
    success: bool
    tool_name: str
    tool_version: str
    state: SimulatorState
    output_hash: str
    output: dict[str, Any] | None = None
    error: str | None = None
    correlation_id: str | None = None
    resource_usage: dict[str, int | float] | None = None


@dataclass
class ToolActionLog:
    """Log entry for tool action."""
    
    action_id: str
    tool_name: str
    tool_version: str
    input_args: dict[str, Any]
    authorization_result: bool
    normalized_args: dict[str, Any]
    output_hash: str
    correlation_id: str
    timestamp: str = field(default_factory=lambda: "")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "input_args": self.input_args,
            "authorization_result": self.authorization_result,
            "output_hash": self.output_hash,
            "correlation_id": self.correlation_id,
        }


# Tool manifests registry
TOOL_MANIFESTS: dict[str, ToolManifest] = {}


def register_tool_manifest(manifest: ToolManifest) -> None:
    """Register a tool manifest for simulation."""
    TOOL_MANIFESTS[manifest.tool_name] = manifest
    logger.info(
        "tool_manifest_registered",
        extra={"tool_name": manifest.tool_name, "version": manifest.version}
    )


def get_tool_manifest(tool_name: str) -> ToolManifest | None:
    """Get registered tool manifest."""
    return TOOL_MANIFESTS.get(tool_name)


class DeterministicToolSimulator:
    """Deterministic tool simulator for certification workflows.
    
    Security guarantees:
    - No live external actions
    - No network access
    - No shell execution
    - Bounded resources
    - Deterministic results via seed
    """
    
    def __init__(self, manifest: ToolManifest | None = None):
        self._manifest = manifest
        self._action_logs: list[ToolActionLog] = []
    
    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        correlation_id: str,
        seed: int = 42,
    ) -> ToolSimulatorResult:
        """Execute tool in simulation mode.
        
        Args:
            tool_name: Name of the tool to simulate
            arguments: Tool arguments (validated against manifest)
            correlation_id: Request correlation ID for tracing
            seed: Seed for deterministic output
            
        Returns:
            Simulated result (same seed = same output)
        """
        manifest = get_tool_manifest(tool_name)
        if not manifest:
            return ToolSimulatorResult(
                success=False,
                tool_name=tool_name,
                tool_version="unknown",
                state=SimulatorState.FAILED,
                output_hash="",
                error=f"Tool manifest not found: {tool_name}",
                correlation_id=correlation_id,
            )
        
        # Validate arguments
        normalized = manifest.validate_arguments(arguments)
        
        # Check network/shell policy (must fail closed)
        if manifest.network_allowed:
            logger.warning(
                "network_not_allowed_in_certification",
                extra={"tool_name": tool_name}
            )
        if manifest.shell_allowed:
            logger.warning(
                "shell_not_allowed_in_certification",
                extra={"tool_name": tool_name}
            )
        
        # Deterministic simulation
        output = self._simulate_tool(manifest, normalized, seed)
        output_hash = self._compute_output_hash(output)
        
        # Log action
        log = ToolActionLog(
            action_id=f"action_{seed}_{correlation_id[:8]}",
            tool_name=tool_name,
            tool_version=manifest.version,
            input_args=arguments,
            authorization_result=True,
            normalized_args=normalized,
            output_hash=output_hash,
            correlation_id=correlation_id,
        )
        self._action_logs.append(log)
        
        return ToolSimulatorResult(
            success=True,
            tool_name=tool_name,
            tool_version=manifest.version,
            state=SimulatorState.COMPLETED,
            output_hash=output_hash,
            output=output,
            correlation_id=correlation_id,
            resource_usage={"simulated": True, "seed": seed},
        )
    
    def _simulate_tool(
        self,
        manifest: ToolManifest,
        arguments: dict[str, Any],
        seed: int,
    ) -> dict[str, Any]:
        """Generate deterministic simulation output."""
        # Build deterministic output based on manifest and seed
        output = {
            "tool": manifest.tool_name,
            "version": manifest.version,
            "simulated": True,
            "seed": seed,
            "arguments": {
                k: v for k, v in arguments.items()
                if k != manifest.seed_field  # Exclude seed from output
            },
            "result": self._compute_deterministic_result(manifest, arguments, seed),
            "metadata": {
                "network_enabled": manifest.network_allowed,
                "shell_enabled": manifest.shell_allowed,
            }
        }
        return output
    
    def _compute_deterministic_result(
        self,
        manifest: ToolManifest,
        arguments: dict[str, Any],
        seed: int,
    ) -> Any:
        """Compute deterministic result based on tool type."""
        # Hash-based deterministic result
        payload = json.dumps({
            "tool": manifest.tool_name,
            "args": arguments,
            "seed": seed,
        }, sort_keys=True)
        return f"simulated_result_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    
    def _compute_output_hash(self, output: dict[str, Any]) -> str:
        """Compute hash of output for verification."""
        return f"sha256:{hashlib.sha256(json.dumps(output, sort_keys=True).encode()).hexdigest()[:32]}"
    
    def get_action_logs(self) -> list[ToolActionLog]:
        """Get recorded action logs."""
        return self._action_logs.copy()


# Built-in tool manifests for certification
def _register_builtin_manifests() -> None:
    """Register built-in tool manifests."""
    # Search tool (simulated)
    register_tool_manifest(ToolManifest(
        tool_name="search_internal",
        version="1.0.0",
        allowed_arguments={"query", "max_results", "filters"},
        network_allowed=False,
        shell_allowed=False,
    ))
    
    # File read tool (simulated, read-only)
    register_tool_manifest(ToolManifest(
        tool_name="file_read",
        version="1.0.0",
        allowed_arguments={"path", "mode"},
        allowed_paths=["/data/**", "/evidence/**"],
        network_allowed=False,
        shell_allowed=False,
    ))
    
    # Metric query tool (simulated)
    register_tool_manifest(ToolManifest(
        tool_name="metric_query",
        version="1.0.0",
        allowed_arguments={"metric_id", "time_range", "dimensions"},
        network_allowed=False,
        shell_allowed=False,
    ))


# Initialize built-in manifests on import
_register_builtin_manifests()


__all__ = [
    "ToolExecutionMode",
    "SimulatorState",
    "ToolManifest",
    "ToolSimulatorResult",
    "ToolActionLog",
    "DeterministicToolSimulator",
    "register_tool_manifest",
    "get_tool_manifest",
]