from __future__ import annotations

import os
from pathlib import Path

import pytest

from wilson_eval3ngine.security.secrets_backend import (
    EnvironmentSecretBackend,
    MountedSecretBackend,
    SecretBackendError,
    SecretLease,
    build_secret_backend,
    validate_secret_name,
)


def test_production_rejects_environment_secret_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WE3_SECRET_BACKEND", "environment")
    with pytest.raises(SecretBackendError, match="external secret authority"):
        build_secret_backend(environment="production")


def test_mounted_secret_is_path_confined_and_permission_checked(tmp_path: Path) -> None:
    root = tmp_path / "secrets"
    root.mkdir(mode=0o700)
    value = root / "DATABASE_PASSWORD"
    value.write_bytes(b"correct-horse\n")
    value.chmod(0o600)

    backend = MountedSecretBackend(root)
    assert backend.read("DATABASE_PASSWORD") == b"correct-horse"

    value.chmod(0o640)
    with pytest.raises(SecretBackendError, match="permissions"):
        backend.read("DATABASE_PASSWORD")


def test_mounted_secret_rejects_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    root = tmp_path / "secrets"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.write_bytes(b"private")
    link = root / "TOKEN"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")

    with pytest.raises(SecretBackendError, match="non-symlink"):
        MountedSecretBackend(root).read("TOKEN")


def test_secret_lease_closes_and_zeroes_internal_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WE3_SECRET_TOKEN", "secret-value")
    lease = SecretLease.obtain(EnvironmentSecretBackend(), "TOKEN")
    internal = lease._value

    assert lease.text() == "secret-value"
    lease.close()

    assert internal == bytearray(len(internal))
    with pytest.raises(SecretBackendError, match="closed"):
        lease.bytes()


def test_secret_names_are_narrow_and_non_pathlike() -> None:
    assert validate_secret_name("OIDC_CLIENT_SECRET") == "OIDC_CLIENT_SECRET"
    for name in {"../TOKEN", "token", "A/B", "A-B", ""}:
        with pytest.raises(ValueError):
            validate_secret_name(name)
