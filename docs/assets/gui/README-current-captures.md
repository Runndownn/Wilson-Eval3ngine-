# Current GUI captures

The files under `docs/assets/gui/current/` are the active operator and analytics screenshots used by the public documentation. The current high-resolution five-workspace walkthrough follows the same order implemented by `gui/static/index.html`:

1. `endpoints.png` — provider endpoint configuration and live connectivity inventory.
2. `models.png` — model registry, family grouping, endpoint lineage, and model discovery.
3. `generate.png` — model selection, prompt-set configuration, request-volume review, and job start.
4. `charts.png` — per-run analytics/chart inventory and evidence inspection.
5. `reports.png` — generated PDF report inventory and inline preview.

`Generate.png` and `generate.png` contain the same repository image; public documentation uses the lowercase path once rather than rendering duplicate content. The older `01-endpoints.webp`, `02-models.webp`, `04-charts.webp`, and `05-reports.webp` captures remain in the directory as lower-resolution compatibility/history assets. The former `03-generate.webp` was intentionally removed and must not be referenced by current documentation.

The same directory now also contains the current detailed analytics capture set (`cross-run-comp.png`, `csa.png`, `csp.png`, `mch.png`, `mpce.png`, `mpr.png`, `odm.png`, `pprth.png`, `ppsh.png`, `pptch.png`, `psr.png`, `ret.png`, `rld.png`, `rtd.png`, `rtmp.png`, `rttap.png`, `rttc.png`, `success-rate-with-confidene-confidance-in.png`, and `tum.png`). The root README displays these images as a visual atlas and normalizes their rendered height so differing native dimensions do not make one chart visually dominate another.

`docs/assets/gui/05-pdf-viewer.png` remains outside `current/` and is retained as a useful report-reading capture. PDF viewing now belongs conceptually to the Reports workflow rather than a separate sixth navigation stage.

All screenshots and chart captures are point-in-time presentation evidence. Counts, provider health states, model names, run totals, report totals, chart labels, and visible values describe the captured session only; they are not release metrics. When an exact value matters, use the current run's structured evidence, sidecars, metric snapshots, hashes, and report metadata rather than reading the value from an image.
