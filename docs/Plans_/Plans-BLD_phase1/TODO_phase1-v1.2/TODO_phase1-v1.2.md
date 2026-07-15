# Wilson Eval3ngine Flagship Production Engineering TODO

## Delivery Summary

| Epic name | Tasks by priority (P0/P1/P2/P3) | Total estimated hours | Top 3 highest-risk tasks |
|---|---:|---:|---|
| Epic 1 — Evidence, Governance, and Architecture | 5/1/0/0 | 50h | **T1.1.1** — Unverified repository state could invalidate all sequencing.<br>**T1.1.3** — Platform-service mismatch could force architecture redesign.<br>**T1.1.4** — Late compliance/residency findings could block production. |
| Epic 2 — Contracts, Dataset, and Expectations | 7/1/0/0 | 120h | **T2.1.1** — Denominator or label drift could reverse release decisions.<br>**T2.1.4** — Poisoned/leaked benchmark content could invalidate certification.<br>**T2.1.7** — Observation leakage could turn grading into hidden policy. |
| Epic 3 — Persistence, Evidence, and Data Lifecycle | 4/2/0/0 | 96h | **T3.1.2** — A missing scope control could leak cross-project evidence.<br>**T3.1.3** — Mutable or partial artifacts could break reproducibility.<br>**T3.1.5** — Lifecycle/backfill defects could destroy historical truth. |
| Epic 4 — Execution, Scheduling, and Providers | 6/2/0/0 | 116h | **T4.1.2** — Lease races could lose or duplicate logical runs.<br>**T4.1.5** — Provider-specific drift could silently alter semantics.<br>**T4.1.7** — Bad limits could overspend or starve certification. |
| Epic 5 — Grading, Statistics, Review, and Release Gates | 7/2/0/0 | 132h | **T5.1.2** — Prompt injection could coerce a privileged judge.<br>**T5.1.4** — Invalid clustering could create false statistical confidence.<br>**T5.1.8** — Gate or override defects could authorize an unsafe release. |
| Epic 6 — Identity, Security, and Supply Chain | 4/3/0/0 | 112h | **T6.1.2** — Authorization gaps could expose restricted tenant data.<br>**T6.1.3** — Key compromise could forge dossiers or expose credentials.<br>**T6.1.5** — Active content could compromise reviewers. |
| Epic 7 — API, CLI, Reporting, and User Workflows | 2/4/0/0 | 92h | **T7.1.1** — API ambiguity could duplicate or authorize mutations.<br>**T7.1.3** — Reports could hide stale, excluded, or inconsistent data.<br>**T7.1.4** — Drill-down could overexpose harmful evidence. |
| Epic 8 — Observability, Performance, Resilience, and Delivery | 5/4/1/1 | 164h | **T8.1.5** — A partial restore could sever evidence lineage.<br>**T8.1.7** — Version skew could make rollback unsafe.<br>**T8.1.8** — Stale or weak evidence could produce false certification. |
| **Total** | **40/19/1/1** | **882h** | Certification remains prohibited until T8.1.8 passes. |

## Evidence Boundary

No repository, CI system, runtime, cloud account, or remote host was independently inspected. Source-reported results are historical evidence only; commands are future runbook actions for authorized `{REMOTE_EXEC_CONTEXT}`.

- **Primary architecture and source-reported delivery evidence:** `/mnt/data/Pasted markdown.md` (embeds ADR-001–ADR-005, `threat-model.md`, `foundation-runbook.md`, `Plan_conceptual-v1.md`, `Plan_conceptual-v2.md`, `framework_status.md`, `implementation_blueprint.md`, `source_evidence.md`, `test_report.md`, and `DELIVERY_NOTES.md`).
- **Identity and directory-security reference corpus:** `/mnt/data/ALL-ActDir-GPT-k.md_.md`, `/mnt/data/ALL-ActDir-GPT-k.md_-1.md`, `/mnt/data/ActiveDirect-GPT-k-1.md_.md`, `/mnt/data/ActiveDirect-GPT-k-1.md_-1.md`.
- **Web, CVE, and defensive-testing reference corpus:** `/mnt/data/1.0SWebApp-GPT-k-1.md_.md`, `/mnt/data/ALL-CVE-GPT-k-1.md_.md`, `/mnt/data/ALL-DEFENCE-GPT-k-1.md_.md`, `/mnt/data/GeneralScan-Gpt-k-1.md_.md`.
- **Crypto, forensics, network, logging, and supply-chain reference corpus:** `/mnt/data/ALL-CRYPTO-GPT-k.md_.md`, `/mnt/data/ALL-CRYPTO-GPT-k.md_-1.md`, `/mnt/data/CTF-Notes-PDF-GPT-k.md_.md`, `/mnt/data/MetaCTF-Crypto-GPT-k.md_.md`, `/mnt/data/NTFSAna-GPT-k.md_.md`, `/mnt/data/forensics.md`, `/mnt/data/newest-rudi-kcrypto.md`, `/mnt/data/rudi-kevert.md`, `/mnt/data/rudievery-k.md`, `/mnt/data/tools_and_usage_-1.md_11.md`.

The supporting corpus is non-authoritative for WE3 architecture and is used only to seed defensive tests.

## Resolved Platform Context

| Placeholder | Resolution |
|---|---|
| `{PLATFORM_NAME}` | Wilson Eval3ngine (source-resolved). |
| `{VERSION_TAG}` | Source-reported `0.1.0 Foundation`; current repository version is (ASSUMED) [A-001]. |
| `{COMPONENT_SCOPE}` | Entire supplied WE3 foundation/target architecture; current repository scope is validated by T1.1.1. |
| `{TECH_STACK}` | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Typer, PyYAML, Uvicorn, `cryptography`. |
| `{DATA_STORES}` | SQLite/local filesystem for development only; PostgreSQL plus immutable S3-compatible object storage for production. |
| `{OBSERVABILITY_STACK}` | OpenTelemetry-compatible; concrete backend is (ASSUMED) [A-003]. |
| `{API_CONTRACT}` | Versioned JSON REST `/v1`, generated OpenAPI, cursor pagination, idempotency keys, ETags, operation resources. |
| `{RETRIEVAL_CONTEXT} / {ACCELERATOR_CONTEXT}` | Not evidenced for the initial release; validation T8.1.10. |
| `{DEPLOYMENT_SCOPE}` | Target includes staging/production, but actual environment/topology is (ASSUMED) [A-003]. |
| `{REMOTE_EXEC_CONTEXT}` | Unresolved and validated by T1.1.3 before commands are run. |

## Assumption-to-Validation Register

| Assumption ID | Unsupported conclusion | Exactly one validation task |
|---|---|---|
| A-001 | Current repository, version, generated artifacts, and claimed foundation state are unverified. | T1.1.1 |
| A-002 | The source-proposed staffing and decision-authority model is available. | T1.1.2 |
| A-003 | Single-region production plus required platform/managed services and remote execution context are available. | T1.1.3 |
| A-004 | No undisclosed compliance, residency, retention, or content-class obligation changes the design. | T1.1.4 |
| A-005 | Release populations, minimum family support, and first-release language scope can be approved as proposed. | T2.1.3 |
| A-006 | Initial workload fits the PostgreSQL leasing and materialized-view envelope. | T4.1.1 |
| A-007 | Two hosted providers are the correct initial production scope. | T4.1.4 |
| A-008 | Prompt family is the valid statistical cluster and an independent reference implementation is available. | T5.1.4 |
| A-009 | Qualified reviewers can meet critical-case completion and safety requirements. | T5.1.6 |
| A-010 | Retrieval, vector storage, embeddings, and accelerators are not required for the initial production release. | T8.1.10 |

## Conflict Register

| Conflict | Safest interpretation | Exactly one follow-up |
|---|---|---|
| `implementation_blueprint.md` §1.3 says implementation-empty; `DELIVERY_NOTES.md`/`test_report.md` report a runnable 0.1.0 foundation; ADR-001 is duplicated. | Treat delivery/test claims as historical, current repository state as unknown, and normalize one ADR only after evidence reconciliation. | **T1.1.1**, ticket stub `EVID-001`; its output gates T1.1.5. |

## Hierarchical TODO Plan

### Epic 1 — Evidence, Governance, and Architecture

- [ ] - **T1.1.1 — Reconcile source claims with the current repository snapshot**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PROGRAM_OWNER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GOVERNANCE}, {DOMAIN_ARCHITECTURE}
  - **Dependencies:** None
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §1.3/§13, `DELIVERY_NOTES.md`, `test_report.md`; current repository and `{VERSION_TAG}` are (ASSUMED) [A-001].
  - **Acceptance Criteria:** A hash-addressed inventory records every supplied source and discovered repository artifact; Claimed versus verified capabilities, CI state, logs/metrics/traces availability, and compatibility risks are mapped with no unqualified execution claim.
  - **Steps / Subtasks:**
    - Commands to Run ({REMOTE_EXEC_CONTEXT}): `mkdir -p evidence && git status --short --branch > evidence/git-status.txt && git rev-parse HEAD > evidence/git-head.txt && git ls-files | sort > evidence/repository-files.txt`.
    - When authorized, run `bash -o pipefail -c 'python -m pytest -q --maxfail=1 2>&1 | tee evidence/pytest.txt'` and `bash -o pipefail -c 'we3 validate examples/experiments/foundation.yaml 2>&1 | tee evidence/we3-validate.txt'`.
  - **Risks & Mitigations:** Historical delivery notes may not match the current tree. / Block implementation sequencing until discrepancies are classified and owned.
  - **Tags:** [evidence] [repository-audit] [P0]

- [ ] - **T1.1.2 — Validate staffing, RACI, and decision authority**
  - **Priority:** P0
  - **Est. Effort:** 6h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PROGRAM_OWNER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GOVERNANCE}, {DOMAIN_DELIVERY}
  - **Dependencies:** None
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-002, §27.1, §30; staffing availability is (ASSUMED) [A-002].
  - **Acceptance Criteria:** Named accountable roles cover architecture, measurement, safety, security, SRE, curation, review, and release authority; Every P0/P1 workstream has one accountable approver and no prohibited separation-of-duties overlap.
  - **Steps / Subtasks:**
    - Map available people to the source RACI and weekly decision cadence.
    - Record reviewer pool, on-call ownership, escalation paths, and approval quorum.
  - **Risks & Mitigations:** Understaffing can force unsafe role consolidation. / Gate parallel execution and production scope to funded capacity.
  - **Tags:** [raci] [staffing] [governance]

- [ ] - **T1.1.3 — Validate production operating context and platform services**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PLATFORM_ARCHITECT} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_ARCHITECTURE}, {DOMAIN_INFRASTRUCTURE}, {DOMAIN_OBSERVABILITY}
  - **Dependencies:** T1.1.1
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-003/ASM-005, §24, §34.9; deployment, managed services, observability vendor, and `{REMOTE_EXEC_CONTEXT}` are (ASSUMED) [A-003].
  - **Acceptance Criteria:** A signed decision identifies region model, orchestrator, PostgreSQL, object store, OIDC, KMS/secrets, telemetry backend, and network-policy capabilities; Environment boundaries for local, integration, staging, and production are documented with credentials and data classes.
  - **Steps / Subtasks:**
    - Inventory approved cloud/platform services and existing IaC standards.
    - Define production invariants and exact remote execution/audit channel.
  - **Risks & Mitigations:** A platform mismatch can invalidate identity, storage, and DR design. / Decide before migrations, IaC, or security-control implementation.
  - **Tags:** [platform-decision] [infrastructure] [assumption]

- [ ] - **T1.1.4 — Approve compliance, residency, retention, and content classes**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SECURITY_OWNER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GOVERNANCE}, {DOMAIN_SECURITY}, {DOMAIN_PRIVACY}
  - **Dependencies:** T1.1.1
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-009, §5.4 Q-002/Q-008, §15.3; binding obligations are (ASSUMED) [A-004].
  - **Acceptance Criteria:** Legal/security approval records applicable regimes, residency, retention, legal hold, deletion, export, and incident-notification duties; Each Public/Internal/Confidential/Restricted/Secret class has storage, key, access, telemetry, and disposal rules.
  - **Steps / Subtasks:**
    - Run a data-flow and jurisdiction workshop using the threat-model assets.
    - Create a decision record and control-to-requirement mapping.
  - **Risks & Mitigations:** Late compliance discovery can require redesign or data relocation. / Freeze data classes and residency before production persistence is provisioned.
  - **Tags:** [compliance] [data-classification] [privacy]

- [ ] - **T1.1.5 — Ratify modular-monolith boundaries and split triggers**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PRINCIPAL_ARCHITECT} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_ARCHITECTURE}, {DOMAIN_GOVERNANCE}
  - **Dependencies:** T1.1.1
  - **Evidence:** `Pasted markdown.md` → ADR-001, `Plan_conceptual-v2.md` §F.0A/§F.7, `implementation_blueprint.md` §6/§13; duplicate ADR-001 text is an input-normalization issue.
  - **Acceptance Criteria:** One accepted ADR defines domain dependency direction, deployable processes, shared contract ownership, and forbidden cross-boundary imports; Split triggers are measurable: credentials, sustained scaling, isolation, residency, ownership, runtime, or cadence.
  - **Steps / Subtasks:**
    - Normalize duplicate ADR content into one authoritative record.
    - Map modules to API, scheduler, executors, graders, review, metrics, evidence, and maintenance processes.
  - **Risks & Mitigations:** Premature services can create contract and policy drift. / Require measured triggers and shared versioned contracts before any split.
  - **Tags:** [architecture] [modular-monolith] [adr]

- [ ] - **T1.1.6 — Create requirements traceability and architecture-conformance gates**
  - **Priority:** P1
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GOVERNANCE}, {DOMAIN_TESTING}, {DOMAIN_ARCHITECTURE}
  - **Dependencies:** T1.1.2, T1.1.5
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §4, §20, §21, §28; `docs/requirements_catalog.csv` is source-reported but repository existence is covered by T1.1.1.
  - **Acceptance Criteria:** Every Must requirement maps to one owner, component, test ID, release gate, and evidence artifact; CI fails on orphan requirements, missing tests, or unauthorized architecture dependencies.
  - **Steps / Subtasks:**
    - Define the machine-readable traceability schema and evidence index.
    - Add conformance checks for module imports, contract ownership, and release-gate linkage.
  - **Risks & Mitigations:** Traceability can become documentation-only theater. / Make missing links blocking and independently reviewed.
  - **Tags:** [traceability] [fitness-functions] [testing]

### Epic 2 — Contracts, Dataset, and Expectations

- [ ] - **T2.1.1 — Freeze taxonomy, counting rules, and critical-event precedence**
  - **Priority:** P0
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_MEASUREMENT_OWNER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_CONTRACTS}, {DOMAIN_METRICS}, {DOMAIN_SAFETY}
  - **Dependencies:** T1.1.5
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §B–D/§AA; `implementation_blueprint.md` FR-007/FR-009/FR-011 and RG-01.
  - **Acceptance Criteria:** Approved decision tables cover appropriate refusal, false refusal, safe useful compliance, unsafe compliance, and ambiguous/partial outcomes; Strict/nominal denominators reconcile and reliability failures never enter behavioral numerators.
  - **Steps / Subtasks:**
    - Version enums, secondary labels, exclusion reasons, and invariants.
    - Approve boundary examples for authorization, partial refusal, leakage, tool use, and reliability failure.
  - **Risks & Mitigations:** Ambiguous labels can silently change release decisions. / Use golden boundary cases and semantic versioning for all score-affecting changes.
  - **Tags:** [taxonomy] [metrics] [safety]

- [ ] - **T2.1.2 — Establish the versioned schema and contract registry**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_BACKEND_ARCHITECT} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_CONTRACTS}, {DOMAIN_API}, {DOMAIN_DATA}
  - **Dependencies:** T1.1.5, T2.1.1
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §J/V/W, `implementation_blueprint.md` FR-001/FR-002/DATA-001, recommended `contracts/`, `configs/schemas/`, `datasets/schemas/`.
  - **Acceptance Criteria:** JSON/YAML/API/event/artifact schemas reject unknown fields and publish deterministic hashes; Backward/forward compatibility policy and semantic-version rules are executable in CI.
  - **Steps / Subtasks:**
    - Inventory or define experiment, case, provider, response, expectation, classification, metric, threshold, event, and dossier contracts.
    - Generate JSON Schema/OpenAPI from typed definitions and store compatibility fixtures.
  - **Risks & Mitigations:** Divergent schemas can corrupt lineage and clients. / Make the registry single-source and block incompatible changes.
  - **Tags:** [schemas] [contracts] [versioning]

- [ ] - **T2.1.3 — Validate benchmark populations, support, and language scope**
  - **Priority:** P0
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATASET_CURATOR} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DATASET}, {DOMAIN_STATISTICS}, {DOMAIN_GOVERNANCE}
  - **Dependencies:** T1.1.4, T2.1.1
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-010, §5.4 Q-001, §35.3; release population and language support are (ASSUMED) [A-005].
  - **Acceptance Criteria:** Approved scope defines categories, severities, authorization states, tool-use modes, languages, hidden splits, and minimum independent-family support; Power/sample analysis documents where certification is pass-capable versus indeterminate-only.
  - **Steps / Subtasks:**
    - Preregister target populations and exclusion rules.
    - Quantify current/source-reported eight-family gap against provisional thirty-family support and production needs.
  - **Risks & Mitigations:** An imbalanced benchmark can hide rare critical failures. / Require risk-weighted cells, minimal pairs, and indeterminate outcomes for unsupported slices.
  - **Tags:** [benchmark] [population] [assumption]

- [ ] - **T2.1.4 — Build dataset supply-chain and promotion controls**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATA_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DATASET}, {DOMAIN_PROVENANCE}, {DOMAIN_SECURITY}
  - **Dependencies:** T2.1.2, T2.1.3
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §E, `implementation_blueprint.md` FR-002/PRIV-001/DATA-003.
  - **Acceptance Criteria:** Draft→reviewed→approved→deprecated transitions require dual approval, immutable manifests, hashes, split rules, and provenance; Promotion rejects duplicate IDs/content, contamination, prohibited data, unsigned sources, and missing policy/rubric links.
  - **Steps / Subtasks:**
    - Define case/manifest validators and source-to-benchmark lineage.
    - Add de-identification, contamination, near-duplicate, license, and coverage checks.
  - **Risks & Mitigations:** Poisoned or leaked cases can invalidate certification. / Use signed manifests, canaries, dual review, and immutable releases.
  - **Tags:** [dataset-governance] [provenance] [supply-chain]

- [ ] - **T2.1.5 — Curate and dual-review benchmark tranche A**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATASET_CURATOR} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DATASET}, {DOMAIN_SAFETY}
  - **Dependencies:** T2.1.4
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §E.3–E.7 and backlog B-004; tranche size must follow T2.1.3.
  - **Acceptance Criteria:** One approved tranche fits the validated hour cap and covers benign compliance, appropriate refusal, false refusal, and safe-redirection boundaries; Every family has minimal pairs, policy/rubric versions, source provenance, expected treatment, and two independent reviews.
  - **Steps / Subtasks:**
    - Curate the highest-risk core cells first.
    - Resolve disagreements through adjudication, not majority overwrite.
  - **Risks & Mitigations:** Fast curation can encode policy bias. / Use blind dual review and explicit disagreement records.
  - **Tags:** [benchmark] [curation] [golden-data]

- [ ] - **T2.1.6 — Curate and dual-review benchmark tranche B**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATASET_CURATOR} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DATASET}, {DOMAIN_SAFETY}, {DOMAIN_SECURITY}
  - **Dependencies:** T2.1.5
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §E.3/§E.11, threat-model assets, and supporting hostile-content corpus inventory.
  - **Acceptance Criteria:** One approved tranche fits the validated hour cap and covers critical harm, authorization counterfactuals, tool simulation, injection, malformed content, and rare/outlier cases; All attachments/tool fixtures are inert or simulated and classification/retention metadata is complete.
  - **Steps / Subtasks:**
    - Select underrepresented high-severity and hostile cells.
    - Create deterministic tool/attachment fixtures without live harmful actions.
  - **Risks & Mitigations:** Hostile fixtures may endanger reviewers or systems. / Use quarantine, inert rendering, simulators, and need-to-know access.
  - **Tags:** [benchmark] [adversarial-cases] [reviewer-safety]

- [ ] - **T2.1.7 — Implement deterministic expectation compilation**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SAFETY_BACKEND_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_EXPECTATIONS}, {DOMAIN_CONTRACTS}, {DOMAIN_SAFETY}
  - **Dependencies:** T2.1.1, T2.1.2, T2.1.4
  - **Evidence:** `Pasted markdown.md` → ADR-004, `Plan_conceptual-v2.md` §G.0, `implementation_blueprint.md` FR-003.
  - **Acceptance Criteria:** Expectation records are compiled and persisted before provider execution from approved case, policy, rubric, and compiler versions; Identical canonical inputs reproduce the same hash; any score-affecting change creates a new immutable record.
  - **Steps / Subtasks:**
    - Define trusted input ordering and canonical serialization.
    - Implement decision-rule diagnostics and explicit failure states.
  - **Risks & Mitigations:** Observation leakage can turn the grader into an unreviewed policy engine. / Enforce process/data separation and pre-execution persistence.
  - **Tags:** [expectations] [determinism] [policy]

- [ ] - **T2.1.8 — Execute contract and dataset hostile-input tests**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_CONTRACTS}, {DOMAIN_DATASET}
  - **Dependencies:** T2.1.2, T2.1.7
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1/§N.2; supporting corpora: `1.0SWebApp-GPT-k-1.md_.md`, `ALL-CVE-GPT-k-1.md_.md`, `forensics.md`.
  - **Acceptance Criteria:** Tests cover common flows, malformed/unknown fields, duplicate keys, hash tampering, huge payloads, Unicode/confusables, version skew, hostile prompts, partial files, and replay; Property/mutation tests catch denominator, label, canonicalization, and exclusion drift.
  - **Steps / Subtasks:**
    - Build schema, property, golden, mutation, and fuzz fixtures.
    - Assert resource limits and safe error redaction.
  - **Risks & Mitigations:** Parsers may accept ambiguous or resource-exhausting inputs. / Fail closed with bounded parsing and mutation-tested invariants.
  - **Tags:** [contract-testing] [fuzzing] [hostile-input]

### Epic 3 — Persistence, Evidence, and Data Lifecycle

- [ ] - **T3.1.1 — Create core PostgreSQL schema and ordered migrations**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATA_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PERSISTENCE}, {DOMAIN_DATA}
  - **Dependencies:** T2.1.2
  - **Evidence:** `Pasted markdown.md` → ADR-002, `Plan_conceptual-v2.md` §J.1/§J.12, `implementation_blueprint.md` §7/§26.
  - **Acceptance Criteria:** Migrations cover projects, versions, experiments, runs, attempts, jobs, reviews, snapshots, gates, and audit metadata with typed constraints; Prerequisites and expand→backfill→switch→contract order are explicit; upgrade and rollback pass against historical fixtures.
  - **Steps / Subtasks:**
    - Model state-machine checks, logical-run uniqueness, foreign keys, and JSONB extension fields.
    - Create migration verification queries and rollback notes for each revision.
  - **Risks & Mitigations:** Irreversible schema changes can strand workers or history. / Use expand/contract and one-release read compatibility.
  - **Tags:** [postgresql] [migrations] [schema]

- [ ] - **T3.1.2 — Enforce project keys, RLS, and database authorization**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SECURITY_BACKEND_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PERSISTENCE}, {DOMAIN_IDENTITY}, {DOMAIN_SECURITY}
  - **Dependencies:** T3.1.1, T1.1.3
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §F.8/§J.11, `implementation_blueprint.md` SEC-002/B-003.
  - **Acceptance Criteria:** Every business row carries project scope; RLS denies cross-project reads/writes under API and worker identities; Migration owner bypass is isolated, audited, and unavailable to application roles.
  - **Steps / Subtasks:**
    - Define role grants, session project binding, and policy migrations.
    - Add composite uniqueness/indexes that include project ID.
  - **Risks & Mitigations:** A single missing predicate can expose restricted evidence. / Use database-enforced policy plus exhaustive negative tests.
  - **Tags:** [rls] [multi-project] [authorization]

- [ ] - **T3.1.3 — Implement immutable content-addressed object storage**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_EVIDENCE}, {DOMAIN_STORAGE}, {DOMAIN_SECURITY}
  - **Dependencies:** T1.1.3, T3.1.1
  - **Evidence:** `Pasted markdown.md` → ADR-003, `implementation_blueprint.md` FR-006/SEC-006; local filesystem is development-only.
  - **Acceptance Criteria:** S3-compatible writes are SHA-256 addressed, write-once/versioned, encrypted, project/classification scoped, and verified on put/get/head; Metadata includes media type, size, classification, retention, legal hold, source, and hash.
  - **Steps / Subtasks:**
    - Implement object-key policy and envelope-encryption integration.
    - Handle idempotent same-hash writes and reject hash/content collisions.
  - **Risks & Mitigations:** Partial or mutable writes can invalidate evidence lineage. / Require atomic commit markers, versioning, and verification before state advance.
  - **Tags:** [object-storage] [content-addressing] [integrity]

- [ ] - **T3.1.4 — Implement provenance, transactional outbox, and audit linkage**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_BACKEND_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PROVENANCE}, {DOMAIN_PERSISTENCE}, {DOMAIN_AUDIT}
  - **Dependencies:** T3.1.1, T3.1.3
  - **Evidence:** `Pasted markdown.md` → ADR-002/ADR-003, `Plan_conceptual-v2.md` §H.10/§J.9, `implementation_blueprint.md` DATA-003/SEC-007.
  - **Acceptance Criteria:** Every source→case→prompt→expectation→attempt→response→grade→snapshot→gate→dossier edge resolves and hash-verifies; Domain state and outbox event commit atomically; consumers are replay-safe and deduplicate by event ID.
  - **Steps / Subtasks:**
    - Define event envelope, ordering expectations, and consumer idempotency keys.
    - Link audit previous-hash and external-checkpoint references.
  - **Risks & Mitigations:** Dual writes or replay can create invisible gaps or duplicate effects. / Use one transaction, idempotent consumers, and periodic reconciliation.
  - **Tags:** [provenance] [outbox] [audit]

- [ ] - **T3.1.5 — Implement lifecycle, regrade, backfill, and rollback workflows**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DATA_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DATA}, {DOMAIN_GOVERNANCE}, {DOMAIN_EVIDENCE}
  - **Dependencies:** T3.1.1, T3.1.3, T3.1.4, T1.1.4
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §26/§27, FR-013, PRIV-002.
  - **Acceptance Criteria:** Regrades and recomputations create new immutable versions and preserve prior snapshots/classifications; Retention, legal hold, deletion tombstones, cryptographic deletion, and restore precedence pass a policy matrix.
  - **Steps / Subtasks:**
    - Define lifecycle jobs and approvals by data class.
    - Implement resumable bounded backfills with dry-run reports.
  - **Risks & Mitigations:** Backfill or deletion bugs can destroy reproducibility. / Use immutable history, hold precedence, dry runs, and hash reconciliation.
  - **Tags:** [lifecycle] [backfill] [regrade]

- [ ] - **T3.1.6 — Run persistence and evidence failure-injection tests**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_PERSISTENCE}, {DOMAIN_EVIDENCE}
  - **Dependencies:** T3.1.2, T3.1.3, T3.1.4, T3.1.5
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1 and certification durability/integrity criteria.
  - **Acceptance Criteria:** Tests cover concurrent writes, replay, stale leases, DB restart, network partition, object delay/failure, partial upload, corruption, hash collision simulation, orphan rows/objects, large artifacts, and version skew; No accepted logical run is lost or duplicated; corrupted evidence blocks grading/publication.
  - **Steps / Subtasks:**
    - Automate fault fixtures and reconciliation assertions.
    - Capture before/after row, object, audit, and outbox counts.
  - **Risks & Mitigations:** Fault tests may miss cross-store timing windows. / Use deterministic barriers plus repeated randomized concurrency runs.
  - **Tags:** [failure-injection] [data-integrity] [resilience]

### Epic 4 — Execution, Scheduling, and Providers

- [ ] - **T4.1.1 — Validate workload and PostgreSQL queue envelope**
  - **Priority:** P0
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PERFORMANCE_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_EXECUTION}, {DOMAIN_CAPACITY}, {DOMAIN_PERSISTENCE}
  - **Dependencies:** T1.1.3
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-004, §16, §34.17; volume/concurrency are (ASSUMED) [A-006].
  - **Acceptance Criteria:** Forecast covers monthly runs, peak leases/s, token rates, response sizes, grading fan-out, human escalation, report concurrency, and retention growth; A reproducible model confirms the PostgreSQL lease design or opens an ADR with measured alternatives.
  - **Steps / Subtasks:**
    - Collect stakeholder forecast and source-reported design bounds.
    - Create mock-provider load profiles and acceptance thresholds.
  - **Risks & Mitigations:** Underestimated load can cause queue starvation and lost SLOs. / Validate early and preserve broker/workflow migration triggers.
  - **Tags:** [capacity] [queue] [assumption]

- [ ] - **T4.1.2 — Implement durable leasing scheduler and reconciliation**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_EXECUTION}, {DOMAIN_SCHEDULER}, {DOMAIN_PERSISTENCE}
  - **Dependencies:** T3.1.1, T3.1.4, T4.1.1
  - **Evidence:** `Pasted markdown.md` → ADR-002, `Plan_conceptual-v2.md` §H, `implementation_blueprint.md` OPS-004/§34.7.
  - **Acceptance Criteria:** `FOR UPDATE SKIP LOCKED` leasing supports priorities, lease expiry, heartbeat, bounded retries, poisoned/dead-letter state, pause/resume/cancel, and reconciliation; Worker death produces no lost or duplicate logical run; attempts remain distinct from logical runs.
  - **Steps / Subtasks:**
    - Implement explicit run/job state transitions and lease ownership checks.
    - Add stale-job sweeper, reconciliation reports, and admission pause.
  - **Risks & Mitigations:** Lease races can duplicate provider calls or strand work. / Use unique logical keys, fenced updates, heartbeats, and reconciliation.
  - **Tags:** [scheduler] [leasing] [idempotency]

- [ ] - **T4.1.3 — Implement canonical adapter contract and deterministic mock**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_INTEGRATION_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PROVIDERS}, {DOMAIN_CONTRACTS}, {DOMAIN_TESTING}
  - **Dependencies:** T2.1.2, T2.1.7
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §J.4/§J.5, backlog B-010; source reports a mock but current state is governed by T1.1.1.
  - **Acceptance Criteria:** Canonical request/response types preserve exact model config, provider metadata, usage, finish reason, raw hashes, and normalized errors; Mock deterministically simulates success, timeout, 429, 5xx, malformed output, partial response, and identity drift.
  - **Steps / Subtasks:**
    - Define capability negotiation and error taxonomy.
    - Implement attempt deadlines and explicit retryability without implicit retry.
  - **Risks & Mitigations:** Provider-specific behavior may leak into domain logic. / Keep normalization in adapters and enforce shared fixtures.
  - **Tags:** [provider-contract] [mock] [fault-fixtures]

- [ ] - **T4.1.4 — Approve initial provider and model scope**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PRODUCT_OWNER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PROVIDERS}, {DOMAIN_GOVERNANCE}, {DOMAIN_SECURITY}
  - **Dependencies:** T1.1.3, T1.1.4
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-008/Q-003; two hosted providers are (ASSUMED) [A-007].
  - **Acceptance Criteria:** Decision names provider/model IDs, regions, parameters, identity metadata, pricing, quotas, retention terms, and prohibited data classes; Two-provider requirement is approved or replaced with an explicit alternative and risk record.
  - **Steps / Subtasks:**
    - Compare provider capabilities against canonical contract and compliance decisions.
    - Confirm alias behavior, request/response retention, and credential model.
  - **Risks & Mitigations:** Ambiguous model aliases can invalidate comparisons. / Require provider-reported identity and fingerprint canaries.
  - **Tags:** [provider-scope] [model-identity] [assumption]

- [ ] - **T4.1.5 — Implement production provider adapter A**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_INTEGRATION_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PROVIDERS}, {DOMAIN_EXECUTION}
  - **Dependencies:** T4.1.3, T4.1.4
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` backlog B-011 and `implementation_blueprint.md` FR-005/FR-018.
  - **Acceptance Criteria:** Adapter A passes canonical success/error/timeout/usage/identity fixtures and records each attempt separately; Credentials are short-lived and absent from artifacts/telemetry; egress is allowlisted.
  - **Steps / Subtasks:**
    - Implement request mapping, response normalization, deadlines, and retry classification.
    - Capture provider-reported model ID/capabilities and cost inputs.
  - **Risks & Mitigations:** Provider quirks can cause silent semantic drift. / Pin versions, normalize explicitly, and fail on missing gating metadata.
  - **Tags:** [provider-a] [adapter] [integration]

- [ ] - **T4.1.6 — Implement production provider adapter B**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_INTEGRATION_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PROVIDERS}, {DOMAIN_EXECUTION}
  - **Dependencies:** T4.1.3, T4.1.4
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` backlog B-012 and `implementation_blueprint.md` production acceptance.
  - **Acceptance Criteria:** Adapter B passes the identical canonical fixture suite and exposes documented extensions only; Cross-provider comparisons preserve request intent while recording capability differences.
  - **Steps / Subtasks:**
    - Implement mapping and normalized failure behavior independently of Adapter A.
    - Add provider-specific identity probes and cost capture.
  - **Risks & Mitigations:** Superficial fixture parity can hide capability mismatch. / Add negative and differential tests for unsupported features.
  - **Tags:** [provider-b] [adapter] [integration]

- [ ] - **T4.1.7 — Add fingerprints, budgets, backpressure, and rate limits**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_EXECUTION}, {DOMAIN_PROVIDERS}, {DOMAIN_COST}
  - **Dependencies:** T4.1.1, T4.1.2, T4.1.5, T4.1.6
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §H.6/§H.11, K.6, M.7; `implementation_blueprint.md` FR-017/FR-018.
  - **Acceptance Criteria:** Admission and runtime controls enforce cost, tokens, elapsed time, storage, reviewer tasks, per-provider/project quotas, and priority fairness; Provider alias/capability/fingerprint changes mark comparisons pending and alert.
  - **Steps / Subtasks:**
    - Implement token-bucket or persisted quota controls without making Redis authoritative.
    - Add hard/soft budget transitions and safe pause checkpoints.
  - **Risks & Mitigations:** Bad limits can starve critical work or overspend. / Use explicit priority policy, reserved certification capacity, and audited overrides.
  - **Tags:** [backpressure] [budgets] [model-drift]

- [ ] - **T4.1.8 — Run execution resilience and hostile-concurrency tests**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_EXECUTION}, {DOMAIN_PROVIDERS}
  - **Dependencies:** T4.1.2, T4.1.5, T4.1.6, T4.1.7
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1 and platform certification durability criteria.
  - **Acceptance Criteria:** Tests cover common runs, bursts, concurrent lease claims, replay/idempotency, worker kill, scheduler failover, timeouts, retries, 429/5xx, malformed/partial responses, network partitions, large payloads, cancellation races, and version skew; No duplicate logical run or silent model substitution occurs.
  - **Steps / Subtasks:**
    - Use deterministic barriers plus randomized stress and soak profiles.
    - Assert retry budgets and dead-letter transitions.
  - **Risks & Mitigations:** Non-deterministic races can produce flaky evidence. / Control clocks/faults and require reproducible seeds.
  - **Tags:** [concurrency] [resilience] [provider-failures]

### Epic 5 — Grading, Statistics, Review, and Release Gates

- [ ] - **T5.1.1 — Harden deterministic five-outcome grading**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_EVALUATION_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GRADING}, {DOMAIN_SAFETY}, {DOMAIN_METRICS}
  - **Dependencies:** T2.1.1, T2.1.7
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` FR-007, `framework_status.md`, `test_report.md`; current implementation is source-reported only.
  - **Acceptance Criteria:** All five primary outcomes, secondary labels, abstention flags, and reliability terminal states have golden fixtures; Reliability failures remain excluded from behavioral counts and evidence references are complete.
  - **Steps / Subtasks:**
    - Audit or implement extractor, rule, fusion-input, and explanation contracts.
    - Add empty, ambiguous, partial-refusal, mixed-language, and hostile-output cases.
  - **Risks & Mitigations:** Rule shortcuts can misclassify nuanced or adversarial responses. / Escalate uncertainty and preserve evidence for calibrated layers.
  - **Tags:** [grading] [five-outcome] [golden-tests]

- [ ] - **T5.1.2 — Build an isolated schema-only judge runner**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_ML_PLATFORM_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GRADING}, {DOMAIN_SECURITY}, {DOMAIN_INFRASTRUCTURE}
  - **Dependencies:** T1.1.3, T5.1.1
  - **Evidence:** `Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §G.5/L.5, `implementation_blueprint.md` SEC-004.
  - **Acceptance Criteria:** Judge workers have no provider credentials, tools, default egress, writable shared filesystem, or unapproved secrets; Trusted rubric and untrusted evidence are structurally separated; output must validate against a strict schema.
  - **Steps / Subtasks:**
    - Create separate workload identity, image, network policy, and resource limits.
    - Enforce schema retries without relaxing output rules.
  - **Risks & Mitigations:** A manipulated response could turn the judge into an action agent. / Use no-action isolation, strict schema, and adversarial tests.
  - **Tags:** [llm-judge] [isolation] [prompt-injection]

- [ ] - **T5.1.3 — Build grader calibration and hidden-set release harness**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_EVALUATION_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_GRADING}, {DOMAIN_DATASET}, {DOMAIN_GOVERNANCE}
  - **Dependencies:** T2.1.5, T2.1.6, T5.1.1, T5.1.2
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §G.7/N.3 and `implementation_blueprint.md` B-010.
  - **Acceptance Criteria:** Harness reports macro F1, unsafe-compliance recall, subgroup performance, ECE, abstention, disagreement, injection resistance, and confidence intervals; Hidden-set access is separate and every certification grader has an approved version plus rollback version.
  - **Steps / Subtasks:**
    - Define blinded gold ingestion and evaluation protocol.
    - Store immutable calibration snapshots and failure clusters.
  - **Risks & Mitigations:** Overfitting to visible gold can inflate grader quality. / Use hidden partitions, canaries, and independent approval.
  - **Tags:** [calibration] [hidden-set] [grader-governance]

- [ ] - **T5.1.4 — Validate clustering and independent statistical reference**
  - **Priority:** P0
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_STATISTICIAN} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_STATISTICS}, {DOMAIN_METRICS}, {DOMAIN_DATASET}
  - **Dependencies:** T2.1.3, T5.1.3
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-006/Q-010; prompt-family clustering/reference are (ASSUMED) [A-008].
  - **Acceptance Criteria:** Empirical dependence analysis confirms prompt family or selects a better cluster hierarchy; Independent R/Python reference implementation and numeric tolerances are approved.
  - **Steps / Subtasks:**
    - Analyze repeated/minimal-pair correlations and variance components.
    - Cross-check Wilson, bootstrap, and paired methods on fixed fixtures.
  - **Risks & Mitigations:** Wrong clustering can create false precision and unsafe passes. / Use conservative intervals until the unit is validated.
  - **Tags:** [statistics] [cluster-bootstrap] [assumption]

- [ ] - **T5.1.5 — Implement versioned metrics and statistical comparisons**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_MEASUREMENT_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_METRICS}, {DOMAIN_STATISTICS}
  - **Dependencies:** T2.1.1, T5.1.4
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §C/I/AA, `implementation_blueprint.md` FR-009/FR-010/FR-014.
  - **Acceptance Criteria:** Snapshots expose included/excluded runs, numerator, denominator, support, interval, method/version, and input-set hash; Wilson, cluster bootstrap, paired deltas, practical thresholds, drift, and changed-dataset warnings match the approved reference.
  - **Steps / Subtasks:**
    - Implement registry-driven formulas and immutable snapshots.
    - Add deterministic seeds and exact population queries.
  - **Risks & Mitigations:** Metric drift can appear as model drift. / Mutation-test definitions and preserve versioned trends.
  - **Tags:** [metrics] [bootstrap] [comparisons]

- [ ] - **T5.1.6 — Validate reviewer capacity, qualification, and safety model**
  - **Priority:** P0
  - **Est. Effort:** 8h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SAFETY_OPERATIONS_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_REVIEW}, {DOMAIN_SAFETY}, {DOMAIN_GOVERNANCE}
  - **Dependencies:** T1.1.2, T1.1.4, T5.1.3
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-007/Q-007 and `Plan_conceptual-v2.md` §L.10; reviewer operations are (ASSUMED) [A-009].
  - **Acceptance Criteria:** Pilot measures arrival rate, handling time, skill coverage, backlog, critical-case completion, and exposure limits; Approved staffing and queue SLO guarantee unresolved critical reviews block publication.
  - **Steps / Subtasks:**
    - Run a blinded pilot with representative safe/redacted cases.
    - Model peak backlog and release cadence.
  - **Risks & Mitigations:** Review backlog or harm exposure can fail the authority path. / Reserve critical capacity and cap exposure with wellness controls.
  - **Tags:** [human-review] [capacity] [assumption]

- [ ] - **T5.1.7 — Implement human review and adjudication workflow**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_FULL_STACK_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_REVIEW}, {DOMAIN_GOVERNANCE}, {DOMAIN_AUDIT}
  - **Dependencies:** T5.1.3, T5.1.6, T3.1.2
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §G.6–G.10, `implementation_blueprint.md` FR-008/B-011.
  - **Acceptance Criteria:** Rules create review tasks for ambiguity, criticality, disagreement, low confidence, and sampling; blind dual assignment prevents self-adjudication; Submissions, rationale, abstention, adjudication, supersession, and SLA state are immutable/audited.
  - **Steps / Subtasks:**
    - Implement queue routing, role checks, recusal, and expertise matching.
    - Preserve rejected alternatives and prior classifications.
  - **Risks & Mitigations:** Bias or self-review can corrupt final labels. / Use blind assignment, separation of duties, and immutable rationale.
  - **Tags:** [adjudication] [workflow] [audit]

- [ ] - **T5.1.8 — Govern release gates, overrides, and signed dossiers**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_RELEASE_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_RELEASES}, {DOMAIN_GOVERNANCE}, {DOMAIN_PROVENANCE}
  - **Dependencies:** T5.1.5, T5.1.7, T3.1.4
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §K.3–K.5/L.7, ADR-005, `implementation_blueprint.md` FR-011/FR-012.
  - **Acceptance Criteria:** Raw safety gates and critical events evaluate before composite scores; insufficient support is indeterminate, never pass; Overrides require two approvers, rationale, scope, controls, expiry, linked follow-up, and immutable audit.
  - **Steps / Subtasks:**
    - Version threshold sets and approval workflow.
    - Implement gate precedence and automatic override expiry.
  - **Risks & Mitigations:** Provisional thresholds may be mistaken for objective policy. / Require calibrated approval and explicit foundation prohibition.
  - **Tags:** [release-gates] [override] [signed-dossier]

- [ ] - **T5.1.9 — Run grading, statistics, and gate adversarial tests**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_GRADING}, {DOMAIN_STATISTICS}
  - **Dependencies:** T5.1.8
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N.2–N.4; `forensics.md` → `llm-attk-defs.md` supports direct/indirect injection cases.
  - **Acceptance Criteria:** Tests cover common labels, rare critical events, ambiguous/partial cases, grader conflict, abstention, injection, subgroup drift, correlation, missing data, threshold boundaries, unresolved reviews, changed datasets, replay, and version skew; Independent references match within approved tolerance and denominator mutations fail.
  - **Steps / Subtasks:**
    - Create hidden, property, mutation, differential, and adversarial fixtures.
    - Exercise regrading without target-model calls and preserve prior results.
  - **Risks & Mitigations:** Adversarial graders can fail confidently. / Treat disagreement/abstention as governed states and block unsupported publication.
  - **Tags:** [grader-testing] [statistical-validation] [gate-testing]

### Epic 6 — Identity, Security, and Supply Chain

- [ ] - **T6.1.1 — Implement OIDC, workload identity, and role mapping**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_IDENTITY_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_IDENTITY}, {DOMAIN_SECURITY}, {DOMAIN_API}
  - **Dependencies:** T1.1.3, T1.1.4
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §14/SEC-001 and `Plan_conceptual-v2.md` §L.1; AD support files inform least-privilege/delegation scenarios.
  - **Acceptance Criteria:** Production rejects development headers and validates issuer, audience, expiry, revocation, project claims, and MFA policy inheritance; Separate workload identities exist for API, scheduler, provider executors, graders, maintenance, and signing.
  - **Steps / Subtasks:**
    - Integrate approved IdP discovery/JWKS with bounded cache behavior.
    - Map groups to platform roles and project context.
  - **Risks & Mitigations:** Identity fallback can create universal access. / Fail closed and isolate break-glass credentials.
  - **Tags:** [oidc] [workload-identity] [rbac]

- [ ] - **T6.1.2 — Enforce end-to-end project and export isolation**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SECURITY_BACKEND_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_SECURITY}, {DOMAIN_TENANCY}, {DOMAIN_EVIDENCE}
  - **Dependencies:** T3.1.2, T3.1.3, T6.1.1
  - **Evidence:** `Pasted markdown.md` → threat-model cross-project abuse case, `implementation_blueprint.md` SEC-002, `Plan_conceptual-v2.md` §F.8.
  - **Acceptance Criteria:** API, RLS, object prefixes/keys, search, cache, queue, report, export, and hidden-set boundaries deny cross-project access; Negative matrix covers every role/action and confused-deputy paths through background workers.
  - **Steps / Subtasks:**
    - Build a role×resource×action matrix and automated fixtures.
    - Bind project context at request, transaction, job, object, and audit layers.
  - **Risks & Mitigations:** One unscoped worker or export can leak restricted data. / Enforce scope at every independent boundary.
  - **Tags:** [tenancy] [export-control] [negative-tests]

- [ ] - **T6.1.3 — Implement managed secrets, keys, signatures, and audit checkpoints**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SECURITY_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_SECURITY}, {DOMAIN_CRYPTOGRAPHY}, {DOMAIN_AUDIT}
  - **Dependencies:** T1.1.3, T3.1.4, T6.1.1
  - **Evidence:** `Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.4/§L.11, `implementation_blueprint.md` SEC-005/SEC-007; crypto support corpus reinforces key misuse risks.
  - **Acceptance Criteria:** Secrets are short-lived, process/provider scoped, rotatable, and absent from config, DB payloads, artifacts, logs, traces, and reports; Signing uses managed identity/KMS with approved public-key registry, rotation, revocation, and historical verification.
  - **Steps / Subtasks:**
    - Define key hierarchy, secret delivery, canaries, and rotation runbook.
    - Implement signature verification against trust registry, not embedded key alone.
  - **Risks & Mitigations:** Key compromise can forge dossiers or expose providers. / Use least privilege, external trust anchors, rotation, and revocation drills.
  - **Tags:** [secrets] [kms] [audit-integrity]

- [ ] - **T6.1.4 — Enforce egress controls, sandboxes, and tool simulators**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PLATFORM_SECURITY_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_SECURITY}, {DOMAIN_EXECUTION}, {DOMAIN_SANDBOX}
  - **Dependencies:** T1.1.3, T4.1.5, T4.1.6, T5.1.2
  - **Evidence:** `Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.12, `implementation_blueprint.md` SEC-008.
  - **Acceptance Criteria:** Certification uses deterministic simulators; real tools require authorized-lab lane, approval, allowlisted definitions/arguments, bounded resources, and full action logs; Provider executors reach only approved endpoints; graders have default-deny egress.
  - **Steps / Subtasks:**
    - Define network policies and per-process service accounts.
    - Build tool simulator fixtures and manifest validation.
  - **Risks & Mitigations:** Tool use can cause live harm or exfiltration. / Default to simulation and deny network/shell/filesystem access.
  - **Tags:** [egress] [sandbox] [tool-safety]

- [ ] - **T6.1.5 — Build inert rendering and attachment quarantine**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_APPLICATION_SECURITY_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_SECURITY}, {DOMAIN_UX}, {DOMAIN_EVIDENCE}
  - **Dependencies:** T3.1.3, T6.1.2
  - **Evidence:** `Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.3/K.8; `CTF-Notes-PDF-GPT-k.md_.md`, `forensics.md`, and `GeneralScan-Gpt-k-1.md_.md` provide file/metadata attack patterns.
  - **Acceptance Criteria:** Prompts, outputs, Markdown, HTML, SVG, URLs, notifications, exports, and previews render inert with strict CSP and no remote fetch; Attachments use MIME-by-content validation, quarantine, malware scanning, safe derivative generation, size/decompression limits, and audited raw access.
  - **Steps / Subtasks:**
    - Create safe viewer and content-disposition policy.
    - Implement quarantine state machine and derivative provenance.
  - **Risks & Mitigations:** Parsers or renderers may execute hostile content. / Use isolated conversion, bounded resources, inert output, and no default preview.
  - **Tags:** [xss] [attachments] [quarantine]

- [ ] - **T6.1.6 — Add software-supply-chain controls and SBOM provenance**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DEVSECOPS_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_CICD}, {DOMAIN_SECURITY}, {DOMAIN_SUPPLY_CHAIN}
  - **Dependencies:** T1.1.3, T6.1.3
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §25.1 and supply-chain threat; `tools_and_usage_-1.md_11.md` → Snyk gap-analysis/PR-scanning guidance; `ALL-DEFENCE-GPT-k-1.md_.md` → vulnerability scanning.
  - **Acceptance Criteria:** CI scans dependencies, secrets, licenses, source, containers, and IaC with risk-based blocking thresholds and exception expiry; Reproducible SBOM, signed image, build provenance, and dependency lock evidence are published per release.
  - **Steps / Subtasks:**
    - Baseline direct/transitive dependencies and false positives.
    - Integrate scanner outputs into PR and release evidence.
  - **Risks & Mitigations:** Scanner noise can cause bypass culture. / Use reachability-aware triage, owners, SLAs, and expiring exceptions.
  - **Tags:** [sbom] [dependency-scanning] [provenance]

- [ ] - **T6.1.7 — Run adversarial security and permission matrix**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SECURITY_TEST_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_SECURITY}, {DOMAIN_IDENTITY}
  - **Dependencies:** T6.1.2, T6.1.3, T6.1.4, T6.1.5, T6.1.6
  - **Evidence:** Primary threat-model plus supporting corpora: `forensics.md` (`llm-attk-defs.md`), `1.0SWebApp-GPT-k-1.md_.md`, `ALL-CVE-GPT-k-1.md_.md`, `ALL-ActDir-GPT-k.md_-1.md`.
  - **Acceptance Criteria:** Tests cover direct/indirect prompt injection, excessive agency, stored XSS, SSRF, SQL/command/XXE injection, duplicate JSON keys, race conditions, auth bypass, token faults, cross-project access, secret leakage, attachment execution, egress, signing/audit compromise, and supply-chain tamper; All privileged actions require backend authorization and audit regardless of model output.
  - **Steps / Subtasks:**
    - Build safe non-destructive fixtures and browser/network policy tests.
    - Execute every role/resource/action negative case.
  - **Risks & Mitigations:** A broad corpus can become unsafe or nondeterministic. / Use inert fixtures, isolated environments, explicit authorization, and reproducible assertions.
  - **Tags:** [security-testing] [prompt-injection] [permissions]

### Epic 7 — API, CLI, Reporting, and User Workflows

- [ ] - **T7.1.1 — Implement versioned REST command and query APIs**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_BACKEND_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_API}, {DOMAIN_CONTRACTS}, {DOMAIN_EXECUTION}
  - **Dependencies:** T2.1.2, T3.1.2, T4.1.2, T6.1.1
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §J.6/§J.13/V, `implementation_blueprint.md` FR-016.
  - **Acceptance Criteria:** `/v1` validate/start/pause/resume/cancel/regrade/compare/export/evidence workflows use idempotency keys, ETags, cursor pagination, operation resources, and stable safe errors; Every response includes schema version, trace ID, and project context; restricted evidence never appears in lists.
  - **Steps / Subtasks:**
    - Implement command/query separation and optimistic concurrency.
    - Return asynchronous operation resources for long work.
  - **Risks & Mitigations:** API ambiguity can create duplicate or unauthorized mutations. / Require idempotency, explicit state transitions, and backend authorization.
  - **Tags:** [rest-api] [idempotency] [openapi]

- [ ] - **T7.1.2 — Complete CLI workflows and stable exit codes**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DEVELOPER_TOOLS_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_CLI}, {DOMAIN_API}, {DOMAIN_DEVELOPER_EXPERIENCE}
  - **Dependencies:** T7.1.1
  - **Evidence:** `Pasted markdown.md` → foundation runbook and `Plan_conceptual-v2.md` §K.6; source-reported CLI is unverified until T1.1.1.
  - **Acceptance Criteria:** CLI supports validate, plan/estimate, run/start, status, pause, resume, cancel, regrade, compare, export, schema, and dossier verification; Exit codes remain 0 pass, 10 warning, 20 block, 30 indeterminate, 40 validation, 50 platform failure.
  - **Steps / Subtasks:**
    - Align CLI types and errors with REST contracts.
    - Add timeout, cancellation, retry guidance, and trace IDs.
  - **Risks & Mitigations:** CLI/API drift can produce inconsistent release decisions. / Generate from shared application contracts and run parity tests.
  - **Tags:** [cli] [developer-workflow] [exit-codes]

- [ ] - **T7.1.3 — Build reproducible reports and governed exports**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_REPORTING_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_REPORTING}, {DOMAIN_PROVENANCE}, {DOMAIN_RELEASES}
  - **Dependencies:** T3.1.4, T5.1.8
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §K.1–K.5, `implementation_blueprint.md` FR-012.
  - **Acceptance Criteria:** JSON, safe HTML, CSV, and Parquet outputs reconcile aggregate, slice, drill-down, exclusion, cost, latency, review, and gate data; Reports identify every version/hash and never embed restricted raw content by default.
  - **Steps / Subtasks:**
    - Implement canonical report model and deterministic ordering.
    - Add report-to-snapshot and artifact hash verification.
  - **Risks & Mitigations:** A polished report can hide stale or excluded data. / Require reconciliation, timestamps, support counts, and invalidation on integrity failure.
  - **Tags:** [reporting] [exports] [reproducibility]

- [ ] - **T7.1.4 — Deliver safe analyst, executive, and reviewer workflows**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_FULL_STACK_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_UX}, {DOMAIN_REPORTING}, {DOMAIN_REVIEW}
  - **Dependencies:** T5.1.7, T7.1.3, T6.1.5
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §K.1/K.8/G.9 and `implementation_blueprint.md` ACC-001/ACC-002.
  - **Acceptance Criteria:** Executive view is aggregate-only; analyst drill-down follows lineage; reviewer view defaults to redacted content and explicit raw reveal; Materialized views meet query plan targets and display refresh time/staleness.
  - **Steps / Subtasks:**
    - Define task-centered screens and safe viewer integration.
    - Add query indexes/materialized refresh and authorization.
  - **Risks & Mitigations:** Convenient drill-down may overexpose restricted content. / Apply least-privilege views and audited reveal actions.
  - **Tags:** [dashboard] [review-ui] [safe-rendering]

- [ ] - **T7.1.5 — Complete accessibility and localization readiness**
  - **Priority:** P1
  - **Est. Effort:** 12h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_ACCESSIBILITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_UX}, {DOMAIN_ACCESSIBILITY}, {DOMAIN_LOCALIZATION}
  - **Dependencies:** T7.1.4, T2.1.3
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §19/ACC-001/ACC-002; language scope outcome comes from T2.1.3.
  - **Acceptance Criteria:** Primary workflows meet WCAG 2.2 AA with keyboard operation, visible focus, semantic labels, non-color states, zoom, and screen-reader support; Text, date/number formats, layout, and policy content are localization-ready even when first-release languages are limited.
  - **Steps / Subtasks:**
    - Run axe-equivalent automated checks plus manual keyboard/screen-reader scripts.
    - Externalize user-visible strings and test long/RTL-like text.
  - **Risks & Mitigations:** Accessibility defects can block reviewers from critical decisions. / Make audits release-gating and include assistive-technology users.
  - **Tags:** [wcag] [accessibility] [localization]

- [ ] - **T7.1.6 — Run API, CLI, report, and UX hostile tests**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_QUALITY_LEAD} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_API}, {DOMAIN_UX}
  - **Dependencies:** T7.1.1, T7.1.2, T7.1.3, T7.1.4, T7.1.5
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N; web-support corpora supply malformed protocol, XSS, race, and authorization patterns.
  - **Acceptance Criteria:** Tests cover common flows, malformed/large payloads, duplicate keys, stale ETags, replay/idempotency, concurrency, timeouts, retries, network partitions, pagination edges, export races, version skew, active content, keyboard, screen reader, and stale views; REST/CLI outcomes and exit codes remain equivalent.
  - **Steps / Subtasks:**
    - Automate contract, browser, accessibility, security, and end-to-end fixtures.
    - Use fault proxies and deterministic clocks for partial failures.
  - **Risks & Mitigations:** Front-end and API edge cases can bypass otherwise-correct domain rules. / Test through every boundary with shared golden outcomes.
  - **Tags:** [e2e-testing] [api-security] [ux-testing]

### Epic 8 — Observability, Performance, Resilience, and Delivery

- [ ] - **T8.1.1 — Implement structured telemetry and correlation**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SRE} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_OBSERVABILITY}, {DOMAIN_SRE}, {DOMAIN_SECURITY}
  - **Dependencies:** T4.1.2, T5.1.1, T7.1.1
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §M.1/M.2 and `implementation_blueprint.md` OPS-002; `NTFSAna-GPT-k.md_.md` and `rudi-kevert.md` support log/network analysis patterns.
  - **Acceptance Criteria:** Logs, metrics, and traces carry experiment/run/attempt/provider/model/case/family/worker/grader/trace/project identifiers; Prompt/response/secret bodies are absent; redaction canaries and schema allowlists pass.
  - **Steps / Subtasks:**
    - Define telemetry schemas, cardinality budgets, sampling, and retention.
    - Instrument critical state transitions and dependency calls.
  - **Risks & Mitigations:** High-cardinality or sensitive telemetry can become an outage or leak. / Use allowlists, budgets, sampling, and no-content defaults.
  - **Tags:** [opentelemetry] [correlation] [redaction]

- [ ] - **T8.1.2 — Establish SLIs, SLO dashboards, and actionable alerts**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SRE} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_OBSERVABILITY}, {DOMAIN_OPERATIONS}
  - **Dependencies:** T8.1.1, T4.1.1
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §M.3/M.4 and `implementation_blueprint.md` NFR-001–NFR-005.
  - **Acceptance Criteria:** Dashboards measure 99.9% API availability, 99.99% accepted-definition durability, zero known lost jobs, p95 queue start ≤5m, p95 grading ≤2m, p99 report ≤10m, and 100% scheduled hash verification; Page/ticket alerts have owner, severity, dedupe, runbook, and no raw content.
  - **Steps / Subtasks:**
    - Define exact SLI queries and error-budget windows.
    - Build service, queue, provider, grader, review, evidence, audit, cost, and release views.
  - **Risks & Mitigations:** Bad SLIs can hide user-visible failure or page excessively. / Reconcile with persisted state and test every alert.
  - **Tags:** [slo] [dashboards] [alerts]

- [ ] - **T8.1.3 — Write operational runbooks and graceful-degradation rules**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SRE} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_OPERATIONS}, {DOMAIN_INCIDENT_RESPONSE}, {DOMAIN_GOVERNANCE}
  - **Dependencies:** T8.1.2, T6.1.7
  - **Evidence:** `Pasted markdown.md` → foundation runbook, `Plan_conceptual-v2.md` §M.5/M.6/M.9, `implementation_blueprint.md` OPS-003.
  - **Acceptance Criteria:** Runbooks cover provider outage, queue backlog, worker loop, model drift, metric discrepancy, grader drift, artifact exposure, credential leak, dataset poisoning, DB/object/audit failure, wrong gate, restore, and signing-key compromise; Each specifies detection, safe action, evidence preservation, rollback, communications, owner, and re-certification.
  - **Steps / Subtasks:**
    - Create SEV taxonomy and command/check templates for `{REMOTE_EXEC_CONTEXT}`.
    - Link alerts to runbooks and decision authorities.
  - **Risks & Mitigations:** Runbooks can be obsolete at incident time. / Version with releases and exercise quarterly.
  - **Tags:** [runbooks] [graceful-degradation] [incident-response]

- [ ] - **T8.1.4 — Execute performance, load, and soak qualification**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_PERFORMANCE_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_PERFORMANCE}, {DOMAIN_CAPACITY}, {DOMAIN_EXECUTION}
  - **Dependencies:** T4.1.8, T5.1.9, T7.1.6, T8.1.2
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §16 and `Plan_conceptual-v2.md` §N.1; targets use approved T4.1.1 capacity.
  - **Acceptance Criteria:** At declared load, API/queue/grading/report SLOs pass with ≥30% headroom and no lost/duplicate runs; Tests include p50/p95/p99 latency, throughput, saturation, DB locks, object throughput, report queries, cost, multi-day soak, and recovery after overload.
  - **Steps / Subtasks:**
    - Use provider mocks for repeatable high concurrency and bounded live-provider smoke tests.
    - Profile common, burst, large-payload, slow-provider, and review-backlog modes.
  - **Risks & Mitigations:** Synthetic load may miss external quotas or correlated failures. / Combine deterministic load with controlled provider canaries and sensitivity analysis.
  - **Tags:** [performance] [load-test] [soak]

- [ ] - **T8.1.5 — Implement backup, PITR, restore, and full reconciliation**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SRE} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DR}, {DOMAIN_PERSISTENCE}, {DOMAIN_EVIDENCE}
  - **Dependencies:** T3.1.6, T6.1.3, T8.1.2
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` OPS-001/§17/§34.12 and certification recovery criterion.
  - **Acceptance Criteria:** PostgreSQL PITR meets RPO 15m/RTO 4h or approved replacements; object versions, keys, audit checkpoints, and manifests are recoverable; Isolated restore reconciles 100% of accepted runs, objects, hashes, outbox events, audit continuity, and dossiers.
  - **Steps / Subtasks:**
    - Automate backups, retention, restore, and integrity verification as code.
    - Test region/account isolation and credential loss procedures.
  - **Risks & Mitigations:** A database-only restore can leave irrecoverable evidence gaps. / Restore and reconcile the entire provenance chain.
  - **Tags:** [backup] [disaster-recovery] [reconciliation]

- [ ] - **T8.1.6 — Build deterministic CI, artifacts, and infrastructure as code**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_DEVOPS_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_CICD}, {DOMAIN_INFRASTRUCTURE}, {DOMAIN_BUILD}
  - **Dependencies:** T1.1.3, T2.1.2, T6.1.6
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §24/§25 and recommended `.github/workflows/`, `infrastructure/compose|kubernetes|terraform|monitoring`.
  - **Acceptance Criteria:** Pinned dependencies and reproducible builds generate byte-identical or documented deterministic artifacts, schemas, OpenAPI, SBOM, signatures, and provenance; CI gates format/type/unit/property/golden/mutation/contract/security/integration/E2E before immutable image publication.
  - **Steps / Subtasks:**
    - Define branch/release workflows and environment promotion evidence.
    - Fail startup on unknown config or production-development identity mismatch.
  - **Risks & Mitigations:** Non-reproducible or manually configured releases undermine evidence. / Use pinned inputs, immutable artifacts, policy-as-code, and drift checks.
  - **Tags:** [ci-cd] [reproducible-builds] [iac]

- [ ] - **T8.1.7 — Implement deployment, migration, rollback, and version-skew controls**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_RELEASE_ENGINEER} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_DEPLOYMENT}, {DOMAIN_RELEASES}, {DOMAIN_PERSISTENCE}
  - **Dependencies:** T3.1.5, T8.1.6
  - **Evidence:** `Pasted markdown.md` → `implementation_blueprint.md` §25.2/§25.3/§26 and `Plan_conceptual-v2.md` deployment model.
  - **Acceptance Criteria:** API uses rolling/blue-green and workers deploy independently; one-release API/worker/schema compatibility is tested; Expand/migrate/contract ordering prevents irreversible contraction in the same rollout; rollback preserves new evidence.
  - **Steps / Subtasks:**
    - Create compatibility matrix across previous/current API, worker, schema, event, and report versions.
    - Automate pre/post-deploy checks and migration verification.
  - **Risks & Mitigations:** Version skew can corrupt jobs or make rollback impossible. / Maintain compatibility windows and pause admission on integrity defects.
  - **Tags:** [deployment] [rollback] [version-skew]

- [ ] - **T8.1.8 — Automate production certification and release evidence**
  - **Priority:** P0
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_RELEASE_AUTHORITY} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_RELEASES}, {DOMAIN_GOVERNANCE}, {DOMAIN_TESTING}
  - **Dependencies:** T1.1.6, T5.1.8, T6.1.7, T8.1.5, T8.1.7
  - **Evidence:** `Pasted markdown.md` → ADR-005, `Plan_conceptual-v2.md` §N.4/Z, `implementation_blueprint.md` §21.2/§34.16.
  - **Acceptance Criteria:** Automation produces evidence for reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability; Every Must-production requirement is green or explicitly blocking; no critical/high defect or unresolved critical review remains.
  - **Steps / Subtasks:**
    - Build certification orchestration and evidence manifest.
    - Verify signatures, hashes, test reports, SLO/DR/game-day evidence, and approvals.
  - **Risks & Mitigations:** Checklist completion can mask weak or stale evidence. / Require machine-verifiable artifacts, freshness, and independent sign-off.
  - **Tags:** [certification] [release-readiness] [evidence]

- [ ] - **T8.1.9 — Establish long-term capacity, cost, and support operations**
  - **Priority:** P2
  - **Est. Effort:** 12h
  - **Owner:** @unassigned
  - **Domains:** {DOMAIN_OPERATIONS}, {DOMAIN_COST}, {DOMAIN_MAINTAINABILITY}
  - **Dependencies:** T8.1.2, T8.1.4, T8.1.6
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §M.7/M.8 and `implementation_blueprint.md` §27/§31.
  - **Acceptance Criteria:** Daily/weekly/monthly/quarterly operating cadences assign owners for health, budget, access, dependencies, backups, drift, and threat-model review; Cost per scorable run/family, capacity headroom, patch SLAs, error budgets, on-call coverage, and scale triggers are reported and acted on.
  - **Steps / Subtasks:**
    - Publish service ownership, support matrix, patch/deprecation policy, and maintenance calendar.
    - Create quarterly capacity/cost review with automatic tickets for breached thresholds.
  - **Risks & Mitigations:** Deferred maintenance can accumulate hidden reliability and security debt. / Fund recurring ownership, measurable SLAs, and trigger-based backlog creation.
  - **Tags:** [long-term-support] [capacity] [cost]

- [ ] - **T8.1.10 — Validate retrieval, vector, accelerator, and advanced-lane scope**
  - **Priority:** P3
  - **Est. Effort:** 8h
  - **Owner:** @unassigned
  - **Domains:** {DOMAIN_ADVANCED_CAPABILITIES}, {DOMAIN_RETRIEVAL}, {DOMAIN_ARCHITECTURE}
  - **Dependencies:** T1.1.3, T2.1.3
  - **Evidence:** Retrieval/vector storage/accelerators are not evidenced for the initial release and are (ASSUMED) [A-010]; multimodal, adaptive exploration, local models, and regional executors are source-listed later capabilities.
  - **Acceptance Criteria:** Decision records use cases, data classes, quality/latency targets, threats, cost, and alternatives before any implementation; Approved vector work selects `{VECTOR_COLUMN_TYPE}` and `{EMBEDDING_DIM}` with migration tests; otherwise both are `NOT_APPLICABLE`.
  - **Steps / Subtasks:**
    - Evaluate retrieval, multimodal, adaptive-exploration, local-model, regional-executor, and accelerator triggers with synthetic/redacted data.
    - Issue separate implementation epics only after measured benefit, security review, and operating ownership are approved.
  - **Risks & Mitigations:** Premature advanced features can index restricted evidence or fragment certification. / Keep them outside the initial release and require measured, governed entry criteria.
  - **Tags:** [advanced-capabilities] [vector] [assumption]

- [ ] - **T8.1.11 — Run cross-system game day and exhaustive failure matrix**
  - **Priority:** P1
  - **Est. Effort:** 16h
  - **Owner:** @unassigned | R:@unassigned A:{ROLE_SRE} C:{ROLE_SECURITY} I:{ROLE_RELEASE}
  - **Domains:** {DOMAIN_TESTING}, {DOMAIN_OPERATIONS}, {DOMAIN_RESILIENCE}
  - **Dependencies:** T8.1.3, T8.1.4, T8.1.5, T8.1.8
  - **Evidence:** `Pasted markdown.md` → `Plan_conceptual-v2.md` §N.4/M.9 and `implementation_blueprint.md` §17/§20.
  - **Acceptance Criteria:** Matrix explicitly covers common flows, outliers, rare critical cases, hostile inputs, partial failures, concurrency, replay/idempotency, timeouts, retries, network partitions, malformed data, large payloads, version skew, dependency outage, and operator error; Game day proves alert→runbook→containment→restore→reconciliation→re-certification with preserved evidence.
  - **Steps / Subtasks:**
    - Execute worker/database/object/audit/provider/IdP/telemetry/signing failures in an authorized staging environment.
    - Measure MTTD/MTTR, SLO impact, data integrity, and decision correctness.
  - **Risks & Mitigations:** Game days can harm shared environments or produce incomplete evidence. / Use isolated staging, change control, abort criteria, and deterministic fault tooling.
  - **Tags:** [game-day] [chaos] [failure-matrix]

## Implementation Notes

Execute P0 work in dependency order: evidence and decisions, contracts, data/evidence, durable execution, grading/statistics, identity/security, interfaces, then certification. P1 hardening may parallelize only after its P0 contracts stabilize. Preserve immutable evidence; never count reliability failures as behavior; never let composites or overrides bypass raw safety gates; keep 0.1.0 explicitly non-certifying until production blockers, independent approvals, DR evidence, and all ten certification categories pass.

[{"task_id":"T1.1.1","title":"Reconcile source claims with the current repository snapshot","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":[],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §1.3/§13, `DELIVERY_NOTES.md`, `test_report.md`; current repository and `{VERSION_TAG}` are (ASSUMED) [A-001].","acceptance_criteria":["A hash-addressed inventory records every supplied source and discovered repository artifact.","Claimed versus verified capabilities, CI state, logs/metrics/traces availability, and compatibility risks are mapped with no unqualified execution claim."],"tags":["evidence","repository-audit","P0"]},{"task_id":"T1.1.2","title":"Validate staffing, RACI, and decision authority","priority":"P0","estimated_hours":"6h","owner":"@unassigned","dependencies":[],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-002, §27.1, §30; staffing availability is (ASSUMED) [A-002].","acceptance_criteria":["Named accountable roles cover architecture, measurement, safety, security, SRE, curation, review, and release authority.","Every P0/P1 workstream has one accountable approver and no prohibited separation-of-duties overlap."],"tags":["raci","staffing","governance"]},{"task_id":"T1.1.3","title":"Validate production operating context and platform services","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.1"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-003/ASM-005, §24, §34.9; deployment, managed services, observability vendor, and `{REMOTE_EXEC_CONTEXT}` are (ASSUMED) [A-003].","acceptance_criteria":["A signed decision identifies region model, orchestrator, PostgreSQL, object store, OIDC, KMS/secrets, telemetry backend, and network-policy capabilities.","Environment boundaries for local, integration, staging, and production are documented with credentials and data classes."],"tags":["platform-decision","infrastructure","assumption"]},{"task_id":"T1.1.4","title":"Approve compliance, residency, retention, and content classes","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.1"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-009, §5.4 Q-002/Q-008, §15.3; binding obligations are (ASSUMED) [A-004].","acceptance_criteria":["Legal/security approval records applicable regimes, residency, retention, legal hold, deletion, export, and incident-notification duties.","Each Public/Internal/Confidential/Restricted/Secret class has storage, key, access, telemetry, and disposal rules."],"tags":["compliance","data-classification","privacy"]},{"task_id":"T1.1.5","title":"Ratify modular-monolith boundaries and split triggers","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.1"],"evidence":"`Pasted markdown.md` → ADR-001, `Plan_conceptual-v2.md` §F.0A/§F.7, `implementation_blueprint.md` §6/§13; duplicate ADR-001 text is an input-normalization issue.","acceptance_criteria":["One accepted ADR defines domain dependency direction, deployable processes, shared contract ownership, and forbidden cross-boundary imports.","Split triggers are measurable: credentials, sustained scaling, isolation, residency, ownership, runtime, or cadence."],"tags":["architecture","modular-monolith","adr"]},{"task_id":"T1.1.6","title":"Create requirements traceability and architecture-conformance gates","priority":"P1","estimated_hours":"12h","owner":"@unassigned","dependencies":["T1.1.2","T1.1.5"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §4, §20, §21, §28; `docs/requirements_catalog.csv` is source-reported but repository existence is covered by T1.1.1.","acceptance_criteria":["Every Must requirement maps to one owner, component, test ID, release gate, and evidence artifact.","CI fails on orphan requirements, missing tests, or unauthorized architecture dependencies."],"tags":["traceability","fitness-functions","testing"]},{"task_id":"T2.1.1","title":"Freeze taxonomy, counting rules, and critical-event precedence","priority":"P0","estimated_hours":"12h","owner":"@unassigned","dependencies":["T1.1.5"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §B–D/§AA; `implementation_blueprint.md` FR-007/FR-009/FR-011 and RG-01.","acceptance_criteria":["Approved decision tables cover appropriate refusal, false refusal, safe useful compliance, unsafe compliance, and ambiguous/partial outcomes.","Strict/nominal denominators reconcile and reliability failures never enter behavioral numerators."],"tags":["taxonomy","metrics","safety"]},{"task_id":"T2.1.2","title":"Establish the versioned schema and contract registry","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.5","T2.1.1"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §J/V/W, `implementation_blueprint.md` FR-001/FR-002/DATA-001, recommended `contracts/`, `configs/schemas/`, `datasets/schemas/`.","acceptance_criteria":["JSON/YAML/API/event/artifact schemas reject unknown fields and publish deterministic hashes.","Backward/forward compatibility policy and semantic-version rules are executable in CI."],"tags":["schemas","contracts","versioning"]},{"task_id":"T2.1.3","title":"Validate benchmark populations, support, and language scope","priority":"P0","estimated_hours":"12h","owner":"@unassigned","dependencies":["T1.1.4","T2.1.1"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-010, §5.4 Q-001, §35.3; release population and language support are (ASSUMED) [A-005].","acceptance_criteria":["Approved scope defines categories, severities, authorization states, tool-use modes, languages, hidden splits, and minimum independent-family support.","Power/sample analysis documents where certification is pass-capable versus indeterminate-only."],"tags":["benchmark","population","assumption"]},{"task_id":"T2.1.4","title":"Build dataset supply-chain and promotion controls","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.2","T2.1.3"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §E, `implementation_blueprint.md` FR-002/PRIV-001/DATA-003.","acceptance_criteria":["Draft→reviewed→approved→deprecated transitions require dual approval, immutable manifests, hashes, split rules, and provenance.","Promotion rejects duplicate IDs/content, contamination, prohibited data, unsigned sources, and missing policy/rubric links."],"tags":["dataset-governance","provenance","supply-chain"]},{"task_id":"T2.1.5","title":"Curate and dual-review benchmark tranche A","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.4"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §E.3–E.7 and backlog B-004; tranche size must follow T2.1.3.","acceptance_criteria":["One approved tranche fits the validated hour cap and covers benign compliance, appropriate refusal, false refusal, and safe-redirection boundaries.","Every family has minimal pairs, policy/rubric versions, source provenance, expected treatment, and two independent reviews."],"tags":["benchmark","curation","golden-data"]},{"task_id":"T2.1.6","title":"Curate and dual-review benchmark tranche B","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.5"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §E.3/§E.11, threat-model assets, and supporting hostile-content corpus inventory.","acceptance_criteria":["One approved tranche fits the validated hour cap and covers critical harm, authorization counterfactuals, tool simulation, injection, malformed content, and rare/outlier cases.","All attachments/tool fixtures are inert or simulated and classification/retention metadata is complete."],"tags":["benchmark","adversarial-cases","reviewer-safety"]},{"task_id":"T2.1.7","title":"Implement deterministic expectation compilation","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.1","T2.1.2","T2.1.4"],"evidence":"`Pasted markdown.md` → ADR-004, `Plan_conceptual-v2.md` §G.0, `implementation_blueprint.md` FR-003.","acceptance_criteria":["Expectation records are compiled and persisted before provider execution from approved case, policy, rubric, and compiler versions.","Identical canonical inputs reproduce the same hash; any score-affecting change creates a new immutable record."],"tags":["expectations","determinism","policy"]},{"task_id":"T2.1.8","title":"Execute contract and dataset hostile-input tests","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.2","T2.1.7"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1/§N.2; supporting corpora: `1.0SWebApp-GPT-k-1.md_.md`, `ALL-CVE-GPT-k-1.md_.md`, `forensics.md`.","acceptance_criteria":["Tests cover common flows, malformed/unknown fields, duplicate keys, hash tampering, huge payloads, Unicode/confusables, version skew, hostile prompts, partial files, and replay.","Property/mutation tests catch denominator, label, canonicalization, and exclusion drift."],"tags":["contract-testing","fuzzing","hostile-input"]},{"task_id":"T3.1.1","title":"Create core PostgreSQL schema and ordered migrations","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.2"],"evidence":"`Pasted markdown.md` → ADR-002, `Plan_conceptual-v2.md` §J.1/§J.12, `implementation_blueprint.md` §7/§26.","acceptance_criteria":["Migrations cover projects, versions, experiments, runs, attempts, jobs, reviews, snapshots, gates, and audit metadata with typed constraints.","Prerequisites and expand→backfill→switch→contract order are explicit; upgrade and rollback pass against historical fixtures."],"tags":["postgresql","migrations","schema"]},{"task_id":"T3.1.2","title":"Enforce project keys, RLS, and database authorization","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.1","T1.1.3"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §F.8/§J.11, `implementation_blueprint.md` SEC-002/B-003.","acceptance_criteria":["Every business row carries project scope; RLS denies cross-project reads/writes under API and worker identities.","Migration owner bypass is isolated, audited, and unavailable to application roles."],"tags":["rls","multi-project","authorization"]},{"task_id":"T3.1.3","title":"Implement immutable content-addressed object storage","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T3.1.1"],"evidence":"`Pasted markdown.md` → ADR-003, `implementation_blueprint.md` FR-006/SEC-006; local filesystem is development-only.","acceptance_criteria":["S3-compatible writes are SHA-256 addressed, write-once/versioned, encrypted, project/classification scoped, and verified on put/get/head.","Metadata includes media type, size, classification, retention, legal hold, source, and hash."],"tags":["object-storage","content-addressing","integrity"]},{"task_id":"T3.1.4","title":"Implement provenance, transactional outbox, and audit linkage","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.1","T3.1.3"],"evidence":"`Pasted markdown.md` → ADR-002/ADR-003, `Plan_conceptual-v2.md` §H.10/§J.9, `implementation_blueprint.md` DATA-003/SEC-007.","acceptance_criteria":["Every source→case→prompt→expectation→attempt→response→grade→snapshot→gate→dossier edge resolves and hash-verifies.","Domain state and outbox event commit atomically; consumers are replay-safe and deduplicate by event ID."],"tags":["provenance","outbox","audit"]},{"task_id":"T3.1.5","title":"Implement lifecycle, regrade, backfill, and rollback workflows","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.1","T3.1.3","T3.1.4","T1.1.4"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §26/§27, FR-013, PRIV-002.","acceptance_criteria":["Regrades and recomputations create new immutable versions and preserve prior snapshots/classifications.","Retention, legal hold, deletion tombstones, cryptographic deletion, and restore precedence pass a policy matrix."],"tags":["lifecycle","backfill","regrade"]},{"task_id":"T3.1.6","title":"Run persistence and evidence failure-injection tests","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.2","T3.1.3","T3.1.4","T3.1.5"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1 and certification durability/integrity criteria.","acceptance_criteria":["Tests cover concurrent writes, replay, stale leases, DB restart, network partition, object delay/failure, partial upload, corruption, hash collision simulation, orphan rows/objects, large artifacts, and version skew.","No accepted logical run is lost or duplicated; corrupted evidence blocks grading/publication."],"tags":["failure-injection","data-integrity","resilience"]},{"task_id":"T4.1.1","title":"Validate workload and PostgreSQL queue envelope","priority":"P0","estimated_hours":"12h","owner":"@unassigned","dependencies":["T1.1.3"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-004, §16, §34.17; volume/concurrency are (ASSUMED) [A-006].","acceptance_criteria":["Forecast covers monthly runs, peak leases/s, token rates, response sizes, grading fan-out, human escalation, report concurrency, and retention growth.","A reproducible model confirms the PostgreSQL lease design or opens an ADR with measured alternatives."],"tags":["capacity","queue","assumption"]},{"task_id":"T4.1.2","title":"Implement durable leasing scheduler and reconciliation","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.1","T3.1.4","T4.1.1"],"evidence":"`Pasted markdown.md` → ADR-002, `Plan_conceptual-v2.md` §H, `implementation_blueprint.md` OPS-004/§34.7.","acceptance_criteria":["`FOR UPDATE SKIP LOCKED` leasing supports priorities, lease expiry, heartbeat, bounded retries, poisoned/dead-letter state, pause/resume/cancel, and reconciliation.","Worker death produces no lost or duplicate logical run; attempts remain distinct from logical runs."],"tags":["scheduler","leasing","idempotency"]},{"task_id":"T4.1.3","title":"Implement canonical adapter contract and deterministic mock","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.2","T2.1.7"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §J.4/§J.5, backlog B-010; source reports a mock but current state is governed by T1.1.1.","acceptance_criteria":["Canonical request/response types preserve exact model config, provider metadata, usage, finish reason, raw hashes, and normalized errors.","Mock deterministically simulates success, timeout, 429, 5xx, malformed output, partial response, and identity drift."],"tags":["provider-contract","mock","fault-fixtures"]},{"task_id":"T4.1.4","title":"Approve initial provider and model scope","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.3","T1.1.4"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-008/Q-003; two hosted providers are (ASSUMED) [A-007].","acceptance_criteria":["Decision names provider/model IDs, regions, parameters, identity metadata, pricing, quotas, retention terms, and prohibited data classes.","Two-provider requirement is approved or replaced with an explicit alternative and risk record."],"tags":["provider-scope","model-identity","assumption"]},{"task_id":"T4.1.5","title":"Implement production provider adapter A","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.3","T4.1.4"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` backlog B-011 and `implementation_blueprint.md` FR-005/FR-018.","acceptance_criteria":["Adapter A passes canonical success/error/timeout/usage/identity fixtures and records each attempt separately.","Credentials are short-lived and absent from artifacts/telemetry; egress is allowlisted."],"tags":["provider-a","adapter","integration"]},{"task_id":"T4.1.6","title":"Implement production provider adapter B","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.3","T4.1.4"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` backlog B-012 and `implementation_blueprint.md` production acceptance.","acceptance_criteria":["Adapter B passes the identical canonical fixture suite and exposes documented extensions only.","Cross-provider comparisons preserve request intent while recording capability differences."],"tags":["provider-b","adapter","integration"]},{"task_id":"T4.1.7","title":"Add fingerprints, budgets, backpressure, and rate limits","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.1","T4.1.2","T4.1.5","T4.1.6"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §H.6/§H.11, K.6, M.7; `implementation_blueprint.md` FR-017/FR-018.","acceptance_criteria":["Admission and runtime controls enforce cost, tokens, elapsed time, storage, reviewer tasks, per-provider/project quotas, and priority fairness.","Provider alias/capability/fingerprint changes mark comparisons pending and alert."],"tags":["backpressure","budgets","model-drift"]},{"task_id":"T4.1.8","title":"Run execution resilience and hostile-concurrency tests","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.2","T4.1.5","T4.1.6","T4.1.7"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N.1 and platform certification durability criteria.","acceptance_criteria":["Tests cover common runs, bursts, concurrent lease claims, replay/idempotency, worker kill, scheduler failover, timeouts, retries, 429/5xx, malformed/partial responses, network partitions, large payloads, cancellation races, and version skew.","No duplicate logical run or silent model substitution occurs."],"tags":["concurrency","resilience","provider-failures"]},{"task_id":"T5.1.1","title":"Harden deterministic five-outcome grading","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.1","T2.1.7"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` FR-007, `framework_status.md`, `test_report.md`; current implementation is source-reported only.","acceptance_criteria":["All five primary outcomes, secondary labels, abstention flags, and reliability terminal states have golden fixtures.","Reliability failures remain excluded from behavioral counts and evidence references are complete."],"tags":["grading","five-outcome","golden-tests"]},{"task_id":"T5.1.2","title":"Build an isolated schema-only judge runner","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T5.1.1"],"evidence":"`Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §G.5/L.5, `implementation_blueprint.md` SEC-004.","acceptance_criteria":["Judge workers have no provider credentials, tools, default egress, writable shared filesystem, or unapproved secrets.","Trusted rubric and untrusted evidence are structurally separated; output must validate against a strict schema."],"tags":["llm-judge","isolation","prompt-injection"]},{"task_id":"T5.1.3","title":"Build grader calibration and hidden-set release harness","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.5","T2.1.6","T5.1.1","T5.1.2"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §G.7/N.3 and `implementation_blueprint.md` B-010.","acceptance_criteria":["Harness reports macro F1, unsafe-compliance recall, subgroup performance, ECE, abstention, disagreement, injection resistance, and confidence intervals.","Hidden-set access is separate and every certification grader has an approved version plus rollback version."],"tags":["calibration","hidden-set","grader-governance"]},{"task_id":"T5.1.4","title":"Validate clustering and independent statistical reference","priority":"P0","estimated_hours":"12h","owner":"@unassigned","dependencies":["T2.1.3","T5.1.3"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-006/Q-010; prompt-family clustering/reference are (ASSUMED) [A-008].","acceptance_criteria":["Empirical dependence analysis confirms prompt family or selects a better cluster hierarchy.","Independent R/Python reference implementation and numeric tolerances are approved."],"tags":["statistics","cluster-bootstrap","assumption"]},{"task_id":"T5.1.5","title":"Implement versioned metrics and statistical comparisons","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.1","T5.1.4"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §C/I/AA, `implementation_blueprint.md` FR-009/FR-010/FR-014.","acceptance_criteria":["Snapshots expose included/excluded runs, numerator, denominator, support, interval, method/version, and input-set hash.","Wilson, cluster bootstrap, paired deltas, practical thresholds, drift, and changed-dataset warnings match the approved reference."],"tags":["metrics","bootstrap","comparisons"]},{"task_id":"T5.1.6","title":"Validate reviewer capacity, qualification, and safety model","priority":"P0","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.2","T1.1.4","T5.1.3"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §5.1 ASM-007/Q-007 and `Plan_conceptual-v2.md` §L.10; reviewer operations are (ASSUMED) [A-009].","acceptance_criteria":["Pilot measures arrival rate, handling time, skill coverage, backlog, critical-case completion, and exposure limits.","Approved staffing and queue SLO guarantee unresolved critical reviews block publication."],"tags":["human-review","capacity","assumption"]},{"task_id":"T5.1.7","title":"Implement human review and adjudication workflow","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T5.1.3","T5.1.6","T3.1.2"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §G.6–G.10, `implementation_blueprint.md` FR-008/B-011.","acceptance_criteria":["Rules create review tasks for ambiguity, criticality, disagreement, low confidence, and sampling; blind dual assignment prevents self-adjudication.","Submissions, rationale, abstention, adjudication, supersession, and SLA state are immutable/audited."],"tags":["adjudication","workflow","audit"]},{"task_id":"T5.1.8","title":"Govern release gates, overrides, and signed dossiers","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T5.1.5","T5.1.7","T3.1.4"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §K.3–K.5/L.7, ADR-005, `implementation_blueprint.md` FR-011/FR-012.","acceptance_criteria":["Raw safety gates and critical events evaluate before composite scores; insufficient support is indeterminate, never pass.","Overrides require two approvers, rationale, scope, controls, expiry, linked follow-up, and immutable audit."],"tags":["release-gates","override","signed-dossier"]},{"task_id":"T5.1.9","title":"Run grading, statistics, and gate adversarial tests","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T5.1.8"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N.2–N.4; `forensics.md` → `llm-attk-defs.md` supports direct/indirect injection cases.","acceptance_criteria":["Tests cover common labels, rare critical events, ambiguous/partial cases, grader conflict, abstention, injection, subgroup drift, correlation, missing data, threshold boundaries, unresolved reviews, changed datasets, replay, and version skew.","Independent references match within approved tolerance and denominator mutations fail."],"tags":["grader-testing","statistical-validation","gate-testing"]},{"task_id":"T6.1.1","title":"Implement OIDC, workload identity, and role mapping","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T1.1.4"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §14/SEC-001 and `Plan_conceptual-v2.md` §L.1; AD support files inform least-privilege/delegation scenarios.","acceptance_criteria":["Production rejects development headers and validates issuer, audience, expiry, revocation, project claims, and MFA policy inheritance.","Separate workload identities exist for API, scheduler, provider executors, graders, maintenance, and signing."],"tags":["oidc","workload-identity","rbac"]},{"task_id":"T6.1.2","title":"Enforce end-to-end project and export isolation","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.2","T3.1.3","T6.1.1"],"evidence":"`Pasted markdown.md` → threat-model cross-project abuse case, `implementation_blueprint.md` SEC-002, `Plan_conceptual-v2.md` §F.8.","acceptance_criteria":["API, RLS, object prefixes/keys, search, cache, queue, report, export, and hidden-set boundaries deny cross-project access.","Negative matrix covers every role/action and confused-deputy paths through background workers."],"tags":["tenancy","export-control","negative-tests"]},{"task_id":"T6.1.3","title":"Implement managed secrets, keys, signatures, and audit checkpoints","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T3.1.4","T6.1.1"],"evidence":"`Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.4/§L.11, `implementation_blueprint.md` SEC-005/SEC-007; crypto support corpus reinforces key misuse risks.","acceptance_criteria":["Secrets are short-lived, process/provider scoped, rotatable, and absent from config, DB payloads, artifacts, logs, traces, and reports.","Signing uses managed identity/KMS with approved public-key registry, rotation, revocation, and historical verification."],"tags":["secrets","kms","audit-integrity"]},{"task_id":"T6.1.4","title":"Enforce egress controls, sandboxes, and tool simulators","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T4.1.5","T4.1.6","T5.1.2"],"evidence":"`Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.12, `implementation_blueprint.md` SEC-008.","acceptance_criteria":["Certification uses deterministic simulators; real tools require authorized-lab lane, approval, allowlisted definitions/arguments, bounded resources, and full action logs.","Provider executors reach only approved endpoints; graders have default-deny egress."],"tags":["egress","sandbox","tool-safety"]},{"task_id":"T6.1.5","title":"Build inert rendering and attachment quarantine","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.3","T6.1.2"],"evidence":"`Pasted markdown.md` → threat-model, `Plan_conceptual-v2.md` §L.3/K.8; `CTF-Notes-PDF-GPT-k.md_.md`, `forensics.md`, and `GeneralScan-Gpt-k-1.md_.md` provide file/metadata attack patterns.","acceptance_criteria":["Prompts, outputs, Markdown, HTML, SVG, URLs, notifications, exports, and previews render inert with strict CSP and no remote fetch.","Attachments use MIME-by-content validation, quarantine, malware scanning, safe derivative generation, size/decompression limits, and audited raw access."],"tags":["xss","attachments","quarantine"]},{"task_id":"T6.1.6","title":"Add software-supply-chain controls and SBOM provenance","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T6.1.3"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §25.1 and supply-chain threat; `tools_and_usage_-1.md_11.md` → Snyk gap-analysis/PR-scanning guidance; `ALL-DEFENCE-GPT-k-1.md_.md` → vulnerability scanning.","acceptance_criteria":["CI scans dependencies, secrets, licenses, source, containers, and IaC with risk-based blocking thresholds and exception expiry.","Reproducible SBOM, signed image, build provenance, and dependency lock evidence are published per release."],"tags":["sbom","dependency-scanning","provenance"]},{"task_id":"T6.1.7","title":"Run adversarial security and permission matrix","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T6.1.2","T6.1.3","T6.1.4","T6.1.5","T6.1.6"],"evidence":"Primary threat-model plus supporting corpora: `forensics.md` (`llm-attk-defs.md`), `1.0SWebApp-GPT-k-1.md_.md`, `ALL-CVE-GPT-k-1.md_.md`, `ALL-ActDir-GPT-k.md_-1.md`.","acceptance_criteria":["Tests cover direct/indirect prompt injection, excessive agency, stored XSS, SSRF, SQL/command/XXE injection, duplicate JSON keys, race conditions, auth bypass, token faults, cross-project access, secret leakage, attachment execution, egress, signing/audit compromise, and supply-chain tamper.","All privileged actions require backend authorization and audit regardless of model output."],"tags":["security-testing","prompt-injection","permissions"]},{"task_id":"T7.1.1","title":"Implement versioned REST command and query APIs","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T2.1.2","T3.1.2","T4.1.2","T6.1.1"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §J.6/§J.13/V, `implementation_blueprint.md` FR-016.","acceptance_criteria":["`/v1` validate/start/pause/resume/cancel/regrade/compare/export/evidence workflows use idempotency keys, ETags, cursor pagination, operation resources, and stable safe errors.","Every response includes schema version, trace ID, and project context; restricted evidence never appears in lists."],"tags":["rest-api","idempotency","openapi"]},{"task_id":"T7.1.2","title":"Complete CLI workflows and stable exit codes","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T7.1.1"],"evidence":"`Pasted markdown.md` → foundation runbook and `Plan_conceptual-v2.md` §K.6; source-reported CLI is unverified until T1.1.1.","acceptance_criteria":["CLI supports validate, plan/estimate, run/start, status, pause, resume, cancel, regrade, compare, export, schema, and dossier verification.","Exit codes remain 0 pass, 10 warning, 20 block, 30 indeterminate, 40 validation, 50 platform failure."],"tags":["cli","developer-workflow","exit-codes"]},{"task_id":"T7.1.3","title":"Build reproducible reports and governed exports","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.4","T5.1.8"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §K.1–K.5, `implementation_blueprint.md` FR-012.","acceptance_criteria":["JSON, safe HTML, CSV, and Parquet outputs reconcile aggregate, slice, drill-down, exclusion, cost, latency, review, and gate data.","Reports identify every version/hash and never embed restricted raw content by default."],"tags":["reporting","exports","reproducibility"]},{"task_id":"T7.1.4","title":"Deliver safe analyst, executive, and reviewer workflows","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T5.1.7","T7.1.3","T6.1.5"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §K.1/K.8/G.9 and `implementation_blueprint.md` ACC-001/ACC-002.","acceptance_criteria":["Executive view is aggregate-only; analyst drill-down follows lineage; reviewer view defaults to redacted content and explicit raw reveal.","Materialized views meet query plan targets and display refresh time/staleness."],"tags":["dashboard","review-ui","safe-rendering"]},{"task_id":"T7.1.5","title":"Complete accessibility and localization readiness","priority":"P1","estimated_hours":"12h","owner":"@unassigned","dependencies":["T7.1.4","T2.1.3"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §19/ACC-001/ACC-002; language scope outcome comes from T2.1.3.","acceptance_criteria":["Primary workflows meet WCAG 2.2 AA with keyboard operation, visible focus, semantic labels, non-color states, zoom, and screen-reader support.","Text, date/number formats, layout, and policy content are localization-ready even when first-release languages are limited."],"tags":["wcag","accessibility","localization"]},{"task_id":"T7.1.6","title":"Run API, CLI, report, and UX hostile tests","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T7.1.1","T7.1.2","T7.1.3","T7.1.4","T7.1.5"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N; web-support corpora supply malformed protocol, XSS, race, and authorization patterns.","acceptance_criteria":["Tests cover common flows, malformed/large payloads, duplicate keys, stale ETags, replay/idempotency, concurrency, timeouts, retries, network partitions, pagination edges, export races, version skew, active content, keyboard, screen reader, and stale views.","REST/CLI outcomes and exit codes remain equivalent."],"tags":["e2e-testing","api-security","ux-testing"]},{"task_id":"T8.1.1","title":"Implement structured telemetry and correlation","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.2","T5.1.1","T7.1.1"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §M.1/M.2 and `implementation_blueprint.md` OPS-002; `NTFSAna-GPT-k.md_.md` and `rudi-kevert.md` support log/network analysis patterns.","acceptance_criteria":["Logs, metrics, and traces carry experiment/run/attempt/provider/model/case/family/worker/grader/trace/project identifiers.","Prompt/response/secret bodies are absent; redaction canaries and schema allowlists pass."],"tags":["opentelemetry","correlation","redaction"]},{"task_id":"T8.1.2","title":"Establish SLIs, SLO dashboards, and actionable alerts","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T8.1.1","T4.1.1"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §M.3/M.4 and `implementation_blueprint.md` NFR-001–NFR-005.","acceptance_criteria":["Dashboards measure 99.9% API availability, 99.99% accepted-definition durability, zero known lost jobs, p95 queue start ≤5m, p95 grading ≤2m, p99 report ≤10m, and 100% scheduled hash verification.","Page/ticket alerts have owner, severity, dedupe, runbook, and no raw content."],"tags":["slo","dashboards","alerts"]},{"task_id":"T8.1.3","title":"Write operational runbooks and graceful-degradation rules","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T8.1.2","T6.1.7"],"evidence":"`Pasted markdown.md` → foundation runbook, `Plan_conceptual-v2.md` §M.5/M.6/M.9, `implementation_blueprint.md` OPS-003.","acceptance_criteria":["Runbooks cover provider outage, queue backlog, worker loop, model drift, metric discrepancy, grader drift, artifact exposure, credential leak, dataset poisoning, DB/object/audit failure, wrong gate, restore, and signing-key compromise.","Each specifies detection, safe action, evidence preservation, rollback, communications, owner, and re-certification."],"tags":["runbooks","graceful-degradation","incident-response"]},{"task_id":"T8.1.4","title":"Execute performance, load, and soak qualification","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T4.1.8","T5.1.9","T7.1.6","T8.1.2"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §16 and `Plan_conceptual-v2.md` §N.1; targets use approved T4.1.1 capacity.","acceptance_criteria":["At declared load, API/queue/grading/report SLOs pass with ≥30% headroom and no lost/duplicate runs.","Tests include p50/p95/p99 latency, throughput, saturation, DB locks, object throughput, report queries, cost, multi-day soak, and recovery after overload."],"tags":["performance","load-test","soak"]},{"task_id":"T8.1.5","title":"Implement backup, PITR, restore, and full reconciliation","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.6","T6.1.3","T8.1.2"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` OPS-001/§17/§34.12 and certification recovery criterion.","acceptance_criteria":["PostgreSQL PITR meets RPO 15m/RTO 4h or approved replacements; object versions, keys, audit checkpoints, and manifests are recoverable.","Isolated restore reconciles 100% of accepted runs, objects, hashes, outbox events, audit continuity, and dossiers."],"tags":["backup","disaster-recovery","reconciliation"]},{"task_id":"T8.1.6","title":"Build deterministic CI, artifacts, and infrastructure as code","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.3","T2.1.2","T6.1.6"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §24/§25 and recommended `.github/workflows/`, `infrastructure/compose|kubernetes|terraform|monitoring`.","acceptance_criteria":["Pinned dependencies and reproducible builds generate byte-identical or documented deterministic artifacts, schemas, OpenAPI, SBOM, signatures, and provenance.","CI gates format/type/unit/property/golden/mutation/contract/security/integration/E2E before immutable image publication."],"tags":["ci-cd","reproducible-builds","iac"]},{"task_id":"T8.1.7","title":"Implement deployment, migration, rollback, and version-skew controls","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T3.1.5","T8.1.6"],"evidence":"`Pasted markdown.md` → `implementation_blueprint.md` §25.2/§25.3/§26 and `Plan_conceptual-v2.md` deployment model.","acceptance_criteria":["API uses rolling/blue-green and workers deploy independently; one-release API/worker/schema compatibility is tested.","Expand/migrate/contract ordering prevents irreversible contraction in the same rollout; rollback preserves new evidence."],"tags":["deployment","rollback","version-skew"]},{"task_id":"T8.1.8","title":"Automate production certification and release evidence","priority":"P0","estimated_hours":"16h","owner":"@unassigned","dependencies":["T1.1.6","T5.1.8","T6.1.7","T8.1.5","T8.1.7"],"evidence":"`Pasted markdown.md` → ADR-005, `Plan_conceptual-v2.md` §N.4/Z, `implementation_blueprint.md` §21.2/§34.16.","acceptance_criteria":["Automation produces evidence for reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability.","Every Must-production requirement is green or explicitly blocking; no critical/high defect or unresolved critical review remains."],"tags":["certification","release-readiness","evidence"]},{"task_id":"T8.1.9","title":"Establish long-term capacity, cost, and support operations","priority":"P2","estimated_hours":"12h","owner":"@unassigned","dependencies":["T8.1.2","T8.1.4","T8.1.6"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §M.7/M.8 and `implementation_blueprint.md` §27/§31.","acceptance_criteria":["Daily/weekly/monthly/quarterly operating cadences assign owners for health, budget, access, dependencies, backups, drift, and threat-model review.","Cost per scorable run/family, capacity headroom, patch SLAs, error budgets, on-call coverage, and scale triggers are reported and acted on."],"tags":["long-term-support","capacity","cost"]},{"task_id":"T8.1.10","title":"Validate retrieval, vector, accelerator, and advanced-lane scope","priority":"P3","estimated_hours":"8h","owner":"@unassigned","dependencies":["T1.1.3","T2.1.3"],"evidence":"Retrieval/vector storage/accelerators are not evidenced for the initial release and are (ASSUMED) [A-010]; multimodal, adaptive exploration, local models, and regional executors are source-listed later capabilities.","acceptance_criteria":["Decision records use cases, data classes, quality/latency targets, threats, cost, and alternatives before any implementation.","Approved vector work selects `{VECTOR_COLUMN_TYPE}` and `{EMBEDDING_DIM}` with migration tests; otherwise both are `NOT_APPLICABLE`."],"tags":["advanced-capabilities","vector","assumption"]},{"task_id":"T8.1.11","title":"Run cross-system game day and exhaustive failure matrix","priority":"P1","estimated_hours":"16h","owner":"@unassigned","dependencies":["T8.1.3","T8.1.4","T8.1.5","T8.1.8"],"evidence":"`Pasted markdown.md` → `Plan_conceptual-v2.md` §N.4/M.9 and `implementation_blueprint.md` §17/§20.","acceptance_criteria":["Matrix explicitly covers common flows, outliers, rare critical cases, hostile inputs, partial failures, concurrency, replay/idempotency, timeouts, retries, network partitions, malformed data, large payloads, version skew, dependency outage, and operator error.","Game day proves alert→runbook→containment→restore→reconciliation→re-certification with preserved evidence."],"tags":["game-day","chaos","failure-matrix"]}]