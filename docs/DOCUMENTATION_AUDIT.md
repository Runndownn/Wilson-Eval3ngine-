# Documentation Reconciliation Audit

**Audit date:** 2026-08-21  
**Scope:** public-facing documentation, repository architecture/status claims, install/use guidance, visual assets, and selected implementation wording  
**Historical Plans/TODO policy:** preserved in place and intentionally not rewritten

## Why this audit exists

The repository evolved faster than several public documents. Earlier documentation correctly described the first deterministic vertical slice at the time it was written, but later source added provider adapters, review/adjudication, durable scheduling, encrypted storage, identity/security controls, certification orchestration, operations, and hardened deployment material; retaining the old global “foundation” description eventually understated the repository.

A previous documentation pass also introduced two presentation defects: it relied on GitHub Mermaid rendering for core diagrams and created three small WebP gallery files that did not render as valid images in GitHub. This pass treats documentation rendering as part of correctness, replaces those fragile references with static SVG diagrams and the repository's original PNG assets, and records the maturity distinction explicitly.

## Repository areas reviewed for current claims

The public documentation was reconciled against the following implementation families rather than against planning documents alone:

- package/version/entry points in `pyproject.toml` and `src/wilson_eval3ngine/__init__.py`;
- CLI and synchronous application orchestration;
- domain contracts and dataset/experiment validation;
- expectation compilation, rendering, and logical run identity;
- mock, hosted, local, and CLI provider adapters;
- grading and human review/adjudication;
- metrics, Wilson intervals, comparison/drift primitives, and gate logic;
- evidence storage, encrypted storage, audit, reports, and signing;
- persistence and PostgreSQL durable scheduling;
- API/auth/project security and GUI access/provider/secret boundaries;
- telemetry/tracing, backups/recovery, production Compose/container material;
- certification requirements/orchestration;
- point-in-time security assessment and private-runtime assurance contract;
- active documentation, historical Phase-1 reports, Plans/TODOs, and archived visual assets.

## Corrections made

### 1. Project maturity

**Previous problem:** public docs described the entire repository as `0.1.0 foundation`, even though “foundation” accurately named only the original deterministic local vertical slice and historical identifiers.

**Correction:** current docs describe the package as version `0.1.0` and the project as an **active evaluation platform in pre-production assurance**. The deterministic local lane and `examples/experiments/foundation.yaml` retain their historical name, while production certification is described as evidence-dependent because target runtime facts are not proven by source code alone.

### 2. Provider implementation

**Previous problem:** older status material said real providers were not implemented.

**Correction:** documentation now records implemented Azure OpenAI, Anthropic, Ollama, and supported CLI adapter paths while distinguishing source implementation from authorized provider configuration/runtime validation. The deterministic local service still defaults to the mock provider, so the docs state that narrower fact without using it to characterize the whole provider layer.

### 3. Human review

**Previous problem:** older status language reduced human review to an escalation flag.

**Correction:** current docs describe the implemented review/adjudication primitives: task creation, assignment, blind dual review, recusal, abstention, disagreement, adjudication, and immutable review records. They also state that a functioning organizational review operation still requires identities, staffing, policy, SLA, and runtime integration.

### 4. Statistics

**Previous problem:** high-level descriptions could imply that all planned comparison statistics were production complete.

**Correction:** `STATUS.md` explicitly records the placeholder p-value path in metric comparison and the prompt-family-count approximation noted by `create_metric_snapshot`. Wilson intervals and the core gate behavior are described as implemented, while unfinished comparison/bootstrap/reference work is not promoted into a stronger claim.

### 5. Certification

**Previous problem:** “not approved for production certification” was presented beside a global foundation label without explaining that certification orchestration itself now exists.

**Correction:** documentation now states that the certification subsystem is implemented across ten requirement categories while production certification of an actual release/deployment remains dependent on satisfied evidence. This explains both facts without conflating “certification code exists” with “this deployment is certified.”

### 6. Security assessment dating

**Previous problem:** a detailed 2026-08-01 assessment risked being read as continuously current runtime evidence.

**Correction:** current docs label `docs/security/MASTER_SECURITY_ASSESSMENT.md` as a point-in-time assessment of the branch/head it reviewed. The durable public/private assurance boundary is referenced separately through `docs/security/PRIVATE_RUNTIME_ASSURANCE.md`.

### 7. README usability

**Previous problem:** the README was concise but too compressed, leaving readers to infer how inputs, runs, evidence, metrics, gates, GUI workflows, and production controls related.

**Correction:** the README now explains the problem WE3 solves, target users, five outcomes, separate reliability states, full evaluation sequence, installation, deterministic first run, GUI workflow, architecture, implementation/assurance matrix, visual evidence, repository map, and documentation map in explanatory prose. The required Agentic Engineering Origin content remains intact and is presented in a Markdown quote block as requested.

### 8. Broken images

**Previous problem:** `docs/assets/images/ui-workflow.webp`, `metrics-gallery.webp`, and `performance-gallery.webp` did not render correctly on GitHub.

**Correction:** the public docs no longer rely on those generated WebPs. The original Wilson logo, six GUI screenshots, and complete sample-chart PNG set are promoted from their archived Git blobs into stable `docs/assets/brand/`, `docs/assets/gui/`, and `docs/assets/charts/` paths.

### 9. Broken Mermaid diagrams

**Previous problem:** GitHub displayed “Unable to render rich display” for Mermaid in the README/architecture page.

**Correction:** active public docs use static SVG files in `docs/assets/diagrams/`. Historical Mermaid in archived documents or preserved Plans/TODOs remains untouched because those files are provenance rather than the active public rendering surface.

## Visual source provenance

The Wilson logo and six GUI screenshots already existed in `.archive/unused_files/static/images/`. The chart catalogue already existed in `.archive/unused_files/gui_charts/charts/sample-charts/`; this pass reuses those exact binary Git blobs under active documentation paths instead of recompressing or fabricating replacements.

This is important because the visual documentation now has a simple provenance story: active docs point to valid repository binaries, while the archive continues to preserve the original location. The documentation diagrams are the only newly authored visual files, and they describe repository architecture rather than claiming runtime measurements.

## Historical material preserved

No file under `docs/Plans_/` or `docs/08-planning/Plans_/` is modified by this correction. Those directories remain original build/planning evidence, and the documentation index explains why they should be read historically rather than as the current manual.

Superseded public documentation already stored under `.archive/documentation/` remains available. Historical test reports retain their original claims in the archive while the active path points readers toward current status/verification evidence.

## Remaining assurance work

This documentation pass is a source/document reconciliation and rendering correction. It does not substitute for running the complete test, browser, container, provider, restore, security, or private runtime-assurance matrix for a production release.

The rule for future updates is straightforward: **implemented code can justify an implementation claim; integrated code can justify a supported-path claim; only executed and retained evidence can justify a runtime/certification claim.**
