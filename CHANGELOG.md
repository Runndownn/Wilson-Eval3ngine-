# Changelog

All notable changes to Wilson Eval3ngine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Current security reassessment (`2026-08-22`)** that revalidates the twelve
  July 30 findings against current source, records newly discovered second-order
  defects, distinguishes revocation from bearer sender-binding, and defines the
  manual/runtime assurance contract while GitHub Actions are disabled.
- **Request-scoped authorization-decision auditing** at the common authorization
  boundary, with required hash-linked audit persistence before an allow decision
  returns and a bounded fail-closed response when that persistence is unavailable.
- **Bounded Redis security-authority adapter** so Redis failures used by shared
  rate-limit/revocation state are normalized without leaking backend details.
- **Current five-workspace GUI capture set** under `docs/assets/gui/current/` for
  Endpoints, Models, Generate, Charts, and Reports, with explicit point-in-time
  evidence/provenance guidance.
- **CONTRIBUTING.md** — comprehensive contributor guide covering environment
  setup, branch naming, commit conventions, testing, and PR process.
- **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 adopted for all
  community interaction spaces.
- **CHANGELOG.md** — this file, tracking notable changes per release.
- **`.github/dependabot.yml`** — dependency update configuration for GitHub
  Actions, Python dependencies, Docker images, and Terraform. Configuration is
  not represented as an executed scan while repository Actions are disabled.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — PR template with security, testing,
  and documentation checklists.
- **`.github/ISSUE_TEMPLATE/bug_report.yml`** — structured bug report workflow.
- **`.github/ISSUE_TEMPLATE/feature_request.yml`** — structured feature request
  workflow.
- **"Contributing" section in README.md** — links to CONTRIBUTING.md and
  CODE_OF_CONDUCT.md for first-time visitors.

### Changed

- **Production API request security** now composes shared Redis-backed security
  state, exact-origin CORS, actual-byte body enforcement, bounded metadata/media
  validation, exact role authorization, durable authentication/authorization
  audit, and application-lifetime OIDC authority as one supported path.
- **Rate-limit identity** now derives enforcement keys from the complete
  normalized client address without storing the address itself. Forwarded client
  identity is accepted only from configured trusted proxy CIDRs; an unverified
  `X-WE3-Project-ID` cannot select a fresh pre-authentication bucket.
- **Redis failure behavior** is fail-closed in staging/production for distributed
  request admission, revocation, and shared idempotency decisions. Development
  can retain an explicit process-local fallback.
- **OIDC semantics** now require bounded signed identity/lifetime claims and
  shared revocation state in assurance environments. Documentation no longer
  describes `jti` as cryptographic replay prevention for an unrevoked bearer
  token.
- **Authorization identity** preserves exact workload namespaces such as
  `workload:api`; suffix-stripping is removed. Recognized `system_admin` identity
  receives no implicit API superuser bypass without an explicit matrix grant.
- **Core project API routes** now enter the same authorization matrix as extended
  operation routes, so the decision and its audit record cannot be bypassed by a
  separate hard-coded role check.
- **Caddy public ingress** overwrites `X-Forwarded-For`, blocks public API
  readiness/metrics/schema UI paths, and no longer exposes Prometheus through a
  public virtual host. Prometheus stays on the internal observability network.
- **Production images/configuration** align Redis runtime dependencies, external
  mounted secret authority, immutable image references, explicit CORS/trusted
  proxy inputs, PostgreSQL TLS, and internal service networks.
- **Operator documentation** follows the implemented five-step workflow
  (`Endpoints → Models → Generate → Charts → Reports`) instead of presenting
  six older point-in-time screenshots as current navigation.
- **GUI evidence guidance** distinguishes workspace inventory from model quality,
  provider health from behavioral outcomes, synthetic demo charts from run
  evidence, and PDF narratives from authoritative structured evidence.
- **GUI runtime documentation and lint coverage** account for the supported
  runtime-injected `ux4`, `ux5`, and `ux6` browser overlays in addition to
  `enhanced.js`.
- **Documentation asset validation** validates WebP `RIFF/WEBP` signatures as
  well as PNG/SVG assets.

### Fixed

- **Distributed rate-limit bypass/fail-open paths** involving arbitrary
  `X-Forwarded-For`, caller-selected project buckets, privacy-reduced enforcement
  identity, and Redis outage fallback in assurance environments.
- **OIDC revocation composition** so supported API requests share the same
  application-lifetime revocation authority rather than recreating isolated
  per-request in-memory state.
- **Workload-role authorization bug** where `check_authorization()` stripped the
  `workload:` namespace before looking up matrix permissions.
- **API audit semantics** — compatibility `AuditService.log_event()` is now
  explicitly best effort; security-sensitive callers use required persistence
  and fail closed rather than describing swallowed audit failures as fail-closed.
- **Client error disclosure** — unexpected errors use bounded public messages;
  internal diagnostic sanitization remains on the server-side logging plane.
- **Browser conditional-request CORS** includes `If-Match` in the explicit
  preflight allowlist used by state-changing ETag flows.
- **Makefile cleanup scope** — recursive `__pycache__` removal belongs to
  `make clean` rather than running as an unrelated side effect of
  `backup-restore-plan`.
- **GUI JavaScript lint gap** — `make lint` syntax-checks `ux5.js` and `ux6.js`,
  which are injected by the supported GUI runtime overlay.
- **Test collection in `tests/hostile/`** — added the missing `__init__.py`
  package marker and corrected the hostile scenario import.
- **Dependency vulnerability: `cryptography`** — upgraded the dependency floor
  from the earlier 46.x range to `>=50.0.0,<51.0.0` in the current dependency
  policy.

### Removed

- **Public Prometheus Caddy route** — metrics remain internal; operators needing
  remote Prometheus access must add a separately authenticated private gateway.
- **`.archive/unused_files/secrets/fernet.key`** — committed Fernet key removed
  from the repository. The relevant secret paths are ignored to prevent
  recurrence. Any value ever committed remains treated as compromised even
  after active-tree deletion.

## [0.1.0] — 2026-07-15

### Foundation release

- Metrics-first LLM evaluation framework with five-outcome classification
  (appropriate refusal, false refusal, safe useful compliance, unsafe
  compliance, ambiguous/partial)
- Deterministic mock provider for reproducible local/CI runs
- Wilson score confidence intervals and versioned metric snapshots
- Release-gate engine with critical-event precedence
- Ed25519-signed release dossiers
- Content-addressed, SHA-256 evidence store
- Versioned Pydantic contracts and JSON Schema export
- FastAPI REST API with early OIDC/security middleware implementation
- PostgreSQL RLS project-isolation policy definitions
- SQLite for local testing; PostgreSQL-oriented production paths
- Operator GUI with endpoint, model, generation, chart, and report workflows
- Observability definitions for SLIs, alerting, dashboards, and error budget
- Backup/recovery data models, runbook, and early reconciliation scaffolding
- Browser assurance definitions for geometry, accessibility, zoom, and containment
- Supply-chain scanning/build-provenance definitions
- Threat model, ADRs, operational runbooks, and security assessments

Historical release bullets describe the repository at that release point and are
not substitutes for the current implementation/status or executed production
evidence.
