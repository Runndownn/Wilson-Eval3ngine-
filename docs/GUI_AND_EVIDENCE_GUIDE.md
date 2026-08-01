# Wilson Eval3ngine GUI and Evidence Guide

This guide is the focused companion to the project README. It explains the operator workflow, model-family navigation, report viewer, chart catalogue, and the evidence represented by each visual without duplicating the full architecture and implementation history.

> Runtime status: the interface remains a loopback-only administrative workspace. Start it with `we3 gui --host 127.0.0.1 --port 8080`. Historical CLI wildcard defaults are safely translated to loopback; explicitly requested remote hosts still fail closed.

## Operator workflow

| Step | Workspace | Primary action | Evidence produced |
|---|---|---|---|
| 1 | Endpoints | Register and test a provider | Health result, provider response, discovered model IDs |
| 2 | Models | Review inventory by family and endpoint | Registered model lineage and availability |
| 3 | Generate | Select models, prompts, and execution mode | Evaluation job, progress events, PDF reports, JSON sidecars |
| 4 | Charts | Inspect run-level analytical visuals | PNG chart set with run metadata and explanations |
| 5 | Reports | Read and export generated reports | Inline PDFs, full-document view, hashes, evidence bundle |

### Endpoint testing

Each endpoint test uses a bounded request timeout and returns an inline result on the endpoint card. Failures are described as authentication, route, rate-limit, provider-service, timeout, TLS, DNS, or reachability problems so the operator can distinguish a bad credential from an unavailable service.

A successful test reconciles the provider-reported inventory with the local model registry. Credentials remain password inputs, are encrypted before persistence, and are not returned in endpoint JSON responses.

### Model-family explorer

The Models page presents one compact card per inferred model family rather than one large card for every model. Each family card summarizes registered count, ready count, providers, endpoints, and several popular candidates; **Explore models** opens a keyboard-accessible dialog with the complete family inventory.

Family and role labels are navigation aids inferred from provider model IDs, not benchmark claims. The dialog preserves exact model identifiers and shows provider, endpoint, readiness, likely role, selection state, and removal controls.

### Generate reports

The full-width **Review and start** row appears before detailed configuration and continuously summarizes models, prompts, total requests, and execution mode. Below it, operators can select popular models, expand families, filter by provider, load a prompt package, edit prompts, and start a coordinated or reduced-concurrency batch.

The model selector and Models page use the same family vocabulary and status cues. This keeps discovery and execution consistent while preserving access to every registered model.

### Charts and reports are separate artifacts

Charts are PNG evidence views intended for comparison and pattern recognition. Reports are PDF documents containing narrative, metrics, prompt-level evidence, run identity, and exportable results; a chart is never presented as a report.

The Reports page opens the first four PDFs automatically in high-visibility card viewers. Each can be collapsed with **Hide card viewer**, while remaining reports stay closed until requested to avoid loading an unbounded number of documents.

## Chart gallery

The gallery below uses the repository's generated PNG samples from `gui/static/charts/test-run-final/`. These images are demonstration assets tied to the chart-generation implementation; source run metadata and JSON sidecars remain authoritative for exact values.

### 1. Model Performance Radar

![Model Performance Radar](../gui/static/charts/test-run-final/radar.png)

The radar chart compares representative models across normalized dimensions such as latency, success, token volume, code signals, and security awareness. It is useful for seeing trade-offs quickly, while exact comparisons should still be made from the run metadata because area and overlap can visually exaggerate small differences.

### 2. Extended Model Comparison Radar

![Extended Model Comparison Radar](../gui/static/charts/test-run-final/radar_extended.png)

The extended radar adds efficiency, consistency, and safety-oriented dimensions to the basic comparison. It helps identify balanced models and exposes cases where apparent quality depends on high cost, variable latency, or weak safety context.

### 3. Response Time by Model and Prompt

![Response Time by Model and Prompt](../gui/static/charts/test-run-final/response_times.png)

Grouped bars compare model latency for each prompt rather than hiding prompt-level variation inside one average. The chart reveals which tasks trigger slowdowns and whether a provider is consistently fast or only performs well on a subset of the evaluation set.

### 4. Response Time Trend Across Prompts

![Response Time Trend Across Prompts](../gui/static/charts/test-run-final/line_response_trend.png)

The line chart follows latency in prompt order for each model. Rising, falling, or unstable traces can indicate warm-up effects, context growth, rate limiting, or inconsistent inference behavior that deserves operational investigation.

### 5. Response Time Distribution Histogram

![Response Time Distribution Histogram](../gui/static/charts/test-run-final/histogram_distribution.png)

The histogram shows how often response times fall into each range and marks the overall shape of the workload. Skew, multiple peaks, and long tails communicate service risk that a mean or median alone cannot show.

### 6. Response Time Box Plot

![Response Time Box Plot](../gui/static/charts/test-run-final/boxplot_response_times.png)

The box plot compares each model's median, interquartile range, whiskers, and outliers. Narrow boxes indicate predictable behavior, while long whiskers and isolated points identify models whose worst-case latency may be materially different from their typical result.

### 7. Response Time versus Token Count

![Response Time versus Token Count](../gui/static/charts/test-run-final/scatter_time_tokens.png)

Each point connects one prompt evaluation's latency and token output, with model identity preserved by grouping. The scatter reveals clusters and outliers and helps test whether slower responses are explained by verbosity or by provider and architecture effects.

### 8. Token Usage by Model

![Token Usage by Model](../gui/static/charts/test-run-final/tokens.png)

This bar chart aggregates generated tokens per model. It provides a direct view of verbosity and a practical proxy for cost and throughput, helping operators distinguish concise models from those that consume substantially more output budget.

### 9. Code and Security Awareness

![Code and Security Awareness](../gui/static/charts/test-run-final/security_code.png)

Paired bars compare code-generation signals with security-awareness signals found in responses. The relationship matters because technical capability without adequate discussion of risks, validation, and mitigation can produce useful-looking but unsafe output.

### 10. Success Rate with Wilson Confidence Intervals

![Success Rate with Wilson Confidence Intervals](../gui/static/charts/test-run-final/confidence_intervals.png)

The point or bar estimate is shown with a Wilson 95% confidence interval, keeping sample size visible in the interpretation. Wide intervals warn that a high observed success rate may still be uncertain and should not be treated as release-grade evidence.

### 11. Outcome Distribution by Model

![Outcome Distribution by Model](../gui/static/charts/test-run-final/stacked_outcomes.png)

Stacked segments show pass, fail, and ambiguous outcomes for each model rather than reducing behavior to one percentage. This makes failure shape visible and highlights models that appear successful only because ambiguous or partial responses are overlooked.

### 12. Metric Correlation Heatmap

![Metric Correlation Heatmap](../gui/static/charts/test-run-final/correlation_heatmap.png)

The heatmap summarizes pairwise relationships among response time, token use, success, and other recorded metrics. It is useful for generating hypotheses about trade-offs, but correlation is descriptive evidence and does not establish that one metric causes another.

### 13. Code Sophistication Progression Heatmap

![Code Sophistication Progression Heatmap](../gui/static/charts/test-run-final/heatmap.png)

This matrix depicts implementation dimensions across development phases, making growth and remaining gaps visible in one view. It is a project-evolution visual rather than a model benchmark and should be interpreted alongside repository history and validation evidence.

### 14. Run Execution Timeline

![Run Execution Timeline](../gui/static/charts/test-run-final/timeline.png)

The timeline places report generation, game-day, and fault-injection runs on a shared time axis. It helps operators identify execution bursts, long-running jobs, failed short runs, and the relationship between testing activity and later analysis.

### 15. Prompt Success Rate by Model

![Prompt Success Rate by Model](../gui/static/charts/test-run-final/success_rate.png)

This chart provides a fast comparison of the proportion of prompts completed successfully by each model. It is a screening view rather than a complete release decision because it does not, by itself, express outcome severity, sample uncertainty, or evidence quality.

## PDF report experience

Each report card includes:

- a browser-native inline PDF document viewer;
- a concise explanation of what the report contains;
- run, model, modification time, file size, and SHA-256 context when available;
- **Open full report** for native zoom, search, print, and download;
- an evidence-bundle export for linked runs;
- direct deletion without a second confirmation dialog.

The first four PDFs open by default. This gives immediate visual evidence without making the page load every report at once; operators can hide any viewer or open additional cards independently.

## GUI screenshot plan

Screenshots must be captured only after the corrected launcher, endpoint test flow, family explorer, Generate layout, chart catalogue, and PDF behavior are exercised in a real browser. The final set should include:

1. Endpoints with one successful test and one categorized failure.
2. Models family cards and an open family dialog.
3. Generate with the full-width Review and Start row plus popular and family choices.
4. Charts showing the complete PNG gallery and one full-screen chart.
5. Reports showing four default-open PDFs and one collapsed card.

Do not substitute mock browser frames for runtime evidence. Until those captures exist, the chart PNGs and generated PDFs are the repository's visual demonstration assets.

## Agentic engineering origin

The README's **Agentic Engineering Origin** remains the canonical account of how Wilson Eval3ngine began and who directed it. This guide does not rewrite that history: it preserves the central account that The Repo Operator Arty remained the principal architect, decision-maker, and accountable authority; agentic systems acted as bounded engineering collaborators whose proposals were inspected, tested, and governed.

## Development and verification

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/unit/test_gui_bind_security.py tests/unit/test_gui_ux4.py tests/unit/test_gui_ux5.py -q
node --check gui/static/enhanced.js
node --check gui/static/ux4.js
node --check gui/static/ux5.js
we3 gui --host 127.0.0.1 --port 8080
```

After startup, open `http://127.0.0.1:8080`. Real provider validation must use operator-owned credentials entered through the GUI; credentials must not be committed, pasted into issue or PR text, or placed directly in shell history.
