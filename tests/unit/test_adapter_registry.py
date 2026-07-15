"""Unit tests for Adapter Registry (TODO 11)."""

from pathlib import Path

import pytest

from wilson_eval3ngine.adapters.adapter_registry import (
    AdapterCapabilityRecord,
    AdapterRegistry,
    CategoryType,
    NormalizedCategory,
    NormalizedDocument,
    NormalizedSelector,
    QuarantineReason,
    SelectorKind,
    SourceFamily,
    get_adapter_registry,
)


@pytest.fixture
def sample_registry() -> AdapterRegistry:
    """Create adapter registry for testing."""
    return AdapterRegistry()


class TestSourceFamily:
    """Test suite for source families."""

    def test_all_source_families_exist(self):
        """Verify all source families are defined."""
        families = [f.value for f in SourceFamily]
        expected = [
            "text-markdown",
            "text-structured",
            "pdf",
            "image-raster",
            "image-vector",
            "archive-zip",
            "archive-tar",
            "binary-unknown",
            "polyglot",
        ]
        for expected_family in expected:
            assert expected_family in families, f"Missing source family: {expected_family}"


class TestNormalizedSelector:
    """Test suite for normalized selectors."""

    def test_valid_selector_creation(self):
        """Verify selector can be created."""
        selector = NormalizedSelector(
            kind=SelectorKind.TEXTUAL,
            confidence=0.95,
            locator="heading:Main Content",
        )
        assert selector.kind == SelectorKind.TEXTUAL
        assert selector.confidence == 0.95

    def test_confidence_bounds(self):
        """Verify confidence is bounded between 0 and 1."""
        selector_high = NormalizedSelector(kind=SelectorKind.TEXTUAL, confidence=1.0, locator="test")
        selector_low = NormalizedSelector(kind=SelectorKind.TEXTUAL, confidence=0.0, locator="test")
        assert selector_high.confidence == 1.0
        assert selector_low.confidence == 0.0


class TestNormalizedCategory:
    """Test suite for normalized categories."""

    def test_valid_category_creation(self):
        """Verify category can be created."""
        category = NormalizedCategory(
            category=CategoryType.HEADINGS,
            content="## Introduction\n## Main Content",
        )
        assert category.category == CategoryType.HEADINGS

    def test_category_with_selectors(self):
        """Verify category can have selectors."""
        selector = NormalizedSelector(kind=SelectorKind.TEXTUAL, confidence=0.9, locator="h2:Intro")
        category = NormalizedCategory(
            category=CategoryType.HEADINGS,
            content="## Introduction",
            selectors=[selector],
        )
        assert len(category.selectors) == 1

    def test_all_category_types_exist(self):
        """Verify all 14 category types exist."""
        categories = [c.value for c in CategoryType]
        expected = [
            "metadata",
            "headings",
            "prose",
            "code",
            "tool_references",
            "procedures",
            "facts_claims",
            "questions_answers",
            "warnings",
            "credentials_or_flags",
            "applications",
            "links",
            "opaque_regions",
        ]
        for expected_cat in expected:
            assert expected_cat in categories, f"Missing category: {expected_cat}"


class TestAdapterCapabilityRecord:
    """Test suite for adapter capability records."""

    def test_valid_adapter_record(self):
        """Verify adapter record can be created."""
        record = AdapterCapabilityRecord(
            adapter_id="adapter:test-markdown-v1",
            adapter_version="v1.0.0",
            accepted_media_types=["text/markdown"],
            max_input_bytes=10 * 1024 * 1024,
            max_output_bytes=5 * 1024 * 1024,
            sandbox_profile="default-sandbox",
        )
        assert record.adapter_id == "adapter:test-markdown-v1"

    def test_adapter_id_validation(self):
        """Verify adapter ID must follow naming convention."""
        with pytest.raises(ValueError):
            AdapterCapabilityRecord(
                adapter_id="invalid-id",
                adapter_version="v1.0.0",
                accepted_media_types=["text/plain"],
                max_input_bytes=1024,
                max_output_bytes=1024,
                sandbox_profile="default",
            )


class TestNormalizedDocument:
    """Test suite for normalized documents."""

    def test_valid_document_creation(self):
        """Verify document can be created."""
        doc = NormalizedDocument(
            source_family=SourceFamily.TEXT_MARKDOWN,
            source_uri="file:///test/document.md",
            raw_hash="sha256:abc123",
            raw_size_bytes=1024,
            adapter_id="adapter:text-markdown-v1",
            adapter_version="v1.0.0",
            normalization_version="v1.0.0",
        )
        assert doc.source_family == SourceFamily.TEXT_MARKDOWN
        assert doc.object_id.startswith("normalized:")

    def test_derived_hash_generation(self):
        """Verify derived hash is generated when categories present."""
        category = NormalizedCategory(
            category=CategoryType.HEADINGS,
            content="## Test",
        )
        doc = NormalizedDocument(
            source_family=SourceFamily.TEXT_MARKDOWN,
            source_uri="file:///test/doc.md",
            raw_hash="sha256:abc123",
            raw_size_bytes=1024,
            adapter_id="adapter:text-markdown-v1",
            adapter_version="v1.0.0",
            normalization_version="v1.0.0",
            categories=[category],
        )
        assert doc.derived_hash.startswith("sha256:")

    def test_quarantine_on_invalid_content(self):
        """Verify document can be quarantined for suspicious content."""
        doc = NormalizedDocument(
            source_family=SourceFamily.BINARY_UNKNOWN,
            source_uri="file:///test/binary.bin",
            raw_hash="sha256:abc123",
            raw_size_bytes=1024,
            adapter_id="adapter:binary-unknown-v1",
            adapter_version="v1.0.0",
            normalization_version="v1.0.0",
            quarantine={"reason": "active_content", "reason_enum": QuarantineReason.ACTIVE_CONTENT},
        )
        assert doc.quarantine is not None


class TestAdapterRegistry:
    """Test suite for adapter registry."""

    def test_registry_creation(self, sample_registry: AdapterRegistry):
        """Verify registry can be created."""
        assert sample_registry is not None

    def test_default_adapters_loaded(self, sample_registry: AdapterRegistry):
        """Verify default adapters are loaded."""
        assert len(sample_registry._adapters) >= 4

    def test_register_adapter(self, sample_registry: AdapterRegistry):
        """Verify custom adapter registration."""
        record = AdapterCapabilityRecord(
            adapter_id="adapter:custom-test-v1",
            adapter_version="v1.0.0",
            accepted_media_types=["application/custom"],
            max_input_bytes=1024,
            max_output_bytes=1024,
            sandbox_profile="custom-sandbox",
        )
        sample_registry.register_adapter(record)
        assert "adapter:custom-test-v1" in sample_registry._adapters

    def test_select_adapter_by_media_type(self, sample_registry: AdapterRegistry):
        """Verify adapter selection by media type."""
        adapter = sample_registry.select_adapter("text/markdown", None)
        assert adapter is not None
        assert "markdown" in adapter.adapter_id

    def test_select_adapter_by_magic_bytes(self, sample_registry: AdapterRegistry):
        """Verify adapter selection by magic signature."""
        # PNG magic bytes
        adapter = sample_registry.select_adapter("image/png", b"\x89PNG\r\n\x1a\n")
        assert adapter is not None
        assert "image" in adapter.adapter_id

    def test_resolve_markdown_file(self, sample_registry: AdapterRegistry, tmp_path: Path):
        """Verify file resolution for markdown."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")
        adapter = sample_registry.resolve(md_file)
        assert adapter is not None

    def test_resolve_json_file(self, sample_registry: AdapterRegistry, tmp_path: Path):
        """Verify file resolution for JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        adapter = sample_registry.resolve(json_file)
        assert adapter is not None

    def test_resolve_missing_file(self, sample_registry: AdapterRegistry, tmp_path: Path):
        """Verify None returned for missing file."""
        missing = tmp_path / "missing.md"
        adapter = sample_registry.resolve(missing)
        assert adapter is None


class TestGetAdapterRegistry:
    """Test suite for registry accessor."""

    def test_singleton_returns_same_instance(self):
        """Verify accessor returns singleton."""
        reg1 = get_adapter_registry()
        reg2 = get_adapter_registry()
        assert reg1 is reg2