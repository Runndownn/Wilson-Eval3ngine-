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
