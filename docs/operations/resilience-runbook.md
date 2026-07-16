# Wilson Eval3ngine Execution Resilience Runbook

## Overview

This runbook documents the execution-resilience and hostile-concurrency testing
infrastructure implemented in TODO 28 (T4.1.8).

## Scenarios Covered

| Scenario | Description | Invariant Tested |
|----------|-------------|----------------|
| CONCURRENT_LEASE_CLAIMS | Multiple workers racing to claim same jobs | SKIP LOCKED prevents duplicate claims |
| STALE_LEASE | Worker attempts to use expired lease | Lease expiry prevents completion |
| TIMEOUT_HANDLING | Max attempts enforced limit | Bounded retry budgets |
| IDENTITY_DRIFT | Model identity changes detected | Model identity consistency |
| MALFORMED_PARTIAL_OUTPUT | Invalid/partial responses handled | Protocol validation |

## Evidence Package

Each test run produces a `ScenarioMatrix` with:
- `scenario_id`: Unique identifier
- `scenario_type`: Category of resilience test
- `seed`: Deterministic seed for reproducibility
- `workers_involved`: Concurrent workers count
- `duplicate_attempts_detected`: Count of prevented race conditions
- `stale_lease_violations`: Count of expired lease attempts
- `audit_events`: Timeline of recorded events
- `timeline`: Ordered event history for forensics

## How to Run

```bash
# Run all resilience tests
python3 -m pytest tests/resilience/ -v

# Run specific scenario class
python3 -m pytest tests/resilience/test_execution_resilience.py::TestConcurrentLeaseClaims -v

# Run with coverage
python3 -m pytest tests/resilience/ --cov=src/wilson_eval3ngine --cov-report=term-missing
```

## Validation Commands

```bash
# Verify test suite passes
python3 -m pytest tests/ --ignore=tests/governance -q

# Check for race condition regressions
python3 -m pytest tests/resilience/ -v --tb=short

# Validate evidence serialization
python3 -c "
from tests.resilience.test_execution_resilience import ScenarioMatrix, ScenarioType
import json

m = ScenarioMatrix(
    scenario_id='validation_test',
    scenario_type=ScenarioType.COMMON_RUN.value,
    description='Check serialization',
    seed=1,
)
print(json.dumps(m.to_dict()))
"
```

## Debugging Checklist

When investigating failures:

1. **Check scenario seed** - Reproducible with same seed
2. **Check timeline** - EvidenceRecorder captures event order
3. **Check lease version** - Fencing uses version comparisons
4. **Check state transitions** - ValidJobTransition validates changes
5. **Check retry counts** - RetryPolicy.is_retryable() bounds

## Related Files

- `tests/resilience/test_execution_resilience.py` - Test implementation
- `src/wilson_eval3ngine/persistence/scheduler.py` - DurableScheduler
- `src/wilson_eval3ngine/testing/failure_injection.py` - Fault infrastructure
- `src/wilson_eval3ngine/providers/mock.py` - Deterministic mock provider