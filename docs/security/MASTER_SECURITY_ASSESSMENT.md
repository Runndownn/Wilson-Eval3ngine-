# Ben Reaper's Security Partner — Master Security Assessment and Hardening Report

## 1. Document control

| Field | Value |
|---|---|
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Visibility | Public |
| Base branch/head | `main` / `193f25c48fede79a928cdd7cb3d4e32c5652e223` |
| Assessment branch | `security/hardening-20260731-wilson-eval3ngine` |
| Assessment date | 2026-07-31, America/New_York |
| Authorization | Repository assessment, modification, branch publication, and draft PR explicitly authorized by the owner |
| Completion state | `partial` |
| Runtime evidence | Not supplied; deployment state unverified |
| Report path | `docs/security/MASTER_SECURITY_ASSESSMENT.md` |

### Revision history

| Revision | Summary |
|---|---|
| 0.1 | Established authority, architecture, initial findings, attack paths, and remediation plan. |
| 0.2 | Enforced loopback-only GUI binding, added negative tests, and reconciled finding status and residual risk. |

## 2. Partner charter and bounded assurance statement

Repository evidence establishes target facts. Supplied security knowledge generated defensive hypotheses only and was not treated as target evidence. No production service, real credential, external provider account, or third-party target was tested. Repository remediation does not prove deployed remediation.

The assessment is partial because the available environment did not provide a complete local checkout suitable for byte-level inventory, repository-native test execution, dependency scanning, container scanning, or runtime HTTP/WebSocket testing. No blocked validation is represented as passing.

## 3. Executive narrative

Wilson Eval3ngine combines a project-scoped evaluation API with a separate operator GUI. The primary API includes OIDC/dev authentication, authorization, persistence, rate limiting, audit, evaluation execution, evidence production, and signed dossiers. The operator GUI manages provider endpoints and credentials, invokes report-generation subprocesses, exposes jobs and telemetry, serves reports, and performs destructive administrative actions.

The highest-confidence attack path was the GUI launcher: it disclosed that the GUI had no built-in authentication, warned on non-loopback binding, and still started. An operator typo or copied deployment command could therefore convert local administrative capability into a network-reachable control plane. This branch changes that boundary to fail closed. The launcher now accepts only loopback hostnames or IP addresses and rejects wildcard, private, public, and ambiguous bind targets before Uvicorn starts.

Three material findings remain open: connection-time provider egress validation is not consistently bound to every DNS answer and redirect; subprocess credential handoff uses a plaintext owner-only temporary file and misleading encrypted-key telemetry; and CI suppresses lint failure, downloads an executable without integrity verification, and describes an unsigned source record as OIDC signing.

## 4. Scope, methodology, and limitations

Reviewed evidence includes repository metadata and history, security policy, environment template, production and development containers, primary API security boundaries, GUI application/runtime/launcher, provider adapters, egress controls, key vault, signing/dossier code, CI workflow, tests, and repository integrity declarations.

Blocked evidence includes a complete tree inventory, local test runs, dependency/SAST/secret/IaC/container scans, runtime request testing, and deployment configuration. The latest assessed base commit had no workflow-run or combined-status evidence returned by the connected GitHub account.

## 5. Repository and system understanding

- **Primary API:** authenticated project-scoped operations, storage, evidence, and health surfaces.
- **Evaluation service:** manifest/dataset loading, prompt rendering, provider execution, grading, metrics, gates, and dossiers.
- **Operator GUI:** endpoint and credential administration, model discovery, job control, subprocess execution, telemetry, charts, and reports.
- **Provider boundary:** SDK, HTTP, Ollama, and local CLI adapters processing untrusted model output.
- **Evidence boundary:** local artifacts, audit chain, Ed25519 signatures, and optional trust-registry verification.
- **Supply chain:** Python package build, tests, scans, containers, SBOM-like output, and GitHub Actions artifacts.

```text
browser or network client
  -> operator GUI REST/WebSocket
  -> endpoint credentials + local state
  -> report subprocess / local CLI identity / remote provider
  -> reports, sidecars, charts, telemetry

API client
  -> authentication and project authorization
  -> service, database, artifact store, worker, provider
  -> evidence and signed dossier

contributor
  -> GitHub Actions
  -> build, tests, scanners, artifacts, claimed provenance
```

## 6. Architecture profile and control expectations

| Expectation | Invariant | Status | Finding/debt |
|---|---|---|---|
| WILSON-EVAL3NGINE-EXP-0001 | Repository launcher cannot expose unauthenticated GUI controls beyond loopback. | Satisfied in branch | SEC-0001 |
| WILSON-EVAL3NGINE-EXP-0002 | Every provider connection and redirect is checked against current resolved addresses and egress policy. | Violated | SEC-0002 |
| WILSON-EVAL3NGINE-EXP-0003 | Provider secrets are accurately described, minimally exposed, and never logged in stable fragments. | Partially satisfied | SEC-0003 |
| WILSON-EVAL3NGINE-EXP-0004 | CI gates fail closed and provenance claims are cryptographically true. | Violated | SEC-0004 |
| WILSON-EVAL3NGINE-EXP-0005 | Repository inventory and checksums correspond to the assessed tree. | Uncertain | DEBT-0001 |
| WILSON-EVAL3NGINE-EXP-0006 | OIDC fails closed during refresh, rotation, revocation, replay, and malformed-token conditions. | Partially reviewed | DEBT-0002 |

Applicable profiles: browser/web, API/service, identity/authorization, data/state, worker/subprocess, LLM/provider/tool execution, network/transport, secrets/cryptography, file/report, CI/supply chain, container, observability/resilience, and privacy governance.

## 7. Asset and security-objective register

| Asset | Security objectives |
|---|---|
| Provider keys and local CLI identities | Confidentiality, least privilege, revocation, bounded delegation |
| Prompts, responses, evaluation evidence | Isolation, confidentiality, integrity, retention control |
| Job and subprocess authority | Authorization, bounded execution, availability, auditability |
| Dossiers and release evidence | Integrity, authenticity, approved-signer trust |
| CI and release artifacts | Reproducibility, provenance, integrity, recoverability |

## 8. Identity, privilege, and trust-boundary model

The primary API has an explicit identity model. The GUI has no built-in user authentication. Therefore network reachability is equivalent to operator authority for endpoint administration, job launch/cancel/retry, report retrieval/deletion, and telemetry access. WebSocket origin checks constrain browser origins but do not identify or authorize an actor.

The implemented launcher control reduces the default and repository-supported trust zone to the local host. It does not authenticate a reverse-proxy user. Any remote-access deployment must supply authenticated TLS termination and an authorization contract outside this process until built-in identity is implemented.

## 9. Data, state, and lifecycle model

GUI endpoint state stores encrypted API keys. Report generation decrypts a key and writes it to a short-lived owner-only temporary file for the child process. Jobs and telemetry can contain prompts, provider/model identifiers, stdout/stderr, statuses, artifact names, and hashes. Reports and charts are served from local directories.

Dossier verification with the embedded public key proves integrity, not organizational signer trust. Production release authority must use the trust-registry-aware verification path.

## 10. Attack-surface inventory

| Surface | Identity boundary | Side effects | Status |
|---|---|---|---|
| GUI launcher | Local process invocation | Selects network exposure | Hardened to loopback only |
| GUI REST `/api/*` | No built-in user auth | Endpoints, jobs, reports, telemetry | Residual architectural debt |
| GUI WebSocket `/ws` | Origin comparison only | Job and administrative operations | Residual architectural debt |
| Provider HTTP | Stored endpoint and key | Authenticated outbound requests | SEC-0002 open |
| CLI providers | Local OS/tool identity | Executes installed authenticated tools | Constrained by loopback launcher, still privileged |
| Primary API | Dev headers or OIDC | Project-scoped operations | Further lifecycle testing required |
| CI workflow | GitHub runner identity | Build, scan, artifact publication | SEC-0004 open |

## 11. Web and API expectation assessment

The GUI has bounded request models, output sanitization, security headers, size limits, and safe report filename checks. These controls do not replace actor authentication. Loopback-only binding now blocks accidental direct network exposure through the repository launcher.

Provider URL normalization rejects malformed schemes, embedded credentials, fragments, and several unsafe address classes. However the security decision is not consistently repeated at connection time for every DNS result and redirect hop. Application checks must be backed by network egress policy.

## 12. Knowledge-system provenance and synthesis

The supplied corpus was used to challenge assumptions around prompt injection, stored output, SSRF, credential handling, authentication, and supply-chain trust. It did not prove any target finding. No challenge answers, credentials, destructive payloads, or raw corpus excerpts were committed.

## 13. Defensive security game deck

| Game | Scenario | Result |
|---|---|---|
| WILSON-EVAL3NGINE-GAME-0001 | Bind the unauthenticated GUI to wildcard, private, public, or arbitrary hostname targets. | Branch implementation rejects before server start. Test added; execution blocked. |
| WILSON-EVAL3NGINE-GAME-0002 | Rebind or redirect a configured provider hostname to private/internal space. | Design review failed; SEC-0002 remains open. |
| WILSON-EVAL3NGINE-GAME-0003 | Introduce a lint violation. | Workflow suppresses failure; SEC-0004 remains open. |
| WILSON-EVAL3NGINE-GAME-0004 | Verify a self-signed dossier as release-authoritative. | Integrity verifier alone is insufficient; trust-aware path exists. |

## 14. Individual attack-path analysis

### WILSON-EVAL3NGINE-PATH-0001 — network client to operator authority

Before remediation:

```text
non-loopback bind -> no GUI authentication -> REST/WebSocket action
-> endpoint/job/report/subprocess authority -> provider key or local CLI identity
```

After remediation, the repository launcher rejects the first edge unless the bind target is loopback. Deliberate external proxying remains outside this code boundary and must be authenticated.

### WILSON-EVAL3NGINE-PATH-0002 — configured endpoint to internal destination

```text
endpoint creation -> point-in-time URL/DNS validation -> later request or redirect
-> changed/private destination -> possible internal probing or credential forwarding
```

The break point must be immediately before every connection and redirect.

## 15. Compound and cross-domain attack-path analysis

The GUI combines credentials, local CLI identities, subprocess execution, artifacts, and destructive state changes. These individually expected features form an administrative control plane when combined. Loopback enforcement substantially reduces accidental remote reachability but does not establish user identity.

Provider URL configuration combines untrusted destination selection, mutable DNS, redirects, and bearer credentials. Syntax-only validation cannot close the chain.

## 16. Findings register

| Finding | Severity | Confidence | Status | Residual risk |
|---|---|---|---|---|
| WILSON-EVAL3NGINE-SEC-0001 — fail-open remote GUI binding | High | High | Remediated in branch; runtime unverified | An external proxy can still deliberately expose the unauthenticated app |
| WILSON-EVAL3NGINE-SEC-0002 — stale/incomplete provider egress decision | High | Medium | Confirmed, deferred | DNS, redirect, and network topology determine exploitability |
| WILSON-EVAL3NGINE-SEC-0003 — plaintext temp credential handoff and misleading logging | Medium | High | Confirmed, deferred | Child process necessarily receives usable credentials |
| WILSON-EVAL3NGINE-SEC-0004 — fail-open and unsupported CI trust claims | High | High | Confirmed, deferred | CI artifacts remain unproven until workflow repair and successful run |

## 17. Detailed findings

### WILSON-EVAL3NGINE-SEC-0001

The prior launcher warned on non-loopback binding and continued. Because the GUI has no built-in authentication and exposes administrative operations, a reachable listener crossed directly into operator authority. The authoritative fix is in `src/wilson_eval3ngine/gui/run_gui.py`: `validate_bind_host` canonicalizes known loopback hostnames and IP addresses and rejects every non-loopback or ambiguous target. `main` invokes this check before constructing Uvicorn configuration. `tests/unit/test_gui_bind_security.py` covers IPv4/IPv6 loopback, case/trailing-dot normalization, wildcard addresses, private addresses, public hostnames, and empty input.

Compatibility impact is intentional: `0.0.0.0` and remote interface binds no longer start. Remote deployments must terminate authenticated TLS at a separate proxy connected to loopback. Rollback reopens the attack path.

### WILSON-EVAL3NGINE-SEC-0002

The application validates endpoint syntax and some resolved address properties during configuration, while later legacy HTTP calls may follow redirects and attach Authorization headers. The required fix is a single connection-time policy that resolves all addresses, rejects private/loopback/link-local/multicast/unspecified/metadata destinations unless explicitly allowed for a local provider, disables automatic redirects, and revalidates each `Location` hop. Network policy must provide defense in depth.

### WILSON-EVAL3NGINE-SEC-0003

Long-term endpoint keys are encrypted, but report invocation calls a plaintext owner-only temp-file helper and logs that encrypted credentials were prepared while including masked stable fragments. Required follow-up: remove all key fragments from logs, correct terminology, and replace pathname-based plaintext handoff with a pipe, inherited descriptor, or equivalent narrow channel where child compatibility permits.

### WILSON-EVAL3NGINE-SEC-0004

The CI workflow runs `make lint || true`, fetches and extracts Trivy without digest/signature verification, and labels a source-commit text file as OIDC signing. Required follow-up: fail lint closed, pin and verify scanner acquisition, produce real attestations/signatures with identity binding, and validate the resulting workflow in GitHub Actions. No replacement workflow was committed without executable validation.

## 18. Rejected hypotheses and false positives

- The reviewed safe HTML dossier renderer escapes identifiers and excludes raw prompts/responses; no target-proven XSS finding was confirmed there.
- Reviewed CLI provider execution uses argument arrays rather than `shell=True`; prompt metacharacters are not directly shell-interpreted in that path.
- Reviewed primary API operation routes contain project authorization checks; no confirmed cross-project bypass was established from available evidence.

## 19. Remediation implementation narrative

Commit `2d4980fb2fa652b74ea5e7c4d9e9edec942e257a` replaced warning-only remote GUI binding with a fail-closed loopback validator. Commit `7b61f15db7909131c298c48bc90d073fa90562f6` added focused positive and negative tests. The change is deliberately narrow: no unrelated GUI route, provider, state, or rendering behavior was modified.

## 20. Validation and assurance

Completed evidence:

- Repository identity, permissions, default branch, and exact base head confirmed through GitHub.
- Security branch created from exact base head.
- Branch comparison confirms three intended files changed: master report, launcher, and focused test.
- Static review confirms validation occurs before Uvicorn configuration and rejects non-loopback addresses.
- Base head returned no connected workflow run or combined-status evidence.

Blocked/not run:

- `pytest tests/unit/test_gui_bind_security.py`
- formatter, linter, type checker, full unit/integration/E2E suite
- secret, dependency, SAST, IaC, container, SBOM, and workflow execution checks
- complete inventory and report validator
- runtime bind and proxy tests

## 21. Change impact, rollout, and rollback

Operators using remote bind addresses must change topology. Run the GUI on `127.0.0.1` or `::1`; place an authenticated TLS reverse proxy in front only after defining actor identity, authorization, headers, WebSocket handling, request limits, audit fields, and network access controls. Monitor startup failures after rollout. Reverting the launcher commit restores unauthenticated remote-binding risk.

## 22. Detection, response, and operational hardening

- Alert on any GUI process listening beyond loopback.
- Record authenticated actor, object, action, decision, and outcome for endpoint/job/report operations once GUI identity exists.
- Alert on provider redirects, DNS answer changes, blocked address classes, and repeated endpoint failures.
- Rotate provider credentials if a prior GUI instance was reachable beyond loopback without authenticated proxy protection.
- Treat artifacts from the current CI “signing” step as unsigned.

## 23. Residual risk and accepted assumptions

No risk is accepted for maintainers. Runtime proxy configuration, firewall and egress rules, DNS behavior, secret storage, Redis, PostgreSQL RLS, artifact immutability, and provider scopes are unverified. The repository security policy describes a development/internal-testing foundation and prohibits production credentials and sensitive corpora; this limits intended use but does not erase repository weaknesses.

## 24. Security debt and maturity ledger

| Debt | Missing assurance | Action |
|---|---|---|
| WILSON-EVAL3NGINE-DEBT-0001 | Complete authoritative file inventory and reproducible checksums | Generate from a clean checkout and reconcile manifests |
| WILSON-EVAL3NGINE-DEBT-0002 | OIDC refresh/revocation/replay/failure execution evidence | Add fault and lifecycle tests |
| WILSON-EVAL3NGINE-DEBT-0003 | Production dossier verification requires approved signer trust | Add trust-required production command/path |
| WILSON-EVAL3NGINE-DEBT-0004 | Built-in or formally contracted GUI authentication | Implement sessions/token auth or verified proxy contract |

## 25. Prioritized future roadmap

1. Repair CI fail-open and false-provenance behavior; obtain an actual workflow run.
2. Centralize connection-time egress and redirect validation with DNS/private-range tests.
3. Redesign credential handoff and remove key-fragment logging.
4. Complete OIDC lifecycle, tenant authorization, rate-limit failure, audit failure, restore, and signer-trust tests.
5. Produce complete inventory, regenerate checksums, and reconcile documentation.

## 26. Continuous assurance and reassessment triggers

Reassess on GUI remote-access changes, identity/session changes, provider adapters, endpoint policy, subprocess interfaces, CI/signing changes, dependency advisories, container topology, restore events, and incidents. Recurring controls should include route inventory, authz matrices, SSRF/egress tests, secret/dependency/workflow scans, and signature verification.

## 27. Coverage ledger

Coverage remains partial. Reviewed domains include the primary API security boundary, GUI application/runtime/launcher, providers, egress, key vault, signing/dossier, CI, containers, security policy, environment template, and integrity declarations. Total file/byte counts and zero-unreviewed proof are blocked without a complete local inventory.

## 28. Traceability matrix

| Item | Evidence | Change/test | Commit | Status |
|---|---|---|---|---|
| SEC-0001 | GUI launcher and route authority | Loopback validator + negative tests | `2d4980f`, `7b61f15` | Remediated in branch, not executed |
| SEC-0002 | URL normalization and later HTTP/redirect behavior | Execution-ready design only | — | Open |
| SEC-0003 | Key vault and report invocation | Execution-ready design only | — | Open |
| SEC-0004 | `.github/workflows/ci.yml` | Execution-ready design only | — | Open |
| DEBT-0001 | Manifest/checksum drift and incomplete inventory | Full inventory blocked | — | Open |

## 29. Portfolio and cross-repository dependencies

No second repository was authorized. Identity providers, Redis, PostgreSQL, object storage, reverse proxies, provider services, and GitHub Actions are external deployment dependencies rather than assessed repositories.

## 30. Knowledge delta

Reusable lessons: local operator GUIs that combine secrets, subprocesses, local identities, and destructive actions are administrative control planes; warnings are not exposure controls; URL validation must be bound to connection-time resolution and every redirect; and provenance labels require cryptographic evidence.

No knowledge is promoted automatically.

## 31. Appendices

### Evidence classes

`[REPO]` direct repository evidence; `[RUNTIME]` collected runtime evidence; `[HISTORY]` commit/PR evidence; `[CORPUS-*]` hypothesis source; `[STANDARD]` current authoritative guidance; `[INFERENCE]` analyst conclusion; `[BLOCKED]` unavailable evidence.

### Current blockers

- No complete local checkout/test environment.
- No supplied deployment/runtime evidence.
- No workflow run/status evidence for the assessed base head.
- No complete byte-level tree inventory.
