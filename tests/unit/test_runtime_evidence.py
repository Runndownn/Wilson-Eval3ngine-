from __future__ import annotations

import hashlib

import pytest

from wilson_eval3ngine.assurance.runtime_evidence import (
    RuntimeCheck,
    build_runtime_evidence,
    verify_runtime_evidence,
)

COMMIT = "a" * 40
FINGERPRINT = hashlib.sha256(b"private evidence retained outside repository").hexdigest()


def test_runtime_evidence_is_deterministic_and_order_independent() -> None:
    checks = [
        RuntimeCheck("tls.chain", "passed", "tls.v1", FINGERPRINT),
        RuntimeCheck("oidc.signature", "passed", "oidc.v1", FINGERPRINT),
    ]
    first = build_runtime_evidence(
        source_commit=COMMIT,
        environment_class="staging",
        checks=checks,
    )
    second = build_runtime_evidence(
        source_commit=COMMIT,
        environment_class="staging",
        checks=reversed(checks),
    )
    assert first.bundle_sha256 == second.bundle_sha256
    assert [check.check_id for check in first.checks] == ["oidc.signature", "tls.chain"]
    assert verify_runtime_evidence(first.to_dict()) == first


def test_passed_check_requires_non_reversible_fingerprint() -> None:
    with pytest.raises(ValueError, match="require an evidence fingerprint"):
        build_runtime_evidence(
            source_commit=COMMIT,
            environment_class="isolated",
            checks=[RuntimeCheck("tls.chain", "passed", "tls.v1")],
        )


def test_free_form_operational_material_is_rejected() -> None:
    for reason in {
        "https://internal.example",
        "server 10.0.0.8",
        "Bearer abc",
        "password failed",
        "user@example.invalid",
    }:
        with pytest.raises(ValueError, match="canonical reason code"):
            build_runtime_evidence(
                source_commit=COMMIT,
                environment_class="production",
                checks=[
                    RuntimeCheck(
                        "network.metadata_denied",
                        "blocked",
                        "network.v1",
                        safe_reason=reason,
                    )
                ],
            )


def test_reason_code_is_allowed_without_private_detail() -> None:
    envelope = build_runtime_evidence(
        source_commit=COMMIT,
        environment_class="staging",
        checks=[
            RuntimeCheck(
                "database.tls",
                "blocked",
                "database.v1",
                safe_reason="dependency_unavailable",
            )
        ],
    )
    assert envelope.checks[0].safe_reason == "dependency_unavailable"


def test_bundle_tampering_is_detected() -> None:
    envelope = build_runtime_evidence(
        source_commit=COMMIT,
        environment_class="isolated",
        checks=[RuntimeCheck("tls.chain", "passed", "tls.v1", FINGERPRINT)],
    ).to_dict()
    envelope["bundle_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="bundle hash mismatch"):
        verify_runtime_evidence(envelope)


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValueError, match="environment_class"):
        build_runtime_evidence(
            source_commit=COMMIT,
            environment_class="private",  # type: ignore[arg-type]
            checks=[],
        )
