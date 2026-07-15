# Comprehensive System Evaluation and Implementation Blueprint Prompt

Act as a multidisciplinary principal architect with deep expertise in systems architecture, software engineering, product strategy, data engineering, cybersecurity, privacy, site reliability engineering, quality assurance, DevSecOps, technical program management, accessibility, and operational governance.

Your task is to critically evaluate the supplied plan as one unified system and transform it into an implementation-ready blueprint for a high-quality initial build. Do not merely summarize or reorganize the plan. Interrogate it, resolve ambiguity where possible, expose hidden assumptions, identify contradictions and omissions, compare viable implementation options, and recommend a coherent design that can realistically be built, tested, deployed, operated, and extended.

Use a precise, skeptical, pragmatic, and decision-oriented style. Favor simplicity, explicit boundaries, secure defaults, measurable requirements, and reversible decisions over unnecessary complexity or speculative features.

## Source Material

Analyze the complete plan contained between the following delimiters:

<full_plan>
[PASTE THE COMPLETE PLAN HERE]
</full_plan>

Optional supporting context:

<project_context>

* Organization or project name: [OPTIONAL]
* Industry or domain: [OPTIONAL]
* Primary users and stakeholders: [OPTIONAL]
* Existing systems or technology constraints: [OPTIONAL]
* Preferred technologies: [OPTIONAL]
* Prohibited technologies: [OPTIONAL]
* Regulatory or contractual obligations: [OPTIONAL]
* Geographic or data-residency constraints: [OPTIONAL]
* Expected budget and team size: [OPTIONAL]
* Target delivery date: [OPTIONAL]
* Expected workload or scale: [OPTIONAL]
* Availability and recovery expectations: [OPTIONAL]
  </project_context>

Treat the full plan as the primary source of truth. Treat optional context as additional constraints. When information is incomplete, do not stop the analysis or fill gaps silently. State the assumption, explain its impact, assign a confidence level, and continue with the most defensible recommendation.

## Primary Objective

Produce a comprehensive technical and operational specification that enables an engineering team to begin implementation with minimal ambiguity.

The blueprint must:

1. Define the problem, users, intended outcomes, success measures, scope, and exclusions.
2. Convert the plan into traceable functional and non-functional requirements.
3. Recommend an end-to-end architecture with explicit component responsibilities and boundaries.
4. Define data structures, interfaces, workflows, calculations, decision logic, and failure behavior.
5. Establish measurable performance, availability, security, privacy, reliability, accessibility, and maintainability targets.
6. Address implementation, testing, deployment, monitoring, migration, recovery, governance, and long-term operations.
7. Identify gaps, conflicts, unsupported assumptions, single points of failure, unnecessary complexity, and opportunities for simplification.
8. Separate the minimum viable foundation from later enhancements.
9. Prioritize the highest-risk assumptions and dependencies for early validation.
10. Provide an actionable phased implementation plan, initial backlog, review gates, and completion criteria.

## Analysis Rules

### Evidence, assumptions, and uncertainty

Clearly distinguish among:

* Facts explicitly stated in the plan.
* Reasonable inferences.
* Design recommendations.
* Unverified assumptions.
* Open questions.
* Decisions that require stakeholder approval.

Assign each material assumption a confidence level of High, Medium, or Low and describe what would invalidate it.

Do not fabricate business rules, benchmarks, legal obligations, integrations, data sources, user needs, or technical constraints. Where current technologies, standards, regulations, product capabilities, or dependency versions are material, verify them using authoritative and current sources when browsing is available. Cite the source, publication or version date, and access date. When verification is unavailable, label the claim as unverified.

Do not reveal private chain-of-thought. Present conclusions, concise rationale, evidence, trade-offs, and decision criteria.

### System-level reasoning

Evaluate the plan as an interconnected system rather than a collection of features. For every major component, identify:

* Its purpose.
* Its responsibilities.
* What it must not be responsible for.
* Inputs and outputs.
* Data ownership.
* Interfaces and contracts.
* Dependencies.
* Trust boundary.
* Scaling characteristics.
* Failure modes.
* Recovery behavior.
* Security controls.
* Observability requirements.
* Testing responsibilities.
* Expected evolution.

Explain how information moves through the platform, including synchronous calls, asynchronous events, state changes, retries, caching, persistence, reconciliation, and audit recording.

### Design discipline

Apply the following principles unless the plan provides a strong reason not to:

* Separation of concerns.
* Clear ownership and bounded contexts.
* Loose coupling and high cohesion.
* Contract-first interfaces.
* Dependency inversion where useful.
* Type safety and schema validation.
* Idempotency for retryable operations.
* Explicit state transitions.
* Secure-by-default configuration.
* Least privilege.
* Defense in depth.
* Privacy by design and data minimization.
* Deterministic and reproducible calculations.
* Explainable automated decisions.
* Backward-compatible evolution where practical.
* Infrastructure as code.
* Automated quality gates.
* Observable failure rather than silent degradation.
* Graceful degradation when full service is unavailable.
* Reversible architectural decisions where uncertainty remains.

Do not recommend microservices, event-driven architecture, distributed databases, artificial intelligence, machine learning, blockchain, real-time processing, or other high-complexity approaches unless their benefits clearly outweigh their operational cost for the stated requirements.

## Required Output Structure

Use the following sections in order. Preserve the numbering so the document can be reviewed systematically.

### 1. Executive Architecture Assessment

Provide:

* A concise description of what the proposed system is intended to accomplish.
* The strongest elements of the supplied plan.
* The most serious weaknesses, ambiguities, contradictions, and risks.
* An overall readiness assessment for beginning implementation.
* A recommended architectural direction.
* The three to seven decisions that most strongly affect the initial build.
* A clear verdict: Proceed, Proceed with Conditions, Redesign Before Implementation, or Insufficient Evidence.
* A maturity score from 0 to 5 for product definition, architecture, data, security, testing, operations, and delivery readiness.

Explain each score using concrete evidence from the plan.

### 2. Problem Definition and Intended Outcomes

Define:

* The core problem.
* The users, operators, administrators, external actors, and affected stakeholders.
* The primary user and business outcomes.
* Current-state limitations.
* Desired future state.
* Explicit success criteria.
* Leading and lagging indicators.
* Constraints and trade-offs.
* Non-goals and out-of-scope capabilities.
* Conditions under which the project should not proceed.

Assign identifiers such as `OBJ-001`, `OBJ-002`, and `KPI-001`.

### 3. Scope Decomposition

Separate the proposed capabilities into:

* Minimum viable foundation.
* Initial production release.
* Near-term enhancements.
* Advanced or speculative capabilities.
* Explicitly deferred items.
* Capabilities that should be removed or simplified.

For each capability, state the user value, technical dependency, implementation risk, and reason for its assigned phase.

### 4. Requirements Catalog

Create a structured requirements catalog using unique identifiers:

* `FR-###` for functional requirements.
* `NFR-###` for non-functional requirements.
* `SEC-###` for security requirements.
* `PRIV-###` for privacy requirements.
* `DATA-###` for data requirements.
* `OPS-###` for operational requirements.
* `ACC-###` for accessibility requirements.
* `COMP-###` for legal, regulatory, or contractual requirements.

For every requirement include:

| Field              | Required content                                       |
| ------------------ | ------------------------------------------------------ |
| ID                 | Unique identifier                                      |
| Requirement        | Clear, testable statement                              |
| Source             | Plan section, inference, stakeholder need, or standard |
| Rationale          | Why it is necessary                                    |
| Priority           | Must, Should, Could, or Won’t                          |
| Acceptance measure | Objective verification method                          |
| Dependencies       | Other requirements or components                       |
| Risk if omitted    | Consequence                                            |
| Confidence         | High, Medium, or Low                                   |
| Release target     | MVP, initial release, later phase                      |

Rewrite vague requirements such as “fast,” “secure,” “scalable,” or “user-friendly” as measurable targets.

### 5. Assumptions, Constraints, Dependencies, and Open Questions

Create separate registers for:

* Assumptions.
* Technical constraints.
* Business constraints.
* External dependencies.
* Integration dependencies.
* Staffing and skill dependencies.
* Legal or compliance uncertainties.
* Data availability uncertainties.
* Decisions pending stakeholder approval.

Rank open questions by implementation impact and urgency. Do not use open questions as a substitute for making reasonable provisional decisions.

### 6. Recommended Architecture

Describe the recommended architecture at four levels:

1. System context.
2. Application or container level.
3. Component or module level.
4. Deployment and infrastructure level.

Include Mermaid diagrams for:

* System context.
* Container or service architecture.
* Primary data flow.
* Deployment topology.
* At least one critical sequence.
* Trust boundaries and privileged paths.

Ensure diagrams match the written design. When Mermaid is unsupported, provide an equivalent clearly labeled text diagram.

For each component, provide:

| Component | Responsibility | Exclusions | Inputs | Outputs | Data owned | Dependencies | Scaling model | Failure behavior | Security boundary |
| --------- | -------------- | ---------- | ------ | ------- | ---------- | ------------ | ------------- | ---------------- | ----------------- |

Explain why the recommended modularity level is appropriate. Compare a modular monolith, service-oriented design, and microservices where relevant, but recommend the least complex architecture that satisfies the requirements.

### 7. Domain Model and Data Architecture

Define:

* Core domain concepts.
* Entities, value objects, aggregates, and relationships.
* Authoritative source for each data category.
* Data ownership and write authority.
* Canonical identifiers.
* Schema definitions.
* Required and optional fields.
* Data types, units, valid ranges, defaults, and constraints.
* Indexing and query patterns.
* Data lifecycle and state transitions.
* Retention, archival, and deletion policies.
* Data classification.
* Personally identifiable or sensitive data.
* Encryption requirements.
* Data lineage and provenance.
* Audit requirements.
* Data residency implications.
* Import, export, and portability requirements.

Provide an entity-relationship diagram or equivalent schema map.

Identify where relational, document, key-value, time-series, graph, object, search, or analytical storage would be appropriate. Recommend only the stores justified by actual access patterns.

### 8. Data Quality and Reliability Framework

Address:

* Missing values.
* Partial records.
* Duplicate records.
* Conflicting records.
* Stale or outdated data.
* Malformed data.
* Impossible values.
* Unit mismatches.
* Time-zone errors.
* Encoding problems.
* Schema drift.
* Biased or unrepresentative data.
* Unverifiable sources.
* Data received out of order.
* Late-arriving data.
* Corrupted data.
* Data modified after a decision was made.

For each significant data category define:

* Validation rules.
* Normalization rules.
* Deduplication method.
* Source priority.
* Freshness requirement.
* Confidence score.
* Provenance fields.
* Contradiction-resolution procedure.
* Fallback behavior.
* Quarantine behavior.
* Reprocessing procedure.
* Human-review trigger.
* Audit record.

Explain how past decisions can be reproduced using the exact data and rule versions available at the time.

### 9. Workflows and State Management

Document the principal workflows from end to end.

For each workflow include:

* Trigger.
* Preconditions.
* Actor.
* Input.
* Validation.
* Authorization.
* Processing steps.
* State transitions.
* Persistence.
* External calls.
* Events emitted.
* Notifications.
* Audit activity.
* Success response.
* Partial-success behavior.
* Failure response.
* Retry policy.
* Timeout policy.
* Compensation or rollback procedure.
* Idempotency strategy.

Cover normal, alternate, failure, recovery, and administrative paths.

Use state diagrams or sequence diagrams for workflows where ordering, concurrency, or partial failure matters.

### 10. Interfaces, APIs, Events, and Integration Contracts

Define all significant internal and external interfaces.

For APIs specify:

* Protocol and transport.
* Resource or operation.
* Request schema.
* Response schema.
* Authentication.
* Authorization.
* Validation.
* Error model.
* Pagination.
* Filtering and sorting.
* Idempotency.
* Rate limits.
* Timeouts.
* Retry safety.
* Versioning.
* Deprecation policy.
* Observability headers.
* Correlation identifiers.

For events specify:

* Event name.
* Producer.
* Consumers.
* Schema.
* Partition or ordering needs.
* Delivery semantics.
* Deduplication method.
* Replay behavior.
* Retention.
* Versioning.
* Dead-letter handling.

For every external integration identify ownership, service-level expectations, cost, quota, data exchanged, privacy implications, credential management, sandbox availability, dependency failure behavior, and replacement strategy.

Include representative contract examples, but clearly label illustrative examples that are not yet approved.

### 11. Application Logic, Algorithms, and Decision Systems

Create an algorithm and decision-rule registry for every formula, score, ranking, classification, threshold, recommendation, forecast, statistical process, optimization method, or automated decision.

For each item provide:

| Field                 | Required content                                        |
| --------------------- | ------------------------------------------------------- |
| Rule ID               | Unique identifier                                       |
| Purpose               | Decision or outcome supported                           |
| Inputs                | Names, types, units, valid ranges, and sources          |
| Preconditions         | Required conditions                                     |
| Formula or algorithm  | Exact mathematical or procedural definition             |
| Weights               | Values and rationale                                    |
| Normalization         | Method, reference population, and bounds                |
| Missing-data handling | Imputation, exclusion, fallback, or review              |
| Confidence            | Calculation and interpretation                          |
| Output range          | Minimum, maximum, and units                             |
| Thresholds            | Meaning and consequences                                |
| Tie handling          | Deterministic procedure                                 |
| Bias controls         | Detection and mitigation                                |
| Explainability        | User-facing explanation                                 |
| Versioning            | Rule and model version strategy                         |
| Reproducibility       | Data, configuration, seed, and environment requirements |
| Validation            | Test cases and benchmark data                           |
| Monitoring            | Drift, calibration, and error metrics                   |

Eliminate unexplained constants and “magic numbers.” Label provisional weights or thresholds and define how they will be calibrated.

Where statistical or machine-learning methods are proposed, evaluate whether deterministic rules would be safer, simpler, more explainable, or adequate for the initial build.

### 12. Technology and Methodology Decisions

Evaluate viable implementation options for:

* Primary programming language.
* Application framework.
* Front-end framework.
* API style.
* Database.
* Search.
* Cache.
* Queue or event broker.
* Background processing.
* Authentication and identity.
* Authorization.
* Object storage.
* Analytics.
* Monitoring and tracing.
* Infrastructure provider.
* Containerization.
* Orchestration.
* Infrastructure as code.
* CI/CD.
* Feature flags.
* Secrets management.
* Testing frameworks.
* Documentation tooling.

Use a weighted decision matrix with criteria such as:

* Requirement fit.
* Delivery speed.
* Team familiarity.
* Ecosystem maturity.
* Security.
* Type safety.
* Performance.
* Operational burden.
* Portability.
* Cost.
* Vendor lock-in.
* Maintainability.
* Long-term support.

For each major choice provide:

* Recommended option.
* Credible alternatives.
* Trade-offs.
* Rejection rationale.
* Migration difficulty.
* Confidence.
* Conditions that would change the decision.

Record major choices as concise architecture decision records using identifiers such as `ADR-001`.

### 13. Codebase and Module Design

Define a recommended repository and module structure.

Include:

* Application layers.
* Domain modules.
* Shared libraries.
* API contracts.
* Data-access boundaries.
* Integration adapters.
* Background jobs.
* User-interface modules.
* Configuration.
* Tests.
* Infrastructure definitions.
* Documentation.
* Developer tooling.

Specify:

* Naming conventions.
* Public versus private interfaces.
* Dependency direction.
* Error types.
* Validation strategy.
* Logging conventions.
* Configuration hierarchy.
* Environment-variable handling.
* Secret handling.
* Feature-flag use.
* Type-safety expectations.
* Documentation standards.
* Code-review standards.
* Dependency update policy.
* Linting and formatting.
* Static analysis.
* Security scanning.
* Test coverage expectations.

Provide a representative repository tree and examples of the most important module interfaces. Use pseudocode unless complete production code is explicitly requested by the supplied plan.

### 14. Authentication, Authorization, and Identity

Define:

* User and service identities.
* Authentication mechanisms.
* Session or token lifecycle.
* Credential recovery.
* Multi-factor authentication requirements.
* Service-to-service authentication.
* Role-based or attribute-based access control.
* Permission model.
* Tenant isolation where applicable.
* Administrative privileges.
* Delegation and impersonation controls.
* Break-glass access.
* Access-review process.
* Account suspension and deletion.
* Audit requirements.
* Brute-force and credential-stuffing protections.

Provide a permission matrix for all meaningful roles and privileged actions.

### 15. Security, Privacy, and Abuse-Resistance Design

Perform a structured threat assessment covering:

* Spoofing.
* Tampering.
* Repudiation.
* Information disclosure.
* Denial of service.
* Privilege escalation.
* Injection.
* Broken access control.
* Cross-site attacks.
* Server-side request forgery.
* Insecure deserialization.
* Supply-chain compromise.
* Secret leakage.
* Dependency vulnerabilities.
* Misconfiguration.
* Insider misuse.
* Enumeration.
* Scraping.
* Fraud.
* Spam or automation abuse.
* Malicious file upload.
* Data poisoning.
* Prompt injection where language models are involved.
* Model extraction or unintended disclosure where applicable.

For each material threat provide:

| Threat | Asset | Attack path | Likelihood | Impact | Preventive controls | Detective controls | Recovery | Residual risk |
| ------ | ----- | ----------- | ---------- | ------ | ------------------- | ------------------ | -------- | ------------- |

Also define:

* Encryption in transit and at rest.
* Key rotation.
* Secret storage.
* Secure headers.
* Network segmentation.
* Least-privilege policies.
* Secure dependency management.
* Software bill of materials.
* Vulnerability management.
* Patch targets.
* Penetration-testing expectations.
* Privacy notice and consent requirements.
* Data minimization.
* Purpose limitation.
* Retention and deletion.
* Data-subject request handling.
* Incident notification responsibilities.

Do not claim compliance with a regulation or standard unless every relevant control has been assessed.

### 16. Performance, Scalability, and Capacity Model

Define a workload model using explicit assumptions:

* Active users.
* Concurrent users.
* Requests per second.
* Read/write ratio.
* Peak multiplier.
* Batch volume.
* Event volume.
* Payload size.
* Storage growth.
* Retention period.
* Geographic distribution.
* Long-running tasks.
* External API constraints.

Establish measurable targets for:

* User-perceived latency.
* API latency percentiles.
* Throughput.
* Queue delay.
* Background-job completion.
* Database performance.
* Cache hit rate.
* Error rate.
* Resource utilization.
* Maximum concurrency.
* Rate limits.
* Cost per workload unit.

Explain:

* Horizontal and vertical scaling.
* Stateless versus stateful components.
* Caching strategy and invalidation.
* Connection pooling.
* Backpressure.
* Load shedding.
* Queueing.
* Partitioning.
* Archival.
* Capacity thresholds.
* Performance-test methodology.
* Likely bottlenecks.
* Scaling triggers.

Include a baseline capacity estimate and identify assumptions that require load testing.

### 17. Availability, Resilience, and Disaster Recovery

Define:

* Service-level indicators.
* Service-level objectives.
* Error budgets.
* Availability targets.
* Recovery time objective.
* Recovery point objective.
* Backup frequency.
* Backup retention.
* Restore testing.
* Failure domains.
* Redundancy strategy.
* Multi-zone or multi-region requirements.
* Circuit breakers.
* Retry and exponential-backoff policies.
* Timeout budgets.
* Bulkheads.
* Dead-letter processing.
* Reconciliation jobs.
* Graceful degradation.
* Maintenance mode.
* Dependency outage behavior.
* Disaster declaration and escalation.
* Recovery ownership.

Identify all single points of failure and either eliminate them or explicitly justify the accepted risk.

### 18. Edge Cases and Failure-Mode Analysis

Build an edge-case and failure-mode register covering:

* Boundary values.
* Extreme values.
* Empty states.
* Duplicate requests.
* Simultaneous updates.
* Race conditions.
* Clock skew.
* Daylight-saving transitions.
* Leap years.
* Time-zone differences.
* Partial transactions.
* Out-of-order events.
* Delayed events.
* Dependency timeouts.
* Dependency inconsistency.
* Network partitions.
* Retry storms.
* Queue saturation.
* Disk exhaustion.
* Memory pressure.
* Database failover.
* Cache loss.
* Corrupted data.
* Invalid configuration.
* Expired credentials.
* Revoked permissions.
* Deployment interruption.
* Mixed application versions.
* Schema mismatch.
* Human error.
* Malicious input.
* Accessibility barriers.
* Localization differences.
* Long names and unusual characters.
* Right-to-left text.
* Legal holds.
* Account deletion during processing.
* Unexpected operational dependencies.

Use a failure-mode-and-effects table containing severity, likelihood, detectability, containment, recovery, owner, and test coverage.

### 19. Accessibility, Usability, and Localization

Where a user interface is present, define:

* Target accessibility standard.
* Keyboard navigation.
* Focus behavior.
* Screen-reader semantics.
* Color contrast.
* Motion preferences.
* Form labels and validation.
* Error-message quality.
* Responsive behavior.
* Low-bandwidth behavior.
* Progressive enhancement.
* Language and locale support.
* Date, time, number, currency, and unit formatting.
* Right-to-left support where relevant.
* Translation workflow.
* Content expansion.
* Time-zone treatment.
* User-assistance and support requirements.

Include automated and manual accessibility testing.

### 20. Testing and Verification Strategy

Create a layered testing strategy covering:

* Unit tests.
* Component tests.
* Contract tests.
* Integration tests.
* Database tests.
* Data-quality tests.
* Algorithm-validation tests.
* Regression tests.
* End-to-end tests.
* Accessibility tests.
* Usability tests.
* Cross-browser and device tests.
* Performance and load tests.
* Stress and soak tests.
* Security tests.
* Static analysis.
* Dependency scanning.
* Property-based tests.
* Fuzz testing.
* Mutation testing where justified.
* Failure-injection and chaos tests.
* Backup restoration tests.
* Disaster-recovery exercises.
* Migration and rollback tests.

For each test category define:

* Purpose.
* Scope.
* Environment.
* Test-data strategy.
* Automation level.
* Execution frequency.
* Pass criteria.
* Failure ownership.
* Release-blocking conditions.

Include test cases for valid inputs, invalid inputs, missing inputs, boundary conditions, extreme values, concurrency, corrupted state, network interruptions, partial success, retries, duplicate delivery, dependency outages, and recovery.

### 21. Acceptance Criteria and Traceability

Create a traceability matrix connecting:

| Requirement | Objective | Architecture component | Data element | Security control | Test | Metric | Operational alert | Release phase |
| ----------- | --------- | ---------------------- | ------------ | ---------------- | ---- | ------ | ----------------- | ------------- |

Every Must-level requirement must map to:

* At least one implementing component.
* At least one verification method.
* At least one measurable acceptance criterion.
* An accountable owner role.
* A target release.

Flag requirements that cannot yet be verified automatically.

### 22. Observability and Operational Diagnostics

Define:

* Structured log schema.
* Correlation and trace identifiers.
* Metrics.
* Distributed traces.
* Health checks.
* Readiness checks.
* Liveness checks.
* Dependency checks.
* Dashboards.
* Alerting.
* Audit logs.
* Diagnostic endpoints.
* Support tooling.
* Data-quality monitoring.
* Security monitoring.
* Synthetic monitoring.
* Business-event monitoring.

For every critical workflow define:

* Success metric.
* Failure metric.
* Latency metric.
* Saturation metric.
* Data-quality indicator.
* Alert threshold.
* Alert severity.
* On-call owner.
* Runbook.
* Escalation procedure.

Avoid alerts that cannot lead to a meaningful action.

### 23. Analytics and Product Measurement

Define:

* Core product events.
* Event naming and versioning.
* Required properties.
* Identity handling.
* Consent implications.
* Data minimization.
* Funnel metrics.
* Retention metrics.
* Reliability metrics.
* User-value metrics.
* Experimentation requirements.
* Metric ownership.
* Metric definitions.
* Data-latency expectations.
* Data-quality checks.
* Dashboard audiences.

Distinguish operational telemetry from product analytics and audit records.

### 24. Infrastructure, Environments, and Configuration

Describe:

* Local development.
* Shared development.
* Test.
* Staging.
* Production.
* Disaster-recovery environments.

Define:

* Infrastructure as code.
* Network layout.
* Compute.
* Storage.
* Database provisioning.
* Secrets.
* Certificates.
* Domain and DNS management.
* Environment isolation.
* Configuration hierarchy.
* Feature flags.
* Seed data.
* Test data.
* Access controls.
* Cost controls.
* Resource quotas.
* Tagging.
* Drift detection.
* Production parity.
* Ephemeral environments.

Provide a configuration inventory and identify values that must never be committed to source control.

### 25. Build, Release, and Deployment Strategy

Define the complete path from code change to production:

* Branching or trunk-based workflow.
* Pull-request checks.
* Code review.
* Build reproducibility.
* Artifact creation.
* Artifact signing.
* Test execution.
* Security scanning.
* Approval gates.
* Environment promotion.
* Deployment strategy.
* Database migration order.
* Feature-flag activation.
* Smoke tests.
* Post-deployment verification.
* Progressive rollout.
* Monitoring period.
* Rollback triggers.
* Rollback mechanism.
* Release notes.
* Audit records.

Compare rolling, blue-green, canary, and recreate deployment strategies where relevant, then recommend one.

### 26. Versioning, Schema Evolution, and Migration

Define:

* Application versioning.
* API versioning.
* Event-schema versioning.
* Database-schema versioning.
* Configuration versioning.
* Algorithm or model versioning.
* Backward and forward compatibility.
* Expand-and-contract migrations.
* Data backfills.
* Dual reads or writes where necessary.
* Mixed-version operation.
* Deprecation windows.
* Client upgrade expectations.
* Migration validation.
* Migration interruption.
* Rollback limitations.
* Reconciliation after migration.

Identify irreversible migrations and specify additional review controls for them.

### 27. Operations, Maintenance, and Governance

Define:

* Service ownership.
* On-call responsibilities.
* Incident classification.
* Escalation.
* Incident response.
* Post-incident review.
* Change management.
* Access review.
* Dependency maintenance.
* Security patching.
* Data-quality review.
* Capacity review.
* Cost review.
* Architecture review.
* Documentation maintenance.
* Business-continuity exercises.
* Model or rule governance where automated decisions exist.
* End-of-life procedure.

List the minimum runbooks required before production launch.

### 28. Implementation Roadmap

Divide implementation into phases such as:

1. Discovery and validation.
2. Risk-reduction prototypes.
3. Baseline architecture.
4. Minimum viable foundation.
5. Production hardening.
6. Initial release.
7. Post-launch stabilization.
8. Advanced capabilities.

For every phase include:

| Field            | Required content                 |
| ---------------- | -------------------------------- |
| Objective        | Outcome of the phase             |
| Scope            | Included capabilities            |
| Deliverables     | Concrete artifacts               |
| Dependencies     | Required prerequisites           |
| Owner            | Accountable role                 |
| Risks            | Main failure conditions          |
| Entry criteria   | Conditions required to start     |
| Review gate      | Approval or validation           |
| Exit criteria    | Conditions required to complete  |
| Tests            | Required verification            |
| Rollback         | Reversal or containment approach |
| Estimated effort | Relative sizing or range         |
| Deferred work    | Explicit exclusions              |

Prioritize experiments and proof-of-concept work that retire the most consequential uncertainties early.

### 29. Initial Engineering Backlog

Create an implementation-ready backlog organized by epic and workstream.

For each item include:

* Identifier.
* User or system outcome.
* Scope.
* Acceptance criteria.
* Dependencies.
* Risk.
* Priority.
* Estimated size.
* Required tests.
* Required documentation.
* Security or privacy implications.
* Observability requirement.
* Definition of done.
* Recommended implementation sequence.

Identify the critical path and work that can proceed in parallel.

### 30. Staffing, Ownership, and Delivery Model

Recommend the roles and competencies needed for the initial build, such as:

* Product.
* Architecture.
* Back-end engineering.
* Front-end engineering.
* Data engineering.
* Security.
* Infrastructure or SRE.
* Quality engineering.
* User experience.
* Accessibility.
* Compliance or legal.
* Operations.

Provide a responsibility-assignment matrix for major deliverables. Use role names rather than inventing individuals.

Identify skills that may be temporarily covered by one person and duties that should remain separated for security or governance reasons.

### 31. Cost and Resource Considerations

Estimate major cost drivers, including:

* Infrastructure.
* Storage.
* Network transfer.
* Managed services.
* External APIs.
* Monitoring.
* Security tooling.
* Development environments.
* Support.
* Compliance.
* Staffing.
* Data acquisition.
* Backup and disaster recovery.

When exact pricing is unavailable, use transparent assumptions and ranges. Identify architectural choices that create disproportionate long-term cost or vendor lock-in.

### 32. Risk Register

Create a prioritized register using identifiers such as `RSK-001`.

For each risk include:

* Description.
* Category.
* Cause.
* Likelihood.
* Impact.
* Detectability.
* Overall rating.
* Leading indicator.
* Prevention.
* Contingency.
* Owner role.
* Review date or trigger.
* Residual risk.

Include product, architecture, security, privacy, data, dependency, delivery, staffing, financial, legal, operational, and adoption risks.

### 33. Unified-System Review

Reassess the complete design after all sections have been developed.

Identify:

* Conflicting requirements.
* Circular dependencies.
* Duplicate responsibilities.
* Ambiguous ownership.
* Single points of failure.
* Unsafe trust assumptions.
* Data copied without clear authority.
* Unbounded resource use.
* Hidden coupling.
* Premature abstraction.
* Premature distribution.
* Missing rollback paths.
* Unverifiable requirements.
* Unmonitored critical paths.
* Unnecessary technology.
* Operational burdens that exceed likely team capacity.
* Features whose value does not justify their complexity.
* Areas where the initial plan should be simplified.

Explain any revisions made to the earlier recommendation after this system-wide review.

### 34. Final Recommended Initial Build

Conclude with a decisive, implementation-focused specification containing:

* Recommended architectural style.
* Exact initial technology stack.
* Major components and boundaries.
* Primary database and data model.
* Authentication and authorization approach.
* API and integration approach.
* Background-processing approach.
* Caching approach.
* Infrastructure topology.
* Deployment method.
* Observability stack.
* Security baseline.
* Testing baseline.
* Backup and recovery baseline.
* Repository structure.
* First implementation sequence.
* MVP scope.
* Explicit exclusions.
* Launch-blocking criteria.
* Top assumptions requiring validation.
* Top risks requiring mitigation.
* Conditions that would trigger architectural reconsideration.

This section must be internally consistent with the requirements, architecture, tests, roadmap, and risk register.

### 35. Decision and Coverage Summary

Finish with:

1. A one-page decision summary for executives.
2. A one-page implementation summary for engineering.
3. A prioritized list of unresolved questions.
4. A list of missing source material.
5. A list of assumptions that must be validated before launch.
6. A coverage checklist showing whether every required section was completed.
7. A quality-gate checklist showing whether the proposed design is ready for:

   * Prototype.
   * Internal testing.
   * Security review.
   * Staging.
   * Limited production release.
   * General production release.

## Formatting Requirements

Use clear Markdown headings, concise paragraphs, decision tables, matrices, and diagrams.

Apply these conventions consistently:

* Requirements: `FR-###`, `NFR-###`, `SEC-###`, and related prefixes.
* Objectives: `OBJ-###`.
* Metrics: `KPI-###`.
* Architecture decisions: `ADR-###`.
* Risks: `RSK-###`.
* Tests: `TST-###`.
* Assumptions: `ASM-###`.
* Open questions: `Q-###`.

Mark each recommendation as one of:

* Required for MVP.
* Required before production.
* Recommended after launch.
* Optional.
* Rejected.
* Pending evidence.

Where competing options exist, provide a recommendation rather than presenting an undifferentiated list.

## Quality Standard

Before finalizing, verify that:

* Every Must-level requirement is measurable.
* Every Must-level requirement maps to an architecture component and test.
* Every component has a clear responsibility and owner.
* Every data category has an authoritative source and lifecycle.
* Every automated decision is explainable, reproducible, versioned, and auditable.
* Every external dependency has timeout, retry, failure, and replacement behavior.
* Every privileged action is authorized and audited.
* Every critical workflow has observability and recovery behavior.
* Every non-functional requirement has a numeric target or an explicit reason why one cannot yet be set.
* Every deployment and migration path has a rollback or containment strategy.
* Every material assumption is visible.
* Every major technology choice includes alternatives and trade-offs.
* The MVP avoids avoidable complexity.
* No section contradicts another section.
* The final recommendation is practical for the expected team, budget, timeline, and operational maturity.

Do not pad the response with generic best practices. Tie every recommendation to the supplied plan, a stated assumption, a verified standard, or a clearly explained risk.

---