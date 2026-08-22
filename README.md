<p align="center">
  <img src="docs/assets/brand/wilson-eval3ngine-logo.png" alt="Wilson Eval3ngine" width="1000">
</p>

# Wilson Eval3ngine

**Evidence-first LLM evaluation for safety, usefulness, reliability, comparison, and governed release decisions.**

[Getting Started](docs/GETTING_STARTED.md) · [Features](docs/FEATURES.md) · [Architecture](docs/ARCHITECTURE.md) · [Current Status](docs/STATUS.md) · [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md) · [Security](SECURITY.md) · [Documentation Index](docs/README.md)

Wilson Eval3ngine (WE3) turns versioned experiments and datasets into traceable provider attempts, behavior classifications, uncertainty-aware metrics, explicit release decisions, and reviewable evidence. The repository distinguishes **implemented source**, **supported composition**, **observed automated assurance**, and **production runtime evidence**; none of those terms is used as a substitute for another.

## Project position

**Package version:** `0.1.0`  
**Stage:** active evaluation platform / pre-production assurance  
**Production certification:** not established by source code alone

The deterministic local lane remains the fastest way to inspect the complete measurement contract. The repository also includes real-provider adapters, durable PostgreSQL scheduling, human review/adjudication, encrypted evidence storage, OIDC/project controls, distributed rate limiting, deployment hardening, GUI/operator workflows, backup/WAL/PITR recovery, telemetry, and certification orchestration. [Current Status](docs/STATUS.md) is the authority for implementation and assurance boundaries.

## Measurement contract

WE3 preserves five behavioral outcomes rather than collapsing behavior and infrastructure into a single pass/fail result:

| Outcome | Meaning |
|---|---|
| **Appropriate refusal** | A request that should be refused was refused. |
| **False refusal** | A request that should be answered was unnecessarily refused. |
| **Safe useful compliance** | A permitted request received a safe, useful response. |
| **Unsafe compliance** | A response crossed the defined safety boundary. |
| **Ambiguous / partial** | The response cannot be classified confidently or completely. |

Timeouts, malformed responses, exhausted retries, authentication failures, and other provider/reliability failures remain separate from behavioral labels. Operational-failure subtypes are diagnostic subsets and are not double-counted in the aggregate failure metric.

<p align="center"><img src="docs/assets/diagrams/evaluation-pipeline.svg" alt="Wilson Eval3ngine evaluation pipeline" width="1100"></p>

The core path is:

1. Validate experiment, dataset identity/version/hash, and execution configuration.
2. Compile expected treatment **before** observing the target response.
3. Render a deterministic provider request and preserve attempts/retries.
4. Grade valid terminal behavior while retaining reliability failures separately.
5. Build metric snapshots with numerator, denominator, exclusions, population lineage, version, and Wilson intervals.
6. Compare compatible independent-binomial proportions with an explicit two-sided statistical test; incompatible or indeterminate populations fail closed.
7. Apply explicit gate/support rules; insufficient evidence is indeterminate, never an artificial pass.
8. Preserve reports, hashes, classifications, metrics, audit data, and signed dossier/result artifacts.

The generic snapshot helper does **not** infer prompt-family independence from run count. Callers that have prompt-family lineage provide it explicitly; otherwise the independent-family count is zero so downstream support checks can fail closed.

## Five-minute deterministic start

Requires Python `3.12–3.14` and Git. No provider credential is required.

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

The deterministic lane proves the local measurement path for the checked-out revision. It does not certify a provider, identity system, production network, KMS, backup schedule, or private deployment.

## Security architecture

<p align="center"><img src="docs/assets/diagrams/trust-boundaries.svg" alt="Wilson Eval3ngine trust and assurance boundaries" width="1100"></p>

The supported API has one authoritative implementation for each request-security control. Shared logging, tracing, response headers, content-type validation, and readiness behavior live in `api/middleware.py`; streaming byte limits live in `api/body_limit.py`; strict metadata/CORS/CSRF/rate-limit/OIDC-revocation controls live in `api/security_middleware.py`; authorization decision evidence lives in `api/authorization_audit.py`. Production composition does not depend on import-time replacement of weaker classes.

Staging/production rate limiting uses the configured Redis authority and fails closed if shared rate state is unavailable. Forwarded client identity is trusted only from configured proxy networks. Browser origins/methods/headers are exact allowlists. Bearer-header OIDC is non-ambient authentication, so credentialed CORS is not advertised by default. Security-relevant unexpected responses are bounded; detailed diagnostics remain server-side.

Production templates keep databases, Redis, monitoring, and the API off direct public host ports and use Caddy as the ingress boundary. Source configuration still requires target-environment evidence for TLS, firewalling, proxy CIDRs, direct-port denial, egress controls, and secret custody.

## Operator GUI

Start the supported loopback launcher:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

The launcher defaults to loopback and installs exactly one reviewed API-key transport before serving. The UX overlay is presentation-only and cannot replace that transport. POSIX uses a one-shot FIFO implementation; unsupported platforms fail closed unless an explicitly configured private transport plugin satisfies the factory contract.

The current five workspaces are **Endpoints → Models → Generate → Charts → Reports**. Current captures live under `docs/assets/gui/current/`; screenshot counts, provider state, model inventory, report totals, and demo charts are point-in-time presentation evidence, not release metrics. See [GUI & Evidence Guide](docs/GUI_AND_EVIDENCE_GUIDE.md).

## Backup, WAL, and point-in-time recovery

The native recovery subsystem in `src/wilson_eval3ngine/backup/` is real implementation, not metadata-only scaffolding. It includes PostgreSQL cluster identity capture, credential-safe physical backup invocation, encrypted payloads, signed manifests, trusted-key verification, WAL continuity checks, recovery baselines, isolated restore execution, reconciliation, and recovery evidence.

That source does not establish an RPO/RTO. Operators must execute and retain target-environment evidence for backup cadence, WAL retention/continuity, restore reachability, reconciliation, and measured recovery objectives. Current engineering constraints such as timeline transitions, crash-safe publication/locking, and time-target semantics are tracked transparently in [Current Status](docs/STATUS.md) and the [Backup and Recovery Runbook](docs/operations/backup-recovery-runbook.md).

## Persona and report boundaries

Analyst views reject missing or cross-project canonical scope before copying metric/artifact lineage. Executive support/uncertainty fields are `None` until the canonical report defines authoritative aggregate semantics; missing evidence is never presented as `100%` support or `0%` uncertainty. Reviewer redaction is bounded pattern masking, not a complete production DLP authority.

Cross-format report reconciliation requires the canonical report hash to survive JSON/CSV/HTML representation. Optional Parquet export fails explicitly when `pyarrow` is unavailable. Hash carriage is a representation-integrity control, not independent semantic proof of every rendered field.

## Repository map

| Path | Purpose |
|---|---|
| `src/wilson_eval3ngine/` | Main application package. |
| `providers/`, `grading/`, `metrics/`, `statistics/`, `gates/` | Provider execution, behavior, measurement, comparison, and decisions. |
| `evidence/`, `storage/`, `reports/`, `security/` | Evidence, rendering, signing, storage, and security controls. |
| `review/`, `ui/`, `gui/` | Human review, persona views, and operator interface. |
| `persistence/`, `execution/` | Database state and durable execution support. |
| `backup/` | Encrypted physical backup, WAL archive, PITR planning/execution, and recovery evidence. |
| `certification/` | Certification requirements and orchestration. |
| `tests/` | Unit, integration, hostile/adversarial, governance, browser, and runtime-contract checks. |
| `infrastructure/`, `docker-compose*.yml`, `Dockerfile*` | Deployment, ingress, observability, and container material. |
| `docs/` | Current documentation plus deliberately preserved historical planning/provenance. |
| `.archive/` | Superseded/unused artifacts retained outside the live implementation surface. |

## Verification

```bash
make install
make lint
make test
make coverage
```

The normal `CI` workflow is configured for `main` pushes and pull requests. The `Security and quality assurance` workflow is also configured for `main` and adds focused security contracts, privacy-safe repository inventory, full non-runtime/non-browser tests with coverage, distribution inspection, hermetic browser checks, and secure-Compose topology validation.

A workflow definition is not evidence that a particular revision passed. Use the actual run for the exact commit before making a CI-assured claim.

## Documentation and provenance

Current product claims belong in current source, [Current Status](docs/STATUS.md), supported operator documentation, and executed evidence. The original plans, prompts, TODO progression, security assessments, and agentic-engineering history remain preserved as provenance and are not rewritten to make earlier forecasts appear current.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Keep credentials, private topology, provider allowlists, raw private assurance material, real KMS/backup metadata, and identity details out of public issues, pull-request text, screenshots, and examples.

## License

MIT. See [LICENSE](LICENSE).
