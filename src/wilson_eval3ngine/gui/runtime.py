"""Runtime composition for the hardened GUI application.

This module keeps narrowly-scoped compatibility fixes outside the legacy
monolith while the new application boundary is incrementally extracted and
tested.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
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

# ---------------------------------------------------------------------------
# Provider egress boundary
# ---------------------------------------------------------------------------

_ALWAYS_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.azure.internal",
    "metadata.azure.net",
    "metadata.amazonaws.com",
    "metadata.cloud.yandex.net",
    "metadata.internal",
}
_LOCAL_PROVIDER_ENV = "WE3_GUI_ALLOW_LOCAL_PROVIDERS"


def _local_providers_enabled() -> bool:
    return os.environ.get(_LOCAL_PROVIDER_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _is_forbidden_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return whether an address is never a valid provider destination."""

    return (
        address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


def _resolve_destination(hostname: str, port: int) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    """Resolve all connection candidates and fail closed on ambiguity."""

    try:
        records = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise httpx.ConnectError("Provider hostname could not be resolved") from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for record in records:
        try:
            address = ipaddress.ip_address(record[4][0])
        except ValueError as exc:
            raise httpx.ConnectError("Provider hostname returned an invalid address") from exc
        if address not in addresses:
            addresses.append(address)

    if not addresses:
        raise httpx.ConnectError("Provider hostname resolved to no addresses")
    return tuple(addresses)


def _validate_outbound_url(value: str | httpx.URL) -> None:
    """Revalidate a provider URL immediately before each HTTP dispatch.

    Local/private destinations are denied by default and require the explicit
    WE3_GUI_ALLOW_LOCAL_PROVIDERS=1 deployment decision. Link-local, metadata,
    multicast, unspecified, and reserved ranges remain blocked even in local
    mode. Every resolved address must satisfy the same policy.
    """

    parsed = urlparse(str(value))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise httpx.UnsupportedProtocol("Provider URL must use HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise httpx.InvalidURL("Embedded provider credentials are prohibited")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in _ALWAYS_BLOCKED_HOSTS:
        raise httpx.ConnectError("Cloud metadata destinations are prohibited")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolve_destination(hostname, port)
    local_enabled = _local_providers_enabled()

    for address in addresses:
        if _is_forbidden_address(address):
            raise httpx.ConnectError("Provider destination is in a prohibited address range")
        if (address.is_private or address.is_loopback) and not local_enabled:
            raise httpx.ConnectError(
                f"Private provider destinations require {_LOCAL_PROVIDER_ENV}=1"
            )


class _PolicyAsyncClient(httpx.AsyncClient):
    """HTTP client enforcing connection-time destination policy.

    Redirect following is disabled so credentials are never automatically
    replayed to a Location target. Callers must explicitly validate and issue a
    subsequent request if redirect support is ever introduced.
    """

    async def request(self, method: str, url: str | httpx.URL, *args: Any, **kwargs: Any) -> httpx.Response:
        await asyncio.to_thread(_validate_outbound_url, url)
        kwargs["follow_redirects"] = False
        return await super().request(method, url, *args, **kwargs)


def _create_policy_http_client(
    timeout: float | httpx.Timeout = legacy._DEFAULT_HTTP_TIMEOUT,
) -> httpx.AsyncClient:
    return _PolicyAsyncClient(
        timeout=timeout,
        verify=True,
        http2=True,
        limits=legacy._HTTP_LIMITS,
        trust_env=False,
        headers=legacy._SECURITY_HEADERS,
        follow_redirects=False,
    )


# All legacy endpoint-discovery and test paths resolve this symbol at call time.
legacy._create_secure_http_client = _create_policy_http_client


# Secret values are never suitable log identifiers. Preserve the helper API
# while ensuring every current and future caller receives a constant marker.
def _fully_redact_api_key(_api_key: str, visible_chars: int = 0) -> str:
    del visible_chars
    return "[redacted]"


legacy.mask_api_key = _fully_redact_api_key

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
    """List chart artifacts without auto-generating content.

    Inventory reads are strictly idempotent. Deleted charts remain hidden until
    an operator explicitly requests regeneration for that run.
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
            # Clean up empty run directory so empty frames don't persist.
            # A run-window frame remains visible only while it contains
            # one or more charts.
            try:
                run_dir.rmdir()
            except OSError:
                pass
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


def _clear_chart_deletion_markers(run_id: str, telemetry: list[dict[str, Any]]) -> bool:
    """Clear persisted deletion markers only for an explicit regeneration."""

    changed = False
    for entry in telemetry:
        if entry.get("runId") == run_id and entry.get("deletedCharts"):
            entry["deletedCharts"] = []
            changed = True
    deleted_runs = getattr(legacy, "_deleted_chart_runs", None)
    if isinstance(deleted_runs, set):
        deleted_runs.discard(run_id)
    return changed


def _expected_chart_names() -> set[str]:
    names = getattr(legacy, "_CHART_ORDER", ())
    return {str(name) for name in names if name}


@app.get("/api/charts/runs")
async def list_chart_runs() -> dict[str, Any]:
    return {"runs": _existing_chart_runs()}


@app.post("/api/charts/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_charts(payload: ChartGenerateRequest) -> dict[str, Any]:
    """Generate or restore charts for one evidence run.

    Refresh never generates content. This explicit mutation is allowed to clear
    that run's deletion markers, restore deleted charts, and fill a partial set.
    A complete undeleted set is reused without unnecessary rendering.
    """

    telemetry = _load_telemetry()
    run = next(
        (entry for entry in telemetry if entry.get("runId") == payload.run_id),
        None,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not _run_has_evaluation_data(run):
        raise HTTPException(
            status_code=409,
            detail="This run has no evaluation sidecar data available for chart generation",
        )

    existing_run = next(
        (entry for entry in _existing_chart_runs() if entry.get("runId") == payload.run_id),
        None,
    )
    existing_names = {
        str(chart.get("name"))
        for chart in (existing_run or {}).get("charts", [])
        if chart.get("name")
    }
    deleted_markers = run.get("deletedCharts") or []
    expected = _expected_chart_names()
    if existing_names and expected and expected.issubset(existing_names) and not deleted_markers:
        return {
            "runId": payload.run_id,
            "generated": 0,
            "reused": True,
            "charts": {
                chart["name"]: chart["url"]
                for chart in (existing_run or {}).get("charts", [])
            },
        }

    if _clear_chart_deletion_markers(payload.run_id, telemetry):
        _save_telemetry(telemetry)

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

    telemetry = _load_telemetry()
    for entry in telemetry:
        if entry.get("runId") == payload.run_id:
            entry["chartUrls"] = chart_urls
            entry["deletedCharts"] = []
            break
    _save_telemetry(telemetry)

    return {
        "runId": payload.run_id,
        "generated": len(chart_urls),
        "reused": False,
        "charts": chart_urls,
    }


@app.post("/api/charts/demo", status_code=status.HTTP_202_ACCEPTED)
async def generate_demo_charts() -> dict[str, Any]:
    """Generate a clearly-labelled synthetic demonstration chart set.

    Demonstration data is created only through this explicit endpoint. It never
    runs during inventory refresh and never masquerades as a real evidence run.
    """

    deleted_runs = getattr(legacy, "_deleted_chart_runs", None)
    if isinstance(deleted_runs, set):
        deleted_runs.discard("sample-charts")

    result = await asyncio.to_thread(
        legacy._generate_charts_impl,
        {"runId": "sample-charts"},
    )
    normalized = _normalize_legacy_result(result)
    chart_urls = normalized.get("charts") or {}
    if not isinstance(chart_urls, dict) or not chart_urls:
        raise HTTPException(
            status_code=422,
            detail="Demonstration chart generation produced no artifacts",
        )
    return {
        "runId": "sample-charts",
        "generated": len(chart_urls),
        "charts": chart_urls,
        "isSample": True,
    }


@app.delete("/api/charts/runs/all")
async def delete_all_chart_runs() -> dict[str, Any]:
    return _normalize_legacy_result(await legacy.delete_all_chart_runs())


@app.delete("/api/charts/runs/{run_id}/all")
async def delete_chart_run(run_id: str) -> dict[str, Any]:
    return _normalize_legacy_result(await legacy.delete_chart_run(run_id))


@app.delete("/api/charts/runs/{run_id}/{chart_name}")
async def delete_chart(run_id: str, chart_name: str) -> dict[str, Any]:
    return _normalize_legacy_result(await legacy.delete_chart(run_id, chart_name))
