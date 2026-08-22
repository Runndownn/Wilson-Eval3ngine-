# Getting Started with Wilson Eval3ngine

This guide gets a new user from a clean checkout to a working, inspectable evaluation without requiring them to infer how the repository is supposed to fit together. Start with the deterministic local lane so the evidence model is clear before introducing provider credentials, external network behavior, or production infrastructure.

## 1. Requirements

WE3 declares support for Python `3.12` through `3.14`. You also need Git and a normal Python virtual environment. Docker is optional for local learning and becomes relevant only when validating deployment-oriented paths.

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

The editable install provides the `we3`, `we3-gui-start`, and `we3-gui-stop` commands declared by the package. The development extra installs the normal test/coverage tooling used by repository validation.

## 3. Validate before executing

```bash
we3 validate examples/experiments/foundation.yaml
```

This validates the included experiment and referenced dataset/contracts before work is sent anywhere. The `foundation.yaml` name is historical: it identifies the deterministic local vertical-slice example, not the maturity level of the entire current repository.

## 4. Run the credential-free local evaluation

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

The local lane uses deterministic mock-provider behavior, SQLite, and local filesystem artifacts. It is intended to expose the complete measurement sequence safely: input validation, expectation compilation, request rendering, provider attempts, response evidence, grading, metric snapshots, Wilson intervals, gates, report/dossier generation, and result indexing.

After the run, inspect `var/foundation/` and the configured artifact root. The precise output set can evolve, so treat returned paths and current contracts as authoritative rather than relying on a memorized file list.

## 5. Verify the dossier

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

Signature verification detects post-generation dossier modification. In the deterministic local path the signing key is a development artifact; managed production signing identity and key custody are separate assurance concerns.

## 6. Useful Make targets

The Makefile wraps the same basic workflow:

```bash
make validate
make demo
make verify
```

Development checks are:

```bash
make lint
make test
make coverage
```

`make lint` compiles Python source/tests/scripts, validates active documentation image references, and syntax-checks the browser JavaScript used by the supported GUI composition. `make coverage` enforces the repository's configured overall 80% threshold. These are source-level checks; they do not prove the behavior of a real provider or deployed environment.

`make clean` is the cleanup target for caches/build outputs. Backup restore planning is intentionally separate from source-tree cleanup so an operational planning command has no unrelated filesystem side effects.

## 7. Start the operator GUI

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. The supported launcher accepts loopback only because the GUI can manage provider credentials, endpoints, model inventory, jobs, charts, reports, exports, and deletion. Remote access belongs behind a separately authenticated and authorized TLS proxy.

The current workflow is:

1. **Endpoints** — add and test an approved provider destination.
2. **Models** — discover or register the exact provider/model identities available through those endpoints.
3. **Generate** — select models and prompt material, review execution mode and request volume, then start a bounded job.
4. **Charts** — inspect run-scoped visualizations and their data/metadata context.
5. **Reports** — read generated PDFs and reconcile the narrative with hashes, sidecars, run/model metadata, and exports.

Current screenshots and the detailed interpretation rules are in [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md).

## 8. What you should understand when the GUI opens

The top-bar **Endpoints / Models / Runs / Reports** numbers are inventory counters. They are not quality scores and are not evidence that a release passed. A workspace can contain hundreds of discovered models and zero evaluated runs.

On **Endpoints**, `online` means the configured destination was reachable under the test. It does not mean the model is safe or good. An offline provider should be debugged as connectivity/credential/TLS/routing/provider state before any missing model output is interpreted behaviorally.

On **Models**, family grouping and recommended starting points are navigation aids. They do not replace the exact provider model ID and endpoint lineage required for reproducibility.

On **Generate**, the important pre-flight question is: *what population and how many requests am I about to execute?* Check selected models, prompt set, execution mode, and request volume before starting, especially with metered hosted providers.

On **Charts**, distinguish run-derived evidence from **demo charts**. Demo charts are synthetic demonstrations created only through the demo action. They must not become benchmark or release claims.

On **Reports**, understand that the PDF is a presentation layer. If a legacy report says models were not recorded or lacks current run metadata, that missing provenance should remain visible; use associated sidecars/hashes or rerun under the current evidence path rather than inventing lineage.

## 9. Connect a real hosted or local provider

Do not place a provider key in source code, committed YAML, a shell command, or a committed `.env` file. Use [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md), which documents public HTTPS providers, intentional local/private gateways, Ollama, and CLI-backed adapters separately.

The mental model is **connectivity first, identity second, evaluation third**:

1. prove the destination/credential work;
2. discover or register the exact model identity;
3. only then run an evaluation so provider failures remain distinguishable from model behavior.

## 10. Understand the GUI composition

The baseline page in `gui/static/index.html` contains the current five workspaces and loads `enhanced.js`. The supported server path then injects the versioned `ux4`, `ux5`, and `ux6` CSS/JavaScript overlays before serving `/`. Those files are therefore active runtime behavior even though their tags are not permanently written into the baseline HTML.

This distinction is useful when debugging the interface: inspect both the baseline document and the runtime overlay composition instead of assuming an apparently unreferenced `ux*.js` file is dead code.

## 11. Understand what a result means

Read a result as a bundle of related evidence, not as one chart or PDF. Behavioral classifications say what the model did; reliability state says whether execution was valid; metric snapshots say how the population was counted; confidence intervals show uncertainty; gates apply explicit decision rules; and hashes/signatures provide lineage/integrity evidence.

A successful deterministic run demonstrates that this local measurement path works for the checked-out code/configuration. It does **not** certify an arbitrary real provider, organizational IdP, secret manager, production network, human-review operation, backup/restore deployment, or container stack.

## 12. Known statistical cautions

The core Wilson interval path is implemented, but one metric-comparison function still exposes a placeholder `p_value=0.5` where completed bootstrap/reference significance work is intended. One snapshot helper also documents an approximation where `prompt_family_count` uses the number of run IDs. Treat those paths as provisional for certification-grade significance or independence claims; [Current Status](STATUS.md) records the exact boundary.

## 13. Where to go next

Read [Features](FEATURES.md) for a capability-oriented tour, [Architecture](ARCHITECTURE.md) for component/data-flow relationships, and [Current Status](STATUS.md) before making maturity or production-readiness claims. Security reviewers should continue with [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md) and [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md).
