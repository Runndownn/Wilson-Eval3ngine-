# Wilson Eval3ngine — Foundation Framework

Wilson Eval3ngine (WE3) is a metrics-first, evidence-backed framework for evaluating whether an LLM:

1. refused when it should;
2. refused when it should not;
3. complied safely and usefully;
4. complied unsafely; or
5. produced ambiguous or partial behavior.

This repository is **version 0.1.0 Foundation**. It is a runnable vertical slice for contract, evidence, counting, gate, and lineage validation. It is **not approved for production model certification**.

## What is implemented

- Strict, versioned Pydantic contracts for experiments, datasets, cases, provider traffic, classifications, metrics, thresholds, and operations.
- Deterministic expectation compilation before target execution.
- Deterministic mock provider with safe fault and behavior sentinels.
- Content-addressed artifact storage with SHA-256 verification.
- Five-outcome deterministic foundation grader.
- Core safety/helpfulness/reliability metrics with Wilson intervals.
- Release gates that block observed unsafe compliance and return `indeterminate` when support is insufficient.
- Ed25519-signed JSON release dossier and inert HTML summary.
- SQLAlchemy state schema, hash-linked audit ledger, and PostgreSQL leasing contract.
- Development REST API, CLI, example experiments, JSON Schemas, and automated tests.
- A 35-section critical architecture and delivery blueprint.

## Deliberate production blockers

The foundation does not include real provider adapters, production OIDC, PostgreSQL RLS runtime policy, external immutable object storage, calibrated semantic/LLM graders, human review UI, cluster bootstrap, production observability, or disaster-recovery evidence.

## Run locally

From the repository root:

```bash
python -m pip install -e ".[dev]"
we3 validate examples/experiments/foundation.yaml
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
we3 verify-dossier var/foundation/release_dossier.json
python -m pytest -q
```

The run creates:

```text
var/foundation/
├── .dev-ed25519-signing-key.pem
├── experiment_result.json
├── release_dossier.json
└── report.safe.html
```

The development key is generated only for local verification. Do not use it in production.

## Demonstrate a critical gate block

```bash
we3 run examples/experiments/critical_failure.yaml --output var/critical-failure --database-url sqlite:///./var/we3-critical.db --artifact-root var/artifacts-critical
```

The candidate mock profile emits inert unsafe-content sentinels; it contains no operational exploit instructions. A confirmed unsafe-compliance event causes a `block` decision.

## Development API

```bash
WE3_DATABASE_URL=sqlite:///./var/api.db WE3_ARTIFACT_ROOT=./var/api-artifacts we3 serve --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl --fail --silent http://127.0.0.1:8000/health
```

Validate a manifest through the API:

```bash
python -c 'import json,yaml; print(json.dumps(yaml.safe_load(open("examples/experiments/foundation.yaml"))))' > /tmp/we3-foundation.json
curl --fail --silent \
  -H 'Content-Type: application/json' \
  -H 'X-WE3-Project-ID: model-safety' \
  -H 'X-WE3-Role: evaluation_engineer' \
  --data-binary @/tmp/we3-foundation.json \
  http://127.0.0.1:8000/v1/experiments:validate
```

Development headers are intentionally rejected by production configuration.

## Contracts

The repository includes `contracts/openapi.v1.json` and nine versioned JSON
Schemas. Export the implemented JSON Schemas:

```bash
we3 export-schemas --output contracts/schemas
```

## Architecture

Read:

- `DELIVERY_NOTES.md`
- `docs/implementation_blueprint.md`
- `docs/requirements_catalog.csv`
- `docs/source_evidence.md`
- `docs/test_report.md`
- `docs/architecture/threat-model.md`
- `docs/adrs/`
- `docs/operations/foundation-runbook.md`

## Safe content handling

The sample dataset uses synthetic, inert prompts and provider sentinels. Reports never embed raw prompts or model responses. Evidence remains in the project-scoped artifact store.

## License

MIT. See `LICENSE`.
