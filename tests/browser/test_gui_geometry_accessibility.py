from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "gui" / "static" / "ux6.css").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "gui" / "static" / "ux6.js").read_text(encoding="utf-8")

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>WE3 browser contract</title>
  <style>* { box-sizing: border-box; } html, body { margin: 0; min-width: 0; }</style>
</head>
<body>
  <main>
    <section class="report-grid" aria-label="Evaluation reports">
      <article class="report-card"><h4>Report one</h4><p class="report-meta">A</p><div class="report-viewer"></div><div></div><div class="actions"><button>Open one</button></div></article>
      <article class="report-card report-default-open"><h4>Report two</h4><p class="report-meta">B</p><div class="pdf-preview"></div><div></div><div class="actions"><button>Open two</button></div></article>
    </section>
  </main>
  <section id="chart-window" class="chart-window" role="dialog" aria-label="Chart detail" tabindex="-1" style="position:fixed;left:5000px;top:5000px;width:1800px;height:1400px">
    <header><div class="window-actions"><button id="close-chart">Close</button></div></header>
    <div class="chart-stage"><img alt="Synthetic chart" /></div>
  </section>
</body>
</html>
"""


def _browser_page(
    viewport: dict[str, int],
    *,
    device_scale_factor: float = 1.0,
):
    manager = sync_playwright().start()
    browser = manager.chromium.launch()
    context = browser.new_context(
        viewport=viewport,
        device_scale_factor=device_scale_factor,
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.set_content(HTML)
    page.add_style_tag(content=CSS)
    page.add_script_tag(content=JAVASCRIPT)
    page.wait_for_timeout(100)
    return manager, browser, page


def _horizontal_overflow(page) -> float:
    return page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )


@pytest.mark.browser
def test_desktop_reports_are_exactly_two_equal_columns() -> None:
    manager, browser, page = _browser_page({"width": 1440, "height": 1000})
    try:
        boxes = page.locator(".report-card").evaluate_all(
            "nodes => nodes.map(node => node.getBoundingClientRect())"
        )
        assert len(boxes) == 2
        assert abs(boxes[0]["width"] - boxes[1]["width"]) <= 1
        assert abs(boxes[0]["top"] - boxes[1]["top"]) <= 1
        assert boxes[0]["right"] <= boxes[1]["left"]
        main_box = page.locator("main").bounding_box()
        assert main_box is not None
        assert main_box["width"] >= 1439
        assert _horizontal_overflow(page) <= 1
    finally:
        browser.close()
        manager.stop()


@pytest.mark.browser
@pytest.mark.parametrize("width", [320, 600, 1023])
def test_narrow_viewports_use_one_column_without_horizontal_overflow(width: int) -> None:
    manager, browser, page = _browser_page({"width": width, "height": 900})
    try:
        boxes = page.locator(".report-card").evaluate_all(
            "nodes => nodes.map(node => node.getBoundingClientRect())"
        )
        assert boxes[1]["top"] > boxes[0]["bottom"]
        assert _horizontal_overflow(page) <= 1
    finally:
        browser.close()
        manager.stop()


@pytest.mark.browser
def test_chart_window_is_clamped_and_reset_is_keyboard_reachable() -> None:
    manager, browser, page = _browser_page({"width": 1280, "height": 720})
    try:
        window_box = page.locator("#chart-window").bounding_box()
        assert window_box is not None
        assert window_box["x"] >= 8
        assert window_box["y"] >= 8
        assert window_box["x"] + window_box["width"] <= 1272
        assert window_box["y"] + window_box["height"] <= 712

        reset = page.locator("#chart-window-reset")
        assert reset.count() == 1
        reset.focus()
        assert page.evaluate("document.activeElement.id") == "chart-window-reset"
        page.keyboard.press("Enter")
        page.wait_for_timeout(50)

        reset_box = page.locator("#chart-window").bounding_box()
        assert reset_box is not None
        assert reset_box["x"] >= 8
        assert reset_box["y"] >= 8
        assert reset_box["x"] + reset_box["width"] <= 1272
        assert reset_box["y"] + reset_box["height"] <= 712
    finally:
        browser.close()
        manager.stop()


@pytest.mark.browser
@pytest.mark.parametrize("scale", [1.25, 1.5, 2.0])
def test_layout_survives_browser_zoom_emulation(scale: float) -> None:
    # Browser zoom reduces the available CSS-pixel viewport while preserving the
    # physical window. Device scale factor models the denser rendered surface.
    viewport = {"width": int(1280 / scale), "height": int(900 / scale)}
    manager, browser, page = _browser_page(
        viewport,
        device_scale_factor=scale,
    )
    try:
        page.dispatch_event("body", "pointerup")
        page.wait_for_timeout(50)
        chart = page.locator("#chart-window").bounding_box()
        assert _horizontal_overflow(page) <= 1
        assert chart is not None
        assert chart["x"] >= 8 and chart["y"] >= 8
        assert chart["x"] + chart["width"] <= viewport["width"] - 8
        assert chart["y"] + chart["height"] <= viewport["height"] - 8
    finally:
        browser.close()
        manager.stop()
