# Wilson Eval3ngine — Master Security Living Document

## Document authority

This document is the authoritative record of **known unresolved security findings** for Wilson Eval3ngine. It is intentionally a living ledger: resolved, disproven, no-longer-applicable, or duplicate findings do not remain here with checkmarks or strike-through text; after an evidence-backed state transition their complete history moves to `docs/MASTER-TOMBSTONE-SECURITY.md` under the same stable finding ID.

An empty findings section means only that no known unresolved findings remain within the scope and evidence of the most recently completed assessment. It is not a claim that the software is incapable of containing an undiscovered vulnerability.

**Assessment baseline:** `main` at `a5bd171208b65bf427c0a4e413fd1bd79e7418ff` on 2026-08-22.  
**Assessment branch:** `security/living-ledger-20260822`.  
**Method:** source-document ingestion → implementation trace → threat model → current-state verification → bounded remediation → independent test/CI verification → lifecycle transition.  
**Current state:** assessment/remediation in progress. Findings marked *Verification Pending* remain active until the branch tests and relevant repository gates provide closure evidence.

## Finding lifecycle

Every finding, regardless of whether it originates from a human review, Codex-style agent, scanner, incident, test, or another AI system, follows the same state model:

`Discover → Normalize → Classify → Verify → Record Active → Investigate → Remediate → Test → Re-verify → Tombstone`

Allowed active states are **Active — Verified**, **Active — Partially Remediated**, and **Active — Verification Pending**. Allowed resolved states are **Resolved — Remediated and Verified**, **Resolved — No Longer Applicable**, **Resolved — Disproven**, and **Resolved — Duplicate or Consolidated**. No finding may disappear between these records; stable IDs and source provenance follow it for its complete lifecycle.

## Risk method

Wilson Eval3ngine does not currently publish one repository-wide numeric vulnerability scoring contract, so this ledger uses qualitative severity with explicit reasoning. Severity considers attacker-controlled input, required access, privilege, trust-boundary crossings, confidentiality/integrity/availability effects, persistence, blast radius, production exposure, compensating controls, and whether a risky path is a supported deployment path or an operator-only/local compatibility path. Where a future release adopts CVSS or another project-specific scoring contract, numeric vectors can be added without replacing this reasoning.

## Security architecture and trust boundaries

```text
Public client
    |
    v
Caddy TLS / ingress boundary
    |   blocks public diagnostics; overwrites forwarding identity
    v
API request-security boundary
    |   streamed body limit -> CORS/metadata/content type -> Redis rate authority
    |   -> OIDC authentication/revocation -> project identity
    v
Exact authorization + durable authorization-audit boundary
    |
    +--> PostgreSQL project data / hash-linked audit
    +--> Redis idempotency, revocation, rate state
    +--> artifact/evidence storage

Operator browser
    |
    +--> loopback GUI -- local synthetic operator identity
    |
    +--> remote GUI -- explicit OIDC profile required by supported launcher
             |
             v
       endpoint/model/job controls
             |
             +--> GUI policy HTTP client
             |
             +--> report child process -> provider endpoint -> report/evidence artifacts
                          ^
                          | separate legacy network policy remains an active finding
```

Security properties are deliberately separated. CORS is not authentication. A reverse proxy is not trusted merely because a forwarding header exists. `jti` plus revocation is not sender-constrained authentication. Structured logs are not the durable audit ledger. A configured Redis URL is not runtime proof of multi-worker distributed state. Local encrypted credential storage is not a production secret authority.

## Assessment source provenance

The six documents that occupied `docs/security/` at the baseline were treated as claims, not current authority. Their original bytes are preserved in the security archive and are identified below by the Git blob object ID from the baseline tree. These object IDs are repository-content fingerprints, not a representation that an independent SHA-256 file digest was computed during this connector-only review.

| Source | Baseline Git blob object ID | Role in normalization |
|---|---|---|
| `MASTER_SECURITY_ASSESSMENT.md` | `71b5c1d1a6a653cde050e8f107229b8c4eb50e79` | 2026-08-01 ten-finding hardening assessment and residual debt |
| `PRIVATE_RUNTIME_ASSURANCE.md` | `0fd875d5d77a14ed70331bb10806e1c3e44e82b4` | private/public assurance boundary and runtime proof requirements |
| `SECURITY_ASSESSMENT.md` | `ec17e96fd6832201c79dfbece84c890fc90b662c` | 2026-07-30 twelve-finding source assessment |
| `SECURITY_REASSESSMENT_2026-08-22.md` | `3f515c803063728781dd42b922175435b0814a68` | second-order revalidation of July findings plus eight new defects |
| `TECHNICAL_ASSESSMENT_BRANCH_INTEGRATION.md` | `ecb1bf0f69d83dff3d75a7eb29dff898fa5d40b1` | private-assurance integration history and residual gaps |
| `Wilson-Eval3ngine-dev-mid-security-quality-plan.md` | `2e73a29bdf72ae2822a73f57c0924f4ecca7e68c` | detailed hardening plan, threat paths, acceptance criteria, and future debt |

The normalized disposition of each explicit finding family is recorded either below or in the tombstone. Operational assurance requirements that are not vulnerabilities are retained later in this document under **Assurance obligations**, rather than being inflated into artificial findings.

# Active findings

## Authentication and identity

### WE3-SEC-0021 — Bearer credentials are not sender-constrained

**Domain:** Authentication and token handling  
**Severity:** Medium  
**Lifecycle:** Active — Verified  
**Source provenance:** July finding 1; 2026-08-22 reassessment residual 1; `PRIVATE_RUNTIME_ASSURANCE.md` sender-constraint warning.  
**Affected components:** `src/wilson_eval3ngine/security/oidc.py`, API OIDC composition, remote GUI OIDC composition, private identity-provider configuration.

**Problem and security property.** Current OIDC validation correctly verifies issuer, audience, allowed signing algorithm/key type, signed lifetime claims, project/role/subject/JWT ID, MFA evidence, and application revocation state. Those controls establish token authenticity and allow invalidation, but an ordinary bearer token remains usable by any party that possesses it until its signed expiry or successful revocation. The missing property is proof that the requester possesses a separately bound client key or channel credential.

**Threat scenario and preconditions.** An attacker must first obtain a still-valid bearer token through a separate compromise such as endpoint malware, browser/session leakage, an IdP/client defect, or mishandled operational evidence. The repository does not itself create that theft primitive in the reviewed OIDC path, so severity is not rated as though token capture were unauthenticated. If theft does occur, a valid unrevoked token can be replayed from another sender until expiry/revocation because `jti` is an identifier, not proof-of-possession.

**Current controls.** Tokens have bounded signed lifetimes; `jti` and `sub` are required; API revocation uses shared Redis in assurance environments; revocation TTL covers the token's complete remaining signed lifetime; MFA claim validation and exact project/role authorization reduce blast radius; duplicate/malformed Authorization headers are rejected on the remediation branch.

**Control limitation.** The remote GUI constructs its own OIDC authenticator and does not presently participate in the API's Redis-backed self-revocation authority. This does not invalidate signature/expiry checks, but it reinforces that application revocation and sender binding are separate controls.

**Required remediation or decision.** If the production threat model requires token-theft resistance beyond short lifetime and revocation, integrate a sender-constrained mechanism supported by the real IdP and client population (for example DPoP, mTLS-bound access tokens, or workload-specific mutually authenticated credentials) and explicitly bind GUI/API behavior to that deployment contract. Do not relabel `jti` as replay prevention.

**Verification required for closure.** Demonstrate with the selected production identity system that a token replayed without the sender key/channel binding is rejected, while legitimate clients continue to authenticate; retain private raw evidence and publish only bounded evidence fingerprints/statuses.

## Network, provider, and AI execution trust boundaries

### WE3-SEC-0022 — Report-child provider egress is not governed by the authoritative GUI network policy

**Domain:** Network/API security; model/provider execution; secrets  
**Severity:** Medium  
**Lifecycle:** Active — Partially Remediated  
**Source provenance:** Aug-01 `SEC-0004`, hardening-plan P0-4, master-assessment residual `DEBT-0002`; verified directly in `scripts/generate_5_reports.py`.  
**Affected locations:** `src/wilson_eval3ngine/gui/runtime.py`, `src/wilson_eval3ngine/gui/application.py`, `src/wilson_eval3ngine/gui/server.py` compatibility call paths, `scripts/generate_5_reports.py`.

**Problem.** The modern GUI HTTP client revalidates resolved destinations immediately before dispatch, fails closed on mixed prohibited DNS answers, permanently blocks metadata/link-local/multicast/unspecified/reserved classes, disables redirects, verifies TLS, and ignores proxy environment variables. The report-generation child uses a separate older URL/DNS policy. Its `_validate_gateway_url` historically allows DNS-resolution failure to continue with only a warning, uses a separate `WE3_REPORT_ALLOW_LOCAL` decision, and validates before a later lower-level connection rather than sharing one authoritative destination object/control.

**Threat path.** A provider endpoint accepted into the report-child path can cross a process and network trust boundary while provider credentials may be in scope. Divergent validation creates room for DNS change/rebinding, inconsistent treatment of local/reserved destinations, or redirect/connection behavior that the GUI's stricter client would have denied. Required access is significant—an attacker generally needs operator/GUI authority or control over configured provider infrastructure—so the finding is Medium rather than treating the endpoint as an unauthenticated public SSRF primitive.

**Current controls.** The supported GUI path has a hardened policy client; public endpoints require secure transport; the report script contains SSRF checks and TLS verification; one-shot child-secret transport reduces credential persistence; production topology includes an egress-proxy boundary.

**Control limitation.** Two implementations can drift, and source-level URL/DNS checks cannot by themselves prove what peer was ultimately reached. Private egress policy is also a deployment fact, so repository code alone cannot close the compound path.

**Remediation requirement.** Extract one versioned endpoint network policy used by creation, discovery, test, GUI dispatch, report child, and retry paths. It must define schemes, host/CIDR/port/path policy, permanent denied ranges, local/private profiles, DNS/mixed-answer behavior, redirect behavior, credential origin binding, proxy policy, timeouts, and peer revalidation where transport APIs permit. DNS failure must fail closed for a network request rather than authorizing an unresolved target.

**Verification requirement.** Table-driven IPv4/IPv6 tests; mixed-answer and DNS-failure tests; simulated rebinding/peer tests; redirect credential-stripping tests; local Ollama positive tests; metadata/link-local negative tests; and a private egress-proxy test demonstrating that an out-of-policy destination is blocked without credential forwarding.

## Compatibility and alternate entry points

### WE3-SEC-0023 — Legacy GUI FastAPI application remains directly startable outside the supported launcher contract

**Domain:** Authentication/authorization; configuration/deployment; legacy compatibility  
**Severity:** Medium  
**Lifecycle:** Active — Verified  
**Source provenance:** hardening-plan P2-3 required a direct-module-start negative test; current review confirmed the condition in `src/wilson_eval3ngine/gui/server.py`.  
**Affected components:** `src/wilson_eval3ngine/gui/server.py`, `src/wilson_eval3ngine/gui/application.py`, `src/wilson_eval3ngine/gui/runtime.py`, documented GUI entry points.

**Problem.** The supported `we3-gui-start` path serves the newer runtime application and now couples non-loopback binding to OIDC. The compatibility module nevertheless creates `app = FastAPI(...)` at import time and registers its own legacy routes. A knowledgeable operator or deployment script can therefore point an ASGI server directly at `wilson_eval3ngine.gui.server:app`, bypassing controls installed only by the supported launcher/runtime composition.

**Threat scenario.** Exploitation requires deployment/operator misconfiguration or a stale script that starts the internal module directly; this is not the default product path. If such a listener is network-reachable, the mismatch can restore exactly the administrative-control-plane exposure that the modern launcher is designed to prevent. The consequence can include endpoint/model/job/report operations under the legacy route set.

**Current controls.** Package CLI points to the modern launcher; `application.py` documents that the legacy module is not the served app; supported launcher defaults to loopback and now requires validated OIDC for non-loopback exposure.

**Remediation requirement.** Remove the legacy ASGI application as an independently serveable authority or make direct startup fail closed. Extract still-used helpers behind typed modules, retain characterization tests, and add a regression proving `uvicorn wilson_eval3ngine.gui.server:app` cannot expose an alternate control plane. Compatibility changes must preserve helper behavior consumed by `application.py`/`runtime.py` without maintaining a second security boundary.

**Verification requirement.** Route inventory proving one authoritative GUI application; import smoke tests; direct-module-start negative test; supported local and OIDC launcher tests; and all provider/chart/report/job regression suites.

## Remediations awaiting independent verification

The following findings remain active solely because closure requires independent test/CI evidence after the branch patches. If those gates pass and adjacency review finds no bypass, their full records must move to the tombstone and disappear from this section.

### WE3-SEC-0024 — Remote GUI bind could retain local synthetic administrator identity

**Domain:** Authentication / administrative exposure  
**Severity:** High  
**Lifecycle:** Active — Verification Pending  
**Discovery:** current 2026-08-22 living-ledger review; regression of the intent behind Aug-01 `SEC-0001`.  
**Affected components:** `gui/run_gui.py`, `gui/access_control.py`.

`WE3_GUI_ALLOW_REMOTE_BIND=1` previously permitted a non-loopback/wildcard listener while `WE3_GUI_ACCESS_MODE` could remain its default `local`; local mode stamps every request with synthetic `local-operator` / `project_admin`. The branch adds `validate_exposure_contract`: every non-loopback/wildcard bind now requires a fully validated OIDC profile, while loopback local mode remains available. Targeted tests cover remote opt-in + local rejection, valid OIDC remote acceptance, and local loopback compatibility. Closure requires those tests and the broader GUI security suite to pass.

### WE3-SEC-0025 — Assurance API synchronous run lane accepted caller-selected host filesystem paths

**Domain:** File/path handling; privilege boundary; API execution  
**Severity:** High  
**Lifecycle:** Active — Verification Pending  
**Discovery:** current 2026-08-22 code-path review.  
**Affected components:** `api/main.py::RunRequest`, `application/service.py::run_manifest`, `api/security_middleware.py`.

The authenticated `/v1/experiments:run` route accepts `manifest_path`, `output_dir`, and optional `signing_key_path`. The synchronous service resolves those paths, creates the output directory, reads the manifest/dataset, and can generate/load a signing key at the selected path. In a remotely reachable assurance deployment this grants authenticated evaluation roles filesystem authority broader than project authorization, limited only by the service OS/container account. The synchronous lane is documented for local development, deterministic CI, and recovery diagnostics; durable production execution belongs to the scheduler. The branch therefore rejects `/v1/experiments:run` before route side effects in staging/production while preserving development behavior. Closure requires targeted middleware tests plus API integration/security tests.

### WE3-SEC-0026 — Security log redaction could preserve secret-bearing URL query parameters

**Domain:** Logging and sensitive-data exposure  
**Severity:** Medium  
**Lifecycle:** Active — Verification Pending  
**Source provenance:** Technical-assessment `GAP-02`; independently confirmed in current `security/log_redaction.py`.  
**Affected components:** `security/log_redaction.py`, all log sinks using `SensitiveLogFilter`.

The prior URL helper primarily changed credential-bearing userinfo. A URL without userinfo but with query fields such as `access_token`, `api_key`, `token`, or `password` could therefore retain the secret value in an otherwise non-sensitive logging field. The branch now parses URL query pairs, replaces values for sensitive parameter names, removes fragments, preserves benign query values, and keeps existing field/userinfo/Bearer/assignment redaction. A regression test proves the token and fragment disappear. Closure requires the focused test plus the broader security/logging suite.

### WE3-SEC-0027 — Ambiguous duplicate Authorization headers could select inconsistent bearer credentials

**Domain:** Authentication / HTTP parsing  
**Severity:** Medium  
**Lifecycle:** Active — Verification Pending  
**Discovery:** adjacency review of API and GUI OIDC boundaries.  
**Affected components:** `api/auth.py`, `api/security_middleware.py`, `gui/access_control.py`.

Security-sensitive authentication must not depend on framework/header folding behavior when duplicate `Authorization` fields arrive. The remediation branch reads the raw ASGI header sequence and accepts exactly one bounded ASCII `Bearer` value; ambiguous, malformed, empty, non-ASCII, and oversized values fail closed. API context creation and self-revocation use the same parser; GUI access performs the same single-header invariant. Closure requires parser, API composition, GUI identity, and hostile HTTP tests.

# Assurance obligations — not vulnerability findings

These items must remain visible because repository source alone cannot prove deployment security, but they are not duplicated as vulnerability findings without evidence of an actual defect:

- Execute OIDC signature/audience/expiry/role-denial/key-rotation and multi-worker revocation tests with the real private identity configuration.
- Prove Redis authentication, shared rate/revocation/idempotency state, outage fail-closed behavior, and private transport policy.
- Prove PostgreSQL TLS hostname/chain validation, authorization/RLS behavior, audit concurrency/integrity, encrypted backup/WAL/PITR behavior, and denial of unintended plaintext connections.
- Validate Caddy with the exact digest-pinned deployed image and prove only the intended proxy ingress is public; verify diagnostics and Prometheus remain private.
- Build and scan exact production images, validate immutable digest references, SBOM/provenance/attestation, non-root/read-only behavior, and secret mounts.
- Run browser CORS/preflight/conditional-request and authenticated GUI tests; review private screenshots for sensitive content before publication.
- Generate the deterministic repository byte inventory from a clean checkout. The current connector review does not claim literal byte-by-byte coverage of inaccessible runtime/generated/private material.
- Treat any Fernet key that historically entered Git as compromised even though it is absent from the active tree; private deployment owners must retain rotation/revocation evidence where the value was ever used.
- HSTS `preload` response text is not evidence of browser preload-list enrollment; enrollment remains a deliberate domain-owner decision.

# Review cursor / coverage record

The current assessment has inspected and cross-referenced the six baseline security documents; API authentication, authorization, middleware, operations, synchronous service execution, OIDC, rate limiting, secret authority, log redaction, production Docker/Compose/Caddy, CI/hardening workflows, GUI launcher/access control/runtime/application boundaries, the legacy GUI server entry point, report-child network validation, and the directly relevant regression tests. The assessment has not represented a complete local filesystem byte inventory, private deployment, live provider environment, browser session, container runtime, or external identity system as examined when those surfaces are unavailable through the repository connector.

# Updating this ledger

When a new concern is found, normalize it against stable IDs here and in the tombstone before creating a new record. Record the security domain, severity reasoning, exact affected paths/functions, source provenance, attack/failure preconditions, current controls, evidence, remediation and verification requirements. After remediation, keep the finding here as **Verification Pending** until the original condition has been reconstructed and denied by appropriate tests; only then remove it from this file and append the complete lifecycle to the tombstone.
