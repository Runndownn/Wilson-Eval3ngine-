# Ben Reaper's Security Partner — Master Security Assessment and Hardening Report

## 1. Document control

| Field | Value |
|---|---|
| Repository | `https://github.com/Runndownn/Wilson-Eval3ngine-` |
| Visibility | Public |
| Base branch | `main` |
| Base head | `193f25c48fede79a928cdd7cb3d4e32c5652e223` |
| Assessment branch | `security/hardening-20260731-wilson-eval3ngine` |
| Assessment date | 2026-07-31 (America/New_York) |
| Authorization | Owner-authorized repository assessment, modification, branch publication, and draft pull request |
| Completion state | `partial` |
| Runtime evidence | Not supplied; repository-only review in progress |
| Draft pull request | Not yet opened |

### Revision history

| Revision | Date | Summary |
|---|---|---|
| 0.1 | 2026-07-31 | Established repository authority, architecture baseline, initial confirmed findings, and remediation plan. |

## 2. Partner charter and bounded assurance statement

This assessment treats repository evidence as authoritative and uses external or challenge-derived material only to generate defensive hypotheses. The authorized scope includes the complete accessible repository, implementation changes, security tests, a dedicated branch, and a draft pull request. No production deployment, real provider account, live credential, or external target testing is authorized or claimed.

A repository change is not evidence that a deployed environment is fixed. Findings are confirmed only when the repository establishes a reachable path, a security boundary failure, and a material impact. Validation claims in this report identify commands actually run or explicitly state when execution was blocked.

## 3. Executive narrative

Wilson Eval3ngine is a Python evaluation platform with two materially different application boundaries. The primary API provides OIDC/dev authentication, project-scoped persistence, rate limiting, audit, evaluation execution, evidence production, and signed dossiers. A separate operator GUI manages provider endpoints and credentials, launches report-generation subprocesses, exposes job and telemetry state over REST and WebSocket, serves reports, and performs destructive administrative operations.

The highest-risk repository-proven boundary is the operator GUI. It intentionally has no built-in user authentication while providing credential management, subprocess execution, endpoint configuration, report deletion, job cancellation/retry, and telemetry access. The launcher warns when bound to a non-loopback address but still proceeds. That is a fail-open deployment control: one command-line option can turn local operator capability into a network-reachable administrative surface.

The second material boundary is provider URL handling. The newer GUI application validates scheme and some address classes, but configured hostnames are accepted after a point-in-time resolution check and later used by legacy HTTP helpers that can follow redirects. This leaves DNS rebinding and redirect-to-private-network risk insufficiently controlled. The repository contains a separate egress policy module, but the GUI HTTP path does not consistently enforce it at connection time.

The repository also declares strong supply-chain guarantees that the workflow does not currently prove. CI suppresses lint failures with `make lint || true`, downloads an executable archive using a mutable network fetch rather than a verified digest, and labels artifact signing as OIDC while only writing the source commit to a text file. The latest base commit has no attached workflow-run or combined-status evidence available through the connected GitHub account.

## 4. Scope, methodology, and limitations

Reviewed evidence includes repository metadata and permissions, the current `main` head, security policy, environment template, production and development container definitions, primary API authentication/middleware/operation paths, GUI application/runtime/launcher, provider adapters, egress controls, signing and dossier code, CI workflow, repository manifests/checksums, and related unit/integration test locations.

A complete local checkout could not be established in the available execution environment. Full-tree byte hashing, local repository-native test execution, dependency scanning, container scanning, and report-validator execution remain blocked. File coverage therefore remains incomplete and is represented as security debt rather than silently treated as complete.

## 5. Repository and system understanding

### Components

- **Primary API**: FastAPI service with dev/OIDC request context, project-scoped repositories, operation endpoints, middleware, audit, rate limiting, and health checks.
- **Evaluation service**: Loads experiment and dataset manifests, renders prompts, executes providers, grades outputs, computes metrics/gates, persists evidence, and generates signed dossiers.
- **Operator GUI**: FastAPI REST/WebSocket application for endpoints, models, prompts, jobs, reports, charts, telemetry, and report-generation subprocesses.
- **Provider boundary**: SDK, HTTP, Ollama, and local CLI adapters. Provider responses and model output are untrusted data.
- **Evidence and signing**: Local artifact storage, hash-linked audit records, Ed25519 dossier signatures, and optional trust-registry verification.
- **Supply chain**: Python package build, tests, scans, artifacts, SBOM-like output, container definitions, and GitHub Actions.

### Trust boundaries

```text
Browser/operator
  -> unauthenticated GUI REST/WebSocket
  -> endpoint credentials + local state
  -> report-generation subprocess
  -> local CLI/provider account or remote model endpoint
  -> generated PDF/JSON/chart/telemetry artifacts

API client
  -> API middleware + OIDC/dev context
  -> project authorization
  -> database/artifact store/worker/provider
  -> signed dossier and reports

Contributor/PR
  -> GitHub Actions runner
  -> package install/build/test/scans
  -> uploaded artifacts and claimed signing/provenance
```

## 6. Architecture profile and control expectations

| Expectation ID | Pack | Invariant | Enforcement point | Status | Finding/debt |
|---|---|---|---|---|---|
| WILSON-EVAL3NGINE-EXP-0001 | Web/API | Operator side effects require authenticated, authorized context. | GUI request/WebSocket boundary | Violated | SEC-0001 |
| WILSON-EVAL3NGINE-EXP-0002 | Network/LLM | Every provider connection and redirect is validated against current resolved addresses and egress policy. | Outbound connection boundary | Violated | SEC-0002 |
| WILSON-EVAL3NGINE-EXP-0003 | Secrets | Provider keys are not logged, exposed to unnecessary processes, or persisted in plaintext. | GUI vault/subprocess boundary | Partially satisfied | SEC-0003 |
| WILSON-EVAL3NGINE-EXP-0004 | Supply chain | Required quality gates fail closed and claimed signatures/provenance are cryptographically real. | CI workflow | Violated | SEC-0004 |
| WILSON-EVAL3NGINE-EXP-0005 | Integrity | Repository manifests and checksum inventories match the assessed tree. | Release/inventory process | Violated | DEBT-0001 |
| WILSON-EVAL3NGINE-EXP-0006 | Identity | OIDC verification fails closed during key refresh, rotation, revocation, and malformed-token conditions. | API authenticator | Partially reviewed | DEBT-0002 |

Required packs: web/browser, API/service, identity/authentication/authorization, data/state, queue/worker, LLM/provider/tool execution, CI/supply chain, container/IaC, network/transport, file/report, cryptography/secrets, observability/resilience, and privacy/data governance.

## 7. Asset and security-objective register

| Asset | Objective | Exposure | Recovery requirement |
|---|---|---|---|
| Provider API keys and local CLI identities | Confidentiality, least privilege, revocation | GUI state and report subprocess | Rotate/revoke and remove persisted copies |
| Model prompts/responses and evaluation evidence | Tenant isolation, confidentiality, integrity | API, GUI telemetry, artifacts, reports | Traceable deletion and tamper detection |
| Job/subprocess authority | Integrity, bounded execution, availability | GUI REST/WebSocket | Cancel, reap, audit, and prevent unauthorized launch |
| Signed dossier and release evidence | Authenticity, integrity, trust binding | Filesystem and consumers | Verify against approved trust registry |
| CI/release artifacts | Provenance, reproducibility, integrity | GitHub Actions and uploaded artifacts | Rebuild, revoke, and distinguish unsigned material |

## 8. Identity, privilege, and trust-boundary model

The primary API has an explicit identity model. The GUI does not. Any network client that can reach the GUI can enumerate endpoint metadata and models, create or delete endpoint configurations, trigger endpoint tests and model discovery, create/cancel/retry jobs, subscribe to job state, retrieve telemetry, download report bundles, delete reports, and indirectly invoke configured provider credentials or locally authenticated CLI tools. Origin checks on WebSocket messages do not authenticate a user and REST routes have no equivalent identity gate.

## 9. Data, state, and lifecycle model

GUI state is persisted to owner-readable JSON files using atomic replacement in the newer application boundary. API keys are encrypted for long-term endpoint storage, but are decrypted for use and copied into a temporary file for report subprocesses. Jobs and telemetry include prompts, stdout, stderr, provider/model metadata, artifact names, and operational status. Generated reports and charts are served from repository-adjacent directories.

The synchronous evaluation path generates a development signing key automatically when one is not provided. Verification with the embedded public key proves integrity but not organizational trust; the repository correctly exposes a separate trust-registry verification method. Production workflows must therefore reject integrity-only verification for release authority.

## 10. Attack-surface inventory

| Surface | Authentication | Side effects/data | Current concern |
|---|---|---|---|
| GUI REST `/api/*` | None | Credentials, endpoints, jobs, reports, telemetry | Administrative capability exposure |
| GUI WebSocket `/ws` | Origin comparison only | Job creation/cancellation/retry and operational reads | No actor identity or authorization |
| GUI launcher | Loopback default, remote warning only | Controls network reachability | Fail-open remote binding |
| Provider HTTP endpoints | Stored configuration + API key | Outbound authenticated calls | DNS/redirect/private-network policy gaps |
| CLI providers | Local process identity | Executes installed authenticated tools | GUI reachability can delegate local identity |
| Primary API | Dev headers or OIDC | Project data and operations | OIDC lifecycle review incomplete |
| Report serving/bundles | GUI reachability | PDF/JSON/chart evidence | No user authorization |
| CI workflow | GitHub event/runner | Build, tests, artifacts, package authority | Suppressed gates and non-cryptographic signing claim |

## 11. Web and API expectation assessment

The primary API contains meaningful controls: content-type and body-size middleware, CSRF handling, security headers, project-scoped authorization, and rate limiting. Several controls intentionally fail open under dependency loss, including the Redis rate limiter. That posture requires an explicit deployment decision and detection because an outage removes abuse protection.

The GUI has bounded Pydantic request models and output sanitization, but no authentication layer. WebSocket origin checking accepts missing Origin headers, which is reasonable for non-browser clients only when a separate authentication mechanism exists; none is present. Browser security headers reduce XSS and framing risk but do not compensate for missing identity and authorization.

## 12. Knowledge-system provenance and synthesis

The supplied security corpus was used only as a hypothesis source for prompt-injection, stored-output, SSRF, credential, authentication, and supply-chain review. It did not establish any target finding. No challenge flags, credentials, destructive payloads, or corpus excerpts are copied into the repository.

## 13. Defensive security game deck

| Game ID | Scenario | Protected invariant | Result | Finding/debt |
|---|---|---|---|---|
| WILSON-EVAL3NGINE-GAME-0001 | Bind GUI to a non-loopback address without an authenticated proxy. | Operator capability is not accidentally network exposed. | Failed by decisive code path | SEC-0001 |
| WILSON-EVAL3NGINE-GAME-0002 | Configure a hostname that resolves publicly during validation and privately during use, or redirects to private space. | Provider egress is validated at connection time. | Failed by design review | SEC-0002 |
| WILSON-EVAL3NGINE-GAME-0003 | Run lint with a violation. | CI blocks quality/security gate failure. | Failed by workflow logic (`|| true`) | SEC-0004 |
| WILSON-EVAL3NGINE-GAME-0004 | Verify a dossier signed by an untrusted self-generated key. | Release verification requires approved signer trust. | Partially protected; trust-aware verifier exists, generic CLI does not enforce it | DEBT-0003 |

## 14. Individual attack-path analysis

### WILSON-EVAL3NGINE-PATH-0001 — Network client to operator subprocess authority

```text
[REPO] Non-loopback GUI bind
  -> [REPO] no built-in authentication
  -> [REPO] REST/WebSocket job operation
  -> [REPO] report-generation subprocess
  -> [REPO] configured provider key or local CLI identity
  -> [INFERENCE] unauthorized spend, data disclosure, artifact deletion, or local-tool action
```

### WILSON-EVAL3NGINE-PATH-0002 — Configured provider URL to internal service

```text
[REPO] GUI endpoint creation
  -> [REPO] point-in-time hostname validation
  -> [REPO] later HTTP call / redirect handling
  -> [INFERENCE] changed DNS answer or redirect to private/internal address
  -> [REPO] Authorization header may be attached to provider request
  -> [INFERENCE] internal service probing or credential disclosure
```

## 15. Compound and cross-domain attack-path analysis

The most important compound path combines missing GUI authentication, provider configuration, local CLI execution, persisted provider credentials, report subprocesses, and telemetry. Each feature is expected for an operator tool; together they form an administrative control plane. Network exposure therefore changes the impact from local-user trust to remote administrative authority.

A second path combines user-configured endpoints, hostname resolution, redirect behavior, and bearer credentials. URL syntax validation alone is insufficient because the security decision can become stale before connection and can be bypassed by a redirect if every hop is not revalidated.

## 16. Findings register

| Finding | Severity | Confidence | Status | Component | Remediation | Residual risk |
|---|---|---|---|---|---|---|
| WILSON-EVAL3NGINE-SEC-0001 | High | High | Confirmed | Operator GUI | Enforce loopback-only launcher; design authenticated proxy/token boundary | Local reverse-proxy exposure remains operator-controlled |
| WILSON-EVAL3NGINE-SEC-0002 | High | Medium | Confirmed | GUI provider egress | Centralize connection-time destination and redirect validation | Runtime DNS/network policy still required |
| WILSON-EVAL3NGINE-SEC-0003 | Medium | High | Confirmed | API key subprocess handoff | Remove misleading claims/logging; prefer inherited pipe/FD or encrypted handoff | Child process necessarily receives usable credential |
| WILSON-EVAL3NGINE-SEC-0004 | High | High | Confirmed | GitHub Actions | Make gates fail closed; verify downloads; implement real signing/provenance | CI execution remains unverified until workflow runs |

## 17. Detailed findings

### WILSON-EVAL3NGINE-SEC-0001 — Unauthenticated operator GUI can be bound to a network interface

**Status:** confirmed. **Severity:** High. **Confidence:** High.

The GUI launcher documents that the application has no built-in authentication. When the host is not loopback it logs a warning and still starts. The served application exposes state-changing endpoint, model, job, report, and WebSocket actions. The starting attacker capability is network reachability to the configured host/port. No credential or session is required. The authority transition occurs when an unauthenticated request is accepted as an operator action and reaches endpoint storage, report deletion, job control, or subprocess execution.

The selected first remediation invariant is: **the repository-provided GUI launcher must not bind the unauthenticated operator application to a non-loopback address.** The launcher is the authoritative repository-controlled network exposure point. This does not claim to prevent an operator from deliberately placing loopback behind an external reverse proxy; production documentation and deployment controls must require authenticated TLS termination for that separate topology.

### WILSON-EVAL3NGINE-SEC-0002 — Provider endpoint validation is not bound to each connection and redirect

**Status:** confirmed. **Severity:** High. **Confidence:** Medium because exploitability depends on deployment DNS and network reachability.

The GUI accepts configured HTTP(S) endpoints and performs hostname/address checks during normalization. Later requests are made by legacy HTTP helpers, including a generic path that follows redirects. A hostname can change resolution after validation, and redirects can change the destination. The repository has a separate egress-policy module, but the GUI connection path does not consistently use it. Authorization headers are constructed from stored API keys for these requests.

The required invariant is: **every resolved address for the initial request and every redirect hop must be checked immediately before connection; private, loopback, link-local, multicast, unspecified, and metadata targets must be rejected unless an explicit local-provider policy applies.** Network-layer egress policy remains required because application validation cannot fully eliminate DNS TOCTOU.

### WILSON-EVAL3NGINE-SEC-0003 — API-key subprocess handoff uses plaintext temporary files and misleading security telemetry

**Status:** confirmed. **Severity:** Medium. **Confidence:** High.

Long-term endpoint storage is encrypted, but report invocation calls `store_api_key_temp_file`, which writes plaintext to an owner-only temporary file. The process then logs that it prepared “encrypted endpoint credentials,” while also emitting a masked prefix/suffix of the key. The file permission is a useful control, but it is not encryption, and masking still discloses stable key fragments.

The invariant is: **telemetry and documentation must accurately describe key handling and reveal no stable key material; plaintext temporary-file handoff should be replaced with a narrower process channel where compatible.** Until the child interface is redesigned, the temporary file must remain owner-only, short-lived, and reliably deleted.

### WILSON-EVAL3NGINE-SEC-0004 — CI security and quality claims fail open or are not cryptographically implemented

**Status:** confirmed. **Severity:** High. **Confidence:** High.

The CI test job runs `make lint || true`, suppressing the linter’s exit status. The workflow downloads a Trivy archive through `wget | tar` without verifying a digest or signature. The “Sign artifacts with OIDC identity” step does not obtain a signing identity or create a signature; it writes the source commit to `artifact_digest.txt`. These behaviors contradict the workflow’s deterministic and signed-artifact claims.

The invariant is: **required checks must fail closed, downloaded executables must be integrity verified, and output must not be labeled signed unless a verifiable signature and identity binding are produced.** A documentation-only claim is not provenance.

## 18. Rejected hypotheses and false positives

- The signed dossier HTML path escapes model and gate identifiers and intentionally excludes raw prompts/responses. No repository-proven XSS finding was confirmed in that renderer.
- CLI provider subprocess calls use argument arrays rather than `shell=True`; arbitrary shell metacharacters in prompts are therefore not directly interpreted by a shell in the reviewed path.
- The main API has explicit project authorization checks on reviewed operation routes; no confirmed cross-project object authorization bypass was established from the available evidence.

## 19. Remediation implementation narrative

Revision 0.1 is report-first and contains no implementation changes. Planned coherent change sets are:

1. Enforce loopback-only GUI binding and add negative tests.
2. Harden GUI destination validation and remove credential-fragment logging.
3. Make CI quality gates fail closed and remove unsupported signing claims unless real provenance is configured.
4. Add or repair security tests and update this report with exact validation evidence.

## 20. Validation and assurance

### Completed

- Confirmed repository identity, visibility, default branch, current head, and administrative write permission through the connected GitHub application.
- Confirmed the dedicated security branch was created from exact base head `193f25c48fede79a928cdd7cb3d4e32c5652e223`.
- Checked the base commit for connected GitHub workflow runs and combined status; no run/status evidence was returned.
- Performed static source review of the components and paths described above.

### Blocked/not run

- Local formatter, linter, type checker, unit/integration/E2E tests.
- Dependency, secret, SAST, IaC, container, and SBOM validation.
- Full-tree inventory and exact duplicate hashing.
- Runtime HTTP/WebSocket tests and controlled provider egress tests.
- Master-report validator script.

No blocked command is represented as passing.

## 21. Change impact, rollout, and rollback

Loopback enforcement is intentionally behavior-changing for operators who currently bind the unauthenticated GUI to `0.0.0.0` or another network address. Those deployments must move the GUI behind an authenticated TLS reverse proxy that connects to loopback, or adopt a future built-in authentication mode. Rollback would restore accidental network exposure and must therefore be treated as a security-significant action.

Egress hardening may reject endpoints that previously resolved to private networks. Local Ollama or explicitly approved private gateways need a narrow, named policy rather than a broad bypass. CI changes may initially expose existing lint or workflow failures that were previously hidden.

## 22. Detection, response, and operational hardening

- Alert on GUI processes bound to non-loopback interfaces.
- Record endpoint creation/deletion, job launch/cancel/retry, report deletion, and credential access with an authenticated actor once identity is implemented.
- Alert on provider destination changes, redirects, blocked address classes, DNS answer changes, and repeated endpoint-test failures.
- Rotate provider keys if a GUI instance was exposed beyond loopback without authenticated proxy protection.
- Treat CI artifacts produced by the current “signing” step as unsigned until verifiable provenance is added.

## 23. Residual risk and accepted assumptions

No risk is accepted on behalf of maintainers. Runtime topology, reverse-proxy authentication, DNS, firewall/egress rules, secret-store configuration, Redis availability, PostgreSQL RLS deployment, and provider account scopes are unverified. The repository security policy identifies the project as a development/internal-testing foundation and prohibits production credentials and real harmful or personal data; that limitation materially reduces intended exposure but does not remove the code-level risks.

## 24. Security debt and maturity ledger

| Debt ID | Missing assurance/control | Reason not a confirmed finding | Recommended action |
|---|---|---|---|
| WILSON-EVAL3NGINE-DEBT-0001 | Complete authoritative file inventory and reproducible checksums | Current connector cannot enumerate and hash every byte locally | Generate inventory from a clean checkout and replace stale manifest/checksum data |
| WILSON-EVAL3NGINE-DEBT-0002 | Full OIDC key refresh/revocation/failure validation | Authenticator lifecycle was not fully executed or fault-tested | Add stale-key, refresh failure, revoked key, duplicate header, and clock-skew tests |
| WILSON-EVAL3NGINE-DEBT-0003 | Release verification requires trust registry | Generic dossier verifier intentionally proves integrity only | Add a production verification command that requires approved signer trust |
| WILSON-EVAL3NGINE-DEBT-0004 | Runtime GUI authentication architecture | Loopback enforcement controls exposure but not actor identity | Implement authenticated operator sessions or a formally verified proxy contract |

## 25. Prioritized future roadmap

1. Close SEC-0001 and SEC-0004 because they govern administrative reachability and build/release trust.
2. Centralize provider egress validation and add redirect/DNS/private-range regression tests for SEC-0002.
3. Redesign credential handoff for SEC-0003 and remove all stable key-fragment logging.
4. Complete OIDC lifecycle, tenant-authorization, rate-limit failure, audit failure, restore, and dossier trust tests.
5. Produce a complete inventory, regenerate checksums, and reconcile documentation with implementation.

## 26. Continuous assurance and reassessment triggers

Reassess after any GUI remote-access feature, identity/session change, provider adapter, endpoint policy, subprocess interface, CI workflow, signing/provenance mechanism, dependency advisory, container topology, restore event, or security incident. Recurring controls should include dependency and secret scans, workflow-policy checks, route inventory, authz matrix tests, SSRF/egress tests, and signed-artifact verification.

## 27. Coverage ledger

Current coverage is partial. Reviewed classes include primary API security boundaries, GUI application/runtime/launcher, providers, egress, signing/dossier, CI, containers, security policy, environment template, and repository integrity declarations. A numeric total-file ledger is blocked until a complete tree inventory can be produced. Unreviewed count is therefore unknown and is not represented as zero.

## 28. Traceability matrix

| Item | Evidence | Change | Test | Commit | PR | Status |
|---|---|---|---|---|---|---|
| SEC-0001 | GUI launcher and GUI route inventory | Planned | Planned negative bind tests | Pending | Pending | Confirmed |
| SEC-0002 | GUI URL normalization and legacy HTTP requests | Planned | Planned DNS/redirect/address tests | Pending | Pending | Confirmed |
| SEC-0003 | GUI vault and report invocation | Planned | Planned key-handoff/redaction tests | Pending | Pending | Confirmed |
| SEC-0004 | `.github/workflows/ci.yml` | Planned | Workflow syntax/policy and actual CI run | Pending | Pending | Confirmed |
| DEBT-0001 | Checksums/manifest drift and incomplete tree access | None | Full inventory blocked | N/A | Pending | Open |

## 29. Portfolio and cross-repository dependencies

No second repository was authorized or supplied. External provider services, identity providers, Redis, PostgreSQL, object storage, reverse proxies, and GitHub Actions are runtime/deployment dependencies rather than assessed repositories.

## 30. Knowledge delta

Reusable defensive lessons: operator GUIs that combine secrets, local identities, subprocesses, and artifact deletion are administrative control planes even when branded as local tools; URL validation must be bound to connection-time resolution and every redirect; provenance labels must be backed by cryptographic evidence; fail-open quality gates create documentation/implementation drift.

No target-specific fact is promoted into a shared corpus automatically.

## 31. Appendices

### Evidence-class legend

- `[REPO]`: direct repository evidence.
- `[RUNTIME]`: safely collected runtime evidence.
- `[HISTORY]`: commit, issue, PR, or release evidence.
- `[CORPUS-*]`: knowledge used only as hypothesis input.
- `[STANDARD]`: current official standard/vendor guidance.
- `[INFERENCE]`: reasoned conclusion.
- `[BLOCKED]`: evidence unavailable or unsafe to collect.

### Current blockers

- No complete local checkout/test environment.
- No supplied deployment/runtime evidence.
- No connected CI run/status for the assessed base head.
- No complete byte-level tree inventory.
