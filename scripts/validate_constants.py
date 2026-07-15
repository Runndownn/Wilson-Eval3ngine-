#!/usr/bin/env python3
"""
Validation script for Wilson Eval3ngine Timing Constants.
Location: scripts/validate_constants.py

Ensures timing and pattern constants remain first-class governance artifacts
aligned with the implementation blueprint and domain requirements.
"""

import sys
from wilson_eval3ngine.constants import (
    TimingProfile,
    RetryThresholds,
    PopulationThresholds,
    ConfidenceThresholds,
    StateTimeouts,
    RetentionDefaults,
    FailureMode,
    OperationState,
    VALIDATION_PATTERNS,
)


def validate_timing_constants() -> dict:
    """Validate timing constants against blueprint requirements."""
    results = {
        "valid": True,
        "errors": [],
        "checks": [],
    }

    # Check 1: Timing profile values are positive
    results["checks"].append("Timing profiles are positive")
    if TimingProfile.DEFAULT <= 0:
        results["errors"].append("DEFAULT timing must be positive")
        results["valid"] = False
    if TimingProfile.FAST <= 0:
        results["errors"].append("FAST timing must be positive")
        results["valid"] = False

    # Check 2: Retry thresholds are sensible
    results["checks"].append("Retry thresholds are bounded")
    if RetryThresholds.MAX_ATTEMPTS < 1 or RetryThresholds.MAX_ATTEMPTS > 10:
        results["errors"].append("MAX_ATTEMPTS out of reasonable range (1-10)")
        results["valid"] = False
    if RetryThresholds.TIMEOUT_BUFFER < 1.0:
        results["errors"].append("TIMEOUT_BUFFER must be >= 1.0")
        results["valid"] = False

    # Check 3: Population thresholds align with statistical requirements
    results["checks"].append("Population thresholds meet minimums")
    if PopulationThresholds.MIN_TOTAL_SAMPLES < 50:
        results["errors"].append("MIN_TOTAL_SAMPLES too low for Wilson interval stability")
        results["valid"] = False

    # Check 4: Confidence thresholds are valid probabilities
    results["checks"].append("Confidence thresholds are valid probabilities")
    for name, value in [
        ("WILSON_CONFIDENCE", ConfidenceThresholds.WILSON_CONFIDENCE),
        ("UNSAFE_CRITICAL", ConfidenceThresholds.UNSAFE_CRITICAL),
        ("UNSAFE_WARNING", ConfidenceThresholds.UNSAFE_WARNING),
    ]:
        if not 0 < value <= 1:
            results["errors"].append(f"{name} must be in (0, 1]")
            results["valid"] = False

    # Check 5: State timeouts are reasonable
    results["checks"].append("State timeouts are bounded")
    if StateTimeouts.LEASE_TIMEOUT < 30 or StateTimeouts.LEASE_TIMEOUT > 600:
        results["errors"].append("LEASE_TIMEOUT out of reasonable range (30-600)")
        results["valid"] = False

    # Check 6: Validation patterns exist
    results["checks"].append("Validation patterns are defined")
    required_patterns = [
        "population_reconciliation",
        "artifact_integrity",
        "gate_independence",
    ]
    for pattern in required_patterns:
        if pattern not in VALIDATION_PATTERNS:
            results["errors"].append(f"Missing validation pattern: {pattern}")
            results["valid"] = False

    # Check 7: Failure modes are defined
    results["checks"].append("Failure modes are enumerated")
    required_modes = [
        "PROVIDER_TIMEOUT",
        "AUTH_FAILURE",
        "STORAGE_FAILURE",
    ]
    for mode in required_modes:
        if not hasattr(FailureMode, mode):
            results["errors"].append(f"Missing failure mode: {mode}")
            results["valid"] = False

    return results


def main():
    print("Wilson Eval3ngine Constants Validation")
    print("=" * 40)

    results = validate_timing_constants()
    
    print(f"Valid: {results['valid']}")
    print(f"Checks performed: {len(results['checks'])}")
    
    for check in results["checks"]:
        print(f"  - {check}")

    if results["errors"]:
        print(f"Errors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  ERROR: {error}")
        sys.exit(1)
    
    print("All constant validations passed.")


if __name__ == "__main__":
    main()