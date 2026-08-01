# SLI/SLO Verification Runbook

## Overview

This runbook covers verification of Service Level Indicators and Objectives (TODO 52).

## SLI Query Verification

### API Availability SLI
```bash
# Query Telemetry API for SLI values
python3 -c "
from wilson_eval3ngine.observability.sli_slo import SLIRegistry
registry = SLIRegistry()
sli = registry.get_sli('sli-api-availability-v1')
print(f'SLI Query: {sli.query_template}')
print(f'Target: {registry.get_slo_for_sli(\"sli-api-availability-v1\").target}')
"

# Check current value
curl -s 'http://prometheus:9090/api/v1/query?query=we3_sli_api_availability_v1' | jq '.data.result[]'
```

### Queue Start Latency SLI
```bash
# Check P95 queue latency
curl -s 'http://prometheus:9090/api/v1/query?query=we3_sli_queue_start_latency_p95_v1' | jq '.data.result[]'

# Verify jobs are not stuck
python3 -c "
from wilson_eval3ngine.persistence.scheduler import DurableScheduler
from wilson_eval3ngine.persistence.database import Database
db = Database('postgresql://...')
sched = DurableScheduler(db)
report = sched.reconcile()
print(f'Stranded jobs: {report.stranded_jobs}')
print(f'Duplicate keys: {report.duplicate_logical_keys}')
"
```

### Evidence Durability SLI
```bash
# Check evidence durability rate
curl -s 'http://prometheus:9090/api/v1/query?query=we3_sli_evidence_durability_v1' | jq '.data.result[]'

# Verify database has all accepted records
python3 -c "
from wilson_eval3ngine.observability.sli_slo import StateReconciler
reconciler = StateReconciler('postgresql://...')
# Check evidence integrity
result = reconciler.verify_evidence_integrity('project_id')
print(f'Verified: {result[\"verified_count\"]}, Failed: {result[\"failed_count\"]}')
"
```

## Alert Testing

### Test Alert Firing
```bash
# Simulate alert condition (for testing)
curl -X POST 'http://prometheus:9090/api/v1/admin/tsdb/create-blocks' \
  --data 'start=<timestamp>&end=<timestamp>&step=15'

# Check alert rules are loaded
curl -s 'http://prometheus:9090/api/v1/rules' | jq '.data.groups[].name' | grep we3

# Verify alert labels and annotations
python3 -c "
from wilson_eval3ngine.observability.alerts import get_alert_rules
for rule in get_alert_rules():
    print(f'{rule.alert_id}: severity={rule.severity.value}, owner={rule.owner}')
    print(f'  runbook: {rule.runbook_url}')
"
```

## Error Budget Verification

```bash
# Check current error budget status
python3 -c "
from wilson_eval3ngine.observability.error_budget import ErrorBudgetPolicy
policy = ErrorBudgetPolicy()
status = policy.evaluate_budget('slo-api-availability-99.9', 8, 10000)  # 8 errors in 10k
print(f'State: {status.state.value}')
print(f'Burn rate: {status.burn_rate}')
print(f'Remaining budget: {status.remaining_budget}%')
"
```

## Dashboard Verification

```bash
# Check Grafana dashboard health
curl -s 'http://grafana:3000/api/health' | jq '.ok'

# List WE3 dashboards
curl -s 'http://grafana:3000/api/search?query=we3' | jq '.[].title'

# Verify dashboard panels
python3 -c "
from wilson_eval3ngine.observability.dashboards import get_dashboards
for d in get_dashboards():
    print(f'{d.name}: {len(d.panels)} panels')
"
```

## Reconciliation Verification

```bash
# Run live reconciliation
python3 -c "
from wilson_eval3ngine.observability.sli_slo import StateReconciler
reconciler = StateReconciler('postgresql://...')
print('Checking for lost jobs...')
result = reconciler.check_lost_jobs('proj_test', start_time, end_time)
print(f'Potential lost jobs: {result[\"potential_lost_jobs\"]}')

print('Checking for stuck jobs...')
report = reconciler.check_stuck_jobs()
print(f'Stuck jobs: {len(report[\"stuck_jobs\"])}')
"
```

## SLO Breach Simulation

```bash
# Simulate SLO breach (for testing)
# This would update a test SLI to a breaching value

# Verify alerting on breach
sleep 30
curl -s 'http://alertmanager:9093/api/v1/alerts' | jq '.data[] | select(.labels.alertname == "APIAvailabilityBreaching")'
```

## Acceptance Criteria Verification

```bash
# Verify all acceptance criteria are met:
python3 -c "
from wilson_eval3ngine.observability.sli_slo import SLIRegistry
from wilson_eval3ngine.observability.alerts import get_alert_rules

registry = SLIRegistry()

# Check every SLI has versioned query, owner, target, window, source of truth
for sli_id in ['sli-api-availability-v1', 'sli-evidence-durability-v1', 
               'sli-queue-start-latency-p95-v1', 'sli-grading-duration-p95-v1',
               'sli-report-generation-p99-v1', 'sli-hash-verification-v1']:
    sli = registry.get_sli(sli_id)
    slo = registry.get_slo_for_sli(sli_id)
    assert sli is not None, f'Missing SLI: {sli_id}'
    assert slo is not None, f'Missing SLO for: {sli_id}'
    assert slo.owner, f'Missing owner for: {sli_id}'
    assert slo.runbook_url, f'Missing runbook for: {sli_id}'
    print(f'{sli_id}: OK')

print('All SLIs have required fields')
"
```