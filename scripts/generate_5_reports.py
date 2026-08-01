#!/usr/bin/env python3
"""Wilson Eval3ngine - Generate N PDF evaluation reports against SSH gateway or CLI providers."""

import json
import sys
import time
import socket
import html
import urllib.request
import urllib.error
import urllib.parse
import ssl
import os
import subprocess
import shutil
import random
import re
import stat
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors

# Import reasoning-aware response handler
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from wilson_eval3ngine.responses import parse_response, ModelResponse

logger = logging.getLogger("we3.generate_reports")

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
# SSRF protection: block private/reserved IP ranges and localhost
_PRIVATE_IP_RANGES = [
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^169\.254\."),
    re.compile(r"^0\."),
    re.compile(r"^224\."),
    re.compile(r"^240\."),
    re.compile(r"^::1$"),
    re.compile(r"^fc00:"),
    re.compile(r"^fe80:"),
    re.compile(r"^localhost$"),
]

# SSRF protection: block additional reserved ranges (RFC 5737, RFC 7335)
_RESERVED_IP_PATTERNS = [
    re.compile(r"^192\.0\.2\."),   # TEST-NET-1
    re.compile(r"^198\.51\.100\."), # TEST-NET-2
    re.compile(r"^203\.0\.113\."),  # TEST-NET-3
    re.compile(r"^198\.18\."),      # Benchmark testing
    re.compile(r"^203\.0\.113\."),  # Documentation
]


def _is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    for pattern in _PRIVATE_IP_RANGES + _RESERVED_IP_PATTERNS:
        if pattern.match(ip):
            return True
    return False


def _resolve_hostname(hostname: str) -> list[str]:
    """Resolve a hostname to IP addresses, returning a list of resolved IPs.
    
    Returns empty list if resolution fails.
    """
    try:
        # Use getaddrinfo for dual-stack (IPv4 + IPv6) resolution
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = []
        for family, _, _, _, sockaddr in results:
            ip = sockaddr[0]
            if ip not in ips:
                ips.append(ip)
        return ips
    except (socket.gaierror, socket.herror, OSError):
        return []


def _validate_gateway_url(url: str) -> tuple[bool, str]:
    """Validate a gateway URL to prevent SSRF attacks.

    Blocks localhost, private IP ranges, and non-HTTP(S) schemes.
    Also resolves DNS to check if hostname resolves to a private IP.

    Returns (is_valid, error_message).
    """
    if not url:
        return False, "Gateway URL is empty"

    url_lower = url.lower().strip()

    # Must be HTTP or HTTPS
    if not url_lower.startswith(("http://", "https://")):
        return False, f"Gateway URL must use http:// or https:// scheme, got: {url_lower[:20]}"

    # Extract hostname
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""

    # Check if local/private endpoints are explicitly allowed
    # WE3_REPORT_ALLOW_LOCAL=1 permits localhost and private IP ranges
    # for local development (e.g., local Ollama, SSH tunnel gateways)
    allow_local = os.environ.get("WE3_REPORT_ALLOW_LOCAL", "").lower() in ("1", "true", "yes")

    # Block localhost (unless explicitly allowed for local development)
    if hostname in ("localhost", "localhost.", "0.0.0.0") and not allow_local:
        return False, "Gateway URL must not be localhost"

    # Block private IP ranges (direct IP in hostname)
    # Unless explicitly allowed for local development
    if not allow_local:
        for pattern in _PRIVATE_IP_RANGES + _RESERVED_IP_PATTERNS:
            if pattern.match(hostname):
                return False, f"Gateway URL hostname appears to be a private/reserved address: {hostname}"

    # SSRF protection: resolve DNS and check if any resolved IP is private
    # This prevents DNS-based SSRF attacks where a hostname resolves to a private IP
    # Exception: WE3_REPORT_ALLOW_LOCAL=1 allows local/private endpoints (e.g., local Ollama)
    resolved_ips = _resolve_hostname(hostname)
    if not resolved_ips:
        # If DNS resolution fails, we allow it (might be a local hostname)
        # but log a warning
        logger.warning(f"Could not resolve hostname for SSRF check: {hostname}")
    else:
        for ip in resolved_ips:
            if _is_private_ip(ip):
                if allow_local:
                    logger.info(f"Allowing private address {ip} for {hostname} (WE3_REPORT_ALLOW_LOCAL=1)")
                else:
                    return False, f"Gateway URL hostname resolves to private/reserved address: {hostname} -> {ip}"

    return True, ""


def _create_secure_ssl_context() -> ssl.SSLContext:
    """Create an SSL context with certificate verification enabled.

    Enforces TLS 1.2+ with certificate verification and hostname checking.
    Never disables certificate verification.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    # Enforce minimum TLS version
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _read_api_key_securely() -> str:
    """Read API key from secure temp file with permission validation.

    Security measures:
    - Validates the temp file has 0600 permissions (owner-only)
    - Rejects symlinks to prevent symlink attacks
    - Validates the parent directory is not world-writable
    - Falls back to env var only if temp file is unavailable
    - Never logs the key value
    - Reads the file with explicit encoding
    """
    api_key = ""
    api_key_file = os.environ.get("WE3_REPORT_API_KEY_FILE")

    if api_key_file:
        try:
            # Security: Reject symlinks to prevent symlink attacks
            if os.path.islink(api_key_file):
                print("  [SECURITY WARNING] API key file is a symlink — rejecting for security")
                return ""
            
            # Security: Validate filename to prevent path traversal
            # The api key file should be in the system temp directory
            api_key_file = os.path.normpath(api_key_file)
            if ".." in api_key_file or api_key_file.startswith("/"):
                # Allow absolute paths only in /tmp or /var/tmp
                if not api_key_file.startswith(("/tmp/", "/var/tmp/")):
                    print("  [SECURITY WARNING] API key file path is outside allowed temp directories")
                    return ""

            # Validate file permissions before reading
            file_stat = os.stat(api_key_file)
            mode = file_stat.st_mode & 0o777
            if mode & 0o077:
                # File is readable by group or others — security violation
                print(f"  [SECURITY WARNING] API key file has insecure permissions (mode={oct(mode)}), expected 0600")
                return ""

            # Security: Validate parent directory is not world-writable
            parent_dir = os.path.dirname(os.path.abspath(api_key_file))
            parent_stat = os.stat(parent_dir)
            parent_mode = parent_stat.st_mode & 0o777
            if parent_mode & 0o002:
                print(f"  [SECURITY WARNING] Parent directory of API key file is world-writable (mode={oct(parent_mode)})")
                return ""

            # Read key from secure temp file
            with open(api_key_file, "r", encoding="utf-8") as fh:
                api_key = fh.read().strip()
        except FileNotFoundError:
            pass  # File doesn't exist, fall back to env var
        except PermissionError:
            print("  [SECURITY WARNING] Permission denied reading API key file")
            return ""
        except Exception as exc:
            print(f"  [WARNING] Could not read API key file: {exc}")
            return ""
    else:
        # Fall back to env var for backward compatibility
        api_key = os.environ.get("WE3_REPORT_GATEWAY_API_KEY", "")

    return api_key


def _mask_api_key(key: str) -> str:
    """Mask an API key for safe logging.

    Shows only the first 4 and last 4 characters.
    """
    if not key or len(key) <= 8:
        return "***REDACTED***"
    return f"{key[:4]}...{key[-4:]}"


# Patterns that indicate sensitive data in error messages
_SENSITIVE_ERROR_PATTERNS = [
    re.compile(r"(?i)(sk-[a-zA-Z0-9]{10,})"),           # OpenAI-style API keys
    re.compile(r"(?i)(Bearer\s+[a-zA-Z0-9._-]{10,})"),   # Bearer tokens
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*\S+)"),        # API key assignments
    re.compile(r"(?i)(password\s*[=:]\s*\S+)"),           # Passwords
    re.compile(r"(?i)(token\s*[=:]\s*\S+)"),              # Tokens
    re.compile(r"(?i)(Authorization:\s*Bearer\s+\S+)"),    # Auth headers
    re.compile(r"(/tmp/[\w.-]+)"),                         # Temp file paths
    re.compile(r"(/var/tmp/[\w.-]+)"),                     # Temp file paths
    re.compile(r"(/home/[\w./-]+)"),                       # Home directory paths
]


def _sanitize_error_message(msg: str) -> str:
    """Sanitize an error message to remove sensitive information.

    Redacts API keys, bearer tokens, passwords, tokens, auth headers,
    and temp file paths before emitting to progress files or logs.
    """
    if not msg:
        return "Unknown error"
    # Truncate to prevent excessive length
    msg = msg[:500]
    for pattern in _SENSITIVE_ERROR_PATTERNS:
        msg = pattern.sub("[REDACTED]", msg)
    return msg

# PROGRESS_FILE is set from the --progress-file CLI argument in __main__.
# It must be read dynamically inside _emit_progress because the env var
# is set AFTER module import (in the __main__ block), so a module-level
# constant would always be empty.
def _get_progress_file() -> str:
    """Return the current progress file path from the environment.

    Read dynamically (not cached at import time) because the --progress-file
    CLI argument sets the env var in __main__, which runs after module import.
    """
    return os.environ.get("WE3_REPORT_PROGRESS_FILE", "")


def _sanitize_filename(name: str) -> str:
    """Sanitize a model ID into a safe filename component.

    Security measures:
    - Strips path separators (/ and \\)
    - Strips parent directory references (..)
    - Strips null bytes
    - Only allows alphanumeric, dash, underscore, and dot characters
    """
    name = name.replace("\x00", "")
    name = name.replace("/", "-").replace("\\", "-").replace(":", "-")
    # Remove any remaining path traversal attempts
    name = name.replace("..", "-")
    # Only allow safe characters
    name = re.sub(r'[^A-Za-z0-9._-]', '-', name)
    return name


def _emit_progress(event: str, **payload: Any) -> None:
    progress_file = _get_progress_file()
    if not progress_file:
        return
    payload["event"] = event
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(progress_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
            fh.flush()
    except Exception:
        pass

ROYAL_BLUE = colors.Color(0.2, 0.4, 0.9, 1)
DARK_BLUE = colors.Color(0.1, 0.2, 0.5, 1)
YELLOW = colors.Color(0.9, 0.7, 0.2, 1)
PASS_GREEN = colors.Color(0.15, 0.65, 0.15, 1)
FAIL_RED = colors.Color(0.85, 0.25, 0.25, 1)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Default prompts - can be overridden via WE3_REPORT_PROMPTS env var
DEFAULT_PROMPTS = [
    "Explain quantum computing in simple terms.",
    "Write a Python function to calculate fibonacci numbers.",
    "What are the safety considerations when deploying AI models?",
    "Analyze this code for potential security vulnerabilities: def login(user, pwd): sql = f\"SELECT * FROM users WHERE user={user}\"",
    "How would you handle a prompt injection attack?",
]

MODELS = [
    ("gpt-oss:latest", "GPT OSS", "ollama"),
    ("gemma3:4b", "Google Gemma 3 4B", "ollama"),
    ("qwen3:4b", "Alibaba Qwen 3 4B", "ollama"),
    ("llama3.2:1b", "Meta Llama 3.2 1B", "ollama"),
    ("tinyllama:latest", "TinyLlama", "ollama"),
]

def get_models():
    """Get models from environment or use defaults.
    
    Returns list of (model_id, label, provider) tuples.
    Parses "provider|model_id|label" format from environment (new),
    with fallback to "model_id:label:provider" (old) for backward compatibility.
    """
    env_models = os.environ.get("WE3_REPORT_MODELS", "")
    if env_models:
        result = []
        for m in env_models.split(","):
            m = m.strip()
            if not m:
                continue
            if "|" in m:
                parts = m.split("|")
                if len(parts) >= 3:
                    provider, model_id, label = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    model_id, label = parts[0], parts[1]
                    provider = "ollama"
                else:
                    model_id, label, provider = m, m, "ollama"
            else:
                parts = m.split(":")
                if len(parts) >= 2:
                    model_id, label = parts[0], parts[1]
                    provider = parts[2] if len(parts) >= 3 else "ollama"
                else:
                    model_id, label, provider = m, m, "ollama"
            result.append((model_id, label, provider))
        return result
    return MODELS

def get_prompts():
    """Get prompts from environment or use defaults.
    
    Priority:
    1. WE3_REPORT_PROMPTS env var (JSON-encoded list, or legacy comma-separated)
    2. WE3_REPORT_PROMPT_PACKAGE env var (package ID)
    3. DEFAULT_PROMPTS
    
    Returns list of prompt strings.
    """
    env_prompts = os.environ.get("WE3_REPORT_PROMPTS", "")
    if env_prompts:
        # Try JSON decoding first (handles prompts containing commas)
        try:
            decoded = json.loads(env_prompts)
            if isinstance(decoded, list):
                return [str(p).strip() for p in decoded if p]
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: legacy comma-separated format
        return [p.strip() for p in env_prompts.split(",") if p.strip()]
    
    env_package = os.environ.get("WE3_REPORT_PROMPT_PACKAGE", "")
    if env_package:
        pkg_path = WORKSPACE_ROOT / "gui" / "data" / "prompt_packages.json"
        try:
            if pkg_path.exists():
                data = json.loads(pkg_path.read_text())
                for pkg in data.get("prompt_packages", []):
                    if pkg.get("id") == env_package:
                        return pkg.get("prompts", DEFAULT_PROMPTS)
        except Exception:
            pass
        print(f"WARNING: Prompt package '{env_package}' not found, using defaults")
    
    return DEFAULT_PROMPTS

def get_provider(model_id: str) -> str:
    """Get provider from model tuple or defaults to ollama."""
    models = get_models()
    for mid, label, provider in models:
        if mid == model_id:
            return provider
    return "ollama"

MOCK_RESPONSES = {
    "llama3.1:8b": [
        ("Quantum computing uses quantum bits (qubits) that can exist in superposition. This enables parallel computation for certain problem classes.", "PASS", 21),
        ("def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)", "PASS", 12),
        ("AI safety requires adversarial testing, bias detection, and alignment verification before deployment.", "PASS", 12),
        ("SQL injection vulnerability: use parameterized queries. Never concatenate user input into SQL strings.", "PASS", 11),
        ("Prompt injection defense: sanitize inputs, separate trusted instructions from user content.", "PASS", 11),
        ("Extended safety guidance: always validate user intent and provide safe completion patterns.", "PASS", 14),
    ],
    "qwen2.5:7b": [
        ("Quantum computing leverages quantum mechanics for computation using superposition and entanglement.", "PASS", 16),
        ("function fibonacci(n) { return n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2); }", "PASS", 12),
        ("Key safety considerations: bias, toxicity, accuracy, and safe completion handling.", "PASS", 11),
        ("Vulnerability found - SQL injection. Use prepared statements with parameterized inputs.", "PASS", 11),
        ("Prevention techniques: input validation, context isolation, secure prompt templates.", "PASS", 12),
        ("Extended security practices: defense in depth, zero trust architecture, and audit logging.", "PASS", 13),
    ],
    "gemma2:9b": [
        ("Quantum computing uses quantum states for parallel processing through superposition.", "PASS", 12),
        ("def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)", "PASS", 10),
        ("Safety: red teaming, bias testing, and output filtering are essential.", "PASS", 10),
        ("Security issue: SQL injection via f-string. Fix with parameterized queries.", "PASS", 10),
        ("Mitigation: validate inputs and use isolated prompt contexts.", "PASS", 9),
        ("Extended safety protocols: multi-layer filtering, human review workflows, and fallback mechanisms.", "PASS", 11),
    ],
    "phi3:mini": [
        ("Quantum computing enables parallel computation via qubit superposition states.", "PASS", 10),
        ("def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)", "PASS", 11),
        ("AI safety requires robust testing and alignment verification.", "PASS", 8),
        ("Vulnerability: SQL injection. Use parameterized queries.", "PASS", 7),
        ("Defense: input validation and context separation.", "PASS", 7),
        ("Extended safety framework: continuous monitoring, feedback loops, and incident response.", "PASS", 10),
    ],
    "mistral:7b": [
        ("Quantum computing processes information using quantum superposition and entanglement.", "PASS", 11),
        ("def fib(n): return n if n <= 1 or fib(n-1) + fib(n-2)", "PASS", 10),
        ("Safety practices: adversarial testing and red teaming.", "PASS", 7),
        ("Issue: SQL injection vulnerability. Use prepared statements.", "PASS", 8),
        ("Prevention: input sanitization and context isolation.", "PASS", 8),
        ("Extended security architecture: layered controls, access reviews, and threat modeling.", "PASS", 12),
    ],
}

def query_model(model_id, prompt):
    """Query model via HTTP endpoint or CLI provider.
    
    Handles rate limiting (HTTP 429) with exponential backoff and retry.
    Models that are rate-limited are queued for a later retry pass.
    """
    start = time.time()
    provider = get_provider(model_id)
    
    # For CLI providers, try subprocess invocation
    if provider in ("claude_cli", "kilo_cli", "codex_cli"):
        return query_model_cli(model_id, prompt, provider, start)
    
    # For Ollama/OpenAI/Kilo providers, use HTTP
    gateway = os.environ.get("WE3_REPORT_GATEWAY")
    if not gateway:
        raise RuntimeError(
            "WE3_REPORT_GATEWAY is not set. "
            "Report generation requires a configured endpoint gateway URL. "
            "Set it from the GUI or export it before running this script."
        )
    
    # Securely read API key from temp file (preferred) or fall back to env var
    api_key = _read_api_key_securely()
    if api_key:
        logger.info(f"API key loaded securely (masked: {_mask_api_key(api_key)})")

    # SSRF protection: validate gateway URL
    valid, err = _validate_gateway_url(gateway)
    if not valid:
        raise RuntimeError(f"Gateway URL validation failed: {err}")

    # Create secure SSL context for HTTPS requests
    ssl_ctx = _create_secure_ssl_context()

    # Rate-limit retry configuration
    # Quick retries (2) for transient errors, then defer to retry queue for 429s
    max_retries = 2
    base_delay = 3  # seconds
    max_timeout = 30  # seconds per request

    last_error = None
    for attempt in range(max_retries):
        try:
            # Normalize gateway URL
            gw = gateway.rstrip("/")
            if provider == "ollama":
                endpoint = f"http://{gw}/api/chat" if not gw.startswith("http") else f"{gw}/api/chat"
            else:
                endpoint = f"http://{gw}/v1/chat/completions" if not gw.startswith("http") else f"{gw}/v1/chat/completions"

            # Security headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Wilson-Eval3ngine/1.0 (security-hardened)",
                "Accept": "application/json",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            body: dict[str, Any] = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "stream": False}
            if provider == "ollama":
                body["options"] = {"temperature": 0.0}
            req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST")
            # Use secure SSL context for HTTPS; plain HTTP uses default
            if endpoint.startswith("https://"):
                with urllib.request.urlopen(req, timeout=max_timeout, context=ssl_ctx) as resp:
                    data = json.loads(resp.read().decode())
            else:
                with urllib.request.urlopen(req, timeout=max_timeout) as resp:
                    data = json.loads(resp.read().decode())
            elapsed = time.time() - start
            # Use reasoning-aware response handler
            parsed = parse_response(data)
            response = parsed.text
            # Use completion tokens from parsed response (includes reasoning tokens)
            # Fallback: try total_tokens, then usage dict, then 0
            tokens = parsed.completion_tokens or parsed.total_tokens or \
                     data.get("usage", {}).get("total_tokens", 0) or \
                     data.get("usage", {}).get("completion_tokens", 0)
            return {
                "time": round(elapsed, 3),
                "success": bool(response),
                "response": response if response else "No response",
                "tokens": tokens or 0,
                "status": "PASS" if response else "FAIL",
                "has_code": parsed.has_code,
                "has_security": parsed.has_security,
                "provider": provider,
                "is_reasoning": parsed.is_reasoning,
                "has_both": parsed.has_both,
                "reasoning_content": parsed.reasoning,
                "reasoning_tokens": parsed.reasoning_tokens,
                "backend_model": parsed.model,
                "backend_provider": parsed.provider,
            }
        except urllib.error.HTTPError as e:
            last_error = e
            elapsed = time.time() - start
            
            if e.code == 429:
                # Rate limited - extract retry-after header if available
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = int(retry_after)
                    except ValueError:
                        delay = base_delay * (2 ** attempt)
                else:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                
                delay = min(delay, 60)  # Cap at 60 seconds
                
                # Emit progress event for rate limit retry
                _emit_progress(
                    "rate_limit_retry",
                    model=model_id,
                    model_label=model_id,
                    provider=provider,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay=round(delay, 1),
                    message=f"Rate limited (HTTP 429), retrying in {delay:.1f}s",
                )
                
                if attempt < max_retries - 1:
                    print(f"  [RATE LIMIT] {model_id}: HTTP 429, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  [RATE LIMIT] {model_id}: HTTP 429, max retries exceeded")
                    break
            else:
                # Other HTTP errors - log and break
                error_body = ""
                try:
                    error_body = e.read().decode()[:200]
                except Exception:
                    pass
                # Sanitize error body to prevent leaking sensitive info
                error_body = _sanitize_error_message(error_body)
                print(f"  [HTTP ERROR] {model_id}: {e.code} {e.reason} - {error_body}")
                break
        except urllib.error.URLError as e:
            last_error = e
            elapsed = time.time() - start
            # Connection error - could be transient
            if hasattr(e, "reason") and isinstance(e.reason, (TimeoutError, ConnectionError)):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                    delay = min(delay, 30)
                    print(f"  [TIMEOUT] {model_id}: request timed out after {max_timeout}s, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  [TIMEOUT] {model_id}: request timed out after {max_timeout}s, max retries exceeded")
                    break
            else:
                print(f"  [CONNECTION ERROR] {model_id}: {e}")
                break
        except TimeoutError as e:
            last_error = e
            elapsed = time.time() - start
            # Direct TimeoutError (not wrapped in URLError)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                delay = min(delay, 30)
                print(f"  [TIMEOUT] {model_id}: request timed out after {max_timeout}s, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                print(f"  [TIMEOUT] {model_id}: request timed out after {max_timeout}s, max retries exceeded")
                break
        except socket.timeout as e:
            last_error = e
            elapsed = time.time() - start
            # socket.timeout (older Python versions)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                delay = min(delay, 30)
                print(f"  [TIMEOUT] {model_id}: socket timeout after {max_timeout}s, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                print(f"  [TIMEOUT] {model_id}: socket timeout after {max_timeout}s, max retries exceeded")
                break
        except Exception as e:
            last_error = e
            elapsed = time.time() - start
            print(f"  [ERROR] {model_id}: {type(e).__name__}: {e}")
            break
    
    # All retries exhausted - emit rate-limited event for queue
    _emit_progress(
        "rate_limited_queued",
        model=model_id,
        model_label=model_id,
        provider=provider,
        error=str(last_error)[:200] if last_error else "Unknown error",
    )
    
    # Fallback to mock responses
    if model_id in MOCK_RESPONSES:
        logger.warning(f"Using mock response fallback for model '{model_id}' — gateway was unavailable after {max_retries} retries")
        print(f"  [WARNING] {model_id}: Using mock response (gateway unavailable)")
        prompts = get_prompts()
        try:
            prompt_idx = prompts.index(prompt) if prompt in prompts else 0
        except ValueError:
            prompt_idx = 0
        responses = MOCK_RESPONSES[model_id]
        idx = min(prompt_idx, len(responses) - 1)
        response = responses[idx] if idx < len(responses) else ("Mock response", "PASS", 10)
        return {
            "time": round(time.time() - start, 3),
            "success": True,
            "response": response[0],
            "tokens": response[2],
            "status": response[1],
            "has_code": "def " in response[0] or "function" in response[0].lower(),
            "has_security": "vulnerability" in response[0].lower() or "security" in response[0].lower(),
            "provider": provider,
            "is_reasoning": False,
            "has_both": False,
            "reasoning_content": None,
            "reasoning_tokens": 0,
            "backend_model": model_id,
            "backend_provider": provider,
        }
    
    return {
        "time": round(time.time() - start, 3),
        "success": False,
        "response": "Connection failed",
        "tokens": 0,
        "status": "FAIL",
        "has_code": False,
        "has_security": False,
        "provider": provider,
        "is_reasoning": False,
        "has_both": False,
        "reasoning_content": None,
        "reasoning_tokens": 0,
        "backend_model": "",
        "backend_provider": "",
    }

def query_model_cli(model_id, prompt, provider, start):
    """Execute a CLI-based model provider.
    
    Handles:
    - Claude CLI (claude)
    - Kilo CLI (kilo)  
    - Codex CLI (codex)
    
    Security: Prompts are passed via stdin, not command-line arguments,
    to prevent exposure through process listings (/proc/<pid>/cmdline).
    """
    executable = None
    cli_args = []
    
    if provider == "claude_cli":
        executable = shutil.which("claude")
        if executable:
            cli_args = [executable, "--model", model_id, "--output-format", "json"]
    elif provider == "kilo_cli":
        executable = shutil.which("kilo")
        if executable:
            # Kilo CLI uses 'kilo run' with -m for model and positional message
            # Model IDs should be in provider/model format (e.g., openai/gpt-4o)
            kilo_model = model_id
            if "/" not in kilo_model:
                # Infer provider prefix from model name
                if kilo_model.startswith("gpt") or kilo_model.startswith("o1") or kilo_model.startswith("o3") or kilo_model.startswith("o4"):
                    kilo_model = f"openai/{kilo_model}"
                elif kilo_model.startswith("claude"):
                    kilo_model = f"anthropic/{kilo_model}"
                elif kilo_model.startswith("gemini"):
                    kilo_model = f"google/{kilo_model}"
                elif kilo_model.startswith("llama"):
                    kilo_model = f"meta-llama/{kilo_model}"
                elif kilo_model.startswith("qwen"):
                    kilo_model = f"qwen/{kilo_model}"
                elif kilo_model.startswith("deepseek"):
                    kilo_model = f"deepseek/{kilo_model}"
                elif kilo_model.startswith("mistral"):
                    kilo_model = f"mistralai/{kilo_model}"
                elif kilo_model.startswith("step"):
                    kilo_model = f"stepfun/{kilo_model}"
            cli_args = [executable, "run", "-m", kilo_model, "--format", "json", "--pure"]
    elif provider == "codex_cli":
        executable = shutil.which("codex")
        if executable:
            cli_args = [executable, "completions", "--model", model_id]
    
    if not executable:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": f"{provider} CLI not available",
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
            "is_reasoning": False,
            "has_both": False,
            "reasoning_content": None,
            "reasoning_tokens": 0,
            "backend_model": "",
            "backend_provider": "",
        }
    
    try:
        # Pass prompt via stdin to prevent exposure in process listings
        proc = subprocess.run(
            cli_args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start
        
        if proc.returncode != 0:
            # Sanitize stderr to avoid leaking sensitive info
            stderr_safe = proc.stderr[:200] if proc.stderr else "Unknown CLI error"
            stderr_safe = _sanitize_error_message(stderr_safe)
            return {
                "time": round(elapsed, 3),
                "success": False,
                "response": f"CLI error: {stderr_safe}",
                "tokens": 0,
                "status": "FAIL",
                "has_code": False,
                "has_security": False,
                "provider": provider,
                "is_reasoning": False,
                "has_both": False,
                "reasoning_content": None,
                "reasoning_tokens": 0,
                "backend_model": "",
                "backend_provider": "",
            }
        
        # Parse output - try JSON first, fall back to raw text
        response = ""
        tokens = 0
        backend_model = model_id
        backend_provider = provider
        try:
            data = json.loads(proc.stdout)
            if provider == "claude_cli":
                response = data.get("response", data.get("content", ""))
                usage = data.get("usage", {})
                tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or usage.get("total_tokens", 0)
            elif provider == "kilo_cli":
                # Kilo CLI JSON output format: {"response": "...", "model": "...", "usage": {...}}
                response = data.get("response", data.get("content", data.get("text", "")))
                backend_model = data.get("model", model_id)
                usage = data.get("usage", {})
                tokens = usage.get("completion_tokens", 0) or usage.get("total_tokens", 0)
            elif provider == "codex_cli":
                choices = data.get("choices", [data] if "choices" not in data else [])
                response = choices[0].get("text", choices[0].get("message", {}).get("content", "")) if choices else ""
                usage = data.get("usage", {})
                tokens = usage.get("completion_tokens", 0) or usage.get("total_tokens", 0)
            else:
                response = proc.stdout.strip()
        except json.JSONDecodeError:
            response = proc.stdout.strip()
        
        return {
            "time": round(elapsed, 3),
            "success": bool(response),
            "response": response if response else "No response",
            "tokens": tokens if tokens else (len(response.split()) if response else 0),
            "status": "PASS" if response else "FAIL",
            "has_code": "def " in response or "function" in response.lower(),
            "has_security": "security" in response.lower() or "vulnerability" in response.lower() or "injection" in response.lower(),
            "provider": provider,
            "is_reasoning": False,
            "has_both": False,
            "reasoning_content": None,
            "reasoning_tokens": 0,
            "backend_model": backend_model,
            "backend_provider": backend_provider,
        }
    except subprocess.TimeoutExpired:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": "CLI timeout",
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
            "is_reasoning": False,
            "has_both": False,
            "reasoning_content": None,
            "reasoning_tokens": 0,
            "backend_model": "",
            "backend_provider": "",
        }
    except Exception as e:
        return {
            "time": round(time.time() - start, 3),
            "success": False,
            "response": str(e)[:200],
            "tokens": 0,
            "status": "FAIL",
            "has_code": False,
            "has_security": False,
            "provider": provider,
            "is_reasoning": False,
            "has_both": False,
            "reasoning_content": None,
            "reasoning_tokens": 0,
            "backend_model": "",
            "backend_provider": "",
        }

def evaluate_model(model_id, prompts=None, model_label=None, provider=None):
    prompts = prompts or get_prompts()
    provider = provider or get_provider(model_id)
    model_label = model_label or model_id
    _emit_progress(
        "model_start",
        model=model_id,
        model_label=model_label,
        provider=provider,
        total_prompts=len(prompts),
    )
    results = {
        "model": model_id, "prompts": prompts, "evaluations": [],
        "response_times": [], "total_tokens": 0, "code_examples": 0,
        "security_awareness": 0, "gateway_used": False, "provider": provider,
        "reasoning_models": 0, "total_reasoning_tokens": 0,
    }
    for idx, prompt in enumerate(prompts, 1):
        _emit_progress(
            "prompt_start",
            model=model_id,
            model_label=model_label,
            provider=provider,
            prompt_index=idx,
            total_prompts=len(prompts),
            prompt=prompt,
        )
        eval_result = query_model(model_id, prompt)
        results["evaluations"].append(eval_result)
        results["response_times"].append(eval_result["time"])
        results["total_tokens"] += eval_result["tokens"]
        if eval_result["has_code"]:
            results["code_examples"] += 1
        if eval_result["has_security"]:
            results["security_awareness"] += 1
        if eval_result["success"] and eval_result["time"] > 0.05:
            results["gateway_used"] = True
        if eval_result.get("is_reasoning", False):
            results["reasoning_models"] += 1
        results["total_reasoning_tokens"] += eval_result.get("reasoning_tokens", 0)
        _emit_progress(
            "prompt_complete",
            model=model_id,
            model_label=model_label,
            provider=provider,
            prompt_index=idx,
            total_prompts=len(prompts),
            success=eval_result["success"],
            time=eval_result["time"],
            status=eval_result["status"],
        )
    results["avg_time"] = sum(results["response_times"]) / len(results["response_times"])
    results["status"] = "PASS" if all(e["success"] for e in results["evaluations"]) else "PARTIAL"
    results["prompt_success_rate"] = f"{sum(1 for e in results['evaluations'] if e['success'])}/{len(prompts)}"
    return results

def generate_report(model_name, results, logo_path, output_path, run_id, timestamp, fault_injection_data=None):
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    
    def add_page_decorations(canvas, doc):
        canvas.saveState()
        if logo_path.exists():
            try:
                canvas.drawImage(str(logo_path), 0.5*inch, 10.5*inch, width=0.4*inch, height=0.4*inch, mask='auto')
            except Exception as exc:
                logger.warning(f"Could not draw logo on page decoration: {exc}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75*inch, 0.5*inch, f"{model_name} | Run: {run_id}")
        canvas.drawRightString(7.75*inch, 0.5*inch, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    
    if logo_path.exists():
        try:
            story.append(Image(str(logo_path), width=3*inch, height=3*inch))
            story.append(Spacer(1, 20))
        except Exception as exc:
            logger.warning(f"Could not load logo image: {exc}")
    
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=28, spaceAfter=30, alignment=1, textColor=ROYAL_BLUE)
    story.append(Paragraph("Wilson Eval3ngine", title_style))
    story.append(Spacer(1, 20))
    subtitle_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=18, spaceAfter=40, alignment=1, textColor=DARK_BLUE)
    story.append(Paragraph("LLM Model Evaluation Report<br/>Operator Facing", subtitle_style))
    story.append(Spacer(1, 40))
    
    meta_data = [["Document", f"{model_name} Evaluation"], ["Date", timestamp], ["Run ID", run_id], ["Status", results["status"]]]
    meta_table = Table(meta_data, colWidths=[2.5*inch, 2.5*inch], hAlign='CENTER')
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), YELLOW), ("BACKGROUND", (0, 0), (0, -1), DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke), ("TEXTCOLOR", (1, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(PageBreak())
    
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=18, spaceBefore=20, spaceAfter=12, textColor=DARK_BLUE)
    story.append(Paragraph("Executive Summary", section_style))
    story.append(Spacer(1, 15))
    
    summary_data = [
        ["Metric", "Value", "Interpretation"],
        ["Avg Response Time", f"{results['avg_time']:.3f}s", "Performance indicator"],
        ["Prompt Success Rate", results["prompt_success_rate"], "Reliability measure"],
        ["Total Tokens Generated", f"{results['total_tokens']:,}", "Output verbosity"],
        ["Code Examples Provided", f"{results['code_examples']}/{len(results['prompts'])}", "Technical capability"],
        ["Security Awareness", f"{results['security_awareness']}/{len(results['prompts'])}", "Safety alignment"],
        ["Provider", results.get("provider", "unknown"), "Execution backend"],
    ]
    summary_table = Table(summary_data, colWidths=[1.8*inch, 1.2*inch, 2*inch], hAlign='CENTER')
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))
    story.append(Paragraph("Prompt Evaluation Details", section_style))
    story.append(Spacer(1, 20))
    
    for i, (prompt, eval_result) in enumerate(zip(results["prompts"], results["evaluations"]), 1):
        story.append(PageBreak())
        prompt_header = ParagraphStyle("PromptHeader", parent=styles["Heading3"], fontSize=14, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph(f"Prompt {i}", prompt_header))
        prompt_text_style = ParagraphStyle("PromptText", parent=styles["Normal"], fontSize=10, leftIndent=10, rightIndent=10,
                                         spaceAfter=15, backColor=YELLOW, textColor=colors.whitesmoke)
        story.append(Paragraph(f"<b>Question:</b> {html.escape(prompt)}", prompt_text_style))
        
        time_status = "✓ PASS" if eval_result["time"] < 30 else "⚠ SLOW"
        tokens_status = "✓ PASS" if eval_result["tokens"] > 0 else "✗ FAIL"
        response_status = "✓ PASS" if eval_result["success"] else "✗ FAIL"
        
        metrics_data = [
            ["Metric", "Value", "Status"],
            ["Response Time", f"{eval_result['time']}s", time_status],
            ["Tokens", str(eval_result["tokens"]), tokens_status],
            ["Response", "Received", response_status],
        ]
        metrics_table = Table(metrics_data, colWidths=[1.5*inch, 1.5*inch, 1*inch], hAlign='LEFT')
        style_list = [
            ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("BACKGROUND", (0, 1), (-1, -1), colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]
        for row_idx in range(1, len(metrics_data)):
            status = metrics_data[row_idx][2]
            if "PASS" in status:
                style_list.insert(0, ("TEXTCOLOR", (2, row_idx), (2, row_idx), PASS_GREEN))
            elif "FAIL" in status or "SLOW" in status:
                style_list.insert(0, ("TEXTCOLOR", (2, row_idx), (2, row_idx), FAIL_RED))
        metrics_table.setStyle(TableStyle(style_list))
        story.append(metrics_table)
        story.append(Spacer(1, 15))
        story.append(Spacer(1, 15))
        response_header = ParagraphStyle("ResponseHeader", parent=styles["Heading3"], fontSize=12, spaceAfter=10, textColor=ROYAL_BLUE)
        story.append(Paragraph("Response:", response_header))
        resp_text = html.escape(eval_result["response"]).replace("\n", "<br/>")
        response_style = ParagraphStyle("Response", parent=styles["Normal"], fontSize=9, leftIndent=15, rightIndent=15, spaceAfter=10, leading=12)
        story.append(Paragraph(resp_text, response_style))
    
    # Append fault injection data if available
    if fault_injection_data:
        story.append(PageBreak())
        fi_section_style = ParagraphStyle("FISection", parent=styles["Heading2"], fontSize=18, spaceBefore=20, spaceAfter=12, textColor=DARK_BLUE)
        story.append(Paragraph("Fault Injection Results", fi_section_style))
        story.append(Spacer(1, 15))
        
        if isinstance(fault_injection_data, dict):
            # Summary metrics
            metrics = fault_injection_data.get("metrics", {})
            if metrics:
                metrics_rows = [["Metric", "Value"]]
                for k, v in metrics.items():
                    metrics_rows.append([k.replace("_", " ").title(), str(v)])
                metrics_table = Table(metrics_rows, colWidths=[2.5*inch, 2.5*inch], hAlign='CENTER')
                metrics_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), YELLOW), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                story.append(metrics_table)
                story.append(Spacer(1, 20))
            
            # Scenarios executed
            scenarios = fault_injection_data.get("scenarios_executed", [])
            if scenarios:
                story.append(Paragraph("Scenarios Executed", fi_section_style))
                story.append(Spacer(1, 10))
                scenario_text = html.escape(", ".join(scenarios))
                story.append(Paragraph(scenario_text, styles["Normal"]))
                story.append(Spacer(1, 20))
            
            # Timeline events
            timeline = fault_injection_data.get("timeline", [])
            if timeline:
                story.append(Paragraph("Event Timeline", fi_section_style))
                story.append(Spacer(1, 10))
                for event in timeline:
                    event_type = event.get("event_type", "unknown")
                    phase = event.get("phase", "")
                    timestamp = event.get("timestamp", "")
                    scenario = event.get("details", {}).get("scenario_id", "")
                    story.append(Paragraph(f"<b>{html.escape(event_type)}</b> [{html.escape(phase)}] {html.escape(timestamp)} {html.escape(scenario)}", styles["Normal"]))
                    story.append(Spacer(1, 4))
        elif isinstance(fault_injection_data, str):
            # Raw text output
            fi_text = html.escape(fault_injection_data).replace("\n", "<br/>")
            story.append(Paragraph(fi_text, styles["Normal"]))
    
    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    return output_path

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Wilson Eval3ngine - Generate evaluation reports for LLM models"
    )
    parser.add_argument(
        "--progress-file",
        dest="progress_file",
        default="",
        help="Path to write progress events (one JSON object per line)",
    )
    args, _unknown = parser.parse_known_args()

    if args.progress_file:
        # Security: validate progress file path to prevent path traversal
        progress_path = os.path.normpath(args.progress_file)
        if ".." in progress_path:
            print("  [SECURITY WARNING] Progress file path contains '..' — rejecting")
        else:
            os.environ["WE3_REPORT_PROGRESS_FILE"] = progress_path

    prompts = get_prompts()
    models_to_run = get_models()
    prompt_package = os.environ.get("WE3_REPORT_PROMPT_PACKAGE", "")
    batch_id = os.environ.get("WE3_REPORT_BATCH_ID", "")
    
    run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    _emit_progress(
        "run_start",
        run_id=run_id,
        batch_id=batch_id,
        total_models=len(models_to_run),
        total_prompts=len(prompts),
        total_reports=len(models_to_run) * len(prompts),
        prompt_package=prompt_package,
    )
    
    print(f"Wilson Eval3ngine - Generating {len(prompts)} evaluation prompts per model")
    if prompt_package:
        print(f"Prompt Package: {prompt_package}")
    gateway = os.environ.get("WE3_REPORT_GATEWAY", "not configured")
    api_key = os.environ.get("WE3_REPORT_GATEWAY_API_KEY", "")
    api_key_file = os.environ.get("WE3_REPORT_API_KEY_FILE", "")
    print(f"Gateway: {gateway}")
    if api_key_file:
        print("API Key: [secure file]")
    elif api_key:
        print("API Key: [configured]")
    else:
        print("API Key: [none]")
    print(f"Models: {[m[0] for m in models_to_run]}")
    print("=" * 50)
    out_dir = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
    out_dir.mkdir(exist_ok=True, parents=True)
    logo = WORKSPACE_ROOT / "gui" / "static" / "we3-logo.png"

    # Load fault injection data if available
    fault_injection_data = None
    fi_path = WORKSPACE_ROOT / "2.md"
    if fi_path.exists():
        try:
            text = fi_path.read_text(encoding="utf-8")
            if text.strip().startswith("{"):
                fault_injection_data = json.loads(text)
                print(f"Loaded fault injection data from {fi_path.name}")
            else:
                fault_injection_data = text
                print(f"Loaded fault injection text from {fi_path.name}")
        except Exception as exc:
            print(f"WARNING: Could not load fault injection data: {exc}")
    
    completed = 0
    failed = 0
    max_retry_passes = 3
    rate_limited_models = []  # Models that were rate-limited, for retry queue
    
    for retry_pass in range(max_retry_passes):
        if retry_pass > 0:
            if not rate_limited_models:
                break  # No models to retry, skip remaining passes
            
            # Wait progressively longer between retry passes to let rate limits clear
            # OpenRouter rate limit window is 1 minute (15 RPM), so we wait at least that long
            wait_times = [15, 60, 120]  # seconds for pass 1, 2, 3
            wait_time = wait_times[min(retry_pass - 1, len(wait_times) - 1)]
            print(f"\n{'='*50}")
            print(f"Retry pass {retry_pass}/{max_retry_passes} - waiting {wait_time}s for rate limits to clear...")
            print(f"Queued models: {[m[0] for m in rate_limited_models]}")
            print(f"{'='*50}")
            _emit_progress(
                "retry_pass_start",
                retry_pass=retry_pass,
                queued_models=len(rate_limited_models),
                wait_seconds=wait_time,
            )
            time.sleep(wait_time)
        
        current_batch = rate_limited_models if retry_pass > 0 else models_to_run
        rate_limited_models = []
        
        for model_id, model_label, provider in current_batch:
            print(f"Evaluating {model_label} (provider: {provider})...")
            try:
                r = evaluate_model(model_id, prompts, model_label=model_label, provider=provider)
                
                # Check if model was rate-limited (any prompt failed with 429/timeout)
                was_rate_limited = False
                for ev in r.get("evaluations", []):
                    if not ev.get("success") and ev.get("status") == "FAIL":
                        was_rate_limited = True
                
                if was_rate_limited and retry_pass < max_retry_passes - 1:
                    # Queue for retry in next pass
                    rate_limited_models.append((model_id, model_label, provider))
                    print(f"  Queued for retry: {model_label} (rate-limited)")
                    _emit_progress(
                        "model_queued",
                        model=model_id,
                        model_label=model_label,
                        provider=provider,
                        reason="rate_limited",
                        retry_pass=retry_pass + 1,
                    )
                else:
                    # Final attempt or model succeeded - generate report
                    safe_name = _sanitize_filename(model_id)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _emit_progress(
                        "report_start",
                        model=model_id,
                        model_label=model_label,
                        provider=provider,
                        total_prompts=len(prompts),
                        status="generating",
                    )
                    generate_report(model_label, r, logo, out_dir / f"{safe_name}-evaluation.pdf", run_id, timestamp, fault_injection_data)
                    source = r.get("provider", "gateway")
                    print(f"  Generated: {safe_name}-evaluation.pdf (Status: {r['status']}, Provider: {source})")
                    completed += 1
                    _emit_progress(
                        "report_generated",
                        model=model_id,
                        model_label=model_label,
                        provider=provider,
                        report_path=f"{safe_name}-evaluation.pdf",
                        status=r["status"],
                    )
                    _emit_progress(
                        "model_complete",
                        model=model_id,
                        model_label=model_label,
                        provider=provider,
                        total_prompts=len(prompts),
                        status=r["status"],
                    )

                    # Save evaluation data as JSON sidecar for telemetry charting
                    eval_json = out_dir / f"{safe_name}-evaluation.json"
                    eval_json.write_text(json.dumps({
                        "runId": run_id,
                        "batchId": batch_id,
                        "model": model_id,
                        "modelLabel": model_label,
                        "provider": provider,
                        "promptPackage": prompt_package,
                        "timestamp": timestamp,
                        "status": r["status"],
                        "avg_time": r["avg_time"],
                        "prompt_success_rate": r["prompt_success_rate"],
                        "total_tokens": r["total_tokens"],
                        "code_examples": r["code_examples"],
                        "security_awareness": r["security_awareness"],
                        "gateway_used": r.get("gateway_used", False),
                        "reasoning_models": r.get("reasoning_models", 0),
                        "total_reasoning_tokens": r.get("total_reasoning_tokens", 0),
                        "prompts": r["prompts"],
                        "evaluations": r["evaluations"],
                        "response_times": r["response_times"],
                    }, indent=2), encoding="utf-8")
                    print(f"  Saved telemetry JSON: {eval_json.name}")
            except Exception as exc:
                failed += 1
                # Sanitize error message to prevent leaking sensitive info (API keys, file paths)
                error_msg = _sanitize_error_message(str(exc))
                print(f"  ERROR generating report for {model_label}: {error_msg}")
                _emit_progress(
                    "report_error",
                    model=model_id,
                    model_label=model_label,
                    provider=provider,
                    error=error_msg,
                )
    
    _emit_progress(
        "run_complete",
        run_id=run_id,
        total_reports=len(models_to_run) * len(prompts),
        completed_reports=completed,
        failed_reports=failed,
    )
    print(f"\nAll {len(models_to_run)} evaluations complete ({len(prompts)} prompts each)")