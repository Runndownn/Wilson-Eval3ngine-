# ADR-001: Hybrid Modular Monolith

**Status:** Accepted for foundation  
**Decision:** Keep one versioned domain codebase. Deploy API, scheduler, executors, graders, and maintenance separately only where trust or scaling requires it.

## Context

WE3 needs strict domain consistency across expectations, run identity, grading, metrics, and release gates. A script harness lacks governance; microservices introduce distributed consistency and contract drift before workload evidence exists.

## Consequences

- Shared types and migrations are straightforward.
- Production processes can have distinct credentials and network policy.
- Independent scaling is coarser until a measured split trigger occurs.
- A module may split only for distinct credentials, sustained scaling, failure isolation, residency, ownership, runtime, or release cadence.
