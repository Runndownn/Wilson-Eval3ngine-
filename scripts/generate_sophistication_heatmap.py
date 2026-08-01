#!/usr/bin/env python3
"""Generate a Code Sophistication Progression Heatmap.

This replaces the pass/fail model evaluation heatmap with a meaningful
visualization showing how the Wilson Eval3ngine codebase evolved in sophistication
across the 8 development phases (July 14-30, 2026).

Each cell shows whether a given sophistication dimension was implemented (1) or
not yet present (0) during that phase. Darker green = implemented, darker red = not.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from wilson_eval3ngine.gui.server import (
    _CHART_BG, _CHART_PANEL, _CHART_TEXT, _CHART_MUTED,
    _CHART_GRID, _CHART_PASS, _CHART_FAIL, _CHART_PRIMARY, _CHART_ACCENT,
    CHARTS_DIR,
)

# Phase → sophistication dimension matrix
# 1 = implemented in that phase, 0 = not yet implemented
PHASES = [
    "Phase 1\n(Foundation)",
    "Phase 2\n(Data Layer)",
    "Phase 3\n(Providers)",
    "Phase 4\n(Metrics & Judgement)",
    "Phase 5\n(Observability & Controls)",
    "Phase 6\n(Production Hardening)",
    "Phase 7\n(Security & Production)",
    "Phase 8\n(GUI & Finalization)",
]

DIMENSIONS = [
    "Architecture",
    "Data Layer",
    "Provider\nAdapters",
    "Metrics\nEngine",
    "Observability",
    "Security\nControls",
    "Production\nControls",
    "GUI/UX",
    "Testing\n(2036 tests)",
    "Documentation",
]

# Each row is a phase, each column is a dimension
# Data derived from the actual development history documented in README.md
PROGRESSION = np.array([
    # Arch  Data  Prov  Metrics  Obs    Security  Prod    GUI    Testing  Docs
    [1,    0,    0,    0,       0,     0,         0,       0,     0,       1],  # Phase 1
    [1,    1,    0,    0,       0,     0,         0,       0,     0,       1],  # Phase 2
    [1,    1,    1,    0,       0,     0,         0,       0,     0,       1],  # Phase 3
    [1,    1,    1,    1,       0,     0,         0,       0,     0,       1],  # Phase 4
    [1,    1,    1,    1,       1,     0,         0,       0,     0,       1],  # Phase 5
    [1,    1,    1,    1,       1,     0,         1,       0,     0,       1],  # Phase 6
    [1,    1,    1,    1,       1,     1,         1,       0,     0,       1],  # Phase 7
    [1,    1,    1,    1,       1,     1,         1,       1,     1,       1],  # Phase 8
])


def generate_sophistication_heatmap(run_id: str = "test-run-final") -> str | None:
    """Generate the Code Sophistication Progression Heatmap."""
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_BG)

    # Use a custom colormap: red (0) → yellow (0.5) → green (1)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "sophistication",
        [_CHART_FAIL, _CHART_ACCENT, _CHART_PASS],
        N=256,
    )

    im = ax.imshow(PROGRESSION, cmap=cmap, aspect="auto", vmin=0, vmax=1)

    # Axis labels
    ax.set_xticks(range(len(DIMENSIONS)))
    ax.set_xticklabels(DIMENSIONS, color=_CHART_TEXT, fontsize=9, rotation=30, ha="right")
    ax.set_yticks(range(len(PHASES)))
    ax.set_yticklabels(PHASES, color=_CHART_TEXT, fontsize=10)

    ax.set_title("Code Sophistication Progression\n(Dark = Not Yet, Bright = Implemented)",
                 color=_CHART_TEXT, fontsize=14, fontweight="bold", pad=15)

    # Annotate each cell with checkmark or dash
    for i in range(len(PHASES)):
        for j in range(len(DIMENSIONS)):
            val = PROGRESSION[i, j]
            text = "✓" if val == 1 else "—"
            color = _CHART_PASS if val == 1 else _CHART_MUTED
            ax.text(j, i, text, ha="center", va="center", color=color,
                    fontsize=14, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, aspect=30)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(["Not Yet", "Partial", "Complete"])
    cbar.ax.yaxis.set_tick_params(color=_CHART_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=_CHART_TEXT, fontsize=9)
    cbar.outline.set_edgecolor(_CHART_GRID)

    # Grid
    ax.set_xticks(np.arange(len(DIMENSIONS) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(PHASES) + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=_CHART_GRID, linestyle="-", linewidth=1.5)
    ax.tick_params(which="minor", length=0)

    plt.tight_layout()

    # Save
    run_dir = CHARTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "heatmap.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=_CHART_BG, edgecolor="none")
    plt.close(fig)
    print(f"  ✓ sophistication_heatmap: {out_path}")
    return f"/static/charts/{run_id}/heatmap.png"


if __name__ == "__main__":
    result = generate_sophistication_heatmap("test-run-final")
    if result:
        print(f"Generated: {result}")
    else:
        print("Failed to generate heatmap")
