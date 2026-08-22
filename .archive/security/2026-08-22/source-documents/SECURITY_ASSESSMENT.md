# Security Assessment Report — Wilson Eval3ngine v0.1.0

**Date:** 2026-07-30  
**Assessor:** Automated security review  
**Scope:** Full source tree (`src/wilson_eval3ngine/`, `tests/`, `infrastructure/`, `Dockerfile.prod`, `docker-compose.prod.yml`)

---

## 1. Executive Summary

The Wilson Eval3ngine foundation has a strong security foundation with OIDC authentication,
row-level security (RLS), encrypted object storage, audit logging, provider allowlists,
egress controls, and attachment quarantine. However, several **critical gaps** exist
in production-readiness:

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | JWT token replay protection missing (no `jti` claim validation, no revocation list) | **High** | Open |
| 2 | Rate limiting is in-memory only — fails under multi-instance deployments | **High** | Open |
| 3 | No CSRF protection on state-changing API endpoints | **High** | Open |
| 4 | Sensitive error details leak to clients (`str(exc)[:500]`) | **Medium** | Open |
| 5 | Committed secret: `.secrets/fernet.key` in repository | **Medium** | Open |
| 6 | Missing security headers: COOP, CORP, Cross-Origin-Opener-Policy | **Medium** | Open |
| 7 | No CORS policy enforcement | **Medium** | Open |
| 8 | Audit trail not persisted to database in API layer (only structured logs) | **Medium** | Open |
| 9 | No content-type validation on request bodies | **Low** | Open |
| 10 | Idempotency key format not validated | **Low** | Open |
| 11 | HSTS header missing `preload` directive | **Low** | Open |
| 12 | No automated dependency vulnerability scanning in CI | **Low** | Open |

---

## 2. Existing Security Controls (Strengths)

### 2.1 Authentication & Authorization
- ✅ OIDC JWT validation with JWKS caching and key rotation support
- ✅ MFA claim validation (amr claim checking)
- ✅ Role-based access control matrix with 14 roles (7 human + 7 workload)
- ✅ Project-scoped authorization with `validate_project_scope`
- ✅ Export-specific authorization (`check_export_authorization`, `check_raw_evidence_authorization`)
- ✅ Workload identity isolation with narrow scopes

### 2.2 Data Protection
- ✅ AES-256-GCM envelope encryption for artifact storage
- ✅ Content-addressed immutable storage (SHA-256)
- ✅ Local KMS client for development, pluggable for production KMS
- ✅ Retention policies with legal hold support (90d–100y)
- ✅ Project-scoped artifact paths with regex validation
- ✅ Path traversal prevention in artifact store

### 2.3 Database Security
- ✅ PostgreSQL Row-Level Security (RLS) policies on 14 tables
- ✅ Fail-closed project context binding with verification
- ✅ Session variable-based isolation (`we3.current_project_id`, `we3.is_system_admin`)
- ✅ Database role assertion (blocks migration/admin role usage)
- ✅ Hash-linked append-only audit ledger

### 2.4 API Security
- ✅ Security headers middleware (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
- ✅ Rate limiting (in-memory sliding window)
- ✅ Request body size limits (10 MB default)
- ✅ Structured logging with correlation IDs
- ✅ IP anonymization in logs
- ✅ Idempotency key support for duplicate prevention
- ✅ ETag-based conditional requests for state changes

### 2.5 Supply Chain & Runtime
- ✅ Provider/model allowlist with exact version identifiers
- ✅ Egress control (metadata endpoint blocking, private network blocking)
- ✅ Attachment quarantine with MIME type detection and content scanning
- ✅ Parser sandbox with resource limits and path traversal detection
- ✅ SAST scanning for command injection and other patterns
- ✅ Telemetry redaction with field allowlists
- ✅ Non-root container user (UID 10001)
- ✅ Read-only root filesystem in containers

### 2.6 Evidence Integrity
- ✅ Ed25519 signing for audit checkpoints
- ✅ Trust registry for key fingerprint management
- ✅ Key inventory with rotation support
- ✅ Dossier signing and verification

---

## 3. Detailed Findings

### Finding 1: JWT Token Replay Protection Missing (High)

**Location:** `src/wilson_eval3ngine/security/oidc.py`

**Description:** The `JWKSClient.verify_token()` method validates issuer, audience, signature,
and required claims (project_id, role, amr/MFA), but does **not** validate the `jti`
(JWT ID) claim. There is no token revocation list or replay detection. A captured token
can be replayed indefinitely until natural expiry.

**Risk:** Token replay attacks allow unauthorized access if a token is intercepted.

**Recommendation:** Implement `jti` claim validation with a Redis-backed or database-backed
revocation list. Add `exp`/`nbf` claim validation (currently delegated to `jose.decode`
but not explicitly checked).

---

### Finding 2: In-Memory Rate Limiting (High)

**Location:** `src/wilson_eval3ngine/api/middleware.py` — `RateLimitMiddleware`

**Description:** Rate limiting uses an in-memory `defaultdict` with no distributed state.
The `docker-compose.prod.yml` includes a Redis service, but the middleware does not
connect to it. Under multi-instance deployment, each instance has its own rate limit
state, allowing clients to bypass limits by round-robining requests.

**Risk:** Rate limiting bypass leads to DoS, brute-force attacks, and resource exhaustion.

**Recommendation:** Implement a Redis-backed rate limiter using atomic Lua scripts for
sliding-window counters. Fall back to in-memory mode only when Redis is unavailable.

---

### Finding 3: No CSRF Protection (High)

**Location:** `src/wilson_eval3ngine/api/` — all POST/PUT/DELETE endpoints

**Description:** The API uses header-based authentication (`X-WE3-Project-ID`,
`X-WE3-Role` in dev mode; `Authorization: Bearer` in OIDC mode). However, there is no
CSRF token mechanism. If the API is ever consumed by a browser-based client using
cookie-based authentication, CSRF attacks would be possible.

**Risk:** Cross-site request forgery on state-changing operations.

**Recommendation:** Implement double-submit CSRF token pattern. Generate a CSRF token
on authentication, require it as `X-CSRF-Token` header for all state-changing requests.

---

### Finding 4: Error Information Leakage (Medium)

**Location:** `src/wilson_eval3ngine/api/main.py` — `execute_operation()` function, line 287

**Description:** The error handler includes `str(exc)[:500]` in the operation update,
which could leak internal file paths, database schema details, or stack trace fragments
to clients querying operation status.

**Risk:** Information disclosure that aids attackers in understanding system internals.

**Recommendation:** Sanitize all error details before storing. Use only error codes
and safe, pre-defined messages. Log full details server-side only.

---

### Finding 5: Committed Secret File (Medium)

**Location:** `.secrets/fernet.key`

**Description:** A Fernet key file is present in the repository. While it may be a
development key, committed secrets are a security risk. The `.gitignore` should exclude
the `.secrets/` directory.

**Risk:** Credential compromise if the key is used in production.

**Recommendation:** Remove from repository, add to `.gitignore`, implement proper
secrets management via environment variables or a secrets manager.

---

### Finding 6: Missing Security Headers (Medium)

**Location:** `src/wilson_eval3ngine/api/middleware.py` — `SECURITY_HEADERS`

**Description:** The following critical security headers are missing:
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- `Cross-Origin-Embedder-Policy: require-corp`

**Risk:** Cross-origin attacks, Spectre-style side-channel attacks, data exfiltration.

**Recommendation:** Add COOP, CORP, and COEP headers to the security headers middleware.

---

### Finding 7: No CORS Policy (Medium)

**Location:** `src/wilson_eval3ngine/api/main.py`

**Description:** No CORS middleware is configured. If the API is accessed from browsers,
any origin can make requests. In production, only approved origins should be allowed.

**Risk:** Cross-origin data theft, unauthorized API access from malicious websites.

**Recommendation:** Add CORS middleware with explicit allowlist of origins, methods,
and headers. Reject all cross-origin requests by default.

---

### Finding 8: Audit Trail Not Persisted in API Layer (Medium)

**Location:** `src/wilson_eval3ngine/api/main.py`

**Description:** The API layer writes audit events to structured logs but does not
persist them to the `audit_events` database table. The `AuditLedger` class exists but
is only used in the synchronous `EvaluationService`, not in the API endpoints.

**Risk:** Audit trails can be lost on log rotation, tampered with, or unavailable
for forensic analysis.

**Recommendation:** Integrate `AuditLedger` into API endpoints. Persist all
authorization decisions, operation state changes, and data access events.

---

### Finding 9: No Content-Type Validation (Low)

**Location:** `src/wilson_eval3ngine/api/main.py`

**Description:** API endpoints accept any content type. There is no validation that
request bodies are `application/json` or that the content type matches the expected
schema.

**Risk:** Content-type confusion attacks, parser confusion.

**Recommendation:** Add content-type validation middleware that rejects requests
with unexpected content types for POST/PUT endpoints.

---

### Finding 10: Idempotency Key Format Not Validated (Low)

**Location:** `src/wilson_eval3ngine/api/main.py` — `run_experiment()`

**Description:** The `Idempotency-Key` header is accepted without validation.
Malformed or excessively long keys could cause issues.

**Risk:** Resource exhaustion, key collision attacks.

**Recommendation:** Validate idempotency key format (alphanumeric, max 128 chars).

---

### Finding 11: HSTS Missing Preload Directive (Low)

**Location:** `src/wilson_eval3ngine/api/middleware.py` — `SECURITY_HEADERS`

**Description:** The HSTS header is `max-age=31536000; includeSubDomains` but lacks
the `preload` directive, which enables inclusion in browser HSTS preload lists.

**Recommendation:** Add `preload` to the HSTS header.

---

### Finding 12: No Automated Dependency Scanning (Low)

**Location:** `.github/workflows/ci.yml`

**Description:** The CI pipeline does not include automated dependency vulnerability
scanning (e.g., `pip-audit`, `safety`, or Dependabot).

**Recommendation:** Add `pip-audit` or `safety` to CI pipeline. Configure Dependabot
for automated dependency updates.

---

## 4. Risk Matrix

| Risk | Impact | Likelihood | Exposure |
|------|--------|------------|----------|
| Token replay | High | Medium | High |
| Rate limit bypass | High | High (multi-instance) | High |
| CSRF | High | Medium | Medium |
| Error leakage | Medium | High | Medium |
| Committed secret | Medium | Low | Medium |
| Missing headers | Medium | Medium | Medium |
| No CORS policy | Medium | Medium | Medium |
| Audit not persisted | Medium | High | Medium |

---

## 5. Implementation Priority

1. **Immediate (P0):** Findings 1, 2, 3 — replay protection, distributed rate limiting, CSRF
2. **Short-term (P1):** Findings 4, 5, 7, 8 — error sanitization, secret removal, CORS, audit persistence
3. **Medium-term (P2):** Findings 6, 9, 10, 11 — security headers, content-type, idempotency validation, HSTS preload
4. **Ongoing (P3):** Finding 12 — dependency scanning automation

---

## 6. Conclusion

The Wilson Eval3ngine foundation has a robust security architecture with defense-in-depth
principles applied across authentication, authorization, data protection, and supply chain
security. The identified gaps are primarily in **production-readiness features** that
are critical for production deployment but not yet implemented in the foundation build.

All findings are addressable through code changes that maintain backward compatibility
with the development/default mode while adding production-grade security controls.