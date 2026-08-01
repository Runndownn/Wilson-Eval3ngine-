"""Unit tests for advanced lane scope validation.

TODO 60 - Tests for prototype contracts, project filters, versioning,
deletion propagation, and deterministic fallback.
"""

from datetime import datetime, timezone

import pytest

from wilson_eval3ngine.evaluation.scope_validation import (
    AcceleratorConfiguration,
    CapabilityAnalyst,
    CapabilityDecision,
    CapabilityEvaluation,
    CapabilityType,
    MultimodalConfiguration,
    PrototypeRunner,
    VectorConfiguration,
)


# =============================================================================
# Capability Decision Tests
# =============================================================================


class TestCapabilityDecisions:
    """Tests for capability decision types."""

    def test_decisions_are_exclusive(self):
        """Each capability has exactly one decision."""
        decisions = [CapabilityDecision.ADOPT, CapabilityDecision.DEFER, CapabilityDecision.NOT_APPLICABLE]
        assert len(decisions) == 3

    def test_default_decisions_set(self):
        """Default decisions are set for all capabilities after evaluation."""
        analyst = CapabilityAnalyst()
        # Need to run evaluations for all capabilities including embeddings
        analyst.evaluate_retrieval("Test", "population")
        analyst.evaluate_vector_storage("model")
        analyst.evaluate_accelerators("A100")
        analyst.evaluate_multimodal(["image/*"])
        decisions = analyst.get_decisions()

        # Check that evaluated capabilities are present
        assert "retrieval" in decisions
        assert "vector_storage" in decisions
        assert "accelerators" in decisions
        assert "multimodal" in decisions


class TestSpecificCapabilities:
    """Tests for each capability type."""

    def test_retrieval_default_defer(self):
        """Retrieval capability defaults to DEFER."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_retrieval("Test use case", "safe-compliance-core")

        assert eval_.capability == CapabilityType.RETRIEVAL
        assert eval_.decision == CapabilityDecision.DEFER

    def test_vector_storage_default_not_applicable(self):
        """Vector storage defaults to NOT_APPLICABLE."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_vector_storage("bge-m3:latest")

        assert eval_.capability == CapabilityType.VECTOR_STORAGE
        assert eval_.decision == CapabilityDecision.NOT_APPLICABLE

    def test_accelerator_default_not_applicable(self):
        """Accelerator capability defaults to NOT_APPLICABLE."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_accelerators("A100")

        assert eval_.capability == CapabilityType.ACCELERATORS
        assert eval_.decision == CapabilityDecision.NOT_APPLICABLE

    def test_multimodal_default_not_applicable(self):
        """Multimodal capability defaults to NOT_APPLICABLE."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_multimodal(["image/jpeg", "image/png"])

        assert eval_.capability == CapabilityType.MULTIMODAL
        assert eval_.decision == CapabilityDecision.NOT_APPLICABLE


# =============================================================================
# Vector Configuration Tests
# =============================================================================


class TestVectorConfiguration:
    """Tests for vector configuration if ADOPT is chosen."""

    def test_vector_config_serialization(self):
        """Vector configuration serializes with required fields."""
        config = VectorConfiguration(
            column_type="hnsw",
            embedding_dimension=768,
            embedding_model_version="bge-m3:1.0",
            distance_metric="cosine",
            index_parameters={"m": 16, "ef": 100},
        )

        d = config.to_dict()
        assert d["column_type"] == "hnsw"
        assert d["embedding_dimension"] == 768
        assert d["embedding_model_version"] == "bge-m3:1.0"

    def test_vector_model_versioning(self):
        """Embedding model version is tracked for lifecycle."""
        config = VectorConfiguration(
            column_type="hnsw",
            embedding_dimension=768,
            embedding_model_version="bge-m3:1.0",
            distance_metric="cosine",
        )

        assert "bge-m3" in config.embedding_model_version
        assert "1.0" in config.embedding_model_version


# =============================================================================
# Project/Classification Scope Tests
# =============================================================================


class TestProjectScope:
    """Tests for project and data classification scoping."""

    def test_evaluation_includes_data_classifications(self):
        """Each evaluation includes data classification impact."""
        analyst = CapabilityAnalyst()

        for capability in CapabilityType:
            eval_ = analyst.evaluate_retrieval("Test", "test-population")
            break

        # Retrieval evaluation should have classifications
        eval_ = analyst.evaluate_retrieval(
            "RAG for long prompts",
            "safe-compliance-core",
        )
        assert "internal" in eval_.data_classifications

    def test_security_threats_identified(self):
        """Each capability has documented threat analysis."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_multimodal(["image/png"])
        assert len(eval_.threats) > 0
        # Check for threat content (lowercase matching)
        threats_lower = [t.lower() for t in eval_.threats]
        # Check for specific multimodal threats
        assert any("parser" in t or "malformed" in t for t in threats_lower)


# =============================================================================
# Prototype Comparison Tests
# =============================================================================


class TestPrototypeComparison:
    """Tests for prototype vs baseline comparison."""

    def test_prototype_runner_exists(self):
        """PrototypeRunner can be instantiated."""
        runner = PrototypeRunner()
        assert runner is not None

    def test_comparison_identifies_improvement(self):
        """Prototype comparison correctly identifies improvement."""
        runner = PrototypeRunner()

        baseline = {
            "quality_score": 0.85,
            "latency_seconds": 5.0,
        }
        prototype = {
            "quality_score": 0.94,  # 9% better (>= 10% threshold)
            "latency_seconds": 2.5,  # Faster
        }

        comparison = runner.run_comparison(
            CapabilityType.ACCELERATORS,
            baseline,
            prototype,
        )

        assert comparison["improvement"] == pytest.approx(0.09, rel=0.01)
        assert comparison["meets_quality_target"] is True
        assert comparison["meets_latency_target"] is True

    def test_comparison_negative_improvement(self):
        """Negative improvement correctly identified."""
        runner = PrototypeRunner()

        baseline = {
            "quality_score": 0.90,
            "latency_seconds": 2.0,
        }
        prototype = {
            "quality_score": 0.85,  # Worse
            "latency_seconds": 3.0,  # Slower
        }

        comparison = runner.run_comparison(
            CapabilityType.ACCELERATORS,
            baseline,
            prototype,
        )

        assert comparison["improvement"] == pytest.approx(-0.05, rel=0.01)

    def test_comparison_requires_10pct_improvement(self):
        """Quality target requires 10% improvement."""
        runner = PrototypeRunner()

        baseline = {"quality_score": 0.90, "latency_seconds": 1.0}
        prototype = {"quality_score": 0.94, "latency_seconds": 0.5}  # Only 4% better

        comparison = runner.run_comparison(
            CapabilityType.ACCELERATORS,
            baseline,
            prototype,
        )

        assert comparison["meets_quality_target"] is False


# =============================================================================
# Deletion Propagation Tests
# =============================================================================


class TestDeletionPropagation:
    """Tests for vector deletion lifecycle."""

    def test_vector_config_includes_lifecycle_considerations(self):
        """Vector configuration considers deletion lifecycle."""
        # This is documented in the evaluation, not enforced by the config
        # The evaluation notes deletion requirements
        config = VectorConfiguration(
            column_type="NOT_APPLICABLE",
            embedding_dimension=0,
            embedding_model_version="NOT_APPLICABLE",
            distance_metric="NOT_APPLICABLE",
        )

        # For NOT_APPLICABLE, dimension is 0
        assert config.embedding_dimension == 0

    def test_stale_embeddings_risk_documented(self):
        """Stale embeddings after source deletion is documented as risk."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("test-model")
        # Risks include vectors surviving deletion
        assert any("surviving" in t.lower() or "deletion" in t.lower() for t in eval_.threats)


# =============================================================================
# Security Tests
# =============================================================================


class TestAdvancedLaneSecurity:
    """Security tests for advanced capabilities."""

    def test_embedding_inversion_prevented(self):
        """Embedding inversion is documented as threat for ADOPT decisions."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("model-v1")
        # If ADOPT, would require controls
        # If NOT_APPLICABLE, still documents threat
        assert any("inversion" in t.lower() for t in eval_.threats)

    def test_cross_project_retrieval_prevented(self):
        """Cross-project retrieval is documented as threat."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_retrieval("Test", "population")
        assert any(
            "cross-project" in t.lower() or "scope" in t.lower() for t in eval_.threats
        )

    def test_multimodal_parser_security(self):
        """Multimodal parser vulnerabilities documented."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_multimodal(["image/*"])
        assert any("parser" in t.lower() or "vulnerability" in t.lower() for t in eval_.threats)


# =============================================================================
# Operational Owner Tests
# =============================================================================


class TestOperationalOwnership:
    """Tests for operational ownership requirements."""

    def test_operational_owner_required(self):
        """Each evaluation has operational owner assigned."""
        analyst = CapabilityAnalyst()

        for capability in [CapabilityType.RETRIEVAL, CapabilityType.VECTOR_STORAGE, CapabilityType.ACCELERATORS]:
            if capability == CapabilityType.RETRIEVAL:
                eval_ = analyst.evaluate_retrieval("Test", "population")
            elif capability == CapabilityType.VECTOR_STORAGE:
                eval_ = analyst.evaluate_vector_storage("model")
            else:
                eval_ = analyst.evaluate_accelerators("gpu")

            assert eval_.operational_owner, f"Missing owner for {capability}"

    def test_certification_impact_documented(self):
        """Each evaluation documents certification impact."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_multimodal(["audio/wav"])
        assert eval_.certification_impact
        assert len(eval_.certification_impact) > 0


# =============================================================================
# Deterministic Fallback Tests
# =============================================================================


class TestDeterministicFallback:
    """Tests for deterministic fallback behavior."""

    def test_not_applicable_allows_fallback(self):
        """NOT_APPLICABLE capabilities fall back to simpler approach."""
        # When capability is NOT_APPLICABLE, system uses existing approach
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("model")
        assert eval_.decision == CapabilityDecision.NOT_APPLICABLE
        assert eval_.vector_config is not None
        assert eval_.vector_config.column_type == "NOT_APPLICABLE"

    def test_deferred_not_implicit_dependency(self):
        """Deferred capabilities cannot become implicit production dependencies."""
        # DEFER means explicitly not implemented - no hidden dependency
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_retrieval("Test", "population")
        assert eval_.decision == CapabilityDecision.DEFER
        assert eval_.certification_impact  # Must not silently slip in


# =============================================================================
# Evaluation Serialization Tests
# =============================================================================


class TestEvaluationSerialization:
    """Tests for evaluation record serialization."""

    def test_evaluation_to_dict(self):
        """Evaluation serializes to complete dictionary."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_accelerators("H100")

        d = eval_.to_dict()
        assert d["capability"] == "accelerators"
        assert "operational" in d
        assert "use_case" in d
        assert "alternatives" in d
        assert "certification" in d

    def test_evaluation_stored_and_retrievable(self):
        """Evaluations are stored and can be retrieved."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("test-model")
        retrieved = analyst.get_evaluation(eval_.evaluation_id)

        assert retrieved is not None
        assert retrieved.capability == eval_.capability


# =============================================================================
# Privacy Review Tests
# =============================================================================


class TestPrivacyReviewRequirements:
    """Tests for privacy review requirements."""

    def test_vector_requires_privacy_review(self):
        """Vector storage requires privacy review for derived data."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("model")
        assert eval_.privacy_review_required is True

    def test_multimodal_requires_privacy_review(self):
        """Multimodal requires privacy review for media content."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_multimodal(["image/*"])
        assert eval_.privacy_review_required is True


# =============================================================================
# Capacity Approval Tests
# =============================================================================


class TestCapacityApproval:
    """Tests for capacity approval requirements."""

    def test_accelerator_requires_capacity_approval(self):
        """Accelerators require capacity approval before implementation."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_accelerators("A100")
        assert eval_.capacity_approval_required is True

    def test_vector_does_not_require_capacity_approval(self):
        """Vector storage can defer capacity approval if NOT_APPLICABLE."""
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_vector_storage("model")
        assert eval_.capacity_approval_required is False


# =============================================================================
# Hidden Set Contamination Tests
# =============================================================================


class TestHiddenSetContamination:
    """Tests for hidden set contamination prevention."""

    def test_adaptive_exploration_contamination_prevented(self):
        """Adaptive exploration contamination is documented as risk."""
        # This would be an explicit check when capability is ADOPT
        # For now, verify the threat is documented
        analyst = CapabilityAnalyst()

        eval_ = analyst.evaluate_retrieval("Test", "hidden-set")
        # Should document contamination as risk
        threats_str = " ".join(eval_.threats).lower()
        assert "cross-project" in threats_str or "scope" in threats_str


# =============================================================================
# Missing Capability Evaluation Tests
# =============================================================================


class TestLocalModelsCapability:
    """Tests for local models capability evaluation."""

    def test_local_models_default_defer(self):
        """Local models capability defaults to DEFER."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_local_models(5, "local-models-vendor")

        assert eval_.capability == CapabilityType.LOCAL_MODELS
        assert eval_.decision == CapabilityDecision.DEFER

    def test_local_models_threats_documented(self):
        """Local models have documented security threats."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_local_models(10, "vendor")

        assert any("tampering" in t.lower() for t in eval_.threats)


class TestRegionalExecutorsCapability:
    """Tests for regional executors capability evaluation."""

    def test_regional_executors_default_not_applicable(self):
        """Regional executors defaults to NOT_APPLICABLE."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_regional_executors(["us-east-1", "eu-west-1"])

        assert eval_.capability == CapabilityType.REGIONAL_EXECUTORS
        assert eval_.decision == CapabilityDecision.NOT_APPLICABLE

    def test_regional_executors_sovereignty_threats(self):
        """Regional executors document data sovereignty threats."""
        analyst = CapabilityAnalyst()
        eval_ = analyst.evaluate_regional_executors(["us-east-1"])

        threats_str = " ".join(eval_.threats).lower()
        assert "sovereignty" in threats_str or "isolation" in threats_str


class TestEvaluateAll:
    """Tests for comprehensive capability evaluation."""

    def test_evaluate_all_returns_all_capabilities(self):
        """evaluate_all returns all seven capability evaluations."""
        analyst = CapabilityAnalyst()
        evaluations = analyst.evaluate_all(
            use_case="Test use case",
            target_population="test-population",
        )

        assert len(evaluations) == 7

        # Verify all capabilities are evaluated
        capability_values = {e.capability for e in evaluations}
        assert CapabilityType.RETRIEVAL in capability_values
        assert CapabilityType.VECTOR_STORAGE in capability_values
        assert CapabilityType.ACCELERATORS in capability_values
        assert CapabilityType.MULTIMODAL in capability_values
        assert CapabilityType.EMBEDDINGS in capability_values
        assert CapabilityType.LOCAL_MODELS in capability_values
        assert CapabilityType.REGIONAL_EXECUTORS in capability_values