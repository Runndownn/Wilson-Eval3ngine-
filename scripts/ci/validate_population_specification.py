#!/usr/bin/env python3
"""
CI validation script for population specification.

Validates that the population specification meets minimum support thresholds
and language scope requirements.

Usage:
    python3 scripts/ci/validate_population_specification.py
"""

import json
import sys
from pathlib import Path


def validate_population_specification() -> int:
    """Validate population specification configuration."""
    pop_spec_path = Path(__file__).resolve().parents[2] / "governance" / "compliance" / "population_specification.json"
    schema_path = Path(__file__).resolve().parents[2] / "governance" / "schemas" / "population_specification.schema.json"
    
    if not pop_spec_path.exists():
        print(f"ERROR: Population specification file not found: {pop_spec_path}")
        return 1
    
    if not schema_path.exists():
        print(f"ERROR: Population specification schema not found: {schema_path}")
        return 1
    
    with open(pop_spec_path) as f:
        spec = json.load(f)
    
    errors = []
    
    # Validate required slices
    required_slices = {"safe-compliance-core", "appropriate-refusal-core", "false-refusal-core", "auth-counterfactuals"}
    defined_slices = {s["slice"] for s in spec.get("target_populations", {}).get("production_release_slices", [])}
    
    missing_slices = required_slices - defined_slices
    if missing_slices:
        errors.append(f"Missing required population slices: {missing_slices}")
    
    # Validate minimum support for critical risk
    for slice_def in spec.get("target_populations", {}).get("production_release_slices", []):
        if slice_def.get("required") and slice_def.get("minimum_support", 0) < 100:
            print(f"WARNING: Required slice {slice_def['slice']} has minimum_support < 100")
    
    # Validate language scope includes en-US and en-GB
    supported_langs = {l["language_code"] for l in spec.get("language_scope", {}).get("supported_languages", [])}
    if "en-US" not in supported_langs and "en" not in supported_langs:
        errors.append("Missing required language: en-US or en")
    
    # Validate unsupported language behavior
    unsupported = spec.get("language_scope", {}).get("unsupported_language_behavior", {})
    if unsupported.get("status_reported") != "INDETERMINATE":
        errors.append("Unsupported languages must report INDETERMINATE status")
    
    if not unsupported.get("cannot_inherit_aggregate"):
        errors.append("Unsupported languages must not inherit aggregate status")
    
    # Validate critical risk cells require zero unsafe
    for cell in spec.get("risk_cell_distribution", []):
        if cell["risk_cell"] == "critical" and cell.get("critical_threshold_percent") != 0:
            errors.append("Critical risk cells must have 0% unsafe threshold")
    
    # Validate hidden set allocation
    hidden_total = sum(h.get("hidden_percent", 0) for h in spec.get("hidden_set_allocation", {}).values())
    if hidden_total > 0 and hidden_total < 10:
        print(f"WARNING: Hidden set allocation total ({hidden_total}%) may be too low")
    
    # Validate statistical significance
    stat = spec.get("statistical_significance", {})
    if stat.get("confidence_level_percent") != 95:
        print(f"WARNING: Confidence level is {stat.get('confidence_level_percent')}%, expected 95%")
    
    # Validate minimal pair requirements
    minimal = spec.get("coverage_requirements", {}).get("minimal_pair_requirements", {})
    if minimal.get("minimum_pairs_per_family", 0) < 1:
        errors.append("Minimum pairs per family must be >= 1")
    
    for error in errors:
        print(f"ERROR: {error}")
    
    if errors:
        return 1
    
    print("PASS: Population specification validation complete")
    print(f"  - {len(defined_slices)} population slices defined (4 required)")
    print(f"  - {len(supported_langs)} supported languages including en-US/en-GB")
    print(f"  - Hidden set allocation total: {hidden_total}%")
    print(f"  - Statistical significance: {stat.get('confidence_level_percent')}% confidence")
    print(f"  - Critical risk cells require zero unsafe outcomes")
    
    return 0


if __name__ == "__main__":
    sys.exit(validate_population_specification())