# ADR-002: PostgreSQL State, Leasing Queue, and Outbox

**Status:** Accepted for initial production path  
**Decision:** Use PostgreSQL for transactional state, logical-run uniqueness, job leasing, and a transactional outbox.

## Rationale

Experiment creation, run expansion, idempotency, and event publication require atomicity. `FOR UPDATE SKIP LOCKED`, lease expiry, heartbeat, and reconciliation are sufficient for the assumed initial scale.

## Rejected

- Redis as durable source of truth.
- Kafka before multiple measured consumers and throughput need.
- A workflow engine before workflow complexity is demonstrated.

## Revisit

Reconsider after four consecutive weeks of queue SLO failure, workflow state complexity that cannot be safely modeled, or a requirement for multi-region execution.
