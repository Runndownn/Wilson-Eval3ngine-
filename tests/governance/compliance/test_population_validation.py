"""
Tests for benchmark population validation.

Validates T2.1.3 requirements.
"""

import json
import pytest
from pathlib import Path


POPULATION_SPEC = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/population_specification.json")
POPULATION_SPEC_SCHEMA = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/schemas/population_specification.schema.json")
SCHEMA_REGISTRY = Path("/home/geezeradmin/work/Wilson-Eval3ngine/governance/compliance/schema_registry_index.json")


@pytest.fixture
def population_spec():
    with open(POPULATION_SPEC) as f:
        return json.load(f)


@pytest.fixture
def population_spec_text():
    with open(POPULATION_SPEC) as f:
        return f.read()


@pytest.fixture
def schema_registry():
    with open(SCHEMA_REGISTRY) as f:
        return json.load(f)


class TestPopulationSpecificationJSON:
    """Test population specification JSON completeness."""

    def test_population_spec_json_exists(self, population_spec):
        """Population specification JSON exists."""
        assert population_spec is not None

    def test_population_spec_schema_exists(self):
        """Population specification schema exists and is valid JSON."""
        with open(POPULATION_SPEC_SCHEMA) as f:
            schema = json.load(f)
        assert schema["$schema"] is not None


class TestRequiredSlicesDefined:
    """Test required population slices are defined."""

    def test_required_slices_defined(self, population_spec):
        """Required population slices are defined."""
        required_slices = [
            "safe-compliance-core",
            "appropriate-refusal-core",
            "false-refusal-core",
            "auth-counterfactuals"
        ]
        defined_slices = {s["slice"] for s in population_spec.get("target_populations", {}).get("production_release_slices", [])}
        for slice in required_slices:
            assert slice in defined_slices, f"Missing required slice: {slice}"

    def test_all_slices_have_minimum_support(self, population_spec):
        """All slices have minimum support defined."""
        for slice_def in population_spec.get("target_populations", {}).get("production_release_slices", []):
            assert "minimum_support" in slice_def
            assert slice_def["minimum_support"] >= 1


class TestLanguageScopeDefined:
    """Test language scope is explicitly defined."""

    def test_english_language_defined(self, population_spec):
        """English language is in supported languages."""
        supported_langs = {l["language_code"] for l in population_spec.get("language_scope", {}).get("supported_languages", [])}
        assert "en" in supported_langs or "en-US" in supported_langs

    def test_unsupported_language_returns_indeterminate(self, population_spec):
        """Unsupported languages must report INDETERMINATE."""
        unsupported = population_spec.get("language_scope", {}).get("unsupported_language_behavior", {})
        assert unsupported.get("status_reported") == "INDETERMINATE"
        assert unsupported.get("secondary_label_required") == "unsupported_language"


class TestHiddenSetAllocation:
    """Test hidden set allocation."""

    def test_hidden_set_defined(self, population_spec):
        """Hidden set allocation is defined."""
        hidden = population_spec.get("hidden_set_allocation", {})
        assert len(hidden) >= 1

    def test_hidden_set_allocation_sum(self, population_spec):
        """Hidden set allocation totals to meaningful percentage."""
        hidden_total = sum(h.get("hidden_percent", 0) for h in population_spec.get("hidden_set_allocation", {}).values())
        assert hidden_total > 0


class TestRiskCellDistribution:
    """Test risk cell distribution requirements."""

    def test_critical_cells_require_zero_unsafe(self, population_spec):
        """Critical risk cells require zero unsafe outcomes."""
        for cell in population_spec.get("risk_cell_distribution", []):
            if cell["risk_cell"] == "critical":
                assert cell.get("critical_threshold_percent") == 0

    def test_all_risk_cells_defined(self, population_spec):
        """All risk cell types are defined."""
        cells = {c["risk_cell"] for c in population_spec.get("risk_cell_distribution", [])}
        assert cells == {"low", "medium", "high", "critical"}


class TestStatisticalSignificance:
    """Test statistical significance requirements."""

    def test_confidence_intervals_required(self, population_spec):
        """Confidence intervals must be reported."""
        stat = population_spec.get("statistical_significance", {})
        assert stat.get("confidence_level_percent") == 95

    def test_critical_cells_minimum_n(self, population_spec):
        """Critical cells have minimum sample size."""
        stat = population_spec.get("statistical_significance", {})
        assert stat.get("critical_cells_minimum", 0) >= 50


class TestCoverageRequirements:
    """Test coverage requirements."""

    def test_prohibited_categories_defined(self, population_spec):
        """Prohibited content categories are defined."""
        categories = population_spec.get("coverage_requirements", {}).get("prohibited_content_categories", [])
        assert len(categories) >= 5

    def test_minimal_pairs_required(self, population_spec):
        """Minimal pairs are required for each family."""
        minimal = population_spec.get("coverage_requirements", {}).get("minimal_pair_requirements", {})
        assert minimal.get("minimum_pairs_per_family", 0) >= 2


class TestCertificationWording:
    """Test certification wording constraints."""

    def test_claim_patterns_constrained(self, population_spec):
        """Certification language is mechanically constrained."""
        wording = population_spec.get("certification_wording_constraints", {})
        assert "permissible_patterns" in wording or "prohibited_patterns" in wording


class TestPopulationSpecAgainstSchema:
    """Test population spec structure against schema."""

    def test_schema_required_fields_present(self, population_spec):
        """Population spec has all required fields per schema."""
        required_fields = ["schema_version", "target_populations", "risk_cell_distribution",
                          "language_scope", "hidden_set_allocation", "statistical_significance",
                          "coverage_requirements", "certification_wording_constraints", "family_target"]
        for field in required_fields:
            assert field in population_spec, f"Missing required field: {field}"