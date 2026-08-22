<p align="center">
  <img src="docs/assets/brand/wilson-eval3ngine-logo.png" alt="Wilson Eval3ngine" width="1000">
</p>

# Wilson Eval3ngine

**Evidence-first LLM evaluation for safety, usefulness, reliability, comparison, and governed release decisions.**

[Getting Started](docs/GETTING_STARTED.md) · [Features](docs/FEATURES.md) · [Architecture](docs/ARCHITECTURE.md) · [Current Status](docs/STATUS.md) · [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) · [Security](SECURITY.md) · [Documentation Index](docs/README.md)

Wilson Eval3ngine (WE3) turns a versioned experiment and dataset into traceable model runs, keeps provider/reliability failures separate from model behavior, computes uncertainty-aware metrics, applies explicit gates, and preserves the evidence needed to reconstruct a decision later.

The governing question is not merely *“what score did the model get?”* It is **“what population was evaluated, what exactly happened, how much support exists, what rule produced the decision, and can another reviewer verify the lineage?”**

## Current project position

**Package version:** `0.1.0`  
**Project stage:** **active evaluation platform / pre-production assurance**  
**Production certification:** **not established by source code alone**

`foundation` remains in historical identifiers and the deterministic local lane because that lane was the first complete vertical slice. It is not the maturity label for the whole repository. Real-provider paths, durable scheduling, review/adjudication, evidence protection, identity/security controls, GUI/operator workflows, observability, encrypted PostgreSQL backup/PITR, deployment material, and certification orchestration extend beyond it.

Some important areas remain explicitly provisional, particularly one cross-run statistical p-value path, one prompt-family support path, and executive persona support/uncertainty aggregates. PostgreSQL recovery is now implemented at source level and has a dedicated disposable runtime exercise, but production RPO/RTO, KMS custody, backup-storage durability, external tablespace topology, and return-to-service approval remain deployment evidence requirements. [Current Status](docs/STATUS.md) is the authority for these boundaries.

## Behavioral outcomes

WE3 preserves five behavior families instead of collapsing everything into one pass/fail result:

| Outcome | Meaning |
|---|---|
| **Appropriate refusal** | A request that should be refused was refused. |
| **False refusal** | A request that should be answered was unnecessarily refused. |
| **Safe useful compliance** | A permitted request received a safe, useful response. |
| **Unsafe compliance** | A response crossed the defined safety boundary. |
| **Ambiguous / partial** | The response cannot be classified confidently or completely. |

Timeouts, malformed responses, exhausted retries, authentication failures, and other provider/reliability problems remain separate from those behavior labels.

## Evidence path

<p align="center"><img src="docs/assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evaluation pipeline" width="1100"></p>

1. Validate the experiment, dataset identity/version/hash, and execution configuration.
2. Compile expected treatment **before** seeing the target model response.
3. Render a deterministic provider request and preserve provider attempts/retries.
4. Grade valid terminal behavior while keeping reliability failures separate.
5. Build metric snapshots with numerator, denominator, exclusions, version, population, and Wilson confidence intervals.
6. Apply explicit gate/support rules; insufficient evidence becomes indeterminate rather than an artificial pass.
7. Preserve reports, hashes, classifications, metrics, audit data, and signed dossier/result artifacts.

## Five-minute deterministic start

Requires Python `3.12–3.14` and Git; no provider credential is required.

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

The deterministic lane proves the local measurement path for the checked-out code/configuration. It does **not** certify a real provider or private deployment.

## Current operator GUI

Start with the secure-default loopback listener:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

The supported launcher repairs legacy wildcard defaults to loopback unless the operator deliberately sets `WE3_GUI_ALLOW_REMOTE_BIND=1`. That override changes only bind policy; it does not add authentication, authorization, TLS, firewalling, or multi-user isolation. Intentionally remote operation must supply and validate those controls independently.

The current workflow is exactly five workspaces:

**Endpoints → Models → Generate → Charts → Reports**

### 1. Endpoints

<p align="center"><img src="docs/assets/gui/current/01-endpoints.webp" alt="Current Wilson Eval3ngine Endpoints workspace" width="1100"></p>

Register/test an approved provider destination and reconcile its discovered model inventory. `online`/`offline` is connectivity evidence, not a model-quality or safety judgment.

### 2. Models

<p align="center"><img src="docs/assets/gui/current/02-models.webp" alt="Current Wilson Eval3ngine Models workspace" width="1100"></p>

Inspect exact provider model IDs, endpoint lineage, inferred families, and selection readiness. Family/recommended labels are navigation aids, not benchmark endorsements.

### 3. Generate

<p align="center"><img src="docs/assets/gui/current/03-generate.webp" alt="Current Wilson Eval3ngine Generate workspace" width="1100"></p>

Choose models, prompt package/custom prompts, execution mode, and review total request volume before starting. Prompt-package selection belongs here rather than in a separate workflow stage.

### 4. Charts

<p align="center"><img src="docs/assets/gui/current/04-charts.webp" alt="Current Wilson Eval3ngine Charts workspace" width="1100"></p>

Inspect run-scoped visualizations and associated metadata. **Demo charts are synthetic** and must never be cited as real model-run evidence; use structured sidecars/metric snapshots for exact values.

### 5. Reports

<p align="center"><img src="docs/assets/gui/current/05-reports.webp" alt="Current Wilson Eval3ngine Reports workspace" width="1100"></p>

Read two-column PDF previews and open/export full reports. A PDF is a presentation layer, not the sole authority for release claims. Missing lineage on a legacy report is a provenance warning that should be preserved rather than guessed away.

Visible screenshot counts, provider states, model names, run totals, report totals, and chart values are **point-in-time capture state**, not current release metrics. See [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md).

## Architecture and trust boundary

<p align="center"><img src="docs/assets/diagrams/system-architecture.svg" alt="Wilson Eval3ngine system architecture" width="1100"></p>

The Python platform separates contracts/orchestration, provider execution, grading/review, metrics/gates, persistence/evidence, security/identity, certification, GUI, recovery, and operational/deployment concerns. The supported browser path is also composed in layers: baseline `index.html`/`enhanced.js` plus runtime-injected `ux4`, `ux5`, and `ux6` overlays.

<p align="center"><img src="docs/assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100"></p>

**Implemented source can support an implementation claim. Supported composition can support a supported-path claim. Only executed and retained evidence can support a runtime/certification claim.**

That distinction matters for OIDC, KMS, networking, provider credentials, production certificates, human review, and backup/PITR/recovery.

## Important current limitations

### Statistics

`src/wilson_eval3ngine/metrics/engine.py` still exposes a placeholder `p_value=0.5` in one comparison path, and one snapshot helper approximates `prompt_family_count` with run count. Do not make certification-grade significance/independence claims from those paths.

### Persona views

Analyst-view construction rejects unscoped or cross-project reports before copying metrics/artifact lineage. Executive support/uncertainty aggregate fields are still provisional constants, and the reviewer regex redactor is baseline masking rather than a complete production DLP policy.

### Report serialization

Cross-format report reconciliation fails closed unless JSON/CSV/HTML carries the exact canonical report hash. Optional Parquet export fails explicitly when `pyarrow` is unavailable rather than returning a zero-byte artifact. Hash carriage is an integrity/linkage check, not independent semantic proof of every rendered field.

## PostgreSQL backup, PITR, and recovery

WE3 now includes a real native recovery path rather than the previous metadata-only scaffold. `pg_basebackup` streams its physical tar output directly through AES-256-GCM encryption, using a one-time data-encryption key wrapped by the configured KMS. A signed canonical manifest binds the encrypted object to plaintext/ciphertext SHA-256 values, KMS identity, PostgreSQL system identifier, timeline, WAL coordinates, and a storage version. Verification requires a trusted Ed25519 signer and checks manifest, ciphertext, KMS unwrap, AEAD authentication, and decrypted plaintext identity before an object is eligible for restore.

WAL planning uses actual completed PostgreSQL WAL files. The catalogue persists across process restarts, records the real 24-hex segment names and database identity, and rejects missing/non-contiguous coverage instead of inventing placeholder segments. A signed recovery baseline defines the state that recovery must reproduce. The restore orchestrator authenticates/decrypts selected objects, performs a loopback-only PostgreSQL PITR start, waits for the recovery target and promotion, and then reconciles runs, classifications, metrics, gates, outbox, provenance, and the canonical project audit chains.

The supported operator interface is:

```bash
python -m pip install -e ".[dev,backup]"
we3-backup --help
```

This source capability does not turn configured objectives into production evidence. A private deployment still has to prove its actual KMS authority, backup-storage durability/immutability/replication, WAL archival, database scale, restore duration, external artifact recovery, and accountable return-to-service process. The current native streaming path also rejects user-defined PostgreSQL tablespaces rather than silently producing an incomplete topology. See [Backup and Recovery Runbook](docs/operations/backup-recovery-runbook.md).

## Repository map

| Path | Purpose |
|---|---|
| `src/wilson_eval3ngine/` | Main package and platform modules. |
| `src/wilson_eval3ngine/providers/` | Provider abstractions/adapters/destination policy. |
| `src/wilson_eval3ngine/grading/`, `metrics/`, `statistics/`, `gates/` | Behavior, metrics, uncertainty, comparison, decisions. |
| `src/wilson_eval3ngine/evidence/`, `storage/`, `reports/`, `security/` | Evaluation evidence, rendering, signing, storage/security controls. |
| `src/wilson_eval3ngine/review/`, `ui/` | Human-review and persona/operator view models. |
| `src/wilson_eval3ngine/persistence/`, `execution/` | Database state, durable scheduling, execution support. |
| `src/wilson_eval3ngine/backup/` | Encrypted PostgreSQL physical backup, WAL, PITR, recovery baseline, restore, and reconciliation. |
| `src/wilson_eval3ngine/certification/` | Certification requirements/orchestration. |
| `src/wilson_eval3ngine/gui/`, `gui/static/` | GUI server/composition/browser assets. |
| `tests/` | Unit, integration, hostile/adversarial, governance, browser, and other checks. |
| `infrastructure/`, `docker-compose*.yml`, `Dockerfile*` | Deployment/ingress/observability/container material. |
| `docs/` | Current documentation plus historical design/planning material. |
| `.archive/` | Superseded/unused artifacts retained for provenance. |

## Development and verification

```bash
make install
make lint
make test
make coverage
```

`make lint` compiles Python source/tests/scripts, validates active documentation assets (including WebP signatures), and syntax-checks active browser JavaScript layers: `enhanced.js`, `ux4.js`, `ux5.js`, and `ux6.js`. The project configures an 80% overall coverage threshold.

The GitHub workflow defines build, supply-chain/security, deterministic-foundation, and a dedicated disposable PostgreSQL recovery runtime job. The recovery job creates an encrypted physical backup, archives real WAL, exercises missing-WAL/signature/ciphertext negatives, restores to a second loopback PostgreSQL instance, reconciles the restored state, and uploads the runtime directory as workflow evidence. A workflow definition is not proof that a particular commit passed it; check the actual run for the exact commit, and do not treat CI recovery as proof of a private production deployment.

## Documentation map

| Need | Start here |
|---|---|
| Install and run locally | [Getting Started](docs/GETTING_STARTED.md) |
| Understand what the platform does | [Features](docs/FEATURES.md) |
| Understand components and data flow | [Architecture](docs/ARCHITECTURE.md) |
| Know what is implemented vs. proven | [Current Status](docs/STATUS.md) |
| Use the GUI, charts, and reports | [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) |
| Configure hosted/local providers | [Provider & Local Model Setup](docs/operations/api-key-local-model-setup.md) |
| Operate/test PostgreSQL recovery | [Backup & Recovery Runbook](docs/operations/backup-recovery-runbook.md) |
| Review security posture | [Security Policy](SECURITY.md) and [Master Security Assessment](docs/security/MASTER_SECURITY_ASSESSMENT.md) |
| Understand private runtime assurance | [Private Runtime Assurance](docs/security/PRIVATE_RUNTIME_ASSURANCE.md) |
| See documentation reconciliation work | [Documentation Audit](docs/DOCUMENTATION_AUDIT.md) |
| Historical implementation records | [`docs/Plans_/`](docs/Plans_/) and [documentation archive](.archive/documentation/) |

The original Plans/TODO material remains in `docs/Plans_/` and `docs/08-planning/Plans_/` and is intentionally not rewritten as current product documentation.

## Agentic Engineering Origin

 **Agentic Engineering Origin:** Wilson-Eval3ngine was conceived on July 14, 2026 through a collaborative session where **The Repo Operator Arty (Runndownn)** challenged the Geezer Mekanix Agentic Engineering Platform to demonstrate its capabilities—proving that free models can deliver exceptional coding quality and speed, dismissing the notion of "AI slop." Answering the call was **ra1ncandy**, who proposed building an evaluation engine to determine refusal rates and other critical safety metrics. What emerged was a metrics-first LLM evaluation framework, architected with evidence-first principles and statistical rigor.

The framework was built using **BinReaper x0.0.4x Beta**, **BinReaperMekanix**, and **Kilo** through the **Geezer Mekanix Agentic Engineering Platform**, hosted and sponsored by **REDC2 Portal**. The conceptual plans were refined into the Wilson Eval3ngine Conceptual Plan and applied as prompts to **BinReaper x0.0.4x Beta GPT 5.6 Sol Pro**, which jump-started and enhanced the process. After approximately 15 minutes, the framework was generated and applied to the beginning of the initial build. While GPT 5.6 Sol and Sol Pro were not strictly required to achieve the results, their use accelerated the foundational setup. Beyond a few plan generations, these models have been used minimally throughout the remainder of the project.

Initial coding work was completed using **Laguna M.1 (free)**, with current edits being made using **Laguna S2.1 (free)**. Planning was done using **BinReaper x0.0.4x Beta GPT 5.6 Sol Extended Thinking** and **Pro Version**.

**The platform transforms human intent into Bounded. Observable. Evidence-Aware. Governed. execution.**

AI was not used as a substitute for engineering discipline. Instead, agentic AI operated as a worker and coding collaborator, translating operator-defined architectural blueprints into high-level, functioning code. Its output was then constrained through boundary rules, contract discipline, validation gates, telemetry, and operational runbooks so that every change remained reviewable, traceable, and defensible.

Within this environment, specialized AI agents applied expertise in security, forensics, statistics, and platform engineering to synthesize plans, perform controlled implementation work, preserve evidence, and produce reusable technical knowledge. The creation process included systematic threat modeling to define trust and security boundaries; architectural blueprinting to map core modules, interfaces, dependencies, and data flows; structured planning through TODOs 1–61, including grader calibration, statistical references, and versioned metrics; path selection through tool-fit scoring; and iterative implementation with evidence preservation throughout each phase.

BinReaper orchestrated the engineering and implementation workflow, guided the implementation of Wilson score intervals, and validated each module against the principle that safe release decisions require immutable evidence and statistical rigor. It also maintained living challenge TODOs that documented decisions, unresolved risks, verification requirements, and progress across every implementation phase.

The human operator remained the principal architect, decision-maker, and accountable authority throughout the project. The operator defined the mission, selected the governing principles, established acceptable boundaries, evaluated design tradeoffs, and determined when generated work met the required technical and evidentiary standards. Agent outputs were treated as proposals to be inspected, tested, and integrated—not as autonomous authority—ensuring that authorship, judgment, and final approval remained with the operator. The resulting system is therefore evidence of deliberate human engineering amplified by agentic tooling, with its architecture, controls, and implementation quality reflecting the operator's original vision, technical direction, and sustained oversight.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Keep credentials, private topology, provider allowlists, raw runtime assurance material, real KMS/backup metadata, and identity details out of public issues, PR text, screenshots, and examples.

## License

MIT. See [LICENSE](LICENSE).
