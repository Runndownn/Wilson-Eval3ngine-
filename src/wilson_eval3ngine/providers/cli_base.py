"""CLI-backed provider adapters for approved locally installed agents.

The adapters never invoke a shell. Provider output is treated as untrusted data,
and response metadata contains only bounded operational evidence: raw stderr,
exception text, absolute executable paths, credentials, and prompts are not
copied into canonical response metadata.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import shutil

from ..constants import FailureMode
from ..domain.contracts import ProviderRequest, ProviderResponse
from ..util import new_id, sha256_hex
from .base import ProviderFailure

logger = logging.getLogger(__name__)

_MAX_STDOUT_BYTES = 4 * 1024 * 1024
_MAX_STDERR_BYTES = 512 * 1024


class CLIProviderAdapter:
    """Base adapter for a reviewed local CLI provider."""

    name: str = "cli_base"
    executable_name: str = "cli-tool"

    def __init__(self) -> None:
        self._executable_path: str | None = None

    def _find_executable(self) -> str | None:
        """Resolve an executable through the operating system PATH policy."""
        path = shutil.which(self.executable_name)
        self._executable_path = path
        return path

    def detect_available(self) -> bool:
        return self._find_executable() is not None

    def get_supported_models(self) -> list[str]:
        return []

    @staticmethod
    def _bounded_text(value: str, max_bytes: int) -> str:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return value
        return encoded[:max_bytes].decode("utf-8", errors="ignore")

    def _execute_cli(
        self,
        args: list[str],
        input_data: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> tuple[int, str, str, float]:
        """Execute one argv-only process and bound captured provider output."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not args or not args[0]:
            raise ValueError("CLI argv requires an executable")

        started = time.monotonic()
        try:
            result = subprocess.run(
                args,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            elapsed_ms = (time.monotonic() - started) * 1000
            return (
                result.returncode,
                self._bounded_text(result.stdout or "", _MAX_STDOUT_BYTES),
                self._bounded_text(result.stderr or "", _MAX_STDERR_BYTES),
                elapsed_ms,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = (time.monotonic() - started) * 1000
            logger.warning(
                "cli_provider_timeout",
                extra={
                    "structured": {
                        "adapter": self.name,
                        "timeout_seconds": timeout_seconds,
                        "error_class": type(exc).__name__,
                    }
                },
            )
            return -1, "", "command_timeout", elapsed_ms
        except FileNotFoundError as exc:
            logger.warning(
                "cli_provider_executable_unavailable",
                extra={"structured": {"adapter": self.name, "error_class": type(exc).__name__}},
            )
            return -1, "", "executable_unavailable", 0.0
        except Exception as exc:
            # Never return str(exc): subprocess/OSError diagnostics can include
            # private filesystem paths, environment details, or argv values.
            logger.error(
                "cli_provider_execution_failed",
                extra={"structured": {"adapter": self.name, "error_class": type(exc).__name__}},
            )
            return -1, "", "execution_failed", (time.monotonic() - started) * 1000

    def execute(
        self,
        request: ProviderRequest,
        *,
        simulation: dict[str, Any] | None = None,
        attempt_number: int = 1,
    ) -> ProviderResponse:
        """Execute a request and return bounded canonical provider evidence."""
        del simulation
        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        prompt = self._extract_prompt(request)
        if not self._executable_path and not self._find_executable():
            raise ProviderFailure(
                FailureMode.AUTH_FAILURE,
                f"{self.executable_name} is not available",
                retryable=False,
            )

        args = self.build_command(request, prompt)
        returncode, stdout, stderr, elapsed_ms = self._execute_cli(
            args,
            input_data=prompt,
            timeout_seconds=request.timeout_seconds,
        )
        response_data = self.parse_output(stdout, stderr, returncode)

        stderr_hash = sha256_hex(stderr) if stderr else None
        executable_name = Path(self._executable_path or self.executable_name).name
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
                "executable": executable_name,
                "attempt_number": attempt_number,
                "provider_metadata": {
                    "returncode": returncode,
                    "stderr_present": bool(stderr),
                    "stderr_sha256": stderr_hash,
                },
            },
            raw_response_hash=sha256_hex(stdout or ""),
        )

    def _extract_prompt(self, request: ProviderRequest) -> str:
        for turn in request.messages:
            if turn.role == "user":
                for block in turn.content:
                    if block.type == "text":
                        return block.text
        return ""

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        raise NotImplementedError("Subclasses must implement build_command")

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement parse_output")


class ClaudeCLIAdapter(CLIProviderAdapter):
    """Adapter for the configured Claude CLI contract."""

    name = "claude_cli"
    executable_name = "claude"

    def detect_available(self) -> bool:
        path = self._find_executable()
        if not path:
            return False
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-7-sonnet-20250219",
            "claude-sonnet-4",
        ]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        if not self._executable_path:
            raise ProviderFailure(FailureMode.AUTH_FAILURE, "claude is not available", retryable=False)
        args = [self._executable_path, "--model", request.model]
        if request.messages and request.messages[0].role == "system":
            for block in request.messages[0].content:
                if block.type == "text":
                    args.extend(["--system-prompt", block.text])
        # The repository's current CLI contract carries prompt text in argv.
        # Operators must therefore include same-user process inspection in the
        # local host trust model until the upstream interface supports stdin-only.
        args.extend(["--prompt", prompt, "--output-format", "json"])
        return args

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
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
        except json.JSONDecodeError:
            return {"text": stdout.strip(), "finish_reason": "stop", "usage": {}}
        if not isinstance(data, dict):
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return {
            "text": str(data.get("response", data.get("content", ""))),
            "finish_reason": "stop",
            "usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        }


class KiloCLIAdapter(CLIProviderAdapter):
    """Adapter for the configured Kilo CLI contract."""

    name = "kilo_cli"
    executable_name = "kilo"

    def detect_available(self) -> bool:
        path = self._find_executable()
        if not path:
            return False
        try:
            result = subprocess.run(
                [path, "status"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return [
            "gpt-4", "gpt-4-turbo", "gpt-4o", "o1-preview", "o1-mini", "o3-mini",
            "claude-sonnet-4", "claude-opus-4", "gemini-2.5-flash", "step-3.7-flash",
        ]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        if not self._executable_path:
            raise ProviderFailure(FailureMode.AUTH_FAILURE, "kilo is not available", retryable=False)
        model = request.model
        if "/" not in model:
            prefixes = (
                (("gpt", "o1", "o3", "o4"), "openai"),
                (("claude",), "anthropic"),
                (("gemini",), "google"),
                (("llama",), "meta-llama"),
                (("qwen",), "qwen"),
                (("deepseek",), "deepseek"),
                (("mistral",), "mistralai"),
                (("step",), "stepfun"),
            )
            for starts, provider in prefixes:
                if model.startswith(starts):
                    model = f"{provider}/{model}"
                    break
        return [self._executable_path, "run", prompt, "-m", model, "--format", "json", "--pure"]

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
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
            if not isinstance(data, dict):
                raise ValueError("provider output must be an object")
            return {
                "text": str(data.get("content", data.get("text", ""))),
                "finish_reason": "stop",
                "usage": data.get("usage", {}) if isinstance(data.get("usage", {}), dict) else {},
            }
        except (json.JSONDecodeError, ValueError):
            content: list[str] = []
            for line in stdout.splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("type") == "content":
                    value = record.get("content")
                    if isinstance(value, str):
                        content.append(value)
            if content:
                return {"text": "".join(content), "finish_reason": "stop", "usage": {}}
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }


class CodexCLIAdapter(CLIProviderAdapter):
    """Adapter for the configured Codex CLI contract."""

    name = "codex_cli"
    executable_name = "codex"

    def detect_available(self) -> bool:
        path = self._find_executable()
        if not path:
            return False
        try:
            result = subprocess.run(
                [path, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_supported_models(self) -> list[str]:
        return ["codex-mini-latest", "o1-mini", "o1-preview", "o3-mini", "o3-preview"]

    def build_command(self, request: ProviderRequest, prompt: str) -> list[str]:
        del prompt
        if not self._executable_path:
            raise ProviderFailure(FailureMode.AUTH_FAILURE, "codex is not available", retryable=False)
        return [self._executable_path, "completions", "--model", request.model]

    def parse_output(self, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
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
        except json.JSONDecodeError:
            return {"text": stdout.strip(), "finish_reason": "stop", "usage": {}}
        if not isinstance(data, dict):
            return {
                "text": "",
                "finish_reason": "error",
                "error_class": FailureMode.PROVIDER_ERROR,
                "retryable": False,
                "protocol_valid": False,
            }
        choices = data.get("choices", [data] if "choices" not in data else [])
        if not isinstance(choices, list):
            choices = []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = first.get("text", message.get("content", data.get("text", "")))
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return {
            "text": str(content),
            "finish_reason": first.get("finish_reason", "stop") if first else "stop",
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }


__all__ = ["CLIProviderAdapter", "ClaudeCLIAdapter", "KiloCLIAdapter", "CodexCLIAdapter"]
