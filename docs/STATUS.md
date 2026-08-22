# Wilson Eval3ngine Current Status

**Package version:** `0.1.0`  
**Project stage:** **active evaluation platform / pre-production assurance**  
**Production certification status:** **not automatically established by repository source**

This page is the current status authority for public documentation. It exists so historical plans, point-in-time test reports, screenshots, and the original deterministic vertical slice are not mistaken for the state or assurance level of the entire repository.

## “Foundation” is a lane, not the whole project

Names such as `examples/experiments/foundation.yaml`, `we3.foundation_result.v1`, and older comments referring to the foundation runner describe the deterministic local/CI vertical slice that established the first complete measurement path. They are not a current whole-project maturity label.

The broader repository contains real-provider paths, durable PostgreSQL scheduling, human review/adjudication, encrypted evaluation-evidence storage, OIDC/project controls, telemetry, deployment/security controls, GUI/operator workflows, certification orchestration, and an implemented PostgreSQL physical-backup/PITR recovery path. The package version remains `0.1.0`; semantic version alone neither proves immaturity nor certifies production readiness.

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
| Encrypted evaluation-evidence store | **Implemented** | AES-256-GCM envelope-encryption/retention interfaces exist; development `LocalKMSClient` is not a production KMS authority. |
| Audit chain | **Implemented** | Event hashing and chain verification are shared by normal audit and recovery reconciliation. External checkpoint/trust operation still depends on deployment configuration/evidence. |
| Ed25519 dossier signing | **Implemented / local-lane exercised** | Development key generation is not managed production signing identity/key custody. |
| Durable PostgreSQL scheduler | **Implemented** | Fenced leases, heartbeats, retry/dead-letter behavior, and reconciliation code exist; target workload behavior still needs runtime evidence. |
| OIDC/project authorization | **Implemented** | Real issuer/JWKS, claims, role mapping, RLS/object policy, revocation, and negative authorization results are environment-specific. |
| GUI secure-default bind policy | **Implemented / integrated** | The supported launcher defaults to loopback and repairs legacy wildcard defaults to `127.0.0.1`. Explicit `WE3_GUI_ALLOW_REMOTE_BIND=1` permits non-loopback binding; that opt-in requires independent authenticated/authorized TLS, firewall, and network assurance. |
| GUI runtime overlays (`ux4`/`ux5`/`ux6`) | **Implemented / integrated** | The supported server injects these layers into baseline `index.html` before serving `/`; they are active runtime assets even though baseline HTML lacks static script tags for them. |
| Provider destination policy | **Implemented / GUI integrated** | Application controls reduce risk; network-level egress assurance and deployment allowlists remain environment responsibilities. |
| GUI secret transport | **Implemented in supported POSIX path** | One-shot secret transport avoids the historical regular plaintext temp file; non-POSIX secure transport remains platform specific. |
| Streaming request-body limit | **Implemented** | Actual ASGI bytes are counted rather than trusting `Content-Length`; deployment testing remains relevant. |
| Telemetry/tracing | **Implemented** | Production SLOs, alerts, tracing backends, and evidence must be validated in the running environment. |
| Encrypted PostgreSQL physical backup | **Implemented / runtime assurance required** | `pg_basebackup` is streamed directly through AES-256-GCM; the DEK is KMS-wrapped and the signed manifest records PostgreSQL and KMS identity. Production KMS authorization/storage durability still require target-environment evidence. |
| Backup integrity and trust verification | **Implemented** | Verification checks canonical manifest SHA-256, trusted Ed25519 signer, ciphertext digest/size, KMS unwrap, AES-GCM authentication, and decrypted plaintext digest/size. It fails closed when any layer disagrees. |
| Durable backup catalogue | **Implemented for filesystem backup root** | `backup_catalog.v2.json` survives process restart and binds backup/WAL records to database identity and ciphertext storage versions. Atomic local persistence is not the same as managed immutable object storage or multi-writer distributed coordination. |
| Real WAL archive and PITR coverage | **Implemented / runtime assurance required** | WE3 ingests actual 24-hex PostgreSQL WAL files, binds them to system/timeline/segment-size identity, and rejects missing or non-contiguous coverage. The deployment must still operate a reliable WAL archival service and prove its observed RPO. |
| Signed recovery baseline and reconciliation | **Implemented** | Expected run/classification/metric/gate/provenance/outbox populations and per-project audit roots are signed before recovery. Reconciliation uses the real `outbox_events` and `provenance_edges` schema and recomputes audit chains cryptographically. |
| Isolated PostgreSQL restore/PITR | **Implemented / runtime assurance required** | The recovery orchestrator decrypts/authenticates selected objects, performs a loopback-only physical restore, waits for recovery target/promotion, requires reconciliation to pass, and retains measured evidence. Production RTO and return-to-service authorization remain deployment facts. |
| Disposable PostgreSQL recovery exercise in CI | **Configured as runtime validation** | A dedicated workflow creates an actual disposable cluster, encrypts a physical backup, archives real WAL, exercises corruption/signature/missing-WAL negatives, restores to a second loopback cluster, and retains the runtime directory as an artifact. A green run proves that tested commit/environment, not a private production deployment. |
| Native recovery for user-defined PostgreSQL tablespaces | **Not currently supported** | The streaming physical-backup path deliberately rejects user-defined tablespaces because safe restoration of external tablespace topology requires a deployment-specific storage mapping. Use the platform backup service until native support is added. |
| Production Compose/Caddy topology | **Implemented templates** | Intended ingress/source config does not prove deployed firewall/network behavior. |
| Certification requirements/orchestration | **Implemented** | A release only passes when required evidence is actually satisfied. |
| Production certification of a specific deployment | **Runtime assurance required** | Public source cannot establish private identities, secrets, provider destinations, certificates, network policy, KMS custody, restore duration, storage durability, scans, or runtime results by itself. |

## What the deterministic local lane proves

The included local example proves that the core measurement contract can be exercised without external credentials: load/validate the manifest and dataset, establish expectations, execute deterministic provider behavior, preserve evidence, grade responses, compute metrics/Wilson intervals, evaluate gates, build reports/dossiers, and verify signatures. It is intentionally small enough for repeatable development and CI use.

It does **not** exercise every provider, production scheduler, external KMS/secret manager, organizational IdP, private egress boundary, multi-user review operation, production recovery deployment, certificate, or target infrastructure. Recovery has its own separate PostgreSQL runtime exercise because physical backup/PITR cannot be meaningfully validated by the SQLite-based deterministic evaluation lane.

## Known implementation limitations that must stay visible

### Statistical comparison completion

`src/wilson_eval3ngine/metrics/engine.py` still sets `p_value=0.5` in one comparison path with a comment that real bootstrap comparison belongs there. The same module notes one `create_metric_snapshot` path approximates prompt-family count using `len(run_ids)`. Certification-grade significance or independent-prompt support must therefore use a validated statistical/reference path and retained evidence rather than these placeholders.

### Executive persona aggregates

`src/wilson_eval3ngine/ui/views.py` derives release status and critical blocks from the canonical report, but its aggregate support and uncertainty percentages remain provisional constants because `CanonicalReport` does not yet provide an authoritative aggregate support/uncertainty contract.

### Analyst/reviewer scope

The analyst helper enforces that the canonical report's project matches the authorized project argument and rejects missing project scope. That closes the local view-construction relabelling gap, but authorization must still be enforced at API/service boundaries and backed by real identity/project policy. The reviewer redaction helper is baseline pattern masking, not a production DLP engine.

### Report/export boundaries

Cross-format hash reconciliation checks that JSON, CSV, and HTML representations carry the exact canonical hash instead of returning unconditional success. This verifies a shared representation identifier; it does not independently prove semantic equality of every serialized field. Parquet export requires optional `pyarrow` and fails explicitly if unavailable.

### Backup/PITR/recovery runtime boundary

The recovery source implementation now includes real physical backup encryption, signed manifest verification, persistent catalogue state, real WAL-file ingestion and continuity checks, signed recovery baselines, actual isolated PostgreSQL restore/PITR, and schema-aware reconciliation. That removes the earlier source-level scaffold limitation tracked by issue #38.

The assurance boundary has therefore moved rather than disappeared. The repository can prove what the implementation does and, when the dedicated recovery workflow is green, that a disposable PostgreSQL environment completed the exercised path for that commit. It cannot prove that a private production deployment has a 15-minute RPO, a four-hour RTO, approved KMS custody, immutable/replicated backup storage, correct tablespace handling, adequate operator staffing, or approved return-to-service authorization. Those claims require retained evidence from that exact environment.

The native streaming path currently rejects PostgreSQL clusters with user-defined tablespaces. The backup-root catalogue is durable across process restarts and written atomically, but it is a filesystem catalogue rather than a distributed multi-writer service. Deployments that require cross-host writers, managed retention/legal hold, object lock, regional replication, or external tablespace recovery should integrate the platform-native storage/database controls and retain those as additional assurance evidence.

### Calibration and threshold authority

Deterministic grading and gate code do not make every grader or threshold certification-approved. Grader calibration, benchmark composition, severity/category policy, minimum support, and release thresholds must be validated and approved for the specific program.

### Local versus managed evidence controls

Content-addressed local artifacts, local audit data, development signing keys, and the development KMS are appropriate for deterministic development but are not substitutes for managed production storage, key custody, retention/legal hold, secret management, and external audit/checkpoint controls. The backup CLI likewise requires explicit opt-in before its local KMS can be used, and that mode remains development/test only.

### GUI bind/identity boundary

The supported GUI is **secure-by-default**, not mathematically incapable of remote binding. Its default launcher is loopback-only unless the operator deliberately sets `WE3_GUI_ALLOW_REMOTE_BIND=1`. If that override is used, the operator owns the authenticated/authorized TLS proxy or equivalent access layer, firewall exposure, network policy, and target-deployment validation. A wildcard bind with the override is explicitly warned about by the launcher.

## Security assessment status

`docs/security/MASTER_SECURITY_ASSESSMENT.md` is a valuable **point-in-time security assessment dated 2026-08-01**. Later code/documentation should not present its runtime-pending statements as if they were freshly re-executed on every commit. Recovery work added after that assessment must be reviewed against current code and workflow evidence rather than retroactively changing the historical assessment.

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` remains the enduring contract for what public source can prove versus what must be verified privately. Raw private evidence should stay outside the public repository while bounded outcomes/fingerprints can be published where appropriate.

## GUI and screenshot status

The canonical documentation captures match the five-workspace interface and live under `docs/assets/gui/current/`. Older six-image PNGs remain as historical point-in-time assets. Screenshot counters, provider health, model inventory, run/report totals, demo chart values, and legacy report metadata are capture state—not current release metrics.

## Historical documents

The original `docs/Plans_/` and `docs/08-planning/Plans_/` material remains in place by design. Superseded public-facing documents are stored under `.archive/documentation/`. Historical “all tests passing” reports are evidence about their earlier snapshot, not proof about the latest branch or a production deployment.

## Current release statement

> **Wilson Eval3ngine `0.1.0` is an active evidence-first LLM evaluation platform in pre-production assurance. The deterministic evaluation lane and substantial provider, scheduling, review, security, evidence, reporting, GUI, certification, and PostgreSQL recovery capabilities are implemented. Explicit statistical/persona-view limitations remain provisional, while production recovery, identity, key custody, network, storage, provider, and certification claims remain evidence-dependent for the exact release and deployment being approved.**

See [Architecture](ARCHITECTURE.md) for component relationships, [Getting Started](GETTING_STARTED.md) for the first safe run, [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) for the operator/evidence model, and [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) for the recovery mechanics and runtime-assurance boundary.
