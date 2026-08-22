# Wilson Eval3ngine Security Reassessment — 2026-08-22

## Document control

| Field | Value |
|---|---|
| Product | Wilson Eval3ngine `0.1.0` |
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Historical input | `docs/security/SECURITY_ASSESSMENT.md`, dated 2026-07-30 |
| Reassessment branch | `security/current-hardening-20260822` |
| Base reviewed | `main` at `8862c609e33b83775327af2d4993b2ec0f0801ef` |
| Evidence class | Repository/source/configuration review plus authored regression contracts |
| Runtime/CI evidence | **Not claimed. GitHub Actions are disabled for this repository at the time of this reassessment.** |

This document is the current source-level reassessment of the twelve findings in the July 30 report. The older report is preserved as point-in-time evidence and is not rewritten into present tense. Source code can prove that a control is implemented and composed; it cannot prove that a private deployment is configured correctly, that a scanner found no vulnerabilities, or that a runtime control behaved correctly under real load.

## Executive result

The July 30 report correctly identified important production-readiness gaps, but its status table is now historical. Later hardening added most of the missing control families. This reassessment did not treat the presence of a class or middleware name as closure: it followed each control through API composition, shared state, reverse-proxy trust, error handling, persistence, tests, authorization semantics, and production packaging.

That deeper pass found several second-order defects inside the earlier remediations. Distributed rate limiting could trust attacker-controlled forwarding/project metadata and fail open; OIDC authenticators could lose shared revocation state when composed per request; workload role prefixes were stripped before authorization lookup; core API routes bypassed the authorization matrix; extended routes referenced actions that the matrix never granted; dossier generation could fall back from a denied dossier permission to a broader export permission; audit failure semantics were described inaccurately; the production image could require Redis without installing the client; and the public proxy surface exposed diagnostic/Prometheus paths that did not need to be public. The hardening branch repairs those root causes.

The branch is **not a production certification**. GitHub Actions are disabled, so no workflow result, dependency scan result, container build, Caddy validation, Redis/PostgreSQL integration run, browser run, or private runtime check is represented as passing here.

## Revalidation of the July 30 findings

| # | Historical finding | 2026-08-22 source status | Current interpretation |
|---|---|---|---|
| 1 | JWT `jti`/revocation missing | **Remediated for revocation; residual bearer replay remains** | OIDC requires bounded `jti`, `sub`, `exp`, and `iat`, verifies signed lifetime claims, shares a Redis-backed revocation authority in assurance environments, and exposes bounded self-revocation. This is revocation/session invalidation, **not** cryptographic proof that an unrevoked bearer token cannot be replayed before expiry. |
| 2 | Rate limiting process-local | **Remediated in supported production composition; runtime pending** | Production/staging require Redis. The Redis sliding window is atomic, security-state outages fail closed, untrusted forwarding headers are ignored, pre-authentication buckets cannot be selected with `X-WE3-Project-ID`, raw client addresses are not stored in rate keys, and Caddy overwrites forwarding identity. |
| 3 | No CSRF protection | **Reclassified + defense in depth implemented** | Current production authentication uses an explicit `Authorization: Bearer` header, not an ambient browser cookie, so classic CSRF is not the primary attack for that credential transport. A bound double-submit/HMAC control is present for any future cookie/session-authenticated state-changing path; bearer and development header auth are deliberately exempt. |
| 4 | Exception text leaked to clients | **Remediated in source** | Unexpected exceptions use fixed public messages/codes. Internal diagnostic redaction remains separate. Operation failure state no longer serializes raw exception text. |
| 5 | Committed Fernet key | **Active-tree exposure removed; historical-compromise rule remains** | `.secrets/` is ignored; the active tree does not contain `.secrets/fernet.key`; production rejects the development Fernet manager and uses the external secret backend/KMS boundary. Any key that ever existed in Git history must remain treated as compromised/revoked even after deletion. |
| 6 | Missing COOP/CORP/COEP | **Remediated in API and proxy definitions; browser runtime pending** | API and Caddy emit COOP/CORP/COEP alongside CSP, frame, MIME, cache, referrer, and permissions controls. Compatibility with exact browser/report flows still requires executed assurance. |
| 7 | No CORS policy | **Remediated in supported API composition** | Browser `Origin` is matched against an exact allowlist; wildcard origins are rejected; unauthorized origins and invalid preflights are rejected server-side before route side effects. `If-Match` is included for conditional state changes. CORS is explicitly not treated as authentication. |
| 8 | API audit not durable | **Remediated at authentication/authorization boundaries; runtime DB evidence pending** | Authenticated requests write to the hash-linked database ledger before route side effects. `check_authorization` has a request-scoped required audit hook that records allow/deny decisions before an allow returns. Audit persistence failure produces a bounded service-unavailable response. Self-revocation is also durably audited. |
| 9 | No content-type validation | **Remediated in source** | State-changing JSON/form routes have explicit media-type validation in the composed middleware boundary. |
| 10 | Idempotency key unvalidated | **Remediated and strengthened** | Keys are format/length validated. Assurance environments use Redis-backed project-scoped bindings, bind request intent hashes, reject key reuse for different intent, and fail closed when shared idempotency state is unavailable. Start-operation binding is established before the process-local operation is created, avoiding a ghost operation on a failed/racing binding. Operation execution state itself remains process-local and is called out below. |
| 11 | HSTS lacks `preload` | **Header fixed; preload enrollment is operational** | The API/proxy header includes `max-age=31536000; includeSubDomains; preload`. Header text does not prove the domain is enrolled in browser preload lists, nor that every subdomain is safe to preload. Enrollment remains a deliberate deployment/domain-owner decision. |
| 12 | No dependency vulnerability automation | **Tooling configured; automated execution unavailable** | `pip-audit`, Bandit, repository-native supply-chain scanning, Trivy workflow definitions, and Dependabot configuration exist. `make security-check` provides a local/manual fail-closed lane. Because GitHub Actions are disabled, no current automated scan result is claimed. |

## New defects found during this reassessment

### SR-2026-001 — Rate-limit identity and failure policy

**Severity:** High  
**Status:** Remediated in branch; runtime pending

The earlier Redis implementation did not by itself guarantee distributed abuse control. It trusted `X-Forwarded-For` without proving the direct peer was a trusted proxy, mixed an unauthenticated project header into the pre-authentication key space, anonymized the address before enforcement, and allowed Redis errors to become fail-open behavior.

The hardened path now separates enforcement identity from log privacy, trusts forwarded addresses only from configured proxy CIDRs, hashes the complete normalized client identity for the backend key, ignores unverified project headers when choosing the pre-auth bucket, uses an atomic Redis script with collision-resistant event members, and fails closed in staging/production when the shared authority cannot decide. Development may still use a process-local limiter intentionally. Authentication/revocation receives its own lower request limit rather than inheriting the general API budget.

### SR-2026-002 — OIDC revocation authority lifetime/composition

**Severity:** High  
**Status:** Remediated in branch; identity-provider runtime pending

Constructing an OIDC authenticator per request would create isolated in-memory revocation state and defeat self-revocation unless Redis happened to be explicitly threaded through every call. The supported application now creates one authenticator at app composition and binds it to the same shared Redis authority used by the production security path. Redis implementation exceptions are normalized into a stable security-state-unavailable condition instead of leaking backend messages.

Revocation TTL uses the token's complete remaining signed lifetime (plus configured skew) rather than truncating revocation to a shorter default.

### SR-2026-003 — Workload authorization namespace collapse

**Severity:** High  
**Status:** Remediated in branch

The authorization matrix contained roles such as `workload:api`, while `check_authorization` stripped everything before the colon and looked up `api`. That made intended workload permissions unusable and created a dangerous normalization pattern that could later alias identities unexpectedly.

Authorization now uses the exact canonical role string. Tests require `workload:api` to receive only its defined grants while the suffix-only `api` identity fails closed. `system_admin` remains recognized by OIDC but has no implicit API matrix grant; any future administrative API must define explicit permissions rather than inheriting an all-powerful bypass.

### SR-2026-004 — Core routes bypassed the authorization matrix

**Severity:** High  
**Status:** Remediated in branch

Several core routes relied only on authenticated project context or a hard-coded role set. They therefore bypassed the common authorization/audit boundary. Validation, execution, operation read, and experiment read now enter `check_authorization` with project context and return bounded 403 responses on denial. Extended operation routes use the same matrix.

### SR-2026-005 — Authorization audit was not fail-closed by construction

**Severity:** Medium  
**Status:** Remediated in branch; database-runtime evidence pending

The legacy `AuditService` described failures as “fail-closed” while swallowing them and returning an empty hash. That wording is corrected. The compatibility `log_event` is explicitly best effort, while `log_event_required` raises `AuditPersistenceError`.

For the API, a request-scoped authorization-audit middleware records matrix allow/deny decisions to `AuditLedger` before an allow decision returns. A failed required audit write prevents the protected action from continuing and returns a safe 503 through the normal security-header/logging stack.

### SR-2026-006 — Production Redis dependency mismatch

**Severity:** High  
**Status:** Remediated in image definition; image build pending

Production configuration required Redis-backed rate/revocation/idempotency state, but the standard production wheelhouse path did not consistently install the Redis client. `Dockerfile.prod` and the secure image contract now include the Redis runtime dependency and use the external-secret entrypoint.

### SR-2026-007 — Public diagnostics and forwarding trust at ingress

**Severity:** Medium  
**Status:** Remediated in Caddy definition; Caddy/runtime validation pending

The public API site proxied all paths, which made `/metrics` and `/ready` reachable through the public API hostname even though those are operational surfaces. The earlier template also exposed Prometheus through a public virtual host guarded only by source-address matching, despite Grafana/internal monitoring already having direct access on the observability network. Production additionally needed an unambiguous contract for forwarded client identity.

Caddy now blocks `/metrics`, `/ready`, `/openapi.json`, `/docs*`, and `/redoc*` on the public API host, has no Prometheus public site, disables its admin endpoint, and overwrites `X-Forwarded-For` with the public peer address before proxying. Production FastAPI disables interactive docs/OpenAPI endpoints. `WE3_TRUSTED_PROXY_CIDRS` must contain only the private Caddy-to-API network ranges; an empty value remains spoof-safe but rate-limits clients as the proxy peer rather than individually.

### SR-2026-008 — Extended-route permission mismatch and dossier fallback

**Severity:** High  
**Status:** Remediated in branch

Extended experiment routes checked `start` and `regrade` actions that were not present in the permission matrix, making those protected actions unreachable for intended engineering/admin roles. More seriously, dossier generation first checked `create:dossier` and then accepted generic `exports:create` after the privileged check failed, allowing roles intended only for ordinary exports to cross into release-evidence generation.

The matrix now contains explicit `start` and `regrade` grants only for the intended evaluation-engineer/project-admin roles. Dossier generation requires `create:dossier` without fallback, preserving the release/signing authority boundary. The start route establishes the idempotency binding before creating the process-local operation, so backend failure or a competing binding cannot leave an unauthoritative local operation behind. Dedicated route/matrix regression tests lock these semantics.

## Architecture after hardening

```text
internet/browser
      |
      v
Caddy TLS/public trust boundary
  - only published host ports
  - overwrites forwarded client identity
  - blocks API diagnostics/schema UI
  - no public Prometheus route
      |
      v
API request boundary
  - actual-byte body limit
  - exact CORS/preflight policy
  - metadata/content-type validation
  - Redis-authoritative pre-auth rate limit
  - OIDC bearer validation + shared revocation authority
      |
      v
request identity
  - project / exact role / subject
  - durable authenticated-request audit
      |
      v
exact authorization matrix
  - human and workload:* namespaces stay distinct
  - explicit route actions; no privileged fallback
  - durable allow/deny audit before allow returns
      |
      v
project-scoped repository / operation / evidence behavior
      |
      +--> PostgreSQL audit hash chain
      +--> Redis idempotency / revocation / rate state
```

The security boundaries are intentionally distinct. Redis is not the identity provider and PostgreSQL is not a rate limiter. CORS is not authentication. `jti` is not sender binding. Structured logs are not the durable audit ledger. Caddy forwarding headers are not trusted unless the direct peer is within the configured private proxy range. Generic report-export permission is not release-dossier authority.

## Residual risks and required follow-up evidence

1. **Bearer replay before revocation/expiry.** A stolen, otherwise valid bearer token remains reusable until expiry or revocation. If the threat model requires proof-of-possession, evaluate sender-constrained tokens such as DPoP or mutually authenticated client credentials with the actual identity provider; do not relabel `jti` as replay prevention.
2. **Operation state is process-local in the synchronous API lane.** Redis preserves idempotency binding, but after a process restart the API can deliberately return `idempotency_operation_state_unavailable`. Durable execution/state belongs to the PostgreSQL scheduler and should be used for horizontally scaled long-running work.
3. **Historical secret exposure cannot be undone by deletion.** Any old Fernet value ever committed must remain revoked. A history/hosted-secret scan should be executed with an approved scanner; no clean result is claimed here.
4. **Proxy CIDRs are private deployment facts.** Incorrectly broad `WE3_TRUSTED_PROXY_CIDRS` can reintroduce forwarding-header spoofing. The production deployment must prove that only Caddy can reach the API ingress network and that the configured CIDRs match that path.
5. **HSTS preload is a domain-owner decision.** Do not submit a domain for browser preload until every required subdomain is HTTPS-only and the organization accepts the rollback implications.
6. **GitHub Actions are disabled.** Workflow YAML and Dependabot configuration are definitions, not current evidence. Until automation is restored, run the repository's local/manual security lane and retain its outputs privately.
7. **Runtime assurance remains mandatory.** Real OIDC key rotation/revocation, Redis outages, PostgreSQL audit concurrency, Caddy config parsing, TLS behavior, dependency/container scans, browser CORS/header compatibility, direct-port/Prometheus denial, authorization negative paths, and egress behavior must be executed against the exact release/deployment.
8. **Recovery work is a separate assurance stream.** The base branch used here still carries the recovery status of `main`; the separate recovery-completion work must be reviewed/merged independently rather than copied into this security branch merely to make this report broader.

## Manual validation contract while GitHub Actions are disabled

Install the development/security tooling and run the repository-owned lane from a clean checkout of the exact reviewed commit:

```bash
make install-security
make lint
make security-check
make test
make coverage
```

For production artifacts, that is still not enough. Build the exact digest-pinned image using an approved base, validate Caddy and Compose with private synthetic/real configuration as appropriate, scan the resulting image/SBOM, and execute the private runtime-assurance sequence. Store raw private evidence outside the public repository and publish only bounded fingerprints/statuses when public traceability is needed.

No command in this section is represented as having passed during this connector-only reassessment.

## Closure standard

A historical finding is marked remediated here only when the current branch contains the control and the supported composition uses it. “Runtime pending” means exactly that: the source no longer contains the identified design gap, but production behavior still requires executed evidence. A control is not closed merely because a class, environment variable, test name, or workflow definition exists.
