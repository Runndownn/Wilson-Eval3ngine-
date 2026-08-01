"""Runtime composition for the hardened GUI application.

This module keeps compatibility fixes outside the legacy monolith while the
new application boundary is incrementally extracted and tested.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from . import server as legacy
from .application import (
    ChartGenerateRequest,
    _RESPONSE_SECURITY_HEADERS,
    _load_telemetry,
    app,
)

# The current page uses a small number of inline layout declarations and
# dynamic progress widths. Scripts remain same-origin only; inline JavaScript
# is never enabled. This scoped style exception is temporary and documented in
# the interface design log.
_RESPONSE_SECURITY_HEADERS["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-src 'self'; "
    "worker-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'"
)


@app.post("/api/charts/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_charts(payload: ChartGenerateRequest) -> dict[str, Any]:
    """Regenerate charts for one known telemetry run.

    The legacy chart helper expects camelCase ``runId``. Keeping the adapter in
    this runtime layer prevents the old implementation detail from leaking into
    the validated public contract.
    """

    run = next(
        (entry for entry in _load_telemetry() if entry.get("runId") == payload.run_id),
        None,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    result = await legacy.generate_charts_endpoint({"runId": payload.run_id})
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Chart generator returned an invalid response")
    return result
