# Systems: Adapter Registry
# Tags: ADAPTERS
# Colors: Slate
# Provenance: Authored here
# Tag confidence: High
# Inventory date: 2026-07-15

"""Adapter registry and evidence-preserving normalization pipeline."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceFamily(StrEnum):
    """Source family classifications for adapter selection."""

    TEXT_MARKDOWN = "text-markdown"
    TEXT_STRUCTURED = "text-structured"
    PDF = "pdf"
    IMAGE_RASTER = "image-raster"
    IMAGE_VECTOR = "image-vector"
    ARCHIVE_ZIP = "archive-zip"
    ARCHIVE_TAR = "archive-tar"
    BINARY_UNKNOWN = "binary-unknown"
    POLYGLOT = "polyglot"


class QuarantineReason(StrEnum):
    """Reason codes for quarantine classification."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    MEDIA_MISMATCH = "media_mismatch"
    OPAQUE_ENCRYPTED = "opaque_encrypted"
    PARSE_FAILED = "parse_failed"
    OUTPUT_EXCEEDS_LIMIT = "output_exceeds_limit"
    ACTIVE_CONTENT = "active_content"


class SelectorKind(StrEnum):
    """Selector kinds for source location tracking."""

    TEXTUAL = "textual"
    SPATIAL = "spatial"
    VIRTUAL = "virtual"


class CategoryType(StrEnum):
    """Knowledge categories extracted during normalization."""

    METADATA = "metadata"
    HEADINGS = "headings"
    PROSE = "prose"
    CODE = "code"
    TOOL_REFERENCES = "tool_references"
    PROCEDURES = "procedures"
    FACTS_CLAIMS = "facts_claims"
    QUESTIONS_ANSWERS = "questions_answers"
    WARNINGS = "warnings"
    CREDENTIALS_OR_FLAGS = "credentials_or_flags"
    APPLICATIONS = "applications"
    LINKS = "links"
    OPAQUE_REGIONS = "opaque_regions"


class NormalizedSelector(BaseModel):
    """Selector for locating content in the original source."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: SelectorKind
    confidence: float = Field(ge=0.0, le=1.0)
    locator: str = Field(min_length=1)
    source_fingerprint: str | None = None

    @field_validator("locator")
    @classmethod
    def _normalize_locator(cls, value: str) -> str:
        return value.strip()


class NormalizedCategory(BaseModel):
    """Normalized content category with evidence references."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    category: CategoryType
    content: str
    selectors: list[NormalizedSelector] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class AdapterCapabilityRecord(BaseModel):
    """Registry record for adapter capabilities."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = "adapter_capability_record.v1"
    adapter_id: str = Field(pattern=r"^adapter:[a-z][a-z0-9-]{0,62}$")
    adapter_version: str = Field(pattern=r"^v\d+\.\d+\.\d+$")
    accepted_media_types: list[str] = Field(min_length=1)
    magic_signatures: list[dict[str, Any]] = Field(default_factory=list)
    schema_versions: list[str] = Field(default_factory=list)
    max_input_bytes: int = Field(ge=0)
    max_output_bytes: int = Field(ge=0)
    archive_rules: dict[str, Any] | None = None
    determinism_guaranteed: bool = True
    selector_support: bool = True
    fallback_adapter_id: str | None = None
    sandbox_profile: str = Field(min_length=1)
    resource_limits: dict[str, Any] | None = None

    @field_validator("adapter_id", "sandbox_profile")
    @classmethod
    def _normalize_fields(cls, value: str) -> str:
        return value.strip()


class NormalizedDocument(BaseModel):
    """Evidence-preserving normalized document output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = "normalized_document_contract.v1"
    object_id: str = ""
    source_family: SourceFamily
    source_uri: str
    raw_hash: str
    raw_size_bytes: int = Field(ge=0)
    derived_hash: str = ""
    derived_size_bytes: int = Field(default=0, ge=0)
    adapter_id: str
    adapter_version: str
    normalization_version: str
    produced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    categories: list[NormalizedCategory] = Field(default_factory=list)
    selectors: list[NormalizedSelector] = Field(default_factory=list)
    quarantine: dict[str, Any] | None = None
    validation: dict[str, bool] = Field(default_factory=lambda: {
        "schema_valid": True,
        "output_valid": True,
        "size_within_limit": True,
        "encoding_valid": True,
    })

    def model_post_init(self, __context: Any = None) -> None:
        """Generate canonical IDs and hashes after initialization."""
        if not self.object_id:
            self.object_id = f"normalized:{uuid4().hex[:24]}"
        if not self.derived_hash and self.categories:
            content_hash = hashlib.sha256(
                "|".join(c.content for c in self.categories).encode()
            ).hexdigest()
            self.derived_hash = f"sha256:{content_hash}"
            self.derived_size_bytes = sum(len(c.content) for c in self.categories)


class AdapterRegistry:
    """Registry of available adapters for content normalization."""

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterCapabilityRecord] = {}
        self._logger = logging.getLogger("wilson.adapters.registry")
        self._load_default_adapters()

    def _load_default_adapters(self) -> None:
        """Load built-in adapter registrations."""
        default_adapters = [
            AdapterCapabilityRecord(
                adapter_id="adapter:text-markdown-v1",
                adapter_version="v1.0.0",
                accepted_media_types=["text/markdown", "text/x-markdown"],
                magic_signatures=[{"offset": 0, "pattern": "#"}],
                max_input_bytes=10 * 1024 * 1024,
                max_output_bytes=5 * 1024 * 1024,
                sandbox_profile="default-sandbox",
            ),
            AdapterCapabilityRecord(
                adapter_id="adapter:text-structured-v1",
                adapter_version="v1.0.0",
                accepted_media_types=["application/json", "text/yaml", "text/x-yaml"],
                max_input_bytes=5 * 1024 * 1024,
                max_output_bytes=2 * 1024 * 1024,
                sandbox_profile="default-sandbox",
            ),
            AdapterCapabilityRecord(
                adapter_id="adapter:image-raster-v1",
                adapter_version="v1.0.0",
                accepted_media_types=["image/png", "image/jpeg", "image/webp"],
                magic_signatures=[
                    {"offset": 0, "pattern": "\x89PNG"},
                    {"offset": 0, "pattern": "\xff\xd8\xff"},
                ],
                archive_rules={"max_members": 0, "max_depth": 0},
                max_input_bytes=50 * 1024 * 1024,
                max_output_bytes=10 * 1024 * 1024,
                sandbox_profile="image-sandbox",
                resource_limits={"cpu_time_seconds": 30, "memory_bytes": 512 * 1024 * 1024},
            ),
            AdapterCapabilityRecord(
                adapter_id="adapter:archive-zip-v1",
                adapter_version="v1.0.0",
                accepted_media_types=["application/zip"],
                magic_signatures=[{"offset": 0, "pattern": "PK"}],
                max_input_bytes=100 * 1024 * 1024,
                max_output_bytes=20 * 1024 * 1024,
                sandbox_profile="archive-sandbox",
                resource_limits={
                    "max_archive_members": 10000,
                    "max_compression_ratio": 100,
                },
            ),
        ]

        for adapter in default_adapters:
            self.register_adapter(adapter)

    def register_adapter(self, record: AdapterCapabilityRecord) -> None:
        """Register an adapter capability record."""
        self._adapters[record.adapter_id] = record
        self._logger.info("adapter_registered", extra={"adapter_id": record.adapter_id})

    def select_adapter(
        self,
        media_type: str,
        magic_bytes: bytes | None = None,
    ) -> AdapterCapabilityRecord | None:
        """Select an adapter based on media type and magic signature."""
        for adapter in self._adapters.values():
            if media_type in adapter.accepted_media_types:
                return adapter

            if magic_bytes:
                for sig in adapter.magic_signatures:
                    offset = sig.get("offset", 0)
                    pattern = sig.get("pattern", "")
                    if (
                        offset + len(pattern) <= len(magic_bytes)
                        and magic_bytes[offset : offset + len(pattern)] == pattern.encode()
                    ):
                        return adapter

        return None

    def resolve(self, source_path: Path | str) -> AdapterCapabilityRecord | None:
        """Resolve adapter for a given source file."""
        path = Path(source_path) if isinstance(source_path, str) else source_path

        if not path.exists():
            return None

        extension = path.suffix.lower()
        media_type_map = {
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".json": "application/json",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".zip": "application/zip",
        }

        media_type = media_type_map.get(extension)
        if not media_type:
            return None

        magic_bytes = None
        try:
            with open(path, "rb") as f:
                magic_bytes = f.read(8)
        except Exception:
            pass

        return self.select_adapter(media_type or "", magic_bytes)


# Global registry instance
_registry: AdapterRegistry | None = None


def get_adapter_registry() -> AdapterRegistry:
    """Return singleton adapter registry."""
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry


__all__ = [
    "SourceFamily",
    "QuarantineReason",
    "SelectorKind",
    "CategoryType",
    "NormalizedSelector",
    "NormalizedCategory",
    "AdapterCapabilityRecord",
    "NormalizedDocument",
    "AdapterRegistry",
    "get_adapter_registry",
]