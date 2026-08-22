from __future__ import annotations

import json
from unittest.mock import patch

from wilson_eval3ngine.domain.contracts import ContentBlock, ConversationTurn, ProviderRequest
from wilson_eval3ngine.providers.cli_base import CLIProviderAdapter, ClaudeCLIAdapter


def _request() -> ProviderRequest:
    return ProviderRequest(
        run_id="run-cli-security",
        model_config_id="cfg-cli-security",
        provider="claude_cli",
        model="claude-sonnet-4",
        messages=[
            ConversationTurn(
                role="user",
                content=[ContentBlock(text="review this request")],
            )
        ],
    )


def test_cli_response_metadata_does_not_disclose_stderr_or_absolute_path() -> None:
    adapter = ClaudeCLIAdapter()
    adapter._executable_path = "/private/operator/bin/claude"
    secret_stderr = "token=super-secret /home/operator/private/config.json"

    with patch.object(adapter, "_execute_cli") as execute:
        execute.return_value = (1, "", secret_stderr, 12.0)
        response = adapter.execute(_request())

    metadata = response.metadata
    provider_metadata = metadata["provider_metadata"]
    serialized = json.dumps(metadata)
    assert metadata["executable"] == "claude"
    assert "/private/operator" not in serialized
    assert "super-secret" not in serialized
    assert secret_stderr not in serialized
    assert provider_metadata["stderr_present"] is True
    assert len(provider_metadata["stderr_sha256"]) == 64


def test_generic_subprocess_exception_is_not_returned_verbatim() -> None:
    adapter = CLIProviderAdapter()
    sensitive = "failure in /home/operator/private with token=super-secret"

    with patch("subprocess.run", side_effect=RuntimeError(sensitive)):
        returncode, stdout, stderr, _elapsed = adapter._execute_cli(["safe-cli"])

    assert returncode == -1
    assert stdout == ""
    assert stderr == "execution_failed"
    assert sensitive not in stderr


def test_cli_execution_is_explicitly_shell_free() -> None:
    adapter = CLIProviderAdapter()

    with patch("subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        run.return_value.stderr = ""
        adapter._execute_cli(["safe-cli"], input_data="payload")

    assert run.call_args.kwargs["shell"] is False
    assert run.call_args.kwargs["check"] is False
