# Documentation Reconciliation Audit

**Audit date:** 2026-08-21  
**Goal:** make public-facing documentation describe the current repository rather than a mixture of current code, historical plans, and earlier foundation assumptions.

## Review basis

The reconciliation reviewed the active README/documentation hierarchy and representative implementation paths governing CLI/GUI startup, evaluation orchestration, provider registration, metrics/statistics, gates, review/adjudication, durable scheduling, encrypted storage, production Compose, and security/runtime assurance. Historical Plans/TODO material was treated as provenance and deliberately left unchanged.

This is a documentation reconciliation, not a claim that every runtime assurance check has passed. The Master Security Assessment remains the authority for validation evidence.

## Material mismatches found

| Area | Previous documentation issue | Reconciled representation |
|---|---|---|
| Provider support | Framework status said real providers were “not implemented.” | Provider adapter modules/registration paths exist; foundation sync service still defaults to mock. |
| Human review | Framework status said “escalation flag only.” | Review/adjudication workflow code exists, but is not fully integrated into foundation `run_manifest`. |
| GUI visuals | Guide referenced `gui/static/charts/test-run-final/`, which is not part of the current tree. | Supplied runtime screenshots/charts are stored under `docs/assets/images/` and documented explicitly. |
| Screenshot status | Guide described screenshots as future work. | Actual supplied captures are now incorporated. |
| Encrypted evidence | Broad wording could imply a production KMS/storage deployment. | Encrypted store is identified as an implemented module; local KMS is development-only and deployment assurance remains external. |
| Statistical comparison | High-level text risked implying completed bootstrap inference. | Status now calls out placeholder p-value/bootstrap work and prompt-family-count approximation. |
| Historical blueprint | July blueprint described a greenfield/implementation-empty state. | Preserved as historical material; current docs defer to code + STATUS + assurance evidence. |
| Public README | Large README mixed product explanation, deep security detail, implementation history, and visual references. | Replaced with a concise value-first entry point and layered documentation. |

## Active document responsibilities

- `README.md` — value, quick start, workflow, architecture overview, status disclaimer, canonical origin statement.
- `docs/GETTING_STARTED.md` — installation and first successful local run.
- `docs/FEATURES.md` — capability explanation.
- `docs/ARCHITECTURE.md` — component and data-flow model.
- `docs/STATUS.md` — current implementation/readiness truth.
- `docs/GUI_AND_EVIDENCE_GUIDE.md` — screenshots, charts, operator interpretation.
- `docs/security/*` — security assessment and runtime-assurance detail.
- `docs/operations/*` — operational procedures.
- `docs/Plans_/*` — historical plans/TODOs, preserved unchanged.
- `.archive/documentation/*` — snapshots of superseded public-facing documentation.

## Update convention

When a future implementation changes a public claim:

1. update `STATUS.md` first;
2. update the responsible feature/architecture/operations guide;
3. update README only when the entry-level story or quick-start changes;
4. archive a materially superseded document if it is useful as historical evidence;
5. do not rewrite Plans/TODOs to make history look current.
