from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from wilson_eval3ngine.gui import application
from wilson_eval3ngine.gui.runtime import app


def test_runtime_registers_one_chart_generation_route() -> None:
    routes = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) == "/api/charts/generate"
        and "POST" in (getattr(route, "methods", None) or set())
    ]
    assert len(routes) == 1


def test_health_response_has_browser_security_headers() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-inline'" not in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_job_contract_normalizes_duplicates_and_counts_work() -> None:
    payload = application.JobCreate.model_validate(
        {
            "models": ["model-a", "model-a", "model-b"],
            "prompts": [" first ", "second", "third"],
            "promptCount": 2,
            "executionMode": "batch",
            "batchSize": 1,
        }
    )

    assert payload.models == ["model-a", "model-b"]
    assert payload.prompts == ["first", "second"]
    assert payload.prompt_count == 2
    assert payload.execution_mode == "batch"


def test_job_contract_rejects_resource_exhaustion() -> None:
    with pytest.raises(ValidationError, match="work-item limit"):
        application.JobCreate.model_validate(
            {
                "models": [f"model-{index}" for index in range(20)],
                "prompts": [f"prompt-{index}" for index in range(60)],
            }
        )


def test_invocations_are_grouped_by_endpoint_and_batched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        application,
        "_load_models",
        lambda: [
            {"id": "a", "endpointId": "ep-1"},
            {"id": "b", "endpointId": "ep-1"},
            {"id": "c", "endpointId": "ep-2"},
        ],
    )
    monkeypatch.setattr(
        application,
        "_load_endpoints",
        lambda: [
            {"id": "ep-1", "name": "Primary", "provider": "ollama", "available": True},
            {"id": "ep-2", "name": "Remote", "provider": "openai", "available": True},
        ],
    )
    request = application.JobCreate.model_validate(
        {
            "models": ["a", "b", "c"],
            "prompts": ["evaluate"],
            "executionMode": "batch",
            "batchSize": 1,
        }
    )

    invocations, warnings = application._build_invocations(request)

    assert warnings == []
    assert [(item["endpoint_id"], item["models"]) for item in invocations] == [
        ("ep-1", ["a"]),
        ("ep-1", ["b"]),
        ("ep-2", ["c"]),
    ]


def test_atomic_json_write_is_private_and_complete(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    payload = {"job": {"status": "queued", "prompts": ["one", "two"]}}

    application._atomic_write_json(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert os.stat(target).st_mode & 0o077 == 0
    assert not list(tmp_path.glob("*.tmp"))


def test_restart_marks_nonterminal_jobs_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            {
                "active": {"status": "running", "updated_at": "old"},
                "done": {"status": "completed", "updated_at": "old"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(application.legacy, "JOBS_FILE", jobs_file)

    asyncio.run(application._reconcile_interrupted_jobs())

    jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
    assert jobs["active"]["status"] == "interrupted"
    assert jobs["active"]["error"]
    assert jobs["done"]["status"] == "completed"


def test_endpoint_url_rejects_public_plaintext_http() -> None:
    with pytest.raises(Exception) as captured:
        application._normalize_endpoint_url("openai", "http://example.com/v1")

    assert getattr(captured.value, "status_code", None) == 422


def test_endpoint_sanitization_removes_credentials() -> None:
    sanitized = application._sanitize_endpoint(
        {
            "id": "ep-1",
            "name": "Provider",
            "apiKey": "plain",
            "encryptedApiKey": "encrypted",
            "keyFile": "/tmp/key",
        }
    )

    assert sanitized == {"id": "ep-1", "name": "Provider"}
