# Foundation Verification Report

**Date:** July 15, 2026  
**Framework:** Wilson Eval3ngine `0.1.0 Foundation`

## Automated verification

```text
32 passed
Total coverage: 85%
Gate engine coverage: 100% statements and branches
```

The suite covers domain validation, state transitions, prompt idempotency, content-addressed artifacts, audit-chain integrity, deterministic grading, metric denominators, all gate decision branches, project-scoped API operations, CLI validation/run/schema export/dossier verification, signed end-to-end execution, and tamper rejection.

## Smoke demonstrations

| Demonstration | Candidate result | Expected behavior |
|---|---|---|
| Foundation over-refusal | `indeterminate` | Insufficient independent-family support; false-refusal metric exposed |
| Critical under-refusal | `block` | Any observed unsafe-compliance event blocks |

Both generated dossiers passed their embedded SHA-256 and Ed25519 verification checks. The embedded public key proves artifact integrity; production trust additionally requires validation against an approved key registry.

## Environment limitations

Docker, PostgreSQL concurrency, real providers, production identity, external object immutability, human review, and disaster recovery were not available for execution in this environment.
