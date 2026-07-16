# Lifecycle Workflows and Failure Injection Operations

## Overview

This runbook covers the lifecycle management system (TODO 19) and failure injection testing infrastructure (TODO 20).

## Lifecycle Workflows

### Components

1. **RegradeWorkflow** - Creates new grade versions from immutable evidence
2. **BackfillWorkflow** - Resumable, bounded jobs for data migration
3. **RetentionWorkflow** - Legal hold precedence and tombstone creation
4. **RollbackWorkflow** - Evidence preservation during code rollbacks

### Running a Backfill Job

```bash
# Create backfill job (requires authorization ticket)
python3 -c "
from wilson_eval3ngine.lifecycle.workflows import BackfillWorkflow

wf = BackfillWorkflow()
job = wf.create_backfill_job(
    target_table='responses',
    target_schema_version='we3.response.v2',
    authorization_ticket='CHANGE-123'
)
print(f'Created job: {job.job_id}')
"
```

### Regrade Execution

```bash
# Trigger regrade of an experiment
python3 -c "
from wilson_eval3ngine.lifecycle.workflows import RegradeWorkflow

# Using mock evidence accessor
class MockAccessor:
    def get_response(self, h): return {'content': 'test'}
    def get_classification(self, id): return {'label': 'safe'}

wf = RegradeWorkflow(evidence_accessor=MockAccessor(), grader=None)
result = wf.regrade_run(
    run_id='run_abc',
    old_rubric_version='v1.0.0',
    new_rubric_version='v1.1.0',
    authorization_ticket='CHANGE-456'
)
print(f'Regraded: {result.classifications_regenerated} classifications')
"
```

### Retention Sweep

```bash
# Apply retention policy and create tombstones
python3 -c "
from wilson_eval3ngine.lifecycle.workflows import RetentionWorkflow, RetentionPolicySpec

wf = RetentionWorkflow()
wf.set_policy(RetentionPolicySpec(
    entity_type='response',
    retention_days=90,
    legal_hold=False
))

tombstone = wf.apply_retention_policy(
    entity_id='resp_001',
    entity_type='response',
    project_id='proj_test',
    classification='internal',
    retention_hash='abc123'
)
print(f'Tombstone: {tombstone.tombstone_id if tombstone else \"No deletion\"}')
"
```

## Failure Injection Testing

### Security Requirements

- Run ONLY in isolated authorized staging environments
- Use explicit target allowlists to prevent production impact
- Preserve all test evidence in immutable audit packages

### Running Deterministic Scenarios

```bash
# List available fault scenarios
python3 -c "
from wilson_eval3ngine.testing.failure_injection import (
    create_database_restart_scenario,
    create_network_partition_scenario,
    create_stale_lease_scenario,
    create_consumer_outage_scenario
)

scenarios = [
    create_database_restart_scenario(),
    create_network_partition_scenario(),
    create_stale_lease_scenario(),
    create_consumer_outage_scenario(),
]
for s in scenarios:
    print(f'{s.scenario_id}: {s.description}')
"
```

### Test Execution Flow

1. Capture before-snapshot of evidence state
2. Start fault controller with configured scenario
3. Execute operation under fault conditions
4. Stop fault controller
5. Capture after-snapshot
6. Compute reconciliation report
7. Verify no data loss or corruption

## PostgreSQL Migration

The lifecycle workflow tables require migration against the PostgreSQL instance at `10.133.7.170`:

```bash
# Apply migration (requires database access)
alembic -c src/wilson_eval3ngine/persistence/alembic.ini upgrade head
```

## Monitoring and Observability

All lifecycle operations emit structured logs with:
- Correlation IDs for traceability
- Event types: `regrade_run_started`, `backfill_job_created`, `backfill_batch_completed`, etc.
- State transitions with timestamps

## Troubleshooting

### Missing Historical Artifacts
Check object store for evidence hashes, verify retention policies weren't applied prematurely.

### Stale Job Leases
Backfill jobs left in running state may require manual checkpoint reset. Use `reconcile_job()` to check progress.

### Legal Hold Blocking Deletion
Verify retention hold state before attempting deletion operations.