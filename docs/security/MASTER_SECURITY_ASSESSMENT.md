# Ben Reaper's Security Partner — Master Security Assessment and Hardening Report

## 1. Document control

| Field | Value |
|---|---|
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Visibility | Public |
| Requested base | `dev-mid` / `aa82b419572e7bc22dbc042fb390357cb1236d1f` |
| Integrated lineage | The dedicated branch was fast-forwarded through the 47 descendant commits ending at `main` / `a0c9d80c2afb97905f7bb88f90995b95504cfaae` before new remediation was added. |
| Assessment branch | `security/hardening-20260801-wilson-eval3ngine` |
| Reviewed remediation head | `19e4e7851cfa5c79a2452ca80d792b6064fc586d` |
| Assessment date | 2026-08-01 |
| Authorization | Assessment, repository modification, dedicated branch publication, push, and draft pull request were explicitly authorized by the repository owner. |
| Completion state | `partial` |
| Runtime evidence | Repository and supplied screenshot evidence only; production deployment and live provider state are unverified. |
| Report path | `docs/security/MASTER_SECURITY_ASSESSMENT.md` |
| Draft pull request | Pending publication at this revision. |

### Revision history

| Revision | Summary |
|---|---|
| 1.0 | Reconciled the requested `dev-mid` base with its 47 descendant commits already present on `main`; preserved that reviewed lineage on the dedicated branch. |
| 1.1 | Repaired the production image and Compose topology, removed weak credential fallbacks and direct internal-service host ports, and added deployment contract tests. |
| 1.2 | Replaced the active report credential regular-file handoff with a bounded one-shot POSIX FIFO and added lifecycle tests. |
| 1.3 | Enforced deterministic two-column report layout, fluid window-edge alignment, and chart viewport containment with source-level regression tests. |

## 2. Partner charter and bounded assurance statement

Repository evidence establishes target facts. Supplied screenshots establish visual behavior only. The partner may implement repository-local fixes on a dedicated branch, but may not deploy to production, use real credentials, alter external identity or cloud systems, merge, or enable auto-merge without separate authorization.

This assessment does not claim the system is fully secure, that production is fixed, or that every repository file has been reviewed. A complete local checkout, deterministic file inventory, repository-native test run, container build, browser execution, and live GitHub Actions results remain required before the completion state can advance beyond `partial`.

## 3. Executive narrative

Wilson Eval3ngine combines a project-scoped evaluation API with a local operator GUI that manages provider endpoints, credentials, models, asynchronous evaluation jobs, subprocesses, telemetry, charts, reports, and destructive actions. The operator GUI therefore acts as an administrative control plane even when it is intended for one local user. The repository also includes a production API topology with PostgreSQL, Redis, Caddy, Prometheus, and Grafana, plus GitHub Actions for build, test, security checks, artifact publication, and provenance.

The requested base branch was materially behind the repository's current linear history. Rather than discard 47 descendant commits that already addressed GUI startup, endpoint egress, CI trust, evidence galleries, documentation, and prior security work, the dedicated branch was advanced through that exact ancestry without force-pushing. The draft pull request remains targeted at `dev-mid`, so reviewers can see the complete integration and new remediation as one bounded change set.

The highest-value remaining repository-local gaps were a production image that could not truthfully install and start the declared application, production services reachable outside the intended TLS proxy, known fallback credentials, plaintext report-key files, nondeterministic report geometry, and chart windows that could leave the visible viewport. This branch fixes those root causes at the image, deployment, runtime-composition, and browser-layout boundaries. Execution evidence is still pending, so each fix is reported as implemented but not runtime-proven.

## 4. Scope, methodology, and limitations

### In scope

- GUI launcher, runtime composition, provider egress, endpoint/model/job/report/chart workflows, and static frontend assets.
- API-key persistence and report-child credential handoff.
- Production Dockerfile, Docker Compose, reverse-proxy topology, monitoring exposure, and required production configuration.
- CI security contracts, repository documentation, current master report, and supplied screenshots.
- Positive and negative regression tests that can run without real providers or production credentials.

### Out of scope or separately authorized

- Live provider or cloud-metadata probing.
- Production deployment, DNS, certificates, OIDC tenant changes, external secret managers, and real credential use.
- Merge, auto-merge, or branch-protection modification.

### Evidence sources

- `[REPO]` GitHub repository files, history, branch ancestry, and prior merged remediation.
- `[RUNTIME]` Supplied Endpoints and Models screenshots only.
- `[INFERENCE]` Architecture and attack-path conclusions tied to repository call paths.
- `[BLOCKED]` Full local checkout, inventory scripts, dependency/container scanners, browser automation, and production runtime proof.

### Coverage limitation

The GitHub connector supported targeted retrieval and mutation but not an exhaustive byte-level local traversal. The coverage ledger therefore records reviewed behavioral surfaces and known blocks rather than claiming zero unreviewed files.

## 5. Repository and system understanding

### Components

- **Primary API:** authenticated project-scoped evaluation, persistence, evidence, governance, and release operations.
- **Operator GUI:** endpoint and model administration, job planning, subprocess execution, charts, reports, telemetry, and exports.
- **Provider boundary:** hosted HTTP APIs, explicitly enabled local/private gateways, and local CLI adapters.
- **Execution boundary:** `scripts/generate_5_reports.py` runs as a child process and creates PDF and JSON evidence.
- **Evidence boundary:** report PDFs, evaluation sidecars, chart PNGs, hashes, telemetry, dossiers, and audit data.
- **Production boundary:** Caddy ingress, API, PostgreSQL, Redis, Prometheus, and Grafana.
- **Supply-chain boundary:** GitHub Actions, package build, security checks, artifacts, SBOM/provenance, and release trust.

```text
browser -> loopback GUI -> endpoint/model state -> job plan -> report child
                         -> provider policy -> hosted or approved local provider
                         -> evaluation sidecar -> chart/report manifest -> browser/export

internet -> Caddy TLS ingress -> API -> PostgreSQL / Redis / artifact volumes
                              -> Prometheus <- Grafana

contributor -> pinned CI -> lint/test/security/build -> tested artifact -> attestation
```

### State and side effects

GUI state is persisted in owner-controlled JSON files. Evaluation jobs mutate job and telemetry state, start provider-capable subprocesses, and create reports/charts. Production API state uses database and artifact storage. Destructive routes include endpoint/model/report/chart deletion and job cancellation.

### Recovery and rollback

State writes use atomic replacement on active GUI paths. The branch preserves existing endpoint, model, job, telemetry, and artifact schemas. The FIFO transport retains the legacy `file_path` call contract, so rollback is limited to runtime-composition code, but restoring the regular-file implementation would reopen plaintext-at-rest exposure and is not a safe rollback without an equivalent transport.

## 6. Architecture profile and control expectations

| Expectation ID | Pack | Invariant | Enforcement point | Status | Finding/debt |
|---|---|---|---|---|---|
| WILSON-EVAL3NGINE-EXP-0001 | Web/identity | The operator GUI cannot be accidentally bound to a non-loopback interface. | `run_gui.validate_bind_host` | Satisfied in repository; runtime pending | SEC-0001 |
| WILSON-EVAL3NGINE-EXP-0002 | Network/LLM | Every provider request is evaluated against explicit destination policy and does not automatically forward credentials across redirects. | GUI policy HTTP client | Partially satisfied | SEC-0004, DEBT-0002 |
| WILSON-EVAL3NGINE-EXP-0003 | Cryptography/secrets | A report child never receives a provider secret through a regular plaintext file, process argument, or log. | Runtime-composition credential transport | Implemented; tests pending | SEC-0003 |
| WILSON-EVAL3NGINE-EXP-0004 | Containers/IaC | Only the intended TLS ingress publishes production host ports and mandatory credentials have no known fallback. | `docker-compose.prod.yml` | Implemented; runtime pending | SEC-0002 |
| WILSON-EVAL3NGINE-EXP-0005 | Supply chain/runtime | The production image builds the complete package before installation and starts only declared runtime software. | `Dockerfile.prod` | Implemented; build pending | SEC-0007 |
| WILSON-EVAL3NGINE-EXP-0006 | Browser/rendering | Desktop report galleries render exactly two equal columns and chart windows remain visible. | UX6 CSS/JS overlay | Implemented; browser execution pending | SEC-0005 |
| WILSON-EVAL3NGINE-EXP-0007 | API | Actual streamed request bytes are bounded before expensive parsing. | API ASGI receive boundary | Violated/open | SEC-0009 |
| WILSON-EVAL3NGINE-EXP-0008 | Governance | Documentation, security status, and validation claims match the assessed head. | Master report and docs CI | Partially satisfied | SEC-0008, SEC-0010 |

Required packs: web/browser, API/service, identity/authorization, data/state, asynchronous workflow, LLM/provider execution, CI/CD, container/IaC, network/transport, file/report rendering, cryptography/secret lifecycle, observability/resilience, and privacy/data governance. Active Directory, mobile, native/FFI, and OT/IoT were not evidenced in the reviewed scope.

## 7. Asset and security-objective register

| Asset | Security objectives | Exposure and recovery |
|---|---|---|
| Provider credentials | Confidentiality, purpose binding, rotation, revocation | GUI process and report child; revoke and rotate after suspected exposure |
| Operator control plane | Authentication boundary, integrity, availability, auditability | Local listener; remote access must terminate at an independently authenticated proxy |
| Prompts and model responses | Confidentiality, integrity, provenance, safe rendering | Provider, reports, telemetry, browser; restore from verified evidence only |
| Reports, charts, sidecars | Integrity, run binding, reproducibility, deletion semantics | Filesystem and browser/export paths; reconcile hashes/manifests |
| Database/cache | Isolation, availability, backup/restore | Internal production data network only |
| Monitoring data | Confidentiality, integrity, bounded administration | Internal observability network only |
| CI artifacts and attestations | Integrity, reproducibility, signer identity | GitHub Actions and downstream consumers; revoke or rebuild on compromise |

## 8. Identity, privilege, and trust-boundary model

The primary API has an explicit authentication and authorization system. The GUI has no built-in actor identity and therefore relies on a loopback host boundary. `run_gui.py` rejects remote binds and converts historical wildcard defaults to loopback; any reverse proxy exposing the GUI must provide its own authenticated TLS and authorization contract.

The GUI process holds filesystem state, decrypts provider credentials, starts child processes, and may access local CLI identities. The report child receives only the credential needed for its selected endpoint. The new one-shot FIFO narrows transport exposure to the parent process, kernel pipe buffer, and one reader; it does not provide an external vault or protect against compromise of the same OS account.

## 9. Data, state, and lifecycle model

Endpoint records persist encrypted credential material under the local GUI account. The current branch does not claim this local encryption is equivalent to an external secret manager. The report-child transport now uses a mode-0600 FIFO inside a mode-0700 temporary directory, writes at most 4096 bytes to one reader, overwrites the parent bytearray, and removes the FIFO directory during success, cancellation, or cleanup.

Production Compose requires database, Redis, Grafana, OIDC, domain, and TLS configuration at interpolation time. API, database, cache, Prometheus, and Grafana expose only internal container ports. Caddy alone publishes host ports. PostgreSQL TLS flags were removed because no certificate mount was evidenced; end-to-end database TLS remains a deployment decision and debt item rather than a misleading configuration claim.

## 10. Attack-surface inventory

| Surface | Identity/authority | Parsing and limits | Side effects | Current state |
|---|---|---|---|---|
| GUI listener | Local host boundary | Uvicorn request/WebSocket limits | Full operator authority | Loopback-only launcher |
| GUI REST/WebSocket | No built-in actor auth | Pydantic schemas, message size | Mutations, execution, deletion, export | Local-only; remote proxy contract required |
| Provider HTTP | Stored endpoint + optional key | URL/DNS/address policy, timeouts | Authenticated outbound request | Improved; network egress still required |
| Report child | Parent process and selected key | Environment/job schema, progress JSONL | Provider calls and artifact creation | FIFO credential transport implemented |
| Reports/charts | Local files and telemetry | Filename/path validation | Browser render, deletion, ZIP export | Evidence-derived active path; manifest maturity remains |
| Production API | OIDC/project identity | Middleware and route schemas | Database/artifact operations | Direct host port removed in Compose |
| Prometheus/Grafana | Internal observability plane | Product-specific auth/config | Metrics query/admin | Host ports removed; Prometheus admin API disabled |
| CI workflows | GitHub workflow identity | YAML/actions/tool inputs | Build, scan, artifact, attestation | Prior hardening preserved; run pending |

## 11. Web and API expectation assessment

The active GUI uses same-origin static assets, a strict script CSP, escaped dynamic labels, bounded Pydantic request models, same-host WebSocket Origin validation, and loopback-only launcher policy. Missing built-in GUI actor identity remains architectural debt; the secure repository default is local-only rather than an unauthenticated remote mode.

The provider policy disables automatic redirects and blocks metadata, link-local, multicast, unspecified, and reserved destinations. Private and loopback providers require explicit opt-in. Application-layer DNS checking cannot eliminate the validation-to-connect race; production requires network-level egress restrictions.

The API body-size middleware still needs an ASGI receive wrapper that counts actual streamed bytes independently of `Content-Length`. That gap remains open as SEC-0009 and is not hidden by this report.

## 12. Knowledge-system provenance and synthesis

The repository's prior assessments, architecture documents, tests, and supplied local security corpus were used to generate expectations and defensive game scenarios. Target findings were confirmed only from repository evidence. No challenge answers, real credentials, personal data, raw exploit payloads, or corpus instructions were committed.

## 13. Defensive security game deck

| Game ID | Scenario | Protected invariant | Safe exercise | Result |
|---|---|---|---|---|
| WILSON-EVAL3NGINE-GAME-0001 | Wildcard/private GUI bind | Local administrative reachability | Unit-test bind parser | Existing tests; execution pending |
| WILSON-EVAL3NGINE-GAME-0002 | Mixed/blocked provider DNS answers | No provider request reaches prohibited networks | Mock resolver/client | Existing tests; execution pending |
| WILSON-EVAL3NGINE-GAME-0003 | Child credential persistence | Secret is never a regular file | Inspect FIFO type/mode and one-shot read | New tests added; execution pending |
| WILSON-EVAL3NGINE-GAME-0004 | Child never opens credential channel | Cleanup cannot hang or leave material | Destroy blocked writer | New test added; execution pending |
| WILSON-EVAL3NGINE-GAME-0005 | Direct API/monitoring access | Only TLS proxy publishes host ports | Parse Compose and isolated network probe | Source test added; runtime probe blocked |
| WILSON-EVAL3NGINE-GAME-0006 | Weak missing production secret | Production config fails before start | Compose interpolation without variables | Contract added; execution pending |
| WILSON-EVAL3NGINE-GAME-0007 | Odd/wide/narrow report gallery | Two desktop columns, one mobile column | Browser geometry and screenshots | Source test added; browser execution blocked |
| WILSON-EVAL3NGINE-GAME-0008 | Drag/resize chart beyond viewport | Modal remains visible and recoverable | Pointer/viewport automation | Guard added; browser execution blocked |

## 14. Individual attack-path analysis

### WILSON-EVAL3NGINE-PATH-0001 — network client to GUI authority

`non-loopback listener -> unauthenticated REST/WebSocket -> endpoint/job/report mutation`

The official launcher breaks the first edge by accepting only loopback addresses. Residual risk exists when an operator intentionally places an unauthenticated proxy in front of the listener.

### WILSON-EVAL3NGINE-PATH-0002 — provider configuration to internal service

`stored URL -> DNS/redirect ambiguity -> internal destination -> credential-bearing request`

The GUI policy client revalidates destinations and disables redirects. Network-level egress policy remains necessary to close the application validation/connect race and to cover independently implemented report-script networking.

### WILSON-EVAL3NGINE-PATH-0003 — endpoint key to filesystem recovery

`encrypted endpoint state -> GUI decryption -> plaintext regular temp file -> same-account/offline recovery -> provider credential`

The active launcher now replaces the regular-file helper with a one-shot FIFO. The secret is not a regular filesystem object and cleanup handles a child that never reads.

### WILSON-EVAL3NGINE-PATH-0004 — proxy bypass to production control plane

`host network -> directly published API/Prometheus/Grafana port -> bypass Caddy/TLS policy -> data or administrative action`

Compose removes those host publications. Only Caddy publishes ports 80 and 443; data and observability networks are internal.

### WILSON-EVAL3NGINE-PATH-0005 — build label to unrunnable image

`Docker build -> install project before source exists -> missing package or undeclared Gunicorn -> unhealthy deployment`

The builder now copies source, creates a wheel, resolves runtime wheels, and the final image installs from that wheelhouse. The image starts declared Uvicorn directly.

## 15. Compound and cross-domain attack-path analysis

### GUI + secrets + subprocess + provider

An exposed GUI could select a credential-bearing endpoint and start a provider-capable child. Loopback-only binding constrains initial reachability, the provider policy constrains destination authority, and FIFO transport removes plaintext regular-file persistence. Built-in GUI identity and network-level egress remain defense-in-depth gaps.

### Compose + proxy + monitoring + weak defaults

Directly published ports combined with known fallback credentials could bypass the intended proxy and expose administration or sensitive telemetry. The branch removes direct ports, requires all production credentials, disables the Prometheus admin API, and separates ingress, data, and observability networks.

### Evidence + browser + responsive controls

Unbounded report/card geometry and draggable windows can hide controls or evidence, increasing operator error during deletion, export, and review. UX6 establishes deterministic two-column desktop geometry, mobile fallback, viewport clamping, and a reset control. Browser execution is still required to prove actual geometry.

## 16. Findings register

| Finding | Severity | Confidence | Status | Component | Residual risk |
|---|---|---|---|---|---|
| WILSON-EVAL3NGINE-SEC-0001 — remote GUI bind exposure | High | High | Remediated in repository; runtime pending | GUI launcher | An insecure external proxy can re-expose the local app |
| WILSON-EVAL3NGINE-SEC-0002 — production ingress bypass and fallback credentials | High | High | Remediating | Compose/Caddy/monitoring | Image digests, Caddy module validation, and runtime probes pending |
| WILSON-EVAL3NGINE-SEC-0003 — plaintext report credential file | Medium | High | Remediating | GUI/report child | POSIX-only transport; same-account compromise and external vault gap remain |
| WILSON-EVAL3NGINE-SEC-0004 — incomplete provider destination policy | Medium | Medium | Partially remediated | HTTP/report networking | Report script and network egress need unified enforcement |
| WILSON-EVAL3NGINE-SEC-0005 — nondeterministic report geometry and off-screen chart window | Medium | High | Remediating | Browser GUI | Browser/a11y execution pending |
| WILSON-EVAL3NGINE-SEC-0006 — CI trust claims | High | High | Prior remediation preserved; run pending | GitHub Actions | Current branch run and attestation verification pending |
| WILSON-EVAL3NGINE-SEC-0007 — broken production image contract | High | High | Remediating | Dockerfile | Clean build/readiness scan pending |
| WILSON-EVAL3NGINE-SEC-0008 — stale security/inventory documentation | Medium | High | Remediating | Documentation | Full inventory and generated docs checks pending |
| WILSON-EVAL3NGINE-SEC-0009 — streamed body limit not enforced by actual bytes | Medium | High | Confirmed/open | API middleware | Requires ASGI receive-bound implementation |
| WILSON-EVAL3NGINE-SEC-0010 — unsafe/obsolete API-key setup guide | Medium | High | Confirmed/open | Operations docs | Must be rewritten after final secret/backend contract |

## 17. Detailed findings

### WILSON-EVAL3NGINE-SEC-0002

**Root cause:** Production topology published internal services directly and used known fallback credentials. **Impact:** A reachable host port could bypass Caddy/TLS policy, while default credentials could permit unauthorized access. **Selected invariant:** only the intended ingress publishes ports; every production credential is mandatory. **Change:** removed API, Prometheus, and Grafana host ports; disabled Prometheus administrative flags; required database, Redis, Grafana, OIDC, domain, and TLS variables; segmented internal networks. **Validation:** source contract added; Compose and runtime network tests pending.

### WILSON-EVAL3NGINE-SEC-0003

**Root cause:** The active job path wrote a decrypted provider key to a mode-0600 regular file. **Impact:** Same-account processes, crash artifacts, snapshots, or filesystem recovery could obtain plaintext during the invocation. **Selected invariant:** child handoff must not persist plaintext as a regular file. **Change:** `OneShotSecretPipe` creates a mode-0600 FIFO in a mode-0700 temporary directory, bounds the value to 4096 bytes, serves one reader, clears parent memory, unblocks safely on cancellation, and removes all paths. The launcher installs it at the runtime composition boundary without changing job schemas. **Compatibility:** POSIX only; unsupported platforms fail closed for keyed report jobs instead of reverting to plaintext. **Validation:** unit tests added; execution pending.

### WILSON-EVAL3NGINE-SEC-0005

**Root cause:** `auto-fit` and a full-row exception made report geometry content-dependent, while chart drag/resize enforced minimums but not viewport maximums. **Impact:** Reports could fail the required two-per-row comparison layout and chart controls could become inaccessible. **Selected invariant:** exactly two equal report columns at desktop widths, one column below 1024 CSS pixels, and a recoverable chart window fully inside the visual viewport. **Change:** UX6 CSS/JS and source-level contract tests. **Validation:** browser geometry, zoom, keyboard, and screenshot tests pending.

### WILSON-EVAL3NGINE-SEC-0007

**Root cause:** The builder invoked a local project install before copying source and the runtime invoked undeclared Gunicorn. **Impact:** Clean builds could fail or produce an image that cannot start. **Selected invariant:** build the complete source into a wheel and start only declared runtime software. **Change:** copied source before build, created wheel and dependency wheelhouse, installed offline into the final stage, and started Uvicorn as a non-root user. **Validation:** Docker build, image scan, and readiness smoke pending.

## 18. Rejected hypotheses and false positives

- The current report browser path escapes dynamic labels rather than inserting them as raw HTML; no confirmed stored XSS was established from the reviewed frontend paths.
- CLI provider adapters use direct argument arrays rather than `shell=True`; no prompt-to-shell interpretation path was confirmed.
- Owner-only encryption and files are not described as equivalent to a remote vault; the issue is threat-model limitation and plaintext child handoff, not an allegation that Fernet itself is broken.
- The supplied screenshots contain no visible credential values and were used only as visual layout evidence.

## 19. Remediation implementation narrative

| Change set | Invariant | Files |
|---|---|---|
| Production image | Complete source is built into a wheel and the final image starts declared software | `Dockerfile.prod` |
| Production topology | Only TLS ingress publishes ports; production secrets are mandatory | `docker-compose.prod.yml`, deployment contract test |
| Secret transport | Report credentials are one-shot and never regular plaintext files | `secret_transport.py`, `ux_overlay.py`, secret transport tests |
| Report geometry | Exactly two equal desktop columns and aligned fluid edges | `ux6.css`, UX6 tests |
| Chart containment | Window remains visible after drag, resize, zoom, and viewport changes | `ux6.js`, UX6 tests |
| Runtime composition | Hardened adapters install before the server accepts requests | `ux_overlay.py` |

The changes intentionally preserve existing endpoint, model, job, report, chart, and telemetry contracts. They avoid a broad GUI rewrite and keep new browser behavior in the repository's reversible versioned overlay pattern.

## 20. Validation and assurance

### Added but not yet executed

- `tests/governance/test_production_deployment_contract.py`
- `tests/unit/test_gui_secret_transport.py`
- `tests/unit/test_gui_ux6.py`

### Required commands

```bash
python -m pytest -q tests/governance/test_production_deployment_contract.py
python -m pytest -q tests/unit/test_gui_secret_transport.py
python -m pytest -q tests/unit/test_gui_ux6.py
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report
WE3_POSTGRES_PASSWORD=test-postgres WE3_REDIS_PASSWORD=test-redis WE3_GRAFANA_PASSWORD=test-grafana WE3_OIDC_ISSUER=https://issuer.invalid WE3_OIDC_JWKS_URI=https://issuer.invalid/jwks WE3_DOMAIN=example.invalid WE3_TLS_EMAIL=security@example.invalid docker compose -f docker-compose.prod.yml config
DOCKER_BUILDKIT=1 docker build -f Dockerfile.prod -t we3:hardening-test .
```

### Browser validation still required

- Two report cards per row at 1024, 1280, 1440, 1920, and 2560 CSS-pixel widths.
- One report column below 1024 pixels.
- Equal card width/row height and no horizontal overflow.
- Drag/resize chart window against every viewport edge, browser resize, 200% zoom, fullscreen/restore, reset, keyboard focus, and reduced-motion behavior.

No command above is represented as passed in this revision.

## 21. Change-impact, rollout, and rollback

### Behavior changes

- Production Compose now refuses interpolation when mandatory credentials, OIDC settings, domain, or TLS email are missing.
- API, Prometheus, and Grafana are no longer directly published on host ports.
- Redis now requires authentication.
- Prometheus admin and lifecycle APIs are disabled.
- Keyed GUI report generation requires POSIX FIFO support through the official launcher.
- Report layout uses two columns at 1024 CSS pixels and above.

### Rollout order

1. Supply production secrets through the deployment's approved secret mechanism.
2. Validate Caddy configuration and the required modules with the exact image.
3. Build and scan the production image.
4. Validate Compose interpolation and isolated service health.
5. Start database/cache, then API, then proxy, then observability.
6. Verify direct host ports are closed and only TLS ingress is reachable.
7. Exercise one synthetic evaluation and verify FIFO cleanup, artifact hashes, chart/report layout, and audit output.

### Rollback

Roll back the entire image/topology change together, restore the last verified state snapshot, and rerun readiness and direct-port checks. Do not restore weak default passwords, Prometheus admin exposure, unsigned artifacts, or the regular plaintext credential file. A compatibility rollback for non-POSIX report execution requires a separately reviewed secure transport rather than plaintext fallback.

## 22. Detection, response, and operational hardening

- Alert on any GUI listener outside loopback.
- Alert on blocked provider destinations, DNS failures, and unexpected redirect responses.
- Monitor missing/invalid production secrets as startup failures, not runtime warnings.
- Alert on direct access attempts to internal API, Prometheus, Grafana, PostgreSQL, or Redis addresses.
- Audit endpoint credential use by secret reference/purpose without value fragments.
- Verify FIFO directory removal after each job and alert on stale `we3-*-secret-*` directories.
- Verify release attestations before downstream use.
- Rotate provider credentials if an earlier GUI instance or temp file may have been exposed.

## 23. Residual risk and accepted assumptions

No risk is accepted on behalf of maintainers.

- Built-in GUI actor identity remains absent; loopback is the enforced repository boundary.
- FIFO transport is POSIX-specific and does not solve same-account process compromise.
- Endpoint encryption still uses a local same-account master key rather than an external production secret manager.
- Report-script networking has separate URL/DNS logic and must be unified with the runtime policy.
- Application DNS validation cannot replace workload-level egress policy.
- Database TLS is not configured in Compose after removing unevidenced certificate paths.
- Container image tags are not yet pinned by digest.
- Streamed request body enforcement remains open.
- Full inventory, browser tests, container tests, and CI execution remain blocked/pending.

## 24. Security debt and maturity ledger

| Debt ID | Missing assurance/control | Recommended action | Status |
|---|---|---|---|
| WILSON-EVAL3NGINE-DEBT-0001 | Complete byte-level inventory and final coverage hash | Run bundled inventory/profile tools from a clean checkout | Blocked |
| WILSON-EVAL3NGINE-DEBT-0002 | Network-level egress and unified report-script policy | Extract one destination-policy module and enforce container egress | Open |
| WILSON-EVAL3NGINE-DEBT-0003 | Production external secret manager/KMS | Implement a versioned `SecretStore` backend and migration | Open |
| WILSON-EVAL3NGINE-DEBT-0004 | Built-in or formally verified GUI identity | Add authenticated proxy contract or application identity | Open |
| WILSON-EVAL3NGINE-DEBT-0005 | Non-POSIX secure child transport | Implement stdin/handle transport with cross-platform tests | Open |
| WILSON-EVAL3NGINE-DEBT-0006 | Image digest pinning and Caddy module proof | Resolve and pin exact production images; run `caddy validate` | Open |
| WILSON-EVAL3NGINE-DEBT-0007 | Browser geometry/accessibility evidence | Add Playwright geometry, keyboard, a11y, and screenshot jobs | Open |
| WILSON-EVAL3NGINE-DEBT-0008 | Actual streamed body bound | Implement ASGI receive counting and fault tests | Open |

## 25. Prioritized future roadmap

1. Execute CI and repair genuine failures without suppressing controls.
2. Unify GUI and report-script endpoint policy and add network egress enforcement.
3. Implement actual streamed-body limits before parsing.
4. Add browser geometry, accessibility, and screenshot gates.
5. Introduce an external production secret-store adapter and versioned endpoint references.
6. Pin production images by digest and validate Caddy modules/TLS.
7. Complete full-tree inventory and regenerate documentation/evidence indexes.
8. Rewrite the API-key/local-model guide after the final secret and endpoint policy contracts are stable.

## 26. Continuous assurance and reassessment triggers

Reassess after changes to authentication, GUI binding, provider adapters, report subprocesses, secret storage, Docker/Compose/Caddy, browser rendering, CI actions, package locks, or artifact signing. Reassess after credential exposure, provider redirect/DNS behavior changes, backup restoration, image base updates, or a material security advisory. Recurring checks should cover branch rules, dependency advisories, image vulnerabilities, secret scans, report/chart provenance, audit health, direct-port exposure, and stale FIFO directories.

## 27. Coverage ledger

| Category | Status |
|---|---|
| Repository metadata and branch ancestry | Reviewed |
| Active GUI launcher/runtime/application paths | Reviewed in targeted depth |
| Provider policy and report-child credential path | Reviewed in targeted depth |
| Charts/reports frontend overlays | Reviewed in targeted depth |
| Production Dockerfile and Compose | Reviewed and changed |
| CI and prior master report | Reviewed in targeted depth |
| Supplied screenshots | Reviewed visually |
| Complete tracked-file inventory | Blocked without local checkout |
| Binary/archive/LFS/submodule inventory | Blocked/unknown |
| Runtime deployment and external services | Not tested |

The unreviewed count is unknown and is not represented as zero. A final inventory hash must be added before completion.

## 28. Traceability matrix

| ID | Evidence | Change | Test | Commit(s) | Status |
|---|---|---|---|---|---|
| SEC-0002 | `docker-compose.prod.yml`, Caddy topology | Internal-only services, required credentials, Redis auth, admin API removal | deployment contract | `b9c4cb3`, `0425f26` | Implemented; not run |
| SEC-0003 | application report invocation and key-file helper | one-shot FIFO + composition adapter | secret transport | `2611585`, `2c60e97`, `51877ae` | Implemented; not run |
| SEC-0005 | existing CSS/JS and screenshots | UX6 CSS/JS + overlay | UX6 contract | `5429709`, `31616a6`, `1dd219f`, `19e4e78` | Implemented; not run |
| SEC-0007 | `Dockerfile.prod`, `pyproject.toml` | wheel build/install and Uvicorn runtime | deployment contract | `0026e68`, `0425f26` | Implemented; not run |
| SEC-0009 | API middleware | No code change in this revision | Pending streamed-body tests | None | Open |
| SEC-0010 | API-key operations guide | No final rewrite in this revision | Docs checks pending | None | Open |

## 29. Portfolio and cross-repository dependencies

No second authorized repository was identified. External dependencies include hosted model providers, local model gateways, OIDC, container registries, GitHub Actions, and any future secret manager. Their deployed configuration and availability are outside repository-only proof.

## 30. Knowledge delta

Reusable lessons proposed for review:

- A mode-0600 regular file is access-controlled but still plaintext-at-rest; a one-shot FIFO can preserve a path-based child contract while removing persistent content on POSIX.
- A reverse proxy does not protect a service that is also published directly.
- Security configuration that references absent certificate files is weaker than an explicit documented debt because it creates false confidence and startup failure.
- Responsive `auto-fit` is not equivalent to an exact comparison layout contract; geometry needs explicit columns and browser tests.
- A runtime package install must occur after complete source availability, and the final command must be backed by declared dependencies.

These are sanitized candidates only and are not automatically promoted into a governed corpus.

## 31. Appendices

### A. Branch ancestry decision

`dev-mid` at `aa82b419572e7bc22dbc042fb390357cb1236d1f` is an ancestor of `main` at `a0c9d80c2afb97905f7bb88f90995b95504cfaae`. The dedicated branch was created from `dev-mid` and fast-forwarded, without force, through those 47 commits before new work. The pull request remains based on `dev-mid` so the complete descendant integration is visible and reviewable.

### B. Added validation files

- `tests/governance/test_production_deployment_contract.py`
- `tests/unit/test_gui_secret_transport.py`
- `tests/unit/test_gui_ux6.py`

### C. Blocked evidence

- Bundled inventory and report-validator execution.
- Full formatter/lint/type/test/coverage run.
- Docker build, Compose config, image scan, and Caddy validation.
- Browser automation and accessibility scan.
- GitHub Actions and attestation verification for the draft pull request.
- Production identity, TLS, provider, database, cache, and network evidence.
