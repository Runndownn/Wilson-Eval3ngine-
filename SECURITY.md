# Security Policy

## Foundation status

Version 0.1.0 is a development and internal-testing foundation. Do not connect
it to production model credentials, real harmful corpora, personal data, or
release-gating workflows.

## Security invariants

- Raw model content is untrusted.
- Reliability errors are not behavioral labels.
- Development header authentication is prohibited in production mode.
- The local artifact adapter is not a production immutability control.
- Graders must not receive provider credentials or live tools.
- Certification must not use target-response caching.
- A composite score may not override a raw safety gate.

## Security architecture

### Authentication
- **OIDC JWT validation** with JWKS caching, key rotation support, and MFA enforcement
- **Token replay protection** via `jti` claim validation and distributed revocation list (Redis-backed)
- **Workload identity isolation** with least-privilege scopes per service type
- **Dev mode** header-based auth (prohibited in production)

### Authorization
- **Role-based access control** with 14 roles (7 human + 7 workload)
- **Project-scoped authorization** with database RLS enforcement
- **Export-specific authorization** (raw evidence requires explicit approval)
- **Backend-only authorization** (model responses cannot change roles)

### Rate Limiting
- **Redis-backed distributed rate limiting** using atomic Lua scripts (sliding window)
- **In-memory fallback** for single-instance deployments
- **Project-scoped keys** prevent cross-tenant rate limit bypass
- **IP anonymization** in logs and rate limit keys

### CSRF Protection
- **Double-submit cookie pattern** with HMAC-SHA256 tokens
- **Constant-time comparison** via `hmac.compare_digest`
- **Token expiry** (1 hour TTL with clock skew tolerance)
- **Bearer token exemption** (OIDC mode uses header-based auth, not cookies)

### Input Validation
- **Project ID validation** (alphanumeric + underscore/hyphen, max 64 chars)
- **SQL injection prevention** (pattern-based detection in identifiers)
- **Path traversal prevention** (rejects `..`, `/`, `\` in project IDs)
- **Idempotency key validation** (alphanumeric + hyphen/underscore, max 128 chars)
- **Content-type validation** (rejects unexpected content types for POST/PUT)
- **HTML escaping** for all sanitized output strings

### Secrets Management
- **Fernet key management** with versioning and rotation support
- **Environment variable-based** secret loading (no committed secrets)
- **Key rotation** with zero-downtime (old keys retained for decryption)
- **Health checks** for key validity and rotation status
- **Production validation** (rejects dev keys, enforces rotation intervals)

### Audit & Integrity
- **Hash-linked append-only audit ledger** (SHA-256 chain)
- **Signed checkpoints** using Ed25519 for integrity verification
- **Trust registry** for key fingerprint management
- **Event categorization** (auth, authz, data access, operations)
- **Correlation ID tracking** across all events

### Error Handling
- **Safe error responses** with sanitized details (no internal info leakage)
- **Standardized error codes** for client-side handling
- **Server-side full logging** with structured events
- **Pattern-based redaction** (file paths, DB connections, API keys, IPs, UUIDs)

### Security Headers
- **HSTS** with `includeSubDomains` and `preload` directives
- **Content-Security-Policy** with restrictive `default-src 'self'`
- **X-Frame-Options: DENY** (prevents clickjacking)
- **X-Content-Type-Options: nosniff** (prevents MIME sniffing)
- **Cross-Origin-Opener-Policy: same-origin** (prevents cross-origin attacks)
- **Cross-Origin-Resource-Policy: same-origin** (prevents cross-origin data reads)
- **Cross-Origin-Embedder-Policy: require-corp** (prevents speculative execution attacks)
- **Permissions-Policy** restricting geolocation, microphone, camera, payment, USB
- **Cache-Control: no-store** (prevents sensitive data caching)

### CORS
- **Explicit origin allowlist** (configured via `WE3_CORS_ALLOWED_ORIGINS`)
- **Default deny** (no CORS headers for unlisted origins)
- **Credentials support** for authenticated requests
- **Preflight caching** with limited max-age (3600s)

### Container Security
- **Non-root user** (UID 10001) in production containers
- **Read-only root filesystem** in Docker
- **Multi-stage build** to minimize attack surface
- **Caddy reverse proxy** with TLS termination and rate limiting

### Network Security
- **Egress controls** (metadata endpoint blocking, private network blocking)
- **Provider allowlist** with exact model version identifiers
- **Attachment quarantine** with MIME type detection and content scanning
- **Parser sandbox** with resource limits and path traversal detection

## Production deployment requirements

For production deployments, the following must be configured:

1. **PostgreSQL** (not SQLite) for database
2. **OIDC** authentication (not dev mode)
3. **External immutable object store** for artifacts
4. **Redis** for distributed rate limiting and token revocation
5. **Fernet encryption key** via `WE3_ENCRYPTION_KEY`
6. **CSRF secret** via `WE3_CSRF_SECRET`
7. **CORS origins** via `WE3_CORS_ALLOWED_ORIGINS`
8. **TLS** with valid certificates (handled by Caddy reverse proxy)

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner or the
organization's approved security intake. Include the affected version, a
minimal reproduction using synthetic data, impact, and suggested containment.
Do not include real secrets or harmful evidence in issue trackers.
