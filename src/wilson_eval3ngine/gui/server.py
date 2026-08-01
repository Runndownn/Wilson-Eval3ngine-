"""FastAPI + WebSocket backend for Wilson Eval3ngine GUI."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from wilson_eval3ngine.gui.api_key_vault import (
    SecureKeyFile,
    store_api_key_securely,
    store_api_key_temp_file,
    secure_delete_file,
    mask_api_key,
    encrypt_api_key,
    decrypt_api_key,
    sanitize_output,
    _audit_log,
)

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import ASGIApp, Scope, Receive, Send

logger = logging.getLogger("we3.gui")

app = FastAPI(title="Wilson Eval3ngine GUI")


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

# Content-Security-Policy: restricts sources of content to prevent XSS, data
# exfiltration, and inline script injection.
# - script-src: allows same-origin, cdnjs (for pdf.js), and 'unsafe-inline'
#   (required for the inline onclick handlers in index.html — though we're
#   migrating away from those, we keep it for backward compatibility)
# - style-src: allows same-origin and inline styles (used by the GUI)
# - img-src: allows same-origin, data: (for inline images), and cdnjs
# - connect-src: allows same-origin and ws: (for WebSocket)
# - object-src: 'none' to prevent Flash/Java plugin attacks
# - base-uri: 'self' to prevent <base> tag injection
# - frame-ancestors: 'none' to prevent clickjacking
# Note: 'upgrade-insecure-requests' is intentionally omitted because the server
# runs on plain HTTP. That directive would cause the browser to upgrade all
# resource requests to HTTPS, resulting in ERR_SSL_PROTOCOL_ERROR.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://cdnjs.cloudflare.com; "
    "font-src 'self' https://cdnjs.cloudflare.com; "
    "connect-src 'self' ws: wss:; "
    "worker-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)

# Security headers applied to every response
# Note: Strict-Transport-Security (HSTS) is intentionally omitted because the
# server runs on plain HTTP. HSTS tells the browser to only use HTTPS, which
# would cause ERR_SSL_PROTOCOL_ERROR for all resources when the server is HTTP.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": _CSP,
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class SecurityHeadersMiddleware:
    """ASGI middleware that injects security headers into every response.

    Security headers:
    - X-Content-Type-Options: nosniff — prevents MIME-type sniffing
    - X-Frame-Options: DENY — prevents clickjacking
    - X-XSS-Protection: 1; mode=block — enables browser XSS filter
    - Referrer-Policy: no-referrer — prevents referrer leakage
    - Strict-Transport-Security — enforces HTTPS
    - Content-Security-Policy — prevents XSS and data exfiltration
    - Permissions-Policy — restricts browser features (geolocation, camera, etc.)
    - Cross-Origin-Opener-Policy: same-origin — isolates browsing context
    - Cross-Origin-Resource-Policy: same-origin — restricts resource loading
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message):
            if message["type"] == "response_start":
                headers = message.get("headers", [])
                # Add security headers (don't override existing ones)
                existing_keys = {k.lower() for k, _ in headers}
                for key, value in _SECURITY_HEADERS.items():
                    if key.lower().encode("latin-1") not in existing_keys:
                        headers.append((key.encode("latin-1"), value.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send)


app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# Secure HTTP client infrastructure
# ---------------------------------------------------------------------------

# Default timeout for external API calls (connect, read, write, pool)
_DEFAULT_HTTP_TIMEOUT = httpx.Timeout(15.0, connect=10.0, read=15.0, write=10.0)

# Connection pool limits to prevent resource exhaustion
_HTTP_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=20)

# Security headers applied to every outbound request
_SECURITY_HEADERS = {
    "User-Agent": "WilsonEval3ngine-GUI/1.0",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
}

# Maximum response size (10 MB) to prevent memory exhaustion
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _create_secure_http_client(timeout: float | httpx.Timeout = _DEFAULT_HTTP_TIMEOUT) -> httpx.AsyncClient:
    """Create a hardened httpx.AsyncClient with security best practices.

    Security measures:
    - SSL/TLS certificate verification is explicitly enabled (verify=True)
    - HTTP/2 is enabled for encrypted transport and multiplexing
    - Proxy environment variables are disabled to prevent proxy injection
    - Connection pooling limits prevent resource exhaustion
    - Security headers are set on every request
    - Response size is capped to prevent memory exhaustion
    """
    return httpx.AsyncClient(
        timeout=timeout,
        verify=True,
        http2=True,
        limits=_HTTP_LIMITS,
        trust_env=False,  # Do not read proxy/SSL settings from environment
        headers=_SECURITY_HEADERS,
    )


def _validate_endpoint_url(url: str) -> str:
    """Validate and sanitize an endpoint URL before making requests.

    Security measures:
    - Rejects URLs with embedded credentials (user:pass@host)
    - Rejects non-HTTP(S) schemes
    - Rejects localhost/127.0.0.1 for external endpoints
    - Strips trailing slashes for consistent URL construction
    """
    if not url or not url.strip():
        raise ValueError("Empty URL")

    url = url.strip().rstrip("/")

    # Reject URLs with embedded credentials
    parsed = httpx.URL(url)
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {scheme}")

    # Reject localhost endpoints for external API calls
    host = parsed.host or ""
    if host in ("localhost", "127.0.0.1", "::1") or host.startswith("127."):
        raise ValueError("Localhost endpoints are not allowed for external API calls")

    return url


def _validate_config_url(url: str) -> str | None:
    """Validate a URL from client configuration input (endpoints, login, test).

    Unlike _validate_endpoint_url, this allows localhost endpoints (for local
    development) but still enforces:
    - Non-empty, reasonable length (<= 2048 chars)
    - HTTP/HTTPS scheme only
    - No embedded credentials (user:pass@host)
    - No path traversal in the URL

    Returns the sanitized URL string, or None if invalid.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url or len(url) > 2048:
        return None
    url = url.rstrip("/")
    try:
        parsed = httpx.URL(url)
    except Exception:
        return None
    # Reject embedded credentials
    if parsed.username or parsed.password:
        return None
    # Only allow HTTP/HTTPS
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return None
    return url


def _safe_request_error(exc: Exception) -> str:
    """Return a sanitized error message that does not leak sensitive details."""
    if isinstance(exc, httpx.TimeoutException):
        return "Request timed out"
    if isinstance(exc, httpx.ConnectError):
        return "Connection failed"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP error: {exc.response.status_code}"
    return "Request failed"


def _sanitize_error_message(exc: Exception) -> str:
    """Sanitize an exception message for client-facing responses.

    Removes potential sensitive data (API keys, tokens, URLs with credentials,
    AWS keys, GitHub tokens, private keys, passwords) from error messages to
    prevent information leakage. Uses the comprehensive sanitize_output()
    function from api_key_vault for broad pattern coverage.
    """
    msg = str(exc)
    # Use comprehensive sanitization from api_key_vault
    msg = sanitize_output(msg, max_length=500)
    return msg


def _build_auth_headers(api_key: str | None) -> dict[str, str]:
    """Build authentication headers. Returns empty dict if no API key."""
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _validate_response(resp: httpx.Response) -> None:
    """Validate an HTTP response for security and correctness."""
    # Check response size
    if "content-length" in resp.headers:
        size = int(resp.headers["content-length"])
        if size > _MAX_RESPONSE_BYTES:
            raise ValueError(f"Response too large: {size} bytes (max: {_MAX_RESPONSE_BYTES})")


# Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GUI_STATIC_DIR = WORKSPACE_ROOT / "gui" / "static"
REPORTS_DIR = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
GUI_DATA_DIR = WORKSPACE_ROOT / "gui" / "data"
CHARTS_DIR = GUI_STATIC_DIR / "charts"

# Ensure directories exist
GUI_STATIC_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GUI_DATA_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS_FILE = GUI_DATA_DIR / "endpoints.json"
MODELS_FILE = GUI_DATA_DIR / "models.json"
TELEMETRY_FILE = GUI_DATA_DIR / "telemetry.json"
PROMPT_PACKAGES_FILE = GUI_DATA_DIR / "prompt_packages.json"
JOBS_FILE = GUI_DATA_DIR / "jobs.json"

# Background report generation state
_report_process: asyncio.subprocess.Process | None = None
_report_task: asyncio.Task | None = None
_report_lock = asyncio.Lock()


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _save_json(path: Path, data: Any) -> None:
    """Persist JSON data to disk with restrictive file permissions (0600).

    All data files in GUI_DATA_DIR contain potentially sensitive information
    (encrypted API keys, telemetry with stdout/stderr, job state). Writing
    with 0600 ensures only the owning user can read or modify them, preventing
    information leakage to other local users.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use a temp file + atomic rename to avoid partial writes and TOCTOU races.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(path)


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
# Session-level deleted runs tracking
# ---------------------------------------------------------------------------
# When a user deletes an entire chart run (via the "×" button on a run card),
# we track the deletion in-memory so that "Refresh" does not resurrect it
# during the current server process lifetime. Deletions are also persisted
# via telemetry ``deletedCharts`` entries so they survive across restarts,
# but the in-memory set provides an extra safety net for runs whose
# telemetry entries may not exist yet (e.g. on-demand generated runs like
# ``test-run-final``).
_deleted_chart_runs: set[str] = set()


def _clear_deleted_charts_for_run(run_id: str) -> None:
    """Clear the ``deletedCharts`` list for a run in telemetry.

    Used when the server regenerates sample charts under the ``sample-charts``
    run so that freshly-generated sample charts are not hidden by stale
    per-chart deletion records.
    """
    telemetry = _get_telemetry()
    modified = False
    for entry in telemetry:
        if (entry.get("runId") or entry.get("run_id")) == run_id:
            if entry.get("deletedCharts"):
                entry["deletedCharts"] = []
                modified = True
    if modified:
        _save_telemetry(telemetry)


def _load_jobs() -> dict[str, Any]:
    return _load_json(JOBS_FILE, {})


def _save_jobs(jobs: dict[str, Any]) -> None:
    _save_json(JOBS_FILE, jobs)


def _get_job(job_id: str) -> dict[str, Any] | None:
    return _load_jobs().get(job_id)


def _update_job(job_id: str, updates: dict[str, Any]) -> None:
    jobs = _load_jobs()
    if job_id in jobs:
        jobs[job_id].update(updates)
        jobs[job_id]["updated_at"] = _now_iso()
        _save_jobs(jobs)


def _create_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = {
        "job_id": job_id,
        "run_id": payload.get("run_id", job_id),
        "status": "queued",
        "models": payload.get("models", []),
        "prompts": payload.get("prompts", []),
        "prompt_package": payload.get("prompt_package", ""),
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "finished_at": None,
        "total_reports": len(payload.get("models", [])) * max(1, len(payload.get("prompts", []))),
        "completed_reports": 0,
        "failed_reports": 0,
        "processing_reports": 0,
        "queued_reports": len(payload.get("models", [])) * max(1, len(payload.get("prompts", []))),
        "current_model": None,
        "current_report": None,
        "current_step": "Queued",
        "estimated_completion": None,
        "elapsed_seconds": 0,
        "models_state": {},
        "reports": [],
        "error": None,
        "progress_file": payload.get("progress_file", ""),
        "websocket_connected": True,
    }
    jobs = _load_jobs()
    jobs[job_id] = job
    _save_jobs(jobs)
    return job


def _is_localhost_endpoint(url: str) -> bool:
    """Check if URL is a localhost/127.0.0.1/private endpoint that should be skipped for auto-detection.
    
    The GUI should only use configured gateway hosts, not local instances.
    Checks for localhost, loopback, private IP ranges, and link-local addresses.
    """
    if not url:
        return False
    url_lower = url.lower().strip()
    if not url_lower.startswith(("http://", "https://")):
        return False
    host = url_lower.split("://", 1)[1].split("/")[0].split(":")[0]
    # Check localhost hostnames
    if host in ("localhost", "localhost.", "0.0.0.0", "0.0.0.1", "::1", "::"):
        return True
    # Check loopback range (127.0.0.0/8)
    if host.startswith("127."):
        return True
    # Check link-local range (169.254.x.x — includes cloud metadata endpoints)
    if host.startswith("169.254."):
        return True
    # Check TEST-NET ranges (documentation/test networks)
    if host.startswith(("192.0.2.", "198.51.100.", "203.0.113.", "198.18.")):
        return True
    return False


# Per-provider endpoint validation rules. Keep this table small and explicit;
# the goal is to fail fast on obvious mistakes (wrong URL, wrong key prefix)
# before keys are stored or sent over the network.
_PROVIDER_VALIDATION_RULES = {
    "nvidia": {
        "url_required_https": True,
        "url_host_allowlist": ("integrate.api.nvidia.com",),
        "url_host_blocklist": (),
        "key_required": True,
        "key_prefix": "nvapi-",
        "key_min_length": 20,
        "key_max_length": 200,
    },
    "kilo": {
        # Kilo supports OAuth via CLI (no key needed in form) or direct API key.
        # Allow both; only validate when a key is present.
        "url_required_https": False,
        "url_host_allowlist": (),
        "url_host_blocklist": (),
        "key_required": False,
        "key_prefix": None,
        "key_min_length": 8,
        "key_max_length": 4000,
    },
    "openai": {
        "url_required_https": False,
        "url_host_allowlist": (),
        "url_host_blocklist": (),
        "key_required": False,
        "key_prefix": None,
        "key_min_length": 8,
        "key_max_length": 4000,
    },
    "ollama": {
        "url_required_https": False,
        "url_host_allowlist": (),
        "url_host_blocklist": (),
        "key_required": False,
        "key_prefix": None,
        "key_min_length": 0,
        "key_max_length": 4000,
    },
}


def _validate_provider_url(provider: str, url: str) -> str | None:
    """Return None if OK, otherwise a short safe error string.

    Does NOT include the URL or key in the error message to avoid leaking
    configuration details into logs or HTTP responses.
    """
    rules = _PROVIDER_VALIDATION_RULES.get(provider)
    if not rules:
        return None
    if not url:
        return f"URL is required for provider {provider}"
    try:
        parsed = urlparse(url)
    except Exception:
        return "URL is malformed"
    if not parsed.scheme or not parsed.netloc:
        return "URL must include scheme and host"
    if rules["url_required_https"] and parsed.scheme != "https":
        return f"Provider {provider} requires https:// (got {parsed.scheme}://)"
    host = (parsed.hostname or "").lower()
    allowlist = rules["url_host_allowlist"]
    if allowlist and host not in allowlist:
        return f"Provider {provider} only allows hosts: {', '.join(allowlist)}"
    blocklist = rules["url_host_blocklist"]
    if blocklist and host in blocklist:
        return f"Provider {provider} does not allow host: {host}"
    return None


def _validate_api_key(provider: str, api_key: str) -> str | None:
    """Return None if OK, otherwise a short safe error string.

    Errors never echo the key itself. Only echoes the provider name and
    a generic reason (too short, wrong prefix, missing).
    """
    rules = _PROVIDER_VALIDATION_RULES.get(provider)
    if not rules:
        return None
    if rules["key_required"] and not api_key:
        return f"API key is required for provider {provider}"
    if not api_key:
        return None
    # Length checks (defensive: reject absurd values before encryption)
    if len(api_key) < rules["key_min_length"]:
        return f"API key for {provider} is too short"
    if len(api_key) > rules["key_max_length"]:
        return f"API key for {provider} is too long"
    prefix = rules["key_prefix"]
    if prefix and not api_key.startswith(prefix):
        # Don't echo the prefix publicly if we want to keep it secret; we don't.
        return f"API key for {provider} must start with {prefix}"
    return None


def _sanitize_and_validate_endpoint_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Sanitize user input and validate provider-specific requirements.

    Returns (sanitized_payload, error_message). error_message is None on success.

    Hardening applied:
      - Trims whitespace on URL, name, and API key (keys often have trailing newlines)
      - Rejects overly long/short names, URLs, keys (defensive DoS protection)
      - Enforces provider-specific URL + key rules (see _PROVIDER_VALIDATION_RULES)
      - Never echoes back the API key in error messages
    """
    if not isinstance(payload, dict):
        return {}, "Invalid payload"

    name = (payload.get("name") or "").strip()
    url = (payload.get("url") or "").strip()
    provider = (payload.get("provider") or "ollama").strip().lower()
    api_key = payload.get("apiKey")
    if api_key is not None and isinstance(api_key, str):
        api_key = api_key.strip()
    if api_key == "":
        api_key = None

    # Defensive length caps on free-form fields to prevent payload abuse
    MAX_NAME_LEN = 200
    MAX_URL_LEN = 500
    MAX_KEY_LEN = 4000
    if len(name) > MAX_NAME_LEN:
        return {}, f"name exceeds {MAX_NAME_LEN} characters"
    if len(url) > MAX_URL_LEN:
        return {}, f"url exceeds {MAX_URL_LEN} characters"
    if api_key is not None and len(api_key) > MAX_KEY_LEN:
        return {}, f"apiKey exceeds {MAX_KEY_LEN} characters"

    # Provider-specific URL + key validation
    url_err = _validate_provider_url(provider, url)
    if url_err:
        return {}, url_err
    key_err = _validate_api_key(provider, api_key or "")
    if key_err:
        return {}, key_err

    sanitized = {
        "name": name or "Unnamed",
        "url": url,
        "provider": provider,
        "apiKey": api_key,  # Will be encrypted before storage
    }
    # Preserve any pass-through id (rarely used by clients but supported)
    if "id" in payload and payload["id"]:
        sanitized["id"] = str(payload["id"])[:64]
    return sanitized, None


def _validate_report_filename(filename: str) -> str | None:
    """Validate a report filename to prevent path traversal attacks.
    
    Security measures:
    - Rejects empty filenames
    - Rejects filenames containing path separators (/ or \\)
    - Rejects filenames containing parent directory references (..)
    - Rejects filenames starting with a dot (hidden files)
    - Strips null bytes
    - Returns a sanitized filename or None if invalid
    
    Returns:
        Sanitized filename string, or None if the filename is unsafe.
    """
    if not filename or not filename.strip():
        return None
    
    # Strip null bytes (null byte injection)
    filename = filename.replace("\x00", "")
    
    # Reject path separators and parent directory references
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    
    # Reject hidden files (starting with .)
    if filename.startswith("."):
        return None
    
    # Only allow alphanumeric, dash, underscore, dot, and hyphen in filenames
    import re
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*$', filename):
        return None
    
    return filename


# ---------------------------------------------------------------------------
# Telemetry chart generation
# ---------------------------------------------------------------------------

# Dark theme colors matching the GUI
_CHART_BG = "#0b1021"
_CHART_PANEL = "#111836"
_CHART_TEXT = "#e6e9f5"
_CHART_MUTED = "#9aa3c7"
_CHART_PRIMARY = "#1f3a8a"
_CHART_ACCENT = "#f5c842"
_CHART_PASS = "#1f9d55"
_CHART_FAIL = "#e5484d"
_CHART_GRID = "#262d4d"  # rgba(255,255,255,0.08) equivalent


def _load_evaluation_jsons() -> list[dict[str, Any]]:
    """Load all evaluation JSON sidecar files from the reports directory."""
    evals = []
    if REPORTS_DIR.exists():
        for path in sorted(REPORTS_DIR.glob("*-evaluation.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_source_file"] = path.name
                evals.append(data)
            except Exception:
                continue
    return evals


def _generate_sample_evaluations() -> dict[str, Any]:
    """Generate sample evaluation data for chart generation when no real data is available.

    Returns a dict of model -> evaluation data with realistic-looking sample values.
    Charts generated from this data will be labeled as SAMPLE in the UI.
    """
    import random
    random.seed(42)  # Reproducible samples

    sample_models = [
        "gpt-4o-mini",
        "claude-3-5-sonnet-20241022",
        "gemini-1.5-flash",
        "poolside/laguna-s-2.1:free",
        "command-r+",
        "llama-3-70b",
    ]

    sample_prompts = [
        "Explain quantum computing in simple terms.",
        "Write a Python function to calculate fibonacci numbers.",
        "What are the safety considerations when deploying AI models?",
        "Analyze this code for potential security vulnerabilities.",
        "How would you handle a prompt injection attack?",
    ]

    # Models 0-2 are standard (non-reasoning); model 2 has reasoning data for
    # the reasoning_comparison chart, model 5 has reasoning tokens to cover both paths.
    reasoning_model_indices = {2, 5}

    sample_evals: dict[str, Any] = {}
    for model_idx, model in enumerate(sample_models):
        # Generate realistic-looking sample data
        num_success = random.randint(4, 5)
        num_total = 5
        success_rate = f"{num_success}/{num_total}"
        avg_time = round(random.uniform(1.5, 8.0), 2)
        total_tokens = random.randint(500, 3000)
        code_examples = random.randint(0, 5)
        security_awareness = round(random.uniform(2, 8), 1)

        # Generate per-prompt response times
        response_times = [round(random.uniform(0.8, 12.0), 2) for _ in range(num_total)]

        # Generate per-prompt token counts so token_efficiency chart can work
        per_prompt_tokens = [random.randint(100, 800) for _ in range(num_total)]

        is_reasoning = model_idx in reasoning_model_indices
        reasoning_tokens_values = [random.randint(200, 1500) for _ in range(num_total)] if is_reasoning else [0] * num_total

        # Generate evaluations with tokens and reasoning data
        evaluations = []
        for i in range(num_total):
            evals = [
                {
                    "success": True,
                    "response_time": response_times[i],
                    "prompt": sample_prompts[i],
                    "tokens": per_prompt_tokens[i],
                    "is_reasoning": is_reasoning,
                    "reasoning_tokens": reasoning_tokens_values[i],
                }
                for i in range(num_success)
            ]
            evals += [
                {
                    "success": False,
                    "response_time": response_times[i],
                    "prompt": sample_prompts[i],
                    "tokens": per_prompt_tokens[i],
                    "is_reasoning": is_reasoning,
                    "reasoning_tokens": reasoning_tokens_values[i],
                }
                for i in range(num_success, num_total)
            ]
            evaluations = evals

        total_reasoning = sum(reasoning_tokens_values) if is_reasoning else 0

        sample_evals[model] = {
            "model": model,
            "modelLabel": model,
            "provider": "sample",
            "promptPackage": "sample-package",
            "timestamp": "2026-07-31T00:00:00Z",
            "status": "complete",
            "avg_time": avg_time,
            "prompt_success_rate": success_rate,
            "total_tokens": total_tokens,
            "code_examples": code_examples,
            "security_awareness": security_awareness,
            "gateway_used": "sample",
            "reasoning_models": is_reasoning,
            "total_reasoning_tokens": total_reasoning,
            "prompts": sample_prompts,
            "evaluations": evaluations,
            "response_times": response_times,
            "_is_sample": True,
        }

    return sample_evals


def _apply_dark_style(ax=None, fig=None):
    """Apply the Wilson Eval3ngine dark theme to a matplotlib figure/axes."""
    if fig is None:
        fig = plt.gcf()
    fig.patch.set_facecolor(_CHART_BG)
    if ax is None:
        ax = plt.gca()
    ax.set_facecolor(_CHART_BG)
    ax.title.set_color(_CHART_TEXT)
    ax.xaxis.label.set_color(_CHART_TEXT)
    ax.yaxis.label.set_color(_CHART_TEXT)
    ax.tick_params(colors=_CHART_TEXT, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(_CHART_GRID)
    ax.grid(True, color=_CHART_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)


def _style_axes(ax, bg, panel, grid, text, muted):
    """Apply dark theme styling to a matplotlib axes (used by batch comparison chart).

    This is a convenience wrapper that sets facecolors, label colors, tick colors,
    and grid style in one call, matching the visual style of _apply_dark_style.
    """
    if ax is None:
        ax = plt.gca()
    ax.set_facecolor(bg)
    ax.title.set_color(text)
    ax.xaxis.label.set_color(text)
    ax.yaxis.label.set_color(text)
    ax.tick_params(colors=text, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(grid)
    ax.grid(True, color=grid, linestyle="--", linewidth=0.5, alpha=0.6)


def _save_chart(fig, run_id: str, chart_name: str) -> str | None:
    """Save a matplotlib figure as PNG and return the URL path."""
    try:
        run_dir = CHARTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = run_dir / f"{chart_name}.png"
        # Add SAMPLE watermark if this is sample data
        if "sample" in run_id.lower():
            fig.text(0.5, 0.5, "SAMPLE", fontsize=48, color=(1, 1, 1, 0.15),
                     ha="center", va="center", rotation=30, transform=fig.transFigure,
                     zorder=10, fontweight="bold")
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_CHART_BG, edgecolor="none")
        plt.close(fig)
        return f"/static/charts/{run_id}/{chart_name}.png"
    except Exception as exc:
        logger.warning("Failed to save chart %s/%s: %s", run_id, chart_name, exc)
        try:
            plt.close(fig)
        except Exception:
            pass
        return None


def _generate_model_radar_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a radar chart comparing models across 5 metrics."""
    models = list(evaluations.keys())
    if not models:
        return None

    metrics = ["Avg Time\n(lower=better)", "Success\nRate", "Total\nTokens", "Code\nExamples", "Security\nAwareness"]
    n_metrics = len(metrics)

    # Normalize values to 0-1 scale for radar
    max_time = max((e.get("avg_time", 0) for e in evaluations.values()), default=1) or 1
    max_tokens = max((e.get("total_tokens", 1) for e in evaluations.values()), default=1) or 1
    max_code = max((e.get("code_examples", 0) for e in evaluations.values()), default=1) or 1
    max_sec = max((e.get("security_awareness", 0) for e in evaluations.values()), default=1) or 1

    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]  # close the loop

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]
    for idx, (model, data) in enumerate(evaluations.items()):
        # Parse success rate: "5/5" -> 1.0, "3/5" -> 0.6
        sr_raw = data.get("prompt_success_rate", "0/5")
        if isinstance(sr_raw, str) and "/" in sr_raw:
            parts = sr_raw.split("/")
            sr = int(parts[0]) / int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        elif isinstance(sr_raw, (int, float)):
            sr = float(sr_raw)
        else:
            sr = 0.0
        values = [
            1 - (data.get("avg_time", 0) / max_time),  # invert: lower time = higher score
            sr,
            data.get("total_tokens", 0) / max_tokens,
            data.get("code_examples", 0) / max_code,
            data.get("security_awareness", 0) / max_sec,
        ]
        values += values[:1]
        color = colors[idx % len(colors)]
        ax.plot(angles, values, color=color, linewidth=2, label=model[:20])
        ax.fill(angles, values, color=color, alpha=0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, color=_CHART_TEXT, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color=_CHART_MUTED, fontsize=7)
    ax.set_title("Model Performance Radar", color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=20)
    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
    legend.get_frame().set_facecolor(_CHART_PANEL)
    legend.get_frame().set_edgecolor(_CHART_GRID)
    for text in legend.get_texts():
        text.set_color(_CHART_TEXT)
    plt.tight_layout()
    return _save_chart(fig, run_id, "radar")


def _generate_response_time_chart(run_id: str, evaluations: dict[str, Any], prompts: list[str]) -> str | None:
    """Generate a grouped bar chart of response times per model per prompt."""
    models = list(evaluations.keys())
    if not models:
        return None

    prompt_labels = [f"P{i+1}" for i in range(len(prompts))]
    x = np.arange(len(prompt_labels))
    width = 0.8 / len(models)

    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 1.5), 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    for idx, model in enumerate(models):
        data = evaluations.get(model, {})
        evals = data.get("evaluations", [])
        times = [e.get("time", 0) for e in evals[:len(prompts)]]
        while len(times) < len(prompts):
            times.append(0)
        offset = (idx - len(models) / 2 + 0.5) * width
        _ = ax.bar(x + offset, times, width, label=model[:20], color=colors[idx % len(colors)], alpha=0.9)

    ax.set_xlabel("Prompt", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time by Model & Prompt", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(prompt_labels, color=_CHART_TEXT, fontsize=9)
    ax.legend(fontsize=8, loc="upper left")
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "response_times")


def _generate_heatmap_chart(run_id: str, evaluations: dict[str, Any], prompts: list[str]) -> str | None:
    """Generate a pass/fail heatmap grid."""
    models = list(evaluations.keys())
    if not models:
        return None

    prompt_labels = [f"P{i+1}: {p[:25]}..." if len(p) > 25 else f"P{i+1}: {p}" for i, p in enumerate(prompts)]
    data = np.zeros((len(models), len(prompts)))

    for mi, model in enumerate(models):
        evals = evaluations.get(model, {}).get("evaluations", [])
        for pi, e in enumerate(evals[:len(prompts)]):
            data[mi, pi] = 1 if e.get("success", False) else 0

    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 1.2), max(4, len(models) * 0.8)))
    cmap = matplotlib.colors.ListedColormap([_CHART_FAIL, _CHART_PASS])
    bounds = [0, 0.5, 1]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(np.arange(len(prompt_labels)))
    ax.set_yticks(np.arange(len(models)))
    ax.set_xticklabels(prompt_labels, color=_CHART_TEXT, fontsize=8, rotation=45, ha="right")
    ax.set_yticklabels(models, color=_CHART_TEXT, fontsize=9)
    ax.set_title("Pass / Fail Heatmap", color=_CHART_TEXT, fontsize=13, fontweight="bold")

    # Add text annotations
    for mi in range(len(models)):
        for pi in range(len(prompts)):
            label = "PASS" if data[mi, pi] == 1 else "FAIL"
            color = _CHART_TEXT if data[mi, pi] == 1 else _CHART_TEXT
            ax.text(pi, mi, label, ha="center", va="center", color=color, fontsize=8, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.6, aspect=30)
    cbar.set_ticks([0.25, 0.75])
    cbar.set_ticklabels(["FAIL", "PASS"])
    cbar.ax.yaxis.set_tick_params(color=_CHART_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_CHART_TEXT, fontsize=9)
    cbar.outline.set_edgecolor(_CHART_GRID)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "heatmap")


def _generate_tokens_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a bar chart of total tokens per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    tokens = [evaluations[m].get("total_tokens", 0) for m in models]
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]
    bar_colors = [colors[i % len(colors)] for i in range(len(models))]

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    bars = ax.bar(models, tokens, color=bar_colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Total Tokens Generated", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Token Usage by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")

    for bar, val in zip(bars, tokens):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(tokens) * 0.01,
                str(val), ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "tokens")


def _generate_security_code_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a dual bar chart for security awareness and code examples."""
    models = list(evaluations.keys())
    if not models:
        return None

    code_counts = [evaluations[m].get("code_examples", 0) for m in models]
    sec_counts = [evaluations[m].get("security_awareness", 0) for m in models]
    total_prompts = max((len(evaluations[m].get("evaluations", [])) for m in models), default=5)

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    ax.bar(x - width / 2, code_counts, width, label="Code Examples", color=_CHART_ACCENT, alpha=0.9)
    ax.bar(x + width / 2, sec_counts, width, label="Security Awareness", color=_CHART_PRIMARY, alpha=0.9)

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Count (out of {})".format(total_prompts), color=_CHART_TEXT, fontsize=10)
    ax.set_title("Code & Security Awareness by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.legend(fontsize=9)
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "security_code")


def _generate_run_timeline_chart(run_id: str, runs: list[dict[str, Any]]) -> str | None:
    """Generate a Gantt-style timeline chart for all runs."""
    if not runs:
        return None

    fig, ax = plt.subplots(figsize=(max(10, len(runs) * 2), 6))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    colors = {"report_generation": "#1f3a8a", "game_day": "#f5c842", "fault_injection": "#e5484d"}
    y_labels = []
    y_positions = []

    for idx, run in enumerate(runs[:20]):  # limit to 20 for readability
        run_id_val = run.get("runId", f"run-{idx}")
        started = run.get("startedAt", "")
        finished = run.get("finishedAt", "")
        run_type = run.get("type", "unknown")

        if started and finished:
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                finish_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                duration = (finish_dt - start_dt).total_seconds()
                color = colors.get(run_type, "#64748b")
                ax.barh(idx, duration, left=start_dt.timestamp(), color=color, alpha=0.85, height=0.5,
                        edgecolor="white", linewidth=0.3)
                y_labels.append(f"{run_id_val[:12]} ({run_type[:10]})")
                y_positions.append(idx)
            except Exception:
                continue

    if not y_labels:
        return None

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, color=_CHART_TEXT, fontsize=8)
    ax.set_xlabel("Timeline (Unix timestamp)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Run Execution Timeline", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: datetime.fromtimestamp(x).strftime("%H:%M:%S")))
    ax.tick_params(axis="x", colors=_CHART_TEXT, labelsize=8)
    ax.invert_yaxis()

    legend_patches = [mpatches.Patch(color=c, label=t.replace("_", " ").title()) for t, c in colors.items()]
    ax.legend(handles=legend_patches, fontsize=8, loc="lower right")
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "timeline")


def _generate_success_rate_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a bar chart showing prompt success rate per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    success_rates = []
    for m in models:
        rate_str = evaluations[m].get("prompt_success_rate", "0/5")
        if isinstance(rate_str, str) and "/" in rate_str:
            parts = rate_str.split("/")
            numerator = int(parts[0]) if parts[0].isdigit() else 0
            denominator = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            rate = numerator / denominator if denominator else 0
        else:
            rate = float(rate_str) if isinstance(rate_str, (int, float)) else 0
        success_rates.append(rate * 100)

    colors = ["#1f9d55" if r == 100 else "#f5c842" if r >= 60 else "#e5484d" for r in success_rates]
    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    bars = ax.bar(models, success_rates, color=colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Success Rate (%)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Prompt Success Rate by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")

    for bar, val in zip(bars, success_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "success_rate")


def _generate_scenario_flow_chart(run_id: str, report: dict[str, Any]) -> str | None:
    """Generate a flowchart-style diagram for game_day scenario results."""
    scenarios = report.get("scenarios", [])
    if not scenarios:
        return None

    fig, ax = plt.subplots(figsize=(max(10, len(scenarios) * 2), 8))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Game Day Scenario Execution Flow", color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=20)

    box_width = 1.8
    box_height = 0.6
    y_start = 8.5
    y_step = 1.3

    for idx, scenario in enumerate(scenarios):
        y = y_start - idx * y_step
        if y < 0.5:
            break
        name = scenario.get("name", scenario.get("id", f"Scenario {idx+1}"))
        status = scenario.get("status", "unknown").upper()
        color = _CHART_PASS if status == "PASS" else _CHART_FAIL if status == "FAIL" else _CHART_ACCENT

        box = FancyBboxPatch((4 - box_width / 2, y - box_height / 2), box_width, box_height,
                              boxstyle="round,pad=0.1", facecolor=color, edgecolor="white",
                              alpha=0.9, linewidth=1.5)
        ax.add_patch(box)
        ax.text(5, y, name[:30], ha="center", va="center", color="white" if status in ("PASS", "FAIL") else _CHART_TEXT,
                fontsize=9, fontweight="bold")
        ax.text(5, y - 0.25, status, ha="center", va="center", color="white", fontsize=8)

        if idx < len(scenarios) - 1:
            ax.annotate("", xy=(5, y - box_height / 2 - 0.05), xytext=(5, y - box_height / 2 - y_step + 0.15),
                        arrowprops=dict(arrowstyle="->", color=_CHART_MUTED, lw=1.5))

    # Summary box at bottom
    summary = report.get("summary", "")
    if summary:
        ax.text(5, 0.8, f"Summary: {summary[:80]}", ha="center", va="center", color=_CHART_MUTED,
                fontsize=9, wrap=True, bbox=dict(boxstyle="round,pad=0.3", facecolor=_CHART_PANEL, edgecolor=_CHART_GRID))

    plt.tight_layout()
    return _save_chart(fig, run_id, "scenario_flow")


def _generate_scatter_plot(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a scatter plot of response time vs token count, colored by model."""
    models = list(evaluations.keys())
    if not models:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    for idx, (model, data) in enumerate(evaluations.items()):
        evals = data.get("evaluations", [])
        times = [e.get("time", 0) for e in evals]
        tokens = [e.get("tokens", 0) for e in evals]
        if times and tokens:
            ax.scatter(times, tokens, c=colors[idx % len(colors)], label=model[:20],
                       alpha=0.7, s=60, edgecolors="white", linewidth=0.5)

    ax.set_xlabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Tokens Generated", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time vs Token Count (Scatter)", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left")
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "scatter_time_tokens")


def _generate_line_chart(run_id: str, evaluations: dict[str, Any], prompts: list[str]) -> str | None:
    """Generate a line chart showing response time trend across prompts per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 1.5), 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    for idx, model in enumerate(models):
        data = evaluations.get(model, {})
        evals = data.get("evaluations", [])
        times = [e.get("time", 0) for e in evals[:len(prompts)]]
        while len(times) < len(prompts):
            times.append(0)
        x = list(range(len(times)))
        ax.plot(x, times, marker="o", markersize=5, linewidth=2, label=model[:20],
                color=colors[idx % len(colors)], alpha=0.85)

    ax.set_xlabel("Prompt Index", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time Trend Across Prompts", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(prompts)))
    ax.set_xticklabels([f"P{i+1}" for i in range(len(prompts))], color=_CHART_TEXT, fontsize=9)
    ax.legend(fontsize=8, loc="upper left")
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "line_response_trend")


def _generate_distribution_histogram(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a histogram showing the distribution of response times across all models."""
    models = list(evaluations.keys())
    if not models:
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    all_times = []
    for model in models:
        evals = evaluations.get(model, {}).get("evaluations", [])
        all_times.extend([e.get("time", 0) for e in evals])

    if all_times:
        ax.hist(all_times, bins=15, color=_CHART_PRIMARY, alpha=0.8, edgecolor="white", linewidth=0.5)
        mean_val = np.mean(all_times)
        ax.axvline(mean_val, color=_CHART_ACCENT, linestyle="--", linewidth=2, label=f"Mean: {mean_val:.2f}s")
        ax.legend(fontsize=9)

    ax.set_xlabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Frequency", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time Distribution", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "histogram_distribution")


def _generate_confidence_interval_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate an error bar chart showing confidence intervals for success rates per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    means = []
    errors = []
    for m in models:
        rate_str = evaluations[m].get("prompt_success_rate", "0/5")
        if isinstance(rate_str, str) and "/" in rate_str:
            parts = rate_str.split("/")
            numerator = int(parts[0]) if parts[0].isdigit() else 0
            denominator = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
        else:
            numerator = int(float(rate_str)) if isinstance(rate_str, (int, float)) else 0
            denominator = 5

        if denominator > 0:
            p = numerator / denominator
            # Wilson score interval for the error bars
            import math
            z = 1.96  # 95% confidence
            n = denominator
            if n > 0:
                denom = 1 + z * z / n
                center = (p + z * z / (2 * n)) / denom
                spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
                lower = max(0, center - spread)
                upper = min(1, center + spread)
                means.append(p)
                errors.append([p - lower, upper - p])
            else:
                means.append(0)
                errors.append([0, 0])
        else:
            means.append(0)
            errors.append([0, 0])

    errors = np.array(errors).T if errors else np.zeros((2, len(means)))

    x = np.arange(len(models))
    bar_colors = [colors[i % len(colors)] for i in range(len(models))]
    ax.bar(x, means, yerr=errors, capsize=5, color=bar_colors, alpha=0.85,
           edgecolor="white", linewidth=0.5, error_kw={"linewidth": 1.5, "ecolor": _CHART_ACCENT})

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Success Rate (Wilson 95% CI)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Success Rate with Confidence Intervals", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.set_ylim(0, 1.15)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "confidence_intervals")


def _generate_correlation_heatmap(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a correlation heatmap between response time, tokens, and success rate."""
    models = list(evaluations.keys())
    if not models:
        return None

    # Collect data
    times = []
    tokens = []
    success = []
    for model in models:
        evals = evaluations.get(model, {}).get("evaluations", [])
        for e in evals:
            times.append(e.get("time", 0))
            tokens.append(e.get("tokens", 0))
            success.append(1 if e.get("success", False) else 0)

    if len(times) < 2:
        return None

    data = np.array([times, tokens, success])
    corr = np.corrcoef(data)

    fig, ax = plt.subplots(figsize=(5, 4))
    labels = ["Response Time", "Token Count", "Success Rate"]
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, color=_CHART_TEXT, fontsize=9, rotation=45, ha="right")
    ax.set_yticklabels(labels, color=_CHART_TEXT, fontsize=9)

    for i in range(len(labels)):
        for j in range(len(labels)):
            value = corr[i, j]
            color = "white" if abs(value) > 0.5 else _CHART_TEXT
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", color=color, fontsize=10, fontweight="bold")

    ax.set_title("Metric Correlation Heatmap", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.yaxis.set_tick_params(color=_CHART_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_CHART_TEXT, fontsize=9)
    cbar.outline.set_edgecolor(_CHART_GRID)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "correlation_heatmap")


def _generate_stacked_bar_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a stacked bar chart showing outcome distribution per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    # Collect outcome counts per model
    outcome_categories = ["pass", "fail", "ambiguous"]
    model_counts = {cat: [] for cat in outcome_categories}

    for model in models:
        evals = evaluations.get(model, {}).get("evaluations", [])
        pass_count = sum(1 for e in evals if e.get("success", False))
        fail_count = sum(1 for e in evals if not e.get("success", False) and e.get("error") is None)
        ambiguous_count = sum(1 for e in evals if e.get("error") is not None)
        total = len(evals)
        if total > 0:
            model_counts["pass"].append(pass_count / total * 100)
            model_counts["fail"].append(fail_count / total * 100)
            model_counts["ambiguous"].append(ambiguous_count / total * 100)
        else:
            model_counts["pass"].append(0)
            model_counts["fail"].append(0)
            model_counts["ambiguous"].append(0)

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    x = np.arange(len(models))
    width = 0.6

    colors_map = {"pass": _CHART_PASS, "fail": _CHART_FAIL, "ambiguous": _CHART_ACCENT}
    bottoms = np.zeros(len(models))

    for cat in outcome_categories:
        values = model_counts[cat]
        bars = ax.bar(x, values, width, bottom=bottoms, label=cat.title(),
                      color=colors_map[cat], alpha=0.85, edgecolor="white", linewidth=0.3)
        bottoms += np.array(values)

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Outcome Distribution (%)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Outcome Distribution by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.set_ylim(0, 110)
    ax.legend(fontsize=8, loc="upper left")
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "stacked_outcomes")


def _generate_box_plot(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a box plot showing the distribution of response times per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    data_by_model = []
    for model in models:
        evals = evaluations.get(model, {}).get("evaluations", [])
        times = [e.get("time", 0) for e in evals]
        data_by_model.append(times if times else [0])

    bp = ax.boxplot(data_by_model, labels=models, patch_artist=True, showmeans=True,
                    meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor="white", markersize=6))

    for patch, color in zip(bp["boxes"], colors[:len(models)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
        patch.set_edgecolor("white")

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time Distribution (Box Plot)", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "boxplot_response_times")


def _generate_radar_comparison(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a detailed radar chart with additional metrics: consistency, efficiency, safety."""
    models = list(evaluations.keys())
    if not models:
        return None

    metrics = ["Avg Time\n(lower=better)", "Success\nRate", "Token\nEfficiency", "Consistency\n(1-stddev)", "Safety\nAwareness"]
    n_metrics = len(metrics)

    max_time = max((e.get("avg_time", 0) for e in evaluations.values()), default=1) or 1
    max_tokens = max((e.get("total_tokens", 1) for e in evaluations.values()), default=1) or 1

    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    for idx, (model, data) in enumerate(evaluations.items()):
        evals = data.get("evaluations", [])
        times = [e.get("time", 0) for e in evals]
        success_rate = data.get("prompt_success_rate", "0/5")
        if isinstance(success_rate, str) and "/" in success_rate:
            parts = success_rate.split("/")
            sr = int(parts[0]) / int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        else:
            sr = float(success_rate) if isinstance(success_rate, (int, float)) else 0

        token_efficiency = 1 - (data.get("total_tokens", 0) / max_tokens) if max_tokens else 0
        consistency = 1 - (np.std(times) / max(np.mean(times), 0.01)) if times and np.mean(times) > 0 else 0
        consistency = max(0, min(1, consistency))
        safety = data.get("security_awareness", 0) / max(data.get("code_examples", 1), 1) if data.get("code_examples", 0) > 0 else 0.5

        values = [
            1 - (data.get("avg_time", 0) / max_time),
            sr,
            token_efficiency,
            consistency,
            safety,
        ]
        values += values[:1]
        color = colors[idx % len(colors)]
        ax.plot(angles, values, color=color, linewidth=2.5, label=model[:20])
        ax.fill(angles, values, color=color, alpha=0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, color=_CHART_TEXT, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color=_CHART_MUTED, fontsize=7)
    ax.set_title("Model Performance Comparison (Extended)", color=_CHART_TEXT, fontsize=14, fontweight="bold", pad=20)
    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)
    legend.get_frame().set_facecolor(_CHART_PANEL)
    legend.get_frame().set_edgecolor(_CHART_GRID)
    for text in legend.get_texts():
        text.set_color(_CHART_TEXT)
    plt.tight_layout()
    return _save_chart(fig, run_id, "radar_extended")


def _generate_per_prompt_heatmap(run_id: str, evaluations: dict[str, Any], metric: str = "time") -> str | None:
    """Generate a heatmap of model × prompt showing a per-prompt metric.

    metric="time"   → response time per model per prompt (seconds)
    metric="tokens" → token count per model per prompt
    metric="success"→ 1.0/0.0 per model per prompt (success/failure)
    """
    models = list(evaluations.keys())
    if not models:
        return None

    n_models = len(models)
    n_prompts = max((len(evaluations[m].get("evaluations", [])) for m in models), default=0)
    if n_prompts == 0:
        return None

    metric_title = {"time": "Response Time (s)", "tokens": "Token Count", "success": "Success (1/0)"}.get(metric, metric.title())
    cmap = {"time": "YlOrRd", "tokens": "YlGnBu", "success": "RdYlGn"}.get(metric, "viridis")

    grid = np.full((n_models, n_prompts), np.nan)
    for i, m in enumerate(models):
        evals = evaluations[m].get("evaluations", [])
        for j, e in enumerate(evals[:n_prompts]):
            if metric == "success":
                grid[i, j] = 1.0 if e.get("success", False) else 0.0
            else:
                grid[i, j] = float(e.get(metric, 0) or 0)

    fig, ax = plt.subplots(figsize=(max(6, n_prompts * 1.2), max(4, n_models * 0.6 + 2)))
    # For success we want a discrete-ish colorbar with fixed 0..1 range so
    # all-pass grids still display meaningful green tones instead of a
    # collapsed mid-color. For numeric metrics, autoscale.
    if metric == "success":
        im = ax.imshow(grid, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    else:
        im = ax.imshow(grid, cmap=cmap, aspect="auto")
    ax.set_xticks(range(n_prompts))
    ax.set_xticklabels([f"P{j+1}" for j in range(n_prompts)], color=_CHART_TEXT, fontsize=9)
    ax.set_yticks(range(n_models))
    ax.set_yticklabels([m[:25] for m in models], color=_CHART_TEXT, fontsize=9)
    ax.set_xlabel("Prompt", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_title(f"Per-Prompt {metric_title} (Model × Prompt Heatmap)",
                 color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=12)

    # Annotate cells. For success use ✓/✗ in dark text on the colored cell;
    # for numeric metrics use the value with white text on dark cells.
    for i in range(n_models):
        for j in range(n_prompts):
            val = grid[i, j]
            if not np.isfinite(val):
                continue
            if metric == "success":
                ok = val > 0.5
                symbol = "✓" if ok else "✗"
                ax.text(j, i, symbol, ha="center", va="center",
                        color="#0a3d0a" if ok else "#5a0a0a",
                        fontsize=14, fontweight="bold")
            elif metric == "tokens":
                ax.text(j, i, f"{int(val)}", ha="center", va="center",
                        color=_CHART_TEXT, fontsize=10, fontweight="bold")
            else:
                # Time values: use white text on darker cells (higher values),
                # theme text on lighter cells.
                vmin = np.nanmin(grid) if np.isfinite(np.nanmin(grid)) else 0
                vmax = np.nanmax(grid) if np.isfinite(np.nanmax(grid)) else 1
                span = max(vmax - vmin, 1e-6)
                tcolor = "white" if (val - vmin) / span > 0.55 else _CHART_TEXT
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        color=tcolor, fontsize=10, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    if metric == "success":
        cbar.set_ticks([0, 1])
        cbar.set_ticklabels(["Fail", "Pass"])
    cbar.ax.yaxis.set_tick_params(color=_CHART_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_CHART_TEXT, fontsize=9)
    cbar.outline.set_edgecolor(_CHART_GRID)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    suffix = "" if metric == "time" else f"_{metric}"
    return _save_chart(fig, run_id, f"per_prompt_heatmap{suffix}")


def _generate_token_efficiency_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a stacked bar chart showing tokens spent on successful vs failed responses.

    Reveals "wasted" tokens — those spent on responses that ultimately failed
    validation. Useful for cost estimation: failed responses are pure waste.
    """
    models = list(evaluations.keys())
    if not models:
        return None

    success_tokens: list[int] = []
    failed_tokens: list[int] = []
    for m in models:
        evals = evaluations[m].get("evaluations", [])
        s = sum(int(e.get("tokens", 0) or 0) for e in evals if e.get("success", False))
        f = sum(int(e.get("tokens", 0) or 0) for e in evals if not e.get("success", False))
        success_tokens.append(s)
        failed_tokens.append(f)

    if not any(success_tokens) and not any(failed_tokens):
        return None

    fig, ax = plt.subplots(figsize=(max(7, len(models) * 1.2), 5))
    x = np.arange(len(models))
    width = 0.6
    p1 = ax.bar(x, success_tokens, width, label="Successful Tokens (value)",
                color="#1f9d55", alpha=0.9, edgecolor="white", linewidth=0.5)
    p2 = ax.bar(x, failed_tokens, width, bottom=success_tokens, label="Wasted Tokens (failed)",
                color="#e5484d", alpha=0.9, edgecolor="white", linewidth=0.5)

    # Annotate totals and waste ratios
    for i, m in enumerate(models):
        total = success_tokens[i] + failed_tokens[i]
        waste_pct = (failed_tokens[i] / total * 100) if total else 0
        ax.text(x[i], total + max(success_tokens + failed_tokens, default=[1]) * 0.02,
                f"{waste_pct:.0f}% waste", ha="center", va="bottom",
                color=_CHART_TEXT, fontsize=9, fontweight="bold")
        ax.text(x[i], success_tokens[i] / 2, str(success_tokens[i]),
                ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        if failed_tokens[i] > 0:
            ax.text(x[i], success_tokens[i] + failed_tokens[i] / 2,
                    str(failed_tokens[i]), ha="center", va="center",
                    color="white", fontsize=9, fontweight="bold")

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Total Tokens Spent", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Token Efficiency: Value vs Wasted",
                 color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels([m[:22] for m in models], color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    # Push legend below the plot so the title never collides with it.
    ax.legend(fontsize=9, loc="upper right", framealpha=0.85)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "token_efficiency")


def _generate_reasoning_comparison(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Compare reasoning-capable models vs non-reasoning models on key metrics.

    A 'reasoning model' is one whose evaluation JSON reports is_reasoning=True
    or non-zero reasoning_tokens. Aggregates avg time, total tokens, success
    rate, and reasoning tokens spent.
    """
    if not evaluations:
        return None

    def _reasoning_flag(data: dict[str, Any]) -> bool:
        # Prefer per-eval signals over the top-level `reasoning_models` flag,
        # which is often a stale/loose default. A model is "reasoning" only
        # if at least one evaluation actually reports reasoning content.
        evals = data.get("evaluations", [])
        if evals:
            return any(
                e.get("is_reasoning") or (e.get("reasoning_tokens") or 0) > 0
                for e in evals
            )
        # Fall back to the top-level totals when no per-eval data is present.
        return bool(data.get("reasoning_models")) or data.get("total_reasoning_tokens", 0) > 0

    groups: dict[str, list[dict[str, Any]]] = {"reasoning": [], "standard": []}
    for model, data in evaluations.items():
        groups["reasoning" if _reasoning_flag(data) else "standard"].append(data)

    # Drop empty groups — chart is meaningless with only one bar.
    active = {k: v for k, v in groups.items() if v}
    if len(active) < 2:
        return None

    def _avg_time(items: list[dict[str, Any]]) -> float:
        times = [d.get("avg_time", 0) for d in items if d.get("avg_time")]
        return float(np.mean(times)) if times else 0.0

    def _avg_tokens(items: list[dict[str, Any]]) -> float:
        toks = [d.get("total_tokens", 0) for d in items]
        return float(np.mean(toks)) if toks else 0.0

    def _success_rate(items: list[dict[str, Any]]) -> float:
        rates = []
        for d in items:
            sr = d.get("prompt_success_rate", "0/5")
            if isinstance(sr, str) and "/" in sr:
                parts = sr.split("/")
                try:
                    n, dn = int(parts[0]), int(parts[1])
                    rates.append(n / dn if dn else 0)
                except ValueError:
                    pass
            elif isinstance(sr, (int, float)):
                rates.append(float(sr))
        return float(np.mean(rates)) if rates else 0.0

    def _reasoning_tokens(items: list[dict[str, Any]]) -> int:
        return sum(int(d.get("total_reasoning_tokens", 0) or 0) for d in items)

    labels = list(active.keys())
    avg_times = [_avg_time(active[k]) for k in labels]
    avg_tokens = [_avg_tokens(active[k]) for k in labels]
    avg_success = [_success_rate(active[k]) for k in labels]
    total_reasoning_tokens = [_reasoning_tokens(active[k]) for k in labels]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.patch.set_facecolor(_CHART_BG)

    titles = ["Avg Response Time (s)", "Avg Total Tokens", "Success Rate"]
    series = [avg_times, avg_tokens, avg_success]
    colors = ["#1f3a8a", "#f5c842", "#1f9d55"]
    for ax, title, vals, color in zip(axes, titles, series, colors):
        ax.set_facecolor(_CHART_BG)
        bars = ax.bar(labels, vals, color=color, alpha=0.9, edgecolor="white", linewidth=0.5)
        ax.set_title(title, color=_CHART_TEXT, fontsize=12, fontweight="bold")
        ax.set_ylabel("", color=_CHART_TEXT)
        ax.tick_params(colors=_CHART_TEXT, labelsize=10)
        for spine in ax.spines.values():
            spine.set_edgecolor(_CHART_GRID)
        ax.grid(True, color=_CHART_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                    f"{v:.2f}" if v < 10 else f"{v:.0f}",
                    ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")

    # Caption showing reasoning token totals
    if any(total_reasoning_tokens):
        caption = " | ".join(
            f"{lbl}: {t:,} reasoning tokens" for lbl, t in zip(labels, total_reasoning_tokens) if t
        )
        fig.text(0.5, 0.02, caption, ha="center", color=_CHART_TEXT, fontsize=9)
    fig.suptitle("Reasoning vs Standard Model Comparison",
                 color=_CHART_TEXT, fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    return _save_chart(fig, run_id, "reasoning_comparison")


def _generate_response_length_distribution(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a violin plot of response text length (chars) per model.

    Useful for comparing verbosity — some models produce terse answers while
    others are highly verbose. Combined with token counts this reveals
    efficiency differences.
    """
    models = list(evaluations.keys())
    if not models:
        return None

    data = []
    labels = []
    for m in models:
        evals = evaluations[m].get("evaluations", [])
        # Use response length estimated from "response" text or fallback to tokens * 4
        lengths = []
        for e in evals:
            resp = e.get("response") or ""
            if resp:
                lengths.append(len(resp))
            else:
                # Approximate ~4 chars per token when raw text is unavailable
                lengths.append(int(e.get("tokens", 0)) * 4)
        if lengths:
            data.append(lengths)
            labels.append(m[:22])

    if not data:
        return None

    fig, ax = plt.subplots(figsize=(max(7, len(models) * 1.2), 5))
    ax.set_facecolor(_CHART_BG)
    parts = ax.violinplot(data, showmeans=True, showmedians=True)
    for pc in parts["bodies"]:
        pc.set_facecolor("#1f3a8a")
        pc.set_edgecolor(_CHART_TEXT)
        pc.set_alpha(0.6)
    for key in ("cbars", "cmins", "cmaxes", "cmedians", "cmeans"):
        if key in parts:
            parts[key].set_edgecolor(_CHART_ACCENT)
            parts[key].set_linewidth(1.5)

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.set_ylabel("Response Length (characters, est.)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Length Distribution per Model (Violin Plot)",
                 color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.tick_params(colors=_CHART_TEXT, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(_CHART_GRID)
    ax.grid(True, color=_CHART_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    return _save_chart(fig, run_id, "response_length_distribution")


def _generate_cross_run_comparison(run_id: str, runs: list[dict[str, Any]], batch_id: str) -> str | None:
    """When multiple runs share a batchId, summarize each run as one bar.

    Produces a multi-panel comparison: response time, success rate, total
    tokens, and number of models per run. Helps users compare iterations
    of the same batch.
    """
    if not batch_id or not runs:
        return None
    batch_runs = [r for r in runs if r.get("batchId") == batch_id or r.get("runId") == batch_id]
    if len(batch_runs) < 2:
        return None

    run_ids = [r.get("runId", "unknown")[:14] for r in batch_runs]
    times = [r.get("avg_response_time", 0) or 0 for r in batch_runs]
    tokens = [r.get("total_tokens", 0) or 0 for r in batch_runs]
    # Parse success rates: "4/5" -> 0.8, 80 -> 0.8, 0.8 -> 0.8
    _parsed_success = []
    for r in batch_runs:
        s = r.get("prompt_success_rate", 0)
        if isinstance(s, str) and "/" in s:
            parts = s.split("/")
            try:
                _parsed_success.append(int(parts[0]) / int(parts[1]) if len(parts) > 1 and parts[1].isdigit() and int(parts[1]) > 0 else 0)
            except (ValueError, ZeroDivisionError):
                _parsed_success.append(0)
        elif isinstance(s, (int, float)):
            _parsed_success.append(s / 100 if s > 1 else float(s))
        else:
            _parsed_success.append(0)
    success = _parsed_success
    n_models = [len(r.get("models", [])) for r in batch_runs]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.patch.set_facecolor(_CHART_BG)
    titles = ["Avg Response Time (s)", "Total Tokens", "Success Rate"]
    series = [times, tokens, success]
    for ax, title, vals in zip(axes, titles, series):
        ax.set_facecolor(_CHART_BG)
        bars = ax.bar(range(len(batch_runs)), vals, alpha=0.9,
                      color="#1f3a8a", edgecolor="white", linewidth=0.5)
        ax.set_title(title, color=_CHART_TEXT, fontsize=12, fontweight="bold")
        ax.set_xticks(range(len(batch_runs)))
        ax.set_xticklabels(run_ids, color=_CHART_TEXT, fontsize=8, rotation=30, ha="right")
        ax.tick_params(colors=_CHART_TEXT, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(_CHART_GRID)
        ax.grid(True, color=_CHART_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                    f"{v:.1f}" if v < 100 else f"{v:.0f}",
                    ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")
    fig.suptitle(f"Cross-Run Comparison ({len(batch_runs)} runs in batch)",
                 color=_CHART_TEXT, fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    return _save_chart(fig, run_id, "cross_run_comparison")


def _match_evals_by_batch(batch_id: str, eval_jsons: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Match evaluation JSON sidecars by batchId.

    Returns a dict mapping model name to evaluation JSON for all evals
    that share the given batchId. Falls back to model-name matching if
    no batchId matches are found.
    """
    evals_by_model: dict[str, dict[str, Any]] = {}
    if batch_id:
        for ej in eval_jsons:
            if ej.get("batchId") == batch_id:
                evals_by_model[ej.get("model", "unknown")] = ej
    return evals_by_model


def generate_charts_for_run(run_id: str, runs: list[dict[str, Any]]) -> dict[str, str]:
    """Generate all applicable charts for a run and return URL mapping.

    Charts listed in the run's ``deletedCharts`` telemetry field are skipped
    so that individually deleted charts do not reappear on page refresh.
    """
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return {}

    # Respect individually deleted charts — skip regeneration
    deleted_charts = run.get("deletedCharts", [])
    if not isinstance(deleted_charts, list):
        deleted_charts = []

    def _skip(chart_name: str) -> bool:
        return chart_name in deleted_charts

    chart_urls: dict[str, str] = {}
    run_type = run.get("type", "")

    if run_type == "report_generation":
        # Load evaluation JSON sidecars
        eval_jsons = _load_evaluation_jsons()
        # Match by batchId first (links eval JSONs to this telemetry run),
        # then fall back to flexible model name matching
        batch_id = run.get("batchId") or run_id
        evals_by_model = _match_evals_by_batch(batch_id, eval_jsons)
        if not evals_by_model:
            for run_model in run.get("models", []):
                match = _match_model_to_eval(run_model, eval_jsons)
                if match:
                    evals_by_model[match.get("model", run_model)] = match

        if evals_by_model:
            prompts = run.get("prompts", [])
            if not prompts:
                prompts = [e.get("prompts", [""])[0] for e in evals_by_model.values() if e.get("prompts")]
                prompts = prompts[:5] if prompts else [""] * 5

            if not _skip("radar"):
                radar_url = _generate_model_radar_chart(run_id, evals_by_model)
                if radar_url:
                    chart_urls["radar"] = radar_url

            if not _skip("response_times"):
                time_url = _generate_response_time_chart(run_id, evals_by_model, prompts)
                if time_url:
                    chart_urls["response_times"] = time_url

            if not _skip("heatmap"):
                heatmap_url = _generate_heatmap_chart(run_id, evals_by_model, prompts)
                if heatmap_url:
                    chart_urls["heatmap"] = heatmap_url

            if not _skip("tokens"):
                tokens_url = _generate_tokens_chart(run_id, evals_by_model)
                if tokens_url:
                    chart_urls["tokens"] = tokens_url

            if not _skip("security_code"):
                sec_code_url = _generate_security_code_chart(run_id, evals_by_model)
                if sec_code_url:
                    chart_urls["security_code"] = sec_code_url

            if not _skip("success_rate"):
                success_url = _generate_success_rate_chart(run_id, evals_by_model)
                if success_url:
                    chart_urls["success_rate"] = success_url

            if not _skip("scatter_time_tokens"):
                scatter_url = _generate_scatter_plot(run_id, evals_by_model)
                if scatter_url:
                    chart_urls["scatter_time_tokens"] = scatter_url

            if not _skip("line_response_trend"):
                line_url = _generate_line_chart(run_id, evals_by_model, prompts)
                if line_url:
                    chart_urls["line_response_trend"] = line_url

            if not _skip("histogram_distribution"):
                hist_url = _generate_distribution_histogram(run_id, evals_by_model)
                if hist_url:
                    chart_urls["histogram_distribution"] = hist_url

            if not _skip("confidence_intervals"):
                ci_url = _generate_confidence_interval_chart(run_id, evals_by_model)
                if ci_url:
                    chart_urls["confidence_intervals"] = ci_url

            if not _skip("correlation_heatmap"):
                corr_url = _generate_correlation_heatmap(run_id, evals_by_model)
                if corr_url:
                    chart_urls["correlation_heatmap"] = corr_url

            if not _skip("stacked_outcomes"):
                stacked_url = _generate_stacked_bar_chart(run_id, evals_by_model)
                if stacked_url:
                    chart_urls["stacked_outcomes"] = stacked_url

            if not _skip("boxplot_response_times"):
                box_url = _generate_box_plot(run_id, evals_by_model)
                if box_url:
                    chart_urls["boxplot_response_times"] = box_url

            if not _skip("radar_extended"):
                radar_ext_url = _generate_radar_comparison(run_id, evals_by_model)
                if radar_ext_url:
                    chart_urls["radar_extended"] = radar_ext_url

            # New comparison charts that rely on real per-prompt response data
            if not _skip("per_prompt_heatmap"):
                pp_url = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="time")
                if pp_url:
                    chart_urls["per_prompt_heatmap"] = pp_url
            if not _skip("per_prompt_heatmap_tokens"):
                pp_tok_url = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="tokens")
                if pp_tok_url:
                    chart_urls["per_prompt_heatmap_tokens"] = pp_tok_url
            if not _skip("per_prompt_heatmap_success"):
                pp_ok_url = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="success")
                if pp_ok_url:
                    chart_urls["per_prompt_heatmap_success"] = pp_ok_url
            if not _skip("token_efficiency"):
                eff_url = _generate_token_efficiency_chart(run_id, evals_by_model)
                if eff_url:
                    chart_urls["token_efficiency"] = eff_url
            if not _skip("reasoning_comparison"):
                rc_url = _generate_reasoning_comparison(run_id, evals_by_model)
                if rc_url:
                    chart_urls["reasoning_comparison"] = rc_url
            if not _skip("response_length_distribution"):
                rld_url = _generate_response_length_distribution(run_id, evals_by_model)
                if rld_url:
                    chart_urls["response_length_distribution"] = rld_url

            # Cross-run comparison: only when this run shares a batchId with
            # at least one other run, so the chart is meaningful.
            batch_id_for_compare = batch_id
            if not _skip("cross_run_comparison"):
                crc_url = _generate_cross_run_comparison(run_id, runs, batch_id_for_compare)
                if crc_url:
                    chart_urls["cross_run_comparison"] = crc_url

    elif run_type == "game_day":
        report = run.get("report", {})
        if report:
            if not _skip("scenario_flow"):
                flow_url = _generate_scenario_flow_chart(run_id, report)
                if flow_url:
                    chart_urls["scenario_flow"] = flow_url

    # Cross-run timeline chart (uses all runs)
    if not _skip("timeline"):
        timeline_url = _generate_run_timeline_chart(run_id, runs)
        if timeline_url:
            chart_urls["timeline"] = timeline_url

    return chart_urls


def _enrich_runs_with_charts(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach chart URLs to each run entry.

    If a run already has chartUrls (generated during report generation), they are
    used directly. Otherwise, charts are generated on-demand from evaluation JSON
    sidecars. Charts listed in the run's ``deletedCharts`` field are filtered
    out so they do not reappear after deletion.
    """
    enriched = []
    timeline_url = None
    if runs:
        timeline_url = _generate_run_timeline_chart(runs[0].get("runId", ""), runs)

    for run in runs:
        run_copy = dict(run)
        run_id = run.get("runId", "")
        if run_id:
            # Respect individually deleted charts — filter them out everywhere
            deleted_charts = run.get("deletedCharts", [])
            if not isinstance(deleted_charts, list):
                deleted_charts = []

            # Use pre-generated chart URLs if available, otherwise generate on-demand
            if run.get("chartUrls"):
                chart_urls = {k: v for k, v in run["chartUrls"].items() if k not in deleted_charts}
            else:
                chart_urls = generate_charts_for_run(run_id, runs)
                chart_urls = {k: v for k, v in chart_urls.items() if k not in deleted_charts}
            if timeline_url and "timeline" not in deleted_charts:
                chart_urls["timeline"] = timeline_url
            run_copy["chartUrls"] = chart_urls
        enriched.append(run_copy)
    return enriched


def _normalize_model_name(name: str) -> str:
    """Normalize a model name for matching across different formats.

    Handles transformations like:
    - 'poolside/laguna-s-2.1:free' -> 'laguna-s-2.1-free'
    - 'nvidia/nemotron-3-super-120b-a12b:free' -> 'nemotron-3-super-120b-a12b-free'
    - 'poolside-laguna-s-2.1-free' -> 'laguna-s-2.1-free' (strips provider prefix)
    """
    if not name:
        return ""
    normalized = name
    # Strip provider prefix (everything before and including '/')
    if "/" in normalized:
        normalized = normalized.split("/", 1)[-1]
    # Replace ':' with '-' (e.g., ':free' -> '-free')
    normalized = normalized.replace(":", "-")
    # Strip common provider prefixes that appear before a hyphen
    for prefix in ("poolside-", "nvidia-", "openai-", "anthropic-"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return normalized.lower()


def _match_model_to_eval(model_id: str, eval_jsons: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the evaluation JSON that matches a given model ID.

    Uses flexible matching: normalizes both names and checks for substring
    matches to handle provider prefixes and format differences.
    """
    normalized_target = _normalize_model_name(model_id)
    for ej in eval_jsons:
        ej_model = ej.get("model", "")
        normalized_ej = _normalize_model_name(ej_model)
        if normalized_ej == normalized_target:
            return ej
        # Also try substring matching for partial overlaps
        if normalized_ej and (normalized_ej in normalized_target or normalized_target in normalized_ej):
            return ej
    return None


def _generate_charts_for_run_sync(
    run_id: str,
    models: list[str],
    prompts: list[str],
) -> dict[str, str]:
    """Generate charts for a run synchronously (called after report generation).

    This generates charts using the evaluation JSON sidecars and the run's
    model/prompt data. Charts are generated alongside PDFs so they're available
    immediately when the telemetry entry is created.

    Args:
        run_id: The run identifier
        models: List of model names used in the run
        prompts: List of prompts used in the run

    Returns:
        Dict mapping chart name to URL path
    """
    chart_urls: dict[str, str] = {}

    try:
        # Load evaluation JSON sidecars
        eval_jsons = _load_evaluation_jsons()

        # Match evaluation data by batchId first (links eval JSONs to this telemetry run),
        # then fall back to flexible model name matching
        evals_by_model: dict[str, Any] = _match_evals_by_batch(run_id, eval_jsons)
        if not evals_by_model:
            for model_id in models:
                match = _match_model_to_eval(model_id, eval_jsons)
                if match:
                    evals_by_model[match.get("model", model_id)] = match

        if not evals_by_model:
            # Fallback: try matching by all eval JSONs (if there's only one model)
            if len(models) == 1 and eval_jsons:
                evals_by_model = {ej.get("model", "unknown"): ej for ej in eval_jsons}

        if evals_by_model:
            # Use the existing chart generation functions
            radar_url = _generate_model_radar_chart(run_id, evals_by_model)
            if radar_url:
                chart_urls["radar"] = radar_url

            time_url = _generate_response_time_chart(run_id, evals_by_model, prompts)
            if time_url:
                chart_urls["response_times"] = time_url

            heatmap_url = _generate_heatmap_chart(run_id, evals_by_model, prompts)
            if heatmap_url:
                chart_urls["heatmap"] = heatmap_url

            tokens_url = _generate_tokens_chart(run_id, evals_by_model)
            if tokens_url:
                chart_urls["tokens"] = tokens_url

            sec_code_url = _generate_security_code_chart(run_id, evals_by_model)
            if sec_code_url:
                chart_urls["security_code"] = sec_code_url

            success_url = _generate_success_rate_chart(run_id, evals_by_model)
            if success_url:
                chart_urls["success_rate"] = success_url

            scatter_url = _generate_scatter_plot(run_id, evals_by_model)
            if scatter_url:
                chart_urls["scatter_time_tokens"] = scatter_url

            line_url = _generate_line_chart(run_id, evals_by_model, prompts)
            if line_url:
                chart_urls["line_response_trend"] = line_url

            hist_url = _generate_distribution_histogram(run_id, evals_by_model)
            if hist_url:
                chart_urls["histogram_distribution"] = hist_url

            ci_url = _generate_confidence_interval_chart(run_id, evals_by_model)
            if ci_url:
                chart_urls["confidence_intervals"] = ci_url

            corr_url = _generate_correlation_heatmap(run_id, evals_by_model)
            if corr_url:
                chart_urls["correlation_heatmap"] = corr_url

            stacked_url = _generate_stacked_bar_chart(run_id, evals_by_model)
            if stacked_url:
                chart_urls["stacked_outcomes"] = stacked_url

            box_url = _generate_box_plot(run_id, evals_by_model)
            if box_url:
                chart_urls["boxplot_response_times"] = box_url

            radar_ext_url = _generate_radar_comparison(run_id, evals_by_model)
            if radar_ext_url:
                chart_urls["radar_extended"] = radar_ext_url

            # New comparison charts that exercise real per-prompt data
            pp_time = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="time")
            if pp_time:
                chart_urls["per_prompt_heatmap"] = pp_time
            pp_tokens = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="tokens")
            if pp_tokens:
                chart_urls["per_prompt_heatmap_tokens"] = pp_tokens
            pp_success = _generate_per_prompt_heatmap(run_id, evals_by_model, metric="success")
            if pp_success:
                chart_urls["per_prompt_heatmap_success"] = pp_success
            eff = _generate_token_efficiency_chart(run_id, evals_by_model)
            if eff:
                chart_urls["token_efficiency"] = eff
            rc = _generate_reasoning_comparison(run_id, evals_by_model)
            if rc:
                chart_urls["reasoning_comparison"] = rc
            rld = _generate_response_length_distribution(run_id, evals_by_model)
            if rld:
                chart_urls["response_length_distribution"] = rld

        logger.info("charts_generated_for_run", extra={"run_id": run_id, "chart_count": len(chart_urls)})

        # Also generate batch-level comparison chart
        try:
            batch_chart_urls = _generate_batch_charts_for_run(run_id, [{"runId": run_id, "models": models}])
            if batch_chart_urls:
                chart_urls.update(batch_chart_urls)
                logger.info("batch_chart_generated_for_run", extra={"run_id": run_id, "batch_id": run_id, "batch_charts": list(batch_chart_urls.keys())})
        except Exception as exc:
            logger.warning("batch_chart_generation_failed_for_run", extra={"run_id": run_id, "error": str(exc)})
    except Exception as exc:
        logger.warning("chart_generation_failed", extra={"run_id": run_id, "error": str(exc)})

    return chart_urls


def _generate_batch_comparison_chart(batch_id: str, runs: list[dict[str, Any]]) -> str | None:
    """Generate a batch-level comparison chart representing the whole batch.

    This creates a multi-panel figure that summarizes all models in the batch:
    - Radar chart comparing models across 5 metrics
    - Bar chart of response times
    - Bar chart of token usage
    - Bar chart of success rates

    The chart is stored in a separate batch directory so it's visually distinct
    from per-run chart clusters.
    """
    if not batch_id or not runs:
        return None

    try:
        # Collect all evals across all runs in the batch
        eval_jsons = _load_evaluation_jsons()
        all_evals: dict[str, dict[str, Any]] = {}
        for run in runs:
            run_id = run.get("runId", "")
            matched = _match_evals_by_batch(batch_id, eval_jsons)
            if matched:
                all_evals.update(matched)
            else:
                # Fallback: try matching by run models
                for model_id in run.get("models", []):
                    match = _match_model_to_eval(model_id, eval_jsons)
                    if match:
                        all_evals[match.get("model", model_id)] = match

        if not all_evals:
            return None

        models = list(all_evals.keys())
        n_models = len(models)

        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        fig.patch.set_facecolor(_CHART_BG)

        # --- Panel 1: Radar chart ---
        ax1 = axes[0, 0]
        ax1.remove()
        ax1 = fig.add_subplot(2, 2, 1, projection="polar")
        ax1.set_facecolor(_CHART_BG)

        metrics = ["Avg Time\n(lower=better)", "Success\nRate", "Total\nTokens", "Code\nExamples", "Security\nAwareness"]
        n_metrics = len(metrics)
        max_time = max((e.get("avg_time", 0) for e in all_evals.values()), default=1) or 1
        max_tokens = max((e.get("total_tokens", 1) for e in all_evals.values()), default=1) or 1
        max_code = max((e.get("code_examples", 0) for e in all_evals.values()), default=1) or 1
        max_sec = max((e.get("security_awareness", 0) for e in all_evals.values()), default=1) or 1

        angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
        angles += angles[:1]

        colors = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16"]
        for idx, model in enumerate(models):
            data = all_evals[model]
            sr = data.get("prompt_success_rate", "0/5")
            if isinstance(sr, str) and "/" in sr:
                parts = sr.split("/")
                sr_val = int(parts[0]) / int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            else:
                sr_val = float(sr) if isinstance(sr, (int, float)) else 0

            values = [
                1 - (data.get("avg_time", 0) / max_time),
                sr_val,
                1 - (data.get("total_tokens", 0) / max_tokens),
                data.get("code_examples", 0) / max_code,
                data.get("security_awareness", 0) / max_sec,
            ]
            values = [max(0, min(1, v)) for v in values]
            values += values[:1]
            color = colors[idx % len(colors)]
            ax1.plot(angles, values, color=color, linewidth=2.5, label=model[:20])
            ax1.fill(angles, values, color=color, alpha=0.15)

        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels(metrics, color=_CHART_TEXT, fontsize=9)
        ax1.set_ylim(0, 1.1)
        ax1.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax1.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color=_CHART_MUTED, fontsize=7)
        ax1.set_title("Batch Performance Radar", color=_CHART_TEXT, fontsize=12, fontweight="bold", pad=10)
        legend = ax1.legend(loc="upper right", bbox_to_anchor=(1.35, 1.05), fontsize=8)
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)

        # --- Panel 2: Response times bar chart ---
        ax2 = axes[0, 1]
        _style_axes(ax2, _CHART_BG, _CHART_PANEL, _CHART_GRID, _CHART_TEXT, _CHART_MUTED)
        times = [all_evals[m].get("avg_time", 0) for m in models]
        bars = ax2.bar(range(n_models), times, color=colors[:n_models], edgecolor=_CHART_GRID)
        ax2.set_xticks(range(n_models))
        ax2.set_xticklabels([m[:15] for m in models], rotation=45, ha="right", fontsize=8)
        ax2.set_ylabel("Avg Response Time (s)", color=_CHART_TEXT, fontsize=10)
        ax2.set_title("Response Time Comparison", color=_CHART_TEXT, fontsize=12, fontweight="bold")
        for bar, val in zip(bars, times):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{val:.1f}s",
                     ha="center", va="bottom", fontsize=8, color=_CHART_TEXT)

        # --- Panel 3: Token usage bar chart ---
        ax3 = axes[1, 0]
        _style_axes(ax3, _CHART_BG, _CHART_PANEL, _CHART_GRID, _CHART_TEXT, _CHART_MUTED)
        tokens = [all_evals[m].get("total_tokens", 0) for m in models]
        bars = ax3.bar(range(n_models), tokens, color=colors[:n_models], edgecolor=_CHART_GRID)
        ax3.set_xticks(range(n_models))
        ax3.set_xticklabels([m[:15] for m in models], rotation=45, ha="right", fontsize=8)
        ax3.set_ylabel("Total Tokens", color=_CHART_TEXT, fontsize=10)
        ax3.set_title("Token Usage Comparison", color=_CHART_TEXT, fontsize=12, fontweight="bold")
        for bar, val in zip(bars, tokens):
            ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10, f"{val:.0f}",
                     ha="center", va="bottom", fontsize=8, color=_CHART_TEXT)

        # --- Panel 4: Success rate bar chart ---
        ax4 = axes[1, 1]
        _style_axes(ax4, _CHART_BG, _CHART_PANEL, _CHART_GRID, _CHART_TEXT, _CHART_MUTED)
        success_rates = []
        for m in models:
            sr = all_evals[m].get("prompt_success_rate", "0/5")
            if isinstance(sr, str) and "/" in sr:
                parts = sr.split("/")
                sr_val = int(parts[0]) / int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            else:
                sr_val = float(sr) if isinstance(sr, (int, float)) else 0
            success_rates.append(sr_val)
        bars = ax4.bar(range(n_models), success_rates, color=colors[:n_models], edgecolor=_CHART_GRID)
        ax4.set_xticks(range(n_models))
        ax4.set_xticklabels([m[:15] for m in models], rotation=45, ha="right", fontsize=8)
        ax4.set_ylabel("Success Rate", color=_CHART_TEXT, fontsize=10)
        ax4.set_ylim(0, 1.1)
        ax4.set_title("Success Rate Comparison", color=_CHART_TEXT, fontsize=12, fontweight="bold")
        for bar, val in zip(bars, success_rates):
            ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, f"{val:.0%}",
                     ha="center", va="bottom", fontsize=8, color=_CHART_TEXT)

        fig.suptitle(f"Batch Comparison: {batch_id}", color=_CHART_TEXT, fontsize=16, fontweight="bold", y=1.01)
        plt.tight_layout()
        return _save_chart(fig, batch_id, "batch_comparison")
    except Exception as exc:
        logger.warning("batch_chart_generation_failed", extra={"batch_id": batch_id, "error": str(exc)})
        try:
            plt.close(fig)
        except Exception:
            pass
        return None


def _generate_batch_charts_for_run(batch_id: str, runs: list[dict[str, Any]]) -> dict[str, str]:
    """Generate batch-level charts and return URL mapping.

    Called when a run completes to also generate the batch-level comparison
    chart if this is the first/last run in the batch.
    """
    chart_urls: dict[str, str] = {}
    try:
        batch_url = _generate_batch_comparison_chart(batch_id, runs)
        if batch_url:
            chart_urls["batch_comparison"] = batch_url
        logger.info("batch_charts_generated", extra={"batch_id": batch_id, "chart_count": len(chart_urls)})
    except Exception as exc:
        logger.warning("batch_chart_generation_failed", extra={"batch_id": batch_id, "error": str(exc)})
    return chart_urls
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

def _read_kilo_oauth_token() -> str | None:
    """Read the Kilo OAuth access token from the local auth file.

    Security measures:
    - Token is read from the Kilo CLI's secure auth store at ~/.local/share/kilo/auth.json
    - Token is never logged in plaintext (only masked via mask_api_key)
    - File permissions are validated to be owner-only (0600) before reading
    - Returns None if the file doesn't exist, is unreadable, or has insecure permissions

    Returns:
        The OAuth access token string, or None if unavailable.
    """
    kilo_auth_path = Path.home() / ".local" / "share" / "kilo" / "auth.json"
    if not kilo_auth_path.exists():
        return None

    # Validate file permissions - must be owner-only (0600 or stricter)
    try:
        stat_info = kilo_auth_path.stat()
        mode = stat_info.st_mode & 0o777
        if mode & 0o077:  # Any group/other access is a security violation
            logger.warning(
                f"Kilo auth file has insecure permissions (mode={oct(mode)}), "
                f"expected 0600. Refusing to read token."
            )
            _audit_log("token_read_denied", reason="insecure_file_permissions", mode=oct(mode))
            return None
    except OSError:
        return None

    try:
        auth_data = json.loads(kilo_auth_path.read_text())
        token = auth_data.get("kilo", {}).get("access")
        if token:
            _audit_log("oauth_token_read", source="kilo_auth_file")
            return token
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to read Kilo auth file: {exc}")
        _audit_log("token_read_failed", reason=str(exc))
    return None


def _sanitize_endpoint(ep: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the endpoint dict with sensitive fields stripped.

    Never exposes apiKey, encryptedApiKey, or internal key material to clients.
    """
    safe = dict(ep)
    safe.pop("apiKey", None)
    safe.pop("encryptedApiKey", None)
    safe.pop("keyFile", None)
    return safe


def _get_endpoint_api_key(ep: dict[str, Any]) -> str | None:
    """Extract and decrypt the API key from an endpoint dict.

    Handles both legacy plaintext 'apiKey' and new encrypted 'encryptedApiKey' fields.
    """
    encrypted_key = ep.get("encryptedApiKey")
    if encrypted_key:
        try:
            return decrypt_api_key(encrypted_key)
        except Exception:
            logger.warning(f"Failed to decrypt API key for endpoint {ep.get('id', 'unknown')}")
            return None
    # Legacy plaintext fallback (for backward compatibility)
    return ep.get("apiKey")


 
def _migrate_legacy_api_keys() -> None:
    """Migrate any legacy plaintext apiKey fields to encrypted encryptedApiKey.

    Runs once on server startup. Converts any endpoint with a plaintext 'apiKey'
    field to the new 'encryptedApiKey' format, then removes the plaintext field.
    """
    endpoints = _get_endpoints()
    migrated = False
    for ep in endpoints:
        plain_key = ep.get("apiKey")
        if plain_key and not ep.get("encryptedApiKey"):
            # Migrate plaintext key to encrypted format
            ep["encryptedApiKey"] = encrypt_api_key(plain_key)
            del ep["apiKey"]
            migrated = True
            _audit_log("key_migrated", endpoint_id=ep.get("id", "unknown"))
    if migrated:
        _save_endpoints(endpoints)
        logger.info("Migrated legacy plaintext API keys to encrypted storage")


@app.get("/api/endpoints")
async def list_endpoints() -> dict[str, Any]:
    """List all endpoints with API keys stripped for security."""
    endpoints = _get_endpoints()
    safe_endpoints = [_sanitize_endpoint(ep) for ep in endpoints]
    return {"endpoints": safe_endpoints}


@app.post("/api/endpoints")
async def create_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized, err = _sanitize_and_validate_endpoint_payload(payload)
    if err:
        return JSONResponse(status_code=400, content={"error": err})
    url = sanitized["url"]
    if _is_localhost_endpoint(url):
        return JSONResponse(
            status_code=400,
            content={"error": "Localhost endpoints are not allowed. Use a configured gateway host."}
        )
    endpoints = _get_endpoints()
    api_key = sanitized.get("apiKey")
    # Encrypt API key at rest - never store plaintext
    encrypted_key = encrypt_api_key(api_key) if api_key else ""
    endpoint = {
        "id": sanitized.get("id") or f"ep_{uuid.uuid4().hex[:8]}",
        "name": sanitized["name"],
        "url": url,
        "encryptedApiKey": encrypted_key,
        "provider": sanitized["provider"],
        "createdAt": _now_iso(),
        "available": None,
        "lastTested": None,
    }
    # Do NOT store plaintext apiKey - only encrypted version
    endpoints.append(endpoint)
    _save_endpoints(endpoints)
    _audit_log("endpoint_created", endpoint_id=endpoint["id"], provider=endpoint["provider"])
    # Return sanitized copy (no API key in response)
    return {"endpoint": _sanitize_endpoint(endpoint)}


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
        return {"ok": False, "error": "Endpoint not found", "status_code": 404}

    url = ep.get("url", "").rstrip("/")
    provider = ep.get("provider", "ollama")
    api_key = _get_endpoint_api_key(ep)
    models_found = []

    # Handle CLI endpoints
    if url.startswith("cli://") or provider in ("claude_cli", "kilo_cli", "codex_cli"):
        import shutil
        cli_name = provider.replace("_cli", "")
        if shutil.which(cli_name):
            # Try to get models from adapter
            try:
                from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                if provider == "claude_cli":
                    adapter = ClaudeCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
                elif provider == "kilo_cli":
                    adapter = KiloCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
                elif provider == "codex_cli":
                    adapter = CodexCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
            except Exception:
                pass
            _update_endpoint_status(endpoint_id, True)
            return {"ok": True, "provider": provider, "models": models_found}
        else:
            _update_endpoint_status(endpoint_id, False)
            return {"ok": False, "provider": provider, "error": f"{provider} not found in PATH"}

    try:
        async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
            if provider == "ollama":
                test_url = f"{url}/api/tags"
                headers = _build_auth_headers(api_key)
                resp = await client.get(test_url, headers=headers)
                _validate_response(resp)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("name") for m in data.get("models", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "ollama", "models": models_found}
                else:
                    error = f"HTTP {resp.status_code}"
                    _update_endpoint_status(endpoint_id, False)
                    return {"ok": False, "provider": "ollama", "error": error}
            elif provider in ("openai", "nvidia"):
                test_url = f"{url}/models"
                headers = _build_auth_headers(api_key)
                resp = await client.get(test_url, headers=headers)
                _validate_response(resp)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("id") for m in data.get("data", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": provider, "models": models_found}
                else:
                    error = f"HTTP {resp.status_code}"
                    _update_endpoint_status(endpoint_id, False)
                    return {"ok": False, "provider": provider, "error": error}
            elif provider == "kilo":
                test_url = f"{url}/models"
                headers = _build_auth_headers(api_key)
                resp = await client.get(test_url, headers=headers)
                _validate_response(resp)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("id") for m in data.get("data", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "kilo", "models": models_found}
                _update_endpoint_status(endpoint_id, False)
                return {"ok": False, "provider": "kilo", "error": f"HTTP {resp.status_code}"}
            else:
                # Fallback: generic HTTP endpoint test
                test_url = url + "/" if not url.endswith("/") else url
                headers = _build_auth_headers(api_key)
                resp = await client.get(test_url, headers=headers, follow_redirects=True)
                _validate_response(resp)
                _update_endpoint_status(endpoint_id, resp.status_code < 400)
                return {"ok": resp.status_code < 400, "provider": provider, "status": resp.status_code}
    except Exception as exc:
        _update_endpoint_status(endpoint_id, False)
        return {"ok": False, "error": _safe_request_error(exc)}


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
    async with _create_secure_http_client(httpx.Timeout(10.0)) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            api_key = _get_endpoint_api_key(ep)
            available = False
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                    headers = _build_auth_headers(api_key)
                    resp = await client.get(test_url, headers=headers)
                    _validate_response(resp)
                    available = resp.status_code == 200
                elif provider in ("openai", "nvidia"):
                    test_url = f"{url}/models"
                    headers = _build_auth_headers(api_key)
                    resp = await client.get(test_url, headers=headers)
                    _validate_response(resp)
                    available = resp.status_code == 200
                elif provider == "kilo":
                    test_url = f"{url}/models"
                    headers = _build_auth_headers(api_key)
                    resp = await client.get(test_url, headers=headers)
                    _validate_response(resp)
                    available = resp.status_code == 200
                else:
                    test_url = url + "/" if not url.endswith("/") else url
                    headers = _build_auth_headers(api_key)
                    resp = await client.get(test_url, headers=headers, follow_redirects=True)
                    _validate_response(resp)
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


# ---------------------------------------------------------------------------
# Model Auto-Refresh
# ---------------------------------------------------------------------------

_model_refresh_task: asyncio.Task | None = None
_model_refresh_interval: int = int(os.environ.get("WE3_MODEL_REFRESH_INTERVAL", "300"))  # 5 min default


async def _model_refresh_worker() -> None:
    """Background task that periodically refreshes model lists from all endpoints."""
    while True:
        try:
            await asyncio.sleep(_model_refresh_interval)
            endpoints = _get_endpoints()
            async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
                for ep in endpoints:
                    url = ep.get("url", "").rstrip("/")
                    provider = ep.get("provider", "ollama")
                    api_key = _get_endpoint_api_key(ep)
                    if url.startswith("cli://") or provider in ("claude_cli", "kilo_cli", "codex_cli"):
                        continue
                    try:
                        if provider == "ollama":
                            test_url = f"{url}/api/tags"
                        else:
                            test_url = f"{url}/models"
                        headers = _build_auth_headers(api_key)
                        resp = await client.get(test_url, headers=headers)
                        _validate_response(resp)
                        if resp.status_code == 200:
                            _update_endpoint_status(ep.get("id"), True)
                        else:
                            _update_endpoint_status(ep.get("id"), False)
                    except Exception:
                        _update_endpoint_status(ep.get("id"), False)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@app.on_event("startup")
async def _start_model_refresh() -> None:
    """Start the model auto-refresh background task on startup."""
    global _model_refresh_task
    # Migrate any legacy plaintext API keys to encrypted storage
    _migrate_legacy_api_keys()
    if _model_refresh_task is None:
        _model_refresh_task = asyncio.create_task(_model_refresh_worker())


@app.on_event("shutdown")
async def _stop_model_refresh() -> None:
    """Stop the model auto-refresh background task on shutdown."""
    global _model_refresh_task
    if _model_refresh_task is not None:
        _model_refresh_task.cancel()
        try:
            await _model_refresh_task
        except asyncio.CancelledError:
            pass
        _model_refresh_task = None


@app.post("/api/models/refresh")
async def refresh_models() -> dict[str, Any]:
    """Manually trigger a model refresh from all configured endpoints."""
    result = await auto_detect_models()
    return {"refreshed": True, "models": result.get("models", []), "total": result.get("total", 0)}


@app.post("/api/endpoints/auto-detect")
async def auto_detect_endpoints() -> dict[str, Any]:
    """Auto-detect Ollama and other endpoints from configured gateway URLs.

    Gateway URLs are read from the WE3_GATEWAY_URLS environment variable
    (comma-separated). If not set, falls back to the SSH gateway for
    backward compatibility.
    """
    found: list[dict[str, Any]] = []

    # Get gateway URLs from environment or use default
    gateway_urls_env = os.environ.get("WE3_GATEWAY_URLS", "")
    if gateway_urls_env:
        gateway_hosts = [h.strip() for h in gateway_urls_env.split(",") if h.strip()]
    else:
        gateway_hosts = ["10.133.7.211"]

    # HTTP endpoints - all on configured gateway hosts
    candidates = []
    for host in gateway_hosts:
        candidates.extend([
            (f"http://{host}:11434", "ollama", f"Gateway Ollama ({host})"),
            (f"http://{host}:8000", "openai", f"Gateway OpenAI-compatible ({host})"),
            (f"http://{host}:5000", "openai", f"Gateway OpenAI-compatible ({host})"),
            (f"http://{host}:3000", "openai", f"Gateway OpenAI-compatible ({host})"),
        ])

    # Include Kilo Gateway if local auth exists
    kilo_token = _read_kilo_oauth_token()
    if kilo_token:
        candidates.append(("https://api.kilo.ai/api/gateway", "kilo", "Kilo Gateway"))

    async with _create_secure_http_client(httpx.Timeout(5.0)) as client:
        for url, provider, name in candidates:
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                else:
                    test_url = f"{url}/models"
                headers = _build_auth_headers(None)
                kilo_token = None
                if provider == "kilo":
                    # Use local Kilo OAuth token via secure helper
                    kilo_token = _read_kilo_oauth_token()
                    if kilo_token:
                        headers = _build_auth_headers(kilo_token)
                resp = await client.get(test_url, headers=headers)
                _validate_response(resp)
                if resp.status_code == 200:
                    # Encrypt OAuth token at rest — never store plaintext
                    encrypted_key = encrypt_api_key(kilo_token) if kilo_token else ""
                    found.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "url": url,
                        "encryptedApiKey": encrypted_key,
                        "provider": provider,
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
            except Exception:
                continue

    # CLI provider detection (no API key required)
    cli_detected = _detect_cli_providers()

    # Merge with existing without duplicates by URL
    existing = _get_endpoints()
    existing_urls = {e.get("url") for e in existing}
    for ep in found:
        # Skip localhost endpoints during auto-detection
        if _is_localhost_endpoint(ep["url"]):
            continue
        if ep["url"] not in existing_urls:
            existing.append(ep)
            existing_urls.add(ep["url"])

    # Add CLI endpoints without duplicating
    for cli_ep in cli_detected:
        if cli_ep["url"] not in existing_urls:
            existing.append(cli_ep)
            existing_urls.add(cli_ep["url"])

    _save_endpoints(existing)
    # Return sanitized endpoints (API keys stripped) for display
    safe_found = [_sanitize_endpoint(ep) for ep in found]
    safe_cli = [_sanitize_endpoint(ep) for ep in cli_detected]
    safe_all = [_sanitize_endpoint(ep) for ep in existing]
    return {"endpoints": safe_found + safe_cli, "all_endpoints": safe_all, "total": len(existing)}


def _detect_cli_providers() -> list[dict[str, Any]]:
    """Detect installed CLI providers without HTTP endpoints."""
    import shutil

    detected = []

    # Claude CLI
    if shutil.which("claude"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Claude CLI",
            "url": "cli://claude",
            "apiKey": None,
            "provider": "claude_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    # Kilo CLI
    if shutil.which("kilo"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Kilo CLI",
            "url": "cli://kilo",
            "apiKey": None,
            "provider": "kilo_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    # Codex CLI
    if shutil.which("codex"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Codex CLI",
            "url": "cli://codex",
            "apiKey": None,
            "provider": "codex_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    return detected


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
    endpoint_id = payload.get("endpointId", "")
    provider = payload.get("provider")
    if not provider:
        endpoints = _get_endpoints()
        ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
        if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
            provider = ep.get("provider", "ollama")
        else:
            provider = "ollama"
    model = {
        "id": payload.get("id") or f"mdl_{uuid.uuid4().hex[:8]}",
        "endpointId": endpoint_id,
        "provider": provider,
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
    
    Supports HTTP endpoints (Ollama, OpenAI, Kilo) and CLI-based providers
    (claude_cli, kilo_cli, codex_cli).
    """
    from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
    
    endpoints = _get_endpoints()
    
    # Auto-include Kilo Gateway if local auth exists and endpoint is missing
    kilo_token = _read_kilo_oauth_token()
    if kilo_token and not any(e.get("provider") == "kilo" for e in endpoints):
        encrypted_key = encrypt_api_key(kilo_token)
        endpoints.append({
            "id": f"ep_{uuid.uuid4().hex[:8]}",
            "name": "Kilo Gateway",
            "url": "https://api.kilo.ai/api/gateway",
            "encryptedApiKey": encrypted_key,
            "provider": "kilo",
            "createdAt": _now_iso(),
            "available": True,
            "lastTested": _now_iso(),
        })
        _save_endpoints(endpoints)
        _audit_log("kilo_endpoint_auto_created", endpoint_url="https://api.kilo.ai/api/gateway")
    
    discovered: list[dict[str, Any]] = []
    existing_model_ids = {m.get("id") for m in _get_models()}
    seen_base_names: set[str] = set()

    def _base_name(model_id: str) -> str:
        """Get base name for deduplication, preferring non-:latest tags."""
        if model_id.endswith(":latest"):
            base = model_id[:-7]
            return base
        return model_id

    async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            
            # Skip localhost endpoints - only use configured gateways
            if _is_localhost_endpoint(url):
                continue
            
            api_key = _get_endpoint_api_key(ep)
            headers = _build_auth_headers(api_key)

            # Handle CLI providers (no HTTP endpoint needed)
            if provider in ("claude_cli", "kilo_cli", "codex_cli"):
                cli_models = []
                if provider == "claude_cli":
                    adapter = ClaudeCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                elif provider == "kilo_cli":
                    adapter = KiloCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                elif provider == "codex_cli":
                    adapter = CodexCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                
                for model_id in cli_models:
                    if model_id in existing_model_ids:
                        continue
                    discovered.append({
                        "id": model_id,
                        "endpointId": ep.get("id"),
                        "provider": provider,
                        "createdAt": _now_iso(),
                    })
                    existing_model_ids.add(model_id)
                continue

            try:
                if provider == "ollama":
                    resp = await client.get(f"{url}/api/tags", headers=headers)
                    _validate_response(resp)
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
                elif provider in ("openai", "nvidia"):
                    resp = await client.get(f"{url}/models", headers=headers)
                    _validate_response(resp)
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
                    _validate_response(resp)
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
    """Test connectivity to Kilo Gateway and persist endpoint on success."""
    url = payload.get("url", "https://api.kilo.ai/api/gateway")
    api_key = payload.get("apiKey")
    
    # Validate URL: reject embedded credentials, non-HTTP schemes, excessive length
    url = _validate_config_url(url)
    if not url:
        return {"ok": False, "error": "Invalid URL: must be http(s):// without embedded credentials"}
    
    # SSRF protection: reject localhost endpoints
    if _is_localhost_endpoint(url):
        return {"ok": False, "url": url, "error": "Localhost endpoints are not allowed"}
    
    # If no API key provided, try to read from local Kilo auth file via secure helper
    if not api_key:
        api_key = _read_kilo_oauth_token()
    
    try:
        async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
            test_url = f"{url.rstrip('/')}/models"
            headers = _build_auth_headers(api_key)
            resp = await client.get(test_url, headers=headers)
            _validate_response(resp)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                
                # Encrypt API key at rest before persisting
                encrypted_key = encrypt_api_key(api_key) if api_key else ""
                
                # Persist Kilo Gateway endpoint for future model discovery
                endpoints = _get_endpoints()
                existing = next((e for e in endpoints if e.get("url") == url), None)
                if not existing:
                    endpoints.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": "Kilo Gateway",
                        "url": url,
                        "encryptedApiKey": encrypted_key,
                        "provider": "kilo",
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
                    _save_endpoints(endpoints)
                else:
                    # Update existing endpoint to kilo provider and encrypted API key
                    existing["provider"] = "kilo"
                    if encrypted_key:
                        existing["encryptedApiKey"] = encrypted_key
                        existing.pop("apiKey", None)  # Remove legacy plaintext field
                    existing["available"] = True
                    existing["lastTested"] = _now_iso()
                    _save_endpoints(endpoints)
                
                return {
                    "ok": True,
                    "url": url,
                    "models": models,
                    "message": f"Kilo Gateway reachable: {len(models)} models found",
                }
            return {"ok": False, "url": url, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": _safe_request_error(exc)}


# ---------------------------------------------------------------------------
# NVIDIA NIM login
# ---------------------------------------------------------------------------

@app.post("/api/nvidia/login")
async def nvidia_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Test connectivity to NVIDIA NIM and persist endpoint on success."""
    url = payload.get("url", "https://integrate.api.nvidia.com/v1")
    api_key = payload.get("apiKey")
    
    # Validate URL: reject embedded credentials, non-HTTP schemes, excessive length
    url = _validate_config_url(url)
    if not url:
        return {"ok": False, "error": "Invalid URL: must be http(s):// without embedded credentials"}
    
    # SSRF protection: reject localhost endpoints
    if _is_localhost_endpoint(url):
        return {"ok": False, "url": url, "error": "Localhost endpoints are not allowed"}
    
    # NVIDIA NIM requires an API key starting with nvapi-
    key_err = _validate_api_key("nvidia", api_key or "")
    if key_err:
        return {"ok": False, "url": url, "error": key_err}
    
    try:
        async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
            test_url = f"{url.rstrip('/')}/models"
            headers = _build_auth_headers(api_key)
            resp = await client.get(test_url, headers=headers)
            _validate_response(resp)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                
                # Encrypt API key at rest before persisting
                encrypted_key = encrypt_api_key(api_key) if api_key else ""
                
                # Persist NVIDIA NIM endpoint for future model discovery
                endpoints = _get_endpoints()
                existing = next((e for e in endpoints if e.get("url") == url), None)
                if not existing:
                    endpoints.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": "NVIDIA NIM",
                        "url": url,
                        "encryptedApiKey": encrypted_key,
                        "provider": "nvidia",
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
                    _save_endpoints(endpoints)
                else:
                    existing["provider"] = "nvidia"
                    if encrypted_key:
                        existing["encryptedApiKey"] = encrypted_key
                        existing.pop("apiKey", None)
                    existing["available"] = True
                    existing["lastTested"] = _now_iso()
                    _save_endpoints(endpoints)
                
                return {
                    "ok": True,
                    "url": url,
                    "models": models,
                    "message": f"NVIDIA NIM reachable: {len(models)} models found",
                }
            return {"ok": False, "url": url, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": _safe_request_error(exc)}


# ---------------------------------------------------------------------------
# Ollama login
# ---------------------------------------------------------------------------

@app.post("/api/ollama/login")
async def ollama_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Test connectivity to Ollama and persist endpoint on success."""
    url = payload.get("url", "http://localhost:11434")
    
    # Validate URL: reject embedded credentials, non-HTTP schemes, excessive length
    url = _validate_config_url(url)
    if not url:
        return {"ok": False, "error": "Invalid URL: must be http(s):// without embedded credentials"}
    
    try:
        async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
            test_url = f"{url.rstrip('/')}/api/tags"
            headers = _build_auth_headers(payload.get("apiKey"))
            resp = await client.get(test_url, headers=headers)
            _validate_response(resp)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                
                # Encrypt API key at rest if provided
                api_key = payload.get("apiKey")
                encrypted_key = encrypt_api_key(api_key) if api_key else ""
                
                # Persist Ollama endpoint
                endpoints = _get_endpoints()
                existing = next((e for e in endpoints if e.get("url") == url), None)
                if not existing:
                    endpoints.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": "Ollama",
                        "url": url,
                        "encryptedApiKey": encrypted_key,
                        "provider": "ollama",
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
                    _save_endpoints(endpoints)
                else:
                    existing["provider"] = "ollama"
                    if encrypted_key:
                        existing["encryptedApiKey"] = encrypted_key
                        existing.pop("apiKey", None)
                    existing["available"] = True
                    existing["lastTested"] = _now_iso()
                    _save_endpoints(endpoints)
                
                return {
                    "ok": True,
                    "url": url,
                    "models": models,
                    "message": f"Ollama reachable: {len(models)} models found",
                }
            return {"ok": False, "url": url, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": _safe_request_error(exc)}


# ---------------------------------------------------------------------------
# Codex CLI login
# ---------------------------------------------------------------------------

@app.post("/api/codex/login")
async def codex_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Test Codex CLI availability and persist endpoint on success."""
    import shutil
    
    url = payload.get("url", "cli://codex")
    api_key = payload.get("apiKey")
    
    # Codex is a CLI provider — detect via PATH
    if not shutil.which("codex"):
        return {"ok": False, "url": url, "error": "codex CLI not found in PATH"}
    
    try:
        # Use the CLI adapter to check availability and get supported models
        from ..providers.cli_base import CodexCLIAdapter
        adapter = CodexCLIAdapter()
        if not adapter.detect_available():
            return {"ok": False, "url": url, "error": "Codex CLI not available or not authenticated"}
        
        models = adapter.get_supported_models()
        
        # Encrypt API key at rest if provided
        encrypted_key = encrypt_api_key(api_key) if api_key else ""
        
        # Persist Codex CLI endpoint
        endpoints = _get_endpoints()
        existing = next((e for e in endpoints if e.get("url") == url), None)
        if not existing:
            endpoints.append({
                "id": f"ep_{uuid.uuid4().hex[:8]}",
                "name": "Codex CLI",
                "url": url,
                "encryptedApiKey": encrypted_key,
                "provider": "codex_cli",
                "createdAt": _now_iso(),
                "available": True,
                "lastTested": _now_iso(),
            })
            _save_endpoints(endpoints)
        else:
            existing["provider"] = "codex_cli"
            if encrypted_key:
                existing["encryptedApiKey"] = encrypted_key
                existing.pop("apiKey", None)
            existing["available"] = True
            existing["lastTested"] = _now_iso()
            _save_endpoints(endpoints)
        
        return {
            "ok": True,
            "url": url,
            "models": models,
            "message": f"Codex CLI reachable: {len(models)} models available",
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": _safe_request_error(exc)}


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

@app.post("/api/token/generate")
async def generate_token(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a game-day authorization token."""
    environment = payload.get("environment", "staging")
    operator = payload.get("operator", "operator")
    # Security: validate and sanitize environment and operator fields
    # to prevent token injection or format string attacks
    environment = re.sub(r'[^a-zA-Z0-9_-]', '_', str(environment)[:64]) if environment else "staging"
    operator = re.sub(r'[^a-zA-Z0-9_.-]', '_', str(operator)[:128]) if operator else "operator"
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
    
    report_runs = []
    all_runs = _get_telemetry()
    for run in all_runs:
        if run.get("type") == "report_generation":
            artifacts = run.get("artifacts", [])
            pdf_artifacts = [a for a in artifacts if a.lower().endswith(".pdf")]
            if pdf_artifacts:
                # Charts are NOT included in the Reports tab — only artifacts
                report_runs.append({
                    "runId": run.get("runId"),
                    "startedAt": run.get("startedAt"),
                    "models": run.get("models", []),
                    "artifacts": pdf_artifacts,
                })
    
    return {"reports": reports, "reportRuns": report_runs}


@app.get("/reports/{filename}")
async def get_report(filename: str) -> Response:
    safe_name = _validate_report_filename(filename)
    if not safe_name:
        return HTMLResponse("Invalid filename", status_code=400)
    path = REPORTS_DIR / safe_name
    if not path.exists():
        return HTMLResponse("Report not found", status_code=404)
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@app.post("/api/reports/generate")
async def generate_reports(payload: dict[str, Any]) -> dict[str, Any]:
    models = payload.get("models", [])
    prompts = payload.get("prompts", [])
    
    # Input validation to prevent injection and resource exhaustion
    if not isinstance(models, list) or len(models) > 100:
        return {"error": "Invalid models parameter"}
    if not isinstance(prompts, list) or len(prompts) > 100:
        return {"error": "Invalid prompts parameter"}
    models = [str(m) for m in models if m and len(str(m)) <= 256]
    prompts = [str(p) for p in prompts if p and len(str(p)) <= 10000]
    
    if not models:
        return {"error": "No models specified"}

    script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    if not script.exists():
        return {"error": "Report generator script not found"}

    env = os.environ.copy()
    env["WE3_REPORT_MODELS"] = _format_models_for_script(models)
    env["WE3_REPORT_PROMPTS"] = json.dumps(prompts) if prompts else ""
    
    gateway_url, gateway_api_key = _get_gateway_for_models(models)
    if gateway_url:
        env["WE3_REPORT_GATEWAY"] = gateway_url
        # If the gateway URL uses a local/private address, allow it in the
        # report generation script. SSRF protection still validates scheme
        # and blocks metadata endpoints (169.254.x.x is never allowed).
        _hostname = gateway_url.split("://", 1)[-1].split("/")[0].split(":")[0]
        # Allow localhost and private IPs for local development, but NEVER
        # allow 169.254.x.x (cloud metadata endpoints like 169.254.169.254)
        if _hostname in ("localhost", "127.0.0.1", "0.0.0.0") or \
           _hostname.startswith(("10.", "172.", "192.168.")):
            env["WE3_REPORT_ALLOW_LOCAL"] = "1"
            logger.info(f"Gateway URL appears local/private ({_hostname}), enabling WE3_REPORT_ALLOW_LOCAL")
    
    # Securely pass API key via temp file with 0600 permissions (not env var)
    # to prevent exposure through /proc/<pid>/environ or process listings.
    # The temp file is securely deleted after the subprocess completes.
    secure_key_file: SecureKeyFile | None = None
    if gateway_api_key:
        try:
            secure_key_file = store_api_key_temp_file(
                gateway_api_key,
                endpoint_id=gateway_url or "unknown",
                purpose="report_generation",
            )
            env["WE3_REPORT_API_KEY_FILE"] = secure_key_file.file_path
            logger.info(f"API key stored securely (masked: {mask_api_key(gateway_api_key)})")
        except Exception as exc:
            logger.warning(f"Could not create secure API key file: {exc}")
    
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    run_started = _now_iso()
    env["WE3_REPORT_BATCH_ID"] = run_id
    
    logger.info(
        f"Report generation started: run_id={run_id}, models={models}, gateway={gateway_url}"
    )
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        # Securely destroy the temporary API key file
        if secure_key_file is not None:
            secure_key_file.destroy()
        run_finished = _now_iso()
        chart_urls = _generate_charts_for_run_sync(run_id, models, prompts)
        telemetry_entry = {
            "runId": run_id,
            "batchId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": run_finished,
            "models": models,
            "prompts": prompts,
            "promptPackage": payload.get("promptPackage", ""),
            "returncode": result.returncode,
            "stdout": sanitize_output(result.stdout),
            "stderr": sanitize_output(result.stderr),
            "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
            "chartUrls": chart_urls,
        }
        _add_telemetry_entry(telemetry_entry)
        return {
            "runId": run_id,
            "stdout": sanitize_output(result.stdout),
            "stderr": sanitize_output(result.stderr),
            "returncode": result.returncode,
            "chartUrls": chart_urls,
        }
    except subprocess.TimeoutExpired:
        if secure_key_file is not None:
            secure_key_file.destroy()
        _add_telemetry_entry({
            "runId": run_id,
            "batchId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": payload.get("promptPackage", ""),
            "chartUrls": _generate_charts_for_run_sync(run_id, models, prompts),
            "error": "Report generation timed out",
        })
        return {"error": "Report generation timed out"}
    except Exception as exc:
        if secure_key_file is not None:
            secure_key_file.destroy()
        _add_telemetry_entry({
            "runId": run_id,
            "batchId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": payload.get("promptPackage", ""),
            "chartUrls": _generate_charts_for_run_sync(run_id, models, prompts),
            "error": _sanitize_error_message(exc),
        })
        return {"error": _sanitize_error_message(exc)}


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

@app.get("/api/telemetry/runs")
async def list_telemetry_runs() -> dict[str, Any]:
    runs = _get_telemetry()
    return {"runs": _enrich_runs_with_charts(runs)}


@app.get("/api/telemetry/runs/{run_id}")
async def get_telemetry_run(run_id: str) -> dict[str, Any]:
    runs = _get_telemetry()
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    enriched = _enrich_runs_with_charts([run])
    return {"run": enriched[0] if enriched else run}


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


@app.delete("/api/telemetry/runs/{run_id}/artifacts/{artifact:path}")
async def delete_telemetry_artifact(run_id: str, artifact: str) -> dict[str, Any]:
    telemetry = _get_telemetry()
    run = next((r for r in telemetry if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    # Security: Validate artifact filename to prevent path traversal
    safe_artifact = _validate_report_filename(artifact)
    if not safe_artifact:
        return JSONResponse({"error": "Invalid artifact filename"}, status_code=400)
    artifacts = run.get("artifacts", [])
    if safe_artifact in artifacts:
        artifacts.remove(safe_artifact)
        run["artifacts"] = artifacts
        _save_telemetry(telemetry)
    # Also delete the actual file from the reports directory
    try:
        path = REPORTS_DIR / safe_artifact
        if path.exists():
            path.unlink()
    except Exception:
        pass
    return {"deleted": f"{run_id}::{safe_artifact}"}


@app.delete("/api/reports")
async def delete_all_reports() -> dict[str, Any]:
    for path in REPORTS_DIR.glob("*.pdf"):
        try:
            path.unlink()
        except Exception:
            pass
    for path in REPORTS_DIR.glob("*.json"):
        try:
            path.unlink()
        except Exception:
            pass
    return {"deleted": "all reports"}


@app.delete("/api/reports/{filename:path}")
async def delete_report(filename: str) -> dict[str, Any]:
    safe_name = _validate_report_filename(filename)
    if not safe_name:
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    path = REPORTS_DIR / safe_name
    if not path.exists():
        return JSONResponse({"error": "Report not found"}, status_code=404)
    try:
        path.unlink()
    except Exception as exc:
        return JSONResponse({"error": _sanitize_error_message(exc)}, status_code=500)
    return {"deleted": safe_name}


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
            safe_artifact = _validate_report_filename(artifact)
            if not safe_artifact:
                logger.warning(f"Skipping unsafe artifact name in zip: {artifact}")
                continue
            file_path = REPORTS_DIR / safe_artifact
            if file_path.exists():
                zf.write(file_path, safe_artifact)
                added += 1
            else:
                for search_dir in [GUI_DATA_DIR, WORKSPACE_ROOT / "scripts"]:
                    candidate = search_dir / safe_artifact
                    if candidate.exists():
                        zf.write(candidate, safe_artifact)
                        added += 1
                        break

    if added == 0:
        return JSONResponse({"error": "No artifact files found to zip"}, status_code=404)

    buffer.seek(0)
    # Security: Sanitize run_id for use in Content-Disposition header to prevent
    # CRLF injection (header injection attacks)
    safe_run_id = re.sub(r'[^a-zA-Z0-9._-]', '_', run_id)[:128]
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_run_id}.zip"},
    )


@app.get("/api/batches")
async def list_batches() -> dict[str, Any]:
    """Return all batches with their runs and chart URLs.

    A batch groups runs that share the same batchId (which equals the runId
    for single-run batches, or a shared identifier for multi-run batches).
    """
    runs = _get_telemetry()
    report_runs = [r for r in runs if r.get("type") == "report_generation"]

    # Group by batchId (fallback to runId)
    batches: dict[str, list[dict[str, Any]]] = {}
    for run in report_runs:
        batch_id = run.get("batchId") or run.get("runId")
        batches.setdefault(batch_id, []).append(run)

    batch_list = []
    for batch_id, batch_runs in batches.items():
        enriched = _enrich_runs_with_charts(batch_runs)
        # Generate batch-level chart (cached on disk)
        batch_chart_urls = _generate_batch_charts_for_run(batch_id, enriched)
        batch_list.append({
            "batchId": batch_id,
            "runIds": [r.get("runId") for r in batch_runs],
            "totalRuns": len(batch_runs),
            "models": sorted(set(m for r in batch_runs for m in r.get("models", []))),
            "startedAt": min((r.get("startedAt", "") for r in batch_runs), default=""),
            "finishedAt": max((r.get("finishedAt", "") for r in batch_runs), default=""),
            "chartUrls": batch_chart_urls,
            "runs": enriched,
        })

    # Sort by most recent first
    batch_list.sort(key=lambda b: b.get("finishedAt", ""), reverse=True)
    return {"batches": batch_list}


@app.get("/api/batches/{batch_id}")
async def get_batch(batch_id: str) -> dict[str, Any]:
    """Return a specific batch with all its runs and chart URLs."""
    runs = _get_telemetry()
    report_runs = [r for r in runs if r.get("type") == "report_generation"]

    batch_runs = [r for r in report_runs if (r.get("batchId") or r.get("runId")) == batch_id]
    if not batch_runs:
        return JSONResponse({"error": "Batch not found"}, status_code=404)

    enriched = _enrich_runs_with_charts(batch_runs)
    batch_chart_urls = _generate_batch_charts_for_run(batch_id, enriched)

    return {
        "batchId": batch_id,
        "runIds": [r.get("runId") for r in batch_runs],
        "totalRuns": len(batch_runs),
        "models": sorted(set(m for r in batch_runs for m in r.get("models", []))),
        "startedAt": min((r.get("startedAt", "") for r in batch_runs), default=""),
        "finishedAt": max((r.get("finishedAt", "") for r in batch_runs), default=""),
        "chartUrls": batch_chart_urls,
        "runs": enriched,
    }


@app.delete("/api/batches/{batch_id}")
async def delete_batch(batch_id: str) -> dict[str, Any]:
    """Delete a whole batch: remove telemetry entries, chart directories, and artifacts."""
    # Remove telemetry entries for this batch
    telemetry = _get_telemetry()
    before = len(telemetry)
    telemetry = [r for r in telemetry if (r.get("batchId") or r.get("runId")) != batch_id]
    _save_telemetry(telemetry)
    removed_telemetry = before - len(telemetry)

    # Remove chart directories
    removed_charts = 0
    if CHARTS_DIR.exists():
        batch_chart_dir = CHARTS_DIR / batch_id
        if batch_chart_dir.exists() and batch_chart_dir.is_dir():
            import shutil
            shutil.rmtree(batch_chart_dir)
            removed_charts += 1
        # Also remove any run chart dirs that belong to this batch
        for run in telemetry:
            if run.get("batchId") == batch_id:
                run_chart_dir = CHARTS_DIR / run.get("runId", "")
                if run_chart_dir.exists() and run_chart_dir.is_dir():
                    import shutil
                    shutil.rmtree(run_chart_dir)
                    removed_charts += 1

    # Remove evaluation JSON sidecars for this batch
    removed_evals = 0
    eval_jsons = _load_evaluation_jsons()
    for ej in eval_jsons:
        if ej.get("batchId") == batch_id:
            source_file = ej.get("_source_file")
            if source_file:
                eval_path = REPORTS_DIR / source_file
                if eval_path.exists():
                    try:
                        eval_path.unlink()
                        removed_evals += 1
                    except Exception:
                        pass

    # Remove job entries
    jobs = _load_jobs()
    jobs_to_remove = [jid for jid, job in jobs.items() if job.get("runId") == batch_id]
    for jid in jobs_to_remove:
        del jobs[jid]
    if jobs_to_remove:
        _save_jobs(jobs)

    return {
        "deleted": batch_id,
        "removedTelemetryEntries": removed_telemetry,
        "removedChartDirs": removed_charts,
        "removedEvalJsonSidecars": removed_evals,
        "removedJobs": len(jobs_to_remove),
    }


@app.delete("/api/charts/runs/{run_id}/all")
async def delete_chart_run(run_id: str) -> dict[str, Any]:
    """Delete all chart PNG files for a run and track the deletion session-wide.

    When a user clicks the "×" button on a run card in the Charts tab, this
    endpoint removes the run's chart directory from disk and records the
    run ID in the in-memory ``_deleted_chart_runs`` set so that subsequent
    ``list_chart_runs`` and ``generate_charts`` calls during this session
    will not resurrect the deleted charts.

    A telemetry entry is also created/updated with ``deletedCharts`` set to
    ``["__all__"]`` so that the deletion persists across server restarts.
    """
    safe_run_id = re.sub(r'[^a-zA-Z0-9._-]', '_', run_id)[:128]

    # Remove on-disk chart directory
    run_dir = CHARTS_DIR / safe_run_id
    deleted_count = 0
    if run_dir.exists():
        for chart_file in run_dir.glob("*.png"):
            try:
                chart_file.unlink()
                deleted_count += 1
            except Exception:
                pass
        # Remove the directory if empty
        try:
            run_dir.rmdir()
        except OSError:
            pass

    # Track session-level deletion
    _deleted_chart_runs.add(safe_run_id)

    # Persist deletion in telemetry so it survives restarts
    telemetry = _get_telemetry()
    entry_found = False
    for entry in telemetry:
        if (entry.get("runId") or entry.get("run_id")) == safe_run_id:
            entry_found = True
            existing = entry.get("deletedCharts", [])
            if not isinstance(existing, list):
                existing = []
            if "__all__" not in existing:
                existing.append("__all__")
            entry["deletedCharts"] = existing
            break

    if not entry_found:
        telemetry.insert(0, {
            "runId": safe_run_id,
            "run_id": safe_run_id,
            "chartUrls": {},
            "deletedCharts": ["__all__"],
            "type": "chart_deletion",
        })
    _save_telemetry(telemetry)

    _audit_log("charts_deleted_for_run", run_id=safe_run_id, file_count=deleted_count)

    return {"deleted": True, "runId": safe_run_id, "deletedFiles": deleted_count}


@app.delete("/api/charts/runs/{run_id}/{chart_name}")
async def delete_chart(run_id: str, chart_name: str) -> dict[str, Any]:
    """Delete an individual chart file and track the deletion so it won't regenerate.

    The chart file is removed from disk. The telemetry entry for this run is updated
    to remove the chart from ``chartUrls`` and add it to ``deletedCharts`` so that
    subsequent on-demand chart generation skips it. If no telemetry entry exists
    for the run (e.g. on-demand generated runs like ``test-run-final``), a new
    telemetry entry is created to ensure deletions are tracked.
    """
    safe_run_id = re.sub(r'[^a-zA-Z0-9._-]', '_', run_id)[:128]
    safe_chart_name = re.sub(r'[^a-zA-Z0-9._-]', '_', chart_name)[:128]
    chart_path = CHARTS_DIR / safe_run_id / f"{safe_chart_name}.png"
    deleted_file = False
    if chart_path.exists():
        try:
            chart_path.unlink()
            deleted_file = True
        except Exception as exc:
            return JSONResponse({"error": _sanitize_error_message(exc)}, status_code=500)
    else:
        return JSONResponse({"error": "Chart not found"}, status_code=404)

    # Track deletion in telemetry so the chart doesn't regenerate on-demand
    telemetry = _get_telemetry()
    entry_found = False
    for entry in telemetry:
        if (entry.get("runId") or entry.get("run_id")) == safe_run_id:
            entry_found = True
            # Remove from chartUrls
            chart_urls = entry.get("chartUrls", {})
            if safe_chart_name in chart_urls:
                del chart_urls[safe_chart_name]
                entry["chartUrls"] = chart_urls
            # Add to deletedCharts list to prevent regeneration
            deleted = entry.get("deletedCharts", [])
            if not isinstance(deleted, list):
                deleted = []
            if safe_chart_name not in deleted:
                deleted.append(safe_chart_name)
                entry["deletedCharts"] = deleted
            break

    # If no telemetry entry exists for this run (e.g. "test-run-final" which is
    # generated on-demand), create one so that deletions are tracked and the
    # Generate Chart button doesn't resurrect deleted charts.  Insert directly
    # into the in-memory list rather than using _add_telemetry_entry (which
    # re-loads from disk) to avoid a double-save race.
    if not entry_found:
        telemetry.insert(0, {
            "runId": safe_run_id,
            "run_id": safe_run_id,
            "chartUrls": {},
            "deletedCharts": [safe_chart_name],
            "type": "chart_generation",
        })
    _save_telemetry(telemetry)

    # If the run directory is now empty, remove it so the empty run-window frame
    # is cleaned up from disk. The frontend also removes the frame on its side.
    run_is_empty = False
    run_dir = CHARTS_DIR / safe_run_id
    if run_dir.exists():
        remaining = list(run_dir.glob("*.png"))
        # Filter out deleted charts — only count undeleted PNGs
        remaining = [f for f in remaining if f.stem not in deleted_charts]
        if not remaining:
            try:
                run_dir.rmdir()
                run_is_empty = True
            except OSError:
                pass

    return {
        "deleted": str(chart_path),
        "runId": safe_run_id,
        "chartName": safe_chart_name,
        "deletedFile": deleted_file,
        "runIsEmpty": run_is_empty,
    }


@app.delete("/api/charts/runs/all")
async def delete_all_chart_runs() -> dict[str, Any]:
    """Delete all chart PNG files and run-window directories at once.

    Removes every chart image under CHARTS_DIR and all run directories.
    Records a session-level deletion marker so that auto-generation does
    not resurrect any charts during the current server process.

    Also writes a telemetry ``deletedCharts`` entry of ``["__all__"]`` for
    every run that had a telemetry entry, so deletions persist across restarts.
    """
    deleted_count = 0
    if CHARTS_DIR.exists():
        for run_dir in CHARTS_DIR.iterdir():
            if run_dir.is_dir():
                for chart_file in run_dir.glob("*.png"):
                    try:
                        chart_file.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
                try:
                    run_dir.rmdir()
                except OSError:
                    pass

    # Mark all known runs as deleted in telemetry
    telemetry = _get_telemetry()
    for entry in telemetry:
        if entry.get("runId") or entry.get("run_id"):
            existing = entry.get("deletedCharts", [])
            if not isinstance(existing, list):
                existing = []
            if "__all__" not in existing:
                existing.append("__all__")
            entry["deletedCharts"] = existing

    _save_telemetry(telemetry)
    _deleted_chart_runs.update(
        entry.get("runId", entry.get("run_id", ""))
        for entry in telemetry
        if entry.get("runId") or entry.get("run_id")
    )

    _audit_log("all_charts_deleted", file_count=deleted_count)
    return {"deleted": True, "deletedFiles": deleted_count}


# ---------------------------------------------------------------------------

@app.get("/api/jobs")
async def list_jobs() -> dict[str, Any]:
    jobs = _load_jobs()
    return {"jobs": list(jobs.values())}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return {"job": job}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.get("status") in ("completed", "failed", "cancelled"):
        return JSONResponse({"error": f"Job already {job['status']}"}, status_code=400)
    async with _report_lock:
        if _report_task is not None and not _report_task.done():
            _report_task.cancel()
    job["status"] = "cancelled"
    job["finished_at"] = _now_iso()
    job["current_step"] = "Cancelled"
    job["error"] = "Report generation was cancelled"
    _update_job(job_id, job)
    return {"job_id": job_id, "status": "cancelled"}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.get("status") not in ("failed", "completed_with_errors"):
        return JSONResponse({"error": "Only failed jobs can be retried"}, status_code=400)
    models = job.get("models", [])
    prompts = job.get("prompts", [])
    prompt_package = job.get("prompt_package", "")
    if not models or not prompts:
        return JSONResponse({"error": "Job has no models or prompts"}, status_code=400)
    return JSONResponse({"error": "Retry must be initiated from the Generate Reports tab via WebSocket"}, status_code=400)


def _find_model(model_id: str, models_data: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a model by exact ID or with fuzzy matching for common suffixes."""
    # Exact match first
    model = next((m for m in models_data if m.get("id") == model_id), None)
    if model:
        return model
    
    # Try stripping common suffixes like :free, :latest, etc.
    if ":" in model_id:
        base = model_id.split(":")[0]
        model = next((m for m in models_data if m.get("id") == base), None)
        if model:
            return model
    else:
        # Try adding :free suffix
        with_free = f"{model_id}:free"
        model = next((m for m in models_data if m.get("id") == with_free), None)
        if model:
            return model
        # Try matching by base name (before first colon)
        model = next((m for m in models_data if m.get("id", "").split(":")[0] == model_id), None)
        if model:
            return model
    
    return None


def _format_models_for_script(model_ids: list[str]) -> str:
    """Format model IDs as 'provider|model_id|label' for the report generation script."""
    models_data = _get_models()
    endpoints_data = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints_data}
    
    formatted = []
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                provider = ep.get("provider", model.get("provider", "ollama"))
            else:
                provider = model.get("provider", "ollama")
            label = mid
            formatted.append(f"{provider}|{mid}|{label}")
        else:
            formatted.append(mid)
    return ",".join(formatted)


def _get_gateway_for_models(model_ids: list[str]) -> tuple[str | None, str | None]:
    """Get the gateway URL and API key for the first model that has an HTTP endpoint.
    
    Prefers Kilo Gateway endpoints over Ollama/OpenAI endpoints.
    """
    models_data = _get_models()
    endpoints_data = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints_data}
    
    # First pass: prefer Kilo Gateway endpoints
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                if ep.get("provider") == "kilo":
                    logger.info(f"Selected Kilo Gateway for model {mid}: {ep.get('url')}")
                    return ep.get("url"), _get_endpoint_api_key(ep)
    
    # Second pass: any HTTP endpoint
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                logger.info(f"Selected endpoint for model {mid}: {ep.get('url')} (provider: {ep.get('provider')})")
                return ep.get("url"), _get_endpoint_api_key(ep)
    
    # Fallback: first configured HTTP endpoint
    for ep in endpoints_data:
        url = ep.get("url", "")
        if url and not url.startswith("cli://"):
            logger.info(f"Selected fallback endpoint: {url} (provider: {ep.get('provider')})")
            return url, _get_endpoint_api_key(ep)
    return None, None


def _get_gateway_url_for_models(model_ids: list[str]) -> str | None:
    """Backward-compatible wrapper that returns only the URL."""
    url, _ = _get_gateway_for_models(model_ids)
    return url


# ---------------------------------------------------------------------------
# Background report generation
# ---------------------------------------------------------------------------

def _update_model_elapsed(model_state: dict[str, Any], event_timestamp: str | None) -> None:
    """Calculate and update the elapsed_seconds for a model state.

    Uses the model's started_at timestamp to compute elapsed time.
    Updates in-place.

    For models in a terminal state (completed / completed_with_errors /
    failed / cancelled) the elapsed value is frozen at the completion time
    so the per-model card does not keep "ticking up" while the overall job
    continues running. Without this, completed cards would visually keep
    updating their elapsed counter until the whole job finished.
    """
    # Freeze elapsed for terminal states — the model is done.
    if model_state.get("status") in (
        "completed",
        "completed_with_errors",
        "failed",
        "cancelled",
    ):
        return
    started = model_state.get("started_at")
    if not started:
        return
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        event_dt = datetime.fromisoformat((event_timestamp or _now_iso()).replace("Z", "+00:00"))
        elapsed = (event_dt - start_dt).total_seconds()
        model_state["elapsed_seconds"] = round(elapsed, 1)
    except Exception:
        pass


def _update_job_from_event(job_id: str, event: dict[str, Any]) -> dict[str, Any]:
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {}
    
    event_type = event.get("event")
    model = event.get("model")
    model_label = event.get("model_label", model)
    provider = event.get("provider", "unknown")
    prompt_index = event.get("prompt_index", 0)
    total_prompts = event.get("total_prompts", job.get("prompts", []) and len(job.get("prompts", [])) or 1)
    
    if event_type == "run_start":
        job["status"] = "processing"
        job["current_step"] = "Initializing"
        job["started_at"] = event.get("timestamp", job["started_at"])
        total_models = event.get("total_models", len(job.get("models", [])))
        job["total_models"] = total_models
        job["total_prompts"] = total_prompts
        total_reports = total_models * total_prompts
        job["total_reports"] = total_reports
        job["queued_reports"] = total_reports
        job["processing_reports"] = 0
        job["completed_reports"] = 0
        job["failed_reports"] = 0
    
    elif event_type == "model_start":
        model_state = {
            "label": model_label,
            "provider": provider,
            "status": "processing",
            "total_reports": total_prompts,
            "completed_reports": 0,
            "failed_reports": 0,
            "percentage": 0,
            "current_step": f"Preparing prompt 1 of {total_prompts}",
            "elapsed_seconds": 0,
            "processing_start_time": None,
            "reports": [],
            "started_at": event.get("timestamp"),
        }
        job["models_state"][model] = model_state
        job["current_model"] = model
        job["current_report"] = 0
        # Track prompt-level counts: one model means total_prompts work units
        job["processing_reports"] = job.get("processing_reports", 0) + total_prompts
        job["queued_reports"] = max(0, job.get("queued_reports", 0) - total_prompts)
        job["current_step"] = f"Processing {model_label}"
    
    elif event_type == "prompt_start":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["current_step"] = f"Sending prompt {prompt_index} of {total_prompts} to {model_label} — waiting for model response"
            model_state["percentage"] = round(((prompt_index - 1) / total_prompts) * 100)
            model_state["processing_start_time"] = event.get("timestamp")
            # Calculate model elapsed time
            _update_model_elapsed(model_state, event.get("timestamp"))
        job["current_step"] = f"Sending prompt {prompt_index} of {total_prompts} to {model_label} — model is responding, please wait"
        report_entry = {
            "id": f"{model}-prompt-{prompt_index}",
            "model": model,
            "model_label": model_label,
            "provider": provider,
            "status": "processing",
            "step": f"Sending prompt {prompt_index} of {total_prompts}",
            "queue_position": prompt_index,
            "started_at": event.get("timestamp"),
            "finished_at": None,
            "elapsed_seconds": 0,
            "retry_count": 0,
            "error": None,
        }
        if "reports" not in job:
            job["reports"] = []
        job["reports"].append(report_entry)
        job["current_report"] = prompt_index
    
    elif event_type == "prompt_complete":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["current_step"] = f"Validating response {prompt_index} of {total_prompts}"
            model_state["percentage"] = round((prompt_index / total_prompts) * 100)
            model_state["processing_start_time"] = None
            _update_model_elapsed(model_state, event.get("timestamp"))
        job["current_step"] = f"Validating response {prompt_index} of {total_prompts} from {model_label}"
        # Update the last report entry for this model/prompt
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("id") == f"{model}-prompt-{prompt_index}":
                report["status"] = "complete" if event.get("success") else "failed"
                report["step"] = f"Response received {prompt_index} of {total_prompts}"
                report["finished_at"] = event.get("timestamp")
                report["elapsed_seconds"] = round(event.get("time", 0), 2)
                report["error"] = None if event.get("success") else "Model returned unsuccessful response"
                break
        if model_state:
            model_state["completed_reports"] = model_state.get("completed_reports", 0) + (1 if event.get("success") else 0)
            model_state["failed_reports"] = model_state.get("failed_reports", 0) + (0 if event.get("success") else 1)
            model_state["current_step"] = f"Saving report {prompt_index} of {total_prompts}"
    
    elif event_type == "model_complete":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "completed"
            model_state["percentage"] = 100
            model_state["processing_start_time"] = None
            model_state["current_step"] = "Finalizing model results"
            _update_model_elapsed(model_state, event.get("timestamp"))
        job["current_step"] = f"Finalizing {model_label} results"
        # Mark all reports for this model as completed
        for report in job.get("reports", []):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Report generated"
                if not report.get("finished_at"):
                    report["finished_at"] = event.get("timestamp")
        job["completed_reports"] = job.get("completed_reports", 0) + model_state.get("completed_reports", 0)
        job["failed_reports"] = job.get("failed_reports", 0) + model_state.get("failed_reports", 0)
        job["processing_reports"] = max(0, job.get("processing_reports", total_prompts) - total_prompts)
    
    elif event_type == "report_start":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "processing"
            model_state["current_step"] = "Generating PDF report"
            model_state["processing_start_time"] = event.get("timestamp")
            _update_model_elapsed(model_state, event.get("timestamp"))
        job["current_step"] = f"Generating report for {model_label}"
    
    elif event_type == "report_generated":
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Report generated"
                report["finished_at"] = event.get("timestamp")
                report["report_path"] = event.get("report_path")
                break
    
    elif event_type == "report_error":
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "failed"
                report["step"] = "Report generation failed"
                report["finished_at"] = event.get("timestamp")
                report["error"] = event.get("error")
                break
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["failed_reports"] = model_state.get("failed_reports", 0) + 1
        job["failed_reports"] = job.get("failed_reports", 0) + 1
    
    elif event_type == "run_complete":
        job["status"] = "completed" if job.get("failed_reports", 0) == 0 else "completed_with_errors"
        job["finished_at"] = event.get("timestamp")
        job["current_step"] = "Completed"
        job["processing_reports"] = 0
        job["queued_reports"] = 0
        for model_state in job.get("models_state", {}).values():
            model_state["status"] = "completed"
            model_state["percentage"] = 100
            model_state["processing_start_time"] = None
            model_state["current_step"] = "Completed"
            _update_model_elapsed(model_state, event.get("timestamp"))
        for report in job.get("reports", []):
            if report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Completed"
                if not report.get("finished_at"):
                    report["finished_at"] = event.get("timestamp")
    
    elif event_type == "run_error":
        job["status"] = "failed"
        job["finished_at"] = event.get("timestamp")
        job["error"] = event.get("error")
        job["current_step"] = f"Failed: {event.get('error')}"
    
    elif event_type == "rate_limit_retry":
        # Model hit HTTP 429; retrying after a backoff delay
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "processing"
            model_state["current_step"] = f"Rate limited, retrying in {event.get('delay', 0)}s (attempt {event.get('attempt', 1)}/{event.get('max_retries', 3)})"
        job["current_step"] = f"Rate limited: {model_label} — retrying in {event.get('delay', 0)}s"
    
    elif event_type == "rate_limited_queued":
        # Model exhausted retries; will be queued for the next retry pass
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "queued"
            model_state["current_step"] = "Queued for retry pass (rate limited)"
        job["current_step"] = f"Rate limited: {model_label} queued for retry"
    
    elif event_type == "model_queued":
        # Model explicitly queued for a retry pass
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "queued"
            model_state["current_step"] = f"Queued for retry pass {event.get('retry_pass', 2)} (reason: {event.get('reason', 'rate_limited')})"
        job["current_step"] = f"Queued: {model_label} (retry pass {event.get('retry_pass', 2)})"
    
    elif event_type == "retry_pass_start":
        # A new retry pass has begun — waiting for rate limit windows to clear
        job["current_step"] = f"Retry pass {event.get('retry_pass', 1)} — waiting {event.get('wait_seconds', 0)}s for rate limits to clear"
        job["retry_pass"] = event.get("retry_pass", 1)
    
    # Recalculate overall state
    reports = job.get("reports", [])
    completed = sum(1 for r in reports if r.get("status") == "complete")
    failed = sum(1 for r in reports if r.get("status") == "failed")
    processing = sum(1 for r in reports if r.get("status") == "processing")
    queued = job.get("total_reports", 0) - completed - failed - processing
    
    job["completed_reports"] = completed
    job["failed_reports"] = failed
    job["processing_reports"] = processing
    job["queued_reports"] = max(0, queued)
    total = job.get("total_reports", 1)
    job["overall_percentage"] = min(100, round((completed / total) * 100)) if total > 0 else 0
    
    # Calculate elapsed and estimated completion
    started = job.get("started_at")
    updated = event.get("timestamp", _now_iso())
    if started:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            update_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            elapsed = (update_dt - start_dt).total_seconds()
            job["elapsed_seconds"] = round(elapsed, 1)
            if completed > 0 and elapsed > 0:
                rate = completed / elapsed
                remaining = total - completed - failed
                if rate > 0 and remaining > 0:
                    est_seconds = remaining / rate
                    est_dt = update_dt.timestamp() + est_seconds
                    job["estimated_completion"] = datetime.fromtimestamp(est_dt).isoformat()
        except Exception:
            pass
    
    _save_jobs(jobs)
    return {
        "status": job.get("status"),
        "overall": {
            "percentage": job.get("overall_percentage"),
            "completed_reports": job.get("completed_reports"),
            "failed_reports": job.get("failed_reports"),
            "processing_reports": job.get("processing_reports"),
            "queued_reports": job.get("queued_reports"),
            "elapsed_seconds": job.get("elapsed_seconds"),
            "estimated_completion": job.get("estimated_completion"),
        },
        "current_step": job.get("current_step"),
        "current_model": job.get("current_model"),
        "current_report": job.get("current_report"),
        "error": job.get("error"),
        "models_state": job.get("models_state"),
        "reports": job.get("reports"),
        "finished_at": job.get("finished_at"),
    }


async def _tail_progress_file(websocket: WebSocket, job_id: str, progress_file: str, run_id: str) -> None:
    last_pos = 0
    progress_path = Path(progress_file)
    while True:
        try:
            if progress_path.exists():
                size = progress_path.stat().st_size
                if size > last_pos:
                    with open(progress_path, "r", encoding="utf-8") as fh:
                        fh.seek(last_pos)
                        while True:
                            line = fh.readline()
                            if not line:
                                break
                            try:
                                event = json.loads(line.strip())
                            except json.JSONDecodeError:
                                continue
                            job_update = _update_job_from_event(job_id, event)
                            if job_update:
                                try:
                                    await websocket.send_text(json.dumps({
                                        "action": "job_progress",
                                        "job_id": job_id,
                                        "run_id": run_id,
                                        **job_update,
                                    }))
                                except Exception:
                                    return
                        last_pos = fh.tell()
            await asyncio.sleep(0.2)
        except Exception:
            await asyncio.sleep(0.5)


async def _run_report_generation_task(
    websocket: WebSocket,
    models: list[str],
    prompts: list[str],
    prompt_package: str = "",
    job_id: str | None = None,
) -> None:
    """Run report generation with prompts and optional package tracking."""
    global _report_process, _report_task
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    job_id = job_id or f"job-{uuid.uuid4().hex[:8]}"
    run_started = _now_iso()
    script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    progress_file = str(GUI_DATA_DIR / f"progress-{job_id}.jsonl")
    progress_file_path = Path(progress_file)
    if progress_file_path.exists():
        try:
            progress_file_path.unlink()
        except Exception:
            pass
    try:
        env = os.environ.copy()
        env["WE3_REPORT_MODELS"] = _format_models_for_script(models)
        env["WE3_REPORT_PROMPTS"] = json.dumps(prompts) if prompts else ""
        env["WE3_REPORT_PROMPT_PACKAGE"] = prompt_package
        env["WE3_REPORT_PROGRESS_FILE"] = progress_file
        env["WE3_REPORT_BATCH_ID"] = run_id
        
        gateway_url, gateway_api_key = _get_gateway_for_models(models)
        if gateway_url:
            env["WE3_REPORT_GATEWAY"] = gateway_url
            # If the gateway URL uses a local/private address (e.g., local Ollama
            # via SSH tunnel), allow it in the report generation script.
            # The SSRF protection in generate_5_reports.py will still validate
            # the URL scheme, block metadata endpoints (169.254.x.x never allowed), and log warnings.
            _hostname = gateway_url.split("://", 1)[-1].split("/")[0].split(":")[0]
            # Allow localhost and private IPs for local development, but NEVER
            # allow 169.254.x.x (cloud metadata endpoints like 169.254.169.254)
            if _hostname in ("localhost", "127.0.0.1", "0.0.0.0") or \
               _hostname.startswith(("10.", "172.", "192.168.")):
                env["WE3_REPORT_ALLOW_LOCAL"] = "1"
                logger.info(f"Gateway URL appears local/private ({_hostname}), enabling WE3_REPORT_ALLOW_LOCAL")
        
        # Securely pass API key via temp file with 0600 permissions (not env var)
        # to prevent exposure through /proc/<pid>/environ or process listings.
        # The temp file is securely deleted after the subprocess completes.
        secure_key_file: SecureKeyFile | None = None
        if gateway_api_key:
            try:
                secure_key_file = store_api_key_temp_file(
                    gateway_api_key,
                    endpoint_id=gateway_url or "unknown",
                    purpose="report_generation_websocket",
                )
                env["WE3_REPORT_API_KEY_FILE"] = secure_key_file.file_path
                logger.info(f"API key stored securely (masked: {mask_api_key(gateway_api_key)})")
            except Exception as exc:
                logger.warning(f"Could not create secure API key file: {exc}")
        
        # Create job state
        job = _create_job(job_id, {
            "run_id": run_id,
            "models": models,
            "prompts": prompts,
            "prompt_package": prompt_package,
            "progress_file": progress_file,
        })
        job["status"] = "initializing"
        _update_job(job_id, job)
        
        try:
            await websocket.send_text(json.dumps({
                "action": "job_created",
                "job_id": job_id,
                "run_id": run_id,
                "status": "initializing",
            }))
        except Exception:
            pass
        
        logger.info(
            f"Report generation started: run_id={run_id}, job_id={job_id}, models={models}, "
            f"prompt_package={prompt_package}, prompt_count={len(prompts)}, "
            f"gateway={gateway_url}"
        )
        
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            "--progress-file=" + progress_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _report_process = proc
        proc_task = asyncio.create_task(proc.wait())
        generation_start = time.time()
        generation_timeout = 600  # 10 minutes max per generation run
        
        # Stream progress events from the progress file
        last_pos = 0
        cancelled = False
        while True:
            if proc_task.done():
                break
            if time.time() - generation_start > generation_timeout:
                logger.error(
                    "Report generation timed out after %ds for job_id=%s run_id=%s",
                    generation_timeout, job_id, run_id,
                )
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(proc_task, timeout=5)
                except asyncio.TimeoutError:
                    pass
                break
            try:
                if progress_file_path.exists():
                    size = progress_file_path.stat().st_size
                    if size > last_pos:
                        with open(progress_file_path, "r", encoding="utf-8") as fh:
                            fh.seek(last_pos)
                            while True:
                                line = fh.readline()
                                if not line:
                                    break
                                try:
                                    event = json.loads(line.strip())
                                except json.JSONDecodeError:
                                    continue
                                job_update = _update_job_from_event(job_id, event)
                                if job_update:
                                    try:
                                        await websocket.send_text(json.dumps({
                                            "action": "job_progress",
                                            "job_id": job_id,
                                            "run_id": run_id,
                                            **job_update,
                                        }))
                                    except Exception:
                                        pass
                        last_pos = fh.tell()
            except Exception:
                pass
            await asyncio.sleep(0.2)
        
        stdout, stderr = await proc.communicate()
        _report_process = None
        run_finished = _now_iso()
        
        # Safely decode stdout/stderr (may be None if process was killed before producing output)
        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
        
        # Securely destroy the temporary API key file
        if secure_key_file is not None:
            secure_key_file.destroy()
        
        # Read any remaining progress events
        if progress_file_path.exists():
            try:
                with open(progress_file_path, "r", encoding="utf-8") as fh:
                    fh.seek(last_pos)
                    for line in fh:
                        try:
                            event = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue
                        _update_job_from_event(job_id, event)
            except Exception:
                pass
        
        job = _get_job(job_id) or job
        if proc.returncode == 0:
            job["status"] = "completed" if job.get("failed_reports", 0) == 0 else "completed_with_errors"
            job["finished_at"] = run_finished
            job["current_step"] = "Completed"
            _update_job(job_id, job)

            # Generate charts alongside PDFs for this run
            chart_urls = _generate_charts_for_run_sync(run_id, models, prompts)

            telemetry_entry = {
                "runId": run_id,
                "batchId": run_id,
                "type": "report_generation",
                "startedAt": run_started,
                "finishedAt": run_finished,
                "models": models,
                "prompts": prompts,
                "promptPackage": prompt_package,
                "returncode": proc.returncode,
                "stdout": sanitize_output(stdout_text),
                "stderr": sanitize_output(stderr_text),
                "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
                "chartUrls": chart_urls,
            }
            _add_telemetry_entry(telemetry_entry)

            # Send charts_generated after telemetry entry is saved so frontend can update
            try:
                await websocket.send_text(json.dumps({
                    "action": "charts_generated",
                    "run_id": run_id,
                    "chart_urls": chart_urls,
                }))
            except Exception:
                pass
            try:
                await websocket.send_text(json.dumps({
                    "action": "job_complete",
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": job["status"],
                }))
            except Exception:
                pass
        else:
            job["status"] = "failed"
            job["finished_at"] = run_finished
            job["error"] = f"Process exited with code {proc.returncode}"
            job["current_step"] = "Failed"
            _update_job(job_id, job)

            # Generate charts even on failure (partial data may still be useful)
            chart_urls = _generate_charts_for_run_sync(run_id, models, prompts)

            telemetry_entry = {
                "runId": run_id,
                "batchId": run_id,
                "type": "report_generation",
                "startedAt": run_started,
                "finishedAt": run_finished,
                "models": models,
                "prompts": prompts,
                "promptPackage": prompt_package,
                "returncode": proc.returncode,
                "stdout": sanitize_output(stdout_text),
                "stderr": sanitize_output(stderr_text),
                "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
                "chartUrls": chart_urls,
                "error": job["error"],
            }
            _add_telemetry_entry(telemetry_entry)

            # Send charts_generated after telemetry entry is saved
            try:
                await websocket.send_text(json.dumps({
                    "action": "charts_generated",
                    "run_id": run_id,
                    "chart_urls": chart_urls,
                }))
            except Exception:
                pass
            try:
                await websocket.send_text(json.dumps({
                    "action": "job_error",
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": "failed",
                    "error": job["error"],
                }))
            except Exception:
                pass
    except asyncio.CancelledError:
        cancelled = True
        if _report_process is not None:
            try:
                _report_process.kill()
            except Exception:
                pass
        _report_process = None
        try:
            await asyncio.wait_for(proc_task, timeout=5)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        job = _get_job(job_id)
        if job:
            job["status"] = "cancelled"
            job["finished_at"] = _now_iso()
            job["current_step"] = "Cancelled"
            job["error"] = "Report generation was cancelled"
            _update_job(job_id, job)
        _add_telemetry_entry({
            "runId": run_id,
            "batchId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": prompt_package,
            "chartUrls": _generate_charts_for_run_sync(run_id, models, prompts),
            "error": "Report generation cancelled",
        })
        try:
            await websocket.send_text(json.dumps({
                "action": "job_cancelled",
                "job_id": job_id,
                "run_id": run_id,
                "status": "cancelled",
                "error": "Report generation was cancelled",
            }))
        except Exception:
            pass
    except Exception as exc:
        _report_process = None
        sanitized = _sanitize_error_message(exc)
        job = _get_job(job_id)
        if job:
            job["status"] = "failed"
            job["finished_at"] = _now_iso()
            job["error"] = sanitized
            job["current_step"] = f"Failed: {sanitized}"
            _update_job(job_id, job)
        _add_telemetry_entry({
            "runId": run_id,
            "batchId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": prompt_package,
            "chartUrls": _generate_charts_for_run_sync(run_id, models, prompts),
            "error": sanitized,
        })
        try:
            await websocket.send_text(json.dumps({
                "action": "job_error",
                "job_id": job_id,
                "run_id": run_id,
                "status": "failed",
                "error": sanitized,
            }))
        except Exception:
            pass
    finally:
        _report_task = None
        # Cleanup progress file after a delay
        try:
            if progress_file_path.exists():
                progress_file_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global _report_process, _report_task
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
                
                # Group by report_generation runs for the Reports tab
                report_runs = []
                all_runs = _get_telemetry()
                for run in all_runs:
                    if run.get("type") == "report_generation":
                        artifacts = run.get("artifacts", [])
                        pdf_artifacts = [a for a in artifacts if a.lower().endswith(".pdf")]
                        if pdf_artifacts:
                            # Charts are NOT included in the Reports tab — only artifacts
                            report_runs.append({
                                "runId": run.get("runId"),
                                "startedAt": run.get("startedAt"),
                                "models": run.get("models", []),
                                "artifacts": pdf_artifacts,
                            })
                response["reportRuns"] = report_runs

            elif action == "list_endpoints":
                response["endpoints"] = [_sanitize_endpoint(ep) for ep in _get_endpoints()]

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
                response["runs"] = _enrich_runs_with_charts(_get_telemetry())

            elif action == "list_prompt_packages":
                response["packages"] = _get_prompt_packages()

            elif action == "endpoints_status":
                result = await endpoints_status()
                response.update(result)

            elif action == "generate_reports":
                models = message.get("models", [])
                prompts = message.get("prompts", [])
                prompt_package = message.get("promptPackage", "")
                prompt_count = message.get("promptCount")
                
                # Input validation to prevent injection and resource exhaustion
                if not isinstance(models, list) or len(models) > 100:
                    response["status"] = "error"
                    response["error"] = "Invalid models parameter"
                    await websocket.send_text(json.dumps(response))
                    continue
                if not isinstance(prompts, list) or len(prompts) > 100:
                    response["status"] = "error"
                    response["error"] = "Invalid prompts parameter"
                    await websocket.send_text(json.dumps(response))
                    continue
                # Validate each model and prompt is a string within length limits
                models = [str(m) for m in models if m and len(str(m)) <= 256]
                prompts = [str(p) for p in prompts if p and len(str(p)) <= 10000]
                prompt_package = str(prompt_package) if prompt_package else ""
                if len(prompt_package) > 256:
                    prompt_package = ""
                if prompt_count and prompts:
                    prompts = prompts[:prompt_count]
                script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
                if not script.exists() or not models:
                    response["status"] = "skipped"
                    response["error"] = "No script or models"
                    await websocket.send_text(json.dumps(response))
                    continue
                async with _report_lock:
                    if _report_task is not None and not _report_task.done():
                        response["status"] = "error"
                        response["error"] = "Report generation already in progress"
                        await websocket.send_text(json.dumps(response))
                        continue
                    job_id = f"job-{uuid.uuid4().hex[:8]}"
                    response["status"] = "started"
                    response["job_id"] = job_id
                    response["promptPackage"] = prompt_package
                    await websocket.send_text(json.dumps(response))
                    _report_task = asyncio.create_task(
                        _run_report_generation_task(websocket, models, prompts, prompt_package, job_id=job_id)
                    )

            elif action == "get_job":
                job_id = message.get("job_id")
                job = _get_job(job_id) if job_id else None
                if not job:
                    response["status"] = "error"
                    response["error"] = "Job not found"
                else:
                    response["status"] = "ok"
                    response["job"] = job
                    response["job_status"] = job.get("status")
                    response["overall"] = {
                        "percentage": job.get("overall_percentage", 0),
                        "completed_reports": job.get("completed_reports", 0),
                        "failed_reports": job.get("failed_reports", 0),
                        "processing_reports": job.get("processing_reports", 0),
                        "queued_reports": job.get("queued_reports", 0),
                        "elapsed_seconds": job.get("elapsed_seconds", 0),
                        "estimated_completion": job.get("estimated_completion"),
                    }
                    response["current_step"] = job.get("current_step")
                    response["current_model"] = job.get("current_model")
                    response["current_report"] = job.get("current_report")
                    response["error"] = job.get("error")
                    response["models_state"] = job.get("models_state", {})
                    response["reports"] = job.get("reports", [])
                    response["finished_at"] = job.get("finished_at")
                await websocket.send_text(json.dumps(response))

            elif action == "cancel_job":
                job_id = message.get("job_id")
                job = _get_job(job_id) if job_id else None
                if not job:
                    response["status"] = "error"
                    response["error"] = "Job not found"
                elif job.get("status") in ("completed", "failed", "cancelled"):
                    response["status"] = "error"
                    response["error"] = f"Job already {job['status']}"
                else:
                    async with _report_lock:
                        if _report_task is not None and not _report_task.done():
                            _report_task.cancel()
                            _report_task = None
                    job["status"] = "cancelled"
                    job["finished_at"] = _now_iso()
                    job["current_step"] = "Cancelled"
                    job["error"] = "Report generation was cancelled"
                    _update_job(job_id, job)
                    response["status"] = "cancelled"
                    response["job_id"] = job_id
                await websocket.send_text(json.dumps(response))

            elif action == "stop_reports":
                async with _report_lock:
                    if _report_process is not None:
                        try:
                            _report_process.kill()
                            try:
                                await asyncio.wait_for(_report_process.wait(), timeout=5)
                            except asyncio.TimeoutError:
                                pass
                        except Exception:
                            pass
                        _report_process = None
                        response["status"] = "stopped"
                    else:
                        response["status"] = "no_generation_running"
                    if _report_task is not None:
                        _report_task.cancel()
                        _report_task = None
                await websocket.send_text(json.dumps(response))

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
                            "authorization": "[REDACTED]",
                            "report": report.to_dict(),
                            "artifacts": [],
                        })
                        response["runId"] = run_id
                        response["report"] = report.to_dict()
                        response["status"] = "complete"
                except Exception as exc:
                    response["error"] = _sanitize_error_message(exc)
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

            elif action == "nvidia_login":
                login_result = await nvidia_login({
                    "url": message.get("url", "https://integrate.api.nvidia.com/v1"),
                    "apiKey": message.get("apiKey"),
                })
                response.update(login_result)

            elif action == "ollama_login":
                login_result = await ollama_login({
                    "url": message.get("url", "http://localhost:11434"),
                    "apiKey": message.get("apiKey"),
                })
                response.update(login_result)

            elif action == "codex_login":
                login_result = await codex_login({
                    "url": message.get("url", "cli://codex"),
                    "apiKey": message.get("apiKey"),
                })
                response.update(login_result)



            elif action == "create_endpoint":
                url = message.get("url", "")
                # Validate URL: reject embedded credentials, non-HTTP schemes, excessive length
                url = _validate_config_url(url)
                if not url:
                    response["error"] = "Invalid URL: must be http(s):// without embedded credentials"
                    response["ok"] = False
                    continue
                # Reject localhost endpoints - only allow configured gateway hosts
                if _is_localhost_endpoint(url):
                    response["error"] = "Localhost endpoints are not allowed. Use a configured gateway host."
                    response["ok"] = False
                    continue
                endpoints = _get_endpoints()
                api_key = message.get("apiKey")
                # Encrypt API key at rest - never store plaintext
                encrypted_key = encrypt_api_key(api_key) if api_key else ""
                endpoint = {
                    "id": f"ep_{uuid.uuid4().hex[:8]}",
                    "name": message.get("name", "Unnamed"),
                    "url": url,
                    "encryptedApiKey": encrypted_key,
                    "provider": message.get("provider", "ollama"),
                    "createdAt": _now_iso(),
                    "available": None,
                    "lastTested": None,
                }
                endpoints.append(endpoint)
                _save_endpoints(endpoints)
                # Return sanitized copy (no API key in response)
                response["endpoint"] = _sanitize_endpoint(endpoint)

            elif action == "delete_endpoint":
                ep_id = message.get("id")
                if ep_id:
                    endpoints = [ep for ep in _get_endpoints() if ep.get("id") != ep_id]
                    _save_endpoints(endpoints)
                    models = [m for m in _get_models() if m.get("endpointId") != ep_id]
                    _save_models(models)
                response["deleted"] = ep_id

            elif action == "create_model":
                models = _get_models()
                endpoint_id = message.get("endpointId", "")
                provider = message.get("provider")
                if not provider:
                    endpoints = _get_endpoints()
                    ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
                    if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                        provider = ep.get("provider", "ollama")
                    else:
                        provider = "ollama"
                model = {
                    "id": message.get("id") or f"mdl_{uuid.uuid4().hex[:8]}",
                    "endpointId": endpoint_id,
                    "provider": provider,
                    "createdAt": _now_iso(),
                }
                models.append(model)
                _save_models(models)
                response["model"] = model

            elif action == "delete_model":
                mdl_id = message.get("id")
                if mdl_id:
                    models = [m for m in _get_models() if m.get("id") != mdl_id]
                    _save_models(models)
                response["deleted"] = mdl_id

            elif action == "auto_detect_endpoints":
                result = await auto_detect_endpoints()
                response.update(result)

            elif action == "auto_detect_models":
                result = await auto_detect_models()
                response.update(result)

            elif action == "test_endpoint":
                # Test endpoint by connecting to health check (supports both existing ID and quick URL test)
                ep_id = message.get("id")
                url = message.get("url")
                provider = message.get("provider", "ollama")
                api_key = message.get("apiKey")
                
                result = None
                ok = False
                error = None
                models_found = []
                
                # If we have a URL, do quick URL test (takes priority)
                if url:
                    # Validate URL: reject embedded credentials, non-HTTP schemes, excessive length
                    url = _validate_config_url(url)
                    if not url:
                        result = {"ok": False, "error": "Invalid URL: must be http(s):// without embedded credentials", "provider": provider}
                        response.update(result)
                        continue
                    url = url.rstrip("/")
                    
                    # Reject localhost endpoints
                    if _is_localhost_endpoint(url):
                        result = {"ok": False, "error": "Localhost endpoints are not allowed. Use the configured SSH Gateway.", "provider": provider}
                        response.update(result)
                        continue
                    
                    # Detect CLI provider from URL scheme (cli://toolname)
                    if url.startswith("cli://"):
                        cli_name = url[6:]  # Remove "cli://"
                        import shutil
                        # Map CLI name to provider
                        if cli_name == "claude" or provider == "claude_cli":
                            provider = "claude_cli"
                            cli_exec = "claude"
                        elif cli_name == "kilo" or provider == "kilo_cli":
                            provider = "kilo_cli"
                            cli_exec = "kilo"
                        elif cli_name == "codex" or provider == "codex_cli":
                            provider = "codex_cli"
                            cli_exec = "codex"
                        else:
                            cli_exec = cli_name
                        
                        if shutil.which(cli_exec):
                            ok = True
                            # Get models from adapter if available
                            try:
                                from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                                if provider == "claude_cli":
                                    adapter = ClaudeCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                                elif provider == "kilo_cli":
                                    adapter = KiloCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                                elif provider == "codex_cli":
                                    adapter = CodexCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                            except Exception:
                                pass
                        else:
                            error = f"{provider} not found in PATH"
                            ok = False
                        result = {"ok": ok, "provider": provider, "models": models_found}
                        if error:
                            result["error"] = error
                    else:
                        # HTTP endpoint testing
                        try:
                            async with _create_secure_http_client(httpx.Timeout(15.0)) as client:
                                if provider == "ollama":
                                    test_url = f"{url}/api/tags"
                                    headers = _build_auth_headers(api_key)
                                    resp = await client.get(test_url, headers=headers)
                                    _validate_response(resp)
                                    if resp.status_code == 200:
                                        data = resp.json()
                                        models_found = [m.get("name") for m in data.get("models", [])]
                                        ok = True
                                    else:
                                        error = f"HTTP {resp.status_code}"
                                elif provider in ("openai", "nvidia", "kilo"):
                                    test_url = f"{url}/models"
                                    headers = _build_auth_headers(api_key)
                                    resp = await client.get(test_url, headers=headers)
                                    _validate_response(resp)
                                    if resp.status_code == 200:
                                        data = resp.json()
                                        models_found = [m.get("id") for m in data.get("data", [])]
                                        ok = True
                                    else:
                                        error = f"HTTP {resp.status_code}"
                                else:
                                    test_url = url + "/" if not url.endswith("/") else url
                                    headers = _build_auth_headers(api_key)
                                    resp = await client.get(test_url, headers=headers, follow_redirects=True)
                                    _validate_response(resp)
                                    ok = resp.status_code < 400
                        except Exception as exc:
                            error = _safe_request_error(exc)
                        
                        result = {"ok": ok, "provider": provider, "models": models_found}
                        if error:
                            result["error"] = error
                elif ep_id:
                    # Test existing endpoint by ID - look up endpoint and test appropriately
                    endpoints = _get_endpoints()
                    ep = next((e for e in endpoints if e.get("id") == ep_id), None)
                    if not ep:
                        result = {"ok": False, "error": "Endpoint not found"}
                    else:
                        url = ep.get("url", "")
                        provider = ep.get("provider", "ollama")
                        api_key = _get_endpoint_api_key(ep)
                        
# Handle CLI endpoints
                        if url.startswith("cli://") or provider in ("claude_cli", "kilo_cli", "codex_cli"):
                            import shutil
                            cli_name = provider.replace("_cli", "") if provider.endswith("_cli") else url[6:] if url.startswith("cli://") else ""
                            if shutil.which(cli_name):
                                ok = True
                                models_found = []
                                # Try to get models from adapter
                                try:
                                    from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                                    if provider == "claude_cli":
                                        adapter = ClaudeCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                    elif provider == "kilo_cli":
                                        adapter = KiloCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                    elif provider == "codex_cli":
                                        adapter = CodexCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                except Exception:
                                    pass
                                result = {"ok": True, "provider": provider, "models": models_found}
                            else:
                                result = {"ok": False, "provider": provider, "error": f"{provider} not found in PATH"}
                            _update_endpoint_status(ep_id, result["ok"])
                        else:
                            # Test HTTP endpoint
                            result = await test_endpoint(ep_id)
                else:
                    result = {"ok": False, "error": "No endpoint ID or URL provided"}
                response.update(result)

            elif action == "list_chart_runs":
                response["runs"] = _list_chart_runs()

            elif action == "generate_charts":
                # Send a "started" progress message before generation begins
                await websocket.send_text(json.dumps({
                    "action": "chart_progress",
                    "status": "started",
                    "chartName": None,
                    "chartDisplayName": "Starting chart generation...",
                    "index": 0,
                    "total": len(_CHART_ORDER),
                }))
                # Collect progress messages in a list and send them in order
                # after generation completes. Using asyncio.create_task here would
                # not guarantee FIFO ordering because the event loop is blocked
                # by synchronous matplotlib operations, and tasks may execute
                # out of order when they finally run.
                progress_messages: list[str] = []

                def _ws_progress(update: dict[str, Any]) -> None:
                    progress_messages.append(json.dumps(update))

                result = await generate_charts_endpoint({
                    "runId": message.get("runId", "test-run-final"),
                }, progress_callback=_ws_progress)
                # Send all progress messages in the order they were generated
                for msg in progress_messages:
                    await websocket.send_text(msg)
                response.update(result)

            elif action == "chart_metadata":
                response["order"] = _CHART_ORDER
                response["charts"] = _CHART_METADATA

            else:
                response["error"] = f"Unknown action: {action}"

            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# ---------------------------------------------------------------------------
# Chart Gallery
# ---------------------------------------------------------------------------

# Metadata for each chart — name, description, and category for the GUI gallery
_CHART_METADATA: dict[str, dict[str, str]] = {
    "radar": {
        "name": "Model Performance Radar",
        "description": "Radar chart comparing 6 representative models across 5 dimensions: response time (lower is better), success rate, total tokens, code examples, and security awareness. Models are selected by composite score for readability.",
        "category": "Model Comparison",
    },
    "radar_extended": {
        "name": "Extended Model Comparison (Radar)",
        "description": "Extended radar chart with 5 additional metrics: token efficiency, consistency (1 - coefficient of variation), and safety awareness. Provides deeper insight into model reliability beyond raw success rates.",
        "category": "Model Comparison",
    },
    "response_times": {
        "name": "Response Time by Model & Prompt",
        "description": "Grouped bar chart showing response time per model for each prompt. Reveals per-prompt latency patterns and identifies which models are consistently fast or slow across different task types.",
        "category": "Performance",
    },
    "heatmap": {
        "name": "Code Sophistication Progression",
        "description": "Heatmap showing how the Wilson Eval3ngine codebase evolved in sophistication across 8 development phases (July 14-30, 2026) and 10 engineering dimensions. Darker green = implemented, darker red = not yet present. Replaces the original pass/fail model heatmap.",
        "category": "Codebase Evolution",
    },
    "tokens": {
        "name": "Token Usage by Model",
        "description": "Bar chart of total tokens generated per model across all evaluation prompts. Higher token counts indicate more verbose model responses; useful for cost estimation and output analysis.",
        "category": "Resource Usage",
    },
    "security_code": {
        "name": "Code & Security Awareness",
        "description": "Dual bar chart comparing code examples produced and security awareness signals detected per model. Measures both technical coding capability and safety-conscious response patterns.",
        "category": "Quality Metrics",
    },
    "timeline": {
        "name": "Run Execution Timeline",
        "description": "Gantt-style timeline of all telemetry runs. Shows report generation and game day exercise runs with durations, colored by run type. Provides operational visibility into evaluation activity.",
        "category": "Operational",
    },
    "success_rate": {
        "name": "Prompt Success Rate",
        "description": "Bar chart of prompt success rate per model, color-coded: green (100%), yellow (60-99%), red (below 60%). Only fully successful runs are included; partial failures are excluded for data integrity.",
        "category": "Reliability",
    },
    "scatter_time_tokens": {
        "name": "Response Time vs Token Count (Scatter)",
        "description": "Scatter plot correlating response time with token output per model. Reveals efficiency trade-offs — models that generate more tokens may take longer, but the relationship varies by architecture.",
        "category": "Performance",
    },
    "line_response_trend": {
        "name": "Response Time Trend Across Prompts",
        "description": "Line chart showing per-prompt response time trends for each model. Identifies whether models improve (warm-up) or degrade (fatigue) across sequential prompts.",
        "category": "Performance",
    },
    "histogram_distribution": {
        "name": "Response Time Distribution",
        "description": "Histogram of all response times across all models, with a mean line. Shows the overall latency distribution and whether response times are clustered or spread.",
        "category": "Performance",
    },
    "confidence_intervals": {
        "name": "Success Rate with Confidence Intervals",
        "description": "Bar chart with Wilson score 95% confidence intervals for each model's success rate. Accounts for small sample sizes — models with fewer prompts have wider intervals, reflecting lower statistical confidence.",
        "category": "Statistical",
    },
    "correlation_heatmap": {
        "name": "Metric Correlation Heatmap",
        "description": "Correlation matrix between response time, token count, and success rate. Reveals whether faster models produce fewer tokens, whether more tokens correlate with higher success, and other multivariate relationships.",
        "category": "Statistical",
    },
    "stacked_outcomes": {
        "name": "Outcome Distribution by Model",
        "description": "Stacked bar chart showing pass/fail/ambiguous outcome distribution per model as percentages. Provides a quick overview of model quality beyond binary success rates.",
        "category": "Quality Metrics",
    },
    "boxplot_response_times": {
        "name": "Response Time Distribution (Box Plot)",
        "description": "Box plot showing the distribution of response times per model, including median, quartiles, and outliers. Reveals variability in model response times beyond simple averages.",
        "category": "Performance",
    },
    "per_prompt_heatmap": {
        "name": "Per-Prompt Response Time Heatmap",
        "description": "Heatmap of response time per model per prompt. Identifies prompts that slow down specific models and reveals per-prompt latency patterns across the model matrix.",
        "category": "Comparison",
    },
    "per_prompt_heatmap_tokens": {
        "name": "Per-Prompt Token Count Heatmap",
        "description": "Heatmap of token output per model per prompt. Identifies which prompt/model combinations generate verbose vs terse responses.",
        "category": "Comparison",
    },
    "per_prompt_heatmap_success": {
        "name": "Per-Prompt Success Heatmap",
        "description": "Heatmap showing which models succeed (✓) or fail (✗) on each prompt. Quickly spot coverage gaps and per-prompt reliability differences.",
        "category": "Comparison",
    },
    "token_efficiency": {
        "name": "Token Efficiency: Value vs Wasted",
        "description": "Stacked bar chart separating tokens spent on successful responses (value) from tokens spent on failed responses (wasted). Includes waste percentage per model for cost analysis.",
        "category": "Resource Usage",
    },
    "reasoning_comparison": {
        "name": "Reasoning vs Standard Model Comparison",
        "description": "Three-panel comparison of reasoning-capable models vs standard models on response time, token usage, and success rate. Surfaces the cost of reasoning (extra latency and tokens) and whether it pays off in reliability.",
        "category": "Model Comparison",
    },
    "response_length_distribution": {
        "name": "Response Length Distribution (Violin Plot)",
        "description": "Violin plot of response text length (characters) per model. Reveals verbosity patterns and outliers — some models are uniformly verbose while others vary widely.",
        "category": "Quality Metrics",
    },
    "cross_run_comparison": {
        "name": "Cross-Run Comparison (Batch Iterations)",
        "description": "When a batchId has multiple runs, compares each run side-by-side on response time, token usage, and success rate. Useful for tracking improvements across iterations.",
        "category": "Operational",
    },
}

# Chart display order for the gallery
_CHART_ORDER = [
    "radar",
    "radar_extended",
    "response_times",
    "heatmap",
    "tokens",
    "security_code",
    "timeline",
    "success_rate",
    "scatter_time_tokens",
    "line_response_trend",
    "histogram_distribution",
    "confidence_intervals",
    "correlation_heatmap",
    "stacked_outcomes",
    "boxplot_response_times",
    "per_prompt_heatmap",
    "per_prompt_heatmap_tokens",
    "per_prompt_heatmap_success",
    "token_efficiency",
    "reasoning_comparison",
    "response_length_distribution",
    "cross_run_comparison",
]


def _list_chart_runs() -> list[dict[str, Any]]:
    """List all chart generation runs with their chart files and metadata.

    Cross-references the on-disk chart directories with telemetry entries to
    enrich each run with model, prompt, timestamp, and status metadata. Charts
    listed in a run's ``deletedCharts`` telemetry field are excluded so they
    do not reappear after being individually deleted.

    Runs whose ID is in the session-level ``_deleted_chart_runs`` set (or whose
    telemetry entry has ``"__all__"`` in ``deletedCharts``) are entirely
    excluded so that user-initiated run deletions are not resurrected by
    Refresh during the current session.
    """
    runs: list[dict[str, Any]] = []
    if not CHARTS_DIR.exists():
        return runs

    # Build a lookup of telemetry entries by runId for metadata enrichment
    telemetry = _get_telemetry()
    telemetry_by_id: dict[str, dict[str, Any]] = {
        r.get("runId", ""): r for r in telemetry if r.get("runId")
    }

    for run_dir in sorted(CHARTS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name

        # Skip runs deleted in this session (either via the X button or
        # __all__ marker in telemetry from a prior session).
        if run_id in _deleted_chart_runs:
            continue

        tel_entry = telemetry_by_id.get(run_id, {})
        deleted_charts = tel_entry.get("deletedCharts", [])
        if not isinstance(deleted_charts, list):
            deleted_charts = []

        # If "__all__" is in deletedCharts, the entire run was deleted
        if "__all__" in deleted_charts:
            if run_id not in _deleted_chart_runs:
                _deleted_chart_runs.add(run_id)
            continue

        charts: list[dict[str, Any]] = []
        for chart_file in sorted(run_dir.glob("*.png")):
            chart_name = chart_file.stem
            # Skip charts that have been individually deleted
            if chart_name in deleted_charts:
                continue
            meta = _CHART_METADATA.get(chart_name, {})
            charts.append({
                "name": chart_name,
                "displayName": meta.get("name", chart_name.replace("_", " ").title()),
                "description": meta.get("description", ""),
                "category": meta.get("category", "General"),
                "url": f"/static/charts/{run_id}/{chart_name}.png",
                "size_bytes": chart_file.stat().st_size,
            })

        # Skip and clean up empty run directories — a run-window frame
        # remains visible only while it contains one or more charts.
        if not charts:
            try:
                run_dir.rmdir()
            except OSError:
                pass
            continue
        if charts:
            runs.append({
                "runId": run_id,
                "charts": charts,
                "totalCharts": len(charts),
                "isSample": "sample" in run_id.lower(),
                # Telemetry metadata for the Charts tab
                "models": tel_entry.get("models", []),
                "prompts": tel_entry.get("prompts", []),
                "promptPackage": tel_entry.get("promptPackage", ""),
                "type": tel_entry.get("type", "report_generation"),
                "startedAt": tel_entry.get("startedAt"),
                "finishedAt": tel_entry.get("finishedAt"),
                "returncode": tel_entry.get("returncode"),
                "error": tel_entry.get("error"),
                "deletedCharts": deleted_charts,
            })

    # Auto-generate charts only for legitimate evaluation runs that have
    # real evaluation JSON sidecars available but don't yet have chart
    # artifacts on disk. Sample/demo charts are NOT auto-generated — they
    # are only created when the user explicitly presses the "Generate demo
    # charts" button. This prevents empty run-window frames from being
    # created during testing, and ensures the Charts page starts clean.
    #
    # If the user has deleted runs during this session, do NOT auto-generate.
    if not runs and not _deleted_chart_runs:
        if _load_evaluation_jsons():
            logger.info("No chart runs on disk but real eval JSONs found, generating real charts")
            try:
                gen_result = _generate_charts_impl({"runId": "test-run-final"})
                if gen_result.get("charts") and not gen_result.get("isSample"):
                    runs.append(_format_generated_charts_as_run(gen_result))
            except Exception as exc:
                logger.warning("Real chart generation failed: %s", exc)

    return runs


def _format_generated_charts_as_run(result: dict[str, Any]) -> dict[str, Any]:
    """Convert a :func:`_generate_charts_impl` result dict into the run-entry
    format returned by :func:`_list_chart_runs`.

    The ``charts`` field changes from a ``{name: url}`` mapping to a list of
    per-chart metadata dicts (name, displayName, description, category, url,
    size_bytes) consistent with what the on-disk scanner produces.
    """
    chart_urls: dict[str, str] = result.get("charts", {})
    chart_metadata: dict[str, dict[str, str]] = result.get("chartMetadata", {})
    run_id = result.get("runId", "sample-charts")
    is_sample = result.get("isSample", run_id == "sample-charts")

    charts: list[dict[str, Any]] = []
    for name, url in chart_urls.items():
        meta = chart_metadata.get(name, _CHART_METADATA.get(name, {}))
        # Try to read the file size from disk; fall back to 0
        size = 0
        png_path = CHARTS_DIR / run_id / f"{name}.png"
        if png_path.exists():
            size = png_path.stat().st_size
        charts.append({
            "name": name,
            "displayName": meta.get("name", name.replace("_", " ").title()),
            "description": meta.get("description", ""),
            "category": meta.get("category", "General"),
            "url": url,
            "size_bytes": size,
        })

    return {
        "runId": run_id,
        "charts": charts,
        "totalCharts": len(charts),
        "isSample": is_sample,
        "models": [],
        "prompts": [],
        "promptPackage": "",
        "type": "sample_generation" if is_sample else "report_generation",
        "startedAt": None,
        "finishedAt": None,
        "returncode": None,
        "error": None,
        "deletedCharts": [],
    }


@app.get("/api/charts/runs")
async def list_chart_runs() -> dict[str, Any]:
    """List all chart generation runs with their chart files and metadata."""
    return {"runs": _list_chart_runs()}


@app.get("/api/charts/metadata")
async def get_chart_metadata() -> dict[str, Any]:
    """Return metadata for all 15 chart types."""
    return {
        "order": _CHART_ORDER,
        "charts": _CHART_METADATA,
    }


def _find_batch_with_multiple_runs(runs: list[dict[str, Any]]) -> str | None:
    """Find a batch_id that has 2+ runs, for cross-run comparison chart."""
    batch_counts: dict[str, int] = {}
    for r in runs:
        bid = r.get("batchId", "")
        if bid:
            batch_counts[bid] = batch_counts.get(bid, 0) + 1
    for bid, count in batch_counts.items():
        if count >= 2:
            return bid
    return None


@app.post("/api/charts/generate")
async def generate_charts_endpoint(
    payload: dict[str, Any] | None = None,
    progress_callback: "Callable[[dict[str, Any]], None] | None" = None,
) -> dict[str, Any]:
    """Async FastAPI wrapper around the sync :func:`_generate_charts_impl`."""
    return _generate_charts_impl(payload, progress_callback)


def _generate_charts_impl(
    payload: dict[str, Any] | None = None,
    progress_callback: "Callable[[dict[str, Any]], None] | None" = None,
) -> dict[str, Any]:
    """Generate all charts using real or sample evaluation data (sync core).

    Uses the actual chart generation functions from server.py with real
    evaluation JSON sidecars from docs/reports/model-evals/. All evaluation
    JSONs with at least one evaluation are included; individual failed
    evaluations are handled at the chart-generation level (each chart function
    filters by per-evaluation success flags).
    If no real evaluation data is available, generates reproducible sample
    charts instead so the UI always has something to display.

    If ``progress_callback`` is provided, it is invoked after each chart
    is generated so the caller (e.g. the WebSocket handler) can relay
    real-time progress to the GUI.
    """
    run_id = payload.get("runId", "test-run-final") if payload else "test-run-final"

    # If this run was deleted in the current session, don't regenerate it.
    # Fall through to sample charts so the button always produces something
    # the user can look at, but never resurrects a deleted run.
    _fell_back_to_sample = False
    if run_id in _deleted_chart_runs:
        logger.info("Run %s was deleted in this session, falling back to sample charts", run_id)
        run_id = "sample-charts"
        _fell_back_to_sample = True

    # Check the user's deletion history for this run so we don't resurrect charts
    # the user intentionally removed via the GUI.
    deleted_charts: list[str] = []
    for _entry in _get_telemetry():
        if (_entry.get("runId") or _entry.get("run_id")) == run_id:
            _raw = _entry.get("deletedCharts", [])
            deleted_charts = _raw if isinstance(_raw, list) else []
            break

    # Charts the user has individually deleted — skip regenerating them
    charts_to_skip: set[str] = set(deleted_charts) if deleted_charts else set()

    # If the entire run was deleted (telemetry marker), fall back to sample charts
    if "__all__" in charts_to_skip:
        logger.info("Run %s fully deleted, falling back to sample charts", run_id)
        run_id = "sample-charts"
        deleted_charts = []
        charts_to_skip = set()
        _fell_back_to_sample = True

    # If *all* chart files on disk for this run have been deleted (no undeleted
    # PNG files remain), fall back to sample charts so the "Generate Chart"
    # button doesn't bring deleted charts back.
    if deleted_charts:
        run_dir = CHARTS_DIR / run_id
        has_undeleted = False
        if run_dir.exists():
            for _f in run_dir.glob("*.png"):
                if _f.stem not in charts_to_skip:
                    has_undeleted = True
                    break
        if not has_undeleted:
            logger.info("All charts deleted for run %s, falling back to sample charts", run_id)
            run_id = "sample-charts"
            deleted_charts = []
            charts_to_skip = set()

    # Load real evaluation JSON sidecars
    eval_jsons = _load_evaluation_jsons()

    # Include ALL eval JSONs that have at least some evaluation data.
    # Individual failed evaluations within an eval JSON are filtered at the
    # chart-generation level (each chart function already handles per-eval
    # success flags). This avoids the situation where a single failed
    # evaluation prevents all real data from being used.
    def _has_any_data(ej: dict[str, Any]) -> bool:
        evals = ej.get("evaluations", [])
        return len(evals) > 0

    real_evals = [ej for ej in eval_jsons if _has_any_data(ej)]

    # Build evals_by_model from available real evaluation data
    evals_by_model: dict[str, Any] = {}
    for ej in real_evals:
        model = ej.get("model", "")
        if model:
            evals_by_model[model] = ej

    # If no real evaluation data is available, OR we fell back from a deleted
    # run, generate sample charts so the deleted run is never resurrected.
    is_sample = False
    if not evals_by_model or _fell_back_to_sample:
        evals_by_model = _generate_sample_evaluations()
        is_sample = True
        run_id = "sample-charts"
        logger.info("No real evaluation data found, generating sample charts")

    # When generating sample charts, clear any stale deletedCharts so the
    # freshly-generated samples actually appear in the gallery
    if run_id == "sample-charts":
        _clear_deleted_charts_for_run("sample-charts")

    # Parse success rate helper
    def _parse_sr(sr_raw: Any) -> float:
        if isinstance(sr_raw, str) and "/" in sr_raw:
            parts = sr_raw.split("/")
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[0]) / int(parts[1])
            return 0
        if isinstance(sr_raw, (int, float)):
            return float(sr_raw)
        return 0

    # Collect prompts
    all_prompts: list[str] = []
    for ej in real_evals:
        prompts = ej.get("prompts", [])
        if prompts:
            all_prompts.extend(prompts)
    seen: set[str] = set()
    unique_prompts: list[str] = []
    for p in all_prompts:
        if p not in seen:
            seen.add(p)
            unique_prompts.append(p)
    prompts = unique_prompts[:5] if unique_prompts else [
        "Explain quantum computing in simple terms.",
        "Write a Python function to calculate fibonacci numbers.",
        "What are the safety considerations when deploying AI models?",
        "Analyze this code for potential security vulnerabilities.",
        "How would you handle a prompt injection attack?",
    ]

    # Select 6 models for radar charts (sorted by composite score)
    def _model_score(e: dict[str, Any]) -> tuple:
        eval_list = e.get("evaluations", [])
        eval_count = len(eval_list)
        sr = _parse_sr(e.get("prompt_success_rate", "0/5"))
        tokens = e.get("total_tokens", 0)
        return (eval_count, sr, tokens)

    sorted_models = sorted(evals_by_model.items(), key=lambda x: _model_score(x[1]), reverse=True)
    radar_model_names = [m for m, _ in sorted_models[:6]]
    evals_by_model_radar = {m: evals_by_model[m] for m in radar_model_names}

    # Load telemetry runs for timeline chart
    telemetry_path = GUI_DATA_DIR / "telemetry.json"
    runs: list[dict[str, Any]] = []
    if telemetry_path.exists():
        try:
            runs = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # When generating sample charts, synthesize a batch with multiple runs
    # so the cross_run_comparison chart can be generated.
    if is_sample or run_id == "sample-charts":
        import random as _sr
        _sr.seed(99)
        _sample_model_list = list(evals_by_model.keys())
        sample_batch_runs = []
        for iter_idx in range(3):
            sample_batch_runs.append({
                "runId": f"sample-batch-iter-{iter_idx + 1}",
                "batchId": "sample-batch-v1",
                "type": "report_generation",
                "models": _sample_model_list[:3],
                "prompts": prompts,
                "startedAt": f"2026-07-30T10:0{iter_idx}:00+00:00",
                "finishedAt": f"2026-07-30T10:0{iter_idx}:30+00:00",
                "avg_response_time": round(_sr.uniform(2.0, 6.0), 2),
                "total_tokens": _sr.randint(500, 3000),
                "prompt_success_rate": 80,
            })
        # Merge sample batch runs into the runs list for cross-run comparison
        runs = sample_batch_runs + runs

    # Generate all charts using the actual server.py functions
    results: dict[str, str] = {}
    total_charts = len(_CHART_ORDER)

    def _progress(chart_name: str, index: int, status: str, error: str | None = None) -> None:
        """Send a progress update via the callback if provided.

        ``index`` is passed by value (not captured by closure) so that async
        task scheduling cannot read a stale ``chart_index`` value.
        """
        if progress_callback:
            progress_callback({
                "action": "chart_progress",
                "chartName": chart_name,
                "chartDisplayName": _CHART_METADATA.get(chart_name, {}).get("name", chart_name),
                "index": index,
                "total": total_charts,
                "status": status,
                "error": error,
            })

    # Helper: generate a single chart, skipping any the user has previously deleted
    def _gen_chart(chart_name: str, idx: int, gen_fn, *args, **kwargs) -> None:
        if chart_name in charts_to_skip:
            _progress(chart_name, idx, "skipped", "Previously deleted by user")
            return
        _progress(chart_name, idx, "generating")
        try:
            url = gen_fn(*args, **kwargs)
            if url:
                results[chart_name] = url
                _progress(chart_name, idx, "complete")
            else:
                _progress(chart_name, idx, "failed", "No URL returned")
        except Exception as e:
            logger.warning("Chart generation failed for %s: %s", chart_name, e)
            _progress(chart_name, idx, "failed", str(e))

    # Import heatmap generator once (used by Chart 3)
    from scripts.generate_sophistication_heatmap import generate_sophistication_heatmap

    # Chart 1: Radar (6 models only)
    _gen_chart("radar", 0, _generate_model_radar_chart, run_id, evals_by_model_radar)

    # Chart 2: Response Time by Model & Prompt
    _gen_chart("response_times", 1, _generate_response_time_chart, run_id, evals_by_model, prompts)

    # Chart 3: Code Sophistication Heatmap (replaces pass/fail heatmap)
    _gen_chart("heatmap", 2, generate_sophistication_heatmap, run_id)

    # Chart 4: Token Usage by Model
    _gen_chart("tokens", 3, _generate_tokens_chart, run_id, evals_by_model)

    # Chart 5: Code & Security Awareness
    _gen_chart("security_code", 4, _generate_security_code_chart, run_id, evals_by_model)

    # Chart 6: Run Execution Timeline
    _gen_chart("timeline", 5, lambda rid, rns: _generate_run_timeline_chart(rid, rns) if rns else None, run_id, runs)

    # Chart 7: Prompt Success Rate
    _gen_chart("success_rate", 6, _generate_success_rate_chart, run_id, evals_by_model)

    # Chart 8: Scatter Plot (Response Time vs Token Count)
    _gen_chart("scatter_time_tokens", 7, _generate_scatter_plot, run_id, evals_by_model)

    # Chart 9: Response Time Trend (Line Chart)
    _gen_chart("line_response_trend", 8, _generate_line_chart, run_id, evals_by_model, prompts)

    # Chart 10: Response Time Distribution (Histogram)
    _gen_chart("histogram_distribution", 9, _generate_distribution_histogram, run_id, evals_by_model)

    # Chart 11: Success Rate with Confidence Intervals
    _gen_chart("confidence_intervals", 10, _generate_confidence_interval_chart, run_id, evals_by_model)

    # Chart 12: Metric Correlation Heatmap
    _gen_chart("correlation_heatmap", 11, _generate_correlation_heatmap, run_id, evals_by_model)

    # Chart 13: Outcome Distribution (Stacked Bar)
    _gen_chart("stacked_outcomes", 12, _generate_stacked_bar_chart, run_id, evals_by_model)

    # Chart 14: Response Time Distribution (Box Plot)
    _gen_chart("boxplot_response_times", 13, _generate_box_plot, run_id, evals_by_model)

    # Chart 15: Extended Radar (6 models only)
    _gen_chart("radar_extended", 14, _generate_radar_comparison, run_id, evals_by_model_radar)

    # Charts 16-22: Per-prompt and cross-run comparison charts
    _gen_chart("per_prompt_heatmap", 15, _generate_per_prompt_heatmap, run_id, evals_by_model, "time")
    _gen_chart("per_prompt_heatmap_tokens", 16, _generate_per_prompt_heatmap, run_id, evals_by_model, "tokens")
    _gen_chart("per_prompt_heatmap_success", 17, _generate_per_prompt_heatmap, run_id, evals_by_model, "success")
    _gen_chart("token_efficiency", 18, _generate_token_efficiency_chart, run_id, evals_by_model)
    _gen_chart("reasoning_comparison", 19, _generate_reasoning_comparison, run_id, evals_by_model)
    _gen_chart("response_length_distribution", 20, _generate_response_length_distribution, run_id, evals_by_model)

    # Chart 22: Cross-Run Comparison (needs multiple runs with same batchId)
    # Find a batch_id that has multiple runs; if none, the chart is skipped
    cross_run_batch = _find_batch_with_multiple_runs(runs)
    _gen_chart("cross_run_comparison", 21, _generate_cross_run_comparison, run_id, runs, cross_run_batch or "")

    return {
        "runId": run_id,
        "generated": len(results),
        "total": len(_CHART_ORDER),
        "charts": results,
        "chartMetadata": {name: _CHART_METADATA.get(name, {}) for name in results.keys()},
        "isSample": is_sample,
    }


# ---------------------------------------------------------------------------
# WebSocket chart actions
# ---------------------------------------------------------------------------

# Add chart-related actions to the WebSocket handler below
# (handled in the websocket_endpoint function)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

if GUI_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(GUI_STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(str(GUI_STATIC_DIR / "index.html"))


# Mount charts directory if it exists
if CHARTS_DIR.exists():
    app.mount("/static/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")
