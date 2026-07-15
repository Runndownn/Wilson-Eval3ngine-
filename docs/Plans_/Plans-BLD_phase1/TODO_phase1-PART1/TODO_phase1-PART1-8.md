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






















* [ ] TODO 22: Implement the durable leasing scheduler and reconciliation

  **Purpose / Why this exists**

  * Reliably execute logical runs despite worker death, retries, cancellation, provider faults, and scheduler failover.
  * Prevent lost work, duplicate logical outcomes, stale workers committing results, and jobs remaining permanently stranded.

  **Where this applies**

  * PostgreSQL job/run/attempt tables, scheduler process, worker heartbeats, retry policy, pause/resume/cancel controls, dead-letter handling, and reconciliation.
  * Provider execution, grading, report, and maintenance job types.

  **Implementation requirements**

  * Treat this as T4.1.2, P0, estimated at 16 platform hours; it depends on TODOs 15, 18, and 21.
  * Use `FOR UPDATE SKIP LOCKED` or an equivalent proven pattern to claim eligible jobs by priority, project fairness, and scheduled time.
  * Distinguish logical runs from attempts. A logical run has one deterministic uniqueness key; every provider call creates a separately persisted attempt.
  * Implement fenced leases with owner ID, lease token/version, acquired time, expiry, heartbeat, and compare-and-set completion.
  * Define states including pending, leased, running, retry-wait, succeeded, terminal-failed, cancelled, and dead-letter; permit only explicit transitions.
  * Add bounded retries with jitter, poisoned-job detection, stale-job sweeper, admission pause, cancellation checkpoints, and periodic full reconciliation.

  **Security and safety requirements**

  * Workers may claim only authorized job types and projects through workload identity plus RLS.
  * Validate job payload schema and artifact hashes before execution; never execute arbitrary commands or unregistered task types.
  * Audit claim, heartbeat loss, retry, cancellation, dead-letter, manual replay, and reconciliation changes.

  **Edge cases and outliers to handle**

  * Worker completes after lease expiry, two workers race to finalize, cancellation arrives during provider response, scheduler clock skew, and heartbeat delays.
  * Duplicate start requests, provider call succeeded but acknowledgment failed, poison jobs repeatedly retried, and a project paused mid-lease.
  * Database failover, partial network partition, long-running attempts, priority inversion, and version-skewed workers.

  **Acceptance criteria (“done” definition)**

  * Worker death or scheduler restart causes no lost or duplicate logical run.
  * Stale workers cannot commit after a newer lease is issued.
  * Pause, resume, cancel, retry, and dead-letter behavior are deterministic, authorized, and auditable.
  * Reconciliation reports zero unexplained stranded jobs, duplicate logical keys, or attempts lacking provenance.

  **Testing plan**

  * Unit-test transition rules, lease fencing, retry calculation, logical keys, and cancellation semantics.
  * Integration-test concurrent claims, heartbeat, expiry, worker restart, database failover, and outbox interaction.
  * End-to-end test start/pause/resume/cancel/retry/dead-letter through API and workers.
  * Negative-test forged lease tokens, unauthorized job types, stale completion, and duplicate requests; load/stress-test claim contention and security-test cross-project isolation.

  **Debugging checklist**

  * Inspect logical-run key, job state, attempt number, lease owner/token/expiry, heartbeat, retry count, cancellation marker, worker version, and state-transition audit.
  * Reproduce races with deterministic barriers and a controllable clock.
  * Check for completion updates lacking lease predicates, local-clock assumptions, transaction boundaries around claim, retries performed inside adapters, and reconciliation reading stale replicas.

* [ ] TODO 23: Implement the canonical provider-adapter contract and deterministic mock

  **Purpose / Why this exists**

  * Isolate provider-specific APIs behind a stable request, response, identity, usage, and error model.
  * Enable deterministic development and failure testing without external cost or provider behavior leaking into core execution logic.

  **Where this applies**

  * Provider interface, canonical request/response types, capability negotiation, error taxonomy, deterministic mock, execution workers, cost accounting, and test fixtures.
  * All future hosted or local provider adapters.

  **Implementation requirements**

  * Treat this as T4.1.3, P0, estimated at 16 integration hours; it depends on TODOs 8 and 13.
  * Define canonical request fields for provider/model ID, messages/input, system context, parameters, tool/simulator definitions, deadline, expected capabilities, experiment/run/attempt IDs, and request hash.
  * Define response fields for provider request ID, reported model identity, content/artifact references, finish reason, usage, latency, raw-response hash, normalized error, retryability, and capability observations.
  * Adapters must perform one attempt only; retry policy belongs to the scheduler.
  * Implement a seeded mock that simulates success, timeout, 429, 5xx, malformed response, partial stream, usage anomalies, content filtering, and model-identity drift.
  * Publish extension rules so provider-specific metadata remains namespaced and cannot alter common semantics.

  **Security and safety requirements**

  * Keep credentials outside request objects, persistence payloads, logs, fixtures, and telemetry.
  * Validate all provider output as untrusted; bound response sizes and parsing time.
  * Audit provider, model identity, endpoint class, request/response hashes, usage, normalized error, and correlation IDs without storing secret headers.

  **Edge cases and outliers to handle**

  * Streaming disconnect, missing usage, unknown finish reason, provider returning an alias instead of exact model ID, malformed JSON, and success with empty content.
  * Unsupported parameters, provider silently clamping values, asynchronous moderation failures, and cost metadata arriving after content.
  * Mock scenarios requested with invalid seeds or incompatible capability sets.

  **Acceptance criteria (“done” definition)**

  * Canonical types and normalized errors are versioned, strict, and shared by all adapters.
  * The deterministic mock reproduces each documented scenario byte-for-byte from the same seed.
  * Core scheduler and grading code contain no provider-specific branches.
  * Missing gating metadata or unexpected identity produces an explicit non-scorable failure, not silent substitution.

  **Testing plan**

  * Unit-test mapping, normalization, request hashing, error classification, capability negotiation, and mock determinism.
  * Integration-test workers, scheduler retry decisions, persistence, telemetry, and cost accounting using the mock.
  * End-to-end test complete experiments for every mock fault scenario.
  * Negative-test oversized/malformed responses, credential leakage, unsupported parameters, and identity mismatch; load-test mock concurrency and security-test parser and metadata handling.

  **Debugging checklist**

  * Inspect canonical request hash, adapter version, endpoint, provider request ID, reported model ID, finish reason, usage, deadline, raw hash, normalized error, and retry decision.
  * Compare raw-provider fixtures with normalized records without exposing credentials.
  * Check for retries hidden in SDK defaults, provider-specific fields copied into core models, implicit parameter defaults, streaming buffers bypassing limits, and mock seeds not recorded.

* [ ] TODO 24: Approve the initial provider and model scope

  **Purpose / Why this exists**

  * Select the specific hosted providers and model identities that the initial production release will support.
  * Prevent implementation against ambiguous aliases, prohibited data terms, unsuitable regions, unstable capabilities, or unbudgeted quotas.

  **Where this applies**

  * Provider adapters A and B, model identity/fingerprinting, credentials, network allowlists, pricing, quotas, data-processing terms, experiment validation, and release claims.
  * Provider/model combinations permitted by data classification and region.

  **Implementation requirements**

  * Treat this as T4.1.4, P0, estimated at 8 product/architecture hours plus vendor review lead time; it depends on TODOs 3 and 4.
  * Produce a signed decision listing provider, exact model IDs or immutable version identifiers, regions, supported parameters, context limits, tool capabilities, identity metadata, pricing, quotas, retention, training-use terms, and deprecation policy.
  * Map each data classification and benchmark mode to allowed or prohibited provider/model combinations.
  * Compare both candidates against the canonical adapter contract and document unsupported capabilities and safe fallback behavior.
  * Approve the two-provider assumption or replace it with an explicit alternative, risk record, and revised acceptance criteria.

  **Security and safety requirements**

  * Require enterprise authentication, short-lived/scoped credentials where available, approved processing terms, and endpoint allowlists.
  * Prohibit aliases that can silently retarget models unless provider-reported identity and fingerprint controls can detect change.
  * Audit provider approvals, contract-term changes, model deprecation notices, and scope exceptions.

  **Edge cases and outliers to handle**

  * Provider changes model behind an alias, model available in one region only, quota varies by account, or retention terms differ by endpoint.
  * Capability mismatch between providers, content filters preventing comparable requests, and a provider unable to return required identity or usage metadata.
  * Sudden deprecation, region outage, price change, or a data-classification policy becoming stricter.

  **Acceptance criteria (“done” definition)**

  * The decision names every approved provider/model/region and documents required metadata, limits, cost, and data rules.
  * Experiment validation rejects unapproved combinations before scheduling.
  * Model aliases or unverifiable identities cannot be used for release-gating comparisons.
  * Provider scope has accountable product, security, privacy, measurement, and release approval.

  **Testing plan**

  * Unit-test provider/model allowlist and classification policy evaluation.
  * Integration-test identity probes, quota discovery, endpoint access, retention configuration, and canonical capability mapping.
  * End-to-end test one synthetic request per approved combination in staging.
  * Negative-test unapproved regions/models, prohibited classifications, alias drift, missing identity, and expired credentials; load-test documented quotas and security-test endpoint/credential scope.

  **Debugging checklist**

  * Inspect approved-scope version, provider account/region, requested and reported model IDs, capability probe, quota, retention mode, and policy decision.
  * Re-run identity and capability probes using non-sensitive canaries.
  * Check for console-only configuration, alias resolution changes, account-level defaults, stale legal terms, regional endpoint mismatch, and SDK defaults selecting a different model.
