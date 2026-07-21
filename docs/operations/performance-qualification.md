# Performance Qualification Runbook

## Overview

This runbook (TODO 54 - T8.1.4) documents how to execute performance, load, and soak qualification tests.

## Prerequisites

- Isolated test environment (NOT production)
- PostgreSQL database available
- Mock provider configured (no live provider calls)
- At least 30% headroom requirement validation

## Workload Profiles

| Profile | Description | Runs/Hour | Latency | Expected Outcome |
|---------|-------------|-----------|---------|------------------|
| common | Normal steady-state | 100 | 2.0s | Within SLOs |
| burst | Flash burst | 1000 | 1.0s | Headroom validated |
| slow_provider | Degraded provider | 100 | 6.0s | Graceful degradation |
| large_payload | Oversized artifacts | 100 | 4.0s | Resource limits enforced |
| report_heavy | Many reports | 100 | 2.0s | Concurrent limit respected |
| review_backlog | Review saturation | 100 | 2.0s | Queue behavior validated |
| overload | Beyond capacity | 1000+ | 2.0s | Backpressure triggered |

## Running Qualification Tests

```bash
# Run all qualification profiles
python3 -c "
from wilson_eval3ngine.performance.load_testing import run_qualification_suite
results = run_qualification_suite(
    database_url='postgresql://test:test@localhost/test_db',
    artifact_root='/tmp/test-artifacts'
)
for profile, metrics in results.items():
    print(f'{profile}: {metrics.total_runs} runs, p95={metrics.p95_latency_ms}ms')
"

# Run specific profile
python3 -c "
from wilson_eval3ngine.performance.load_testing import (
    PerformanceQualifier, LoadScenario, LoadProfile
)
qualifier = PerformanceQualifier(
    database_url='sqlite:///:memory:',  # For unit testing
    artifact_root='/tmp/artifacts',
    scenario=LoadScenario(
        profile=LoadProfile.COMMON,
        runs_per_hour=1000,
        concurrent_workers=10,
        payload_size_bytes=5000,
        provider_latency_seconds=0.1,
        duration_seconds=60,
    ),
)
metrics = qualifier.run_load_test()
print(f'Completed: {metrics.total_runs} runs')
print(f'Headroom met: {qualifier._check_headroom(metrics, None)}')
"
```

## Soak Testing

Soak tests run for extended periods (typically 24-72 hours) to validate:
- Memory stability (no leaks)
- Connection pool behavior
- Queue stability under sustained load
- Evidence persistence integrity

```bash
# Run 24-hour soak test (production)
# WARNING: Do not run in development without resources
python3 -c "
import asyncio
from wilson_eval3ngine.performance.load_testing import run_soak_test

# Run for 24 hours
result = run_soak_test(
    database_url='postgresql://test:test@localhost/test_db',
    artifact_root='/var/we3/artifacts',
    duration_hours=24,
)

print(f'Soak test completed: {result[\"duration_hours\"]} hours')
print(f'Stability check: {result[\"stability_check\"]}')
"
```

## Overload and Recovery Testing

```bash
# Test system behavior under overload
python3 -c "
from wilson_eval3ngine.performance.load_testing import run_overload_recovery

result = run_overload_recovery(
    database_url='sqlite:///:memory:',
    artifact_root='/tmp/artifacts',
)
print(f'Overload phase: {result[\"overload_phase\"]}')
print(f'Recovery needed: {result[\"recovery_needed\"]}')
print(f'Recovery actions: {result[\"recovery_actions\"]}')
"
```

## Headroom Validation

The system must demonstrate 30% headroom at declared load:

```python
def validate_headroom(metrics, expected_load):
    """Verify at least 30% headroom above expected load."""
    actual_throughput = metrics.total_runs / max(1, metrics.test_duration_seconds)
    expected_throughput = expected_load.runs_per_hour / 3600.0

    ratio = actual_throughput / expected_throughput
    assert ratio >= 1.3, f"Headroom {ratio*100:.1f}% below 130% requirement"
    return True
```

## Metrics Validation

### Required Metrics (from TODO 52)

| SLI | Target | Warning | Window |
|-----|--------|---------|--------|
| API Availability | 99.9% | 99.95% | 5 min |
| Evidence Durability | 99.99% | 99.995% | 60 min |
| Queue Start P95 | ≤5 min | ≤3 min | 60 min |
| Grading Duration P95 | ≤2 min | ≤1 min | 30 min |
| Report Generation P99 | ≤10 min | ≤5 min | 60 min |
| Hash Verification | 100% | 100% | 24 hours |

### Checking Metrics

```bash
# Check all SLI values
for sli in api_availability evidence_durability queue_start_latency grading_duration report_generation hash_verification; do
    echo "Checking ${sli}:"
    curl -s "http://prometheus:9090/api/v1/query?query=we3_sli_${sli}_v1" | jq '.data.result[]?.value[1]' || echo "No data"
done
```

## Cost and Budget Monitoring

```bash
# Check spend during test
curl -s 'http://prometheus:9090/api/v1/query?query=we3_provider_spend_usd' | jq '.data.result[]?.value[1]'

# Verify budget not exceeded
python3 -c "
from wilson_eval3ngine.observability.error_budget import ErrorBudgetPolicy
policy = ErrorBudgetPolicy()
# Add budget checks here
"
```

## Post-Test Verification

```bash
# Verify no data loss
python3 -c "
from wilson_eval3ngine.persistence.scheduler import DurableScheduler
from wilson_eval3ngine.persistence.database import Database

db = Database('postgresql://...')
sched = DurableScheduler(db)
report = sched.reconcile()

assert report.lost_logical_runs == 0, 'Lost runs detected!'
assert report.duplicate_logical_keys == 0, 'Duplicate keys detected!'
print('No data loss detected')
"
```

## Production Considerations

- Tests MUST run in isolated environment
- Live provider spend must be capped
- Large payloads must not trigger real tool execution
- Evidence should use ephemeral storage
- All actions logged for audit trail

## Acceptance Criteria

- [ ] All SLOs pass at declared load with 30% headroom
- [ ] No lost or duplicate logical runs
- [ ] Memory stable over test duration
- [ ] Queue drains cleanly after load stops
- [ ] Evidence integrity verified