"""Network controls for Wilson Eval3ngine.

T6.1.4 - Enforce egress controls and network policy.
"""

from .egress import (
    BLOCKED_NETWORKS,
    EgressDecision,
    check_egress_allowed,
    detect_metadata_access,
    validate_redirect_chain,
)

__all__ = [
    "EgressDecision",
    "BLOCKED_NETWORKS",
    "check_egress_allowed",
    "validate_redirect_chain",
    "detect_metadata_access",
]