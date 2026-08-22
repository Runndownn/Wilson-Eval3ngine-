# Wilson Eval3ngine Features

Wilson Eval3ngine is an evidence-producing evaluation platform rather than a thin model-call benchmark script. Its capabilities are easiest to understand by asking what was defined, what executed, what behavior occurred, how it was measured, what decision rule was applied, and what evidence survives afterward.

This page describes **capability groups**, not blanket production certification. [Current Status](STATUS.md) records which portions are implemented, integrated, provisional, or runtime-assurance dependent.

## Evaluation contracts and reproducibility

Experiments, datasets, cases, provider requests/responses, classifications, metrics, thresholds, and dossiers use explicit versioned contracts. Dataset identity/version/split/hash relationships are validated before execution, while logical run identity incorporates score-affecting experiment/case/prompt/model/repetition/execution inputs.

Configuration therefore becomes part of the evidence rather than background context.

## Expectation-first evaluation

Expected treatment is compiled before the target model response is available. This prevents a persuasive/unexpected response from silently redefining what the evaluator intended to measure. Expectation failures remain execution/reliability evidence rather than being guessed after the fact.

## Provider abstraction and attempts

The provider layer includes a deterministic mock plus registration/adapters for hosted, Ollama/private, and supported CLI-backed model paths. The mock supports credential-free deterministic development; real adapters preserve the same higher-level evaluation contracts for authorized destinations.

Retries retain attempt records, error class, retryability, limits/backoff, and elapsed budget so provider instability is not confused with model refusal behavior.

## Five-outcome behavioral grading

WE3 distinguishes:

- appropriate refusal;
- false refusal;
- safe useful compliance;
- unsafe compliance;
- ambiguous/partial behavior.

Reliability state is separate from those labels. “The model refused” and “the provider never returned a valid response” are different engineering facts.

## Human review and adjudication

Review primitives include task creation, qualified assignment, blind dual review, recusal, abstention, disagreement handling, adjudication, and immutable review records. Automated grading is therefore not treated as autonomous release authority.

The analyst persona helper rejects canonical reports outside the authorized project scope before copying metrics/artifact lineage. Executive aggregate support/uncertainty fields remain provisional because the canonical report does not yet define authoritative aggregate contracts for them, and the reviewer regex redactor is baseline masking rather than a production DLP system.

## Metrics and uncertainty

Metric snapshots retain numerator, denominator, exclusions, run IDs, method/version metadata, and Wilson score intervals. A reviewer can see both the estimate and the evidence supporting it.

Comparison/drift primitives are also present, but two current limitations must stay visible: one comparison path still uses placeholder `p_value=0.5` pending completed bootstrap/reference significance work, and one snapshot helper approximates prompt-family count with run count. Do not use those provisional paths for certification-grade significance or independence claims.

## Deterministic release gates

The gate engine evaluates configured raw metrics and minimum-support rules with explicit `pass`, `warning`, `indeterminate`, and `block` outcomes. Critical unsafe-compliance evidence can block even when aggregate results look favorable, while insufficient support prevents an artificial pass.

Gate implementation is not threshold authority; organizational/benchmark policy still defines which thresholds are approved for a release program.

## Content-addressed evaluation evidence and signed dossiers

The deterministic path persists score-affecting artifacts in a content-addressed evidence store, records audit events, and generates signed dossier/report/result artifacts. The broader evaluation-evidence layer includes AES-256-GCM envelope-encryption and retention/legal-hold interfaces.

Development/local key handling is not equivalent to external production KMS/signing custody. The backup system described later reuses the same envelope-encryption principle but has a separate operational trust chain because a physical database backup has different size, WAL, restore, and recovery requirements from ordinary evaluation artifacts.

## Report serialization and reconciliation

Canonical reports have deterministic hashes and safe summary serialization. CSV export protects against common formula-injection prefixes. Cross-format reconciliation fails closed unless JSON, CSV, and HTML outputs carry the exact canonical report hash; it does not report unconditional success for unrelated representations.

Optional Parquet export writes report identity/hash plus metric rows when `pyarrow` is available. If the optional dependency is absent, export fails explicitly instead of returning an empty byte string that could be mistaken for a valid artifact.

Hash carriage proves shared representation identity, not independent semantic re-computation of every rendered field.

## Durable evaluation execution

The local evaluation service remains synchronous for deterministic development/CI. Separately, the persistence/execution layer implements PostgreSQL-backed durable scheduling with `FOR UPDATE SKIP LOCKED`, fenced lease ownership/versioning, heartbeats, bounded retry policy, poisoned/dead-letter transitions, and reconciliation support.

This lets the platform keep a simple local lane without pretending production execution must also be one synchronous process.

## Certification orchestration

Certification requirements are organized across reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability. Blocking/must requirements can prevent certification and the model is evidence-oriented rather than a free-form “looks good” decision.

Certification code existing does not mean a checkout/deployment is certified. Required evidence and approvals must be present for the exact target.

## Operator GUI

The current GUI has five workspaces:

**Endpoints → Models → Generate → Charts → Reports**

The supported launcher defaults to loopback and repairs historical wildcard defaults to `127.0.0.1` unless `WE3_GUI_ALLOW_REMOTE_BIND=1` is deliberately set. That explicit override permits non-loopback listening but does not provide authentication, authorization, TLS, or firewall policy; a remote deployment must independently supply and validate those controls.

The baseline browser page loads `enhanced.js`, while the supported runtime injects the `ux4`, `ux5`, and `ux6` overlays. Those files are active runtime layers rather than dead assets. Current screenshots and evidence-reading rules are in [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).

## Provider and credential protections

Provider handling differentiates public destinations from intentional local/private gateways, constrains credential-bearing redirect behavior, and avoids returning credential values in endpoint API responses. Local/private provider egress and remote GUI listening use separate explicit controls.

On the supported POSIX report-job path, one-shot protected secret transport replaces the historical regular plaintext temp-key file. These application controls do not replace operating-system identity security, secret management, provider-side scope/rotation, or network egress policy.

## Authentication, authorization, and project isolation

The platform includes OIDC support and project-scoped security controls. Production assurance still depends on the real issuer/JWKS, audience, claims, role/group mapping, database/object policies, revocation behavior, and negative authorization testing.

[Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md) documents that public implementation and private deployment evidence are separate domains.

## Hardened API and deployment controls

Production-oriented material includes Caddy ingress, API service, PostgreSQL, Redis, Prometheus, and Grafana with internal service networks. The API includes actual received-byte body limiting rather than trusting client-declared `Content-Length`, and deployment files contain explicit secret/configuration requirements and hardening choices.

A Compose/Docker/Terraform file is still a template until executed and verified. Exact image identity, TLS, firewall behavior, database/cache protection, identity, and egress enforcement require target-runtime evidence.

## Telemetry and observability

Telemetry/tracing modules provide correlation and operational instrumentation across evaluation stages. Prometheus recording/alert rules and dashboard/deployment material provide the source-side surface for monitoring.

Production SLO, alert-delivery, tracing-backend, and incident-response claims require observed runtime evidence rather than source presence alone.

## Encrypted PostgreSQL backup, PITR, and recovery

WE3 now implements an end-to-end native PostgreSQL recovery path instead of the earlier metadata-only scaffold. A physical backup begins by recording the PostgreSQL system identifier, timeline, WAL-segment size, LSN, and server identity. `pg_basebackup` then streams its tar output directly through AES-256-GCM encryption. A one-time 256-bit data-encryption key protects the stream, while the configured KMS stores only the wrapped form of that key. The repository includes an AWS KMS adapter for production-oriented use; the local KMS remains an explicit development/test option and cannot be selected accidentally through the backup CLI.

The encrypted object is not trusted merely because encryption completed. WE3 records both plaintext and ciphertext SHA-256 values, the ciphertext storage version, the bounded KMS identity, PostgreSQL identity, and recovery coordinates in a canonical manifest. The manifest is signed with Ed25519. Verification requires a trusted signer and then checks the manifest hash/signature, catalogue identity, ciphertext size/hash, KMS unwrap, AES-GCM authentication tag, and decrypted plaintext size/hash. A changed manifest, forged signature, changed ciphertext byte, wrong KMS key, or unauthenticated plaintext therefore causes verification to fail instead of producing a “valid” Boolean from metadata alone.

### Durable catalogue and actual WAL

Backup metadata is persisted in `backup_catalog.v2.json` under the backup root rather than existing only in process memory. Independent `we3-backup list`, verify, plan, and restore invocations can therefore operate over retained state. Catalogue writes are atomic on the local filesystem. This is durable across process restarts, but it is deliberately not described as a distributed multi-writer database or immutable object store; production storage durability, object lock, retention/legal hold, replication, and concurrency policy still belong to the deployment.

WAL archival accepts actual completed PostgreSQL WAL files. Their 24-hex filenames are parsed according to the recorded cluster WAL-segment size, and every segment is bound to the same PostgreSQL system identifier and timeline as the base backup. Restore planning uses those real filenames, sorts them by PostgreSQL sequence, requires coverage to begin at the base backup's ending segment, and rejects gaps or insufficient coverage through the requested timestamp/LSN. The earlier synthetic `segment_0` style planning no longer exists in the supported path.

### Signed recovery baseline and schema-aware reconciliation

Before a protected recovery point is approved, WE3 can capture a signed recovery baseline. The baseline records expected run, classification, metric-snapshot, gate-decision, provenance-edge, and pending-outbox populations plus the terminal audit-chain root for each project. Audit chains are recomputed with the same canonical function used by normal audit writes; a baseline cannot be signed from a broken chain.

After restore, reconciliation reads the real persistence schema. Pending delivery work comes from `outbox_events`, provenance comes from `provenance_edges`, and audit events are cryptographically recomputed rather than accepted because an `event_hash` column is non-empty. Restored counts and project audit roots are compared with the trusted baseline, and every discrepancy remains explicit in the reconciliation artifact.

### Actual isolated restore

The recovery orchestrator decrypts and authenticates the selected full backup and WAL objects, safely extracts the physical backup into an empty data directory, writes PostgreSQL recovery settings, starts the restored server on loopback with `pg_ctl`, waits for the requested recovery point and promotion, and requires reconciliation to pass. A startup failure, missing WAL, target that cannot be reached, signature/KMS/integrity error, or reconciliation difference prevents a successful result. The restored server is stopped after the exercise, including failure paths.

The restore evidence records measured duration, PostgreSQL/tool versions, restore-log hash, and reconciliation result. This distinction is important: the repository's 15-minute RPO and four-hour RTO are objectives, while the duration of an executed recovery exercise is evidence. A source constant cannot prove an SLO.

### Recovery CLI and runtime validation

The supported recovery interface is the dedicated `we3-backup` CLI. It requires PostgreSQL and explicit KMS/signing/trust configuration rather than silently falling back to SQLite or a development key. See [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) for the complete operator workflow.

A dedicated CI runtime job exercises the real path against disposable PostgreSQL: physical encrypted backup, state mutation, real WAL archival, negative corruption/signature/missing-WAL cases, restore to a second loopback database, and reconciliation. That is strong evidence about the tested commit and CI environment. It is not a substitute for a production recovery exercise on the target database size, storage system, KMS, network boundary, and operational process.

The current native streaming path intentionally rejects PostgreSQL clusters with user-defined tablespaces. Safe reconstruction of external tablespace topology requires deployment-specific storage mapping; such deployments should use their platform-native backup service until that mapping is implemented rather than accept an incomplete physical backup.

## Visual analytics

The chart system includes confidence intervals, response-time distributions/trends, prompt-level heatmaps, token views, outcome distributions, radar comparisons, cross-run comparisons, timelines, and related analytical views.

Charts are for pattern recognition. Exact values and provenance come from structured metric/evidence sidecars. GUI **demo charts are synthetic** and must not be promoted into real benchmark evidence.

## What WE3 deliberately avoids claiming

WE3 does not claim that:

- a model is safe outside the tested population;
- a high aggregate score overrides a critical safety event;
- provider failure is a refusal;
- a screenshot is a metric snapshot;
- a PDF is the entire release dossier;
- a source file proves private deployment security;
- implementing KMS-backed backup encryption proves a deployment's KMS policy or key custody;
- a configured RPO/RTO is an observed recovery result;
- a disposable CI restore proves production disaster-recovery readiness;
- a restore plan means a restore executed;
- automated judging removes accountable human release authority;
- historical Plans/TODOs or old test reports are current runtime evidence.

For exact implementation/assurance state read [Current Status](STATUS.md); for component relationships read [Architecture](ARCHITECTURE.md).
