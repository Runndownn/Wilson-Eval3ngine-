# GUI and Evidence Guide

The Wilson Eval3ngine GUI is a loopback-only administrative workspace for configuring providers, exploring model inventory, starting evaluations, reviewing charts, and inspecting reports.

Start it with:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

## Operator workflow

![Wilson Eval3ngine operator workflow](assets/images/ui-workflow.webp)

| Step | Workspace | Purpose |
|---|---|---|
| 1 | **Endpoints** | Register/test a provider endpoint and reconcile available models. |
| 2 | **Models** | Explore model inventory by family/provider/endpoint. |
| 3 | **Generate** | Select models, prompts, and execution settings and start bounded jobs. |
| 4 | **Charts** | Compare model behavior, uncertainty, latency, tokens, and run patterns. |
| 5 | **Reports** | Inspect generated PDF reports, hashes, sidecars, and evidence exports. |

The screenshots are user-supplied runtime captures incorporated as documentation assets. They are visual evidence of the interface, not proof of production deployment or of any numeric benchmark claim.

## Endpoints and models

Endpoint testing is intended to distinguish authentication, route, rate-limit, provider-service, timeout, TLS/DNS, and reachability failures. Credentials are handled through protected inputs and are not returned through endpoint JSON responses.

The Models workspace groups inventory by inferred family while preserving exact provider model identifiers. Family/role labels are navigation aids rather than benchmark claims.

## Generate

The Generate workspace coordinates model selection, prompt packages, request counts, and execution mode. Exact run semantics remain governed by the versioned experiment/dataset contracts and evidence generated for the run.

## Metric and safety views

![Wilson Eval3ngine metric gallery](assets/images/metrics-gallery.webp)

The supplied metric gallery includes:

- success rate with Wilson confidence intervals;
- outcome distribution by model;
- prompt success rate by model;
- per-prompt success heatmap;
- cross-run comparison;
- model performance radar;
- extended model comparison;
- metric correlation heatmap;
- code/security-awareness comparison;
- code-sophistication progression.

These visualizations are useful for pattern recognition. They must not replace the underlying numerator/denominator, interval method, run population, classifications, or evidence hashes.

## Performance and operational views

![Wilson Eval3ngine performance gallery](assets/images/performance-gallery.webp)

The supplied performance gallery includes:

- response time by model and prompt;
- response-time trend;
- response-time distribution;
- response time versus token count;
- response-length distribution;
- token usage by model;
- per-prompt response-time heatmap;
- per-prompt token-count heatmap;
- run execution timeline.

Timing/token charts are operational evidence. They do not by themselves establish safety or model quality.

## Reports and evidence bundles

Reports and charts are separate artifacts. Reports can contain narrative, metrics, prompt-level evidence, run identity, and linked exports. Exact behavior may evolve with GUI implementation; stored run evidence and sidecars remain authoritative.

## Security boundary

The GUI has administrative authority over endpoints, credentials, jobs, reports, charts, exports, and deletion actions. The official launcher therefore rejects non-loopback binds. Do not expose it directly to a LAN or public interface.

For remote operation, deploy an authenticated TLS proxy with explicit authorization. For provider destination policy, local gateways, credential rotation, and secret handling, see [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md).

## Interpretation rule

A screenshot can show that a feature or visual existed in the captured UI. It cannot prove:

- a production deployment was hardened;
- a provider/model was approved;
- a test suite passed;
- a chart value is statistically sufficient;
- an external secret/identity/network control was configured.

Use [Current Status](STATUS.md), run artifacts, and the security/assurance documents for those claims.
