# Wilson Eval3ngine — Current Status

**Package version:** `0.1.0`  
**Project stage:** active evaluation platform / pre-production assurance  
**Authority:** this page describes the current `main` source tree; historical plans and point-in-time assessments are provenance, not current product truth.

## How to read status

Repository source can establish that a control is implemented and composed. It cannot, by itself, establish production identities, secrets, provider behavior, network enforcement, certificate state, restore success, performance objectives, or the outcome of a workflow run that has not been observed.

| Term | Meaning |
|---|---|
| **Implemented** | Concrete source behavior exists. |
| **Integrated** | The behavior is composed into a supported execution path. |
| **CI-assured** | The current revision has an observed successful automated check for the claim. |
| **Runtime assurance required** | Correctness depends on the deployed environment or executed evidence. |
| **Provisional** | A material implementation or evidence requirement is still incomplete. |
| **Historical** | Useful provenance that is not current release truth. |

## Current architecture

### Evaluation and evidence

The repository implements versioned experiment/dataset contracts, expectation compilation before provider execution, deterministic and real-provider adapters, retry/attempt evidence, five-outcome grading, metric snapshots, Wilson intervals, release gates, content-addressed artifacts, canonical report hashing, governed exports, Ed25519 dossier signing, and human review/adjudication primitives.

The deterministic local lane is intentionally credential-free and repeatable. It demonstrates the core measurement contract, not production certification of every provider, policy, identity system, storage backend, or deployment.

### API security boundary

`src/wilson_eval3ngine/api/middleware.py` now contains only shared observability, response-policy, content-type, and health primitives. Concrete request-security controls have one authoritative implementation:

- streaming byte limits: `api/body_limit.py`
- metadata validation, CSRF, exact CORS, distributed rate limiting, and OIDC revocation: `api/security_middleware.py`
- authorization decision evidence: `api/authorization_audit.py`

Production composition no longer depends on import-time replacement of weaker middleware classes. Historical import names resolve to the same concrete implementations rather than maintaining alternate control logic.

Staging/production rate limiting requires the configured Redis authority and fails closed when shared rate state is unavailable. Forwarded client identity is accepted only through configured trusted proxy ranges. OIDC uses one application authority with bounded validation and Redis-backed revocation. Authorization decisions are audited before protected work is allowed.

Bearer-header OIDC is non-ambient browser authentication, so credentialed CORS is not advertised by default. Exact origin, method, and request-header allowlists remain enforced. CSRF validation remains available for any future ambient cookie/session-authenticated mutation path.

### GUI security boundary

The supported GUI launcher defaults to loopback and installs exactly one reviewed API-key secret transport before the listener starts. UX/static overlay composition is presentation-only and cannot replace the selected transport. POSIX uses the one-shot FIFO transport; unsupported platforms fail closed unless an explicitly configured private transport plugin satisfies the factory contract.

Versioned `ux4`/`ux5`/`ux6` presentation assets are injected by the supported overlay. Unreferenced legacy TypeScript/JavaScript/CSS build remnants have been removed from the live static tree rather than retained as a second interface implementation.

### Backup, WAL, and point-in-time recovery

`src/wilson_eval3ngine/backup/` contains real encrypted PostgreSQL physical-backup and WAL-archive behavior rather than placeholder scaffolding. The current implementation includes:

- PostgreSQL cluster/system identity capture
- credential-safe `pg_basebackup` invocation
- AES-256-GCM encrypted payloads backed by the configured KMS interface
- canonical manifests, Ed25519 signatures, ciphertext/plaintext integrity checks, and trusted-key verification
- WAL segment identity/continuity validation on the selected timeline
- signed recovery baselines
- isolated loopback restore execution and PostgreSQL promotion to a requested target
- post-restore reconciliation, audit-chain verification, and durable recovery evidence

These capabilities still require target-environment exercises before an RPO/RTO or production-recoverability claim is valid. A configured RPO/RTO is a target, not observed evidence.

Known recovery engineering constraints that must remain visible until removed by implementation and tests: the planner currently operates on one PostgreSQL timeline; archive-observation time is not equivalent to a WAL record timestamp; backup catalogue/manifest publication and restore-target locking should be treated as crash/concurrency-sensitive paths; and recovery configuration must remain deterministic and shell-safe. Runtime restore success is the authoritative reachability check for a time target.

## Known source-level limitations

### Statistical comparison

One comparison path in `metrics/engine.py` still uses a placeholder significance value, and one snapshot path approximates prompt-family independence. Certification-grade significance and independence claims must use a completed, validated statistical path rather than those provisional values.

### Executive aggregate semantics

The executive view contains provisional aggregate support/uncertainty semantics because the canonical report contract does not yet expose an authoritative aggregate for those fields. They must not be presented as independently measured evidence.

### Synchronous operation state

Redis idempotency durably binds project/key/request intent, but the synchronous API `OperationRegistry` remains process-local. Durable long-running execution belongs to the PostgreSQL scheduler. A restart must fail safely rather than silently creating duplicate work.

### Bearer replay

Expiry, `jti`, and revocation invalidate bearer tokens; they do not sender-bind an otherwise valid token. Proof-of-possession is a separate identity-provider and threat-model decision.

### Reviewer redaction

The built-in reviewer redaction helper is bounded pattern masking, not a complete production DLP system.

## Automated assurance

The normal `CI` workflow runs on pushes and pull requests to `main` and performs the repository lint target, tests, coverage gate, package build, and distribution inspection.

The `Security and quality assurance` workflow now also runs on pushes to `main`, pull requests targeting `main`, security branches, and manual dispatch. It adds focused security contracts, privacy-safe repository inventory, the full non-runtime/non-browser test suite with branch coverage, distribution inspection, hermetic browser tests, and secure-Compose topology checks.

Workflow definitions are controls; their presence is not proof that a particular revision passed. This status page does not claim a green revision unless that run has been observed.

## Production assurance boundary

A production deployment still needs independently retained evidence for at least:

- real IdP issuer/JWKS/key rotation and negative authentication cases
- proxy CIDRs, TLS, firewall, direct-port denial, and egress enforcement
- production Redis/PostgreSQL failure and concurrency behavior
- real KMS/signing/secret custody and rotation
- provider destinations and credential scopes
- backup cadence, WAL retention/continuity, destructive recovery exercises, measured RPO/RTO, and reconciliation
- calibrated graders, benchmark composition, thresholds, reviewer operation, and release approvals
- alerting/SLO behavior under target workload

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` is the enduring boundary for public source evidence versus private deployment evidence.

## Documentation and provenance

`docs/Plans_/` and `docs/08-planning/Plans_/` are intentionally preserved as historical planning records and are not edited to make old forecasts look current. Superseded point-in-time material may remain under `.archive/` for provenance. Current operator and architecture documents must describe the live `main` implementation and distinguish implementation from executed assurance.
