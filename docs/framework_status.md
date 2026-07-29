# Framework Status Matrix

| Capability | Foundation 0.1.0 | Production requirement |
|---|---|---|
| Contract validation | Implemented | Compatibility governance |
| Mock provider | Implemented | Retained for tests |
| Real providers | Not implemented | Two approved adapters |
| Immutable evidence | Encrypted object store with AES-256-GCM, KMS envelope encryption, retention policies | External encrypted/versioned store |
| Five labels | Deterministic implementation | Calibrated layered grading |
| Human review | Escalation flag only | Review/adjudication service with blind dual review, adjudication, self-adjudication prevention, critical task blocking |
| Metrics/Wilson intervals | Implemented | Cluster bootstrap and independent reference |
| Gates | Implemented, provisional thresholds | Approved severity/category thresholds |
| Dossier signing | Development Ed25519 key | Managed signing identity with Ed25519, trust registry, key inventory, audit checkpoints |
| Audit | Local hash chain | External checkpoints with signed audit checkpoints, trust registry validation |
| Auth | OIDC with MFA validation, JWKS caching, workload identity | Production OIDC with managed IdP |
| Project isolation | PostgreSQL RLS with 14-table policy coverage, session variable context, negative permission matrix | API/RLS/object policy negative matrix |
| Queue | PostgreSQL lease contract | Scheduler/worker/reconciliation implementation |
| Observability | Minimal | SLO dashboards, alerts, runbooks |
| DR | Not implemented | Backup/restore with PITR, object recovery, quarterly exercise |
| Production certification | Prohibited | Full certification suite (20 tests) |
