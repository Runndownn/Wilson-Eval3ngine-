#!/usr/bin/env python3
"""Generate all 15 charts for the test-run-final chart gallery using real evaluation data.

This script uses the actual chart generation functions from server.py with the
real evaluation JSON sidecars from docs/reports/model-evals/ to produce high-quality
charts that accurately reflect the code's output.

Only models with at least one successful evaluation are included, since the early
development runs were mostly connection failures that don't reflect real model performance.
The pass/fail heatmap is replaced with a Code Sophistication Progression Heatmap
that shows how the codebase evolved across the 8 development phases.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wilson_eval3ngine.gui.server import (
    generate_charts_for_run,
    _load_evaluation_jsons,
    _generate_model_radar_chart,
    _generate_response_time_chart,
    _generate_heatmap_chart,
    _generate_tokens_chart,
    _generate_security_code_chart,
    _generate_run_timeline_chart,
    _generate_success_rate_chart,
    _generate_scatter_plot,
    _generate_line_chart,
    _generate_distribution_histogram,
    _generate_confidence_interval_chart,
    _generate_correlation_heatmap,
    _generate_stacked_bar_chart,
    _generate_box_plot,
    _generate_radar_comparison,
    REPORTS_DIR,
    CHARTS_DIR,
)

# Import the sophistication heatmap generator
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_sophistication_heatmap import generate_sophistication_heatmap


def _parse_success_rate(sr_raw):
    """Parse prompt_success_rate string like '5/5' into a float 0-1."""
    if isinstance(sr_raw, str) and "/" in str(sr_raw):
        parts = str(sr_raw).split("/")
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[0]) / int(parts[1])
        return 0
    if isinstance(sr_raw, (int, float)):
        return float(sr_raw)
    return 0


def _has_successful_eval(ej):
    """Check if an evaluation JSON has at least one successful evaluation."""
    evals = ej.get("evaluations", [])
    return any(e.get("success", False) for e in evals)


def _is_fully_successful(ej):
    """Check if ALL evaluations in the JSON were successful.

    Only fully successful runs are included in README charts, since partial
    successes may indicate configuration issues or intermittent failures.
    """
    evals = ej.get("evaluations", [])
    if not evals:
        return False
    return all(e.get("success", False) for e in evals)


def _model_score(e):
    """Score models for radar chart selection: prefer complete data + diverse profiles."""
    eval_list = e.get("evaluations", [])
    eval_count = len(eval_list)
    sr = _parse_success_rate(e.get("prompt_success_rate", "0/5"))
    tokens = e.get("total_tokens", 0)
    return (eval_count, sr, tokens)


def main():
    # Load real evaluation JSON sidecars
    eval_jsons = _load_evaluation_jsons()
    print(f"Loaded {len(eval_jsons)} evaluation JSON files")

    # Filter to only models with ALL successful evaluations
    # Partial successes may indicate configuration issues; only fully
    # successful runs are included in README charts
    successful_evals = [ej for ej in eval_jsons if _is_fully_successful(ej)]
    print(f"Models with all evaluations successful: {len(successful_evals)}")

    # Build evals_by_model dict from successful evaluations only
    models_in_evals = [ej.get("model", "") for ej in successful_evals if ej.get("model")]
    print(f"Models with successful data: {models_in_evals}")

    # Collect all unique prompts from successful evaluation data
    all_prompts = []
    for ej in successful_evals:
        prompts = ej.get("prompts", [])
        if prompts:
            all_prompts.extend(prompts)
    # Deduplicate while preserving order
    seen = set()
    unique_prompts = []
    for p in all_prompts:
        if p not in seen:
            seen.add(p)
            unique_prompts.append(p)
    # Use up to 5 prompts (the standard test suite size)
    prompts = unique_prompts[:5] if unique_prompts else [
        "Write a haiku about quantum computing",
        "Create a JSON object representing a book",
        "Write a Python function for fibonacci",
        "Implement a REST API endpoint in Node.js",
        "Write a SQL query for top customers",
    ]
    print(f"Using {len(prompts)} prompts for chart generation")

    # Build evals_by_model from successful evaluations only
    evals_by_model = {}
    for ej in successful_evals:
        model = ej.get("model", "")
        if model and model in models_in_evals:
            evals_by_model[model] = ej

    # For radar charts, select a representative subset of 6 models with diverse profiles.
    # Using all models creates an unreadable mess of overlapping polygons.
    # Only fully successful runs are considered (no partial failures).
    sorted_models = sorted(evals_by_model.items(), key=lambda x: _model_score(x[1]), reverse=True)
    radar_model_names = [m for m, _ in sorted_models[:6]]
    evals_by_model_radar = {m: evals_by_model[m] for m in radar_model_names}

    print(f"\nModels selected for radar charts (6): {radar_model_names}")
    print(f"\nModels in evals_by_model: {list(evals_by_model.keys())}")

    # Load real telemetry runs for timeline chart
    telemetry_path = CHARTS_DIR.parent.parent / "data" / "telemetry.json"
    if telemetry_path.exists():
        with open(telemetry_path) as f:
            runs = json.load(f)
        print(f"Loaded {len(runs)} telemetry runs")
    else:
        runs = []

    run_id = "test-run-final"

    # Generate each chart individually
    # Chart 1: Radar - use filtered 6 models for readability
    results = {}

    print("\n--- Generating Charts ---")

    # Chart 1: Model Performance Radar (6 models only)
    try:
        url = _generate_model_radar_chart(run_id, evals_by_model_radar)
        if url:
            results["radar"] = url
            print(f"  ✓ radar (6 models): {url}")
    except Exception as e:
        print(f"  ✗ radar: ERROR - {e}")

    # Chart 2: Response Time by Model & Prompt
    try:
        url = _generate_response_time_chart(run_id, evals_by_model, prompts)
        if url:
            results["response_times"] = url
            print(f"  ✓ response_times: {url}")
    except Exception as e:
        print(f"  ✗ response_times: ERROR - {e}")

    # Chart 3: Code Sophistication Heatmap (replaces pass/fail heatmap)
    try:
        url = generate_sophistication_heatmap(run_id)
        if url:
            results["heatmap"] = url
            print(f"  ✓ sophistication_heatmap: {url}")
    except Exception as e:
        print(f"  ✗ heatmap: ERROR - {e}")

    # Chart 4: Token Usage by Model
    try:
        url = _generate_tokens_chart(run_id, evals_by_model)
        if url:
            results["tokens"] = url
            print(f"  ✓ tokens: {url}")
    except Exception as e:
        print(f"  ✗ tokens: ERROR - {e}")

    # Chart 5: Code & Security Awareness
    try:
        url = _generate_security_code_chart(run_id, evals_by_model)
        if url:
            results["security_code"] = url
            print(f"  ✓ security_code: {url}")
    except Exception as e:
        print(f"  ✗ security_code: ERROR - {e}")

    # Chart 6: Run Execution Timeline
    try:
        url = _generate_run_timeline_chart(run_id, runs) if runs else None
        if url:
            results["timeline"] = url
            print(f"  ✓ timeline: {url}")
    except Exception as e:
        print(f"  ✗ timeline: ERROR - {e}")

    # Chart 7: Prompt Success Rate
    try:
        url = _generate_success_rate_chart(run_id, evals_by_model)
        if url:
            results["success_rate"] = url
            print(f"  ✓ success_rate: {url}")
    except Exception as e:
        print(f"  ✗ success_rate: ERROR - {e}")

    # Chart 8: Scatter Plot (Response Time vs Token Count)
    try:
        url = _generate_scatter_plot(run_id, evals_by_model)
        if url:
            results["scatter_time_tokens"] = url
            print(f"  ✓ scatter_time_tokens: {url}")
    except Exception as e:
        print(f"  ✗ scatter_time_tokens: ERROR - {e}")

    # Chart 9: Response Time Trend (Line Chart)
    try:
        url = _generate_line_chart(run_id, evals_by_model, prompts)
        if url:
            results["line_response_trend"] = url
            print(f"  ✓ line_response_trend: {url}")
    except Exception as e:
        print(f"  ✗ line_response_trend: ERROR - {e}")

    # Chart 10: Response Time Distribution (Histogram)
    try:
        url = _generate_distribution_histogram(run_id, evals_by_model)
        if url:
            results["histogram_distribution"] = url
            print(f"  ✓ histogram_distribution: {url}")
    except Exception as e:
        print(f"  ✗ histogram_distribution: ERROR - {e}")

    # Chart 11: Success Rate with Confidence Intervals
    try:
        url = _generate_confidence_interval_chart(run_id, evals_by_model)
        if url:
            results["confidence_intervals"] = url
            print(f"  ✓ confidence_intervals: {url}")
    except Exception as e:
        print(f"  ✗ confidence_intervals: ERROR - {e}")

    # Chart 12: Metric Correlation Heatmap
    try:
        url = _generate_correlation_heatmap(run_id, evals_by_model)
        if url:
            results["correlation_heatmap"] = url
            print(f"  ✓ correlation_heatmap: {url}")
    except Exception as e:
        print(f"  ✗ correlation_heatmap: ERROR - {e}")

    # Chart 13: Outcome Distribution (Stacked Bar)
    try:
        url = _generate_stacked_bar_chart(run_id, evals_by_model)
        if url:
            results["stacked_outcomes"] = url
            print(f"  ✓ stacked_outcomes: {url}")
    except Exception as e:
        print(f"  ✗ stacked_outcomes: ERROR - {e}")

    # Chart 14: Response Time Distribution (Box Plot)
    try:
        url = _generate_box_plot(run_id, evals_by_model)
        if url:
            results["boxplot_response_times"] = url
            print(f"  ✓ boxplot_response_times: {url}")
    except Exception as e:
        print(f"  ✗ boxplot_response_times: ERROR - {e}")

    # Chart 15: Extended Radar (6 models only)
    try:
        url = _generate_radar_comparison(run_id, evals_by_model_radar)
        if url:
            results["radar_extended"] = url
            print(f"  ✓ radar_extended (6 models): {url}")
    except Exception as e:
        print(f"  ✗ radar_extended: ERROR - {e}")

    # List final chart files
    run_dir = CHARTS_DIR / run_id
    if run_dir.exists():
        print(f"\n--- Final chart files in {run_dir} ---")
        for f in sorted(run_dir.glob("*.png")):
            print(f"  {f.name}: {f.stat().st_size} bytes")

    print(f"\nTotal charts generated: {len(results)}")


if __name__ == "__main__":
    main()
