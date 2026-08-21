# Wilson Eval3ngine GUI and Evidence Guide

This guide explains the operator interface, the normal evaluation workflow, the screenshots preserved with the repository, and every sample chart promoted into the active documentation asset tree. It is intended to answer two questions at once: **what does the operator do in the GUI, and what does each visual tell a reviewer after a run?**

The screenshots and charts below are real repository assets that were previously stored under `.archive/unused_files/`; they are now copied by exact Git blob identity into `docs/assets/` so GitHub can render them directly. Screenshots are point-in-time interface evidence and charts are visualizations of sample/run data, so neither should replace the structured sidecars, hashes, manifests, classifications, or metric snapshots when an exact value or release claim matters.

## Security boundary before you start

The official GUI launcher binds only to loopback. Start it with:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080` on the same host. The GUI can manage providers, credentials, models, jobs, reports, charts, exports, and deletion, so direct LAN/public binding is intentionally rejected; remote use belongs behind a separately authenticated TLS proxy with an explicit authorization policy.

Provider destinations are also policy boundaries. Public providers are expected to use canonical HTTPS endpoints, intentional local/private gateways require explicit enablement, and credentials should be entered through the supported GUI/provider workflow rather than committed to configuration files or copied into shell history; see [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md).

## Operator workflow

| Step | Workspace | What the operator does | What it establishes |
|---|---|---|---|
| 1 | **Endpoints** | Register and test an approved provider destination. | Connectivity and provider boundary before evaluation traffic. |
| 2 | **Models** | Discover and inspect exact provider/model identities. | The model inventory that can be selected for work. |
| 3 | **Generate** | Choose models, prompts, and execution settings, then start a bounded job. | Declared evaluation scope and execution progress. |
| 4 | **Charts** | Inspect run-level and cross-run visualizations. | Fast pattern recognition across metrics and observations. |
| 5 | **Reports** | Read PDFs and inspect hashes/sidecars/evidence exports. | Human-readable interpretation linked back to structured evidence. |

## GUI screenshots

### 1. Endpoints workspace

<p align="center"><img src="assets/gui/01-endpoints.png" alt="Wilson Eval3ngine Endpoints workspace" width="1100"></p>

The Endpoints workspace is where an operator defines and tests the model destinations WE3 is allowed to use. It makes provider connectivity a deliberate configuration step before model discovery or report generation, which helps separate credential, route, TLS, rate-limit, and reachability failures from evaluation behavior. This view is useful when onboarding a hosted provider or approved local gateway because the connection can be validated before evaluation budget is spent.

### 2. Models workspace

<p align="center"><img src="assets/gui/02-models.png" alt="Wilson Eval3ngine Models workspace" width="1100"></p>

The Models workspace presents the model inventory discovered or registered through configured endpoints. It helps the operator understand which exact provider/model identifiers are available and organize model families before choosing evaluation targets. This matters for reproducibility because comparisons should point to explicit provider and model identities instead of ambiguous display names.

### 3. Generate workspace

<p align="center"><img src="assets/gui/03-generate.png" alt="Wilson Eval3ngine Generate workspace" width="1100"></p>

The Generate workspace turns selected models and prompt material into bounded evaluation jobs and exposes execution progress. It is the operational bridge between configuration and evidence creation, allowing the workload to be reviewed before it becomes provider traffic and stored artifacts. This view is useful for coordinated model comparisons because selected models, prompts, and execution choices remain part of the visible run setup.

### 4. Reports workspace

<p align="center"><img src="assets/gui/04-reports.png" alt="Wilson Eval3ngine Reports workspace" width="1100"></p>

The Reports workspace organizes generated evaluation documents as inspectable artifacts rather than treating a completed job as the end of the process. It keeps report identity and run context close together so narrative findings can be reconciled with the evidence that produced them. This view is useful for review and handoff because operators do not need to search the filesystem manually for each report.

### 5. PDF report viewer

<p align="center"><img src="assets/gui/05-pdf-viewer.png" alt="Wilson Eval3ngine PDF report viewer" width="1100"></p>

The PDF viewer shows how generated reports can be read inside the operator experience. It supports human review by keeping the rendered document close to run metadata, hashes, and export actions while preserving the distinction between a report and authoritative structured evidence. This is useful when reviewers need narrative context without losing the ability to trace the report back to its run.

### 6. Prompt package selection

<p align="center"><img src="assets/gui/06-prompt-package.png" alt="Wilson Eval3ngine prompt package selection" width="1100"></p>

The prompt-package view shows how reusable prompt material is selected instead of being pasted ad hoc into every run. It helps make the evaluated population understandable and repeatable because prompt selection becomes part of the declared workflow. This is useful when comparing model families across a stable task set because the prompts can be held constant while the target models change.

## What happens after Generate

A GUI job is not just a request to make a PDF. The execution path records provider attempts and response evidence, the evaluation logic produces classifications and metrics, and report/chart generation creates human-readable views over those underlying results. When a chart and a sidecar disagree, the structured evidence and the code that generated the chart are the authoritative places to investigate.

The Reports and Charts workspaces therefore serve different purposes. **Reports** package narrative and evidence context for reading and export, while **Charts** make patterns, distributions, comparisons, and uncertainty easier to see quickly; neither should be used to infer values that are not supported by the associated run artifacts.

## Complete chart catalogue

All charts below use the same presentation width for predictable GitHub rendering. The promoted files come from the repository's `sample-charts` set and are documentation examples, not claims about a current production model population.

### Response-time box plot
<p align="center"><img src="assets/charts/boxplot_response_times.png" alt="Response-time box plot" width="1000"></p>
This box plot compares response-latency distributions across evaluated models instead of showing only one average. It makes medians, spread, and outliers visible, helping identify unstable tail behavior. It is useful for operational comparison because predictability can matter as much as typical speed.

### Wilson confidence intervals
<p align="center"><img src="assets/charts/confidence_intervals.png" alt="Wilson confidence intervals" width="1000"></p>
This chart places observed rates beside Wilson confidence intervals so uncertainty stays visible with the estimate. Wide intervals reveal when apparently strong results are supported by too little evidence for a precise conclusion. It is useful because WE3 treats sample support and uncertainty as part of the decision itself.

### Metric-correlation heatmap
<p align="center"><img src="assets/charts/correlation_heatmap.png" alt="Metric correlation heatmap" width="1000"></p>
This heatmap summarizes relationships among recorded quantitative dimensions such as latency, token use, and outcome-oriented measurements. It helps analysts spot associations and trade-offs that are difficult to see in separate tables. It is useful for hypothesis generation while remaining descriptive rather than proof of causation.

### Cross-run comparison
<p align="center"><img src="assets/charts/cross_run_comparison.png" alt="Cross-run model comparison" width="1000"></p>
This chart compares results across evaluation runs rather than treating every run as isolated. It makes baseline-versus-candidate changes and possible regressions easier to inspect. It is useful when configuration or model changes need to be judged against prior evidence.

### Code-sophistication heatmap
<p align="center"><img src="assets/charts/heatmap.png" alt="Code sophistication progression heatmap" width="1000"></p>
This heatmap visualizes represented implementation or response-sophistication dimensions as a matrix. It compresses multiple observations into a view that makes stronger and weaker areas easy to locate. It is useful for seeing uneven capability development that a single overall score would hide.

### Response-time histogram
<p align="center"><img src="assets/charts/histogram_distribution.png" alt="Response-time histogram" width="1000"></p>
This histogram shows how response times are distributed across ranges rather than reporting only a mean or median. Skew, multiple modes, and long tails can expose operational behavior hidden by one summary statistic. It is useful when occasional extreme delays matter to throughput or service quality.

### Response-time trend
<p align="center"><img src="assets/charts/line_response_trend.png" alt="Response-time trend across prompts" width="1000"></p>
This line chart follows latency through prompt order for each represented model or run. It makes warm-up effects, bursts, rate-limit behavior, and task-specific slowdowns easier to notice. It is useful when the important question is when performance changed rather than only what the overall average was.

### Per-prompt performance heatmap
<p align="center"><img src="assets/charts/per_prompt_heatmap.png" alt="Per-prompt performance heatmap" width="1000"></p>
This heatmap places prompts and models on a common grid so task-level differences remain visible. It identifies uniformly difficult cases as well as model weaknesses concentrated in particular parts of the evaluation set. It is useful for debugging benchmark composition because aggregates can conceal which prompts are driving a result.

### Per-prompt success heatmap
<p align="center"><img src="assets/charts/per_prompt_heatmap_success.png" alt="Per-prompt success heatmap" width="1000"></p>
This view focuses the prompt-by-model grid on successful and unsuccessful outcomes. It shows whether a high aggregate success rate is broad-based or concentrated in easier cases. It is useful for choosing where regrading, additional cases, or targeted model investigation will provide the most information.

### Per-prompt token heatmap
<p align="center"><img src="assets/charts/per_prompt_heatmap_tokens.png" alt="Per-prompt token usage heatmap" width="1000"></p>
This heatmap shows token usage at prompt granularity across compared models. It exposes prompts that consistently trigger long responses and models whose verbosity varies sharply by task. It is useful for cost and throughput analysis because equal behavioral outcomes can consume very different output budgets.

### Model-performance radar
<p align="center"><img src="assets/charts/radar.png" alt="Model performance radar chart" width="1000"></p>
This radar chart compares representative models across several normalized dimensions in one profile. It makes trade-offs easy to see when no model dominates every axis. It is useful as a screening view, while exact decisions should still use the underlying metrics because polygon area can exaggerate differences.

### Extended model radar
<p align="center"><img src="assets/charts/radar_extended.png" alt="Extended model performance radar chart" width="1000"></p>
This extended radar adds more dimensions to the compact comparison so balance, efficiency, consistency, and safety-oriented signals can be viewed together. It helps distinguish a broadly capable model from one that reaches a similar headline result through an extreme trade-off. It is useful for triage before returning to exact metric tables and evidence.

### Reasoning comparison
<p align="center"><img src="assets/charts/reasoning_comparison.png" alt="Reasoning comparison chart" width="1000"></p>
This chart compares reasoning-oriented signals across the represented models or runs. It provides a focused view for tasks where solution structure or reasoning behavior carries information beyond simple completion. It is useful for capability comparison while the associated rubric and grader evidence remain necessary to define the plotted measure precisely.

### Response-length distribution
<p align="center"><img src="assets/charts/response_length_distribution.png" alt="Response length distribution" width="1000"></p>
This distribution shows how response length varies across the evaluated population. It reveals whether a model is consistently concise, consistently verbose, or changes sharply by prompt. It is useful for interpreting token cost and user experience because average output length can hide substantial variation.

### Response time by model and prompt
<p align="center"><img src="assets/charts/response_times.png" alt="Response time by model and prompt" width="1000"></p>
This grouped comparison shows latency for individual prompts across represented models. It keeps task-level variation visible instead of burying timing behavior in one aggregate value. It is useful for finding prompts that trigger slowdowns and distinguishing consistently fast models from models that are fast only on some tasks.

### Response time versus tokens
<p align="center"><img src="assets/charts/scatter_time_tokens.png" alt="Response time versus token count" width="1000"></p>
This scatter plot places response time and token output on the same axes for individual observations. It helps test whether slower responses broadly track larger outputs or whether distinct clusters and outliers remain. It is useful for efficiency diagnosis because latency and verbosity often interact without having a simple causal relationship.

### Code and security-awareness comparison
<p align="center"><img src="assets/charts/security_code.png" alt="Code and security awareness comparison" width="1000"></p>
This chart compares code-oriented and security-awareness signals from the represented evaluation results. It makes cases easier to notice where technical capability is strong but risk recognition, validation, or mitigation signals lag. It is useful for security-focused evaluation because technically sophisticated output is not automatically safe output.

### Outcome distribution
<p align="center"><img src="assets/charts/stacked_outcomes.png" alt="Outcome distribution by model" width="1000"></p>
This stacked chart preserves the shape of the outcome population instead of compressing behavior into one percentage. It allows successful, failed, and ambiguous portions to remain visible side by side. It is useful because models with similar aggregate success can have very different safety or ambiguity profiles.

### Success rate
<p align="center"><img src="assets/charts/success_rate.png" alt="Prompt success rate by model" width="1000"></p>
This chart provides a fast comparison of observed prompt success across represented models. It is a screening view rather than a complete release decision because it does not by itself express severity, uncertainty, denominator quality, or provenance. It is useful for orientation before moving into confidence intervals, outcome distributions, and underlying evidence.

### Execution timeline
<p align="center"><img src="assets/charts/timeline.png" alt="Evaluation execution timeline" width="1000"></p>
This timeline places evaluation activity on a shared time axis so run timing and sequencing can be inspected. It makes execution bursts, long operations, gaps, and failures easier to correlate with the surrounding workflow. It is useful for operational diagnosis because many performance problems become clearer in temporal context.

### Token efficiency
<p align="center"><img src="assets/charts/token_efficiency.png" alt="Token efficiency comparison" width="1000"></p>
This chart focuses on useful output relative to token consumption for represented models. It helps identify configurations that achieve comparable outcomes with materially different output budgets. It is useful for throughput and cost planning because efficiency can matter even when behavioral grades are similar.

### Token usage
<p align="center"><img src="assets/charts/tokens.png" alt="Token usage by model" width="1000"></p>
This chart aggregates generated-token volume for the compared models. It provides a direct view of relative verbosity and a practical proxy for output-side cost and capacity pressure. It is useful when choosing between otherwise similar configurations because token consumption can materially affect both economics and latency.

## Reports, PDFs, hashes, and sidecars

A chart is not a report, and a report is not the raw evidence. Generated PDF reports are human-readable presentations, while sidecars and run metadata carry machine-readable identity, hashes, model/run context, and other values needed for exact reconciliation; evidence bundles allow related artifacts to travel together.

The GUI can present PDFs inline for quick review and can expose report/export actions without requiring the user to navigate directly through internal storage paths. When reviewing a release-sensitive result, use the PDF to understand the narrative and then use the associated structured evidence, metric snapshot, gate record, and hashes to verify the exact claim.

## Accuracy rules for these visuals

Do not read exact values from a screenshot when the associated sidecar or metric snapshot exists, do not treat a sample chart as a current benchmark claim, and do not infer production assurance from a UI capture. Provider names, model inventories, credentials, private addresses, identities, and real runtime evidence may also be sensitive, so screenshots intended for publication should be reviewed before they leave the authorized environment.

For implementation boundaries see [Architecture](ARCHITECTURE.md), for maturity and known limitations see [Current Status](STATUS.md), and for the public/private assurance split see [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md).
