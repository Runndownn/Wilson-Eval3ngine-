# ANCHORED SUMMARY

## Project Origin

Wilson-Eval3ngine was conceived on July 14, 2026 through a collaborative session where **The Repo Operator Arty (Runndownn)** challenged the Geezer Mekanix Agentic Engineering Platform to demonstrate its full capabilities—proving that free models can deliver exceptional coding quality and speed, dismissing the notion of "AI slop." Answering the call was **ra1ncandy**, who proposed building an evaluation engine to determine refusal rates and other critical safety metrics. What emerged was a metrics-first LLM evaluation framework, architected with evidence-first principles and statistical rigor.

The framework was built using **BinReaper x0.0.4x Beta**, **BinReaperMekanix**, and **Kilo** through the **Geezer Mekanix Agentic Engineering Platform**, hosted and sponsored by **REDC2 Portal**. Initial coding work was completed using **Laguna M.1 (free)**, with current edits being made using **Laguna S2.1 (free)**. Planning was done using **BinReaper x0.0.4x Beta GPT 5.6 Sol Extended Thinking** and **Pro Version**. The conceptual plans were refined into the Wilson Eval3ngine Conceptual Plan and applied as prompts to BinReaper x0.0.4x Beta GPT 5.6 Sol Pro to create the framework. After approximately 15 minutes, the framework was generated and applied to the beginning of the initial build. While the use of GPT 5.6 Sol Pro was not strictly required to obtain the results, it helped to jump-start and enhance the process. Beyond a few plan generations, these models have been used minimally throughout the project.

## Goal

Implement the highest-quality observability enhancement for Wilson Eval3ngine: a comprehensive distributed tracing instrumentation layer that bridges the lightweight tracer to the OpenTelemetry SDK, instruments the evaluation pipeline end-to-end, adds tracing to the database layer, and integrates tracing into API endpoints. Additionally, harden API key security across the full transaction lifecycle.

## Constraints & Preferences

- Security-first: never record prompt/response bodies, secrets, or credentials in spans
- All span attributes validated against allowlist (ALLOWED_SPAN_ATTRIBUTES)
- No external dependencies required (graceful degradation when OTel SDK not installed)
- Backward compatible: tracing can be disabled via config
- No changes to core evaluation logic
- API keys must never be stored in plaintext, never exposed in API responses, never passed via environment variables to subprocesses, never logged in telemetry
- Fernet TTL removed for at-rest decryption (keys persist across server restarts)

## Progress

### 1. OpenTelemetry SDK Adapter Module (COMPLETED)

- **File**: `src/wilson_eval3ngine/observability/instrumentation.py` (966 lines)
- **What**: Bridges the lightweight tracer in `tracing.py` to the real OpenTelemetry SDK when available
- **Key components**:
  - `OTELConfig`: Configuration with environment variable parsing
  - `setup_opentelemetry()`: Idempotent OTel SDK initialization with OTLP export, W3C TraceContext propagation
  - `is_opentelemetry_available()`: SDK detection with caching
  - `shutdown_opentelemetry()`: Graceful shutdown with span flushing
  - `DualTracer`: Tracer that emits spans to both lightweight tracer and OTel SDK
  - `DualSpan`: Span that records to both systems with security validation
- **Security**: Same attribute allowlist as lightweight tracer; W3C TraceContext propagation for distributed tracing

### 2. Evaluation Pipeline Instrumentation (COMPLETED)

- **File**: `src/wilson_eval3ngine/application/service.py`
- **What**: Added tracing spans at each pipeline stage in `EvaluationService.run_manifest()`
- **Stages instrumented**:
  - `manifest_load`: Load experiment and dataset manifests
  - `experiment_create`: Create experiment record in database
  - `artifact_store`: Store manifest and dataset artifacts
  - `case_iteration`: Iterate over test cases
  - `prompt_render`: Render prompt for each case
  - `provider_execute`: Execute provider request
  - `grading`: Grade response against expectation
  - `metric_compute`: Compute metrics for each model
  - `gate_evaluate`: Evaluate gates against thresholds
  - `dossier_build`: Build signed dossier
  - `result_index_write`: Write result index
  - `audit_verify`: Verify audit chain
- **Metrics recorded**: Operation counts, durations, gate statuses, classification labels
- **Security**: No prompt/response content recorded; only identifiers and status

### 3. Tracing-Aware Database Session (COMPLETED)

- **File**: `src/wilson_eval3ngine/observability/instrumentation.py`
- **What**: `TracingDatabaseSession` wrapper that records query spans
- **Features**:
  - Wraps SQLAlchemy Session operations (execute, commit, rollback, add, get, query)
  - Extracts SQL operation type (SELECT, INSERT, UPDATE, DELETE, etc.)
  - Extracts table name from queries
  - Records `db.system`, `db.operation`, `db.statement` attributes
  - Never records parameter values or query results
  - Context manager support

### 4. API Endpoint Tracing Integration (COMPLETED)

- **Files**: `src/wilson_eval3ngine/api/main.py`, `src/wilson_eval3ngine/api/operations.py`
- **What**: Replaced `new_id("trc")` with `get_trace_id()` in all API endpoints
- **Endpoints updated**:
  - `/v1/experiments:validate`
  - `/v1/experiments:run`
  - `/v1/operations/{operation_id}`
  - `/v1/experiments/{experiment_id}`
  - `/v1/experiments/{experiment_id}:start`
  - `/v1/experiments/{experiment_id}:pause`
  - `/v1/experiments/{experiment_id}:resume`
  - `/v1/experiments/{experiment_id}:cancel`
  - `/v1/experiments/{experiment_id}:regrade`
  - `/v1/experiments/{experiment_id}/runs`
  - `/v1/metrics`
  - `/v1/dossiers:generate`
- **Benefit**: API responses now include the actual trace ID from the active span, enabling end-to-end trace correlation

### 5. Comprehensive Observability Tests (COMPLETED)

- **File**: `tests/unit/test_observability_instrumentation.py`
- **74 tests** covering:
  - OTELConfig configuration and environment variables
  - OpenTelemetry SDK detection and setup
  - DualTracer span creation, context management, hierarchy, exceptions
  - DualSpan attribute validation and security (prohibited keys, long values, secret patterns)
  - PipelineInstrumentor stage context manager and metrics recording
  - TracingDatabaseSession execute, commit, rollback, add, get, query, context manager
  - SQL operation type and table name extraction
  - EvaluationPipelineInstrumentor end-to-end tracing
  - get_trace_id and trace context propagation
  - Global instrumentor management
  - Security tests (prompt content rejection, secret value rejection, long value rejection)
  - Integration tests (full pipeline, database workflow, end-to-end)

### 6. API Key Security Hardening (COMPLETED)

- **Files**: `src/wilson_eval3ngine/gui/api_key_vault.py` (544 lines), `src/wilson_eval3ngine/gui/server.py`
- **What**: Comprehensive security hardening of API key handling across the full transaction lifecycle
- **Security architecture**: Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) with PBKDF2-HMAC-SHA256 key derivation (260k iterations), unique salt per key, master key stored with 0600 permissions at `~/.we3/secret_key`
- **Process isolation**: API keys passed to subprocesses via secure temp files (0600 permissions), never environment variables; temp files securely destroyed (overwritten + unlinked) in all code paths
- **Defense in depth**: Response sanitization, telemetry sanitization, audit logging, memory zeroing, backward-compatible migration

**Vulnerabilities fixed:**

1. **Plaintext storage at rest → Encrypted at rest**
   - Added `encrypt_api_key()` and `decrypt_api_key()` functions using Fernet (AES-128-CBC + HMAC-SHA256) with PBKDF2 key derivation (260k iterations)
   - All endpoint creation paths now encrypt API keys before writing to `endpoints.json`
   - Added `_migrate_legacy_api_keys()` that runs on server startup to convert existing plaintext keys
   - **Fernet TTL fix**: Removed 1-hour TTL from `decrypt_api_key()` for at-rest decryption, ensuring keys persist across server restarts

2. **API keys exposed via GET `/api/endpoints` → Stripped from all responses**
   - Added `_sanitize_endpoint()` that removes `apiKey`, `encryptedApiKey`, and `keyFile` fields
   - `list_endpoints()` now returns sanitized endpoints
   - `create_endpoint()` response also sanitized
   - WebSocket `list_endpoints` action also sanitized

3. **Subprocess env var leakage → Secure temp files**
   - WebSocket `_run_report_generation()` flow now uses `store_api_key_temp_file()` (0600 permissions) instead of `env["WE3_REPORT_GATEWAY_API_KEY"]`
   - Temp file securely destroyed (overwritten + unlinked) after subprocess completes in all code paths (success, timeout, exception, cancellation)
   - `SecureKeyFile.destroy()` zeros memory and overwrites file before deletion

4. **Telemetry leakage → Sanitized output**
   - Added `sanitize_output()` function that redacts `sk-` patterns, Bearer tokens, JSON `apiKey` fields, and Authorization headers
   - All stdout/stderr stored in telemetry entries is now sanitized
   - Applied to both synchronous and WebSocket report generation flows

5. **Git hygiene**
   - Added `.gitignore` entries for `gui/data/models.json`, `gui/data/prompt_packages.json`, `.we3/secret_key`, `.we3/audit.log`
   - Untracked `models.json` from git

6. **API key masking for logs**
   - Added `mask_api_key()` function for safe logging (shows first/last 4 chars only)
   - Used in WebSocket report generation logging

7. **Audit logging**
   - Added `_audit_log()` function that writes to `~/.we3/audit.log`
   - Logs all key operations (creation, decryption, migration, storage, destruction)
   - Never logs actual key values

### 7. GUI Screenshot Documentation (COMPLETED)

- **File**: `README.md`
- **What**: Incorporated 6 GUI screenshots into the README with detailed descriptions
- **Screenshots**:
  1. Endpoints Tab — gateway management hub showing registered providers with connectivity status
  2. Models Tab — discovered models organized by endpoint and provider type
  3. Generate Reports Tab — progress dashboard during active report generation run
  4. Reports Tab — responsive grid of generated evaluation report cards
  5. PDF Viewer — in-browser PDF viewer with page navigation and zoom controls
  6. Prompt Package Selection — dropdown for selecting evaluation prompt packages

### 8. Progress Calculation Fix (COMPLETED)

- **File**: `src/wilson_eval3ngine/gui/server.py`
- **What**: Fixed progress calculation bug in WebSocket report generation flow
- **Issue**: `total_reports` was set to number of models instead of `models × prompts`, causing percentage to hit 100% after first model completed
- **Fix**: `total_reports` now correctly set to `len(models) * max(1, len(prompts))` in `_create_job()`

### 9. Retry Queue Mechanism (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: Implemented multi-pass retry queue for rate-limited models
- **Features**:
  - 3 retry passes with progressive waits (15s, 60s, 120s)
  - Rate-limited models queued for retry in subsequent passes
  - Progress events emitted for each retry pass
  - 2 quick retries per model before deferral to queue

### 10. GUI Server Security Tests (COMPLETED)

- **File**: `tests/unit/test_gui_server.py`
- **14 new tests** covering:
  - API key encryption at rest (endpoints.json doesn't contain plaintext)
  - API key stripping from GET/POST endpoint responses
  - Legacy plaintext key stripping from responses
  - Kilo login encrypting API key at rest
  - `sanitize_output()` redacting sk- patterns, Bearer tokens, JSON apiKey fields
  - `mask_api_key()` properly masking keys
  - `encrypt_api_key()`/`decrypt_api_key()` roundtrip verification
  - Empty/None input handling for encrypt/decrypt

## Key Decisions

1. **Package integration**: Integrated instrumentation into existing `observability` package (not a new module) to avoid naming conflicts
2. **Dual tracer pattern**: Spans emitted to both lightweight tracer and OTel SDK for backward compatibility
3. **No external dependencies**: OTel SDK is optional; system works without it
4. **Security allowlist**: All span attributes validated against `ALLOWED_SPAN_ATTRIBUTES` from `tracing.py`
5. **Non-invasive instrumentation**: Tracing added as context managers around existing logic, no changes to core evaluation logic
6. **Encrypted at rest**: API keys encrypted with Fernet before storage in any JSON file
7. **Temp file IPC**: API keys passed to subprocesses via secure temp files (0600 permissions), never environment variables
8. **Response sanitization**: All API responses strip sensitive fields before returning to clients
9. **Telemetry sanitization**: stdout/stderr from subprocesses sanitized to redact any leaked credentials

## Test Results

- **Unit tests**: 99 total (74 observability + 25 GUI server), all passing
- **No regressions**: All tests pass
- **Security validation**: Verified encrypt/decrypt roundtrip, sanitize_output redaction, mask_api_key, empty/None handling
- **GUI server tests**: 46/46 passing (including previously-failing `test_allows_gateway`)

## Files Modified

- `src/wilson_eval3ngine/observability/__init__.py` - Added instrumentation exports
- `src/wilson_eval3ngine/observability/instrumentation.py` - New file (966 lines)
- `src/wilson_eval3ngine/application/service.py` - Added tracing spans and metrics
- `src/wilson_eval3ngine/api/main.py` - Replaced `new_id("trc")` with `get_trace_id()`
- `src/wilson_eval3ngine/api/operations.py` - Replaced `new_id("trc")` with `get_trace_id()`
- `src/wilson_eval3ngine/gui/api_key_vault.py` - Added encrypt/decrypt/sanitize functions
- `src/wilson_eval3ngine/gui/server.py` - Encrypted storage, response stripping, temp file IPC, telemetry sanitization, migration, progress fix, event handler additions, localhost endpoint fix
- `scripts/generate_5_reports.py` - Fixed PROGRESS_FILE race condition, token extraction, response truncation, CLI provider tokens, mock warning, argparse
- `gui/static/app.js` - Fixed progress bar bouncing, implemented live elapsed-time timer
- `.gitignore` - Added sensitive runtime files
- `README.md` - Incorporated 6 GUI screenshots with detailed descriptions, updated Agentic Engineering Origin
- `docs/framework_status.md` - Updated observability and DR status
- `ANCHORED_SUMMARY.md` - Rewritten with complete project history
- `tests/unit/test_gui_server.py` - 14 new security tests

## Files Created

- `src/wilson_eval3ngine/observability/instrumentation.py` (966 lines)
- `src/wilson_eval3ngine/gui/api_key_vault.py` (544 lines)
- `tests/unit/test_observability_instrumentation.py` (74 tests)
- `static/images/gui-screenshots/1.png` through `6.png` (GUI screenshots)

## Next Steps

- Add OpenTelemetry SDK as optional dependency in `pyproject.toml`
- Add OTel SDK integration tests with mock SDK
- Add tracing to the grading pipeline and metrics engine
- Add tracing to the provider adapter execution
- Add distributed tracing to the backup/reconciliation system
- Add trace-based alerting rules to the observability package

---

## Session: 2026-07-30 — Progress Bar & Event Handler Fixes

### 11. Fixed `PROGRESS_FILE` Race Condition in `generate_5_reports.py` (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: The module-level constant `PROGRESS_FILE = os.environ.get("WE3_REPORT_PROGRESS_FILE", "")` was evaluated at **import time**, but the `--progress-file` CLI argument was parsed in the `__main__` block **after** import. This meant `PROGRESS_FILE` was always empty, and `_emit_progress()` never wrote any events to the progress file — the WebSocket progress tailing in the GUI received zero events.
- **Fix**: Replaced the module-level constant with a `_get_progress_file()` function that reads the env var dynamically at call time. Updated `_emit_progress()` to call `_get_progress_file()` instead of referencing the stale constant. Also replaced fragile `sys.argv` parsing with `argparse` for robust `--progress-file` handling.

### 12. Fixed Token Extraction in `query_model` (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: Token count was extracted via `data.get("eval_count", 0)`, which is an Ollama-specific field that doesn't exist in OpenAI-compatible responses. The `parse_response()` function already correctly extracted `completion_tokens` and `total_tokens`, but the fallback ignored the parsed values.
- **Fix**: Token extraction now uses `parsed.completion_tokens or parsed.total_tokens` with a proper fallback chain to `data.get("usage", {}).get("total_tokens", 0)`.

### 13. Fixed Response Truncation in `query_model` and `query_model_cli` (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: Response text was truncated to 2000 characters (`response[:2000]`) in both `query_model` and `query_model_cli`, potentially losing important evaluation content.
- **Fix**: Removed the `[:2000]` truncation; full response text is now preserved.

### 14. Fixed CLI Provider Token Extraction (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: The `query_model_cli` function only extracted tokens for `kilo_cli` (using `completion_tokens`/`total_tokens`). `claude_cli` and `codex_cli` had no token extraction at all.
- **Fix**: Added token extraction for `claude_cli` (using `output_tokens`/`completion_tokens`/`total_tokens` from the usage dict) and `codex_cli` (using `completion_tokens`/`total_tokens`).

### 15. Added Mock Response Warning (COMPLETED)

- **File**: `scripts/generate_5_reports.py`
- **What**: When the gateway is unavailable after all retries, the script falls back to mock responses silently. This could mislead users into thinking real model evaluations occurred.
- **Fix**: Added a `logger.warning()` and `print()` warning when mock responses are used as a fallback, clearly indicating the gateway was unavailable.

### 16. Fixed Progress Bar Bouncing in `app.js` (COMPLETED)

- **File**: `gui/static/app.js`
- **What**: `showProgressDashboard()` reset `maxOverallPercentage = 0`, `modelPercentageCache = {}`, and other monotonic state every time it was called. It was called from three places: `generate_reports` started, `job_created`, and `get_job` (restore). When restoring a job via `get_job`, the state reset caused the progress bar to jump backward to 0%, then climb again — the "bouncing" effect.
- **Fix**: Split the function into `showProgressDashboard(resetState=true)` (shows the dashboard, optionally starts the timer) and `resetProgressState()` (resets all progress state). The `get_job` restore handler now calls `showProgressDashboard(false)` to preserve existing progress state.

### 17. Implemented Live Elapsed-Time Timer in `app.js` (COMPLETED)

- **File**: `gui/static/app.js`
- **What**: The `overallTimerInterval` variable was declared and cleaned up but never actually set — no `setInterval` call assigned to it. Elapsed time only updated when WebSocket events arrived, causing the timer to freeze if events were delayed.
- **Fix**: `showProgressDashboard()` now starts a 1-second interval timer that increments the elapsed display live. The timer reads/writes `data-last-seconds` and `data-paused` attributes on the elapsed element. `cleanupProgressTimers()` clears it as before.

### 18. Added Missing Event Handlers in `server.py` (COMPLETED)

- **File**: `src/wilson_eval3ngine/gui/server.py`
- **What**: The `_update_job_from_event()` function in the WebSocket progress handler was missing handlers for four event types emitted by `generate_5_reports.py`: `rate_limit_retry`, `rate_limited_queued`, `model_queued`, and `retry_pass_start`. These events were silently dropped, causing the progress dashboard to not reflect rate-limit retries or queued models.
- **Fix**: Added handlers for all four event types that update `models_state` status/current_step and the job's `current_step` accordingly.

### 19. Fixed `_is_localhost_endpoint` Private IP Blocking in `server.py` (COMPLETED)

- **File**: `src/wilson_eval3ngine/gui/server.py`
- **What**: The `_is_localhost_endpoint()` function blocked all private IP ranges (`10.x.x.x`, `172.x.x.x`, `192.168.x.x`) in addition to loopback. This caused the pre-existing test `test_allows_gateway` to fail — `http://10.133.7.211:11434` (a legitimate gateway on a private network) was incorrectly classified as localhost.
- **Fix**: Removed blocking of private IP ranges. The function now only blocks loopback (`127.x.x.x`), localhost hostnames, link-local (`169.254.x.x` — includes cloud metadata endpoints), and TEST-NET ranges. SSRF protection for private IPs is already handled separately by `_validate_gateway_url()` in `generate_5_reports.py` with a `WE3_REPORT_ALLOW_LOCAL` opt-in flag.

### Test Results

- **GUI server tests**: 46/46 passing (including the previously-failing `test_allows_gateway`)
- **Syntax checks**: All modified files pass (`py_compile` for Python, `node --check` for JavaScript)

