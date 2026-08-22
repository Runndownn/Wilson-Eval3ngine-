# Wilson Eval3ngine Current Status

**Package version:** `0.1.0`  
**Project stage:** **active evaluation platform / pre-production assurance**  
**Production certification status:** **not automatically established by repository source**

This page is the current status authority for public documentation. It exists so historical plans, point-in-time test reports, screenshots, and the original deterministic vertical slice are not mistaken for the state or assurance level of the entire repository.

## “Foundation” is a lane, not the whole project

Names such as `examples/experiments/foundation.yaml`, `we3.foundation_result.v1`, and older comments referring to the foundation runner describe the deterministic local/CI vertical slice that established the first complete measurement path. They are not a current whole-project maturity label.

The broader repository contains real-provider paths, durable PostgreSQL scheduling, human review/adjudication, encrypted evaluation-evidence storage, OIDC/project controls, telemetry, deployment/security controls, GUI/operator workflows, and certification orchestration. Backup/PITR/recovery also has substantial scaffolding on this branch, but its real encryption/WAL/restore execution remains a separate completion workstream and is called out below. The package version remains `0.1.0`; semantic version alone neither proves immaturity nor certifies production readiness.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Implemented** | A concrete source implementation exists. |
| **Integrated** | The capability is composed into at least one supported execution/deployment path. |
| **Local-lane exercised** | The deterministic local path uses the capability directly. |
| **Provisional** | Implementation/scaffolding exists, but a material functional, calibration, reference, policy, or evidence requirement is incomplete. |
| **Runtime assurance required** | Source exists, but the production claim depends on the target environment and executed evidence. |
| **Historical** | Provenance/planning material that is not current product truth. |

## Capability matrix

| Capability | Current repository status | What that does and does not mean |
|---|---|---|
| Versioned experiment/dataset contracts | **Implemented / local-lane exercised** | Schema, identity, split, and dataset-hash checks are part of the synchronous path. Production datasets still require governance/approval. |
| Expectation compilation before execution | **Implemented / local-lane exercised** | Expected treatment is established before provider output is seen. |
| Deterministic mock provider | **Implemented / local-lane exercised** | Supports credential-free local/CI runs and failure simulation. |
| Azure OpenAI adapter | **Implemented** | Real use requires authorized endpoint/credentials/capability validation and runtime evidence. |
| Anthropic adapter | **Implemented** | Real use requires authorized endpoint/credentials and provider-specific validation. |
| Ollama adapter | **Implemented** | Local/private destination access is policy constrained and opt-in where required. |
| CLI-backed provider adapters | **Implemented** | Availability depends on installed/authenticated CLIs and operating-system identity. |
| Provider retry/attempt evidence | **Implemented / local-lane exercised** | Attempts/reliability outcomes remain distinct from behavioral labels. |
| Five-outcome grading | **Implemented / local-lane exercised** | Certification-grade calibration still needs evidence for the target program. |
| Human review/adjudication workflow | **Implemented** | Dual review, recusal, abstention, disagreement, and adjudication primitives exist; live operation still needs identities/staffing/policy/SLA/integration. |
| Persona analyst view project isolation | **Implemented** | Analyst views reject unscoped or cross-project canonical reports before copying metrics/artifact lineage. Higher-level authorization remains a caller/API responsibility. |
| Executive persona support/uncertainty aggregates | **Provisional** | `build_executive_summary` still uses placeholder aggregate support/uncertainty values because `CanonicalReport` does not yet define authoritative aggregate contracts for them. Do not cite those fields as measured evidence. |
| Reviewer redaction helper | **Baseline implementation / provisional for DLP** | Email, long numeric-ID, and phone patterns are masked; this regex helper is not a complete production sensitive-data/DLP policy. |
| Metric snapshots | **Implemented / local-lane exercised** | Results retain numerator, denominator, exclusions, method/version, and run population. |
| Wilson score intervals | **Implemented / local-lane exercised** | Core proportion uncertainty is present. |
| Cross-run comparisons and drift | **Implemented with provisional portions** | Comparison/drift primitives exist; one comparison path still returns placeholder `p_value=0.5` pending completed bootstrap/reference significance work. |
| Prompt-family independence accounting | **Provisional in one snapshot path** | `create_metric_snapshot` currently documents `prompt_family_count=len(run_ids)` as an approximation; certification independence claims must use validated evidence. |
| Release gate engine | **Implemented / local-lane exercised** | Minimum support, pass/warn/indeterminate/block precedence, and critical unsafe-compliance blocking exist. Threshold authority remains program specific. |
| Canonical report model and CSV export | **Implemented** | Canonical report hashing and formula-injection-aware CSV export exist. Raw prompts/responses are intentionally omitted from this summary export. |
| Cross-format report-hash reconciliation | **Implemented** | Reconciliation fails closed unless JSON/CSV/HTML output carries the exact canonical report hash; carrying the hash is a representation-integrity check, not proof that every field was independently recomputed. |
| Parquet report export | **Implemented as optional capability** | Requires `pyarrow`; missing support is an explicit error rather than a zero-byte artifact. `pyarrow` is not a default package dependency. |
| Content-addressed local evaluation evidence | **Implemented / local-lane exercised** | Strong development/CI traceability; local filesystem storage alone is not managed production immutability. |
| Encrypted evaluation-evidence store | **Implemented** | AES-256-GCM envelope-encryption/retention interfaces exist; development `LocalKMSClient` is not a production KMS authority. This is distinct from the database-backup workstream. |
| Audit chain | **Implemented / API integrated** | Authenticated API requests and authorization decisions use the hash-linked database ledger on the supported path. External checkpoint/trust operation and real database behavior still require runtime evidence. |
| Ed25519 dossier signing | **Implemented / local-lane exercised** | Development key generation is not managed production signing identity/key custody. |
| Durable PostgreSQL scheduler | **Implemented** | Fenced leases, heartbeats, retry/dead-letter behavior, and reconciliation code exist; target workload behavior still needs runtime evidence. |
| OIDC authentication | **Implemented / API integrated / runtime assurance required** | Supported API composition uses one application-lifetime authenticator, bounded signed claims, restricted algorithms, MFA/project/role checks, and shared Redis-backed revocation in staging/production. `jti` supports invalidation but is not sender-constrained bearer replay prevention. Real issuer/JWKS/key rotation/negative tests remain deployment evidence. |
| Exact role authorization | **Implemented / API integrated** | Human and `workload:*` roles retain exact canonical identity. Core and extended project routes enter the shared authorization matrix; `system_admin` has no implicit all-powerful API bypass. |
| Authorization-decision audit | **Implemented / API integrated** | Matrix allow/deny decisions are persisted before an allow returns. Required audit failure blocks protected work with a bounded service-unavailable response. Runtime database failure/concurrency behavior still needs target evidence. |
| Distributed rate limiting | **Implemented / API integrated / runtime assurance required** | Staging/production require Redis and fail closed when shared rate state is unavailable. Forwarded client identity is trusted only from configured proxy CIDRs; unverified project headers do not select pre-auth buckets; exact client identity is one-way hashed for enforcement and privacy-reduced only for logs. |
| API idempotency authority | **Implemented / API integrated** | Keys are bounded and project scoped; assurance environments bind request intent atomically in Redis and reject reuse for different intent. Synchronous operation state itself remains process-local. |
| Browser CORS/CSRF boundary | **Implemented / API integrated** | CORS uses exact origin/preflight allowlists with server-side rejection. Bearer-header OIDC is non-ambient and intentionally CSRF-exempt; a bound HMAC/double-submit control exists for future cookie/session-authenticated mutations. CORS is not authentication. |
| Streaming request-body limit | **Implemented / API integrated** | Actual ASGI bytes are counted rather than trusting `Content-Length`; deployment testing remains relevant. |
| Client-safe unexpected errors | **Implemented** | Unexpected client responses use fixed safe codes/messages; detailed diagnostics stay on the server-side logging plane. |
| Security headers | **Implemented in API and Caddy / runtime assurance required** | CSP, HSTS, COOP, CORP, COEP, frame/MIME/referrer/permissions/cache controls are defined. HSTS `preload` text is not proof of preload-list enrollment or browser compatibility. |
| External production secret authority | **Implemented / deployment integrated** | Active production composition uses mounted/private secret authority and rejects the development Fernet manager. `.secrets/` is ignored; any credential historically committed remains compromised and must stay rotated. |
| Production ingress topology | **Implemented templates / runtime assurance required** | Only Caddy publishes host ports; public API diagnostics/schema UI are blocked; Prometheus has no public Caddy route; Caddy overwrites forwarding identity. Exact proxy CIDRs, TLS, firewall and direct-port denial remain target-deployment facts. |
| Dependency/security scanning | **Configured; execution evidence unavailable** | Dependabot, Bandit, `pip-audit`, repository-native scanning, Trivy workflow definitions, and a manual `make security-check` lane exist. GitHub Actions are disabled at the time of the 2026-08-22 reassessment, so no current automated result is claimed. |
| GUI secure-default bind policy | **Implemented / integrated** | The supported launcher defaults to loopback and repairs legacy wildcard defaults to `127.0.0.1`. Explicit `WE3_GUI_ALLOW_REMOTE_BIND=1` permits non-loopback binding; that opt-in requires independent authenticated/authorized TLS, firewall, and network assurance. |
| GUI runtime overlays (`ux4`/`ux5`/`ux6`) | **Implemented / integrated** | The supported server injects these layers into baseline `index.html` before serving `/`; they are active runtime assets even though baseline HTML lacks static script tags for them. |
| Provider destination policy | **Implemented / GUI integrated** | Application controls reduce risk; network-level egress assurance and deployment allowlists remain environment responsibilities. |
| GUI secret transport | **Implemented in supported POSIX path** | One-shot secret transport avoids the historical regular plaintext temp file; non-POSIX secure transport remains platform specific. |
| Telemetry/tracing | **Implemented** | Production SLOs, alerts, tracing backends, and evidence must be validated in the running environment. |
| Backup metadata / recovery models / reconciliation scaffold | **Implemented / provisional on this branch** | Models, command scaffolding, restore-plan concepts, reconciliation queries, recovery manifests, tests, and runbooks exist. Separate recovery-completion work must be reviewed/merged independently. |
| Encrypted database backup payload | **Not established on this branch** | This security branch is based on the current `main` recovery state; do not borrow claims from a separate unmerged recovery branch. |
| Backup content-integrity verification | **Provisional on this branch** | Apply the recovery status of the exact deployed branch rather than a parallel workstream. |
| WAL archive / PITR coverage | **Provisional scaffold on this branch** | Continuous real WAL coverage is not claimed by this branch. |
| Isolated restore execution | **Provisional scaffold on this branch** | Actual restore/replay evidence must come from the recovery workstream and target runtime. |
| Durable CLI backup catalogue | **Not established on this branch** | Apply the exact branch/release recovery implementation and evidence. |
| Production Compose/Caddy topology | **Implemented templates** | Intended ingress/source config does not prove deployed firewall/network behavior. |
| Certification requirements/orchestration | **Implemented** | A release only passes when required evidence is actually satisfied. |
| Production certification of a specific deployment | **Runtime assurance required** | Public source cannot establish private identities, secrets, provider destinations, certificates, network policy, restores, scans, or runtime results by itself. |

## What the deterministic local lane proves

The included local example proves that the core measurement contract can be exercised without external credentials: load/validate the manifest and dataset, establish expectations, execute deterministic provider behavior, preserve evidence, grade responses, compute metrics/Wilson intervals, evaluate gates, build reports/dossiers, and verify signatures. It is intentionally small enough for repeatable development and CI use.

It does **not** exercise every provider, production scheduler, external KMS/secret manager, organizational IdP, private egress boundary, multi-user review operation, real encrypted database backup/PITR restore, production certificate, or target deployment.

## Known implementation limitations that must stay visible

### Statistical comparison completion

`src/wilson_eval3ngine/metrics/engine.py` still sets `p_value=0.5` in one comparison path with a comment that real bootstrap comparison belongs there. The same module notes one `create_metric_snapshot` path approximates prompt-family count using `len(run_ids)`. Certification-grade significance or independent-prompt support must therefore use a validated statistical/reference path and retained evidence rather than these placeholders.

### Executive persona aggregates

`src/wilson_eval3ngine/ui/views.py` derives release status and critical blocks from the canonical report, but its aggregate support and uncertainty percentages remain provisional constants because `CanonicalReport` does not yet provide an authoritative aggregate support/uncertainty contract.

### Analyst/reviewer scope

The analyst helper enforces that the canonical report's project matches the authorized project argument and rejects missing project scope. That closes the local view-construction relabelling gap, but authorization must still be enforced at API/service boundaries and backed by real identity/project policy. The reviewer redaction helper is baseline pattern masking, not a production DLP engine.

### Synchronous operation state

Redis-backed idempotency preserves the project/key/request-intent binding, but `OperationRegistry` is deliberately process-local in the synchronous API lane. A retry after process restart can therefore receive `idempotency_operation_state_unavailable` instead of silently creating duplicate work. Horizontally scaled long-running execution should use the durable PostgreSQL scheduler rather than treating the synchronous registry as durable state.

### Bearer-token replay boundary

`jti`, expiry, and Redis revocation provide token invalidation. They do not sender-bind an unrevoked bearer token. If the target threat model requires proof-of-possession, that must be designed and validated with the actual identity provider; the repository does not claim ordinary bearer tokens are cryptographically non-replayable.

### Proxy and browser deployment inputs

`WE3_TRUSTED_PROXY_CIDRS` must name only the private Caddy-to-API ranges. Empty is spoof-safe but collapses remote clients into the proxy's rate bucket; overly broad values can reintroduce forwarded-header spoofing. CORS origins must likewise be exact approved browser origins. COEP/CSP/HSTS behavior and Grafana/browser compatibility require runtime validation.

### Report/export boundaries

Cross-format hash reconciliation checks that JSON, CSV, and HTML representations carry the exact canonical hash instead of returning unconditional success. This verifies a shared representation identifier; it does not independently prove semantic equality of every serialized field. Parquet export requires optional `pyarrow` and fails explicitly if unavailable.

### Backup/PITR/recovery execution

This branch does not import assurance claims from the parallel recovery-completion workstream. Production recovery status must be read from the exact release branch being deployed and proven with executed encrypted-backup, WAL, restore, reconciliation, and approval evidence.

### Calibration and threshold authority

Deterministic grading and gate code do not make every grader or threshold certification-approved. Grader calibration, benchmark composition, severity/category policy, minimum support, and release thresholds must be validated and approved for the specific program.

### Local versus managed evidence controls

Content-addressed local artifacts, local audit data, development signing keys, and development KMS are appropriate for deterministic development but are not substitutes for managed production storage, key custody, retention/legal hold, secret management, and external audit/checkpoint controls.

### GUI bind/identity boundary

The supported GUI is **secure-by-default**, not mathematically incapable of remote binding. Its default launcher is loopback-only unless the operator deliberately sets `WE3_GUI_ALLOW_REMOTE_BIND=1`. If that override is used, the operator owns the authenticated/authorized TLS proxy or equivalent access layer, firewall exposure, network policy, and target-deployment validation. A wildcard bind with the override is explicitly warned about by the launcher.

## Security assessment status

[`docs/security/SECURITY_ASSESSMENT.md`](security/SECURITY_ASSESSMENT.md) is the historical 2026-07-30 finding set. [`docs/security/MASTER_SECURITY_ASSESSMENT.md`](security/MASTER_SECURITY_ASSESSMENT.md) is a point-in-time 2026-08-01 assessment. The current source-level revalidation is [`docs/security/SECURITY_REASSESSMENT_2026-08-22.md`](security/SECURITY_REASSESSMENT_2026-08-22.md).

GitHub Actions are disabled at the time of the current reassessment. Workflow files are therefore definitions, not current execution evidence. The manual security lane is documented in the reassessment and `SECURITY.md`; no unobserved command is represented as passing.

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` remains the enduring contract for what public source can prove versus what must be verified privately. Raw private evidence should stay outside the public repository while bounded outcomes/fingerprints can be published where appropriate.

## GUI and screenshot status

The canonical documentation captures match the five-workspace interface and live under `docs/assets/gui/current/`. Older six-image PNGs remain as historical point-in-time assets. Screenshot counters, provider health, model inventory, run/report totals, demo chart values, and legacy report metadata are capture state—not current release metrics.

## Historical documents

The original `docs/Plans_/` and `docs/08-planning/Plans_/` material remains in place by design. Superseded public-facing documents are stored under `.archive/documentation/`. Historical “all tests passing” reports are evidence about their earlier snapshot, not proof about the latest branch or a production deployment.

## Current release statement

> **Wilson Eval3ngine `0.1.0` is an active evidence-first LLM evaluation platform in pre-production assurance. The deterministic local evaluation lane and many provider, scheduling, review, security, evidence, reporting, GUI, and certification components are implemented, while explicitly documented statistical, persona-view, recovery, and private-runtime areas remain provisional or evidence-dependent. Production certification must be established for the exact release/deployment being approved.**

See [Architecture](ARCHITECTURE.md) for component relationships, [Getting Started](GETTING_STARTED.md) for the first safe run, [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) for the operator/evidence model, [Current Security Reassessment](security/SECURITY_REASSESSMENT_2026-08-22.md) for the active security findings/status, and [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) for the recovery boundary of the exact branch being reviewed.
