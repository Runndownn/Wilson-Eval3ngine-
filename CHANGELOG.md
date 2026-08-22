# Changelog

All notable changes to Wilson Eval3ngine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Encrypted PostgreSQL physical backup and PITR implementation** — `pg_basebackup`
  output is streamed directly through AES-256-GCM, with one-time data-encryption
  keys wrapped by the configured KMS and both plaintext/ciphertext identities
  retained for verification.
- **Production-oriented AWS KMS backup adapter** plus explicit opt-in local KMS
  support for hermetic development/recovery tests.
- **Signed backup/WAL manifests and signed recovery baselines** — Ed25519 signer
  trust, PostgreSQL system/timeline/WAL identity, KMS identity, object hashes,
  storage version, and expected restored-state populations are retained as
  recovery evidence.
- **Restart-durable backup catalogue** (`backup_catalog.v2.json`) with atomic
  filesystem updates and database/WAL/storage identity binding.
- **Real PostgreSQL WAL ingestion and continuity checking** using actual 24-hex
  WAL segment names rather than synthetic restore-plan entries.
- **Actual loopback-only PostgreSQL restore/PITR execution** with safe physical
  backup extraction, `pg_ctl` startup, recovery-target/promotion wait,
  post-restore reconciliation, shutdown, and measured restore evidence.
- **Dedicated `we3-backup` CLI** for full backup, WAL archive, catalogue listing,
  integrity verification, baseline capture, restore planning, and restore.
- **Migration `008_backup_evidence_v2`** to align persisted recovery schema with
  PostgreSQL system/timeline/WAL identity, ciphertext/manifest/signing fields,
  storage version, baseline identity, and explicit discrepancies.
- **Disposable PostgreSQL recovery CI exercise** that creates a real encrypted
  physical backup, mutates state, archives actual WAL, exercises missing-WAL,
  forged-signature, and ciphertext-corruption negatives, restores to a second
  loopback PostgreSQL instance, reconciles state, and retains runtime artifacts.
- **Current five-workspace GUI capture set** under `docs/assets/gui/current/` for
  Endpoints, Models, Generate, Charts, and Reports, with explicit point-in-time
  evidence/provenance guidance.
- **CONTRIBUTING.md** — comprehensive contributor guide covering environment
  setup, branch naming, commit conventions, testing, and PR process.
- **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1 adopted for all
  community interaction spaces.
- **CHANGELOG.md** — this file, tracking notable changes per release.
- **`.github/dependabot.yml`** — automated dependency update configuration for
  GitHub Actions, Python dependencies, GitHub Actions workflows, and Docker
  base images.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — PR template with security, testing,
  and documentation checklists.
- **`.github/ISSUE_TEMPLATE/bug_report.yml`** — structured bug report workflow.
- **`.github/ISSUE_TEMPLATE/feature_request.yml`** — structured feature request
  workflow.

### Changed

- **Backup/recovery status** moves from a fail-closed source scaffold to an
  implemented capability with a separate runtime-assurance boundary. The
  configured 15-minute RPO and four-hour RTO remain objectives until measured
  on the exact deployment.
- **Recovery reconciliation** now reads the actual `outbox_events` and
  `provenance_edges` tables and recomputes project audit chains using the same
  canonical hash function as normal audit persistence.
- **Recovery tests** no longer assert that restore is intentionally unimplemented.
  Unit tests cover encryption/trust/catalogue/WAL failures while the dedicated
  runtime job exercises a real PostgreSQL backup/PITR cycle.
- **Makefile recovery targets** now route through the explicit PostgreSQL/KMS-aware
  `we3-backup` interface rather than historical flat backup commands.
- **Backup and game-day runbooks** now distinguish component runtime evidence,
  scenario simulation, configured objectives, and production assurance. The
  game-day documentation now matches the source-defined 25 scenarios and
  current `we3 game-day --context ...` CLI.
- **Audit-service wording** now accurately identifies `AuditService.log_event()`
  as a non-blocking convenience wrapper; the underlying `AuditLedger.append()`
  remains the raising persistence primitive.
- **Operator documentation** follows the implemented five-step workflow
  (`Endpoints → Models → Generate → Charts → Reports`) instead of presenting
  six older point-in-time screenshots as current navigation.
- **GUI evidence guidance** distinguishes workspace inventory from model
  quality, provider health from behavioral outcomes, synthetic demo charts from
  run evidence, and PDF narratives from authoritative structured evidence.
- **GUI runtime documentation and lint coverage** account for runtime-injected
  `ux4`, `ux5`, and `ux6` browser overlays in addition to `enhanced.js`.
- **Documentation asset validation** validates WebP `RIFF/WEBP` signatures as
  well as PNG/SVG assets.

### Fixed

- **Issue #38 backup/PITR false-success paths** — backup metadata can no longer
  stand in for actual payload encryption, pathname strings no longer stand in
  for content integrity, synthetic WAL no longer stands in for archive
  coverage, and restore success now requires PostgreSQL recovery plus
  reconciliation.
- **Backup trust verification** — a valid manifest requires both a correct
  Ed25519 signature and a signer fingerprint explicitly trusted by the recovery
  trust registry; verification also authenticates/decrypts the payload.
- **Recovery schema drift** — reconciliation now uses the repository's real
  outbox/provenance/audit schema instead of searching unrelated audit JSON for
  those concepts.
- **Makefile cleanup scope** — recursive `__pycache__` removal belongs to
  `make clean` rather than running as a recovery-plan side effect.
- **GUI JavaScript lint gap** — `make lint` syntax-checks `ux5.js` and `ux6.js`,
  which are injected by the supported GUI runtime overlay.
- **Test collection in `tests/hostile/`** — added missing `__init__.py` package
  marker and corrected the import in `test_hostile_scenarios.py` from an
  absolute `tests.hostile.scenarios` import to a relative `.scenarios` import.
  The hostile test suite (39 tests) now collects and runs correctly.
- **Dependency vulnerability: `cryptography`** — upgraded the dependency floor
  from `>=46.0.0,<47.0.0` to `>=50.0.0,<51.0.0`, resolving CVE-2026-69249,
  CVE-2026-69248, and CVE-2026-69247.

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
- Operator GUI with endpoint, model, generation, chart, and report workspaces
- Observability: 6 core SLIs, 13 alert rules, 9 dashboards, error budget
- Backup/recovery data models, runbook, and early reconciliation scaffolding
- Browser assurance suite (geometry, accessibility, zoom, containment)
- Supply-chain controls: SBOM, SAST, secret detection, Trivy, IaC scanning
- Threat model, ADRs, operational runbooks, and security assessments
- CI with pinned actions, build provenance attestation, and reproducible builds
