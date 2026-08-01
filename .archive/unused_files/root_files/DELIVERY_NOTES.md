# Wilson Eval3ngine 0.1.0 Foundation — Delivery Notes

**Delivery date:** July 15, 2026  
**Status:** Runnable foundation for development and controlled internal testing  
**Production certification status:** Prohibited until the documented pre-production gates are met

## Delivered

- A Python modular-monolith implementation with typed, versioned domain contracts.
- Deterministic expectation compilation, mock provider execution, five-outcome grading, metric calculation, Wilson intervals, and release gates.
- Content-addressed local evidence, a hash-linked audit ledger, Ed25519-signed release dossiers, and inert HTML reports.
- A development REST API, CLI, PostgreSQL-compatible schema, PostgreSQL `SKIP LOCKED` leasing contract, Docker/Compose profile, JSON Schemas, and OpenAPI contract.
- A synthetic eight-family safety-boundary dataset and two end-to-end demonstrations.
- A 35-section critical architecture and implementation blueprint, requirements catalog, ADRs, threat model, runbook, status matrix, and initial backlog.

## Verification performed

| Check | Result |
|---|---|
| Automated tests | 32 passed |
| Total statement/branch coverage | 85% |
| Gate engine statement/branch coverage | 100% |
| Python bytecode compilation | Passed |
| JSON, YAML, and TOML parsing | Passed |
| JSON Schema export | 9 schemas generated |
| OpenAPI export | Generated deterministically |
| Foundation dossier integrity | Digest and Ed25519 signature verified |
| Critical-failure demonstration | Under-refusal candidate blocked |
| Audit chain verification | Passed in both demonstrations |
| Private signing material in delivery | None |

## Demonstration results

### Foundation comparison

- `mdl_mock_balanced`: `indeterminate`
- `mdl_mock_over_refusal`: `indeterminate`

Both are intentionally indeterminate because the demonstration has only eight independent prompt families while the provisional threshold set requires thirty. The metrics still expose the over-refusal regression.

### Critical-failure comparison

- `mdl_mock_balanced`: `indeterminate`
- `mdl_mock_under_refusal`: `block`

The unsafe-compliance event overrides insufficient sample support, as required by the safety-gate precedence rule.

## Not verified in this environment

- Docker image build or Compose startup; no Docker runtime was available.
- PostgreSQL integration and concurrent `SKIP LOCKED` worker behavior.
- Real hosted-provider adapters or provider fingerprinting.
- Production OIDC, row-level security enforcement, managed signing keys, external immutable storage, human-review operations, disaster recovery, or SLO evidence.
- Grader calibration against an approved hidden benchmark.

These are explicit production blockers, not implied capabilities.
