"""Attachment quarantine and inert rendering for safe content handling.

Provides content-based type validation, quarantine state transitions, bounded
structure checks, isolated derivative generation, and inert HTML/Markdown
rendering with an explicit content-security policy.
"""

from .quarantine import (
    AttachmentMetadata,
    AttachmentQuarantine,
    AttachmentRecord,
    QuarantineDecision,
    QuarantineState,
    process_attachment,
    validate_attachment_content,
)
from .inert_render import (
    InertRenderer,
    RenderingAudit,
    RenderingOptions,
    generate_csp_header,
    render_as_inert,
    sanitize_html,
    sanitize_markdown,
)

__all__ = [
    "AttachmentMetadata",
    "AttachmentQuarantine",
    "AttachmentRecord",
    "QuarantineDecision",
    "QuarantineState",
    "InertRenderer",
    "RenderingAudit",
    "RenderingOptions",
    "generate_csp_header",
    "process_attachment",
    "render_as_inert",
    "sanitize_html",
    "sanitize_markdown",
    "validate_attachment_content",
]
