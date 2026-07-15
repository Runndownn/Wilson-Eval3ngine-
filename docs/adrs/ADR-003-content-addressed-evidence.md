# ADR-003: Content-Addressed Evidence Store

**Status:** Accepted  
**Decision:** Store raw and derived evidence by SHA-256 in immutable object storage; keep query metadata and references in PostgreSQL.

## Invariants

- Evidence bytes are write-once.
- Every reference carries project, media type, size, classification, retention, and hash.
- A response must persist and verify before behavioral grading.
- Published reports identify every artifact and snapshot hash.
- Local filesystem storage is development-only.
