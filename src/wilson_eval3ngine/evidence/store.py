from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import re
from typing import Any, Protocol

from ..util import sha256_hex, utc_now


_PROJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    project_id: str
    sha256: str
    media_type: str
    size_bytes: int
    relative_path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactStore(Protocol):
    def put_bytes(
        self,
        project_id: str,
        payload: bytes,
        *,
        media_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef: ...

    def get_bytes(self, ref: ArtifactRef) -> bytes: ...

    def verify(self, ref: ArtifactRef) -> bool: ...


class LocalArtifactStore:
    """Development content-addressed store.

    Files are write-once by hash. This adapter is suitable for local testing,
    not for production immutability or legal retention guarantees.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_project(project_id: str) -> str:
        if not _PROJECT_RE.fullmatch(project_id):
            raise ValueError("invalid project_id for artifact path")
        return project_id

    def _payload_path(self, project_id: str, digest: str) -> Path:
        project = self._validate_project(project_id)
        return self.root / project / "sha256" / digest[:2] / digest

    def put_bytes(
        self,
        project_id: str,
        payload: bytes,
        *,
        media_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        digest = sha256_hex(payload)
        target = self._payload_path(project_id, digest)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            with target.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing = target.read_bytes()
            if existing != payload:
                raise RuntimeError("content-address collision or artifact corruption")

        created_at = utc_now().isoformat()
        ref = ArtifactRef(
            project_id=project_id,
            sha256=digest,
            media_type=media_type,
            size_bytes=len(payload),
            relative_path=str(target.relative_to(self.root)),
            created_at=created_at,
        )
        sidecar = target.with_suffix(".metadata.json")
        if not sidecar.exists():
            sidecar_payload = {
                "artifact": ref.to_dict(),
                "metadata": metadata or {},
            }
            try:
                with sidecar.open("x", encoding="utf-8") as handle:
                    json.dump(sidecar_payload, handle, sort_keys=True, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
            except FileExistsError:  # pragma: no cover - race-safe fallback
                pass
        return ref

    def put_json(
        self,
        project_id: str,
        value: Any,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return self.put_bytes(
            project_id,
            payload,
            media_type="application/json",
            metadata=metadata,
        )

    def get_bytes(self, ref: ArtifactRef) -> bytes:
        target = self.root / ref.relative_path
        resolved = target.resolve()
        if self.root.resolve() not in resolved.parents:
            raise ValueError("artifact path escaped store root")
        return target.read_bytes()

    def verify(self, ref: ArtifactRef) -> bool:
        try:
            payload = self.get_bytes(ref)
        except OSError:
            return False
        return len(payload) == ref.size_bytes and sha256_hex(payload) == ref.sha256
