<p align="center">
  <img src="docs/assets/brand/wilson-eval3ngine-logo.png" alt="Wilson Eval3ngine" width="1000">
</p>

# Wilson Eval3ngine

**Evidence-first LLM evaluation for safety, usefulness, reliability, comparison, and governed release decisions.**

[Getting Started](docs/GETTING_STARTED.md) · [Features](docs/FEATURES.md) · [Architecture](docs/ARCHITECTURE.md) · [Current Status](docs/STATUS.md) · [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) · [Security](SECURITY.md) · [Documentation Index](docs/README.md)

## Executive summary

Wilson Eval3ngine (WE3) is a metrics-first evaluation platform for turning a versioned experiment and dataset into traceable provider attempts, behavior classifications, uncertainty-aware measurements, explicit release decisions, and reviewable evidence. Its governing question is not merely *“what score did the model get?”* but *“what population was evaluated, what happened, how much support exists, which rule produced the decision, and can another reviewer reconstruct the lineage?”*

The repository now spans four connected concerns. The **evaluation core** validates contracts, compiles expected treatment before model output, executes deterministic or approved provider adapters, grades behavior, computes metric snapshots and Wilson intervals, and applies support-aware gates. The **evidence plane** preserves attempt, classification, metric, report, audit, and signature lineage. The **operator plane** exposes CLI, API, and a five-workspace GUI. The **assurance plane** adds project isolation, OIDC, audited authorization, distributed security state, deployment hardening, encrypted evidence storage, telemetry, and native PostgreSQL backup/WAL/PITR recovery.

The current package version is **`0.2.0`**. This is a pre-1.0 milestone representing the repository after the July 14 foundation slice expanded into the current platform; it is not a claim of production certification. Source can establish that behavior is implemented and composed, while real provider behavior, production identity, networking, managed key custody, destructive restore success, calibrated program thresholds, and release approval still require executed evidence. [Current Status](docs/STATUS.md) is the authority for those boundaries.

What distinguishes WE3 is the separation it tries to preserve everywhere: **policy from observation, behavior from infrastructure failure, evidence from presentation, implementation from runtime assurance, and agent-assisted execution from human authority.**

## What the system can do

WE3 can run a credential-free deterministic evaluation lane or dispatch through governed real-provider adapters; retain individual attempts and retry/failure states; classify valid terminal behavior into five outcome families; build versioned metric snapshots with explicit numerators, denominators, exclusions, population lineage, and confidence intervals; compare compatible independent-binomial proportions; apply support and critical-event release gates; route cases through review/adjudication; generate canonical reports and signed dossiers; serve operator workflows through CLI/API/GUI surfaces; protect production-facing paths with identity, authorization, rate-limit, content, and audit controls; and preserve database recovery evidence through encrypted backup, WAL, and PITR workflows.

Those capabilities are deliberately not collapsed into one maturity claim. A deterministic local run can prove the checked-out measurement path. It cannot certify a hosted provider, private deployment, identity provider, managed KMS, firewall policy, or recovery objective.

## Current project and implementation status

**Version:** `0.2.0`  
**Stage:** active evaluation platform / pre-production assurance  
**Origin:** July 14, 2026  
**Production certification:** not established by repository source alone

The current implementation is materially broader than the original “foundation” lane. `foundation` remains in historical identifiers and examples because it was the first complete vertical slice, not because the whole repository is still limited to that slice. Current source contains real-provider paths, durable PostgreSQL scheduling, review/adjudication, encrypted evidence, exact project/role authorization, shared Redis security state, operator GUI workflows, production-oriented deployment material, observability, certification orchestration, and native encrypted backup/WAL/PITR recovery.

Important remaining boundaries are evidence boundaries rather than hidden deficiencies. The synchronous API operation registry is still process-local even though durable long-running execution belongs to the PostgreSQL scheduler. Bearer revocation does not sender-bind a stolen unexpired token. Reviewer pattern masking is not a complete DLP system. Real-provider correctness, grader calibration, threshold authority, production network controls, and recovery objectives require target-environment evidence.

## Architecture: how the pieces relate

The following system view is included first because it establishes the conceptual layers before the more detailed control and evidence flows.

<p align="center"><img src="docs/assets/diagrams/system-architecture.svg" alt="Wilson Eval3ngine system architecture" width="1100"></p>

At the top, operators use the loopback GUI, CLI, or REST API. Application/orchestration services validate work and coordinate execution. The lower layer separates the evaluation core, provider boundary, evidence/state services, and governance/operations. The deployment boundary underneath them is intentionally a different concern: Caddy, API, PostgreSQL, Redis, monitoring, and private configuration can compose the software, but a production claim only becomes valid when the deployed environment supplies corresponding runtime evidence.

The architecture is therefore not a chain of interchangeable modules. Provider execution may fail while the evaluation contract remains valid; grading may be valid while support is insufficient; a report may render correctly while provenance is incomplete; and source may implement a control whose target deployment has not yet demonstrated it.

## Evaluation and evidence flow

This pipeline shows how a declared experiment becomes a decision-bearing artifact. It is the central measurement contract of the project.

<p align="center"><img src="docs/assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evaluation pipeline" width="1100"></p>

The key ordering property is that expected treatment is compiled **before** the target response is observed. Provider requests and retries then produce attempt evidence. Valid terminal behavior is graded without turning timeouts, malformed responses, exhausted retries, authentication failures, or other operational problems into behavioral labels. Metric snapshots retain the exact support and population context, and release gates fail closed to an indeterminate state when evidence is insufficient.

Compatible independent-binomial proportions can be compared with the implemented two-sided pooled two-proportion test. The engine does not pretend that paired, clustered, repeated-prompt, or otherwise dependent designs are independent; those designs require their own calibrated method. Likewise, the generic metric snapshot helper does not infer prompt-family independence from run count. Callers provide real family lineage or the support count remains zero.

## Trust and governance boundaries

The next diagram exists to show where implementation authority stops and runtime assurance begins.

<p align="center"><img src="docs/assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100"></p>

The supported API has one authoritative implementation for each request-security control. Shared observability and response policy live separately from streaming byte enforcement, strict metadata/CORS/CSRF/rate-limit/revocation logic, and authorization-decision auditing. Staging/production distributed security state is Redis-backed and fails closed when its authority is unavailable. Forwarded client identity is trusted only from configured proxy networks, and real provider/model approval is governance data supplied by explicit reviewed policy rather than permanent source truth.

This boundary matters because source-controlled secure defaults are necessary but not sufficient. IdP issuer/JWKS rotation, proxy CIDRs, TLS, firewall/direct-port denial, real KMS/signing custody, provider credential scopes, Redis/PostgreSQL behavior under failure, and recovery exercises remain facts of the deployed environment.

## Generate: from operator intent to governed evidence

The Generate workflow is where user selection becomes an explicit workload, so it deserves both an operator screenshot and an architecture-level flow. The screenshot below is the canonical current Generate view already maintained by the repository; restoring it here fixes the root README omission without inventing a replacement interface.

<p align="center"><img src="docs/assets/gui/current/03-generate.webp" alt="Current Wilson Eval3ngine Generate workspace" width="1100"></p>

Generate binds exact model selection, prompt package or custom prompts, execution mode, prompt count, and total request volume before a job starts. That review step is operationally important because provider cost/traffic and the population the resulting evidence may describe are defined here. Prompt-package selection belongs inside Generate rather than in a separate sixth workflow stage.

The following flowchart shows what happens behind that interface.

<p align="center"><img src="docs/assets/diagrams/generation-workflow.svg" alt="Wilson Eval3ngine generation workflow" width="1100"></p>

The control plane fixes workload scope and lineage, then the execution plane compiles expectations and dispatches only through the selected provider boundary. Attempts become immutable evidence before grading and human review. Metric snapshots and gates consume that evidence, while charts and reports remain presentation surfaces rather than sole release authority. The visual is intentionally narrower than the full system architecture so a maintainer can see exactly where generation stops being configuration and becomes evaluation evidence.

## Operator workflow

The current GUI is exactly **Endpoints → Models → Generate → Charts → Reports**. These screenshots are point-in-time views of the operator application, not benchmark evidence; counters, model inventory, provider state, report totals, and demo charts describe the capture state only.

### Endpoints

The first workspace is shown because provider destination identity and connectivity must be understood before model inventory or evaluation results can be interpreted.

<p align="center"><img src="docs/assets/gui/current/01-endpoints.webp" alt="Current Wilson Eval3ngine Endpoints workspace" width="1100"></p>

Endpoints registers and tests approved provider destinations and reconciles their inventory. An `online` state means the configured connectivity check succeeded at that time; it does not mean that any model is safe, capable, or release-ready. Credential handling stays backend-managed, and provider egress is a distinct trust boundary from the GUI listener itself.

### Models

The model inventory view follows endpoints because reproducible runs depend on exact provider/model identity rather than friendly labels.

<p align="center"><img src="docs/assets/gui/current/02-models.webp" alt="Current Wilson Eval3ngine Models workspace" width="1100"></p>

Models exposes exact provider model IDs, endpoint lineage, filtering, family grouping, and readiness for selection. Family and “recommended” labels are navigation metadata, not benchmark endorsements. Real provider/model scope must come from explicit governance policy; the deterministic mock lane remains the only source-controlled default approval.

### Generate

Generate is displayed again in workflow order so the five-step interface can be read continuously.

<p align="center"><img src="docs/assets/gui/current/03-generate.webp" alt="Current Wilson Eval3ngine Generate workspace in operator sequence" width="1100"></p>

The workspace turns inventory into a bounded workload. Model set, prompt population, execution mode, and total request volume are reviewed before dispatch, which is why generation is a control-plane action rather than a result. No quality claim exists until attempts, classifications, metrics, and supporting evidence are produced.

### Charts

Charts are shown next because they help humans spot structure in completed run evidence, but they deliberately sit downstream of structured measurements.

<p align="center"><img src="docs/assets/gui/current/04-charts.webp" alt="Current Wilson Eval3ngine Charts workspace" width="1100"></p>

Charts are grouped by run and can expose associated metadata or be regenerated from evidence. Synthetic demo charts exist only to demonstrate the analytics surface. A visualization never overrides a metric snapshot, population definition, or provenance record; if the picture and structured evidence disagree, the underlying evidence is investigated first.

### Reports

Reports complete the operator sequence because they are the narrative handoff rather than the beginning of the evidence chain.

<p align="center"><img src="docs/assets/gui/current/05-reports.webp" alt="Current Wilson Eval3ngine Reports workspace" width="1100"></p>

Reports provide human-readable PDF previews and export actions while preserving run/model context. A legacy report with incomplete lineage is treated as a provenance warning rather than having missing metadata guessed into place. Release-sensitive review therefore follows the chain back through hashes, canonical report data, metric snapshots, attempts, and approvals.

## Measurement model

WE3 preserves five behavioral outcomes instead of collapsing behavior and infrastructure into one pass/fail number:

| Outcome | Meaning |
|---|---|
| **Appropriate refusal** | A request that should be refused was refused. |
| **False refusal** | A request that should be answered was unnecessarily refused. |
| **Safe useful compliance** | A permitted request received a safe, useful response. |
| **Unsafe compliance** | A response crossed the defined safety boundary. |
| **Ambiguous / partial** | The response cannot be classified confidently or completely. |

Metric snapshots preserve numerator, denominator, exclusions, method/version, and run population. Wilson score intervals communicate uncertainty for proportions. Critical unsafe-compliance and operational-failure rules can block a release, while insufficient support becomes `indeterminate` instead of being forced into pass/fail. Executive summaries likewise leave support/uncertainty unknown when canonical evidence does not define them; missing information is not converted into optimistic values.

## Visualization posture

WE3 includes a broad chart catalogue for exploring run behavior. The examples below are included on the main README because they explain what the analytics layer is intended to make visible. They are sample/demo visualization assets, not current production benchmark claims.

Confidence intervals are shown first because the project treats uncertainty as part of the result rather than decoration.

<p align="center"><img src="docs/assets/charts/confidence_intervals.png" alt="Sample Wilson Eval3ngine confidence interval chart" width="900"></p>

The chart illustrates why a point estimate cannot be read without support. Wide intervals signal limited evidence, while narrower intervals indicate more precise estimation for the same metric definition. Release logic should still use the structured snapshot and configured gate rather than eyeballing a plot.

The stacked outcome example is useful because it preserves the shape of the behavioral population instead of hiding everything behind one success score.

<p align="center"><img src="docs/assets/charts/stacked_outcomes.png" alt="Sample Wilson Eval3ngine stacked outcomes chart" width="900"></p>

A stacked view can reveal whether two models with similar aggregate rates reach them through very different mixtures of appropriate refusal, false refusal, safe compliance, unsafe compliance, or ambiguity. Operational failures remain separate from those behavior categories and should not be visually reclassified to make the chart cleaner.

The per-prompt heatmap demonstrates the system’s ability to move from aggregate behavior back toward the prompts that drive it.

<p align="center"><img src="docs/assets/charts/per_prompt_heatmap.png" alt="Sample Wilson Eval3ngine per-prompt heatmap" width="900"></p>

This view is diagnostic: it helps identify concentrated weak or strong areas that an average can conceal. Every cell still requires the same run, prompt, provider/model, grading, and metric lineage as the aggregate from which it was derived.

The cross-run comparison example explains the intended role of candidate-versus-baseline analysis.

<p align="center"><img src="docs/assets/charts/cross_run_comparison.png" alt="Sample Wilson Eval3ngine cross-run comparison chart" width="900"></p>

Cross-run visualization is meaningful only when the compared populations and metric definitions are compatible. The implemented statistical comparison is explicitly scoped to independent-binomial proportions; a plot cannot turn paired, clustered, or otherwise dependent observations into a valid independent test.

The complete sample chart catalogue and its cautions are documented in [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md).

## Engineering and design principles

WE3’s implementation history repeatedly converged on a small set of principles. **Evidence precedes claims:** reports, screenshots, source, and runtime proof have different authority. **Policy precedes observation:** expected treatment and threshold definitions are established before model output is interpreted. **Failure categories remain distinct:** network/protocol/provider failures do not become behavior labels. **Fail closed when support or authority is missing:** unknown evidence, security-state outages in assurance environments, and unsupported comparison designs should not silently become success. **Lineage is part of the result:** model/provider identity, dataset hashes, metric definitions, report hashes, audit events, and signatures exist so a reviewer can reconstruct the path. **Human authority remains explicit:** review, adjudication, deployment approval, and final release judgment are not delegated to an agent merely because implementation work can be accelerated by one.

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

This lineage is preserved because it explains both the origin and the governing philosophy of the project. The important engineering lesson is not that an AI system produced code quickly. It is that human intent, architectural boundaries, evidence requirements, and review authority remained explicit throughout the process.

## Development origin and evolution

Git history supports July 14, 2026 as the beginning of the repository’s implemented foundation. The initial `0.1.0` foundation commit established versioned contracts, the deterministic mock provider, five-outcome grading, Wilson confidence intervals, content-addressed artifacts, gates, signed dossiers, state/audit foundations, API/CLI surfaces, tests, and architecture/runbook material. July 15–16 then added hostile datasets, expectation compilation, PostgreSQL/schema work, parser/retention boundaries, hosted providers, scheduler/lifecycle support, grading calibration, statistics references, telemetry, supply-chain controls, and broader tests.

The next clear implementation era began July 29 with OIDC/MFA, PostgreSQL row-level project isolation, and encrypted evidence storage. July 31 transformed the operator experience into the current evidence workspace and, in parallel, introduced intensive security/egress/provenance hardening. August 1 expanded the assurance model around deterministic repository inventory, external secret authority, protected credential transport, private-runtime evidence, immutable production images, secure deployment topology, and explicit public/private assurance boundaries.

August 9 added governance/community infrastructure and dependency hardening. August 21 reconciled public documentation and archived stale material. On August 22, the repository gained the native encrypted physical-backup/WAL/PITR path and then underwent another concentrated security, API, metric, grading, persona, CLI, and provider-governance consolidation. The current `0.2.0` milestone records that accumulated state without pretending those intervening commits were formal releases.

## Version and milestone progression

| Milestone | Evidence-backed meaning |
|---|---|
| **July 14, 2026 — `0.1.0` foundation** | First complete deterministic evaluation slice: contracts → provider simulation → grading → Wilson metrics → gates → evidence/dossier. |
| **July 15–16 — evaluation platform expansion** | Expectations, hostile data, database/schema, hosted providers, calibration/statistics, scheduler/lifecycle, retention, telemetry, and supply-chain controls. |
| **July 29 — identity and evidence protection** | OIDC/MFA, PostgreSQL RLS, KMS-oriented encrypted evidence storage. |
| **July 31–August 1 — operator and assurance architecture** | Five-workspace GUI, charts/reports, security/egress hardening, external secret authority, private assurance, hardened deployment composition. |
| **August 9–21 — governance and documentation consolidation** | Community/governance material, dependency hardening, current-status authority, provenance-preserving archive/documentation cleanup. |
| **August 22 — recovery and fail-closed consolidation** | Encrypted backup/WAL/PITR, recovery CLI, shared security authorities, audited authorization, metric/grader/persona corrections, provider-governance hardening. |
| **August 22 — `0.2.0`** | Current pre-1.0 platform milestone and documentation/version reconciliation; not a production certification claim. |

## Complete build timeline

The Gantt chart below is intentionally date-bounded by repository evidence. Multi-day bars represent periods with commit-supported work; single-day bars represent concentrated implementation bursts rather than invented durations.

<p align="center"><img src="docs/assets/diagrams/development-gantt.svg" alt="Wilson Eval3ngine development Gantt from July 14 through August 22 2026" width="1200"></p>

The timeline shows three important transitions. First, the repository moved from a deterministic foundation into a broader evaluation platform within its first several days. Second, late July and early August shifted the center of gravity toward operator experience, security boundaries, private assurance, and deployability. Third, August 22 closed a previously distinct recovery workstream while simultaneously consolidating fail-closed security and measurement semantics. The development pattern is therefore not a simple linear feature sequence: evaluation, governance, UI, security, and operations evolved as overlapping workstreams that were repeatedly reconciled back into one supported architecture.

## Practical usage

The fastest way to understand the complete measurement contract remains the deterministic local lane. It requires Python `3.12–3.14` and Git and does not require a provider credential.

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

For the operator GUI, use the secure-default loopback launcher:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Real provider operation additionally depends on explicitly approved provider/model scope, credentials, destination policy, and target-environment validation. Backup/recovery operation depends on the backup optional dependencies, PostgreSQL tooling, trusted signing/KMS material, and the target recovery environment described in the runbook.

## Repository structure by responsibility

The repository is easier to understand as cooperating responsibility areas than as a flat file inventory. `src/wilson_eval3ngine/` contains the application package; its evaluation, grading, metrics, statistics, and gate modules define the measurement path, while providers isolate execution destinations. Evidence, reports, storage, security, and persistence preserve or protect the resulting state. Review, UI, and GUI modules provide human decision surfaces. Backup and certification modules cover recovery and release-oriented orchestration. `tests/` mirrors those responsibilities with unit, integration, hostile/adversarial, governance, browser, and runtime-contract checks. `infrastructure/`, Docker/Compose material, and operational documentation describe deployment composition without turning templates into claims about a particular environment. Historical plans and superseded artifacts remain under documentation/archive areas as provenance rather than being treated as live implementation.

## Validation and quality posture

The repository defines normal lint/test/coverage/package checks plus focused security, browser, deployment, evidence-inventory, and recovery-oriented validation lanes. The usual local verification sequence is:

```bash
make install
make lint
make test
make coverage
```

Workflow definitions are controls, not proof that the branch you are reading passed. A CI-assured statement requires an observed successful run for the exact revision. Production assurance is stricter still: it needs independently retained evidence for real IdP/JWKS behavior, proxy/TLS/firewall state, Redis/PostgreSQL failure behavior, managed KMS/signing/secret custody, provider destinations and scopes, calibrated graders and thresholds, reviewer operations, alerting/SLO behavior, backup cadence/WAL continuity, destructive restore exercises, reconciliation, and measured RPO/RTO.

## Documentation authority and deeper references

The root README is the high-level narrative. [Current Status](docs/STATUS.md) is the implementation/assurance authority; [Architecture](docs/ARCHITECTURE.md) gives deeper component and trust-boundary detail; [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) explains the operator interface and chart catalogue; [Getting Started](docs/GETTING_STARTED.md) covers setup; [Security](SECURITY.md) and the security documentation define current controls and disclosure boundaries; [Backup and Recovery Runbook](docs/operations/backup-recovery-runbook.md) covers recovery operation; and [Documentation Index](docs/README.md) points to the remaining current material.

Historical plans, prompts, TODO progression, assessments, and archived README states are intentionally preserved because they explain how the system arrived here. They are provenance, not substitutes for current source or executed evidence.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md). Keep credentials, private topology, provider allowlists, raw private assurance material, real KMS/backup metadata, and identity details out of public issues, pull-request text, screenshots, and examples.

## License

MIT. See [LICENSE](LICENSE).
