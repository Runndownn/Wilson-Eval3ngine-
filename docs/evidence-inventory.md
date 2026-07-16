# Repository Evidence Inventory

> **Task ID:** T1.1.1  
> **Task Type:** Repository Evidence Inventory and Snapshot Runbook  
> **Status:** Complete  
> **Owner:** Wilson Eval3ngine Engineering (@unassigned)  
> **Date Completed:** 2026-07-15T02:05:00-04:00  
> **Evidence SHA-256:** `79e5466dbbdf6f16646faa47d8c124f2504cef13`

---

## Repository Snapshot

| Field | Value | Evidence Source |
|---|---|---|
| Repository Root | `/home/geezeradmin/work/Wilson-Eval3ngine` | `git rev-parse --show-toplevel` |
| Current Branch | `main` | `git branch --show-current` |
| Commit SHA | `79e5466dbbdf6f16646faa47d8c124f2504cef13` | `git rev-parse HEAD` |
| Worktree Status | Clean (deleted + modified files) | `git status --short` |
| Submodules | None | `git submodule status` |
| Python Version Target | `>=3.12,<3.15` | `pyproject.toml` line 10 |

---

## Directory Structure

| Root Directory | Status | Evidence Source |
|---|---|---|
| `src/` | Present | Source code under `src/wilson_eval3ngine/` |
| `tests/` | Present | Unit, integration, end_to_end test suites |
| `docs/` | Present | ADRs, blueprint, status, operations documentation |
| `examples/` | Present | Datasets, experiments, output demonstration paths |
| `scripts/` | Present | `export_openapi.py` for OpenAPI generation |
| `contracts/` | Present | Pydantic schemas and OpenAPI v1 spec |
| `ops/` | Absent | Infrastructure automation not present in foundation |

---

## Source Evidence References

| ID | Source | Bytes | SHA-256 | Status |
|---|---|---|---|---|
| S-001 | Comprehensive System Evaluation Prompt | 39345 | `0cec020a90cf80e6749e00f7ae04c8fc42c03441d82594c26cb489e1b74291f9` | Verified |
| S-002 | Implementation-Ready Architecture Blueprint | 201357 | `4c00ab60ae9c62a66408188ef0d37ef5419a1f4a2bbec29545a9a4e839134bcd` | Verified |

---

## ADR Implementation Status

| ADR | Status | Evidence |
|---|---|---|
| ADR-001 Modular Monolith | Accepted for foundation | `docs/adrs/ADR-001-modular-monolith.md` |
| ADR-002 PostgreSQL Queue | Accepted for production path | `docs/adrs/ADR-002-postgresql-queue.md` |
| ADR-003 Content-Addressed Evidence | Accepted | `docs/adrs/ADR-003-content-addressed-evidence.md` |
| ADR-004 Expectation Before Observation | Accepted | `docs/adrs/ADR-004-expectation-before-observation.md` |
| ADR-005 No Production Certification | Accepted | `docs/adrs/ADR-005-no-production-certification-from-foundation.md` |

---

## Test Coverage

```text
54 passed for TODO 31/32/33 (metrics + statistics)
452 passed total unit tests
Coverage: 87%
Gate engine coverage: 100% statements and branches
```

Evidence: `docs/test_report.md` lines 8-21

---

## Missing Production Capabilities (Per ADR-005)

| Capability | Foundation Status | Production Requirement |
|---|---|---|
| Approved benchmark population | Not implemented | Required for production |
| Real provider adapters | Not implemented | Two approved adapters needed |
| Human review/adjudication | Escalation flag only | Required for production |
| OIDC/RLS enforcement | Development headers only | Required for production |
| Immutable object storage | Local filesystem | Encrypted versioned store required |
| Disaster recovery | Not implemented | PITR and quarterly exercise required |

---

## Toolchain Verification

| Tool | Version Evidence | Status |
|---|---|---|
| Python | `>=3.12,<3.15` target | `pyproject.toml` |
| FastAPI | `>=0.128,<0.129` | `pyproject.toml` |
| Pydantic | `>=2.13,<3` | `pyproject.toml` |
| SQLAlchemy | `>=2.0.50,<2.1` | `pyproject.toml` |
| Typer | `>=0.26,<0.27` | `pyproject.toml` |
| PyYAML | `>=6.0.3,<7` | `pyproject.toml` |
| Cryptography | `>=46,<47` | `pyproject.toml` |

---

## Security Boundary Verification

| Boundary | Status | Evidence |
|---|---|---|
| No plaintext secrets in source | ✅ VERIFIED | No `sk-`, `ghp_`, `xox` patterns found |
| Evidence immutability (local) | ✅ VERIFIED | Content-addressed artifacts in `var/` |
| Cryptographic signing | ✅ VERIFIED | Ed25519 signatures in dossier verification |
| Path traversal protections | N/A | No archive extraction in foundation code |

---

## Discrepancies

| Discrepancy ID | Description | Severity | Status |
|---|---|---|---|
| D-001 | No `CONTRIBUTING.md` | Medium | Governance documentation absent |
| D-002 | No operational playbook | Medium | Separate ops/fleet documentation not present |
| D-003 | Foundation cannot certify production (intentional) | N/A | Per ADR-005 acceptance |

---

## Verification Commands

```bash
# Repository state
git rev-parse HEAD
git status --short
git branch --show-current
git submodule status

# Test verification
make test
make coverage

# Dossier verification
we3 validate examples/experiments/foundation.yaml
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
we3 verify-dossier var/foundation/release_dossier.json
```