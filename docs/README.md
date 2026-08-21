# Documentation

This directory separates **current product documentation**, **operations/security assurance**, and **historical build material**.

## Start here

| Document | Purpose |
|---|---|
| [Getting Started](GETTING_STARTED.md) | Install, run the mock demo, start the GUI, connect providers. |
| [Features](FEATURES.md) | Product capabilities and the evaluation model. |
| [Architecture](ARCHITECTURE.md) | Components, data flow, execution modes, and trust boundaries. |
| [Current Status](STATUS.md) | Exact implemented/integrated/partial/assurance boundary. |
| [GUI and Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) | Operator workflow, screenshots, charts, and reports. |
| [Documentation Audit](DOCUMENTATION_AUDIT.md) | Reconciliation findings and document ownership. |

## Operations

- [Provider credentials and local model endpoints](operations/api-key-local-model-setup.md)
- Additional runbooks and operational material remain under `docs/operations/`.

## Security and assurance

- [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md)
- [Private Runtime Assurance Contract](security/PRIVATE_RUNTIME_ASSURANCE.md)
- Supporting security evidence and specialized assessments remain under `docs/security/`.

Security documents intentionally distinguish repository implementation from runtime proof.

## Historical engineering material

`docs/Plans_/` contains the original plans, TODOs, blueprints, and execution records used to build the platform. They are preserved **as historical engineering evidence** and are not rewritten to match the current codebase.

Superseded public-facing documents are snapshotted in [`.archive/documentation/`](../.archive/documentation/) so the active documentation tree stays concise while prior wording remains inspectable.

## Documentation ownership rule

When current code and historical planning disagree:

1. executable repository code and current tests define implemented behavior;
2. `STATUS.md` defines the public readiness/integration claim;
3. security assurance documents define what has actually been validated;
4. Plans/TODOs remain provenance and intent, not current product truth.
