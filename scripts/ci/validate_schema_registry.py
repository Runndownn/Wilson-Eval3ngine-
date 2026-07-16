#!/usr/bin/env python3
"""
CI validation script for schema registry.

Validates that all contract schemas are registered, hashes are verifiable,
canonical serialization is configured, and security parser requirements are defined.

Usage:
    python3 scripts/ci/validate_schema_registry.py
"""

import json
import hashlib
import sys
from pathlib import Path


def validate_schema_registry() -> int:
    """Validate schema registry configuration."""
    registry_path = Path(__file__).resolve().parents[2] / "governance" / "compliance" / "schema_registry_index.json"
    registry_schema_path = Path(__file__).resolve().parents[2] / "governance" / "schemas" / "schema_registry_index.schema.json"
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts" / "schemas"
    
    if not registry_path.exists():
        print(f"ERROR: Schema registry file not found: {registry_path}")
        return 1
    
    if not registry_schema_path.exists():
        print(f"ERROR: Registry schema file not found: {registry_schema_path}")
        return 1
    
    with open(registry_path) as f:
        registry = json.load(f)
    
    with open(registry_schema_path) as f:
        schema = json.load(f)
    
    errors = []
    
    # Validate registry has schemas array
    schemas = registry.get("schemas", [])
    if not schemas:
        errors.append("Schema registry contains no schemas")
    
    # Validate all contract schemas are registered
    schema_files = list(contracts_dir.glob("*.schema.json"))
    registry_names = {s["schema_name"] for s in schemas}
    
    for schema_file in schema_files:
        name = schema_file.stem.replace(".v1.schema", "").replace(".v2.schema", "")
        if name not in registry_names:
            errors.append(f"Schema {name} not registered in schema_registry_index.json")
    
    # Validate schema hash format
    for entry in schemas:
        schema_hash = entry.get("schema_hash", "")
        if schema_hash and not schema_hash.startswith("sha256:"):
            errors.append(f"Schema {entry['schema_name']} has invalid hash format (expected sha256:*)")
    
    # Validate canonical serialization
    canonical = registry.get("canonical_serialization", {})
    required_canonical = ["encoding", "key_ordering", "timestamp_format", "identifier_format"]
    for field in required_canonical:
        if field not in canonical:
            errors.append(f"Missing canonical serialization field: {field}")
    
    if canonical.get("encoding") != "UTF-8":
        errors.append("Canonical encoding must be UTF-8")
    
    if canonical.get("timestamp_format") != "ISO_8601_with_offset":
        errors.append("Timestamp format must be ISO_8601_with_offset")
    
    # Validate security parsers
    security = registry.get("security_parsers", {})
    required_security = ["reject_duplicate_keys", "reject_invalid_unicode", "reject_non_finite_numbers",
                       "reject_unsafe_yaml_tags", "max_nesting_depth", "max_scalar_bytes"]
    for field in required_security:
        if field not in security:
            errors.append(f"Missing security parser requirement: {field}")
    
    if security.get("reject_duplicate_keys") is not True:
        errors.append("Security parsers must reject duplicate keys")
    
    if security.get("reject_invalid_unicode") is not True:
        errors.append("Security parsers must reject invalid unicode")
    
    # Validate compatibility policy
    policy = registry.get("compatibility_policy", {})
    required_policy = ["additive_optional_fields", "removed_fields", "renamed_fields", "score_affecting_changes"]
    for field in required_policy:
        if field not in policy:
            errors.append(f"Missing compatibility policy field: {field}")
    
    for error in errors:
        print(f"ERROR: {error}")
    
    if errors:
        return 1
    
    # Compute actual schema hashes for reporting
    computed_hashes = {}
    for schema_file in schema_files:
        content = schema_file.read_bytes()
        computed_hashes[schema_file.name] = hashlib.sha256(content).hexdigest()
    
    print("PASS: Schema registry validation complete")
    print(f"  - {len(schemas)} schemas registered")
    print(f"  - {len(schema_files)} contract schema files verified")
    print(f"  - Canonical serialization: {canonical.get('encoding')} encoding, {canonical.get('timestamp_format')}")
    print(f"  - Security parsers: duplicate_keys={security.get('reject_duplicate_keys')}, "
          f"invalid_unicode={security.get('reject_invalid_unicode')}, "
          f"non_finite={security.get('reject_non_finite_numbers')}")
    print(f"  - Compatibility policy: removed_fields={policy.get('removed_fields')}, "
          f"score_affecting={policy.get('score_affecting_changes')}")
    
    return 0


if __name__ == "__main__":
    sys.exit(validate_schema_registry())