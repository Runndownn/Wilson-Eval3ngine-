# Documentation Reconciliation Audit

**Initial audit:** 2026-08-21  
**Recovery/alignment follow-up:** 2026-08-22  
**Scope:** public-facing documentation, repository architecture/status claims, install/use guidance, GUI/runtime composition, visual assets, validation/CI wiring, recovery implementation, operational runbooks, and selected code comments whose wording carried security meaning  
**Historical Plans/TODO policy:** preserved in place and intentionally not rewritten

## Why this audit exists

Wilson Eval3ngine evolved faster than several documents that described it. Some older material correctly described the first deterministic vertical slice when it was written, but later source added real-provider paths, review/adjudication, durable scheduling, encrypted storage, identity/security controls, certification orchestration, hardened deployment material, layered GUI composition, and eventually a real PostgreSQL physical-backup/PITR implementation. Without reconciliation, one page could understate a completed capability while another could overstate a scaffold, screenshot, simulated test, or configured objective.

The purpose of this audit is not to make every document say “complete.” It is to make each document say the most specific thing the code and evidence justify. That means distinguishing implementation from integration, simulation from execution, configured targets from measurements, cryptographic integrity from storage durability, and public source from private deployment facts.

## Repository areas reviewed for current claims

The reconciliation has inspected current implementation/configuration rather than relying on planning documents alone, including:

- package version, optional dependencies, and console entry points in `pyproject.toml`;
- CLI and synchronous application orchestration;
- domain contracts and dataset/experiment validation;
- expectation compilation, rendering, and logical run identity;
- mock, hosted, local, and CLI provider adapters;
- grading and human review/adjudication;
- metrics, Wilson intervals, comparison/drift primitives, and gate logic;
- evidence storage, encrypted storage, audit, reports, and signing;
- persistence, outbox/provenance schema, migrations, and PostgreSQL durable scheduling;
- API/auth/project security and GUI access/provider/secret boundaries;
- GUI baseline HTML, runtime UX overlay composition, and active browser assets;
- telemetry/tracing and production Compose/container material;
- backup KMS/encryption, PostgreSQL identity/WAL handling, catalogue, restore planning, restore execution, recovery baseline, and reconciliation;
- game-day scenario/orchestration code versus the operational runbook;
- certification requirements/orchestration;
- `.github/workflows/ci.yml`, Make targets, and source/runtime validation expectations;
- active documentation, historical Phase-1 reports, Plans/TODOs, prompts, and archived visual/document assets.

## Corrections and findings

### 1. Project maturity

**Problem:** older public docs described the entire repository as `0.1.0 foundation`, even though `foundation` accurately named only the original deterministic local lane and historical identifiers.

**Correction:** current docs describe package version `0.1.0` and the project as an **active evaluation platform in pre-production assurance**. Production certification remains evidence-dependent because source code cannot prove the target deployment's identities, secrets, network policy, providers, certificates, recovery behavior, or other private runtime facts.

### 2. Provider implementation

**Problem:** older status language said real providers were not implemented.

**Correction:** current docs distinguish the deterministic mock lane from implemented Azure OpenAI, Anthropic, Ollama, local/private, and supported CLI adapter paths. An adapter existing in source is not treated as proof that a particular endpoint, credential, or model configuration has been authorized or validated.

### 3. Human review

**Problem:** older status material reduced human review to an escalation flag.

**Correction:** documentation now describes implemented review/adjudication primitives—task creation, assignment, blind dual review, recusal, abstention, disagreement, adjudication, and immutable review records—while keeping staffing, identity, policy, SLA, and runtime integration as organizational requirements.

### 4. Statistics remain partially provisional

**Problem:** high-level language could imply all planned comparison statistics were production complete.

**Correction:** current docs preserve two source limitations in `src/wilson_eval3ngine/metrics/engine.py`: one comparison path returns placeholder `p_value=0.5` where completed bootstrap/reference significance is intended, and one snapshot helper approximates `prompt_family_count` with `len(run_ids)`. Wilson intervals/core metric snapshots remain implemented, but those provisional paths must not be used to overclaim certification-grade significance or prompt-family independence.

### 5. Certification

**Problem:** old “not approved for production certification” wording sat beside a global foundation label without explaining that certification orchestration now exists.

**Correction:** documentation explains both facts: certification requirements/orchestration are implemented, while certification of a release/deployment only exists when required evidence is actually satisfied for that exact target.

### 6. Security assessment dating

**Problem:** the detailed 2026-08-01 master assessment could be mistaken for continuously refreshed runtime evidence.

**Correction:** current docs identify it as a point-in-time assessment. Later source changes do not retroactively rewrite what that assessment observed. The enduring public/private assurance split is documented separately through `docs/security/PRIVATE_RUNTIME_ASSURANCE.md`.

### 7. Current GUI is five workspaces, not six screenshot stages

**Problem:** the README/GUI guide promoted six older captures as if they were the current workflow. The live baseline interface implements five workspaces: **Endpoints, Models, Generate, Charts, Reports**.

**Correction:** five current captures live under `docs/assets/gui/current/`. Older six-image PNGs remain historical evidence. Prompt-package selection is explained inside Generate and PDF viewing inside Reports.

### 8. Screenshot values are point-in-time state

**Problem:** polished screenshots invite readers to interpret visible endpoint/model/run/report counts, provider status, names, or chart values as stable project facts.

**Correction:** active docs state that screenshot values describe the captured session. Inventory counters are not quality scores, endpoint health is connectivity evidence, and exact evaluation claims must come from structured run evidence/sidecars/metrics.

### 9. Demo charts versus run evidence

**Problem:** the Charts workspace can explicitly generate demo charts, making a screenshot easy to over-read.

**Correction:** documentation states that demo charts are synthetic and must never be cited as benchmark/release evidence. Run-derived charts should be reconciled through run identity, metadata, sidecars, and structured metrics.

### 10. Reports and legacy provenance

**Problem:** historical report artifacts can contain incomplete lineage such as missing model identity.

**Correction:** active docs preserve that absence as a provenance warning. Release-sensitive claims that depend on missing lineage should be reconciled through sidecars/hashes or regenerated under the current path rather than having lineage invented afterward.

### 11. Runtime GUI composition was easy to misread

**Problem:** `gui/static/index.html` directly loads `enhanced.js`, which could make `ux4.js`, `ux5.js`, and `ux6.js` look dead when only baseline HTML is inspected.

**Finding:** `src/wilson_eval3ngine/gui/ux_overlay.py` injects those layers into `/` before the supported listener serves the page.

**Correction:** architecture/operator docs now explain the composed runtime path instead of classifying injected assets as obsolete.

### 12. JavaScript lint coverage missed active overlays

**Problem:** `make lint` syntax-checked `enhanced.js` and `ux4.js` but omitted active `ux5.js` and `ux6.js`.

**Correction:** lint now checks all four browser JavaScript layers used by the supported composition.

### 13. Makefile cleanup side effect was attached to the wrong command

**Problem:** recursive `__pycache__` deletion was placed under a recovery-planning target instead of `clean`.

**Correction:** source cleanup belongs to `make clean`; recovery targets no longer perform unrelated filesystem cleanup.

### 14. Documentation validator did not validate WebP signatures

**Problem:** active documentation used WebP but the asset validator only understood PNG/SVG signatures.

**Correction:** `scripts/validate_documentation_assets.py` now verifies `RIFF....WEBP` signatures before accepting WebP documentation assets.

### 15. CI configuration versus observed CI evidence

**Problem:** a workflow file can be described as if a particular commit had already passed it.

**Correction:** current docs distinguish configured CI behavior from an observed run. Workflow YAML establishes intended checks; a green run/artifact establishes evidence for a specific commit/environment.

### 16. Backup encryption metadata did not match stored bytes

**Problem:** the previous backup scaffold called `pg_basebackup` but marked the record `encrypted=True` without encrypting the physical backup payload. Its checksum was derived from the backup-directory pathname rather than backup content.

**Correction:** issue #38 replaces that scaffold with streaming AES-256-GCM. `pg_basebackup` tar output is encrypted as it is read, using a one-time 256-bit DEK wrapped through the repository KMS contract. Manifests retain plaintext and ciphertext SHA-256 values, KMS identity, PostgreSQL identity, storage version, and a trusted Ed25519 signature. Deep verification authenticates/decrypts the object and rechecks the plaintext digest/size rather than trusting metadata.

### 17. Recovery needed a production-oriented KMS adapter without normalizing development KMS

**Problem:** the repository had a useful `LocalKMSClient` for development/evidence-store testing but no concrete production-oriented backup KMS adapter. Reusing the local client implicitly would have made the new encrypted backup look stronger operationally than it was.

**Correction:** `src/wilson_eval3ngine/backup/kms.py` adds AWS KMS support through the existing KMS protocol. The dedicated recovery CLI defaults to AWS KMS and only permits local KMS when `WE3_BACKUP_KMS_PROVIDER=local` and `WE3_ALLOW_LOCAL_BACKUP_KMS=1` are both explicitly set. Documentation states that local KMS remains test/development key custody.

### 18. Backup catalogue did not survive process restart

**Problem:** the old manager stored backup records only in `_backups`, so a new CLI process could not reliably list, verify, or plan from a previously created backup.

**Correction:** the operational backup root now contains atomically written `backup_catalog.v2.json`. It binds each full/WAL backup record to database identity, hashes, signer, storage location/version, and verification state and is loaded on manager startup.

**Boundary:** this solves restart durability, not distributed multi-writer coordination or immutable storage. Current documentation states that managed object lock, replication, legal hold, cross-host writes, and storage SLAs still belong to the deployment.

### 19. WAL planning used synthetic names rather than WAL evidence

**Problem:** the earlier planner manufactured placeholder `segment_0`-style values and WAL archival was metadata-only.

**Correction:** WAL ingestion now accepts actual PostgreSQL 24-hex WAL files, checks size/timeline against the base backup, encrypts/signs them, prevents conflicting content for an existing segment identity, and persists them in the catalogue. Planning sorts real PostgreSQL segment indices and fails when coverage does not begin at the base segment or contains a gap through the recovery target.

### 20. Restore success was previously a log message

**Problem:** `execute_isolated_restore()` previously logged the intended restore and returned success without starting a restored database.

**Correction:** the recovery orchestrator now verifies/decrypts selected objects, safely extracts the physical backup, creates PostgreSQL recovery configuration, starts a loopback-only restored server with `pg_ctl`, waits for the requested timestamp/LSN and promotion, performs reconciliation, stops the server, and retains measured restore evidence. Startup, target, integrity, or reconciliation failure prevents success.

### 21. Recovery reconciliation queried the wrong persistence concepts

**Problem:** the old reconciliation code searched for pending outbox state and provenance inside `audit_events.payload_json`, even though the repository has real `outbox_events` and `provenance_edges` tables. It also treated non-empty audit hashes as evidence of a valid chain.

**Correction:** reconciliation now queries the actual tables. Canonical audit hashing was refactored into a shared `compute_audit_event_hash()`/`verify_audit_records()` path so normal audit verification and recovery use the same definition. Recovery compares per-project terminal audit roots against a signed baseline.

### 22. Recovery needed an expected-state contract, not only intact bytes

**Problem:** a cryptographically intact backup can still restore the wrong logical recovery point.

**Correction:** WE3 now captures a signed `RecoveryBaseline` containing expected run/classification/metric/gate/provenance/outbox populations and audit roots. Restore planning and reconciliation require that baseline's hash/signature/trust. Baseline capture refuses to sign an already broken audit chain.

### 23. Recovery tests previously proved scaffolding, not recovery

**Problem:** old integration tests created fake metadata and deliberately asserted that real restore was unimplemented. That was appropriate while the code was a scaffold, but it could not validate issue #38.

**Correction:** the ordinary unit suite now covers AEAD tampering, KMS identity, PostgreSQL URL/WAL semantics, signed baseline trust, catalogue reload, manifest/ciphertext corruption, and actual WAL planning. Reconciliation unit tests exercise the real outbox/provenance/audit schema contract.

A separate runtime integration test initializes a disposable PostgreSQL cluster, creates a real physical encrypted backup, mutates state, archives real WAL, exercises missing-WAL/signature/ciphertext negative cases, restores to a second loopback PostgreSQL instance, and requires reconciliation to pass. The test is opt-in locally and enabled by the dedicated CI recovery job.

### 24. Recovery schema lagged behind implementation identity

**Problem:** migration `006_backup_and_recovery` represented the earlier design and lacked the system/timeline/WAL/ciphertext/manifest/signer/storage fields needed by the implemented recovery model.

**Correction:** migration history remains intact. New migration `008_backup_evidence_v2` augments the existing tables instead of editing an old migration in place. It adds the recovery identities and checks needed to mirror the operational catalogue in a managed control plane.

### 25. Recovery CLI needed its own explicit contract

**Problem:** historical flat `we3 backup-*` commands were designed around the scaffold and could not cleanly express the new KMS, signer trust, signed baseline, target LSN, or isolated restore inputs. Some historical examples also implied a SQLite/default path for physical backup behavior.

**Correction:** `pyproject.toml` now exposes `we3-backup`, a dedicated PostgreSQL/KMS-aware CLI with `create`, `wal-archive`, `list`, `verify`, `capture-baseline`, `plan`, and `restore`. Makefile recovery targets use this interface. Current documentation treats the old flat commands as compatibility surface rather than the supported operator contract.

### 26. Game-day documentation described commands and execution that do not exist

**Problem:** the old game-day runbook said the matrix had 19 scenarios, documented `we3 game-day run`, `run-scenario`, load/concurrency flags, and described integration points in a way that suggested real infrastructure faults were being injected.

**Finding:** `GameDayOrchestrator.FAILURE_MATRIX` currently contains **25 scenarios across 14 categories**. The CLI exposes `we3 game-day --context ...`, not subcommands. The current orchestrator simulates phase timing/state and report/findings logic; it does not itself restart PostgreSQL, partition a network, disable an IdP/provider, or invoke the physical recovery subsystem.

**Correction:** the runbook now describes the simulator as a scenario/orchestration layer, documents the executable CLI, lists the 25 source-defined scenarios, explains synthetic versus runtime metrics, and shows how real component evidence—such as `we3-backup` recovery evidence—should be composed into a governed game day.

### 27. Audit-service “fail-closed” wording contradicted code

**Problem:** `AuditService.log_event()` caught ledger exceptions, logged the failure, and returned an empty string, while its module/comment called this “fail-closed.” That phrase implies the surrounding operation is blocked, which is not what the wrapper does.

**Correction:** source comments and `SECURITY.md` now call the wrapper **non-blocking** and identify the empty hash as its failure signal. The underlying `AuditLedger.append()` still raises. Security-sensitive callers that require durable audit evidence must check the returned hash or enforce a fail-closed policy at their service boundary rather than assuming the convenience wrapper aborts work automatically.

## Recovery architecture and assurance after issue #38

The recovery implementation can now justify source-level claims that WE3 supports:

- streaming encrypted PostgreSQL physical backup;
- KMS-wrapped DEKs and bounded KMS identity;
- signed canonical backup/WAL manifests;
- plaintext/ciphertext integrity verification;
- restart-durable local catalogue state;
- real WAL-file ingestion and gap checking;
- signed expected-state recovery baselines;
- actual loopback PostgreSQL PITR execution;
- real-schema outbox/provenance reconciliation;
- cryptographic audit-chain verification;
- measured restore evidence;
- a real disposable PostgreSQL runtime exercise in CI.

Those claims do **not** establish that an arbitrary private deployment meets a 15-minute RPO or four-hour RTO, uses an approved KMS policy, stores backups on immutable/replicated media, supports user-defined tablespaces through the native path, has adequate operator staffing, or has approved return-to-service authority. Those remain environment-specific evidence requirements.

## Current visual provenance

Canonical current GUI captures remain under:

```text
docs/assets/gui/current/
├── 01-endpoints.webp
├── 02-models.webp
├── 03-generate.webp
├── 04-charts.webp
└── 05-reports.webp
```

`docs/assets/gui/README-current-captures.md` records their interpretation/provenance rules. The older six PNGs remain historical point-in-time captures. Chart examples under `docs/assets/charts/` demonstrate visualization capability but are not automatically current run evidence.

The static SVG architecture diagrams are repository-authored explanatory diagrams rather than runtime measurement artifacts.

## Historical material preserved

No file under `docs/Plans_/` or `docs/08-planning/Plans_/` is rewritten by this reconciliation. Superseded public documentation under `.archive/documentation/` remains available. Historical test reports retain their original claims as evidence about those snapshots rather than being silently rewritten to match current source.

The 2026-08-01 master security assessment remains point-in-time evidence. New recovery code and tests are documented by current status/security/operations material instead of retroactively changing the historical assessment's observations.

## Remaining assurance work

This pass aligns a broad set of source, tests, public documentation, and operational instructions, but it does not turn the repository into evidence about an unobserved production environment. Before merge/release, the branch still needs its configured CI results to be observed. Before production certification, the target deployment still needs its private runtime-assurance matrix, including real providers, identity, KMS/storage, network controls, restore exercises at target scale, observability, and accountable approvals.

Future documentation changes should continue to apply the same rule:

**implemented code can justify an implementation claim; supported composition can justify a supported-path claim; only executed and retained evidence can justify a runtime/certification claim.**
