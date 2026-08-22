# Wilson Eval3ngine Documentation

This directory contains current product/operator documentation **and** historical engineering material. Do not treat every Markdown file, TODO, screenshot, or old test report as equally current. The documents under **Current documentation** describe the present repository; plans, design passes, archived docs, and point-in-time assessments preserve how the platform was developed and verified at earlier moments.

## Current documentation

| Document | Use it for |
|---|---|
| [Getting Started](GETTING_STARTED.md) | Install WE3, run the credential-free local example, start the GUI, and understand the first successful workflow. |
| [Features](FEATURES.md) | Learn what capability groups exist and why they matter. |
| [Architecture](ARCHITECTURE.md) | Understand modules, execution flow, persistence, certification, trust boundaries, and local-versus-production architecture. |
| [Current Status](STATUS.md) | Determine what is implemented, integrated, provisional, historical, or still dependent on private runtime assurance. |
| [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) | Use the current five-workspace UI and interpret charts/reports without confusing inventory, demos, or screenshots with release evidence. |
| [Provider & Local Model Setup](operations/api-key-local-model-setup.md) | Configure hosted providers, intentional local/private gateways, Ollama, and CLI-backed model access safely. |
| [Current Security Reassessment](security/SECURITY_REASSESSMENT_2026-08-22.md) | Revalidate the July 30 findings against current source, including root-cause fixes, residual bearer/proxy/runtime risks, and manual/runtime validation requirements. |
| [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md) | Understand which production facts belong in private runtime evidence rather than the public repository. |
| [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md) | Review the detailed 2026-08-01 point-in-time assessment and the branch/head it evaluated; do not use it as a substitute for the current reassessment. |
| [Documentation Audit](DOCUMENTATION_AUDIT.md) | See how documentation was reconciled against code and what stale claims/assets were corrected. |

The root [README](../README.md) is the public entry point and authoritative high-level narrative. It explains the project identity, current implementation, architecture, operator flow, agentic-engineering origin, version progression, and evidence-based development timeline; the documents above add operational and assurance detail.

## Source-of-truth rules

For **implementation behavior**, current source code and machine-readable configuration win. For **maturity/assurance**, [STATUS.md](STATUS.md) explains whether source is merely implemented, composed into a supported path, still statistically provisional, or dependent on private runtime evidence. For **exact evaluation values**, use run evidence, sidecars, metric snapshots, gate records, hashes, and dossiers—not screenshots or old report prose.

A useful precedence model is:

1. current source/configuration for what the software implements;
2. current status/operations docs for what is supported and what still needs assurance;
3. retained run evidence for what a specific evaluation/deployment actually demonstrated;
4. historical plans, screenshots, reports, and archives for provenance only.

The package version is `0.2.0`. `foundation` remains the name of the retained deterministic local lane and the historical `0.1.0` milestone; the broader repository now includes real-provider paths, durable scheduling, review/adjudication, encrypted storage, identity/security, operations, recovery, certification, and deployment capabilities.

## Historical planning and TODO material

`docs/Plans_/` and `docs/08-planning/Plans_/` are preserved in place and are not rewritten into present-tense product documentation. They document the engineering process, decisions, evidence tasks, and build progression that created the platform. A completed capability may therefore still appear as a future/TODO item in an old plan.

`docs/Prompts_/`, design-pass documents, and other historical directories should likewise be read according to their date and purpose. When an old document conflicts with current source or [STATUS.md](STATUS.md), preserve it as provenance but use the current implementation/status evidence for present-tense claims.

## Documentation archive

Superseded public-facing documents are stored under `.archive/documentation/` with dated snapshots. Historical Phase-1 reports and previous README/blueprint/status material remain useful evidence about earlier repository states, not automatic proof about the latest branch or a private deployment.

`.archive/unused_files/` contains source/assets that are not the active runtime or active public-documentation surface. Reusing a historical binary in documentation does not make its displayed data current; provenance and current meaning must be explained separately.

## Visual asset convention

Active documentation visuals live under:

```text
docs/assets/
├── brand/
│   └── wilson-eval3ngine-logo.png
├── diagrams/
│   ├── development-gantt.svg
│   ├── evaluation-pipeline.svg
│   ├── generation-workflow.svg
│   ├── system-architecture.svg
│   └── trust-boundaries.svg
├── gui/
│   ├── current/
│   │   ├── 01-endpoints.webp
│   │   ├── 02-models.webp
│   │   ├── 03-generate.webp
│   │   ├── 04-charts.webp
│   │   └── 05-reports.webp
│   ├── 01-endpoints.png
│   ├── 02-models.png
│   ├── 03-generate.png
│   ├── 04-reports.png
│   ├── 05-pdf-viewer.png
│   └── 06-prompt-package.png
└── charts/
    └── *.png
```

`diagrams/generation-workflow.svg` explains the current Generate-to-evidence control path. `diagrams/development-gantt.svg` is an evidence-based July 14–August 22 history view derived from Git milestones rather than arbitrary file timestamps.

`gui/current/` is the canonical five-workspace walkthrough matching the current UI: **Endpoints → Models → Generate → Charts → Reports**. The six PNGs in the parent `gui/` directory are retained historical point-in-time screenshots. Prompt-package controls are now explained as part of **Generate**, while PDF viewing is part of **Reports**.

Current screenshots use WebP to keep documentation assets practical at repository scale; the documentation validator checks their `RIFF/WEBP` signature in addition to PNG and SVG validation. Sample/generated chart PNGs remain examples of visualization capability and must not be presented as current benchmark evidence unless tied to the specific run that produced them.

## Understanding the GUI source

The baseline `gui/static/index.html` does not by itself show every active browser asset. It loads `enhanced.js`, while the supported GUI server installs `ux4`, `ux5`, and `ux6` CSS/JavaScript overlays at runtime. Documentation and linting therefore need to reason about the composed supported path, not only literal script tags in the baseline HTML.

This is a useful general rule for the repository: apparently unreferenced files should not be declared dead until runtime composition, imports, tests, and deployment wiring have been checked.

## Maintaining documentation

When behavior changes:

- update the smallest current document that owns the claim;
- update [STATUS.md](STATUS.md) if maturity/assurance changed;
- update screenshots only when they represent the current workflow and explain point-in-time values as such;
- keep synthetic/demo charts explicitly synthetic;
- preserve missing provenance rather than inventing lineage for a legacy report;
- keep Plans/TODOs historical rather than rewriting them into a second current manual;
- never claim that source code proves private deployment facts;
- never publish credentials, real private endpoints, certificates, identity details, provider allowlists, or raw runtime assurance evidence merely to make documentation look complete.

The durable rule is: **implemented code can justify an implementation claim; supported composition can justify a supported-path claim; only executed and retained evidence can justify a runtime/certification claim.**
