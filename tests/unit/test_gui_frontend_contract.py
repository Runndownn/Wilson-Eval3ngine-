from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "gui" / "static" / "index.html"
SCRIPT = ROOT / "gui" / "static" / "enhanced.js"
STYLE = ROOT / "gui" / "static" / "ux3.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_five_stage_workflow_is_prominent_and_described() -> None:
    html = _read(INDEX)

    assert html.count('class="tab-number"') == 5
    for number in range(1, 6):
        assert f"Workflow {number} of 5" in html
    assert 'class="tabs workflow-tabs"' in html
    assert "/static/ux3.css" in html


def test_generation_selector_has_popular_and_family_surfaces() -> None:
    html = _read(INDEX)
    script = _read(SCRIPT)

    assert 'id="popular-models"' in html
    assert 'id="model-families"' in html
    assert "slice(0, 6)" in script
    assert "function modelFamily" in script
    assert "we3.openFamilies" in script


def test_endpoint_health_reconciles_model_inventory() -> None:
    script = _read(SCRIPT)

    test_call = 'api(`/api/endpoints/${encodeURIComponent(button.dataset.testEndpoint)}/test`'
    discovery_call = 'api("/api/models/auto-detect", { method: "POST" })'
    assert test_call in script
    assert discovery_call in script
    assert script.index(test_call) < script.index(discovery_call)
    assert "registered model" in script


def test_chart_actions_are_run_scoped_and_demo_is_explicit() -> None:
    html = _read(INDEX)
    script = _read(SCRIPT)

    assert 'id="generate-demo-charts"' in html
    assert 'api("/api/charts/demo", { method: "POST" })' in script
    assert 'data-generate-run="${escapeAttr(runId)}"' in script
    assert "mergedChartRuns" in script
    assert "Refresh will not restore it" in script


def test_destructive_actions_do_not_use_blocking_confirm_dialogs() -> None:
    script = _read(SCRIPT)

    assert "confirm(" not in script
    assert "window.confirm" not in script


def test_socket_updates_do_not_force_navigation() -> None:
    script = _read(SCRIPT)
    handler = script[script.index("function handleSocketMessage") : script.index("async function refreshOverview")]

    assert 'setTab("generate")' not in handler
    assert "updateJob(job)" in handler


def test_reports_explain_contents_and_lazy_load_in_half_card_viewer() -> None:
    html = _read(INDEX)
    script = _read(SCRIPT)

    assert "what the report contains" in html.lower()
    assert "function reportSummary" in script
    assert "Open full report" in script
    assert "data-pdf-half" in script
    assert "report-half-card" in script
    assert "report-half-row" in script
    assert "iframe.dataset.src" in script


def test_visual_boundary_layer_has_required_components() -> None:
    css = _read(STYLE)

    for selector in (
        ".workflow-tabs",
        ".surface-heading",
        ".bounded-grid",
        ".endpoint-card",
        ".popular-model-grid",
        ".model-family",
        ".chart-run-summary",
        ".report-half-meta",
        ".report-half-card",
        ".pdf-half-frame",
    ):
        assert selector in css
