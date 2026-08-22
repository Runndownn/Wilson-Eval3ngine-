# Wilson Eval3ngine Features

Wilson Eval3ngine is designed as an evidence-producing evaluation platform rather than a thin model-call benchmark script. Its features are easiest to understand in groups because each group answers a different part of the release question: what was defined, what was executed, what behavior occurred, how it was measured, what decision rule was applied, and what evidence survives afterward.

## Evaluation contracts and reproducibility

Experiments, datasets, cases, provider requests/responses, classifications, metrics, thresholds, and dossiers use explicit versioned contracts. The application validates dataset identity, version, split, and hash relationships before execution, while logical run identity incorporates the experiment definition, case version, rendered prompt, model configuration, repetition, and execution mode.

This design makes configuration part of the evidence rather than background context. A result should be reproducible from frozen definitions and should change identity when a score-affecting input changes.

## Expectation-first evaluation

WE3 compiles the expected treatment for a case before calling the evaluated model. That ordering is important because it prevents a persuasive or unexpected model response from silently changing what the evaluator intended to measure.

Expectation records are persisted alongside other run artifacts. Compilation failures are treated as execution/reliability failures rather than sending an undefined case to the provider and guessing afterward.

## Provider abstraction

The provider layer defines one canonical execution boundary and includes a deterministic mock plus adapters/registration paths for Azure OpenAI, Anthropic, Ollama, and supported local CLI providers. The mock makes the local lane deterministic and credential-free, while the real adapters allow the same higher-level evaluation concepts to be applied to authorized external or local models.

Retries preserve individual attempt records. Retryability, error class, maximum attempts, backoff, and elapsed budget are explicit so provider instability remains visible instead of being confused with model refusal behavior.

## Five-outcome behavioral grading

The primary behavioral taxonomy distinguishes:

- appropriate refusal;
- false refusal;
- safe useful compliance;
- unsafe compliance;
- ambiguous or partial behavior.

Reliability states are separate from these behavioral labels. That separation is one of WE3's most important features because “the model refused” and “the provider failed to return a usable response” are not the same outcome.

## Human review and adjudication

The repository contains a review workflow that goes beyond a boolean escalation flag. It includes task creation, qualified reviewer assignment, blind dual review, recusal, abstention, disagreement handling, adjudication, and immutable submission/adjudication records.

These primitives support the principle that automated grading should not become autonomous release authority. A real review program still has to supply the people, identities, policy, SLA, workload capacity, and runtime integration needed to exercise the workflow responsibly.

## Metrics and statistical uncertainty

Metric snapshots retain explicit numerators, denominators, exclusions, run IDs, method/version metadata, and Wilson score intervals. WE3 therefore lets a reviewer see both the observed rate and the amount of evidence behind it instead of publishing an unexplained percentage.

Comparison and drift primitives are also present. Some cross-run significance/bootstrap work remains provisional in the current source, and one snapshot helper notes a prompt-family-count approximation; these limitations are recorded in [STATUS.md](STATUS.md) so they are not mistaken for completed certification statistics.

## Deterministic release gates

The gate engine evaluates configured raw metrics and minimum-support rules with explicit `pass`, `warning`, `indeterminate`, and `block` outcomes. A confirmed unsafe-compliance event can force a block even when support is otherwise small, while insufficient support prevents an artificial pass.

Threshold code and threshold authority are deliberately different things. A threshold becomes release policy only when it has been approved for the intended benchmark, model population, severity model, and organizational decision process.

## Content-addressed evidence and signed dossiers

The local path persists score-affecting artifacts in a content-addressed evidence store and records audit events around the evaluation lifecycle. It then generates a signed release dossier, safe report output, and experiment-result index so the final human-readable result remains linked to exact hashes and run identities.

The broader repository also includes encrypted evidence-store behavior using AES-256-GCM envelope encryption and retention/legal-hold policy interfaces. Development/local key handling is intentionally not described as equivalent to an external production KMS or managed signing authority.

## Durable execution

The local evaluation service is synchronous because that makes development, CI, and recovery diagnostics straightforward. Separately, the persistence layer implements PostgreSQL-backed durable scheduling with `FOR UPDATE SKIP LOCKED`, fenced lease ownership/versioning, heartbeats, bounded retry policy, poisoned/dead-letter transitions, and reconciliation support.

This lets the codebase preserve a simple deterministic lane without pretending the production execution model must also be a single synchronous process.

## Certification orchestration

The certification package organizes release requirements across ten categories: reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability. Blocking/must requirements can prevent a certification outcome, and the orchestration model is built around evidence rather than a free-form “looks good” approval.

Certification capability being implemented does not mean every checkout or deployment is certified. The required tests, artifacts, approvals, and private runtime evidence must still be present and valid for the exact release under consideration.

## Operator GUI

The GUI provides operator-facing workspaces for provider endpoints, model inventory, report/evaluation generation, charts, reports, PDFs, and related evidence operations. The official launcher binds only to loopback because those controls are administrative; remote access is expected to be provided through an independently authenticated TLS proxy.

The visual workflow is documented with real repository screenshots and the complete chart catalogue in [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).

## Provider and credential protections

GUI provider handling differentiates public destinations from intentional local/private gateways, constrains redirect behavior, and avoids returning credential values in endpoint API responses. The supported POSIX report-job path uses a one-shot FIFO for keyed child-process handoff instead of the historical regular plaintext temporary file.

These are application controls, not a replacement for deployment egress policy, operating-system account security, secret management, provider-side credential scope/rotation, or network assurance.

## Authentication, authorization, and project isolation

The broader platform includes OIDC support and project-scoped security controls. Production use depends on the real organization's issuer/JWKS, audience, claims, group/role mapping, database policies, object policies, revocation behavior, and negative authorization testing.

This distinction is why [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md) treats public implementation and private deployment configuration as separate evidence domains.

## Hardened API and deployment controls

Production-oriented deployment material includes Caddy ingress, API service, PostgreSQL, Redis, Prometheus, and Grafana with internal service networks. The API includes actual received-byte body limiting rather than trusting a client-declared `Content-Length`, and container/deployment material includes explicit secret/configuration requirements and hardening choices.

A Compose file is still a template until it is executed and verified. Container identity, image digests, TLS, firewall behavior, database/cache protection, and egress enforcement require runtime evidence from the actual deployment.

## Observability and recovery

Telemetry and tracing modules provide correlation and operational instrumentation across evaluation stages. Backup/recovery modules and runbooks support backup creation, verification, restore planning, and broader recovery validation.

The presence of those implementations means operations were designed into the platform rather than added only to documentation. Production SLO, alerting, restore, PITR, object reconciliation, and disaster-recovery claims nevertheless require executed evidence.

## Visual analytics

The chart system includes confidence intervals, response-time distributions and trends, prompt-level heatmaps, token views, outcome distributions, radar comparisons, cross-run comparisons, timelines, and other analytical views. Charts make patterns easier to see but never replace the structured metric snapshots and sidecars that hold exact values and provenance.

Every promoted documentation chart is visible in [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md), with three-sentence explanations of what the visual shows and when it is useful.

## What WE3 deliberately avoids claiming

WE3 does not claim that a model is safe outside the tested population, that a high aggregate score overrides a critical safety event, that a provider error is a refusal, that source code proves the security of a deployed environment, or that automated judging removes the need for accountable human decision authority. It also does not treat historical Plans/TODOs or a point-in-time test report as current runtime evidence.

For the exact implementation/assurance boundary, read [Current Status](STATUS.md). For component relationships and trust boundaries, read [Architecture](ARCHITECTURE.md).
