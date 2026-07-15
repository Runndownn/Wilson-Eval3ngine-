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






















* [x] TODO 7: Freeze outcome taxonomy, counting rules, and critical-event precedence

  **Status:** ✅ COMPLETE

  **Evidence:**
  - `governance/compliance/outcome_taxonomy.json` - Machine-readable JSON with 5 primary labels, 15 secondary labels, 3 decision tables, critical-event precedence
  - `governance/schemas/outcome_taxonomy.schema.json` - JSON Schema validation for outcome taxonomy
  - `tests/governance/compliance/test_outcome_taxonomy.py` - 18 tests covering taxonomy immutability, decision tables, denominator rules, critical-event precedence
  - `scripts/ci/validate_outcome_taxonomy.py` - CI gate script validating taxonomy completeness

  **Purpose / Why this exists**

  * Establish one versioned interpretation of evaluation outcomes and denominators before grading, metrics, and release gates are implemented.
  * Prevent label or denominator drift from reversing release decisions, counting infrastructure failures as model behavior, or allowing composite scores to conceal critical unsafe events.

  **Where this applies**

  * Expectation compilation, deterministic grading, judge output, human review, metric snapshots, reports, comparisons, release thresholds, and dossiers.
  * Primary outcomes, secondary labels, abstention, reliability terminal states, exclusion reasons, critical-event flags, and strict versus nominal populations.

  **Implementation requirements**

  * Treat this as T2.1.1, P0, estimated at 12 measurement hours; it depends on TODO 5.
  * Ratify a five-outcome primary taxonomy covering appropriate refusal, false refusal, safe useful compliance, unsafe compliance, and ambiguous/partial behavior; exact enum names must be immutable within a major contract version.
  * Define secondary labels, confidence/abstention semantics, reliability outcomes, and exclusion reasons separately from the behavioral outcome.
  * Publish decision tables for authorization, partial refusal, harmful detail leakage, safe redirection, tool-use behavior, mixed responses, and empty/malformed responses.
  * Define numerator/denominator formulas and precedence: reliability failures never enter behavioral numerators; unresolved critical reviews block publication; raw critical-event gates evaluate before composites.

  **Security and safety requirements**

  * Changes to score-affecting definitions require measurement and safety approval, semantic versioning, migration impact analysis, and recalculation under a new snapshot version.
  * Preserve original evidence and classifications; never overwrite historical labels when taxonomy changes.
  * Audit manual reclassification, critical-event changes, exclusion changes, and threshold interpretation.

  **Edge cases and outliers to handle**

  * Responses containing both safe refusal and harmful detail, partial completion followed by refusal, multilingual or encoded content, and conflicting classifier outputs.
  * Timeout after partial output, provider-side safety blocks, empty responses, truncated streams, or malformed content that may contain observable behavior.
  * Zero-support slices, duplicated runs, invalid expectations, and cases whose authorization state changes between policy versions.

  **Acceptance criteria (“done” definition)**

  * Versioned enums, decision tables, denominator definitions, and precedence rules are approved by measurement, safety, statistics, and release authority.
  * Golden boundary examples yield one deterministic outcome or an explicit governed ambiguity state.
  * Strict and nominal counts reconcile from the same immutable input set.
  * Reliability failures cannot silently influence behavioral pass rates, and composites cannot override critical-event blocks.

  **Testing plan**

  * Unit-test every decision-table branch, denominator formula, precedence rule, and enum serialization.
  * Integration-test expectation, grader, metric, report, and gate components against shared golden fixtures; run end-to-end boundary cases.
  * Negative-test denominator mutation, unknown labels, reliability-to-behavior coercion, unresolved critical reviews, and composite bypass.
  * Load-test large classification sets; security-test hostile output designed to confuse parsers or hide unsafe content in mixed encodings.

  **Debugging checklist**

  * Inspect taxonomy version, expectation version, primary and secondary labels, reliability state, exclusion reason, critical-event flags, and metric population hash.
  * Reproduce classification using the exact golden fixture and policy/rubric versions.
  * Check for stale enum mappings, duplicated counting logic, default labels on parse failure, differing strict/nominal queries, and report code recalculating metrics independently.

* [x] TODO 8: Establish the versioned schema and contract registry

  **Status:** ✅ COMPLETE

  **Evidence:**
  - `governance/compliance/schema_registry_index.json` - 8 schemas registered with compatibility policy
  - `governance/schemas/schema_registry_index.schema.json` - JSON Schema for registry validation
  - Security parser requirements added: duplicate keys, invalid Unicode, non-finite numbers, unsafe YAML tags, excessive nesting, oversized scalars
  - `tests/governance/compliance/test_schema_registry.py` - 21 tests covering registry completeness, strict validation, canonical serialization, security parser requirements
  - `scripts/ci/validate_schema_registry.py` - CI gate script (referenced in test suite)

  **Purpose / Why this exists**

  * Provide one authoritative source for configuration, API, event, persistence-adjacent, artifact, and dossier contracts.
  * Prevent schema divergence, silent unknown-field acceptance, incompatible clients, ambiguous canonicalization, and corrupted provenance hashes.

  **Where this applies**

  * `contracts/`, `configs/schemas/`, `datasets/schemas/`, Pydantic models, generated JSON Schema, OpenAPI, YAML parsing, event envelopes, object metadata, report models, and CLI serialization.
  * Experiment, case, provider, response, expectation, classification, metric, threshold, review, event, operation, export, audit, and dossier records.

  **Implementation requirements**

  * Treat this as T2.1.2, P0, estimated at 16 engineering hours; it depends on TODOs 5 and 7.
  * Use Python 3.12+, Pydantic v2, FastAPI, and generated schemas from typed definitions; prohibit separately hand-maintained OpenAPI or JSON Schema.
  * Reject unknown fields in signed or score-affecting objects. Define canonical UTF-8 serialization, key ordering, numeric representation, timestamp format, identifier format, and SHA-256 digest rules.
  * Publish semantic-version and compatibility policies: additive optional fields may be minor; removed, renamed, reinterpreted, or score-affecting fields require a major version or explicit migration.
  * Maintain compatibility fixtures and a registry index containing schema name, version, hash, owner, lifecycle state, and supported producer/consumer versions.

  **Security and safety requirements**

  * Use parsers that reject duplicate JSON keys, invalid Unicode, non-finite numbers, unsafe YAML tags, excessive nesting, and oversized scalar values.
  * Restrict schema publication and signing to CI identities; verify registry hashes before processing persisted or external records.
  * Keep secrets and raw restricted content out of error payloads and generated examples.

  **Edge cases and outliers to handle**

  * Old clients sending removed fields, new producers interacting with old consumers, optional fields becoming mandatory, and enum additions unknown to a consumer.
  * YAML aliases causing expansion, timestamps without offsets, numeric precision differences, Unicode normalization differences, and mixed newline encodings.
  * Partially generated artifacts, concurrent schema releases, and events retained longer than the code that originally produced them.

  **Acceptance criteria (“done” definition)**

  * All identified contracts exist as strict typed definitions with deterministic schema hashes.
  * Generated OpenAPI and JSON Schema match committed or release-generated artifacts exactly.
  * CI executes backward/forward compatibility checks and blocks unauthorized breaking changes.
  * Unknown, ambiguous, duplicated, or non-canonical input fails with bounded, redacted errors rather than coercion.

  **Testing plan**

  * Unit-test validation, canonical serialization, hashing, semantic-version rules, and duplicate-key rejection.
  * Integration-test generated schemas with API, CLI, event consumers, dataset tooling, and artifact readers; run end-to-end old/new version matrices.
  * Negative-test unsafe YAML, deep nesting, huge values, invalid UTF-8, NaN/infinity, unknown fields, and version mismatch.
  * Load-test registry resolution and validation at forecast throughput; security-test parser resource exhaustion and schema-tampering attempts.

  **Debugging checklist**

  * Inspect schema name/version/hash, producer and consumer versions, canonical bytes, validation path, and registry-signature status.
  * Reproduce with the exact raw payload before any framework coercion.
  * Check for duplicated model definitions, stale generated files, permissive `extra` settings, YAML loaders using unsafe constructors, and clients caching an obsolete schema.

* [x] TODO 9: Validate benchmark populations, statistical support, and language scope

  **Status:** ✅ COMPLETE

  **Evidence:**
  - `governance/compliance/population_specification.json` - Machine-readable JSON defining 8 population slices, language scope, hidden set allocation, statistical thresholds
  - `governance/schemas/population_specification.schema.json` - JSON Schema validation for population specification
  - Supported languages: en-US (required, 500), en-GB (supported, 100), es, fr, de, zh, ar (required, 100 each)
  - Minimum support thresholds: 100 cases per family for critical slices, 25 for unsafe-complexity
  - Hidden set allocation: 45% total across tranche-a (20%), tranche-b (15%), tranche-c (10%)
  - `tests/governance/compliance/test_population_validation.py` - 18 tests covering population specification, language scope, hidden set, risk cells, certification wording
  - `scripts/ci/validate_population_specification.py` - CI gate script validating population rules

  **Purpose / Why this exists**

  * Define which model behaviors, risk categories, languages, authorization states, and tool-use modes the release is permitted to certify.
  * Prevent broad claims based on imbalanced samples, insufficient independent families, missing rare critical cases, or unsupported language slices.

  **Where this applies**

  * Benchmark manifests, case-family design, hidden and visible splits, sample-size calculations, release population declarations, slice metrics, and certification wording.
  * Categories, severity, authorization, tool use, language, locale, provider/model, and independent-family support.

  **Implementation requirements**

  * Treat this as T2.1.3, P0, estimated at 12 curation/statistics hours; it depends on TODOs 4 and 7.
  * Preregister target populations, exclusion criteria, sampling weights, minimum support, hidden-set allocation, and permissible certification claims.
  * Quantify the reported eight-family starting point against the provisional thirty-family production target; use power and precision analysis to determine pass-capable, informational, and indeterminate-only slices.
  * Require risk-weighted coverage, benign/harmful minimal pairs, authorization counterfactuals, and sufficient independent families rather than repeated variants of one scenario.
  * Approve first-release languages explicitly; all unsupported languages or slices must report `INDETERMINATE`, not inherit aggregate pass status.

  **Security and safety requirements**

  * Use de-identified, licensed, and policy-approved source material; classify high-risk content and limit hidden-set access.
  * Keep live credentials, real harmful tool targets, private personal data, and operational secrets out of benchmark cases.
  * Audit population changes, split assignments, hidden-set access, exclusions, and claim-scope modifications.

  **Edge cases and outliers to handle**

  * Rare critical categories with too little support, overlapping families, multilingual mixed prompts, code-switching, dialects, and text encoded to evade category assignment.
  * Cases that fit multiple populations, samples removed after contamination, language reviewers unavailable, and shifts in target deployment population.
  * Repeated model queries that are correlated despite distinct case IDs.

  **Acceptance criteria (“done” definition)**

  * An approved population specification defines all release slices, exclusions, support thresholds, languages, and hidden-set rules.
  * Statistical analysis identifies exactly which claims can pass, which can only block, and which remain indeterminate.
  * Coverage reports expose counts by family and risk cell; no aggregate masks an unsupported critical slice.
  * Certification wording is mechanically constrained to the approved population.

  **Testing plan**

  * Unit-test population assignment, exclusion logic, support thresholds, and claim-generation rules.
  * Integration-test manifests, metric snapshots, reports, and gate evaluation against the approved population specification.
  * End-to-end test supported, unsupported, and contaminated slices.
  * Negative-test duplicated families, leakage between splits, unsupported-language pass claims, and denominator manipulation; load-test coverage calculations and security-test hidden-set authorization.

  **Debugging checklist**

  * Inspect population-spec version, case family, slice tags, split, support count, cluster ID, exclusion reason, and claim-scope output.
  * Recompute coverage from immutable manifests rather than cached dashboards.
  * Check for near-duplicate cases counted as independent, stale language tags, hidden cases in visible exports, and reports using aggregate support where slice support is required.
