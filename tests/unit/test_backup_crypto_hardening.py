from __future__ import annotations

import io
from pathlib import Path

import pytest

from wilson_eval3ngine.backup import crypto
from wilson_eval3ngine.storage.encrypted_store import LocalKMSClient


def test_streaming_gcm_fails_closed_before_single_nonce_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(crypto, "MAX_GCM_PLAINTEXT_BYTES", 8)
    destination = tmp_path / "too-large.enc"

    with pytest.raises(crypto.BackupEncryptionError, match="AES-GCM bound"):
        crypto.encrypt_stream(
            io.BytesIO(b"123456789"),
            destination,
            kms_client=LocalKMSClient(master_key=b"K" * 32),
            key_id="test-key",
            kms_identity={"provider": "local-test"},
        )

    assert not destination.exists()


def test_envelope_rejects_invalid_nonce_and_tag_lengths(tmp_path: Path) -> None:
    kms = LocalKMSClient(master_key=b"K" * 32)
    source = tmp_path / "plain"
    encrypted = tmp_path / "encrypted"
    source.write_bytes(b"bounded backup")
    envelope = crypto.encrypt_file(
        source,
        encrypted,
        kms_client=kms,
        key_id="test-key",
        kms_identity={"provider": "local-test"},
    )

    broken = crypto.EncryptionEnvelope(
        **{
            **envelope.to_dict(),
            "nonce_base64": "AA==",
        }
    )
    with pytest.raises(crypto.BackupEncryptionError, match="nonce_base64"):
        crypto.decrypt_file(
            encrypted,
            tmp_path / "restored",
            kms_client=kms,
            envelope=broken,
        )
