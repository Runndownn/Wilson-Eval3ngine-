# Wilson Eval3ngine — Current Status

**Package version:** `0.1.0`  
**Project stage:** active evaluation platform / pre-production assurance  
**Authority:** this page describes the current `main` source tree; historical plans and point-in-time assessments are provenance, not current product truth.

## Status language

Repository source can establish that a control is implemented and composed. It cannot, by itself, establish production identities, secrets, provider behavior, network enforcement, certificate state, restore success, performance objectives, or the outcome of an unobserved workflow run.

| Term | Meaning |
|---|---|
| **Implemented** | Concrete source behavior exists. |
| **Integrated** | The behavior is composed into a supported path. |
| **CI-assured** | The exact revision has an observed successful automated check for the claim. |
| **Runtime assurance required** | Correctness depends on deployed infrastructure or executed evidence. |
| **Provisional** | A material implementation or evidence requirement is incomplete. |
| **Historical** | Provenance that is not current release truth. |

## Current implementation

### Evaluation, metrics, and evidence

The repository implements versioned experiment/dataset contracts, expectation compilation before provider output, deterministic and real-provider adapters, retry/attempt evidence, five-outcome grading, metric snapshots, Wilson intervals, release gates, content-addressed evidence, canonical report hashing, governed exports, Ed25519 dossier signing, and human review/adjudication primitives.

Metric comparison no longer returns a placeholder p-value. Compatible independent-binomial proportions use an explicit two-sided pooled two-proportion test; incompatible or indeterminate populations do not receive fabricated significance. The generic snapshot helper no longer treats run count as prompt-family independence: callers provide family lineage explicitly, otherwise the family count is zero so support logic can fail closed. `MetricEngine` also avoids double-counting timeout/malformed diagnostic subtypes in the aggregate operational-failure numerator.

Those changes do **not** make every experimental design independent-binomial. Paired, clustered, repeated-prompt, or other dependent designs require their corresponding calibrated statistical method and retained evidence.

### Persona views and reporting

Analyst construction rejects unscoped or cross-project canonical reports before copying metrics or artifact lineage. Executive support/uncertainty aggregates are represented as unknown (`None`) until `CanonicalReport` defines authoritative aggregate semantics; missing evidence is never converted into optimistic `100%` support or `0%` uncertainty. Unknown gate-status vocabulary fails closed to `indeterminate`. Reviewer redaction remains bounded pattern masking rather than a production DLP authority.

Cross-format report reconciliation uses the canonical report hash as an integrity/linkage control. Optional Parquet export fails explicitly when its optional dependency is unavailable rather than manufacturing an empty artifact.

### API security boundary

`src/wilson_eval3ngine/api/middleware.py` contains only shared observability, response-policy, content-type, and health primitives. Concrete request-security controls have one authoritative implementation:

- streaming byte limits: `api/body_limit.py`
- metadata validation, CSRF, exact CORS, distributed rate limiting, and OIDC revocation: `api/security_middleware.py`
- authorization-decision evidence: `api/authorization_audit.py`

Production composition no longer relies on import-time replacement of weaker middleware implementations. Historical import names resolve to the same concrete controls instead of preserving alternate security logic.

Staging/production rate limiting requires the configured Redis authority and fails closed when shared rate state is unavailable. Forwarded client identity is accepted only through configured trusted proxy ranges. OIDC uses one application authority with bounded validation and Redis-backed revocation. Authorization decisions are audited before protected work is allowed.

Bearer-header OIDC is non-ambient browser authentication, so credentialed CORS is not advertised by default. Exact origin/method/request-header allowlists remain enforced. CSRF validation remains available for any future ambient cookie/session-authenticated mutation path. Correlation/project metadata is normalized before structured logging so invalid attacker-controlled identifiers are not trusted as log context.

### GUI security boundary

The supported launcher defaults to loopback and installs exactly one reviewed API-key secret transport before the listener starts. UX/static overlay composition is presentation-only and cannot replace the selected transport. POSIX uses the one-shot FIFO transport; unsupported platforms fail closed unless an explicitly configured private transport plugin satisfies the factory contract.

Versioned `ux4`/`ux5`/`ux6` presentation assets remain the supported overlays. Unreferenced legacy `app.ts`, generated `app.js`, `styles.css`, and the orphaned TypeScript build configuration were removed from the live tree rather than kept as a second unused interface implementation.

### Backup, WAL, and point-in-time recovery

`src/wilson_eval3ngine/backup/` contains real encrypted PostgreSQL physical-backup and WAL-archive behavior. The current implementation includes PostgreSQL cluster/system identity capture, credential-safe `pg_basebackup`, encrypted payloads backed by the KMS interface, canonical manifests, Ed25519 signatures, ciphertext/plaintext integrity checks, trusted-key verification, WAL identity/continuity checks, signed recovery baselines, isolated loopback restore execution, post-restore reconciliation, audit-chain verification, and recovery evidence.

These capabilities still require target-environment exercises before an RPO/RTO or production-recoverability claim is valid. A configured objective is not observed evidence.

Recovery engineering constraints that remain visible until removed by implementation and tests include: same-timeline planning, the difference between archive-observation time and WAL record time, crash/concurrency-sensitive catalogue/publication paths, restore-target locking, and deterministic shell-safe recovery configuration. Runtime PostgreSQL recovery remains the authoritative reachability check for a timestamp target.

## Remaining assurance boundaries

### Synchronous operation state

Redis idempotency durably binds project/key/request intent, but the synchronous API `OperationRegistry` remains process-local. Durable long-running execution belongs to the PostgreSQL scheduler. A restart must fail safely rather than silently creating duplicate work.

### Bearer replay

Expiry, `jti`, and revocation invalidate bearer tokens; they do not sender-bind an otherwise valid bearer token. Proof-of-possession is a separate identity-provider and threat-model decision.

### Provider and CLI adapters

Real-provider correctness depends on provider API/CLI versions, destination policy, credential scopes, model availability, and target-environment negative testing. Provider stderr/stdout, prompts, credentials, and local executable paths are sensitive operational data and must remain bounded/redacted when adapters are evolved.

### Reviewer redaction

The built-in redactor is a convenience boundary for common patterns, not a complete sensitive-data discovery or DLP system.

## Automated assurance

The normal `CI` workflow is configured for pushes and pull requests to `main` and performs the repository lint target, tests, coverage gate, package build, and distribution inspection.

The `Security and quality assurance` workflow is configured for pushes to `main`, pull requests targeting `main`, security branches, and manual dispatch. It adds focused security contracts, privacy-safe repository inventory, the full non-runtime/non-browser test suite with branch coverage, distribution inspection, hermetic browser tests, and secure-Compose topology checks.

Workflow definitions are controls; their presence is not proof that a particular revision passed. This page does not claim a green revision unless that run has been observed.

## Production assurance boundary

A production deployment still needs independently retained evidence for at least:

- real IdP issuer/JWKS/key rotation and negative authentication cases
- proxy CIDRs, TLS, firewall, direct-port denial, and egress enforcement
- production Redis/PostgreSQL failure and concurrency behavior
- real KMS/signing/secret custody and rotation
- provider destinations and credential scopes
- backup cadence, WAL retention/continuity, destructive recovery exercises, measured RPO/RTO, and reconciliation
- calibrated graders, benchmark composition, statistical design, thresholds, reviewer operation, and release approvals
- alerting/SLO behavior under target workload

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` is the enduring boundary for public source evidence versus private deployment evidence.

## Documentation and provenance

`docs/Plans_/` and `docs/08-planning/Plans_/` are intentionally preserved historical planning records. They are not edited to make old forecasts appear current. Superseded point-in-time material may remain under `.archive/` for provenance. Current operator and architecture documents must describe the live `main` implementation and distinguish implementation from executed assurance.
