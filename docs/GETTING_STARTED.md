# Getting Started with Wilson Eval3ngine

This guide gets a new user from a clean checkout to a working evaluation with the fewest concepts necessary. Start with the deterministic local run so you can see the evidence pipeline without provider credentials, then move to the GUI and real providers only after the local workflow makes sense.

## 1. Requirements

WE3 declares support for Python `3.12` through `3.14`. You also need Git and a normal Python virtual environment; Docker is optional for local learning and becomes relevant only when validating deployment-oriented paths.

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

The editable install provides the `we3`, `we3-gui-start`, and `we3-gui-stop` commands declared by the package. The development extra installs the test and coverage dependencies needed for normal repository validation.

## 3. Validate the included experiment

```bash
we3 validate examples/experiments/foundation.yaml
```

This checks the included deterministic experiment and its referenced dataset/contracts before execution. The `foundation.yaml` filename is historical: it names the original local vertical-slice example, not the maturity level of the entire current repository.

## 4. Run the credential-free local evaluation

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

The local lane uses deterministic mock-provider behavior, SQLite, and local filesystem artifacts. It is designed to let a new contributor observe the full measurement sequence—input validation, expectation compilation, request rendering, provider attempts, response evidence, grading, metrics, Wilson intervals, gates, report/dossier generation, and result indexing—without needing an external account.

After the run, inspect `var/foundation/`. The exact files can evolve, but the lane returns paths for the signed dossier, safe HTML report, experiment-result index, and signing key used for that local execution, while content-addressed run artifacts are written beneath the configured artifact root.

## 5. Verify the generated dossier

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

Signature verification checks that the dossier has not simply been edited after generation. In the deterministic local path the signing key is a development artifact; managed production signing identity and key custody are separate assurance concerns.

## 6. Use the Makefile shortcuts

The repository wraps the same basic workflow in convenient targets:

```bash
make validate
make demo
make verify
```

For development validation:

```bash
make lint
make test
make coverage
```

These commands are appropriate source-level checks. They do not, by themselves, prove the behavior of an external provider or a production deployment.

## 7. Start the operator GUI

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. The official launcher accepts loopback only because the GUI can manage provider credentials, endpoints, model inventory, jobs, reports, charts, exports, and deletion; remote access belongs behind a separately authenticated TLS proxy.

The normal workflow is:

1. **Endpoints** — add and test an approved provider destination.
2. **Models** — discover or inspect the exact models available through that endpoint.
3. **Generate** — select models and prompt material, review the workload, and start a bounded job.
4. **Charts** — inspect distributions, comparisons, uncertainty, latency, tokens, and outcome patterns.
5. **Reports** — inspect PDF narratives, hashes, sidecars, and evidence exports.

See [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) for screenshots and the complete chart catalogue.

## 8. Connect a real hosted or local provider

Do not begin by placing a provider key in source code, an example YAML, a shell command, or a committed `.env` file. Use the supported endpoint/credential workflow described in [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md), where public HTTPS providers, intentional local/private gateways, Ollama, and CLI-backed adapters are documented separately.

The important mental model is that provider connectivity is not the evaluation result. First prove that the destination and credential work, then discover the model identity, and only then run evaluation work so connection errors remain distinguishable from model behavior.

## 9. Understand what a result means

A WE3 result should be read as a bundle of related evidence, not as one chart. Behavioral classifications tell you what the model did, reliability state tells you whether the execution itself was valid, metric snapshots tell you how results were counted, confidence intervals show uncertainty, gates apply an explicit decision policy, and hashes/signatures provide lineage/integrity evidence.

A successful local run demonstrates that the deterministic measurement path works for that code/configuration. It does not certify an arbitrary real provider, production network, organizational identity system, secret manager, backup/restore operation, human-review program, or deployed container stack.

## 10. Where to go next

Read [Features](FEATURES.md) for a capability-oriented tour, [Architecture](ARCHITECTURE.md) for the component/data-flow model, and [Current Status](STATUS.md) before making maturity or production-readiness claims. Security reviewers should continue with [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md) and [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md).
