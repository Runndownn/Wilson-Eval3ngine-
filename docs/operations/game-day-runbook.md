# Wilson Eval3ngine Game Day Runbook

## Overview

This runbook (T8.1.11 / TODO 61) documents the cross-system game day exercise procedures for validating the complete socio-technical system's ability to detect, contain, recover, reconcile, and re-certify after realistic failures.

## Prerequisites

### Authorization Requirements

All game day exercises require **written authorization** before execution:

```yaml
authorization_required: true
approval_authority: "Platform Lead + SRE Lead"
authorization_format: "gd_auth_{environment}_{timestamp}_{requester}"
safety_observer_required: true
```

### Environment Setup

Game day exercises MUST use **isolated staging environment** with production-like topology:

- PostgreSQL instance with WAL archiving
- Object storage (S3-compatible) with versioning
- Outbox/audit stream configured
- Telemetry collection active
- Alert system with pages

### Safety Controls

- Fault allowlists restrict injection to approved targets
- Abort criteria automatically stop exercise on critical issues
- Rollback plans must be tested before exercise
- Independent safety observer present during all exercises

## Failure Matrix

The exhaustive failure matrix covers **14 fault categories** with **19 total scenarios**:

| Category | Scenarios | Description | Typical Metrics Target |
|----------|-----------|-------------|---------------------|
| Common Flow | gd_common_001 | Normal operation baseline | RTO: 0min, RPO: 0min |
| Rare Critical | gd_critical_001-002 | Database restart, object store outage | RTO: 4hr, RPO: 15min |
| Hostile Input | gd_hostile_001-002 | Prompt injection, XSS | Blocked before execution |
| Partial Failure | gd_partial_001-002 | Consumer outage, partial upload | Recovery < 30min |
| Concurrency | gd_concurrent_001-002 | Stale lease, duplicate claims | Violations: 0 |
| Replay | gd_replay_001 | Idempotency key replay | Replay prevented |
| Timeout/Retry | gd_timeout_001-002 | Provider timeout, retry storm | Bounds enforced |
| Network Partition | gd_network_001 | PostgreSQL/object store partition | Handled gracefully |
| Malformed Data | gd_malformed_001-002 | Bad records, invalid hashes | Schema validation |
| Large Payload | gd_large_001 | Memory pressure | Backpressure applied |
| Version Skew | gd_skew_001-002 | Old worker, grader incompatibility | Incompatible blocked |
| Dependency Outage | gd_deps_001-002 | IdP outage, provider fallback | Fallback activated |
| Operator Error | gd_operator_001-002 | Wrong action, unauthorized override | Authorization blocked |
| Security Compromise | gd_security_001-003 | Key compromise, audit tampering, egress | Evidence verified |

## How to Execute

### Basic Game Day

```bash
# Validate authorization
python3 -c "
from wilson_eval3ngine.testing.game_day import GameDayOrchestrator
orchestrator = GameDayOrchestrator()
assert orchestrator.validate_authorization('gd_auth_staging_$(date +%s)_operator')
orchestrator.assert_safety_observer(True)
"

# Run full failure matrix
we3 game-day run \
  --authorization "gd_auth_staging_$(date +%s)_operator" \
  --output var/game_day_result.json
```

### Single Scenario Execution

```bash
we3 game-day run-scenario \
  --scenario-id gd_partial_001 \
  --authorization "gd_auth_staging_$(date +%s)_operator"
```

### With Load Testing

```bash
# Run game day with simulated load
we3 game-day run \
  --authorization "gd_auth_staging_$(date +%s)_operator" \
  --with-load \
  --concurrent-users 10
```

## Verification Commands

```bash
# Verify game day result structure
python3 -c "
import json
with open('var/game_day_result.json') as f:
    result = json.load(f)
    
assert 'exercise_id' in result
assert 'scenarios_executed' in result
assert 'timeline' in result
assert 'metrics' in result
assert len(result['scenarios_executed']) >= 19  # All scenarios
"

# Verify metrics meet SLOs
python3 -c "
import json
with open('var/game_day_result.json') as f:
    result = json.load(f)
    
metrics = result['metrics']
assert metrics['rpo_minutes'] <= 15.0  # Target RPO
assert metrics['rto_hours'] <= 4.0  # Target RTO
assert metrics['data_integrity_verified'] is True
assert metrics['decision_correctness_score'] >= 0.9
"

# Verify no unexplained data loss
python3 -c "
import json
with open('var/game_day_result.json') as f:
    result = json.load(f)
    
# All findings should have evidence refs
for finding in result['findings']:
    if finding['severity'] in ('critical', 'high'):
        assert len(finding['evidence_refs']) > 0
"
```

## Debugging Checklist

When investigating game day failures:

1. **Check authorization** - Valid `gd_auth_` prefix required
2. **Check safety observer** - Must be present during execution
3. **Check abort criteria** - Look for triggered abort conditions
4. **Check timeline order** - Events should follow phase sequence
5. **Check evidence preservation** - All findings have evidence refs
6. **Check metrics targets** - RPO/RTO compliance verified
7. **Check fault targeting** - Injection within allowlist only

## Timeline Event Verification

```bash
# Reconstruct chronological timeline
python3 -c "
import json
from datetime import datetime

with open('var/game_day_result.json') as f:
    result = json.load(f)

timeline = sorted(result['timeline'], key=lambda e: e['timestamp'])
for event in timeline[:10]:
    print(f\"{event['timestamp']}: {event['phase']}/{event['event_type']}\")
"
```

## Integration Points

| System | Integration Module | Purpose |
|--------|------------------|---------|
| Backup/PITR | `src/wilson_eval3ngine/backup/` | Evidence recovery simulation |
| Certification | `src/wilson_eval3ngine/certification/` | Re-certification validation |
| Operations | `src/wilson_eval3ngine/operations/` | Cadence integration |
| Telemetry | `src/wilson_eval3ngine/telemetry.py` | Alert simulation |
| Signing | `src/wilson_eval3ngine/security/signing.py` | Key compromise simulation |
| Scheduler | `src/wilson_eval3ngine/persistence/scheduler.py` | Lease/stale job simulation |
| API | `src/wilson_eval3ngine/api/` | Endpoint failure simulation |

## Abort Criteria

The following conditions will automatically abort the game day:

- `data_loss_detected` - Evidence loss detected
- `integrity_violation` - Data integrity violation
- `backup_unavailable` - Recovery backup unavailable
- `evidence_unrecoverable` - Cannot recover evidence
- `system_compromised` - Security breach detected
- `data_leak_detected` - Unauthorized data exfiltration
- `schema_violation_unhandled` - Unhandled schema errors
- `integrity_violation_unhandled` - Unhandled integrity errors
- `incompatible_grader_running` - Wrong grader version active
- `auth_failure_unhandled` - Authentication failure
- `unauthorized_action_executed` - Unauthorized operation

## Evidence Requirements

### Evidence During Exercise

- **Before** fault injection: System state snapshot
- **During** fault: Alert events, state transitions
- **After** fault: Recovery actions, integrity checks
- **Post-recovery**: Reconciliation report, re-certification

### Evidence Preservation Rules

1. All timeline events are immutable records
2. Evidence refs use content-addressed SHA-256 hashes
3. Findings include evidence refs for verification
4. Timeline includes monotonic and wall-clock timestamps

## RPO/RTO Targets

| Scenario Type | RPO Target | RTO Target | Verification |
|---------------|------------|------------|--------------|
| Rare Critical | 15 minutes | 4 hours | Backup restore test |
| Common Flow | N/A | N/A | Baseline metrics |
| Hostile Input | N/A | < 1 min | Blocked before execution |
| Partial Failure | 5 minutes | 30 minutes | WAL archive check |
| Concurrency | N/A | < 1 min | Lease validation |
| Security Compromise | N/A | < 15 min | Key rotation test |

## Security Considerations

### Key Compromise Simulation

- Only simulates signature verification failure
- Does NOT expose real keys
- Verifies trust registry blocks untrusted signatures
- Tests re-certification blocking

### Audit Tampering Detection

- Simulates bad hash in chain
- Verifies audit validation rejects tampering
- Tests evidence preservation during audit gap

### Egress Violation Prevention

- Tests network egress controls
- Verifies flow isolation between services
- Confirms no data leakage paths

## Runbook References

- [SEV Incidents](./sev-incidents.md) - Incident response procedures
- [Backup/Recovery](./backup-recovery-runbook.md) - Recovery procedures
- [Performance Qualification](./performance-qualification.md) - Load testing
- [Certification Runbook](./certification-runbook.md) - Re-certification process