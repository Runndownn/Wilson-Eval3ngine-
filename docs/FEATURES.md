# Wilson Eval3ngine Features

Wilson Eval3ngine is an evidence-producing evaluation platform, not a thin model-call benchmark. It preserves what was defined, what executed, what behavior occurred, how it was measured, what decision rule was applied, and what evidence survives afterward.

This page describes implemented capability groups. [Current Status](STATUS.md) is the authority for implementation, integration, automated-assurance, and runtime-assurance boundaries.

## Evaluation contracts and reproducibility

Experiments, datasets, cases, provider requests/responses, classifications, metric results, release gates, reports, and dossiers use explicit contracts. Dataset identity/version/split/hash relationships are validated before execution, while score-affecting configuration participates in evidence lineage.

Expected treatment is compiled before the target response is observed. A persuasive or unexpected model response therefore cannot silently redefine what the evaluator intended to measure.

## Providers and attempt evidence

The provider layer includes a deterministic mock plus hosted, private/local, and CLI-backed adapters. Attempts preserve failure class, retryability, backoff/budget information, and response evidence so provider instability is not confused with model behavior.

CLI-backed adapters invoke argument vectors without a shell and no longer copy raw stderr, absolute executable paths, or raw exception text into canonical response metadata. Stderr is represented by presence and a SHA-256 digest. Some configured upstream CLI contracts still place prompts in process arguments; on those paths, same-user process inspection remains part of the trusted-host boundary until an upstream stdin-only contract is available.

## Five-outcome behavioral grading

WE3 distinguishes appropriate refusal, false refusal, safe useful compliance, unsafe compliance, and ambiguous/partial behavior. Reliability failures remain separate. A timeout is not treated as a refusal and malformed/provider errors are not behavioral outcomes.

## Human review and adjudication

Review primitives cover task creation, qualification-aware assignment, blind dual review, recusal, abstention, disagreement, adjudication, and immutable review evidence. Automated grading is therefore not treated as autonomous release authority.

Analyst views reject missing or cross-project canonical scope before copying metrics or artifact lineage. Executive aggregate support/uncertainty values are represented as unknown until the canonical report defines authoritative aggregate semantics; the platform does not fabricate `100%` support or `0%` uncertainty. Reviewer regex redaction is bounded pattern masking, not a complete DLP authority.

## Metrics, uncertainty, and comparisons

Metric snapshots retain numerator, denominator, exclusions, run IDs, method/version metadata, prompt-family support where known, and Wilson confidence intervals.

Compatible independent-binomial proportions use an explicit two-sided pooled two-proportion significance test. Incompatible definitions/populations and zero-support comparisons remain indeterminate or incompatible and do not receive fabricated p-values. Paired, clustered, repeated-prompt, or otherwise dependent designs require the statistical method appropriate to that design.

The generic snapshot helper never infers prompt-family independence from run count. Callers provide family lineage explicitly; when it is unavailable, independent-family support is recorded as zero so downstream support rules can fail closed.

Operational failure subtypes such as timeout and malformed response remain diagnostic subsets of the aggregate provider-failure count and are not double-counted in the aggregate failure metric.

## Deterministic release gates

The gate engine evaluates configured metrics and minimum-support rules with explicit `pass`, `warning`, `indeterminate`, and `block` outcomes. Critical unsafe-compliance evidence can block even when aggregate results look favorable; insufficient support cannot become an artificial pass.

Gate code is not threshold authority. Approved benchmark composition, policy, minimum support, and release thresholds remain program-specific governance inputs.

## Evidence, reports, and signed dossiers

The deterministic path persists score-affecting artifacts in content-addressed storage, records audit evidence, and generates report/dossier/result artifacts. The broader evidence layer includes AES-256-GCM envelope encryption and retention/legal-hold interfaces.

Canonical reports have deterministic hashes. CSV serialization protects against formula injection. JSON/CSV/HTML reconciliation requires the canonical report hash to survive representation. Optional Parquet export fails explicitly when its optional dependency is unavailable rather than producing an empty artifact.

Hash carriage is an integrity/linkage control; it is not independent semantic recomputation of every rendered field.

## Durable execution

The local evaluation service remains intentionally simple for deterministic development. Separately, the persistence/execution layer implements PostgreSQL-backed scheduling with fenced leases, `FOR UPDATE SKIP LOCKED`, heartbeats, bounded retries, dead-letter handling, and reconciliation primitives.

Redis-backed API idempotency binds project, key, and request intent. The synchronous operation registry remains process-local; durable long-running work belongs to the PostgreSQL scheduler.

## Authentication, authorization, and API hardening

The supported API has one authoritative implementation for each request-security control rather than weaker duplicate middleware that is replaced at import time.

Implemented controls include:

- actual ASGI received-byte body limits;
- exact request-metadata validation;
- exact CORS origin/method/header allowlists;
- bound CSRF protection for ambient credential paths;
- distributed Redis-backed rate limiting with trusted-proxy CIDRs and assurance-mode fail-closed behavior;
- OIDC validation and Redis-backed revocation;
- exact role/project authorization;
- pre-side-effect authorization decision audit;
- bounded client-safe unexpected errors;
- CSP/HSTS/COOP/CORP/COEP and related response controls;
- centralized sensitive-log redaction.

Bearer-header OIDC is non-ambient authentication, so credentialed CORS is not advertised by default. `jti`, expiry, and revocation invalidate bearer tokens but do not sender-bind an otherwise valid token; proof-of-possession is a separate identity-provider design decision.

## Operator GUI and secret transport

The supported launcher defaults to loopback. Remote binding requires an explicit operator override and does not itself add authentication, TLS, firewalling, or multi-user isolation.

The launcher installs exactly one reviewed API-key secret transport before serving. Presentation overlays cannot replace that transport. POSIX uses a one-shot FIFO path; unsupported platforms fail closed unless a configured private plugin satisfies the transport factory contract.

The active browser composition uses the baseline page plus `enhanced` and versioned `ux4`/`ux5`/`ux6` layers. Orphaned `app.ts`/generated `app.js`/`styles.css` and their unused TypeScript build configuration have been removed from the live tree.

## Encrypted PostgreSQL backup, WAL, and PITR recovery

The native recovery subsystem is substantive implementation rather than metadata-only scaffolding. It includes:

- PostgreSQL cluster/system/timeline/WAL identity capture;
- credential-safe `pg_basebackup` execution;
- AES-256-GCM encrypted physical backup and WAL objects through the KMS interface;
- canonical signed manifests and trusted-key verification;
- plaintext/ciphertext integrity checks;
- WAL segment identity and continuity validation;
- signed recovery baselines;
- isolated loopback restore execution and recovery promotion;
- reconciliation and audit-chain verification;
- measured recovery evidence.

Source capability is not proof of recoverability for a deployment. Operators still need executed backup cadence, WAL retention/continuity, destructive restore exercises, target reachability, reconciliation, and measured RPO/RTO evidence.

Current engineering limitations remain visible in [Current Status](STATUS.md): same-timeline planning, archive-observation time versus WAL record time, crash/concurrency-sensitive publication/catalogue paths, restore-target locking, and deterministic recovery configuration are areas where source/runtime assurance must remain precise.

## Hardened deployment and observability

Production-oriented Compose/Caddy material keeps PostgreSQL, Redis, monitoring, and the API off direct public host ports and uses explicit internal network boundaries and mounted/private secret authority. These files remain templates until target TLS, firewalling, proxy ranges, egress policy, image identity, secret custody, and direct-port denial are executed and verified.

Telemetry, tracing, Prometheus rules, dashboard material, and runtime evidence helpers provide the source-side observability surface. Production SLOs, alert delivery, retention, and incident-response claims require observed runtime evidence.

## Certification orchestration

Certification requirements span reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability. Blocking requirements prevent certification when required evidence is missing.

Certification code existing does not certify a checkout or deployment. Evidence and approvals must belong to the exact target and revision.

## What WE3 deliberately does not claim

WE3 does not claim that a model is safe outside the tested population, that a high aggregate score overrides critical safety evidence, that a provider failure is a refusal, that a screenshot is a metric snapshot, that source files prove private deployment security, that a configured recovery objective was achieved, or that historical plans/test reports are current runtime evidence.

For exact implementation and assurance state read [Current Status](STATUS.md). For component relationships read [Architecture](ARCHITECTURE.md). For the public/private evidence boundary read [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md).
