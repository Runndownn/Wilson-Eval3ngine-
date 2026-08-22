# Wilson Eval3ngine — Security, Reliability, GUI, Reporting, and Documentation Hardening Plan

## Plan Metadata

- **Repository:** `https://github.com/Runndownn/Wilson-Eval3ngine-`
- **Requested base:** `dev-mid`
- **Exact base commit:** Blocked until a complete checkout or branch-ref API response exposes the current `dev-mid` SHA
- **Plan version:** 1.0
- **Date:** 2026-08-01
- **Status:** Proposed; read-only assessment complete, implementation awaiting approval
- **Owner:** @unassigned
- **Authorization:** The repository owner explicitly authorized assessment, modification, creation of a dedicated hardening branch, push, and draft pull request
- **Source assessment:** Connector-based static review of current `dev-mid` files plus the two supplied GUI screenshots
- **Target platforms/toolchains:** Python 3.12–3.14, FastAPI/Uvicorn, browser GUI, Docker Compose, PostgreSQL, Redis, Caddy, Prometheus, Grafana, GitHub Actions
- **Evidence limitations:** A full checkout, recursive tree, current branch SHA, test execution, browser automation, container build, Caddy validation, and runtime provider connectivity were unavailable in this read-only pass
- **Proposed implementation branch:** `security/hardening-20260801-wilson-eval3ngine` with a numeric suffix if that branch already exists
- **Proposed master report:** `docs/security/MASTER_SECURITY_ASSESSMENT.md`
- **Planning format:** Repository-native TODO detail adapted to the validated execution-plan contract

## Objective

Produce a reviewable hardening series that makes the active Wilson Eval3ngine implementation safer to run locally and remotely, more reliable under failure and concurrency, more accurate about evidence provenance, and easier to operate. The work will enforce a real access boundary around the GUI, replace overclaimed local secret handling with an explicit secret-store abstraction and safe subprocess handoff, constrain endpoint networking without breaking authorized local Ollama use, repair production deployment and CI contracts, and make chart/report rendering deterministic, symmetric, responsive, and provenance-backed.

The same change series will create a living master security assessment, reconcile stale repository claims with the inspected code, add adversarial regression coverage, and rewrite the README so setup, security modes, visual samples, diagrams, and operational constraints match the implementation.

## Scope

- Active GUI composition in `src/wilson_eval3ngine/gui/application.py`, `runtime.py`, and `run_gui.py`.
- Compatibility helpers still consumed from `src/wilson_eval3ngine/gui/server.py`.
- Secret lifecycle in `src/wilson_eval3ngine/gui/api_key_vault.py`, endpoint persistence, report generation, CLI/provider adapters, and operational guidance.
- Endpoint URL validation, DNS/IP policy, local/private-network profiles, outbound HTTP behavior, redirect behavior, timeouts, response limits, and audit evidence.
- Chart generation, chart gallery behavior, report rendering, report-card layout, viewport alignment, deletion/export behavior, and evidence provenance.
- API middleware controls that affect body limits, CORS, CSRF, authentication, authorization, rate limiting, and exceptional conditions.
- `Dockerfile.prod`, `docker-compose.prod.yml`, Caddy, health checks, secret injection, port exposure, image pinning, and least privilege.
- `.github/workflows/ci.yml`, Makefile gates, dependency resolution, scanner acquisition, SBOM, provenance, signing, and reproducibility.
- README, GUI guide, API-key/local-model guide, security reports, evidence inventories, generated diagrams, and supplied screenshots.
- Unit, integration, browser, security-regression, container, deployment, and documentation checks.
- Dedicated branch, coherent commits, draft pull request, rollout/rollback notes, and residual-risk ledger.

## Non-goals

- No merge or auto-merge.
- No claim that a repository-only patch proves production deployment is secure.
- No unrestricted public-hosting mode for the operator GUI.
- No removal of supported local Ollama, CLI adapters, or configurable bind addresses; remote use will instead require an explicit security profile.
- No replacement of the evaluation taxonomy or unrelated product features.
- No storage of real provider tokens, private internal addresses, usernames, or production data in tests or documentation.
- No automatic acceptance of residual risk on behalf of maintainers.
- No reproduction of offensive challenge payloads against real systems.

## Authority and Evidence Baseline

Repository evidence is authoritative for implementation claims. The active GUI entry point imports `wilson_eval3ngine.gui.runtime:app`, which composes the validated application boundary and selected legacy helpers; findings therefore distinguish reachable application behavior from inactive legacy routes. The supplied screenshots establish only the Endpoints and Models visual baseline; they do not prove Charts or Reports runtime behavior.

Material baseline facts:

- `we3-gui-start` resolves to `wilson_eval3ngine.gui.run_gui:main`.
- GUI bind defaults to loopback, but any non-loopback bind is accepted with only a warning.
- The active GUI application exposes state-changing endpoint, model, job, chart, and report operations without built-in authentication or authorization.
- The GUI persists endpoint secrets through a local Fernet scheme whose master key is a file owned by the same local account; report subprocesses currently receive secrets through owner-readable plaintext temporary files.
- Public HTTP provider endpoints are rejected, while explicitly configured local/private HTTP endpoints are allowed.
- The CSS report grid uses auto-fit rather than a deterministic two-column contract, and the main container is centered behind a fixed maximum width.
- The draggable/resizable chart window has minimum bounds but no right/bottom viewport clamp.
- The production Compose file publishes API, Prometheus, and Grafana ports directly and supplies weak fallback credentials.
- CI suppresses lint failure, does not cover `dev-mid`, labels a single hash as determinism verification, and labels an echo plus digest file as signing.
- The production Dockerfile invokes Gunicorn although Gunicorn is absent from declared dependencies and attempts to install the local project before copying the package source.
- The July security assessment and older inventory/manifest contain claims that no longer match the current implementation.
- No canonical `docs/security/MASTER_SECURITY_ASSESSMENT.md` exists on `dev-mid`.

## Current-State Architecture Summary

### Experience and operator plane

The browser loads static HTML, CSS, and JavaScript from the GUI process. REST endpoints handle inventory, endpoint/model mutation, job lifecycle, telemetry, report files, chart metadata, and deletion/export actions. A same-origin WebSocket carries job subscriptions and compatibility actions.

### GUI application and compatibility plane

`run_gui.py` starts the app exported by `runtime.py`. `runtime.py` composes `application.py` and deliberately reuses selected functions and data paths from the larger `server.py` compatibility module, especially provider tests, report generation, telemetry enrichment, and chart generation.

### Evaluation and artifact plane

The GUI builds a bounded job plan and invokes `scripts/generate_5_reports.py` as a subprocess. Evaluation sidecars and PDFs are written under the repository report path, chart PNGs are generated beneath the static chart tree, and JSON job/telemetry/endpoint/model state is stored under `gui/data`.

### Provider and network plane

Registered models map to endpoint records. Endpoint adapters may use HTTPS providers, explicitly configured local/private HTTP services such as Ollama, or local CLI tools. Credentials are decrypted in the GUI process and made available to provider calls or report subprocesses.

### Production API and infrastructure plane

A separate API application uses authentication, authorization, persistence, and middleware modules. The production files describe Caddy, API, PostgreSQL, Redis, Prometheus, and Grafana, but the published ports and secret defaults create bypass paths around the intended proxy boundary.

### Build, release, and assurance plane

GitHub Actions builds, tests, runs repository-native supply-chain checks, validates an example, generates an SBOM-like artifact, and uploads release artifacts. Several named controls are presently descriptive rather than enforced, and the inspected workflow does not execute for `dev-mid`.

### Required architecture profiles

Required: web/browser, API/service, identity/authorization, data/state, asynchronous workflow, LLM/provider execution, CI/CD, container/IaC, network/transport, file/report rendering, cryptography/secret lifecycle, observability/resilience, and privacy/data governance. Active Directory, mobile, native/FFI, and OT/IoT are not supported by current target evidence and remain not applicable unless the complete inventory shows otherwise.

## Confirmed Findings

| ID | Severity | Confidence | Finding | Primary evidence |
|---|---|---:|---|---|
| `WILSON-EVAL3NGINE-SEC-0001` | High | High | Non-loopback GUI binding exposes an unauthenticated operator control plane; same-host Origin checking is not an identity or authorization boundary, and missing WebSocket Origin is accepted. | `run_gui.py`, `application.py` REST and WebSocket routes |
| `WILSON-EVAL3NGINE-SEC-0002` | High | High | Production Compose publishes API, Prometheus admin API, and Grafana directly, bypassing the intended Caddy/TLS path, while PostgreSQL and Grafana have known fallback credentials. | `docker-compose.prod.yml`, `infrastructure/caddy/Caddyfile` |
| `WILSON-EVAL3NGINE-SEC-0003` | Medium | High | The GUI “vault” stores its master key beside the application account, creates plaintext API-key temp files for subprocesses, cannot zero returned Python strings, and has no external-vault/KMS/keyring integration or multi-process-safe master-key initialization. | `api_key_vault.py`, report-generation call paths |
| `WILSON-EVAL3NGINE-SEC-0004` | Medium | Medium | Authorized local/private endpoints are supported without a complete destination policy, connect-time IP revalidation, redirect revalidation, or an explicit per-endpoint CIDR/port allowlist, leaving DNS rebinding and internal-service reachability insufficiently constrained. | `application.py::_normalize_endpoint_url`, legacy HTTP helpers |
| `WILSON-EVAL3NGINE-SEC-0005` | Medium | High | Report cards are not guaranteed to render two equal columns, the main content does not align to large-window edges, and chart windows can be dragged or resized beyond the visible viewport. | `enhanced.css`, `enhanced.js::initializeChartWindow` |
| `WILSON-EVAL3NGINE-SEC-0006` | High | High | CI quality and release-integrity labels exceed their enforcement: lint is ignored, `dev-mid` is not covered, determinism is not compared across clean rebuilds, scanner download is not verified, and “signing” performs no cryptographic signature or attestation. | `.github/workflows/ci.yml`, `Makefile` |
| `WILSON-EVAL3NGINE-SEC-0007` | High | High | The production image contract is internally inconsistent: the local project is installed before package source is copied, and the runtime starts Gunicorn although it is not declared in project dependencies. | `Dockerfile.prod`, `pyproject.toml` |
| `WILSON-EVAL3NGINE-SEC-0008` | Medium | High | Security, inventory, and production-readiness documentation is stale and contradictory; the canonical living master report required for traceability is absent. | `docs/security/SECURITY_ASSESSMENT.md`, dated evidence inventory and framework manifest |
| `WILSON-EVAL3NGINE-SEC-0009` | Medium | High | API request-size enforcement checks declared `Content-Length` but does not independently bound streamed/chunked bodies before downstream parsing. | `src/wilson_eval3ngine/api/middleware.py::BodySizeLimitMiddleware` |
| `WILSON-EVAL3NGINE-SEC-0010` | Medium | High | The API-key/local-model guide includes environment-specific topology, an unsafe environment-variable/token-file workflow, a broken tilde-expansion command, an obsolete GUI entry point, and security claims that exceed the local file-vault threat model. | `docs/operations/api-key-local-model-setup.md` |

## Assumptions and Unresolved Decisions

- **Unresolved:** The exact current `dev-mid` commit SHA and recursive tracked-file inventory.
- **Unresolved:** Whether repository protection rules require CI on `dev-mid` or only on pull requests targeting `main`.
- **Unresolved:** Whether remote GUI use is a supported production mode or an operator-only maintenance mode. The plan supports both through explicit profiles but requires a maintainer decision on the default remote identity provider.
- **Unresolved:** Preferred production secret backend: HashiCorp Vault, cloud secret manager/KMS, OS keyring, or a pluggable interface supporting more than one.
- **Unresolved:** Whether the production API and GUI are intended to share a reverse proxy/domain or remain separate deployables.
- **Unresolved:** Whether vanilla `caddy:2-alpine` can parse the repository's `rate_limit` directives; this requires `caddy validate` with the actual image.
- **Unresolved:** Whether PostgreSQL TLS certificate/key files exist in the runtime image or mounted volumes; Compose does not currently demonstrate that path.
- **Unresolved:** Browser support baseline and exact responsive breakpoints. The proposed default is two columns at widths of 1024 CSS pixels and above, one column below.
- **Inferred:** Local/private endpoint support is intentional because the user requires loopback and current-IP configurability.
- **Best practice:** Use an external or OS-protected secret backend for production and a narrowly scoped encrypted local backend only for single-user development.
- **Best practice:** Treat reports, model output, telemetry, and chart metadata as untrusted content at every rendering/export sink.

## Workstream and Dependency Map

1. Baseline and branch control gate all work.
2. GUI access control, secret lifecycle, endpoint network policy, and production exposure are P0 security workstreams that may proceed in parallel after the baseline.
3. Chart/report layout depends on stable API contracts but not on the secret-store implementation.
4. CI hardening must land before the final validation commit so every later change is gated.
5. README and diagram work follows stabilized behavior and records verified commands rather than planned commands.
6. The master report is created before the first remediation commit and updated after every workstream.
7. The draft pull request is opened only after full diff review, secret scanning, plan/report validation, and all executable gates complete or have explicit blockers.

## Execution Tasks

### [ ] P0-1 — Establish the exact repository baseline, branch, and living assessment

- **Priority:** P0
- **Owner:** @unassigned
- **Dependencies:** None
- **Status:** Not started
- **Evidence:** requested `dev-mid`; stale `docs/evidence-inventory.md`; stale `FRAMEWORK_MANIFEST.json`; absent `docs/security/MASTER_SECURITY_ASSESSMENT.md`; findings `WILSON-EVAL3NGINE-SEC-0008`
- **Purpose:** Establish one immutable source of truth before changing behavior and create the traceability authority required for every later remediation.
- **Affected surfaces:** complete repository tree, Git metadata, submodules/LFS if present, tests, generated assets, docs, workflows, containers, `docs/security/MASTER_SECURITY_ASSESSMENT.md`
- **Constraints:** Do not execute unknown binaries or connect to real providers; do not overwrite an existing hardening branch; do not claim inaccessible files were reviewed.

#### Implementation steps
1. Resolve the latest `dev-mid` SHA, repository rules, submodules, LFS objects, symlinks, generated/vendor status, and worktree state from a clean isolated checkout.
2. Run the repository inventory script and generate a hash-addressed coverage ledger for every accessible file and exact duplicate set.
3. Create `security/hardening-20260801-wilson-eval3ngine`, adding a numeric suffix when required.
4. Create `docs/security/MASTER_SECURITY_ASSESSMENT.md` before the first remediation commit and register all findings, expectations, compound paths, evidence classes, tests, residual risks, and status transitions.
5. Reconcile README, security assessment, evidence inventory, manifests, CI claims, and test-count claims against the exact base.
6. Capture tool versions, commands, timestamps, exit codes, stdout/stderr hashes, and blocked external dependencies.

#### Edge and failure cases
- Shallow clone, detached HEAD, inaccessible LFS object, broken symlink, case-colliding paths, generated files outside Git, unavailable provider credentials, or tests that require live infrastructure.

#### Security, safety, and privacy controls
- Inventory in read-only mode first; redact secret-like values; do not follow symlinks outside the checkout; quarantine unknown binaries and archives from execution.

#### Observability and debugging
- Persist the inventory JSON, claim-to-evidence matrix, command ledger, and a human-readable coverage summary in the master report.

#### Tests
- Run inventory determinism twice; validate path normalization and duplicate grouping; execute repository-native format, build, and test discovery without external providers.

#### Acceptance criteria
- [ ] Every accessible file is present in the coverage ledger or an exact-duplicate group tied to the exact `dev-mid` SHA.
- [ ] The dedicated branch and master report exist before any remediation commit.
- [ ] Every pre-existing “implemented,” “passing,” “secure,” or “production-ready” claim is verified, corrected, or marked blocked.
- [ ] No secret or uncontrolled personal data is written to evidence artifacts.

#### Risks and mitigations
- **Risk:** The baseline reveals a materially different architecture than the connector review.
  **Mitigation:** Pause dependent tasks, update finding status/evidence, and reissue the plan delta before broad edits.

### [ ] P0-2 — Enforce an authenticated GUI exposure boundary while preserving configurable binds

- **Priority:** P0
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `run_gui.py::main`; unauthenticated REST routes and `application.py::websocket_endpoint`; finding `WILSON-EVAL3NGINE-SEC-0001`
- **Purpose:** Ensure that network reachability alone cannot create, delete, execute, cancel, read, or export operator-controlled resources.
- **Affected surfaces:** `run_gui.py`, `runtime.py`, `application.py`, frontend request/WebSocket helpers, configuration, reverse-proxy examples, tests, README
- **Constraints:** Keep loopback as the frictionless default; retain explicit IP binding; remote mode must fail closed when identity configuration is absent.

#### Implementation steps
1. Introduce explicit profiles: `local-loopback`, `remote-token`, and `remote-proxy`, with `local-loopback` as the default.
2. Reject non-loopback binds unless `--allow-remote` and a supported authentication profile are both supplied.
3. Add a server-side principal/capability model for read, configure, execute, cancel, delete, export, and administration operations.
4. Require authorization on every REST and WebSocket action at the authoritative operation boundary.
5. Require an exact allowed Origin for browser WebSockets; reject missing Origin in remote mode and enforce a separate non-browser authentication path when needed.
6. Add CSRF protection for cookie-authenticated state changes; when bearer tokens are used, require `Authorization` and prohibit ambient cookie fallback.
7. Add host validation and explicit trusted-proxy configuration; never trust forwarded identity or scheme headers from arbitrary clients.
8. Update the frontend to acquire, retain, and send the configured credential without storing long-lived secrets in `localStorage`.
9. Add audit events with actor, action, object, outcome, correlation ID, and source profile.
10. Document an authenticated TLS reverse-proxy example and a loopback-only SSH-tunnel alternative.

#### Edge and failure cases
- IPv4/IPv6 loopback, Unix socket, missing Origin, null Origin, DNS alias, proxy restart, stale session, role change, multiple browser tabs, WebSocket reconnect, and cancellation during authorization changes.

#### Security, safety, and privacy controls
- Use constant-time token comparison where applicable; hash stored API access tokens; set secure cookie attributes; rotate credentials; redact tokens and session identifiers from logs.

#### Observability and debugging
- Emit bounded authentication/authorization denial counters, session creation/revocation events, WebSocket connect/disconnect outcomes, and proxy-trust decisions.

#### Tests
- Unit-test profile parsing and authorization matrix; integration-test every mutating route/action as anonymous, read-only, operator, and administrator; browser-test CSRF, Origin, logout/revocation, and reconnect behavior.

#### Acceptance criteria
- [ ] A non-loopback start without an explicit secure profile exits non-zero before opening a socket.
- [ ] Anonymous clients cannot mutate, execute, cancel, delete, export, or read sensitive telemetry in remote mode.
- [ ] Loopback mode remains usable with a documented local threat model and no silent transition to remote exposure.
- [ ] WebSocket and REST authorization matrices produce equivalent decisions for equivalent actions.

#### Risks and mitigations
- **Risk:** Authentication breaks existing single-user workflows.
  **Mitigation:** Preserve loopback-only local mode, add migration guidance, and keep remote enforcement behind an explicit versioned configuration contract.

### [ ] P0-3 — Replace the file-only “vault” with a versioned secret-store and secret-safe process handoff

- **Priority:** P0
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `api_key_vault.py`; endpoint `encryptedApiKey`; `store_api_key_temp_file`; report subprocess environment; finding `WILSON-EVAL3NGINE-SEC-0003`
- **Purpose:** Protect provider credentials according to an explicit threat model, remove plaintext-at-rest handoff, enable rotation/revocation, and eliminate unsupported “memory zeroing” and “production vault” claims.
- **Affected surfaces:** secret module, endpoint schema/migration, report process launcher, provider clients, audit, configuration, docs, tests
- **Constraints:** Preserve existing encrypted endpoint records through a one-way migration; never log, serialize, or return plaintext credentials; avoid provider-specific hardcoding.

#### Implementation steps
1. Define a `SecretStore` protocol with `put`, `get_for_use`, `rotate`, `revoke`, `metadata`, and `delete`, plus versioned secret references rather than ciphertext in endpoint objects.
2. Implement a development backend with a 0700 directory, atomic `O_EXCL` initialization, 0600 files, key-version metadata, authenticated encryption, and an explicit same-user compromise limitation.
3. Add pluggable production adapters for a selected external secret manager/KMS or OS credential store; fail closed in production when only the development backend is configured.
4. Replace plaintext temporary files with an inherited pipe/file descriptor or standard input dedicated to the child process; close descriptors in unrelated children and guarantee cleanup on timeout/cancel/crash.
5. Remove no-op string-zeroing claims; minimize immutable plaintext lifetime and keep secrets out of exception text, command lines, environment variables, telemetry, artifacts, and browser responses.
6. Add rotation and migration logic for legacy `apiKey` and `encryptedApiKey` fields, including rollback metadata that never restores plaintext.
7. Make audit failure behavior explicit: high-risk secret mutation fails closed or writes to a durable fallback, while read/use events expose a degraded-audit signal.
8. Add a secret-store health check that reports backend readiness without revealing key identifiers beyond approved metadata.

#### Edge and failure cases
- Concurrent first start, corrupted key metadata, rotation during an active job, revoked secret, unavailable vault, child crash, timeout, cancellation, process fork, stale endpoint reference, and restore from backup.

#### Security, safety, and privacy controls
- Purpose-bind secret use to endpoint/provider/job, use least-privilege vault policies, restrict secret metadata, use TLS and hostname verification to external vaults, and support emergency revocation.

#### Observability and debugging
- Record secret-reference version, purpose, actor/workload, decision, outcome, latency, and backend health; never record plaintext, ciphertext, bearer headers, or child descriptors.

#### Tests
- Unit-test cryptographic serialization and migration; concurrency-test initialization and rotation; integration-test child-process handoff and descriptor closure; fault-inject vault outage, invalid token, cancellation, and crash cleanup.

#### Acceptance criteria
- [ ] No report/provider subprocess receives a credential through plaintext temp files, command arguments, or environment variables.
- [ ] Production mode refuses to start without an approved secret backend and valid transport trust.
- [ ] Legacy records migrate without exposing plaintext in files, logs, responses, or test output.
- [ ] Rotation, revocation, failed lookup, and audit degradation have deterministic tested behavior.

#### Risks and mitigations
- **Risk:** Provider jobs fail during migration or rotation.
  **Mitigation:** Version references, dual-read migration for a bounded window, preflight health checks, and rollback to the previous key version without plaintext restoration.

### [ ] P0-4 — Enforce a destination policy for remote, loopback, and private model endpoints

- **Priority:** P0
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `application.py::_normalize_endpoint_url`, `_is_local_hostname`, legacy HTTP clients; finding `WILSON-EVAL3NGINE-SEC-0004`
- **Purpose:** Preserve authorized local Ollama and gateway use while preventing endpoints from becoming a general internal-network or metadata-service request primitive.
- **Affected surfaces:** endpoint model, URL parser, provider adapters, HTTP client creation, discovery/testing, report generation, configuration, audit, tests
- **Constraints:** One authoritative parser and policy; no string-prefix CIDR logic; no implicit trust based solely on a hostname resolving private once.

#### Implementation steps
1. Add an `EndpointNetworkPolicy` object containing profile, allowed schemes, exact hosts/CIDRs, ports, path prefixes, redirect policy, DNS policy, and TLS requirements.
2. Define safe presets: `public-https`, `loopback-ollama`, `private-gateway`, and `cli`; require explicit selection for private networks.
3. Resolve all addresses, reject mixed allowed/blocked answers, block link-local, metadata, multicast, unspecified, and Unix-socket destinations, and revalidate the actual connected peer where the HTTP stack permits.
4. Disable redirects by default; when enabled, validate every redirect target and strip authorization headers on origin change.
5. Bound connection/read/write/pool timeouts, body size, decompression, JSON depth/shape, and retry behavior.
6. Bind credentials to the configured origin and provider purpose; never forward them to a redirected or discovered host.
7. Apply the same policy to endpoint creation, test, discovery, model refresh, report execution, and background retries.
8. Add egress-policy examples for local containers and remote deployments.

#### Edge and failure cases
- IPv6, DNS rebinding, split-horizon DNS, trailing dots, IDNA, alternate IP notation, userinfo, fragments, proxy variables, redirects, HTTPS-to-HTTP downgrade, multi-address hosts, and network changes between validation and connection.

#### Security, safety, and privacy controls
- Reject cloud metadata ranges regardless of profile; require TLS for public endpoints; allow cleartext only for explicitly approved loopback/private scopes; never expose resolved internal addresses to unprivileged clients.

#### Observability and debugging
- Log normalized destination, policy ID/version, resolution class, redirect decision, and safe failure category; retain no credentials or full sensitive URLs.

#### Tests
- Table-driven parser tests, mocked DNS/connect peer tests, redirect tests, proxy-environment tests, local Ollama positive tests, and metadata/private-network negative tests.

#### Acceptance criteria
- [ ] Every outbound provider request is authorized by one versioned destination policy at connection time.
- [ ] Authorized loopback/private endpoints remain configurable without enabling arbitrary private-network access.
- [ ] Redirects and DNS changes cannot move credentials or requests to a destination outside policy.
- [ ] The same test corpus covers GUI endpoint testing, discovery, and report generation.

#### Risks and mitigations
- **Risk:** Strict policy blocks legitimate dynamic gateway addresses.
  **Mitigation:** Support reviewed CIDR/hostname policy sets with diagnostics and an explicit operator change process rather than permissive fallback.

### [ ] P0-5 — Make the production container and network topology buildable, fail-closed, and non-bypassable

- **Priority:** P0
- **Owner:** @unassigned
- **Dependencies:** P0-1, P0-2, P0-3
- **Status:** Not started
- **Evidence:** `Dockerfile.prod`, `docker-compose.prod.yml`, `Caddyfile`, `pyproject.toml`; findings `WILSON-EVAL3NGINE-SEC-0002` and `WILSON-EVAL3NGINE-SEC-0007`
- **Purpose:** Ensure the declared production path actually builds, starts, uses required secrets, and exposes only the intended authenticated TLS ingress.
- **Affected surfaces:** production Dockerfile, Compose, Caddy, health endpoints, dependency manifests/lock, secret mounts, observability service exposure, operations docs
- **Constraints:** No weak credential fallback in production; no direct host publication of internal control planes; retain a documented loopback-only debug profile separately.

#### Implementation steps
1. Copy build metadata and package source in a valid order, build a wheel in an isolated stage, and install only the resulting wheel plus pinned runtime dependencies.
2. Either declare and pin Gunicorn or use a supported Uvicorn process model; add a startup smoke test matching the final command.
3. Generate a lock with hashes or equivalent reproducible dependency artifact and enforce it in image/CI builds.
4. Remove production fallback passwords and require Docker secrets or mounted secret references.
5. Replace direct host `ports` for API, Prometheus, and Grafana with internal `expose` or loopback-only mappings in an explicit debug override.
6. Disable Prometheus admin API unless a separately authenticated maintenance profile requires it.
7. Validate/mount PostgreSQL TLS material or remove invalid TLS flags until a complete certificate path exists; document client/server verification.
8. Pin images by digest, drop capabilities, set resource limits, health checks, read-only mounts, and service-specific networks.
9. Validate Caddy with the exact image/module set; replace unsupported directives or build a provenance-pinned image containing required modules.
10. Add authenticated access for metrics/dashboard planes and an ingress/egress matrix.
11. Add backup/restore and secret-rotation effects to rollout and rollback instructions.

#### Edge and failure cases
- Missing secret, expired certificate, failed health check, database migration failure, Caddy reload failure, image pull failure, read-only filesystem violation, and rollback to an older schema.

#### Security, safety, and privacy controls
- Fail startup on missing production secrets; no credentials in Compose interpolation defaults or logs; isolate monitoring data; use least-privilege service identities.

#### Observability and debugging
- Emit readiness reasons without secrets, container health transitions, proxy upstream errors, certificate-expiry metrics, and blocked direct-access checks.

#### Tests
- Clean Docker build, image SBOM/scan, non-root/read-only assertions, Compose config validation, Caddy validation, startup smoke, direct-port negative tests, TLS tests, and secret-missing negative tests.

#### Acceptance criteria
- [ ] A clean pinned build produces a runnable image whose declared health check succeeds.
- [ ] Only the intended TLS ingress is reachable from outside the Compose network in production profile.
- [ ] Missing production credentials or TLS material causes a clear non-zero startup failure.
- [ ] Prometheus administration and Grafana administration are not anonymously reachable through direct host ports.

#### Risks and mitigations
- **Risk:** Network hardening disrupts existing local monitoring.
  **Mitigation:** Provide a separate loopback-only development override and migration commands without weakening the production profile.

### [ ] P1-1 — Make report and chart layouts deterministic, symmetric, responsive, and viewport-safe

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `enhanced.css::main`, `.report-grid`, `.report-card`; `enhanced.js::initializeChartWindow`; supplied Endpoints and Models screenshots; finding `WILSON-EVAL3NGINE-SEC-0005`
- **Purpose:** Satisfy the explicit visual contract: at least two reports in one row on supported desktop widths, equal card geometry, aligned outer edges, stable chart rendering, and no off-screen modal state.
- **Affected surfaces:** `gui/static/enhanced.css`, `enhanced.js`, `index.html`, browser fixtures, screenshot baselines, accessibility behavior
- **Constraints:** Preserve one-column mobile layout, keyboard access, readable minimum widths, PDF usability, and browser zoom behavior.

#### Implementation steps
1. Replace centered fixed maximum-width behavior with a fluid container using consistent viewport gutters and a documented optional ultra-wide cap.
2. Set the desktop report grid to exactly two equal `minmax(0, 1fr)` columns; collapse to one at the measured breakpoint where two cards would violate minimum content width.
3. Normalize card header, metadata, preview, and action regions so cards in the same row have equal height and aligned controls.
4. Use aspect-ratio/min-height rules for PDF previews and explicit overflow behavior for long file/model names.
5. Keep chart galleries responsive while preserving a stable ordering and equal image frames.
6. Clamp chart drag and resize operations to the visual viewport, account for browser resize/zoom, and provide a “reset window” action.
7. Add focus trapping, escape handling, visible focus, accessible labels, and reduced-motion behavior.
8. Capture approved screenshots at 1280×720, 1440×900, 1920×1080, and 2560×1440 plus a mobile breakpoint.

#### Edge and failure cases
- Odd report count, one report, long SHA/name, unavailable PDF plugin, 200% zoom, narrow landscape, mobile browser chrome, scrollbars, fullscreen toggle, and window resize while modal is open.

#### Security, safety, and privacy controls
- Continue escaping all labels/attributes; never insert report/model output as HTML; sandbox PDF previews if browser behavior or report trust requires it.

#### Observability and debugging
- Add deterministic browser-test snapshots and console-error collection; record layout viewport and device-pixel ratio with failures.

#### Tests
- Playwright or equivalent DOM geometry assertions, accessibility scan, keyboard navigation, screenshot comparisons, and no-horizontal-overflow checks at all target widths.

#### Acceptance criteria
- [ ] At every supported desktop viewport, two report cards occupy each complete row with equal widths, equal row heights, aligned outer edges, and no horizontal overflow.
- [ ] Below the documented breakpoint, reports render as one readable column.
- [ ] The chart window cannot be dragged or resized beyond the visible viewport and recovers after viewport resize.
- [ ] Screenshot and accessibility baselines pass with no unapproved differences.

#### Risks and mitigations
- **Risk:** Exact two-column layout becomes cramped on mid-size screens.
  **Mitigation:** Derive the breakpoint from measured card minimum width and test browser zoom before finalizing it.

### [ ] P1-2 — Guarantee chart/report provenance, idempotency, and evidence-derived rendering

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-1, P1-1
- **Status:** Not started
- **Evidence:** `runtime.py` chart adapters, `application.py` job/telemetry/report routes, legacy chart helpers, report subprocess; current chart metadata
- **Purpose:** Ensure every chart and report is generated from recorded evaluation data, belongs to the correct run, and can be reproduced or safely rejected.
- **Affected surfaces:** evaluation sidecars, telemetry schema, chart generators, artifact discovery, report index/export, hashes, deletion/retry behavior, frontend metadata
- **Constraints:** No synthetic fallback through the operator GUI; no cross-run artifact capture; preserve historical artifacts through a migration.

#### Implementation steps
1. Define a versioned run-artifact manifest with run/job/batch IDs, models, prompts, provider endpoint reference, evaluation sidecars, metric version, chart version, report version, hashes, and timestamps.
2. Replace directory-wide “all PDFs” snapshots with before/after or manifest-returned artifact membership scoped to one invocation.
3. Require evaluation-sidecar provenance before chart generation and validate sidecar schema, run binding, model set, and content hash.
4. Make chart generation idempotent and atomic: generate into a private temp directory, validate outputs, then replace the run directory.
5. Make deletion update the manifest and filesystem transactionally or record a recoverable partial-failure state.
6. Add chart/report status and error objects so the UI distinguishes unavailable evidence, generation failure, deliberate deletion, and unsupported legacy artifacts.
7. Store exact metric definitions and source counts used by every chart; never label synthetic or incomplete values as measured results.
8. Add deterministic ordering and stable filename conventions independent of filesystem enumeration.

#### Edge and failure cases
- Partial report success, process crash after one artifact, stale sidecar, duplicate run ID, retry, deleted chart, odd encoding, corrupted PDF/PNG, concurrent refresh, and old unmanifested artifacts.

#### Security, safety, and privacy controls
- Validate paths and types, isolate renderers, bound input size/count, prevent external fetches in PDF generation, and redact secrets from manifests and error text.

#### Observability and debugging
- Record artifact state transitions, input/output hashes, generator version, duration, failure class, reuse decision, and reconciliation results.

#### Tests
- Golden fixtures for metrics/charts, property tests for manifest membership, concurrent generation/deletion tests, corrupt-sidecar tests, retry/idempotency tests, and export integrity verification.

#### Acceptance criteria
- [ ] Every new report/chart maps to exactly one manifest and one evidence run with verified hashes.
- [ ] A run without valid evaluation data returns a clear non-success response and produces no synthetic chart.
- [ ] Repeating generation with unchanged inputs either reuses verified artifacts or creates byte/semantic-equivalent versioned outputs.
- [ ] Concurrent generate/delete/refresh operations do not resurrect deliberately deleted artifacts or mix runs.

#### Risks and mitigations
- **Risk:** Historical artifacts cannot be fully attributed.
  **Mitigation:** Mark them `legacy-unverified`, keep them read-only, and exclude them from certified comparisons until reconstructed.

### [ ] P1-3 — Turn CI, dependency, provenance, and release checks into real gates

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `.github/workflows/ci.yml`; `Makefile`; `pyproject.toml`; finding `WILSON-EVAL3NGINE-SEC-0006`
- **Purpose:** Make workflow names match enforced behavior and prevent unverified tools, dependencies, or artifacts from entering the release path.
- **Affected surfaces:** CI workflows, Makefile, lockfiles, action references, scanner acquisition, SBOM, build, signing, artifacts, branch rules, docs
- **Constraints:** Keep workflows reproducible, least-privilege, fork-safe, and usable without production provider credentials.

#### Implementation steps
1. Add explicit Make targets for format, lint, type, unit, integration, browser, security, container, docs, and plan/report validation.
2. Remove `|| true` from mandatory checks and document any advisory checks separately.
3. Trigger required validation for `dev-mid` and all pull requests into the protected base; add concurrency cancellation without dropping required results.
4. Verify every action SHA against the intended release and pin reusable workflows and external tools by digest/checksum/signature.
5. Replace unconstrained editable installs with a hashed lock or reviewed constraints artifact.
6. Perform two isolated builds from the same source and compare normalized wheel/sdist contents and hashes.
7. Generate a standards-compliant SBOM from resolved dependencies, not only `pyproject.toml`.
8. Produce cryptographic keyless signatures/attestations with verifiable OIDC claims, and verify them before promotion.
9. Minimize workflow permissions and remove OIDC write permission from jobs that do not actually sign or federate.
10. Add secret scanning, dependency audit, SAST, workflow policy, container/IaC scans, license checks, and artifact-retention rules.
11. Add CI evidence to the master report and draft PR without overstating unexecuted deployment checks.

#### Edge and failure cases
- Fork PRs, scheduled run on a non-main ref, compromised download, unavailable transparency log, nondeterministic timestamp metadata, yanked dependency, and action revocation.

#### Security, safety, and privacy controls
- No secrets in fork jobs; verify downloaded scanners; isolate build artifacts; bind signing claims to repository/ref/workflow; use least-privilege permissions.

#### Observability and debugging
- Publish machine-readable gate results, tool versions, checksums, attestation verification, false-positive dispositions, and reproducibility diffs.

#### Tests
- Workflow lint, local action simulation where practical, intentionally failing lint fixture, tampered scanner/artifact test, two-build comparison, and signature verification negative test.

#### Acceptance criteria
- [ ] Mandatory lint, test, coverage, security, and documentation failures cause a non-zero required check.
- [ ] CI runs for the hardening branch/PR and no required job depends on live provider credentials.
- [ ] Reproducibility compares two clean builds, and release artifacts have a verifiable signature/attestation plus resolved-dependency SBOM.
- [ ] All external actions/tools are pinned and integrity-verified.

#### Risks and mitigations
- **Risk:** Enforcing dormant checks reveals a large pre-existing failure backlog.
  **Mitigation:** Baseline findings explicitly, fix P0/P1 failures first, and use time-bounded reviewed waivers rather than suppression.

### [ ] P1-4 — Close API exceptional-condition gaps in request limits, CSRF, and rate-limit behavior

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-1
- **Status:** Not started
- **Evidence:** `api/middleware.py`, `security/csrf.py`, existing auth/rate-limit modules; finding `WILSON-EVAL3NGINE-SEC-0009`
- **Purpose:** Enforce body and browser request invariants independently of client-declared headers and make degraded security-service behavior explicit.
- **Affected surfaces:** body-size middleware, request stream handling, CSRF token model, CORS preflight, rate-limit fallback, authentication mode configuration, tests
- **Constraints:** Preserve API clients using bearer authentication; do not require CSRF for non-browser bearer-only requests unless cookies or ambient authority are involved.

#### Implementation steps
1. Wrap the ASGI receive stream and count actual bytes, terminating over-limit requests before framework parsing regardless of `Content-Length` or transfer encoding.
2. Reject malformed, negative, conflicting, or excessive `Content-Length` and document proxy/backend body-limit alignment.
3. Bind CSRF tokens to the authenticated session/user and purpose, add nonce/single-use or bounded replay semantics for high-risk actions, and fail production startup when the CSRF secret is missing in cookie-auth mode.
4. Ensure CORS preflight validates requested method/headers and returns denial rather than a generic successful response without policy headers.
5. Decide and document rate-limit dependency failure posture per route; high-cost or authentication-sensitive operations should not silently become unlimited.
6. Add stable public errors and protected diagnostics for stream abort, limiter outage, audit outage, and CSRF failure.
7. Verify middleware ordering so limits and identity controls execute before expensive parsing and side effects.

#### Edge and failure cases
- Chunked body, missing length, duplicate length, slow upload, disconnect, compressed payload, HTTP/2 streaming, limiter outage, clock skew, token reuse, and proxy normalization mismatch.

#### Security, safety, and privacy controls
- Bound time and memory; do not echo tokens/body data; use constant-time comparisons; ensure denial logs cannot be injected.

#### Observability and debugging
- Counters for actual bytes rejected, CSRF reason class, limiter backend state, fail-closed decisions, and middleware latency with bounded labels.

#### Tests
- Raw ASGI/HTTP streaming tests, chunked over-limit tests, duplicate-header tests, browser CSRF tests, limiter outage fault injection, and middleware-order assertions.

#### Acceptance criteria
- [ ] A streamed request exceeding the configured limit is rejected before endpoint parsing even without `Content-Length`.
- [ ] Cookie-authenticated state changes require a session-bound valid CSRF token; bearer-only clients follow the documented non-cookie policy.
- [ ] Rate-limit backend failure has deterministic route-specific behavior and an observable degraded state.
- [ ] Error responses expose no request body, credentials, stack trace, or internal query/path details.

#### Risks and mitigations
- **Risk:** Stream wrapping conflicts with framework middleware.
  **Mitigation:** Use ASGI-level tests across supported Uvicorn/Starlette versions and retain a feature-gated rollback.

### [ ] P1-5 — Rewrite README and operations documentation around verified behavior, screenshots, and three-sentence diagrams

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-2, P0-3, P0-4, P0-5, P1-1, P1-2
- **Status:** Not started
- **Evidence:** current `README.md`; `docs/operations/api-key-local-model-setup.md`; supplied `image.png` and `Screenshot 2026-08-01 014855.png`; finding `WILSON-EVAL3NGINE-SEC-0010`
- **Purpose:** Give operators one accurate, safe, reproducible path from clone to loopback GUI, optional remote deployment, provider setup, evaluation, charts, reports, exports, troubleshooting, and security operations.
- **Affected surfaces:** README, GUI/evidence guide, API-key/local-model guide, security docs, `docs/images/gui/`, Mermaid/source diagrams, examples, generated documentation checks
- **Constraints:** Use only sanitized examples; preserve supplied screenshots without leaking credentials; no volatile model counts or internal IPs presented as universal facts.

#### Implementation steps
1. Copy the supplied Endpoints and Models screenshots into a stable `docs/images/gui/` path with descriptive filenames, alt text, captions, and source date.
2. Add a visual tour covering the five workflow tabs, explaining what each control changes and what evidence it produces.
3. Generate source-controlled diagrams for system context/trust boundaries, credential lifecycle, evaluation-to-artifact flow, and local-versus-remote deployment.
4. Place exactly three complete explanatory sentences directly below each diagram, covering what it shows, why it is useful, and when an operator should consult it.
5. Add a five-minute loopback quickstart using `we3-gui-start --host 127.0.0.1`.
6. Add an explicit remote guide requiring TLS plus authentication and showing safe bind-address alteration without weakening defaults.
7. Replace plaintext environment-variable and ad-hoc `/tmp` token examples with secret-store references and safe login/token refresh procedures.
8. Remove environment-specific IPs/usernames and broken tilde-expansion commands; use clearly marked placeholders only in prose and complete executable local examples where values are repository-defined.
9. Document key rotation/revocation, audit behavior, backup/restore, endpoint policy profiles, chart/report provenance, supported browser widths, and rollback.
10. Add copy-paste samples for endpoint registration, model discovery, one-model evaluation, batch evaluation, chart generation, report export, API health, and troubleshooting.
11. Generate version/test counts from source or remove them; add a docs drift check that verifies commands, routes, filenames, images, and example schemas.
12. Link the master security report and state residual limitations without “fully secure” language.

#### Edge and failure cases
- Missing screenshot asset, changed route/CLI flag, offline provider, Windows/macOS path differences, local IPv6, no PDF browser plugin, and optional production dependencies.

#### Security, safety, and privacy controls
- Strip metadata from screenshots if necessary; never include tokens, local usernames, internal addresses, raw harmful prompts, or live provider responses; render diagrams and Markdown inertly.

#### Observability and debugging
- Documentation CI reports broken links, missing images, stale command output, schema drift, and screenshots outside approved dimensions.

#### Tests
- Execute documented local commands in a clean environment; validate Mermaid syntax; check links/images/anchors; run doctest-style API/CLI snippets with mocks; scan docs/images for secrets and metadata.

#### Acceptance criteria
- [ ] README contains the two supplied screenshots, four generated diagrams, all requested setup/usage/security samples, and exactly three explanatory sentences beneath each diagram.
- [ ] Loopback quickstart and remote authenticated deployment commands are verified against the implemented entry points.
- [ ] Documentation contains no real secret, internal username/IP, obsolete entry point, or unsupported production-security claim.
- [ ] Documentation checks pass and every screenshot/diagram has meaningful alt text and a stable source path.

#### Risks and mitigations
- **Risk:** Documentation becomes stale after refactors.
  **Mitigation:** Generate volatile facts, test executable snippets, and make documentation drift a required CI gate.

### [ ] P1-6 — Add end-to-end security games and regression coverage for complete attack paths

- **Priority:** P1
- **Owner:** @unassigned
- **Dependencies:** P0-2, P0-3, P0-4, P0-5, P1-2, P1-3, P1-4
- **Status:** Not started
- **Evidence:** findings `WILSON-EVAL3NGINE-SEC-0001` through `0010`; current test directories; required web/API assurance artifacts
- **Purpose:** Prove negative behavior and prevent individual fixes from leaving equivalent alternate paths.
- **Affected surfaces:** unit/integration/browser/security tests, fixtures, Compose test profile, master report game cards, CI
- **Constraints:** Tests must be isolated, non-destructive, deterministic, and free of real credentials or uncontrolled provider calls.

#### Implementation steps
1. Build an authorization matrix fixture covering REST and WebSocket operations, objects, roles, and profiles.
2. Add a remote-GUI game: anonymous network client attempts endpoint mutation, job execution, telemetry read, report deletion, and WebSocket actions.
3. Add a secret-lifecycle game: migration, use, child handoff, rotation, revocation, cancellation, vault outage, and log/artifact scanning.
4. Add an SSRF game: redirect, DNS rebind simulation, mixed address answers, metadata ranges, loopback/private profile positives, and credential-forwarding checks.
5. Add a deployment-bypass game: direct API/Prometheus/Grafana host ports and missing-secret startup.
6. Add chart/report games: cross-run contamination, corrupt sidecar, concurrent deletion/generation, untrusted metadata rendering, and viewport layout.
7. Add CI games: lint failure, tampered scanner, nondeterministic build fixture, invalid signature, and untrusted pull-request metadata.
8. Add body-size/CSRF/rate-limit failure games and restore/restart reconciliation.
9. Map every game to findings, expectations, commands, environment, result, false positives, and residual risk in the master report.

#### Edge and failure cases
- Test timeouts, unavailable container runtime, platform-specific browser rendering, nondeterministic fonts, and intentionally blocked external services.

#### Security, safety, and privacy controls
- Use mocks/sink servers and reserved test networks; never target real metadata endpoints or third-party providers; sanitize retained fixtures.

#### Observability and debugging
- Preserve machine-readable results, screenshots only on failure, captured safe HTTP transcripts, and exact environment/tool versions.

#### Tests
- Run the complete game suite twice from clean state; run mutation/fault injections where practical; verify all negative oracles fail before the fix and pass afterward.

#### Acceptance criteria
- [ ] Every confirmed finding has at least one regression that failed against the vulnerable behavior and passes against the fix.
- [ ] Compound paths are tested end to end, not only as isolated helpers.
- [ ] Tests use no real token, private address, or production service and produce machine-readable failure status.
- [ ] Blocked tests have exact prerequisites, owner, residual risk, and no false “passed” claim.

#### Risks and mitigations
- **Risk:** Browser/container tests are flaky.
  **Mitigation:** Pin images/fonts/toolchains, use deterministic fixtures, separate retry diagnostics from pass criteria, and quarantine only with an owned expiry.

### [ ] P2-1 — Make security audit and operational telemetry durable, bounded, and actionable

- **Priority:** P2
- **Owner:** @unassigned
- **Dependencies:** P0-2, P0-3, P0-4
- **Status:** Not started
- **Evidence:** local audit append in `api_key_vault.py`; GUI/application logs; API audit modules; finding `WILSON-EVAL3NGINE-SEC-0003`
- **Purpose:** Ensure security-relevant actions remain attributable during failure without leaking credentials or allowing log/metric abuse.
- **Affected surfaces:** GUI audit events, API audit ledger, log configuration, metrics, retention/rotation, exports, alert rules, runbooks
- **Constraints:** No raw prompt/output or credential by default; bounded metric labels; explicit behavior when the audit sink is unavailable.

#### Implementation steps
1. Define one versioned security-event schema with actor, tenant/project, object, action, policy decision, outcome, reason class, correlation ID, and timestamp.
2. Route high-risk GUI events into a durable append-only or tamper-evident sink rather than a best-effort local text file alone.
3. Sanitize untrusted fields, bound lengths/cardinality, and separate protected diagnostics from operator-visible errors.
4. Add alerts for repeated auth denial, secret lookup failure, blocked endpoint destinations, destructive action bursts, audit degradation, and direct-port access attempts.
5. Define rotation, retention, access control, export, clock, and incident-preservation behavior.
6. Add a post-fix monitoring section to the master report and operations guide.

#### Edge and failure cases
- Audit sink outage, disk full, clock skew, log rotation, malformed Unicode, newline injection, high-cardinality endpoint IDs, and backup restore.

#### Security, safety, and privacy controls
- Least-privilege read access, integrity checks, redaction before sink, and no secret-bearing labels or messages.

#### Observability and debugging
- Audit health metric, dropped/rejected event counters, sink latency, integrity checkpoint status, and runbook links.

#### Tests
- Log-injection tests, redaction corpus, audit-outage fault injection, retention/rotation tests, and cross-project export authorization.

#### Acceptance criteria
- [ ] Every high-risk action has a durable actor/object/decision/outcome event or fails according to the documented policy.
- [ ] Credential, token, private key, raw Authorization header, and secret-bearing URL fixtures are redacted before all sinks.
- [ ] Metrics have bounded labels and alert tests demonstrate each material attack path.
- [ ] Audit restore/export preserves integrity and project/tenant filtering.

#### Risks and mitigations
- **Risk:** Fail-closed audit creates availability impact.
  **Mitigation:** Apply fail-closed only to defined high-risk operations and use a durable bounded local queue with operator-visible degraded state.

### [ ] P2-2 — Bound local state growth and profile chart/report performance

- **Priority:** P2
- **Owner:** @unassigned
- **Dependencies:** P1-2, P1-3
- **Status:** Not started
- **Evidence:** JSON state files, synchronous legacy chart helpers, report/telemetry lists, GUI refresh patterns
- **Purpose:** Keep the single-user/local mode responsive and predictable as jobs, telemetry, charts, and reports accumulate.
- **Affected surfaces:** JSON repositories, retention/reconciliation, chart workers, report indexing, API pagination, frontend refresh, performance docs
- **Constraints:** Preserve evidence integrity and deletion semantics; do not optimize by dropping unreported data.

#### Implementation steps
1. Measure current state-file, artifact, chart, and report performance using sanitized generated fixtures at small, expected, and stress sizes.
2. Add pagination and bounded summaries to list APIs while preserving explicit export/download paths.
3. Move CPU-heavy chart generation off the event loop into a bounded worker with cancellation, timeout, and memory controls.
4. Add retention/archival policy and atomic compaction for local JSON state or migrate high-volume state to the existing persistence layer behind a compatibility interface.
5. Cache only immutable hash-addressed metadata and invalidate on manifest changes.
6. Add startup reconciliation budgets and a repair command for orphaned/corrupt state.
7. Document measured limits and operational cleanup.

#### Edge and failure cases
- Tens of thousands of runs, large prompts excluded from list responses, interrupted compaction, duplicate IDs, disk full, concurrent readers, and old schema versions.

#### Security, safety, and privacy controls
- Authorization before pagination/export, no prompt/secret content in summaries, resource quotas, and safe cancellation.

#### Observability and debugging
- State size, list latency, chart queue depth, generation duration/memory, compaction status, reconciliation counts, and retention actions.

#### Tests
- Performance benchmarks with thresholds, concurrent read/write tests, interrupted compaction recovery, pagination authorization, and worker cancellation/resource tests.

#### Acceptance criteria
- [ ] Defined expected-scale list and chart operations meet documented latency/memory thresholds on the reference environment.
- [ ] State growth has an enforceable retention/archive policy and safe recovery after interruption.
- [ ] CPU-heavy rendering cannot block health/auth/cancel requests beyond the agreed budget.
- [ ] Pagination and summaries do not leak prompts, secrets, or cross-project data.

#### Risks and mitigations
- **Risk:** State migration creates compatibility or data-loss risk.
  **Mitigation:** Version schemas, backup before migration, dry-run reconciliation, checksums, and reversible read compatibility.

### [ ] P2-3 — Reduce legacy GUI coupling after compatibility behavior is characterized

- **Priority:** P2
- **Owner:** @unassigned
- **Dependencies:** P0-1, P1-2, P1-6
- **Status:** Not started
- **Evidence:** `runtime.py` and `application.py` import selected behavior from the large `server.py` compatibility module
- **Purpose:** Remove ambiguous duplicate route/security implementations and make the active application boundary easier to review and test.
- **Affected surfaces:** `server.py`, `runtime.py`, `application.py`, provider/chart/report services, imports, tests, docs
- **Constraints:** No broad rewrite; extract only responsibilities whose duplication or legacy side effects are proven by characterization tests.

#### Implementation steps
1. Inventory every active import/call from `server.py` and classify it as pure helper, state access, network effect, subprocess effect, rendering, or dead code.
2. Add characterization tests around active helper contracts and side effects.
3. Extract provider networking, artifact manifests, chart generation, secret access, and validation into narrowly scoped modules with typed interfaces.
4. Remove duplicate inactive FastAPI app/routes or move them to a clearly marked compatibility module that cannot be started accidentally.
5. Update imports, tests, entry points, and documentation to one authoritative GUI application.
6. Delete dead code only after coverage and history review; retain migration shims with expiry where necessary.

#### Edge and failure cases
- Hidden script imports, module execution via `python -m`, circular imports, monkeypatched tests, stale docs, and third-party users importing internal helpers.

#### Security, safety, and privacy controls
- Preserve enforcement at authoritative boundaries; do not create a second unprotected route or secret path during extraction.

#### Observability and debugging
- Import/deprecation warnings in development, compatibility usage counters where appropriate, and call-graph documentation.

#### Tests
- Import smoke tests, route inventory tests, characterization tests, no-duplicate-route assertion, and direct-module-start negative test.

#### Acceptance criteria
- [ ] One documented GUI app/entry point owns all reachable routes and security middleware.
- [ ] Active legacy helper behavior is either extracted behind typed interfaces or explicitly retained with tests and an expiry rationale.
- [ ] Direct execution of the legacy server cannot expose an alternate unprotected control plane.
- [ ] All route, provider, chart, report, and job regression tests pass after extraction.

#### Risks and mitigations
- **Risk:** Hidden coupling causes subtle regressions.
  **Mitigation:** Characterize before extraction, use small commits, and preserve reversible adapters until end-to-end tests pass.

## Validation and Release Gates

Mandatory repository gates after implementation:

1. Exact inventory and changed-file adjacency review.
2. Formatter, lint, type, build, unit, integration, browser, contract, migration, and documentation checks.
3. Security games for GUI authorization, CSRF/Origin, secrets, SSRF, body limits, direct-port exposure, report/chart provenance, and CI tampering.
4. Secret, dependency, SAST, workflow, container, IaC, license, SBOM, provenance, and signature verification.
5. Two clean reproducibility builds.
6. Docker/Compose/Caddy validation and isolated startup smoke.
7. Screenshot geometry and accessibility at all target viewports.
8. Master-report structural validation and finding-to-commit/test traceability.
9. Full diff and Git history scan for credentials, internal topology, unsafe corpus content, and generated artifacts.
10. Remote branch and draft pull request existence verification.

All mandatory gates must exit zero with no unapproved skips. Blocked deployment/runtime checks must be labeled blocked with exact prerequisites and residual risk; they may not be described as passed.

## Rollback and Recovery

- Keep each security invariant in a coherent commit mapped to finding IDs.
- Preserve the previous endpoint-record format in read-only migration code for one documented release window.
- Version secret references and permit rollback to a previous active key version without restoring plaintext.
- Maintain separate local and production Compose profiles so production hardening is not undone to recover local convenience.
- Back up state/manifests before schema migration and verify restoration in isolation.
- Provide feature-gated rollback only where it does not reopen unauthenticated remote exposure or plaintext secret handling.
- On failed rollout, revoke newly issued access tokens, rotate exposed credentials, restore the last verified artifact/state snapshot, and rerun reconciliation.
- Never roll back by re-enabling weak default passwords, public monitoring ports, unsigned artifacts, or suppressed mandatory tests.

## Risks and Mitigations

- **Authentication compatibility:** Preserve loopback-only local mode and migrate remote users through explicit profiles.
- **Secret backend availability:** Add health/preflight checks, bounded retries, durable audit degradation, and versioned rollback.
- **Private gateway variability:** Use reviewed policy sets and diagnostics rather than global private-network access.
- **UI snapshot brittleness:** Assert geometry/accessibility and pin fonts/browser; use pixel snapshots as supporting evidence.
- **CI backlog:** Separate pre-existing failures from regressions, but do not suppress P0/P1 gates.
- **Artifact migration:** Mark unverifiable historical outputs as legacy and exclude them from certified comparisons.
- **Container/network disruption:** Provide loopback-only debug overrides and staged direct-port removal tests.
- **Legacy extraction:** Characterize every active call and keep changes small/reversible.
- **Documentation drift:** Execute examples and generate volatile counts/route inventories in CI.

## Completion Definition

The workstream is complete only when:

- the exact base/head and full file coverage are recorded;
- every confirmed finding is remediated, partially remediated with explicit residual risk, or formally deferred by maintainers;
- all active GUI/API routes have tested identity, authorization, input, failure, and audit behavior;
- remote GUI exposure cannot occur without an explicit authenticated secure profile;
- provider credentials use an approved secret backend and secret-safe child handoff;
- local/private model endpoints are governed by explicit destination policies;
- production images build and start from pinned inputs;
- production ingress cannot be bypassed through directly published internal ports;
- charts and reports are evidence-derived, manifest-bound, reproducible, and rendered in the required two-column symmetric layout;
- chart windows remain within the viewport at supported sizes/zoom;
- CI gates, reproducibility, SBOM, provenance, and signing are genuinely enforced;
- README and operational docs match current commands and include the supplied screenshots, generated diagrams, samples, and exactly three explanatory sentences per diagram;
- all mandatory validations pass or are precisely blocked without false claims;
- the master report is current and validated;
- the dedicated branch exists remotely;
- a draft pull request links the master report, changes, tests, rollout, rollback, and residual risk; and
- no merge or auto-merge has occurred.
