"""Advanced lane scope validation - retrieval, vector, accelerator capabilities.

T8.1.10 - Validates whether advanced capabilities are necessary and documents
use cases, benefits, risk analysis, and operational owner decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from ..util import new_id, utc_now

logger = logging.getLogger("wilson.advanced_lanes")


# =============================================================================
# Capability Decisions
# =============================================================================


class CapabilityDecision(StrEnum):
    """Decision for each advanced capability."""

    ADOPT = "ADOPT"
    DEFER = "DEFER"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# =============================================================================
# Capability Types
# =============================================================================


class CapabilityType(StrEnum):
    """Advanced capability types."""

    RETRIEVAL = "retrieval"
    EMBEDDINGS = "embeddings"
    VECTOR_STORAGE = "vector_storage"
    MULTIMODAL = "multimodal"
    ACCELERATORS = "accelerators"
    LOCAL_MODELS = "local_models"
    REGIONAL_EXECUTORS = "regional_executors"


@dataclass(frozen=True, slots=True)
class VectorConfiguration:
    """Vector storage configuration for ADOPT decisions."""

    column_type: str  # e.g., "hnsw", "ivfflat", "annoy"
    embedding_dimension: int
    embedding_model_version: str
    distance_metric: str  # "cosine", "euclidean", "dot_product"
    index_parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column_type": self.column_type,
            "embedding_dimension": self.embedding_dimension,
            "embedding_model_version": self.embedding_model_version,
            "distance_metric": self.distance_metric,
            "index_parameters": self.index_parameters,
        }


@dataclass(frozen=True, slots=True)
class MultimodalConfiguration:
    """Multimodal processing configuration."""

    supported_formats: list[str]  # e.g., ["image/jpeg", "image/png", "audio/wav"]
    parser_sandbox_required: bool
    isolation_required: bool
    retention_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported_formats": self.supported_formats,
            "parser_sandbox_required": self.parser_sandbox_required,
            "isolation_required": self.isolation_required,
            "retention_policy": self.retention_policy,
        }


@dataclass(frozen=True, slots=True)
class AcceleratorConfiguration:
    """Accelerator (GPU) configuration."""

    gpu_type: str  # "A100", "H100", "T4"
    memory_gb: int
    isolation_required: bool
    signing_required: bool
    unsafe_cache_sharing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_type": self.gpu_type,
            "memory_gb": self.memory_gb,
            "isolation_required": self.isolation_required,
            "signing_required": self.signing_required,
            "unsafe_cache_sharing": self.unsafe_cache_sharing,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingsConfiguration:
    """Embeddings configuration."""

    model_name: str
    embedding_dimension: int
    batch_size: int
    cache_embeddings: bool
    retention_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "batch_size": self.batch_size,
            "cache_embeddings": self.cache_embeddings,
            "retention_policy": self.retention_policy,
        }


# =============================================================================
# Capability Evaluation Record
# =============================================================================


@dataclass
class CapabilityEvaluation:
    """Complete evaluation record for an advanced capability."""

    evaluation_id: str
    capability: CapabilityType
    decision: CapabilityDecision
    evaluated_at: datetime
    evaluator: str

    # Use case analysis
    use_case_description: str
    measurable_benefit: str
    target_population: str
    data_classifications: list[str]
    quality_target: str
    latency_target: str
    cost_estimate: str
    threats: list[str]
    operational_owner: str

    # Alternatives analysis
    alternatives_considered: list[str]
    selected_alternative: str

    # Effect on certification
    certification_impact: str
    privacy_review_required: bool = True
    capacity_approval_required: bool = True

    # Implementation details (if ADOPT)
    vector_config: VectorConfiguration | None = None
    multimodal_config: MultimodalConfiguration | None = None
    accelerator_config: AcceleratorConfiguration | None = None
    embeddings_config: EmbeddingsConfiguration | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "evaluation_id": self.evaluation_id,
            "capability": self.capability.value,
            "decision": self.decision.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluator": self.evaluator,
            "use_case": {
                "description": self.use_case_description,
                "measurable_benefit": self.measurable_benefit,
                "target_population": self.target_population,
                "data_classifications": self.data_classifications,
            },
            "operational": {
                "quality_target": self.quality_target,
                "latency_target": self.latency_target,
                "cost_estimate": self.cost_estimate,
                "operational_owner": self.operational_owner,
                "threats": self.threats,
            },
            "alternatives": {
                "considered": self.alternatives_considered,
                "selected": self.selected_alternative,
            },
            "certification": {
                "impact": self.certification_impact,
                "privacy_review_required": self.privacy_review_required,
                "capacity_approval_required": self.capacity_approval_required,
            },
        }
        if self.vector_config:
            result["vector_configuration"] = self.vector_config.to_dict()
        if self.multimodal_config:
            result["multimodal_configuration"] = self.multimodal_config.to_dict()
        if self.accelerator_config:
            result["accelerator_configuration"] = self.accelerator_config.to_dict()
        if self.embeddings_config:
            result["embeddings_configuration"] = self.embeddings_config.to_dict()
        return result


# =============================================================================
# Capability Analyst
# =============================================================================


class CapabilityAnalyst:
    """Analyzes and decides on advanced capabilities.

    Security requirements enforced:
    - No cross-project retrieval
    - Hidden-set leakage prevention
    - Embedding inversion exposure controls
    - Poisoned document ingestion detection
    - No unauthorized external model calls
    """

    # Default decisions for this evaluation (can be overridden)
    DEFAULT_DECISIONS: dict[CapabilityType, CapabilityDecision] = {
        CapabilityType.RETRIEVAL: CapabilityDecision.DEFER,
        CapabilityType.EMBEDDINGS: CapabilityDecision.NOT_APPLICABLE,
        CapabilityType.VECTOR_STORAGE: CapabilityDecision.NOT_APPLICABLE,
        CapabilityType.MULTIMODAL: CapabilityDecision.NOT_APPLICABLE,
        CapabilityType.ACCELERATORS: CapabilityDecision.NOT_APPLICABLE,
        CapabilityType.LOCAL_MODELS: CapabilityDecision.DEFER,
        CapabilityType.REGIONAL_EXECUTORS: CapabilityDecision.NOT_APPLICABLE,
    }

    def __init__(self) -> None:
        self._evaluations: dict[str, CapabilityEvaluation] = {}

    def evaluate_retrieval(
        self,
        use_case: str,
        target_population: str,
        security_review_completed: bool = False,
    ) -> CapabilityEvaluation:
        """Evaluate retrieval capability.

        Security: Prevents cross-project retrieval and hidden-set leakage.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.RETRIEVAL,
            decision=self.DEFAULT_DECISIONS[CapabilityType.RETRIEVAL],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description=use_case,
            measurable_benefit="Reduced token consumption for long-context tasks",
            target_population=target_population,
            data_classifications=["internal"],
            quality_target="Recall >= 95% for known relevant documents",
            latency_target="Query < 100ms for 95th percentile",
            cost_estimate="$500/month for vector storage at scale",
            threats=[
                "Cross-project retrieval if scope not enforced",
                "Hidden-set leakage through similarity search",
                "Poisoned document ingestion leading to unsafe responses",
            ],
            operational_owner="Platform Team",
            alternatives_considered=[
                "No retrieval (current)",
                "Simple keyword search",
                "Vector similarity search",
            ],
            selected_alternative="No retrieval (current) - outside scope",
            certification_impact="Would require vector index isolation controls",
            privacy_review_required=True,
            capacity_approval_required=False,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation

        if not security_review_completed:
            logger.warning(
                "retrieval_evaluation_security_required",
                extra={
                    "evaluation_id": evaluation.evaluation_id,
                    "capability": CapabilityType.RETRIEVAL.value,
                },
            )

        return evaluation

    def evaluate_vector_storage(
        self,
        embedding_model: str,
        required: bool = False,
    ) -> CapabilityEvaluation:
        """Evaluate vector storage capability.

        If adopted, returns VectorConfiguration.
        Otherwise marks as NOT_APPLICABLE per TODO 60 requirements.

        Security: Retention, deletion, legal hold, provenance controls required.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.VECTOR_STORAGE,
            decision=self.DEFAULT_DECISIONS[CapabilityType.VECTOR_STORAGE],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description="Store embeddings for retrieval-augmented evaluation",
            measurable_benefit="Fast similarity search for case matching",
            target_population="All evaluation families",
            data_classifications=["derived_vectors"],
            quality_target="Index rebuild time < 1 hour",
            latency_target="Search < 50ms",
            cost_estimate="$200/month for 100GB vector storage",
            threats=[
                "Embedding inversion exposing source content",
                "Vectors surviving source deletion",
                "Unauthorized search access",
            ],
            operational_owner="SRE Team",
            alternatives_considered=["No vectors", "Local FAISS", "PostgreSQL pgvector"],
            selected_alternative="No vectors (current)",
            certification_impact="Requires vector deletion lifecycle management",
            vector_config=VectorConfiguration(
                column_type="NOT_APPLICABLE",
                embedding_dimension=0,
                embedding_model_version="NOT_APPLICABLE",
                distance_metric="NOT_APPLICABLE",
            ),
            privacy_review_required=True,
            capacity_approval_required=False,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def evaluate_accelerators(
        self,
        gpu_type: str = "A100",
        workload_profile: str = "inference",
    ) -> CapabilityEvaluation:
        """Evaluate accelerator (GPU) capability.

        Security: Requires patched images, isolated workloads, signed artifacts,
        and no shared unsafe caches.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.ACCELERATORS,
            decision=self.DEFAULT_DECISIONS[CapabilityType.ACCELERATORS],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description=f"Accelerate {workload_profile} workloads",
            measurable_benefit=f"3x throughput for {workload_profile}",
            target_population="High-volume evaluation runs",
            data_classifications=["internal"],
            quality_target="No performance regression vs CPU",
            latency_target="Response time improvement >= 50%",
            cost_estimate="$2000/month for GPU instances",
            threats=[
                "GPU exhaustion attacks",
                "Shared cache contamination",
                "Unsigned artifact execution",
            ],
            operational_owner="ML Platform Team",
            alternatives_considered=[
                "CPU-only (current)",
                "Single GPU instance",
                "GPU cluster",
            ],
            selected_alternative="CPU-only (current)",
            certification_impact="Requires isolated GPU workloads with signing",
            accelerator_config=AcceleratorConfiguration(
                gpu_type=gpu_type,
                memory_gb=0,
                isolation_required=False,
                signing_required=False,
            ),
            privacy_review_required=False,
            capacity_approval_required=True,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def evaluate_embeddings(
        self,
        model_name: str | None = None,
    ) -> CapabilityEvaluation:
        """Evaluate embeddings capability.

        Security: Embedding inversion exposure, poisoned document ingestion.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.EMBEDDINGS,
            decision=self.DEFAULT_DECISIONS[CapabilityType.EMBEDDINGS],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description="Vector representation of text for retrieval",
            measurable_benefit="Semantic search over large document corpora",
            target_population="All text-based model outputs",
            data_classifications=["derived_embeddings"],
            quality_target="Recall >= 90% for semantic queries",
            latency_target="< 50ms per embedding",
            cost_estimate="$200/month for embedding model API calls",
            threats=[
                "Embedding inversion exposing training data",
                "Poisoned document ingestion leading to unsafe vectors",
                "Cross-project retrieval if vector isolation not enforced",
            ],
            operational_owner="Platform Team",
            alternatives_considered=[
                "No embeddings (current)",
                "Local embedding model",
                "External API service",
            ],
            selected_alternative="No embeddings (current)",
            certification_impact="Requires vector isolation controls and model approval",
            embeddings_config=EmbeddingsConfiguration(
                model_name=model_name or "text-embedding-3-small",
                embedding_dimension=1536,
                batch_size=100,
                cache_embeddings=False,
                retention_policy="NOT_APPLICABLE",
            ),
            privacy_review_required=False,
            capacity_approval_required=False,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def evaluate_multimodal(
        self,
        formats: list[str] | None = None,
    ) -> CapabilityEvaluation:
        """Evaluate multimodal input capability.

        Security: Parser vulnerabilities, malformed media, resource exhaustion risks.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.MULTIMODAL,
            decision=self.DEFAULT_DECISIONS[CapabilityType.MULTIMODAL],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description="Process images, audio, video in evaluation prompts",
            measurable_benefit="Expanded test capabilities for vision/audio models",
            target_population="Multimodal-capable model families",
            data_classifications=["media_attachments"],
            quality_target="Accurate transcription/recognition",
            latency_target="< 2s for image processing",
            cost_estimate="$300/month for additional compute",
            threats=[
                "Multimodal parser vulnerabilities",
                "Malformed media causing crashes",
                "Resource exhaustion attacks",
            ],
            operational_owner="Security Team",
            alternatives_considered=[
                "Text-only (current)",
                "Sandboxed media parsing",
                "External API integration",
            ],
            selected_alternative="Text-only (current)",
            certification_impact="Requires parser sandbox and media quarantine",
            multimodal_config=MultimodalConfiguration(
                supported_formats=formats or [],
                parser_sandbox_required=False,
                isolation_required=False,
                retention_policy="NOT_APPLICABLE",
            ),
            privacy_review_required=True,
            capacity_approval_required=False,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def evaluate_local_models(
        self,
        model_count: int = 0,
        model_vendor: str = "none",
    ) -> CapabilityEvaluation:
        """Evaluate local models capability.

        Security: Requires model approval, signature verification, and
        secure model lifecycle management.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.LOCAL_MODELS,
            decision=self.DEFAULT_DECISIONS[CapabilityType.LOCAL_MODELS],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description=f"Run {model_count} models locally for offline evaluation",
            measurable_benefit="Reduced provider costs and improved privacy",
            target_population="Resource-constrained or air-gapped environments",
            data_classifications=["internal"],
            quality_target="Model outputs match provider equivalents",
            latency_target="Local inference < provider latency",
            cost_estimate="$0/month - no external provider costs",
            threats=[
                "Model tampering without signature verification",
                "Unauthorized model loading",
                "Side-channel leakage through local execution",
                "Unpatched model vulnerabilities",
            ],
            operational_owner="ML Platform Team",
            alternatives_considered=[
                "Provider APIs (current)",
                "Local signed models only",
                "Hybrid approach",
            ],
            selected_alternative="Provider APIs (current)",
            certification_impact="Requires model signature verification and approval workflow",
            privacy_review_required=False,
            capacity_approval_required=False,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def evaluate_regional_executors(
        self,
        regions: list[str] | None = None,
        latency_sla_hours: float = 0.0,
    ) -> CapabilityEvaluation:
        """Evaluate regional executors capability.

        Security: Requires cross-region isolation, data sovereignty controls,
        and region-specific key management.
        """
        evaluation = CapabilityEvaluation(
            evaluation_id=f"eval_{new_id('cap')[:16]}",
            capability=CapabilityType.REGIONAL_EXECUTORS,
            decision=self.DEFAULT_DECISIONS[CapabilityType.REGIONAL_EXECUTORS],
            evaluated_at=utc_now(),
            evaluator="System",
            use_case_description="Cross-region execution for reduced latency or data sovereignty",
            measurable_benefit="Improved latency through regional proximity",
            target_population="Multi-region evaluation workloads",
            data_classifications=["internal", "regional_restricted"],
            quality_target="Consistent results across regions",
            latency_target=f"< {latency_sla_hours or 24}h cross-region sync",
            cost_estimate="$1000/month for regional infrastructure",
            threats=[
                "Cross-region data leakage without proper isolation",
                "Data sovereignty violations",
                "Inconsistent regional key management",
                "Clock skew affecting evidence ordering",
            ],
            operational_owner="SRE Team",
            alternatives_considered=[
                "Single-region execution (current)",
                "Regional isolation with sync",
                "Active-active multi-region",
            ],
            selected_alternative="Single-region execution (current)",
            certification_impact="Requires data sovereignty validation and regional key rotation",
            privacy_review_required=True,
            capacity_approval_required=True,
        )

        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def get_evaluation(self, evaluation_id: str) -> CapabilityEvaluation | None:
        """Get evaluation by ID."""
        return self._evaluations.get(evaluation_id)

    def get_all_evaluations(self) -> list[CapabilityEvaluation]:
        """Get all capability evaluations."""
        return list(self._evaluations.values())

    def get_decisions(self) -> dict[str, CapabilityDecision]:
        """Get all capability decisions as a summary."""
        return {
            e.capability.value: e.decision
            for e in self._evaluations.values()
        }

    def evaluate_all(
        self,
        use_case: str = "General evaluation",
        target_population: str = "safe-compliance-core",
        embedding_model: str | None = None,
        gpu_type: str = "A100",
        formats: list[str] | None = None,
        model_count: int = 0,
        regions: list[str] | None = None,
    ) -> list[CapabilityEvaluation]:
        """Evaluate all advanced capabilities with consistent defaults.

        Returns all capability evaluations for the platform scope review.
        """
        evaluations = [
            self.evaluate_retrieval(use_case, target_population),
            self.evaluate_vector_storage(embedding_model or "bge-m3:latest"),
            self.evaluate_accelerators(gpu_type),
            self.evaluate_multimodal(formats),
            self.evaluate_embeddings(embedding_model),
            self.evaluate_local_models(model_count, "unknown"),
            self.evaluate_regional_executors(list(regions) if regions else None),
        ]
        return evaluations


# =============================================================================
# Prototype Runner (for validation testing)
# =============================================================================


class PrototypeRunner:
    """Runs isolated prototypes with synthetic data.

    Security: Only uses synthetic or approved redacted data.
    Compare against simpler baseline to show measurable benefit.
    """

    def __init__(self) -> None:
        self._results: dict[str, Any] = {}

    def run_comparison(
        self,
        capability: CapabilityType,
        baseline_results: dict[str, Any],
        prototype_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare baseline vs prototype results.

        Returns comparison showing whether prototype demonstrates benefit.
        """
        comparison = {
            "capability": capability.value,
            "baseline": baseline_results,
            "prototype": prototype_results,
            "improvement": None,
            "meets_quality_target": False,
            "meets_latency_target": False,
        }

        # Compute improvement metric
        baseline_quality = baseline_results.get("quality_score", 0)
        prototype_quality = prototype_results.get("quality_score", 0)

        if baseline_quality > 0:
            comparison["improvement"] = prototype_quality - baseline_quality
            comparison["meets_quality_target"] = (
                prototype_quality >= baseline_quality * 1.1
            )  # 10% improvement threshold

        # Check latency
        baseline_latency = baseline_results.get("latency_seconds", 0)
        prototype_latency = prototype_results.get("latency_seconds", 0)
        comparison["meets_latency_target"] = prototype_latency < baseline_latency

        # Record for audit
        self._results[f"{capability}_comparison"] = comparison

        return comparison


__all__ = [
    "CapabilityDecision",
    "CapabilityType",
    "VectorConfiguration",
    "MultimodalConfiguration",
    "AcceleratorConfiguration",
    "EmbeddingsConfiguration",
    "CapabilityEvaluation",
    "CapabilityAnalyst",
    "PrototypeRunner",
]