# Security Policy

## Current security position

Wilson Eval3ngine `0.1.0` is an **active evaluation platform in pre-production assurance**. The repository contains substantial security, identity, evidence-protection, deployment, recovery, and certification implementations, but source code alone does not certify a production environment. Production use must satisfy the applicable repository checks plus the private runtime-assurance contract for the exact deployment.

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
- A restore plan is not proof that a restore executed; successful recovery requires the restore target to be reached and reconciliation to pass.
- Repository implementation is not deployment proof; required runtime evidence must be executed and retained.

## Authentication and authorization

The production-oriented API includes OIDC/JWT validation, JWKS handling, workload-identity concepts, role-based authorization, project scope, and database/project-isolation controls. Development modes exist for local work but must not be treated as production identity.

A real deployment owns its approved issuer, JWKS endpoint, audience, claims, groups/roles, MFA policy, revocation behavior, workload identities, database row policies, object policies, and negative authorization tests. Do not publish those private values merely to document that a feature exists.

The analyst-view helper also enforces that a canonical report's project matches the authorized project scope before copying metrics or artifact lineage. That defense-in-depth check does not remove the requirement for API/service authorization and database/object-store isolation.

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

Credentials must not be committed, logged, returned through endpoint APIs, pasted into issue/PR text, or placed in regular plaintext report-key files. Local GUI state uses encrypted credential storage under the operating-system account; this protects some accidental/offline disclosure cases but is not equivalent to an external production secret manager.

On supported POSIX systems, the supported keyed report-job path uses a one-shot FIFO inside a restrictive directory rather than the historical regular temporary file. Production deployment should use its approved secret authority and platform-appropriate protected process-to-process transport.

## Input and browser protections

The API includes content-type/project/idempotency validation and an ASGI receive-channel body limiter that counts actual received bytes rather than trusting `Content-Length`. Browser-facing controls include restrictive security headers, CSRF/CORS protections where applicable, inert-rendering rules, and bounded operator/session assumptions.

Untrusted prompts, outputs, attachments, report text, Markdown, filenames, and provider metadata must never be treated as executable instructions simply because they were generated by a model. Browser assurance should include XSS/inert-rendering, keyboard/accessibility, zoom/layout, origin controls, and bounded WebSocket/message behavior where relevant.

## Evidence, audit, reporting, and cryptography

The evaluation path uses content-addressed artifacts, audit-chain primitives, and Ed25519 signing for dossier integrity. The broader evaluation-evidence storage layer includes AES-256-GCM envelope-encryption behavior and retention/legal-hold interfaces.

The backup path now applies the same envelope-encryption principle to physical PostgreSQL data through a streaming implementation appropriate for large backups. `pg_basebackup` stdout is encrypted directly with a one-time AES-256-GCM data key, while the configured KMS retains the wrapped DEK. The signed canonical manifest binds plaintext/ciphertext hashes, KMS identity, PostgreSQL system/timeline/WAL identity, and storage version. Verification requires a trusted signer and then verifies manifest hash/signature, ciphertext identity, KMS unwrap, AEAD authentication, and decrypted plaintext identity.

The repository includes an AWS KMS adapter for production-oriented backup use. `LocalKMSClient` remains development/test only, and the backup CLI requires an explicit opt-in before selecting it. A production deployment must still prove its KMS IAM policy, key rotation/revocation/custody, storage durability, retention, object lock/legal hold where required, and recovery authorization in the target environment.

Cross-format report reconciliation requires JSON, CSV, and HTML representations to carry the exact canonical report hash. This is a representation-integrity check; it is not a substitute for validating the meaning of every rendered field.

### Audit failure semantics

The persistent `AuditLedger` raises when an append fails. `AuditService.log_event()` is a higher-level **non-blocking** wrapper: it catches that exception, logs `audit_event_failed`, and returns an empty string. Code that requires audit persistence as a precondition for a security-sensitive operation must therefore check the returned event hash or call the ledger/another fail-closed policy boundary; it must not assume the `AuditService` wrapper automatically aborts the surrounding operation. This is intentionally stated plainly because calling the current wrapper “fail-closed” would misdescribe its behavior.

Recovery reconciliation does not rely on the presence of non-empty event-hash fields. It recomputes each project's chain using the same canonical event-hash function used by normal audit writes and requires the terminal roots to match the trusted signed recovery baseline.

## Backup and recovery security boundary

The native recovery path is now implemented, but its security properties depend on several independent checks rather than a single success flag.

A backup is eligible for restore only when its catalogue identity, canonical manifest hash, Ed25519 signature, trusted signer fingerprint, ciphertext SHA-256/size, KMS-wrapped key, AES-GCM tag, decrypted plaintext SHA-256/size, PostgreSQL system identifier, timeline, and WAL properties agree. Actual PostgreSQL WAL files are archived through the same encrypted/signed model, and restore planning rejects a missing base segment, timeline mismatch, or non-contiguous sequence instead of inventing placeholder WAL names.

A restore is loopback-only, requires an empty data directory, authenticates/decrypts every selected object, safely extracts the physical backup, configures PostgreSQL recovery, starts the restored server with `pg_ctl`, waits for the requested timestamp/LSN and promotion, and then reconciles the restored state to a trusted signed baseline. Pending outbox state comes from the actual `outbox_events` table, provenance comes from `provenance_edges`, and audit chains are recomputed cryptographically. A discrepancy prevents a successful recovery result.

The dedicated operator interface is `we3-backup`; it does not silently fall back to SQLite or a local development KMS. See [`docs/operations/backup-recovery-runbook.md`](docs/operations/backup-recovery-runbook.md) for the workflow and failure interpretation.

These source controls still do not prove production disaster recovery. A production claim additionally needs evidence about the real KMS authority, backup storage durability/immutability/replication, PostgreSQL archive operation, database size and workload, network isolation, restore duration, external artifact stores, operator approvals, and return-to-service process. The configured 15-minute RPO and four-hour RTO remain objectives until measured on that environment.

The current native streaming path rejects user-defined PostgreSQL tablespaces because restoring external tablespace topology safely requires deployment-specific storage mapping. Treat that rejection as a safety boundary rather than disabling it to force an unsupported restore.

## Production-oriented deployment

The repository includes hardened Docker/Compose material with Caddy as intended published ingress and API, PostgreSQL, Redis, Prometheus, and Grafana on internal service networks. Required configuration is explicit and production identity is intended to use OIDC rather than development headers.

Deployment source is a template, not runtime evidence. Before production approval, validate exact image digests, TLS, only-proxy ingress, database/cache authentication/transport, filesystem/container permissions, egress default-deny behavior, health/readiness, real backup/restore behavior, observability, and failure handling using the authorized environment.

## Certification and assurance

The repository contains certification orchestration across reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability. A certification result is valid only when the required evidence for the exact release is present, verified, and meets blocking requirements.

Private runtime evidence such as real identities, certificates, provider destinations, raw scanner output, logs, packet captures, test accounts, KMS/object metadata, and restore topology should remain outside the public repository. Follow [`docs/security/PRIVATE_RUNTIME_ASSURANCE.md`](docs/security/PRIVATE_RUNTIME_ASSURANCE.md) to publish only bounded statuses/fingerprints when public traceability is required.

## Historical security material

[`docs/security/MASTER_SECURITY_ASSESSMENT.md`](docs/security/MASTER_SECURITY_ASSESSMENT.md) is a point-in-time assessment dated 2026-08-01 and should be read against the branch/head it reviewed. Recovery implementation added after that assessment does not retroactively change what the historical assessment observed. ADRs, Plans/TODOs, evidence inventories, and Phase-1 reports likewise preserve useful history but do not automatically describe the latest implementation or runtime state.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner or the organization's approved security intake. Include the affected version/commit, a minimal synthetic reproduction, impact, and suggested containment when possible. Do not include real secrets, private topology, harmful evidence, or sensitive user/provider data in public issue trackers.
