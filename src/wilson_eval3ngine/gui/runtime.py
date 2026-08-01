"""Runtime composition for the hardened GUI application.

This module keeps narrowly-scoped compatibility fixes outside the legacy
monolith while the new application boundary is incrementally extracted and
tested.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from . import server as legacy
from .application import (
    ChartGenerateRequest,
    _RESPONSE_SECURITY_HEADERS,
    _load_telemetry,
    _save_telemetry,
    app,
)

# The page uses dynamic progress widths and a movable/resizable chart window.
# Scripts remain same-origin only; inline JavaScript execution is never enabled.
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


def _remove_route(path: str, method: str) -> None:
    """Remove one inherited route before registering a corrected adapter."""

    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and method in (getattr(route, "methods", None) or set())
        )
    ]


_remove_route("/api/charts/runs", "GET")
_remove_route("/api/charts/generate", "POST")


def _normalize_legacy_result(result: Any) -> dict[str, Any]:
    if isinstance(result, JSONResponse):
        return json.loads(result.body)
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="The chart subsystem returned an invalid response",
        )
    return result


def _existing_chart_runs() -> list[dict[str, Any]]:
    """List chart artifacts without auto-generating sample content.

    The legacy gallery helper creates sample charts as a side effect when the
    directory is empty. Inventory reads must be idempotent, so this runtime
    adapter scans only files that already exist.
    """

    telemetry = _load_telemetry()
    telemetry_by_id = {
        str(entry.get("runId")): entry
        for entry in telemetry
        if entry.get("runId")
    }
    runs: list[dict[str, Any]] = []

    if not legacy.CHARTS_DIR.exists():
        return runs

    for run_dir in sorted(
        legacy.CHARTS_DIR.iterdir(),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    ):
        if not run_dir.is_dir():
            continue

        run_id = run_dir.name
        telemetry_entry = telemetry_by_id.get(run_id, {})
        deleted = telemetry_entry.get("deletedCharts", [])
        if not isinstance(deleted, list):
            deleted = []
        if "__all__" in deleted:
            continue

        charts: list[dict[str, Any]] = []
        for chart_file in sorted(run_dir.glob("*.png")):
            chart_name = chart_file.stem
            if chart_name in deleted:
                continue
            metadata = legacy._CHART_METADATA.get(chart_name, {})
            charts.append(
                {
                    "name": chart_name,
                    "displayName": metadata.get(
                        "name",
                        chart_name.replace("_", " ").title(),
                    ),
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", "General"),
                    "url": f"/static/charts/{run_id}/{chart_name}.png",
                    "size_bytes": chart_file.stat().st_size,
                }
            )

        if not charts:
            continue

        runs.append(
            {
                "runId": run_id,
                "charts": charts,
                "totalCharts": len(charts),
                "isSample": bool(telemetry_entry.get("isSample"))
                or "sample" in run_id.lower(),
                "models": telemetry_entry.get("models", []),
                "prompts": telemetry_entry.get("prompts", []),
                "promptPackage": telemetry_entry.get("promptPackage", ""),
                "type": telemetry_entry.get("type", "report_generation"),
                "startedAt": telemetry_entry.get("startedAt"),
                "finishedAt": telemetry_entry.get("finishedAt"),
                "returncode": telemetry_entry.get("returncode"),
                "error": telemetry_entry.get("error"),
                "deletedCharts": deleted,
            }
        )

    return runs


def _run_has_evaluation_data(run: dict[str, Any]) -> bool:
    """Confirm that chart generation can use real run evidence."""

    sidecars = run.get("evaluationSidecars", [])
    for name in sidecars if isinstance(sidecars, list) else []:
        safe = legacy._validate_report_filename(str(name))
        if safe and (legacy.REPORTS_DIR / safe).is_file():
            return True

    run_id = str(run.get("runId") or "")
    batch_id = str(run.get("batchId") or "")
    models = {str(model) for model in run.get("models", [])}
    for evaluation in legacy._load_evaluation_jsons():
        if evaluation.get("runId") == run_id:
            return True
        if batch_id and evaluation.get("batchId") == batch_id:
            return True
        if str(evaluation.get("model") or "") in models:
            return True

    return False


@app.get("/api/charts/runs")
async def list_chart_runs() -> dict[str, Any]:
    return {"runs": _existing_chart_runs()}


@app.post("/api/charts/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_charts(payload: ChartGenerateRequest) -> dict[str, Any]:
    """Generate a chart set only when that run has none.

    Existing artifacts are returned unchanged. New charts are generated only
    from real evaluation sidecars; synthetic sample fallback is not permitted
    through the operator GUI.
    """

    existing = next(
        (
            entry
            for entry in _existing_chart_runs()
            if entry.get("runId") == payload.run_id and entry.get("charts")
        ),
        None,
    )
    if existing:
        return {
            "runId": payload.run_id,
            "generated": 0,
            "reused": True,
            "charts": {
                chart["name"]: chart["url"]
                for chart in existing.get("charts", [])
            },
        }

    telemetry = _load_telemetry()
    run = next(
        (entry for entry in telemetry if entry.get("runId") == payload.run_id),
        None,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if "__all__" in (run.get("deletedCharts") or []):
        raise HTTPException(
            status_code=409,
            detail="This run's charts were intentionally removed",
        )
    if not _run_has_evaluation_data(run):
        raise HTTPException(
            status_code=409,
            detail="This run has no evaluation sidecar data available for chart generation",
        )

    chart_urls = await asyncio.to_thread(
        legacy._generate_charts_for_run_sync,
        payload.run_id,
        list(run.get("models", [])),
        list(run.get("prompts", [])),
    )
    if not chart_urls:
        raise HTTPException(
            status_code=422,
            detail="No chart could be produced from this run's evaluation data",
        )

    for entry in telemetry:
        if entry.get("runId") == payload.run_id:
            entry["chartUrls"] = chart_urls
            entry["deletedCharts"] = [
                name
                for name in entry.get("deletedCharts", [])
                if name not in chart_urls
            ]
            break
    _save_telemetry(telemetry)

    return {
        "runId": payload.run_id,
        "generated": len(chart_urls),
        "reused": False,
        "charts": chart_urls,
    }


@app.delete("/api/charts/runs/{run_id}/all")
async def delete_chart_run(run_id: str) -> dict[str, Any]:
    return _normalize_legacy_result(await legacy.delete_chart_run(run_id))


@app.delete("/api/charts/runs/{run_id}/{chart_name}")
async def delete_chart(run_id: str, chart_name: str) -> dict[str, Any]:
    return _normalize_legacy_result(await legacy.delete_chart(run_id, chart_name))
