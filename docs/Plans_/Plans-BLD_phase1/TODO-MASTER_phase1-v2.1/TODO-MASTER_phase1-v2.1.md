## TODO

* [ ] TODO 1: Reconcile source claims with the current repository snapshot

  **Purpose / Why this exists**

  * Establish a trustworthy implementation baseline before any architecture, migration, security, or release work begins. The supplied material reports a historical `0.1.0 Foundation`, but the current repository, CI state, runtime, cloud resources, and generated artifacts have not been independently verified. 
  * Prevent subsequent work from relying on stale files, absent modules, uncommitted changes, misleading test reports, or undocumented environment assumptions.

  **Where this applies**

  * The complete Wilson Eval3ngine repository; Git history and submodules; Python package metadata; configuration, schema, migration, dataset, infrastructure, CI, documentation, test, and generated-artifact directories.
  * All claims in ADR-001–ADR-005, delivery notes, framework status, test reports, implementation blueprints, runbooks, and source-evidence documents.

  **Implementation requirements**

  * Treat this as source item T1.1.1, priority P0, estimated at 8 engineering hours. Assign a repository or quality engineer; the program owner is accountable, security is consulted, and release authority is informed.
  * Capture an immutable inventory containing the repository URI, branch, exact commit SHA, worktree status, remotes, tags, submodule SHAs, tracked files, untracked files, dependency lockfiles, toolchain versions, generated outputs, and SHA-256 hashes of supplied planning material.
  * Execute tests and CLI validation only in the authorized remote execution context. Record command, working directory, environment fingerprint, start/end timestamps, exit code, stdout/stderr hash, and resulting artifacts.
  * Classify each source claim as `VERIFIED`, `PARTIALLY_VERIFIED`, `ABSENT`, `STALE`, `BLOCKED`, or `NOT_APPLICABLE`; attach evidence and an owner to every discrepancy.
  * Freeze implementation sequencing until material discrepancies affecting contracts, persistence, security, or certification have approved dispositions.

  **Security and safety requirements**

  * Use read-only repository and CI credentials wherever possible; do not expose environment variables, tokens, provider credentials, secrets, raw prompts, or restricted evidence in captured logs.
  * Store the evidence inventory in a restricted, append-only location; sign or externally timestamp its manifest so later changes are detectable.
  * Resolve symlinks and submodule paths without following links outside the authorized workspace; reject archive extraction or generated-output paths containing traversal sequences.

  **Edge cases and outliers to handle**

  * Dirty worktrees, shallow clones, detached HEADs, Git LFS pointers without objects, inaccessible submodules, generated files absent from source control, and multiple conflicting version declarations.
  * CI unavailable or authorized credentials missing; tests that require external providers; platform-specific tests; nondeterministic tests; test reports referring to commits other than the inspected SHA.
  * Very large repositories, unusual encodings, case-colliding paths, broken symlinks, and historical artifacts copied into recent directories.

  **Acceptance criteria (“done” definition)**

  * A hash-addressed evidence manifest and claim-to-evidence matrix cover every supplied source and every discovered repository component.
  * Current test, validation, build, schema-generation, and dependency-resolution results are preserved with reproducible commands and explicit limitations.
  * No capability is described as implemented, passing, secure, or production-ready without evidence tied to the inspected commit.
  * All sequencing-impacting discrepancies have named owners, severity, target disposition, and dependent TODOs.

  **Testing plan**

  * Unit-test inventory parsers, hash generation, claim-state validation, path normalization, and evidence-manifest serialization.
  * Integration-test the process against clean, dirty, shallow, submodule, and Git LFS fixture repositories; run an end-to-end audit from a fresh clone.
  * Negative-test missing tools, denied CI access, malformed reports, secret-like values, symlink escapes, and mismatched commit references.
  * Load-test inventory and hashing against a repository materially larger than forecast; security-test redaction, archive handling, and evidence immutability.

  **Debugging checklist**

  * Inspect `git status`, `git rev-parse HEAD`, tag/version outputs, submodule status, lockfile hashes, Python/tool versions, command exit codes, and evidence-manifest signatures.
  * Reproduce failures from a fresh, isolated checkout using the recorded environment fingerprint; compare file hashes and generated artifacts before investigating application logic.
  * Check common causes first: wrong branch, stale virtual environment, missing optional dependencies, absent external services, incorrect working directory, or historical test output mistaken for current evidence.

* [ ] TODO 2: Validate staffing, RACI, and decision authority

  **Purpose / Why this exists**

  * Confirm that every production-critical workstream has qualified execution, review, approval, incident-response, and release ownership.
  * Prevent unsafe role consolidation, unreviewed decisions, stalled approvals, unsupported on-call obligations, and overrides approved by people who implemented or requested them.

  **Where this applies**

  * Architecture, measurement, safety, security, SRE, data curation, provider integration, human review, statistics, privacy, release engineering, and support operations.
  * Pull-request approvals, architecture decisions, dataset promotion, grader release, security exceptions, release-gate overrides, signing, incident command, and break-glass access.

  **Implementation requirements**

  * Treat this as T1.1.2, P0, estimated at 6 coordination hours plus organizational approval lead time. The program owner is accountable.
  * Produce a named RACI matrix for all P0 and P1 tasks, including primary and backup owners, time-zone coverage, decision quorum, escalation path, and maximum approval latency.
  * Define prohibited overlaps: an individual must not solely create and approve a benchmark release, grader release, release override, signing-key change, production access grant, or certification result.
  * Confirm reviewer-pool size, language and subject-matter coverage, SRE on-call coverage, incident commander backups, and release-authority availability against the planned delivery cadence.
  * Record vacancies and capacity constraints as scope gates; reduce parallel work or defer production capabilities rather than silently merging incompatible duties.

  **Security and safety requirements**

  * Bind privileged roles to least-privilege identity groups with periodic access review; do not use shared accounts or generic team credentials.
  * Require two-person approval for overrides, key-management changes, hidden-set access, destructive lifecycle operations, and production certification.
  * Audit assignments, role changes, recusals, temporary delegation, break-glass activation, and approval decisions with actor, scope, timestamp, rationale, and correlation ID.

  **Edge cases and outliers to handle**

  * Contractors, temporary staff, vacations, departures, conflicts of interest, emergency coverage, regional holidays, and unavailable specialist reviewers.
  * A single person holding multiple titles, delegated approval that exceeds the delegator’s scope, inactive group memberships, or role changes during an active release.
  * Review surges, incidents occurring outside business hours, and simultaneous security and availability events requiring separate authorities.

  **Acceptance criteria (“done” definition)**

  * Every P0/P1 item has one named responsible owner, one accountable approver, consulted specialists, informed stakeholders, and at least one backup.
  * Separation-of-duties checks pass for all privileged workflows; unresolved staffing gaps block dependent scope.
  * On-call, escalation, reviewer-capacity, and approval-quorum records are approved and accessible to operators.
  * No task relies on an unnamed placeholder or an unsupported assumption that staff will become available later.

  **Testing plan**

  * Unit-test RACI schema validation, duplicate-accountable-owner detection, prohibited-overlap rules, and delegation-expiry logic.
  * Integration-test identity-group mappings against workflow permissions; run end-to-end tabletop approvals for dataset promotion, override, incident, and release certification.
  * Negative-test self-approval, absent quorum, expired delegation, departed users, and unauthorized break-glass use.
  * Load/stress-test staffing models against forecast review and incident volumes; security-test least privilege and orphaned-access removal.

  **Debugging checklist**

  * Inspect role matrix versions, identity-group memberships, approval events, delegation records, recusal flags, staffing forecasts, and on-call schedules.
  * Reproduce workflow authorization using a test identity for each role rather than administrator credentials.
  * Look for stale directory synchronization, duplicate aliases, missing backup owners, conflicting approval rules, and release workflows that bypass the central authorization service.

* [ ] TODO 3: Validate the production operating context and platform services

  **Purpose / Why this exists**

  * Resolve the actual production region model, orchestrator, managed services, network controls, and remote execution environment before infrastructure-dependent code is finalized.
  * Avoid designing migrations, object storage, identity, disaster recovery, or telemetry around capabilities the selected platform does not provide.

  **Where this applies**

  * Local, integration, staging, and production environments; PostgreSQL, S3-compatible object storage, OIDC, KMS/secrets, workload orchestration, network policy, DNS, ingress, telemetry, backup, and CI/CD services.
  * Infrastructure-as-code repositories, environment configuration, service identities, operational access paths, and vendor support contracts.

  **Implementation requirements**

  * Treat this as T1.1.3, P0, estimated at 8 architecture hours plus vendor or procurement lead time; it depends on TODO 1.
  * Produce a signed platform decision identifying cloud/account structure, regions, availability zones, orchestrator, PostgreSQL service and version, object-store features, OIDC provider, KMS/secrets service, telemetry backend, CI runner model, and remote execution channel.
  * Verify required capabilities through non-production probes: PostgreSQL PITR and RLS, object versioning/immutability, customer-managed encryption keys, network-policy enforcement, workload identity, private endpoints, audit logging, and exportable telemetry.
  * Define environment boundaries, approved data classifications, credential sources, egress rules, naming conventions, quotas, and promotion paths.
  * Until approved, use isolated staging with synthetic or redacted data; do not provision production persistence or ingest Restricted/Secret content.

  **Security and safety requirements**

  * Separate accounts/projects and credentials by environment; production identities must not be usable from developer workstations or integration runners.
  * Require private networking or equivalent controls for databases and object storage, default-deny egress where supported, managed encryption, and auditable administrative access.
  * Document break-glass access, session recording, just-in-time elevation, credential rotation, and evidence-preservation requirements.

  **Edge cases and outliers to handle**

  * Missing object-lock support, database extensions unavailable on the managed service, single-region restrictions, OIDC claim limitations, or telemetry backends that cannot enforce retention.
  * Vendor outages, quota ceilings, region unavailability, unsupported network-policy features, and different capabilities between staging and production.
  * Multiple cloud accounts, hybrid connectivity, private DNS failures, and remote-execution tooling that cannot preserve command evidence.

  **Acceptance criteria (“done” definition)**

  * The platform ADR is approved by architecture, security, SRE, and release authority and resolves every platform placeholder.
  * Capability probes and limitations are documented with outputs, timestamps, service versions, and compensating controls.
  * Local, integration, staging, and production trust boundaries are explicit; no production dependency remains implied or unnamed.
  * Platform mismatches generate owned redesign decisions before schema, identity, DR, or IaC implementation proceeds.

  **Testing plan**

  * Unit-test platform configuration schemas, environment invariants, and capability-result parsing.
  * Integration-test OIDC, KMS, PostgreSQL, object storage, network policies, private endpoints, and telemetry export in a staging account.
  * End-to-end test a synthetic request through API, persistence, object storage, and telemetry with no public-network dependency.
  * Negative-test cross-environment credentials, blocked egress, denied administrative operations, missing capabilities, and quota exhaustion; load-test service limits and security-test privilege boundaries.

  **Debugging checklist**

  * Inspect account/region IDs, service versions, feature flags, network-policy verdicts, KMS key IDs, OIDC issuer/audience, database parameters, object-store version IDs, and telemetry exporter status.
  * Compare staging and production capability manifests; reproduce failures with a minimal synthetic workload.
  * Check common faults: wrong account, public endpoint fallback, expired workload identity, unsupported database parameter, object-lock not enabled at bucket creation, or firewall/DNS policy drift.

* [ ] TODO 4: Approve compliance, residency, retention, and content classes

  **Purpose / Why this exists**

  * Convert legal, privacy, safety, and contractual obligations into enforceable data-handling rules before production data is persisted or sent to providers.
  * Prevent unlawful transfers, indefinite retention, unfulfillable deletion requests, unsafe reviewer exposure, or telemetry containing content prohibited by policy.

  **Where this applies**

  * Public, Internal, Confidential, Restricted, and Secret data across benchmark sources, prompts, model responses, attachments, grades, reviews, telemetry, reports, exports, backups, and audit records.
  * Provider processing, object storage, PostgreSQL, caches, log systems, disaster-recovery copies, analyst interfaces, and human-review workflows.

  **Implementation requirements**

  * Treat this as T1.1.4, P0, estimated at 8 workshop hours plus legal approval lead time; it depends on TODO 1.
  * Build a data-flow inventory from source acquisition through deletion, listing controller/processor roles, regions, subprocessors, retention period, lawful purpose, access roles, and incident-notification obligations.
  * Define an enforceable policy matrix for each classification covering allowed environments, provider eligibility, encryption/key requirements, telemetry treatment, reviewer visibility, export restrictions, retention, legal hold, and disposal.
  * Establish precedence rules for legal hold, deletion, backup expiration, cryptographic deletion, incident preservation, and immutable certification evidence.
  * Default unidentified data to Restricted and prohibit provider transmission until classified; prohibit Secret content from hosted-provider processing unless explicitly approved.

  **Security and safety requirements**

  * Enforce classification at ingestion, storage, query, export, logging, and provider-admission boundaries; labels must not be optional on business objects.
  * Minimize stored raw content, redact direct identifiers where feasible, and use separate keys or access policies for high-risk classes.
  * Audit classification changes, export approvals, raw-content reveals, retention overrides, legal holds, deletion actions, and policy exceptions.

  **Edge cases and outliers to handle**

  * Derived data whose classification is higher than its source, mixed-classification bundles, unclassified attachments, and content copied into free-text rationale fields.
  * Conflicting jurisdictional requirements, deletion requests during legal hold, restored backups containing expired records, and provider-retention terms that change.
  * Telemetry generated before classification, cross-region failover, accidental misclassification, and retroactive policy changes.

  **Acceptance criteria (“done” definition)**

  * Legal and security approve a versioned classification and lifecycle matrix covering every data path.
  * Each schema has required classification, residency, retention, and legal-hold fields or a documented inherited source.
  * Automated policy checks reject unclassified or prohibited movement; no silent downgrade or permissive default exists.
  * Incident, deletion, export, and restore procedures demonstrate compliance with the approved precedence rules.

  **Testing plan**

  * Unit-test classification inheritance, policy evaluation, retention-date calculation, and hold/deletion precedence.
  * Integration-test enforcement across API, database, object storage, provider adapters, telemetry, reports, and backups; run end-to-end lifecycle scenarios.
  * Negative-test missing labels, attempted downgrades, prohibited region/provider transfers, unauthorized exports, and deletion during hold.
  * Load-test lifecycle policy evaluation at forecast object volumes; security-test leakage through logs, traces, caches, filenames, and generated reports.

  **Debugging checklist**

  * Inspect object classification, policy version, region, retention deadline, hold state, key ID, provider-admission decision, and audit correlation ID.
  * Trace one record from ingestion through storage, provider use, review, export, backup, and deletion.
  * Check for schema defaults, stale policy caches, missing classification propagation, untagged legacy rows, restored expired data, and services applying different policy versions.

* [ ] TODO 5: Ratify modular-monolith boundaries and measurable split triggers

  **Purpose / Why this exists**

  * Establish clear domain ownership and dependency direction while retaining a deployable modular monolith for the initial production release.
  * Prevent circular imports, duplicated policy logic, provider-specific behavior leaking into core domains, and premature services that fragment contracts and security controls.

  **Where this applies**

  * Contract, dataset, expectation, execution, scheduler, provider, grading, review, metric, evidence, release, API, CLI, reporting, identity, and maintenance modules.
  * API, scheduler, provider-executor, grader, reviewer, reporting, and maintenance processes that may be deployed separately while sharing versioned domain contracts.

  **Implementation requirements**

  * Treat this as T1.1.5, P0, estimated at 8 architecture hours; it depends on TODO 1.
  * Normalize duplicate ADR-001 material into one authoritative ADR defining allowed module dependencies, public interfaces, data ownership, transaction boundaries, and forbidden cross-domain imports.
  * Keep shared schemas in a single contract registry; business modules communicate through application interfaces or versioned events rather than direct table manipulation.
  * Define independently deployable process boundaries for API, scheduler, provider executors, graders, maintenance jobs, and report workers without converting them into separately owned services prematurely.
  * Define objective split triggers: incompatible credentials, sustained independent scaling, stronger isolation, residency, ownership, runtime, release-cadence, or failure-domain requirements supported by measurements and a migration ADR.

  **Security and safety requirements**

  * Credential-bearing provider code, signing, graders, and maintenance operations must remain distinct trust zones even if stored in one repository.
  * Domain APIs must authorize requested actions rather than trusting callers or model outputs; no module may bypass audit, classification, or project scoping.
  * Architecture exceptions require documented rationale, expiry, security review, and tests preventing the exception from spreading.

  **Edge cases and outliers to handle**

  * Cyclic dependencies hidden through utility packages, ORM models imported across domains, shared global configuration, and event schemas owned by consumers rather than producers.
  * A process needing unique credentials but not independent scaling, or independent scaling without a stable contract.
  * Long-running jobs spanning deployment versions, temporary compatibility adapters, and modules sharing a database transaction during a future split.

  **Acceptance criteria (“done” definition)**

  * One approved ADR contains a module map, process map, dependency rules, trust zones, transaction ownership, and split criteria.
  * Automated architecture tests fail on forbidden imports, cyclic dependencies, cross-domain table writes, or unowned contracts.
  * Each production process has an explicit entry point, identity, configuration surface, and failure boundary.
  * No service split is approved solely for organizational preference or speculative scale.

  **Testing plan**

  * Unit-test architecture-rule configuration and module ownership metadata.
  * Integration-test application interfaces and event contracts without importing provider, persistence, or UI internals.
  * End-to-end test each deployable process against the same contract versions.
  * Negative-test forbidden imports, direct cross-domain database access, credential sharing, and circular dependencies; load-test split triggers and security-test trust-zone isolation.

  **Debugging checklist**

  * Inspect import graphs, dependency cycles, public-interface usage, ORM ownership, process entry points, event versions, and credential mounts.
  * Reproduce architecture failures with the smallest import path or transaction trace.
  * Check common causes: utility modules becoming implicit shared domains, generated code importing application internals, test-only imports reaching production, and background jobs bypassing application services.

* [ ] TODO 6: Create requirements traceability and architecture-conformance gates

  **Purpose / Why this exists**

  * Make every mandatory requirement traceable to ownership, implementation, verification, release gates, and retained evidence.
  * Prevent documentation-only compliance, orphaned requirements, untested architecture decisions, and production certification based on incomplete checklists.

  **Where this applies**

  * Requirements catalogs, ADRs, source specifications, code modules, tests, CI workflows, release gates, dossiers, risk exceptions, and certification evidence.
  * Must/Should/Could production requirements and all security, privacy, reliability, accessibility, and operational constraints.

  **Implementation requirements**

  * Treat this as T1.1.6, P1, estimated at 12 engineering hours; it depends on TODOs 2 and 5.
  * Define a machine-readable record with at least `requirement_id`, source/version, normative level, owner, component, implementation reference, test IDs, gate ID, evidence artifact, status, exception, expiry, and last verification timestamp.
  * Generate human-readable matrices from the machine source; do not maintain independent copies.
  * Add CI gates that reject duplicate IDs, missing owners, missing tests for Must requirements, absent evidence links, unauthorized architecture dependencies, expired exceptions, or release gates with untraced inputs.
  * Preserve historical requirement versions and the exact catalog hash used for each release dossier.

  **Security and safety requirements**

  * Restrict modification of requirement severity, security controls, gate mapping, and exception status to approved roles with review.
  * Store evidence references without embedding Restricted/Secret content; use object hashes and authorized locators.
  * Audit requirement creation, reclassification, waiver, owner change, evidence replacement, and gate-link modification.

  **Edge cases and outliers to handle**

  * One test covering multiple requirements, one requirement requiring several tests, conditional requirements, deprecated requirements, and requirements superseded across releases.
  * Evidence unavailable because a dependency is blocked, test IDs renamed, generated artifacts missing, or exceptions spanning multiple release trains.
  * Conflicting source documents and requirements that cannot be automated but require independent review.

  **Acceptance criteria (“done” definition)**

  * Every Must requirement maps to a named owner, component, test, release gate, and immutable evidence artifact.
  * CI blocks orphaned or internally inconsistent records and produces a deterministic traceability report.
  * Architecture conformance checks are enforced on pull requests and release builds.
  * No release dossier can mark a requirement satisfied solely through free-text assertion.

  **Testing plan**

  * Unit-test catalog schema, graph completeness, duplicate detection, expiry handling, and deterministic report generation.
  * Integration-test links to test reports, code ownership, CI gates, evidence storage, and release dossiers; run an end-to-end release-candidate trace.
  * Negative-test missing test IDs, stale evidence, invalid owners, expired exceptions, and unauthorized dependency edges.
  * Load-test catalogs larger than forecast; security-test evidence-link authorization, tamper detection, and privilege boundaries around waivers.

  **Debugging checklist**

  * Inspect requirement IDs, source hashes, test-result IDs, evidence hashes, exception expiry, ownership, and CI conformance output.
  * Traverse the graph in both directions from requirement to evidence and from evidence to release gate.
  * Check for renamed tests, stale generated reports, inconsistent branch catalogs, missing code-owner mappings, and CI jobs running against a different requirement hash.

* [x] TODO 7: Freeze outcome taxonomy, counting rules, and critical-event precedence

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

* [ ] TODO 10: Build dataset supply-chain and promotion controls

  **Purpose / Why this exists**

  * Protect benchmark integrity from poisoned, contaminated, duplicated, unlicensed, leaked, or improperly reviewed content.
  * Ensure every production benchmark release can be traced to approved sources and cannot be silently modified after certification.

  **Where this applies**

  * Source ingestion, case authoring, attachments, manifests, split assignment, validation, review, approval, deprecation, hidden-set storage, and release packaging.
  * Dataset lifecycle states `DRAFT`, `REVIEWED`, `APPROVED`, and `DEPRECATED`.

  **Implementation requirements**

  * Treat this as T2.1.4, P0, estimated at 16 engineering hours; it depends on TODOs 8 and 9.
  * Implement immutable manifests containing dataset/version IDs, case hashes, source provenance, licenses, policy/rubric links, split assignments, classifications, reviewer approvals, and signature metadata.
  * Enforce state transitions: authors may create drafts; two independent qualified reviewers must approve promotion; approved releases are immutable; deprecation creates a new signed state without deleting history.
  * Add checks for duplicate IDs, exact and near-duplicate content, source contamination, split leakage, prohibited data, missing consent/license, PII, missing policy links, unsupported language, malformed attachments, and unsigned sources.
  * Generate deterministic release bundles and promotion reports; failed checks must leave the prior approved release unchanged.

  **Security and safety requirements**

  * Separate hidden and visible datasets by identity, object-store policy, encryption scope, and export rules.
  * Require backend authorization and dual approval for promotion, split changes, hidden-set access, and deprecation.
  * Record actor, source hashes, validator versions, review decisions, manifest hash, signature, and correlation ID for every transition.

  **Edge cases and outliers to handle**

  * Same semantic case expressed with different formatting, Unicode confusables, translated duplicates, attachment-only duplicates, and sources that later change license.
  * Partial uploads, missing attachments, reviewer disagreement, an approver losing access mid-promotion, and promotion retries after timeout.
  * Contamination discovered after a release, hidden-set leakage, and a deprecated case still referenced by historical dossiers.

  **Acceptance criteria (“done” definition)**

  * Only dual-approved, signed, hash-complete manifests can enter `APPROVED`.
  * Promotion rejects every defined integrity, provenance, classification, contamination, and coverage failure with actionable diagnostics.
  * Historical approved releases remain verifiable and immutable after deprecation or replacement.
  * No production run can reference a draft, unsigned, or hash-mismatched dataset.

  **Testing plan**

  * Unit-test lifecycle transitions, manifest hashing, duplicate detection, approval rules, and provenance validation.
  * Integration-test source ingestion, object storage, registry, review, signing, and experiment validation; run end-to-end promotion and deprecation.
  * Negative-test self-approval, hidden/visible leakage, tampered manifests, license removal, missing files, and replayed approvals.
  * Load-test near-duplicate and contamination checks at projected dataset size; security-test path traversal, archive bombs, malicious metadata, and unauthorized hidden-set access.

  **Debugging checklist**

  * Inspect dataset state, manifest hash, case/object hashes, validator versions, reviewer identities, split tags, provenance links, and signature verification.
  * Re-run validators against the immutable candidate bundle using the recorded configuration.
  * Check for stale indexes, inconsistent Unicode normalization, missing object versions, reviewer-role drift, partial promotion transactions, and caches serving a superseded manifest.

* [ ] TODO 11: Curate and dual-review benchmark tranche A

  **Purpose / Why this exists**

  * Create the first production-quality benchmark tranche covering core safe-use and refusal boundaries.
  * Provide sufficient representative cases to develop, calibrate, and verify grading without rushing directly into the most hazardous content.

  **Where this applies**

  * Benign compliance, appropriate refusal, false refusal, safe useful redirection, authorization boundaries, and common ambiguous cases.
  * Case families, minimal pairs, source records, policy/rubric links, expected treatment, attachments, and reviewer records.

  **Implementation requirements**

  * Treat this as T2.1.5, P0, estimated at 16 curation hours for a tranche sized by TODO 9; it depends on TODO 10.
  * Select highest-risk core cells first while maintaining balance across benign, allowed, disallowed, and ambiguous requests.
  * For every family, create minimal pairs that vary one decision-relevant attribute, such as authorization, intent, specificity, or requested action.
  * Attach approved source provenance, case classification, policy/rubric versions, expected treatment, criticality, language, and rationale.
  * Require blind dual review; disagreements must enter explicit adjudication and remain preserved rather than being overwritten by a majority edit.

  **Security and safety requirements**

  * Minimize harmful detail and personal data; use synthetic or redacted examples where the evaluation objective permits.
  * Restrict raw high-risk content to qualified curators and reviewers; render all material inert.
  * Audit authoring, review, disagreement, adjudication, case replacement, and approval events.

  **Edge cases and outliers to handle**

  * Cases that are deceptively benign, authorization claims that cannot be verified, partial refusals, safe summaries containing operational detail, and policy ambiguities.
  * Reviewer conflict, reviewer exposure limits, unavailable language expertise, duplicate family concepts, and a policy version changing during review.
  * Cases that pass validators but produce inconsistent expected treatment across minimal pairs.

  **Acceptance criteria (“done” definition)**

  * The tranche meets the approved size and coverage plan and contains complete minimal-pair, provenance, classification, and policy metadata.
  * Every case has two independent review decisions and adjudication where required.
  * Coverage and disagreement reports identify unresolved gaps; no unresolved case is promoted.
  * The signed tranche is immutable and usable by expectation compilation and calibration tooling.

  **Testing plan**

  * Unit-test case validators, minimal-pair invariants, metadata completeness, and review-state transitions.
  * Integration-test tranche promotion, expectation compilation, grader fixtures, and coverage reporting; run end-to-end sample execution using the deterministic provider mock.
  * Negative-test missing rationale, inconsistent pairs, self-review, prohibited content, and stale policy links.
  * Load-test reviewer workflow at planned tranche volume; security-test redaction, raw-content access, active-content rendering, and hidden-set separation.

  **Debugging checklist**

  * Inspect case/family IDs, minimal-pair links, source hashes, policy/rubric versions, expected treatment, reviewer identities, disagreement state, and manifest membership.
  * Reproduce a disputed case with the exact policy and rubric versions used during review.
  * Check for duplicate concepts under different IDs, stale reviewer qualifications, incomplete attachment metadata, and promotion reports built before the final adjudication.

* [ ] TODO 12: Curate and dual-review benchmark tranche B

  **Purpose / Why this exists**

  * Add the high-severity, hostile, malformed, and rare cases needed to test safety-critical behavior and defensive system boundaries.
  * Prevent certification from being based only on clean prompts while excluding injection, authorization counterfactuals, tool-use hazards, and outlier content.

  **Where this applies**

  * Critical-harm cases, authorization counterfactuals, prompt injection, tool simulations, malformed inputs, hostile attachments, rare categories, and high-severity minimal pairs.
  * Quarantine, inert rendering, hidden-set controls, reviewer safety, and deterministic simulator fixtures.

  **Implementation requirements**

  * Treat this as T2.1.6, P0, estimated at 16 curation hours for a scope approved by TODO 9; it depends on TODO 11.
  * Select underrepresented high-severity cells and create cases that distinguish unsupported harmful requests from legitimate defensive, educational, or authorized contexts.
  * Represent tool use through deterministic simulators; do not include live credentials, reachable targets, destructive actions, or uncontrolled external dependencies.
  * Store attachment and tool-fixture hashes, media types, classifications, retention, simulator version, expected actions, prohibited actions, and reviewer exposure tier.
  * Require blind dual review and specialist adjudication for critical cases, with explicit reviewer-safety controls and maximum exposure limits.

  **Security and safety requirements**

  * Quarantine all attachments until content validation and safe derivative generation complete; no automatic execution, macro processing, network fetch, or active preview.
  * Limit raw access to qualified roles with explicit reveal actions and audit events.
  * Keep hostile fixtures non-deployable outside authorized test lanes and exclude actionable secrets or real victim data.

  **Edge cases and outliers to handle**

  * Polyglot files, nested archives, malformed encodings, oversized decompression, hidden instructions in metadata, mixed-language injection, and adversarial formatting.
  * Simulators receiving unsupported arguments, attempts to escape the simulator, conflicting authorization signals, and cases whose harmfulness depends on external facts.
  * Reviewer distress, recusal, incomplete specialist coverage, and contamination discovered after approval.

  **Acceptance criteria (“done” definition)**

  * The tranche satisfies approved high-severity and hostile-input coverage with complete provenance and classification.
  * All attachments and tools are inert, simulated, hash-addressed, and reproducible.
  * Every critical case has two qualified reviews and resolved adjudication.
  * No fixture can cause live external action, credential use, or execution in normal certification infrastructure.

  **Testing plan**

  * Unit-test hostile-case schemas, simulator manifests, attachment metadata, and critical-review routing.
  * Integration-test quarantine, safe rendering, expectation compilation, mock execution, grading, and review; run end-to-end hostile cases in isolated staging.
  * Negative-test simulator escape, active content, malformed archives, missing authorization metadata, and unauthorized raw reveal.
  * Load-test large hostile payload handling within limits; security-test injection resistance, decompression limits, SSRF prevention, and sandbox boundaries.

  **Debugging checklist**

  * Inspect fixture hash, quarantine state, scanner verdict, safe derivative, simulator version, expected/prohibited action list, review status, and audit trail.
  * Reproduce only in the isolated test lane using the stored fixture and deterministic simulator seed.
  * Check for MIME mismatch, converter fallback, missing size limits, stale simulator manifests, hidden external URLs, and reviewer-role misconfiguration.

* [ ] TODO 13: Implement deterministic expectation compilation

  **Purpose / Why this exists**

  * Compile the trusted grading expectation before any target-model response exists, preserving separation between policy and observed behavior.
  * Prevent observation leakage from turning the grader into an undocumented policy engine or allowing expected outcomes to change after seeing a response.

  **Where this applies**

  * Approved cases, policy and rubric registries, expectation compiler, experiment validation, persistence, grading, regrading, provenance, and release evidence.
  * Expectation records and compiler diagnostics generated before provider execution.

  **Implementation requirements**

  * Treat this as T2.1.7, P0, estimated at 16 engineering hours; it depends on TODOs 7, 8, and 10.
  * Define an immutable expectation record containing expectation ID, case/version, policy/version, rubric/version, compiler/version, expected treatment, allowed and prohibited behaviors, criticality, decision-rule trace, schema version, and canonical hash.
  * Canonicalize trusted inputs in a fixed order and persist the expectation before creating provider work.
  * Make compilation deterministic: identical canonical inputs must produce byte-identical records and hashes; any score-affecting change creates a new expectation version.
  * Use explicit terminal failures such as `INVALID_CASE`, `MISSING_POLICY`, `AMBIGUOUS_RULE`, and `UNSUPPORTED_VERSION`; do not silently substitute defaults.

  **Security and safety requirements**

  * The compiler must not accept target responses, grades, reviewer outcomes, or provider metadata as inputs.
  * Restrict policy/rubric publication and compiler release to approved identities; verify all source hashes.
  * Audit compiler version, input hashes, decision-rule path, output hash, actor/process identity, and failure reason without logging restricted source text.

  **Edge cases and outliers to handle**

  * Multiple matching policy rules, no matching rule, policy and rubric version mismatch, deprecated cases, unsupported language, and malformed metadata.
  * Clock or locale differences, Unicode normalization, dictionary ordering, numeric representation, and compiler retries after persistence failure.
  * A case approved under an earlier policy but executed after a policy release.

  **Acceptance criteria (“done” definition)**

  * Expectations are persisted and hash-verified before provider scheduling.
  * Golden inputs reproduce identical outputs across supported machines and repeated runs.
  * Score-affecting source or compiler changes produce new immutable records and preserve prior expectations.
  * No compiler code path reads or derives from model observations.

  **Testing plan**

  * Unit-test rule resolution, canonical serialization, deterministic hashing, explicit failure states, and version compatibility.
  * Integration-test case/policy/rubric registries, persistence, provenance, scheduler admission, and grader lookup; run end-to-end pre-execution compilation.
  * Negative-test response leakage, ambiguous rules, missing versions, tampered hashes, and default fallbacks.
  * Load-test bulk compilation at forecast experiment size; security-test untrusted metadata, parser limits, and attempts to inject observation fields.

  **Debugging checklist**

  * Inspect case, policy, rubric, and compiler versions; canonical input hash; rule trace; expectation hash; persistence transaction; and scheduler reference.
  * Reproduce from stored canonical inputs in a clean process with fixed locale and timezone.
  * Check for unordered serialization, implicit current-policy lookup, stale registry caches, timezone-dependent values, and execution paths compiling after provider output exists.

* [ ] TODO 14: Execute hostile-input tests for contracts and datasets

  **Purpose / Why this exists**

  * Prove that parsers, validators, canonicalization, dataset tooling, and expectation compilation fail safely under malformed, adversarial, and resource-intensive input.
  * Detect denominator, label, exclusion, and hashing mutations that ordinary example tests would miss.

  **Where this applies**

  * JSON, YAML, CSV, Parquet, attachments, manifests, schemas, configuration files, API payloads, event envelopes, dataset promotion, and expectation compilation.
  * Fuzz, property, mutation, golden, compatibility, and resource-limit test harnesses.

  **Implementation requirements**

  * Treat this as T2.1.8, P1, estimated at 16 quality-engineering hours; it depends on TODOs 8 and 13.
  * Build reusable fixtures for unknown fields, duplicate keys, type confusion, invalid UTF-8, confusables, deep nesting, huge scalars, oversized files, partial uploads, tampered hashes, replay, and producer/consumer version skew.
  * Add property tests for canonicalization, idempotence, round trips, manifest closure, and population invariants.
  * Add mutation tests targeting label mappings, denominator selection, exclusion rules, critical-event precedence, and hash verification; establish minimum mutation-detection thresholds.
  * Bound parser CPU, memory, recursion, file count, decompressed size, and error-message size.

  **Security and safety requirements**

  * Use only inert, non-deployable attack fixtures in isolated test environments.
  * Ensure failures redact raw restricted content, filesystem paths, secrets, and internal stack traces from user-facing errors.
  * Audit corpus provenance and restrict hostile fixtures that could create reviewer or system risk.

  **Edge cases and outliers to handle**

  * Duplicate keys interpreted differently across libraries, YAML alias expansion, Unicode normalization collisions, integer overflow, precision loss, and timestamps with ambiguous offsets.
  * Partial archives, nested compression, alternate MIME declarations, path traversal, case-colliding filenames, and interrupted uploads.
  * Fuzz-generated inputs that hang rather than fail, nondeterministic mutation results, and fixtures invalidated by a schema update.

  **Acceptance criteria (“done” definition)**

  * All parsers fail closed within documented resource limits and return stable, redacted errors.
  * Property and mutation suites demonstrate that canonicalization, labels, denominators, exclusions, and hashes cannot drift undetected.
  * Compatibility fixtures cover every supported contract version.
  * No malformed input causes process escape, uncontrolled resource use, partial promotion, or silent coercion.

  **Testing plan**

  * Unit-test each parser and invariant with targeted malformed fixtures.
  * Integration-test dataset promotion, API validation, object ingestion, event consumption, and expectation compilation under faults.
  * End-to-end test rejected and accepted hostile bundles through staging.
  * Run fuzz, load, stress, and security testing with reproducible seeds, bounded duration, parser isolation, and explicit crash/hang detection.

  **Debugging checklist**

  * Capture fixture hash, random seed, parser/library version, schema hash, resource consumption, validation path, and exact failure category.
  * Minimize failing inputs while retaining the same invariant violation.
  * Check for framework preprocessing, multiple parser implementations, default coercion, unbounded archive handling, and test timeouts masking deadlocks.

* [x] TODO 15: Create the core PostgreSQL schema and ordered migrations

  **Purpose / Why this exists**

  * Provide durable, constrained persistence for experiments, execution, grading, review, metrics, releases, provenance, and audit state.
  * Prevent invalid lifecycle transitions, duplicate logical runs, orphan evidence, and irreversible migrations that strand active workers or historical records.

  **Where this applies**

  * PostgreSQL production persistence and SQLAlchemy 2 models for projects, versions, experiments, runs, attempts, jobs, reviews, snapshots, gates, operations, outbox, and audit metadata.
  * Alembic or equivalent ordered migrations, historical fixtures, indexes, constraints, and migration verification queries.

  **Implementation requirements**

  * Treat this as T3.1.1, P0, estimated at 16 data-engineering hours; it depends on TODO 8.
  * Define typed primary keys, project ownership, immutable version references, foreign keys, check constraints, state-transition constraints, logical-run uniqueness, attempt sequencing, and timestamps with timezone.
  * Store extensible metadata only in versioned JSONB fields with schema validation; do not move core authorization, identity, state, or metric fields into untyped blobs.
  * Use expand → backfill → switch → contract migrations. Every revision must state prerequisites, lock risk, data transformation, verification queries, downgrade/roll-forward strategy, and compatible application versions.
  * Maintain one-release read compatibility and avoid destructive contraction in the same deployment that introduces a replacement.

  **Security and safety requirements**

  * Include `project_id` and classification-relevant metadata on every business table where scope cannot be inherited safely.
  * Separate migration-owner privileges from application roles; migrations must not require application credentials.
  * Audit schema changes, migration actor, revision, checksums, duration, row counts, and verification results.

  **Edge cases and outliers to handle**

  * Existing historical fixtures missing new fields, long-running transactions, concurrent workers during migration, failed backfills, and partial deployment.
  * Duplicate logical records discovered while adding constraints, invalid legacy state values, and indexes exceeding maintenance windows.
  * Rollback after new-format records have been written and schema drift between environments.

  **Acceptance criteria (“done” definition)**

  * Ordered migrations create all core tables, constraints, indexes, and relationships from an empty database.
  * Upgrade paths from every supported historical fixture pass verification and preserve immutable history.
  * Rollback or roll-forward procedures are documented and tested for each revision.
  * Invalid transitions, duplicate logical runs, missing project scope, and orphan references are rejected by the database.

  **Testing plan**

  * Unit-test ORM mappings, state validators, constraint-name stability, and migration metadata.
  * Integration-test migrations against real PostgreSQL, including upgrade, backfill, concurrent reads/writes, rollback, and re-upgrade.
  * End-to-end test application behavior across the previous/current schema compatibility window.
  * Negative-test invalid states, duplicate keys, orphan references, privilege misuse, and failed backfills; load-test migration locks and security-test application-role grants.

  **Debugging checklist**

  * Inspect migration revision, schema checksum, PostgreSQL version, active locks, long transactions, row counts, failed constraint queries, and application version.
  * Reproduce against a copy of the failing historical fixture before modifying production data.
  * Check for out-of-order revisions, environment-specific extensions, implicit casts, nullable fields contracted too early, and workers running code incompatible with the active schema.

* [x] TODO 16: Enforce project keys, row-level security, and database authorization

  **Purpose / Why this exists**

  * Make project isolation a database-enforced invariant rather than relying solely on application filters.
  * Prevent one missing predicate, reused connection, unscoped worker, or confused-deputy path from exposing restricted evidence across projects.

  **Where this applies**

  * All PostgreSQL business tables, views, materialized views, functions, application transactions, connection pools, background jobs, reports, and maintenance tasks.
  * API, scheduler, provider-executor, grader, reviewer, reporting, maintenance, and migration database roles.

  **Implementation requirements**

  * Treat this as T3.1.2, P0, estimated at 16 security-backend hours; it depends on TODOs 15 and 3.
  * Require `project_id` on every scoped row and include it in uniqueness constraints, foreign keys, indexes, and joins where appropriate.
  * Bind project scope at transaction start using a fail-closed session setting such as `SET LOCAL app.project_id`; reject scoped queries when the setting is absent.
  * Create explicit RLS policies for read, insert, update, and delete; force RLS for application roles and prohibit `BYPASSRLS`.
  * Isolate migration-owner and emergency roles, require audited elevation, and prevent them from being used by application processes.

  **Security and safety requirements**

  * Validate the caller’s project authorization before setting database context; never accept project scope solely from an untrusted request field.
  * Review `SECURITY DEFINER` functions, views, triggers, and maintenance procedures for scope bypass.
  * Audit denied access, context binding, privileged-role use, policy changes, and cross-project attempts without logging restricted row content.

  **Edge cases and outliers to handle**

  * Connection-pool reuse, nested transactions, asynchronous tasks, prepared statements, cross-project administrative reports, and background jobs processing multiple projects.
  * Null or malformed project IDs, rows created before scope enforcement, joins through unscoped reference tables, and cached query results.
  * Restore or migration scripts that accidentally run as an application role or leave project context set.

  **Acceptance criteria (“done” definition)**

  * Every scoped table and view is covered by verified RLS policies and project-aware constraints.
  * API and worker identities can access only authorized project records; missing context denies access.
  * Migration bypass is unavailable to application roles and produces a high-signal audit event when used.
  * Exhaustive role/resource/action tests find no cross-project read, write, inference, or export path.

  **Testing plan**

  * Unit-test project-context utilities and authorization-to-session binding.
  * Integration-test every role against every scoped table, function, view, queue claim, and report query.
  * End-to-end test concurrent requests for multiple projects through pooled connections and background workers.
  * Negative-test missing context, forged project IDs, cross-project joins, cache leakage, and privileged-function abuse; load-test RLS query plans and security-test timing/inference channels.

  **Debugging checklist**

  * Inspect `current_user`, role grants, `row_security`, active `app.project_id`, policy definitions, query plans, connection-pool lifecycle, and denied-access audit events.
  * Reproduce with the exact application role and transaction sequence rather than a superuser.
  * Check for context set outside a transaction, RLS disabled on a new table, views owned by bypass roles, unscoped cache keys, and maintenance jobs lacking explicit project iteration.

* [x] TODO 17: Implement immutable content-addressed object storage

  **Purpose / Why this exists**

  * Preserve prompts, responses, attachments, reports, and release evidence as verifiable immutable artifacts.
  * Prevent partial, mutable, corrupted, or misrouted objects from invalidating provenance, regrading, restoration, or certification.

  **Where this applies**

  * Production S3-compatible object storage, local development filesystem adapter, upload staging, object metadata, encryption, retention, legal hold, retrieval, and integrity verification.
  * Raw and derived artifacts referenced by PostgreSQL records and dossiers.

  **Implementation requirements**

  * Treat this as T3.1.3, P0, estimated at 16 platform hours; it depends on TODOs 3 and 15.
  * Address committed objects by SHA-256 of canonical bytes and scope keys by project and classification without exposing sensitive names.
  * Upload to a temporary location, compute and verify hash/size/media type, write immutable metadata, then create an atomic commit marker or database reference; uncommitted uploads must never become gradeable.
  * Enable versioning, server-side encryption with approved keys, retention/legal-hold controls where required, and scheduled full/hash sampling.
  * Support idempotent same-hash writes; if an existing key contains different bytes or metadata incompatible with policy, fail as an integrity incident.

  **Security and safety requirements**

  * Enforce project/classification access through workload identity and bucket/key policies; never rely on obscurity of object keys.
  * Validate MIME by content, cap upload and decompressed sizes, block traversal in filenames, and avoid serving raw content inline by default.
  * Audit put, commit, get, raw reveal, retention change, hold change, deletion, verification failure, and key usage.

  **Edge cases and outliers to handle**

  * Multipart upload interruption, eventual consistency, provider checksum differences, object version races, duplicate concurrent uploads, and object-store outage after database commit.
  * Empty files, extremely large artifacts, metadata truncation, unsupported media types, simulated hash collision, and corrupted bytes after storage.
  * Legal hold or retention preventing cleanup, restored object versions, and encryption-key rotation.

  **Acceptance criteria ("done" definition)**

  * Every committed object is content-addressed, encrypted, project/classification scoped, versioned or write-once, and verified on put and read.
  * Metadata includes hash, size, media type, source, classification, retention, legal hold, key ID, and object version.
  * Partial or corrupted objects cannot advance workflow state or appear in reports.
  * Reconciliation identifies orphan database rows, orphan objects, missing versions, and hash mismatches.

  **Testing plan**

  * Unit-test key derivation, hash calculation, metadata validation, idempotent writes, and collision handling.
  * Integration-test PostgreSQL/object-store commit coordination, KMS, versioning, retention, and reconciliation.
  * End-to-end test upload, grade reference, report generation, restore, and hash verification.
  * Negative-test partial upload, corrupted retrieval, unauthorized project access, MIME mismatch, and retention bypass; load-test multipart throughput and security-test path, metadata, and decompression attacks.

  **Debugging checklist**

  * Inspect canonical hash, computed size, object key/version, provider checksum, commit marker, KMS key ID, metadata, and database reference.
  * Verify downloaded bytes independently rather than trusting ETag as a content hash.
  * Check for incomplete multipart uploads, metadata written after state advance, wrong project prefix, versioning disabled, key-policy denial, or local-development adapter accidentally used in production.

* [x] TODO 18: Implement provenance, transactional outbox, and audit linkage

  **Purpose / Why this exists**

  * Preserve a complete, verifiable chain from source material through release decision while ensuring domain changes and emitted events cannot diverge.
  * Prevent dual-write gaps, duplicate side effects, replay confusion, and audit histories that can be modified without detection.

  **Where this applies**

  * Source → case → prompt → expectation → run → attempt → response → grade → review → metric snapshot → gate → dossier relationships.
  * PostgreSQL transactions, outbox tables, event consumers, audit records, object hashes, and external audit checkpoints.

  **Implementation requirements**

  * Treat this as T3.1.4, P0, estimated at 16 backend hours; it depends on TODOs 15 and 17.
  * Define a provenance edge model with typed source/target IDs, versions, hashes, relationship type, creation actor/process, and correlation ID.
  * Commit domain state and an outbox event in the same PostgreSQL transaction.
  * Use an event envelope containing event ID, aggregate ID, aggregate sequence, project ID, schema version, event type, occurred/recorded timestamps, payload hash, trace ID, and producer version.
  * Make consumers idempotent using event ID plus domain-specific effect keys; preserve out-of-order events until prerequisites exist or route them to governed reconciliation.
  * Link audit entries through previous-hash fields and periodically anchor signed checkpoints outside the primary database.

  **Security and safety requirements**

  * Authorize event consumption by project and process role; do not expose restricted payloads to broad event subscribers.
  * Audit privileged state changes with actor, subject, action, decision, policy version, before/after hashes, reason, trace ID, and source IP/workload identity where applicable.
  * Verify object and schema hashes before accepting provenance edges or processing replayed events.

  **Edge cases and outliers to handle**

  * Duplicate delivery, consumer restart, delayed or out-of-order events, poison events, schema version skew, and outbox backlog.
  * Clock skew between services, audit checkpoint service unavailable, event committed but not published, and consumer side effect completed before acknowledgment.
  * Deleted or cryptographically erased content referenced by historical provenance.

  **Acceptance criteria ("done" definition)**

  * Every required provenance edge resolves to a versioned record or documented deletion tombstone and validates expected hashes.
  * Domain state and outbox records are atomic; replay produces no duplicate logical effects.
  * Audit-chain and external-checkpoint verification succeeds for the full retained period.
  * Gaps, duplicate sequence numbers, missing objects, or tampered hashes block dependent grading or publication.

  **Testing plan**

  * Unit-test event envelopes, sequence rules, idempotency keys, provenance validation, and audit-hash chaining.
  * Integration-test transaction rollback, publisher retry, consumer replay, out-of-order handling, and checkpoint anchoring.
  * End-to-end test the complete provenance chain through dossier verification.
  * Negative-test tampered hashes, forged project IDs, missing prerequisites, duplicate events, and unauthorized subscribers; load-test outbox throughput and security-test audit modification.

  **Debugging checklist**

  * Inspect event ID, aggregate sequence, transaction ID, outbox status, publish attempts, consumer checkpoint, effect key, provenance edge, previous audit hash, and external checkpoint.
  * Reproduce consumers from a copied event stream with downstream side effects isolated.
  * Check for non-atomic external writes, sequence assigned outside the transaction, schema registry mismatch, consumer checkpoint committed too early, and clock-based ordering assumptions.

* [x] TODO 19: Implement lifecycle, regrade, backfill, and rollback workflows

  **Purpose / Why this exists**

  * Allow controlled evolution of graders, metrics, schemas, retention, and policies without overwriting historical truth.
  * Prevent backfill, deletion, or rollback defects from destroying reproducibility or causing mixed-version release decisions.

  **Where this applies**

  * Regrading, metric recomputation, schema/data backfills, retention, legal hold, deletion, cryptographic erasure, deprecation, rollback, and restoration.
  * PostgreSQL records, immutable objects, provenance, snapshots, reports, and dossiers.

  **Implementation requirements**

  * Treat this as T3.1.5, P1, estimated at 16 data-platform hours; it depends on TODOs 15, 17, 18, and 4.
  * Regrading must create a new grade version from existing immutable response evidence without invoking the target provider again.
  * Recalculation must create new metric snapshots and gate results; prior classifications, snapshots, reports, and dossiers remain immutable.
  * Implement resumable, bounded backfill jobs with dry-run mode, estimated row/object impact, batch checkpoints, rate limits, pause/cancel, and post-batch reconciliation.
  * Implement retention and deletion policy with legal-hold precedence, tombstones for historical references, cryptographic deletion where approved, and explicit restore behavior.
  * Rollback application code without deleting evidence written by newer versions; use forward remediation when data contraction is irreversible.

  **Security and safety requirements**

  * Require explicit authorization and, for destructive lifecycle actions, dual approval and scoped change tickets.
  * Preserve classification and project scope through every version and backfill.
  * Audit dry-run results, approvals, job parameters, checkpoints, affected IDs/hashes, failures, retries, and final reconciliation.

  **Edge cases and outliers to handle**

  * Backfill interrupted mid-batch, concurrent new writes, stale job leases, restored records past retention, legal hold applied during deletion, and missing historical artifacts.
  * Regrading with a retired rubric, a revoked grader, or schema versions unsupported by current code.
  * Rollback while old and new workers coexist and reports are being generated.

  **Acceptance criteria (“done” definition)**

  * Regrades and recomputations produce new immutable versions with complete provenance and no target-provider calls.
  * Backfills resume safely, are idempotent, and reconcile expected versus actual rows, objects, and events.
  * Retention, hold, deletion, tombstone, cryptographic-erasure, and restore precedence pass the approved policy matrix.
  * Rollback preserves all newly written evidence and cannot silently revert release decisions.

  **Testing plan**

  * Unit-test lifecycle state machines, batch checkpoints, idempotency, policy precedence, and version selection.
  * Integration-test regrade, backfill, delete, hold, restore, and rollback across PostgreSQL, object storage, outbox, and reports.
  * End-to-end test an old release regraded under a new grader while historical dossier verification remains intact.
  * Negative-test unauthorized deletion, missing artifacts, concurrent hold, duplicate backfill, and rollback version skew; load-test large backfills and security-test cross-project scope.

  **Debugging checklist**

  * Inspect lifecycle job ID, policy/version, target population hash, batch checkpoint, lease token, affected counts, object hashes, tombstones, hold flags, and reconciliation report.
  * Re-run a failed batch in dry-run mode against a restored copy.
  * Check for non-idempotent update predicates, batch boundaries changing between retries, stale policy caches, restored data bypassing retention evaluation, and reports selecting “latest” without an explicit version.

* [ ] TODO 20: Run persistence and evidence failure-injection tests

  **Purpose / Why this exists**

  * Prove that cross-store persistence, immutable evidence, provenance, and lifecycle workflows remain correct during partial failures and concurrency.
  * Detect timing windows that can lose accepted work, duplicate logical runs, or allow corrupted evidence into grading or publication.

  **Where this applies**

  * PostgreSQL, object storage, outbox publisher/consumers, audit checkpoints, lifecycle jobs, reconciliation, and application state transitions.
  * Authorized isolated staging environments and deterministic fault-injection tooling.

  **Implementation requirements**

  * Treat this as T3.1.6, P1, estimated at 16 quality-engineering hours; it depends on TODOs 16–19.
  * Build deterministic barriers and fault controls for database restart, transaction abort, network partition, object-store delay/failure, partial upload, consumer outage, duplicate delivery, stale lease, and process termination.
  * Capture before/after row, object, event, audit, and provenance counts plus hashes and state distributions.
  * Execute randomized repeated concurrency runs with recorded seeds after deterministic scenarios pass.
  * Automatically reconcile accepted logical runs, attempts, committed objects, outbox events, audit continuity, and dossiers after each scenario.

  **Security and safety requirements**

  * Run only in an isolated authorized environment with synthetic or approved redacted data.
  * Prevent fault tooling from reaching shared production infrastructure; use explicit target allowlists and abort controls.
  * Preserve test evidence and fault-controller actions in an immutable audit package.

  **Edge cases and outliers to handle**

  * Failure between object upload and database reference, between domain commit and event publish, during audit checkpoint, and during deletion or restore.
  * Concurrent same-hash uploads, simulated collision, large objects, version skew, database failover, and clock discontinuity.
  * Test harness failure, incomplete cleanup, and a fault persisting into a later scenario.

  **Acceptance criteria (“done” definition)**

  * No accepted logical run is lost or duplicated under any tested fault.
  * Corrupted, incomplete, or unverifiable evidence blocks grading and publication.
  * Reconciliation identifies and safely resolves or quarantines every induced inconsistency.
  * Each failure scenario is reproducible from stored seed, topology, versions, and fault timeline.

  **Testing plan**

  * Unit-test fault-controller safety checks and reconciliation assertions.
  * Integration-test each dependency fault independently and in paired combinations.
  * End-to-end test full run, grade, report, failure, restore, reconciliation, and dossier verification.
  * Run load/stress concurrency scenarios and security-test project isolation, audit integrity, and unauthorized fault activation.

  **Debugging checklist**

  * Inspect fault timeline, transaction IDs, object versions, state transitions, lease tokens, outbox lag, consumer checkpoints, audit hashes, and reconciliation findings.
  * Reproduce the smallest deterministic scenario before using randomized stress.
  * Check for cleanup contamination, fault injected at the wrong boundary, retries masking the first failure, inconsistent clocks, and assertions reading stale replicas or caches.

* [ ] TODO 21: Validate the workload and PostgreSQL queue envelope

  **Purpose / Why this exists**

  * Confirm that the PostgreSQL leasing design can support initial execution volume, concurrency, retention, and reporting demand.
  * Prevent queue starvation, database lock contention, cost overruns, or an emergency broker migration late in delivery.

  **Where this applies**

  * Scheduler and job tables, provider execution, grading fan-out, human-review queues, report generation, object growth, database I/O, and capacity planning.
  * Monthly and peak forecasts for runs, leases, tokens, response sizes, retries, reports, and retention.

  **Implementation requirements**

  * Treat this as T4.1.1, P0, estimated at 12 performance/architecture hours; it depends on TODO 3.
  * Build a versioned capacity model covering average and peak runs, jobs per run, lease claims per second, token throughput, response size, retry ratios, grading fan-out, review escalation, concurrent reports, and retained data growth.
  * Define representative common, burst, slow-provider, provider-outage, large-output, reviewer-backlog, and recovery profiles.
  * Benchmark PostgreSQL leasing and materialized/report queries using deterministic provider mocks.
  * Approve the PostgreSQL envelope or create an ADR with measured migration triggers for a broker/workflow engine; do not add one speculatively.

  **Security and safety requirements**

  * Model abuse-driven load, per-project quotas, cost exhaustion, oversized payloads, and intentional retry amplification.
  * Use synthetic data and mock providers for high-volume tests; bound any live-provider canary by explicit budget.
  * Restrict capacity reports containing vendor pricing or internal volume forecasts.

  **Edge cases and outliers to handle**

  * Flash bursts, provider-wide 429s, retry synchronization, long-tail response latency, dead-letter accumulation, and report workloads colliding with scheduler queries.
  * Growth beyond forecast, skewed project usage, one project monopolizing priority capacity, and vacuum/index maintenance.
  * Incomplete stakeholder forecasts and uncertain provider quotas.

  **Acceptance criteria (“done” definition)**

  * The model records approved inputs, assumptions, sensitivity ranges, and observed benchmark results.
  * PostgreSQL supports the declared initial envelope with target SLOs and at least 30% measured headroom or a replacement ADR is opened.
  * Scaling, partitioning, archival, and broker-migration triggers are numeric and monitored.
  * Cost and quota limits are included; capacity is not approved solely from average load.

  **Testing plan**

  * Unit-test capacity calculations, workload-profile generation, and threshold evaluation.
  * Integration-test scheduler/database behavior under each profile and report-query contention.
  * End-to-end test representative experiments through execution, grading, review generation, and reporting.
  * Load/stress/soak-test peak and recovery behavior; negative/security-test retry storms, oversized jobs, quota abuse, and priority starvation.

  **Debugging checklist**

  * Inspect model inputs, lease throughput, queue depth/age, database CPU/I/O, lock waits, connection saturation, index usage, object throughput, and cost counters.
  * Reproduce against a fixed workload seed and database snapshot.
  * Check for unrealistic mock latency, missing retry fan-out, report queries omitted from tests, stale statistics, connection-pool limits, and averages hiding p95/p99 behavior.

* [x] TODO 22: Implement the durable leasing scheduler and reconciliation

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

* [x] TODO 23: Implement the canonical provider-adapter contract and deterministic mock

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

* [x] TODO 24: Approve the initial provider and model scope

  **Status:** ✅ APPROVED  
  **Owner:** Wilson Eval3ngine Engineering (@unassigned)  
  **Decision Date:** 2026-07-15  
  **Evidence:** `docs/provider_scope_approval.md`

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

* [x] TODO 25: Implement production provider adapter A

  **Quality Audit Passed:**
  - Implementation: `src/wilson_eval3ngine/providers/azure_openai.py` (207 lines)
  - Protocol compliance: Implements ProviderAdapter protocol exactly
  - One-attempt semantics enforced (no hidden retries)
  - Endpoint allowlist validation (eastus2, westus3, uksouth only)
  - Model identity drift detection per `docs/provider_scope_approval.md`
  - Short-lived credential injection at runtime (Azure AD/OIDC)
  - Response size bounds (100KB max enforcement)
  - TLS validation on all endpoints
  - All 18 unit tests pass (`tests/unit/test_provider_adapters.py`)
  - Security: Credentials never stored or logged; egress restricted

  **Purpose / Why this exists**

  * Integrate the first approved provider while preserving canonical semantics, exact identity, auditable attempts, and safe failure behavior.
  * Prevent provider-specific quirks from silently changing requests, retries, costs, or release-comparison meaning.

  **Where this applies**

  * Provider A SDK/HTTP client, execution worker, canonical adapter interface, identity probes, usage/cost capture, egress policy, credentials, and telemetry.
  * All approved Provider A model/region combinations from TODO 24.

  **Implementation requirements**

  * Treat this as T4.1.5, P0, estimated at 16 integration hours; it depends on TODOs 23 and 24.
  * Map canonical requests explicitly to Provider A parameters; record every applied default or unsupported field.
  * Enforce per-attempt deadline, bounded response size, canonical normalization, one-attempt-only behavior, and scheduler-owned retry classification.
  * Persist provider request ID, reported model identity, capability/fingerprint data, finish reason, usage, latency, cost inputs, raw-response hash, and normalized error.
  * Fail closed when required identity, usage, or response-integrity metadata is missing for a release-gating run.

  **Security and safety requirements**

  * Use short-lived, Provider-A-scoped workload credentials delivered at runtime; prohibit secrets in configuration files, database payloads, artifacts, logs, and traces.
  * Allow egress only to approved Provider A endpoints and required DNS; validate TLS and redirects.
  * Treat response text and metadata as untrusted; do not execute provider-returned tool calls outside deterministic simulator authorization.

  **Edge cases and outliers to handle**

  * 429 and 5xx responses, timeout after provider acceptance, partial streaming output, malformed usage, content-filter termination, empty success, and unknown finish reason.
  * Alias/model drift, provider-side parameter clamping, regional failover, SDK retry defaults, and cost fields unavailable.
  * Cancellation after request dispatch and provider response arriving after lease expiry.

  **Acceptance criteria (“done” definition)**

  * Adapter A passes the canonical success, error, timeout, usage, identity, and malformed-response fixture suite.
  * Every provider call creates one distinct attempt with complete provenance and no hidden retries.
  * Credentials never appear in retained artifacts or telemetry; egress is restricted.
  * Missing or changed model identity marks affected comparisons pending and emits an alert.

  **Testing plan**

  * Unit-test request mapping, normalization, retryability, usage/cost calculation, redaction, and deadline handling.
  * Integration-test approved Provider A staging endpoints, scheduler, persistence, telemetry, and network policies.
  * End-to-end test representative experiments and controlled provider fault responses.
  * Negative-test invalid credentials, identity drift, malformed output, redirect, oversized response, and stale lease completion; load-test within approved quotas and security-test egress/secret leakage.

  **Debugging checklist**

  * Inspect attempt ID, canonical request hash, adapter/SDK version, endpoint/region, provider request ID, reported model ID, usage, finish reason, deadline, response hash, and normalized error.
  * Compare mapped parameters with the canonical request and Provider A’s acknowledged request metadata.
  * Check for SDK automatic retries, environment credentials overriding workload identity, alias defaults, streaming fragments omitted from hashing, and late responses committed without lease fencing.

* [x] TODO 26: Implement production provider adapter B

  **Quality Audit Passed:**
  - Implementation: `src/wilson_eval3ngine/providers/anthropic.py` (186 lines)
  - Independent implementation (no code reuse from Azure adapter)
  - Protocol compliance: Implements ProviderAdapter protocol exactly
  - One-attempt semantics enforced
  - Model scope validation (claude-3-7-sonnet, claude-3-5-sonnet only)
  - Endpoint allowlist validation (api.anthropic.com only)
  - Short-lived credentials via managed secrets injection
  - Response size bounds (100KB max)
  - TLS validation enforced
  - All 18 unit tests pass (`tests/unit/test_provider_adapters.py`)
  - Security: Credentials never stored or logged; egress restricted to approved endpoint

  **Purpose / Why this exists**

  * Integrate a second approved provider through the same canonical semantics and independent implementation path.
  * Enable meaningful cross-provider comparisons without assuming capability equivalence or copying Adapter A’s provider-specific behavior.

  **Where this applies**

  * Provider B SDK/HTTP client, canonical adapter interface, identity probes, execution workers, usage/cost capture, egress, credentials, and telemetry.
  * Approved Provider B model/region combinations from TODO 24.

  **Implementation requirements**

  * Treat this as T4.1.6, P0, estimated at 16 integration hours; it depends on TODOs 23 and 24.
  * Implement Provider B mapping independently from Adapter A while using the identical canonical conformance suite.
  * Document capability differences and expose extensions only in a versioned Provider-B namespace; unsupported canonical features must fail validation or be explicitly omitted before scheduling.
  * Record exact request intent, applied provider transformations, reported model identity, finish reason, usage, latency, cost inputs, raw hash, and normalized error.
  * Maintain one attempt per call and no implicit retries.

  **Security and safety requirements**

  * Use Provider-B-scoped short-lived credentials and an endpoint allowlist; validate TLS, redirects, and certificate trust.
  * Do not send data classes prohibited by the approved scope and do not persist secret headers or provider credentials.
  * Treat provider-returned tool/action requests as untrusted simulator inputs, never direct execution authority.

  **Edge cases and outliers to handle**

  * Provider B lacks a parameter supported by A, uses different role semantics, returns usage asynchronously, or filters content differently.
  * Alias changes, regional capacity shifts, partial streams, unknown finish reasons, malformed metadata, and SDK-side retries.
  * Cross-provider comparisons where one provider cannot preserve request intent.

  **Acceptance criteria (“done” definition)**

  * Adapter B passes the full canonical conformance and fault suite.
  * Capability differences are explicit and reflected in experiment validation and comparison eligibility.
  * Cross-provider runs preserve canonical request intent or are rejected as non-comparable.
  * Identity, credential, egress, attempt, and audit controls match Adapter A’s production requirements.

  **Testing plan**

  * Unit-test mapping, normalization, capability negotiation, error taxonomy, usage/cost capture, and redaction.
  * Integration-test Provider B staging endpoints, scheduler, persistence, telemetry, and network policy.
  * End-to-end test representative single-provider and paired-provider experiments.
  * Negative-test unsupported features, identity drift, malformed output, credential errors, and cross-provider semantic mismatch; load-test quotas and security-test secret/egress boundaries.

  **Debugging checklist**

  * Inspect canonical request hash, transformed request, endpoint, provider request ID, exact reported model, capabilities, usage, finish reason, response hash, and comparison eligibility.
  * Run differential fixtures through both adapters and compare canonical outputs, not raw provider formats.
  * Check for inherited assumptions from Adapter A, provider-specific role conversion, SDK retries, usage units interpreted incorrectly, and unsupported features silently dropped.

* [x] TODO 27: Add fingerprints, budgets, backpressure, and rate limits

  **Quality Audit Passed:**
  - Implementation: `src/wilson_eval3ngine/providers/fingerprints.py` (198 lines)
  - FingerprintRecord dataclass for drift detection
  - QuotaState with soft/hard threshold evaluation
  - BudgetController singleton with admission controls
  - Quota override mechanism with audit trail
  - Cost estimation per approved providers (Azure OpenAI + Anthropic)
  - All 18 unit tests pass (`tests/unit/test_provider_adapters.py`)
  - Security: No client-provided values become authoritative; scoped overrides audited

  **Purpose / Why this exists**

  * Bound cost and resource consumption while preserving fair, reliable capacity for certification-critical work.
  * Detect provider/model identity drift and prevent overload, retry storms, or one project from exhausting shared resources.

  **Where this applies**

  * Experiment admission, scheduler, provider adapters, project/provider quotas, token and cost accounting, elapsed-time limits, storage, review queues, and model fingerprinting.
  * Soft-limit, hard-limit, pause, block, and audited-override states.

  **Implementation requirements**

  * Treat this as T4.1.7, P1, estimated at 16 platform hours; it depends on TODOs 21, 22, 25, and 26.
  * Enforce pre-admission estimates and runtime counters for provider cost, input/output tokens, attempts, elapsed time, object storage, reviewer tasks, and report work.
  * Implement persisted quotas and token-bucket or equivalent controls; Redis may accelerate but must not be the sole authority.
  * Define soft thresholds that warn or pause at safe checkpoints and hard thresholds that deny new work; preserve reserved capacity for critical certification and incident recovery.
  * Run identity/fingerprint canaries for approved model aliases/capabilities. Changes mark comparisons pending, pause affected admission, and alert owners.
  * Make overrides scoped, time-bound, reasoned, dual-approved where material, and fully audited.

  **Security and safety requirements**

  * Authorize budget and quota changes separately from ordinary experiment creation.
  * Prevent client-provided usage or cost values from becoming authoritative; use provider records plus verified normalization.
  * Avoid telemetry labels that expose raw prompts or create unbounded attacker-controlled cardinality.

  **Edge cases and outliers to handle**

  * Concurrent attempts overspending the remaining budget, delayed usage reports, provider retries after cancellation, and currency/price changes.
  * Clock skew in rate windows, project quota changes mid-run, reserved capacity starvation, and a fingerprint change affecting only one region.
  * Storage or review backlog exceeding limits after execution already completed.

  **Acceptance criteria (“done” definition)**

  * Admission and runtime controls enforce every approved resource dimension and produce deterministic visible states.
  * Concurrent work cannot exceed hard limits beyond documented bounded in-flight exposure.
  * Critical capacity remains available under ordinary project load.
  * Provider identity or capability drift cannot silently enter a release comparison.

  **Testing plan**

  * Unit-test quota arithmetic, concurrent reservations, price/version lookup, soft/hard transitions, fairness, and fingerprint comparison.
  * Integration-test scheduler, adapters, persistence, review generation, telemetry, and override workflow.
  * End-to-end test budget warning, safe pause, increase approval, resume, and hard block.
  * Negative-test forged usage, override misuse, clock manipulation, and quota races; load/stress-test fairness and backpressure and security-test denial-of-wallet scenarios.

  **Debugging checklist**

  * Inspect quota policy/version, reservation IDs, committed and pending usage, provider price version, project priority, pause reason, fingerprint result, and override audit.
  * Recompute balances from immutable attempt and provider-usage records.
  * Check for delayed usage not reserved, different token units, unscoped cache keys, time-window calculations using local clocks, and overrides applied beyond their project or expiry.

* [ ] TODO 28: Run execution-resilience and hostile-concurrency tests

  **Purpose / Why this exists**

  * Validate scheduler, adapters, budgets, cancellation, and retry behavior under races and dependency failures.
  * Demonstrate that concurrency cannot duplicate logical runs, substitute models, exceed bounded retry budgets, or commit stale results.

  **Where this applies**

  * Scheduler, workers, provider adapters A/B, mock provider, quotas, model fingerprints, persistence, object storage, outbox, and telemetry.
  * Deterministic concurrency, randomized stress, and soak environments.

  **Implementation requirements**

  * Treat this as T4.1.8, P1, estimated at 16 quality-engineering hours; it depends on TODOs 22, 25, 26, and 27.
  * Create scenarios for common runs, bursts, concurrent lease claims, duplicate start requests, worker termination, scheduler failover, cancellation races, pause/resume, timeout, 429, 5xx, malformed/partial output, network partition, and version skew.
  * Use deterministic barriers and controllable clocks to reproduce race windows, then execute randomized stress with retained seeds.
  * Assert logical-run uniqueness, attempt separation, lease fencing, bounded retries, budget reservation, dead-letter transitions, identity consistency, and provenance closure.
  * Produce a machine-readable scenario matrix and evidence package.

  **Security and safety requirements**

  * Use deterministic mocks for destructive or high-volume tests; tightly budget and authorize any live-provider smoke tests.
  * Prevent test fault controls from reaching production or unrelated staging resources.
  * Verify project, credential, egress, and audit boundaries throughout concurrent scenarios.

  **Edge cases and outliers to handle**

  * Provider accepted a request but the client timed out, late response after cancellation, concurrent budget exhaustion, and fingerprint drift during a run.
  * Mixed worker versions, database failover while leases are active, object upload delay, and retries synchronized across many jobs.
  * Test flakiness from uncontrolled timing or cleanup from a prior run.

  **Acceptance criteria (“done” definition)**

  * No scenario creates duplicate logical runs, lost accepted work, stale completion, silent model substitution, or unbounded retry/cost.
  * Every failure reaches a documented terminal, retry, pause, or dead-letter state with audit and telemetry.
  * All race failures are reproducible from a stored seed and timeline.
  * Reconciliation returns the system to a consistent state after each scenario.

  **Testing plan**

  * Unit-test concurrency primitives, fencing assertions, retry budgets, and deterministic fault controls.
  * Integration-test scheduler/adapters/storage under each fault and race.
  * End-to-end test API-to-dossier behavior for success, failure, cancellation, and recovery.
  * Perform load, stress, and soak testing plus negative/security tests for forged leases, cross-project claims, credential leakage, and fault-controller authorization.

  **Debugging checklist**

  * Inspect scenario seed, fault timeline, logical-run and attempt IDs, lease tokens, worker versions, provider request IDs, model identity, quota reservations, and reconciliation output.
  * Reduce failures to a deterministic two-worker scenario before investigating broad stress results.
  * Check uncontrolled SDK retries, non-fenced completion, stale clocks, reused test state, transaction isolation, and assertions reading asynchronous data before convergence.

* [ ] TODO 29: Harden deterministic five-outcome grading

  **Purpose / Why this exists**

  * Provide a reliable first grading layer for all five primary outcomes while preserving uncertainty, evidence references, and reliability separation.
  * Prevent rule shortcuts from confidently misclassifying nuanced, adversarial, empty, or mixed responses.

  **Where this applies**

  * Response extraction, deterministic rules, classification records, secondary labels, abstention, reliability states, evidence references, and downstream judge/review escalation.
  * Regrading and golden fixture suites.

  **Implementation requirements**

  * Treat this as T5.1.1, P0, estimated at 16 evaluation-engineering hours; it depends on TODOs 7 and 13.
  * Implement explicit stages for response normalization, evidence extraction, deterministic rule evaluation, confidence/abstention, and explanation reason codes.
  * Emit a strict classification containing outcome, secondary labels, confidence or calibrated score where applicable, abstention flag, reliability state, expectation ID, response hash, evidence references, grader version, and rule trace hash.
  * Keep reliability terminal states separate and excluded from behavioral counts.
  * Escalate ambiguous, mixed, low-confidence, critical, or rule-conflict cases rather than forcing a default outcome.

  **Security and safety requirements**

  * Treat model output as untrusted data; never interpret it as configuration, code, authorization, or tool instruction.
  * Bound normalization and parsing resources; render explanations and evidence inert.
  * Audit grader version, input hashes, rule path, output, escalation decision, and any manual supersession.

  **Edge cases and outliers to handle**

  * Empty output, whitespace, truncated streams, encoded or multilingual content, partial refusal, harmful detail followed by refusal, and contradictory sections.
  * Provider safety message mixed with model content, malformed structure, injection strings targeting the grader, and unsupported media.
  * Reliability failure after partial observable behavior and repeated identical evidence references.

  **Acceptance criteria (“done” definition)**

  * All five outcomes, secondary labels, abstention, and reliability states have approved golden fixtures.
  * Every classification references the immutable expectation and response evidence.
  * Ambiguity and rule conflict create governed escalation, not silent defaults.
  * Reliability failures never enter behavioral numerators or satisfy release gates.

  **Testing plan**

  * Unit-test extraction, normalization, every rule branch, conflict handling, abstention, and evidence references.
  * Integration-test expectation lookup, immutable response storage, judge escalation, review routing, metrics, and regrading.
  * End-to-end test representative common, ambiguous, hostile, multilingual, and partial-response cases.
  * Negative-test prompt injection, malformed encodings, oversized output, missing evidence, and label coercion; load-test batch grading and security-test rendering and parser limits.

  **Debugging checklist**

  * Inspect expectation and response hashes, grader version, normalized representation, matched rules, conflict set, confidence, reliability state, evidence references, and escalation reason.
  * Reproduce from immutable bytes with the same grader package and locale.
  * Check for provider metadata included as model content, default outcome on exception, stale taxonomy mappings, non-deterministic normalization, and report code interpreting reliability as behavior.

* [ ] TODO 30: Build an isolated schema-only judge runner

  **Purpose / Why this exists**

  * Provide a calibrated judgment layer for cases deterministic rules cannot resolve while preventing untrusted evidence from coercing privileged actions.
  * Ensure a judge cannot access provider credentials, tools, networks, shared writable filesystems, or administrative APIs.

  **Where this applies**

  * Judge worker image, workload identity, network policy, input assembly, strict output schema, resource limits, model endpoint if approved, and grading orchestration.
  * Trusted rubrics and untrusted model evidence.

  **Implementation requirements**

  * Treat this as T5.1.2, P0, estimated at 16 ML-platform hours; it depends on TODOs 3 and 29.
  * Deploy judge workers under a distinct identity and image with read-only runtime, no shared writable filesystem, default-deny egress, no tools, and no provider-execution or signing credentials.
  * Structurally separate trusted system/rubric content from untrusted evidence; label each evidence segment and prevent it from entering instruction fields.
  * Require strict output such as outcome, secondary labels, confidence, abstention, evidence references, and reason codes; reject unknown fields.
  * Permit bounded format-repair retries using the same schema and evidence; never relax validation or add capabilities after failure.
  * Enforce input/output size, runtime, memory, and token limits.

  **Security and safety requirements**

  * The judge has no authority to execute actions, modify source evidence, approve releases, access hidden data outside its task, or reveal secrets.
  * Validate and hash all inputs; record only redacted metadata in logs.
  * Alert on denied egress, filesystem writes, tool-call attempts, malformed output bursts, or prompt-injection canaries.

  **Edge cases and outliers to handle**

  * Evidence contains fake system messages, tool schemas, encoded instructions, excessive repetition, malformed Unicode, or active markup.
  * Judge timeout, refusal, invalid JSON, context truncation, model identity drift, and schema-valid but unsupported evidence references.
  * Network policy unavailable or model endpoint requires broader egress than approved.

  **Acceptance criteria (“done” definition)**

  * Judge workers cannot reach unapproved networks, credentials, tools, or writable shared storage.
  * Trusted rubric and untrusted evidence are structurally distinct and hash-verifiable.
  * Only strict schema-valid outputs with valid evidence references can become classification candidates.
  * Isolation or identity failure blocks judging rather than falling back to a privileged process.

  **Testing plan**

  * Unit-test prompt assembly, segment labeling, output validation, evidence-reference checks, and retry limits.
  * Integration-test workload identity, network policy, read-only filesystem, resource limits, and grading orchestration.
  * End-to-end test normal, ambiguous, injection, timeout, malformed-output, and identity-drift cases.
  * Negative/security-test egress, filesystem, secret, tool, and prompt-injection attempts; load/stress-test concurrent judges and safe resource exhaustion.

  **Debugging checklist**

  * Inspect judge task ID, image digest, workload identity, network-policy verdicts, rubric/evidence hashes, model identity, token/runtime usage, validation errors, and denied actions.
  * Reproduce with the exact immutable input bundle in the same sandbox image.
  * Check for inherited environment secrets, permissive DNS/redirect rules, shared volumes, schema-repair code altering content, and evidence accidentally concatenated into trusted instructions.

* [x] TODO 31: Build the grader-calibration and hidden-set release harness

  **Purpose / Why this exists**

  * Quantify grader quality, uncertainty, subgroup behavior, and injection resistance before a grader version can influence certification.
  * Prevent overfitting to visible gold data or releasing a grader that performs poorly on critical unsafe-compliance cases.

  **Where this applies**

  * Deterministic grader, judge runner, human gold labels, visible calibration sets, hidden release sets, metric computation, grader registry, and rollback versions.
  * Macro F1, unsafe-compliance recall, subgroup metrics, expected calibration error, abstention, disagreement, injection resistance, and confidence intervals.

  **Implementation requirements**

  * Treat this as T5.1.3, P0, estimated at 16 evaluation hours; it depends on TODOs 11, 12, 29, and 30.
  * Define blinded gold ingestion with immutable label provenance, split isolation, approved evaluator roles, and no grader-development access to hidden labels.
  * Execute candidate graders over fixed datasets and store immutable calibration snapshots containing package/image digest, configuration, input-set hash, outputs, metrics, confidence intervals, and failure clusters.
  * Define release thresholds per metric and critical subgroup; insufficient support must remain indeterminate.
  * Register an approved current grader and at least one verified rollback version; document compatibility with taxonomy, expectation, and response schemas.
  * Limit repeated hidden-set evaluation and use canaries to detect leakage or tuning against hidden results.

  **Security and safety requirements**

  * Separate hidden-set storage, identities, keys, and network paths from development data.
  * Return aggregate release decisions and approved diagnostics without exposing hidden examples or labels broadly.
  * Audit hidden-set access, evaluation runs, threshold changes, grader promotion, rollback, and result export.

  **Edge cases and outliers to handle**

  * Small subgroups, zero predicted examples, label disagreement in gold data, calibration drift, repeated submissions, and hidden-set contamination.
  * Grader package changes without version bump, dependency drift, nondeterministic judge outputs, and rollback incompatible with new schemas.
  * Metrics improving globally while critical recall declines.

  **Acceptance criteria (“done” definition)**

  * The harness reproducibly reports all required quality, calibration, disagreement, abstention, injection, subgroup, and uncertainty metrics.
  * Hidden-set access is isolated and every result is tied to immutable grader and input hashes.
  * Promotion requires approved thresholds across critical metrics; aggregate improvement cannot waive critical regression.
  * A tested rollback grader is available and compatible.

  **Testing plan**

  * Unit-test metric calculations, threshold rules, confidence intervals, split enforcement, and leakage canaries.
  * Integration-test grader execution, hidden storage, registry, evidence storage, and approval workflow.
  * End-to-end test candidate submission, blinded evaluation, approval/block, promotion, and rollback.
  * Negative-test hidden-label access, replay, package tampering, unsupported schemas, and repeated-evaluation abuse; load-test batch evaluation and security-test result exfiltration.

  **Debugging checklist**

  * Inspect grader package/image digest, configuration hash, dataset/split hash, gold-label version, random seed, confusion matrix, subgroup support, calibration bins, and approval record.
  * Recompute metrics from immutable predictions and gold records with an independent implementation.
  * Check for split leakage, cached predictions from another grader, hidden examples in logs, dependency drift, and thresholds applied to point estimates without required confidence bounds.

* [x] TODO 32: Validate clustering and the independent statistical reference

  **Purpose / Why this exists**

  * Confirm the correct unit of statistical dependence and independently verify interval and comparison calculations.
  * Prevent false precision and unsafe release passes caused by treating correlated prompt variants as independent observations.

  **Where this applies**

  * Case families, minimal pairs, repeated runs, cluster hierarchy, Wilson intervals, cluster bootstrap, paired comparisons, practical thresholds, and statistical fixtures.
  * Independent Python and/or R reference implementation.

  **Implementation requirements**

  * Treat this as T5.1.4, P0, estimated at 12 statistician hours; it depends on TODOs 9 and 31.
  * Analyze within-family and between-family dependence, minimal-pair correlation, repeated-run variance, provider/model effects, and any nested structure.
  * Confirm prompt family as the bootstrap cluster or select a documented alternative hierarchy.
  * Implement an independent reference outside the production metrics module for Wilson intervals, cluster bootstrap, paired deltas, confidence intervals, and edge-case handling.
  * Define deterministic seeds, resampling method, confidence level, minimum clusters, numeric precision, and approved tolerances.

  **Security and safety requirements**

  * Use project-scoped, de-identified analysis extracts; do not copy raw Restricted content into statistical notebooks.
  * Preserve analysis code, package versions, input hashes, outputs, and approvals as release evidence.
  * Restrict changes to reference methods and tolerances to measurement/statistics approval.

  **Edge cases and outliers to handle**

  * Singleton clusters, highly unbalanced clusters, zero or all-success outcomes, missing pairs, repeated cases, and degenerate bootstrap samples.
  * Small cluster counts, nested language/category effects, ties at thresholds, floating-point differences, and changed datasets.
  * Dependence changing materially after benchmark expansion.

  **Acceptance criteria (“done” definition)**

  * An approved analysis confirms the cluster unit or selects and documents a safer alternative.
  * Independent reference outputs and production expectations match within explicit tolerances on fixed fixtures.
  * Minimum-support and degenerate-case behavior are defined and produce indeterminate results where appropriate.
  * Statistical assumptions and limitations appear in reports and certification evidence.

  **Testing plan**

  * Unit-test reference formulas, seed determinism, cluster sampling, paired alignment, and degenerate cases.
  * Integration-test production metrics against the independent implementation over frozen fixtures.
  * End-to-end test release-gate outcomes at representative and boundary datasets.
  * Negative-test broken pairing, duplicated clusters, missing data, and manipulated cluster IDs; load-test large bootstrap workloads and security-test project/data isolation.

  **Debugging checklist**

  * Inspect input-set hash, cluster assignment/version, seed, resample count, confidence level, method version, numeric environment, and intermediate counts.
  * Compare sorted canonical input arrays between implementations before comparing final statistics.
  * Check for row-level rather than cluster-level sampling, unstable ordering before seeding, missing-pair filtering differences, integer division, and tolerance hiding a conceptual mismatch.

* [x] TODO 33: Implement versioned metrics and statistical comparisons

  **Purpose / Why this exists**

  * Produce reproducible performance and safety measurements with transparent populations, uncertainty, and versioned definitions.
  * Prevent metric drift from being mistaken for model drift or reports from hiding exclusions and insufficient support.

  **Where this applies**

  * Metric registry, population queries, immutable snapshots, Wilson intervals, cluster bootstrap, paired comparisons, drift, thresholds, reports, and release gates.
  * Aggregate and slice metrics for behavioral outcomes, reliability, cost, latency, review, and critical events.

  **Implementation requirements**

  * Treat this as T5.1.5, P0, estimated at 16 measurement-engineering hours; it depends on TODOs 7 and 32.
  * Define registry-driven formulas with metric ID/version, population predicate, numerator, denominator, exclusion logic, interval method, clustering, seed policy, and units.
  * Persist immutable snapshots containing included/excluded run IDs or set hashes, counts, support, estimate, interval, method/version, seed, dataset/taxonomy/grader versions, and input-set hash.
  * Implement approved Wilson, cluster-bootstrap, paired-delta, practical-threshold, and drift methods.
  * Mark comparisons pending or invalid when dataset, taxonomy, expectation, grader, model identity, or population differs beyond approved compatibility.
  * Never recompute historical displays from mutable “latest” definitions.

  **Security and safety requirements**

  * Enforce project scope and report access; aggregates must not leak restricted small-cell content.
  * Audit metric-definition changes, snapshot creation, exclusion changes, comparison eligibility, and threshold evaluation.
  * Sign or hash-lock release-relevant snapshots and verify all referenced evidence.

  **Edge cases and outliers to handle**

  * Zero denominators, low support, all-success/all-failure, missing pairs, duplicated runs, unresolved reviews, and reliability-only populations.
  * Threshold equality, floating-point precision, changed datasets, cluster redefinition, and late-arriving review supersession.
  * Snapshot creation interrupted or repeated concurrently.

  **Acceptance criteria (“done” definition)**

  * Every metric exposes included/excluded population, numerator, denominator, support, estimate, interval, method/version, and input hash.
  * Production results match the independent reference within approved tolerances.
  * Unsupported or incompatible comparisons are visibly indeterminate or pending, never silently coerced.
  * Historical snapshots remain reproducible after metric definitions change.

  **Testing plan**

  * Unit-test formulas, population queries, exclusions, support, intervals, comparisons, deterministic seeds, and compatibility rules.
  * Integration-test grading, reviews, immutable snapshots, reports, and gates.
  * End-to-end test baseline/candidate comparisons, changed datasets, low support, and critical-event blocks.
  * Negative-test denominator mutation, duplicate inclusion, cross-project rows, stale snapshots, and threshold bypass; load-test snapshot computation and security-test small-cell leakage.

  **Debugging checklist**

  * Inspect metric/version, dataset/taxonomy/grader versions, population query hash, included/excluded counts, cluster IDs, seed, input-set hash, and comparison-eligibility reasons.
  * Recompute from immutable classifications using the reference implementation.
  * Check for mutable views, duplicated joins, missing project predicates, “latest” version selection, stale materialized views, and report-side recalculation.

* [ ] TODO 34: Validate reviewer capacity, qualification, and safety controls

  **Purpose / Why this exists**

  * Confirm that qualified humans can resolve critical, ambiguous, and disputed cases within the release cadence.
  * Prevent unresolved critical reviews, harmful content overexposure, reviewer burnout, or unqualified adjudication from becoming a hidden production bottleneck.

  **Where this applies**

  * Reviewer recruitment, qualification, language/subject expertise, workload limits, queue SLOs, escalation, wellness controls, and release blocking.
  * Critical-case, disagreement, low-confidence, sampled, and adjudication review streams.

  **Implementation requirements**

  * Treat this as T5.1.6, P0, estimated at 8 operations hours plus pilot duration; it depends on TODOs 2, 4, and 31.
  * Run a blinded pilot using representative redacted cases and measure arrival rate, handling time, disagreement, abstention, skill coverage, backlog, critical-case completion, and reviewer exposure.
  * Model normal and peak demand against planned release cadence, vacations, attrition, language coverage, and mandatory dual review.
  * Define qualification criteria, training, periodic recalibration, maximum exposure, rotation, recusal, escalation, and reviewer support.
  * Set queue SLOs and a hard rule that unresolved critical reviews block publication.

  **Security and safety requirements**

  * Grant least-privilege access by project, content class, language, and expertise; default views to redacted content.
  * Record explicit raw-content reveals and prohibit local downloads or copying unless approved.
  * Protect reviewer identity and wellness data; audit qualification, assignment, recusal, access, and adjudication.

  **Edge cases and outliers to handle**

  * Reviewer absence, surge backlog, rare language or subject matter, conflicts of interest, repeated exposure to harmful content, and simultaneous critical incidents.
  * Reviewers disagree systematically, qualification expires mid-case, or a case changes version after assignment.
  * Very low critical-case volume that makes capacity estimates uncertain.

  **Acceptance criteria (“done” definition)**

  * An approved capacity model and staffing plan meet critical and ordinary queue SLOs with documented headroom.
  * Every review category has qualified primary and backup coverage.
  * Safety, exposure, recusal, and escalation controls are operational and audited.
  * Production publication cannot proceed with unresolved critical tasks or unmet reviewer coverage.

  **Testing plan**

  * Unit-test qualification, routing, exposure, and SLO-calculation rules.
  * Integration-test identity groups, review queues, redacted/raw views, escalation, and release blocking.
  * End-to-end tabletop normal, surge, absence, and critical-review scenarios.
  * Negative-test unqualified assignment, self-review, expired qualification, and unauthorized raw access; load/stress-test queue forecasts and security-test reviewer data isolation.

  **Debugging checklist**

  * Inspect reviewer qualifications, project/content access, assignment history, exposure counters, queue age, SLA state, recusal, disagreement rate, and release-block reason.
  * Reconstruct backlog forecasts from recorded arrival and handling distributions.
  * Check stale directory groups, missing language tags, assignments created before qualification validation, hidden raw-content links, and dashboards excluding paused or critical tasks.

* [ ] TODO 35: Implement human review and adjudication workflow

  **Purpose / Why this exists**

  * Route ambiguous, critical, low-confidence, disputed, and sampled classifications to accountable human judgment.
  * Preserve independent decisions and rationale while preventing self-adjudication, hidden edits, or unresolved reviews from being treated as final.

  **Where this applies**

  * Review-task creation, assignment, redacted/raw evidence viewing, blind dual review, recusal, submission, disagreement, adjudication, supersession, SLA tracking, and audit.
  * Reviewer and adjudicator user interfaces and APIs.

  **Implementation requirements**

  * Treat this as T5.1.7, P1, estimated at 16 full-stack hours; it depends on TODOs 31, 34, and 16.
  * Create tasks from explicit rules for criticality, ambiguity, deterministic/judge disagreement, low confidence, abstention, audit sampling, and policy-required review.
  * Implement states `QUEUED`, `ASSIGNED`, `IN_REVIEW`, `SUBMITTED`, `ADJUDICATION_REQUIRED`, `RESOLVED`, `SUPERSEDED`, and `CANCELLED`, with permitted transitions and SLA timestamps.
  * Blind independent reviewers to each other’s decisions until both submit; route disagreement to an authorized adjudicator who did not author either decision.
  * Persist immutable submissions, rationale reason codes, evidence references, abstention, recusal, adjudication, and supersession links.
  * Preserve rejected alternatives and prior classifications; downstream metrics select an explicit final version.

  **Security and safety requirements**

  * Enforce project, role, qualification, and content-class authorization on assignment and every evidence request.
  * Default to redacted content; raw reveal requires explicit action, reason, and audit.
  * Protect against stored active content and prompt injection; reviewer decisions must be authorized by backend rules, not model suggestions.

  **Edge cases and outliers to handle**

  * Reviewer no-show, duplicate assignment, recusal after viewing, SLA expiry, reviewer departure, and task version changing mid-review.
  * Three-way disagreement, both reviewers abstain, adjudicator conflict, evidence deleted under policy, and a critical task reopened after release preparation.
  * Offline/browser retry causing duplicate submissions.

  **Acceptance criteria (“done” definition)**

  * All rule-triggered tasks are created exactly once and routed to qualified, independent reviewers.
  * Blind dual review and separation-of-duties constraints are enforced.
  * Every state transition and submission is immutable, versioned, and audited.
  * Unresolved critical tasks mechanically block gate evaluation and publication.

  **Testing plan**

  * Unit-test routing, state transitions, assignment independence, recusal, SLA, and final-version selection.
  * Integration-test identity, RLS, safe rendering, notification, metrics, and release gates.
  * End-to-end test agreement, disagreement, abstention, reassignment, adjudication, supersession, and critical blocking.
  * Negative-test self-review, forged task IDs, duplicate submissions, unauthorized raw reveal, and stale-version submission; load-test queue concurrency and security-test project/content isolation.

  **Debugging checklist**

  * Inspect task ID/version, trigger, project, qualification requirements, assignments, reviewer visibility, SLA, submissions, adjudicator, final classification, and audit events.
  * Reproduce using test identities for each role and the exact evidence version.
  * Check for non-unique task creation, stale assignment caches, client-side-only blindness, overwritten rationale, background workers lacking project context, and metrics reading unresolved submissions.

* [ ] TODO 36: Govern release gates, overrides, and signed dossiers

  **Purpose / Why this exists**

  * Convert immutable evidence, metrics, critical events, and reviews into an accountable release decision.
  * Prevent composites, provisional thresholds, or informal overrides from authorizing an unsafe or unsupported release.

  **Where this applies**

  * Threshold registry, gate engine, critical-event precedence, indeterminate outcomes, override workflow, release dossiers, signing, verification, and publication.
  * Raw safety, reliability, support, statistical, review, operational, and governance gates.

  **Implementation requirements**

  * Treat this as T5.1.8, P0, estimated at 16 release-engineering hours; it depends on TODOs 33, 35, and 18.
  * Version threshold sets with owner, rationale, calibration evidence, applicable population, effective period, and approval.
  * Evaluate integrity and critical raw safety gates before composites; unresolved critical reviews, failed evidence verification, or insufficient support produce `BLOCK` or `INDETERMINATE`, never `PASS`.
  * Produce a deterministic evaluation trace listing every gate input, version, result, precedence decision, and supporting artifact hash.
  * Implement overrides requiring two authorized approvers, rationale, exact scope, compensating controls, expiration, linked follow-up, and immutable audit; expiry automatically removes effect.
  * Build a signed dossier manifest containing release identity, all relevant versions/hashes, metrics, gates, reviews, exceptions, test evidence, and signing metadata.
  * Keep the foundation release explicitly non-certifying until production certification passes.

  **Security and safety requirements**

  * Separate gate-definition, override-request, approval, signing, and publication permissions.
  * Use managed signing identity and verify against an approved trust registry, not only a key embedded in the dossier.
  * Never include restricted raw content by default; reference authorized content-addressed evidence.

  **Edge cases and outliers to handle**

  * Threshold equality, conflicting gate results, stale snapshots, changed datasets, expired override at publication time, and clock skew.
  * Signature key rotated or revoked, unresolved reviews arriving after gate calculation, and dossier generation interrupted.
  * Override narrower than the failed gate, follow-up overdue, or two approvers sharing the same underlying identity.

  **Acceptance criteria (“done” definition)**

  * Gate precedence is deterministic and raw critical failures cannot be masked by composites or overrides outside approved policy.
  * Insufficient support and incompatible evidence remain indeterminate.
  * Overrides satisfy dual approval, scope, controls, expiry, and audit requirements.
  * Dossiers are reproducible, signed, independently verifiable, and fail verification on any modified artifact.

  **Testing plan**

  * Unit-test gate precedence, thresholds, indeterminate logic, override scope/expiry, manifest generation, and signature verification.
  * Integration-test metrics, reviews, provenance, KMS, audit, reports, and publication.
  * End-to-end test pass, block, indeterminate, override, expiry, revocation, and dossier verification.
  * Negative-test stale evidence, self-approval, composite bypass, revoked keys, modified manifests, and unresolved critical reviews; load-test dossier generation and security-test signing permissions.

  **Debugging checklist**

  * Inspect threshold-set version, input snapshot hashes, support, critical-event flags, review state, gate trace, override scope/expiry, dossier hash, signer key ID, and trust-registry status.
  * Re-evaluate gates from immutable inputs using the recorded engine version.
  * Check for “latest” snapshot selection, local-clock expiry, report values substituted for source snapshots, override matching too broadly, and signature verification that ignores revocation history.

* [ ] TODO 37: Run adversarial tests for grading, statistics, and release gates

  **Purpose / Why this exists**

  * Demonstrate that classifiers, judges, metrics, comparisons, reviews, and gates resist ambiguous, adversarial, correlated, and boundary inputs.
  * Detect confident grader failures, statistical-reference divergence, denominator mutation, and gate bypass before certification.

  **Where this applies**

  * Deterministic grading, judge runner, calibration, human review, metric snapshots, statistical reference, gate engine, overrides, regrading, and dossiers.
  * Hidden, property, mutation, differential, and adversarial fixture suites.

  **Implementation requirements**

  * Treat this as T5.1.9, P1, estimated at 16 quality-engineering hours; it depends on TODO 36.
  * Cover common labels, rare critical events, partial/ambiguous responses, grader disagreement, abstention, direct and indirect injection, subgroup drift, correlation, missing data, threshold boundaries, unresolved review, changed datasets, replay, and version skew.
  * Compare production metrics with the independent reference on every statistical fixture.
  * Mutation-test outcome mapping, denominator/exclusion rules, cluster assignment, critical precedence, support handling, and override scope.
  * Regrade existing immutable responses without target-provider calls and verify historical results remain unchanged.
  * Store exact fixture, seed, versions, outputs, and expected result.

  **Security and safety requirements**

  * Keep hostile prompts and attachments inert and restricted to authorized test environments.
  * Ensure graders and reviewers cannot execute embedded instructions or access privileged actions.
  * Audit test-corpus access and prevent hidden/gold fixtures from leaking into development logs or reports.

  **Edge cases and outliers to handle**

  * Schema-valid but semantically impossible judge output, encoded injection, tiny subgroups, degenerate bootstrap samples, conflicting review supersessions, and expired overrides.
  * A mutation not killed because the fixture lacks coverage, nondeterministic judge results, and reference/production library precision differences.
  * Test inputs that trigger excessive review volume or resource exhaustion.

  **Acceptance criteria (“done” definition)**

  * Required adversarial scenarios pass with approved deterministic or statistically bounded outcomes.
  * Production and independent statistical results match within approved tolerances.
  * Denominator, label, cluster, precedence, and override mutations are detected at the required threshold.
  * Unsupported or disputed cases block or remain indeterminate rather than passing silently.

  **Testing plan**

  * Unit/property/mutation-test every grading, metric, and gate invariant.
  * Integration-test judge isolation, review routing, snapshot creation, reference comparison, and dossier generation.
  * End-to-end test adversarial response through regrade, review, metrics, gate, and verification.
  * Run load/stress tests for grading and review amplification plus negative/security tests for injection, malformed evidence, cross-project data, and gate privilege misuse.

  **Debugging checklist**

  * Inspect fixture and seed, grader/judge versions, taxonomy, expectation and response hashes, review lineage, metric input set, cluster assignment, gate trace, and mutation identifier.
  * Minimize failures to one invariant and compare intermediate outputs with the reference.
  * Check for nondeterministic model calls, stale gold labels, hidden dataset leakage, mutation operators targeting dead code, and gate tests using mocked values inconsistent with real snapshots.

* [ ] TODO 38: Implement OIDC, workload identity, and role mapping

  **Purpose / Why this exists**

  * Establish strong human and machine identity for every API request, worker, privileged action, and signing operation.
  * Prevent development authentication headers, implicit trust, shared credentials, stale group membership, or identity fallback from granting production access.

  **Where this applies**

  * FastAPI authentication, OIDC provider, JWKS validation, role/group mapping, project claims, workload identities, CLI authentication, and administrative workflows.
  * API, scheduler, provider executors, graders, maintenance jobs, reporting, and signing processes.

  **Implementation requirements**

  * Treat this as T6.1.1, P0, estimated at 16 identity-engineering hours; it depends on TODOs 3 and 4.
  * Validate issuer, audience, signature, algorithm, `exp`, `nbf`, subject, token type, project claims, and required authentication assurance/MFA inheritance.
  * Fetch JWKS through approved endpoints with bounded caching and rotation behavior; unknown keys trigger controlled refresh, not signature bypass.
  * Map identity-provider groups to platform roles and permitted project scopes through a versioned policy.
  * Create separate workload identities for API, scheduler, provider adapters, judge/grader, maintenance, report/export, and signing.
  * Disable development headers and local bypass modes in staging/production at startup; fail closed on identity configuration errors.

  **Security and safety requirements**

  * Use least privilege, short-lived tokens, audience restriction, workload federation, and no shared service accounts.
  * Protect break-glass identities with just-in-time access, independent approval, strong authentication, session recording, expiry, and audit.
  * Log identity decision metadata and denial reason without storing bearer tokens.

  **Edge cases and outliers to handle**

  * JWKS rotation, IdP outage, token clock skew, revoked or disabled users, group membership changes, multiple issuers, and service-token replay.
  * Token valid cryptographically but missing project authorization, user belonging to conflicting groups, or workload token presented to a human endpoint.
  * Cached keys or role mappings surviving beyond approved freshness.

  **Acceptance criteria (“done” definition)**

  * Production rejects development authentication and validates all required token properties.
  * Every process uses a distinct least-privilege identity with documented permissions.
  * Project scope and role are derived from trusted identity/policy, not untrusted request fields.
  * IdP or policy failure denies privileged access and emits actionable telemetry.

  **Testing plan**

  * Unit-test JWT validation, claim normalization, role mapping, token-type separation, and cache expiry.
  * Integration-test the approved IdP, workload federation, API, database context, object policies, and KMS.
  * End-to-end test login, CLI authentication, worker startup, role-protected actions, group change, and break-glass workflow.
  * Negative-test invalid signatures, wrong audience, expiry, replay, missing MFA/project claims, and dev headers; load-test JWKS/cache behavior and security-test role escalation.

  **Debugging checklist**

  * Inspect issuer, audience, subject, token type, key ID, claim times, group/project claims, policy version, mapped role, workload identity, and authorization trace.
  * Reproduce with sanitized token claims and the exact JWKS/policy version.
  * Check clock synchronization, stale JWKS, proxy rewriting issuer URLs, environment flags enabling development auth, group-sync delay, and application roles broader than intended.

* [ ] TODO 39: Enforce end-to-end project and export isolation

  **Purpose / Why this exists**

  * Ensure project boundaries remain intact through every storage, execution, query, cache, reporting, and export surface.
  * Prevent a correctly scoped API from being undermined by an unscoped worker, cache key, object reference, search query, or export process.

  **Where this applies**

  * API authorization, PostgreSQL RLS, object-store policies, queue jobs, caches, search/indexing, reports, materialized views, exports, hidden sets, telemetry, and background workers.
  * Every human and workload role.

  **Implementation requirements**

  * Treat this as T6.1.2, P0, estimated at 16 security-backend hours; it depends on TODOs 16, 17, and 38.
  * Build a role × resource × action matrix for projects, experiments, runs, attempts, evidence, reviews, metrics, reports, exports, datasets, hidden sets, and administrative operations.
  * Bind trusted project context at request admission, database transaction, job creation, lease claim, object operation, cache key, report query, export manifest, and audit event.
  * Require separate authorization for exports and raw evidence; validate scope again in background workers rather than trusting the initiating request.
  * Add automated negative tests for every matrix denial and confused-deputy path.

  **Security and safety requirements**

  * Deny cross-project deduplication or hash lookup when it could reveal existence of restricted content.
  * Partition or scope caches, temporary files, signed URLs, search indexes, report artifacts, and telemetry dimensions.
  * Audit denied and successful high-risk access, raw reveal, export, hidden-set operation, and administrative cross-project action.

  **Edge cases and outliers to handle**

  * Misrouted job, reused cache entry, copied object locator, signed URL forwarded to another user, report generated after access revocation, and export retry under a different worker.
  * Global administrator or support workflow, cross-project aggregate approved by policy, and migration/reconciliation jobs spanning projects.
  * Project deletion, project merge requests, and duplicate content existing in several projects.

  **Acceptance criteria (“done” definition)**

  * Every independent boundary enforces project scope and passes the negative role/action matrix.
  * Background workers cannot act as confused deputies for unauthorized users.
  * Export and raw-evidence actions require explicit authorization and produce scoped, expiring artifacts.
  * No list, count, timing, cache, or error response reveals unauthorized project data.

  **Testing plan**

  * Unit-test scope propagation, cache-key construction, signed-locator claims, and role matrix evaluation.
  * Integration-test API, RLS, storage, queues, search, caches, reports, exports, and telemetry.
  * End-to-end test concurrent multi-project workflows including access revocation during long operations.
  * Negative/security-test every cross-project path, identifier guessing, signed URL reuse, and timing inference; load-test isolation under mixed-project concurrency.

  **Debugging checklist**

  * Trace project ID and authorization decision through request, transaction, job, lease, object, cache, report/export, and audit records.
  * Reproduce with least-privilege identities from both source and target projects.
  * Check missing scope in cache keys, global service roles, background jobs accepting caller-supplied project IDs, pre-signed URLs lacking audience/scope, and materialized views built without RLS-safe filters.

* [ ] TODO 40: Implement managed secrets, keys, signatures, and audit checkpoints

  **Purpose / Why this exists**

  * Protect provider credentials, encryption keys, signing authority, and audit integrity throughout their lifecycle.
  * Prevent secret leakage, forged dossiers, unverifiable historical signatures, or a compromised key from remaining trusted indefinitely.

  **Where this applies**

  * Managed secrets service, KMS/HSM, workload identity, provider credentials, object encryption, dossier signing, public-key trust registry, audit checkpoints, rotation, revocation, and recovery.
  * CI/CD and operational break-glass workflows.

  **Implementation requirements**

  * Treat this as T6.1.3, P0, estimated at 16 security-engineering hours; it depends on TODOs 3, 18, and 38.
  * Define a key hierarchy and inventory with purpose, owner, algorithm, key ID, environment, project/classification scope, creation, rotation, expiry, revocation, and recovery procedure.
  * Deliver secrets at runtime through workload identity; use short-lived/provider-scoped credentials where available.
  * Sign dossiers and audit checkpoints through managed KMS identities; record algorithm, key ID/version, signing time, manifest hash, and certificate/trust-chain metadata.
  * Maintain an independently governed public-key registry with activation, rotation, revocation, and historical verification semantics.
  * Implement rotation and compromise runbooks, canary detection, and verification of historical signatures against validity at signing time.

  **Security and safety requirements**

  * Secrets must not appear in source, configuration, database payloads, objects, logs, traces, reports, crash dumps, or test fixtures.
  * Separate key administration, signing use, verification, and release approval roles.
  * Audit secret access, key use, policy change, rotation, revocation, failed verification, and break-glass recovery.

  **Edge cases and outliers to handle**

  * Rotation during an active job, KMS outage, expired secret lease, revoked key with valid historical signatures, and restore into an isolated environment.
  * Provider credential cannot be short-lived, public-key registry unavailable, or key policy changed independently of application deployment.
  * Backup contains encrypted data but the corresponding key is missing or retired.

  **Acceptance criteria (“done” definition)**

  * All production secrets and keys are managed, scoped, rotatable, inventoried, and absent from retained content.
  * Dossiers and audit checkpoints verify through the approved trust registry and fail on modification or untrusted key status.
  * Rotation, revocation, and compromise drills preserve service safety and historical verification.
  * No application identity can administer the keys it uses.

  **Testing plan**

  * Unit-test secret references, key selection, signature formats, trust-registry rules, rotation, and revocation semantics.
  * Integration-test workload identity, secrets service, KMS signing, object encryption, audit checkpointing, and dossier verification.
  * End-to-end test normal signing, rotation, revoked current key, historical verification, and recovery.
  * Negative-test secret leakage, unauthorized key use, altered manifests, unknown keys, and registry rollback; load-test KMS throughput and security-test privilege separation.

  **Debugging checklist**

  * Inspect workload identity, secret lease/reference, KMS key/version, key policy, signature algorithm, manifest hash, trust-registry version, revocation state, and audit event.
  * Verify signatures independently using the recorded canonical bytes.
  * Check environment-secret fallback, overly broad KMS grants, key alias pointing to the wrong version, registry cache staleness, line-ending/canonicalization differences, and backups lacking key-recovery evidence.

* [ ] TODO 41: Enforce egress controls, sandboxes, and deterministic tool simulators

  **Purpose / Why this exists**

  * Prevent model or grader content from causing live external actions, arbitrary network access, command execution, or data exfiltration.
  * Keep certification reproducible by using deterministic simulators rather than real operational tools.

  **Where this applies**

  * Provider executors, judge workers, tool-use evaluation, simulator runtime, network policies, DNS, metadata-service access, filesystem, process limits, and authorized-lab lanes.
  * Tool definitions, arguments, expected actions, and action logs.

  **Implementation requirements**

  * Treat this as T6.1.4, P0, estimated at 16 platform-security hours; it depends on TODOs 3, 25, 26, and 30.
  * Apply per-process identities and default-deny network policies. Provider executors may reach only approved endpoints; graders have no default egress.
  * Build deterministic simulators with versioned manifests defining tool name, schema, allowed arguments, state model, seed, outputs, side effects, and resource bounds.
  * Validate tool definitions and arguments against strict schemas; reject unknown tools, shell fragments, arbitrary URLs, path traversal, and excessive resource requests.
  * Permit real tools only in a separately authorized lab lane with explicit approval, target allowlists, bounded resources, enhanced audit, and no production certification claims.
  * Record every simulated or lab tool request, authorization result, normalized arguments, simulator version, output hash, and correlation ID.

  **Security and safety requirements**

  * Block cloud metadata endpoints, loopback/private ranges where not required, DNS rebinding, redirects to unapproved hosts, raw sockets, shell access, and writable shared filesystems.
  * Never let model output grant or expand tool permissions.
  * Use sandbox runtime limits for CPU, memory, process count, file size, duration, and network bytes.

  **Edge cases and outliers to handle**

  * IPv6 and alternate IP notation, redirects, DNS changes after validation, compressed arguments, command-like filenames, and encoded URLs.
  * Simulator version skew, state shared across projects, partial simulator failure, and attempts to invoke unregistered extension fields.
  * Network policy unavailable or a provider SDK attempting telemetry to an unapproved domain.

  **Acceptance criteria (“done” definition)**

  * Certification tool use is deterministic, simulated, versioned, and free of live external side effects.
  * Provider and grader egress matches approved allowlists and fails closed.
  * Real-tool lanes are isolated, separately authorized, and cannot produce ordinary certification evidence.
  * All tool actions are bounded, attributable, and auditable.

  **Testing plan**

  * Unit-test tool schemas, argument normalization, simulator determinism, policy matching, and resource limits.
  * Integration-test workload identity, network policy, DNS/redirect handling, sandbox runtime, and action logging.
  * End-to-end test approved simulator flows and blocked external-action attempts.
  * Negative/security-test SSRF, DNS rebinding, command injection, path traversal, metadata access, and simulator escape; load/stress-test sandbox exhaustion.

  **Debugging checklist**

  * Inspect process identity, network-policy decision, resolved IPs, redirect chain, simulator manifest/version, normalized arguments, seed, resource usage, output hash, and action audit.
  * Reproduce in the same sandbox image with networking disabled where possible.
  * Check broad DNS allowances, SDK telemetry endpoints, IPv6 omissions, shell invocation in wrappers, simulator state not project-scoped, and fallback to real tools after simulation failure.

* [ ] TODO 42: Build inert rendering and attachment quarantine

  **Purpose / Why this exists**

  * Protect reviewers, analysts, browsers, and report consumers from active or malformed content in prompts, outputs, attachments, and exports.
  * Prevent stored XSS, remote fetches, parser exploitation, decompression bombs, and unsafe raw previews.

  **Where this applies**

  * Markdown, HTML, SVG, URLs, notifications, reports, previews, PDF/image/text attachments, upload APIs, quarantine storage, scanners, converters, and raw-evidence access.
  * Reviewer, analyst, executive, and export interfaces.

  **Implementation requirements**

  * Treat this as T6.1.5, P1, estimated at 16 application-security hours; it depends on TODOs 17 and 39.
  * Implement quarantine states `UPLOADED`, `QUARANTINED`, `SCANNING`, `SAFE_DERIVATIVE_READY`, `REJECTED`, and `RAW_RESTRICTED`, with immutable source hashes and transition audit.
  * Detect media type by content, validate file structure, enforce file/decompressed size, nesting, page/frame, and processing-time limits, and run approved malware/content scanners.
  * Generate safe derivatives in isolated converters with no network and bounded resources; preserve provenance from raw object to derivative.
  * Render text/Markdown through allowlist sanitization; disallow active HTML, scripts, event handlers, embedded objects, remote resources, and unsafe URI schemes.
  * Apply strict CSP, safe `Content-Disposition`, no remote fetch, and explicit audited raw reveal.

  **Security and safety requirements**

  * Raw attachments remain access-controlled and are never rendered inline by default.
  * Treat scanner or converter failure as quarantine, not approval.
  * Redact sensitive metadata and filenames in broad interfaces while retaining immutable originals for authorized evidence.

  **Edge cases and outliers to handle**

  * Polyglots, nested archives, password-protected files, malformed PDFs/images, SVG scripts, Unicode filenames, MIME mismatch, and decompression bombs.
  * Scanner timeout, conflicting scanner verdicts, converter crash, safe derivative missing content, and raw object under legal hold.
  * Links using redirects, data URIs, filesystem paths, or obfuscated schemes.

  **Acceptance criteria (“done” definition)**

  * User-controlled content renders inert under a strict CSP with no remote requests or script execution.
  * Attachments cannot leave quarantine without required validations and a provenance-linked safe derivative or explicit restricted status.
  * Raw reveals require authorization, reason, and audit.
  * Oversized, malformed, active, or unscannable content fails safely without exposing operators.

  **Testing plan**

  * Unit-test sanitizer policies, MIME detection, quarantine transitions, limits, and URI handling.
  * Integration-test object storage, scanners, converters, browser viewer, RLS, reports, and audit.
  * End-to-end test benign, active, malformed, oversized, and password-protected attachments.
  * Negative/security-test stored XSS, SVG/HTML execution, remote fetch, polyglots, archive bombs, and parser crashes; load-test concurrent scanning/conversion.

  **Debugging checklist**

  * Inspect raw/derivative hashes, detected and declared MIME, size/decompression counters, scanner signatures/verdicts, converter image/version, quarantine state, CSP reports, and raw-reveal audit.
  * Reproduce converters in an isolated sandbox with the exact object version.
  * Check for preview fallbacks to raw content, scanner success cached across a changed object, remote font/image fetches, permissive URL schemes, and converter temp files shared across projects.

* [ ] TODO 43: Add software-supply-chain controls and SBOM provenance

  **Purpose / Why this exists**

  * Reduce risk from vulnerable, malicious, unlicensed, or untraceable dependencies, build images, and infrastructure modules.
  * Ensure every release can prove what source, dependencies, tools, and build process produced its artifacts.

  **Where this applies**

  * Python dependencies, transitive packages, base images, operating-system packages, GitHub Actions or CI plugins, Terraform/Kubernetes modules, containers, source code, secrets, licenses, and release artifacts.
  * Pull requests, scheduled scans, release builds, exception workflow, SBOMs, signatures, and provenance attestations.

  **Implementation requirements**

  * Treat this as T6.1.6, P1, estimated at 16 DevSecOps hours; it depends on TODOs 3 and 40.
  * Inventory and pin direct/transitive dependencies and build tools; use lockfiles and digest-pinned base images/actions.
  * Add dependency, secret, license, SAST, container, and IaC scans to pull requests and release workflows.
  * Define risk-based blocking thresholds using severity, exploitability, reachability, available fix, and asset exposure; exceptions require owner, rationale, compensating controls, expiry, and follow-up.
  * Generate reproducible SBOMs, signed images, source/build provenance, lockfile hashes, and scanner summaries for every release.
  * Periodically rescan released artifacts for newly disclosed vulnerabilities.

  **Security and safety requirements**

  * Use federated CI identities rather than long-lived cloud credentials; isolate untrusted pull-request execution.
  * Restrict who can alter workflows, scanner policy, dependency exceptions, signing configuration, and release tags.
  * Verify fetched dependencies and artifacts against approved registries, hashes, and signatures where available.

  **Edge cases and outliers to handle**

  * Transitive vulnerabilities, typosquatting, dependency confusion, abandoned packages, scanner outage, false positives, and findings without fixes.
  * Base-image updates changing reproducibility, generated dependencies, optional extras, and platform-specific packages.
  * Exception expiring during a release or a vulnerability disclosed after certification.

  **Acceptance criteria (“done” definition)**

  * CI scans all required supply-chain surfaces and blocks according to approved policy.
  * Every release publishes a verifiable SBOM, image digest/signature, build provenance, and dependency-lock evidence.
  * Exceptions are scoped, expiring, owned, and visible in certification.
  * Released artifacts can be mapped quickly to affected components after a new vulnerability disclosure.

  **Testing plan**

  * Unit-test policy evaluation, exception expiry, SBOM normalization, and provenance verification.
  * Integration-test source control, CI runners, scanners, registries, signing, and release evidence.
  * End-to-end test clean release, blocked vulnerable release, approved temporary exception, and post-release rescan.
  * Negative/security-test workflow tampering, malicious dependency, secret inclusion, unsigned image, and cache poisoning; load-test large dependency graphs and scanner concurrency.

  **Debugging checklist**

  * Inspect source commit, lockfile/SBOM hashes, scanner database version, finding IDs, reachability, exception state, image digest, signature, builder identity, and provenance attestation.
  * Reproduce the build in a clean isolated runner with caches disabled.
  * Check stale scanner feeds, unpinned actions/images, dependencies installed outside lockfiles, exceptions matched too broadly, and CI paths that publish before security gates complete.

* [ ] TODO 44: Run the adversarial security and permission matrix

  **Purpose / Why this exists**

  * Validate the complete security model against realistic abuse chains and every role/resource/action denial.
  * Ensure privileged actions remain backend-authorized and audited regardless of model output, UI behavior, or indirect content.

  **Where this applies**

  * Identity, API, database, storage, queues, provider executors, graders, tool simulators, rendering, attachments, exports, signing, audit, CI/CD, and supply chain.
  * Human and workload roles across all project and content classifications.

  **Implementation requirements**

  * Treat this as T6.1.7, P1, estimated at 16 security-test hours; it depends on TODOs 39–43.
  * Build a safe, non-destructive test matrix covering direct/indirect prompt injection, excessive agency, stored XSS, SSRF, SQL/command/XXE injection, duplicate JSON keys, race conditions, auth bypass, token faults, cross-project access, secret leakage, attachment execution, egress, signature/audit compromise, and supply-chain tampering.
  * Execute every role × resource × action denial and selected chained scenarios crossing application boundaries.
  * Use deterministic fixtures and isolated staging; record exact versions, identities, payload hashes, expected control, observed result, and evidence.
  * Convert every confirmed issue into a tracked defect with severity, owner, containment, remediation, regression test, and certification impact.

  **Security and safety requirements**

  * Do not use live victims, production data, destructive payloads, uncontrolled external callbacks, or shared environments.
  * Require written authorization, target allowlist, abort criteria, evidence handling, and cleanup plan.
  * Verify that models, graders, and front ends cannot grant authorization or suppress audit.

  **Edge cases and outliers to handle**

  * Multi-step chains that are harmless individually, races between authorization and use, revoked access during long operations, and hidden content retrieved asynchronously.
  * Browser, API, worker, and database interpreting the same input differently.
  * Scanner/test-tool false positives, nondeterministic timing, and a security control failing only under load.

  **Acceptance criteria (“done” definition)**

  * The permission matrix has evidence for every required allow and deny case.
  * No privileged operation succeeds without backend authorization and complete audit.
  * All critical/high findings are remediated and regression-tested; unresolved findings block certification.
  * Test execution causes no uncontrolled external action, data loss, or cross-project exposure.

  **Testing plan**

  * Unit-test security policy functions and known regression cases.
  * Integration-test each trust boundary and chained abuse path.
  * End-to-end test authorized versus unauthorized user and workload workflows through UI, API, workers, storage, and audit.
  * Run negative, load/stress, and security tests for race, parser, rendering, identity, egress, supply-chain, and exfiltration conditions.

  **Debugging checklist**

  * Inspect actor/workload identity, claims, policy version, project scope, request/trace ID, database role/context, object policy, network verdict, audit event, and security-test fixture hash.
  * Reproduce one boundary at a time before rebuilding a chain.
  * Check inconsistent parser behavior, front-end-only validation, broad service roles, stale authorization caches, missing audit on denied actions, and test tools accidentally using administrator credentials.

* [ ] TODO 45: Implement versioned REST command and query APIs

  **Purpose / Why this exists**

  * Expose stable, authorized, retry-safe workflows for validation, execution, lifecycle, comparison, export, and evidence retrieval.
  * Prevent ambiguous mutations, duplicate operations, stale updates, unsafe errors, or restricted content leaking through list endpoints.

  **Where this applies**

  * FastAPI `/v1` endpoints, OpenAPI, authentication/authorization, command/query application services, operation resources, pagination, idempotency, ETags, errors, and audit.
  * Validate, start, pause, resume, cancel, regrade, compare, export, evidence, schema, status, and verification workflows.

  **Implementation requirements**

  * Treat this as T7.1.1, P0, estimated at 16 backend hours; it depends on TODOs 8, 16, 22, and 38.
  * Separate commands from queries. Long-running commands return an operation resource with operation ID, state, timestamps, target reference, trace ID, and failure code.
  * Require idempotency keys for retriable mutations; persist request hash, caller/project, result, and expiry. Reuse with different payload must fail.
  * Use ETags or equivalent version preconditions for state-changing operations and cursor pagination with stable ordering for collections.
  * Return versioned safe errors containing code, message, trace ID, schema version, and retryability without stack traces or restricted details.
  * Include project context and schema version in responses; list endpoints return metadata summaries, never restricted raw evidence.

  **Security and safety requirements**

  * Perform backend authorization on every command/query and reauthorize asynchronous work.
  * Validate duplicate keys, unknown fields, content type, body size, cursor integrity, and identifier format before domain logic.
  * Audit mutations, evidence access, export initiation, authorization denial, idempotency replay, and concurrency conflict.

  **Edge cases and outliers to handle**

  * Duplicate requests, lost client response, stale ETag, operation timeout, cancellation race, pagination while data changes, and expired cursor.
  * Partial dependency outage, unsupported schema version, access revoked after operation creation, and result artifact deleted under policy.
  * Large filter sets, malformed JSON, ambiguous timestamps, and retry after idempotency expiry.

  **Acceptance criteria (“done” definition)**

  * All required `/v1` workflows have strict generated OpenAPI contracts and stable error codes.
  * Idempotent retries never duplicate logical mutations; stale updates are rejected.
  * Every response includes trace and version context, and restricted evidence is absent from broad listings.
  * Asynchronous operation states accurately reflect domain completion and failure.

  **Testing plan**

  * Unit-test request validation, idempotency, ETags, cursors, operation states, and error mapping.
  * Integration-test identity, RLS, scheduler, lifecycle, reports, exports, evidence storage, and audit.
  * End-to-end test each workflow, retries, cancellation, polling, and access revocation.
  * Negative-test duplicate keys, forged cursors, stale ETags, oversized payloads, unauthorized IDs, and replay; load-test pagination/commands and security-test injection and data leakage.

  **Debugging checklist**

  * Inspect request/trace ID, caller/project, route/version, schema hash, idempotency record, payload hash, ETag, operation state, domain event, and audit record.
  * Replay the exact request against an isolated environment using the same identity and version precondition.
  * Check proxy/body transformations, idempotency storage transactionality, cursor encoding, inconsistent authorization between sync and async paths, and framework defaults exposing validation internals.

* [ ] TODO 46: Complete CLI workflows and stable exit codes

  **Purpose / Why this exists**

  * Provide reliable operator and automation access equivalent to the REST API.
  * Prevent scripts from misinterpreting warning, block, indeterminate, validation, or platform-failure outcomes.

  **Where this applies**

  * Typer CLI commands for validate, plan/estimate, run/start, status, pause, resume, cancel, regrade, compare, export, schema, and dossier verification.
  * Human-readable output, machine-readable JSON, authentication, configuration, timeouts, and exit codes.

  **Implementation requirements**

  * Treat this as T7.1.2, P0, estimated at 16 developer-tools hours; it depends on TODO 45.
  * Build CLI commands from shared application and contract models rather than duplicating domain logic.
  * Preserve exit codes: `0` pass/success, `10` warning, `20` block, `30` indeterminate, `40` validation error, and `50` platform failure.
  * Support explicit project, endpoint, profile, output format, timeout, and trace options; secrets must come from approved credential mechanisms.
  * Emit stable machine-readable JSON on request and concise human output otherwise; send diagnostics to stderr and primary output to stdout.
  * Handle signals and cancellation safely and print operation/trace IDs for asynchronous work.

  **Security and safety requirements**

  * Do not accept credentials on command lines where process listings can expose them.
  * Validate local file paths, symlinks, output permissions, and overwrite behavior.
  * Redact secrets and restricted content from errors, shell-completion data, and command history guidance.

  **Edge cases and outliers to handle**

  * Non-interactive CI, no TTY, broken pipe, interrupted download, network timeout, expired authentication, and operation continuing after client exit.
  * Partial output file, existing destination, invalid locale/terminal encoding, and server/CLI version skew.
  * Warning plus block conditions and API errors without a known CLI mapping.

  **Acceptance criteria (“done” definition)**

  * All required workflows are available and behaviorally equivalent to REST.
  * Exit codes are stable, documented, and covered by compatibility tests.
  * Machine output validates against published schemas and contains trace/operation IDs.
  * No secret or restricted content is emitted unintentionally or stored in insecure output files.

  **Testing plan**

  * Unit-test command parsing, exit-code mapping, output formatting, path safety, and signal handling.
  * Integration-test CLI against the real API, authentication, file upload/download, and dossier verification.
  * End-to-end test each workflow in interactive and CI modes.
  * Negative-test malformed configs, stale credentials, server skew, partial files, and unsafe paths; load-test status polling and security-test credential/redaction behavior.

  **Debugging checklist**

  * Inspect CLI version, server version, active profile/project, request/trace ID, operation ID, HTTP status, domain error code, exit code, stdout/stderr separation, and output-file hash.
  * Reproduce with `--output json` and the same sanitized configuration.
  * Check shell aliases, environment variables overriding flags, stdout consumed by a pipe, client-side retry duplicating commands, and unmapped server errors defaulting to success.

* [ ] TODO 47: Build reproducible reports and governed exports

  **Purpose / Why this exists**

  * Produce deterministic, verifiable reports and export artifacts that disclose populations, exclusions, staleness, cost, latency, review, and gate status.
  * Prevent polished summaries from hiding unsupported slices, stale snapshots, or restricted raw evidence.

  **Where this applies**

  * Canonical report model, JSON, safe HTML, CSV, Parquet, export operations, report manifests, object storage, snapshots, lineage, and verification.
  * Aggregate, slice, drill-down, exclusion, cost, latency, review, critical-event, and gate data.

  **Implementation requirements**

  * Treat this as T7.1.3, P1, estimated at 16 reporting hours; it depends on TODOs 18 and 36.
  * Build one canonical report model from immutable metric, review, gate, and provenance records; serializers must not independently recalculate results.
  * Use deterministic ordering, normalized timestamps/numbers, explicit schema versions, and artifact hashes.
  * Include dataset, taxonomy, expectation, provider/model, grader, metric, threshold, report, and dossier versions/hashes plus generated-at and source-snapshot times.
  * Implement export states `REQUESTED`, `AUTHORIZED`, `BUILDING`, `READY`, `FAILED`, and `EXPIRED`; reauthorize before build and retrieval.
  * Exclude restricted raw content by default; authorized drill-down exports reference or include only explicitly approved evidence.

  **Security and safety requirements**

  * Prevent CSV/spreadsheet formula injection, active HTML, remote resources, unsafe filenames, and unrestricted signed URLs.
  * Apply project/classification policy and small-cell protections to reports and exports.
  * Audit export request, authorization, content scope, artifact hash, retrieval, expiry, and deletion.

  **Edge cases and outliers to handle**

  * Snapshot invalidated during build, large exports, access revoked while building, partial serializer failure, and object upload failure.
  * CSV quoting/encoding, Parquet schema evolution, timezone/locale differences, and HTML viewer script restrictions.
  * Report requested for changed datasets, unresolved reviews, missing artifacts, or unverifiable hashes.

  **Acceptance criteria (“done” definition)**

  * JSON, safe HTML, CSV, and Parquet reconcile to the same canonical report and immutable inputs.
  * Reports visibly show support, exclusions, staleness, versions, hashes, and gate status.
  * Restricted raw content is absent unless separately authorized and audited.
  * Artifact modification, stale source, or failed integrity verification invalidates the report/export.

  **Testing plan**

  * Unit-test canonical model, deterministic sorting, serializers, formula neutralization, and manifest hashing.
  * Integration-test snapshots, review/gate data, object storage, authorization, and expiration.
  * End-to-end test report generation, verification, authorized retrieval, and expired access.
  * Negative-test active content, cross-project export, stale sources, partial build, and malformed data; load-test large exports and security-test content-disposition and signed-locator scope.

  **Debugging checklist**

  * Inspect report/export ID, project, authorization decision, source snapshot hashes, report schema/version, generated time, serializer version, object hash/version, and expiry.
  * Regenerate from the same canonical model and compare bytes and hashes.
  * Check report-side recalculation, nondeterministic ordering, locale-sensitive formatting, stale materialized views, formula-like cells, and retrieval authorization differing from build authorization.

* [ ] TODO 48: Deliver safe analyst, executive, and reviewer workflows

  **Purpose / Why this exists**

  * Provide task-appropriate interfaces without exposing more evidence than each role needs.
  * Ensure executives see decision-ready aggregates, analysts can trace lineage, and reviewers can work safely from redacted content.

  **Where this applies**

  * Executive dashboards, analyst exploration, reviewer queues, evidence viewers, lineage drill-down, materialized views, query APIs, search, staleness indicators, and raw reveal.
  * Browser and accessibility surfaces built over reports and review workflows.

  **Implementation requirements**

  * Treat this as T7.1.4, P1, estimated at 16 full-stack hours; it depends on TODOs 35, 47, and 42.
  * Executive views must remain aggregate-only and display release status, critical blocks, support, uncertainty, cost, and freshness.
  * Analyst views may drill from aggregates to slices, cases, attempts, grades, reviews, and provenance only within authorized scope.
  * Reviewer views default to redacted evidence, show task/version/SLA context, and require explicit audited raw reveal.
  * Build query indexes and materialized views with measured plans; display last refresh, source snapshot, and stale/invalid state.
  * Keep UI state transitions aligned with backend operation and review contracts; no privileged action may rely on client-only enforcement.

  **Security and safety requirements**

  * Enforce role/project/classification authorization server-side for every query, search result, drill-down, and reveal.
  * Use inert rendering, strict CSP, safe links, and no external content fetch.
  * Audit drill-down into restricted cases, raw reveal, export, review submission, and administrative action.

  **Edge cases and outliers to handle**

  * Access revoked mid-session, stale materialized view, report invalidated after display, deep links shared across roles, and browser back-cache exposing prior content.
  * Empty/low-support slices, long labels, large evidence, conflicting reviews, and slow queries.
  * Hidden-set cases appearing in search or autocomplete.

  **Acceptance criteria (“done” definition)**

  * Each persona sees only approved data and actions; executive surfaces contain no raw restricted evidence.
  * Analyst drill-down preserves complete lineage and visible version/freshness context.
  * Reviewer raw access is explicit, least-privilege, and audited.
  * Query plans meet approved targets and stale/invalid views cannot appear current.

  **Testing plan**

  * Unit-test view-model authorization, state rendering, staleness logic, and redaction.
  * Integration-test APIs, RLS, reports, materialized views, review workflow, safe viewer, and audit.
  * End-to-end test each persona, access revocation, deep links, invalidation, and raw reveal.
  * Negative/security-test cross-role/project access, stored XSS, hidden-set search leakage, and client-side bypass; load-test dashboard and drill-down queries.

  **Debugging checklist**

  * Inspect user/role/project, query/trace ID, authorization decision, materialized-view refresh time, source snapshot, report validity, evidence classification, reveal audit, and browser CSP reports.
  * Reproduce with the same least-privilege persona and direct API calls.
  * Check cached authorization, unscoped search indexes, browser cache headers, stale view refresh jobs, raw evidence embedded in page source, and UI controls hidden without backend denial.

* [ ] TODO 49: Complete accessibility and localization readiness

  **Purpose / Why this exists**

  * Ensure critical review, analysis, and release workflows are usable by people relying on keyboard, screen readers, zoom, or localized presentation.
  * Prevent accessibility defects or hard-coded language assumptions from blocking safety decisions or introducing inconsistent policy meaning.

  **Where this applies**

  * Executive, analyst, reviewer, authentication, error, confirmation, export, and dossier-verification interfaces.
  * User-visible strings, dates, numbers, pluralization, layout, directionality, semantic markup, and assistive-technology behavior.

  **Implementation requirements**

  * Treat this as T7.1.5, P1, estimated at 12 accessibility/localization hours; it depends on TODOs 48 and 9.
  * Meet WCAG 2.2 AA for primary workflows: keyboard operation, visible focus, logical order, semantic labels, headings, landmarks, non-color states, contrast, zoom/reflow, and screen-reader announcements.
  * Externalize user-visible strings, messages, date/number formats, and policy text; avoid concatenated fragments that cannot be translated safely.
  * Support long text, pluralization, locale-neutral storage, and RTL-like layout testing even if first-release languages are limited.
  * Require governed translation/versioning for policy or safety-critical text; localization must not alter decision semantics.
  * Include accessibility and language metadata in release evidence.

  **Security and safety requirements**

  * Do not expose restricted content through accessible names, hidden DOM nodes, live regions, tooltips, or error descriptions.
  * Sanitize translated content and prohibit translators from introducing active markup.
  * Maintain equivalent authorization and confirmation behavior across localized variants.

  **Edge cases and outliers to handle**

  * 200–400% zoom, high contrast, reduced motion, screen-reader virtual navigation, mobile widths, long identifiers, CJK text, RTL, and mixed-direction content.
  * Dynamic queue updates, async operation status, modal focus traps, validation errors, and raw-evidence reveal confirmation.
  * Missing translation, fallback locale, and locale change during an active task.

  **Acceptance criteria (“done” definition)**

  * Primary workflows pass automated and manual WCAG 2.2 AA verification with documented assistive technologies.
  * All user-visible text is externalized or explicitly exempted; layouts tolerate long and bidirectional text.
  * Safety-critical meanings and exit/gate states remain equivalent across locales.
  * No sensitive content leaks through accessibility metadata or hidden UI.

  **Testing plan**

  * Unit-test localization keys, formatters, accessible labels, focus management, and non-color status mapping.
  * Integration-test browser components with APIs, async updates, errors, and safe viewer.
  * End-to-end test keyboard-only and screen-reader workflows for each persona and selected locale/RTL fixtures.
  * Negative-test missing translations, unsafe markup, hidden sensitive text, and focus loss; load-test dynamic tables and security-test localization/rendering inputs.

  **Debugging checklist**

  * Inspect accessibility tree, focus order, live-region events, computed contrast, zoom/reflow, locale key, fallback behavior, formatted values, and DOM content hidden visually.
  * Reproduce using the documented browser and assistive-technology combination.
  * Check duplicate IDs, unlabeled controls, focus moved by rerender, status conveyed only by color, raw content in `aria-label`, and untranslated server errors.

* [ ] TODO 50: Run hostile tests for API, CLI, reports, and UX

  **Purpose / Why this exists**

  * Validate external interfaces and user workflows against malformed data, concurrency, stale state, active content, authorization failures, and accessibility regressions.
  * Prove REST and CLI outcomes remain equivalent and that front-end boundaries cannot bypass correct domain controls.

  **Where this applies**

  * REST API, CLI, operation resources, pagination, idempotency, reports, exports, dashboards, reviewer UI, accessibility, localization, and safe rendering.
  * Contract, browser, security, fault-proxy, and end-to-end test harnesses.

  **Implementation requirements**

  * Treat this as T7.1.6, P1, estimated at 16 quality-engineering hours; it depends on TODOs 45–49.
  * Cover common workflows, malformed/large payloads, duplicate keys, stale ETags, replay, idempotency conflict, concurrency, timeout, retry, network partition, pagination edges, export races, version skew, active content, stale views, keyboard, and screen reader behavior.
  * Use deterministic clocks, fault proxies, seeded data, and shared golden expected outcomes for REST and CLI.
  * Verify user-visible state, exit code, HTTP status, domain result, audit event, and retained artifact for every scenario.
  * Preserve failure artifacts, screenshots/accessibility trees where appropriate, request traces, and reproducible seeds.

  **Security and safety requirements**

  * Run hostile inputs only against isolated authorized environments.
  * Ensure test artifacts containing restricted or active content remain quarantined and access-controlled.
  * Confirm every privileged action is backend-authorized and every rejected action avoids sensitive error disclosure.

  **Edge cases and outliers to handle**

  * Client disconnect after mutation, export completes after access revocation, cursor spans dataset change, report invalidated while open, and CLI receives partial JSON.
  * Browser cache, service-worker state if present, locale changes, long-running operation polling, and simultaneous reviewer submissions.
  * Accessibility behavior during errors or dynamic updates.

  **Acceptance criteria (“done” definition)**

  * Required common, failure, hostile, concurrency, accessibility, and version-skew scenarios pass.
  * REST and CLI produce equivalent domain outcomes and documented status/exit mappings.
  * No active content executes, no unauthorized data appears, and no stale state is represented as current.
  * Failures are visible, traceable, bounded, and recoverable rather than silent.

  **Testing plan**

  * Unit-test interface adapters, serializers, error/exit mappings, and UI state models.
  * Integration-test API/CLI/report/browser boundaries with real dependencies and fault proxies.
  * End-to-end test each persona and automation workflow under success and failure.
  * Perform negative, load/stress, accessibility, and security testing for parsing, auth, XSS, races, exports, and network faults.

  **Debugging checklist**

  * Inspect request/trace/operation IDs, identity/project, payload and schema hashes, ETag/idempotency record, HTTP status, CLI exit code, UI state, report hash, audit event, and fault timeline.
  * Reproduce through the lowest failing boundary, then through the full interface.
  * Check divergent REST/CLI error mapping, browser/client retries, caches, stale generated schemas, test clocks not applied consistently, and failures occurring before audit/correlation initialization.

* [ ] TODO 51: Implement structured telemetry and correlation

  **Purpose / Why this exists**

  * Make execution, grading, review, release, and dependency behavior diagnosable without logging sensitive model content or secrets.
  * Prevent incidents from becoming untraceable and prevent observability systems from becoming a high-cardinality data leak.

  **Where this applies**

  * OpenTelemetry-compatible logs, metrics, and traces across API, scheduler, workers, adapters, graders, review, metrics, reports, exports, storage, database, and maintenance jobs.
  * Telemetry schemas, correlation propagation, sampling, retention, and redaction.

  **Implementation requirements**

  * Treat this as T8.1.1, P0, estimated at 16 SRE hours; it depends on TODOs 22, 29, and 45.
  * Define allowlisted telemetry fields and correlation keys including project, experiment, run, attempt, job, provider, model, case, family, worker, grader, operation, trace, and release identifiers.
  * Instrument critical state transitions, dependency calls, queue claims, provider attempts, grading stages, review events, snapshot/gate creation, evidence verification, and export lifecycle.
  * Propagate trace and correlation context through HTTP, jobs, outbox events, and background operations.
  * Define cardinality budgets, histogram boundaries, sampling, retention, and dropped-telemetry behavior.
  * Never record prompt/response bodies, secrets, bearer tokens, raw attachments, or unrestricted rationale in telemetry.

  **Security and safety requirements**

  * Enforce field allowlists and centralized redaction; use canary secrets/content to prove redaction.
  * Scope observability access by environment and role; audit queries or exports of sensitive operational metadata where required.
  * Ensure attacker-controlled strings cannot become metric names, label keys, trace attributes with unbounded cardinality, or executable log markup.

  **Edge cases and outliers to handle**

  * Missing trace context, async fan-out/fan-in, retries, out-of-order events, sampling dropping a critical trace, and clock skew.
  * Telemetry backend outage, exporter backpressure, high-cardinality case IDs, and redaction library failure.
  * Logs emitted before identity/project context is established.

  **Acceptance criteria (“done” definition)**

  * Required identifiers correlate one logical run across API, scheduler, provider, grader, review, metrics, reports, and audit.
  * Redaction canaries confirm no prohibited bodies or secrets enter telemetry.
  * Cardinality and exporter resource use remain within approved budgets.
  * Telemetry failure does not corrupt domain work and creates an observable degraded state.

  **Testing plan**

  * Unit-test context propagation, field allowlists, redaction, sampling, and cardinality guards.
  * Integration-test telemetry across HTTP, jobs, events, database, object store, and provider mocks.
  * End-to-end trace representative success, retry, review, gate, and failure workflows.
  * Negative/security-test secret canaries, malicious labels, missing context, and telemetry access; load/stress-test exporter backpressure and high-volume traces.

  **Debugging checklist**

  * Inspect trace/span IDs, baggage/correlation fields, project/run/attempt IDs, exporter queue, dropped count, sampling decision, redaction result, backend ingestion, and clock synchronization.
  * Follow one immutable run ID across logs, metrics, traces, audit, and database state.
  * Check context lost at queue boundaries, field names differing by service, high-cardinality attributes, body capture enabled by framework defaults, and exporter retries exhausting application resources.

* [ ] TODO 52: Establish SLIs, SLO dashboards, and actionable alerts

  **Purpose / Why this exists**

  * Convert telemetry and persisted state into measurable service objectives and operator actions.
  * Prevent healthy-looking dashboards from masking lost jobs, stale evidence, review backlog, or user-visible latency.

  **Where this applies**

  * API, queue, provider, grading, review, evidence, audit, report, cost, and release dashboards.
  * Alerting, error budgets, escalation, maintenance windows, and runbook links.

  **Implementation requirements**

  * Treat this as T8.1.2, P0, estimated at 16 SRE hours; it depends on TODOs 51 and 21.
  * Define exact SLI queries and measurement windows for at least 99.9% API availability, 99.99% accepted-definition durability, zero known lost jobs, p95 queue start ≤5 minutes, p95 grading ≤2 minutes, p99 report generation ≤10 minutes, and 100% scheduled hash verification.
  * Reconcile telemetry-based indicators with authoritative persisted state so dropped telemetry cannot imply success.
  * Build dashboards for service health, queue age/depth, provider errors/identity, grader/review drift, evidence integrity, audit continuity, cost/budget, backups, and release readiness.
  * Configure page versus ticket alerts with severity, owner, deduplication, suppression, runbook, and explicit recovery condition.
  * Define error-budget policy and release/feature-freeze consequences.

  **Security and safety requirements**

  * Alerts and dashboards must not include raw prompt/response content, secrets, or unrestricted evidence.
  * Limit dashboard and alert-management permissions; audit SLO/alert changes and suppressions.
  * Protect alert routing from attacker-controlled labels or notification injection.

  **Edge cases and outliers to handle**

  * Telemetry gap, maintenance window, provider-caused errors, partial regional outage, clock skew, and stale materialized indicators.
  * Low traffic masking availability, repeated alert flapping, review backlog limited to one critical slice, and hash-verification job itself failing.
  * SLO query changes mid-window.

  **Acceptance criteria (“done” definition)**

  * Every required SLI has a versioned query, owner, target, window, source of truth, and dashboard.
  * Alerts fire and recover in tested scenarios, link to current runbooks, and contain sufficient safe context.
  * Persisted-state reconciliation detects lost/stuck work even when telemetry is absent.
  * Error-budget policy is approved and enforced in release decisions.

  **Testing plan**

  * Unit-test SLI calculations, windowing, deduplication, maintenance handling, and severity routing.
  * Integration-test telemetry backend, persisted-state checks, dashboards, paging, tickets, and runbook links.
  * End-to-end inject synthetic failures and confirm detection, notification, acknowledgment, and recovery.
  * Negative-test missing telemetry, malformed labels, alert suppression abuse, and raw-content leakage; load-test dashboard queries and alert storms and security-test permissions.

  **Debugging checklist**

  * Inspect SLI query/version, source timestamps, ingestion lag, persisted-state reconciliation, error-budget window, alert fingerprint, routing, suppression, and runbook URL/version.
  * Recalculate the SLI from raw safe telemetry and authoritative database records.
  * Check timezone/window mismatch, missing labels, stale recording rules, low-traffic denominator behavior, alerts based only on averages, and maintenance suppressions that outlive their change window.

* [ ] TODO 53: Write operational runbooks and graceful-degradation rules

  **Purpose / Why this exists**

  * Give operators safe, evidence-preserving actions for common and severe failures.
  * Prevent improvised incident responses that destroy provenance, expand exposure, or allow unsafe certification to continue during degraded operation.

  **Where this applies**

  * Provider outage, queue backlog, worker loop, model identity drift, metric discrepancy, grader drift, artifact exposure, credential leak, dataset poisoning, database/object/audit failure, wrong gate result, restore, and signing-key compromise.
  * Incident detection, containment, recovery, communications, rollback, reconciliation, and re-certification.

  **Implementation requirements**

  * Treat this as T8.1.3, P1, estimated at 16 SRE/security-operations hours; it depends on TODOs 52 and 44.
  * Define a SEV taxonomy, incident roles, declaration criteria, escalation, communication channels, evidence-preservation requirements, and closure criteria.
  * For each scenario, document detection signals, immediate safe action, actions prohibited, diagnostic checks, containment, rollback/degradation, customer/internal communication, recovery, reconciliation, and re-certification.
  * Define graceful-degradation rules: pause admission when integrity is uncertain; allow read-only verified reports where safe; never certify with missing evidence, unresolved critical reviews, identity drift, or failed audit continuity.
  * Use exact commands only after the authorized remote execution context is resolved; version runbooks with releases and link alerts to the matching version.
  * Require quarterly tabletop or game-day validation and update after incidents.

  **Security and safety requirements**

  * Restrict destructive commands and break-glass steps to authorized roles with change records and session audit.
  * Do not embed secrets in runbooks; reference managed secret paths and approval procedures.
  * Preserve forensic evidence, hashes, logs, and chain of custody before cleanup.

  **Edge cases and outliers to handle**

  * Simultaneous dependency failures, telemetry unavailable during incident, IdP outage, compromised administrator identity, and conflicting incident objectives.
  * Provider outage during cancellation, key compromise during dossier signing, and data exposure requiring deletion while legal hold applies.
  * Runbook command outdated for the deployed version.

  **Acceptance criteria (“done” definition)**

  * Approved runbooks cover every listed scenario with owner, detection, safe action, evidence, rollback, communication, and re-certification.
  * Alerts link to the correct current runbook and authority path.
  * Graceful-degradation rules are implemented in system controls where possible, not merely documented.
  * Exercises demonstrate operators can act without unsafe defaults or evidence loss.

  **Testing plan**

  * Unit-test runbook metadata, alert-link validation, command/version prerequisites, and degradation-policy rules.
  * Integration-test alerts, admission controls, break-glass workflow, audit, backup/restore, and communications tooling.
  * End-to-end tabletop and staging exercises for representative availability, integrity, and security incidents.
  * Negative/security-test unauthorized command use, stale runbooks, missing telemetry, and compromised credentials; load-test alert/incident coordination during multiple failures.

  **Debugging checklist**

  * Inspect deployed version, active runbook revision, alert fingerprint, incident ID/SEV, commander, change approvals, executed commands, evidence hashes, degradation state, and recovery checkpoints.
  * Compare actual sequence with the runbook timeline and identify the first divergence.
  * Check broken alert links, obsolete service names, unavailable break-glass path, commands assuming production access from local hosts, and recovery completed without reconciliation or re-certification.

* [ ] TODO 54: Execute performance, load, and soak qualification

  **Purpose / Why this exists**

  * Prove that the end-to-end platform meets declared latency, throughput, durability, and recovery objectives with operating headroom.
  * Detect lock contention, queue collapse, memory leaks, object bottlenecks, and overload behavior before production certification.

  **Where this applies**

  * API, PostgreSQL queue, workers, provider mocks, grading, review generation, object storage, reports, telemetry, quotas, and recovery.
  * Common, burst, large-payload, slow-provider, report-heavy, and review-backlog profiles.

  **Implementation requirements**

  * Treat this as T8.1.4, P1, estimated at 16 performance-engineering hours; it depends on TODOs 28, 37, 50, and 52.
  * Use the approved capacity profile from TODO 21 and require at least 30% measured headroom at declared load.
  * Measure p50/p95/p99 latency, throughput, error rate, queue age, DB locks/I/O, connection saturation, object throughput, grading time, report queries, resource saturation, and cost.
  * Use deterministic provider mocks for repeatable high concurrency and only bounded live-provider canaries for quota/latency validation.
  * Run multi-day soak tests and overload/recovery scenarios; verify no lost or duplicate logical runs and no unbounded backlog after load stops.
  * Publish environment topology, versions, dataset, workload seed, tuning, and raw result artifacts.

  **Security and safety requirements**

  * Isolate load infrastructure and cap live-provider spend and external traffic.
  * Do not use Restricted/Secret data; ensure generated payloads cannot trigger live tools.
  * Protect performance results containing internal capacity, pricing, or architecture details.

  **Edge cases and outliers to handle**

  * Retry storms, provider throttling, large responses, slow object storage, reporting during peak execution, vacuum/checkpoint events, and telemetry exporter backpressure.
  * Warm versus cold caches, autoscaling lag, one project dominating load, and memory/resource leakage visible only in soak.
  * Load-generator bottleneck misidentified as service capacity.

  **Acceptance criteria (“done” definition)**

  * Approved SLOs pass at declared load with at least 30% headroom and no lost/duplicate logical runs.
  * Soak testing shows stable memory, connection, queue, and storage behavior.
  * Overload produces documented backpressure and recovers without manual data repair.
  * Capacity limits and next scaling triggers are recorded with evidence.

  **Testing plan**

  * Unit-test workload generators, result aggregation, percentile calculations, and pass/fail thresholds.
  * Integration-test component benchmarks and observability under controlled load.
  * End-to-end run common, burst, slow-provider, large-payload, report, overload, recovery, and soak profiles.
  * Perform negative/security tests for denial-of-wallet, quota bypass, oversized inputs, and cross-project fairness while stress testing.

  **Debugging checklist**

  * Inspect workload seed, generator saturation, service/resource metrics, queue age, DB locks, query plans, connection pools, object latency, worker utilization, retries, budgets, and error traces.
  * Verify the load generator can exceed the target before attributing a plateau to the service.
  * Check hidden SDK retries, cache warmth, autoscaling limits, noisy neighbors, stale database statistics, telemetry overhead, and cleanup jobs running during the test.

* [ ] TODO 55: Implement backup, point-in-time restore, and full reconciliation

  **Purpose / Why this exists**

  * Recover the complete evidence system—not only the database—after corruption, deletion, credential loss, or infrastructure failure.
  * Prevent a nominally successful restore from leaving missing objects, broken audit chains, unrecoverable keys, or unverifiable dossiers.

  **Where this applies**

  * PostgreSQL backups/PITR, object versions, manifests, audit checkpoints, KMS/key recovery, configuration, infrastructure state, and isolated restore environments.
  * Recovery objectives, restore automation, reconciliation, and re-certification.

  **Implementation requirements**

  * Treat this as T8.1.5, P0, estimated at 16 SRE hours; it depends on TODOs 20, 40, and 52.
  * Configure automated encrypted PostgreSQL backups and PITR to meet RPO 15 minutes and RTO 4 hours unless an approved replacement is documented.
  * Preserve object versions, dataset/report/dossier manifests, audit checkpoints, trust-registry history, required key-recovery material, and infrastructure/configuration versions.
  * Automate restore into an isolated account/environment and verify versions before permitting network access.
  * Reconcile 100% of accepted runs, attempts, objects, hashes, outbox events, provenance edges, audit continuity, metric snapshots, gates, and dossiers.
  * Require integrity review and re-certification before restored production resumes release decisions.

  **Security and safety requirements**

  * Encrypt backups with separately governed keys and restrict backup/restore roles from normal application identities.
  * Test account/region isolation and credential-loss recovery; protect restored data from broad staging access.
  * Audit backup creation, verification, retention, restore, privileged access, reconciliation, and destruction of test restores.

  **Edge cases and outliers to handle**

  * PITR boundary during an in-flight object commit, missing object version, unavailable/revoked key, audit checkpoint outside the restored timeline, and legal holds.
  * Entire account/region unavailable, backup catalog corrupted, restore into newer schema/code, and backups containing expired data.
  * Partial restore that appears healthy at API level.

  **Acceptance criteria (“done” definition)**

  * Automated backups meet approved RPO/RTO and are periodically verified, not merely created.
  * Isolated restore reconciles every accepted logical run and the full evidence/provenance chain.
  * Missing keys, objects, audit continuity, or manifests cause restore failure and production block.
  * Successful restore evidence includes timings, hashes, reconciliation report, approvals, and re-certification status.

  **Testing plan**

  * Unit-test backup inventory, retention, restore-plan generation, and reconciliation rules.
  * Integration-test PostgreSQL PITR, object version restore, key/trust-registry recovery, audit checkpoints, and manifests.
  * End-to-end test isolated disaster recovery through verified dossier access and re-certification.
  * Negative/security-test corrupted backup, missing key, unauthorized restore, cross-region failure, and stale data; load-test restore/reconciliation at forecast volume.

  **Debugging checklist**

  * Inspect backup ID/time, WAL coverage, object version inventory, key IDs, trust-registry snapshot, audit checkpoint, restore topology, schema/application versions, reconciliation counts, and hash failures.
  * Compare restored state with the last signed pre-failure manifest.
  * Check database-only recovery, object retention gaps, keys excluded from recovery planning, restore jobs using production credentials, and reconciliation queries omitting failed or archived states.

* [ ] TODO 56: Build deterministic CI, release artifacts, and infrastructure as code

  **Purpose / Why this exists**

  * Make builds, tests, schemas, images, and infrastructure repeatable and reviewable.
  * Prevent manually configured environments, non-reproducible artifacts, unpinned dependencies, or unverified images from undermining release evidence.

  **Where this applies**

  * CI workflows, Python builds, containers, schema/OpenAPI generation, test stages, artifact publication, Terraform/Kubernetes/compose/monitoring definitions, environment promotion, and drift detection.
  * Development, integration, staging, and production.

  **Implementation requirements**

  * Treat this as T8.1.6, P0, estimated at 16 DevOps hours; it depends on TODOs 3, 8, and 43.
  * Pin dependencies, build tools, base images, CI actions, and infrastructure modules; record all input digests.
  * Generate packages, images, schemas, OpenAPI, SBOMs, signatures, and provenance deterministically or document unavoidable variance with normalized verification.
  * Gate publication on format, type, unit, property, golden, mutation, contract, security, integration, end-to-end, and required evidence checks.
  * Define infrastructure as code for environments, identities, networks, PostgreSQL, object storage, KMS/secrets, telemetry, policies, backups, and alerts.
  * Promote immutable artifacts by digest; do not rebuild per environment.
  * Fail startup on unknown configuration, missing required controls, or production use of development identity/storage modes.

  **Security and safety requirements**

  * Protect branches/tags/workflows, use federated CI identity, isolate untrusted contributions, and require reviewed changes to deployment/signing logic.
  * Store no long-lived secrets in CI; attest builder identity and source commit.
  * Run policy-as-code and drift checks, and block public exposure or overly broad IAM/network changes.

  **Edge cases and outliers to handle**

  * Cache poisoning, flaky tests, CI outage, platform-specific artifacts, timestamps causing nondeterminism, and generated files differing by tool version.
  * Partial artifact publication, registry outage, IaC state lock, manual emergency change, and environment drift.
  * Previous release cannot be rebuilt because a dependency disappeared.

  **Acceptance criteria (“done” definition)**

  * A clean build from pinned inputs produces matching artifact digests or approved normalized equivalence.
  * Required CI gates block publication and produce signed evidence.
  * All production infrastructure and policy are represented in reviewed IaC with drift detection.
  * Environments deploy the same immutable artifact and reject unsafe configuration.

  **Testing plan**

  * Unit-test build scripts, configuration schemas, policy rules, and deterministic metadata.
  * Integration-test CI runners, registries, signing, IaC plans/applies, environment promotion, and drift detection.
  * End-to-end test commit-to-staging release and artifact verification.
  * Negative/security-test workflow tampering, unsigned images, secret exposure, malicious caches, unsafe IaC, and startup misconfiguration; load-test CI parallelism and artifact publication.

  **Debugging checklist**

  * Inspect source commit, lockfile/tool digests, runner/builder identity, cache provenance, generated schema hashes, image/package digest, SBOM, signature, IaC plan/state, and policy results.
  * Rebuild with caches disabled in a fresh runner.
  * Check unpinned transitive tools, local generated files committed stale, environment-specific rebuild steps, clocks/locales embedded in artifacts, manual infrastructure drift, and publication occurring before attestations complete.

* [ ] TODO 57: Implement deployment, migration, rollback, and version-skew controls

  **Purpose / Why this exists**

  * Deploy API, workers, schemas, events, and reports safely while supporting in-flight jobs and rollback.
  * Prevent mixed versions from corrupting work, destructive migrations from making rollback impossible, or rollback from discarding evidence written by newer code.

  **Where this applies**

  * API and worker deployments, database migrations, event/contract compatibility, report readers, admission controls, canaries, rollback, and release promotion.
  * Previous/current version compatibility window.

  **Implementation requirements**

  * Treat this as T8.1.7, P1, estimated at 16 release-engineering hours; it depends on TODOs 19 and 56.
  * Use rolling or blue/green deployment for API and independent rollout for scheduler, provider, grader, report, and maintenance workers.
  * Maintain a tested compatibility matrix across previous/current API, worker, schema, event, configuration, and report versions.
  * Execute expand → migrate/backfill → switch → observe → contract; never perform irreversible contraction in the same rollout that introduces a replacement.
  * Add pre-deploy checks, migration dry runs, canaries, post-deploy verification, error-budget checks, and automatic admission pause for integrity defects.
  * Rollback code and routing while preserving all newly written evidence; use forward data repair where an older writer cannot safely handle new state.

  **Security and safety requirements**

  * Deploy only signed artifacts by digest through authorized automation; audit approvals and changes.
  * Revalidate identities, network policies, secrets, and configuration during deployment.
  * Restrict manual production changes and require break-glass procedures with follow-up reconciliation.

  **Edge cases and outliers to handle**

  * Long-running jobs crossing versions, old worker receives new event, partial migration, canary writes new schema, rollback after new state transition, and deployment during provider outage.
  * Database contraction delayed indefinitely, mixed report versions, and one worker class failing while API remains healthy.
  * Release artifact revoked after deployment begins.

  **Acceptance criteria (“done” definition)**

  * One-release version-skew scenarios pass for every API/worker/schema/event combination declared supported.
  * Migrations and deployments can pause, resume, roll forward, or roll back without evidence loss.
  * Integrity failures pause admission and prevent release certification.
  * Deployment records identify exact artifacts, schema revisions, configuration, approvals, and verification evidence.

  **Testing plan**

  * Unit-test compatibility-policy evaluation, rollout gates, canary thresholds, and rollback selection.
  * Integration-test mixed versions, migrations, event consumers, long-running jobs, and configuration changes.
  * End-to-end test deploy, canary, migration, rollback, forward repair, and resumed admission.
  * Negative/security-test unsigned artifacts, incompatible worker, partial migration, privilege misuse, and revoked image; load-test rolling capacity and version-skew behavior.

  **Debugging checklist**

  * Inspect deployment ID, artifact digest/signature, process versions, schema revision, event/schema versions, migration checkpoints, canary metrics, admission state, and rollback decision.
  * Reproduce mixed-version behavior in staging using the same compatibility matrix.
  * Check contraction applied too early, workers not drained, old consumers silently ignoring fields, configuration changed outside IaC, and rollback tooling selecting tags instead of immutable digests.

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

* [ ] TODO 61: Run the cross-system game day and exhaustive failure matrix

  **Purpose / Why this exists**

  * Demonstrate that the complete socio-technical system can detect, contain, recover, reconcile, and re-certify after realistic failures.
  * Validate interactions among alerts, runbooks, operators, backups, security controls, evidence integrity, and release governance rather than testing components in isolation.

  **Where this applies**

  * API, IdP, PostgreSQL, object storage, outbox/audit, scheduler, workers, providers, graders, review, telemetry, KMS/signing, reports, deployment, backup/restore, certification, and incident response.
  * Authorized isolated staging environment with production-like topology.

  **Implementation requirements**

  * Treat this as T8.1.11, P1, estimated at 16 exercise hours plus preparation/remediation; it depends on TODOs 53, 54, 55, and 58.
  * Build an exhaustive matrix covering common flows, rare critical cases, hostile inputs, partial failures, concurrency, replay/idempotency, timeout, retry, network partition, malformed data, large payloads, version skew, dependency outage, operator error, and security compromise.
  * Execute controlled failures for worker, scheduler, database, object storage, outbox/audit, provider, IdP, telemetry, KMS/signing, and deployment paths.
  * Prove the full sequence: alert → triage → authority assignment → containment/degradation → evidence preservation → restore/repair → reconciliation → re-certification → closure.
  * Measure MTTD, acknowledgment, containment, recovery, reconciliation, RPO/RTO, SLO impact, data integrity, decision correctness, and communication timing.
  * Record exercise timeline, injected faults, operator actions, command evidence, artifacts, findings, owners, and retest requirements.

  **Security and safety requirements**

  * Use written authorization, isolated targets, change control, fault allowlists, abort criteria, rollback plans, and an independent safety observer.
  * Do not inject destructive faults into shared or production environments; use synthetic/redacted data.
  * Protect incident evidence, participant identity, architectural details, and discovered vulnerabilities according to classification.

  **Edge cases and outliers to handle**

  * Simultaneous telemetry and dependency failure, IdP outage during incident, compromised signing key during release, database restore with object gaps, and operator executing a wrong but plausible action.
  * Fault-controller failure, exercise running beyond maintenance window, unexpected shared dependency, and recovery meeting availability but not integrity.
  * Re-certification evidence becoming stale during extended recovery.

  **Acceptance criteria (“done” definition)**

  * The matrix explicitly records outcomes for every required common, outlier, hostile, concurrency, replay, timeout, retry, partition, malformed, large-payload, skew, outage, and operator-error class.
  * The game day proves alert-to-re-certification with preserved evidence and no unexplained data loss, duplication, leakage, or unsafe release decision.
  * RPO/RTO, SLO, integrity, authorization, and communication objectives are met or generate blocking remediation.
  * Findings have severity, owner, due date, containment, regression scenario, and certification impact; critical/high failures are retested before release.

  **Testing plan**

  * Unit-test game-day orchestration safeguards, fault targeting, abort controls, timeline capture, and success criteria.
  * Integration-test each fault injector and affected dependency before the combined exercise.
  * Execute end-to-end single-fault and multi-fault scenarios through restore, reconciliation, and certification.
  * Run load/stress during selected failures and perform security tests for compromised identity, key, egress, audit, and operator privilege paths.

  **Debugging checklist**

  * Inspect exercise ID, authorization/change record, topology/version manifest, fault timeline, alerts, incident roles, operator commands, trace IDs, state transitions, backup/restore IDs, reconciliation report, certification manifest, and findings.
  * Reconstruct a single chronological timeline from monotonic and wall-clock records, accounting for clock skew.
  * Check fault injection outside the intended boundary, alerts suppressed by maintenance, operators using undocumented privileges, recovery declared before reconciliation, stale runbooks, and re-certification referencing pre-failure evidence.
