"""Sanitized evidence envelopes for private production verification.

The private deployment performs probes against its real identities, endpoints,
certificates, stores, providers, and network policy. This public module accepts
only bounded outcomes and non-reversible fingerprints. It rejects URLs, IP
addresses, hostnames, credentials, tokens, certificate bodies, and free-form
logs so private operational facts cannot leak into public artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

EvidenceStatus = Literal["passed", "failed", "blocked", "not_run"]

_REQUIRED_CHECKS = frozenset({
    "oidc.discovery",
    "oidc.signature",
    "oidc.audience",
    "oidc.expiry",
    "oidc.role_denial",
    "tls.protocol",
    "tls.hostname",
    "tls.chain",
    "database.connectivity",
    "database.tls",
    "database.authorization",
    "redis.connectivity",
    "redis.authentication",
    "provider.allowed_destination",
    "provider.denied_destination",
    "network.only_proxy_ingress",
    "network.egress_default_deny",
    "network.metadata_denied",
    "container.readiness",
    "container.non_root",
    "container.read_only_root",
})
_CHECK_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_FINGERPRINT = re.compile(r"^[a-f0-9]{64}$")
_SAFE_REASON = re.compile(r"^[A-Za-z0-9 _.,:()/-]{0,240}$")
_FORBIDDEN_TEXT = re.compile(
    r"(?i)(https?://|\b(?:\d{1,3}\.){3}\d{1,3}\b|bearer\s|password|secret|token|"
    r"private[_ -]?key|begin certificate|@|\\\\|/[a-z0-9_.-]+/[a-z0-9_.-]+)"
)


@dataclass(frozen=True, slots=True)
class RuntimeCheck:
    check_id: str
    status: EvidenceStatus
    control_version: str
    evidence_sha256: str | None = None
    safe_reason: str = ""

    def validate(self) -> None:
        if not _CHECK_ID.fullmatch(self.check_id):
            raise ValueError("invalid runtime check identifier")
        if self.status not in {"passed", "failed", "blocked", "not_run"}:
            raise ValueError("invalid runtime check status")
        if not _CHECK_ID.fullmatch(self.control_version):
            raise ValueError("invalid control version")
        if self.evidence_sha256 is not None and not _FINGERPRINT.fullmatch(
            self.evidence_sha256
        ):
            raise ValueError("evidence fingerprint must be lowercase SHA-256")
        if not _SAFE_REASON.fullmatch(self.safe_reason):
            raise ValueError("safe_reason contains unsupported characters or is too long")
        if _FORBIDDEN_TEXT.search(self.safe_reason):
            raise ValueError("safe_reason appears to contain private operational material")
        if self.status == "passed" and self.evidence_sha256 is None:
            raise ValueError("passed checks require an evidence fingerprint")


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceEnvelope:
    schema_version: str
    source_commit: str
    environment_class: Literal["isolated", "staging", "production"]
    checks: tuple[RuntimeCheck, ...]
    bundle_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_commit": self.source_commit,
            "environment_class": self.environment_class,
            "checks": [asdict(check) for check in self.checks],
            "bundle_sha256": self.bundle_sha256,
        }

    def write_json(self, destination: str | Path) -> None:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _canonical_checks(checks: Iterable[RuntimeCheck]) -> tuple[RuntimeCheck, ...]:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    if len({item.check_id for item in ordered}) != len(ordered):
        raise ValueError("runtime check identifiers must be unique")
    for check in ordered:
        check.validate()
    return ordered


def _bundle_hash(
    source_commit: str,
    environment_class: str,
    checks: tuple[RuntimeCheck, ...],
) -> str:
    canonical = json.dumps(
        {
            "source_commit": source_commit,
            "environment_class": environment_class,
            "checks": [asdict(check) for check in checks],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_runtime_evidence(
    *,
    source_commit: str,
    environment_class: Literal["isolated", "staging", "production"],
    checks: Iterable[RuntimeCheck],
    require_complete: bool = False,
) -> RuntimeEvidenceEnvelope:
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("source_commit must be a full lowercase Git SHA-1")
    ordered = _canonical_checks(checks)
    if require_complete:
        observed = {check.check_id for check in ordered}
        missing = sorted(_REQUIRED_CHECKS - observed)
        if missing:
            raise ValueError("missing required runtime checks: " + ", ".join(missing))
        incomplete = [
            check.check_id for check in ordered if check.status != "passed"
        ]
        if incomplete:
            raise RuntimeError(
                "runtime evidence is not complete: " + ", ".join(incomplete)
            )
    return RuntimeEvidenceEnvelope(
        schema_version="we3.runtime_evidence.v1",
        source_commit=source_commit,
        environment_class=environment_class,
        checks=ordered,
        bundle_sha256=_bundle_hash(source_commit, environment_class, ordered),
    )


def verify_runtime_evidence(payload: dict[str, object]) -> RuntimeEvidenceEnvelope:
    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        raise ValueError("runtime evidence checks must be a list")
    checks = tuple(RuntimeCheck(**item) for item in raw_checks if isinstance(item, dict))
    envelope = build_runtime_evidence(
        source_commit=str(payload.get("source_commit", "")),
        environment_class=str(payload.get("environment_class", "")),  # type: ignore[arg-type]
        checks=checks,
    )
    if payload.get("schema_version") != envelope.schema_version:
        raise ValueError("unsupported runtime evidence schema")
    if payload.get("bundle_sha256") != envelope.bundle_sha256:
        raise ValueError("runtime evidence bundle hash mismatch")
    return envelope


__all__ = [
    "RuntimeCheck",
    "RuntimeEvidenceEnvelope",
    "build_runtime_evidence",
    "verify_runtime_evidence",
]
