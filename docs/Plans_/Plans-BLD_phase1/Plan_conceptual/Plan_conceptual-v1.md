# Standalone LLM Refusal-Evaluation Harness: Metrics-to-Platform Implementation Blueprint

**Document date:** July 14, 2026
**Primary domain:** AI evaluation engineering
**Supporting domains:** LLM safety, red teaming, statistical measurement, platform engineering, observability, governance, security, and automation
**Required maturity:** Implementation-ready
**Primary emphasis:** Transform the current metrics, formulas, datasets, results, and prototypes into a fully developed plan for building and operating the complete standalone harness

## Role

Act as a principal AI evaluation architect, LLM safety engineer, statistical measurement specialist, security testing strategist, data architect, and platform implementation planner.

Your task is to analyze the current evaluation metrics and supporting materials, correct their weaknesses, expand them into a complete measurement system, and design the full standalone platform required to collect, classify, analyze, report, govern, and operationalize those metrics.

The result must be a cohesive engineering and delivery blueprint—not a high-level concept paper, generic recommendation list, or description of existing tools.

The plan must be detailed enough for an engineering organization to convert directly into:

* architecture decisions
* service and module boundaries
* database schemas
* APIs and contracts
* experiment configurations
* dataset specifications
* grading pipelines
* statistical procedures
* implementation epics
* development tickets
* CI/CD gates
* dashboards
* operational runbooks
* security controls
* deployment milestones
* release criteria

## Central Objective

Begin with the current metrics and existing implementation evidence.

Use them as the foundation for designing a complete, reproducible, statistically defensible, and operationally secure refusal-evaluation platform.

The final system must measure and distinguish:

1. Appropriate refusal
2. False refusal
3. Safe and useful compliance
4. Unsafe compliance
5. Ambiguous or partial response

The platform must also preserve secondary behavioral signals, including:

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

Treat false refusals, unsafe compliance, ambiguity, reliability failures, and grader failures as separate operational concerns. Do not conceal them inside one aggregate score.

---

# 1. Evidence and Input Analysis

Analyze all supplied materials, including where available:

1. Current metric definitions and formulas
2. Current metric implementation code
3. Existing prompt datasets
4. Existing evaluation results
5. Current scripts, notebooks, services, or prototypes
6. Existing architecture and strategy documents
7. Target model providers and model versions
8. Current infrastructure and deployment constraints
9. Security, compliance, and governance requirements
10. Repository contents and runtime artifacts
11. Existing dashboards, reports, or exported result files
12. Current CI/CD workflows
13. Current human-review procedures
14. Existing policy and rubric definitions

Use the following evidence precedence:

1. Executable code and persisted runtime artifacts
2. Database schemas and generated reports
3. Automated tests
4. Deployed configuration
5. Repository documentation
6. Strategic plans, notes, and proposals

Do not assume that documented behavior exists in the implementation.

For every material finding, classify it as one of:

* verified fact
* inferred behavior
* assumption
* missing input
* verification item
* recommended default
* design decision required

When repository or implementation evidence is supplied, cite the exact file path, module, class, function, schema, configuration, test, or stored artifact supporting the conclusion.

Do not invent missing metrics, results, features, integrations, infrastructure, or historical performance.

---

# 2. Metrics-First Transformation

The blueprint must begin by turning the current metrics into executable, versioned metric contracts.

At minimum, validate and formalize:

[
\text{Refusal Rate}
===================

\frac{\text{All Refusal Responses}}
{\text{All Behaviorally Scorable Responses}}
]

[
\text{False Refusal Rate}
=========================

\frac{\text{Permissible Requests Incorrectly Refused}}
{\text{All Permissible Requests Expected to Receive Compliance}}
]

[
\text{Unsafe Compliance Rate}
=============================

\frac{\text{Harmful Requests Receiving Materially Unsafe Assistance}}
{\text{All Harmful Requests Expected to Receive Refusal or Strict Limitation}}
]

Do not merely restate these formulas.

For each current metric:

1. Reconstruct its intended meaning.
2. Identify the current numerator and denominator.
3. Determine whether the implementation matches the documented formula.
4. Identify hidden exclusions.
5. Identify ambiguous-case handling.
6. Identify failed-run handling.
7. Identify aggregation behavior.
8. Identify class-imbalance sensitivity.
9. Identify whether repeated runs are treated as independent.
10. Identify whether prompt variants are improperly counted as independent.
11. Identify whether the metric is suitable for release decisions.
12. Recommend a corrected formula and migration path.
13. Define tests that prevent future denominator drift.

Every metric must become a versioned metric definition containing:

* metric ID
* metric version
* display name
* formal mathematical formula
* numerator definition
* denominator definition
* unit of analysis
* eligible population
* exclusion rules
* missing-run treatment
* ambiguity treatment
* aggregation method
* confidence-interval method
* stratification dimensions
* interpretation
* known limitations
* warning threshold
* blocking threshold
* target direction
* minimum sample requirement
* required source fields
* source-data lineage requirements
* metric owner
* approval status

---

# 3. Complete Metric Hierarchy

Expand the baseline metrics into a complete hierarchy covering the following dimensions.

## 3.1 Model Safety

Include:

* appropriate refusal rate
* unsafe compliance rate
* severity-weighted unsafe compliance rate
* refusal leakage rate
* harmful-request detection recall
* harmful-request false-negative rate
* unsafe tool-action rate
* critical-severity failure rate
* safe-redirection rate
* policy-consistency rate
* authorization-handling accuracy

## 3.2 Model Helpfulness

Include:

* false refusal rate
* benign-request acceptance rate
* safe and useful compliance rate
* unhelpful safe-response rate
* excessive-disclaimer rate
* irrelevant-response rate
* instruction-adherence score
* response usefulness score
* safe-redirection quality score
* refusal quality score

## 3.3 Classification Performance

Include:

* false positive rate
* false negative rate
* precision
* recall
* specificity
* sensitivity
* balanced accuracy
* per-class precision
* per-class recall
* per-class F1
* macro-averaged F1
* micro-averaged F1
* weighted F1
* Matthews correlation coefficient
* multiclass confusion matrix
* ordinal-score agreement
* calibration error
* Brier score
* confidence-weighted accuracy

## 3.4 Robustness and Stability

Include:

* prompt-family robustness
* minimal-pair correctness
* counterfactual sensitivity
* paraphrase consistency
* multilingual consistency
* run-to-run agreement
* outcome entropy
* repeated-run variance
* context-length robustness
* prompt-mutation robustness
* model nondeterminism rate
* unstable-prompt rate

## 3.5 Grader Quality

Include:

* automated-grader agreement
* human inter-rater agreement
* human-versus-automated agreement
* grader disagreement rate
* human-escalation rate
* adjudication-overturn rate
* grader abstention rate
* grader calibration error
* grader drift
* grader injection-resistance performance
* per-category grader accuracy
* per-severity grader recall

## 3.6 Dataset Quality

Include:

* category coverage
* subcategory coverage
* severity coverage
* language coverage
* authorization-state coverage
* benchmark split balance
* duplicate rate
* near-duplicate rate
* prompt-family imbalance
* contamination-risk rate
* stale-policy-linkage rate
* disputed-label rate
* reviewer-completeness rate
* benchmark retirement rate
* unresolved-adjudication count

## 3.7 Reliability and Operations

Include:

* timeout rate
* provider error rate
* malformed-response rate
* retry rate
* exhausted-retry rate
* queue depth
* queue age
* execution throughput
* provider latency
* end-to-end latency
* grading latency
* human-review latency
* report-generation failure rate
* stale-experiment count
* job duplication rate
* lost-job rate
* artifact-integrity failure rate

## 3.8 Cost and Efficiency

Include:

* input token consumption
* output token consumption
* reasoning token consumption where available
* evaluation cost
* grading cost
* cost per scorable run
* cost per prompt family
* cost per completed experiment
* cost per confirmed failure
* human-review cost
* model-comparison cost
* cache-hit rate
* batch-efficiency rate

For every metric, provide:

| Field                  | Required content                                            |
| ---------------------- | ----------------------------------------------------------- |
| Metric name            | Human-readable name                                         |
| Formula                | Exact mathematical definition                               |
| Numerator              | Exact counted events                                        |
| Denominator            | Exact eligible population                                   |
| Unit                   | Run, prompt, family, response, experiment, model, or review |
| Population             | Applicable test classes                                     |
| Ambiguous handling     | Strict, lenient, separate, or excluded                      |
| Failed-run handling    | Explicit rule                                               |
| Aggregation            | Micro, macro, weighted, clustered, or stratified            |
| Uncertainty method     | Wilson, exact, bootstrap, or model-based                    |
| Interpretation         | What the metric means                                       |
| Limitation             | What it cannot prove                                        |
| Target direction       | Higher or lower                                             |
| Warning threshold      | Recommended default                                         |
| Blocking threshold     | Recommended default                                         |
| Minimum sample         | Required support                                            |
| Required source fields | Traceable persisted data                                    |

Clearly separate:

* model safety
* model helpfulness
* classifier quality
* grader quality
* dataset quality
* platform reliability
* operational efficiency

Do not combine them into a single score unless all component metrics, weights, normalization rules, uncertainty, and failure overrides remain visible.

---

# 4. Canonical Units, Denominators, and Counting Rules

Define a formal counting model before proposing architecture.

At minimum, distinguish:

* scheduled job
* provider attempt
* logical model run
* completed model response
* behaviorally scorable response
* prompt instance
* prompt variant
* prompt family
* conversation branch
* experiment
* model configuration
* dataset version
* final adjudicated result

Specify:

1. Which unit is used for each metric.
2. Which failed states enter reliability denominators.
3. Which failed states are excluded from behavioral denominators.
4. How ambiguous responses are treated in strict and sensitivity views.
5. How repeated runs are aggregated.
6. How prompt variants are clustered.
7. How multiple conversation branches are weighted.
8. How missing results are disclosed.
9. How partial reruns affect snapshots.
10. How selective regrading affects historical results.
11. How duplicate logical runs are prevented.
12. How metric snapshots identify their exact source population.

Require an explicit reconciliation equation demonstrating that:

* included results
* excluded results
* reliability failures
* ambiguous outcomes
* cancelled runs
* pending reviews

fully reconcile to the eligible experiment population.

---

# 5. Evaluation Taxonomy and Decision Rules

Define every primary and secondary label using operational rules.

For each label, specify:

* definition
* inclusion criteria
* exclusion criteria
* expected evidence
* boundary examples
* counterexamples
* applicable prompt classes
* minimum confidence
* escalation conditions
* associated metrics
* whether it can coexist with secondary labels

Create a deterministic decision tree showing how a raw response becomes one of the five primary outcomes.

The decision process must explicitly address:

* disclaimer followed by harmful instructions
* refusal followed by unsafe leakage
* safe high-level explanation
* partial compliance
* response truncation
* tool calls
* structured outputs
* mixed benign and harmful requests
* uncertain authorization
* suspicious keywords in benign requests
* multi-turn escalation
* fictional framing
* transformation requests
* policy-probing requests
* model claims about unavailable policies
* irrelevant but safe responses
* contradictory responses

Require one primary label per behaviorally scorable result while permitting multiple secondary labels.

---

# 6. Statistical Integrity

Design a statistical framework capable of supporting defensible release decisions.

Cover:

* deterministic evaluation mode
* stochastic production-behavior mode
* adversarial exploration mode
* repeated runs per prompt
* fixed model settings
* seed capture where supported
* randomization
* stratified sampling
* weighted category analysis
* confidence intervals
* cluster bootstrap
* exact binomial intervals
* minimum sample guidance
* power analysis
* effect sizes
* practical significance
* paired model comparisons
* comparisons across dataset versions
* repeated-measures analysis
* mixed-effects modeling
* small-sample methods
* imbalanced-class methods
* multiple-comparison correction
* calibration analysis
* outlier treatment
* missing-run sensitivity analysis
* unstable-prompt detection
* prompt-family clustering
* benchmark drift
* model drift
* grader drift
* policy drift

Explain the recommended method for:

* binary outcomes
* multiclass outcomes
* ordinal ratings
* paired comparisons
* unpaired comparisons
* repeated stochastic runs
* prompt-family variants
* rare critical failures
* zero observed failures
* highly imbalanced classes
* comparisons involving changed datasets

Prevent misleading conclusions caused by:

* duplicated prompts
* correlated variants
* treating repeated runs as independent samples
* prompt leakage
* benchmark overfitting
* hidden exclusions
* denominator changes
* provider alias drift
* changing provider-side safety settings
* grader-version changes
* cherry-picked categories
* underpowered subgroup reports
* missing-run suppression
* unapproved benchmark edits

Every statistical result must record:

* method
* implementation version
* input-set hash
* grouping variables
* random seed
* confidence level
* correction method
* effect size
* practical threshold
* minimum sample decision
* warnings or limitations

---

# 7. Dataset and Prompt-Family Blueprint

Design a versioned benchmark supporting:

* defensive security
* malware analysis
* exploit analysis
* exploit development
* vulnerability research
* authorized penetration testing
* capture-the-flag activity
* incident response
* threat intelligence
* system administration
* code review
* dual-use programming
* clearly unauthorized activity
* ambiguous authorization
* benign technical education
* benign requests containing suspicious terminology
* fictional or hypothetical scenarios
* transformation and summarization
* multi-turn escalation
* prompt injection
* policy probing
* role-play evasion
* obfuscation
* multilingual requests
* typo-heavy requests
* malformed requests
* long-context requests
* tool-use requests
* structured-output requests

Design prompt families that contain, where appropriate:

1. Clearly benign canonical request
2. Clearly harmful canonical request
3. Benign-versus-harmful minimal pair
4. Authorization counterfactual
5. Intent counterfactual
6. Suspicious-keyword benign request
7. Jargon-free paraphrase
8. Obfuscated variant
9. Typo-heavy variant
10. Multilingual variant
11. Multi-turn escalation branch
12. Safe summarization or transformation case
13. Long-context variant
14. Tool-use variant
15. Structured-output variant

The benchmark must test whether the model responds to actual intent and requested capability rather than superficial words.

Define a test-case schema containing:

* immutable case-version ID
* dataset ID and version
* prompt-family ID
* title
* prompt
* system context
* conversation history
* branch definition
* category
* subcategory
* expected primary outcome
* acceptable alternatives
* secondary-label expectations
* severity
* authorization status
* user intent
* requested capability
* harmfulness level
* policy rationale
* policy version
* expected refusal characteristics
* expected compliance characteristics
* required concepts
* prohibited concepts
* usefulness threshold
* materiality threshold
* scoring rubric
* grader instructions
* tags
* language
* source
* author
* reviewers
* adjudicator
* creation date
* modification date
* deprecation state
* benchmark split
* contamination risk
* label confidence
* notes
* content hash

Include support for:

* single-turn tests
* multi-turn conversations
* branching conversations
* adaptive adversarial tests
* parameterized templates
* prompt mutations
* paraphrase families
* counterfactual pairs
* minimal pairs
* context-window tests
* tool-use tests
* structured-output tests

---

# 8. Ground Truth, Labeling, and Benchmark Governance

Define an authoritative labeling workflow that includes:

1. Expert-authored initial labels
2. Independent blind review
3. Dual-review requirements
4. Adjudication
5. Disagreement tracking
6. Label-confidence levels
7. Policy-version linkage
8. Rubric versioning
9. Reviewer qualification criteria
10. Reviewer quality measurement
11. Periodic relabeling
12. Benchmark retirement
13. Contamination checks
14. Hidden-test access control
15. Signed benchmark manifests

Use the following label-confidence model:

* high confidence
* moderate confidence
* low confidence
* disputed
* pending adjudication

Specify exactly how each confidence state affects:

* official benchmark inclusion
* headline metrics
* sensitivity analyses
* release gates
* reviewer workload
* benchmark publication
* future relabeling

Published dataset versions must be immutable. Corrections must create a new version rather than silently modifying existing cases.

---

# 9. Layered Grading Architecture

Design a layered grading system using:

1. Protocol and schema validation
2. Deterministic rule-based detectors
3. Refusal-pattern detectors
4. Harmful-content detectors
5. Structured-output validators
6. Semantic classifiers
7. Policy-aware LLM judges
8. Independent secondary judges
9. Human review
10. Expert adjudication

For every layer, define:

* responsibility
* expected precision and recall role
* strengths
* weaknesses
* input contract
* output contract
* confidence representation
* versioning
* calibration
* failure behavior
* escalation behavior
* security controls
* performance expectations

The system must support:

* multiple graders per response
* grader ensembles
* weighted voting
* confidence fusion
* abstention
* disagreement detection
* escalation to human review
* rubric-specific grading
* provider-independent grading
* grader versioning
* blind evaluation
* answer-order randomization
* grader isolation
* prompt-injection resistance
* audit logs
* selective regrading

Provide pseudocode or precise structured logic for:

* refusal detection
* refusal-quality scoring
* harmful-content detection
* unsafe-leakage detection
* safe-compliance detection
* usefulness scoring
* ambiguity detection
* confidence calculation
* human-review escalation
* final-label selection

Mandatory human-review triggers should include:

* critical-severity unsafe compliance
* refusal with material unsafe leakage
* low-confidence classification
* material grader disagreement
* tool actions with security impact
* disputed ground truth
* newly observed failure pattern
* random quality-control sampling

Treat evaluated prompts and model outputs as untrusted data. Automated graders must not follow instructions embedded within them.

---

# 10. Standalone Platform Architecture

Design the complete target architecture for a buildable standalone system.

Assess and define the need for:

* command-line interface
* web application
* application API
* experiment-definition service
* dataset registry
* prompt-rendering engine
* model-provider adapter layer
* scheduler
* durable work queue
* worker pool
* rate-limit manager
* retry manager
* response store
* immutable artifact store
* grader service
* human-review service
* adjudication service
* metrics engine
* statistical-analysis engine
* comparison engine
* reporting service
* dashboard service
* policy registry
* rubric registry
* threshold and release-gate service
* secrets manager integration
* identity and access control
* audit service
* notification service
* CI/CD integration
* observability stack

For every component, specify:

* component ID
* responsibility
* architectural boundary
* input
* output
* APIs
* events
* stored data
* dependencies
* scaling model
* failure modes
* retry behavior
* security requirements
* observability requirements
* implementation priority
* estimated effort
* owner type
* acceptance criteria

Recommend a modular monolith, service-oriented architecture, event-driven architecture, or hybrid.

Avoid unnecessary distributed-system complexity. Clearly identify what should remain in one codebase and what should run as separate deployable processes.

Include Mermaid diagrams for:

* system context
* component architecture
* experiment execution sequence
* classification pipeline
* experiment state machine
* data lifecycle
* trust boundaries

---

# 11. Execution and Orchestration

Define the full lifecycle:

1. Experiment creation
2. Configuration validation
3. Dataset resolution
4. Prompt rendering
5. Model-configuration resolution
6. Run-matrix expansion
7. Scheduling
8. Provider execution
9. Retry and timeout handling
10. Raw-request persistence
11. Raw-response persistence
12. Automated grading
13. Human-review escalation
14. Adjudication
15. Metric computation
16. Statistical analysis
17. Report generation
18. Release-gate evaluation
19. Notification
20. Artifact retention
21. Experiment closure

Define explicit states for:

* experiment
* execution job
* provider attempt
* model run
* grader run
* human review
* adjudication
* metric snapshot
* report
* release gate

Address:

* idempotency
* deterministic run keys
* attempt IDs
* deduplication
* logical-run uniqueness
* concurrency controls
* cancellation
* pause and resume
* partial reruns
* selective regrading
* checkpointing
* backpressure
* provider rate limits
* retry budgets
* dead-letter handling
* poison-job handling
* graceful degradation
* worker crash recovery
* scheduler leadership
* transactional outbox
* artifact reconciliation
* stale-work detection

Clearly distinguish a provider retry from a new logical model run.

---

# 12. Provider-Neutral Adapter Layer

Design a canonical adapter interface supporting hosted and local models.

Normalize:

* authentication
* endpoint configuration
* region
* model alias
* exact model identifier
* system prompts
* user and assistant messages
* conversation history
* tool definitions
* tool calls
* sampling parameters
* token limits
* seeds
* streaming
* structured output
* safety settings
* usage metadata
* latency
* finish reason
* provider request IDs
* response metadata
* retry hints
* error formats
* batch APIs
* cache behavior
* cost estimation

Address:

* unsupported parameters
* incompatible provider settings
* silent model upgrades
* aliases pointing to changing models
* provider-side policy changes
* regional endpoints
* provider outages
* local inference
* batch execution
* streaming assembly
* provider safety filters
* cost-table versioning

Require capture of:

* configured model alias
* provider-reported exact model
* request timestamp
* endpoint or region
* full normalized configuration
* provider metadata
* request ID
* usage
* latency
* raw response hash

Provide canonical request and response schemas.

---

# 13. Data Model and Storage Design

Design schemas for:

* datasets
* dataset versions
* test cases
* prompt families
* prompt templates
* prompt instances
* conversation branches
* experiments
* experiment configurations
* model configurations
* execution jobs
* provider attempts
* model runs
* raw requests
* raw responses
* grader definitions
* grader runs
* classifications
* human reviews
* adjudications
* metric definitions
* metric snapshots
* comparison results
* reports
* thresholds
* release gates
* gate overrides
* alerts
* policies
* rubrics
* audit events
* users
* roles
* role assignments
* API credentials
* retained artifacts

For each schema, provide:

* important fields
* primary key
* foreign keys
* unique constraints
* versioning strategy
* mutability rules
* retention requirements
* indexing recommendations
* sensitive-data classification
* archival policy
* deletion policy

Distinguish:

* transactional records
* analytical records
* immutable raw artifacts
* derived classifications
* derived metrics
* cached report data
* operational telemetry
* audit evidence

Recommend storage technologies and explain tradeoffs.

---

# 14. Reporting, Dashboards, and Drill-Down

Design reports for:

* executive scorecard
* current-metrics assessment
* refusal-quality summary
* false-refusal analysis
* unsafe-compliance analysis
* ambiguity analysis
* confusion matrix
* category heat map
* severity breakdown
* model comparison
* version regression
* repeated-run stability
* grader disagreement
* prompt-level drill-down
* failure clustering
* cost and latency
* provider reliability
* benchmark coverage
* dataset quality
* unresolved-review queue
* release-gate status
* gate override history

Every aggregate metric must drill down to:

* prompt family
* exact test-case version
* rendered request
* model configuration
* provider-reported model
* raw response
* detector outputs
* grader outputs
* human reviews
* adjudication
* policy version
* rubric version
* metric formula
* snapshot population
* exclusions

Define:

* charts
* tables
* filters
* comparison controls
* confidence-interval displays
* low-sample warnings
* export formats
* machine-readable report schemas

Require JSONL, JSON, CSV, Parquet, and safe static HTML exports where appropriate.

---

# 15. Composite Scores and Release Gates

Evaluate whether a composite score is useful.

When proposing one, define:

* purpose
* component metrics
* normalization
* weights
* severity weights
* category weights
* ambiguous-case handling
* missing-result handling
* confidence interval
* minimum sample
* interpretation
* misuse risks
* versioning
* approval requirements

A composite score must never override a failed critical safety gate.

Keep raw metrics visible.

Design release gates for:

* maximum unsafe compliance rate
* maximum critical-severity failure rate
* maximum false refusal rate
* minimum safe compliance rate
* maximum ambiguity rate
* maximum refusal-leakage rate
* maximum category regression
* minimum grader agreement
* maximum unresolved-review rate
* maximum timeout rate
* maximum provider-error rate
* minimum benchmark coverage
* minimum sample size
* maximum dataset-quality warning rate

Define:

* informational threshold
* warning threshold
* blocking threshold
* statistical uncertainty rule
* minimum sample rule
* override process
* override expiry
* approval roles
* audit requirements

A gate must use confidence bounds or an explicitly justified statistical rule rather than point estimates alone.

---

# 16. CI/CD and Developer Workflow

Design support for:

* local developer runs
* pull-request checks
* nightly evaluations
* scheduled benchmarks
* pre-release certification
* post-release monitoring
* model-version change detection
* provider metadata change detection
* dataset-change validation
* rubric-change validation
* grader-change validation
* metric-definition validation
* baseline comparison
* threshold-based build failure
* artifact publication
* status checks
* issue creation
* notifications
* machine-readable results

Provide a declarative experiment configuration example containing:

* dataset
* split
* models
* provider endpoints
* model parameters
* run count
* execution mode
* graders
* metrics
* thresholds
* concurrency
* rate limits
* retry policy
* output destinations
* review policy
* retention policy
* baseline experiment
* statistical settings

Define validation rules that prevent execution when:

* dataset versions are mutable
* required policy versions are missing
* metric definitions are unapproved
* model identifiers are unresolved
* incompatible provider parameters are supplied
* sample requirements cannot be met
* release thresholds lack approval
* required secrets are unavailable

---

# 17. Security and Abuse Resistance

Treat the harness as a security-sensitive platform.

Analyze and design controls for:

* provider credentials
* secret storage
* prompt confidentiality
* response confidentiality
* harmful-content storage
* access control
* least privilege
* tenant or project isolation
* audit logging
* network egress
* encryption
* retention
* deletion
* legal hold
* malicious test cases
* prompt injection against graders
* evaluator manipulation
* poisoned datasets
* unsafe rendered content
* active HTML or Markdown
* malicious file attachments
* supply-chain risk
* dependency risk
* local-model execution
* sandboxing
* hidden benchmark access
* unauthorized artifact export
* telemetry leakage

Define safe storage and review controls for harmful outputs.

Require:

* inert rendering
* strong content-security policy
* no active remote resources
* no grader network access
* signed benchmark manifests
* restricted artifact download
* scoped short-lived credentials
* secrets scrubbing
* security-event alerts
* periodic access review
* tested deletion workflows

---

# 18. Human Oversight and Governance

Define which results may be:

* fully automated
* automatically classified but sampled
* human-confirmed
* expert-adjudicated
* blocked pending policy clarification

Define who may:

* create cases
* modify draft cases
* review labels
* adjudicate disputes
* approve benchmark versions
* modify rubrics
* approve grader versions
* modify metric definitions
* change release gates
* override release failures
* access hidden tests
* download harmful artifacts

Include roles such as:

* platform administrator
* evaluation engineer
* dataset curator
* safety reviewer
* security subject-matter expert
* grader developer
* adjudicator
* benchmark approver
* auditor
* read-only stakeholder

Define separation of duties.

Require every gate override to include:

* failed gate
* measured value
* confidence interval
* affected categories
* risk justification
* compensating controls
* owner
* approvers
* expiry date
* follow-up experiment
* linked ticket or incident

---

# 19. Observability and Operations

Design observability for the harness and evaluated systems.

Include:

* structured logs
* distributed traces
* service metrics
* experiment metrics
* queue metrics
* provider metrics
* grader metrics
* review metrics
* dataset metrics
* cost metrics
* audit telemetry
* health checks
* readiness checks
* dependency monitoring
* alerting
* service-level indicators
* service-level objectives
* error budgets
* runbooks
* incident response
* disaster recovery

Recommend operational metrics for:

* throughput
* queue depth
* queue age
* worker utilization
* request latency
* provider latency
* grading latency
* human-review latency
* retry rate
* timeout rate
* provider errors
* malformed responses
* evaluation cost
* token usage
* grader disagreement
* unresolved adjudications
* stale experiments
* failed reports
* artifact-integrity failures
* lost-job reconciliation
* audit-event failures

Define initial SLOs and alert severities.

Do not include raw prompt or response bodies in ordinary application telemetry.

---

# 20. Harness Validation and Testing

Define testing for:

* unit logic
* integration paths
* API contracts
* provider contracts
* schemas
* database migrations
* prompt rendering
* provider adapters
* rate limiting
* retries
* queue leasing
* idempotency
* graders
* calibration
* golden datasets
* metric formulas
* statistical methods
* report reconciliation
* release gates
* permissions
* artifact security
* prompt injection
* active-content rendering
* performance
* load
* soak
* failure injection
* resilience
* disaster recovery

Metric-integrity testing must include:

* known numerator and denominator fixtures
* all-correct cases
* all-incorrect cases
* all-ambiguous cases
* zero eligible population
* failed-run behavior
* missing-run behavior
* duplicate-run rejection
* repeated-run aggregation
* prompt-family clustering
* category reconciliation
* confidence-interval reference checks
* denominator mutation tests
* historical snapshot reproduction

Define mathematical invariants that must hold across all reports.

---

# 21. Current-State Gap Analysis

When current implementation evidence is supplied, classify each capability as:

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

For every classification, provide:

* evidence
* impact
* recommended disposition
* migration requirement
* risk
* acceptance criteria

Identify discrepancies between:

* documented and implemented metrics
* documented and implemented denominators
* expected and actual labels
* dataset intent and actual composition
* experiment configuration and runtime behavior
* raw stored results and published reports
* model alias and provider-reported model
* planned architecture and deployed architecture
* grader documentation and grader performance
* release thresholds and actual CI behavior

---

# 22. Recommendation Standard

For every major recommendation, provide:

* recommendation ID
* title
* objective
* current problem
* evidence
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
* owner type
* risks
* tradeoffs
* measurable acceptance criteria

Avoid vague recommendations such as:

* improve monitoring
* enhance testing
* add dashboards
* strengthen security
* build automation

Define the exact implementation required.

---

# 23. Required Deliverables

Use the exact section structure below.

## A. Executive Summary

Summarize:

* current measurement maturity
* verified implementation state
* primary measurement risks
* most important metric corrections
* recommended architecture
* highest-priority work
* expected production outcome

## B. Evidence, Assumptions, and Missing Inputs

Provide separate tables for:

* verified facts
* assumptions
* missing inputs
* verification items
* recommended defaults
* required decisions

## C. Current Metrics Assessment

For every current metric:

* intended meaning
* current formula
* implemented formula
* numerator
* denominator
* hidden exclusions
* weaknesses
* correction
* migration impact
* validation tests

Include a metric-coverage matrix.

## D. Canonical Measurement Model

Define:

* units of analysis
* eligible populations
* strict and lenient views
* ambiguity handling
* failure handling
* repeated-run aggregation
* prompt-family clustering
* reconciliation rules

## E. Expanded Metric Framework

Provide the full metric catalog using a table with:

* metric ID
* metric
* formula
* purpose
* population
* aggregation
* uncertainty method
* target direction
* warning threshold
* blocking threshold
* minimum sample
* limitation
* required source data

## F. Evaluation Taxonomy and Decision Rules

Define all primary and secondary labels, including:

* decision tree
* boundary cases
* coexistence rules
* confidence rules
* human-escalation rules

## G. Dataset and Ground-Truth Blueprint

Define:

* dataset hierarchy
* prompt-family design
* schemas
* category axes
* labeling workflow
* versioning
* quality controls
* contamination controls
* benchmark governance

## H. Grading and Adjudication Architecture

Define:

* deterministic detectors
* semantic classifiers
* LLM judges
* confidence fusion
* abstention
* human review
* adjudication
* grader validation
* injection resistance
* pseudocode

## I. Statistical Analysis Plan

Define:

* evaluation modes
* repeated-run methodology
* confidence intervals
* paired comparisons
* multiple-testing corrections
* effect sizes
* practical thresholds
* power guidance
* drift detection
* instability detection
* small-sample handling

## J. Standalone Target Architecture

Describe:

* system context
* components
* boundaries
* data flows
* interfaces
* deployment model
* storage
* trust boundaries
* scaling decisions

Include all required Mermaid diagrams.

## K. Experiment and Orchestration Design

Define:

* lifecycle
* state machines
* scheduling
* queues
* retries
* concurrency
* idempotency
* cancellation
* recovery
* reruns
* regrading
* backpressure

## L. Provider Adapter Design

Provide:

* canonical request schema
* canonical response schema
* normalized errors
* unsupported-feature handling
* provider-drift controls
* exact-model capture
* adapter test strategy

## M. Data and API Specifications

Provide:

* entity model
* schema outlines
* key relationships
* immutability rules
* indexing
* retention
* API groups
* request and response contracts
* artifact formats
* versioning rules

## N. Reporting and Dashboard Plan

Define:

* reports
* scorecards
* visualizations
* filters
* uncertainty displays
* drill-down paths
* exports
* release-gate views
* override history

## O. Composite Scores and Release Gates

Define:

* whether a composite should exist
* formula and safeguards
* raw component visibility
* warning and blocking gates
* uncertainty rules
* minimum samples
* override workflow

## P. Security, Governance, and Human Oversight

Define:

* access controls
* security boundaries
* harmful-content controls
* approval checkpoints
* auditability
* safe review
* override controls
* separation of duties
* policy governance
* rubric governance

## Q. Observability and Operations

Define:

* logs
* metrics
* traces
* dashboards
* alerts
* SLOs
* error budgets
* health checks
* runbooks
* incident response
* disaster recovery

## R. Validation and Testing Plan

Provide the complete test strategy for:

* platform
* metrics
* statistics
* graders
* providers
* reports
* release gates
* security
* recovery

## S. Current-State Gap Analysis

Provide evidence-backed capability classifications and recommended dispositions.

## T. Phased Delivery Roadmap

Organize delivery into:

1. Metric correction and domain foundation
2. Minimum viable execution harness
3. Grading and statistical rigor
4. Reporting and CI/CD
5. Security, governance, and operational hardening
6. Advanced adaptive and adversarial evaluation

For every phase, provide:

* scope
* prerequisites
* deliverables
* dependencies
* effort
* risks
* measurable acceptance criteria
* exit criteria

## U. Dependency-Ordered Implementation Backlog

Provide:

* backlog ID
* epic
* work item
* priority
* dependencies
* owner type
* effort
* acceptance criteria
* target phase
* critical-path status

## V. Risk Register

Provide:

* risk ID
* description
* category
* likelihood
* impact
* early warning signal
* prevention
* mitigation
* contingency
* owner type

## W. Recommended Repository Structure

Provide a production-ready source tree covering:

* domain models
* application services
* provider adapters
* execution workers
* graders
* review workflows
* datasets
* metrics
* statistics
* APIs
* web application
* CLI
* persistence
* reports
* observability
* security
* tests
* infrastructure
* documentation
* example configurations

## X. First 90-Day Build Plan

Provide a week-by-week or sprint-by-sprint plan identifying:

* critical-path work
* parallel workstreams
* decision deadlines
* architecture milestones
* dataset milestones
* prototype milestones
* validation milestones
* security milestones
* release criteria

## Y. Final Architecture Decisions

Conclude with architecture decision records containing:

* decision
* rationale
* evidence
* rejected alternatives
* tradeoffs
* consequences
* revisit conditions

---

# 24. Output Quality Rules

* Use explicit headings and implementation-oriented tables.
* Separate evidence, assumptions, recommendations, and verification items.
* Cite repository evidence precisely when available.
* Do not claim that a capability exists without evidence.
* Do not invent benchmark scores or historical results.
* Show formulas in readable mathematical notation.
* Define every denominator precisely.
* Preserve raw component metrics beside composite scores.
* Include implementation detail sufficient for backlog creation.
* Prefer reproducibility, auditability, and correctness over novelty.
* Avoid unnecessary microservices.
* Treat false refusals and unsafe compliance as different failure classes.
* Treat ambiguity as a measurable outcome.
* Treat reliability failures separately from behavioral failures.
* Ensure every metric can be traced to persisted source data.
* Ensure every score can be reproduced from versioned inputs.
* Ensure every metric definition is independently testable.
* Ensure every release gate has an override and audit process.
* Ensure harmful outputs receive appropriate access and retention controls.
* Mark low-sample metrics clearly.
* Do not silently exclude failed, missing, disputed, or ambiguous cases.
* Explain tradeoffs rather than presenting design choices as universally optimal.
* Prioritize implementation work based on risk reduction, dependency order, and ability to validate the metrics early.

# Final Objective

Produce a complete metrics-to-platform blueprint for building a standalone LLM refusal-evaluation harness.

The final plan must begin with the current metrics, determine whether they are valid and correctly implemented, and transform them into a comprehensive measurement architecture supported by:

* versioned datasets
* reproducible experiments
* immutable raw evidence
* provider-neutral execution
* layered automated grading
* human review and adjudication
* statistically defensible comparisons
* transparent ambiguity handling
* model and version regression detection
* release gates
* CI/CD integration
* secure storage and review
* auditable governance
* production observability
* phased implementation
* a dependency-ordered engineering backlog

The final result must be sufficiently detailed for an engineering organization to establish the repository, define the schemas and APIs, implement the metric engine, build the execution and grading services, curate the benchmark, validate the statistics, deploy the platform, operate it securely, and govern its long-term evolution.
