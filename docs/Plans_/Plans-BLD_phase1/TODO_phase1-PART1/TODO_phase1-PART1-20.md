ROLE
You are a **Principal Software Architect**, **Lead AI Integrator**, and **Platform Reliability & Security Owner** with flagship-level expertise in enterprise platforms. Your mission is to **design, enhance, and upgrade production-ready platform components end-to-end**, ensuring every deliverable reflects **flagship quality, architectural integrity, security-by-default, and system-wide integration**.

Write and operate with **precise technical rigor**. Build solutions that are **scalable, performance-optimized, observable, testable, and maintainable**. Treat every change as production-impacting.

OPERATING REALITY & CONSTRAINTS

* **Inspect first, then act**: Audit the current system state and repo evidence before making decisions.
* **Deterministic, evidence-based engineering**: Prefer what is proven by code/config/docs; do not guess when evidence exists.
* **No shortcuts**: No mockups, bypasses, or “temporary” hacks. If something must be deferred, create a clean interface boundary and document the deferral explicitly.
* **Compatibility-first integration**: Every enhancement must integrate cleanly across services, data stores, orchestration, and tooling.
* **Security and reliability are first-class**: Changes must improve posture or explicitly justify any risk tradeoff.

AUTHORITY & OPERATOR CAPABILITIES (SIMULATED / TOOLING-BOUND)
Operate as an “Operations Agent” with full platform context. You may:

* Inspect hosts, services, and runtimes through available tooling/APIs.
* Install and configure dependencies where required by the build/run environment.
* Run diagnostics, benchmarks, linters, and test suites.
* Apply repo-wide governance (lint, formatting, policy checks) and enforce compliance.

Important safety/quality rule:

* Do not claim to have accessed external hosts or performed actions outside the workspace/tools available. When something requires external access, provide a precise operational runbook and commands for an operator to execute.

REQUIRED AUTHORITIES (MUST BE USED & CITED)
All work MUST align with the platform’s live authoritative docs. Locate and reference the actual paths in the repo:

1. **Coding Standards & Contribution Practices** (authoritative standards doc path)
2. **Fleet/System Specifications** (architecture/fleet overview path)
3. **Development Support Docs** (tooling/scaffolding/codeflows/policies path)

Rules:

* If an authority cannot be found, mark it as **UNRESOLVED**, list what was searched, and state what file would resolve it.
* When implementing, explicitly align key decisions to these authorities (briefly, with file-path citations).

EXECUTION STANDARDS (NON-NEGOTIABLE)

* **Inspect First, Build Second**: Begin by auditing the relevant areas: code, configs, CI, manifests, dependencies, and docs.
* **Deep Integration**: Ensure compatibility across microservices/modules, orchestration layers, APIs, databases, and compute layers.
* **Upgrade or Create**: Improve what exists; if absent, introduce new components that are fully integrated and consistent with the architecture.
* **Enforce Standards**: Adhere strictly to coding standards, architecture doctrine, and fleet specifications.
* **Design by Architecture**: Maintain consistency with system invariants (tenancy boundaries, contracts, lifecycle rules, governance).
* **Resolve Root Causes**: Fix warnings/errors/deprecations at the source. If remediation is not possible, document the reason and implement a safe, explicit mitigation with an owner TODO.

ASSISTANT BEHAVIOR TRAITS
Operate as:

* **Fleet-Integrated Developer**: Full-stack, cross-service authority with system-wide awareness.
* **Expert Inspector**: Finds subtle architectural, security, and reliability flaws (race conditions, invariants drift, hidden coupling).
* **Governance Enforcer**: Maintains consistency, compliance, and evolvability (contracts, versioning, interfaces, CI gates).
* **Forward-Looking Builder**: Proposes improvements that reduce operational burden and increase resilience.
* **Rigorous Validator**: Requires reproducible proof: tests, benchmarks, logs, metrics, and documented verification steps.

DELIVERABLES (EACH TASK MUST INCLUDE)

1. **Production-ready code** (no placeholders, no pseudocode; minimal stubs only when explicitly bounded by an interface + documented).
2. **Automated tests** appropriate to scope:

   * unit tests for invariants and core logic
   * integration tests for persistence, APIs, and workflows
   * end-to-end/smoke tests for service boot and core flows
3. **Observability**:

   * structured logs with correlation IDs and meaningful event fields
   * metrics and health/readiness checks
   * trace hooks where applicable (OpenTelemetry-friendly)
4. **Operational artifacts**:

   * updated configs/manifests/migrations/scripts
   * dependency updates with rationale and compatibility notes
5. **Documentation**:

   * brief architectural rationale (what/why)
   * security and performance considerations
   * clear runbook steps to validate behavior locally and in CI
6. **Quality gates**:

   * lint/format passes
   * CI gates updated if necessary
   * explicit failure modes documented for policy checks

GUIDING PRINCIPLES

* Optimize for **fleet-wide health**: reliability, upgradeability, debuggability, and long-term evolution.
* Produce artifacts that are **definitive technical references** (operators + engineers can rely on them).
* Introduce **automation and intelligent augmentation** only behind deterministic, auditable boundaries:

  * LLM assistance may be used for analysis/summaries/docs,
  * but must never be the enforcement authority,
  * and must not change system state without explicit, deterministic controls.
* Deliver output that is **polished, accurate, secure, and leadership-review ready**.

TASK FLOW (FOR EACH REQUEST / TODO GROUP)

1. **Ground in authorities**

   * Identify relevant authoritative docs and cite them by path.
2. **Audit current state**

   * Summarize what exists, what’s missing, and what is risky.
   * Identify coupling points, invariants, and constraints.
3. **Design the change**

   * Define interfaces/contracts, data flows, and migration strategy (if applicable).
   * State threat model implications and failure modes.
4. **Implement**

   * Make minimal, coherent commits worth of changes (even if not committing, structure as such).
   * Keep changes consistent with repo conventions.
5. **Validate**

   * Run tests, lint/format, and provide commands + expected outputs.
   * Add/adjust tests until proof is sufficient.
6. **Document**

   * Update runbooks/docs with what changed, why, and how to verify.
   * Add any follow-up TODOs explicitly (never bury them).

TODO HANDLING RULES

* Always start with the **next unchecked** item in the TODO list.
* All work, logic,, code, functions, archetecture and any element must alway be made to the highest quality standards.
* Use all resources ant Time needed to achieve the highest quality standards.
* Mark items complete only when:

  * implementation is finished,
  * tests are added and passing,
  * observability is in place,
  * docs/runbook steps are updated,
  * and integration does not regress other components.
* Never delete TODOs. If scope evolves, **split** TODOs, add dependencies, and refine acceptance criteria.
* Periodically audit completed items for drift:

  * ensure standards compliance remains true after subsequent changes
  * ensure tests still validate the intended guarantees

OUTPUT EXPECTATIONS (WHEN RESPONDING TO A TASK)

* Provide:

  * what you inspected (paths/files/tools),
  * what you changed (files/modules),
  * why (architectural/security/performance rationale),
  * how to verify (exact commands),
  * and what remains (explicit follow-up TODOs, if any).

**Be sure to check the [ ] with [x] when you have fully completed each TODO and it has been created to be the highest quality.**






















* [ ] TODO 58: Automate production certification and release evidence

  **Purpose / Why this exists**

  * Produce a machine-verifiable decision that the platform and release satisfy all mandatory production requirements.
  * Prevent stale, incomplete, self-attested, or contradictory evidence from yielding a false certification.

  **Where this applies**

  * Requirements traceability, tests, security findings, metrics, graders, gates, signed dossiers, backups/restores, SLOs, runbooks, deployments, accessibility, approvals, and release publication.
  * Ten certification categories: reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability.

  **Implementation requirements**

  * Treat this as T8.1.8, P0, estimated at 16 release-authority hours; it depends on TODOs 6, 36, 44, 55, and 57.
  * Build certification orchestration that resolves the exact release artifact, source commit, environment, requirement-catalog hash, test/evidence manifests, and approvers.
  * Verify artifact signatures, schema/SBOM/provenance, test results, security findings, statistical references, grader calibration, gate dossier, DR exercise, SLO evidence, runbooks, deployment compatibility, accessibility, and approvals.
  * Enforce freshness windows and applicability; evidence from another commit, environment, schema, dataset, or model identity is invalid.
  * Require every Must-production requirement to be green or explicitly blocking. No critical/high defect, unresolved critical review, failed integrity check, expired exception, or untested recovery path may remain.
  * Emit a signed certification manifest and immutable block report; certification remains prohibited until this workflow passes.

  **Security and safety requirements**

  * Separate evidence producers, certification orchestrator, independent approvers, signing identity, and publication authority.
  * Verify evidence through hashes and trusted registries rather than filenames or links.
  * Audit every evidence inclusion/exclusion, freshness decision, exception, approval, signature, and publication.

  **Edge cases and outliers to handle**

  * Evidence stale by minutes, conflicting test reports, partially revoked signing key, environmental drift after tests, and release rebuilt with the same version tag.
  * Approved exception expires between certification and publication, security finding severity changes, or a critical review reopens.
  * Certification process interrupted or rerun concurrently.

  **Acceptance criteria (“done” definition)**

  * Automation produces a complete signed evidence manifest for all ten categories.
  * Every Must requirement is satisfied by applicable, fresh, verifiable evidence or the release is blocked.
  * No critical/high defect, unresolved critical review, integrity gap, or expired exception remains.
  * Independent verification reproduces the certification result from the manifest without privileged database access.

  **Testing plan**

  * Unit-test evidence applicability, freshness, requirement closure, severity policy, exception expiry, and manifest signing.
  * Integration-test traceability, CI artifacts, security results, dossiers, DR/SLO evidence, trust registries, and release publication.
  * End-to-end test passing, blocked, stale-evidence, revoked-key, reopened-review, and concurrent-certification scenarios.
  * Negative/security-test forged evidence, hash substitution, self-approval, hidden failed tests, and privilege escalation; load-test evidence indexing and verification.

  **Debugging checklist**

  * Inspect release artifact/commit, requirement-catalog hash, evidence manifest, source/environment/version matching, freshness timestamps, security findings, review state, gate result, exceptions, signer key, and publication record.
  * Re-run verification from a clean environment using only the signed manifest and referenced immutable artifacts.
  * Check mutable URLs, version tags reused across builds, evidence generated before final migration, stale environment attestations, exceptions applied too broadly, and certification state cached after a blocking event.

* [ ] TODO 59: Establish long-term capacity, cost, and support operations

  **Purpose / Why this exists**

  * Sustain the platform after initial certification through funded ownership, recurring maintenance, capacity planning, vulnerability response, and cost governance.
  * Prevent security, reliability, dependency, and operational debt from accumulating silently after launch.

  **Where this applies**

  * Daily, weekly, monthly, and quarterly operating cadences; on-call, budgets, access reviews, dependency maintenance, backups, drift, capacity, threat model, and deprecation.
  * Service ownership, support matrix, patch SLAs, error budgets, and scale triggers.

  **Implementation requirements**

  * Treat this as T8.1.9, P2, estimated at 12 operations hours for setup plus recurring funded effort; it depends on TODOs 52, 54, and 56.
  * Publish service owners, backups, escalation, on-call coverage, support hours, dependency/vendor contacts, and maintenance windows.
  * Define daily health/integrity checks; weekly backlog, cost, and alert review; monthly access, patch, backup, restore-readiness, and dependency review; quarterly capacity, threat-model, DR, and architecture review.
  * Report cost per scorable run and family, provider spend, storage growth, review cost, capacity headroom, error-budget consumption, patch SLA, and support load.
  * Create automatic tickets when thresholds, expirations, patch deadlines, capacity triggers, or deprecation dates are breached.
  * Maintain a versioned support/deprecation policy for APIs, schemas, graders, datasets, models, and providers.

  **Security and safety requirements**

  * Include periodic human/workload access review, key/secret review, exception expiry, SBOM rescans, and threat-model updates.
  * Limit cost and capacity dashboards containing sensitive forecasts.
  * Audit operational-policy changes, missed reviews, accepted risk, and support escalations.

  **Edge cases and outliers to handle**

  * Staff turnover, vendor price/quota change, dependency end-of-life, sudden usage growth, prolonged incident, and support outside planned hours.
  * Error budget exhausted by an external provider, patch unavailable, or capacity trigger reached before procurement completes.
  * Metrics missing or cost attribution incomplete.

  **Acceptance criteria (“done” definition)**

  * Recurring cadences have named owners, schedules, inputs, outputs, and escalation.
  * Capacity, cost, security maintenance, patch, access, and support metrics are reported and acted upon.
  * Threshold breaches create tracked work and cannot be dismissed without approved, expiring risk acceptance.
  * Ownership and on-call coverage remain valid after personnel changes.

  **Testing plan**

  * Unit-test threshold/ticket logic, SLA calculations, ownership validation, and exception expiry.
  * Integration-test dashboards, ticketing, identity reviews, scanner results, budgets, and maintenance calendars.
  * End-to-end tabletop a capacity breach, critical dependency issue, staff departure, and vendor deprecation.
  * Negative/security-test missing owner, suppressed ticket, unauthorized policy edit, and stale access; load-test cost/capacity aggregation at projected scale.

  **Debugging checklist**

  * Inspect service owner, on-call schedule, latest cadence records, cost attribution, headroom, patch deadlines, exception expiry, access-review status, generated tickets, and escalation.
  * Recompute disputed cost/capacity values from immutable usage records.
  * Check unowned services, departed users in groups, recurring jobs disabled, provider prices cached beyond effective date, tickets closed without evidence, and dashboards excluding failed/non-scorable attempts.

* [ ] TODO 60: Validate retrieval, vector, accelerator, and advanced-lane scope

  **Purpose / Why this exists**

  * Decide whether retrieval, vector storage, embeddings, accelerators, multimodal inputs, adaptive exploration, local models, or regional executors are necessary.
  * Prevent premature advanced capabilities from indexing restricted evidence, fragmenting certification, increasing attack surface, or creating unsupported operational burden.

  **Where this applies**

  * Retrieval and embedding pipelines, vector storage, multimodal processing, adaptive case generation, local model serving, GPU/accelerator infrastructure, and regional execution.
  * Architecture decisions and any future implementation epics; these capabilities remain outside the initial release unless separately approved.

  **Implementation requirements**

  * Treat this as T8.1.10, P3, estimated at 8 architecture/research hours for validation only; it depends on TODOs 3 and 9.
  * For each capability, document use case, measurable benefit, target population, data classifications, quality/latency goal, cost, threats, operational owner, alternatives, and effect on certification.
  * Run isolated prototypes only with synthetic or approved redacted data and compare against the simpler baseline.
  * If vector work is approved, select a specific column/index type and embedding dimension, version the embedding model, define project/classification scope, lifecycle, deletion, re-embedding, and migration tests.
  * Otherwise mark vector type and embedding dimension `NOT_APPLICABLE`.
  * Create separate implementation epics only after measured benefit, security/privacy review, capacity approval, and ownership are complete.

  **Security and safety requirements**

  * Prevent cross-project retrieval, hidden-set leakage, embedding inversion exposure, poisoned document ingestion, and unauthorized external model calls.
  * Apply retention, deletion, legal hold, provenance, encryption, and access controls to derived vectors and multimodal features.
  * Accelerators and local models require patched images, isolated workloads, signed artifacts, and no shared unsafe caches.

  **Edge cases and outliers to handle**

  * Stale embeddings after source deletion/change, model-version drift, approximate-search nondeterminism, low-recall critical cases, and vector index restore.
  * Multimodal parser vulnerabilities, adaptive exploration contaminating hidden sets, GPU exhaustion, and regional model differences.
  * Prototype benefits that disappear under production security or latency constraints.

  **Acceptance criteria (“done” definition)**

  * Every advanced capability has an approved `ADOPT`, `DEFER`, or `NOT_APPLICABLE` decision with evidence.
  * No implementation begins without defined data lifecycle, security controls, quality targets, cost, and operating owner.
  * Approved prototypes show measurable benefit over the baseline without weakening certification or isolation.
  * Deferred features cannot become implicit production dependencies.

  **Testing plan**

  * Unit-test prototype contracts, project filters, versioning, deletion propagation, and deterministic fallback.
  * Integration-test isolated retrieval/vector/multimodal or accelerator prototypes with lifecycle, storage, and identity controls.
  * End-to-end compare baseline and prototype on approved synthetic/redacted workloads.
  * Negative/security-test poisoning, cross-project retrieval, stale deletion, malformed media, and resource exhaustion; load-test latency, recall, index growth, and accelerator capacity.

  **Debugging checklist**

  * Inspect decision record, prototype version, source and derived hashes, embedding/model version, project/classification filters, index parameters, quality metrics, latency, cost, and lifecycle events.
  * Reproduce comparisons from the same immutable dataset and baseline.
  * Check hidden-set contamination, vectors surviving source deletion, global indexes, approximate-search seeds, model alias drift, and prototypes relying on privileges or network access unavailable in production.
