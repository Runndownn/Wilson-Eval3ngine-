# GUI operational feedback and conflict-resolution pass

## Scope

This pass follows direct operator use after PR #19 and preserves the existing Wilson dark visual identity. It focuses on timely endpoint feedback, actionable health errors, bounded model inventory density, generation-summary hierarchy, chart deletion and demonstration behavior, PDF presentation, application connection state, and API-key handling.

## Branch and baseline

- Branch: `security/hardening-20260731-wilson-eval3ngine-3`
- Baseline: `main` merge commit `8eee11a2c25bd25926828538c98e97914ccf295f`
- Delivery mode: draft pull request; no automatic merge

## Conflict assessment

Open PRs #20 (`dev-main`) and #21 (`stable`) expose the same effective six-file content state under different commit histories. Both are 28 commits behind `main` and conflict with the newer application boundary, provider-egress controls, CI provenance work, chart lifecycle behavior, and merged GUI workflow.

Neither branch is suitable for wholesale merge. The current branch preserves the newer `main` implementation and carries forward only compatible product intentions:

- readable model inventory;
- embedded report viewing;
- grouped chart runs;
- explicit report-generation flow;
- endpoint and model lineage.

The stale branches are treated as superseded source material, not as authoritative merge targets.

## Interaction decisions

### Endpoint tests

Individual endpoint tests use a 15-second browser timeout and create an inline card result immediately. Successful tests distinguish provider-reported models from newly registered models. Errors are grouped into authentication, route, rate-limit, provider-service, timeout, TLS, DNS, and reachability assessments.

`Check all health` tests configured endpoints in bounded groups of three, reports each result on its endpoint card, and ends with a healthy-versus-attention summary.

### Application connection state

The top-right indicator no longer depends solely on the WebSocket. A same-origin `/api/health` poll runs every five seconds:

- green `Connected` means API and WebSocket are healthy;
- amber `Connected · polling` means the API is healthy while live updates reconnect;
- red `Disconnected` means the health endpoint did not respond.

### Model inventory containment

The registry displays eight models per page in a maximum four-column grid. Cards have bounded height and internal scrolling for long lineage text. Family-derived accent roles are deterministic and shared with Generate-page model choices.

### Generate hierarchy

The Review and Start summary is promoted to the first full-width row of the generation workspace. It displays model, prompt, request, and mode totals before the detailed model and prompt configuration surfaces.

### Charts

The expanded chart window receives a direct Delete chart action. The existing whole-run delete remains on the run frame. Demo generation has an explicit long-running state and reports the number of fully rendered synthetic PNG charts produced.

### Reports

The server already returns PDFs with `application/pdf` and inline disposition. The viewer therefore remains browser-native, but is placed in a document frame with a PDF header, paper-colored background, and explicit full-report fallback.

## Security and secret handling

Endpoint API keys remain accepted only through password inputs and sent in request bodies. The backend encrypts keys before persistence and sanitizes endpoint responses. New regression coverage verifies that plaintext keys do not appear in the endpoint state file or returned endpoint object.

The overlay loads only same-origin versioned CSS and JavaScript and does not weaken the existing Content Security Policy.

## CI repair

The prior merged PR run failed before tests because `.github/workflows/ci.yml` invokes `make lint` while the Makefile had no lint target. The target now performs:

- Python bytecode compilation for `src`, `tests`, and `scripts`;
- JavaScript syntax validation for `enhanced.js` and `ux4.js`.

This restores the workflow gate without bypassing or weakening it.

## Validation required

- GitHub Actions lint, tests, coverage, build, supply-chain, and foundation jobs.
- Real NVIDIA and other provider endpoint testing with operator-owned credentials.
- Browser validation of health polling, WebSocket recovery, pagination, responsive layout, chart deletion, and PDF rendering.
- Process-restart verification for deleted chart persistence.

No runtime or CI result is represented as passing until observed.
