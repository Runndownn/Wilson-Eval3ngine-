# Changelog

All notable changes to Wilson Eval3ngine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 version numbers describe repository milestones; they do not constitute production certification.

## [Unreleased]

No unreleased changes are recorded after the `0.2.0` repository-narrative and version reconciliation.

## [0.2.0] — 2026-08-22

`0.2.0` is the first version number that describes the repository after the foundation slice grew into the current multi-surface evaluation platform. It does not invent intermediate releases: the work between `0.1.0` and `0.2.0` remains traceable through Git history, plans, assessments, and preserved documentation.

### Added

- Real-provider support and governed provider/model scope, including Azure OpenAI, Anthropic, Ollama, and approved local CLI adapters alongside the deterministic mock lane.
- Expectation compilation, hardened grading and calibration primitives, versioned metric snapshots, explicit compatible-population comparison logic, human review/adjudication workflows, and certification orchestration.
- Durable PostgreSQL-oriented scheduling, outbox/lifecycle support, row-level project isolation, content-addressed and encrypted evidence storage, audit/signing controls, and telemetry/observability surfaces.
- The five-workspace operator interface — **Endpoints → Models → Generate → Charts → Reports** — with endpoint/model inventory, bounded workload generation, chart evidence, and PDF/report review.
- Production-oriented identity and request-security controls: OIDC/MFA validation, exact role authorization, audited decisions, exact CORS, streaming body limits, shared Redis-backed rate-limit/revocation/idempotency authority, explicit trusted-proxy handling, and bounded client errors.
- Private-assurance and deployment boundaries including external secret authority, secure child credential transport, immutable image references, Caddy ingress policy, repository inventory, sanitized runtime-evidence envelopes, and security validation contracts.
- Native encrypted PostgreSQL backup, WAL, and point-in-time recovery implementation with cluster identity, KMS-backed envelope encryption, signed manifests, continuity checks, isolated restore execution, reconciliation, and recovery evidence.
- Governance/community infrastructure including contribution guidance, code of conduct, pull-request/issue templates, dependency update configuration, and maintained current-status/security documentation.
- Canonical GUI captures, architecture diagrams, the generation-workflow diagram, and the evidence-based July 14–August 22 development Gantt used by the root README.

### Changed

- Project status language now distinguishes **implemented source**, **integrated composition**, **observed automated assurance**, and **runtime assurance required** rather than treating source presence as production proof.
- Metric comparison uses an explicit two-sided pooled two-proportion test only for compatible independent-binomial populations; unsupported designs fail closed instead of receiving fabricated significance.
- Generic metric snapshots no longer infer prompt-family independence from run count. Family support must be supplied by actual lineage or remains zero for support checks.
- Executive support/uncertainty fields remain unknown when canonical evidence does not define them, and unknown gate vocabulary resolves to `indeterminate` rather than pass.
- API security controls were consolidated so each request-security concern has one supported implementation path rather than competing middleware authorities.
- Provider approval became explicit governance policy loaded from reviewed configuration for real destinations/models; source-controlled deterministic mock approval remains the local default.
- CLI provider execution now bounds output and disclosure, uses argv-only subprocess execution, and avoids returning sensitive stderr, exception text, prompts, credentials, or absolute executable paths as canonical metadata.
- Public documentation was reconciled against live source and historical material was moved or retained as provenance rather than silently rewritten as current truth.

### Fixed

- Operational-failure aggregation no longer double-counts diagnostic timeout/malformed subtypes.
- Cross-project analyst views reject missing or mismatched project scope before exposing metric/artifact lineage.
- Authorization decisions are persisted at the decision boundary and required audit failures block protected work.
- Shared Redis security-authority failures fail closed in assurance environments instead of silently degrading distributed controls.
- Proxy/browser trust, CORS, OIDC revocation, CSRF authority, idempotency intent binding, production secret handling, and public ingress behavior were hardened and aligned with the supported deployment contract.
- The historical changelog entry for `0.1.0` now reflects the actual July 14 foundation commit rather than later July/August capabilities.

### Assurance boundary

The repository contains substantial automated-test, security, browser, deployment, and recovery validation machinery, but workflow definitions and source code do not by themselves prove that an arbitrary deployment is production-ready. Provider credentials and behavior, IdP/JWKS state, proxy/TLS/firewall rules, Redis/PostgreSQL failure behavior, managed key custody, grader calibration, benchmark design, reviewer operations, backup cadence, WAL retention, destructive restore exercises, RPO/RTO, and release approval remain runtime/program evidence requirements.

## [0.1.0] — 2026-07-14

### Foundation framework

The initial `0.1.0` commit established the first complete deterministic vertical slice: versioned experiment/data contracts, a deterministic mock provider, five-outcome grading, Wilson score confidence intervals, threshold gates, content-addressed SHA-256 artifacts, Ed25519-signed release dossiers, SQLAlchemy-backed state/audit foundations, a development REST API and CLI, example experiments, tests, and architecture/runbook documentation.

Capabilities added after July 14 — including expectation compilation, hosted/private provider adapters, PostgreSQL RLS, encrypted evidence storage, the five-workspace GUI, private-assurance/deployment hardening, and native backup/WAL/PITR recovery — belong to the development path leading to `0.2.0`, not to the original foundation release.
