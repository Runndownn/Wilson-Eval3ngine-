# ADR-005: Foundation Cannot Certify Production Models

**Status:** Accepted as a historical architectural constraint on the original deterministic foundation lane.  
**Original decision:** Version 0.1.0's first deterministic vertical slice could validate contracts and end-to-end behavior but could not, by itself, gate a production model release.

> **Current interpretation (2026-08-21):** several capabilities listed below as “missing evidence” were subsequently implemented in source, including real provider adapters, human review/adjudication, OIDC/project controls, encrypted evidence storage, durable scheduling, and certification orchestration. The enduring part of this ADR is the assurance rule—not the old implementation inventory: **a deterministic local lane or repository implementation cannot certify a production release without the required benchmark, calibration, approvals, and target-runtime evidence.** See [../STATUS.md](../STATUS.md) for current capability status.

## Missing evidence at the time of the original decision

- Approved benchmark population and sample support.
- Two real provider adapters and identity probes.
- Calibrated, isolated graders.
- Human review and adjudication operations.
- OIDC/RLS/object-policy enforcement.
- Production immutable object storage.
- Statistical reference validation and cluster comparisons.
- SLO, security, backup, and disaster-recovery evidence.

The list above is preserved as historical decision context and must not be used as the current feature matrix. Some items now have repository implementations, while others still depend on calibration, approval, external services, or executed private runtime evidence; [Current Status](../STATUS.md) is the present-tense reconciliation.

## Enduring decision

No local deterministic demonstration, source-only test result, or implemented control may be converted into a production-certification claim without satisfying the certification requirements and runtime-assurance evidence for the exact release and deployment. This remains true even as the platform grows beyond the original foundation lane.
