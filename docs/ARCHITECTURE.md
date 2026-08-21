# Wilson Eval3ngine Architecture

This document describes the architecture that exists in the current repository, not only the July 2026 conceptual plan. It separates the deterministic local execution lane from the broader production-oriented modules so readers can understand both the working end-to-end path and the controls that surround it.

## Architectural intent

WE3 is organized as a Python modular platform whose central contract is an evidence-producing evaluation pipeline. The system validates versioned experiment inputs, compiles the expected behavior before model execution, records provider attempts and terminal responses, classifies behavior, computes versioned statistical snapshots, evaluates release gates, and preserves the artifacts and audit lineage needed to reconstruct the decision.

The repository also contains the infrastructure needed to operate that contract beyond a local demonstration: real provider adapters, durable PostgreSQL scheduling, project and identity controls, encrypted evidence storage, human review/adjudication, certification orchestration, telemetry, backup/recovery, browser/operator controls, and hardened deployment templates. These modules make the codebase substantially broader than the historical “foundation” vertical slice, but a production certification claim still requires runtime evidence from the actual target environment.

## System view

<p align="center"><img src="assets/diagrams/system-architecture.svg" alt="Wilson Eval3ngine system architecture" width="1100"></p>

The architecture places GUI, CLI, and API interfaces above application services so multiple entry points can reuse the same evaluation concepts instead of inventing separate measurement semantics. Evaluation, provider execution, evidence/state, review/governance, and operations are represented as explicit module families, while production infrastructure remains a deployment boundary rather than being mixed into the domain model. This view is useful for contributors because it shows where a change belongs and which interfaces should remain stable when implementation details evolve.

## Core evaluation data flow

<p align="center"><img src="assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evidence-first evaluation pipeline" width="1100"></p>

The pipeline begins with versioned experiment and dataset definitions and ends with signed, reviewable evidence rather than only a score. Compiling expected treatment before provider execution prevents the returned answer from retrospectively redefining what the case was intended to measure, while recording attempts and terminal responses preserves reliability information. This view is useful for reviewing metric correctness because every later aggregation can be traced backward to the exact run population and evidence-producing stages.

### 1. Contracts and input validation

`src/wilson_eval3ngine/domain/` contains the primary contracts, enumerations, state definitions, and loading/IO logic. Experiment manifests define project/lane information, dataset references, model configurations, execution/retry settings, grader configuration, and related versioned inputs; dataset manifests contain test cases and their policy/rubric relationships.

The application service validates dataset identity, version, split, and manifest hash before execution. That means a run is not supposed to silently substitute a different dataset revision or split while keeping the same declared experiment identity.

### 2. Expectation compilation

`src/wilson_eval3ngine/expectations/` converts the case plus its approved policy/rubric context into an expectation record. This occurs before provider execution and is stored as evidence, establishing what treatment the system expected independently of the model's eventual output.

Expectation compilation is an important architectural boundary because grading should compare observed behavior with a declared evaluation contract. If compilation fails, the run is recorded as a reliability/execution failure rather than being sent to a model with an undefined target.

### 3. Prompt rendering and logical identity

`src/wilson_eval3ngine/execution/` contains rendering and idempotency support. A rendered prompt hash and model configuration hash contribute to the logical run key together with the experiment definition, test-case version, repetition index, and execution mode.

This logical identity is meant to make duplicate/replayed work detectable and to keep result lineage attached to the exact input configuration. It also gives schedulers and recovery processes a stable notion of “the same work” independent of a transient worker process.

### 4. Provider boundary

`src/wilson_eval3ngine/providers/` defines the adapter contract and provider-specific implementations. The registry includes the deterministic mock by default and provides registration paths for Azure OpenAI, Anthropic, Ollama, and supported local CLI adapters.

Provider attempts are recorded individually. Retry policy considers whether a failure is retryable, whether its class is allowed by policy, the configured attempt limit, exponential backoff, maximum backoff, and maximum elapsed retry budget; exhausting that budget remains a reliability result rather than being converted into a behavioral label.

The GUI/provider path adds destination-policy and credential-handling controls for real endpoints. Public HTTPS destinations and intentionally enabled local/private gateways are treated differently, and automatic redirect behavior is constrained to reduce the risk of forwarding credentials to an unintended destination.

### 5. Grading and review

`src/wilson_eval3ngine/grading/` implements the grading pipeline and judge-related boundaries. Terminal, protocol-valid responses are classified into the behavioral taxonomy while malformed or provider-error runs remain outside those behavioral counts.

`src/wilson_eval3ngine/review/` contains human-review primitives beyond a simple escalation flag. The workflow includes review-task creation, qualified assignment, blind dual review, recusal, abstention, disagreement handling, adjudication, and immutable submission/adjudication records, giving a production review operation concrete code to integrate with rather than forcing automated graders to become final authority.

### 6. Metrics, statistics, and gates

`src/wilson_eval3ngine/metrics/`, `statistics/`, and `gates/` separate measurement from release decisions. Metric results retain explicit numerators, denominators, exclusions, method/version metadata, and Wilson score intervals; gate rules then compare those results with threshold definitions and minimum-support requirements.

Gate precedence makes a confirmed unsafe-compliance event blocking even when the observed sample is otherwise small. Conversely, insufficient independent support becomes indeterminate instead of becoming a pass merely because no failure happened to appear in a small sample.

Some cross-run comparison/statistical work remains provisional in the current code, including placeholder comparison significance logic and prompt-family-count approximation in one snapshot path. Those limitations are recorded in [STATUS.md](STATUS.md) so the architecture description does not overstate statistical completeness.

### 7. Evidence, audit, reports, and signing

`src/wilson_eval3ngine/evidence/`, `reports/`, `security/`, and `storage/` provide the evidence-handling layer. The local evaluation path uses content-addressed filesystem artifacts and generates a signed JSON dossier plus inert/safe report output, while the broader repository includes encrypted object-storage behavior based on AES-256-GCM envelope encryption and retention/legal-hold policy interfaces.

Audit-chain primitives make security- and decision-relevant events linkable rather than relying solely on mutable application logs. Signing code supports Ed25519 dossier identity, but development keys or locally generated keys should not be confused with a managed production signing authority.

### 8. Persistence and durable scheduling

The deterministic local path can use SQLite for fast development and CI. Production-oriented persistence is PostgreSQL-compatible, and `src/wilson_eval3ngine/persistence/scheduler.py` implements durable job claiming with `FOR UPDATE SKIP LOCKED`, fenced leases, owner/token/version checks, heartbeats, bounded retries, dead-letter transitions, and reconciliation support.

This is a material architectural distinction from the original synchronous slice. The synchronous service remains useful for deterministic local execution and recovery diagnostics, while the durable scheduler provides the primitives required for workers that can survive process failure and prevent stale lease owners from completing work incorrectly.

### 9. Certification orchestration

`src/wilson_eval3ngine/certification/` implements release-evidence orchestration rather than assuming “tests passed” means “production certified.” Requirements can be grouped across reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability, with must-level requirements able to block certification outcomes.

This code means certification capability is part of the current platform. It does **not** mean the public repository can self-certify an arbitrary deployment, because many required facts—real identity configuration, certificates, secrets, egress policy, provider destinations, runtime checks, restore evidence, and similar controls—exist only in the target environment.

## Operator GUI boundary

The operator GUI is an administrative control plane, even when it runs for one user on one workstation. The official launcher enforces loopback binding and composes access-control, UI overlay, and secret-transport behavior around the FastAPI application; remote operation should be provided by an authenticated TLS proxy rather than a direct remote bind.

GUI functions include endpoint configuration/testing, model discovery/inventory, bounded report/evaluation jobs, chart and report presentation, exports, and destructive actions such as deletion. Because the process can decrypt endpoint credentials and start provider-capable child processes, compromise of the local operating-system account remains a meaningful residual risk and is not solved by encrypting state under a key owned by the same account.

## Production-oriented deployment

The repository contains `Dockerfile.prod`, `Dockerfile.secure`, `docker-compose.prod.yml`, `docker-compose.secure.yml`, and supporting infrastructure configuration. The production Compose design places Caddy at the host-published ingress while API, PostgreSQL, Redis, Prometheus, and Grafana remain on internal purpose-specific networks; required secrets/configuration are explicit rather than relying on known production defaults.

OIDC, project authorization, database isolation, body-size enforcement, rate limiting, observability, backup/recovery, and other controls are implemented across the codebase and deployment material. The private deployment must still supply and validate its actual issuer/JWKS, role mapping, secrets, connection material, certificates, host/network policy, approved image digests, provider egress rules, and recovery evidence.

## Trust boundaries

<p align="center"><img src="assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100"></p>

The trust-boundary model distinguishes local operator authority, outbound provider execution, production service exposure, and the evidence boundary between public source and private deployment facts. It prevents a common documentation mistake where implemented security code is presented as proof that every deployment is secure, or where private runtime details are copied into a public repository in an attempt to prove the opposite. This view is useful for security and release reviewers because it identifies exactly which assurances can be established from source and which require controlled runtime validation.

## Public source versus private runtime evidence

The public repository can safely own stable contracts, fail-closed validation, synthetic tests, sanitized runtime-evidence schemas, deterministic inventory tools, deployment templates, security controls, and code-level assurance records. A real deployment owns its identities, groups, domains, certificates, secret-manager implementation, database/cache credentials, provider endpoints, allowlists, hosts, firewall/egress policy, incident contacts, raw scans, logs, packet captures, screenshots, and test accounts.

The bridge between the two is bounded evidence. `docs/security/PRIVATE_RUNTIME_ASSURANCE.md` defines how private checks can be reduced to sanitized statuses and SHA-256 evidence fingerprints without publishing the raw private material.

## Where the historical “foundation” lane fits

The synchronous `EvaluationService` and `examples/experiments/foundation.yaml` are retained because they provide a small, deterministic path through the core measurement contract. That path is valuable for local learning, CI, golden behavior, and recovery diagnostics, but it exercises only a subset of the broader platform and uses development/local choices that are intentionally not production authorities.

Therefore the correct architecture statement is: **WE3 is an active evaluation platform with a deterministic local foundation lane and broader production-oriented modules, currently in pre-production assurance.** The global project should not be described as “the foundation” merely because the original vertical slice and some historical identifiers retain that term.

## Reading the code by concern

| Concern | Primary area |
|---|---|
| Domain contracts and states | `src/wilson_eval3ngine/domain/` |
| Experiment orchestration | `src/wilson_eval3ngine/application/` |
| Prompt rendering/idempotency | `src/wilson_eval3ngine/execution/` |
| Provider adapters/policy | `src/wilson_eval3ngine/providers/` |
| Expectation compilation | `src/wilson_eval3ngine/expectations/` |
| Grading | `src/wilson_eval3ngine/grading/` |
| Human review | `src/wilson_eval3ngine/review/` |
| Metrics/statistics | `src/wilson_eval3ngine/metrics/`, `statistics/` |
| Release gates | `src/wilson_eval3ngine/gates/` |
| Evidence/report/signing/storage | `evidence/`, `reports/`, `security/`, `storage/` |
| Persistence/scheduling/audit | `src/wilson_eval3ngine/persistence/` |
| Certification | `src/wilson_eval3ngine/certification/` |
| API/auth/middleware | `src/wilson_eval3ngine/api/`, `security/` |
| GUI | `src/wilson_eval3ngine/gui/`, `gui/static/` |
| Telemetry/tracing | `src/wilson_eval3ngine/telemetry*`, `tracing*` |
| Deployment/observability | `docker-compose*.yml`, `Dockerfile*`, `infrastructure/` |

For exact maturity and limitations, continue with [Current Status](STATUS.md). For the visual operator flow, continue with [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).
