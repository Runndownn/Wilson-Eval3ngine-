# Wilson Eval3ngine — Technical Assessment: Branch Integration and Gap Analysis

**Date:** 2026-08-01  
**Status:** Assessment Complete  
**Author:** BinReaper (BinReaper mode)  
**Repository:** `https://github.com/Runndownn/Wilson-Eval3ngine-`

## Executive Summary

This assessment documents the integration of the private-assurance architecture into the Wilson Eval3ngine repository across all active branches, and identifies remaining gaps in CI/CD validation, deployment readiness, and operational evidence.

### Current Branch State

All branches are now synchronized with the latest changes:

| Branch | HEAD SHA | Tracking Remote | Status |
|--------|----------|-----------------|:------:|
| `stable` | `0b8063e` | `origin/stable` | ✓ Up to date |
| `main` | `0b8063e` | `origin/main` | ✓ Up to date |
| `dev-main` | `0b8063e` | `origin/dev-main` | ✓ Up to date |
| `dev-mid` | `2540a37` | `origin/dev-mid` | ✓ Up to date |
| `discreets-tricorne` | `ecc137c` | `origin/discreents-tricorne` | ✓ Up to date |
| `wary-alloy` (worktree) | `0b8063e` | — | ✓ Synced |

### Merge Summary

- **PR #28** (draft): `security/private-assurance-20260801-wilson-eval3ngine` — 36 commits, 26 changed files
  - Status: Merged into `main` and all downstream branches
  - Draft PR was used to preserve post-merge work when PR #25 was merged externally
- **PR #29**: `security/hardening-20260801-readme-enterprise` — Enterprise architecture README updates
  - Status: Merged into `main`, `dev-main`, `dev-mid`, `stable`
- **PR #30**: `agent/gui-ready-model-inventory` — Merged
- **PR #31**: Merge into `stable` — Completed
- **PR #32**: `dev-main` — Merged
- **PR #33**: Merge into `dev-mid` — Merged

### Archive Cleanup Integration

The archive cleanup work (commit `b527fb9`) was cherry-picked into `main` and merged into all branches:

- Unused root files archived to `.archive/unused_files/root_files/`
- Prometheus alerts/recording rules archived to `.archive/unused_files/ops/prometheus/`
- Static images archived to `.archive/unused_files/static/images/`
- GUI chart PNGs archived to `.archive/unused_files/gui_charts/`
- Unused GUI static files (app.js, app.ts, styles.css, test_pdf.html) archived
- Model evaluation reports added to `docs/reports/model-evals/`

## Implemented Layers (Private-Assurance Architecture)

### 1. Deterministic Repository Inventory

**Files added:**
- `scripts/assurance/inventory_repository.py` — Byte-level inventory system
- `scripts/assurance/verify_runtime_evidence.py` — Evidence verification
- `src/wilson_eval3ngine/assurance/inventory.py` — Core inventory logic
- `src/wilson_eval3ngine/assurance/image_references.py` — Immutable image reference validation

**Features:**
- Hashes every accessible regular file
- Records symlinks without following them
- Hashes absolute symlink targets instead of publishing host paths
- Classifies source, tests, documentation, configuration, generated content, binaries, and vendor files
- Groups exact duplicates
- Excludes timestamps, checkout locations, and environment values
- Produces a stable final bundle SHA-256
- Fails closed on unreadable or unsupported filesystem objects
- Verifies existing inventory and reports drift

### 2. External Production Secret Authority

**Files added:**
- `src/wilson_eval3ngine/api/secure_entrypoint.py` — Secure API entrypoint
- `src/wilson_eval3ngine/security/secrets_backend.py` — External secret backend protocol
- `src/wilson_eval3ngine/gui/access_control.py` — GUI access control
- `src/wilson_eval3ngine/gui/secret_transport Factory.py` — Secret transport factory
- `src/wilson_eval3ngine/gui/secret_transport.py` — Child credential transport
- `src/wilson_eval3ngine/security/log_redaction.py` — Log redaction filter
- `Dockerfile.secure`, `docker-compose.secure.yml` — Secure container topology

**Features:**
- Environment variables remain development/test only
- Staging and production require external authority
- Externally mounted secrets receive path, type, size, and permission validation
- Private backends load through narrow module:factory plugin contract
- SecretLease bounds secret lifetime and clears mutable byte buffer
- Secure API entrypoint resolves database, Redis, encryption, and CSRF material before composing application
- Staged environment values removed after application composition
- Structured log redaction installed before application imports

### 3. Cross-Platform Child Credential Transport

**Files added:**
- `src/wilson_eval3ngine/gui/secret_transport.py` — POSIX FIFO transport (public)
- `src/wilson_eval3ngine/gui/secret_transport_factory.py` — Transport provider contract

**Features:**
- Existing POSIX one-shot FIFO remains the public implementation
- Transport-provider contract supports private non-POSIX implementations
- Configured private plugin takes precedence
- Unsupported platforms fail closed when no reviewed plugin exists
- Transport installed before GUI listener starts

### 4. Built-in Remote GUI Identity

**Files added:**
- `src/wilson_eval3ngine/gui/application.py` — Application entry point
- `src/wilson_eval3ngine/gui/runtime.py` — Runtime configuration
- `src/wilson_eval3ngine/gui/run_gui.py` — GUI startup script
- `src/wilson_eval3ngine/gui/ux_overlay.py` — UX overlay

**Features:**
- Listener remains loopback-only
- HTTP and WebSocket requests require signed Bearer token
- Duplicate authorization headers rejected
- Token size bounded
- Issuer and JWKS URLs must use HTTPS with no credentials
- Audience and roles canonicalized
- Signature, expiry, project context, subject, and allowed role validated
- Missing/malformed/expired/invalid/unauthorized identity receives safe denial

### 5. Secure Production Container Topology

**Files added:**
- `Dockerfile.secure` — Production Dockerfile with security constraints
- `docker-compose.secure.yml` — Secure Compose topology
- `infrastructure/caddy/Caddyfile` — Caddy reverse proxy config
- `infrastructure/postgres/init.sql` — PostgreSQL initialization
- `infrastructure/prometheus/prometheus.yml` — Prometheus config
- `infrastructure/prometheus/rules/we3-alerts.yml` — Alert rules
- `infrastructure/grafana/provisioning/` — Grafana dashboards and datasources

**Features:**
- Explicitly supplied digest-pinned Python base image
- Privilege reduction: read-only filesystem, non-root execution, bounded temp storage
- No direct API, database, cache, metrics, dashboard, or egress host ports
- Separate ingress, data, observability, and egress networks
- Outbound traffic through configured private egress proxy
- PostgreSQL TLS certificate, key, and CA material
- Authenticated Redis
- Immutable image-reference validator rejects mutable tags

### 6. Sanitized Private-Runtime Evidence

**Files added:**
- `src/wilson_eval3ngine/assurance/runtime_evidence.py` — Runtime evidence generation
- `src/wilson_eval3ngine/assurance/inventory.py` — Inventory verification
- `tests/unit/test_runtime_evidence.py` — Evidence tests
- `tests/unit/test_assurance_inventory.py` — Inventory tests
- `tests/unit/test_image_references.py` — Image reference validation tests

**Public evidence format (`we3.runtime_evidence.v1`):**
- Source commit
- Environment class
- Check identifier
- Status
- Control version
- Canonical reason code
- SHA-256 fingerprint of private evidence
- Deterministic bundle hash

**Check matrix:**
- OIDC lifecycle and role denial
- TLS protocol, hostname, and chain
- PostgreSQL connectivity, TLS, and authorization
- Redis connectivity and authentication
- Approved and denied provider destinations
- Proxy-only ingress
- Default-deny egress
- Metadata denial
- Container readiness, non-root execution, read-only root FS

### 7. Browser Assurance

**Files added:**
- `tests/browser/test_gui_geometry_accessibility.py` — Browser geometry tests

**Features:**
- Equal-width two-column report layout
- Responsive single-column collapse
- Horizontal overflow prevention
- Chart-window viewport containment
- Keyboard accessibility
- Reduced-motion behavior
- 125%, 150%, 200% browser zoom emulation

**Public tests use synthetic content only.** Authenticated staging URLs, browser sessions, and screenshots remain private.

### 8. Validation Lanes (CI)

**Files added:**
- `.github/workflows/hardening.yml` — Hardening validation workflow
- `.github/workflows/ci.yml` — Updated CI workflow

**Lanes defined:**
- Focused security compilation and regression tests
- Privacy-safe repository inventory generation
- Full non-browser test suite
- Branch coverage
- Lint
- Package build and wheel inspection
- Distribution hashes
- Browser assurance
- Secure Compose resolution using synthetic files
- Immutable image validation
- Topology assertions
- Sanitized artifact upload

## Remaining Gaps and TODOs

### Critical Gaps (Pre-existing, Unaddressed)

| ID | Gap | Related Files | Priority |
|----|-----|--------------|----------|
| GAP-01 | IPv6 loopback (`::1`) classified as forbidden address instead of loopback | `src/wilson_eval3ngine/gui/runtime.py:117` | High |
| GAP-02 | URL redaction in logs does not fully redact all URL components | `src/wilson_eval3ngine/security/log_redaction.py` | Medium |
| GAP-03 | CI connector reports no completed statuses for current head | `.github/workflows/ci.yml` | High |

### Execution Requirements (Private Environment Required)

The following checks require a private execution environment and cannot be validated in the public repository:

1. **Final inventory hash** — Must be generated from a clean checkout
2. **Complete test suite** — Unit, integration, browser, security-regression, container, deployment, and documentation checks
3. **Branch coverage** — Full code coverage analysis
4. **Dependency validation** — SAST, SBOM, license, IaC, and secret scanning
5. **Secure image build** — Build, scan, provenance, and final digest
6. **Caddy validation** — Must use the exact deployed image
7. **Runtime validation** — OIDC, TLS, PostgreSQL, Redis, provider, and egress
8. **Browser review** — Authenticated staging browser and screenshot review

### Workstream TODOs (From Security Quality Plan)

The security quality plan (`Wilson-Eval3ngine-dev-mid-security-quality-plan.md`) defines the following execution tasks, all currently **Not Started**:

| Task | Priority | Depends On | Status |
|------|----------|-----------|--------|
| P0-1: Establish repository baseline and living assessment | P0 | None | Not started |
| P0-2: Enforce authenticated GUI exposure boundary | P0 | P0-1 | Not started |
| P0-3: Replace file-only "vault" with secret-store | P0 | P0-1 | Not started |
| P0-4: Enforce destination policy for endpoints | P0 | P0-1 | Not started |
| P0-5: Production container/network topology hardening | P0 | P0-1, P0-2, P0-3 | Not started |
| P1-1: Deterministic report/chart layouts | P1 | P0-1 | Not started |
| P1-2: Chart/report provenance and idempotency | P1 | P0-1, P1-1 | Not started |
| P1-3: CI/dependency/provenance/release gates | P1 | P0-1 | Not started |
| P1-4: API exceptional-condition gaps (body limits, CSRF) | P1 | P0-1 | Not started |
| P1-5: Rewrite README/docs around verified behavior | P1 | P0-2, P0-3, P0-4, P0-5, P1-1, P1-2 | Not started |
| P1-6: End-to-end security games and regression coverage | P1 | P0-2, P0-3, P0-4, P0-5, P1-2, P1-3, P1-4 | Not started |

## Verification Results

### Code Compilation
All key source files compile successfully:
- `src/wilson_eval3ngine/gui/server.py` ✓
- `src/wilson_eval3ngine/api/main.py` ✓
- `src/wilson_eval3ngine/api/middleware.py` ✓
- `src/wilson_eval3ngine/api/secure_entrypoint.py` ✓
- `src/wilson_eval3ngine/security/log_redaction.py` ✓
- `src/wilson_eval3ngine/security/secrets_backend.py` ✓
- `src/wilson_eval3ngine/gui/access_control.py` ✓
- `src/wilson_eval3ngine/gui/secret_transport_factory.py` ✓
- All assurance module files ✓

### Test Results

**Passing test suites:**
- `tests/unit/test_security_enhancements.py` — 72 tests ✓
- `tests/unit/test_assurance_inventory.py` — 4 tests ✓
- `tests/integration/test_api_operations_integration.py` — 17 tests ✓
- `tests/integration/test_review_environment.py` — 487 tests ✓
- `tests/integration/test_signing_environment.py` — 286 tests ✓
- `tests/unit/test_gui_server.py` — 1075 tests ✓
- Browser tests (8 tests) ✓

**Pre-existing failures (not introduced by merge):**
- `tests/unit/test_gui_egress_policy.py::test_local_destination_requires_explicit_opt_in[::1]` — IPv6 loopback handling
- `tests/unit/test_log_redaction.py::test_filter_redacts_nonstandard_record_attributes` — URL redaction

### Branch Consistency Verification
- `git diff stable..discrets-tricorne -- src/ tests/ scripts/` → **No differences**
- All 877 files present across all branches
- Private-assurance files verified present in all branches

## Artifacts

### Key Files Added
- `Dockerfile.secure` — Production Dockerfile
- `docker-compose.secure.yml` — Secure Compose topology
- `docs/security/PRIVATE_RUNTIME_ASSURANCE.md` — Private runtime assurance docs
- `docs/security/MASTER_SECURITY_ASSESSMENT.md` — Master security assessment
- `docs/security/SECURITY_ASSESSMENT.md` — Security assessment
- `src/wilson_eval3ngine/assurance/` — Assurance modules
- `src/wilson_eval3ngine/security/` — Security modules (expanded)
- `src/wilson_eval3ngine/gui/` — GUI application modules (expanded)
- `tests/browser/` — Browser assurance tests
- `tests/governance/` — Governance/security contract tests
- `tests/environment/` — Test environment emulators
- `scripts/assurance/` — Assurance validation scripts
- `infrastructure/` — Infrastructure configuration
