"""Attachment quarantine and inert rendering module (TODO 42).

T6.1.5 - Inert rendering and attachment quarantine for safe content handling.

Provides:
- Quarantine state machine for attachments
- Content-based MIME detection
- Safe derivative generation in isolated converters
- Inert HTML/Markdown rendering with CSP enforcement
- File structure validation with resource limits
"""

from .quarantine import (
    AttachmentQuarantine,
    QuarantineState,
    AttachmentRecord,
    QuarantineDecision,
    AttachmentMetadata,
    process_attachment,
    validate_attachment_content,
)
from .inert_render import (
    InertRenderer,
    RenderingOptions,
    RenderingAudit,
    render_as_inert,
    sanitize_html,
    sanitize_markdown,
    generate_csp_header,
)

__all__ = [
    # Quarantine
    "AttachmentQuarantine",
    "QuarantineState",
    "AttachmentRecord",
    "QuarantineDecision",
    "AttachmentMetadata",
    "process_attachment",
    "validate_attachment_content",
    # Rendering
    "InertRenderer",
    "RenderingOptions",
    "RenderingAudit",
    "render_as_inert",
    "sanitize_html",
    "sanitize_markdown",
    "generate_csp_header",
]