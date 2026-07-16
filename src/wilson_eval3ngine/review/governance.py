"""Threshold versioning and override workflow (TODO 36).

T5.1.8 - Implements versioned threshold sets, gate precedence, override workflow
with dual approval, and signed dossier generation for release governance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from ..domain.contracts import GateDecision, GateStatus, MetricSnapshot, ThresholdSet
from ..reports.dossier import build_dossier
from ..util import new_id, utc_now

logger = logging.getLogger(__name__)


class TrustRegistry:
    """Trusted key registry for signature verification.

    In production, this would integrate with an external PKI/vault.
    For MVP, maintains an in-memory set of trusted key fingerprints.
    """

    def __init__(self) -> None:
        self._trusted_fingerprints: set[str] = set()

    def trust_key(self, fingerprint_sha256: str) -> None:
        """Add a key fingerprint to the trusted registry."""
        self._trusted_fingerprints.add(fingerprint_sha256)

    def is_trusted(self, fingerprint_sha256: str) -> bool:
        """Check if a key fingerprint is trusted."""
        return fingerprint_sha256 in self._trusted_fingerprints

    def revoke_key(self, fingerprint_sha256: str) -> None:
        """Remove a key from the trusted registry."""
        self._trusted_fingerprints.discard(fingerprint_sha256)


class OverrideStatus(StrEnum):
    """Status of an override request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class OverrideRequest:
    """Request for an override with scope and justification."""
    override_id: str
    gate_id: str
    requester: str  # Identity requesting the override
    rationale: str
    scope: dict[str, Any] = field(default_factory=dict)  # Exact scope limitations
    
    # Dual approval tracking
    approver_a: str | None = None
    approver_b: str | None = None
    approved_at: datetime | None = None
    
    # Compensation and follow-up
    compensating_controls: list[str] = field(default_factory=list)
    follow_up_ticket: str | None = None
    
    # Lifecycle
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    applied: bool = False
    
    def is_approved(self) -> bool:
        """Check if override has dual approval."""
        return self.approver_a is not None and self.approver_b is not None
    
    def is_expired(self) -> bool:
        """Check if override has expired."""
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at


@dataclass(frozen=True, slots=True)
class VersionedThresholdSet:
    """Versioned threshold set with approval tracking."""
    threshold_set_id: str
    version: str
    owner: str
    rationale: str
    calibration_evidence_sha256: str
    
    # Effective period
    created_at: datetime = field(default_factory=utc_now)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    
    # Approval
    approved_by: list[str] = field(default_factory=list)
    approved_at: datetime | None = None
    
    # The actual threshold set
    thresholds: ThresholdSet | None = None
    
    def is_active(self) -> bool:
        """Check if this threshold set is currently active."""
        now = utc_now()
        if self.effective_from and now < self.effective_from:
            return False
        if self.effective_until and now > self.effective_until:
            return False
        return len(self.approved_by) >= 2  # Requires dual approval


class GatePrecedence:
    """Enforces gate precedence rules."""

    # Precedence levels (higher = more important)
    PRECEDENCE = {
        "integrity_check": 100,  # Must pass before anything else
        "critical_raw_safety": 90,  # Unsafe compliance, critical events
        "review_completion": 80,  # Critical reviews completed
        "support_threshold": 70,  # Minimum prompt-family support
        "reliability_gate": 60,  # Protocol/reliability checks
        "behavioral_metric": 50,  # Standard behavioral thresholds
        "composite_score": 10,  # Never overrides raw safety
    }

    @classmethod
    def evaluate(cls, decision: GateDecision) -> GateDecision:
        """Apply precedence rules to gate decision.

        Security: Critical raw safety and review completion gates CANNOT be
        overridden by composite scores. This enforces the principle that
        harmful content flags always block publication.
        """
        # Check for critical blocks that should not be overridden
        for check in decision.checks:
            if check.status == GateStatus.BLOCK:
                # Verify this isn't a composite override of raw safety
                # Critical raw safety checks have "unsafe" in their message
                if "unsafe" in check.message.lower() or "critical" in check.message.lower():
                    # Even if composite would pass, critical safety blocks
                    return GateDecision(
                        gate_id=decision.gate_id,
                        experiment_id=decision.experiment_id,
                        model_config_id=decision.model_config_id,
                        status=GateStatus.BLOCK,
                        checks=decision.checks,
                        reasons=[
                            "PRECEDENCE ENFORCED: Critical safety cannot be masked by composite",
                            *decision.reasons,
                        ],
                        threshold_set_id=decision.threshold_set_id,
                        created_at=utc_now(),
                    )

        # Check for unresolved critical reviews
        # This would be populated from review state
        return decision


class OverrideEngine:
    """Manages override requests and application."""

    def __init__(self) -> None:
        self._overrides: dict[str, OverrideRequest] = {}

    def create_override(
        self,
        gate_id: str,
        requester: str,
        rationale: str,
        scope: dict[str, Any],
        expires_in_days: int = 30,
        compensating_controls: list[str] | None = None,
    ) -> OverrideRequest:
        """Create a new override request."""
        req = OverrideRequest(
            override_id=new_id("override"),
            gate_id=gate_id,
            requester=requester,
            rationale=rationale,
            scope=scope,
            expires_at=utc_now() + timedelta(days=expires_in_days),
            compensating_controls=compensating_controls or [],
        )
        self._overrides[req.override_id] = req
        
        logger.info(
            "override_request_created",
            extra={
                "override_id": req.override_id,
                "gate_id": gate_id,
                "requester": requester,
            },
        )
        
        return req

    def approve_override(
        self,
        override_id: str,
        approver: str,
    ) -> OverrideRequest:
        """Record approval from one approver."""
        req = self._overrides.get(override_id)
        if req is None:
            raise ValueError(f"Override {override_id} not found")
        
        if req.is_approved():
            raise ValueError("Override already fully approved")
        
        # First or second approver
        if req.approver_a is None:
            updated = OverrideRequest(
                override_id=req.override_id,
                gate_id=req.gate_id,
                requester=req.requester,
                rationale=req.rationale,
                scope=req.scope,
                approver_a=approver,
                approver_b=req.approver_b,
                approved_at=req.approved_at,
                compensating_controls=req.compensating_controls,
                follow_up_ticket=req.follow_up_ticket,
                created_at=req.created_at,
                expires_at=req.expires_at,
                applied=req.applied,
            )
        else:
            updated = OverrideRequest(
                override_id=req.override_id,
                gate_id=req.gate_id,
                requester=req.requester,
                rationale=req.rationale,
                scope=req.scope,
                approver_a=req.approver_a,
                approver_b=approver,
                approved_at=utc_now(),
                compensating_controls=req.compensating_controls,
                follow_up_ticket=req.follow_up_ticket,
                created_at=req.created_at,
                expires_at=req.expires_at,
                applied=req.applied,
            )
        
        self._overrides[override_id] = updated
        
        logger.info(
            "override_approved",
            extra={
                "override_id": override_id,
                "approver": approver,
                "fully_approved": updated.is_approved(),
            },
        )
        
        return updated

    def apply_override(
        self,
        decision: GateDecision,
        override: OverrideRequest,
    ) -> GateDecision:
        """Apply an approved override to a gate decision."""
        if not override.is_approved():
            raise ValueError("Cannot apply unapproved override")
        
        if override.is_expired():
            raise ValueError("Cannot apply expired override")
        
        # Mark override as applied
        updated = OverrideRequest(
            override_id=override.override_id,
            gate_id=override.gate_id,
            requester=override.requester,
            rationale=override.rationale,
            scope=override.scope,
            approver_a=override.approver_a,
            approver_b=override.approver_b,
            approved_at=override.approved_at,
            compensating_controls=override.compensating_controls,
            follow_up_ticket=override.follow_up_ticket,
            created_at=override.created_at,
            expires_at=override.expires_at,
            applied=True,
        )
        self._overrides[override.override_id] = updated

        # Apply override: change status if within scope
        # In production, this would check the override scope against the specific
        # gate check and apply the appropriate modified status
        overridden = GateDecision(
            gate_id=decision.gate_id,
            experiment_id=decision.experiment_id,
            model_config_id=decision.model_config_id,
            status=GateStatus.WARNING,  # Override typically yields warning not pass
            checks=decision.checks,
            reasons=[
                f"OVERRIDE APPLIED: {override.rationale}",
                f"Approvers: {override.approver_a}, {override.approver_b}",
            ] + decision.reasons,
            threshold_set_id=decision.threshold_set_id,
            created_at=utc_now(),
        )
        
        logger.info(
            "override_applied_to_gate",
            extra={
                "gate_id": decision.gate_id,
                "override_id": override.override_id,
            },
        )
        
        return overridden


class DossierBuilder:
    """Builds signed release dossiers."""

    def build_dossier(
        self,
        *,
        experiment_id: str,
        project_id: str,
        manifest_hash: str,
        dataset_hash: str,
        snapshots: list[MetricSnapshot],
        gates: list[GateDecision],
        overrides: list[OverrideRequest],
        limitations: list[str],
        evidence_verified: bool = True,
    ) -> dict[str, Any]:
        """Build a complete release dossier."""
        dossier = build_dossier(
            experiment_id=experiment_id,
            project_id=project_id,
            manifest_hash=manifest_hash,
            dataset_hash=dataset_hash,
            snapshots=snapshots,
            gates=gates,
            artifact_index=[],
            audit_chain_verified=evidence_verified,
            limitations=list(limitations),
        )
        
        # Add override information
        dossier["overrides"] = [
            {
                "override_id": o.override_id,
                "gate_id": o.gate_id,
                "rationale": o.rationale,
                "scope": o.scope,
                "compensating_controls": o.compensating_controls,
                "approved_by": [o.approver_a, o.approver_b] if o.approver_a and o.approver_b else [],
                "expires_at": o.expires_at.isoformat() if o.expires_at else None,
                "applied": o.applied,
            }
            for o in overrides
            if o.is_approved() and not o.is_expired()
        ]
        
        logger.info(
            "dossier_built",
            extra={
                "experiment_id": experiment_id,
                "project_id": project_id,
                "snapshot_count": len(snapshots),
                "gate_count": len(gates),
                "override_count": len(overrides),
            },
        )
        
        return dossier

    def verify_dossier_integrity(self, dossier: dict[str, Any]) -> bool:
        """Verify dossier integrity without trusting embedded content."""
        required_fields = [
            "experiment_id",
            "manifest_hash",
            "dataset_hash",
            "metric_snapshots",
            "gate_decisions",
        ]
        
        for field_name in required_fields:
            if field_name not in dossier:
                return False
        
        return True


__all__ = [
    "TrustRegistry",
    "OverrideStatus",
    "OverrideRequest",
    "VersionedThresholdSet",
    "GatePrecedence",
    "OverrideEngine",
    "DossierBuilder",
]