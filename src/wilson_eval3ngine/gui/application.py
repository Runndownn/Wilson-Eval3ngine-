"""Production GUI application for Wilson Eval3ngine.

This module intentionally keeps the existing evaluation, provider, chart, and
artifact helpers in :mod:`wilson_eval3ngine.gui.server` as compatibility
primitives while providing a smaller, validated application boundary for the
operator GUI.  The legacy module is not served directly.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
import json
import logging
import os
import re
import socket
import sys
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.types import ASGIApp, Receive, Scope, Send

from . import server as legacy

logger = logging.getLogger("we3.gui.application")

# ---------------------------------------------------------------------------
# Limits and state
# ---------------------------------------------------------------------------

_MAX_MODELS_PER_JOB = 32
_MAX_PROMPTS_PER_JOB = 100
_MAX_WORK_ITEMS = 1_000
_MAX_MESSAGE_BYTES = 1_000_000
_MAX_OUTPUT_CHARS = 50_000
_TERMINAL_JOB_STATES = {
    "completed",
    "completed_with_errors",
    "failed",
    "cancelled",
    "interrupted",
}
_RETRYABLE_JOB_STATES = {
    "completed_with_errors",
    "failed",
    "cancelled",
    "interrupted",
}
_CLI_PROVIDERS = {"claude_cli", "kilo_cli", "codex_cli"}
_HTTP_PROVIDERS = {"ollama", "openai", "kilo", "nvidia"}
_SUPPORTED_PROVIDERS = _CLI_PROVIDERS | _HTTP_PROVIDERS

_FILE_LOCK = RLock()
_STATE_LOCK = asyncio.Lock()
_JOB_LOCK = asyncio.Lock()
_JOB_TASKS: dict[str, asyncio.Task[None]] = {}
_JOB_PROCESSES: dict[str, asyncio.subprocess.Process] = {}
_JOB_SUBSCRIBERS: defaultdict[str, set[WebSocket]] = defaultdict(set)
_MAX_ACTIVE_JOBS = max(1, min(4, int(os.environ.get("WE3_GUI_MAX_ACTIVE_JOBS", "1"))))
_JOB_SEMAPHORE = asyncio.Semaphore(_MAX_ACTIVE_JOBS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, fallback: Any) -> Any:
    """Read a JSON document under an in-process lock.

    Corrupt documents are not silently overwritten.  The caller receives the
    fallback and the error is logged with the path only, never file contents.
    """

    with _FILE_LOCK:
        if not path.exists():
            return deepcopy(fallback)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.error("Unable to read JSON state file %s: %s", path, type(exc).__name__)
            return deepcopy(fallback)


def _atomic_write_json(path: Path, data: Any) -> None:
    """Atomically persist JSON with owner-only permissions.

    A unique temporary file avoids the shared ``.tmp`` race present in the
    legacy writer.  ``fsync`` plus ``os.replace`` prevents partial job and
    telemetry documents after interruption.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with _FILE_LOCK:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            try:
                dir_fd = os.open(path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (AttributeError, OSError):
                pass
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)


def _load_jobs() -> dict[str, dict[str, Any]]:
    value = _read_json(legacy.JOBS_FILE, {})
    return value if isinstance(value, dict) else {}


def _save_jobs(jobs: dict[str, dict[str, Any]]) -> None:
    _atomic_write_json(legacy.JOBS_FILE, jobs)


def _load_telemetry() -> list[dict[str, Any]]:
    value = _read_json(legacy.TELEMETRY_FILE, [])
    return value if isinstance(value, list) else []


def _save_telemetry(entries: list[dict[str, Any]]) -> None:
    _atomic_write_json(legacy.TELEMETRY_FILE, entries)


def _load_endpoints() -> list[dict[str, Any]]:
    value = _read_json(legacy.ENDPOINTS_FILE, [])
    return value if isinstance(value, list) else []


def _save_endpoints(entries: list[dict[str, Any]]) -> None:
    _atomic_write_json(legacy.ENDPOINTS_FILE, entries)


def _load_models() -> list[dict[str, Any]]:
    value = _read_json(legacy.MODELS_FILE, [])
    return value if isinstance(value, list) else []


def _save_models(entries: list[dict[str, Any]]) -> None:
    _atomic_write_json(legacy.MODELS_FILE, entries)


# ---------------------------------------------------------------------------
# Security middleware
# ---------------------------------------------------------------------------

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-src 'self'; "
    "worker-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "form-action 'self'"
)
_RESPONSE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": _CSP,
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class SecurityHeadersMiddleware:
    """Apply browser security headers without sharing outbound client state."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                for key, value in _RESPONSE_SECURITY_HEADERS.items():
                    encoded = key.lower().encode("latin-1")
                    if encoded not in existing:
                        headers.append((key.encode("latin-1"), value.encode("latin-1")))
                path = scope.get("path", "")
                if path == "/" or path.startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---------------------------------------------------------------------------
# Request contracts
# ---------------------------------------------------------------------------


class EndpointCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=500)
    provider: str
    api_key: str | None = Field(default=None, alias="apiKey", max_length=4_000)

    @field_validator("name", "url", "provider", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("provider")
    @classmethod
    def provider_supported(cls, value: str) -> str:
        value = value.lower()
        if value not in _SUPPORTED_PROVIDERS:
            raise ValueError("Unsupported provider adapter")
        return value


class ModelCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1, max_length=256)
    endpoint_id: str = Field(alias="endpointId", min_length=1, max_length=128)

    @field_validator("id", "endpoint_id", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("id")
    @classmethod
    def safe_model_id(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("Model ID contains control characters")
        return value


class JobCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    models: list[str] = Field(min_length=1, max_length=_MAX_MODELS_PER_JOB)
    prompts: list[str] = Field(min_length=1, max_length=_MAX_PROMPTS_PER_JOB)
    prompt_package: str = Field(default="", alias="promptPackage", max_length=256)
    prompt_count: int | None = Field(default=None, alias="promptCount", ge=1, le=_MAX_PROMPTS_PER_JOB)
    execution_mode: Literal["single", "batch"] = Field(default="single", alias="executionMode")
    batch_size: int = Field(default=1, alias="batchSize", ge=1, le=8)
    timeout_seconds: int = Field(default=600, alias="timeoutSeconds", ge=60, le=3_600)
    failure_policy: Literal["continue", "stop"] = Field(default="continue", alias="failurePolicy")
    auto_charts: bool = Field(default=True, alias="autoCharts")

    @model_validator(mode="after")
    def normalize_and_limit(self) -> "JobCreate":
        normalized_models: list[str] = []
        for item in self.models:
            value = str(item).strip()
            if not value or len(value) > 256 or any(ord(character) < 32 for character in value):
                raise ValueError("Invalid model identifier")
            if value not in normalized_models:
                normalized_models.append(value)

        normalized_prompts: list[str] = []
        for item in self.prompts:
            value = str(item).strip()
            if not value:
                continue
            if len(value) > 10_000:
                raise ValueError("A prompt exceeds 10,000 characters")
            normalized_prompts.append(value)

        if not normalized_models:
            raise ValueError("At least one model is required")
        if not normalized_prompts:
            raise ValueError("At least one non-empty prompt is required")

        count = min(self.prompt_count or len(normalized_prompts), len(normalized_prompts))
        normalized_prompts = normalized_prompts[:count]
        work_items = len(normalized_models) * len(normalized_prompts)
        if work_items > _MAX_WORK_ITEMS:
            raise ValueError(f"Job exceeds the {_MAX_WORK_ITEMS} work-item limit")

        self.models = normalized_models
        self.prompts = normalized_prompts
        self.prompt_count = len(normalized_prompts)
        if self.execution_mode == "single":
            self.batch_size = max(1, len(normalized_models))
        return self


class ChartGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    run_id: str = Field(alias="runId", min_length=1, max_length=128)

    @field_validator("run_id")
    @classmethod
    def safe_run_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("Invalid run ID")
        return value


# ---------------------------------------------------------------------------
# Endpoint and model services
# ---------------------------------------------------------------------------


def _is_local_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    lowered = hostname.rstrip(".").lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
        return address.is_private or address.is_loopback
    except ValueError:
        try:
            addresses = socket.getaddrinfo(lowered, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except OSError:
            return False
        for result in addresses:
            try:
                address = ipaddress.ip_address(result[4][0])
            except ValueError:
                continue
            if address.is_private or address.is_loopback:
                return True
    return False


def _normalize_endpoint_url(provider: str, value: str) -> str:
    if provider in _CLI_PROVIDERS:
        expected = f"cli://{provider.removesuffix('_cli')}"
        normalized = value.rstrip("/").lower()
        if normalized not in {expected, "cli://claude", "cli://kilo", "cli://codex"}:
            raise HTTPException(status_code=422, detail="CLI providers require a cli:// adapter URL")
        return normalized

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Endpoint URL must include an http(s) scheme and host")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Embedded URL credentials are not permitted")
    if parsed.fragment:
        raise HTTPException(status_code=422, detail="Endpoint URL fragments are not permitted")

    hostname = parsed.hostname.lower()
    try:
        address = ipaddress.ip_address(hostname)
        if address.is_link_local or address.is_multicast or address.is_unspecified:
            raise HTTPException(status_code=422, detail="Link-local, multicast, and unspecified endpoint addresses are blocked")
    except ValueError:
        pass

    if parsed.scheme == "http" and not _is_local_hostname(hostname):
        raise HTTPException(status_code=422, detail="Public network endpoints must use HTTPS")

    normalized = value.strip().rstrip("/")
    provider_error = legacy._validate_provider_url(provider, normalized)
    if provider_error:
        raise HTTPException(status_code=422, detail=provider_error)
    return normalized


def _sanitize_endpoint(endpoint: dict[str, Any]) -> dict[str, Any]:
    return legacy._sanitize_endpoint(endpoint)


async def _create_endpoint(payload: EndpointCreate) -> dict[str, Any]:
    normalized_url = _normalize_endpoint_url(payload.provider, payload.url)
    key_error = legacy._validate_api_key(payload.provider, payload.api_key or "")
    if key_error:
        raise HTTPException(status_code=422, detail=key_error)

    async with _STATE_LOCK:
        endpoints = _load_endpoints()
        duplicate = next(
            (
                endpoint
                for endpoint in endpoints
                if endpoint.get("provider") == payload.provider
                and str(endpoint.get("url", "")).rstrip("/").lower() == normalized_url.lower()
            ),
            None,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="An endpoint with this provider and URL already exists")

        endpoint = {
            "id": f"ep_{uuid.uuid4().hex[:12]}",
            "name": payload.name,
            "url": normalized_url,
            "provider": payload.provider,
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        }
        if payload.api_key:
            endpoint["encryptedApiKey"] = legacy.encrypt_api_key(payload.api_key)
        endpoints.append(endpoint)
        _save_endpoints(endpoints)
        legacy._audit_log("gui_endpoint_created", endpoint_id=endpoint["id"], provider=payload.provider)
        return _sanitize_endpoint(endpoint)


async def _delete_endpoint(endpoint_id: str) -> dict[str, Any]:
    async with _STATE_LOCK:
        endpoints = _load_endpoints()
        if not any(endpoint.get("id") == endpoint_id for endpoint in endpoints):
            raise HTTPException(status_code=404, detail="Endpoint not found")
        remaining = [endpoint for endpoint in endpoints if endpoint.get("id") != endpoint_id]
        models = _load_models()
        removed_models = [model for model in models if model.get("endpointId") == endpoint_id]
        models = [model for model in models if model.get("endpointId") != endpoint_id]
        _save_endpoints(remaining)
        _save_models(models)
        legacy._audit_log(
            "gui_endpoint_deleted",
            endpoint_id=endpoint_id,
            removed_models=len(removed_models),
        )
        return {"deleted": endpoint_id, "removedModels": len(removed_models)}


def _enriched_models() -> list[dict[str, Any]]:
    endpoints = {endpoint.get("id"): endpoint for endpoint in _load_endpoints()}
    result: list[dict[str, Any]] = []
    for model in _load_models():
        endpoint = endpoints.get(model.get("endpointId"))
        result.append(
            {
                **model,
                "endpointName": endpoint.get("name") if endpoint else None,
                "endpointUrl": endpoint.get("url") if endpoint else None,
                "provider": endpoint.get("provider") if endpoint else model.get("provider"),
                "endpointAvailable": endpoint.get("available") if endpoint else None,
            }
        )
    return sorted(result, key=lambda item: (str(item.get("provider", "")), str(item.get("id", ""))))


async def _create_model(payload: ModelCreate) -> dict[str, Any]:
    async with _STATE_LOCK:
        endpoints = _load_endpoints()
        endpoint = next((item for item in endpoints if item.get("id") == payload.endpoint_id), None)
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        models = _load_models()
        if any(item.get("id") == payload.id for item in models):
            raise HTTPException(
                status_code=409,
                detail="Model IDs must be unique in the current registry; remove or rename the existing registration",
            )
        model = {
            "id": payload.id,
            "endpointId": payload.endpoint_id,
            "provider": endpoint.get("provider"),
            "createdAt": _now_iso(),
        }
        models.append(model)
        _save_models(models)
        return model


async def _delete_model(model_id: str) -> dict[str, Any]:
    async with _STATE_LOCK:
        models = _load_models()
        if not any(item.get("id") == model_id for item in models):
            raise HTTPException(status_code=404, detail="Model not found")
        _save_models([item for item in models if item.get("id") != model_id])
        return {"deleted": model_id}


async def _discover_models() -> dict[str, Any]:
    """Discover models from remote, local, and CLI endpoint adapters.

    The legacy detector intentionally skips local endpoints.  This production
    boundary supplements it by testing every explicitly configured endpoint,
    which makes local Ollama and SSH-tunnel gateways functional without making
    them implicit SSRF targets.
    """

    async with _STATE_LOCK:
        try:
            await legacy.auto_detect_models()
        except Exception as exc:
            logger.warning("Legacy model discovery failed: %s", type(exc).__name__)

        endpoints = _load_endpoints()
        models = _load_models()
        existing_ids = {item.get("id") for item in models}
        added: list[dict[str, Any]] = []
        collisions: list[dict[str, str]] = []

        for endpoint in endpoints:
            endpoint_id = str(endpoint.get("id", ""))
            if not endpoint_id:
                continue
            try:
                result = await legacy.test_endpoint(endpoint_id)
            except Exception as exc:
                logger.info("Model discovery test failed for %s: %s", endpoint_id, type(exc).__name__)
                continue
            if not isinstance(result, dict) or not result.get("ok"):
                continue
            for discovered in result.get("models", []) or []:
                model_id = discovered.get("id") if isinstance(discovered, dict) else discovered
                model_id = str(model_id or "").strip()
                if not model_id or len(model_id) > 256:
                    continue
                if model_id in existing_ids:
                    existing = next((item for item in models if item.get("id") == model_id), None)
                    if existing and existing.get("endpointId") != endpoint_id:
                        collisions.append({"modelId": model_id, "endpointId": endpoint_id})
                    continue
                model = {
                    "id": model_id,
                    "endpointId": endpoint_id,
                    "provider": endpoint.get("provider"),
                    "createdAt": _now_iso(),
                }
                models.append(model)
                added.append(model)
                existing_ids.add(model_id)

        _save_models(models)
        return {"added": added, "total": len(models), "collisions": collisions}


# ---------------------------------------------------------------------------
# Job planning and persistence
# ---------------------------------------------------------------------------


def _safe_component(value: str, max_length: int = 96) -> str:
    value = value.replace("\x00", "").replace("/", "-").replace("\\", "-").replace(":", "-")
    value = value.replace("..", "-")
    value = re.sub(r"[^A-Za-z0-9._-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-.")
    return (value or "artifact")[:max_length]


def _build_invocations(request: JobCreate) -> tuple[list[dict[str, Any]], list[str]]:
    models = _load_models()
    endpoints = {endpoint.get("id"): endpoint for endpoint in _load_endpoints()}
    model_map = {str(model.get("id")): model for model in models}

    missing = [model_id for model_id in request.models if model_id not in model_map]
    if missing:
        raise HTTPException(status_code=422, detail={"message": "Unregistered models", "models": missing})

    grouped: dict[str, list[str]] = {}
    warnings: list[str] = []
    for model_id in request.models:
        model = model_map[model_id]
        endpoint_id = str(model.get("endpointId") or "")
        endpoint = endpoints.get(endpoint_id)
        if not endpoint:
            raise HTTPException(status_code=409, detail=f"Model {model_id} has no valid endpoint")
        if endpoint.get("available") is False:
            warnings.append(f"Endpoint {endpoint.get('name') or endpoint_id} was last observed offline")
        grouped.setdefault(endpoint_id, []).append(model_id)

    invocations: list[dict[str, Any]] = []
    for endpoint_id, model_ids in grouped.items():
        endpoint = endpoints[endpoint_id]
        chunk_size = len(model_ids) if request.execution_mode == "single" else request.batch_size
        for offset in range(0, len(model_ids), chunk_size):
            invocations.append(
                {
                    "index": len(invocations) + 1,
                    "endpoint_id": endpoint_id,
                    "endpoint_name": endpoint.get("name"),
                    "provider": endpoint.get("provider"),
                    "models": model_ids[offset : offset + chunk_size],
                    "status": "queued",
                    "run_id": None,
                    "artifacts": [],
                    "evaluation_sidecars": [],
                    "chart_urls": {},
                    "returncode": None,
                    "error": None,
                }
            )
    return invocations, sorted(set(warnings))


def _initial_job(request: JobCreate, invocations: list[dict[str, Any]], warnings: list[str], retry_of: str | None) -> dict[str, Any]:
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    batch_id = f"batch-{uuid.uuid4().hex[:12]}"
    work_items = {
        json.dumps([model_id, prompt_index], separators=(",", ":")): {
            "model": model_id,
            "prompt_index": prompt_index,
            "status": "queued",
            "updated_at": None,
        }
        for model_id in request.models
        for prompt_index in range(1, len(request.prompts) + 1)
    }
    model_states = {
        model_id: {
            "status": "queued",
            "completed_reports": 0,
            "failed_reports": 0,
            "total_reports": len(request.prompts),
            "percentage": 0,
            "current_step": "Queued",
            "current_prompt": None,
            "elapsed_seconds": 0,
            "started_at": None,
            "finished_at": None,
        }
        for model_id in request.models
    }
    return {
        "job_id": job_id,
        "run_id": batch_id,
        "batch_id": batch_id,
        "retry_of": retry_of,
        "status": "queued",
        "execution_mode": request.execution_mode,
        "batch_size": request.batch_size,
        "timeout_seconds": request.timeout_seconds,
        "failure_policy": request.failure_policy,
        "auto_charts": request.auto_charts,
        "models": request.models,
        "prompts": request.prompts,
        "prompt_package": request.prompt_package,
        "prompt_count": len(request.prompts),
        "total_reports": len(work_items),
        "completed_reports": 0,
        "failed_reports": 0,
        "processing_reports": 0,
        "queued_reports": len(work_items),
        "overall_percentage": 0,
        "current_model": None,
        "current_report": None,
        "current_step": "Queued for execution",
        "current_invocation": None,
        "created_at": _now_iso(),
        "started_at": None,
        "updated_at": _now_iso(),
        "finished_at": None,
        "elapsed_seconds": 0,
        "estimated_completion": None,
        "models_state": model_states,
        "invocations": invocations,
        "artifacts": [],
        "evaluation_sidecars": [],
        "chart_urls": {},
        "artifact_hashes": {},
        "warnings": warnings,
        "error": None,
        "_work_items": work_items,
    }


def _public_job(job: dict[str, Any], include_prompts: bool = True) -> dict[str, Any]:
    public = deepcopy(job)
    public.pop("_work_items", None)
    if not include_prompts:
        public.pop("prompts", None)
    return public


def _recompute_job(job: dict[str, Any]) -> None:
    work_items = job.get("_work_items", {})
    statuses = [item.get("status", "queued") for item in work_items.values()]
    completed = statuses.count("complete")
    failed = statuses.count("failed")
    processing = statuses.count("processing")
    queued = max(0, len(statuses) - completed - failed - processing)
    terminal = completed + failed

    job["completed_reports"] = completed
    job["failed_reports"] = failed
    job["processing_reports"] = processing
    job["queued_reports"] = queued
    job["overall_percentage"] = round((terminal / len(statuses)) * 100) if statuses else 0
    job["updated_at"] = _now_iso()

    for model_id, state in job.get("models_state", {}).items():
        model_items = [item for item in work_items.values() if item.get("model") == model_id]
        state_completed = sum(1 for item in model_items if item.get("status") == "complete")
        state_failed = sum(1 for item in model_items if item.get("status") == "failed")
        state_processing = sum(1 for item in model_items if item.get("status") == "processing")
        state["completed_reports"] = state_completed
        state["failed_reports"] = state_failed
        state["percentage"] = round(((state_completed + state_failed) / len(model_items)) * 100) if model_items else 0
        if state.get("status") not in _TERMINAL_JOB_STATES and state_processing == 0 and state_completed + state_failed == len(model_items):
            state["status"] = "completed" if state_failed == 0 else "completed_with_errors"
            state["finished_at"] = state.get("finished_at") or _now_iso()

    if job.get("started_at"):
        try:
            start = datetime.fromisoformat(str(job["started_at"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(job.get("finished_at") or _now_iso()).replace("Z", "+00:00"))
            elapsed = max(0.0, (end - start).total_seconds())
            job["elapsed_seconds"] = round(elapsed, 1)
            if terminal and terminal < len(statuses) and job.get("status") not in _TERMINAL_JOB_STATES:
                rate = terminal / max(elapsed, 0.1)
                remaining = len(statuses) - terminal
                job["estimated_completion"] = datetime.fromtimestamp(
                    end.timestamp() + remaining / max(rate, 0.001), tz=timezone.utc
                ).isoformat()
        except (TypeError, ValueError):
            pass


def _update_job_record(job_id: str, mutate: Any) -> dict[str, Any] | None:
    with _FILE_LOCK:
        jobs = _load_jobs()
        job = jobs.get(job_id)
        if not job:
            return None
        mutate(job)
        _recompute_job(job)
        jobs[job_id] = job
        _save_jobs(jobs)
        return _public_job(job)


async def _broadcast_job(job: dict[str, Any]) -> None:
    message = json.dumps({"action": "job_update", "job": _public_job(job, include_prompts=False)})
    stale: list[WebSocket] = []
    for subscriber in tuple(_JOB_SUBSCRIBERS.get(job["job_id"], set())):
        try:
            await subscriber.send_text(message)
        except Exception:
            stale.append(subscriber)
    for subscriber in stale:
        _JOB_SUBSCRIBERS[job["job_id"]].discard(subscriber)


async def _set_job_fields(job_id: str, **updates: Any) -> dict[str, Any] | None:
    async with _JOB_LOCK:
        job = _update_job_record(job_id, lambda current: current.update(updates))
    if job:
        await _broadcast_job(job)
    return job


async def _apply_progress_event(job_id: str, event: dict[str, Any], invocation_index: int) -> dict[str, Any] | None:
    event_type = str(event.get("event") or "")
    model_id = str(event.get("model") or "")
    prompt_index = int(event.get("prompt_index") or 0)
    timestamp = str(event.get("timestamp") or _now_iso())

    def mutate(job: dict[str, Any]) -> None:
        job["current_invocation"] = invocation_index
        if event_type == "run_start":
            job["current_step"] = f"Invocation {invocation_index} started"
        elif event_type == "model_start" and model_id:
            state = job["models_state"].setdefault(model_id, {})
            state.update(
                {
                    "status": "processing",
                    "current_step": "Preparing first prompt",
                    "started_at": state.get("started_at") or timestamp,
                }
            )
            job["current_model"] = model_id
            job["current_step"] = f"Processing {event.get('model_label') or model_id}"
        elif event_type == "prompt_start" and model_id and prompt_index:
            key = json.dumps([model_id, prompt_index], separators=(",", ":"))
            item = job["_work_items"].get(key)
            if item and item.get("status") != "complete":
                item.update({"status": "processing", "updated_at": timestamp})
            state = job["models_state"].setdefault(model_id, {})
            state.update(
                {
                    "status": "processing",
                    "current_prompt": prompt_index,
                    "current_step": f"Waiting for response {prompt_index} of {len(job['prompts'])}",
                }
            )
            job["current_model"] = model_id
            job["current_report"] = prompt_index
            job["current_step"] = f"{model_id}: prompt {prompt_index} of {len(job['prompts'])}"
        elif event_type == "prompt_complete" and model_id and prompt_index:
            key = json.dumps([model_id, prompt_index], separators=(",", ":"))
            item = job["_work_items"].get(key)
            if item:
                item.update(
                    {
                        "status": "complete" if event.get("success") else "failed",
                        "updated_at": timestamp,
                        "response_time": event.get("time"),
                        "result_status": event.get("status"),
                    }
                )
            state = job["models_state"].setdefault(model_id, {})
            state["current_step"] = f"Saved response {prompt_index} of {len(job['prompts'])}"
        elif event_type in {"rate_limit_retry", "rate_limited_queued", "model_queued", "retry_pass_start"}:
            delay = event.get("delay") or event.get("wait_seconds") or 0
            job["current_step"] = f"Rate-limit recovery in progress ({delay}s backoff)"
            if model_id:
                state = job["models_state"].setdefault(model_id, {})
                state["status"] = "queued"
                state["current_step"] = job["current_step"]
        elif event_type == "report_start" and model_id:
            job["models_state"].setdefault(model_id, {})["current_step"] = "Generating PDF report"
            job["current_step"] = f"Generating PDF for {model_id}"
        elif event_type == "report_generated" and model_id:
            state = job["models_state"].setdefault(model_id, {})
            state["current_step"] = "Report generated"
            state["report_path"] = event.get("report_path")
        elif event_type == "report_error" and model_id:
            state = job["models_state"].setdefault(model_id, {})
            state["status"] = "failed"
            state["current_step"] = "Report generation failed"
            state["error"] = legacy.sanitize_output(str(event.get("error") or "Report generation failed"))
        elif event_type == "model_complete" and model_id:
            state = job["models_state"].setdefault(model_id, {})
            state["status"] = "completed"
            state["finished_at"] = timestamp
            state["current_step"] = "Completed"
        elif event_type == "run_error":
            job["current_step"] = "Invocation failed"
            job["error"] = legacy.sanitize_output(str(event.get("error") or "Invocation failed"))

    async with _JOB_LOCK:
        public = _update_job_record(job_id, mutate)
    if public:
        await _broadcast_job(public)
    return public


async def _create_job(request: JobCreate, retry_of: str | None = None) -> dict[str, Any]:
    packages = {str(item.get("id")) for item in legacy._get_prompt_packages()}
    if request.prompt_package and request.prompt_package not in packages:
        raise HTTPException(status_code=422, detail="Unknown prompt package")

    invocations, warnings = _build_invocations(request)
    job = _initial_job(request, invocations, warnings, retry_of)
    async with _JOB_LOCK:
        jobs = _load_jobs()
        jobs[job["job_id"]] = job
        _save_jobs(jobs)
        task = asyncio.create_task(_run_job(job["job_id"]), name=f"we3-{job['job_id']}")
        _JOB_TASKS[job["job_id"]] = task
        task.add_done_callback(lambda _task, job_id=job["job_id"]: _JOB_TASKS.pop(job_id, None))
    return _public_job(job)


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------


def _formatted_models(model_ids: list[str]) -> str:
    return legacy._format_models_for_script(model_ids)


def _artifact_targets(model_ids: list[str]) -> list[str]:
    targets: list[str] = []
    for model_id in model_ids:
        safe = _safe_component(model_id)
        targets.extend([f"{safe}-evaluation.pdf", f"{safe}-evaluation.json"])
    return targets


def _archive_conflicting_artifacts(model_ids: list[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    replacements: dict[str, str] = {}
    for name in _artifact_targets(model_ids):
        path = legacy.REPORTS_DIR / name
        if not path.exists():
            continue
        archived = f"legacy-{timestamp}-{uuid.uuid4().hex[:6]}-{name}"
        path.replace(legacy.REPORTS_DIR / archived)
        replacements[name] = archived

    if replacements:
        telemetry = _load_telemetry()
        for entry in telemetry:
            entry["artifacts"] = [replacements.get(item, item) for item in entry.get("artifacts", [])]
            entry["evaluationSidecars"] = [
                replacements.get(item, item) for item in entry.get("evaluationSidecars", [])
            ]
        _save_telemetry(telemetry)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finalize_artifacts(
    model_ids: list[str],
    run_id: str,
    batch_id: str,
    job_id: str,
) -> tuple[list[str], list[str], dict[str, str]]:
    artifacts: list[str] = []
    sidecars: list[str] = []
    hashes: dict[str, str] = {}

    for source_name in _artifact_targets(model_ids):
        source = legacy.REPORTS_DIR / source_name
        if not source.exists():
            continue
        destination_name = f"{_safe_component(run_id)}-{source_name}"
        destination = legacy.REPORTS_DIR / destination_name
        if destination.exists():
            destination_name = f"{_safe_component(run_id)}-{uuid.uuid4().hex[:6]}-{source_name}"
            destination = legacy.REPORTS_DIR / destination_name
        source.replace(destination)

        if destination.suffix == ".json":
            try:
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload.update({"runId": run_id, "batchId": batch_id, "jobId": job_id})
                _atomic_write_json(destination, payload)
            except Exception as exc:
                logger.warning("Unable to normalize evaluation sidecar %s: %s", destination.name, type(exc).__name__)
            sidecars.append(destination.name)
        else:
            artifacts.append(destination.name)
        hashes[destination.name] = _hash_file(destination)
    return artifacts, sidecars, hashes


def _telemetry_upsert(entry: dict[str, Any]) -> None:
    telemetry = [item for item in _load_telemetry() if item.get("runId") != entry.get("runId")]
    telemetry.insert(0, entry)
    _save_telemetry(telemetry)


async def _tail_progress_file(
    job_id: str,
    invocation_index: int,
    path: Path,
    run_holder: dict[str, str],
    stop_event: asyncio.Event,
) -> None:
    position = 0
    while True:
        processed = False
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    handle.seek(position)
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        processed = True
                        position = handle.tell()
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("event") == "run_start" and event.get("run_id"):
                            run_holder["run_id"] = _safe_component(str(event["run_id"]), 128)
                        await _apply_progress_event(job_id, event, invocation_index)
            except OSError:
                pass
        if stop_event.is_set() and not processed:
            return
        await asyncio.sleep(0.2)


async def _run_invocation(job_id: str, invocation: dict[str, Any]) -> dict[str, Any]:
    job = _load_jobs()[job_id]
    endpoint = next(
        (item for item in _load_endpoints() if item.get("id") == invocation["endpoint_id"]),
        None,
    )
    if not endpoint:
        raise RuntimeError("Invocation endpoint no longer exists")

    invocation_index = int(invocation["index"])
    model_ids = list(invocation["models"])
    progress_path = legacy.GUI_DATA_DIR / f"progress-{job_id}-{invocation_index}.jsonl"
    progress_path.unlink(missing_ok=True)
    _archive_conflicting_artifacts(model_ids)

    env = os.environ.copy()
    env["WE3_REPORT_MODELS"] = _formatted_models(model_ids)
    env["WE3_REPORT_PROMPTS"] = json.dumps(job["prompts"], ensure_ascii=False)
    env["WE3_REPORT_PROMPT_PACKAGE"] = str(job.get("prompt_package") or "")
    env["WE3_REPORT_PROGRESS_FILE"] = str(progress_path)
    env["WE3_REPORT_BATCH_ID"] = str(job["batch_id"])

    endpoint_url = str(endpoint.get("url") or "")
    if endpoint_url and not endpoint_url.startswith("cli://"):
        env["WE3_REPORT_GATEWAY"] = endpoint_url
        if _is_local_hostname(urlparse(endpoint_url).hostname):
            env["WE3_REPORT_ALLOW_LOCAL"] = "1"

    secure_key_file = None
    api_key = legacy._get_endpoint_api_key(endpoint)
    if api_key:
        secure_key_file = legacy.store_api_key_temp_file(
            api_key,
            endpoint_id=str(endpoint.get("id") or "unknown"),
            purpose="gui_application_report_generation",
        )
        env["WE3_REPORT_API_KEY_FILE"] = secure_key_file.file_path
        logger.info("Prepared encrypted endpoint credentials for job %s (%s)", job_id, legacy.mask_api_key(api_key))

    await _set_job_fields(
        job_id,
        status="running",
        current_invocation=invocation_index,
        current_step=f"Starting invocation {invocation_index} of {len(job['invocations'])}",
    )

    def mark_invocation(current: dict[str, Any]) -> None:
        current["invocations"][invocation_index - 1]["status"] = "running"
        current["invocations"][invocation_index - 1]["started_at"] = _now_iso()

    async with _JOB_LOCK:
        updated = _update_job_record(job_id, mark_invocation)
    if updated:
        await _broadcast_job(updated)

    script = legacy.WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    if not script.exists():
        raise RuntimeError("Report generator script is missing")

    process: asyncio.subprocess.Process | None = None
    stop_event = asyncio.Event()
    run_holder: dict[str, str] = {}
    tail_task: asyncio.Task[None] | None = None
    started_at = _now_iso()
    stdout_text = ""
    stderr_text = ""
    returncode = -1
    invocation_error: str | None = None

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            f"--progress-file={progress_path}",
            cwd=str(legacy.WORKSPACE_ROOT),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _JOB_PROCESSES[job_id] = process
        tail_task = asyncio.create_task(
            _tail_progress_file(job_id, invocation_index, progress_path, run_holder, stop_event)
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=int(job["timeout_seconds"])
            )
        except asyncio.TimeoutError:
            invocation_error = f"Invocation timed out after {job['timeout_seconds']} seconds"
            process.kill()
            stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]
        stderr_text = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_CHARS]
        returncode = int(process.returncode or 0)
    except asyncio.CancelledError:
        invocation_error = "Invocation cancelled"
        if process and process.returncode is None:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.error("Unable to reap cancelled report process for job %s", job_id)
        raise
    finally:
        _JOB_PROCESSES.pop(job_id, None)
        stop_event.set()
        if tail_task:
            try:
                await asyncio.wait_for(tail_task, timeout=2)
            except asyncio.TimeoutError:
                tail_task.cancel()
            except Exception:
                pass
        if secure_key_file is not None:
            secure_key_file.destroy()
        progress_path.unlink(missing_ok=True)

    run_id = run_holder.get("run_id") or f"eval-{uuid.uuid4().hex[:12]}"
    if any(item.get("runId") == run_id for item in _load_telemetry()):
        run_id = f"{run_id}-{uuid.uuid4().hex[:6]}"

    artifacts, sidecars, hashes = _finalize_artifacts(
        model_ids,
        run_id=run_id,
        batch_id=str(job["batch_id"]),
        job_id=job_id,
    )

    chart_urls: dict[str, str] = {}
    if job.get("auto_charts") and sidecars:
        try:
            chart_urls = await asyncio.to_thread(
                legacy._generate_charts_for_run_sync,
                run_id,
                model_ids,
                job["prompts"],
            )
        except Exception as exc:
            logger.warning("Chart generation failed for run %s: %s", run_id, type(exc).__name__)
            invocation_error = invocation_error or "Charts could not be generated"

    status_value = "completed"
    if returncode != 0 or invocation_error:
        status_value = "completed_with_errors" if artifacts else "failed"

    telemetry_entry = {
        "runId": run_id,
        "batchId": job["batch_id"],
        "jobId": job_id,
        "type": "report_generation",
        "executionMode": job["execution_mode"],
        "invocationIndex": invocation_index,
        "endpointId": invocation["endpoint_id"],
        "provider": invocation.get("provider"),
        "startedAt": started_at,
        "finishedAt": _now_iso(),
        "models": model_ids,
        "prompts": job["prompts"],
        "promptPackage": job.get("prompt_package", ""),
        "returncode": returncode,
        "status": status_value,
        "stdout": legacy.sanitize_output(stdout_text),
        "stderr": legacy.sanitize_output(stderr_text),
        "artifacts": artifacts,
        "evaluationSidecars": sidecars,
        "artifactHashes": hashes,
        "chartUrls": chart_urls,
        "error": legacy.sanitize_output(invocation_error) if invocation_error else None,
    }
    async with _STATE_LOCK:
        _telemetry_upsert(telemetry_entry)

    result = {
        **invocation,
        "run_id": run_id,
        "status": status_value,
        "finished_at": telemetry_entry["finishedAt"],
        "returncode": returncode,
        "artifacts": artifacts,
        "evaluation_sidecars": sidecars,
        "artifact_hashes": hashes,
        "chart_urls": chart_urls,
        "error": telemetry_entry["error"],
    }

    def complete_invocation(current: dict[str, Any]) -> None:
        current["invocations"][invocation_index - 1] = result
        current["artifacts"] = sorted(set(current.get("artifacts", []) + artifacts))
        current["evaluation_sidecars"] = sorted(
            set(current.get("evaluation_sidecars", []) + sidecars)
        )
        current["artifact_hashes"].update(hashes)
        current["chart_urls"].update(chart_urls)
        current["current_step"] = f"Invocation {invocation_index} finished"

    async with _JOB_LOCK:
        updated = _update_job_record(job_id, complete_invocation)
    if updated:
        await _broadcast_job(updated)
    return result


async def _run_job(job_id: str) -> None:
    try:
        async with _JOB_SEMAPHORE:
            current = _load_jobs().get(job_id)
            if not current or current.get("status") == "cancelled":
                return
            await _set_job_fields(
                job_id,
                status="running",
                started_at=_now_iso(),
                current_step="Preparing execution plan",
            )
            job = _load_jobs()[job_id]
            invocation_failures = 0
            for invocation in list(job["invocations"]):
                result = await _run_invocation(job_id, invocation)
                if result["status"] != "completed":
                    invocation_failures += 1
                    if job.get("failure_policy") == "stop":
                        break

            job = _load_jobs()[job_id]
            if invocation_failures and not job.get("artifacts"):
                final_status = "failed"
            elif invocation_failures or job.get("failed_reports", 0):
                final_status = "completed_with_errors"
            else:
                final_status = "completed"
            await _set_job_fields(
                job_id,
                status=final_status,
                finished_at=_now_iso(),
                current_step="Completed" if final_status == "completed" else "Completed with errors",
                current_model=None,
                current_report=None,
                overall_percentage=100,
            )
    except asyncio.CancelledError:
        process = _JOB_PROCESSES.get(job_id)
        if process and process.returncode is None:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
        await _set_job_fields(
            job_id,
            status="cancelled",
            finished_at=_now_iso(),
            current_step="Cancelled",
            error="Report generation was cancelled",
        )
    except Exception as exc:
        logger.exception("Report job %s failed", job_id)
        await _set_job_fields(
            job_id,
            status="failed",
            finished_at=_now_iso(),
            current_step="Failed",
            error=legacy.sanitize_output(str(exc)),
        )
    finally:
        _JOB_PROCESSES.pop(job_id, None)


async def _cancel_job(job_id: str) -> dict[str, Any]:
    job = _load_jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") in _TERMINAL_JOB_STATES:
        raise HTTPException(status_code=409, detail=f"Job is already {job['status']}")
    await _set_job_fields(job_id, status="cancelling", current_step="Cancellation requested")
    task = _JOB_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    else:
        await _set_job_fields(
            job_id,
            status="cancelled",
            finished_at=_now_iso(),
            current_step="Cancelled",
        )
    return _public_job(_load_jobs()[job_id])


async def _retry_job(job_id: str) -> dict[str, Any]:
    job = _load_jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") not in _RETRYABLE_JOB_STATES:
        raise HTTPException(status_code=409, detail="Only failed, interrupted, or cancelled jobs can be retried")
    request = JobCreate.model_validate(
        {
            "models": job["models"],
            "prompts": job["prompts"],
            "promptPackage": job.get("prompt_package", ""),
            "promptCount": len(job["prompts"]),
            "executionMode": job.get("execution_mode", "single"),
            "batchSize": job.get("batch_size", 1),
            "timeoutSeconds": job.get("timeout_seconds", 600),
            "failurePolicy": job.get("failure_policy", "continue"),
            "autoCharts": job.get("auto_charts", True),
        }
    )
    return await _create_job(request, retry_of=job_id)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


async def _reconcile_interrupted_jobs() -> None:
    async with _JOB_LOCK:
        jobs = _load_jobs()
        changed = False
        for job in jobs.values():
            if job.get("status") not in _TERMINAL_JOB_STATES:
                job.update(
                    {
                        "status": "interrupted",
                        "finished_at": _now_iso(),
                        "updated_at": _now_iso(),
                        "current_step": "Interrupted by server restart",
                        "error": "The GUI process restarted before this job completed",
                    }
                )
                changed = True
        if changed:
            _save_jobs(jobs)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    legacy.GUI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    legacy.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    legacy.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    await _reconcile_interrupted_jobs()
    yield
    tasks = [task for task in _JOB_TASKS.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="Wilson Eval3ngine GUI",
    version="2.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    jobs = _load_jobs()
    active = sum(1 for item in jobs.values() if item.get("status") not in _TERMINAL_JOB_STATES)
    return {
        "status": "ok",
        "service": "wilson-eval3ngine-gui",
        "version": "2.0",
        "activeJobs": active,
        "maxActiveJobs": _MAX_ACTIVE_JOBS,
    }


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    jobs = list(_load_jobs().values())
    reports = list(legacy.REPORTS_DIR.glob("*.pdf"))
    return {
        "endpoints": len(_load_endpoints()),
        "models": len(_load_models()),
        "jobs": len(jobs),
        "activeJobs": sum(1 for item in jobs if item.get("status") not in _TERMINAL_JOB_STATES),
        "runs": len([item for item in _load_telemetry() if item.get("type") == "report_generation"]),
        "reports": len(reports),
    }


@app.get("/api/endpoints")
async def list_endpoints() -> dict[str, Any]:
    return {"endpoints": [_sanitize_endpoint(item) for item in _load_endpoints()]}


@app.post("/api/endpoints", status_code=status.HTTP_201_CREATED)
async def create_endpoint(payload: EndpointCreate) -> dict[str, Any]:
    return {"endpoint": await _create_endpoint(payload)}


@app.delete("/api/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str) -> dict[str, Any]:
    return await _delete_endpoint(endpoint_id)


@app.post("/api/endpoints/{endpoint_id}/test")
async def test_endpoint(endpoint_id: str) -> dict[str, Any]:
    if not any(item.get("id") == endpoint_id for item in _load_endpoints()):
        raise HTTPException(status_code=404, detail="Endpoint not found")
    result = await legacy.test_endpoint(endpoint_id)
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Endpoint adapter returned an invalid response")
    return result


@app.post("/api/endpoints/status")
async def refresh_endpoint_status() -> dict[str, Any]:
    result = await legacy.endpoints_status()
    return result if isinstance(result, dict) else {"statuses": []}


@app.post("/api/endpoints/auto-detect")
async def auto_detect_endpoints() -> dict[str, Any]:
    result = await legacy.auto_detect_endpoints()
    return result if isinstance(result, dict) else {"endpoints": []}


@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    return {"models": _enriched_models()}


@app.post("/api/models", status_code=status.HTTP_201_CREATED)
async def create_model(payload: ModelCreate) -> dict[str, Any]:
    return {"model": await _create_model(payload)}


@app.delete("/api/models/{model_id:path}")
async def delete_model(model_id: str) -> dict[str, Any]:
    return await _delete_model(model_id)


@app.post("/api/models/auto-detect")
async def auto_detect_models() -> dict[str, Any]:
    return await _discover_models()


@app.get("/api/prompts/packages")
async def list_prompt_packages() -> dict[str, Any]:
    return {"packages": legacy._get_prompt_packages()}


@app.get("/api/jobs")
async def list_jobs() -> dict[str, Any]:
    jobs = sorted(
        (_public_job(item, include_prompts=False) for item in _load_jobs().values()),
        key=lambda item: str(item.get("created_at", "")),
        reverse=True,
    )
    return {"jobs": jobs}


@app.post("/api/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(payload: JobCreate) -> dict[str, Any]:
    return {"job": await _create_job(payload)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _load_jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": _public_job(job)}


@app.post("/api/jobs/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_job(job_id: str) -> dict[str, Any]:
    return {"job": await _cancel_job(job_id)}


@app.post("/api/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_job(job_id: str) -> dict[str, Any]:
    return {"job": await _retry_job(job_id)}


def _report_run_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for run in _load_telemetry():
        for artifact in run.get("artifacts", []):
            index[str(artifact)] = run
    return index


@app.get("/api/reports")
async def list_reports() -> dict[str, Any]:
    run_index = _report_run_index()
    reports: list[dict[str, Any]] = []
    for path in sorted(legacy.REPORTS_DIR.glob("*.pdf"), key=lambda item: item.stat().st_mtime, reverse=True):
        run = run_index.get(path.name, {})
        reports.append(
            {
                "name": path.name,
                "url": f"/reports/{path.name}",
                "sizeBytes": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "sha256": run.get("artifactHashes", {}).get(path.name) or _hash_file(path),
                "runId": run.get("runId"),
                "batchId": run.get("batchId"),
                "jobId": run.get("jobId"),
                "models": run.get("models", []),
                "status": run.get("status"),
            }
        )
    return {"reports": reports}


@app.get("/reports/{filename}")
async def get_report(filename: str) -> FileResponse:
    safe = legacy._validate_report_filename(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid report filename")
    path = legacy.REPORTS_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe}"'},
    )


@app.delete("/api/reports/{filename}")
async def delete_report(filename: str) -> dict[str, Any]:
    safe = legacy._validate_report_filename(filename)
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid report filename")
    path = legacy.REPORTS_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    path.unlink()
    telemetry = _load_telemetry()
    for run in telemetry:
        run["artifacts"] = [item for item in run.get("artifacts", []) if item != safe]
        run.get("artifactHashes", {}).pop(safe, None)
    _save_telemetry(telemetry)
    return {"deleted": safe}


@app.get("/api/telemetry/runs")
async def list_telemetry_runs() -> dict[str, Any]:
    runs = sorted(
        _load_telemetry(),
        key=lambda item: str(item.get("finishedAt") or item.get("startedAt") or ""),
        reverse=True,
    )
    return {"runs": legacy._enrich_runs_with_charts(runs)}


@app.get("/api/telemetry/runs/{run_id}")
async def get_telemetry_run(run_id: str) -> dict[str, Any]:
    run = next((item for item in _load_telemetry() if item.get("runId") == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    enriched = legacy._enrich_runs_with_charts([run])
    return {"run": enriched[0] if enriched else run}


@app.get("/api/telemetry/runs/{run_id}/zip")
async def download_run_zip(run_id: str) -> StreamingResponse:
    run = next((item for item in _load_telemetry() if item.get("runId") == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = deepcopy(run)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        added += 1
        for name in list(run.get("artifacts", [])) + list(run.get("evaluationSidecars", [])):
            safe = legacy._validate_report_filename(str(name))
            if not safe:
                continue
            path = legacy.REPORTS_DIR / safe
            if path.is_file():
                archive.write(path, f"artifacts/{safe}")
                added += 1
        for chart_name, chart_url in (run.get("chartUrls") or {}).items():
            candidate = legacy.WORKSPACE_ROOT / str(chart_url).lstrip("/")
            if candidate.is_file() and legacy.CHARTS_DIR.resolve() in candidate.resolve().parents:
                archive.write(candidate, f"charts/{_safe_component(str(chart_name))}.png")
                added += 1
    if added <= 1:
        raise HTTPException(status_code=404, detail="No run artifacts were found")
    buffer.seek(0)
    safe_run = _safe_component(run_id, 128)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_run}.zip"'},
    )


@app.get("/api/charts/runs")
async def list_chart_runs() -> dict[str, Any]:
    return {"runs": legacy._list_chart_runs()}


@app.get("/api/charts/metadata")
async def chart_metadata() -> dict[str, Any]:
    return {"order": legacy._CHART_ORDER, "charts": legacy._CHART_METADATA}


@app.post("/api/charts/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_charts(payload: ChartGenerateRequest) -> dict[str, Any]:
    run = next((item for item in _load_telemetry() if item.get("runId") == payload.run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await legacy.generate_charts_endpoint({"run_id": payload.run_id})
    if isinstance(result, JSONResponse):
        return json.loads(result.body)
    return result


# ---------------------------------------------------------------------------
# WebSocket event stream and compatibility actions
# ---------------------------------------------------------------------------


def _websocket_origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc == host


async def _ws_send(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_text(json.dumps(payload, ensure_ascii=False))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    if not _websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await websocket.accept()
    subscribed: set[str] = set()
    await _ws_send(websocket, {"action": "hello", "version": "2.0"})
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > _MAX_MESSAGE_BYTES:
                await _ws_send(websocket, {"action": "error", "error": "Message exceeds size limit"})
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_send(websocket, {"action": "error", "error": "Invalid JSON"})
                continue
            if not isinstance(message, dict):
                await _ws_send(websocket, {"action": "error", "error": "Message must be an object"})
                continue
            action = str(message.get("action") or "")

            try:
                if action in {"subscribe_job", "get_job"}:
                    job_id = str(message.get("job_id") or "")
                    job = _load_jobs().get(job_id)
                    if not job:
                        await _ws_send(websocket, {"action": action, "error": "Job not found"})
                        continue
                    _JOB_SUBSCRIBERS[job_id].add(websocket)
                    subscribed.add(job_id)
                    await _ws_send(websocket, {"action": "job_update", "job": _public_job(job, include_prompts=False)})
                elif action == "generate_reports":
                    request = JobCreate.model_validate(message)
                    job = await _create_job(request)
                    _JOB_SUBSCRIBERS[job["job_id"]].add(websocket)
                    subscribed.add(job["job_id"])
                    await _ws_send(websocket, {"action": "generate_reports", "status": "started", "job": job})
                elif action == "cancel_job":
                    job = await _cancel_job(str(message.get("job_id") or ""))
                    await _ws_send(websocket, {"action": "cancel_job", "job": job})
                elif action == "retry_job":
                    job = await _retry_job(str(message.get("job_id") or ""))
                    _JOB_SUBSCRIBERS[job["job_id"]].add(websocket)
                    subscribed.add(job["job_id"])
                    await _ws_send(websocket, {"action": "retry_job", "job": job})
                elif action == "list_endpoints":
                    await _ws_send(websocket, {"action": action, "endpoints": [_sanitize_endpoint(item) for item in _load_endpoints()]})
                elif action == "list_models":
                    await _ws_send(websocket, {"action": action, "models": _enriched_models()})
                elif action == "list_prompt_packages":
                    await _ws_send(websocket, {"action": action, "packages": legacy._get_prompt_packages()})
                elif action == "list_reports":
                    payload = await list_reports()
                    await _ws_send(websocket, {"action": action, **payload})
                elif action == "list_chart_runs":
                    await _ws_send(websocket, {"action": action, "runs": legacy._list_chart_runs()})
                elif action == "chart_metadata":
                    await _ws_send(websocket, {"action": action, "order": legacy._CHART_ORDER, "charts": legacy._CHART_METADATA})
                elif action == "ping":
                    await _ws_send(websocket, {"action": "pong", "timestamp": _now_iso()})
                else:
                    await _ws_send(websocket, {"action": action or "error", "error": "Unknown action"})
            except HTTPException as exc:
                await _ws_send(websocket, {"action": action, "error": exc.detail, "statusCode": exc.status_code})
            except Exception as exc:
                logger.exception("WebSocket action %s failed", action)
                await _ws_send(websocket, {"action": action, "error": legacy.sanitize_output(str(exc))})
    except WebSocketDisconnect:
        pass
    finally:
        for job_id in subscribed:
            _JOB_SUBSCRIBERS[job_id].discard(websocket)


# Static files are mounted last so API and report routes retain precedence.
if legacy.GUI_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(legacy.GUI_STATIC_DIR)), name="static")


@app.get("/")
async def serve_index(_request: Request) -> FileResponse:
    return FileResponse(legacy.GUI_STATIC_DIR / "index.html", media_type="text/html")
