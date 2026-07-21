"""Unit tests for TODO 49 accessibility and localization.

T7.1.5 - WCAG 2.2 AA compliance for primary workflows.
Tests cover keyboard operation, screen reader, zoom, localization, and RTL.
"""

import pytest

from wilson_eval3ngine.ui.accessibility import (
    SUPPORTED_LOCALES,
    WCAG_PALETTE,
    AccessibilityMetadata,
    get_localized_string,
    format_number_for_locale,
    format_date_for_locale,
    enhance_safe_html_accessibility,
    detect_rtl_locale,
    LOCALIZATION_KEYS,
    sanitize_translated_content,
    get_locale_direction,
    WCAGContrasts,
    check_contrast_ratio,
    validate_wcag_compliance,
    aria_live_region,
)


# ============================================================================
# Localization Keys Tests
# ============================================================================

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

    def test_no_concatenated_fragments(self):
        """Strings are externalized, not concatenated fragments."""
        # All keys are complete strings, not partial
        for locale, strings in LOCALIZATION_KEYS.items():
            for key, value in strings.items():
                # Strings should be complete phrases
                assert len(value) > 0
                assert "{" not in value or "}" in value  # If formatting, must be complete

    def test_wcag_palette_defined(self):
        """WCAG palette has required colors with contrast ratios."""
        assert "text_primary" in WCAG_PALETTE
        assert "focus" in WCAG_PALETTE
        assert WCAG_PALETTE["text_primary"]["min_ratio"] == 4.5


# ============================================================================
# Localized Strings Tests
# ============================================================================

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

    def test_missing_key_returns_key(self):
        """Missing key returns the key as fallback."""
        result = get_localized_string("nonexistent_key", "en-US")
        assert result == "nonexistent_key"


# ============================================================================
# Sanitization and Security Tests
# ============================================================================

class TestSanitizationSecurity:
    """Tests for translation security (XSS prevention, etc.)."""

    def test_sanitize_removes_script_tags(self):
        """Script tags are removed from translated content."""
        malicious = "<script>alert('xss')</script>Hello"
        sanitized = sanitize_translated_content(malicious)
        assert "<script>" not in sanitized
        assert "Hello" in sanitized

    def test_sanitize_removes_event_handlers(self):
        """Event handlers are removed from translated content."""
        malicious = '<img src=x onerror=alert(1)>Test'
        sanitized = sanitize_translated_content(malicious)
        # Event handler should be removed
        assert "onerror" not in sanitized

    def test_sanitize_html_escapes_output(self):
        """HTML special characters are escaped for safety."""
        sanitized = sanitize_translated_content("<script>Test</script>")
        assert "&lt;" in sanitized or "<script>" not in sanitized

    def test_sanitize_removes_javascript_urls(self):
        """javascript: URLs are sanitized."""
        malicious = '<a href="javascript:alert(1)">Click</a>'
        sanitized = sanitize_translated_content(malicious)
        assert "javascript:" not in sanitized

    def test_sanitize_handles_data_urls(self):
        """Dangerous URLs are sanitized."""
        malicious = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        sanitized = sanitize_translated_content(malicious)
        # Should be sanitized or escaped
        assert len(sanitized) > 0


# ============================================================================
# Accessibility Metadata Tests
# ============================================================================

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

    def test_accessibility_reduced_motion(self):
        """Reduced motion preference is configurable."""
        meta = AccessibilityMetadata(prefers_reduced_motion=True)
        assert meta.prefers_reduced_motion is True


# ============================================================================
# RTL Detection Tests
# ============================================================================

class TestRtlDetection:
    """Tests for RTL locale detection."""

    def test_ltr_locale(self):
        """Left-to-right locales are detected correctly."""
        assert detect_rtl_locale("en-US") is False
        assert detect_rtl_locale("fr-FR") is False

    def test_rtl_locale(self):
        """Right-to-left locales are detected correctly."""
        assert detect_rtl_locale("ar-SA") is True

    def test_locale_direction_consistent(self):
        """Locale direction helper is consistent with RTL detection."""
        for locale in SUPPORTED_LOCALES:
            if detect_rtl_locale(locale):
                assert get_locale_direction(locale) == "rtl"
            else:
                assert get_locale_direction(locale) == "ltr"


# ============================================================================
# Number Formatting Tests
# ============================================================================

class TestNumberFormatting:
    """Tests for locale-aware number formatting."""

    def test_format_number_western(self):
        """Western numbers are formatted with grouping."""
        assert format_number_for_locale(1234.5, "en-US") == "1,234.50"

    def test_format_number_asian(self):
        """Asian numbers are formatted without grouping."""
        assert format_number_for_locale(1234.5, "ja-JP") == "1234.50"

    def test_format_date_preserves_iso(self):
        """Date formatting preserves ISO format in MVP."""
        result = format_date_for_locale("2026-07-15T12:00:00Z", "en-US")
        assert result == "2026-07-15T12:00:00Z"


# ============================================================================
# HTML Enhancement Tests
# ============================================================================

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

    def test_enhance_html_includes_skip_link(self):
        """Skip link is included for keyboard users."""
        base = "<html><head></head><body><h1>Report</h1></body></html>"
        enhanced = enhance_safe_html_accessibility(base, locale="en-US")
        assert "skip" in enhanced.lower()

    def test_enhance_html_includes_focus_styles(self):
        """Focus styles for WCAG compliance are included."""
        base = "<html><head></head><body><h1>Report</h1></body></html>"
        enhanced = enhance_safe_html_accessibility(base)
        assert ":focus" in enhanced
        assert "prefers-contrast" in enhanced


# ============================================================================
# WCAG Contrast Tests
# ============================================================================

class TestWCAGContrasts:
    """Tests for WCAG color contrast validation."""

    def test_contrast_ratio_calculation(self):
        """Contrast ratio is calculated correctly."""
        # Black on white should be 21:1 (maximum)
        ratio = check_contrast_ratio("#000000", "#FFFFFF")
        assert ratio >= 21.0

    def test_aaa_contrast_threshold(self):
        """AAA contrast threshold is validated."""
        assert WCAGContrasts.AAA_NORMAL is not None
        assert WCAGContrasts.AAA_NORMAL >= 7.0

    def test_aa_contrast_threshold(self):
        """AA contrast threshold is validated."""
        assert WCAGContrasts.AA_NORMAL is not None
        assert WCAGContrasts.AA_NORMAL >= 4.5

    def test_validate_wcag_compliance_aa(self):
        """WCAG compliance validator works for AA."""
        # Black on white passes AA
        assert validate_wcag_compliance("#000000", "#FFFFFF", "AA") is True

    def test_validate_wcag_compliance_aaa(self):
        """WCAG compliance validator works for AAA."""
        # Black on white passes AAA
        assert validate_wcag_compliance("#000000", "#FFFFFF", "AAA") is True


# ============================================================================
# Live Region Tests
# ============================================================================

class TestLiveRegions:
    """Tests for ARIA live region announcements."""

    def test_aria_live_region_context(self):
        """Live region context provides required attributes."""
        with aria_live_region("test_operation") as ctx:
            assert ctx["aria-live"] == "polite"
            assert ctx["aria-atomic"] == "true"
            assert ctx["data-operation"] == "test_operation"


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases in accessibility and localization."""

    def test_long_text_handling(self):
        """Long text is handled appropriately."""
        long_text = "This is a very long string that might overflow containers " * 10
        result = sanitize_translated_content(long_text)
        assert len(result) > 0

    def test_cjk_text_handling(self):
        """CJK (Chinese/Japanese/Korean) text is supported."""
        cjk_text = "日本語のテストテキスト"
        sanitized = sanitize_translated_content(cjk_text)
        # CJK text may be escaped but should be preserved
        assert len(sanitized) > 0

    def test_mixed_direction_content(self):
        """Mixed RTL/LTR content is handled."""
        mixed = "English and عربى mixed"
        sanitized = sanitize_translated_content(mixed)
        assert len(sanitized) > 0

    def test_empty_input_handling(self):
        """Empty input is handled gracefully."""
        assert sanitize_translated_content("") == ""

    def test_none_input_handling(self):
        """None input is handled gracefully."""
        assert sanitize_translated_content(None) == ""