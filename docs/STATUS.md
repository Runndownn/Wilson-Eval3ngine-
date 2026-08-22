# Wilson Eval3ngine Current Status

**Package version:** `0.1.0`  
**Project stage:** **active evaluation platform / pre-production assurance**  
**Production certification status:** **not automatically established by repository source**

This page is the current status authority for public documentation. It exists so historical plans, point-in-time test reports, screenshots, and the original deterministic vertical slice are not mistaken for the state or assurance level of the entire repository.

## “Foundation” is a lane, not the whole project

Names such as `examples/experiments/foundation.yaml`, `we3.foundation_result.v1`, and older comments referring to the foundation runner describe the deterministic local/CI vertical slice that established the first complete measurement path. They are not a current whole-project maturity label.

The broader repository contains real-provider paths, durable PostgreSQL scheduling, human review/adjudication, encrypted evaluation-evidence storage, OIDC/project controls, telemetry, deployment/security controls, GUI/operator workflows, and certification orchestration. Backup/PITR/recovery also has substantial scaffolding, but its real encryption/WAL/restore execution is still provisional and is called out separately below. The package version remains `0.1.0`; semantic version alone neither proves immaturity nor certifies production readiness.

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
| Cross-format report-hash reconciliation | **Implemented** | Reconciliation now fails closed unless JSON/CSV/HTML output carries the exact canonical report hash; carrying the hash is a representation-integrity check, not proof that every field was independently recomputed. |
| Parquet report export | **Implemented as optional capability** | Requires `pyarrow`; missing support is an explicit error rather than a zero-byte artifact. `pyarrow` is not a default package dependency. |
| Content-addressed local evaluation evidence | **Implemented / local-lane exercised** | Strong development/CI traceability; local filesystem storage alone is not managed production immutability. |
| Encrypted evaluation-evidence store | **Implemented** | AES-256-GCM envelope-encryption/retention interfaces exist; development `LocalKMSClient` is not a production KMS authority. This is distinct from the provisional database-backup encryption path. |
| Audit chain | **Implemented** | External checkpoint/trust operation depends on deployment configuration/evidence. |
| Ed25519 dossier signing | **Implemented / local-lane exercised** | Development key generation is not managed production signing identity/key custody. |
| Durable PostgreSQL scheduler | **Implemented** | Fenced leases, heartbeats, retry/dead-letter behavior, and reconciliation code exist; target workload behavior still needs runtime evidence. |
| OIDC/project authorization | **Implemented** | Real issuer/JWKS, claims, role mapping, RLS/object policy, revocation, and negative authorization results are environment-specific. |
| GUI secure-default bind policy | **Implemented / integrated** | The supported launcher defaults to loopback and repairs legacy wildcard defaults to `127.0.0.1`. Explicit `WE3_GUI_ALLOW_REMOTE_BIND=1` permits non-loopback binding; that opt-in requires independent authenticated/authorized TLS, firewall, and network assurance. |
| GUI runtime overlays (`ux4`/`ux5`/`ux6`) | **Implemented / integrated** | The supported server injects these layers into baseline `index.html` before serving `/`; they are active runtime assets even though baseline HTML lacks static script tags for them. |
| Provider destination policy | **Implemented / GUI integrated** | Application controls reduce risk; network-level egress assurance and deployment allowlists remain environment responsibilities. |
| GUI secret transport | **Implemented in supported POSIX path** | One-shot secret transport avoids the historical regular plaintext temp file; non-POSIX secure transport remains platform specific. |
| Streaming request-body limit | **Implemented** | Actual ASGI bytes are counted rather than trusting `Content-Length`; deployment testing remains relevant. |
| Telemetry/tracing | **Implemented** | Production SLOs, alerts, tracing backends, and evidence must be validated in the running environment. |
| Backup metadata / recovery models / reconciliation scaffold | **Implemented / provisional** | Models, command scaffolding, restore-plan concepts, reconciliation queries, recovery manifests, tests, and runbooks exist. |
| Encrypted database backup payload | **Not yet established by current backup manager** | `create_full_backup` invokes `pg_basebackup` but does not currently encrypt the resulting payload even though metadata is marked encrypted. Do not claim KMS-encrypted WE3 backups from this path. |
| Backup content-integrity verification | **Provisional / insufficient for production** | Current checksum logic hashes the backup directory pathname rather than backup bytes/objects; signature verification also contains an unimplemented branch. |
| WAL archive / PITR coverage | **Provisional scaffold** | Current WAL method creates metadata and restore planning synthesizes placeholder segment names; continuous real WAL coverage is not yet proven. |
| Isolated restore execution | **Provisional scaffold** | `execute_isolated_restore` currently logs intent and returns success rather than executing a real restore/replay. |
| Durable CLI backup catalogue | **Not established by current manager** | Backup metadata is held in an in-process mapping, so separate CLI invocations do not constitute a durable catalogue through this class. |
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

The analyst helper now enforces that the canonical report's project matches the authorized project argument and rejects missing project scope. That closes the local view-construction relabelling gap, but authorization must still be enforced at API/service boundaries and backed by real identity/project policy. The reviewer redaction helper is baseline pattern masking, not a production DLP engine.

### Report/export boundaries

Cross-format hash reconciliation checks that JSON, CSV, and HTML representations carry the exact canonical hash instead of returning unconditional success. This verifies a shared representation identifier; it does not independently prove semantic equality of every serialized field. Parquet export requires optional `pyarrow` and fails explicitly if unavailable.

### Backup/PITR/recovery execution

The current backup module should be treated as **design/scaffold plus partial reconciliation implementation**, not production recovery protection. In particular, backup payload encryption, content-based integrity, signed verification, real WAL archival/coverage, durable catalogue persistence, and actual isolated restore execution are incomplete in the current manager. The previous runbook wording overstated these controls and has been replaced with explicit completion gates in [Backup and Recovery Runbook](operations/backup-recovery-runbook.md).

A CI unit/integration test that simulates backup records is source-level evidence; it is not proof that an authorized PostgreSQL instance was backed up, encrypted, restored to a point in time, reconciled, and returned to service under approval.

### Calibration and threshold authority

Deterministic grading and gate code do not make every grader or threshold certification-approved. Grader calibration, benchmark composition, severity/category policy, minimum support, and release thresholds must be validated and approved for the specific program.

### Local versus managed evidence controls

Content-addressed local artifacts, local audit data, development signing keys, and the development KMS are appropriate for deterministic development but are not substitutes for managed production storage, key custody, retention/legal hold, secret management, and external audit/checkpoint controls.

### GUI bind/identity boundary

The supported GUI is **secure-by-default**, not mathematically incapable of remote binding. Its default launcher is loopback-only unless the operator deliberately sets `WE3_GUI_ALLOW_REMOTE_BIND=1`. If that override is used, the operator owns the authenticated/authorized TLS proxy or equivalent access layer, firewall exposure, network policy, and target-deployment validation. A wildcard bind with the override is explicitly warned about by the launcher.

## Security assessment status

`docs/security/MASTER_SECURITY_ASSESSMENT.md` is a valuable **point-in-time security assessment dated 2026-08-01**. Later code/documentation should not present its runtime-pending statements as if they were freshly re-executed on every commit.

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` remains the enduring contract for what public source can prove versus what must be verified privately. Raw private evidence should stay outside the public repository while bounded outcomes/fingerprints can be published where appropriate.

## GUI and screenshot status

The canonical documentation captures match the five-workspace interface and live under `docs/assets/gui/current/`. Older six-image PNGs remain as historical point-in-time assets. Screenshot counters, provider health, model inventory, run/report totals, demo chart values, and legacy report metadata are capture state—not current release metrics.

## Historical documents

The original `docs/Plans_/` and `docs/08-planning/Plans_/` material remains in place by design. Superseded public-facing documents are stored under `.archive/documentation/`. Historical “all tests passing” reports are evidence about their earlier snapshot, not proof about the latest branch or a production deployment.

## Current release statement

> **Wilson Eval3ngine `0.1.0` is an active evidence-first LLM evaluation platform in pre-production assurance. The deterministic local evaluation lane and many provider, scheduling, review, security, evidence, reporting, GUI, and certification components are implemented, while explicitly documented statistical, persona-view, backup/PITR, and private-runtime areas remain provisional or evidence-dependent. Production certification must be established for the exact release/deployment being approved.**

See [Architecture](ARCHITECTURE.md) for component relationships, [Getting Started](GETTING_STARTED.md) for the first safe run, [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) for the operator/evidence model, and [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) for the current recovery completion boundary.
