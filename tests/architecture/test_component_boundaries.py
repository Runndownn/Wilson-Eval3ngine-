"""
Architecture boundary tests for modular monolith.

Tests module dependencies, trust zones, and split triggers.
"""

import json
import pytest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGERS_PATH = REPO_ROOT / "governance/compliance/modular_split_triggers.json"


@pytest.fixture
def split_triggers():
    """Load the modular split triggers configuration."""
    with open(TRIGGERS_PATH) as f:
        return json.load(f)


class TestSplitTriggersDefined:
    """Test that all split triggers are defined."""

    def test_all_split_triggers_defined(self, split_triggers):
        """All 8 required split triggers must be defined."""
        required_triggers = [
            "incompatible-credentials",
            "sustained-independent-scaling",
            "stronger-isolation-required",
            "residency-required",
            "ownership-separation",
            "different-runtime",
            "independent-release-cadence",
            "failure-domain-split"
        ]
        
        defined_triggers = [t["trigger"] for t in split_triggers["split_triggers"]]
        
        for required in required_triggers:
            assert required in defined_triggers, f"Missing split trigger: {required}"

    def test_split_triggers_have_architecture_review(self, split_triggers):
        """Split triggers requiring architecture review are properly marked."""
        architecture_review_triggers = ["incompatible-credentials", "residency-required", "different-runtime", "failure-domain-split"]
        
        for trigger in split_triggers["split_triggers"]:
            if trigger["trigger"] in architecture_review_triggers:
                assert trigger["measurement_method"] in ["architecture-review", "manual-review"]


class TestModuleDependencies:
    """Test module dependency rules."""

    def test_no_circular_dependencies(self, split_triggers):
        """Module imports must not create circular dependencies."""
        # Build dependency graph
        modules = {m["module_id"]: set(m["allowed_imports"]) for m in split_triggers["module_map"]}
        
        # Check for cycles using DFS
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in modules.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False
        
        visited = set()
        for module in modules:
            if module not in visited:
                assert not has_cycle(module, visited, set())

    def test_modules_have_entry_points(self, split_triggers):
        """Each module must have explicit entry points."""
        for module in split_triggers["module_map"]:
            assert "entry_points" in module
            assert len(module["entry_points"]) > 0

    def test_trust_zones_distinct(self, split_triggers):
        """Trust zones must not overlap in credentials."""
        credentials_by_zone = {}
        for zone in split_triggers["trust_zones"]:
            zone_id = zone["zone_id"]
            for cred in zone.get("credentials", []):
                if cred in credentials_by_zone:
                    pytest.fail(f"Credential {cred} appears in multiple trust zones: {credentials_by_zone[cred]} and {zone_id}")
                credentials_by_zone[cred] = zone_id


class TestTrustZoneIsolation:
    """Test trust zone security isolation."""

    def test_provider_credentials_in_distinct_zone(self, split_triggers):
        """Provider credentials must be in isolated trust zone."""
        provider_zone = next(
            (z for z in split_triggers["trust_zones"] if "PROVIDER" in z["zone_id"]),
            None
        )
        assert provider_zone is not None
        assert len(provider_zone.get("credentials", [])) > 0

    def test_signing_zone_isolated(self, split_triggers):
        """Security signing zone must be network-isolated."""
        signing_zone = next(
            (z for z in split_triggers["trust_zones"] if "SIGNING" in z["zone_id"]),
            None
        )
        assert signing_zone is not None
        assert signing_zone["network_policy"] in ["isolated", "egress-only"]


class TestArchitectureExceptions:
    """Test architecture exception handling."""

    def test_module_may_split_for_measurable_reasons(self, split_triggers):
        """Modules can only split for measurable triggers, not preference."""
        # Verify all triggers are measurable
        for trigger in split_triggers["split_triggers"]:
            assert trigger["measurement_method"] in ["metric-threshold", "manual-review", "architecture-review"]