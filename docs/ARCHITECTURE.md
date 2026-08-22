# Wilson Eval3ngine Architecture

This document describes the live architecture on `main`. Historical plans remain provenance; [Current Status](STATUS.md) is the authority for implementation and assurance boundaries.

## Architectural principle

WE3 is an evidence-producing evaluation platform. The central path validates versioned inputs, fixes the expected treatment before provider execution, records attempts and reliability state, classifies terminal behavior, computes versioned statistics, evaluates explicit gates, and preserves enough evidence to reconstruct the decision later.

A second principle governs operational code: **one supported authority per control**. Security, secret transport, measurement, and recovery behavior should not depend on parallel weaker implementations or import-time replacement tricks.

<p align="center"><img src="assets/diagrams/system-architecture.svg" alt="Wilson Eval3ngine system architecture" width="1100"></p>

## Evaluation data flow

<p align="center"><img src="assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evidence-first evaluation pipeline" width="1100"></p>

### Contracts and expectation compilation

`src/wilson_eval3ngine/domain/` contains the versioned contracts and state definitions. Experiment and dataset identity/version/hash relationships are validated before execution. `expectations/` compiles expected treatment before the target response exists, preventing the observed answer from redefining the evaluation target after the fact.

### Rendering, identity, and provider execution

`execution/` owns rendering/idempotency support. Score-affecting configuration participates in logical work identity so duplicate/replayed work can be detected.

`providers/` defines deterministic, hosted, private/local, and CLI-backed adapters. Attempts preserve failure class, retryability, backoff/budget data, and response evidence. Provider failure remains a reliability outcome, not a behavioral label.

CLI-backed adapters use argv-only subprocess execution with `shell=False`. Canonical response metadata does not retain raw stderr, raw exception strings, or absolute executable paths; stderr is represented by bounded integrity metadata. Where an upstream CLI contract itself requires prompt text in argv, same-user process inspection remains part of the trusted-host boundary.

### Grading, review, and persona views

`grading/` maps valid terminal behavior into the five behavioral families while leaving malformed/provider failures outside behavioral counts. `review/` implements qualified assignment, blind review, recusal, abstention, disagreement, adjudication, and immutable review evidence.

`ui/` builds persona-specific views. Analyst construction fails closed on missing/cross-project scope. Executive support and uncertainty aggregates remain unknown until the canonical report defines authoritative aggregate semantics; unknown data is not transformed into optimistic constants.

### Metrics, statistics, and release gates

`metrics/`, `statistics/`, and `gates/` separate measurement from policy decisions. Metric results retain numerator, denominator, exclusions, versions, population lineage, and confidence intervals.

Compatible independent-binomial proportions use an explicit two-sided pooled two-proportion significance test. That method is not evidence for paired, clustered, repeated-prompt, or otherwise dependent designs; those require their matching calibrated method. The generic snapshot helper does not infer prompt-family independence from run count. Unknown family lineage produces zero independent-family support so support gates can fail closed.

Operational failure subtypes such as timeout/malformed remain diagnostic subsets and are not added a second time to the aggregate provider-failure numerator.

Gate rules then apply explicit thresholds/minimum-support requirements with `pass`, `warning`, `indeterminate`, and `block` semantics. Threshold authority belongs to the approved evaluation program, not the existence of the gate engine itself.

### Evidence, reports, audit, and signing

`evidence/`, `reports/`, `security/`, and `storage/` provide content-addressed evidence, canonical report hashing, safe serialization, signing, encryption, retention/legal-hold interfaces, and linked audit evidence.

Cross-format report reconciliation uses the canonical report hash as a representation-integrity/linkage control. It does not pretend that carrying the same hash independently proves every rendered field. Signing establishes artifact identity/integrity; managed production key custody remains a deployment assurance concern.

### Durable scheduling

The deterministic lane can use SQLite and a synchronous evaluation service for local development/CI. Production-oriented state is PostgreSQL-compatible. `persistence/scheduler.py` implements fenced leases, `FOR UPDATE SKIP LOCKED`, heartbeats, bounded retries, dead-letter transitions, and reconciliation.

The API's synchronous `OperationRegistry` remains process-local. Redis idempotency durably binds project/key/request intent, but horizontally scaled/restart-resilient long-running execution belongs to the PostgreSQL scheduler.

## API security architecture

The supported API request boundary is composed from one authoritative implementation per control:

```text
public client
    |
    v
Caddy TLS / ingress boundary
    - public ports only here
    - internal diagnostics/schema surfaces blocked
    - forwarded client identity normalized
    |
    v
ASGI request boundary
    - streaming received-byte limit
    - request metadata/content-type validation
    - exact CORS/preflight policy
    - Redis-authoritative rate admission
    |
    v
OIDC authentication / revocation
    - issuer/audience/lifetime/claim validation
    - app-lifetime authenticator
    - shared Redis revocation state
    |
    v
exact project/role authorization
    - no implicit administrative bypass
    - durable allow/deny evidence
    |
    v
project-scoped application and persistence behavior
```

Shared logging, tracing, security headers, content-type checks, and readiness primitives live in `api/middleware.py`. Streaming body enforcement lives in `api/body_limit.py`. Metadata validation, CSRF, strict CORS, distributed rate limiting, and OIDC revocation live in `api/security_middleware.py`. Authorization decision evidence lives in `api/authorization_audit.py`.

Production composition does not rely on import-time monkey-patching of weaker alternatives. Historical import aliases resolve to the same canonical concrete classes.

Redis is authoritative shared security state for production request admission/revocation/idempotency. Assurance environments fail closed when required shared state cannot make the decision. Forwarded client identity is trusted only when the direct peer is within configured trusted proxy CIDRs.

Bearer-header OIDC is non-ambient browser authentication; credentialed CORS is therefore not advertised by default. CSRF remains available for ambient cookie/session mutation paths. Expiry, `jti`, and revocation invalidate bearer tokens but do not sender-bind a valid bearer token; proof-of-possession is a separate identity-provider design decision.

## GUI architecture and secret boundary

The operator GUI is an administrative control plane. The supported launcher defaults to loopback and installs exactly one reviewed API-key secret transport before serving. The UX overlay is presentation-only and cannot replace that transport.

The active browser composition is baseline `index.html`/`enhanced` plus versioned `ux4`/`ux5`/`ux6` overlays. Unreferenced legacy TypeScript/generated JavaScript/CSS build remnants were removed from the live tree rather than retained as a parallel unused implementation.

A deliberate remote-bind override changes bind policy only. Remote operation still requires independent authenticated/authorized TLS, firewalling, proxy policy, and multi-user isolation.

## Backup, WAL, and PITR architecture

`src/wilson_eval3ngine/backup/` implements encrypted PostgreSQL physical backups, WAL archive objects, signed manifests, trusted-key verification, cluster/system identity checks, WAL continuity, signed recovery baselines, isolated restore/replay, post-restore reconciliation, audit verification, and recovery evidence.

The recovery trust chain is conceptually:

```text
PostgreSQL cluster identity
       |
       v
credential-safe pg_basebackup
       |
       v
encrypted immutable backup object
       +-- canonical signed manifest
       +-- plaintext/ciphertext digests
       |
       v
verified WAL sequence / target plan
       |
       v
isolated restore + PostgreSQL recovery
       |
       v
promotion / reconciliation / audit validation
       |
       v
measured recovery evidence
```

Source implementation is not an RPO/RTO claim. A deployment must prove cadence, WAL retention/continuity, target reachability, destructive restore success, reconciliation, and measured recovery objectives.

The current implementation remains deliberately explicit about residual engineering boundaries: planning is same-timeline; archive-observation time is not equivalent to WAL-record time; catalogue/publication paths and restore-target ownership are crash/concurrency-sensitive; recovery configuration must remain deterministic and shell-safe. These constraints belong in current status/runbooks rather than being hidden by optimistic documentation.

## Production deployment boundary

The repository includes secure/production Dockerfiles, Compose files, Caddy, PostgreSQL/Redis configuration, observability material, and infrastructure definitions. The intended topology publishes public host ports only at Caddy; API, PostgreSQL, Redis, Prometheus, and Grafana remain on explicit service networks according to their role.

Templates are not runtime proof. The target deployment must independently establish immutable image identity, TLS, firewall/direct-port denial, proxy CIDRs, egress controls, real IdP behavior, secret/KMS/signing custody, database/cache authentication, and recovery evidence.

## Public source versus private runtime evidence

<p align="center"><img src="assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100"></p>

Public source can safely own contracts, fail-closed validation, tests, sanitized evidence schemas, deployment templates, security controls, and deterministic inventory tools. Private runtime evidence owns real identities, groups, domains, certificates, credentials, provider destinations, allowlists, hosts, firewall/egress rules, logs, packet captures, incident contacts, raw scans, and destructive assurance exercises.

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` defines the boundary between those domains.

GitHub workflow definitions are configured for `main`, including the normal CI workflow and the security/quality assurance workflow. Their definitions are policy/configuration; a particular revision is CI-assured only after its exact run has been observed successfully.

## Historical foundation lane

`examples/experiments/foundation.yaml` and the synchronous `EvaluationService` remain because they provide a small deterministic path through the core measurement contract. They are useful for learning, regression checks, and diagnostics, but they exercise only a subset of the broader platform.

The correct project description is therefore: **an active evaluation platform with a deterministic local foundation lane and broader production-oriented modules, currently in pre-production assurance.**

## Code map

| Concern | Primary area |
|---|---|
| Domain contracts/states | `src/wilson_eval3ngine/domain/` |
| Application orchestration | `src/wilson_eval3ngine/application/` |
| Rendering/idempotency | `src/wilson_eval3ngine/execution/` |
| Provider adapters/policy | `src/wilson_eval3ngine/providers/` |
| Expectation compilation | `src/wilson_eval3ngine/expectations/` |
| Grading/review/persona views | `grading/`, `review/`, `ui/` |
| Metrics/statistics/gates | `metrics/`, `statistics/`, `gates/` |
| Evidence/report/signing/storage | `evidence/`, `reports/`, `security/`, `storage/` |
| Persistence/scheduling/audit | `src/wilson_eval3ngine/persistence/` |
| Backup/WAL/PITR | `src/wilson_eval3ngine/backup/` |
| Certification | `src/wilson_eval3ngine/certification/` |
| API/auth/middleware | `src/wilson_eval3ngine/api/`, `security/` |
| GUI | `src/wilson_eval3ngine/gui/`, `gui/static/` |
| Telemetry/tracing | `src/wilson_eval3ngine/telemetry*`, `tracing*` |
| Deployment/observability | `docker-compose*.yml`, `Dockerfile*`, `infrastructure/` |

For exact maturity and residual limitations, read [Current Status](STATUS.md). For visual operator interpretation, read [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).
