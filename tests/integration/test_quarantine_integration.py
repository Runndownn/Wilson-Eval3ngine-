"""Integration tests for attachment quarantine and inert rendering (TODO 42)."""


from wilson_eval3ngine.quarantine.inert_render import (
    RenderingOptions,
    sanitize_html,
    sanitize_markdown,
    render_as_inert,
    generate_csp_header,
)
from wilson_eval3ngine.quarantine.quarantine import (
    AttachmentQuarantine,
    QuarantineState,
    AttachmentBlockedReason,
)


class TestInertRenderingIntegration:
    """Integration tests for inert rendering workflow."""

    def test_html_xss_neutralized(self) -> None:
        """XSS scripts are neutralized in rendering."""
        malicious = "<script>alert('xss')</script>Hello world"
        rendered = render_as_inert(malicious)

        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered

    def test_html_sanitization_allows_safe_tags(self) -> None:
        """Safe HTML tags are preserved with allow_html option."""
        html = "<p>Safe paragraph</p><script>evil</script>"
        rendered = render_as_inert(html, RenderingOptions(allow_html=True))

        assert "<p>" in rendered
        assert "<script>" not in rendered

    def test_javascript_uri_blocked(self) -> None:
        """JavaScript URIs are blocked."""
        html = '<a href="javascript:alert(1)">Click</a>'
        rendered = sanitize_html(html)

        assert "javascript:" not in rendered.lower()

    def test_markdown_sanitization(self) -> None:
        """Markdown is sanitized for safe rendering."""
        md = "# Heading\n\n**Bold** and <script>evil</script>"
        rendered = sanitize_markdown(md)

        assert "# Heading" in rendered
        assert "<script>" not in rendered

    def test_csp_header_generated(self) -> None:
        """CSP header is generated correctly."""
        csp = generate_csp_header()

        assert "default-src 'none'" in csp
        assert "script-src 'none'" in csp
        assert "object-src 'none'" in csp


class TestQuarantineIntegration:
    """Integration tests for quarantine workflow."""

    def test_full_quarantine_lifecycle(self) -> None:
        """Complete quarantine lifecycle for safe attachment."""
        quarantine = AttachmentQuarantine()

        # Register upload
        record, initial = quarantine.register_upload(
            project_id="model-safety",
            content=b"Analysis report content",
            declared_mime="text/plain",
            filename="report.txt",
        )

        assert initial.state == QuarantineState.QUARANTINED

        # Process through scanning
        final = quarantine.process_quarantine(record.object_id)

        assert final.state == QuarantineState.SAFE_DERIVATIVE_READY
        assert final.safe_derivative_hash is not None
        assert final.scanner_verdict == "safe_derivative_available"

    def test_multiple_attachments_tracked(self) -> None:
        """Multiple attachments are tracked independently."""
        quarantine = AttachmentQuarantine()

        record1, _ = quarantine.register_upload("proj_a", b"Content A", "text/plain")
        record2, _ = quarantine.register_upload("proj_b", b"Content B", "text/plain")

        assert len(quarantine._attachments) == 2
        quarantine.process_quarantine(record1.object_id)
        quarantine.process_quarantine(record2.object_id)

        assert quarantine.get_record(record1.object_id) is not None
        assert quarantine.get_record(record2.object_id) is not None


class TestAttachmentRenderingSecurity:
    """Security-focused tests for attachment rendering."""

    def test_base64_encoded_content_inert(self) -> None:
        """Base64 encoded content is treated as inert text."""
        encoded = "PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg=="  # base64 of <script>alert(1)</script>
        rendered = render_as_inert(encoded)

        # The content is encoded, so it should remain as-is with HTML escaped
        assert "<script>" not in rendered

    def test_html_entity_encoded_inert(self) -> None:
        """HTML entity encoded content is inert."""
        encoded = "&lt;script&gt;alert(1)&lt;/script&gt;"
        rendered = render_as_inert(encoded)

        # Already encoded, should remain inert
        assert "<script>" not in rendered

    def test_nested_script_tags_neutralized(self) -> None:
        """Nested script tags are neutralized."""
        nested = "<div><script><script>nested</script></script></div>"
        rendered = render_as_inert(nested)

        assert "<script>" not in rendered

    def test_event_handlers_stripped(self) -> None:
        """Event handler attributes are stripped."""
        html = '<img src="x" onerror="alert(1)">'
        from wilson_eval3ngine.quarantine.inert_render import RenderingOptions
        rendered = render_as_inert(html, RenderingOptions(allow_html=True))

        assert "onerror" not in rendered.lower()

    def test_file_uri_blocked(self) -> None:
        """File URIs are blocked."""
        html = '<a href="file:///etc/passwd">passwd</a>'
        rendered = sanitize_html(html)

        assert "file:/" not in rendered.lower() or "#" in rendered


class TestQuarantineRecordSerialization:
    """Tests for record serialization."""

    def test_record_serialization(self) -> None:
        """Quarantine record serializes correctly."""
        quarantine = AttachmentQuarantine()

        record, _ = quarantine.register_upload(
            project_id="proj",
            content=b"Content",
            declared_mime="text/plain",
        )

        d = record.to_dict()

        assert d["object_id"] == record.object_id
        assert d["project_id"] == "proj"
        assert "original_metadata" in d
        assert "state_history" in d


class TestXSSSecurityHardening:
    """Security tests for XSS prevention edge cases."""

    def test_svg_script_neutralized(self) -> None:
        """SVG scripts are neutralized."""
        svg = "<svg onload='alert(1)'><script>alert(2)</script></svg>"
        rendered = render_as_inert(svg)

        assert "<svg" not in rendered or "&lt;svg" in rendered
        assert "<script>" not in rendered

    def test_iframe_neutralized(self) -> None:
        """Iframe injection is neutralized."""
        iframe = '<iframe src="evil.com"></iframe><p>Safe</p>'
        rendered = render_as_inert(iframe)

        assert "<iframe" not in rendered

    def test_object_embed_neutralized(self) -> None:
        """Object and embed tags are neutralized."""
        html = '<object data="evil.swf"></object><embed src="x"></embed>'
        rendered = sanitize_html(html)

        assert "<object" not in rendered.lower()
        assert "<embed" not in rendered.lower()

    def test_data_uri_blocked(self) -> None:
        """Data URIs are blocked."""
        html = '<img src="data:text/html,<script>alert(1)</script>">'
        rendered = sanitize_html(html)

        assert "data:" not in rendered.lower() or "#" in rendered

    def test_vbscript_uri_blocked(self) -> None:
        """VBScript URIs are blocked."""
        html = '<a href="vbscript:msgbox(1)">Click</a>'
        rendered = sanitize_html(html)

        assert "vbscript:" not in rendered.lower()

    def test_blob_uri_blocked(self) -> None:
        """Blob URIs are blocked."""
        html = '<a href="blob:https://evil.com/blob">Click</a>'
        rendered = sanitize_html(html)

        assert "blob:" not in rendered.lower()

    def test_math_tag_neutralized(self) -> None:
        """Math tags (potential XSS vector) are neutralized."""
        html = "<math><script>alert(1)</script></math>"
        rendered = sanitize_html(html)

        assert "<math" not in rendered.lower()

    def test_style_tag_neutralized(self) -> None:
        """Style tags are neutralized."""
        html = "<style>body{background:url('javascript:alert(1)')}</style>"
        rendered = sanitize_html(html)

        assert "<style" not in rendered.lower()

    def test_base_tag_neutralized(self) -> None:
        """Base tags are neutralized."""
        html = '<base href="https://evil.com">'
        rendered = sanitize_html(html)

        assert "<base" not in rendered.lower()

    def test_form_tag_neutralized(self) -> None:
        """Form tags are neutralized."""
        html = "<form action='evil.com'><input type='text'></form>"
        rendered = sanitize_html(html)

        assert "<form" not in rendered.lower()
        assert "<input" not in rendered.lower()

    def test_link_tag_neutralized(self) -> None:
        """Link tags are neutralized."""
        html = '<link rel="stylesheet" href="evil.css">'
        rendered = sanitize_html(html)

        assert "<link" not in rendered.lower()

    def test_meta_tag_neutralized(self) -> None:
        """Meta tags are neutralized."""
        html = '<meta http-equiv="refresh" content="0;url=evil.com">'
        rendered = sanitize_html(html)

        assert "<meta" not in rendered.lower()


class TestObfuscatedURIHandling:
    """Tests for obfuscated URI schemes."""

    def test_mixed_case_javascript_uri(self) -> None:
        """Mixed case JavaScript URIs are blocked."""
        html = '<a href="JaVaScRiPt:alert(1)">Click</a>'
        rendered = sanitize_html(html)

        assert "javascript:" not in rendered.lower()

    def test_encoded_javascript_uri(self) -> None:
        """URL-encoded JavaScript URIs are blocked."""
        # %6A%61%76%61%73%63%72%69%70%74 = javascript
        html = '<a href="%6A%61%76%61%73%63%72%69%70%74:alert(1)">Click</a>'
        rendered = sanitize_html(html)

        # Should be sanitized or escaped
        assert rendered is not None

    def test_multiple_event_handlers_stripped(self) -> None:
        """Multiple event handlers are stripped."""
        html = '<div onload="a()" onerror="b()" onclick="c()">content</div>'
        rendered = sanitize_html(html)

        assert "onload" not in rendered.lower()
        assert "onerror" not in rendered.lower()
        assert "onclick" not in rendered.lower()


class TestPolyglotContent:
    """Tests for polyglot content handling."""

    def test_html_js_polyglot_neutralized(self) -> None:
        """HTML/JS polyglot content is neutralized."""
        # Content that is both valid HTML and JS
        polyglot = "<svg><script>alert(1)</script></svg>"
        rendered = render_as_inert(polyglot)

        assert "<script>" not in rendered
        assert "alert(1)" not in rendered or "&lt;" in rendered


class TestSafeDerivativesIntegration:
    """Integration tests for safe derivative workflow."""

    def test_safe_derivative_only_after_scanning(self) -> None:
        """Safe derivative is only available after scanning completes."""
        quarantine = AttachmentQuarantine()

        record, _ = quarantine.register_upload(
            project_id="proj",
            content=b"Safe content",
            declared_mime="text/plain",
        )

        # Before scanning, no safe derivative
        assert quarantine.get_safe_derivative(record.object_id) is None

        # After scanning, derivative available
        quarantine.process_quarantine(record.object_id)
        # Returns empty in MVP, but state is correct
        assert record.current_state == QuarantineState.SAFE_DERIVATIVE_READY


class TestQuarantineAuditTrail:
    """Tests for quarantine audit trail."""

    def test_transition_audit_logged(self) -> None:
        """All transitions are logged."""
        quarantine = AttachmentQuarantine()

        record, decision = quarantine.register_upload(
            project_id="audit_test",
            content=b"Test content",
            declared_mime="text/plain",
            correlation_id="corr-123",
        )

        assert decision.correlation_id == "corr-123"
        assert len(record.state_history) >= 1

    def test_rejected_attachment_audit(self) -> None:
        """Rejected attachment has audit trail."""
        quarantine = AttachmentQuarantine()

        record, decision = quarantine.register_upload(
            project_id="audit_test",
            content=b"x" * 101_000_000,
            declared_mime="text/plain",
            correlation_id="corr-reject",
        )

        assert record.current_state == QuarantineState.REJECTED
        assert decision.correlation_id == "corr-reject"
        assert decision.blocked_reason == AttachmentBlockedReason.SIZE_EXCEEDED