# Interface Design Log

## 2026-07-31 — Enhanced evaluation workspace

- **Branch:** `feat/enhanced-evaluation-workspace`
- **Base:** `dev-mid`
- **Direction:** Preserve and evolve. The dark Wilson Eval3ngine visual identity, blue/cyan emphasis, yellow evidence accents, five-tab single-page structure, and backend contracts remain intact.

### Baseline and constraints

The previous GUI already exposed Endpoints, Models, Generate Reports, Charts, and Reports in a single-page tab flow. It also contained substantial functionality, but the information hierarchy was uneven, model and endpoint lineage was difficult to scan, report generation controls were dense, progress rendering could regress or flicker, and detailed run evidence was split across several visual patterns.

The backend remains authoritative. The interface consumes existing WebSocket actions and REST resources for endpoints, models, prompt packages, report generation, persistent jobs, chart runs, chart metadata, telemetry run detail, PDF reports, and run ZIP export. No backend data contract or security boundary is intentionally changed.

### Decisions

1. Retain the five sequential tabs and number them to clarify the workflow.
2. Add a persistent operational header showing endpoint, model, run, and report counts plus WebSocket health.
3. Represent endpoints and models as explicit inventory objects with provider, endpoint ID, availability, and lineage visible without opening a modal.
4. Reframe report generation as three steps: select models, configure prompts/execution, and confirm request volume.
5. Keep prompt-package defaults editable at the individual prompt level.
6. Make progress monotonic in the browser. Completed or failed work contributes to a stable percentage that never visually moves backward during out-of-order events.
7. Preserve persistent job restoration through local storage and the existing `get_job` WebSocket action.
8. Group chart evidence by run and provide a detail drawer for run and chart metadata rather than flattening every artifact.
9. Present PDF artifacts as report cards and expose run ZIP export when telemetry lineage exists.
10. Use responsive CSS grid primitives and avoid new frontend dependencies.

### Reused patterns and contracts

- Existing static FastAPI delivery model.
- Existing `/ws` WebSocket endpoint and action names.
- Existing `/api/telemetry/runs/{run_id}` detail endpoint.
- Existing `/api/telemetry/runs/{run_id}/zip` export endpoint.
- Existing `/reports/{filename}` PDF endpoint.
- Existing backend credential handling and sanitization.
- Existing Wilson Eval3ngine logo and dark visual identity.

### Added or changed patterns

- New `enhanced.css` tokenized visual layer.
- New `enhanced.js` state and rendering layer with keyed data collections.
- Rebuilt `index.html` semantic shell with five tab panels.
- Persistent detail drawer for evidence inspection.
- Explicit run-volume summary and per-model job state list.
- Mobile and intermediate-width layout rules.

### Accessibility and responsive behavior

- Tabs are real buttons under a labelled navigation region.
- Forms use explicit labels and native controls.
- Status messages use a live status container.
- Text and border contrast are designed for the dark background, with non-color status labels.
- Layout collapses from twelve columns to one column at narrow widths.
- Horizontal tab overflow remains available on small screens.
- Focus rings are visible on all form controls.

### Validation status

Repository and backend contracts were inspected against the `dev-mid` branch. Static source review confirmed that the interface references existing WebSocket actions and REST routes. A browser-based end-to-end run, production build, automated accessibility scan, and visual-regression capture were not available through the connected GitHub interface and remain required before merge.

### Known limitations and follow-up

- Execution mode is sent with generation requests, but the existing WebSocket backend currently derives execution behavior from its own report-generation path; backend support should be verified before describing batch mode as fully enforced.
- Manual CLI-provider registration should continue to use the provider-specific login or auto-detection path where required by backend URL validation.
- The current PDF experience opens reports in a browser tab; an embedded reader can be reintroduced as a follow-up without changing report contracts.
- Add Playwright coverage for tab persistence, model selection, prompt editing, job restoration, monotonic progress, run inspection, and report opening.

## 2026-07-31 — Usability repair and evidence interaction pass

### Operator feedback addressed

The Endpoints page was retained. The Models, Generate Reports, Charts, and Reports pages were revised after direct operator use identified unclear flow, a `405 Method Not Allowed` generation failure, chart-management gaps, and insufficient in-page PDF readability.

### Decisions and rationale

1. **Model descriptions are two concise sentences.** The browser infers a general model family and likely use from the registered model ID and provider. The copy is explicitly framed as guidance rather than a performance or benchmark claim because the registry does not store an authoritative model-card description.
2. **Model inventory flow is explicit.** A four-step strip explains endpoint connection, discovery or registration, capability review, and report selection. Cards now reserve space for description and lineage rather than presenting IDs as an undifferentiated list.
3. **Model selection uses selectable cards.** Search, provider filtering, availability state, endpoint lineage, select-all-visible, and clear controls make the selected set easier to understand than compact chips.
4. **Run summary is symmetrical and action-oriented.** It sits below the model and prompt work areas, shows the model × prompt equation, and disables Start generation until the request is valid.
5. **Generation is version tolerant.** The browser first posts to the durable `/api/jobs` route. A `405` triggers the existing `generate_reports` WebSocket action so an older running GUI process remains usable while deployment catches up.
6. **Chart inventory is read-only.** Refresh scans existing files and must never create sample or real charts as a side effect.
7. **Chart generation is evidence-bound and idempotent.** Existing chart sets are reused. New generation requires a known telemetry run with real evaluation sidecar data; the operator GUI does not invoke the legacy synthetic-sample fallback.
8. **Runs are visual groups.** Colored run frames expose labels, model and prompt context, metadata, minimize/expand controls, and whole-run chart deletion.
9. **Charts are individually manageable.** Every chart has an individual delete control and opens in a movable, resizable window with fullscreen and metadata views. Escape closes the window and native controls remain keyboard focusable.
10. **Reports are readable in place.** Each longer report card embeds its same-origin PDF and retains full-tab opening, run export, hashing metadata, and deletion.

### Security and data integrity

- Dynamic values continue to be escaped before insertion into markup.
- PDF and chart resources are same-origin.
- Chart deletion delegates to filename-validated backend routes.
- Chart creation requires telemetry evidence and refuses intentionally deleted complete runs.
- The generation compatibility fallback sends the same bounded model and prompt request used by the validated REST route.

### Validation status

- JavaScript syntax was checked with `node --check` during construction of the interaction bundle.
- HTML parsing completed without parser errors and no duplicate element IDs were present in the constructed page.
- CSS brace counts were balanced during construction.
- Backend regression coverage now verifies POST job-route registration, unique chart routes, side-effect-free inventory, chart-set reuse, and refusal to generate without real evidence.
- The connected repository workflow still does not run for pull requests targeting `dev-mid`; executable pytest and browser validation remain required before merge.

### Remaining validation

Run the GUI from the updated branch rather than an already-running legacy process, then exercise model filtering, both generation submission paths, job reconnect, chart drag/resize/fullscreen/delete/minimize, responsive layouts, keyboard order, embedded PDF rendering, and PDF fallback behavior across the supported browsers.
