# Documentation Reconciliation Audit

**Audit date:** 2026-08-21  
**Scope:** public-facing documentation, repository architecture/status claims, install/use guidance, GUI/runtime composition, visual assets, validation configuration, CI wiring, and selected implementation wording  
**Historical Plans/TODO policy:** preserved in place and intentionally not rewritten

## Why this audit exists

The repository evolved faster than several public documents. Earlier material correctly described the first deterministic vertical slice when it was written, but later source added real-provider paths, review/adjudication, durable scheduling, encrypted storage, identity/security controls, certification orchestration, operations, hardened deployment material, and multiple GUI composition passes. Without reconciliation, readers could understate the platform in one section while simultaneously over-reading old screenshots or historical test claims in another.

The second pass also identified a more subtle documentation problem: the public walkthrough described **six historical GUI captures** even though the current baseline interface explicitly implements five workspaces—**Endpoints, Models, Generate, Charts, Reports**. The historical screenshots were real artifacts, but their grouping no longer matched the operator flow. Correct documentation therefore needed not only newer images, but an explanation of what inventory counts, provider health, demo charts, PDF previews, legacy report metadata, and runtime-injected browser overlays actually mean.

## Repository areas reviewed for current claims

The reconciliation uses current implementation/configuration rather than planning documents alone, including:

- package/version/entry points in `pyproject.toml`;
- CLI and synchronous application orchestration;
- domain contracts and dataset/experiment validation;
- expectation compilation, rendering, and logical run identity;
- mock, hosted, local, and CLI provider adapters;
- grading and human review/adjudication;
- metrics, Wilson intervals, comparison/drift primitives, and gate logic;
- evidence storage, encrypted storage, audit, reports, and signing;
- persistence and PostgreSQL durable scheduling;
- API/auth/project security and GUI access/provider/secret boundaries;
- GUI baseline HTML, runtime UX overlay composition, and active browser assets;
- telemetry/tracing, backup/recovery, production Compose/container material;
- certification requirements/orchestration;
- `.github/workflows/ci.yml` and source-level validation expectations;
- active documentation, historical Phase-1 reports, Plans/TODOs, and archived visual assets.

## Corrections and findings

### 1. Project maturity

**Problem:** older public docs described the entire repository as `0.1.0 foundation`, even though `foundation` accurately named only the original deterministic local lane and historical identifiers.

**Correction:** current docs describe package version `0.1.0` and the project as an **active evaluation platform in pre-production assurance**. Production certification remains evidence-dependent because source code cannot prove the target deployment's identities, secrets, network policy, providers, certificates, recovery behavior, or other private runtime facts.

### 2. Provider implementation

**Problem:** older status language said real providers were not implemented.

**Correction:** current docs distinguish the deterministic mock lane from implemented Azure OpenAI, Anthropic, Ollama, local/private, and supported CLI adapter paths. A provider adapter existing in source is not treated as proof that any particular external endpoint/credential/model configuration has been authorized or validated.

### 3. Human review

**Problem:** older status material reduced human review to an escalation flag.

**Correction:** documentation now describes implemented review/adjudication primitives—task creation, assignment, blind dual review, recusal, abstention, disagreement, adjudication, and immutable review records—while keeping staffing, identity, policy, SLA, and runtime integration as real organizational requirements.

### 4. Statistics remain partially provisional

**Problem:** high-level language could imply all planned comparison statistics were production complete.

**Correction:** `STATUS.md`, Getting Started, and the README explicitly preserve two current limitations in `src/wilson_eval3ngine/metrics/engine.py`: one comparison path returns placeholder `p_value=0.5` where completed bootstrap/reference significance is intended, and one snapshot helper approximates `prompt_family_count` with `len(run_ids)`. Wilson intervals/core metric snapshots remain implemented, but those provisional paths must not be used to overclaim certification-grade significance or prompt-family independence.

### 5. Certification

**Problem:** old “not approved for production certification” wording sat beside a global foundation label without explaining that certification orchestration now exists.

**Correction:** documentation explains both facts: certification requirements/orchestration are implemented, while certification of a release/deployment only exists when the required evidence is actually satisfied for that exact target.

### 6. Security assessment dating

**Problem:** the detailed 2026-08-01 master assessment could be mistaken for continuously refreshed runtime evidence.

**Correction:** current docs identify it as a point-in-time assessment. The enduring public/private assurance split is documented separately through `docs/security/PRIVATE_RUNTIME_ASSURANCE.md`.

### 7. Current GUI is five workspaces, not six screenshot stages

**Problem:** the README/GUI guide promoted six older captures as if they were the current workflow. The live baseline `gui/static/index.html` explicitly labels **Workflow 1 of 5** through **Workflow 5 of 5**, with Charts before Reports.

**Correction:** five current operator captures are stored under `docs/assets/gui/current/` and active documentation now follows:

1. Endpoints
2. Models
3. Generate
4. Charts
5. Reports

The older six PNGs remain in `docs/assets/gui/` as historical visual evidence rather than being deleted. Prompt-package selection is documented inside Generate; PDF viewing is documented inside Reports.

### 8. Screenshot values are point-in-time state

**Problem:** a polished screenshot can invite readers to treat visible endpoint/model/run/report counts, provider status, model names, or chart values as stable project facts.

**Correction:** current docs state that those values describe only the captured session. The top-bar numbers are inventory counters, provider online/offline is a connectivity signal, and exact evaluation values must come from run evidence/sidecars/metric snapshots rather than image pixels.

### 9. Demo charts versus run evidence

**Problem:** the Charts workspace supports explicit demo generation, so a screenshot containing sample/demo charts can be visually indistinguishable from real evidence unless its semantics are explained.

**Correction:** the operator guide states that demo charts are synthetic, deliberately labelled, generated only through the demo action, and must never be cited as model benchmark or release evidence. Run-derived charts should be reconciled through run identity, metadata, sidecars, and structured metrics.

### 10. Reports and legacy provenance

**Problem:** historical report artifacts may contain incomplete lineage such as missing recorded models. Hiding or inventing that lineage would be worse than displaying the gap.

**Correction:** current docs describe incomplete legacy metadata as a provenance warning. A release-sensitive claim that depends on missing lineage should be reconciled through sidecars/hashes or regenerated under the current evidence path.

### 11. Runtime GUI composition was easy to misread

**Problem:** `gui/static/index.html` directly loads `enhanced.js`, which could make `ux4.js`, `ux5.js`, and `ux6.js` look dead when only the baseline document is inspected.

**Finding:** `src/wilson_eval3ngine/gui/ux_overlay.py` injects the `ux4`, `ux5`, and `ux6` CSS/JavaScript assets into `/` before the listener serves the supported GUI and also replaces the historical regular-file credential helper with the supported one-shot secret transport.

**Correction:** architecture/operator docs now explain the composed runtime path instead of declaring apparently unreferenced overlay assets obsolete.

### 12. JavaScript lint coverage missed active overlays

**Problem:** `make lint` syntax-checked `enhanced.js` and `ux4.js` but omitted the runtime-injected `ux5.js` and `ux6.js` layers.

**Correction:** the lint target now runs `node --check` across `enhanced.js`, `ux4.js`, `ux5.js`, and `ux6.js`, matching the supported browser composition more closely.

### 13. Makefile cleanup side effect was attached to the wrong command

**Problem:** recursive `__pycache__` deletion was placed under `backup-restore-plan`, giving a backup planning operation an unrelated source-tree cleanup side effect, while `clean` did not perform that cleanup.

**Correction:** `__pycache__` removal is now part of `make clean`; `backup-restore-plan` performs only the restore-plan action.

### 14. Documentation validator did not validate WebP signatures

**Problem:** the active documentation validator understood PNG and SVG signatures but did not validate WebP. That was especially relevant because a previous pass had encountered broken WebP gallery files.

**Correction:** `scripts/validate_documentation_assets.py` now verifies WebP files as `RIFF....WEBP` before considering them valid documentation assets. The current GUI screenshots can therefore use practical WebP files without weakening render-critical validation.

### 15. CI and verification language

**Finding:** `.github/workflows/ci.yml` defines quality/test/coverage/build, supply-chain/security, deterministic foundation validation, main-branch build provenance attestation, and scheduled backup verification jobs. Documentation now describes those configured jobs without claiming that an unobserved branch has passed them.

**Rule:** workflow configuration shows what CI intends to execute. A green status/running artifact for a specific commit is separate execution evidence and should be cited only when actually observed.

## Current visual provenance

The canonical current GUI captures were supplied from the current operator interface and added under:

```text
docs/assets/gui/current/
├── 01-endpoints.webp
├── 02-models.webp
├── 03-generate.webp
├── 04-charts.webp
└── 05-reports.webp
```

`docs/assets/gui/README-current-captures.md` records their interpretation/provenance rules. The old six PNGs remain beside them as historical point-in-time captures. Chart examples remain under `docs/assets/charts/`; they demonstrate visualization capability but are not automatically current run evidence.

The three static SVG architecture diagrams remain repository-authored explanatory diagrams rather than runtime measurement artifacts.

## Historical material preserved

No file under `docs/Plans_/` or `docs/08-planning/Plans_/` is rewritten by this correction. Superseded public documentation under `.archive/documentation/` remains available. Historical test reports retain their original claims as evidence about those snapshots rather than being silently rewritten to match the current branch.

## Remaining assurance work

This pass reconciles source, public documentation, operator screenshots, and selected validation wiring. It does **not** substitute for executing the complete test, browser, container, real-provider, restore, security, deployment, or private runtime-assurance matrix.

Before merge/release, the branch should still be validated through the repository's normal commands/workflows. In particular, do not convert the existence of CI configuration into a statement that this documentation branch has passed CI unless the run is actually observed.

The durable rule for future work is:

**implemented code can justify an implementation claim; supported composition can justify a supported-path claim; only executed and retained evidence can justify a runtime/certification claim.**
