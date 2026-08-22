# Ben Reaper's Security Partner — Master Security Assessment and Hardening Report

## 1. Document control

| Field | Value |
|---|---|
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Requested base | `dev-mid` / `aa82b419572e7bc22dbc042fb390357cb1236d1f` |
| Integrated ancestor | `main` / `a0c9d80c2afb97905f7bb88f90995b95504cfaae`, 47 linear descendant commits from the requested base |
| Assessment branch | `security/hardening-20260801-wilson-eval3ngine` |
| Reviewed code head before this report revision | `2ef25d57a83af41c29021d94fd271fa1aa8c46ce` |
| Draft pull request | `#25` — `security: Ben Reaper partner hardening and master assessment` |
| Date | 2026-08-01 |
| Authorization | Assessment, modification, branch creation, push, and draft PR were explicitly authorized. |
| State | `partial` — implementation present; full execution evidence incomplete |

The branch was created from `dev-mid` and fast-forwarded without force through its reviewed descendant history before new remediation. The PR remains based on `dev-mid`, is draft, mergeable, unmerged, and has no auto-merge.

## 2. Partner charter and bounded assurance statement

Repository code and configuration are authoritative for implementation claims. Supplied screenshots are visual evidence only. This report does not claim production is fixed, every file was reviewed, or every test passed; local checkout, browser, container, Caddy, and production evidence remain required.

## 3. Executive narrative

WE3 combines a project-scoped API with a loopback operator GUI that manages provider endpoints, credentials, models, jobs, subprocesses, telemetry, charts, reports, exports, and deletion. The most material gaps in the reviewed branch lineage were direct production service exposure, weak configuration defaults, an internally inconsistent production image, plaintext regular-file report credential handoff, content-dependent report geometry, off-screen chart windows, a body limit that trusted `Content-Length`, a non-stock Caddy configuration, and stale credential documentation.

The dedicated branch fixes those repository-local root causes while preserving endpoint, model, job, report, chart, and telemetry contracts. Validation code and a branch-local workflow were added, but no tool result is recorded as passed in this report because the connector did not expose a completed run.

## 4. Scope, methodology, and limitations

In scope: active GUI composition, endpoint/provider boundary, report subprocess, charts/reports, API body limits, Dockerfile, Compose, Caddy, CI, README, provider guide, tests, and this report. Out of scope without separate authorization: live providers, production deployment, real credentials, external OIDC/KMS/secret-manager changes, merge, and auto-merge.

Evidence classes used: `[REPO]`, `[RUNTIME]` for supplied screenshots only, `[INFERENCE]`, and `[BLOCKED]`. A complete byte-level local inventory and runtime deployment validation are blocked by the available environment.

## 5. Repository and system understanding

```text
browser -> loopback GUI -> endpoints/models -> bounded job -> report child
                         -> provider policy -> hosted or approved local provider
                         -> sidecars/PDFs -> charts/exports/hashes

internet -> Caddy TLS -> API -> PostgreSQL / Redis / artifact storage
                        -> Prometheus -> Grafana

commit -> pinned CI -> tests/scans/build -> validated artifact -> attestation
```

The GUI is an administrative control plane even in single-user mode. The report child crosses a process boundary and may receive a provider credential. Production services cross separate ingress, data, and observability trust boundaries.

## 6. Architecture profile and control expectations

Required packs: web/browser, API/service, identity/authorization, data/state, asynchronous workflow, LLM/provider execution, CI/CD, container/IaC, network/transport, file/report rendering, cryptography/secret lifecycle, observability/resilience, and privacy/data governance.

| Expectation | Invariant | Status |
|---|---|---|
| EXP-0001 | GUI official launcher is loopback-only | Implemented; runtime pending |
| EXP-0002 | Provider destinations are policy checked and redirects do not carry credentials | Partially implemented; network egress and report-script unification remain |
| EXP-0003 | Report credentials are not regular plaintext files | Implemented with one-shot POSIX FIFO; tests pending |
| EXP-0004 | Only TLS ingress publishes production host ports | Implemented; runtime pending |
| EXP-0005 | Production image builds the complete package and starts declared software | Implemented; build pending |
| EXP-0006 | Desktop reports use exactly two equal columns and chart windows remain visible | Implemented; browser pending |
| EXP-0007 | Actual request bytes are limited before parsing | Implemented; tests pending |
| EXP-0008 | Documentation matches implemented contracts and validation state | Implemented in README, provider guide, and this report |

## 7. Asset and security-objective register

| Asset | Objectives |
|---|---|
| Provider credentials | Confidentiality, purpose binding, rotation, revocation |
| Operator GUI | Reachability control, integrity, availability, auditability |
| Prompts/responses | Confidentiality, provenance, safe rendering |
| Reports/charts/sidecars | Integrity, run binding, reproducibility |
| Database/cache | Isolation, availability, backup/recovery |
| Monitoring | Confidentiality, bounded administration |
| CI artifacts | Integrity, reproducibility, signer identity |

## 8. Identity, privilege, and trust-boundary model

The production API has authentication and project authorization. The GUI has no built-in multi-user identity; its repository-enforced boundary is the loopback listener. Remote access therefore requires a separately authenticated TLS proxy. The GUI process may decrypt endpoint credentials and start provider-capable child processes, so same-account compromise remains material residual risk.

## 9. Data, state, and lifecycle model

Endpoint secrets remain encrypted under a local same-account master key; this is not an external vault. The active official launcher replaces regular plaintext report-key files with a mode-0600 FIFO inside a mode-0700 directory, bounds the value to 4096 bytes, serves one reader, clears the parent bytearray, and removes the path on success or cancellation.

Production Compose requires independent bootstrap passwords and complete encoded database/Redis URLs. API, PostgreSQL, Redis, Prometheus, and Grafana are internal-only; only Caddy publishes ports.

## 10. Attack-surface inventory

| Surface | Side effects | Primary control |
|---|---|---|
| GUI listener | Full operator actions | Loopback-only launcher |
| GUI REST/WebSocket | Mutation, execution, deletion, export | Local boundary, schemas, Origin checks |
| Provider HTTP/CLI | Authenticated outbound request or local identity use | Destination policy, explicit local opt-in |
| Report child | Provider call and artifact creation | Bounded job, FIFO secret transport |
| Reports/charts | Render, delete, export | Path validation, run evidence, same-origin presentation |
| Production API | Database/artifact operations | OIDC/project controls and middleware |
| Monitoring | Metrics query/admin | Internal network, Caddy restriction, admin API disabled |
| CI | Build, scan, publish, attest | Pinned actions, least privilege, fail-closed checks |

## 11. Web and API expectation assessment

The GUI launcher rejects non-loopback binds. Public provider endpoints require HTTPS; private/loopback providers require explicit opt-in and permanent unsafe address classes remain blocked. UX6 enforces exact desktop report columns, one-column fallback below 1024 CSS pixels, fluid outer gutters, chart viewport clamping, and a reset control.

The API now installs `StreamingBodyLimitMiddleware` at package composition. It validates decimal and consistent `Content-Length` when present and independently counts actual ASGI body bytes for chunked, HTTP/2, or missing-length requests before parsing and side effects.

## 12. Knowledge-system provenance and synthesis

Repository history, prior assessments, architecture material, tests, and the supplied visual baseline informed expectations and defensive games. Findings were confirmed from target repository evidence. No real credential, personal data, challenge answer, or exploit-ready payload was committed.

## 13. Defensive security game deck

| Game | Scenario | Result state |
|---|---|---|
| GAME-0001 | Wildcard/private GUI bind | Existing tests; execution pending |
| GAME-0002 | Blocked provider destination and DNS ambiguity | Existing tests; execution pending |
| GAME-0003 | Secret transport file type, one-shot read, cancellation cleanup | New tests; execution pending |
| GAME-0004 | Direct API/monitoring host ports and missing secrets | New tests; execution pending |
| GAME-0005 | Two-column report geometry and viewport escape | Source contracts added; browser blocked |
| GAME-0006 | Chunked overrun, conflicting lengths, exact boundary | New raw ASGI tests; execution pending |
| GAME-0007 | Stock Caddy directives and restricted metrics | New deployment tests; execution pending |

## 14. Individual attack-path analysis

- **PATH-0001:** non-loopback listener → unauthenticated GUI authority. Broken at the official launcher; insecure external proxies remain residual risk.
- **PATH-0002:** stored endpoint URL → prohibited internal destination → credential-bearing request. Application checks improve the path; network egress and report-script unification remain required.
- **PATH-0003:** decrypted endpoint secret → regular temp file → same-account/filesystem recovery. Broken on the official path by the one-shot FIFO.
- **PATH-0004:** direct host port → bypass Caddy/TLS → API or monitoring action. Broken in Compose by internal-only service exposure.
- **PATH-0005:** incomplete build → missing package/undeclared Gunicorn → unhealthy image. Broken by wheel construction and declared Uvicorn runtime.
- **PATH-0006:** chunked/missing-length request → parser allocation/side effect beyond configured budget. Broken by receive-channel byte counting.

## 15. Compound and cross-domain attack-path analysis

GUI reachability, stored credentials, provider egress, subprocess execution, and artifact rendering form one compound control path. The branch adds independent breaks at listener reachability, destination policy, secret handoff, body limits, and evidence presentation.

Production proxy bypass combined with weak fallback credentials and monitoring administration formed a second compound path. The branch removes direct ports and fallback values, requires Redis authentication and full encoded connection URLs, disables Prometheus administration, uses stock Caddy directives, and makes data/observability networks internal.

## 16. Findings register

| ID | Severity | Confidence | Status |
|---|---|---|---|
| SEC-0001 — remote GUI bind exposure | High | High | Remediated in repository; runtime pending |
| SEC-0002 — ingress bypass and weak production configuration | High | High | Remediating; runtime pending |
| SEC-0003 — plaintext report credential file | Medium | High | Remediating; focused tests pending |
| SEC-0004 — incomplete provider destination policy | Medium | Medium | Partially remediated; egress/report-script debt remains |
| SEC-0005 — report geometry and off-screen chart window | Medium | High | Remediating; browser pending |
| SEC-0006 — CI trust claims | High | High | Prior remediation preserved; branch workflow added; result unavailable |
| SEC-0007 — broken production image contract | High | High | Remediating; build pending |
| SEC-0008 — stale security/inventory documentation | Medium | High | Partially remediated; full inventory pending |
| SEC-0009 — header-only body limit | Medium | High | Remediating; actual-byte middleware and tests added |
| SEC-0010 — unsafe/obsolete credential guide | Medium | High | Remediated in documentation; review pending |

## 17. Detailed findings

### SEC-0002
Root cause: direct host publications, known fallback credentials, URL construction from raw passwords, and non-stock proxy assumptions. Selected invariant: only Caddy publishes ports; every production secret/configuration input is explicit; connection URLs are independently encoded. Changes: Compose segmentation, mandatory settings, Redis authentication, Prometheus admin removal, stock Caddy, Caddy admin off, and deployment contracts.

### SEC-0003
Root cause: decrypted provider credentials were written to a regular mode-0600 file. Selected invariant: child handoff must not persist plaintext as a regular file. Changes: one-shot FIFO, bounded length, restrictive permissions, one reader, bytearray clearing, cancellation unblocking, cleanup, composition replacement, and tests.

### SEC-0005
Root cause: `auto-fit`, a full-row exception, fixed centered width, and unbounded drag/resize. Selected invariant: exactly two equal desktop columns, one column below 1024 pixels, aligned outer gutters, and a recoverable viewport-contained chart window. Changes: UX6 CSS/JS and source contracts.

### SEC-0007
Root cause: project installation before source copy and undeclared Gunicorn runtime. Selected invariant: build the full source into a wheel and start declared software. Changes: builder wheelhouse, offline runtime install, non-root Uvicorn, and deployment tests.

### SEC-0009
Root cause: body limits trusted a client-declared header. Selected invariant: actual received bytes are authoritative. Changes: protocol-neutral ASGI receive wrapper, malformed/conflicting header rejection, stable 400/413 responses, and raw ASGI tests.

## 18. Rejected hypotheses and false positives

No confirmed shell-injection path was established in direct argument-array CLI adapters. No confirmed stored XSS was established in reviewed escaped frontend labels. Fernet itself was not found broken; the concern is the local same-account threat model and historical plaintext child handoff.

## 19. Remediation implementation narrative

Implemented layers:

- Wheel-based production image and declared runtime.
- Internal production service networks, mandatory credentials, independent encoded URLs, Redis authentication, stock Caddy, and restricted metrics.
- One-shot FIFO report credential transport installed at the official GUI composition boundary.
- Exact report geometry, fluid page gutters, chart viewport guard, and reset action.
- Actual streamed-body enforcement at the API receive boundary.
- Focused deployment, secret, UI, body-limit, bind, egress, and CI contracts.
- Branch-local hardening workflow for `security/**` pushes.
- Current README, provider credential guide, and master report.

## 20. Validation and assurance

Added tests:

```text
tests/governance/test_production_deployment_contract.py
tests/unit/test_gui_secret_transport.py
tests/unit/test_gui_ux6.py
tests/unit/test_streaming_body_limit.py
```

Required but not recorded as passed:

```bash
make lint
make test
make coverage
python -m build
# synthetic docker compose config
# Docker build and readiness smoke
# caddy validate with the exact image
# browser geometry, zoom, keyboard, a11y, and screenshots
```

A branch-local `.github/workflows/hardening.yml` was added because the existing `dev-mid` base workflow cannot evaluate a new PR trigger from the head branch. The available connector did not expose a completed push-workflow run, so result remains unknown.

## 21. Change-impact, rollout, and rollback

Behavior changes: production now fails early when required values are absent; internal services lose host ports; Redis requires authentication; Prometheus admin endpoints are disabled; full connection URLs are required; keyed official GUI jobs require POSIX FIFO support; report layout becomes two columns at desktop widths; actual body bytes are limited.

Rollout order: supply secrets/configuration, validate Caddy, validate Compose, build/scan image, start data services, API, proxy, then observability, verify closed direct ports, run one synthetic evaluation, verify FIFO cleanup and artifacts, then run browser checks. Do not roll back by restoring weak defaults, direct monitoring ports, Prometheus admin APIs, regular plaintext credential files, or header-only body limits.

## 22. Detection, response, and operational hardening

Alert on non-loopback GUI listeners, blocked provider destinations, missing production inputs, direct internal-service access, secret-transport cleanup failures, repeated body-limit violations, audit degradation, and failed attestation verification. Rotate credentials after suspected exposure. Verify no stale `we3-*-secret-*` directories after jobs.

## 23. Residual risk and accepted assumptions

No risk is accepted on behalf of maintainers. Residuals: no built-in GUI actor identity, POSIX-only FIFO, same-account local key storage, report-script policy not unified with GUI policy, no network-level egress proof, no database TLS deployment contract, image tags not digest-pinned, no complete inventory, and no production/browser/container execution evidence.

## 24. Security debt and maturity ledger

| Debt | Action |
|---|---|
| DEBT-0001 | Run complete inventory and publish hash/coverage ledger |
| DEBT-0002 | Extract one endpoint policy for GUI and report script; enforce workload egress |
| DEBT-0003 | Implement an approved external production `SecretStore` backend |
| DEBT-0004 | Add formal authenticated GUI remote-access contract if remote mode is supported |
| DEBT-0005 | Implement a secure non-POSIX child transport |
| DEBT-0006 | Pin production images by digest and validate Caddy/container runtime |
| DEBT-0007 | Add Playwright geometry, keyboard, a11y, and screenshot gates |
| DEBT-0008 | Define and test production database TLS policy |

## 25. Prioritized future roadmap

1. Obtain branch-workflow results and repair failures without suppression.
2. Run full suite, coverage, build, Compose, Caddy, container, and browser gates.
3. Unify report-script and GUI egress policy with network enforcement.
4. Add external secret-store integration and endpoint-reference migration.
5. Pin images by digest and establish database TLS.
6. Complete inventory and final documentation drift checks.

## 26. Continuous assurance and reassessment triggers

Reassess on changes to identity, GUI binding, endpoint policy, report subprocesses, secrets, middleware, containers, Caddy, browser rendering, CI actions, dependencies, or signing. Reassess after credential exposure, provider DNS/redirect changes, restore, base-image advisories, or deployment topology changes.

## 27. Coverage ledger

Reviewed in targeted depth: branch ancestry, active GUI launcher/runtime, provider path, report child, chart/report frontend, API body limit, Dockerfile, Compose, Caddy, CI, README, provider guide, and supplied screenshots. Blocked/unknown: complete tracked-file count, LFS/submodules/binaries, runtime services, and production state. The unreviewed count is not represented as zero.

## 28. Traceability matrix

| Finding | Main changes | Tests | Representative commits |
|---|---|---|---|
| SEC-0002 | Compose, Caddy, connection URL contract | production deployment contract | `b9c4cb3`, `859fdfa`, `e2fde29`, `c00d046` |
| SEC-0003 | FIFO and composition adapter | secret transport | `2611585`, `2c60e97`, `c378dd5` |
| SEC-0005 | UX6 CSS/JS and overlay | UX6 contract | `5429709`, `31616a6`, `19e4e78` |
| SEC-0007 | wheel image and Uvicorn | production deployment contract | `0026e68`, `99792ed` |
| SEC-0009 | ASGI stream guard and installation | streaming body limit | `2d3f76d`, `9351a0f`, `c773929`, `3f7555b` |
| SEC-0010 | provider guide and README | documentation review/CI pending | `2425abe`, `2ef25d5` |

## 29. Portfolio and cross-repository dependencies

No second authorized repository was identified. External dependencies include provider APIs, local gateways/CLIs, OIDC, container registries, GitHub Actions, databases, Redis, TLS/ACME, and any future secret manager; their deployed state is outside repository-only proof.

## 30. Knowledge delta

Reusable reviewed lessons: mode-0600 regular files are still plaintext-at-rest; reverse proxies do not protect directly published services; raw passwords should not be interpolated into URLs; security configuration must use modules present in the deployed image; responsive `auto-fit` is not an exact comparison contract; and body limits must count actual received bytes.

## 31. Appendices

### A. Draft PR

PR `#25` targets `dev-mid`, is draft, mergeable, unmerged, and contains the integrated 47-commit descendant lineage plus this hardening series.

### B. Primary documentation

- `README.md`
- `docs/operations/api-key-local-model-setup.md`
- `docs/GUI_AND_EVIDENCE_GUIDE.md`
- `docs/security/MASTER_SECURITY_ASSESSMENT.md`

### C. Blocked evidence

Complete inventory; local full test/coverage/build; Docker image and Compose runtime; Caddy validation; browser automation; production identity/TLS/provider/database/cache/network evidence; and completed branch-workflow results.
