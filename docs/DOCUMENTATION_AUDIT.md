# Documentation Reconciliation Audit

**Original audit date:** 2026-08-21  
**Visual/version follow-up:** 2026-08-22  
**Scope:** public-facing documentation, repository architecture/status claims, install/use guidance, GUI/runtime composition, visual assets, validation configuration, CI wiring, and selected implementation wording  
**Historical Plans/TODO policy:** preserved in place and intentionally not rewritten

## Why this audit exists

The repository evolved faster than several public documents. Earlier material correctly described the first deterministic vertical slice when it was written, but later source added real-provider paths, review/adjudication, durable scheduling, encrypted storage, identity/security controls, certification orchestration, operations, hardened deployment material, native backup/WAL/PITR recovery, and multiple GUI composition passes. Without reconciliation, readers could understate the platform in one section while simultaneously over-reading old screenshots or historical test claims in another.

The August 22 follow-up is necessary because the visual asset set changed again after the first audit: high-resolution PNG captures were uploaded, the prior `03-generate.webp` was removed, a detailed analytics capture set was added, and the root README was rebuilt around the current `0.2.0` project narrative. This document therefore records the present documentation state rather than preserving stale file references as if they were still current.

## Repository areas reviewed for current claims

The reconciliation uses current implementation/configuration rather than planning documents alone, including package/version/entry points; CLI/API/application orchestration; domain contracts and experiment validation; expectation compilation and run identity; provider adapters; grading and review/adjudication; metrics, Wilson intervals, comparison and gate logic; evidence, reports, audit, signing and storage; persistence and durable scheduling; API/auth/project security; GUI runtime composition; telemetry; backup/recovery; deployment material; certification; workflow definitions; active documentation; and historical Plans/TODO/archive material.

## Corrections and findings

### 1. Project maturity and version

**Earlier problem:** public docs described the entire repository as the `0.1.0 foundation`, although `foundation` accurately named the first deterministic local vertical slice rather than the complete later platform.

**Current correction:** the package/project milestone is `0.2.0`, representing the accumulated pre-1.0 platform state after the July 14 foundation. Historical `0.1.0` identifiers remain historical. Production certification is still evidence-dependent because source cannot prove the target deployment's identities, secrets, network policy, providers, certificates, managed keys, restore behavior, or other private runtime facts.

### 2. Provider implementation

Older status language said real providers were not implemented. Current documentation distinguishes the deterministic mock lane from implemented hosted, local/private, Ollama, and supported CLI adapter paths. An adapter existing in source is not proof that a particular endpoint, credential, or model has been authorized or validated.

### 3. Human review

Current documentation reflects implemented review/adjudication primitives rather than reducing human review to an escalation flag. Staffing, reviewer identity, policy, SLA, calibration, and target-environment operation remain organizational/runtime requirements.

### 4. Statistics and support semantics

The earlier audit recorded provisional placeholder significance and prompt-family support behavior. Those statements are no longer current. The present metric/status path implements a scoped two-sided pooled two-proportion comparison for compatible independent-binomial populations and does not infer prompt-family independence merely from run count. Paired, clustered, repeated-prompt, and other dependent designs still require their corresponding calibrated method; unsupported designs must not be treated as independent by convenience.

### 5. Certification

Certification requirements/orchestration exist in source, while certification of a release/deployment exists only when required evidence is actually satisfied for that exact target. Documentation preserves that distinction rather than using either “implemented” or “configured” as a substitute for executed certification evidence.

### 6. Security assessment dating

The detailed 2026-08-01 master assessment remains a point-in-time artifact. The 2026-08-22 reassessment is the current source-level security review, and `docs/security/PRIVATE_RUNTIME_ASSURANCE.md` remains the enduring public/private evidence boundary.

### 7. Current GUI is five workspaces

The active operator model is:

1. Endpoints
2. Models
3. Generate
4. Charts
5. Reports

Prompt-package selection belongs inside Generate. PDF viewing belongs inside Reports. Current documentation follows that flow instead of treating older capture groupings as a second navigation model.

### 8. High-resolution current visual set

The canonical current workspace captures are now:

```text
docs/assets/gui/current/
├── endpoints.png
├── models.png
├── generate.png
├── charts.png
└── reports.png
```

`Generate.png` and `generate.png` are byte-identical aliases; current docs render the lowercase path once. Lower-resolution `01-endpoints.webp`, `02-models.webp`, `04-charts.webp`, and `05-reports.webp` remain compatibility/history assets. The former `03-generate.webp` was removed and current documentation must not reference it.

The retained `docs/assets/gui/05-pdf-viewer.png` is displayed in the root README as a report-reading surface, not a separate workflow stage.

### 9. Current analytics visual atlas

The August 22 upload added a detailed analytics capture set under `docs/assets/gui/current/`. The root README now displays the unique current captures and explains how each should be read, including cross-run comparison, confidence intervals, category/safety views, model profiles, outcome distributions, prompt-level heatmaps, latency distributions/trends, response-length views, correlation, efficiency, and token-use views.

Because the native dimensions differ substantially, README rendering uses a common analytics height while preserving each image's aspect ratio. This prevents relatively tall or differently proportioned captures such as `ppsh.png` from visually dominating landscape charts without stretching or cropping the image.

### 10. Screenshot values are point-in-time state

Visible endpoint/model/run/report counts, provider status, model names, chart values, axes, and legends describe the captured session. The screenshots teach the interface and visualization surfaces; exact evaluation claims still come from run evidence, sidecars, metric snapshots, gate records, hashes, and signed/canonical artifacts.

### 11. Demo charts versus run evidence

The Charts workspace supports explicit demo generation. Demo charts are synthetic and must not be cited as real model benchmark or release evidence. Run-derived charts should reconcile through run identity, metadata, sidecars, and structured metrics.

### 12. Reports and legacy provenance

Historical report artifacts can contain incomplete lineage. Current documentation treats missing model/provenance information as a warning rather than guessing it. A release-sensitive claim that depends on missing lineage should be reconciled through sidecars/hashes or regenerated through the current evidence path.

### 13. Runtime GUI composition

`gui/static/index.html` directly loads the baseline behavior, while `src/wilson_eval3ngine/gui/ux_overlay.py` injects the supported `ux4`, `ux5`, and `ux6` presentation layers before serving the composed interface. Current architecture/operator docs therefore reason about the runtime-composed path instead of declaring apparently unreferenced overlays dead from static HTML inspection alone.

### 14. Documentation visual validation

The documentation validator checks render-critical asset signatures, including PNG, SVG, and WebP. Current documentation nevertheless prefers the new high-resolution PNG workspace captures for the root README because they are the latest supplied operator images. Asset existence and path correctness are part of documentation validation; a deleted image path is treated as a documentation defect, not a browser problem.

### 15. Development timeline visualization

The development Gantt remains evidence-bounded to July 14–August 22, 2026, but its presentation was redesigned for README use. The current SVG uses larger phase labels, a dedicated timeline column, a separate “what changed” column, milestone markers, and fewer larger workstream rows. Commit-supported bursts remain short rather than being stretched into invented multi-day activity.

### 16. CI and verification language

Workflow configuration shows what CI intends to execute. A green status and retained artifacts for a specific revision are separate execution evidence. Documentation therefore does not claim that a branch passed merely because the workflow exists or has been triggered.

## Current visual provenance

The active visual surfaces are described in `docs/assets/gui/README-current-captures.md`. The root README now directly displays the principal architecture diagrams, current five-workspace GUI, retained PDF viewer, current analytics capture set, generation workflow, and readable evidence-based development timeline. Each substantial image is introduced and followed by explanatory prose so it functions as technical documentation rather than decoration.

The architecture SVGs are repository-authored explanatory diagrams rather than runtime measurement artifacts. GUI/chart captures remain point-in-time presentation evidence unless tied to a specific retained run.

## Historical material preserved

No file under `docs/Plans_/` or `docs/08-planning/Plans_/` is rewritten by this correction. Superseded public documentation under `.archive/documentation/` remains available. Historical reports retain their original claims as evidence about those snapshots rather than being silently rewritten to match current source.

## Remaining assurance boundary

This reconciliation aligns source-facing claims, visual paths, current screenshots, explanatory text, and the project timeline. It does **not** substitute for executing the complete test, browser, container, real-provider, restore, security, deployment, or private runtime-assurance matrix.

The durable rule for future work is:

**implemented code can justify an implementation claim; supported composition can justify a supported-path claim; only executed and retained evidence can justify a runtime/certification claim.**
