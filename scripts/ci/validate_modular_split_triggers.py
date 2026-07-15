#!/usr/bin/env python3
"""
CI validation script for modular split triggers.

Validates that all split triggers are defined and well-formed.
Used as a quality gate in CI pipelines.

Usage:
    python3 scripts/ci/validate_modular_split_triggers.py
"""

import json
import sys
from pathlib import Path


def validate_split_triggers() -> int:
    """Validate modular split triggers configuration."""
    triggers_path = Path(__file__).resolve().parents[2] / "governance" / "compliance" / "modular_split_triggers.json"
    
    if not triggers_path.exists():
        print(f"ERROR: Split triggers file not found: {triggers_path}")
        return 1
    
    with open(triggers_path) as f:
        config = json.load(f)
    
    # Required triggers per ADR-001
    required_triggers = {
        "incompatible-credentials",
        "sustained-independent-scaling",
        "stronger-isolation-required",
        "residency-required",
        "ownership-separation",
        "different-runtime",
        "independent-release-cadence",
        "failure-domain-split"
    }
    
    defined_triggers = {t["trigger"] for t in config["split_triggers"]}
    
    missing = required_triggers - defined_triggers
    if missing:
        print(f"ERROR: Missing required split triggers: {missing}")
        return 1
    
    # Validate each trigger has required fields
    for trigger in config["split_triggers"]:
        if "description" not in trigger:
            print(f"ERROR: Trigger {trigger['trigger']} missing description")
            return 1
        if "measurement_method" not in trigger:
            print(f"ERROR: Trigger {trigger['trigger']} missing measurement_method")
            return 1
        if "migration_adr_required" not in trigger:
            print(f"ERROR: Trigger {trigger['trigger']} missing migration_adr_required")
            return 1
    
    # Validate modules exist
    if "module_map" not in config:
        print("ERROR: Missing module_map")
        return 1
    
    if len(config["module_map"]) < 5:
        print(f"WARNING: Only {len(config['module_map'])} modules defined, expected at least 5")
    
    print("PASS: Modular split triggers validation complete")
    print(f"  - {len(config['split_triggers'])} triggers defined (8 required)")
    print(f"  - {len(config['module_map'])} modules mapped")
    print(f"  - {len(config.get('trust_zones', []))} trust zones defined")
    
    return 0


if __name__ == "__main__":
    sys.exit(validate_split_triggers())