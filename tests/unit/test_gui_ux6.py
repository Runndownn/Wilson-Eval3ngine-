from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "gui" / "static" / "ux6.css").read_text(encoding="utf-8")
JS = (ROOT / "gui" / "static" / "ux6.js").read_text(encoding="utf-8")
OVERLAY = (ROOT / "src" / "wilson_eval3ngine" / "gui" / "ux_overlay.py").read_text(encoding="utf-8")


def test_report_gallery_uses_exactly_two_desktop_columns() -> None:
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in CSS
    assert ".report-default-open" in CSS
    assert "grid-column: auto !important" in CSS
    assert "@media (max-width: 1023px)" in CSS
    assert "grid-template-columns: minmax(0, 1fr)" in CSS


def test_main_content_uses_fluid_window_edge_alignment() -> None:
    assert "max-width: none !important" in CSS
    assert "padding-inline: clamp(16px, 2.25vw, 44px)" in CSS


def test_chart_window_has_runtime_viewport_guard_and_reset() -> None:
    assert "function clampChartWindow()" in JS
    assert "document.documentElement.clientWidth" in JS
    assert "window.visualViewport" in JS
    assert "ResizeObserver" in JS
    assert 'reset.id = "chart-window-reset"' in JS


def test_versioned_assets_are_loaded_by_the_composition_overlay() -> None:
    assert "/static/ux6.css?v=20260801-ux6" in OVERLAY
    assert "/static/ux6.js?v=20260801-ux6" in OVERLAY
