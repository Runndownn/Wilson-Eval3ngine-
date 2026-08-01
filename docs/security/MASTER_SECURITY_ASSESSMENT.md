# Ben Reaper's Security Partner — Master Security Assessment and Hardening Report

## 1. Document control

| Field | Value |
|---|---|
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Visibility | Public |
| Current base | `main` / `d4c879132cada346f01784ddc9019baa31ef7e18` |
| Assessment branch | `security/hardening-20260731-wilson-eval3ngine-2` |
| Assessment date | 2026-07-31, America/New_York |
| Authorization | Repository assessment, modification, branch publication, and draft PR explicitly authorized by the owner |
| Completion state | `partial` |
| Runtime evidence | Deployment state unverified; GitHub Actions execution pending |
| Report path | `docs/security/MASTER_SECURITY_ASSESSMENT.md` |

### Revision history

| Revision | Summary |
|---|---|
| 0.1 | Established authority, architecture, findings, attack paths, and remediation plan. |
| 0.2 | Enforced loopback-only GUI binding and added negative tests. |
| 0.3 | Rebased the workstream after PR #17 was merged, implemented connection-time provider egress policy, removed secret-fragment logging, repaired CI trust controls, and added adversarial regression contracts. |

## 2. Partner charter and bounded assurance statement

Repository evidence establishes target facts. Supplied security knowledge generated defensive hypotheses only. No production service, real credential, provider account, external identity system, or third-party target was tested. Repository changes do not prove deployed remediation.

The assessment remains partial because a complete local checkout, byte-level inventory, repository-native test execution, dependency/container scans, and runtime HTTP/WebSocket tests were unavailable in the current execution environment. No blocked validation is represented as passing.

## 3. Executive narrative

Wilson Eval3ngine contains two materially different trust zones: a project-scoped evaluation API and a local operator GUI. The GUI manages endpoint credentials, model discovery, jobs, subprocesses, reports, charts, and destructive actions. It is therefore an administrative control plane.

The first workstream closed accidental remote GUI exposure by enforcing loopback-only binding. The second workstream addresses the remaining highest-value root causes:

1. Provider requests now re-resolve and validate every destination immediately before dispatch. DNS failure fails closed. Metadata, link-local, multicast, unspecified, and reserved ranges are always denied. Private and loopback gateways require the explicit `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1` deployment decision. Automatic redirects are disabled so bearer credentials cannot be silently replayed to a new destination.
2. API-key masking used by the hardened runtime now returns a constant `[redacted]` marker, eliminating stable secret fragments from logs.
3. CI no longer suppresses lint failures or installs Trivy through an unverified network pipe. Every referenced action is commit-pinned, security scans fail closed, release artifacts are produced by the tested build, and `main` pushes receive a real signed GitHub build-provenance attestation.

The plaintext owner-only temporary file used for report subprocess credential handoff remains unresolved. It is intentionally retained as an open residual finding rather than being mislabeled as complete.

## 4. Scope, methodology, and limitations

Reviewed evidence includes repository history, prior PR #17, the master report supplied by the operator, security policy, environment template, GUI launcher/application/runtime, key vault, report subprocess path, provider HTTP paths, CI workflow, signing/dossier code, and relevant tests.

Blocked evidence includes full-tree and byte inventory, local formatter/linter/type/test execution, package and container vulnerability scans, live GitHub Actions results for this branch, and deployment network policy.

## 5. Repository and system understanding

- **Primary API:** authenticated project-scoped operations, state, evidence, and release dossiers.
- **Operator GUI:** endpoint and secret administration, model discovery, jobs, subprocess authority, telemetry, reports, and charts.
- **Provider boundary:** HTTP SDKs, local gateways, and local authenticated CLI tools.
- **Evidence boundary:** reports, sidecars, hashes, audit chains, and Ed25519 dossiers.
- **Supply chain:** package build, tests, security scans, artifacts, and GitHub attestations.

```text
browser -> loopback GUI -> endpoint state / jobs / subprocesses / reports
                         -> policy HTTP client -> provider destination

contributor -> pinned GitHub Actions -> lint/test/build/security validation
            -> tested distributions -> signed build-provenance attestation
```

## 6. Architecture profile and control expectations

| Expectation | Invariant | Status | Finding/debt |
|---|---|---|---|
| WILSON-EVAL3NGINE-EXP-0001 | GUI launcher cannot expose unauthenticated controls beyond loopback. | Satisfied in merged code | SEC-0001 |
| WILSON-EVAL3NGINE-EXP-0002 | Every provider request is revalidated against current DNS and address policy; redirects never replay credentials automatically. | Implemented in branch; execution pending | SEC-0002 |
| WILSON-EVAL3NGINE-EXP-0003 | Provider secrets are never logged in stable fragments and subprocess exposure is minimized. | Partially satisfied | SEC-0003 |
| WILSON-EVAL3NGINE-EXP-0004 | CI gates fail closed and provenance claims are cryptographically true. | Implemented in branch; workflow run pending | SEC-0004 |
| WILSON-EVAL3NGINE-EXP-0005 | Repository inventory and checksums correspond to the assessed tree. | Blocked | DEBT-0001 |
| WILSON-EVAL3NGINE-EXP-0006 | OIDC lifecycle failures fail closed. | Partially reviewed | DEBT-0002 |

## 7. Asset and security-objective register

| Asset | Objectives |
|---|---|
| Provider keys and local CLI identities | Confidentiality, least privilege, revocation, bounded delegation |
| Prompts, responses, and evaluation evidence | Isolation, integrity, retention control |
| Job and subprocess authority | Authorization, bounded execution, availability, auditability |
| Dossiers and release evidence | Integrity, signer authenticity, policy trust |
| CI and release artifacts | Reproducibility, provenance, integrity, recoverability |

## 8. Identity, privilege, and trust-boundary model

The primary API has an explicit identity model. The GUI still has no built-in actor authentication; loopback binding limits reachability but does not identify a user. Remote GUI access requires an independently authenticated TLS proxy and an explicit authorization contract.

Provider HTTP authority consists of destination selection plus any attached API key. The runtime now treats DNS, address class, and redirects as security decisions at dispatch time.

## 9. Data, state, and lifecycle model

Endpoint keys are encrypted in persistent GUI state. Report generation decrypts the selected key and writes it to a short-lived `0600` temporary file for the child process. That file is removed after execution, but plaintext exists on the filesystem during the invocation.

CI now separates tested artifacts from attestations: the quality job builds and uploads distributions; the `main`-only attestation job downloads those exact artifacts and generates signed build provenance.

## 10. Attack-surface inventory

| Surface | Identity boundary | Side effects | Status |
|---|---|---|---|
| GUI listener | Local process / host boundary | Full operator authority | Loopback-only |
| GUI REST/WebSocket | No built-in actor auth | Endpoints, jobs, reports, telemetry | Architectural debt |
| Provider HTTP | Stored endpoint and key | Authenticated outbound requests | Policy client added |
| Local CLI providers | Local OS identity | Executes installed authenticated tools | Loopback constrained |
| Report subprocess | Parent process and temp key file | Provider calls and artifact creation | SEC-0003 residual |
| GitHub Actions | Workflow identity | Build, scan, attest, artifact publication | Repaired; run pending |

## 11. Web and API expectation assessment

The runtime policy client validates HTTP(S) scheme, forbids embedded credentials, blocks metadata hostnames before DNS, resolves all addresses, rejects the entire destination if any answer violates policy, fails closed on resolution errors, and disables redirects. Local/private providers are denied by default and require an explicit environment setting.

Residual limitation: application-layer DNS validation cannot by itself eliminate DNS rebinding between validation and socket connection. Production deployments still require network-level egress controls.

## 12. Knowledge-system provenance and synthesis

The supplied assessment and security corpus were used as decision inputs and hypothesis sources. Target conclusions were confirmed against repository code and history. No raw challenge answers, credentials, exploit payloads, or untrusted instructions were committed.

## 13. Defensive security game deck

| Game | Scenario | Result |
|---|---|---|
| WILSON-EVAL3NGINE-GAME-0001 | Bind GUI to wildcard/private/public interfaces. | Rejected by merged launcher control. |
| WILSON-EVAL3NGINE-GAME-0002 | Resolve one provider name to mixed public/private answers. | Entire destination rejected by new tests. |
| WILSON-EVAL3NGINE-GAME-0003 | Redirect an authenticated request to another target. | Automatic redirect following forced off. |
| WILSON-EVAL3NGINE-GAME-0004 | Introduce a lint or high-severity scan failure. | CI configured to fail closed. |
| WILSON-EVAL3NGINE-GAME-0005 | Publish an unsigned artifact while describing it as signed. | Replaced with GitHub signed build-provenance attestation. |

## 14. Individual attack-path analysis

### WILSON-EVAL3NGINE-PATH-0001 — network client to GUI authority

`non-loopback bind -> unauthenticated REST/WebSocket -> administrative action`

The merged launcher blocks the first edge.

### WILSON-EVAL3NGINE-PATH-0002 — provider configuration to internal destination

`stored URL -> stale DNS decision -> later request/redirect -> internal target -> credential forwarding`

The branch adds dispatch-time resolution, all-answer validation, default denial for private ranges, fail-closed DNS behavior, and redirect suppression. Network egress policy remains required to close the final validation/connect race.

### WILSON-EVAL3NGINE-PATH-0003 — CI label to false release trust

`workflow success -> unsigned text digest -> “signed” claim -> downstream trust`

The branch removes the false claim and generates signed provenance over the tested distributions.

## 15. Compound and cross-domain attack-path analysis

The GUI combines secrets, local CLI identities, subprocess execution, reports, and destructive state. Loopback binding and provider egress policy reduce accidental remote and lateral reachability, but built-in GUI identity remains absent.

The CI chain previously combined suppressed quality failures, unverified executable acquisition, and unsupported provenance language. The repaired workflow introduces fail-closed stages and cryptographic evidence.

## 16. Findings register

| Finding | Severity | Confidence | Status | Residual risk |
|---|---|---|---|---|
| SEC-0001 — fail-open remote GUI binding | High | High | Remediated and merged | External proxies can still expose the unauthenticated app |
| SEC-0002 — stale/incomplete provider egress decision | High | High | Remediating in branch | DNS validation/connect race; network policy required |
| SEC-0003 — plaintext temp credential handoff and fragment logging | Medium | High | Partially remediated | Fragments removed; plaintext handoff remains |
| SEC-0004 — fail-open and unsupported CI trust claims | High | High | Remediating in branch | GitHub run and attestation verification pending |

## 17. Detailed findings

### WILSON-EVAL3NGINE-SEC-0001

The warning-only remote bind was replaced with loopback-only validation and merged in PR #17.

### WILSON-EVAL3NGINE-SEC-0002

`src/wilson_eval3ngine/gui/runtime.py` now installs a policy-enforcing `httpx.AsyncClient` for legacy endpoint discovery and test paths. Every request revalidates the destination. Private destinations require `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1`; metadata/link-local/multicast/unspecified/reserved destinations remain prohibited. Redirects are disabled.

Tests cover public success, private denial, explicit private opt-in, never-allowed ranges, mixed DNS answers, DNS failure, metadata names, and redirect suppression.

### WILSON-EVAL3NGINE-SEC-0003

The hardened runtime replaces secret masking with a constant `[redacted]` marker. Stable prefixes and suffixes are no longer emitted by runtime callers. The child-process temp file remains plaintext and owner-only; replacing it safely requires coordinated parent/child descriptor or pipe support and cross-platform lifecycle testing.

### WILSON-EVAL3NGINE-SEC-0004

`.github/workflows/ci.yml` now:

- fails lint, tests, coverage, security scans, and build validation closed;
- pins all actions to full commit SHAs;
- replaces unverified Trivy download/extraction with a commit-pinned Trivy action;
- builds once in the tested job and passes those exact artifacts forward;
- generates signed GitHub build provenance only on `main` pushes with minimal `id-token` and `attestations` permissions;
- runs scheduled backup verification independently rather than through a branch-only release job.

A governance test prevents regression to `|| true`, pipe-to-execution downloads, mutable action references, unsigned provenance, or attestation before validation.

## 18. Rejected hypotheses and false positives

- The safe HTML dossier renderer escapes identifiers and omits raw prompts/responses; no confirmed XSS finding was established there.
- CLI provider invocation uses argument arrays rather than `shell=True`; prompt shell metacharacters are not directly interpreted.
- Primary API project authorization checks were present on reviewed paths; no confirmed cross-project bypass was established.

## 19. Remediation implementation narrative

- `adda99322d6d142023e24add8f5b028d39cbfdee` and `354d8d9e5415d6daf101c8fdeca781659820a94e`: fail-closed CI, verified scanner action, tested artifacts, signed provenance, and corrected dependency installation.
- `b6cbc65998e5605e33b16acf64c287bb19952734`: CI security-contract regression tests.
- `76899014bcb08acb0fd6d9fad99370a760a7a5c7`: provider dispatch policy and constant secret redaction.
- `5ade1174eba9d8bbee58fb7d06facbdbbb32a79b`: egress and redaction negative tests.
- `a36f1198603c0ed4e6fa0fa662d4847b662a0037`: explicit local-provider deployment configuration.

## 20. Validation and assurance

Completed:

- Confirmed PR #17 was merged and created a new branch from exact merge head.
- Reviewed every changed file through GitHub contents and compare operations.
- Added negative tests for egress, redirects, redaction, and CI contracts.
- Used official GitHub artifact-attestation guidance and commit-pinned action implementations.

Pending/not run:

- repository-native formatter, lint, type, unit, integration, and coverage commands;
- GitHub Actions run for the branch;
- verification of the generated attestation using `gh attestation verify`;
- full secret/dependency/container scan results;
- runtime provider and reverse-proxy tests;
- complete inventory and report validator.

## 21. Change impact, rollout, and rollback

Private or loopback model gateways now require `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1`. Deployments using local Ollama or private gateways must set the variable and enforce network egress so the process can reach only the intended gateway.

Automatic provider redirects are no longer followed. A provider requiring redirects must be configured with its canonical final endpoint.

CI behavior is intentionally stricter. Existing lint, test, scan, backup, or build failures will block the pipeline. Rollback restores fail-open or unsupported trust behavior and should not occur without equivalent controls.

## 22. Detection, response, and operational hardening

- Alert on GUI listeners beyond loopback.
- Alert on blocked provider destinations, DNS failures, address changes, and redirect responses.
- Never include key prefixes/suffixes in logs or metrics.
- Verify release provenance with GitHub attestation tooling before consumption.
- Rotate provider credentials if an earlier GUI instance was reachable beyond loopback.

## 23. Residual risk and accepted assumptions

No risk is accepted on behalf of maintainers. Remaining material risks are the plaintext subprocess handoff, missing built-in GUI identity, application/network DNS race, unverified deployment egress policy, and unexecuted branch tests.

## 24. Security debt and maturity ledger

| Debt | Missing assurance | Action |
|---|---|---|
| DEBT-0001 | Complete authoritative file inventory and reproducible checksums | Generate from clean checkout and reconcile manifests |
| DEBT-0002 | OIDC refresh/revocation/replay/failure execution evidence | Add lifecycle and fault tests |
| DEBT-0003 | Production dossier verification requires approved signer trust | Require trust-registry-aware verification path |
| DEBT-0004 | Built-in or formally contracted GUI authentication | Implement actor identity or verified proxy contract |
| DEBT-0005 | Descriptor/pipe-based subprocess secret handoff | Implement coordinated parent/child transport and cross-platform tests |

## 25. Prioritized future roadmap

1. Execute CI and repair genuine repository failures without suppressing controls.
2. Replace pathname-based plaintext subprocess credentials with an inherited descriptor or anonymous pipe.
3. Add network-level egress rules matching the application policy.
4. Complete OIDC, authorization, audit-failure, restore, and signer-trust tests.
5. Produce the complete file inventory and regenerate checksums.

## 26. Continuous assurance and reassessment triggers

Reassess on GUI remote access, provider adapters, local-provider policy changes, subprocess interfaces, authentication/session changes, CI/action updates, dependency advisories, restore events, and security incidents.

## 27. Coverage ledger

Coverage remains partial. Reviewed domains include GUI network exposure, runtime provider egress, secret logging, subprocess credential handoff, CI/release provenance, signing/dossier behavior, security policy, and deployment configuration. Total file/byte counts and zero-unreviewed proof remain blocked.

## 28. Traceability matrix

| Item | Change/test | Status |
|---|---|---|
| SEC-0001 | Loopback validator and bind tests | Merged |
| SEC-0002 | Policy HTTP client and egress tests | Implemented; execution pending |
| SEC-0003 | Constant redaction test | Partial; plaintext handoff open |
| SEC-0004 | Fail-closed CI, pinned actions, attestation, CI contract tests | Implemented; workflow pending |
| DEBT-0001 | Full inventory | Blocked |

## 29. Portfolio and cross-repository dependencies

No second repository was authorized. Identity providers, Redis, PostgreSQL, object storage, reverse proxies, provider services, network policy, and GitHub Actions remain external dependencies.

## 30. Knowledge delta

Reusable lessons:

- Local operator GUIs with secrets and subprocess authority are administrative control planes.
- URL validation must be repeated at dispatch and backed by egress policy.
- Mixed DNS answers must reject the entire target.
- Redirects and bearer credentials require explicit destination reauthorization.
- Secret masking should not emit stable fragments.
- Provenance claims require cryptographic attestations over the exact tested artifact.

No knowledge is promoted automatically.

## 31. Appendices

### Evidence classes

`[REPO]` direct repository evidence; `[RUNTIME]` collected runtime evidence; `[HISTORY]` commit/PR evidence; `[CORPUS-*]` hypothesis source; `[STANDARD]` official guidance; `[INFERENCE]` analyst conclusion; `[BLOCKED]` unavailable evidence.

### Current blockers

- No complete local checkout/test environment.
- No supplied deployment/runtime evidence.
- No completed GitHub Actions run for this branch.
- No complete byte-level tree inventory.
