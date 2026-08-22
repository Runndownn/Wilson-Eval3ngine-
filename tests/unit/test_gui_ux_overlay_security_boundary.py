from __future__ import annotations

from fastapi import FastAPI

from wilson_eval3ngine.gui import server as legacy
from wilson_eval3ngine.gui.ux_overlay import install_ux_overlay


def test_ux_overlay_does_not_mutate_secret_transport(tmp_path, monkeypatch) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<!doctype html><html><head></head><body></body></html>",
        encoding="utf-8",
    )

    sentinel = object()
    monkeypatch.setattr(legacy, "store_api_key_temp_file", sentinel)

    app = FastAPI()
    install_ux_overlay(app, static_dir)

    assert legacy.store_api_key_temp_file is sentinel
    assert app.state.we3_ux_overlay_installed is True


def test_ux_overlay_is_idempotent(tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<!doctype html><html><head></head><body></body></html>",
        encoding="utf-8",
    )

    app = FastAPI()
    install_ux_overlay(app, static_dir)
    route_count = len(app.router.routes)
    install_ux_overlay(app, static_dir)

    assert len(app.router.routes) == route_count
