"""Adapter registry and normalization module."""

from .adapter_registry import (
    SourceFamily,
    QuarantineReason,
    SelectorKind,
    CategoryType,
    NormalizedSelector,
    NormalizedCategory,
    AdapterCapabilityRecord,
    NormalizedDocument,
    AdapterRegistry,
    get_adapter_registry,
)

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