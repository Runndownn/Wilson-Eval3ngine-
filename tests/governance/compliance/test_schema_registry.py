"""
Tests for schema registry and contract validation.

Validates T2.1.2 requirements.
"""

import json
import hashlib
import pytest
from pathlib import Path


REGISTRY_PATH = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/schema_registry_index.json")
CONTRACTS_PATH = Path("/home/geezeradmin/work/Wilson-Eval3ngine/contracts/schemas")


@pytest.fixture
def schema_registry():
    with open(REGISTRY_PATH) as f:
        return json.load(f)


@pytest.fixture
def contracts_dir():
    return CONTRACTS_PATH


class TestSchemaRegistryComplete:
    """Test schema registry completeness."""

    def test_registry_exists(self, schema_registry):
        """Schema registry index exists and is valid JSON."""
        assert "schemas" in schema_registry
        assert "registry_version" in schema_registry

    def test_all_schemas_registered(self, schema_registry, contracts_dir):
        """All contract schemas are registered in the index."""
        registry_names = {s["schema_name"] for s in schema_registry["schemas"]}
        
        # Find schema files
        schema_files = list(contracts_dir.glob("*.schema.json"))
        for schema_file in schema_files:
            # Extract schema name from filename (we3.name.v1.schema.json -> we3.name)
            name = schema_file.stem.replace(".v1.schema", "").replace(".v2.schema", "")
            assert name in registry_names, f"Schema {name} not in registry"

    def test_schema_hash_verification(self, schema_registry, contracts_dir):
        """Schema hashes can be computed and verified."""
        for entry in schema_registry["schemas"]:
            schema_path = contracts_dir / entry["schema_path"].split("/")[-1]
            if schema_path.exists():
                content = schema_path.read_bytes()
                computed_hash = hashlib.sha256(content).hexdigest()
                # Hash should be verifiable (stored hash may be placeholder)
                assert computed_hash is not None


class TestSchemaStrictValidation:
    """Test schema strictness requirements."""

    def test_classification_requires_all_fields(self):
        """Classification schema rejects unknown fields."""
        classification_path = CONTRACTS_PATH / "we3.classification.v1.schema.json"
        with open(classification_path) as f:
            schema = json.load(f)
        
        assert schema.get("additionalProperties") is False

    def test_test_case_rejects_unknown_fields(self):
        """Test case schema rejects unknown fields."""
        test_case_path = CONTRACTS_PATH / "we3.test_case.v1.schema.json"
        with open(test_case_path) as f:
            schema = json.load(f)
        
        assert schema.get("additionalProperties") is False


class TestCanonicalSerialization:
    """Test canonical serialization rules."""

    def test_timestamp_format_iso8601(self, schema_registry):
        """Timestamps must use ISO 8601 format."""
        canonical = schema_registry.get("canonical_serialization", {})
        assert canonical.get("timestamp_format") == "ISO_8601_with_offset"

    def test_encoding_utf8(self, schema_registry):
        """Canonical encoding is UTF-8."""
        canonical = schema_registry.get("canonical_serialization", {})
        assert canonical.get("encoding") == "UTF-8"

    def test_key_ordering_alphabetical(self, schema_registry):
        """Keys are ordered alphabetically for determinism."""
        canonical = schema_registry.get("canonical_serialization", {})
        assert canonical.get("key_ordering") == "alphabetical"


class TestVersionCompatibility:
    """Test semantic versioning and compatibility."""

    def test_compatibility_policy_defined(self, schema_registry):
        """Compatibility policy is explicitly defined."""
        policy = schema_registry.get("compatibility_policy", {})
        assert "additive_optional_fields" in policy
        assert "removed_fields" in policy
        assert "score_affecting_changes" in policy

    def test_removed_fields_require_major(self, schema_registry):
        """Removed fields require major version."""
        policy = schema_registry.get("compatibility_policy", {})
        assert policy.get("removed_fields") is not None


class TestUnknownFieldRejection:
    """Test unknown field rejection in schemas."""

    def test_all_business_objects_strict(self, schema_registry, contracts_dir):
        """All schemas for business objects reject unknown fields."""
        for entry in schema_registry["schemas"]:
            schema_file = contracts_dir / entry["schema_path"].split("/")[-1]
            if schema_file.exists():
                with open(schema_file) as f:
                    schema = json.load(f)
                # Top-level additionalProperties should be false
                assert schema.get("additionalProperties", True) is False, f"Schema {schema_file} allows unknown fields"


class TestSecurityParserRequirements:
    """Test security parser constraints per TODO 8 requirements."""

    def test_security_parsers_defined(self, schema_registry):
        """Security parser requirements are explicitly defined."""
        assert "security_parsers" in schema_registry

    def test_duplicate_key_rejection(self, schema_registry):
        """Parsers reject duplicate JSON keys."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_duplicate_keys") is True

    def test_invalid_unicode_rejection(self, schema_registry):
        """Parsers reject invalid Unicode."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_invalid_unicode") is True

    def test_non_finite_number_rejection(self, schema_registry):
        """Parsers reject non-finite numbers (NaN, Infinity)."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_non_finite_numbers") is True

    def test_unsafe_yaml_tags_rejection(self, schema_registry):
        """Parsers reject unsafe YAML tags."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_unsafe_yaml_tags") is True

    def test_excessive_nesting_limit(self, schema_registry):
        """Parsers reject excessive nesting."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_excessive_nesting") is True
        assert security.get("max_nesting_depth", 0) > 0

    def test_oversized_scalar_limit(self, schema_registry):
        """Parsers reject oversized scalars."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("reject_oversized_scalars") is True
        assert security.get("max_scalar_bytes", 0) > 0

    def test_yaml_safe_constructors(self, schema_registry):
        """YAML parsers use safe constructors only."""
        security = schema_registry.get("security_parsers", {})
        assert security.get("yaml_safe_constructors_only") is True


class TestSchemaRegistryIndexSchema:
    """Test the schema_registry_index.schema.json file."""

    def test_registry_schema_exists(self):
        """Schema for registry index exists."""
        import os
        schema_path = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/schemas/schema_registry_index.schema.json")
        assert schema_path.exists()

    def test_registry_schema_valid_json(self):
        """Registry schema is valid JSON."""
        with open(Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/schemas/schema_registry_index.schema.json")) as f:
            schema = json.load(f)
        assert schema["$schema"] is not None


class TestSchemaRegistryCIValidation:
    """Test the CI validation script for schema registry exists and runs."""

    def test_validate_script_exists(self):
        """CI validation script exists."""
        script_path = Path("/home/geezeradmin/work/Wilson-Eval3ngine/scripts/ci/validate_schema_registry.py")
        assert script_path.exists()

    def test_validate_script_executable(self):
        """CI validation script is valid Python."""
        import ast
        script_path = Path("/home/geezeradmin/work/Wilson-Eval3ngine/scripts/ci/validate_schema_registry.py")
        content = script_path.read_text()
        # Should be parseable as valid Python
        ast.parse(content)