from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI

from wilson_eval3ngine.gui import application
from wilson_eval3ngine.gui.application import EndpointCreate
from wilson_eval3ngine.gui.ux_overlay import _render_overlay, install_ux_overlay


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPOSITORY_ROOT / "gui" / "static"


def test_overlay_injects_versioned_same_origin_assets_once(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html><head></head><body><main>GUI</main></body></html>", encoding="utf-8")

    first = _render_overlay(index)
    index.write_text(first, encoding="utf-8")
    second = _render_overlay(index)

    assert first.count("/static/ux4.css?v=20260801-ux4") == 1
    assert first.count("/static/ux4.js?v=20260801-ux4") == 1
    assert second.count("/static/ux4.css?v=20260801-ux4") == 1
    assert second.count("/static/ux4.js?v=20260801-ux4") == 1


def test_overlay_route_is_first_match_and_idempotent(tmp_path: Path) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    app = FastAPI()

    install_ux_overlay(app, static)
    install_ux_overlay(app, static)

    matching = [route for route in app.router.routes if getattr(route, "path", None) == "/"]
    assert len(matching) == 1
    assert matching[0].name == "enhanced_gui_index"
    assert app.router.routes[0] is matching[0]


def test_ux4_contract_contains_requested_interactions() -> None:
    script = (STATIC_ROOT / "ux4.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_ROOT / "ux4.css").read_text(encoding="utf-8")

    assert "const PAGE_SIZE = 8" in script
    assert 'timedApi("/api/health"' in script
    assert "Authentication rejected" in script
    assert "Provider rate limited the test" in script
    assert "Connection timed out" in script
    assert 'button.id = "chart-window-delete"' in script
    assert "Generating the complete synthetic chart catalogue" in script
    assert "pdf-reader-toolbar" in script
    assert "layout.prepend(summary)" in script
    assert "#model-grid" in stylesheet
    assert "grid-template-columns: repeat(4" in stylesheet
    assert ".run-summary-topbar" in stylesheet
    assert ".pdf-document-frame" in stylesheet


def test_api_key_is_encrypted_at_rest_and_never_returned(
    tmp_path: Path,
    monkeypatch,
) -> None:
    endpoints_file = tmp_path / "endpoints.json"
    monkeypatch.setattr(application.legacy, "ENDPOINTS_FILE", endpoints_file)
    monkeypatch.setattr(application, "_normalize_endpoint_url", lambda _provider, value: value)
    monkeypatch.setattr(application.legacy, "_validate_api_key", lambda _provider, _key: None)
    monkeypatch.setattr(application.legacy, "encrypt_api_key", lambda value: f"cipher::{len(value)}")
    monkeypatch.setattr(application.legacy, "_audit_log", lambda *_args, **_kwargs: None)

    secret = "nvapi-test-secret-value"
    result = asyncio.run(
        application._create_endpoint(
            EndpointCreate.model_validate(
                {
                    "name": "NVIDIA test",
                    "url": "https://integrate.api.nvidia.com/v1",
                    "provider": "nvidia",
                    "apiKey": secret,
                }
            )
        )
    )

    persisted_text = endpoints_file.read_text(encoding="utf-8")
    persisted = json.loads(persisted_text)

    assert secret not in persisted_text
    assert persisted[0]["encryptedApiKey"] == f"cipher::{len(secret)}"
    assert "encryptedApiKey" not in result
    assert "apiKey" not in result
