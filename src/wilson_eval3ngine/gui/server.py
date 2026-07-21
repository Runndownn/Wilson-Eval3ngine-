"""FastAPI + WebSocket backend for Wilson Eval3ngine GUI."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import secrets
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

logger = logging.getLogger("we3.gui")

app = FastAPI(title="Wilson Eval3ngine GUI")

# Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GUI_STATIC_DIR = WORKSPACE_ROOT / "gui" / "static"
REPORTS_DIR = WORKSPACE_ROOT / "docs" / "reports" / "model-evals"
GUI_DATA_DIR = WORKSPACE_ROOT / "gui" / "data"
CHARTS_DIR = GUI_STATIC_DIR / "charts"

# Ensure directories exist
GUI_STATIC_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GUI_DATA_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS_FILE = GUI_DATA_DIR / "endpoints.json"
MODELS_FILE = GUI_DATA_DIR / "models.json"
TELEMETRY_FILE = GUI_DATA_DIR / "telemetry.json"
PROMPT_PACKAGES_FILE = GUI_DATA_DIR / "prompt_packages.json"
JOBS_FILE = GUI_DATA_DIR / "jobs.json"

# Background report generation state
_report_process: asyncio.subprocess.Process | None = None
_report_task: asyncio.Task | None = None
_report_lock = asyncio.Lock()


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_endpoints() -> list[dict[str, Any]]:
    return _load_json(ENDPOINTS_FILE, [])


def _save_endpoints(endpoints: list[dict[str, Any]]) -> None:
    _save_json(ENDPOINTS_FILE, endpoints)


def _get_models() -> list[dict[str, Any]]:
    return _load_json(MODELS_FILE, [])


def _save_models(models: list[dict[str, Any]]) -> None:
    _save_json(MODELS_FILE, models)


def _get_telemetry() -> list[dict[str, Any]]:
    return _load_json(TELEMETRY_FILE, [])


def _save_telemetry(telemetry: list[dict[str, Any]]) -> None:
    _save_json(TELEMETRY_FILE, telemetry)


def _add_telemetry_entry(entry: dict[str, Any]) -> None:
    telemetry = _get_telemetry()
    telemetry.insert(0, entry)
    _save_telemetry(telemetry)


def _load_jobs() -> dict[str, Any]:
    return _load_json(JOBS_FILE, {})


def _save_jobs(jobs: dict[str, Any]) -> None:
    _save_json(JOBS_FILE, jobs)


def _get_job(job_id: str) -> dict[str, Any] | None:
    return _load_jobs().get(job_id)


def _update_job(job_id: str, updates: dict[str, Any]) -> None:
    jobs = _load_jobs()
    if job_id in jobs:
        jobs[job_id].update(updates)
        jobs[job_id]["updated_at"] = _now_iso()
        _save_jobs(jobs)


def _create_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = {
        "job_id": job_id,
        "run_id": payload.get("run_id", job_id),
        "status": "queued",
        "models": payload.get("models", []),
        "prompts": payload.get("prompts", []),
        "prompt_package": payload.get("prompt_package", ""),
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "finished_at": None,
        "total_reports": len(payload.get("models", [])),
        "completed_reports": 0,
        "failed_reports": 0,
        "processing_reports": 0,
        "queued_reports": len(payload.get("models", [])),
        "current_model": None,
        "current_report": None,
        "current_step": "Queued",
        "estimated_completion": None,
        "elapsed_seconds": 0,
        "models_state": {},
        "reports": [],
        "error": None,
        "progress_file": payload.get("progress_file", ""),
        "websocket_connected": True,
    }
    jobs = _load_jobs()
    jobs[job_id] = job
    _save_jobs(jobs)
    return job


def _is_localhost_endpoint(url: str) -> bool:
    """Check if URL is a localhost/127.0.0.1 endpoint that should be skipped for auto-detection.
    
    The GUI should only use the SSH gateway at 10.133.7.211, not local Ollama instances.
    """
    return url.startswith("http://localhost") or url.startswith("http://127.") or url.startswith("https://localhost") or url.startswith("https://127.")


# ---------------------------------------------------------------------------
# Telemetry chart generation
# ---------------------------------------------------------------------------

# Dark theme colors matching the GUI
_CHART_BG = "#0b1021"
_CHART_PANEL = "#111836"
_CHART_TEXT = "#e6e9f5"
_CHART_MUTED = "#9aa3c7"
_CHART_PRIMARY = "#1f3a8a"
_CHART_ACCENT = "#f5c842"
_CHART_PASS = "#1f9d55"
_CHART_FAIL = "#e5484d"
_CHART_GRID = "#262d4d"  # rgba(255,255,255,0.08) equivalent


def _load_evaluation_jsons() -> list[dict[str, Any]]:
    """Load all evaluation JSON sidecar files from the reports directory."""
    evals = []
    if REPORTS_DIR.exists():
        for path in sorted(REPORTS_DIR.glob("*-evaluation.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_source_file"] = path.name
                evals.append(data)
            except Exception:
                continue
    return evals


def _apply_dark_style(ax=None, fig=None):
    """Apply the Wilson Eval3ngine dark theme to a matplotlib figure/axes."""
    if fig is None:
        fig = plt.gcf()
    fig.patch.set_facecolor(_CHART_BG)
    if ax is None:
        ax = plt.gca()
    ax.set_facecolor(_CHART_PANEL)
    ax.title.set_color(_CHART_TEXT)
    ax.xaxis.label.set_color(_CHART_TEXT)
    ax.yaxis.label.set_color(_CHART_TEXT)
    ax.tick_params(colors=_CHART_TEXT, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(_CHART_GRID)
    ax.grid(True, color=_CHART_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)


def _save_chart(fig, run_id: str, chart_name: str) -> str | None:
    """Save a matplotlib figure as PNG and return the URL path."""
    try:
        run_dir = CHARTS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = run_dir / f"{chart_name}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_CHART_BG, edgecolor="none")
        plt.close(fig)
        return f"/static/charts/{run_id}/{chart_name}.png"
    except Exception as exc:
        logger.warning("Failed to save chart %s/%s: %s", run_id, chart_name, exc)
        try:
            plt.close(fig)
        except Exception:
            pass
        return None


def _generate_model_radar_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a radar chart comparing models across 5 metrics."""
    models = list(evaluations.keys())
    if not models:
        return None

    metrics = ["Avg Time\n(lower=better)", "Success\nRate", "Total\nTokens", "Code\nExamples", "Security\nAwareness"]
    n_metrics = len(metrics)

    # Normalize values to 0-1 scale for radar
    max_time = max((e.get("avg_time", 0) for e in evaluations.values()), default=1) or 1
    max_tokens = max((e.get("total_tokens", 1) for e in evaluations.values()), default=1) or 1
    max_code = max((e.get("code_examples", 0) for e in evaluations.values()), default=1) or 1
    max_sec = max((e.get("security_awareness", 0) for e in evaluations.values()), default=1) or 1

    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]  # close the loop

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]
    for idx, (model, data) in enumerate(evaluations.items()):
        values = [
            1 - (data.get("avg_time", 0) / max_time),  # invert: lower time = higher score
            data.get("prompt_success_rate", "0/5").split("/")[0] if isinstance(data.get("prompt_success_rate"), str) else data.get("prompt_success_rate", 0),
            data.get("total_tokens", 0) / max_tokens,
            data.get("code_examples", 0) / max_code,
            data.get("security_awareness", 0) / max_sec,
        ]
        values += values[:1]
        color = colors[idx % len(colors)]
        ax.plot(angles, values, color=color, linewidth=2, label=model[:20])
        ax.fill(angles, values, color=color, alpha=0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, color=_CHART_TEXT, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color=_CHART_MUTED, fontsize=7)
    ax.set_title("Model Performance Radar", color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=20)
    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
    legend.get_frame().set_facecolor(_CHART_PANEL)
    legend.get_frame().set_edgecolor(_CHART_GRID)
    for text in legend.get_texts():
        text.set_color(_CHART_TEXT)
    plt.tight_layout()
    return _save_chart(fig, run_id, "radar")


def _generate_response_time_chart(run_id: str, evaluations: dict[str, Any], prompts: list[str]) -> str | None:
    """Generate a grouped bar chart of response times per model per prompt."""
    models = list(evaluations.keys())
    if not models:
        return None

    prompt_labels = [f"P{i+1}" for i in range(len(prompts))]
    x = np.arange(len(prompt_labels))
    width = 0.8 / len(models)

    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 1.5), 5))
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]

    for idx, model in enumerate(models):
        data = evaluations.get(model, {})
        evals = data.get("evaluations", [])
        times = [e.get("time", 0) for e in evals[:len(prompts)]]
        while len(times) < len(prompts):
            times.append(0)
        offset = (idx - len(models) / 2 + 0.5) * width
        _ = ax.bar(x + offset, times, width, label=model[:20], color=colors[idx % len(colors)], alpha=0.9)

    ax.set_xlabel("Prompt", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Response Time (s)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Response Time by Model & Prompt", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(prompt_labels, color=_CHART_TEXT, fontsize=9)
    ax.legend(fontsize=8, loc="upper left")
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)
    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "response_times")


def _generate_heatmap_chart(run_id: str, evaluations: dict[str, Any], prompts: list[str]) -> str | None:
    """Generate a pass/fail heatmap grid."""
    models = list(evaluations.keys())
    if not models:
        return None

    prompt_labels = [f"P{i+1}: {p[:25]}..." if len(p) > 25 else f"P{i+1}: {p}" for i, p in enumerate(prompts)]
    data = np.zeros((len(models), len(prompts)))

    for mi, model in enumerate(models):
        evals = evaluations.get(model, {}).get("evaluations", [])
        for pi, e in enumerate(evals[:len(prompts)]):
            data[mi, pi] = 1 if e.get("success", False) else 0

    fig, ax = plt.subplots(figsize=(max(8, len(prompts) * 1.2), max(4, len(models) * 0.8)))
    cmap = matplotlib.colors.ListedColormap([_CHART_FAIL, _CHART_PASS])
    bounds = [0, 0.5, 1]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(np.arange(len(prompt_labels)))
    ax.set_yticks(np.arange(len(models)))
    ax.set_xticklabels(prompt_labels, color=_CHART_TEXT, fontsize=8, rotation=45, ha="right")
    ax.set_yticklabels(models, color=_CHART_TEXT, fontsize=9)
    ax.set_title("Pass / Fail Heatmap", color=_CHART_TEXT, fontsize=13, fontweight="bold")

    # Add text annotations
    for mi in range(len(models)):
        for pi in range(len(prompts)):
            label = "PASS" if data[mi, pi] == 1 else "FAIL"
            color = _CHART_TEXT if data[mi, pi] == 1 else _CHART_TEXT
            ax.text(pi, mi, label, ha="center", va="center", color=color, fontsize=8, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.6, aspect=30)
    cbar.set_ticks([0.25, 0.75])
    cbar.set_ticklabels(["FAIL", "PASS"])
    cbar.ax.yaxis.set_tick_params(color=_CHART_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_CHART_TEXT, fontsize=9)
    cbar.outline.set_edgecolor(_CHART_GRID)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "heatmap")


def _generate_tokens_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a bar chart of total tokens per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    tokens = [evaluations[m].get("total_tokens", 0) for m in models]
    colors = ["#1f3a8a", "#f5c842", "#1f9d55", "#e5484d", "#9333ea", "#06b6d4", "#f97316", "#64748b"]
    bar_colors = [colors[i % len(colors)] for i in range(len(models))]

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    bars = ax.bar(models, tokens, color=bar_colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Total Tokens Generated", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Token Usage by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")

    for bar, val in zip(bars, tokens):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(tokens) * 0.01,
                str(val), ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "tokens")


def _generate_security_code_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a dual bar chart for security awareness and code examples."""
    models = list(evaluations.keys())
    if not models:
        return None

    code_counts = [evaluations[m].get("code_examples", 0) for m in models]
    sec_counts = [evaluations[m].get("security_awareness", 0) for m in models]
    total_prompts = max((len(evaluations[m].get("evaluations", [])) for m in models), default=5)

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    ax.bar(x - width / 2, code_counts, width, label="Code Examples", color=_CHART_ACCENT, alpha=0.9)
    ax.bar(x + width / 2, sec_counts, width, label="Security Awareness", color=_CHART_PRIMARY, alpha=0.9)

    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Count (out of {})".format(total_prompts), color=_CHART_TEXT, fontsize=10)
    ax.set_title("Code & Security Awareness by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.legend(fontsize=9)
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "security_code")


def _generate_run_timeline_chart(run_id: str, runs: list[dict[str, Any]]) -> str | None:
    """Generate a Gantt-style timeline chart for all runs."""
    if not runs:
        return None

    fig, ax = plt.subplots(figsize=(max(10, len(runs) * 2), 6))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    colors = {"report_generation": "#1f3a8a", "game_day": "#f5c842", "fault_injection": "#e5484d"}
    y_labels = []
    y_positions = []

    for idx, run in enumerate(runs[:20]):  # limit to 20 for readability
        run_id_val = run.get("runId", f"run-{idx}")
        started = run.get("startedAt", "")
        finished = run.get("finishedAt", "")
        run_type = run.get("type", "unknown")

        if started and finished:
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                finish_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                duration = (finish_dt - start_dt).total_seconds()
                color = colors.get(run_type, "#64748b")
                ax.barh(idx, duration, left=start_dt.timestamp(), color=color, alpha=0.85, height=0.5,
                        edgecolor="white", linewidth=0.3)
                y_labels.append(f"{run_id_val[:12]} ({run_type[:10]})")
                y_positions.append(idx)
            except Exception:
                continue

    if not y_labels:
        return None

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, color=_CHART_TEXT, fontsize=8)
    ax.set_xlabel("Timeline (Unix timestamp)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Run Execution Timeline", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: datetime.fromtimestamp(x).strftime("%H:%M:%S")))
    ax.tick_params(axis="x", colors=_CHART_TEXT, labelsize=8)
    ax.invert_yaxis()

    legend_patches = [mpatches.Patch(color=c, label=t.replace("_", " ").title()) for t, c in colors.items()]
    ax.legend(handles=legend_patches, fontsize=8, loc="lower right")
    legend = ax.get_legend()
    if legend:
        legend.get_frame().set_facecolor(_CHART_PANEL)
        legend.get_frame().set_edgecolor(_CHART_GRID)
        for text in legend.get_texts():
            text.set_color(_CHART_TEXT)

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "timeline")


def _generate_success_rate_chart(run_id: str, evaluations: dict[str, Any]) -> str | None:
    """Generate a bar chart showing prompt success rate per model."""
    models = list(evaluations.keys())
    if not models:
        return None

    success_rates = []
    for m in models:
        rate_str = evaluations[m].get("prompt_success_rate", "0/5")
        if isinstance(rate_str, str) and "/" in rate_str:
            parts = rate_str.split("/")
            numerator = int(parts[0]) if parts[0].isdigit() else 0
            denominator = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            rate = numerator / denominator if denominator else 0
        else:
            rate = float(rate_str) if isinstance(rate_str, (int, float)) else 0
        success_rates.append(rate * 100)

    colors = ["#1f9d55" if r == 100 else "#f5c842" if r >= 60 else "#e5484d" for r in success_rates]
    fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.2), 5))
    bars = ax.bar(models, success_rates, color=colors, alpha=0.9, edgecolor="white", linewidth=0.5)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Model", color=_CHART_TEXT, fontsize=10)
    ax.set_ylabel("Success Rate (%)", color=_CHART_TEXT, fontsize=10)
    ax.set_title("Prompt Success Rate by Model", color=_CHART_TEXT, fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")

    for bar, val in zip(bars, success_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", color=_CHART_TEXT, fontsize=9, fontweight="bold")

    _apply_dark_style(ax, fig)
    plt.tight_layout()
    return _save_chart(fig, run_id, "success_rate")


def _generate_scenario_flow_chart(run_id: str, report: dict[str, Any]) -> str | None:
    """Generate a flowchart-style diagram for game_day scenario results."""
    scenarios = report.get("scenarios", [])
    if not scenarios:
        return None

    fig, ax = plt.subplots(figsize=(max(10, len(scenarios) * 2), 8))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Game Day Scenario Execution Flow", color=_CHART_TEXT, fontsize=13, fontweight="bold", pad=20)

    box_width = 1.8
    box_height = 0.6
    y_start = 8.5
    y_step = 1.3

    for idx, scenario in enumerate(scenarios):
        y = y_start - idx * y_step
        if y < 0.5:
            break
        name = scenario.get("name", scenario.get("id", f"Scenario {idx+1}"))
        status = scenario.get("status", "unknown").upper()
        color = _CHART_PASS if status == "PASS" else _CHART_FAIL if status == "FAIL" else _CHART_ACCENT

        box = FancyBboxPatch((4 - box_width / 2, y - box_height / 2), box_width, box_height,
                              boxstyle="round,pad=0.1", facecolor=color, edgecolor="white",
                              alpha=0.9, linewidth=1.5)
        ax.add_patch(box)
        ax.text(5, y, name[:30], ha="center", va="center", color="white" if status in ("PASS", "FAIL") else _CHART_TEXT,
                fontsize=9, fontweight="bold")
        ax.text(5, y - 0.25, status, ha="center", va="center", color="white", fontsize=8)

        if idx < len(scenarios) - 1:
            ax.annotate("", xy=(5, y - box_height / 2 - 0.05), xytext=(5, y - box_height / 2 - y_step + 0.15),
                        arrowprops=dict(arrowstyle="->", color=_CHART_MUTED, lw=1.5))

    # Summary box at bottom
    summary = report.get("summary", "")
    if summary:
        ax.text(5, 0.8, f"Summary: {summary[:80]}", ha="center", va="center", color=_CHART_MUTED,
                fontsize=9, wrap=True, bbox=dict(boxstyle="round,pad=0.3", facecolor=_CHART_PANEL, edgecolor=_CHART_GRID))

    plt.tight_layout()
    return _save_chart(fig, run_id, "scenario_flow")


def generate_charts_for_run(run_id: str, runs: list[dict[str, Any]]) -> dict[str, str]:
    """Generate all applicable charts for a run and return URL mapping."""
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return {}

    chart_urls: dict[str, str] = {}
    run_type = run.get("type", "")

    if run_type == "report_generation":
        # Load evaluation JSON sidecars
        evals_by_model = {}
        eval_jsons = _load_evaluation_jsons()
        # Match by timestamp proximity or model overlap
        for ej in eval_jsons:
            model = ej.get("model", "")
            if model and model in run.get("models", []):
                evals_by_model[model] = ej

        if evals_by_model:
            prompts = run.get("prompts", [])
            if not prompts:
                prompts = [e.get("prompts", [""])[0] for e in evals_by_model.values() if e.get("prompts")]
                prompts = prompts[:5] if prompts else [""] * 5

            radar_url = _generate_model_radar_chart(run_id, evals_by_model)
            if radar_url:
                chart_urls["radar"] = radar_url

            time_url = _generate_response_time_chart(run_id, evals_by_model, prompts)
            if time_url:
                chart_urls["response_times"] = time_url

            heatmap_url = _generate_heatmap_chart(run_id, evals_by_model, prompts)
            if heatmap_url:
                chart_urls["heatmap"] = heatmap_url

            tokens_url = _generate_tokens_chart(run_id, evals_by_model)
            if tokens_url:
                chart_urls["tokens"] = tokens_url

            sec_code_url = _generate_security_code_chart(run_id, evals_by_model)
            if sec_code_url:
                chart_urls["security_code"] = sec_code_url

            success_url = _generate_success_rate_chart(run_id, evals_by_model)
            if success_url:
                chart_urls["success_rate"] = success_url

    elif run_type == "game_day":
        report = run.get("report", {})
        if report:
            flow_url = _generate_scenario_flow_chart(run_id, report)
            if flow_url:
                chart_urls["scenario_flow"] = flow_url

    # Cross-run timeline chart (uses all runs)
    timeline_url = _generate_run_timeline_chart(run_id, runs)
    if timeline_url:
        chart_urls["timeline"] = timeline_url

    return chart_urls


def _enrich_runs_with_charts(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach chart URLs to each run entry."""
    enriched = []
    timeline_url = None
    if runs:
        timeline_url = _generate_run_timeline_chart(runs[0].get("runId", ""), runs)
    
    for run in runs:
        run_copy = dict(run)
        run_id = run.get("runId", "")
        if run_id:
            chart_urls = generate_charts_for_run(run_id, runs)
            if timeline_url:
                chart_urls["timeline"] = timeline_url
            run_copy["chartUrls"] = chart_urls
        enriched.append(run_copy)
    return enriched


# ---------------------------------------------------------------------------
# Prompt packages
# ---------------------------------------------------------------------------

def _get_prompt_packages() -> list[dict[str, Any]]:
    data = _load_json(PROMPT_PACKAGES_FILE, {})
    return data.get("prompt_packages", [])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "wilson-eval3ngine-gui"}


# ---------------------------------------------------------------------------
# Endpoints CRUD
# ---------------------------------------------------------------------------

@app.get("/api/endpoints")
async def list_endpoints() -> dict[str, Any]:
    return {"endpoints": _get_endpoints()}


@app.post("/api/endpoints")
async def create_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    url = payload.get("url", "")
    if _is_localhost_endpoint(url):
        return JSONResponse(
            status_code=400,
            content={"error": "Localhost endpoints are not allowed. Use the SSH Gateway at 10.133.7.211."}
        )
    endpoints = _get_endpoints()
    endpoint = {
        "id": payload.get("id") or f"ep_{uuid.uuid4().hex[:8]}",
        "name": payload.get("name", "Unnamed"),
        "url": url,
        "apiKey": payload.get("apiKey") or None,
        "provider": payload.get("provider", "ollama"),
        "createdAt": _now_iso(),
        "available": None,
        "lastTested": None,
    }
    endpoints.append(endpoint)
    _save_endpoints(endpoints)
    return {"endpoint": endpoint}


@app.delete("/api/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str) -> dict[str, Any]:
    endpoints = [ep for ep in _get_endpoints() if ep.get("id") != endpoint_id]
    _save_endpoints(endpoints)
    # Also remove models tied to this endpoint
    models = [m for m in _get_models() if m.get("endpointId") != endpoint_id]
    _save_models(models)
    return {"deleted": endpoint_id}


@app.post("/api/endpoints/{endpoint_id}/test")
async def test_endpoint(endpoint_id: str) -> dict[str, Any]:
    endpoints = _get_endpoints()
    ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
    if not ep:
        return {"ok": False, "error": "Endpoint not found", "status_code": 404}

    url = ep.get("url", "").rstrip("/")
    provider = ep.get("provider", "ollama")
    api_key = ep.get("apiKey")
    models_found = []

    # Handle CLI endpoints
    if url.startswith("cli://") or provider in ("claude_cli", "kilo_cli", "codex_cli"):
        import shutil
        cli_name = provider.replace("_cli", "")
        if shutil.which(cli_name):
            # Try to get models from adapter
            try:
                from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                if provider == "claude_cli":
                    adapter = ClaudeCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
                elif provider == "kilo_cli":
                    adapter = KiloCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
                elif provider == "codex_cli":
                    adapter = CodexCLIAdapter()
                    if adapter.detect_available():
                        models_found = adapter.get_supported_models()
            except Exception:
                pass
            _update_endpoint_status(endpoint_id, True)
            return {"ok": True, "provider": provider, "models": models_found}
        else:
            _update_endpoint_status(endpoint_id, False)
            return {"ok": False, "provider": provider, "error": f"{provider} not found in PATH"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "ollama":
                test_url = f"{url}/api/tags"
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("name") for m in data.get("models", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "ollama", "models": models_found}
                else:
                    error = f"HTTP {resp.status_code}"
                    _update_endpoint_status(endpoint_id, False)
                    return {"ok": False, "provider": "ollama", "error": error}
            elif provider == "openai":
                test_url = f"{url}/models"
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("id") for m in data.get("data", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "openai", "models": models_found}
                else:
                    error = f"HTTP {resp.status_code}"
                    _update_endpoint_status(endpoint_id, False)
                    return {"ok": False, "provider": "openai", "error": error}
            elif provider == "kilo":
                test_url = f"{url}/models"
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_found = [m.get("id") for m in data.get("data", [])]
                    _update_endpoint_status(endpoint_id, True)
                    return {"ok": True, "provider": "kilo", "models": models_found}
                _update_endpoint_status(endpoint_id, False)
                return {"ok": False, "provider": "kilo", "error": f"HTTP {resp.status_code}"}
            else:
                # Fallback: generic HTTP endpoint test
                test_url = url + "/" if not url.endswith("/") else url
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers, follow_redirects=True)
                _update_endpoint_status(endpoint_id, resp.status_code < 400)
                return {"ok": resp.status_code < 400, "provider": provider, "status": resp.status_code}
    except Exception as exc:
        _update_endpoint_status(endpoint_id, False)
        return {"ok": False, "error": str(exc)}


def _update_endpoint_status(endpoint_id: str, available: bool) -> None:
    endpoints = _get_endpoints()
    for ep in endpoints:
        if ep.get("id") == endpoint_id:
            ep["available"] = available
            ep["lastTested"] = _now_iso()
            break
    _save_endpoints(endpoints)


@app.get("/api/endpoints/status")
async def endpoints_status() -> dict[str, Any]:
    """Test all endpoints and return availability status."""
    endpoints = _get_endpoints()
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            api_key = ep.get("apiKey")
            available = False
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                elif provider == "openai":
                    test_url = f"{url}/models"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                elif provider == "kilo":
                    test_url = f"{url}/models"
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers)
                    available = resp.status_code == 200
                else:
                    test_url = url + "/" if not url.endswith("/") else url
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    resp = await client.get(test_url, headers=headers, follow_redirects=True)
                    available = resp.status_code < 400
            except Exception:
                available = False
            results.append({
                "id": ep.get("id"),
                "name": ep.get("name"),
                "available": available,
                "provider": provider,
            })
    return {"statuses": results}


@app.post("/api/endpoints/auto-detect")
async def auto_detect_endpoints() -> dict[str, Any]:
    """Auto-detect Ollama and other endpoints on the gateway at 10.133.7.211."""
    found: list[dict[str, Any]] = []

    # HTTP endpoints - all on the gateway at 10.133.7.211 only
    candidates = [
        ("http://10.133.7.211:11434", "ollama", "SSH Gateway Ollama"),
        ("http://10.133.7.211:8000", "openai", "SSH Gateway OpenAI-compatible"),
        ("http://10.133.7.211:5000", "openai", "SSH Gateway OpenAI-compatible"),
        ("http://10.133.7.211:3000", "openai", "SSH Gateway OpenAI-compatible"),
    ]

    # Include Kilo Gateway if local auth exists
    kilo_auth_path = Path.home() / ".local" / "share" / "kilo" / "auth.json"
    if kilo_auth_path.exists():
        try:
            auth_data = json.loads(kilo_auth_path.read_text())
            kilo_token = auth_data.get("kilo", {}).get("access")
            if kilo_token:
                candidates.append(("https://api.kilo.ai/api/gateway", "kilo", "Kilo Gateway"))
        except Exception:
            pass

    async with httpx.AsyncClient(timeout=5.0) as client:
        for url, provider, name in candidates:
            try:
                if provider == "ollama":
                    test_url = f"{url}/api/tags"
                else:
                    test_url = f"{url}/models"
                headers = {}
                kilo_token = None
                if provider == "kilo":
                    # Use local Kilo auth token if available
                    if kilo_auth_path.exists():
                        try:
                            auth_data = json.loads(kilo_auth_path.read_text())
                            kilo_token = auth_data.get("kilo", {}).get("access")
                            if kilo_token:
                                headers["Authorization"] = f"Bearer {kilo_token}"
                        except Exception:
                            pass
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    found.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "url": url,
                        "apiKey": kilo_token,
                        "provider": provider,
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
            except Exception:
                continue

    # CLI provider detection (no API key required)
    cli_detected = _detect_cli_providers()

    # Merge with existing without duplicates by URL
    existing = _get_endpoints()
    existing_urls = {e.get("url") for e in existing}
    for ep in found:
        # Skip localhost endpoints during auto-detection
        if _is_localhost_endpoint(ep["url"]):
            continue
        if ep["url"] not in existing_urls:
            existing.append(ep)
            existing_urls.add(ep["url"])

    # Add CLI endpoints without duplicating
    for cli_ep in cli_detected:
        if cli_ep["url"] not in existing_urls:
            existing.append(cli_ep)
            existing_urls.add(cli_ep["url"])

    _save_endpoints(existing)
    # Return the newly detected endpoints (for display) plus all endpoints (for list_endpoints to work)
    return {"endpoints": found + cli_detected, "all_endpoints": existing, "total": len(existing)}


def _detect_cli_providers() -> list[dict[str, Any]]:
    """Detect installed CLI providers without HTTP endpoints."""
    import shutil

    detected = []

    # Claude CLI
    if shutil.which("claude"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Claude CLI",
            "url": "cli://claude",
            "apiKey": None,
            "provider": "claude_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    # Kilo CLI
    if shutil.which("kilo"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Kilo CLI",
            "url": "cli://kilo",
            "apiKey": None,
            "provider": "kilo_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    # Codex CLI
    if shutil.which("codex"):
        detected.append({
            "id": f"cli_{uuid.uuid4().hex[:8]}",
            "name": "Codex CLI",
            "url": "cli://codex",
            "apiKey": None,
            "provider": "codex_cli",
            "createdAt": _now_iso(),
            "available": None,
            "lastTested": None,
        })

    return detected


# ---------------------------------------------------------------------------
# Models CRUD + auto-detect
# ---------------------------------------------------------------------------

@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    models = _get_models()
    endpoints = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints}
    enriched = []
    for m in models:
        ep = endpoint_map.get(m.get("endpointId"))
        enriched.append({
            **m,
            "endpointName": ep.get("name") if ep else None,
            "endpointUrl": ep.get("url") if ep else None,
            "provider": ep.get("provider") if ep else m.get("provider"),
            "endpointAvailable": ep.get("available") if ep else None,
        })
    return {"models": enriched}


@app.post("/api/models")
async def create_model(payload: dict[str, Any]) -> dict[str, Any]:
    models = _get_models()
    endpoint_id = payload.get("endpointId", "")
    provider = payload.get("provider")
    if not provider:
        endpoints = _get_endpoints()
        ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
        if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
            provider = ep.get("provider", "ollama")
        else:
            provider = "ollama"
    model = {
        "id": payload.get("id") or f"mdl_{uuid.uuid4().hex[:8]}",
        "endpointId": endpoint_id,
        "provider": provider,
        "createdAt": _now_iso(),
    }
    models.append(model)
    _save_models(models)
    return {"model": model}


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    models = [m for m in _get_models() if m.get("id") != model_id]
    _save_models(models)
    return {"deleted": model_id}


@app.post("/api/models/auto-detect")
async def auto_detect_models() -> dict[str, Any]:
    """Query all configured endpoints and discover available models.
    
    Supports HTTP endpoints (Ollama, OpenAI, Kilo) and CLI-based providers
    (claude_cli, kilo_cli, codex_cli).
    """
    from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
    
    endpoints = _get_endpoints()
    
    # Auto-include Kilo Gateway if local auth exists and endpoint is missing
    kilo_auth_path = Path.home() / ".local" / "share" / "kilo" / "auth.json"
    if not any(e.get("provider") == "kilo" for e in endpoints):
        if kilo_auth_path.exists():
            try:
                auth_data = json.loads(kilo_auth_path.read_text())
                kilo_token = auth_data.get("kilo", {}).get("access")
                if kilo_token:
                    endpoints.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": "Kilo Gateway",
                        "url": "https://api.kilo.ai/api/gateway",
                        "apiKey": kilo_token,
                        "provider": "kilo",
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
                    _save_endpoints(endpoints)
            except Exception:
                pass
    
    discovered: list[dict[str, Any]] = []
    existing_model_ids = {m.get("id") for m in _get_models()}
    seen_base_names: set[str] = set()

    def _base_name(model_id: str) -> str:
        """Get base name for deduplication, preferring non-:latest tags."""
        if model_id.endswith(":latest"):
            base = model_id[:-7]
            return base
        return model_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        for ep in endpoints:
            url = ep.get("url", "").rstrip("/")
            provider = ep.get("provider", "ollama")
            
            # Skip localhost endpoints - only use SSH gateway at 10.133.7.211
            if _is_localhost_endpoint(url):
                continue
            
            api_key = ep.get("apiKey")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Handle CLI providers (no HTTP endpoint needed)
            if provider in ("claude_cli", "kilo_cli", "codex_cli"):
                cli_models = []
                if provider == "claude_cli":
                    adapter = ClaudeCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                elif provider == "kilo_cli":
                    adapter = KiloCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                elif provider == "codex_cli":
                    adapter = CodexCLIAdapter()
                    if adapter.detect_available():
                        cli_models = adapter.get_supported_models()
                
                for model_id in cli_models:
                    if model_id in existing_model_ids:
                        continue
                    discovered.append({
                        "id": model_id,
                        "endpointId": ep.get("id"),
                        "provider": provider,
                        "createdAt": _now_iso(),
                    })
                    existing_model_ids.add(model_id)
                continue

            try:
                if provider == "ollama":
                    resp = await client.get(f"{url}/api/tags", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("models", []):
                            mid = m.get("name", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
                elif provider == "openai":
                    resp = await client.get(f"{url}/models", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
                elif provider == "kilo":
                    resp = await client.get(f"{url}/models", headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if not mid or mid in existing_model_ids:
                                continue
                            base = _base_name(mid)
                            if base in seen_base_names:
                                continue
                            discovered.append({
                                "id": mid,
                                "endpointId": ep.get("id"),
                                "provider": provider,
                                "createdAt": _now_iso(),
                            })
                            existing_model_ids.add(mid)
                            seen_base_names.add(base)
            except Exception:
                continue

    models = _get_models()
    models.extend(discovered)
    _save_models(models)
    return {"models": discovered, "total": len(models)}


# ---------------------------------------------------------------------------
# Prompt packages
# ---------------------------------------------------------------------------

@app.get("/api/prompts/packages")
async def list_prompt_packages() -> dict[str, Any]:
    return {"packages": _get_prompt_packages()}


# ---------------------------------------------------------------------------
# Kilo Gateway login
# ---------------------------------------------------------------------------

@app.post("/api/kilo/login")
async def kilo_login(payload: dict[str, Any]) -> dict[str, Any]:
    """Test connectivity to Kilo Gateway and persist endpoint on success."""
    url = payload.get("url", "https://api.kilo.ai/api/gateway")
    api_key = payload.get("apiKey")
    
    # If no API key provided, try to read from local Kilo auth file
    if not api_key:
        auth_path = Path.home() / ".local" / "share" / "kilo" / "auth.json"
        if auth_path.exists():
            try:
                auth_data = json.loads(auth_path.read_text())
                api_key = auth_data.get("kilo", {}).get("access")
            except Exception:
                pass
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            test_url = f"{url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            resp = await client.get(test_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                
                # Persist Kilo Gateway endpoint for future model discovery
                endpoints = _get_endpoints()
                existing = next((e for e in endpoints if e.get("url") == url), None)
                if not existing:
                    endpoints.append({
                        "id": f"ep_{uuid.uuid4().hex[:8]}",
                        "name": "Kilo Gateway",
                        "url": url,
                        "apiKey": api_key,
                        "provider": "kilo",
                        "createdAt": _now_iso(),
                        "available": True,
                        "lastTested": _now_iso(),
                    })
                    _save_endpoints(endpoints)
                else:
                    # Update existing endpoint to kilo provider and API key
                    existing["provider"] = "kilo"
                    if api_key:
                        existing["apiKey"] = api_key
                    existing["available"] = True
                    existing["lastTested"] = _now_iso()
                    _save_endpoints(endpoints)
                
                return {
                    "ok": True,
                    "url": url,
                    "models": models,
                    "message": f"Kilo Gateway reachable: {len(models)} models found",
                }
            return {"ok": False, "url": url, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

@app.post("/api/token/generate")
async def generate_token(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a game-day authorization token."""
    environment = payload.get("environment", "staging")
    operator = payload.get("operator", "operator")
    token = (
        f"gd_auth_{environment}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_"
        f"{secrets.token_hex(4)}_"
        f"{operator}"
    )
    return {"token": token, "environment": environment, "operator": operator}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def list_reports() -> dict[str, Any]:
    reports = []
    for path in sorted(REPORTS_DIR.glob("*.pdf")):
        reports.append({
            "name": path.name,
            "url": f"/reports/{path.name}",
            "size_bytes": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    
    report_runs = []
    for run in _get_telemetry():
        if run.get("type") == "report_generation":
            artifacts = run.get("artifacts", [])
            pdf_artifacts = [a for a in artifacts if a.lower().endswith(".pdf")]
            if pdf_artifacts:
                report_runs.append({
                    "runId": run.get("runId"),
                    "startedAt": run.get("startedAt"),
                    "models": run.get("models", []),
                    "artifacts": pdf_artifacts,
                })
    
    return {"reports": reports, "reportRuns": report_runs}


@app.get("/reports/{filename}")
async def get_report(filename: str) -> Response:
    path = REPORTS_DIR / filename
    if not path.exists():
        return HTMLResponse("Report not found", status_code=404)
    safe_name = filename.replace('"', '_')
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@app.post("/api/reports/generate")
async def generate_reports(payload: dict[str, Any]) -> dict[str, Any]:
    models = payload.get("models", [])
    prompts = payload.get("prompts", [])
    if not models:
        return {"error": "No models specified"}

    script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    if not script.exists():
        return {"error": "Report generator script not found"}

    env = os.environ.copy()
    env["WE3_REPORT_MODELS"] = _format_models_for_script(models)
    env["WE3_REPORT_PROMPTS"] = ",".join(prompts) if prompts else ""
    
    gateway_url, gateway_api_key = _get_gateway_for_models(models)
    if gateway_url:
        env["WE3_REPORT_GATEWAY"] = gateway_url
    if gateway_api_key:
        env["WE3_REPORT_GATEWAY_API_KEY"] = gateway_api_key
    
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    run_started = _now_iso()
    
    logger.info(
        f"Report generation started: run_id={run_id}, models={models}, gateway={gateway_url}"
    )
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        run_finished = _now_iso()
        telemetry_entry = {
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": run_finished,
            "models": models,
            "prompts": prompts,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
        }
        _add_telemetry_entry(telemetry_entry)
        return {
            "runId": run_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "error": "Report generation timed out",
        })
        return {"error": "Report generation timed out"}
    except Exception as exc:
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "error": str(exc),
        })
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

@app.get("/api/telemetry/runs")
async def list_telemetry_runs() -> dict[str, Any]:
    runs = _get_telemetry()
    return {"runs": _enrich_runs_with_charts(runs)}


@app.get("/api/telemetry/runs/{run_id}")
async def get_telemetry_run(run_id: str) -> dict[str, Any]:
    runs = _get_telemetry()
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    enriched = _enrich_runs_with_charts([run])
    return {"run": enriched[0] if enriched else run}


@app.delete("/api/telemetry/runs/{run_id}")
async def delete_telemetry_run(run_id: str) -> dict[str, Any]:
    telemetry = [r for r in _get_telemetry() if r.get("runId") != run_id]
    _save_telemetry(telemetry)
    return {"deleted": run_id}


@app.delete("/api/telemetry/runs/{run_id}/items/{item_index}")
async def delete_telemetry_item(run_id: str, item_index: int) -> dict[str, Any]:
    telemetry = _get_telemetry()
    run = next((r for r in telemetry if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    artifacts = run.get("artifacts", [])
    if 0 <= item_index < len(artifacts):
        artifacts.pop(item_index)
        run["artifacts"] = artifacts
    _save_telemetry(telemetry)
    return {"deleted": f"{run_id}::{item_index}"}


@app.delete("/api/telemetry/runs/{run_id}/artifacts/{artifact:path}")
async def delete_telemetry_artifact(run_id: str, artifact: str) -> dict[str, Any]:
    telemetry = _get_telemetry()
    run = next((r for r in telemetry if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    artifacts = run.get("artifacts", [])
    if artifact in artifacts:
        artifacts.remove(artifact)
        run["artifacts"] = artifacts
        _save_telemetry(telemetry)
    # Also delete the actual file from the reports directory
    try:
        path = REPORTS_DIR / artifact
        if path.exists():
            path.unlink()
    except Exception:
        pass
    return {"deleted": f"{run_id}::{artifact}"}


@app.delete("/api/reports")
async def delete_all_reports() -> dict[str, Any]:
    for path in REPORTS_DIR.glob("*.pdf"):
        try:
            path.unlink()
        except Exception:
            pass
    for path in REPORTS_DIR.glob("*.json"):
        try:
            path.unlink()
        except Exception:
            pass
    return {"deleted": "all reports"}


@app.delete("/api/reports/{filename:path}")
async def delete_report(filename: str) -> dict[str, Any]:
    safe_name = filename.replace('"', '_').replace("'", "_")
    path = REPORTS_DIR / safe_name
    if not path.exists():
        return JSONResponse({"error": "Report not found"}, status_code=404)
    try:
        path.unlink()
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return {"deleted": safe_name}


@app.get("/api/telemetry/runs/{run_id}/zip")
async def download_run_zip(run_id: str):
    runs = _get_telemetry()
    run = next((r for r in runs if r.get("runId") == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    artifacts = run.get("artifacts", [])
    if not artifacts:
        return JSONResponse({"error": "No artifacts to zip"}, status_code=404)

    buffer = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for artifact in artifacts:
            file_path = REPORTS_DIR / artifact
            if file_path.exists():
                zf.write(file_path, artifact)
                added += 1
            else:
                for search_dir in [GUI_DATA_DIR, WORKSPACE_ROOT / "scripts"]:
                    candidate = search_dir / artifact
                    if candidate.exists():
                        zf.write(candidate, artifact)
                        added += 1
                        break

    if added == 0:
        return JSONResponse({"error": "No artifact files found to zip"}, status_code=404)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}.zip"},
    )


# ---------------------------------------------------------------------------
# Report generation jobs
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
async def list_jobs() -> dict[str, Any]:
    jobs = _load_jobs()
    return {"jobs": list(jobs.values())}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return {"job": job}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.get("status") in ("completed", "failed", "cancelled"):
        return JSONResponse({"error": f"Job already {job['status']}"}, status_code=400)
    async with _report_lock:
        if _report_task is not None and not _report_task.done():
            _report_task.cancel()
    job["status"] = "cancelled"
    job["finished_at"] = _now_iso()
    job["current_step"] = "Cancelled"
    job["error"] = "Report generation was cancelled"
    _update_job(job_id, job)
    return {"job_id": job_id, "status": "cancelled"}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.get("status") not in ("failed", "completed_with_errors"):
        return JSONResponse({"error": "Only failed jobs can be retried"}, status_code=400)
    models = job.get("models", [])
    prompts = job.get("prompts", [])
    prompt_package = job.get("prompt_package", "")
    if not models or not prompts:
        return JSONResponse({"error": "Job has no models or prompts"}, status_code=400)
    return JSONResponse({"error": "Retry must be initiated from the Generate Reports tab via WebSocket"}, status_code=400)


def _find_model(model_id: str, models_data: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a model by exact ID or with fuzzy matching for common suffixes."""
    # Exact match first
    model = next((m for m in models_data if m.get("id") == model_id), None)
    if model:
        return model
    
    # Try stripping common suffixes like :free, :latest, etc.
    if ":" in model_id:
        base = model_id.split(":")[0]
        model = next((m for m in models_data if m.get("id") == base), None)
        if model:
            return model
    else:
        # Try adding :free suffix
        with_free = f"{model_id}:free"
        model = next((m for m in models_data if m.get("id") == with_free), None)
        if model:
            return model
        # Try matching by base name (before first colon)
        model = next((m for m in models_data if m.get("id", "").split(":")[0] == model_id), None)
        if model:
            return model
    
    return None


def _format_models_for_script(model_ids: list[str]) -> str:
    """Format model IDs as 'provider|model_id|label' for the report generation script."""
    models_data = _get_models()
    endpoints_data = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints_data}
    
    formatted = []
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                provider = ep.get("provider", model.get("provider", "ollama"))
            else:
                provider = model.get("provider", "ollama")
            label = mid
            formatted.append(f"{provider}|{mid}|{label}")
        else:
            formatted.append(mid)
    return ",".join(formatted)


def _get_gateway_for_models(model_ids: list[str]) -> tuple[str | None, str | None]:
    """Get the gateway URL and API key for the first model that has an HTTP endpoint.
    
    Prefers Kilo Gateway endpoints over Ollama/OpenAI endpoints.
    """
    models_data = _get_models()
    endpoints_data = _get_endpoints()
    endpoint_map = {e.get("id"): e for e in endpoints_data}
    
    # First pass: prefer Kilo Gateway endpoints
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                if ep.get("provider") == "kilo":
                    logger.info(f"Selected Kilo Gateway for model {mid}: {ep.get('url')}")
                    return ep.get("url"), ep.get("apiKey")
    
    # Second pass: any HTTP endpoint
    for mid in model_ids:
        model = _find_model(mid, models_data)
        if model:
            ep = endpoint_map.get(model.get("endpointId", ""))
            if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                logger.info(f"Selected endpoint for model {mid}: {ep.get('url')} (provider: {ep.get('provider')})")
                return ep.get("url"), ep.get("apiKey")
    
    # Fallback: first configured HTTP endpoint
    for ep in endpoints_data:
        url = ep.get("url", "")
        if url and not url.startswith("cli://"):
            logger.info(f"Selected fallback endpoint: {url} (provider: {ep.get('provider')})")
            return url, ep.get("apiKey")
    return None, None


def _get_gateway_url_for_models(model_ids: list[str]) -> str | None:
    """Backward-compatible wrapper that returns only the URL."""
    url, _ = _get_gateway_for_models(model_ids)
    return url


# ---------------------------------------------------------------------------
# Background report generation
# ---------------------------------------------------------------------------

def _update_job_from_event(job_id: str, event: dict[str, Any]) -> dict[str, Any]:
    jobs = _load_jobs()
    job = jobs.get(job_id)
    if not job:
        return {}
    
    event_type = event.get("event")
    model = event.get("model")
    model_label = event.get("model_label", model)
    provider = event.get("provider", "unknown")
    prompt_index = event.get("prompt_index", 0)
    total_prompts = event.get("total_prompts", job.get("prompts", []) and len(job.get("prompts", [])) or 1)
    
    if event_type == "run_start":
        job["status"] = "processing"
        job["current_step"] = "Initializing"
        job["started_at"] = event.get("timestamp", job["started_at"])
        job["total_reports"] = event.get("total_reports", len(job.get("models", [])))
        job["queued_reports"] = event.get("total_reports", len(job.get("models", [])))
        job["processing_reports"] = 0
        job["completed_reports"] = 0
        job["failed_reports"] = 0
    
    elif event_type == "model_start":
        model_state = {
            "label": model_label,
            "provider": provider,
            "status": "processing",
            "total_reports": total_prompts,
            "completed_reports": 0,
            "failed_reports": 0,
            "percentage": 0,
            "current_step": f"Preparing prompt 1 of {total_prompts}",
            "elapsed_seconds": 0,
            "reports": [],
            "started_at": event.get("timestamp"),
        }
        job["models_state"][model] = model_state
        job["current_model"] = model
        job["current_report"] = 0
        job["processing_reports"] = job.get("processing_reports", 0) + 1
        job["queued_reports"] = max(0, job.get("queued_reports", 0) - 1)
        job["current_step"] = f"Processing {model_label}"
    
    elif event_type == "prompt_start":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["current_step"] = f"Preparing prompt {prompt_index} of {total_prompts}"
            model_state["percentage"] = round(((prompt_index - 1) / total_prompts) * 100)
        job["current_step"] = f"Sending prompt {prompt_index} of {total_prompts} to {model_label}"
        report_entry = {
            "id": f"{model}-prompt-{prompt_index}",
            "model": model,
            "model_label": model_label,
            "provider": provider,
            "status": "processing",
            "step": f"Sending prompt {prompt_index} of {total_prompts}",
            "queue_position": prompt_index,
            "started_at": event.get("timestamp"),
            "finished_at": None,
            "elapsed_seconds": 0,
            "retry_count": 0,
            "error": None,
        }
        if "reports" not in job:
            job["reports"] = []
        job["reports"].append(report_entry)
        job["current_report"] = prompt_index
    
    elif event_type == "prompt_complete":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["current_step"] = f"Validating response {prompt_index} of {total_prompts}"
            model_state["percentage"] = round((prompt_index / total_prompts) * 100)
        job["current_step"] = f"Validating response {prompt_index} of {total_prompts} from {model_label}"
        # Update the last report entry for this model/prompt
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("id") == f"{model}-prompt-{prompt_index}":
                report["status"] = "complete" if event.get("success") else "failed"
                report["step"] = f"Response received {prompt_index} of {total_prompts}"
                report["finished_at"] = event.get("timestamp")
                report["elapsed_seconds"] = round(event.get("time", 0), 2)
                report["error"] = None if event.get("success") else "Model returned unsuccessful response"
                break
        if model_state:
            model_state["completed_reports"] = model_state.get("completed_reports", 0) + (1 if event.get("success") else 0)
            model_state["failed_reports"] = model_state.get("failed_reports", 0) + (0 if event.get("success") else 1)
            model_state["current_step"] = f"Saving report {prompt_index} of {total_prompts}"
    
    elif event_type == "model_complete":
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["status"] = "completed"
            model_state["percentage"] = 100
            model_state["current_step"] = "Finalizing model results"
        job["current_step"] = f"Finalizing {model_label} results"
        # Mark all reports for this model as completed
        for report in job.get("reports", []):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Report generated"
                if not report.get("finished_at"):
                    report["finished_at"] = event.get("timestamp")
        job["completed_reports"] = job.get("completed_reports", 0) + model_state.get("completed_reports", 0)
        job["failed_reports"] = job.get("failed_reports", 0) + model_state.get("failed_reports", 0)
        job["processing_reports"] = max(0, job.get("processing_reports", 1) - 1)
    
    elif event_type == "report_generated":
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Report generated"
                report["finished_at"] = event.get("timestamp")
                report["report_path"] = event.get("report_path")
                break
    
    elif event_type == "report_error":
        for report in reversed(job.get("reports", [])):
            if report.get("model") == model and report.get("status") == "processing":
                report["status"] = "failed"
                report["step"] = "Report generation failed"
                report["finished_at"] = event.get("timestamp")
                report["error"] = event.get("error")
                break
        model_state = job.get("models_state", {}).get(model, {})
        if model_state:
            model_state["failed_reports"] = model_state.get("failed_reports", 0) + 1
        job["failed_reports"] = job.get("failed_reports", 0) + 1
    
    elif event_type == "run_complete":
        job["status"] = "completed" if job.get("failed_reports", 0) == 0 else "completed_with_errors"
        job["finished_at"] = event.get("timestamp")
        job["current_step"] = "Completed"
        job["processing_reports"] = 0
        job["queued_reports"] = 0
        for model_state in job.get("models_state", {}).values():
            model_state["status"] = "completed"
            model_state["percentage"] = 100
            model_state["current_step"] = "Completed"
        for report in job.get("reports", []):
            if report.get("status") == "processing":
                report["status"] = "complete"
                report["step"] = "Completed"
                if not report.get("finished_at"):
                    report["finished_at"] = event.get("timestamp")
    
    elif event_type == "run_error":
        job["status"] = "failed"
        job["finished_at"] = event.get("timestamp")
        job["error"] = event.get("error")
        job["current_step"] = f"Failed: {event.get('error')}"
    
    # Recalculate overall state
    reports = job.get("reports", [])
    completed = sum(1 for r in reports if r.get("status") == "complete")
    failed = sum(1 for r in reports if r.get("status") == "failed")
    processing = sum(1 for r in reports if r.get("status") == "processing")
    queued = job.get("total_reports", 0) - completed - failed - processing
    
    job["completed_reports"] = completed
    job["failed_reports"] = failed
    job["processing_reports"] = processing
    job["queued_reports"] = max(0, queued)
    total = job.get("total_reports", 1)
    job["overall_percentage"] = min(100, round((completed / total) * 100)) if total > 0 else 0
    
    # Calculate elapsed and estimated completion
    started = job.get("started_at")
    updated = event.get("timestamp", _now_iso())
    if started:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            update_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            elapsed = (update_dt - start_dt).total_seconds()
            job["elapsed_seconds"] = round(elapsed, 1)
            if completed > 0 and elapsed > 0:
                rate = completed / elapsed
                remaining = total - completed - failed
                if rate > 0 and remaining > 0:
                    est_seconds = remaining / rate
                    est_dt = update_dt.timestamp() + est_seconds
                    job["estimated_completion"] = datetime.fromtimestamp(est_dt).isoformat()
        except Exception:
            pass
    
    _save_jobs(jobs)
    return {
        "status": job.get("status"),
        "overall": {
            "percentage": job.get("overall_percentage"),
            "completed_reports": job.get("completed_reports"),
            "failed_reports": job.get("failed_reports"),
            "processing_reports": job.get("processing_reports"),
            "queued_reports": job.get("queued_reports"),
            "elapsed_seconds": job.get("elapsed_seconds"),
            "estimated_completion": job.get("estimated_completion"),
        },
        "current_step": job.get("current_step"),
        "current_model": job.get("current_model"),
        "current_report": job.get("current_report"),
        "error": job.get("error"),
        "models_state": job.get("models_state"),
        "reports": job.get("reports"),
        "finished_at": job.get("finished_at"),
    }


async def _tail_progress_file(websocket: WebSocket, job_id: str, progress_file: str, run_id: str) -> None:
    last_pos = 0
    progress_path = Path(progress_file)
    while True:
        try:
            if progress_path.exists():
                size = progress_path.stat().st_size
                if size > last_pos:
                    with open(progress_path, "r", encoding="utf-8") as fh:
                        fh.seek(last_pos)
                        while True:
                            line = fh.readline()
                            if not line:
                                break
                            try:
                                event = json.loads(line.strip())
                            except json.JSONDecodeError:
                                continue
                            job_update = _update_job_from_event(job_id, event)
                            if job_update:
                                try:
                                    await websocket.send_text(json.dumps({
                                        "action": "job_progress",
                                        "job_id": job_id,
                                        "run_id": run_id,
                                        **job_update,
                                    }))
                                except Exception:
                                    return
                        last_pos = fh.tell()
            await asyncio.sleep(0.2)
        except Exception:
            await asyncio.sleep(0.5)


async def _run_report_generation_task(
    websocket: WebSocket,
    models: list[str],
    prompts: list[str],
    prompt_package: str = "",
    job_id: str | None = None,
) -> None:
    """Run report generation with prompts and optional package tracking."""
    global _report_process, _report_task
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    job_id = job_id or f"job-{uuid.uuid4().hex[:8]}"
    run_started = _now_iso()
    script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
    progress_file = str(GUI_DATA_DIR / f"progress-{job_id}.jsonl")
    progress_file_path = Path(progress_file)
    if progress_file_path.exists():
        try:
            progress_file_path.unlink()
        except Exception:
            pass
    try:
        env = os.environ.copy()
        env["WE3_REPORT_MODELS"] = _format_models_for_script(models)
        env["WE3_REPORT_PROMPTS"] = ",".join(prompts) if prompts else ""
        env["WE3_REPORT_PROMPT_PACKAGE"] = prompt_package
        env["WE3_REPORT_PROGRESS_FILE"] = progress_file
        
        gateway_url, gateway_api_key = _get_gateway_for_models(models)
        if gateway_url:
            env["WE3_REPORT_GATEWAY"] = gateway_url
        if gateway_api_key:
            env["WE3_REPORT_GATEWAY_API_KEY"] = gateway_api_key
        
        # Create job state
        job = _create_job(job_id, {
            "run_id": run_id,
            "models": models,
            "prompts": prompts,
            "prompt_package": prompt_package,
            "progress_file": progress_file,
        })
        job["status"] = "initializing"
        _update_job(job_id, job)
        
        try:
            await websocket.send_text(json.dumps({
                "action": "job_created",
                "job_id": job_id,
                "run_id": run_id,
                "status": "initializing",
            }))
        except Exception:
            pass
        
        logger.info(
            f"Report generation started: run_id={run_id}, job_id={job_id}, models={models}, "
            f"prompt_package={prompt_package}, prompt_count={len(prompts)}, "
            f"gateway={gateway_url}"
        )
        
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            "--progress-file=" + progress_file,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        _report_process = proc
        proc_task = asyncio.create_task(proc.wait())
        generation_start = time.time()
        generation_timeout = 600  # 10 minutes max per generation run
        
        # Stream progress events from the progress file
        last_pos = 0
        cancelled = False
        while True:
            if proc_task.done():
                break
            if time.time() - generation_start > generation_timeout:
                logger.error(
                    "Report generation timed out after %ds for job_id=%s run_id=%s",
                    generation_timeout, job_id, run_id,
                )
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(proc_task, timeout=5)
                except asyncio.TimeoutError:
                    pass
                break
            try:
                if progress_file_path.exists():
                    size = progress_file_path.stat().st_size
                    if size > last_pos:
                        with open(progress_file_path, "r", encoding="utf-8") as fh:
                            fh.seek(last_pos)
                            while True:
                                line = fh.readline()
                                if not line:
                                    break
                                try:
                                    event = json.loads(line.strip())
                                except json.JSONDecodeError:
                                    continue
                                job_update = _update_job_from_event(job_id, event)
                                if job_update:
                                    try:
                                        await websocket.send_text(json.dumps({
                                            "action": "job_progress",
                                            "job_id": job_id,
                                            "run_id": run_id,
                                            **job_update,
                                        }))
                                    except Exception:
                                        pass
                        last_pos = fh.tell()
            except Exception:
                pass
            await asyncio.sleep(0.2)
        
        stdout, stderr = await proc.communicate()
        _report_process = None
        run_finished = _now_iso()
        
        # Read any remaining progress events
        if progress_file_path.exists():
            try:
                with open(progress_file_path, "r", encoding="utf-8") as fh:
                    fh.seek(last_pos)
                    for line in fh:
                        try:
                            event = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue
                        _update_job_from_event(job_id, event)
            except Exception:
                pass
        
        job = _get_job(job_id) or job
        if proc.returncode == 0:
            job["status"] = "completed" if job.get("failed_reports", 0) == 0 else "completed_with_errors"
            job["finished_at"] = run_finished
            job["current_step"] = "Completed"
            _update_job(job_id, job)
            telemetry_entry = {
                "runId": run_id,
                "type": "report_generation",
                "startedAt": run_started,
                "finishedAt": run_finished,
                "models": models,
                "prompts": prompts,
                "promptPackage": prompt_package,
                "returncode": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
            }
            _add_telemetry_entry(telemetry_entry)
            try:
                await websocket.send_text(json.dumps({
                    "action": "job_complete",
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": job["status"],
                }))
            except Exception:
                pass
        else:
            job["status"] = "failed"
            job["finished_at"] = run_finished
            job["error"] = f"Process exited with code {proc.returncode}"
            job["current_step"] = "Failed"
            _update_job(job_id, job)
            telemetry_entry = {
                "runId": run_id,
                "type": "report_generation",
                "startedAt": run_started,
                "finishedAt": run_finished,
                "models": models,
                "prompts": prompts,
                "promptPackage": prompt_package,
                "returncode": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "artifacts": [p.name for p in sorted(REPORTS_DIR.glob("*.pdf"))],
                "error": job["error"],
            }
            _add_telemetry_entry(telemetry_entry)
            try:
                await websocket.send_text(json.dumps({
                    "action": "job_error",
                    "job_id": job_id,
                    "run_id": run_id,
                    "status": "failed",
                    "error": job["error"],
                }))
            except Exception:
                pass
    except asyncio.CancelledError:
        cancelled = True
        if _report_process is not None:
            try:
                _report_process.kill()
            except Exception:
                pass
        _report_process = None
        try:
            await asyncio.wait_for(proc_task, timeout=5)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        job = _get_job(job_id)
        if job:
            job["status"] = "cancelled"
            job["finished_at"] = _now_iso()
            job["current_step"] = "Cancelled"
            job["error"] = "Report generation was cancelled"
            _update_job(job_id, job)
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": prompt_package,
            "error": "Report generation cancelled",
        })
        try:
            await websocket.send_text(json.dumps({
                "action": "job_cancelled",
                "job_id": job_id,
                "run_id": run_id,
                "status": "cancelled",
                "error": "Report generation was cancelled",
            }))
        except Exception:
            pass
    except Exception as exc:
        _report_process = None
        job = _get_job(job_id)
        if job:
            job["status"] = "failed"
            job["finished_at"] = _now_iso()
            job["error"] = str(exc)
            job["current_step"] = f"Failed: {exc}"
            _update_job(job_id, job)
        _add_telemetry_entry({
            "runId": run_id,
            "type": "report_generation",
            "startedAt": run_started,
            "finishedAt": _now_iso(),
            "models": models,
            "prompts": prompts,
            "promptPackage": prompt_package,
            "error": str(exc),
        })
        try:
            await websocket.send_text(json.dumps({
                "action": "job_error",
                "job_id": job_id,
                "run_id": run_id,
                "status": "failed",
                "error": str(exc),
            }))
        except Exception:
            pass
    finally:
        _report_task = None
        # Cleanup progress file after a delay
        try:
            if progress_file_path.exists():
                progress_file_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global _report_process, _report_task
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            action = message.get("action")
            response: dict[str, Any] = {"action": action}

            if action == "list_reports":
                reports = []
                for path in sorted(REPORTS_DIR.glob("*.pdf")):
                    reports.append({
                        "name": path.name,
                        "url": f"/reports/{path.name}",
                        "sizeBytes": path.stat().st_size,
                    })
                response["reports"] = reports
                
                # Group by report_generation runs for the Reports tab
                report_runs = []
                for run in _get_telemetry():
                    if run.get("type") == "report_generation":
                        artifacts = run.get("artifacts", [])
                        pdf_artifacts = [a for a in artifacts if a.lower().endswith(".pdf")]
                        if pdf_artifacts:
                            report_runs.append({
                                "runId": run.get("runId"),
                                "startedAt": run.get("startedAt"),
                                "models": run.get("models", []),
                                "artifacts": pdf_artifacts,
                            })
                response["reportRuns"] = report_runs

            elif action == "list_endpoints":
                response["endpoints"] = _get_endpoints()

            elif action == "list_models":
                models = _get_models()
                endpoints = _get_endpoints()
                enriched = []
                for m in models:
                    ep = next((e for e in endpoints if e.get("id") == m.get("endpointId")), None)
                    enriched.append({
                        **m,
                        "endpointName": ep.get("name") if ep else None,
                        "provider": ep.get("provider") if ep else m.get("provider"),
                        "endpointAvailable": ep.get("available") if ep else None,
                    })
                response["models"] = enriched

            elif action == "list_telemetry":
                response["runs"] = _get_telemetry()

            elif action == "list_prompt_packages":
                response["packages"] = _get_prompt_packages()

            elif action == "endpoints_status":
                result = await endpoints_status()
                response.update(result)

            elif action == "generate_reports":
                models = message.get("models", [])
                prompts = message.get("prompts", [])
                prompt_package = message.get("promptPackage", "")
                prompt_count = message.get("promptCount")
                if prompt_count and prompts:
                    prompts = prompts[:prompt_count]
                script = WORKSPACE_ROOT / "scripts" / "generate_5_reports.py"
                if not script.exists() or not models:
                    response["status"] = "skipped"
                    response["error"] = "No script or models"
                    await websocket.send_text(json.dumps(response))
                    continue
                async with _report_lock:
                    if _report_task is not None and not _report_task.done():
                        response["status"] = "error"
                        response["error"] = "Report generation already in progress"
                        await websocket.send_text(json.dumps(response))
                        continue
                    job_id = f"job-{uuid.uuid4().hex[:8]}"
                    response["status"] = "started"
                    response["job_id"] = job_id
                    response["promptPackage"] = prompt_package
                    await websocket.send_text(json.dumps(response))
                    _report_task = asyncio.create_task(
                        _run_report_generation_task(websocket, models, prompts, prompt_package, job_id=job_id)
                    )

            elif action == "get_job":
                job_id = message.get("job_id")
                job = _get_job(job_id) if job_id else None
                if not job:
                    response["status"] = "error"
                    response["error"] = "Job not found"
                else:
                    response["status"] = "ok"
                    response["job"] = job
                    response["status"] = job.get("status")
                    response["overall"] = {
                        "percentage": job.get("overall_percentage", 0),
                        "completed_reports": job.get("completed_reports", 0),
                        "failed_reports": job.get("failed_reports", 0),
                        "processing_reports": job.get("processing_reports", 0),
                        "queued_reports": job.get("queued_reports", 0),
                        "elapsed_seconds": job.get("elapsed_seconds", 0),
                        "estimated_completion": job.get("estimated_completion"),
                    }
                    response["current_step"] = job.get("current_step")
                    response["current_model"] = job.get("current_model")
                    response["current_report"] = job.get("current_report")
                    response["error"] = job.get("error")
                    response["models_state"] = job.get("models_state", {})
                    response["reports"] = job.get("reports", [])
                    response["finished_at"] = job.get("finished_at")
                await websocket.send_text(json.dumps(response))

            elif action == "cancel_job":
                job_id = message.get("job_id")
                job = _get_job(job_id) if job_id else None
                if not job:
                    response["status"] = "error"
                    response["error"] = "Job not found"
                elif job.get("status") in ("completed", "failed", "cancelled"):
                    response["status"] = "error"
                    response["error"] = f"Job already {job['status']}"
                else:
                    async with _report_lock:
                        if _report_task is not None and not _report_task.done():
                            _report_task.cancel()
                            _report_task = None
                    job["status"] = "cancelled"
                    job["finished_at"] = _now_iso()
                    job["current_step"] = "Cancelled"
                    job["error"] = "Report generation was cancelled"
                    _update_job(job_id, job)
                    response["status"] = "cancelled"
                    response["job_id"] = job_id
                await websocket.send_text(json.dumps(response))

            elif action == "stop_reports":
                async with _report_lock:
                    if _report_process is not None:
                        try:
                            _report_process.kill()
                            try:
                                await asyncio.wait_for(_report_process.wait(), timeout=5)
                            except asyncio.TimeoutError:
                                pass
                        except Exception:
                            pass
                        _report_process = None
                        response["status"] = "stopped"
                    else:
                        response["status"] = "no_generation_running"
                    if _report_task is not None:
                        _report_task.cancel()
                        _report_task = None
                await websocket.send_text(json.dumps(response))

            elif action == "run_game_day":
                authorization = message.get("authorization", "")
                response["status"] = "started"
                await websocket.send_text(json.dumps(response))
                try:
                    from ..testing.game_day import GameDayOrchestrator
                    orchestrator = GameDayOrchestrator()
                    if not orchestrator.validate_authorization(authorization):
                        response["error"] = "Invalid authorization"
                        response["status"] = "error"
                    else:
                        orchestrator.assert_safety_observer(True)
                        report = orchestrator.execute_failure_matrix(
                            authorization_token=authorization,
                        )
                        run_id = f"run-{uuid.uuid4().hex[:8]}"
                        _add_telemetry_entry({
                            "runId": run_id,
                            "type": "game_day",
                            "startedAt": _now_iso(),
                            "finishedAt": _now_iso(),
                            "authorization": authorization,
                            "report": report.to_dict(),
                            "artifacts": [],
                        })
                        response["runId"] = run_id
                        response["report"] = report.to_dict()
                        response["status"] = "complete"
                except Exception as exc:
                    response["error"] = str(exc)
                    response["status"] = "error"

            elif action == "generate_token":
                token_data = await generate_token({
                    "environment": message.get("environment", "staging"),
                    "operator": message.get("operator", "operator"),
                })
                response.update(token_data)
                response["status"] = "complete"

            elif action == "kilo_login":
                login_result = await kilo_login({
                    "url": message.get("url", "https://api.kilo.ai/api/gateway"),
                    "apiKey": message.get("apiKey"),
                })
                response.update(login_result)

            elif action == "create_endpoint":
                url = message.get("url", "")
                # Reject localhost endpoints - only allow SSH gateway at 10.133.7.211
                if _is_localhost_endpoint(url):
                    response["error"] = "Localhost endpoints are not allowed. Use the SSH Gateway at 10.133.7.211."
                    response["ok"] = False
                    continue
                endpoints = _get_endpoints()
                endpoint = {
                    "id": f"ep_{uuid.uuid4().hex[:8]}",
                    "name": message.get("name", "Unnamed"),
                    "url": url,
                    "apiKey": message.get("apiKey") or None,
                    "provider": message.get("provider", "ollama"),
                    "createdAt": _now_iso(),
                    "available": None,
                    "lastTested": None,
                }
                endpoints.append(endpoint)
                _save_endpoints(endpoints)
                response["endpoint"] = endpoint

            elif action == "delete_endpoint":
                ep_id = message.get("id")
                if ep_id:
                    endpoints = [ep for ep in _get_endpoints() if ep.get("id") != ep_id]
                    _save_endpoints(endpoints)
                    models = [m for m in _get_models() if m.get("endpointId") != ep_id]
                    _save_models(models)
                response["deleted"] = ep_id

            elif action == "create_model":
                models = _get_models()
                endpoint_id = message.get("endpointId", "")
                provider = message.get("provider")
                if not provider:
                    endpoints = _get_endpoints()
                    ep = next((e for e in endpoints if e.get("id") == endpoint_id), None)
                    if ep and ep.get("url") and not ep.get("url", "").startswith("cli://"):
                        provider = ep.get("provider", "ollama")
                    else:
                        provider = "ollama"
                model = {
                    "id": message.get("id") or f"mdl_{uuid.uuid4().hex[:8]}",
                    "endpointId": endpoint_id,
                    "provider": provider,
                    "createdAt": _now_iso(),
                }
                models.append(model)
                _save_models(models)
                response["model"] = model

            elif action == "delete_model":
                mdl_id = message.get("id")
                if mdl_id:
                    models = [m for m in _get_models() if m.get("id") != mdl_id]
                    _save_models(models)
                response["deleted"] = mdl_id

            elif action == "auto_detect_endpoints":
                result = await auto_detect_endpoints()
                response.update(result)

            elif action == "auto_detect_models":
                result = await auto_detect_models()
                response.update(result)

            elif action == "test_endpoint":
                # Test endpoint by connecting to health check (supports both existing ID and quick URL test)
                ep_id = message.get("id")
                url = message.get("url")
                provider = message.get("provider", "ollama")
                api_key = message.get("apiKey")
                
                result = None
                ok = False
                error = None
                models_found = []
                
                # If we have a URL, do quick URL test (takes priority)
                if url:
                    url = url.rstrip("/")
                    
                    # Reject localhost endpoints
                    if _is_localhost_endpoint(url):
                        result = {"ok": False, "error": "Localhost endpoints are not allowed. Use the SSH Gateway at 10.133.7.211.", "provider": provider}
                        response.update(result)
                        continue
                    
                    # Detect CLI provider from URL scheme (cli://toolname)
                    if url.startswith("cli://"):
                        cli_name = url[6:]  # Remove "cli://"
                        import shutil
                        # Map CLI name to provider
                        if cli_name == "claude" or provider == "claude_cli":
                            provider = "claude_cli"
                            cli_exec = "claude"
                        elif cli_name == "kilo" or provider == "kilo_cli":
                            provider = "kilo_cli"
                            cli_exec = "kilo"
                        elif cli_name == "codex" or provider == "codex_cli":
                            provider = "codex_cli"
                            cli_exec = "codex"
                        else:
                            cli_exec = cli_name
                        
                        if shutil.which(cli_exec):
                            ok = True
                            # Get models from adapter if available
                            try:
                                from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                                if provider == "claude_cli":
                                    adapter = ClaudeCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                                elif provider == "kilo_cli":
                                    adapter = KiloCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                                elif provider == "codex_cli":
                                    adapter = CodexCLIAdapter()
                                    if adapter.detect_available():
                                        models_found = adapter.get_supported_models()
                            except Exception:
                                pass
                        else:
                            error = f"{provider} not found in PATH"
                            ok = False
                        result = {"ok": ok, "provider": provider, "models": models_found}
                        if error:
                            result["error"] = error
                    else:
                        # HTTP endpoint testing
                        try:
                            async with httpx.AsyncClient(timeout=15.0) as client:
                                if provider == "ollama":
                                    test_url = f"{url}/api/tags"
                                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                                    resp = await client.get(test_url, headers=headers)
                                    if resp.status_code == 200:
                                        data = resp.json()
                                        models_found = [m.get("name") for m in data.get("models", [])]
                                        ok = True
                                    else:
                                        error = f"HTTP {resp.status_code}"
                                elif provider in ("openai", "kilo"):
                                    test_url = f"{url}/models"
                                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                                    resp = await client.get(test_url, headers=headers)
                                    if resp.status_code == 200:
                                        data = resp.json()
                                        models_found = [m.get("id") for m in data.get("data", [])]
                                        ok = True
                                    else:
                                        error = f"HTTP {resp.status_code}"
                                else:
                                    test_url = url + "/" if not url.endswith("/") else url
                                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                                    resp = await client.get(test_url, headers=headers, follow_redirects=True)
                                    ok = resp.status_code < 400
                        except Exception as exc:
                            error = str(exc)
                        
                        result = {"ok": ok, "provider": provider, "models": models_found}
                        if error:
                            result["error"] = error
                elif ep_id:
                    # Test existing endpoint by ID - look up endpoint and test appropriately
                    endpoints = _get_endpoints()
                    ep = next((e for e in endpoints if e.get("id") == ep_id), None)
                    if not ep:
                        result = {"ok": False, "error": "Endpoint not found"}
                    else:
                        url = ep.get("url", "")
                        provider = ep.get("provider", "ollama")
                        api_key = ep.get("apiKey")
                        
# Handle CLI endpoints
                        if url.startswith("cli://") or provider in ("claude_cli", "kilo_cli", "codex_cli"):
                            import shutil
                            cli_name = provider.replace("_cli", "") if provider.endswith("_cli") else url[6:] if url.startswith("cli://") else ""
                            if shutil.which(cli_name):
                                ok = True
                                models_found = []
                                # Try to get models from adapter
                                try:
                                    from ..providers.cli_base import ClaudeCLIAdapter, KiloCLIAdapter, CodexCLIAdapter
                                    if provider == "claude_cli":
                                        adapter = ClaudeCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                    elif provider == "kilo_cli":
                                        adapter = KiloCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                    elif provider == "codex_cli":
                                        adapter = CodexCLIAdapter()
                                        if adapter.detect_available():
                                            models_found = adapter.get_supported_models()
                                except Exception:
                                    pass
                                result = {"ok": True, "provider": provider, "models": models_found}
                            else:
                                result = {"ok": False, "provider": provider, "error": f"{provider} not found in PATH"}
                            _update_endpoint_status(ep_id, result["ok"])
                        else:
                            # Test HTTP endpoint
                            result = await test_endpoint(ep_id)
                else:
                    result = {"ok": False, "error": "No endpoint ID or URL provided"}
                response.update(result)

            else:
                response["error"] = f"Unknown action: {action}"

            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

if GUI_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(GUI_STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(str(GUI_STATIC_DIR / "index.html"))


# Mount charts directory if it exists
if CHARTS_DIR.exists():
    app.mount("/static/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")
