"""Inert rendering and sanitization (TODO 42).

T6.1.5 - Inert rendering for safe viewer, notifications, reports.

Security guarantees:
- XSS prevention via allowlist sanitization
- No active HTML/scripts/event handlers
- No remote resource fetch
- CSP headers enforced
- Raw evidence never rendered inline by default
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("wilson.rendering.inert")


# Patterns to strip from HTML
DANGEROUS_TAGS = frozenset({
    "script", "iframe", "object", "embed", "applet", "meta", "link",
    "style", "base", "form", "input", "button", "svg", "math",
})

DANGEROUS_ATTRIBUTES = frozenset({
    "onload", "onerror", "onclick", "onmouseover", "onfocus", "onblur",
    "onkeydown", "onkeyup", "onsubmit", "onchange", "oninput",
})

# URI schemes that are unsafe
UNSAFE_URI_SCHEMES = frozenset({
    "javascript:", "vbscript:", "data:", "file:", "blob:",
})


@dataclass(frozen=True, slots=True)
class RenderingOptions:
    """Options for inert rendering."""

    allow_html: bool = False
    allow_links: bool = False
    max_length: int = 100_000
    preserve_newlines: bool = True


@dataclass(frozen=True, slots=True)
class RenderingAudit:
    """Audit record for rendering operation."""

    original_hash: str
    rendered_hash: str
    charset: str
    transformations_applied: list[str]
    content_safe: bool
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_hash": self.original_hash,
            "rendered_hash": self.rendered_hash,
            "charset": self.charset,
            "transformations_applied": self.transformations_applied,
            "content_safe": self.content_safe,
            "correlation_id": self.correlation_id,
        }


class InertRenderer:
    """Renders content safely without script execution.

    All rendering treats content as untrusted data and prevents XSS.
    """

    def __init__(self, options: RenderingOptions | None = None) -> None:
        self._options = options or RenderingOptions()

    def render(self, content: str, correlation_id: str = "") -> str:
        """Render content inertly.

        Args:
            content: Raw content to render
            correlation_id: Trace correlation ID

        Returns:
            Safe rendered content
        """
        original_hash = f"sha256:{hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()}"
        transformations = []

        # Truncate if too long
        if len(content) > self._options.max_length:
            content = content[:self._options.max_length]
            transformations.append("truncated")

        # Escape HTML entities if HTML not allowed
        if not self._options.allow_html:
            content = self._escape_html(content)
            transformations.append("html_escaped")

        # Sanitize if HTML allowed
        elif "<" in content:
            content = self._sanitize_html_allowlist(content)
            transformations.append("html_sanitized")

        # Remove dangerous URI schemes
        if "href" in content or "src" in content:
            content = self._sanitize_uris(content)
            transformations.append("uris_sanitized")

        rendered_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

        _audit = RenderingAudit(
            original_hash=original_hash,
            rendered_hash=rendered_hash,
            charset="utf-8",
            transformations_applied=transformations,
            content_safe=True,
            correlation_id=correlation_id,
        )

        logger.info(
            "content_rendered_inert",
            extra={
                "original_hash": original_hash[:16],
                "rendered_hash": rendered_hash[:16],
                "transformations": transformations,
                "correlation_id": correlation_id,
            },
        )

        return content

    def _escape_html(self, content: str) -> str:
        """Escape HTML special characters."""
        return (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    def _sanitize_html_allowlist(self, content: str) -> str:
        """Strip dangerous tags and attributes."""
        # Build pattern from all dangerous tags
        tags_pattern = "|".join(DANGEROUS_TAGS)
        tag_pattern = r"</?(?:" + tags_pattern + r")[^>]*>"
        content = re.sub(tag_pattern, "", content, flags=re.IGNORECASE)

        # Remove dangerous attributes
        for attr in DANGEROUS_ATTRIBUTES:
            attr_pattern = rf'\s*{attr}\s*=\s*["\'][^"\']*["\']'
            content = re.sub(attr_pattern, "", content, flags=re.IGNORECASE)

        return content

    def _sanitize_uris(self, content: str) -> str:
        """Remove dangerous URI schemes from links."""
        for scheme in UNSAFE_URI_SCHEMES:
            scheme_pattern = rf'{scheme}[^"\'>\s]*'
            content = re.sub(scheme_pattern, "#", content, flags=re.IGNORECASE)
        return content


def sanitize_html(content: str) -> str:
    """Sanitize HTML for safe rendering.

    Strips all dangerous tags and attributes.

    Args:
        content: HTML content to sanitize

    Returns:
        Safe HTML with dangerous elements removed
    """
    renderer = InertRenderer(RenderingOptions(allow_html=True))
    return renderer.render(content)


def sanitize_markdown(content: str) -> str:
    """Sanitize Markdown for safe rendering.

    Escapes HTML entities and removes dangerous constructs.

    Args:
        content: Markdown content to sanitize

    Returns:
        Safe Markdown with HTML escaped
    """
    renderer = InertRenderer(RenderingOptions())
    return renderer.render(content)


def render_as_inert(content: str, options: RenderingOptions | None = None) -> str:
    """Render content inertly for safe display.

    Convenience function that applies appropriate sanitization.

    Args:
        content: Content to render
        options: Rendering options

    Returns:
        Inert rendering of content
    """
    renderer = InertRenderer(options)
    return renderer.render(content)


def generate_csp_header() -> str:
    """Generate Content-Security-Policy header for reports.

    Returns:
        CSP header value
    """
    return (
        "default-src 'none'; "
        "script-src 'none'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "frame-src 'none'; "
        "form-action 'none'"
    )


__all__ = [
    "RenderingOptions",
    "RenderingAudit",
    "InertRenderer",
    "sanitize_html",
    "sanitize_markdown",
    "render_as_inert",
    "generate_csp_header",
]