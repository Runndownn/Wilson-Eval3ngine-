"""Runtime HTML overlay for incremental GUI interaction improvements.

The repository serves a static index document.  This module injects versioned
same-origin assets through a first-match FastAPI route so a focused UX repair
can be rolled back without rewriting the large baseline document.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

_UX4_STYLESHEET = '<link rel="stylesheet" href="/static/ux4.css?v=20260801-ux4">'
_UX4_SCRIPT = '<script src="/static/ux4.js?v=20260801-ux4" defer></script>'


def _render_overlay(index_path: Path) -> str:
    """Return the baseline index with one idempotent same-origin overlay."""

    try:
        document = index_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - deployment failure path
        raise HTTPException(status_code=503, detail="GUI index is unavailable") from exc

    if _UX4_STYLESHEET not in document:
        document = document.replace("</head>", f"  {_UX4_STYLESHEET}\n</head>", 1)
    if _UX4_SCRIPT not in document:
        document = document.replace("</body>", f"  {_UX4_SCRIPT}\n</body>", 1)
    return document


def install_ux_overlay(app: FastAPI, static_dir: Path) -> None:
    """Install the enhanced index route before the inherited root route."""

    if getattr(app.state, "we3_ux_overlay_installed", False):
        return

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
