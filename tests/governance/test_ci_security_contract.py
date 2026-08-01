from __future__ import annotations

import re
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_does_not_suppress_quality_or_security_failures() -> None:
    text = _workflow_text()
    assert "make lint || true" not in text
    assert "continue-on-error: true" not in text
    assert 'exit-code: "1"' in text


def test_ci_does_not_pipe_network_downloads_into_execution() -> None:
    text = _workflow_text()
    forbidden = (
        r"curl\b[^\n|]*\|",
        r"wget\b[^\n|]*\|",
        r"wget\b[^\n]*-O\s+-",
    )
    for pattern in forbidden:
        assert re.search(pattern, text) is None, pattern


def test_all_referenced_actions_are_commit_pinned() -> None:
    text = _workflow_text()
    action_refs = re.findall(r"^\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE)
    assert action_refs
    for action_ref in action_refs:
        _, separator, revision = action_ref.rpartition("@")
        assert separator == "@"
        assert re.fullmatch(r"[0-9a-f]{40}", revision), action_ref


def test_main_builds_receive_signed_provenance() -> None:
    text = _workflow_text()
    assert "attestations: write" in text
    assert "id-token: write" in text
    assert "actions/attest-build-provenance@" in text
    assert "subject-path: release/dist/*" in text


def test_release_attestation_depends_on_full_validation() -> None:
    text = _workflow_text()
    attest_job = text.split("  attest-build:", 1)[1].split("  backup-verification:", 1)[0]
    assert "needs: validate-foundation" in attest_job
    assert "github.event_name == 'push'" in attest_job
    assert "github.ref == 'refs/heads/main'" in attest_job
