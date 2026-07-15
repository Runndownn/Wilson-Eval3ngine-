from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..util import sha256_hex


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    algorithm: str
    public_key_fingerprint_sha256: str
    public_key_pem: str
    signature_base64: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def generate_private_key(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    target.write_bytes(pem)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def load_private_key(path: str | Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("signing key must be Ed25519")
    return key


def sign_bytes(payload: bytes, private_key: Ed25519PrivateKey) -> SignatureEnvelope:
    public = private_key.public_key()
    public_bytes = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = private_key.sign(payload)
    return SignatureEnvelope(
        algorithm="Ed25519",
        public_key_fingerprint_sha256=sha256_hex(public_bytes),
        public_key_pem=public_bytes.decode("ascii"),
        signature_base64=b64encode(signature).decode("ascii"),
    )


def verify_bytes(payload: bytes, envelope: SignatureEnvelope) -> bool:
    try:
        public = serialization.load_pem_public_key(envelope.public_key_pem.encode("ascii"))
        if not isinstance(public, Ed25519PublicKey):
            return False
        if sha256_hex(envelope.public_key_pem.encode("ascii")) != (
            envelope.public_key_fingerprint_sha256
        ):
            return False
        public.verify(b64decode(envelope.signature_base64), payload)
        return True
    except Exception:
        return False
