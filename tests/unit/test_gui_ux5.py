"""Source-contract tests for the model-family and evidence-gallery GUI pass."""

from __future__ import annotations

from pathlib import Path

from wilson_eval3ngine.gui.run_gui import resolve_launcher_host, validate_bind_host
from wilson_eval3ngine.gui.ux_overlay import _render_overlay


ROOT = Path(__file__).resolve().parents[2]
UX5_JS = ROOT / "gui" / "static" / "ux5.js"
UX5_CSS = ROOT / "gui" / "static" / "ux5.css"


def test_legacy_cli_wildcards_are_repaired_to_loopback() -> None:
    assert resolve_launcher_host("0.0.0.0") == ("127.0.0.1", True)
    assert resolve_launcher_host("::") == ("127.0.0.1", True)
    assert resolve_launcher_host("[::]") == ("127.0.0.1", True)


def test_explicit_remote_hosts_still_fail_closed() -> None:
    for host in ("192.168.1.20", "8.8.8.8", "example.com"):
        try:
            resolve_launcher_host(host)
        except ValueError:
            pass
        else:  # pragma: no cover - assertion branch
            raise AssertionError(f"remote host unexpectedly accepted: {host}")

    # The authoritative validator remains strict even for historical defaults.
    try:
        validate_bind_host("0.0.0.0")
    except ValueError:
        pass
    else:  # pragma: no cover - assertion branch
        raise AssertionError("wildcard bind unexpectedly accepted")


def test_overlay_injects_ux4_and_ux5_once(tmp_path: Path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<html><head></head><body></body></html>", encoding="utf-8")

    first = _render_overlay(index)
    index.write_text(first, encoding="utf-8")
    second = _render_overlay(index)

    for asset in ("ux4.css", "ux4.js", "ux5.css", "ux5.js"):
        assert first.count(asset) == 1
        assert second.count(asset) == 1


def test_ux5_family_and_report_contracts() -> None:
    source = UX5_JS.read_text(encoding="utf-8")

    assert "AUTO_OPEN_REPORTS = 4" in source
    assert "model-family-dialog" in source
    assert "Recommended available models" in source
    assert "Popular in this family" not in source
    assert "offline-catalog" in source
    assert "data-open-inventory" in source
    assert "endpointAvailable !== false" in source
    assert "data-family-select" in source
    assert "data-family-delete" in source
    assert "Hide card viewer" in source
    assert "run-summary-full-row" in source
    assert "Why it matters:" in source
    assert "confirm(" not in source


def test_ux5_visual_contracts() -> None:
    source = UX5_CSS.read_text(encoding="utf-8")

    assert ".model-family-card" in source
    assert ".model-family-dialog" in source
    assert ".model-grid.inventory-sections" in source
    assert ".offline-catalog" in source
    assert ".model-family-grid" in source
    assert ".run-summary-full-row" in source
    assert "aspect-ratio: 16 / 10" in source
    assert ".report-default-open" in source
    assert "prefers-reduced-motion" in source
