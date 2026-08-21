# Features

Wilson Eval3ngine is a metrics-first evaluation framework for model behavior and release evidence. Its design separates **behavior**, **reliability**, **statistics**, and **governance** so one favorable aggregate cannot hide a critical safety event or weak evidence base.

## Evaluation model

Each test case carries a versioned expected treatment. WE3 compiles that expectation before the provider is invoked, renders the provider request, preserves attempts and terminal evidence, grades the response, and records lineage.

The five primary behavior outcomes are:

- appropriate refusal;
- false refusal;
- safe useful compliance;
- unsafe compliance;
- ambiguous / partial.

Provider errors, exhausted retries, malformed protocol responses, and other reliability failures are tracked separately.

## Statistical evidence

The metric engine stores explicit numerators, denominators, exclusions, metric-definition versions, and Wilson intervals. The gate engine supports pass, warning, indeterminate, and block outcomes. A confirmed unsafe-compliance event is treated as a critical event and can block release even when sample support is otherwise low.

Comparison and drift primitives exist, but some advanced statistical paths remain incomplete; see [STATUS.md](STATUS.md) for the exact boundary.

## Evidence and reporting

The foundation execution path stores versioned experiment/dataset material, expectations, provider requests, attempts, responses, classifications, metric snapshots, gate decisions, audit events, and a signed release dossier. Reports are generated as inert/safe outputs rather than executable rich content.

Separate storage modules add encrypted, project-scoped, retention-aware object storage using AES-256-GCM envelope-encryption interfaces. The default foundation runner still uses the local artifact store.

## Providers

The provider registry includes a deterministic mock by default and registration paths for:

- Azure OpenAI;
- Anthropic;
- Ollama;
- Claude CLI;
- Kilo CLI;
- Codex CLI.

Provider availability depends on installed optional dependencies, endpoint configuration, local CLI authentication, and the calling execution path. The synchronous foundation service does not auto-register every adapter.

## Human review

Review/adjudication modules model review task creation, qualified assignment, blind dual review, recusal, abstention, override, disagreement, adjudication, SLA tracking, and immutable submissions. This machinery exists as platform capability; it is not yet fully integrated into the synchronous foundation `run_manifest` flow.

## Durable execution

The PostgreSQL scheduler implements:

- `FOR UPDATE SKIP LOCKED` job claims;
- fenced lease tokens and versions;
- heartbeat/expiry semantics;
- bounded retry with jitter;
- poisoned-job/dead-letter handling;
- stale-job sweeping and reconciliation.

The local foundation demo intentionally remains synchronous.

## Operator GUI

The GUI provides focused workspaces for endpoints, model inventory, generation, charts, and reports. The official launcher binds to loopback only. Provider destinations and secret transport are treated as security boundaries, not simple convenience settings.

![Operator workflow](assets/images/ui-workflow.webp)

## Analysis and charts

WE3's GUI includes model-comparison, success/outcome, Wilson-confidence, per-prompt heatmap, timing, token, correlation, radar, cross-run, code/security-awareness, and execution-timeline views.

![Metric views](assets/images/metrics-gallery.webp)

![Performance views](assets/images/performance-gallery.webp)

Screenshots are presentation evidence. Run JSON, report sidecars, hashes, and stored artifacts remain authoritative for exact values.

## Security and operations

Repository modules and deployment files cover OIDC/project-scoped authorization, streaming request-body limits, encrypted evidence storage, secret handling, audit chains, telemetry/tracing, backup/recovery, Caddy-only production ingress, internal database/cache/observability networks, and hardened container settings.

For assurance claims and residual risk, use the [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md) rather than inferring production readiness from source presence.
