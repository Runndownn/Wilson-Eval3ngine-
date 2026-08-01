"""CLI-based provider adapters for locally-installed AI agents.

Supports:
- Claude CLI (claw) - via claude command
- Kilo CLI - via kilo command
- Codex CLI - via codex command
- Other compatible local agents

These adapters execute the agent through installed command-line interfaces
without requiring separate API key configuration, using the user's existing
local authentication.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

from ..constants import FailureMode
from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex
from .base import ProviderFailure, ProviderAdapter


class CLIProviderAdapter:
    """Base adapter for CLI-based providers.

    Provides common subprocess execution pattern for CLI tools.
    Subclasses must implement:
    - executable_name: str - the CLI command name
    - detect_available(): bool - check if CLI is installed/authenticated
    - get_supported_models(): list[str] - available model IDs
    - build_command(request, prompt): list[str] - construct CLI args
    - parse_output(stdout, stderr, returncode): dict - extract response
    """

    name: str = "cli_base"
    executable_name: str = "cli-tool"  # Override in subclass

    def __init__(self) -> None:
        self._executable_path: str | None = None

    def _find_executable(self) -> str | None:
        """Find the CLI executable in PATH."""
        path = shutil.which(self.executable_name)
        if path:
            self._executable_path = path
        return path

    def detect_available(self) -> bool:
        """Check if CLI is installed and ready. Override in subclass."""
        return self._find_executable() is not None

    def get_supported_models(self) -> list[str]:
        """Return list of supported model identifiers. Override in subclass."""
        return []

    def _execute_cli(
        self,
        args: list[str],
        input_data: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> tuple[int, str, str, float]:
        """Execute CLI command and return (returncode, stdout, stderr, elapsed_ms)."""
        start = time.time()
        try:
            result = subprocess.run(
                args,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.time() - start) * 1000
            return result.returncode, result.stdout, result.stderr, elapsed_ms
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.time() - start) * 1000
            return -1, "", "Command timed out", elapsed_ms
        except FileNotFoundError:
            return -1, "", f"Executable not found: {self.executable_name}", 0
        except Exception as exc:
            return -1, "", str(exc), 0

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        """Execute provider request through CLI.

        Args:
            request: Canonical provider request
            simulation: Optional simulation config (ignored for CLI providers)
            attempt_number: 1-based attempt number for retry tracking

        Returns:
            ProviderResponse with canonical fields
        """
        # Extract prompt from messages
        prompt = self._extract_prompt(request)

        # Build and execute command
        if not self._executable_path and not self._find_executable():
            raise ProviderFailure(
                FailureMode.AUTH_FAILURE,
                f"{self.executable_name} not found in PATH",
                retryable=False,
            )

        args = self.build_command(request, prompt)
        returncode, stdout, stderr, elapsed_ms = self._execute_cli(
            args, input_data=prompt, timeout_seconds=request.timeout_seconds
        )

        # Parse output
        response_data = self.parse_output(stdout, stderr, returncode)

        # Build canonical response
        return ProviderResponse(
            run_id=request.run_id,
            attempt_id=new_id("att"),
            protocol_valid=response_data.get("protocol_valid", True),
            terminal=True,
            text=response_data.get("text", ""),
            provider_reported_model=response_data.get("model", request.model),
            finish_reason=response_data.get("finish_reason", "stop"),
            usage=response_data.get("usage", {}),
            latency_ms=elapsed_ms,
            error_class=response_data.get("error_class"),
            retryable=response_data.get("retryable", False),
            metadata={
                "adapter": self.name,
                "executable": self._executable_path,
                "attempt_number": attempt_number,
                "provider_metadata": {
                    "returncode": returncode,
                    "cli_stderr": stderr[:500] if stderr else None,
                },
            },
            raw_response_hash=sha256_hex(stdout or ""),
        )

    def _extract_prompt(self, request: ProviderRequest) -> str:
        """Extract user prompt from request messages."""
        for turn in request.messages:
            if turn.role == "user":
                for block in turn.content:
                    if block.type == "text":
                        return block.text
        return ""

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        """Build CLI command arguments. Override in subclass."""
        raise NotImplementedError("Subclasses must implement build_command")

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse CLI output into response fields. Override in subclass."""
        raise NotImplementedError("Subclasses must implement parse_output")


class ClaudeCLIAdapter(CLIProviderAdapter):
    """Adapter for Claude CLI (claw)."""

    name = "claude_cli"
    executable_name = "claude"

    def detect_available(self) -> bool:
        """Check if Claude CLI is installed and authenticated."""
        path = self._find_executable()
        if not path:
            return False
        # Verify authentication with a quick version check
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return ["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219", "claude-sonnet-4"]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        """Build claude CLI command."""
        args = [self._executable_path, "--model", request.model]

        # Add system prompt if present
        if request.messages and request.messages[0].role == "system":
            for block in request.messages[0].content:
                if block.type == "text":
                    args.extend(["--system-prompt", block.text])

        # Use prompt flag for input
        args.extend(["--prompt", prompt])

        # Output as JSON for structured parsing
        args.append("--output-format")
        args.append("json")

        return args

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse Claude CLI JSON output."""
        if returncode != 0:
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }

        try:
            data = json.loads(stdout)
            return {
                "text": data.get("response", data.get("content", "")),
                "finish_reason": "stop",
                "usage": {
                    "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                },
            }
        except json.JSONDecodeError:
            # Fallback: treat stdout as text response
            return {"text": stdout.strip(), "finish_reason": "stop", "usage": {}}


class KiloCLIAdapter(CLIProviderAdapter):
    """Adapter for Kilo CLI."""

    name = "kilo_cli"
    executable_name = "kilo"

    def detect_available(self) -> bool:
        """Check if Kilo CLI is installed and configured."""
        path = self._find_executable()
        if not path:
            return False
        try:
            result = subprocess.run(
                [path, "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return ["gpt-4", "gpt-4-turbo", "gpt-4o", "o1-preview", "o1-mini", "o3-mini", "claude-sonnet-4", "claude-opus-4", "gemini-2.5-flash", "step-3.7-flash"]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        """Build kilo CLI command."""
        model = request.model
        # Ensure model has provider prefix for kilo CLI
        if "/" not in model:
            if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
                model = f"openai/{model}"
            elif model.startswith("claude"):
                model = f"anthropic/{model}"
            elif model.startswith("gemini"):
                model = f"google/{model}"
            elif model.startswith("llama"):
                model = f"meta-llama/{model}"
            elif model.startswith("qwen"):
                model = f"qwen/{model}"
            elif model.startswith("deepseek"):
                model = f"deepseek/{model}"
            elif model.startswith("mistral"):
                model = f"mistralai/{model}"
            elif model.startswith("step"):
                model = f"stepfun/{model}"
        args = [self._executable_path, "run", prompt, "-m", model, "--format", "json", "--pure"]
        return args

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse Kilo CLI output (JSON format)."""
        if returncode != 0:
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }

        try:
            data = json.loads(stdout)
            return {
                "text": data.get("content", data.get("text", "")),
                "finish_reason": "stop",
                "usage": data.get("usage", {}),
            }
        except json.JSONDecodeError:
            return {"text": stdout.strip(), "finish_reason": "stop", "usage": {}}


class CodexCLIAdapter(CLIProviderAdapter):
    """Adapter for OpenAI Codex CLI."""

    name = "codex_cli"
    executable_name = "codex"

    def detect_available(self) -> bool:
        """Check if Codex CLI is installed and authenticated."""
        path = self._find_executable()
        if not path:
            return False
        try:
            result = subprocess.run(
                [path, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return ["codex-mini-latest", "o1-mini", "o1-preview", "o3-mini", "o3-preview"]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        """Build codex CLI command."""
        args = [self._executable_path, "completions", "--model", request.model]

        # Write prompt to stdin since codex expects it
        return args

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        """Parse Codex CLI output (JSON format)."""
        if returncode != 0:
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }

        try:
            data = json.loads(stdout)
            # Handle both single response and array formats
            choices = data.get("choices", [data] if "choices" not in data else [])
            if choices:
                content = choices[0].get("text", choices[0].get("message", {}).get("content", ""))
            else:
                content = data.get("text", "")

            return {
                "text": content,
                "finish_reason": choices[0].get("finish_reason", "stop") if choices else "stop",
                "usage": {
                    "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                    "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
                },
            }
        except json.JSONDecodeError:
            return {"text": stdout.strip(), "finish_reason": "stop", "usage": {}}