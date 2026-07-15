# ADR-001: Hybrid Modular Monolith Architecture

**Status:** Accepted  
**Decision:** Keep one versioned domain codebase. Deploy API, scheduler, executors, graders, and maintenance separately only where trust or scaling requires it.

## Context

WE3 needs strict domain consistency across expectations, run identity, grading, metrics, and release gates. A script harness lacks governance; microservices introduce distributed consistency and contract drift before workload evidence exists.

## Module Map

| Module ID | Name | Domain | Entry Points | Trust Zone |
|-----------|------|--------|--------------|------------|
| CONTRACT-001 | Contract | contract | api.main, api.contract_endpoints | Core |
| DATASET-002 | Dataset | dataset | api.main, dataset.lifecycle | Core |
| EXECUTION-003 | Execution | execution | execution.scheduler, providers.executor, execution.rendering | Core |
| GRADING-004 | Grading | grading | grading.pipeline, grading.classifier | Data |
| METRIC-005 | Metrics | metrics | metrics.engine, metrics.snapshot | Data |
| EVIDENCE-006 | Evidence | evidence | evidence.store | Storage |
| IDENTITY-007 | Identity | identity | security.signing, api.auth | Security |
| REPORT-008 | Reporting | reporting | reports.dossier, reports.matrix | Core |
| PROVIDER-009 | Provider | provider | providers.executor, providers.mock | Provider |
| SCHEDULER-010 | Scheduler | scheduler | scheduler.main | Core |
| MAINTENANCE-011 | Maintenance | maintenance | maintenance.migrate, maintenance.cleanup | Core |
| RELEASE-012 | Release | release | release.dossier | Core |

## Trust Zones

1. **Core Zone** - General application code with standard credentials
2. **Provider Credentials Zone** - Contains `provider-api-key`, `provider-signing-key`; egress-only network policy
3. **Security Signing Zone** - Contains `signing-key`, `kms-access`; isolated network policy
4. **Data Grading Zone** - GRADING-004, METRIC-005 modules; internal-only network policy
5. **Evidence Storage Zone** - EVIDENCE-006 module; internal-only network policy

## Dependency Rules

- Modules communicate through application interfaces or versioned events
- No direct table manipulation across domains
- Shared schemas live in a single contract registry
- Credential-bearing provider code remains in distinct trust zone

## Allowed Imports

Each module maintains an explicit import allowlist in `governance/compliance/modular_split_triggers.json`.

## Split Triggers (Objective Criteria)

A module may split only for:

| Trigger | Measurement Method | Threshold/Review |
|---------|-------------------|------------------|
| incompatible-credentials | architecture-review | Credentials cannot coexist in same trust boundary |
| sustained-independent-scaling | metric-threshold | >80% resources for >7 days |
| stronger-isolation-required | manual-review | Security boundaries require isolation |
| residency-required | architecture-review | Jurisdictional data residency laws |
| ownership-separation | manual-review | Organizational/team boundaries |
| different-runtime | architecture-review | Runtime version incompatibilities |
| independent-release-cadence | metric-threshold | Release frequency >7 days, >60% independent changes |
| failure-domain-split | architecture-review | Failure isolation requires circuit-breaking |

## Consequences

- Shared types and migrations are straightforward
- Production processes can have distinct credentials and network policy
- Independent scaling is coarser until a measured split trigger occurs
- Transaction boundaries clearly owned per domain
- Migration requires explicit ADR with rollback plan
- No service split for organizational preference alone