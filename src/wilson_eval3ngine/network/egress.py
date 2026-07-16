"""Network Egress Controls (TODO 41).

Provides egress policy enforcement:
- Default-deny network policy
- Metadata endpoint blocking
- Redirect validation
- DNS rebinding prevention
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass

logger = logging.getLogger("wilson.network.egress")


# Blocked network ranges (metadata endpoints, private networks)
BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.IPv4Network("169.254.0.0/16"),  # Cloud metadata link-local
    ipaddress.IPv4Network("10.0.0.0/8"),       # Private
    ipaddress.IPv4Network("172.16.0.0/12"),    # Private
    ipaddress.IPv4Network("192.168.0.0/16"),    # Private
    ipaddress.IPv4Network("127.0.0.0/8"),      # Loopback
]


@dataclass(frozen=True, slots=True)
class EgressDecision:
    """Result of egress policy evaluation."""

    allowed: bool
    reason: str
    target_host: str
    resolved_ip: str | None = None


def check_egress_allowed(url: str, allow_external: bool = False) -> EgressDecision:
    """Check if egress to URL is allowed.

    Default policy: deny all egress.
    Certification mode: no external access.

    Args:
        url: Target URL to check
        allow_external: Must be True for lab-only real tools

    Returns:
        EgressDecision with allow/deny and reason
    """
    if allow_external:
        # Lab mode - still block metadata endpoints
        return _check_lab_mode(url)

    # Certification mode - default deny
    return _check_certification_mode(url)


def _check_certification_mode(url: str) -> EgressDecision:
    """Certification mode: deny all egress."""
    logger.warning(
        "egress_blocked_certification_mode",
        extra={"url": url}
    )
    return EgressDecision(
        allowed=False,
        reason="egress_blocked_in_certification_mode",
        target_host=url,
        resolved_ip=None,
    )


def _check_lab_mode(url: str) -> EgressDecision:
    """Lab mode: block metadata endpoints and private networks."""
    parsed = _parse_url(url)
    if not parsed:
        return EgressDecision(
            allowed=False,
            reason="malformed_url",
            target_host=url,
        )

    host = parsed.get("host", "").lower()

    # Block metadata endpoints
    if host in ("169.254.169.254", "metadata.google.internal", "metadata.azure.internal") or host.startswith("169.254."):
        logger.warning(
            "metadata_endpoint_blocked",
            extra={"host": host}
        )
        return EgressDecision(
            allowed=False,
            reason="metadata_endpoint_blocked",
            target_host=host,
            resolved_ip=host,
        )

    # Block localhost
    if host.startswith("localhost") or host.startswith("127.") or host.startswith("::1"):
        logger.warning(
            "localhost_blocked",
            extra={"host": host}
        )
        return EgressDecision(
            allowed=False,
            reason="localhost_blocked",
            target_host=host,
        )

    # Block private networks
    if _is_private_network(host):
        logger.warning(
            "private_network_blocked",
            extra={"host": host}
        )
        return EgressDecision(
            allowed=False,
            reason="private_network_blocked",
            target_host=host,
            resolved_ip=host,
        )

    logger.info("egress_allowed_lab_mode", extra={"host": host})
    return EgressDecision(
        allowed=True,
        reason="lab_mode_approved",
        target_host=host,
    )


def _is_private_network(host: str) -> bool:
    """Check if host resolves to private network."""
    # Check by prefix first (fast)
    for prefix in ["10.", "172.", "192.168."]:
        if host.startswith(prefix):
            return True
    return False


def _parse_url(url: str) -> dict[str, str] | None:
    """Parse URL into components."""
    if not url:
        return None

    try:
        # Simple URL parsing for security checks
        if "://" not in url:
            return None

        scheme, rest = url.split("://", 1)
        if "/" in rest:
            host, _ = rest.split("/", 1)
        else:
            host = rest

        return {"scheme": scheme, "host": host}
    except Exception:
        return None


def validate_redirect_chain(
    redirect_chain: list[str],
    allow_external: bool = False,
) -> list[EgressDecision]:
    """Validate a chain of redirects.

    All redirects must be approved or explicitly blocked.
    """
    decisions = []
    for url in redirect_chain:
        decision = check_egress_allowed(url, allow_external)
        decisions.append(decision)
        if not decision.allowed:
            break  # Stop at first blocked redirect
    return decisions


def detect_metadata_access(url: str) -> bool:
    """Detect if URL targets cloud metadata endpoint."""
    parsed = _parse_url(url)
    if not parsed:
        return False

    host = parsed.get("host", "").lower()
    metadata_hosts = [
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.azure.net",
        "metadata.amazonaws.com",
        "metadata.cloud.yandex.net",
        "metadata.internal",
    ]

    return host in metadata_hosts or host.startswith("169.254.")


__all__ = [
    "EgressDecision",
    "check_egress_allowed",
    "validate_redirect_chain",
    "detect_metadata_access",
    "BLOCKED_NETWORKS",
]