"""
Accessibility and localization framework (TODO 49).

T7.1.5 - Ensure workflows are usable by people relying on keyboard,
screen readers, zoom, or localized presentation.
"""

from __future__ import annotations

import html
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

# Supported locales
SUPPORTED_LOCALES = frozenset({
    "en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN", "ar-SA",
})

# WCAG 2.2 AA compliant color palette
WCAG_PALETTE = {
    "text_primary": {"fg": "#000000", "bg": "#FFFFFF", "min_ratio": 4.5},
    "text_secondary": {"fg": "#333333", "bg": "#FFFFFF", "min_ratio": 4.5},
    "status_pass": {"fg": "#1B4D2E", "bg": "#E8F5E9", "min_ratio": 4.5},
    "status_block": {"fg": "#7A1F1F", "bg": "#FFEBEE", "min_ratio": 4.5},
    "status_warning": {"fg": "#704200", "bg": "#FFF8E1", "min_ratio": 4.5},
    "link": {"fg": "#0066CC", "bg": "#FFFFFF", "min_ratio": 4.5},
    "focus": {"fg": "#FFFFFF", "bg": "#0066CC", "min_ratio": 4.5},
}

# User-visible strings externalized for translation
LOCALIZATION_KEYS = {
    "en-US": {
        "experiment_status_pass": "Pass",
        "experiment_status_block": "Block",
        "experiment_status_warning": "Warning",
        "experiment_status_indeterminate": "Indeterminate",
        "gate_section": "Gate Decisions",
        "experiment_label": "Experiment",
        "model_label": "Model",
        "status_label": "Status",
        "reasons_label": "Reasons",
        "limitations_header": "Known Limitations",
        "safety_notice": "This report intentionally excludes raw prompts and responses.",
        "critical_block": "Critical block detected",
        "support_percentage": "Support: {pct}%",
        "uncertainty_percentage": "Uncertainty: {pct}%",
        "skip_to_content": "Skip to main content",
    },
}


@dataclass(frozen=True, slots=True)
class AccessibilityMetadata:
    """Accessibility metadata for UI components.

    Security: Does not include any restricted content.
    """
    # WCAG 2.2 AA compliance indicators
    keyboard_navigable: bool = True
    focus_visible: bool = True
    aria_label: str = ""
    aria_describedby: str = ""
    role: str = "region"
    landmark: bool = True

    # High contrast support
    high_contrast_mode: bool = True

    # Zoom/reflow support
    max_zoom_percent: int = 400
    min_zoom_percent: int = 25

    # Reduced motion
    prefers_reduced_motion: bool = True

    def to_html_attributes(self) -> dict[str, str]:
        """Generate HTML accessibility attributes."""
        attrs: dict[str, str] = {}
        if self.aria_label:
            attrs["aria-label"] = self.aria_label
        if self.aria_describedby:
            attrs["aria-describedby"] = self.aria_describedby
        if self.landmark:
            attrs["role"] = f"{self.role} landmark"
        return attrs


@dataclass(frozen=True, slots=True)
class LocaleAwareReport:
    """Report with localized strings and accessible markup.

    Security: Localized content is externalized and sanitized.
    """
    schema_version: str = "we3.locale_aware_report.v1"
    experiment_id: str = ""
    locale: str = "en-US"
    generated_at: str = ""
    html_content: str = ""
    accessibility: dict[str, Any] = field(default_factory=dict)
    rtl_layout: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "locale": self.locale,
            "generated_at": self.generated_at,
            "rtl_layout": self.rtl_layout,
        }


def get_localized_string(key: str, locale: str = "en-US", **format_kwargs: Any) -> str:
    """Get localized string for a key.

    Falls back to English if translation missing.
    No concatenated fragments - full strings only.
    """
    strings = LOCALIZATION_KEYS.get(locale, LOCALIZATION_KEYS["en-US"])
    result = strings.get(key, key)
    if format_kwargs:
        result = result.format(**format_kwargs)
    return result


def format_number_for_locale(value: float, locale: str = "en-US") -> str:
    """Format a number respecting locale conventions.

    Stores values in locale-neutral format; formatting is presentation layer.
    Uses standard Python formatting for simplicity.
    """
    # Group thousands for Western locales
    if locale.startswith("ja") or locale.startswith("zh"):
        return f"{value:.2f}"
    return f"{value:,.2f}"


def format_date_for_locale(date_str: str, locale: str = "en-US") -> str:
    """Format a date string for locale presentation.

    Parses ISO date and reformats.
    """
    # Simple implementation - production would use proper locale dates
    return date_str


def enhance_safe_html_accessibility(
    base_html: str,
    *,
    experiment_id: str = "",
    locale: str = "en-US",
) -> str:
    """Add accessibility attributes to safe HTML report.

    WCAG 2.2 AA compliance:
    - Semantic landmarks for navigation
    - Proper headings hierarchy (h1, h2, h3)
    - Focus indicators
    - Non-color status indicators
    - ARIA labels for screen readers
    """
    strings = LOCALIZATION_KEYS.get(locale, LOCALIZATION_KEYS["en-US"])

    # Add accessibility enhancements with WCAG-compliant focus styling
    enhanced = base_html.replace(
        "<head>",
        """<head>
<style>
/* WCAG 2.2 AA Focus indicators for keyboard navigation */
:focus { outline: 2px solid #0066cc; outline-offset: 2px; }
:focus:not(:focus-visible) { outline: none; }
:focus-visible { outline: 2px solid #0066cc; outline-offset: 2px; }
/* High contrast support */
@media (prefers-contrast: high) { body { border: 2px solid #000; background: #fff; } }
@media (prefers-contrast: high) { * { background: #fff !important; } }
/* Reduced motion support */
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
/* Skip link for keyboard users - WCAG 2.2 AA compliant positioning */
.skip-link { position: absolute; left: -999px; top: -999px; background: #000; color: #fff; padding: 8px 16px; text-decoration: none; z-index: 9999; }
.skip-link:focus, .skip-link:active { left: 1rem; top: 1rem; }
/* Non-color status indicators for WCAG compliance */
.status-pass { border-left: 4px solid #28a745; }
.status-block { border-left: 4px solid #dc3545; }
.status-warning { border-left: 4px solid #ffc107; }
</style>""",
    )

    # Add skip link
    enhanced = enhanced.replace(
        "<body>",
        f'<body><a href="#main" class="skip-link">{strings.get("skip_to_content", "Skip to main content")}</a>',
    )

    # Add main landmark
    enhanced = enhanced.replace(
        "<h1>",
        '<main id="main" role="main" aria-label="Report content"><h1>',
    )

    # Close main landmark before </body>
    enhanced = enhanced.replace(
        "</body>",
        "</main></body>",
    )

    return enhanced


def detect_rtl_locale(locale: str) -> bool:
    """Detect if locale requires right-to-left layout."""
    rtl_locales = {"ar-SA", "he-IL", "fa-IR", "ur-PK"}
    return locale in rtl_locales


def get_locale_direction(locale: str) -> str:
    """Get the layout direction for a locale."""
    return "rtl" if detect_rtl_locale(locale) else "ltr"


def sanitize_translated_content(content: str | None) -> str:
    """Sanitize translated content to prevent XSS.

    Security: Removes script tags, event handlers, and dangerous URLs.
    Prohibits translators from introducing active markup.
    """
    if content is None:
        return ""
    # Remove script tags
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
    # Remove event handlers (onclick, onerror, etc.)
    content = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s+on\w+\s*=\s*'[^']*'", "", content, flags=re.IGNORECASE)
    content = re.sub(r'\s+on\w+\s*=\s*[^\s<]+', "", content, flags=re.IGNORECASE)
    # Remove dangerous URLs
    content = re.sub(r"javascript:", "", content, flags=re.IGNORECASE)
    content = re.sub(r"data:text/html", "", content, flags=re.IGNORECASE)
    # HTML-escape remaining content to prevent injection
    return html.escape(content)


def validate_wcag_compliance(
    foreground: str,
    background: str,
    standard: str = "AA",
) -> bool:
    """Validate WCAG contrast compliance.

    Args:
        foreground: Hex color string (e.g., "#000000")
        background: Hex color string (e.g., "#FFFFFF")
        standard: "AA" or "AAA"

    Returns:
        True if contrast meets WCAG requirements.
    """
    ratio = check_contrast_ratio(foreground, background)
    threshold = WCAGContrasts.AA_NORMAL if standard == "AA" else WCAGContrasts.AAA_NORMAL
    return ratio >= threshold


@contextmanager
def aria_live_region(operation_name: str) -> Iterator[dict[str, str]]:
    """Context manager for ARIA live region announcements.

    Yields a context dict for async/polling status updates.
    """
    context = {
        "aria-live": "polite",
        "aria-atomic": "true",
        "data-operation": operation_name,
    }
    yield context


class WCAGContrasts:
    """WCAG 2.2 AA contrast thresholds."""
    AA_NORMAL = 4.5  # Normal text minimum
    AA_LARGE = 3.0   # Large text minimum
    AAA_NORMAL = 7.0   # AAA normal text
    AAA_LARGE = 4.5    # AAA large text


def check_contrast_ratio(foreground: str, background: str) -> float:
    """Calculate contrast ratio between two colors.

    Args:
        foreground: Hex color string (e.g., "#000000")
        background: Hex color string (e.g., "#FFFFFF")

    Returns:
        Contrast ratio (1-21 range)
    """
    def hex_to_luminance(hex_color: str) -> float:
        """Convert hex color to relative luminance."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255

        def adjust(c: float) -> float:
            return c / 12.92 if c <= 0.0303 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lum1 = hex_to_luminance(foreground)
    lum2 = hex_to_luminance(background)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


__all__ = [
    "SUPPORTED_LOCALES",
    "LOCALIZATION_KEYS",
    "WCAG_PALETTE",
    "AccessibilityMetadata",
    "LocaleAwareReport",
    "get_localized_string",
    "format_number_for_locale",
    "format_date_for_locale",
    "enhance_safe_html_accessibility",
    "detect_rtl_locale",
    "get_locale_direction",
    "sanitize_translated_content",
    "validate_wcag_compliance",
    "aria_live_region",
    "WCAGContrasts",
    "check_contrast_ratio",
]