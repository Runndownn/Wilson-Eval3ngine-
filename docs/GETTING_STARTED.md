# Getting Started with Wilson Eval3ngine

This guide gets a new user from a clean checkout to a working, inspectable evaluation without requiring them to infer how the repository fits together. Start with the deterministic local lane so the evidence model is clear before introducing provider credentials, external network behavior, or production infrastructure.

## 1. Requirements

WE3 declares support for Python `3.12` through `3.14`. You also need Git and a normal Python virtual environment. Docker is optional for local learning and becomes relevant when validating deployment-oriented paths.

## 2. Clone and install

### Linux or macOS

```bash
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The editable development install provides `we3`, `we3-backup`, `we3-gui-start`, and `we3-gui-stop`; backup-specific PostgreSQL/AWS dependencies are optional and installed separately when recovery work is required.

## 3. Validate before executing

```bash
we3 validate examples/experiments/foundation.yaml
```

This validates the included experiment and referenced dataset/contracts before work is sent anywhere. The `foundation.yaml` name is historical: it identifies the deterministic local vertical-slice example, not the maturity level of the entire current repository.

## 4. Run the credential-free local evaluation

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

The local lane uses deterministic mock-provider behavior, SQLite, and local filesystem artifacts. It exposes the measurement sequence safely: input validation, expectation compilation, request rendering, provider attempts, response evidence, grading, metric snapshots, Wilson intervals, gates, report/dossier generation, and result indexing.

After the run, inspect `var/foundation/` and the configured artifact root. The exact output set can evolve, so trust returned paths and current contracts rather than a memorized file list.

## 5. Verify the dossier

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

Signature verification detects post-generation dossier modification. In the deterministic local path the signing key is a development artifact; managed production signing identity and key custody are separate assurance concerns.

## 6. Useful Make targets

```bash
make validate
make demo
make verify
make lint
make test
make coverage
```

`make lint` compiles Python source/tests/scripts, validates active documentation image references, and syntax-checks the browser JavaScript used by the supported GUI composition. `make coverage` enforces the repository's configured overall 80% threshold. These are source-level checks, not proof of a real provider or deployment.

`make clean` owns source-tree cleanup, including `__pycache__`; recovery planning has no unrelated source-tree cleanup side effect.

## 7. Start the operator GUI

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. This is the supported secure default. The launcher repairs historical wildcard defaults such as `0.0.0.0` to loopback unless the operator deliberately sets `WE3_GUI_ALLOW_REMOTE_BIND=1`.

If a controlled deployment genuinely needs a non-loopback listener, configure independent TLS, authentication, authorization, firewall/network policy, and trusted proxy behavior first, then use the explicit override. The override only changes bind policy; it is not an access-control system.

The current workflow is:

1. **Endpoints** — add and test an approved provider destination.
2. **Models** — discover or register exact provider/model identities.
3. **Generate** — select models and prompt material, review execution mode and request volume, then start a bounded job.
4. **Charts** — inspect run-scoped visualizations and data/metadata context.
5. **Reports** — read PDFs and reconcile narrative output with hashes, sidecars, run/model metadata, and exports.

Current screenshots and interpretation rules are in [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).

## 8. What you should understand when the GUI opens

The top-bar **Endpoints / Models / Runs / Reports** values are inventory counters. They are not quality scores and do not mean a release passed. A workspace can contain hundreds of discovered models and zero evaluated runs.

On **Endpoints**, `online` means the destination was reachable under the connection test. It does not mean the model is safe or good. Debug an offline endpoint as a connectivity/credential/TLS/routing/provider problem before interpreting missing output behaviorally.

On **Models**, family grouping and recommended starting points are navigation aids. Reproducibility still depends on the exact provider model ID and endpoint/configuration lineage.

On **Generate**, ask: *what population and how many requests am I about to execute?* Check selected models, prompt set, execution mode, and request volume, particularly for metered hosted providers.

On **Charts**, distinguish run-derived evidence from **demo charts**. Demo charts are synthetic demonstrations generated through the demo action and must not become benchmark or release claims.

On **Reports**, the PDF is a presentation layer. If a legacy report lacks recorded models/current run metadata, preserve that provenance gap and use associated sidecars/hashes or rerun under the current evidence path rather than inventing lineage.

## 9. Connect a real hosted or local provider

Do not place a provider key in source, committed YAML, a shell command, or a committed `.env` file. Use [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md).

The mental model is **connectivity first, identity second, evaluation third**:

1. prove the destination/credential works;
2. discover or register the exact model identity;
3. then evaluate so provider failures remain distinguishable from model behavior.

Remember that local/private provider egress and remote GUI listening use different controls: `WE3_GUI_ALLOW_LOCAL_PROVIDERS` governs provider destinations, while `WE3_GUI_ALLOW_REMOTE_BIND` governs the GUI listener.

## 10. Understand the GUI composition

`gui/static/index.html` contains the five baseline workspaces and loads `enhanced.js`. The supported server path injects versioned `ux4`, `ux5`, and `ux6` CSS/JavaScript overlays before serving `/`. Those files are active runtime behavior even though their tags are not permanently written into the baseline HTML.

When debugging the interface, inspect the baseline and runtime composition before assuming an apparently unreferenced `ux*.js` file is dead code.

## 11. Understand what a result means

Read a result as a bundle, not one chart/PDF. Behavioral classifications say what the model did; reliability state says whether execution was valid; metric snapshots say how the population was counted; confidence intervals show uncertainty; gates apply explicit rules; hashes/signatures provide lineage/integrity evidence.

A successful deterministic run demonstrates the local measurement path for the checked-out code/configuration. It does **not** certify an arbitrary real provider, IdP, secret manager, production network, human-review operation, production backup deployment, or container stack.

## 12. Know the current provisional and runtime-dependent areas

### Statistics

One metric-comparison path still exposes placeholder `p_value=0.5` pending completed bootstrap/reference significance work. One snapshot helper also approximates `prompt_family_count` with run count. Do not use those paths for certification-grade significance or independence claims.

### Persona views

The analyst view rejects reports outside the authorized project scope, but executive support/uncertainty aggregate fields are still provisional constants because the canonical report does not yet carry authoritative aggregate contracts for them. The reviewer regex redactor is baseline masking, not a production DLP policy.

### Backup/PITR/recovery is implemented, but production assurance is separate

The repository now implements encrypted PostgreSQL physical backup, KMS-wrapped data keys, signed manifest verification, a restart-durable backup catalogue, real WAL-file ingestion and continuity checks, signed recovery baselines, loopback-only PostgreSQL PITR restore, cryptographic audit-chain verification, and reconciliation against the actual outbox/provenance tables. Those capabilities are intentionally outside the simple SQLite foundation lane.

To work on recovery, install the optional dependencies and inspect the dedicated interface:

```bash
python -m pip install -e ".[dev,backup]"
we3-backup --help
```

Do not begin by running a recovery command against a production database. Read [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) first and reproduce the workflow only in an authorized disposable/isolated environment. The runbook explains KMS/trust configuration, how a signed recovery baseline differs from a backup manifest, why real WAL continuity matters, and how restore evidence should be interpreted.

The repository's CI contains a separate disposable-PostgreSQL recovery exercise because a physical backup/PITR claim cannot be proven by the local SQLite evaluation demo. A passing CI recovery exercise is evidence for that commit and CI environment; it still does not prove a private deployment's 15-minute RPO, four-hour RTO, KMS policy, backup-storage durability, tablespace topology, or return-to-service approval process.

The native streaming recovery path currently rejects PostgreSQL clusters with user-defined tablespaces. That is an explicit supported-boundary check rather than a silent partial backup.

## 13. Where to go next

Read [Features](FEATURES.md) for capability groups, [Architecture](ARCHITECTURE.md) for component/data-flow relationships, and [Current Status](STATUS.md) before making maturity/production-readiness claims. Security reviewers should continue with [Security Policy](../SECURITY.md), [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md), and [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md). Recovery operators should use [Backup and Recovery Runbook](operations/backup-recovery-runbook.md) rather than the historical flat backup CLI examples.
