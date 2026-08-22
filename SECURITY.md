# Security Policy

## Current security position

Wilson Eval3ngine `0.1.0` is an **active evaluation platform in pre-production assurance**. The repository contains substantial security, identity, evidence-protection, deployment, and certification implementations, but source code alone does not certify a production environment. Production use must satisfy the applicable repository checks plus the private runtime-assurance contract for the exact deployment.

The current source-level security reassessment is [`docs/security/SECURITY_REASSESSMENT_2026-08-22.md`](docs/security/SECURITY_REASSESSMENT_2026-08-22.md). It revalidates the July 30 findings against the hardened API/deployment composition and explicitly separates implemented controls from runtime evidence. GitHub Actions are disabled at the time of that reassessment; workflow definitions therefore are **not** current execution evidence.

The deterministic local `foundation` lane remains intentionally constrained and should not be connected to real production credentials, sensitive corpora, personal data, or release authority merely because it is easy to run. See [`docs/STATUS.md`](docs/STATUS.md) for the current implementation/assurance matrix and [`docs/security/PRIVATE_RUNTIME_ASSURANCE.md`](docs/security/PRIVATE_RUNTIME_ASSURANCE.md) for the public/private evidence boundary.

## Security invariants

- Raw model content is untrusted and must remain inert when rendered.
- Reliability errors are not behavioral labels.
- Development authentication is prohibited as a production identity authority.
- Local filesystem artifacts are not automatically a production immutability control.
- Development/local key implementations are not managed production KMS/signing authority.
- Graders must not receive target-provider credentials or live tools by default.
- Certification must not use target-response caching in ways that invalidate evidence.
- A composite score may not override a raw safety gate or critical unsafe event.
- The operator GUI is **secure-by-default on loopback**. Non-loopback binding requires the explicit `WE3_GUI_ALLOW_REMOTE_BIND=1` override plus independent authenticated/authorized TLS and network controls.
- Provider destination checks do not replace host/container network egress policy.
- A Boolean metadata field is not proof of encryption; cryptographic/storage evidence must match the actual payload.
- A restore plan or successful scaffold test is not proof that a restore occurred.
- CORS is not authentication, `jti` is not bearer sender-binding, and structured logs are not the durable security audit ledger.
- Repository implementation is not deployment proof; required runtime evidence must be executed and retained.

## Authentication and authorization

The production-oriented API uses OIDC/JWT validation with bounded signed claims, restricted signing algorithms, JWKS caching/rotation behavior, project/role/MFA claim checks, and a shared Redis-backed token-revocation authority in staging/production. The supported application composes one OIDC authenticator for the application lifetime rather than recreating independent revocation state per request.

JWT IDs (`jti`) and revocation are useful invalidation controls, but they do **not** make an otherwise valid bearer token non-replayable before it expires or is revoked. If the deployment threat model requires sender-constrained tokens, evaluate that with the real identity provider (for example, DPoP or mutually authenticated client credentials) and retain runtime evidence. Do not label ordinary `jti` checking as cryptographic replay prevention.

Role authorization uses exact canonical identities. Workload role prefixes such as `workload:api` are security-significant and are not collapsed to suffixes. `system_admin` may be recognized as an identity claim, but it receives no implicit all-powerful API bypass; administrative APIs must define explicit matrix grants if they are introduced.

Supported project-scoped API routes pass through the shared authorization matrix. In the API request scope, matrix allow/deny decisions are appended to the hash-linked database audit ledger before an allow returns. If required authorization-audit persistence fails, the protected action fails closed with a bounded service-unavailable response.

A real deployment owns its approved issuer, JWKS endpoint, audience, claims, groups/roles, MFA policy, token lifetime, revocation behavior, workload identities, database row policies, object policies, and negative authorization tests. Do not publish those private values merely to document that a feature exists.

## Operator GUI security

The supported launcher is `we3-gui-start`. Its secure default is `127.0.0.1`; historical wildcard defaults such as `0.0.0.0` are repaired to loopback unless the operator deliberately sets:

```bash
WE3_GUI_ALLOW_REMOTE_BIND=1
```

With that override, a specific non-loopback address or wildcard bind is permitted and the launcher warns for broad exposure. The override is not authentication. Remote operation must still be protected by an independently configured authenticated and authorized TLS proxy or equivalent access layer, firewall policy, trusted forwarding behavior, and deployment-specific validation.

The GUI can administer provider endpoints, credentials, models, jobs, charts, reports, exports, and deletion. The process may decrypt locally stored endpoint credentials and start provider-capable child processes, so compromise of its operating-system identity remains material residual risk.

## Provider and egress security

Public hosted providers should use canonical HTTPS endpoints. Intentional loopback/private gateways require explicit enablement, automatic redirects are constrained to reduce credential-forwarding risk, and unsafe destination classes remain blocked by application policy.

Application destination checks are only one layer. Production deployments must also enforce approved network egress and validate allowed/denied destinations without exposing real allowlists or private topology in the public repository.

## Secrets and child-process transport

Credentials must not be committed, logged, returned through endpoint APIs, pasted into issue/PR text, or placed in regular plaintext report-key files. `.secrets/` is ignored, and the active production path rejects the development Fernet helper in favor of an external secret authority/KMS boundary. Any credential that ever existed in repository history must remain treated as compromised and rotated even after it is deleted from the active tree.

On supported POSIX systems, the supported keyed report-job path uses a one-shot FIFO inside a restrictive directory rather than the historical regular temporary file. Production deployment should use its approved secret authority and platform-appropriate protected process-to-process transport.

## Input, browser, and request-admission protections

The API validates project/idempotency metadata and route media types and enforces request size using the actual ASGI receive stream rather than trusting `Content-Length` alone. Idempotency keys are format-bounded; assurance environments bind key + project + request-intent hash in Redis and fail closed if shared idempotency state is unavailable.

Distributed rate limiting is also a production shared-state control. The supported path uses an atomic Redis sliding window, fails closed in staging/production when Redis cannot decide, separates exact enforcement identity from privacy-reduced log labels, and does not let an unauthenticated `X-WE3-Project-ID` choose a fresh pre-authentication bucket. `X-Forwarded-For` is trusted only when the direct peer is inside `WE3_TRUSTED_PROXY_CIDRS`.

Caddy is the public forwarding authority in the provided production topology. It overwrites `X-Forwarded-For` at ingress. `WE3_TRUSTED_PROXY_CIDRS` must therefore contain only the private Caddy-to-API network range(s), never broad client networks. An empty trusted-proxy value is safe against spoofing but causes the API to rate-limit clients as the proxy peer rather than individually.

Browser `Origin` handling uses an exact configured allowlist with server-side rejection of disallowed origins and invalid preflights. Wildcard origins are not a supported credentialed production policy. Conditional requests include `If-Match` in the allowed preflight header set.

Current production authentication uses an explicit bearer header, which is not an ambient browser cookie and is therefore not subject to classic cookie-CSRF in the same way. A bound HMAC/double-submit CSRF primitive is present for any future cookie/session-authenticated state-changing path; bearer-header OIDC and development header authentication are deliberately exempt. CORS and CSRF remain separate controls.

Security headers are applied by both the API and Caddy, including CSP, COOP, CORP, COEP, MIME/frame/referrer/permissions controls, cache restrictions, and HSTS with `includeSubDomains; preload`. The header token `preload` does not prove browser-list enrollment and should not prompt enrollment until the domain owner has verified every required subdomain and rollback implication.

## Evidence, audit, reporting, and cryptography

The evaluation path uses content-addressed artifacts, hash-linked database audit events, and Ed25519 signing for dossier integrity. Authenticated API requests are durably audited before protected route work, and API authorization decisions are recorded at the matrix decision boundary. The legacy `AuditService.log_event` remains explicitly best effort for compatibility; security-sensitive callers use `log_event_required` or `AuditLedger.append` directly.

The broader evaluation-evidence storage layer includes AES-256-GCM envelope-encryption behavior and retention/legal-hold interfaces. Development key generation and `LocalKMSClient` are not production key custody.

The security branch is based on the current `main` recovery state. Separate backup/PITR completion work must be reviewed and merged on its own evidence rather than copied into this branch to manufacture a broader security claim. Until that work is integrated, apply the backup/recovery status documented by the branch actually being deployed.

## Production-oriented deployment

The hardened production image requires an operator-supplied immutable base reference, builds the complete package into a wheel, installs PostgreSQL/backup and Redis runtime dependencies, runs as UID/GID 10001, and starts the external-secret API entrypoint. Production Compose requires immutable image references and mounted secret files rather than ordinary API secret environment values.

Only Caddy publishes host ports. API, PostgreSQL, Redis, Prometheus, and Grafana remain on purpose-specific internal networks, while explicit egress goes through the egress proxy boundary. Caddy blocks `/metrics`, `/ready`, `/openapi.json`, `/docs*`, and `/redoc*` on the public API hostname; FastAPI also disables interactive docs/OpenAPI endpoints in staging/production.

Deployment source is a template, not runtime evidence. Before production approval, validate exact image digests, Caddy parsing, TLS, only-proxy ingress, trusted proxy CIDRs, database/cache authentication and transport, filesystem/container permissions, egress default-deny behavior, health/readiness from intended internal probes, browser headers/CORS behavior, real backup/restore behavior, observability, and failure handling in the authorized environment.

## Dependency and supply-chain assurance

The repository defines Dependabot updates, a repository-native supply-chain scanner, Bandit, `pip-audit`, Trivy workflow scanning, pinned GitHub Action references, build provenance steps, and governance tests. The local/manual fail-closed lane is:

```bash
make install-security
make lint
make security-check
make test
make coverage
```

These commands are requirements, not claims about this branch. GitHub Actions are disabled at the time of the 2026-08-22 reassessment, so no current automated workflow or vulnerability-scan result is asserted as passing. Raw scanner findings and private deployment evidence should follow the private-assurance boundary.

## Certification and assurance

The repository contains certification orchestration across reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability. A certification result is valid only when the required evidence for the exact release is present, verified, and meets blocking requirements.

Private runtime evidence such as real identities, certificates, provider destinations, raw scanner output, logs, packet captures, test accounts, KMS/object metadata, proxy CIDRs, and restore topology should remain outside the public repository. Follow [`docs/security/PRIVATE_RUNTIME_ASSURANCE.md`](docs/security/PRIVATE_RUNTIME_ASSURANCE.md) to publish only bounded statuses/fingerprints when public traceability is required.

## Historical security material

[`docs/security/SECURITY_ASSESSMENT.md`](docs/security/SECURITY_ASSESSMENT.md) is the July 30 automated assessment supplied to the hardening workstream. [`docs/security/MASTER_SECURITY_ASSESSMENT.md`](docs/security/MASTER_SECURITY_ASSESSMENT.md) is a detailed point-in-time assessment dated 2026-08-01. Read both against the branch/head and date they reviewed. The current source-level revalidation is [`docs/security/SECURITY_REASSESSMENT_2026-08-22.md`](docs/security/SECURITY_REASSESSMENT_2026-08-22.md).

ADRs, Plans/TODOs, evidence inventories, and Phase-1 reports preserve useful history but do not automatically describe the latest implementation or runtime state.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner or the organization's approved security intake. Include the affected version/commit, a minimal synthetic reproduction, impact, and suggested containment when possible. Do not include real secrets, private topology, harmful evidence, or sensitive user/provider data in public issue trackers.
