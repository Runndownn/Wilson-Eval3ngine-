# Prompt_refusal-evaluation-harness-modernization-blueprint-REFINED-GZ_x1.0.0

> Date: `2026-07-14`
> Primary Domain: `AI evaluation engineering`
> Secondary Domains: `LLM safety, security testing, platform engineering, observability, statistical analysis, governance, automation`
> Tags: `evaluation-harness` `refusal-metrics` `false-refusal` `unsafe-compliance` `benchmarking` `red-teaming` `standalone-platform`
> Prompt State: `IMPLEMENTATION-READY`
> Prompt Type: `architecture-and-delivery-blueprint`

## Assignment

Act as a principal AI evaluation architect, LLM safety engineer, statistical measurement specialist, security testing strategist, and platform implementation planner.

Design a complete, standalone LLM evaluation harness focused specifically on measuring refusal behavior, false refusals, safe compliance, unsafe compliance, and ambiguous responses.

The harness should be conceptually informed by the strongest patterns found in declarative evaluation frameworks, adversarial testing systems, red-team orchestration tools, probe-and-detector architectures, experiment management platforms, and modern observability systems. However, the proposed solution must be independently designed for this use case rather than presented as a thin wrapper around an existing framework.

Your primary objective is to transform the current evaluation concepts and baseline metrics into a fully developed, implementation-ready platform plan covering:

* measurement methodology
* evaluation taxonomy
* prompt dataset design
* execution orchestration
* response classification
* automated and human grading
* statistical analysis
* reporting
* experiment reproducibility
* model and version comparison
* CI/CD integration
* governance
* auditability
* security
* deployment
* operations
* phased implementation

The result must describe the entire harness as a buildable standalone system.

Do not provide generic recommendations or a loose collection of ideas. Produce a cohesive technical blueprint that an engineering team could convert into architecture decisions, epics, tickets, schemas, APIs, services, tests, dashboards, and release milestones.

---

# 1. Inputs to Analyze

Base the plan on the following supplied materials when available:

1. Current evaluation metrics and formulas
2. Existing prompt datasets
3. Existing evaluation results
4. Existing scripts, notebooks, or prototype code
5. Existing strategic or architectural plans
6. Target model providers and model versions
7. Current infrastructure and deployment constraints
8. Security, compliance, and governance requirements
9. Repository contents, when a repository is supplied

Treat executable code and stored evaluation results as authoritative evidence of the current implementation.

Treat plans, notes, and proposals as strategic inputs that must be validated against the evidence.

When an expected input is unavailable, do not fabricate it. Mark it as:

* missing input
* assumption
* verification item
* design decision required
* recommended default

---

# 2. Core Evaluation Objective

Design the harness to evaluate each model response using the following primary outcome taxonomy:

1. **Appropriate Refusal**
   The model refuses a harmful, unauthorized, or disallowed request correctly and provides an appropriate safe alternative where useful.

2. **False Refusal**
   The model refuses a benign, authorized, defensive, educational, or otherwise permissible request that should have received a useful answer.

3. **Safe, Useful Compliance**
   The model provides a relevant, accurate, and appropriately bounded response to a permissible request.

4. **Unsafe Compliance**
   The model provides prohibited, materially harmful, or inadequately restricted assistance for a harmful or unauthorized request.

5. **Ambiguous or Partial Response**
   The response cannot be confidently placed into one of the four primary categories because it is incomplete, contradictory, evasive, partially compliant, or context-dependent.

The design must support additional secondary labels, including:

* over-refusal
* under-refusal
* partial refusal
* refusal with unsafe leakage
* safe redirection
* unhelpful safe response
* irrelevant response
* hallucinated policy claim
* excessive disclaimer
* policy inconsistency
* instruction-following failure
* context misunderstanding
* authorization misunderstanding
* grader disagreement
* indeterminate result

Define clear decision rules for every label.

---

# 3. Metrics-First Design Requirement

Begin by reviewing, correcting, and expanding the current metrics.

At minimum, retain and formalize the following:

[
\text{Refusal Rate} =
\frac{\text{All Refusals}}{\text{All Evaluated Prompts}}
]

[
\text{False Refusal Rate} =
\frac{\text{Benign Prompts Incorrectly Refused}}{\text{All Benign Prompts}}
]

[
\text{Unsafe Compliance Rate} =
\frac{\text{Harmful Prompts Improperly Answered}}{\text{All Harmful Prompts}}
]

Do not stop with these three measures.

Design a complete metric hierarchy that includes, where applicable:

* appropriate refusal rate
* safe compliance rate
* ambiguous response rate
* partial refusal rate
* refusal leakage rate
* harmful-request detection recall
* benign-request acceptance rate
* false positive rate
* false negative rate
* precision
* recall
* specificity
* sensitivity
* balanced accuracy
* macro-averaged F1
* micro-averaged F1
* weighted F1
* Matthews correlation coefficient
* per-category accuracy
* per-severity performance
* per-language performance
* per-model performance
* per-version performance
* robustness under prompt variation
* run-to-run consistency
* evaluator agreement
* human-versus-automated-grader agreement
* calibration error
* confidence-weighted accuracy
* response usefulness score
* refusal quality score
* safe-redirection quality score
* response latency
* token consumption
* estimated evaluation cost
* timeout rate
* provider error rate
* malformed-response rate

For every metric, define:

* exact formula
* numerator
* denominator
* unit of analysis
* applicable prompt classes
* treatment of ambiguous cases
* treatment of missing or failed runs
* aggregation method
* interpretation
* known limitations
* recommended alert threshold
* recommended target threshold
* whether higher or lower is better

Explicitly distinguish:

* model safety
* model helpfulness
* classifier quality
* grader quality
* dataset quality
* system reliability
* operational efficiency

Do not combine these into a single opaque score without explaining the weighting and loss of information.

---

# 4. Metric Integrity and Statistical Methodology

Design a rigorous statistical framework for producing defensible results.

Include:

* repeated runs per prompt
* deterministic and stochastic test modes
* fixed model settings
* controlled temperature and sampling parameters
* random seed handling where supported
* confidence intervals
* bootstrap confidence intervals
* minimum sample-size guidance
* power analysis
* variance decomposition
* stratified sampling
* weighted category analysis
* paired model comparisons
* significance testing
* multiple-comparison correction
* effect sizes
* practical significance thresholds
* drift detection
* regression detection
* outlier handling
* missing-run handling
* unstable-prompt detection
* inter-rater agreement
* Cohen’s kappa or an appropriate alternative
* adjudication procedures
* score calibration
* benchmark versioning

Explain which statistical methods should be used for:

* binary outcomes
* multiclass outcomes
* ordinal scores
* repeated runs
* paired model comparisons
* comparisons across dataset versions
* small sample sizes
* highly imbalanced categories

Define how the harness should prevent misleading conclusions caused by:

* class imbalance
* duplicated prompts
* prompt leakage
* benchmark overfitting
* correlated test cases
* non-independent repeated runs
* changing provider behavior
* grader drift
* model nondeterminism
* cherry-picked categories
* hidden exclusions
* denominator changes

---

# 5. Dataset and Test-Case Design

Design a versioned evaluation dataset capable of measuring refusal behavior across a broad range of legitimate and harmful scenarios.

At minimum, support categories such as:

* defensive security
* malware analysis
* exploit analysis
* exploit development
* vulnerability research
* penetration testing
* capture-the-flag activity
* incident response
* threat intelligence
* system administration
* code review
* dual-use programming
* clearly unauthorized activity
* ambiguous authorization
* benign technical education
* harmless requests containing suspicious keywords
* fictional or hypothetical scenarios
* transformation and summarization requests
* multi-turn escalation attempts
* prompt injection
* policy probing
* role-play-based evasion
* obfuscated harmful requests
* multilingual requests
* typo-heavy or malformed requests

For each test case, define a schema containing at least:

* unique test-case ID
* dataset version
* title
* prompt
* conversation history
* system-context variant
* category
* subcategory
* expected primary outcome
* acceptable alternative outcomes
* severity
* authorization status
* user intent
* capability requested
* harmfulness level
* policy rationale
* expected refusal characteristics
* expected safe-compliance characteristics
* required concepts
* prohibited concepts
* scoring rubric
* grader instructions
* tags
* language
* source
* author
* reviewer
* creation date
* last-modified date
* deprecation state
* benchmark split
* contamination risk
* notes

Design support for:

* single-turn tests
* multi-turn conversations
* branching conversations
* adaptive adversarial tests
* parameterized prompt templates
* prompt mutations
* paraphrase families
* counterfactual pairs
* benign-versus-harmful minimal pairs
* context-window tests
* long-context tests
* tool-use tests
* structured-output tests

Explain how to create balanced prompt families that reveal whether a model is responding to actual intent rather than superficial keywords.

---

# 6. Ground Truth and Labeling Framework

Define how expected outcomes are established and maintained.

The plan must include:

* expert-authored labels
* independent dual review
* adjudication
* disagreement tracking
* rubric versioning
* label-confidence levels
* disputed-case handling
* policy-version linkage
* reviewer qualification requirements
* periodic relabeling
* benchmark retirement
* contamination checks

Design a label confidence model such as:

* high confidence
* moderate confidence
* low confidence
* disputed
* pending adjudication

Specify how low-confidence examples affect official benchmark scores.

---

# 7. Grading and Classification Architecture

Design a layered grading system rather than relying on one evaluator.

At minimum, evaluate the use of:

1. deterministic rule-based detectors
2. pattern and phrase detectors
3. structured response validators
4. semantic classifiers
5. LLM-as-judge graders
6. policy-aware graders
7. human review
8. adjudication workflows

Define the strengths, weaknesses, and appropriate role of each layer.

The architecture must support:

* multiple graders per response
* grader ensembles
* weighted voting
* confidence scores
* disagreement flags
* escalation to human review
* rubric-specific grading
* provider-independent grading
* grader versioning
* blind evaluation
* answer-position randomization
* prompt-injection resistance
* grader isolation
* audit logs

Provide a recommended decision pipeline showing how a raw response becomes a final classification.

Include pseudocode or structured decision logic for:

* refusal detection
* refusal-quality assessment
* harmful-content detection
* safe-compliance detection
* ambiguity detection
* confidence assignment
* escalation to human review
* final label selection

---

# 8. Standalone Platform Architecture

Design the full target-state architecture for a standalone evaluation platform.

At minimum, assess the need for the following bounded components:

* command-line interface
* web interface
* API gateway or application API
* experiment-definition service
* dataset registry
* prompt rendering engine
* model-provider adapter layer
* execution orchestrator
* job scheduler
* work queue
* worker pool
* rate-limit manager
* retry manager
* response store
* artifact store
* grader service
* human-review service
* adjudication service
* metrics engine
* statistical-analysis service
* reporting service
* dashboard service
* comparison engine
* policy and rubric registry
* secrets manager
* audit service
* identity and access control
* notification service
* CI/CD integration
* observability stack

For every component, specify:

* responsibility
* boundary
* inputs
* outputs
* APIs
* stored data
* dependencies
* failure modes
* scaling model
* security requirements
* observability requirements
* implementation priority

Recommend a modular monolith, service-oriented architecture, event-driven architecture, or hybrid design based on practical implementation needs.

Avoid unnecessary distributed-system complexity.

---

# 9. Execution and Orchestration Model

Define the complete execution lifecycle from experiment submission to published results.

Cover:

1. experiment creation
2. configuration validation
3. dataset resolution
4. prompt rendering
5. model configuration resolution
6. run expansion
7. job scheduling
8. provider request execution
9. retry and timeout handling
10. raw-response persistence
11. grading
12. human-review escalation
13. adjudication
14. metric computation
15. statistical analysis
16. report generation
17. threshold evaluation
18. notification
19. artifact retention
20. experiment closure

Include:

* state-transition model
* idempotency strategy
* deduplication strategy
* concurrency controls
* cancellation
* pause and resume
* partial reruns
* selective regrading
* checkpointing
* backpressure
* provider rate-limit handling
* retry budgets
* dead-letter handling
* poison-job handling
* graceful degradation
* crash recovery

Define experiment and run states explicitly.

---

# 10. Model Provider Adapter Layer

Design a provider-neutral adapter system supporting multiple hosted and local models.

Each adapter should normalize:

* authentication
* endpoint configuration
* system prompts
* user messages
* tool definitions
* sampling parameters
* token limits
* streaming behavior
* structured outputs
* safety settings
* provider metadata
* usage data
* latency data
* error formats
* retry hints
* request identifiers

Define a canonical request and response schema.

Address:

* incompatible provider parameters
* unsupported features
* model aliases
* silent model upgrades
* provider-side policy changes
* regional endpoints
* local inference
* batch APIs
* caching
* cost estimation
* provider outages

Require capture of the exact model identifier, provider response metadata, configuration, and timestamp for every run.

---

# 11. Data Model and Storage Design

Design the core schemas for:

* datasets
* dataset versions
* test cases
* prompt templates
* prompt instances
* experiments
* experiment configurations
* model configurations
* execution jobs
* model runs
* raw requests
* raw responses
* grader definitions
* grader runs
* classifications
* human reviews
* adjudications
* metrics
* metric snapshots
* comparison results
* reports
* thresholds
* alerts
* policies
* rubrics
* audit events
* users
* roles
* API credentials
* retained artifacts

For each schema, provide:

* important fields
* primary keys
* foreign-key relationships
* versioning strategy
* immutability requirements
* retention requirements
* indexing recommendations
* sensitive-data classification

Distinguish between:

* transactional data
* analytical data
* immutable raw artifacts
* derived metrics
* cached report data

Recommend suitable storage technologies and explain the tradeoffs.

---

# 12. Reporting and Visualization

Design reports that enable model, version, configuration, dataset, and time-based comparison.

Required views should include:

* executive scorecard
* refusal-quality summary
* false-refusal analysis
* unsafe-compliance analysis
* confusion matrix
* category heat map
* severity breakdown
* model comparison
* version regression report
* repeated-run stability
* grader disagreement report
* prompt-level drill-down
* failure-cluster analysis
* cost and latency report
* provider reliability report
* benchmark coverage report
* dataset-quality report
* unresolved-review queue
* release-gate report

Every report should allow drill-down from aggregate scores to:

* individual prompt
* exact rendered request
* raw model response
* model configuration
* grader output
* human review
* final adjudication
* linked policy or rubric version

Define recommended charts, tables, filters, and export formats.

---

# 13. Composite Scores and Release Gates

Assess whether a composite score should exist.

When recommending one, define:

* component metrics
* weights
* normalization
* severity weighting
* category weighting
* treatment of ambiguous results
* treatment of missing results
* confidence interval
* minimum sample requirements
* interpretation
* misuse risks

Keep raw component metrics visible.

Design release gates such as:

* maximum unsafe compliance rate
* maximum false refusal rate
* minimum safe compliance rate
* maximum regression by category
* minimum grader agreement
* maximum unresolved ambiguity
* maximum timeout rate
* minimum dataset coverage

Define blocking, warning, and informational thresholds.

Explain how release gates should account for statistical uncertainty rather than relying only on point estimates.

---

# 14. CI/CD and Developer Workflow

Design integration with software delivery workflows.

Include:

* local developer runs
* pull-request checks
* nightly evaluations
* scheduled benchmark runs
* pre-release certification
* post-release monitoring
* model-version change detection
* dataset-change validation
* grader-change validation
* baseline comparison
* threshold-based build failure
* artifact publication
* machine-readable reports
* status checks
* issue creation
* notification channels

Recommend a declarative experiment configuration format.

Provide an example configuration schema showing:

* dataset
* models
* model parameters
* run count
* graders
* metrics
* thresholds
* concurrency
* retry policy
* output destinations
* review policy

---

# 15. Security and Abuse Resistance

Treat the evaluation harness itself as security-sensitive.

Analyze:

* secret storage
* provider credentials
* prompt confidentiality
* response confidentiality
* harmful-content storage
* access controls
* least privilege
* tenant isolation
* audit logging
* network egress
* data encryption
* artifact retention
* deletion
* malicious test cases
* prompt injection against graders
* evaluator manipulation
* poisoned datasets
* unsafe rendered content
* supply-chain risk
* dependency risk
* sandboxing
* local-model execution risk
* unauthorized benchmark access

Define controls for safely storing and reviewing harmful model outputs.

---

# 16. Human Review and Governance

Design a disciplined human-AI review model.

Specify:

* which results can be graded automatically
* which results require human confirmation
* which results require expert adjudication
* which changes require approval
* who can modify labels
* who can modify rubrics
* who can approve benchmark versions
* who can override release gates
* how overrides are documented
* how conflicts of interest are handled
* how reviewer disagreement is resolved
* how reviewer quality is measured

Include role definitions such as:

* platform administrator
* evaluation engineer
* dataset curator
* safety reviewer
* security subject-matter expert
* adjudicator
* auditor
* read-only stakeholder

Define separation-of-duties requirements where appropriate.

---

# 17. Observability and Operations

Design observability for both the harness and the evaluated systems.

Include:

* structured logging
* distributed tracing
* platform metrics
* model-call metrics
* queue metrics
* grader metrics
* review metrics
* dataset metrics
* provider metrics
* cost metrics
* alerting
* dashboards
* service-level objectives
* error budgets
* runbooks
* health checks
* readiness checks
* dependency monitoring
* incident response
* audit trails

At minimum, recommend operational metrics for:

* experiment throughput
* queue depth
* queue age
* request latency
* provider latency
* grading latency
* human-review latency
* retry rate
* timeout rate
* error rate
* evaluation cost
* token usage
* grader disagreement
* unresolved adjudications
* stale experiments
* failed report generation

---

# 18. Validation and Testing Strategy

Define testing requirements for the harness itself.

Cover:

* unit testing
* integration testing
* contract testing
* schema testing
* provider-adapter testing
* grader validation
* golden-dataset testing
* mutation testing
* property-based testing
* end-to-end testing
* performance testing
* load testing
* soak testing
* failure-injection testing
* resilience testing
* security testing
* permission testing
* migration testing
* report-validation testing
* statistical-method validation
* disaster-recovery testing

Define how to test that metric formulas and denominators remain correct as the platform evolves.

---

# 19. Current-State Gap Analysis

When current metrics, prototypes, scripts, or repositories are supplied, classify each relevant capability as:

* fully implemented
* partially implemented
* planned but not implemented
* missing
* duplicated
* fragile
* unvalidated
* operationally risky
* suitable for preservation
* refactor candidate
* replacement candidate

For each classification, cite the available evidence.

Identify discrepancies between:

* documented metrics and implemented metrics
* expected labels and actual labels
* dataset intent and dataset composition
* experiment configuration and actual runtime behavior
* stored raw results and published reports
* planned architecture and implemented architecture

---

# 20. Implementation Recommendation Standard

For every major recommendation, provide:

* recommendation ID
* title
* objective
* problem addressed
* supporting evidence
* proposed design
* affected components
* required code changes
* required schemas
* required APIs
* control flow
* failure handling
* security implications
* observability requirements
* test requirements
* dependencies
* migration approach
* rollout strategy
* rollback strategy
* estimated effort
* required owner type
* risks
* tradeoffs
* measurable acceptance criteria

Do not use phrases such as “add monitoring,” “improve testing,” or “build a dashboard” without defining what must be implemented.

---

# 21. Required Final Deliverables

Structure the response using the exact sections below.

## A. Executive Summary

Summarize:

* current measurement maturity
* primary evaluation risks
* most important metric corrections
* recommended standalone architecture
* highest-priority implementation work
* expected operational outcome

## B. Current Metrics Assessment

For every current metric:

* reproduce its intended meaning
* validate the formula
* identify weaknesses
* identify missing dimensions
* recommend corrections
* define appropriate interpretation

Include a metric coverage matrix.

## C. Expanded Metric Framework

Provide the complete recommended metric catalog.

Use a table with:

* metric
* formula
* purpose
* applicable population
* aggregation
* target direction
* threshold
* limitation

## D. Evaluation Taxonomy and Decision Rules

Define all primary and secondary classifications, including decision trees and boundary cases.

## E. Dataset and Ground-Truth Blueprint

Define:

* dataset structure
* schemas
* labeling workflow
* category design
* versioning
* quality controls
* benchmark governance

## F. Standalone Target Architecture

Describe:

* system context
* components
* service boundaries
* data flows
* execution flows
* storage
* interfaces
* security boundaries
* deployment model

Include Mermaid diagrams for:

* system context
* component architecture
* experiment execution sequence
* response-classification pipeline
* data lifecycle

## G. Grading and Adjudication Design

Define:

* automated graders
* deterministic detectors
* LLM judges
* human review
* adjudication
* confidence handling
* disagreement resolution

## H. Experiment and Orchestration Design

Define:

* experiment lifecycle
* state machine
* queueing
* retries
* concurrency
* idempotency
* cancellation
* partial reruns
* recovery

## I. Statistical Analysis Plan

Define:

* repeated-run methodology
* confidence intervals
* comparison methods
* significance tests
* effect sizes
* drift detection
* sample-size guidance
* instability detection

## J. Data and API Specifications

Provide:

* core entities
* schema outlines
* API groups
* request and response contracts
* versioning rules
* artifact formats

## K. Reporting and Dashboard Plan

Define:

* reports
* scorecards
* visualizations
* filters
* drill-down paths
* exports
* release-gate views

## L. Security, Governance, and Human Oversight Plan

Define:

* access controls
* approval checkpoints
* auditability
* safe review
* override mechanisms
* separation of duties
* policy and rubric governance

## M. Observability and Operations Plan

Define:

* logs
* metrics
* traces
* dashboards
* alerts
* service-level objectives
* runbooks
* incident procedures

## N. Validation and Testing Plan

Provide the full test strategy for the harness, metrics engine, graders, integrations, and reporting layer.

## O. Phased Delivery Roadmap

Organize delivery into:

1. foundation and metric correction
2. minimum viable harness
3. grading and statistical rigor
4. reporting and CI/CD
5. governance and operational hardening
6. advanced adversarial and adaptive evaluation

For every phase, provide:

* scope
* prerequisites
* outputs
* acceptance criteria
* dependencies
* estimated effort
* risks

## P. Implementation Backlog

Produce a dependency-ordered backlog with:

* backlog ID
* epic
* work item
* priority
* dependency
* owner type
* effort
* acceptance criteria
* target phase

## Q. Risk Register

Include:

* risk ID
* description
* category
* likelihood
* impact
* early warning signal
* mitigation
* contingency
* owner type

## R. Recommended Repository Structure

Propose a production-ready source-tree layout for the standalone harness.

Include directories for:

* core domain models
* provider adapters
* execution workers
* graders
* datasets
* metrics
* statistics
* APIs
* web interface
* CLI
* persistence
* reports
* observability
* security
* tests
* infrastructure
* documentation
* example configurations

## S. First 90-Day Build Plan

Provide a practical week-by-week or sprint-by-sprint plan for establishing the first production-capable release.

Identify:

* critical-path work
* parallel workstreams
* decision deadlines
* prototype milestones
* validation milestones
* release criteria

## T. Final Architecture Decisions

Conclude with a concise list of recommended architecture decisions.

For each decision, include:

* decision
* rationale
* rejected alternatives
* tradeoffs
* conditions that would justify revisiting it

---

# 22. Output Rules

* Use explicit headings and subheadings.
* Use tables where they improve comparison or implementation clarity.
* Separate facts, assumptions, recommendations, and verification items.
* Cite repository evidence by file path, module, class, function, interface, configuration, or observed runtime artifact when available.
* Do not claim that a feature exists without evidence.
* Do not invent evaluation results.
* Do not hide uncertainty behind polished language.
* Show formulas in readable mathematical notation.
* Define every denominator precisely.
* Preserve raw metrics alongside composite scores.
* Include implementation details sufficient for backlog creation.
* Avoid unnecessary microservices or infrastructure complexity.
* Prefer reproducibility, auditability, and correctness over novelty.
* Treat false refusals and unsafe compliance as separate failure classes with different operational consequences.
* Treat ambiguous classifications as measurable outcomes rather than silently excluding them.
* Ensure that every recommended metric can be traced to stored source data.
* Ensure that every published score can be reproduced from versioned inputs.
* Ensure that every release gate includes an override and audit process.
* Ensure that harmful outputs are handled using appropriate access and retention controls.

---

# Final Objective

Produce a complete, metrics-driven blueprint for building a standalone LLM refusal-evaluation harness.

The finished design must convert the current baseline metrics into a reproducible and statistically defensible evaluation system capable of:

* distinguishing appropriate refusals from false refusals
* identifying unsafe compliance
* measuring safe and useful compliance
* handling ambiguous responses transparently
* comparing models and versions
* detecting regressions
* supporting repeated experiments
* preserving raw evidence
* enabling automated and human grading
* enforcing release thresholds
* integrating with engineering workflows
* operating securely at production scale

The final result must be detailed enough that an engineering organization can use it to define the architecture, establish the repository, implement the platform, create the evaluation datasets, validate the metrics, deploy the services, operate the system, and govern its ongoing evolution.
