# Getting Started with Wilson Eval3ngine

This guide takes a clean checkout through the deterministic local lane first. That is the safest place to understand WE3's evidence model before introducing provider credentials, private network destinations, production identity, or recovery infrastructure.

## 1. Requirements

WE3 supports Python `3.12` through `3.14`. Install Git and use an isolated Python virtual environment. Docker is optional for the local deterministic path and is relevant for deployment-contract validation.

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

The editable install provides `we3`, `we3-gui-start`, and `we3-gui-stop` plus the repository's development/test tooling.

## 3. Validate the bundled deterministic experiment

```bash
we3 validate examples/experiments/foundation.yaml
```

`foundation.yaml` is a historical identifier for the first complete deterministic vertical slice. It is not a maturity label for the current repository.

Validation checks the experiment and referenced dataset/contracts before work is sent anywhere.

## 4. Run without provider credentials

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

The local lane uses deterministic provider behavior, SQLite, and local filesystem artifacts. It exercises input validation, expectation compilation, request rendering, attempts, grading, metric snapshots, Wilson intervals, gates, reports/dossiers, and result indexing.

Inspect `var/foundation/` and the configured artifact root after the run. Trust returned paths and current contracts rather than assuming a fixed artifact list forever.

## 5. Verify the dossier

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

Signature verification detects post-generation dossier modification. The deterministic lane uses development signing material; managed production signing identity and key custody are separate assurance requirements.

## 6. Run repository verification

```bash
make validate
make demo
make verify
make lint
make test
make coverage
```

`make lint` validates Python/browser/documentation source contracts. `make coverage` enforces the configured repository coverage threshold. These commands test the checked-out source; they do not prove a real provider or deployment.

GitHub's normal CI and the separate security/quality assurance workflow are configured for `main`. A workflow definition is not evidence that a particular revision passed—check the actual run for the exact commit.

## 7. Start the operator GUI

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. Loopback is the supported default. `WE3_GUI_ALLOW_REMOTE_BIND=1` is an explicit bind-policy override only; remote operation still requires separately validated TLS, authentication, authorization, firewalling, proxy policy, and multi-user isolation.

The supported workflow is:

1. **Endpoints** — register/test an approved provider destination.
2. **Models** — discover or register exact provider/model identities.
3. **Generate** — select models and prompt material, review execution mode and request volume, then start bounded work.
4. **Charts** — inspect run-scoped visualizations with their metadata/evidence context.
5. **Reports** — reconcile presentation output with hashes, run/model metadata, sidecars, and exports.

The launcher installs one reviewed API-key secret transport before serving. Presentation overlays cannot replace that transport. The active browser composition is baseline `index.html`/`enhanced` plus versioned `ux4`/`ux5`/`ux6` overlays.

See [GUI & Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) for current screenshots and interpretation rules.

## 8. Connect a real provider deliberately

Do not place provider keys in source, committed YAML, command-line arguments, or committed `.env` files. Use [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md).

Use the sequence **connectivity → identity → evaluation**:

1. prove the destination and credential work;
2. establish the exact model identity;
3. evaluate only after those facts are known so infrastructure failures remain distinct from model behavior.

CLI-backed provider responses deliberately omit raw stderr and absolute executable paths from canonical response metadata. Some upstream CLI contracts still carry prompts in process arguments, so same-user process inspection is part of that local host trust boundary.

## 9. Read metric evidence correctly

A result is a bundle, not a chart or PDF. Behavioral classification says what the model did. Reliability state says whether execution was valid. Metric snapshots define population/support. Confidence intervals express uncertainty. Gates apply explicit rules. Hashes/signatures establish lineage/integrity evidence.

Compatible independent-binomial metric comparisons use a real two-sided significance test. Dependent/paired/clustered experimental designs require the method appropriate to that design. The generic snapshot helper does not manufacture prompt-family independence from run count: callers must provide family lineage, otherwise independent-family support is zero.

Timeout and malformed-response counts are diagnostic subtypes of the operational-failure aggregate and are not counted again in the aggregate numerator.

## 10. Read persona output conservatively

Analyst views reject missing or cross-project scope. Executive support/uncertainty aggregates are `None` until the canonical report defines authoritative aggregate semantics; missing evidence is not rendered as `100%` support or `0%` uncertainty. Unknown release-gate vocabulary fails closed to `indeterminate`.

Reviewer redaction is bounded pattern masking, not a production DLP system.

## 11. Understand backup and PITR status

The native backup/recovery subsystem is real implementation rather than a simulation-only scaffold. It includes encrypted PostgreSQL physical backups, encrypted WAL objects, signed manifests, trusted-key verification, cluster/WAL identity checks, continuity validation, signed baselines, isolated restore/replay, reconciliation, and recovery evidence.

Do not infer an RPO/RTO from source code. A production recovery claim requires executed evidence for cadence, WAL retention/continuity, destructive restore, target reachability, reconciliation, and measured recovery time/data loss in the target environment.

Current recovery engineering limitations and runtime-assurance boundaries are maintained in [Current Status](STATUS.md) and [Backup and Recovery Runbook](operations/backup-recovery-runbook.md).

## 12. What the deterministic lane does not prove

A successful local run does not certify an arbitrary provider, identity provider, production secret/KMS authority, network perimeter, review operation, backup schedule, restore outcome, container deployment, or release threshold policy.

For current truth, continue with [Features](FEATURES.md), [Architecture](ARCHITECTURE.md), and [Current Status](STATUS.md). Security reviewers should also read [Security Policy](../SECURITY.md) and [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md). Historical Plans/TODO material remains provenance and is not current release authority.
