# Changelog

All notable changes to Wilson Eval3ngine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Current five-workspace GUI capture set** under `docs/assets/gui/current/` for
  Endpoints, Models, Generate, Charts, and Reports, with explicit point-in-time
  evidence/provenance guidance.
- **CONTRIBUTING.md** — comprehensive contributor guide covering environment
  setup, branch naming, commit conventions, testing, and PR process.
- **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 adopted for all
  community interaction spaces.
- **CHANGELOG.md** — this file, tracking notable changes per release.
- **`.github/dependabot.yml`** — automated dependency update configuration for
  GitHub Actions, Python dependencies, GitHub Actions workflows, and
  Docker base images.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — PR template with security, testing,
  and documentation checklists.
- **`.github/ISSUE_TEMPLATE/bug_report.yml`** — structured bug report workflow.
- **`.github/ISSUE_TEMPLATE/feature_request.yml`** — structured feature request
  workflow.
- **"Contributing" section in README.md** — links to CONTRIBUTING.md and
  CODE_OF_CONDUCT.md for first-time visitors.

### Changed

- **Operator documentation** now follows the implemented five-step workflow
  (`Endpoints → Models → Generate → Charts → Reports`) instead of presenting
  six older point-in-time screenshots as current navigation.
- **GUI evidence guidance** now distinguishes workspace inventory from model
  quality, provider health from behavioral outcomes, synthetic demo charts from
  run evidence, and PDF narratives from authoritative structured evidence.
- **GUI runtime documentation and lint coverage** now account for the supported
  runtime-injected `ux4`, `ux5`, and `ux6` browser overlays in addition to
  `enhanced.js`.
- **Documentation asset validation** now validates WebP `RIFF/WEBP` signatures
  as well as PNG/SVG assets.

### Fixed

- **Makefile cleanup scope** — recursive `__pycache__` removal now belongs to
  `make clean` rather than running as an unrelated side effect of
  `backup-restore-plan`.
- **GUI JavaScript lint gap** — `make lint` now syntax-checks `ux5.js` and
  `ux6.js`, which are injected by the supported GUI runtime overlay.
- **Test collection in `tests/hostile/`** — added missing `__init__.py` package
  marker and corrected the import in `test_hostile_scenarios.py` from an
  absolute `tests.hostile.scenarios` import to a relative `.scenarios`
  import. The hostile test suite (39 tests) now collects and runs correctly.
- **Dependency vulnerability: `cryptography`** — upgraded the dependency
  floor from `>=46.0.0,<47.0.0` to `>=50.0.0,<51.0.0`, resolving three
  GitHub security advisories (CVE-2026-69249, CVE-2026-69248, CVE-2026-69247).
  The previous pin (46.0.x) was vulnerable to a Bleichenbacher PKCS#7 oracle,
  wildcard DNS name constraint bypass, and exponential certificate-path
  building. Version 50.0.0 is the minimum release that patches all three.

### Removed

- **`.archive/unused_files/secrets/fernet.key`** — committed Fernet key removed
  from the repository. Added `.archive/unused_files/secrets/` to `.gitignore`
  to prevent recurrence. The key was used only by archived/unused code and was
  not referenced by any active module.

## [0.1.0] — 2026-07-15

### Foundation release

- Metrics-first LLM evaluation framework with five-outcome classification
  (appropriate refusal, false refusal, safe useful compliance, unsafe
  compliance, ambiguous/partial)
- Deterministic mock provider for reproducible CI runs
- Wilson score confidence intervals and versioned metric snapshots
- Release-gate engine with critical-event precedence
- Ed25519-signed release dossiers
- Content-addressed, SHA-256 immutable evidence store
- Versioned Pydantic contracts and JSON Schema export
- FastAPI REST API with OIDC, CSRF, rate limiting, and security headers
- PostgreSQL RLS project isolation (14-table policy coverage)
- SQLite for local testing; PostgreSQL for production
- Operator GUI (loopback-bound) with endpoint, model, generation, chart, and
  report tabs
- Observability: 6 core SLIs, 13 alert rules, 9 dashboards, error budget
- Backup/restore with PITR and reconciliation verification
- Browser assurance suite (geometry, accessibility, zoom, containment)
- Supply-chain controls: SBOM, SAST, secret detection, Trivy, IaC scanning
- Threat model, ADRs, operational runbooks, and security assessments
- CI with pinned actions, build provenance attestation, and reproducible builds
