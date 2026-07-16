# Wilson Eval3ngine Test Report

**Generated:** 2026-07-16  
**Framework Version:** 0.1.0  
**Python Version:** 3.13.12  
**Test Session:** 90.21 seconds

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Tests | 618 passed, 5 skipped |
| Coverage | 81.88% (exceeds 80% threshold) |
| Gate Engine Branches | 100% coverage |
| Critical Components | All passing |

---

## Test Distribution by Category

| Category | Tests | Status |
|----------|-------|--------|
| Unit | ~450 | PASSED |
| Integration | ~70 | PASSED |
| Resilience | ~30 | PASSED |
| Architecture | ~15 | PASSED |
| Governance/Compliance | ~50 | PASSED |

---

## Coverage Analysis

### High Coverage Modules (>90%)

| Module | Coverage | Notes |
|--------|----------|-------|
| grading/calibration.py | 96% | Calibration harness complete |
| grading/judge_runner.py | 91% | Isolated judge runner |
| lifecycle/workflows.py | 93% | Lifecycle state machine |
| statistics/reference.py | 97% | Statistical reference implementation |
| statistics/intervals.py | 90% | Wilson score intervals |
| grading/hardened.py | 86% | Hardened deterministic grader |
| cli.py | 90% | Command line interface |
| grading/pipeline.py | 93% | Grading pipeline orchestration |

### Medium Coverage Modules (70-90%)

| Module | Coverage | Notes |
|--------|----------|-------|
| api/main.py | 68% | API endpoints - requires integration testing |
| application/service.py | 80% | Core service layer |
| benchmark/lifecycle.py | 68% | Lifecycle benchmarks |
| benchmark/supply_chain.py | 90% | Supply chain validation |
| providers/mock.py | 85% | Mock provider scenarios |

### Lower Coverage Modules (<70%)

Modules with lower coverage represent future production components:
- azure_openai.py, anthropic.py - production provider adapters (TODOs)
- benchmarks.py, queue.py - performance testing infrastructure
- Persistence migrations - schema migration verification
- Security context - production-specific controls

These are NOT blockers for foundation stability.

---

## Test Categories Verified

### Deterministic Grading Tests
All 5-outcome classification scenarios verified with golden fixtures:
- tests/unit/test_deterministic_grading_golden.py
- tests/unit/test_grading.py
- tests/unit/test_gate_engine_branches.py

### Integration Tests
Full API, CLI, and provider integration verified:
- tests/integration/test_api.py
- tests/integration/test_audit.py
- tests/integration/test_cli.py
- tests/integration/test_provider_integration.py
- tests/integration/test_scheduler_integration.py
- tests/integration/test_statistics_integration.py

### Resilience Tests
Concurrent lease claims, failure injection, and recovery verified:
- tests/resilience/test_execution_resilience.py

### Compliance Tests
Governance compliance and population validation verified:
- tests/governance/compliance/test_compliance_edge_cases.py
- tests/governance/compliance/test_compliance_load_security.py
- tests/governance/compliance/test_outcome_taxonomy.py
- tests/governance/compliance/test_population_validation.py
- tests/governance/compliance/test_schema_registry.py
- tests/governance/compliance/test_tranche_b_supply_chain.py

---

## Experiment Execution Verification

### Foundation Experiment
Command: we3 run examples/experiments/foundation.yaml

Result: STABLE - Returns indeterminate due to insufficient prompt-family support (expected for foundation)

### Critical Failure Experiment
Command: we3 run examples/experiments/critical_failure.yaml

Result: STABLE - Correctly blocks on unsafe compliance events

---

## CLI Verification

| Command | Status |
|---------|--------|
| we3 validate | WORKING - validates experiment manifests |
| we3 run | WORKING - executes experiments |
| we3 verify-dossier | WORKING - verifies Ed25519 signatures |
| we3 serve | WORKING - API server starts |
| we3 export-schemas | WORKING - exports JSON schemas |

---

## Artifacts Generated

Experiment output directory structure:
- .dev-ed25519-signing-key.pem (development key)
- experiment_result.json (detailed results)
- release_dossier.json (signed dossier)
- report.safe.html (inert HTML summary)

---

## Known Issues (Non-blocking)

1. Resource warnings - Unclosed SQLite connections in some test scenarios
2. Deprecation warnings - SQLite datetime adapter deprecated in Python 3.12
3. Coverage gaps - Production modules not yet exercised (expected)

---

## Production Readiness Assessment

| Requirement | Status | Notes |
|-------------|--------|-------|
| Contracts Implemented | COMPLETE | All 11 schemas in place |
| Deterministic Grading | COMPLETE | Five-outcome classifier complete |
| Evidence Immutability | COMPLETE | SHA-256 content addressing verified |
| Wilson Intervals | COMPLETE | Statistical computations verified |
| Release Gate Logic | COMPLETE | Blocks on unsafe, returns indeterminate |
| CLI/API Interface | COMPLETE | All commands functional |
| Ed25519 Signatures | COMPLETE | Dossier signing verified |
| Test Coverage | COMPLETE | 81.88% exceeds 80% threshold |

Assesssment: Foundation is stable and runnable for development and internal testing. Production blockers (OIDC, RLS, encrypted storage, real providers) are explicitly separated.