# Wilson Eval3ngine — Metrics-First LLM Evaluation

**Version:** `0.1.0` · **Release tier:** `foundation` · **Status:** `not approved for production certification` · **Python:** `3.12–3.14`

Wilson Eval3ngine (WE3) is an evidence-first framework for evaluating whether an LLM is safe, useful, reliable, and sufficiently supported for a release decision. It compiles expectations before execution, preserves content-addressed evidence, classifies five outcome families, computes statistical uncertainty, and applies deterministic release gates. Repository implementation is not the same as production certification; current findings, validation evidence, residual risk, and blocked checks are maintained in [`docs/security/MASTER_SECURITY_ASSESSMENT.md`](docs/security/MASTER_SECURITY_ASSESSMENT.md).

## Outcome model

| Outcome | Meaning | Gate effect |
|---|---|---|
| Appropriate Refusal | Correctly refuses a harmful or disallowed request | Positive safety evidence |
| False Refusal | Refuses a request that should be answered | Helpfulness failure |
| Safe Useful Compliance | Answers safely, correctly, and usefully | Positive capability evidence |
| Unsafe Compliance | Produces materially unsafe or disallowed assistance | Critical failure |
| Ambiguous / Partial | Incomplete, malformed, or indeterminate response | Review or indeterminate |

## Architecture

```mermaid
flowchart LR
    U[Operator or API client] --> X[Experience plane]
    X --> C[Control plane]
    C --> Q[Execution plan and durable state]
    Q --> P[Provider adapters]
    P --> H[Hosted providers]
    P --> L[Approved local or CLI providers]
    Q --> E[Evidence and grading]
    E --> M[Metrics and release gates]
    E --> A[Reports, charts, exports, hashes]
    M --> A
```

This diagram shows the path from a user-visible workflow to provider execution, evidence, metrics, and release artifacts. It is useful for locating the authoritative boundary for each validation, authorization, network, and provenance decision. Consult it before changing provider adapters, job state, grading, reports, or release gates.

```mermaid
flowchart TB
    B[Browser] -->|loopback only| G[Operator GUI]
    G --> S[Encrypted endpoint state]
    G --> J[Evaluation job]
    J --> F[One-shot FIFO credential handoff]
    F --> R[Report child]
    R --> P[Approved provider destination]
    R --> O[PDF and JSON sidecars]
    O --> C[Charts and export manifest]
```

This diagram shows the local operator trust boundary and the credential path used by report generation. It is useful for understanding why the GUI is loopback-only and why a mode-0600 regular file was replaced by a one-shot FIFO. Consult it when changing endpoint storage, report subprocesses, local providers, or cleanup behavior.

```mermaid
flowchart LR
    I[Internet] --> T[Caddy TLS ingress]
    T --> API[WE3 API]
    API --> DB[(PostgreSQL)]
    API --> REDIS[(Redis)]
    API --> METRICS[Prometheus]
    METRICS --> GRAFANA[Grafana]
    subgraph Internal networks
      API
      DB
      REDIS
      METRICS
      GRAFANA
    end
```

This diagram shows the production network invariant: only Caddy publishes host ports while data and observability services remain internal. It is useful for detecting reverse-proxy bypass, weak bootstrap credentials, and monitoring-plane exposure. Consult it during Compose, Caddy, firewall, certificate, or service-discovery changes.

```mermaid
flowchart LR
    PR[Commit or pull request] --> Q[Lint, unit, integration, security tests]
    Q --> B[Wheel and source build]
    B --> S[Supply-chain and container checks]
    S --> V[Foundation validation]
    V --> AT[Attestation on approved main push]
    Q --> EV[Machine-readable evidence]
    S --> EV
    V --> EV
```

This diagram shows the assurance path from source change to tested artifact and provenance evidence. It is useful for separating advisory checks from release gates and for preventing untested artifacts from being attested. Consult it before changing workflow triggers, permissions, dependencies, scanners, build steps, or signing.

## Capability map

| Domain | Primary capabilities | Primary locations |
|---|---|---|
| Contracts | Versioned Pydantic and JSON schemas | `src/wilson_eval3ngine/domain/`, `contracts/` |
| Expectations | Dataset, policy, and rubric compilation | `src/wilson_eval3ngine/expectations/` |
| Providers | Hosted, local, CLI, scope and fingerprint controls | `src/wilson_eval3ngine/providers/` |
| Execution | Logical runs, retries, progress, job state | scheduler and GUI application modules |
| Grading | Five-outcome classification and calibration | `src/wilson_eval3ngine/grading/` |
| Metrics | Wilson intervals, populations, snapshots | `src/wilson_eval3ngine/metrics/`, `statistics/` |
| Gates | Threshold and critical-event decisions | `src/wilson_eval3ngine/gates/` |
| Evidence | Hashes, sidecars, reports, dossiers, exports | evidence, storage, reports, GUI artifact paths |
| Review | Blind review, recusal, adjudication | `src/wilson_eval3ngine/review/` |
| API security | OIDC hooks, project scope, CSRF, CORS, rate limits, actual streamed-body limits | `src/wilson_eval3ngine/api/`, `security/` |
| GUI security | Loopback binding, endpoint egress policy, one-shot report secret transport | `src/wilson_eval3ngine/gui/` |
| Deployment | Wheel-based image, internal service networks, stock Caddy ingress | `Dockerfile.prod`, `docker-compose.prod.yml`, `infrastructure/caddy/` |
| Assurance | CI, supply-chain checks, focused hardening workflow, master report | `.github/workflows/`, `tests/`, `docs/security/` |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

we3 validate examples/experiments/foundation.yaml
we3 run examples/experiments/foundation.yaml \
  --output var/foundation \
  --database-url sqlite:///./var/we3.db \
  --artifact-root var/artifacts
we3 verify-dossier var/foundation/release_dossier.json
python -m pytest -q
```

Windows PowerShell activation differs, but the WE3 commands remain the same after the environment is active.

## Operator GUI

Start the supported launcher:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. The launcher rejects non-loopback addresses because the GUI controls endpoint credentials, model discovery, evaluation execution, evidence, exports, cancellation, and deletion without a built-in multi-user identity layer. Remote operation requires a separately authenticated TLS proxy connected to the loopback listener; do not expose the GUI directly through a wildcard, LAN, VPN, or public bind.

### Workflow

| Step | Tab | Operator action | Resulting evidence or state |
|---|---|---|---|
| 1 | Endpoints | Register and test a canonical provider URL | Encrypted endpoint record and safe health state |
| 2 | Models | Discover, filter, and inspect exact provider model IDs | Model registry linked to endpoint lineage |
| 3 | Generate | Select models, prompts, execution mode, timeout, and failure policy | Bounded job plan and progress state |
| 4 | Charts | Generate or reuse charts from valid evaluation sidecars | Run-bound PNGs and metadata |
| 5 | Reports | Inspect PDFs, hashes, run metadata, and exports | Evidence review and portable bundle |

### Hosted and local providers

Public providers must use canonical HTTPS URLs. Embedded credentials, unsafe address classes, and automatic redirect following are blocked by the GUI policy. Local/private providers require an explicit opt-in:

```bash
WE3_GUI_ALLOW_LOCAL_PROVIDERS=1 we3-gui-start --host 127.0.0.1 --port 8080
```

The opt-in does not permit link-local, cloud metadata, multicast, unspecified, or reserved destinations and does not replace host/container egress policy. Detailed credential, rotation, local Ollama, CLI, and production-secret guidance is in [`docs/operations/api-key-local-model-setup.md`](docs/operations/api-key-local-model-setup.md).

### Credential handling

Credentials are accepted through password inputs, encrypted before endpoint persistence, omitted from browser responses, and represented in logs by a constant redaction marker. The official POSIX launcher replaces the legacy regular plaintext report-key file with a bounded, mode-0600 one-shot FIFO inside a mode-0700 directory, then clears parent memory and removes the path during cleanup. This local backend is not an external vault and does not protect against compromise of the same operating-system account.

### Report and chart layout

At desktop widths of 1024 CSS pixels and above, the Reports tab uses exactly two equal columns with aligned outer edges. Below that breakpoint it uses one column, and long names or hashes wrap without forcing horizontal overflow. Chart windows are clamped after drag, resize, zoom, browser resize, and visual-viewport changes, and include a reset control.

## Chart catalogue

Runtime values must come from each run's evaluation sidecars and manifest; screenshots and generated examples are explanatory only. The gallery supports radar, latency bars and trends, distributions, box plots, token/latency scatter, token usage, code/security signals, Wilson confidence intervals, outcome distributions, correlations, repository evolution, timelines, and prompt success views. Each chart exposes its run, model set, prompt count, category, description, file path, and size where available.

Representative repository examples include:

- [`radar.png`](gui/static/charts/test-run-final/radar.png)
- [`response_times.png`](gui/static/charts/test-run-final/response_times.png)
- [`confidence_intervals.png`](gui/static/charts/test-run-final/confidence_intervals.png)
- [`stacked_outcomes.png`](gui/static/charts/test-run-final/stacked_outcomes.png)
- [`correlation_heatmap.png`](gui/static/charts/test-run-final/correlation_heatmap.png)
- [`timeline.png`](gui/static/charts/test-run-final/timeline.png)

A chart is not a release decision by itself; reviewers must inspect source counts, uncertainty, outcome severity, run provenance, and unresolved evidence.

## PDF reports and exports

Generated reports may include model and run identity, prompt-level results, timings, token counts, outcomes, metric summaries, uncertainty, evidence hashes, and linked JSON sidecars. New artifacts are associated with one run and exposed through validated report names, same-origin PDF viewing, deletion controls, and ZIP export. Historical artifacts without complete provenance should be marked as legacy or unverified rather than treated as certification evidence.

## Production deployment

The production image builds the complete source into a wheel, installs from a builder-produced wheelhouse, runs declared Uvicorn as UID/GID 10001, and exposes only port 8000 inside the container network. Production Compose publishes only Caddy ports 80 and 443; API, PostgreSQL, Redis, Prometheus, and Grafana remain internal. Prometheus administrative/lifecycle APIs are disabled and Caddy uses only stock directives from the official image.

Required production configuration:

```text
WE3_POSTGRES_PASSWORD
WE3_DATABASE_URL
WE3_REDIS_PASSWORD
WE3_REDIS_URL
WE3_GRAFANA_PASSWORD
WE3_OIDC_ISSUER
WE3_OIDC_JWKS_URI
WE3_DOMAIN
WE3_TLS_EMAIL
```

`WE3_DATABASE_URL` and `WE3_REDIS_URL` must be complete, independently encoded URLs rather than strings assembled from raw passwords. Supply all production values through an approved secret/configuration mechanism; the Compose file intentionally has no known credential fallback.

Synthetic configuration validation:

```bash
WE3_POSTGRES_PASSWORD=test-postgres \
WE3_DATABASE_URL=postgresql+psycopg://we3:test-postgres@postgres:5432/we3 \
WE3_REDIS_PASSWORD=test-redis \
WE3_REDIS_URL=redis://:test-redis@redis:6379/0 \
WE3_GRAFANA_PASSWORD=test-grafana \
WE3_OIDC_ISSUER=https://issuer.invalid \
WE3_OIDC_JWKS_URI=https://issuer.invalid/jwks \
WE3_DOMAIN=example.invalid \
WE3_TLS_EMAIL=security@example.invalid \
docker compose -f docker-compose.prod.yml config >/dev/null
```

These values are non-routable examples and must not be deployed.

## Request and browser security

The production API stack includes structured logging, tracing, response security headers, distributed or fallback rate limiting, explicit CORS, content-type validation, CSRF policy, and a stream-aware body limit. The body guard validates decimal `Content-Length` when present, rejects conflicting values, and independently counts actual ASGI request bytes for chunked, HTTP/2, or missing-length bodies. Public errors contain stable safe codes rather than body content or secret-bearing exception details.

## Tests and validation

Repository-local commands:

```bash
make lint
make test
make coverage
python -m build
```

Focused hardening coverage:

```bash
python -m pytest -q \
  tests/governance/test_production_deployment_contract.py \
  tests/unit/test_gui_secret_transport.py \
  tests/unit/test_gui_ux6.py \
  tests/unit/test_streaming_body_limit.py \
  tests/unit/test_gui_bind_security.py \
  tests/unit/test_gui_egress_policy.py \
  tests/governance/test_ci_security_contract.py
```

The branch-local `Hardening validation` workflow runs focused tests and synthetic Compose validation on `security/**` pushes. The main CI workflow covers lint, full tests, coverage, build, repository-native supply-chain analysis, Trivy, foundation validation, and main-branch provenance attestation. A documented command is not considered passed until its exit status and environment are recorded in the master report or CI.

## Security status and known residual risk

Current repository hardening includes loopback-only GUI binding, provider destination controls, one-shot report credential transport, internal production service networks, mandatory production secrets, stock-Caddy routing, deterministic report geometry, chart viewport containment, and actual streamed-body limits. Remaining work includes a complete local inventory, production image and Caddy execution evidence, browser geometry/accessibility runs, unified report-script and GUI egress policy, image digest pinning, an external production secret-store adapter, database TLS deployment policy, and production runtime verification. No maintainer risk acceptance is implied by this list.

## Repository map

| Path | Purpose |
|---|---|
| `contracts/` | Versioned schemas and OpenAPI artifacts |
| `src/wilson_eval3ngine/domain/` | Domain models and state transitions |
| `src/wilson_eval3ngine/providers/` | Provider adapters, registry, scope, fingerprints |
| `src/wilson_eval3ngine/grading/` | Classification and calibration |
| `src/wilson_eval3ngine/metrics/` | Metric computation and snapshots |
| `src/wilson_eval3ngine/gates/` | Release decisions |
| `src/wilson_eval3ngine/api/` | Production API and middleware |
| `src/wilson_eval3ngine/gui/` | Operator application, runtime, jobs, and secure launcher |
| `gui/static/` | Browser assets, charts, and report presentation |
| `tests/` | Unit, integration, resilience, governance, and security tests |
| `docs/` | Architecture, operations, reports, assessments, and guides |
| `infrastructure/` | PostgreSQL, Caddy, Prometheus, Grafana, and infrastructure configuration |
| `scripts/` | Report, chart, validation, and operational tooling |

## Documentation

- [GUI and Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md)
- [Provider Credentials and Local Model Endpoints](docs/operations/api-key-local-model-setup.md)
- [Master Security Assessment](docs/security/MASTER_SECURITY_ASSESSMENT.md)
- [Backup and Recovery Runbook](docs/operations/backup-recovery-runbook.md)

## Responsible operation

Use WE3 only with providers, data, systems, and credentials you are authorized to access. Keep real secrets and private topology out of source, issues, pull requests, screenshots, logs, and example files. Treat prompts, model outputs, reports, imported datasets, and attachments as untrusted content throughout storage, grading, rendering, export, and review.
