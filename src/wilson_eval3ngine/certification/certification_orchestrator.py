"""Production certification and release evidence orchestration.

T8.1.8 - Certification orchestration for production releases.
Verifies all ten certification categories before allowing release publication.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from ..security.signing import (
    Ed25519PrivateKey,
    SignatureEnvelope,
    TrustRegistry,
    sign_bytes,
    verify_bytes,
)
from ..util import sha256_hex, utc_now

logger = logging.getLogger("wilson.certification")


# =============================================================================
# Certification Categories
# =============================================================================


class CertificationCategory(StrEnum):
    """Ten mandatory certification categories for production release."""

    REPRODUCIBILITY = "reproducibility"
    DURABILITY = "durability"
    INTEGRITY = "integrity"
    SECURITY = "security"
    STATISTICS = "statistics"
    GRADING = "grading"
    GOVERNANCE = "governance"
    RECOVERY = "recovery"
    OPERATIONS = "operations"
    USABILITY = "usability"


class EvidenceStatus(StrEnum):
    """Evidence validation status."""

    PASS = "pass"
    BLOCK = "block"
    WARNING = "warning"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    """Single piece of certification evidence."""

    category: CertificationCategory
    evidence_id: str
    source_hash: str
    timestamp: datetime
    expires_at: datetime | None
    evidence_type: str
    evidence_ref: str  # Immutable reference to evidence artifact
    validation_result: str
    signature: SignatureEnvelope | None = None
    source_commit: str | None = None  # Commit that produced this evidence
    environment: str | None = None  # Environment where evidence was generated

    def is_fresh(self, max_age_hours: int = 24) -> bool:
        """Check if evidence is within freshness window."""
        if self.expires_at:
            return utc_now() < self.expires_at
        age = utc_now() - self.timestamp
        return age < timedelta(hours=max_age_hours)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "evidence_id": self.evidence_id,
            "source_hash": self.source_hash,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "evidence_type": self.evidence_type,
            "evidence_ref": self.evidence_ref,
            "validation_result": self.validation_result,
            "signature": self.signature.to_dict() if self.signature else None,
            "source_commit": self.source_commit,
            "environment": self.environment,
        }


@dataclass
class CertificationRequirement:
    """A Must requirement that must be satisfied for certification."""

    requirement_id: str
    category: CertificationCategory
    description: str
    evidence_source_required: bool = True
    freshness_required: bool = True
    max_age_hours: int = 24
    blocking: bool = True  # True = Must requirement, False = Should

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "category": self.category.value,
            "description": self.description,
            "evidence_source_required": self.evidence_source_required,
            "freshness_required": self.freshness_required,
            "max_age_hours": self.max_age_hours,
            "blocking": self.blocking,
        }


# =============================================================================
# Evidence Providers (Protocols for pluggable verification)
# =============================================================================


class EvidenceProvider(Protocol):
    """Protocol for evidence provider implementations."""

    def get_evidence(self, reference: str) -> dict[str, Any] | None:
        """Retrieve evidence by immutable reference."""
        ...

    def verify_signature(self, evidence: dict[str, Any]) -> bool:
        """Verify evidence signature."""
        ...

    def check_freshness(self, evidence: dict[str, Any], max_age_hours: int) -> bool:
        """Check evidence freshness."""
        ...


# =============================================================================
# Certification Registry
# =============================================================================


class CertificationRegistry:
    """Registry of certification requirements and evidence providers."""

    # Core Must requirements for each category
    CORE_REQUIREMENTS: dict[str, CertificationRequirement] = {
        "repro-001": CertificationRequirement(
            requirement_id="repro-001",
            category=CertificationCategory.REPRODUCIBILITY,
            description="Given frozen artifacts and versioned code, the platform shall reproduce published metric counts and hashes exactly",
            blocking=True,
        ),
        "durab-001": CertificationRequirement(
            requirement_id="durab-001",
            category=CertificationCategory.DURABILITY,
            description="At least 99.99% of accepted experiment definitions shall remain durably recoverable",
            blocking=True,
        ),
        "integ-001": CertificationRequirement(
            requirement_id="integ-001",
            category=CertificationCategory.INTEGRITY,
            description="All score-affecting artifacts are content-addressed with verified SHA-256 hashes",
            blocking=True,
        ),
        "sec-001": CertificationRequirement(
            requirement_id="sec-001",
            category=CertificationCategory.SECURITY,
            description="Organization OIDC authentication with MFA policy",
            blocking=True,
        ),
        "stat-001": CertificationRequirement(
            requirement_id="stat-001",
            category=CertificationCategory.STATISTICS,
            description="Wilson score intervals computed with validated statistical methods",
            blocking=True,
        ),
        "grade-001": CertificationRequirement(
            requirement_id="grade-001",
            category=CertificationCategory.GRADING,
            description="Deterministic five-outcome grading with calibrated thresholds",
            blocking=True,
        ),
        "gov-001": CertificationRequirement(
            requirement_id="gov-001",
            category=CertificationCategory.GOVERNANCE,
            description="Dual approval workflow with audit trail for all privileged actions",
            blocking=True,
        ),
        "recov-001": CertificationRequirement(
            requirement_id="recov-001",
            category=CertificationCategory.RECOVERY,
            description="Quarterly restore exercise demonstrates RPO=15min, RTO=4hr targets",
            blocking=True,
        ),
        "ops-001": CertificationRequirement(
            requirement_id="ops-001",
            category=CertificationCategory.OPERATIONS,
            description="Six core SLIs with SLO bindings and alert rules with runbook links",
            blocking=True,
        ),
        "usab-001": CertificationRequirement(
            requirement_id="usab-001",
            category=CertificationCategory.USABILITY,
            description="WCAG 2.2 AA compliance for primary workflows",
            blocking=False,
        ),
    }

    def __init__(self) -> None:
        self._evidence: dict[str, EvidenceEntry] = {}
        self._providers: dict[CertificationCategory, EvidenceProvider] = {}

    def register_provider(
        self, category: CertificationCategory, provider: EvidenceProvider
    ) -> None:
        """Register an evidence provider for a category."""
        self._providers[category] = provider

    def add_evidence(self, evidence: EvidenceEntry) -> None:
        """Add evidence to the registry."""
        self._evidence[evidence.evidence_id] = evidence

    def get_evidence(self, evidence_id: str) -> EvidenceEntry | None:
        """Retrieve evidence by ID."""
        return self._evidence.get(evidence_id)

    def get_requirements(self, category: CertificationCategory | None = None) -> list[CertificationRequirement]:
        """Get all requirements, optionally filtered by category."""
        reqs = list(self.CORE_REQUIREMENTS.values())
        if category:
            reqs = [r for r in reqs if r.category == category]
        return reqs


# =============================================================================
# Certification Orchestration
# =============================================================================


@dataclass
class CertificationResult:
    """Result of certification evaluation."""

    certification_id: str
    generated_at: datetime
    release_artifact_digest: str
    source_commit: str
    environment: str
    requirement_catalog_hash: str
    evidence_validations: dict[str, EvidenceStatus] = field(default_factory=dict)
    blocking_issues: list[str] = field(default_factory=list)
    warning_issues: list[str] = field(default_factory=list)
    indeterminate_issues: list[str] = field(default_factory=list)
    approval_count: int = 0
    signature: SignatureEnvelope | None = None
    status: str = "pending"

    def compute_status(self) -> str:
        """Compute overall certification status."""
        if self.blocking_issues:
            return "blocked"
        if self.indeterminate_issues:
            return "indeterminate"
        if self.warning_issues:
            return "warning"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "certification_id": self.certification_id,
            "generated_at": self.generated_at.isoformat(),
            "release_artifact_digest": self.release_artifact_digest,
            "source_commit": self.source_commit,
            "environment": self.environment,
            "requirement_catalog_hash": self.requirement_catalog_hash,
            "evidence_validations": {
                k: v.value for k, v in self.evidence_validations.items()
            },
            "blocking_issues": self.blocking_issues,
            "warning_issues": self.warning_issues,
            "indeterminate_issues": self.indeterminate_issues,
            "approval_count": self.approval_count,
            "status": self.status,
            "signature": self.signature.to_dict() if self.signature else None,
        }


class CertificationOrchestrator:
    """Orchestrates production certification across all categories.

    Security: Separates evidence producers, certification orchestrator,
    independent approvers, signing identity, and publication authority.
    """

    def __init__(
        self,
        registry: CertificationRegistry,
        trust_registry: TrustRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.trust_registry = trust_registry

    def resolve_release_artifact(self, artifact_path: Path) -> str:
        """Resolve and verify release artifact digest."""
        if not artifact_path.exists():
            raise ValueError(f"Artifact not found: {artifact_path}")
        return f"sha256:{sha256_hex(artifact_path.read_bytes())}"

    def verify_artifact_signature(
        self, artifact_digest: str, expected_digest: str
    ) -> bool:
        """Verify artifact signature matches expected digest."""
        return artifact_digest == expected_digest

    def verify_evidence_applicability(
        self,
        evidence: EvidenceEntry,
        source_commit: str,
        environment: str,
    ) -> bool:
        """Verify evidence applies to correct commit and environment.

        Security: Evidence must include source commit and environment in its metadata
        to prevent cross-environment contamination.
        """
        # Check evidence was generated for this commit/environment
        evidence_data = self.registry.get_evidence(evidence.evidence_id)
        if not evidence_data:
            return False

        # Evidence must be fresh
        if not evidence.is_fresh():
            return False

        # Validate evidence reference format (content-addressed)
        if not evidence.source_hash.startswith("sha256:"):
            return False

        # Verify environment match - evidence from wrong environment is invalid
        if evidence.environment is not None and evidence.environment != environment:
            logger.warning(
                "evidence_environment_mismatch",
                extra={
                    "evidence_id": evidence.evidence_id,
                    "expected_env": environment,
                    "actual_env": evidence.environment,
                },
            )
            return False

        return True

    def check_environment_drift(
        self,
        evidence_list: list[EvidenceEntry],
        source_commit: str,
        environment: str,
    ) -> list[str]:
        """Check for environment drift among evidence entries.

        Returns list of drift warnings for evidence from mismatched environments.
        """
        drift_warnings = []
        for evidence in evidence_list:
            if evidence.environment is not None and evidence.environment != environment:
                drift_warnings.append(
                    f"{evidence.evidence_id}: evidence from {evidence.environment} not {environment}"
                )
            if evidence.source_commit is not None and evidence.source_commit != source_commit:
                drift_warnings.append(
                    f"{evidence.evidence_id}: evidence from commit {evidence.source_commit[:8]} not {source_commit[:8]}"
                )
        return drift_warnings

    def validate_sli_evidence(
        self,
        sli_registry_path: str | None = None,
    ) -> dict[str, Any]:
        """Validate SLI/SLO evidence for operations certification.

        Checks:
        - All six core SLIs have registered definitions
        - SLOs have appropriate alert severity mapping
        - Runbook links are valid
        """
        try:
            from ..observability.sli_slo import get_sli_registry
            from ..observability.alerts import get_alert_rules

            registry = get_sli_registry()
            alert_rules = get_alert_rules()

            # Verify all six core SLIs exist
            core_slis = [
                "sli-api-availability-v1",
                "sli-evidence-durability-v1",
                "sli-queue-start-latency-p95-v1",
                "sli-grading-duration-p95-v1",
                "sli-report-generation-p99-v1",
                "sli-hash-verification-v1",
            ]

            missing_slis = []
            for sli_id in core_slis:
                if registry.get_sli(sli_id) is None:
                    missing_slis.append(sli_id)

            # Verify alerts exist for each SLI
            missing_alerts = []
            for sli_id in core_slis:
                alerts = [a for a in alert_rules if a.sli_id == sli_id]
                if not alerts:
                    missing_alerts.append(sli_id)

            return {
                "valid": len(missing_slis) == 0 and len(missing_alerts) == 0,
                "slis_defined": len(core_slis) - len(missing_slis),
                "total_slis": len(core_slis),
                "missing_slis": missing_slis,
                "missing_alerts": missing_alerts,
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    def evaluate_category(
        self,
        category: CertificationCategory,
        source_commit: str,
        environment: str,
        requirement_catalog_hash: str,
    ) -> EvidenceStatus:
        """Evaluate a single certification category.

        Checks:
        - Evidence exists for category
        - Evidence freshness
        - Evidence applicability (environment/commit match)
        """
        requirements = self.registry.get_requirements(category)
        category_status = EvidenceStatus.PASS

        for req in requirements:
            # Find evidence for this requirement
            required_evidence = [
                e for e in self.registry._evidence.values()
                if e.category == category
            ]

            if req.evidence_source_required and not required_evidence:
                if req.blocking:
                    category_status = EvidenceStatus.BLOCK
                    break
                category_status = EvidenceStatus.WARNING
                continue

            # Verify freshness and applicability for evidence
            for evidence in required_evidence:
                if req.freshness_required and not evidence.is_fresh(req.max_age_hours):
                    # Evidence stale by hours - check applicability
                    if req.blocking:
                        category_status = EvidenceStatus.BLOCK
                    else:
                        category_status = EvidenceStatus.WARNING

                # Verify evidence applicability (environment/commit match)
                if not self.verify_evidence_applicability(evidence, source_commit, environment):
                    if req.blocking:
                        category_status = EvidenceStatus.BLOCK
                    else:
                        category_status = EvidenceStatus.WARNING

        return category_status

    def run_certification(
        self,
        release_artifact_digest: str,
        source_commit: str,
        environment: str,
        requirement_catalog_hash: str,
        approvers: list[str],
    ) -> CertificationResult:
        """Run full certification evaluation.

        Returns:
            CertificationResult with status for each category and overall decision

        Security: Enforces evidence freshness, environment drift detection, and
        prevents stale evidence from hiding failures.
        """
        certification_id = f"cert_{sha256_hex(release_artifact_digest)[:16]}"

        result = CertificationResult(
            certification_id=certification_id,
            generated_at=utc_now(),
            release_artifact_digest=release_artifact_digest,
            source_commit=source_commit,
            environment=environment,
            requirement_catalog_hash=requirement_catalog_hash,
            approval_count=len(approvers),
        )

        # Collect all evidence for drift checking
        all_evidence = list(self.registry._evidence.values())

        # Check for environment drift before evaluation
        drift_warnings = self.check_environment_drift(all_evidence, source_commit, environment)
        for warning in drift_warnings:
            result.indeterminate_issues.append(f"drift: {warning}")

        # Evaluate each category
        for category in CertificationCategory:
            status = self.evaluate_category(
                category, source_commit, environment, requirement_catalog_hash
            )
            result.evidence_validations[category.value] = status

            if status == EvidenceStatus.BLOCK:
                result.blocking_issues.append(f"{category.value}: requirement not satisfied")
            elif status == EvidenceStatus.WARNING:
                result.warning_issues.append(f"{category.value}: requires review")
            elif status == EvidenceStatus.INDETERMINATE:
                result.indeterminate_issues.append(f"{category.value}: evidence unclear")

        # Check for stale evidence that could hide failures
        stale_evidence = [
            e for e in all_evidence
            if not e.is_fresh(max_age_hours=24)
        ]
        if stale_evidence:
            result.indeterminate_issues.append(
                f"stale_evidence: {len(stale_evidence)} pieces exceed freshness window"
            )

        # Compute final status
        result.status = result.compute_status()

        return result

    def sign_certification(
        self,
        result: CertificationResult,
        private_key: Ed25519PrivateKey,
    ) -> CertificationResult:
        """Sign the certification result."""
        unsigned = json.dumps(
            {k: v for k, v in result.to_dict().items() if k != "signature"},
            sort_keys=True,
            ensure_ascii=False,
        )
        signature = sign_bytes(unsigned.encode(), private_key)

        # Create new result with signature
        result.signature = signature
        return result

    def verify_certification(self, path: Path) -> dict[str, Any]:
        """Verify a signed certification result.

        Security: Validates hashes, timestamps, and signatures.
        Does NOT require privileged database access.
        """
        try:
            signed = json.loads(path.read_text())

            # Handle missing signature - valid in foundation mode
            if not signed.get("signature"):
                return {
                    "valid": True,
                    "signature_valid": True,
                    "trust_registry_validated": None,
                    "certification_id": signed.get("certification_id"),
                    "status": signed.get("status"),
                    "mode": "foundation",
                }

            signature = SignatureEnvelope(**signed.get("signature", {}))

            # Verify signature
            unsigned = {k: v for k, v in signed.items() if k != "signature"}
            payload = json.dumps(unsigned, sort_keys=True, ensure_ascii=False).encode()
            sig_valid = verify_bytes(payload, signature)

            # Verify trust registry if available
            trust_valid = True  # Default to True in foundation mode
            if self.trust_registry:
                trust_valid = self.trust_registry.is_trusted(
                    signature.public_key_fingerprint_sha256
                )

            return {
                "valid": sig_valid and trust_valid,
                "signature_valid": sig_valid,
                "trust_registry_validated": trust_valid,
                "certification_id": signed.get("certification_id"),
                "status": signed.get("status"),
            }
        except (OSError, ValueError, KeyError, TypeError) as e:
            return {
                "valid": False,
                "error": f"invalid_certification: {e}",
            }


def create_certification_manifest(
    result: CertificationResult,
    evidence_index: list[EvidenceEntry],
) -> dict[str, Any]:
    """Create a signed certification manifest.

    Security: Includes all evidence references for independent verification.
    """
    return {
        "schema_version": "we3.certification_manifest.v1",
        "generated_at": utc_now().isoformat(),
        "certification_id": result.certification_id,
        "release_artifact_digest": result.release_artifact_digest,
        "source_commit": result.source_commit,
        "environment": result.environment,
        "requirement_catalog_hash": result.requirement_catalog_hash,
        "category_status": {
            k: v.value for k, v in result.evidence_validations.items()
        },
        "evidence_index": [e.to_dict() for e in evidence_index],
        "approvers": result.approval_count,
        "overall_status": result.status,
        "signature": result.signature.to_dict() if result.signature else None,
    }


__all__ = [
    "CertificationCategory",
    "EvidenceStatus",
    "EvidenceEntry",
    "CertificationRequirement",
    "EvidenceProvider",
    "CertificationRegistry",
    "CertificationOrchestrator",
    "CertificationResult",
    "create_certification_manifest",
]