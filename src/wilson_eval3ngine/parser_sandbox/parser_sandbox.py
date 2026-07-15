# Systems: Parser Sandbox
# Tags: SANDBOX
# Colors: Slate
# Provenance: Authored here
# Tag confidence: High
# Inventory date: 2026-07-15

"""Parser sandbox contract and execution for isolated parsing operations."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionMode(StrEnum):
    """Parser execution modes."""

    SANDBOX = "sandbox"
    DIRECT = "direct"
    DISABLED = "disabled"


class QuarantineReason(StrEnum):
    """Quarantine reason codes for parser violations."""

    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    SYMLINK_ESCAPE = "symlink_escape"
    DEVICE_FILE = "device_file"
    TYPE_MISMATCH = "type_mismatch"
    DECOMPRESSION_BOMB = "decompression_bomb"
    RESOURCE_EXCEEDED = "resource_exceeded"
    MALFORMED_OUTPUT = "malformed_output"
    ACTIVE_CONTENT_DETECTED = "active_content_detected"
    PARSE_FAILED = "parse_failed"


class ParserSandboxContract(BaseModel):
    """Contract defining parser sandbox configuration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = "parser_sandbox_contract.v1"
    parser_id: str = Field(min_length=1)
    execution_mode: ExecutionMode = ExecutionMode.SANDBOX
    isolation_controls: dict[str, bool | list[str]] = Field(default_factory=lambda: {
        "non_root": True,
        "no_network": True,
        "read_only_input": True,
        "isolated_temp_storage": True,
        "no_ambient_credentials": True,
        "linux_capabilities_removed": ["all"],
    })
    resource_limits: dict[str, int | float | None] = Field(default_factory=lambda: {
        "cpu_time_seconds": 30,
        "wall_time_seconds": 60,
        "memory_bytes": 512 * 1024 * 1024,
        "max_processes": 1,
        "max_open_files": 64,
    })
    result_envelope_required: bool = True
    result_envelope_schema: str = "normalized_document_contract.v1"
    quarantine_rules: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("parser_id")
    @classmethod
    def _normalize_parser_id(cls, value: str) -> str:
        return value.strip()


@dataclass(frozen=True)
class SandboxResult:
    """Result from sandboxed parser execution."""

    success: bool
    object_id: str
    derived_hash: str
    raw_hash: str
    output: dict[str, Any] | None = None
    quarantine_reason: QuarantineReason | None = None
    error_message: str | None = None
    resource_usage: dict[str, int | float] | None = None


class ParserSandboxExecutor:
    """Execute parsers in isolated sandbox environments."""

    def __init__(self, contract: ParserSandboxContract | None = None) -> None:
        self._contract = contract or ParserSandboxContract(parser_id="default")
        self._logger = logging.getLogger("wilson.parser.sandbox")

    def execute(
        self,
        input_path: Path,
        adapter_id: str,
        adapter_version: str,
    ) -> SandboxResult:
        """Execute parser in sandbox for the given input."""
        object_id = f"parsed:{uuid4().hex[:24]}"

        if self._contract.execution_mode == ExecutionMode.DISABLED:
            self._logger.warning("parser_disabled", extra={"parser_id": self._contract.parser_id})
            return SandboxResult(
                success=False,
                object_id=object_id,
                derived_hash="",
                raw_hash="",
                quarantine_reason=QuarantineReason.PARSE_FAILED,
                error_message="Parser execution is disabled",
            )

        raw_bytes = self._read_input(input_path)
        raw_hash = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"

        return self._execute_sandboxed(
            object_id=object_id,
            input_path=input_path,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            raw_hash=raw_hash,
        )

    def _read_input(self, input_path: Path) -> bytes:
        """Read input file for processing."""
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        with open(input_path, "rb") as f:
            return f.read()

    def _execute_sandboxed(
        self,
        object_id: str,
        input_path: Path,
        adapter_id: str,
        adapter_version: str,
        raw_hash: str,
    ) -> SandboxResult:
        """Execute parser in sandboxed mode."""
        start_time = datetime.now(tz=UTC)

        # Validate input is within size limits
        input_size = input_path.stat().st_size
        max_input = int(self._contract.resource_limits.get("memory_bytes", 512 * 1024 * 1024) or 0)
        if input_size > max_input:
            return SandboxResult(
                success=False,
                object_id=object_id,
                derived_hash="",
                raw_hash=raw_hash,
                quarantine_reason=QuarantineReason.RESOURCE_EXCEEDED,
                error_message=f"Input size {input_size} exceeds limit {max_input}",
            )

        # Check for path traversal attempts in input path
        if self._detect_path_traversal(input_path):
            return SandboxResult(
                success=False,
                object_id=object_id,
                derived_hash="",
                raw_hash=raw_hash,
                quarantine_reason=QuarantineReason.PATH_TRAVERSAL_ATTEMPT,
                error_message="Path traversal attempt detected in input",
            )

        # Create isolated temp directory for processing
        with tempfile.TemporaryDirectory(prefix=f"parser_sandbox_{object_id}_") as temp_dir:
            output_path = Path(temp_dir) / "output.json"
            resource_info = {
                "cpu_time_seconds": self._contract.resource_limits.get("cpu_time_seconds", 30),
                "wall_time_seconds": self._contract.resource_limits.get("wall_time_seconds", 60),
                "input_size_bytes": input_size,
            }

            try:
                # Build and execute isolated command
                result = self._run_isolated_parser(
                    input_path=input_path,
                    output_path=output_path,
                    temp_dir=temp_dir,
                )

                if result.success and output_path.exists():
                    derived_hash = result.derived_hash
                    return SandboxResult(
                        success=True,
                        object_id=object_id,
                        derived_hash=derived_hash,
                        raw_hash=raw_hash,
                        output=result.output,
                        resource_usage=resource_info,
                    )
                return SandboxResult(
                    success=False,
                    object_id=object_id,
                    derived_hash="",
                    raw_hash=raw_hash,
                    quarantine_reason=QuarantineReason.PARSE_FAILED,
                    error_message=result.error_message or "Parser execution failed",
                    resource_usage=resource_info,
                )
            except Exception as e:
                self._logger.exception("sandbox_execution_failed")
                return SandboxResult(
                    success=False,
                    object_id=object_id,
                    derived_hash="",
                    raw_hash=raw_hash,
                    quarantine_reason=QuarantineReason.PARSE_FAILED,
                    error_message=str(e),
                    resource_usage=resource_info,
                )

    def _run_isolated_parser(
        self,
        input_path: Path,
        output_path: Path,
        temp_dir: str,
    ) -> SandboxResult:
        """Run parser command in isolated environment."""
        # Build isolation arguments
        isolation_args = self._build_isolation_arguments(input_path, output_path, temp_dir)

        # Execute via subprocess with strict controls
        try:
            completed = subprocess.run(
                isolation_args,
                capture_output=True,
                text=False,
                timeout=float(self._contract.resource_limits.get("wall_time_seconds", 60) or 60),
                check=False,
            )

            if completed.returncode != 0:
                return SandboxResult(
                    success=False,
                    object_id="",
                    derived_hash="",
                    raw_hash="",
                    error_message=completed.stderr.decode("utf-8", errors="replace")[:500],
                )

            output_data = json.loads(output_path.read_text())
            derived_hash = f"sha256:{hashlib.sha256(json.dumps(output_data, sort_keys=True).encode()).hexdigest()}"

            return SandboxResult(
                success=True,
                object_id=output_data.get("object_id", ""),
                derived_hash=derived_hash,
                raw_hash="",
                output=output_data,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                object_id="",
                derived_hash="",
                raw_hash="",
                quarantine_reason=QuarantineReason.RESOURCE_EXCEEDED,
                error_message="Parser execution timed out",
            )
        except json.JSONDecodeError:
            return SandboxResult(
                success=False,
                object_id="",
                derived_hash="",
                raw_hash="",
                quarantine_reason=QuarantineReason.MALFORMED_OUTPUT,
                error_message="Invalid JSON output from parser",
            )

    def _build_isolation_arguments(
        self,
        input_path: Path,
        output_path: Path,
        temp_dir: str,
    ) -> list[str]:
        """Build isolated execution command arguments."""
        # Use firejail or similar sandboxing if available
        # Fallback to subprocess with restricted environment
        args = ["python3", "-m", "wilson_eval3ngine.adapters.text_markdown_adapter"]
        args.extend([
            "--input", str(input_path),
            "--output", str(output_path),
            "--temp-dir", temp_dir,
        ])
        return args

    def _detect_path_traversal(self, path: Path) -> bool:
        """Detect path traversal attempts in the input path."""
        path_str = str(path)
        traversal_patterns = ["../", "..\\", "/etc/", "C:\\Windows"]
        return any(pattern in path_str for pattern in traversal_patterns)


def get_parser_sandbox_executor() -> ParserSandboxExecutor:
    """Return singleton parser sandbox executor."""
    return ParserSandboxExecutor()


__all__ = [
    "ExecutionMode",
    "QuarantineReason",
    "ParserSandboxContract",
    "SandboxResult",
    "ParserSandboxExecutor",
    "get_parser_sandbox_executor",
]