# Production Certification Runbook

## Overview

This runbook covers T8.1.8 (TODO 58) - Production Certification Orchestration for Wilson Eval3ngine. Certification validates that all ten mandatory categories are satisfied before release publication.

## Certification Categories

| Category | Requirement | Evidence Source |
|----------|-------------|-----------------|
| Reproducibility | Frozen artifacts reproduce metrics exactly | Test execution logs, SHA-256 hashes |
| Durability | ≥99.99% experiment definitions recoverable | Backup verification reports |
| Integrity | All score-affecting artifacts content-addressed | SHA-256 hash verification |
| Security | OIDC authentication with MFA | Auth configuration, policy docs |
| Statistics | Wilson score intervals computed correctly | Statistical validation reports |
| Grading | Deterministic five-outcome with calibrated thresholds | Grader calibration reports |
| Governance | Dual approval with audit trail | Approval records, audit logs |
| Recovery | Quarterly restore demonstrates RPO=15min, RTO=4hr | DR exercise reports |
| Operations | 6 core SLIs with SLO bindings | SLI/SLO dashboards, alert rules |
| Usability | WCAG 2.2 AA compliance | Accessibility audit reports |

## Certification Workflow

### Prerequisites
- Release artifact digest
- Source commit hash
- Environment (staging/production)
- Requirement catalog hash
- Approvers list

### Execute Certification

```bash
# Run certification evaluation
we3 certify \
  --artifact-digest sha256:$ARTIFACT_HASH \
  --source-commit $COMMIT_HASH \
  --environment production \
  --requirement-hash sha256:$REQUIREMENT_HASH \
  --approvers alice,bob
```

### Verify Certification

```bash
# Verify signed certification manifest
we3 verify-certification var/certification_result.json

# Check evidence freshness
python3 -c "
from wilson_eval3ngine.certification.certification_orchestrator import CertificationRegistry, EvidenceEntry, CertificationCategory
from datetime import datetime, timezone, timedelta

# Check if evidence is fresh (within 24h default)
registry = CertificationRegistry()
# Evidence entries are validated for freshness during certification
"
```

## Evidence Validation

### Freshness Requirements

Evidence must be:
- Generated within the last 24 hours (default) OR have explicit expiry
- Marked with SHA-256 content-addressed hash
- Applicable to the correct commit and environment

### Environment Drift Detection

Evidence is validated for:
- **Environment match**: Evidence from staging cannot satisfy production requirements
- **Commit alignment**: Evidence must match the source commit being certified
- **Freshness window**: Evidence must be within 24 hours (or explicit expiry)

When drift is detected:
```
drift: {evidence_id}: evidence from {source_env} not {target_env}
```
This creates INDETERMINATE status requiring manual review.

### Stale Evidence Detection

Evidence exceeding freshness window is flagged:
```
stale_evidence: {count} pieces exceed freshness window
```
This creates INDETERMINATE status - stale evidence cannot hide failures.

### Applicability Rules

- Evidence source hash must match expected value
- Evidence timestamp must align with source commit
- Environment attestation must match target environment
- Security findings must be from approved scanners

## Security Considerations

### Separation of Duties

1. **Evidence Producers** - Generate test/security/quality evidence
2. **Certification Orchestrator** - Evaluates evidence against requirements
3. **Independent Approvers** - Review and approve certification
4. **Signing Authority** - Cryptographically sign certification result
5. **Publication Authority** - Publish release based on certification

### Evidence Integrity

- All evidence verified through SHA-256 hashes
- Trust registry validates signing keys
- No self-attested evidence without cryptographic proof
- Evidence exclusions documented with justification

## Failure Modes

### Missing Evidence

When evidence is missing for a blocking requirement:
```
{category}: requirement not satisfied
```
The certification is BLOCKED. All blocking evidence must be provided.

### Stale Evidence

Evidence older than freshness window:
- Blocking requirements → certification BLOCKED
- Non-blocking requirements → certification WARNING

### Signature Verification Failure

Invalid or untrusted signatures:
- Certification INDETERMINATE
- Manual investigation required

## Re-Certification Triggers

Recertification required when:
- Source commit changes
- Requirement catalog updates
- Any approver certificate expires
- Security finding severity changes
- Previously resolved critical review reopens

## Integration Points

- **Trust Registry**: `src/wilson_eval3ngine/security/signing.py`
- **Observability**: `src/wilson_eval3ngine/observability/sli_slo.py`
- **Backup**: `src/wilson_eval3ngine/backup/`
- **Deployment**: `src/wilson_eval3ngine/deployment/`

## Operations Cadence Integration

### Daily Cadence
- Health/integrity checks
- Cost/ headroom threshold monitoring
- Error budget consumption review

### Weekly Cadence
- Backlog review
- Cost/capacity analysis
- Alert threshold review

### Monthly Cadence
- Access review
- Patch compliance check
- Backup verification
- Dependency review

### Quarterly Cadence
- Capacity planning
- Threat model review
- DR exercise (RPO=15min, RTO=4hr)
- Architecture review

## Threshold Definitions

| Threshold | Warning | Critical | Owner |
|-----------|---------|----------|-------|
| Capacity headroom | 20% | 10% | SRE Team |
| Critical patches overdue | 7 days | 30 days | Platform Team |
| Error budget remaining | 25% | 10% | SRE Team |
| Backup verification | 95% | 80% | SRE Team |
| Queue depth triggers | 5,000 | 10,000 | Platform Team |

## Evidence Requirements

### Security Evidence (Blocking)
- OIDC configuration with MFA
- Security scan results
- Vulnerability assessment reports

### SLO Evidence (Blocking)
- Six core SLI definitions registered
- Alert rules with runbook links
- Recovery conditions documented

### Recovery Evidence (Blocking)
- Quarterly DR exercise reports
- RPO/RTO demonstration
- Backup integrity verification

## Runbook References

- [SEV Incidents](./sev-incidents.md)
- [Provider Outage Response](./sev-incidents.md#provider-outage-response)
- [Evidence Corruption Response](./sev-incidents.md#evidence-corruption-response)
- [Queue Backlog Response](./sev-incidents.md#queue-backlog-response)
- [Grading Drift Response](./sev-incidents.md#grading-drift-response)
- [Report Generation Response](./sev-incidents.md#report-generation-response)