# Current GUI captures

The files under `docs/assets/gui/current/` are the active operator screenshots used by the public documentation. They represent the current five-workspace interface in the same order implemented by `gui/static/index.html`:

1. `01-endpoints.webp` — provider endpoint configuration and live connectivity inventory.
2. `02-models.webp` — model registry, family grouping, endpoint lineage, and model discovery.
3. `03-generate.webp` — model selection, prompt-set configuration, request-volume review, and job start.
4. `04-charts.webp` — per-run analytics/chart inventory and evidence inspection.
5. `05-reports.webp` — generated PDF report inventory and inline preview.

These images are point-in-time operator-interface captures. Counts, provider health states, model names, run totals, report totals, sample chart labels, and other values visible inside a screenshot describe the captured session only; they are not release metrics and should not be copied into current status claims.

The older `01-endpoints.png` through `06-prompt-package.png` files remain in the parent directory as historical visual evidence. They are no longer the canonical walkthrough because that six-image sequence does not match the current five-tab navigation. Prompt-package behavior now belongs to the Generate workspace and PDF viewing belongs to the Reports workspace.

When an exact value matters, use the current run's structured evidence, sidecars, metric snapshots, hashes, and report metadata rather than reading values from an image.
