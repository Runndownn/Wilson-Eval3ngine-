"""Unit tests for TODO 49 accessibility and localization."""

from wilson_eval3ngine.ui.accessibility import (
    SUPPORTED_LOCALES,
    AccessibilityMetadata,
    get_localized_string,
    format_number_for_locale,
    enhance_safe_html_accessibility,
    detect_rtl_locale,
    LOCALIZATION_KEYS,
)


class TestLocalizationKeys:
    """Tests for localization key structure."""

    def test_localization_keys_exist(self):
        """English localization keys are defined."""
        assert "en-US" in LOCALIZATION_KEYS
        assert "experiment_status_pass" in LOCALIZATION_KEYS["en-US"]
        assert "gate_section" in LOCALIZATION_KEYS["en-US"]

    def test_supported_locales_defined(self):
        """Supported locales are known."""
        assert "en-US" in SUPPORTED_LOCALES
        assert "ar-SA" in SUPPORTED_LOCALES  # RTL locale
        assert "ja-JP" in SUPPORTED_LOCALES


class TestLocalizedStrings:
    """Tests for localized string retrieval."""

    def test_get_english_string(self):
        """English strings are retrieved correctly."""
        result = get_localized_string("experiment_status_pass", "en-US")
        assert result == "Pass"

    def test_fallback_to_english(self):
        """Missing locale falls back to English."""
        result = get_localized_string("experiment_status_pass", "xx-XX")
        assert result == "Pass"

    def test_formatting_with_kwargs(self):
        """String formatting with kwargs works."""
        result = get_localized_string("support_percentage", "en-US", pct=85)
        assert result == "Support: 85%"


class TestAccessibilityMetadata:
    """Tests for accessibility metadata."""

    def test_accessibility_defaults(self):
        """Default metadata values are accessible."""
        meta = AccessibilityMetadata()
        assert meta.keyboard_navigable is True
        assert meta.focus_visible is True
        assert meta.max_zoom_percent == 400

    def test_accessibility_to_html(self):
        """HTML attributes are generated correctly."""
        meta = AccessibilityMetadata(
            aria_label="Gate decisions table",
            landmark=True,
        )
        attrs = meta.to_html_attributes()
        assert "aria-label" in attrs
        assert attrs["aria-label"] == "Gate decisions table"


class TestRtlDetection:
    """Tests for RTL locale detection."""

    def test_ltr_locale(self):
        """Left-to-right locales are detected correctly."""
        assert detect_rtl_locale("en-US") is False
        assert detect_rtl_locale("fr-FR") is False

    def test_rtl_locale(self):
        """Right-to-left locales are detected correctly."""
        assert detect_rtl_locale("ar-SA") is True


class TestNumberFormatting:
    """Tests for locale-aware number formatting."""

    def test_format_number_western(self):
        """Western numbers are formatted with grouping."""
        assert format_number_for_locale(1234.5, "en-US") == "1,234.50"

    def test_format_number_asian(self):
        """Asian numbers are formatted without grouping."""
        assert format_number_for_locale(1234.5, "ja-JP") == "1234.50"


class TestHtmlEnhancement:
    """Tests for HTML accessibility enhancement."""

    def test_enhance_html_adds_landmarks(self):
        """HTML enhancement adds proper landmarks."""
        base = "<html><head></head><body><h1>Report</h1></body></html>"
        enhanced = enhance_safe_html_accessibility(base, experiment_id="exp_123")
        assert 'role="main"' in enhanced
        assert "skip-link" in enhanced
        assert "aria-label" in enhanced

    def test_enhance_html_adds_main_landmark(self):
        """HTML enhancement wraps content in main landmark."""
        base = "<html><head></head><body><h1>Report</h1></body></html>"
        enhanced = enhance_safe_html_accessibility(base)
        assert "<main" in enhanced
        assert "</main>" in enhanced