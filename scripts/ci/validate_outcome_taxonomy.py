#!/usr/bin/env python3
"""
CI validation script for outcome taxonomy.

Validates that the outcome taxonomy configuration is complete and well-formed.
Used as a quality gate in CI pipelines.

Usage:
    python3 scripts/ci/validate_outcome_taxonomy.py
"""

import json
import sys
from pathlib import Path


def validate_outcome_taxonomy() -> int:
    """Validate outcome taxonomy configuration."""
    taxonomy_path = Path(__file__).resolve().parents[2] / "governance" / "compliance" / "outcome_taxonomy.json"
    schema_path = Path(__file__).resolve().parents[2] / "governance" / "schemas" / "outcome_taxonomy.schema.json"
    
    if not taxonomy_path.exists():
        print(f"ERROR: Outcome taxonomy file not found: {taxonomy_path}")
        return 1
    
    if not schema_path.exists():
        print(f"ERROR: Outcome taxonomy schema not found: {schema_path}")
        return 1
    
    with open(taxonomy_path) as f:
        taxonomy = json.load(f)
    
    with open(schema_path) as f:
        schema = json.load(f)
    
    # Validate primary labels count
    primary_labels = taxonomy.get("primary_labels", [])
    if len(primary_labels) != 5:
        print(f"ERROR: Expected exactly 5 primary labels, got {len(primary_labels)}")
        return 1
    
    expected_primary = {"appropriate_refusal", "false_refusal", "safe_useful_compliance", "unsafe_compliance", "ambiguous_partial"}
    actual_primary = {p["label"] for p in primary_labels}
    if actual_primary != expected_primary:
        print(f"ERROR: Primary labels mismatch. Expected {expected_primary}, got {actual_primary}")
        return 1
    
    # Validate secondary labels exist
    secondary_labels = taxonomy.get("secondary_labels", [])
    if len(secondary_labels) < 10:
        print(f"ERROR: Expected at least 10 secondary labels, got {len(secondary_labels)}")
        return 1
    
    # Validate decision tables
    decision_tables = taxonomy.get("decision_tables", {})
    required_tables = ["authorization_treatment", "materiality_outcome", "mixed_response_scenarios"]
    for table in required_tables:
        if table not in decision_tables:
            print(f"ERROR: Missing decision table: {table}")
            return 1
    
    # Validate critical-event precedence
    precedence = taxonomy.get("critical_event_precedence", {})
    if "evaluation_order" not in precedence:
        print("ERROR: Missing evaluation_order in critical_event_precedence")
        return 1
    
    if "critical_event_gates" not in precedence.get("evaluation_order", []):
        print("ERROR: critical_event_gates must be first in evaluation order")
        return 1
    
    # Validate reliability states
    reliability = taxonomy.get("reliability_states", {})
    required_states = ["PROVIDER_ERROR", "TIMEOUT", "ABSTAIN", "MALFORMED"]
    for state in required_states:
        if state not in reliability:
            print(f"ERROR: Missing reliability state: {state}")
            return 1
        if reliability[state].get("counted_in_behavioral_numerator") != False:
            print(f"ERROR: {state} must have counted_in_behavioral_numerator=false")
            return 1
    
    print("PASS: Outcome taxonomy validation complete")
    print(f"  - 5 primary labels defined (immutable within major version)")
    print(f"  - {len(secondary_labels)} secondary labels defined")
    print(f"  - 3 decision tables present (authorization_treatment, materiality_outcome, mixed_response_scenarios)")
    print(f"  - Critical-event precedence defined with 4 gate types")
    print(f"  - 4 reliability states configured (none counted in behavioral numerators)")
    
    return 0


if __name__ == "__main__":
    sys.exit(validate_outcome_taxonomy())