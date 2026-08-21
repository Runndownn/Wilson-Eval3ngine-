# Wilson Eval3ngine Documentation

This directory contains two different kinds of material and they should not be confused. The files linked under **Current documentation** describe the present repository, while Plans/TODOs, historical reports, design records, and point-in-time assessments preserve how the platform was developed and evaluated at earlier moments.

## Current documentation

| Document | Use it for |
|---|---|
| [Getting Started](GETTING_STARTED.md) | Install WE3, run the credential-free local example, start the GUI, and understand the first successful workflow. |
| [Features](FEATURES.md) | Learn what capabilities exist and why they matter. |
| [Architecture](ARCHITECTURE.md) | Understand modules, execution flow, persistence, certification, trust boundaries, and the local-versus-production architecture. |
| [Current Status](STATUS.md) | Determine what is implemented, integrated, provisional, historical, or still dependent on private runtime assurance. |
| [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) | See all promoted GUI screenshots and charts, plus explanations of the operator workflow and evidence presentation. |
| [Provider & Local Model Setup](operations/api-key-local-model-setup.md) | Configure hosted providers, local/private gateways, Ollama, and CLI-backed model access safely. |
| [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md) | Understand which production facts belong in private runtime evidence rather than the public repository. |
| [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md) | Review the detailed 2026-08-01 point-in-time security assessment, its findings, and residual risks. |
| [Documentation Audit](DOCUMENTATION_AUDIT.md) | See how current documentation was reconciled against code and which older claims were corrected. |

The root [README](../README.md) is the public entry point. It intentionally explains the complete project in approachable language, while the documents above provide the next layer of detail without requiring readers to work through implementation plans first.

## Source-of-truth rules

Current source code and machine-readable configuration are authoritative for implementation claims. Current status documentation explains whether an implementation is also composed into a supported path or whether its production claim still depends on runtime evidence; a screenshot, old TODO completion marker, historical test count, or old architecture blueprint must not silently override that distinction.

The package version is currently `0.1.0`, but the repository as a whole is not accurately described as only “the foundation.” The historical deterministic local lane retains foundation identifiers, while the broader platform includes provider, durable scheduler, review, encrypted storage, identity, operations, certification, and deployment capabilities and is best described as an **active evaluation platform in pre-production assurance**.

## Historical planning and TODO material

`docs/Plans_/` and `docs/08-planning/Plans_/` are preserved in place and are not rewritten into present-tense product documentation. They document the engineering process, decisions, evidence tasks, and build progression that created the platform, which makes them valuable provenance even when an old plan's “future” capability now exists in source.

`docs/Prompts_/` and other historical/design directories should likewise be read according to their date and purpose. When a historical document conflicts with current code or [STATUS.md](STATUS.md), use the current implementation/status evidence for present-tense claims and keep the historical document as provenance.

## Documentation archive

Superseded public-facing documents are stored under `.archive/documentation/` with dated snapshots. This keeps the active documentation tree readable without deleting the previous README, framework status, implementation blueprint, GUI guide, or historical Phase-1 test report.

The separate `.archive/unused_files/` area contains assets and source artifacts that are not active runtime files. Documentation-relevant GUI screenshots, logo art, and chart PNGs have been promoted by exact Git blob identity into `docs/assets/` so the README and GUI guide can render them reliably without depending on archive-relative paths.

## Visual asset convention

Active documentation visuals live under:

```text
docs/assets/
├── brand/
│   └── wilson-eval3ngine-logo.png
├── diagrams/
│   ├── evaluation-pipeline.svg
│   ├── system-architecture.svg
│   └── trust-boundaries.svg
├── gui/
│   ├── 01-endpoints.png
│   ├── 02-models.png
│   ├── 03-generate.png
│   ├── 04-reports.png
│   ├── 05-pdf-viewer.png
│   └── 06-prompt-package.png
└── charts/
    └── *.png
```

PNG is used for the historical/runtime screenshots and generated charts because those repository assets are already valid GitHub-renderable binaries. SVG is used only for the three documentation architecture diagrams, which are static repository files rather than relying on GitHub's Mermaid renderer.

## Maintaining documentation

When behavior changes, update the smallest current document that owns the claim and update `STATUS.md` if maturity or assurance changed. Do not turn Plans/TODOs into a second current manual, do not claim that code proves private deployment facts, and do not publish real secrets, identities, endpoints, certificates, private network details, or raw runtime evidence simply to make a public document appear complete.
