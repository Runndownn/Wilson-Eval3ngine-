"""Runtime composition overlays for focused GUI hardening.

The repository serves a static index document and retains selected legacy
helpers while the application boundary is extracted. This module installs
versioned same-origin assets and replaces the legacy regular-file credential
handoff before the server begins accepting requests.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from . import server as legacy
from .secret_transport import store_api_key_pipe

_STYLESHEETS = (
    '<link rel="stylesheet" href="/static/ux4.css?v=20260801-ux4">',
    '<link rel="stylesheet" href="/static/ux5.css?v=20260801-ux5">',
    '<link rel="stylesheet" href="/static/ux6.css?v=20260801-ux6">',
)
_SCRIPTS = (
    '<script src="/static/ux4.js?v=20260801-ux4" defer></script>',
    '<script src="/static/ux5.js?v=20260801-ux5" defer></script>',
    '<script src="/static/ux6.js?v=20260801-ux6" defer></script>',
)


def _render_overlay(index_path: Path) -> str:
    """Return the baseline index with each versioned asset injected once."""

    try:
        document = index_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - deployment failure path
        raise HTTPException(status_code=503, detail="GUI index is unavailable") from exc

    for stylesheet in _STYLESHEETS:
        if stylesheet not in document:
            document = document.replace("</head>", f"  {stylesheet}\n</head>", 1)
    for script in _SCRIPTS:
        if script not in document:
            document = document.replace("</body>", f"  {script}\n</body>", 1)
    return document


def install_ux_overlay(app: FastAPI, static_dir: Path) -> None:
    """Install hardened runtime adapters before the listener starts."""

    if getattr(app.state, "we3_ux_overlay_installed", False):
        return

    # Application job execution resolves this legacy helper at invocation time.
    # Preserve the established call contract while replacing the regular-file
    # implementation with a one-shot FIFO that never stores plaintext at rest.
    legacy.store_api_key_temp_file = store_api_key_pipe

    index_path = static_dir / "index.html"

    async def enhanced_index() -> HTMLResponse:
        return HTMLResponse(
            _render_overlay(index_path),
            headers={"Cache-Control": "no-store"},
        )

    route = APIRoute(
        path="/",
        endpoint=enhanced_index,
        methods=["GET"],
        name="enhanced_gui_index",
        include_in_schema=False,
    )
    app.router.routes.insert(0, route)
    app.state.we3_ux_overlay_installed = True
