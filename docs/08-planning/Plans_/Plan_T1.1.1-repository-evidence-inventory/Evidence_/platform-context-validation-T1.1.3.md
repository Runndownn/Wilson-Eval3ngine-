# Production Operating Context and Platform Services - T1.1.3

> **Task:** Validate production operating context and platform services (T1.1.3)  
> **Status:** Complete (Evidence Collected - Capability Gaps Documented)  
> **Owner:** Wilson Eval3ngine Engineering (@unassigned)  
> **Last Updated:** 2026-07-15T02:05:00-04:00

---

## Platform Authority Declaration

**Evidence:** `docs/implementation_blueprint.md` lines 1-10, `framework_status.md` lines 1-20

### Platform Model

| Component | Status | Evidence |
|---|---|---|
| **Deployment Model** | Hybrid modular monolith (per ADR-001) | `docs/adrs/ADR-001-modular-monolith.md` |
| **Database** | PostgreSQL (production), SQLite (local tests) | `pyproject.toml` dependencies, ADR-002 |
| **Evidence Storage** | Local filesystem (foundation) | `var/artifacts/`, ADR-003 |
| **Authentication** | Development headers (foundation) | `pyproject.toml` fastapi, ADR-005 gap |
| **CI/CD** | GitHub Actions | `.github/workflows/ci.yml` |

---

## Services Inventory

### Foundation Runtime Services

| Service | Evidence | Status |
|---|---|---|
| FastAPI | `pyproject.toml` line 13 | Implemented |
| CLI (Typer) | `pyproject.toml` line 18, `we3` script | Implemented |
| OpenAPI generation | `scripts/export_openapi.py` | Available |
| Ed25519 signing | `pyproject.toml` cryptography dependency | Implemented |
| Content-addressed evidence | ADR-003 | Implemented |
| Five-outcome grading | `pyproject.toml` evidence | Implemented |
| Wilson intervals | Blueprint section 5.2 | Implemented |
| Release gate logic | `framework_status.md` line 12-14 | Implemented (provisional) |

---

## Required Production Services (Per ADR-005)

| Service | Foundation Status | Production Requirement | Evidence |
|---|---|---|---|
| PostgreSQL with RLS | Targeted but not enforced | Required for production | ADR-002, ADR-005 |
| Immutable object storage | Local filesystem only | Required for production | ADR-003, ADR-005 |
| OIDC/Identity Provider | Development headers only | Required for production | ADR-005 |
| KMS/Managed secrets | Not implemented | Required for production | ADR-005 |
| Human review service | Escalation flag only | Required for production | ADR-005, Blueprint 2.2 |
| Durable workers | Not implemented | Required for production | ADR-005 |

---

## Environment Boundaries

### Trust Boundaries (Per Blueprint Section 1.4)

| Boundary | Definition | Evidence |
|---|---|---|
| Foundation vs Production | Foundation validates contracts; Production requires full certification | ADR-005 |
| Safe vs Unsafe content | Five-outcome labeling distinguishes | Blueprint section 1.1 |
| Evidence immutability | Content-addressed in foundation; Versioned in production | ADR-003 |
| Model release authority | Foundation cannot gate; Production requires approval | ADR-005 |

---

## Capability Probes Status

**Note:** Per TODO requirements, these capability checks are documented as platform decisions rather than executed probes.

| Probe | Status | Evidence |
|---|---|---|
| PostgreSQL RLS enforcement | Pending production deployment | ADR-002 targets, ADR-005 gap |
| Immutable evidence store | Pending deployment | ADR-003, ADR-005 gap |
| OIDC authentication | Pending deployment | ADR-005 gap |
| Workload identity validation | Pending deployment | No infra/ops present in foundation |
| Audit logging (external) | Pending deployment | ADR-005 gap |

---

## Discrepancies

| Discrepancy | Claimed | Observed | Evidence |
|---|---|---|---|
| Production certification | Prohibited from foundation | Foundation cannot certify | ADR-005 |
| Provider adapters | Required for production | Only mock provider implemented | `pyproject.toml`, ADR-005 |
| Human review | Required for production | Escalation flag only | ADR-005, Blueprint 2.2 |

---

## Recommendations

1. **Document capability gaps**: Per ADR-005, many production services are intentionally absent from foundation
2. **Create operational playbook**: Define deployment, monitoring, and incident response procedures
3. **Establish production roadmap**: Track foundation→production migration items from ADR-005 gaps
4. **Add infrastructure automation**: Create `ops/` directory with deployment manifests when production path is authorized