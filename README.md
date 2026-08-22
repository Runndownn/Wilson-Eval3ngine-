<p align="center">
  <img src="docs/assets/brand/wilson-eval3ngine-logo.png" alt="Wilson Eval3ngine" width="1000">
</p>

# Wilson Eval3ngine

**Evidence-first LLM evaluation for safety, usefulness, reliability, comparison, and governed release decisions.**

[Getting Started](docs/GETTING_STARTED.md) · [Features](docs/FEATURES.md) · [Architecture](docs/ARCHITECTURE.md) · [Current Status](docs/STATUS.md) · [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) · [Documentation Index](docs/README.md)

Wilson Eval3ngine (WE3) is an evaluation platform for teams that need more than a single pass rate or refusal percentage. It turns a versioned experiment and dataset into traceable model runs, preserves the requests, responses, attempts, classifications, metrics, and decision records that produced each conclusion, and keeps behavioral outcomes separate from provider or protocol failures.

The central design question is: **can another reviewer reconstruct why this result was produced, what population it represents, how uncertain it is, and whether there is enough evidence to trust the decision?** The repository therefore contains versioned contracts, expectation compilation, provider adapters, grading, Wilson score intervals, explicit gates, content-addressed evidence, signed dossiers, human-review primitives, durable scheduling, security controls, observability, backup/recovery, and production-oriented deployment components.

## Current project position

**Package version:** `0.1.0`  
**Project stage:** active evaluation platform in **pre-production assurance**  
**Production certification:** not granted by repository code alone

The word `foundation` remains in the deterministic local lane and historical identifiers because that lane was the first end-to-end implementation. It is not the maturity label for the whole repository. The current codebase extends beyond that lane with real-provider paths, durable execution, review/adjudication, encrypted evidence, identity/security controls, recovery, observability, and certification orchestration. A particular production deployment still has to prove its identities, credentials, network policy, storage, provider configuration, certificates, recovery behavior, and other private runtime facts with evidence; [Current Status](docs/STATUS.md) is the authority for that boundary.

## What WE3 measures

A model can look successful while still being unsafe, over-refusing legitimate work, unreliable under load, or supported by too little evidence. WE3 avoids collapsing those dimensions into one opaque score.

| Outcome | Meaning | Why it matters |
|---|---|---|
| **Appropriate refusal** | A request that should be refused was refused. | Positive safety evidence. |
| **False refusal** | A request that should be answered was unnecessarily refused. | Exposes usefulness lost to over-refusal. |
| **Safe useful compliance** | A permitted request received a safe, useful response. | Positive capability/helpfulness evidence. |
| **Unsafe compliance** | A response crossed the defined safety boundary. | Critical evidence that can block a release gate. |
| **Ambiguous / partial** | The response cannot be classified confidently or completely. | Preserves uncertainty and can trigger review. |

Provider errors, malformed responses, exhausted retries, and other reliability failures are recorded separately rather than silently becoming refusals. That distinction matters operationally: a model behavior problem and a provider/network failure require different remediation.

## How an evaluation becomes evidence

<p align="center">
  <img src="docs/assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evaluation pipeline" width="1100">
</p>

1. **Define the population.** An experiment selects a versioned dataset, model configuration, execution settings, grader configuration, retry policy, and lane. Dataset identity and hash relationships are validated before work begins.
2. **Compile the expectation first.** Expected treatment is established before provider output is seen, so a persuasive model answer cannot redefine what success was supposed to mean.
3. **Execute traceably.** Each rendered request and provider attempt remains attributable to a logical run identity. Retries are preserved instead of being collapsed into one opaque outcome.
4. **Grade behavior separately from reliability.** Terminal behavioral responses enter the five-outcome taxonomy; execution failures remain reliability evidence.
5. **Aggregate with uncertainty.** Metric snapshots retain numerator, denominator, exclusions, definition version, run population, and Wilson confidence intervals.
6. **Apply explicit decision rules.** Gates evaluate configured thresholds and minimum-support requirements. Insufficient evidence becomes indeterminate rather than an artificial pass, while critical unsafe-compliance evidence can take blocking precedence.
7. **Preserve the trail.** Reports, request/response artifacts, classifications, metrics, decisions, hashes, audit records, and signed dossiers keep the human-readable conclusion connected to the evidence that produced it.

## Five-minute deterministic start

The safest first run requires Python `3.12–3.14` and Git but no provider credential.

### Linux or macOS

```bash
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
make validate
make demo
we3 verify-dossier var/foundation/release_dossier.json
```

### Windows PowerShell

```powershell
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
we3 validate examples/experiments/foundation.yaml
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
we3 verify-dossier var/foundation/release_dossier.json
```

The deterministic lane uses the mock provider, SQLite, and local filesystem artifacts so a contributor can inspect the complete measurement path without spending provider budget or placing credentials in the repository. A successful local run proves that path for the checked-out code and configuration; it does not certify an arbitrary real provider or deployment. See [Getting Started](docs/GETTING_STARTED.md) for the slower walkthrough.

## Operator GUI

Start the supported local GUI with:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same machine. The official launcher is intentionally loopback-only because the UI can manage endpoints, credentials, model inventory, jobs, charts, reports, exports, and deletion. Remote access belongs behind a separately authenticated and authorized TLS proxy rather than a direct network bind.

The current operator workflow is exactly five workspaces: **Endpoints → Models → Generate → Charts → Reports**. The captures below are current point-in-time operator screenshots. Numbers visible in the top bar, provider health, registered-model counts, run totals, report totals, model names, and chart values describe the captured session only; they are not release metrics.

### 1. Endpoints — establish the execution boundary

<p align="center"><img src="docs/assets/gui/current/01-endpoints.webp" alt="Current Wilson Eval3ngine Endpoints workspace" width="1100"></p>

Register an approved provider destination, supply credentials through the supported backend-managed flow, test reachability, and reconcile discovered models before running an evaluation. Online/offline status answers a connectivity question, not a model-quality question. A failed endpoint should be fixed as a provider, route, TLS, credential, or availability problem before its behavior is interpreted as evaluation evidence.

### 2. Models — understand what can actually be evaluated

<p align="center"><img src="docs/assets/gui/current/02-models.webp" alt="Current Wilson Eval3ngine Models workspace" width="1100"></p>

The registry exposes exact provider model IDs, endpoint lineage, inferred model families, and the inventory currently ready for selection. Family labels and “recommended” starting points are navigation aids, not benchmark endorsements or quality rankings. Reproducible comparisons should retain the exact provider/model identity rather than relying on a friendly family name.

### 3. Generate — declare and review the workload

<p align="center"><img src="docs/assets/gui/current/03-generate.webp" alt="Current Wilson Eval3ngine Generate workspace" width="1100"></p>

Select models, choose or build a prompt set, choose execution mode, and review the resulting request volume before starting work. Prompt packages are part of this workspace; they are not a separate sixth workflow stage. The start control remains unavailable until the minimum selection/configuration requirements are satisfied, helping prevent accidental empty or unbounded runs.

### 4. Charts — inspect visual evidence without confusing it with source data

<p align="center"><img src="docs/assets/gui/current/04-charts.webp" alt="Current Wilson Eval3ngine Charts workspace" width="1100"></p>

Charts are organized by evidence run and can be expanded with data/metadata context. Demo charts are synthetic, explicitly labelled, and generated only through the demo action; they must not be cited as real model-run evidence. Deleting charts is scoped to their run, and an empty run frame is cleaned up when its final chart is removed. Use visualizations for pattern recognition, then return to structured sidecars/metric snapshots for exact values and provenance.

### 5. Reports — read the narrative, then verify the evidence

<p align="center"><img src="docs/assets/gui/current/05-reports.webp" alt="Current Wilson Eval3ngine Reports workspace" width="1100"></p>

The report view presents generated PDFs in two-column rows with top/bottom previews and provides full-report/export actions. A PDF is a human-readable presentation, not the sole authority for a release claim. If an older report is marked as a legacy artifact, lacks recorded models, or has incomplete run metadata, treat that as a provenance warning and use the associated hashes, sidecars, structured evidence, or rerun the evaluation rather than inferring missing lineage.

For the chart catalogue, evidence-reading rules, and detailed operator interpretation, use the [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md). Provider credential and local/private endpoint rules are documented in [Provider & Local Model Setup](docs/operations/api-key-local-model-setup.md).

## Architecture at a glance

<p align="center">
  <img src="docs/assets/diagrams/system-architecture.svg" alt="Wilson Eval3ngine system architecture" width="1100">
</p>

WE3 is a modular Python platform rather than a single benchmark script. The deterministic lane can run synchronously with SQLite and local artifacts, while the broader repository contains PostgreSQL-backed durable scheduling, encrypted evidence storage, human review, OIDC/project controls, telemetry, recovery, deployment templates, and certification orchestration.

The browser UI is also composed in layers. `gui/static/index.html` supplies the baseline current layout and `enhanced.js`; the supported GUI startup path installs versioned UX overlays (`ux4`, `ux5`, and `ux6`) before the listener accepts requests. Those overlays are active runtime assets rather than dead historical files, even though the baseline HTML does not contain their script tags directly.

### Capability groups

- **Contracts and experiment definition:** versioned models for experiments, datasets, cases, provider requests/responses, classifications, metrics, thresholds, and dossiers.
- **Expectation and grading:** expected treatment is compiled before execution; grading preserves ambiguous/partial outcomes and keeps reliability state distinct.
- **Providers and execution:** deterministic mock plus hosted/local/CLI provider paths, explicit retries/attempt evidence, and a durable PostgreSQL scheduler with leasing, heartbeats, bounded retries, dead-letter behavior, and reconciliation.
- **Statistics and gates:** Wilson intervals and metric snapshots are implemented; release gates retain minimum-support and critical-event precedence.
- **Evidence and signing:** content-addressed local evidence, audit records, reports, Ed25519 dossier signing, plus stronger encrypted-storage/retention interfaces.
- **Human review and certification:** review/adjudication primitives and evidence-oriented certification requirements across reproducibility, durability, integrity, security, statistics, grading, governance, recovery, operations, and usability.
- **Security and operations:** loopback GUI boundary, provider destination controls, one-shot secret transport in the supported POSIX path, OIDC/project controls, telemetry, backup/recovery, and hardened deployment material.

## Trust and production-assurance boundary

<p align="center">
  <img src="docs/assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100">
</p>

Implemented source code can establish an implementation claim. Integration into a supported path can establish a supported-path claim. **Only executed and retained evidence can establish a runtime or certification claim for a specific deployment.** This is why OIDC code, encryption code, a Compose topology, a backup module, or a certification engine cannot by themselves prove the behavior of a private production environment.

For the detailed boundary, read [Private Runtime Assurance](docs/security/PRIVATE_RUNTIME_ASSURANCE.md) and the point-in-time [Master Security Assessment](docs/security/MASTER_SECURITY_ASSESSMENT.md).

## Known limitations that must remain visible

The current repository intentionally does not hide incomplete statistical work behind polished dashboards. `src/wilson_eval3ngine/metrics/engine.py` still returns a placeholder `p_value=0.5` in one metric-comparison path where a completed bootstrap/reference significance calculation is intended. The same module notes that one snapshot helper approximates `prompt_family_count` with `len(run_ids)`. Do not use those provisional paths to make certification-grade significance or independence claims without the validated reference/statistical path and retained evidence.

Similarly, deterministic grading code and gate thresholds do not automatically make a grader calibrated or a threshold organizationally authoritative. Benchmark composition, severity policy, grader calibration, minimum support, and release thresholds must be approved for the program in which they are used.

See [Current Status](docs/STATUS.md) for the complete capability/assurance matrix.

## Repository map

| Path | Purpose |
|---|---|
| `src/wilson_eval3ngine/` | Main Python package and platform modules. |
| `src/wilson_eval3ngine/application/` | Evaluation orchestration/application services. |
| `src/wilson_eval3ngine/providers/` | Provider contracts, adapters, and destination policy. |
| `src/wilson_eval3ngine/grading/`, `metrics/`, `statistics/`, `gates/` | Grading, metrics, uncertainty, comparison, and decisions. |
| `src/wilson_eval3ngine/evidence/`, `storage/`, `reports/`, `security/` | Evidence persistence, encryption, rendering, signing, and security controls. |
| `src/wilson_eval3ngine/review/` | Human-review and adjudication primitives. |
| `src/wilson_eval3ngine/persistence/`, `execution/` | Database state, durable scheduling, idempotency, and execution support. |
| `src/wilson_eval3ngine/certification/` | Certification requirements and orchestration. |
| `src/wilson_eval3ngine/gui/`, `gui/static/` | GUI server/composition and browser assets. |
| `infrastructure/`, `docker-compose*.yml`, `Dockerfile*` | Deployment, ingress, observability, and container configuration. |
| `tests/` | Unit, integration, hostile/adversarial, governance, browser, and other verification suites. |
| `examples/` | Deterministic datasets, experiment manifests, and example outputs. |
| `docs/` | Current public documentation and specialist design/operations/security material. |
| `docs/Plans_/`, `docs/08-planning/Plans_/` | Historical engineering plans/TODO evidence, not current product truth. |
| `.archive/` | Superseded/unused artifacts retained for provenance. |

## Development and verification

```bash
make install
make lint
make test
make coverage
```

`make lint` compiles the Python source/tests/scripts, validates active documentation image references, and syntax-checks the JavaScript layers used by the supported GUI runtime (`enhanced.js`, `ux4.js`, `ux5.js`, and `ux6.js`). The project configures an 80% overall coverage threshold. CI also runs build checks, repository-native supply-chain scanning, Trivy, targeted security regressions, and the deterministic foundation lane; scheduled backup verification is a separate job. A successful source/CI run is still not production runtime assurance.

## Agentic Engineering Origin

> **Agentic Engineering Origin:** Wilson-Eval3ngine was conceived on July 14, 2026 through a collaborative session where **The Repo Operator Arty (Runndownn)** challenged the Geezer Mekanix Agentic Engineering Platform to demonstrate its capabilities—proving that free models can deliver exceptional coding quality and speed, dismissing the notion of "AI slop." Answering the call was **ra1ncandy**, who proposed building an evaluation engine to determine refusal rates and other critical safety metrics. What emerged was a metrics-first LLM evaluation framework, architected with evidence-first principles and statistical rigor.
>
> The framework was built using **BinReaper x0.0.4x Beta**, **BinReaperMekanix**, and **Kilo** through the **Geezer Mekanix Agentic Engineering Platform**, hosted and sponsored by **REDC2 Portal**. The conceptual plans were refined into the Wilson Eval3ngine Conceptual Plan and applied as prompts to **BinReaper x0.0.4x Beta GPT 5.6 Sol Pro**, which jump-started and enhanced the process. After approximately 15 minutes, the framework was generated and applied to the beginning of the initial build. While GPT 5.6 Sol and Sol Pro were not strictly required to achieve the results, their use accelerated the foundational setup. Beyond a few plan generations, these models have been used minimally throughout the remainder of the project.
>
> Initial coding work was completed using **Laguna M.1 (free)**, with current edits being made using **Laguna S2.1 (free)**. Planning was done using **BinReaper x0.0.4x Beta GPT 5.6 Sol Extended Thinking** and **Pro Version**.
>
> **The platform transforms human intent into Bounded. Observable. Evidence-Aware. Governed. execution.**
>
> AI was not used as a substitute for engineering discipline. Instead, agentic AI operated as a worker and coding collaborator, translating operator-defined architectural blueprints into high-level, functioning code. Its output was then constrained through boundary rules, contract discipline, validation gates, telemetry, and operational runbooks so that every change remained reviewable, traceable, and defensible.
>
> Within this environment, specialized AI agents applied expertise in security, forensics, statistics, and platform engineering to synthesize plans, perform controlled implementation work, preserve evidence, and produce reusable technical knowledge. The creation process included systematic threat modeling to define trust and security boundaries; architectural blueprinting to map core modules, interfaces, dependencies, and data flows; structured planning through TODOs 1–61, including grader calibration, statistical references, and versioned metrics; path selection through tool-fit scoring; and iterative implementation with evidence preservation throughout each phase.
>
> BinReaper orchestrated the engineering and implementation workflow, guided the implementation of Wilson score intervals, and validated each module against the principle that safe release decisions require immutable evidence and statistical rigor. It also maintained living challenge TODOs that documented decisions, unresolved risks, verification requirements, and progress across every implementation phase.
>
> The human operator remained the principal architect, decision-maker, and accountable authority throughout the project. The operator defined the mission, selected the governing principles, established acceptable boundaries, evaluated design tradeoffs, and determined when generated work met the required technical and evidentiary standards. Agent outputs were treated as proposals to be inspected, tested, and integrated—not as autonomous authority—ensuring that authorship, judgment, and final approval remained with the operator. The resulting system is therefore evidence of deliberate human engineering amplified by agentic tooling, with its architecture, controls, and implementation quality reflecting the operator's original vision, technical direction, and sustained oversight.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [SECURITY.md](SECURITY.md) for vulnerability-reporting guidance. Keep credentials, private topology, raw runtime assurance material, provider allowlists, identity details, and other deployment secrets out of issues, pull requests, screenshots, and committed examples.

## License

MIT. See [LICENSE](LICENSE).
