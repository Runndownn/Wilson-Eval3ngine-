# Wilson Eval3ngine SEV Incident Runbook

## Overview

This runbook (TODO 53 - T8.1.3) provides safe, evidence-preserving operational actions for common and severe failures in the Wilson Eval3ngine platform.

## SEV Taxonomy

| SEV Level | Description | Response Time | Approval Required |
|-----------|-------------|---------------|-------------------|
| SEV-1 Critical | Unsafe compliance detected, evidence loss, security breach | 15 minutes | Platform Lead + SRE Lead + Exec |
| SEV-2 High | Provider outage, queue collapse, audit gap | 1 hour | Platform Lead + SRE Lead |
| SEV-3 Medium | Grading drift, model identity drift, performance degradation | 4 hours | Platform Lead |
| SEV-4 Low | Non-critical review backlog, minor alerts | 24 hours | Team Lead |

## Incident Roles

| Role | Responsibilities |
|------|------------------|
| **Incident Commander** | Coordinates response, makes authorization decisions, owns timeline |
| **Communications Lead** | Internal/external comms, status page updates, stakeholder notifications |
| **Evidence Lead** | Preserves forensic evidence, captures hashes, maintains chain of custody |
| **Operations Lead** | Executes remediation, implements mitigations, validates recovery |
| **Customer Lead** | Interfaces with affected users/customers, documents impact |

## Detection Signals

### Provider Outage
- **Signal**: `we3_provider_errors_total` spike, `we3_provider_latency_ms` > 30s for 5m+
- **Detection**: API availability SLI dropping below 99.9%
- **Evidence Lead Action**: Capture provider error counts and timestamps before remediation

### Queue Backlog
- **Signal**: `we3_queue_pending_count` > 1000 for 30m+
- **Detection**: Queue start latency P95 > 5 minutes
- **Evidence Lead Action**: Snapshot pending jobs and their ages

### Evidence Loss/ Corruption
- **Signal**: `we3_sli_evidence_durability_v1` < 99.99% or `we3_audit_chain_valid` = 0
- **Detection**: Hash verification failures, missing artifacts
- **Evidence Lead Action**: Immediately stop writes, capture all evidence hashes, verify backup integrity

### Model Identity Drift
- **Signal**: `we3_model_identity_drift_events` > 0
- **Detection**: Provider-reported model differs from expected
- **Evidence Lead Action**: Capture all responses with identity drift, tag affected runs

### Metric Discrepancy
- **Signal**: `we3_metric_drift_detected` > 0
- **Detection**: Statistical drift in safety metrics between baseline and candidate
- **Evidence Lead Action**: Capture baseline and candidate snapshots for analysis

### Grader Drift
- **Signal**: Unexpected classification outcomes, gate decisions changed
- **Detection**: Review task disagreements increased
- **Evidence Lead Action**: Capture classification payloads, verify grader version

### Artifact Exposure
- **Signal**: Unauthorized access attempts to evidence store
- **Detection**: Security audit logs, access denied events
- **Evidence Lead Action**: Preserve access logs, rotate credentials after incident

### Credential Leak
- **Signal**: Secret detected in telemetry or logs
- **Detection**: Redaction canary triggered
- **Evidence Lead Action**: Rotate credentials immediately, audit all recent operations

### Dataset Poisoning
- **Signal**: New unsafe compliance patterns, statistical anomalies
- **Detection**: Metric drift, classification anomalies
- **Evidence Lead Action**: Quarantine affected dataset versions, review contamination sources

### Database/Object/Audit Failure
- **Signal**: `we3_sli_evidence_durability_v1` dropping, write failures
- **Detection**: Database connection errors, transaction rollbacks
- **Evidence Lead Action**: Verify backup availability, check replication lag

### Wrong Gate Result
- **Signal**: Unexpected gate status, manual override mismatch
- **Detection**: Gate decision doesn't match metrics
- **Evidence Lead Action**: Review threshold set, verify calculation

### Report Generation Failure
- **Signal**: `we3_sli_report_generation_p99_v1` > 600s (10 minutes) for 5m+
- **Detection**: Database query timeouts, lock contention
- **Evidence Lead Action**: Capture slow query plans, check for stuck transactions

### Review Backlog Alert
- **Signal**: `we3_unresolved_critical_reviews` > 50 for extended period
- **Detection**: Review queue growing faster than human processing
- **Evidence Lead Action**: Snapshot review queue, verify reviewer availability

## Immediate Safe Actions

### For All Incidents (First 15 Minutes)
1. **STOP** - Do not proceed with any destructive actions
2. **PRESERVE** - Capture evidence snapshots and hashes
3. **DECLARE** - Create incident marker with timestamp and commander
4. **NOTIFY** - Alert appropriate SEV level responders

### Provider Outage Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - Do NOT cancel running experiments
  - Let jobs timeout naturally to preserve state
  - Switch to mock provider for critical path ONLY
  - Document outage window for evidence reconciliation
PROHIBITED_ACTIONS:
  - Retry storms (exponential backoff enforced)
  - Manual job requeues without evidence logs
  - Skipping hash verification for recovery
```

### Queue Backlog Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - Scale workers up to max_concurrent_workers limit
  - Check for stuck leases (stale_lease detection)
  - Monitor but do not manually clear queue
PROHIBITED_ACTIONS:
  - Manual DELETE from jobs table
  - Bulk UPDATE without transactional boundaries
  - Clearing queue without evidence of stuck jobs
```

### Evidence Corruption Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - HALT all write operations immediately
  - Verify backup integrity with hash comparison
  - Tag all affected artifacts as quarantined
PROHIBITED_ACTIONS:
  - Any DELETE operations until root cause confirmed
  - Proceeding with releases during evidence loss
  - Manual cleanup without audit trail
```

### Grading Drift Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - Pause grader workers
  - Capture current grader version and checkpoint
  - Snapshot classification discrepancy metrics
PROHIBITED_ACTIONS:
  - Switching grader versions without approval
  - Forcing classification decisions
  - Clearing review queue without analysis
```

### Report Generation Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - Check database connection pool saturation
  - Identify slow-running queries
  - Scale report workers if available
PROHIBITED_ACTIONS:
  - Killing long-running report processes
  - Skipping report validation
  - Manual metric injection
```

### Review Backlog Response
```yaml
IMMEDIATE_SAFE_ACTIONS:
  - Alert reviewer pool
  - Prioritize critical reviews
  - Consider temporary admission pause
PROHIBITED_ACTIONS:
  - Auto-approving critical reviews
  - Deleting review tasks
  - Bypassing human review
```

## Recovery Procedures

### Database Recovery
```bash
# Verify restore point
python3 -c "
from wilson_eval3ngine.persistence.database import Database
db = Database('$DATABASE_URL')
# Check latest audit event hash
# Verify evidence store integrity
"

# Perform point-in-time recovery (authorized only)
pg_restore --verbose \
  --clean \
  --if-exists \
  --dbname=$DATABASE_URL \
  --timestamp="$RECOVERY_POINT"
```

### Evidence Reconciliation
```bash
# Reconcile telemetry with database state
python3 -c "
from wilson_eval3ngine.observability.sli_slo import StateReconciler
reconciler = StateReconciler('$DATABASE_URL')
result = reconciler.check_lost_jobs('$PROJECT_ID', start_time, end_time)
print(f'Lost jobs: {result.potential_lost_jobs}')
"
```

### Audit Continuity Check
```bash
# Verify audit chain integrity
python3 -c "
from wilson_eval3ngine.persistence.audit import AuditLedger
ledger = AuditLedger(database)
valid = ledger.verify('$PROJECT_ID')
print(f'Audit chain valid: {valid}')
"
```

## Graceful Degradation Rules

### Admission Controls
- **PAUSE** experiment admission when:
  - Evidence integrity uncertain (`we3_sli_evidence_durability_v1` < 99%)
  - Critical review backlog > 50 items
  - Hash verification failing for 1 hour+

### Read-Only Mode
- **ALLOW** read-only verified reports when:
  - Database available but writes failing
  - Evidence store integrity verified
  - All reads tagged as "read_only_mode"

### Certification Restrictions
- **NEVER** certify with:
  - Missing evidence (`response_artifact_hash` NULL for completed runs)
  - Unresolved critical reviews
  - Model identity drift detected
  - Failed audit continuity

## Re-Certification Requirements

After any SEV-1 or SEV-2 incident:

1. **Evidence Review** - All affected runs re-verified
2. **Metric Re-compute** - Fresh metric snapshot required
3. **Gate Re-evaluation** - Threshold set re-applied
4. **Human Approval** - Platform lead sign-off on recovery
5. **Documentation** - Incident report with evidence references

## Maintenance Window Handling

### Scheduled Maintenance
- Register maintenance window before work:
```bash
we3 maintenance start \
  --project $PROJECT_ID \
  --duration-hours 2 \
  --reason "scheduled maintenance"
```

### Unscheduled Maintenance
- Automatically triggered on SEV-1/SEV-2
- All non-critical jobs paused
- Evidence preservation priority
- Manual approval required to resume

## Communication Templates

### Internal Status Update
```
SEV-{level} ${project_id}: ${timestamp}
Status: ${identifying/mitigating/resolving}
Impact: ${description}
Current Action: ${action}
Next Update: ${time}
```

### Customer Communication
```
We are experiencing ${issue} affecting ${impact}.
No evidence has been lost. Our systems are designed to preserve data integrity.
We are actively working on resolution. ETA: ${eta}
```

## Rollback Procedures

### Code Rollback (with Evidence Preservation)
```bash
# Never rollback without evidence preservation
python3 -c "
from wilson_eval3ngine.lifecycle.workflows import RollbackWorkflow
wf = RollbackWorkflow()
tombstones = wf.rollback_to('$PREVIOUS_VERSION')
print(f'Preserved {len(tombstones)} evidence records')
"
```

### Configuration Rollback
- Use versioned threshold sets (never modify in place)
- Apply previous threshold via override workflow
- Document reason in runbook evidence

---

## Appendix: Evidence Preservation Checklist

Before ANY cleanup or recovery action:
- [ ] Capture SHA-256 hashes of all affected artifacts
- [ ] Snapshot database state before modification
- [ ] Record audit events for all state changes
- [ ] Verify backup availability and integrity
- [ ] Get written approval for destructive actions
- [ ] Tag evidence as "incident_${timestamp}" for recovery reference