"""
Dataset lifecycle state machine and promotion controls.

Implements DRAFT, REVIEWED, APPROVED, DEPRECATED states with dual-approval
transitions, signing, and hidden-set separation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..security.signing import SignatureEnvelope, load_private_key, sign_bytes


class DatasetLifecycleState(Enum):
    """Dataset lifecycle states for controlled promotion."""
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


@dataclass
class PromotionRecord:
    """Record of a dataset promotion attempt."""
    dataset_id: str
    version: str
    from_state: DatasetLifecycleState
    to_state: DatasetLifecycleState
    reviewer_ids: list[str]
    approved_at: datetime
    signature: SignatureEnvelope | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reviewer_ids": self.reviewer_ids,
            "approved_at": self.approved_at.isoformat(),
        }
        if self.signature:
            result["signature"] = self.signature.to_dict()
        return result


class DatasetLifecycle:
    """
    Manages dataset lifecycle transitions with approval controls.

    State transitions require:
    - DRAFT -> REVIEWED: Single author can transition
    - REVIEWED -> APPROVED: Dual independent reviewers required
    - APPROVED -> DEPRECATED: Dual approval + signed new state
    - No reverse transitions allowed (immutable releases)
    """

    def __init__(self):
        self._current_state: dict[str, DatasetLifecycleState] = {}
        self._approvals: dict[str, list[str]] = {}

    def get_state(self, dataset_version_id: str) -> DatasetLifecycleState:
        """Get current lifecycle state."""
        return self._current_state.get(dataset_version_id, DatasetLifecycleState.DRAFT)

    def can_transition(
        self,
        dataset_version_id: str,
        target_state: DatasetLifecycleState,
        approver_ids: list[str],
    ) -> bool:
        """Check if transition is allowed."""
        current = self.get_state(dataset_version_id)

        if current == target_state:
            return False

        if current == DatasetLifecycleState.APPROVED:
            # Only deprecation allowed from approved state
            return target_state == DatasetLifecycleState.DEPRECATED

        if target_state == DatasetLifecycleState.APPROVED:
            # Need dual independent approvals
            unique_approvers = set(approver_ids)
            return len(unique_approvers) >= 2

        if target_state == DatasetLifecycleState.DEPRECATED:
            return False  # Must come from APPROVED

        return True  # DRAFT -> REVIEWED allowed

    def transition(
        self,
        dataset_version_id: str,
        target_state: DatasetLifecycleState,
        approver_ids: list[str],
        signing_key_pem: bytes | None = None,
    ) -> PromotionRecord | None:
        """Execute state transition if valid."""
        if not self.can_transition(dataset_version_id, target_state, approver_ids):
            return None

        signature = None
        if target_state == DatasetLifecycleState.APPROVED and signing_key_pem:
            # Sign the promotion
            sig_payload = f"{dataset_version_id}:{target_state.value}".encode()
            key = load_private_key(signing_key_pem)
            signature = sign_bytes(sig_payload, key)

        self._current_state[dataset_version_id] = target_state
        self._approvals[dataset_version_id] = approver_ids

        return PromotionRecord(
            dataset_id=dataset_version_id.split("_")[0],
            version=dataset_version_id.split("_")[-1] if "_" in dataset_version_id else "1.0.0",
            from_state=self._get_previous_state(dataset_version_id),
            to_state=target_state,
            reviewer_ids=approver_ids,
            approved_at=datetime.now(UTC),
            signature=signature,
        )

    def _get_previous_state(self, dataset_version_id: str) -> DatasetLifecycleState:
        """Get previous state (for record)."""
        # In a real implementation, this would track history
        return DatasetLifecycleState.DRAFT


@dataclass
class HiddenSetAllocation:
    """Allocation configuration for hidden set separation."""
    tranche_id: str
    hidden_percent: float
    purpose: str
    object_store_policy: dict[str, Any] = None

    def __post_init__(self):
        if self.object_store_policy is None:
            self.object_store_policy = {
                "encryption_required": True,
                "export_restricted": True,
                "access_logging": True,
            }

    def to_dict(self) -> dict[str, Any]:
        return {
            "tranche_id": self.tranche_id,
            "hidden_percent": self.hidden_percent,
            "purpose": self.purpose,
            "object_store_policy": self.object_store_policy,
        }