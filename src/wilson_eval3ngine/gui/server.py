"""FastAPI + WebSocket backend for Wilson Eval3ngine GUI."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import secrets
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

logger = logging.getLogger("we3.gui")

app = FastAPI(title="Wilson Eval3ngine GUI")

# Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GUI_STATIC_DIR = WORKSPACE_ROOT / "gui" / "static"
REPORTS_DIR = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
GUI_DATA_DIR = WORKSPACE_ROOT / "gui" / "data"

# Ensure directories exist
GUI_STATIC_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GUI_DATA_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS_FILE = GUI_DATA_DIR / "endpoints.json"
MODELS_FILE = GUI_DATA_DIR / "models.json"
TELEMETRY_FILE = GUI_DATA_DIR / "telemetry.json"
PROMPT_PACKAGES_FILE = GUI_DATA_DIR / "prompt_packages.json"


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_endpoints() -> list[dict[str, Any]]:
    return _load_json(ENDPOINTS_FILE, [])


def _save_endpoints(endpoints: list[dict[str, Any]]) -> None:
    _save_json(ENDPOINTS_FILE, endpoints)


def _get_models() -> list[dict[str, Any]]:
    return _load_json(MODELS_FILE, [])


def _save_models(models: list[dict[str, Any]]) -> None:
    _save_json(MODELS_FILE, models)


def _get_telemetry() -> list[dict[str, Any]]:
    return _load_json(TELEMETRY_FILE, [])


def _save_telemetry(telemetry: list[dict[str, Any]]) -> None:
    _save_json(TELEMETRY_FILE, telemetry)


def _add_telemetry_entry(entry: dict[str, Any]) -> None:
    telemetry = _get_telemetry()
    telemetry.insert(0, entry)
    _save_telemetry(telemetry)


# ---------------------------------------------------------------------------
# Prompt packages
# ---------------------------------------------------------------------------

def _get_prompt_packages() -> list[dict[str, Any]]:
    data = _load_json(PROMPT_PACKAGES_FILE, {})
    return data.get("prompt_packages", [])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "wilson-eval3ngine-gui"}


# ---------------------------------------------------------------------------
# Endpoints CRUD
# ---------------------------------------------------------------------------

@app.get("/api/endpoints")
async def list_endpoints() -> dict[str, Any]:
    return {"endpoints": _get_endpoints()}


@app.post("/api/endpoints")
async def create_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    endpoints = _get_endpoints()
    endpoint = {
        "id": payload.get("id") or f"ep_{uuid.uuid4().hex[:8]}",
        "name": payload.get("name", "Unnamed"),
        "url": payload.get("url", ""),
        "apiKey": payload.get("apiKey") or None,
        "provider": payload.get("provider", "ollama"),
        "createdAt": _now_iso(),
        "available": None,
        "lastTested": None,
    }
    endpoints.append(endpoint)
    _save_endpoints(endpoints)
    return {"endpoint": endpoint}


@app.delete("/api/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str) -> dict[str, Any]:
    endpoints = [ep for ep in _get_endpoints() if ep.get("id") != endpoint_id]
    _save_endpoints(endpoints)
    # Also remove models tied to this endpoint
    models = [m for m in _get_models() if m.get("endpointId") != endpoint_id]
    _save_models(models)
    return {"deleted": endpoint_id}


@app.post("/api/endpoints/{endpoint_id}/test")
async def test_endpoint(endpoint_id: str) -> dict[str, Any]:
    endpoints = _get_endpoints()
    ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
    if not ep:
        return JSONResponse({"error": "Endpoint not found"}, status_code=404)

    url = ep.get("url", "").rstrip("/")
    provider = ep.get("provider", "ollama")
    api_key = ep.get("apiKey")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "ollama":
                test_url = f"{url}/api/tags"
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(test_url, headers=headers)
                data = resp.json()
                models_found = [m.get("name") for m in data.get("models", [])]
                _update_endpoint_status(endpoint_id, True)
                return {"ok": True, "provider": "ollama", "models": models_found}
            elif provider == "openai":
                test_url = f"{url}/models"
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers)
                data = resp.json()
                models_found = [m.get("id") for m in data.get("data", [])]
                _update_endpoint_status(endpoint_id, True)
                return {"ok": True, "provider": "openai", "models": models_found}
            elif provider == "kilo":
                test_url = f"{url}/models"
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("id") for m in data.get("data", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "kilo", "models": models_found}
                _update_endpoint_status(endpoint_id, False)
                return {"ok": False, "provider": "kilo", "error": f"HTTP {resp.status_code}"}
            else:
                test_url = url + "/" if not url.endswith("/") else url
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers, follow_redirects=True)
                _update_endpoint_status(endpoint_id, True)
                return {"ok": True, "provider": provider, "status": resp.status_code}
    except Exception as exc:
        _update_endpoint_status(endpoint_id, False)
        return {"ok": False, "error": str(exc)}


def _update_endpoint_status(endpoint_id: str, available: bool) -> None:
    endpoints = _get_endpoints()
    for ep in endpoints:
        if ep.get("id") == endpoint_id:
            ep["available"] = available
            ep["lastTested"] = _now_iso()
            break
    _save_endpoints(endpoints)


@app.get("/api/endpoints/status")
async def endpoints_status() -> dict[str, Any]:
    """Test all endpoints and return availability status."""
    endpoints = _get_endpoints()
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            api_key = ep.get("apiKey")
            available = False
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                elif provider == "openai":
                    test_url = f"{url}/models"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                elif provider == "kilo":
                    test_url = f"{url}/models"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                else:
                    test_url = url + "/" if not url.endswith("/") else url
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers, follow_redirects=True)
                    available = resp.status_code < 400
            except Exception:
                available = False
            results.append({
                "id": ep.get("id"),
                "name": ep.get("name"),
                "available": available,
                "provider": provider,
            })
    return {"statuses": results}


@app.post("/api/endpoints/auto-detect")
async def auto_detect_endpoints() -> dict[str, Any]:
    """Auto-detect local Ollama, OpenAI-compatible, and Kilo Gateway endpoints."""
    found: list[dict[str, Any]] = []

    candidates = [
        ("http://localhost:11434", "ollama", "Local Ollama"),
        ("http://127.0.0.1:11434", "ollama", "Local Ollama"),
        ("http://localhost:8000", "openai", "Local OpenAI-compatible"),
        ("http://127.0.0.1:8000", "openai", "Local OpenAI-compatible"),
        ("http://localhost:5000", "openai", "Local OpenAI-compatible"),
        ("http://127.0.0.1:5000", "openai", "Local OpenAI-compatible"),
        ("http://localhost:3000", "openai", "Local OpenAI-compatible"),
        ("http://127.0.0.1:3000", "openai", "Local OpenAI-compatible"),
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for url, provider, name in candidates:
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                else:
                    test_url = f"{url}/models"
                resp = await client.get(test_url)
                if resp.status_code == 200:
                    found.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "url": url,
                        "apiKey": None,
                        "provider": provider,
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
            except Exception:
                continue

    # Merge with existing without duplicates by URL
    existing = _get_endpoints()
    existing_urls = {e.get("url") for e in existing}
    for ep in found:
        if ep["url"] not in existing_urls:
            existing.append(ep)
            existing_urls.add(ep["url"])
    _save_endpoints(existing)
    return {"endpoints": found, "total": len(existing)}


# ---------------------------------------------------------------------------
# Models CRUD + auto-detect
# ---------------------------------------------------------------------------

@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    models = _get_models()
    endpoints = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints}
    enriched = []
    for m in models:
        ep = endpoint_map.get(m.get("endpointId"))
        enriched.append({
            **m,
            "endpointName": ep.get("name") if ep else None,
            "endpointUrl": ep.get("url") if ep else None,
            "provider": ep.get("provider") if ep else m.get("provider"),
            "endpointAvailable": ep.get("available") if ep else None,
        })
    return {"models": enriched}


@app.post("/api/models")
async def create_model(payload: dict[str, Any]) -> dict[str, Any]:
    models = _get_models()
    model = {
        "id": payload.get("id") or f"mdl_{uuid.uuid4().hex[:8]}",
        "endpointId": payload.get("endpointId", ""),
        "provider": payload.get("provider", "ollama"),
        "createdAt": _now_iso(),
    }
    models.append(model)
    _save_models(models)
    return {"model": model}


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    models = [m for m in _get_models() if m.get("id") != model_id]
    _save_models(models)
    return {"deleted": model_id}


@app.post("/api/models/auto-detect")
async def auto_detect_models() -> dict[str, Any]:
    """Query all configured endpoints and discover available models.
    
    Deduplicates models by base name (strips :latest tag) to avoid
    adding both 'model:latest' and 'model:20b' variants unless they
    are distinct base models.
    """
    endpoints = _get_endpoints()
    discovered: list[dict[str, Any]] = []
    existing_model_ids = {m.get("id") for m in _get_models()}
    seen_base_names: set[str] = set()

    def _base_name(model_id: str) -> str:
        """Get base name for deduplication, preferring non-:latest tags."""
        if model_id.endswith(":latest"):
            base = model_id[:-7]
            return base
        return model_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            api_key = ep.get("apiKey")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            try:
                if provider == "ollama":
                    resp = await client.get(f"{url}/api/tags", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("models", []):
                            mid = m.get("name", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
                elif provider == "openai":
                    resp = await client.get(f"{url}/models", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
                elif provider == "kilo":
                    resp = await client.get(f"{url}/models", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
            except Exception:
                continue

    models = _get_models()
    models.extend(discovered)
    _save_models(models)
    return {"models": discovered, "total": len(models)}


# ---------------------------------------------------------------------------
# Prompt packages
# ---------------------------------------------------------------------------

@app.get("/api/prompts/packages")
async def list_prompt_packages() -> dict[str, Any]:
    return {"packages": _get_prompt_packages()}


# ---------------------------------------------------------------------------
# Kilo Gateway login
# ---------------------------------------------------------------------------

@app.post("/api/kilo/login")
async def kilo_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Test connectivity to Kilo Gateway."""
    url = payload.get("url", "https://api.kilo.ai/api/gateway")
    api_key = payload.get("apiKey")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            test_url = f"{url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            resp = await client.get(test_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                return {
                    "ok": True,
                    "url": url,
                    "models": models,
                    "message": f"Kilo Gateway reachable: {len(models)} models found",
                }
            return {"ok": False, "url": url, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

@app.post("/api/token/generate")
async def generate_token(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a game-day authorization token."""
    environment = payload.get("environment", "staging")
    operator = payload.get("operator", "operator")
    token = (
        f"gd_auth_{environment}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_"
        f"{secrets.token_hex(4)}_"
        f"{operator}"
    )
    return {"token": token, "environment": environment, "operator": operator}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def list_reports() -> dict[str, Any]:
    reports = []
    for path in sorted(REPORTS_DIR.glob("*.pdf")):
        reports.append({
            "name": path.name,
            "url": f"/reports/{path.name}",
            "size_bytes": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"reports": reports}


@app.get("/reports/{filename}")
async def get_report(filename: str) -> Response:
    path = REPORTS_DIR / filename
    if not path.exists():
        return HTMLResponse("Report not found", status_code=404)
    safe_name = filename.replace('"', '_')
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@app.post("/api/reports/generate")
async def generate_reports(payload: dict[str, Any]) -> dict[str, Any]:
    models = payload.get("models", [])
    prompts = payload.get("prompts", [])
    if not models:
        return {"error": "No models specified"}

    script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    if not script.exists():
        return {"error": "Report generator script not found"}

    env = os.environ.copy()
    env["WE3_REPORT_MODELS"] = ",".join(models)
    env["WE3_REPORT_PROMPTS"] = ",".join(prompts) if prompts else ""

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    run_started = _now_iso()
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        run_finished = _now_iso()
        telemetry_entry = {
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": run_finished,
            "models": models,
            "prompts": prompts,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
        }
        _add_telemetry_entry(telemetry_entry)
        return {
            "runId": run_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "error": "Report generation timed out",
        })
        return {"error": "Report generation timed out"}
    except Exception as exc:
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "error": str(exc),
        })
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

@app.get("/api/telemetry/runs")
async def list_telemetry_runs() -> dict[str, Any]:
    return {"runs": _get_telemetry()}


@app.get("/api/telemetry/runs/{run_id}")
async def get_telemetry_run(run_id: str) -> dict[str, Any]:
    runs = _get_telemetry()
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return {"run": run}


@app.delete("/api/telemetry/runs/{run_id}")
async def delete_telemetry_run(run_id: str) -> dict[str, Any]:
    telemetry = [r for r in _get_telemetry() if r.get("runId") != run_id]
    _save_telemetry(telemetry)
    return {"deleted": run_id}


@app.delete("/api/telemetry/runs/{run_id}/items/{item_index}")
async def delete_telemetry_item(run_id: str, item_index: int) -> dict[str, Any]:
    telemetry = _get_telemetry()
    run = next((r for r in telemetry if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    artifacts = run.get("artifacts", [])
    if 0 <= item_index < len(artifacts):
        artifacts.pop(item_index)
        run["artifacts"] = artifacts
    _save_telemetry(telemetry)
    return {"deleted": f"{run_id}::{item_index}"}


@app.get("/api/telemetry/runs/{run_id}/zip")
async def download_run_zip(run_id: str):
    runs = _get_telemetry()
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    artifacts = run.get("artifacts", [])
    if not artifacts:
        return JSONResponse({"error": "No artifacts to zip"}, status_code=404)

    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for artifact in artifacts:
            file_path = REPORTS_DIR / artifact
            if file_path.exists():
                zf.write(file_path, artifact)
                added += 1
            else:
                for search_dir in [GUI_DATA_DIR, WORKSPACE_ROOT / "scripts"]:
                    candidate = search_dir / artifact
                    if candidate.exists():
                        zf.write(candidate, artifact)
                        added += 1
                        break

    if added == 0:
        return JSONResponse({"error": "No artifact files found to zip"}, status_code=404)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}.zip"},
    )


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            action = message.get("action")
            response: dict[str, Any] = {"action": action}

            if action == "list_reports":
                reports = []
                for path in sorted(REPORTS_DIR.glob("*.pdf")):
                    reports.append({
                        "name": path.name,
                        "url": f"/reports/{path.name}",
                        "sizeBytes": path.stat().st_size,
                    })
                response["reports"] = reports

            elif action == "list_endpoints":
                response["endpoints"] = _get_endpoints()

            elif action == "list_models":
                models = _get_models()
                endpoints = _get_endpoints()
                enriched = []
                for m in models:
                    ep = next((e for e in endpoints if e.get("id") == m.get("endpointId")), None)
                    enriched.append({
                        **m,
                        "endpointName": ep.get("name") if ep else None,
                        "provider": ep.get("provider") if ep else m.get("provider"),
                        "endpointAvailable": ep.get("available") if ep else None,
                    })
                response["models"] = enriched

            elif action == "list_telemetry":
                response["runs"] = _get_telemetry()

            elif action == "list_prompt_packages":
                response["packages"] = _get_prompt_packages()

            elif action == "endpoints_status":
                result = await endpoints_status()
                response.update(result)

            elif action == "generate_reports":
                models = message.get("models", [])
                script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
                response["status"] = "started"
                await websocket.send_text(json.dumps(response))
                if script.exists() and models:
                    try:
                        env = os.environ.copy()
                        env["WE3_REPORT_MODELS"] = ",".join(models)
                        env["WE3_REPORT_PROMPTS"] = ",".join(message.get("prompts", []))
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable,
                            str(script),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        run_id = f"run-{uuid.uuid4().hex[:8]}"
                        _add_telemetry_entry({
                            "runId": run_id,
                            "type": "report_generation",
                            "startedAt": _now_iso(),
                            "finishedAt": _now_iso(),
                            "models": models,
                            "prompts": message.get("prompts", []),
                            "returncode": proc.returncode,
                            "stdout": stdout.decode(),
                            "stderr": stderr.decode(),
                            "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
                        })
                        response["runId"] = run_id
                        response["stdout"] = stdout.decode()
                        response["stderr"] = stderr.decode()
                        response["status"] = "complete"
                    except Exception as exc:
                        response["error"] = str(exc)
                        response["status"] = "error"
                else:
                    response["status"] = "skipped"
                    response["error"] = "No script or models"

            elif action == "run_game_day":
                authorization = message.get("authorization", "")
                response["status"] = "started"
                await websocket.send_text(json.dumps(response))
                try:
                    from ..testing.game_day import GameDayOrchestrator
                    orchestrator = GameDayOrchestrator()
                    if not orchestrator.validate_authorization(authorization):
                        response["error"] = "Invalid authorization"
                        response["status"] = "error"
                    else:
                        orchestrator.assert_safety_observer(True)
                        report = orchestrator.execute_failure_matrix(
                            authorization_token=authorization,
                        )
                        run_id = f"run-{uuid.uuid4().hex[:8]}"
                        _add_telemetry_entry({
                            "runId": run_id,
                            "type": "game_day",
                            "startedAt": _now_iso(),
                            "finishedAt": _now_iso(),
                            "authorization": authorization,
                            "report": report.to_dict(),
                            "artifacts": [],
                        })
                        response["runId"] = run_id
                        response["report"] = report.to_dict()
                        response["status"] = "complete"
                except Exception as exc:
                    response["error"] = str(exc)
                    response["status"] = "error"

            elif action == "generate_token":
                token_data = await generate_token({
                    "environment": message.get("environment", "staging"),
                    "operator": message.get("operator", "operator"),
                })
                response.update(token_data)
                response["status"] = "complete"

            elif action == "kilo_login":
                login_result = await kilo_login({
                    "url": message.get("url", "https://api.kilo.ai/api/gateway"),
                    "apiKey": message.get("apiKey"),
                })
                response.update(login_result)

            else:
                response["error"] = f"Unknown action: {action}"

            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

if GUI_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(GUI_STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(str(GUI_STATIC_DIR / "index.html"))
