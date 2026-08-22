# Wilson Eval3ngine — Master Security Tombstone

## Purpose and authority

This document is the authoritative historical record for Wilson Eval3ngine security findings that left the active ledger after an evidence-backed disposition. It preserves what was reported, what the actual security condition was, where it applied, how the implementation changed, why closure was justified, and what assumptions remain. Current unresolved work belongs only in `docs/security/MASTER-SECURITY-LIVING-DOCUMENT.md`.

A tombstone entry is not proof that a related vulnerability can never recur. If a closed condition reappears, the new or reopened active record must link back to the stable historical ID and explain the regression.

## Historical source provenance

The 2026-08-22 consolidation ingested the six documents that previously occupied `docs/security/`. Their original bytes are retained under the security archive; the baseline Git blob object IDs below provide content-addressed provenance within this repository.

| Historical source | Git blob object ID | Assessment context |
|---|---|---|
| `MASTER_SECURITY_ASSESSMENT.md` | `71b5c1d1a6a653cde050e8f107229b8c4eb50e79` | 2026-08-01 master hardening report |
| `PRIVATE_RUNTIME_ASSURANCE.md` | `0fd875d5d77a14ed70331bb10806e1c3e44e82b4` | public/private runtime-assurance contract |
| `SECURITY_ASSESSMENT.md` | `ec17e96fd6832201c79dfbece84c890fc90b662c` | 2026-07-30 twelve-finding assessment |
| `SECURITY_REASSESSMENT_2026-08-22.md` | `3f515c803063728781dd42b922175435b0814a68` | 2026-08-22 source reassessment and second-order defects |
| `TECHNICAL_ASSESSMENT_BRANCH_INTEGRATION.md` | `ecb1bf0f69d83dff3d75a7eb29dff898fa5d40b1` | 2026-08-01 branch/private-assurance integration report |
| `Wilson-Eval3ngine-dev-mid-security-quality-plan.md` | `2e73a29bdf72ae2822a73f57c0924f4ecca7e68c` | 2026-08-01 detailed hardening plan |

These are Git object fingerprints, not a claim that an independent SHA-256 digest was calculated during the connector-only consolidation. The repository's deterministic inventory system can produce SHA-256 byte evidence from a clean checkout as an assurance artifact.

## Provenance normalization map

Historical documents often described the same root cause at different stages. The following aliases were consolidated rather than preserved as duplicate active findings:

| Historical label | Canonical lifecycle record |
|---|---|
| July finding 1; reassessment discussion of `jti`; SR-2026-002 | `WE3-SEC-0001` for missing revocation/shared authority; sender-constrained replay limitation continues separately as active `WE3-SEC-0021` |
| July finding 2; SR-2026-001 | `WE3-SEC-0002` |
| July finding 3 | `WE3-SEC-0003` |
| July finding 4 | `WE3-SEC-0004` |
| July finding 5 | `WE3-SEC-0005` |
| July finding 6 | `WE3-SEC-0006` |
| July finding 7 | `WE3-SEC-0007` |
| July finding 8; SR-2026-005 | `WE3-SEC-0008` |
| July finding 9 | `WE3-SEC-0009` |
| July finding 10 | `WE3-SEC-0010` |
| July finding 11 | `WE3-SEC-0011` |
| July finding 12; Aug-01 SEC-0006 | `WE3-SEC-0012` and `WE3-SEC-0016` for the broader release-integrity problem |
| Aug-01 SEC-0001 | `WE3-SEC-0013`; a later remote-bind/local-identity regression is tracked as active `WE3-SEC-0024` until independently verified |
| Aug-01 SEC-0002; SR-2026-006/007 portions | `WE3-SEC-0014` and `WE3-SEC-0017` |
| Aug-01 SEC-0003 | `WE3-SEC-0015` |
| Aug-01 SEC-0004 | Remains partially open as active `WE3-SEC-0022`; no false tombstone was created |
| Aug-01 SEC-0005 | `WE3-SEC-0018` |
| Aug-01 SEC-0007 | `WE3-SEC-0017` |
| Aug-01 SEC-0008 | `WE3-SEC-0019` |
| Aug-01 SEC-0009 | `WE3-SEC-0020` |
| Aug-01 SEC-0010 | `WE3-SEC-0028` |
| SR-2026-003, SR-2026-004, SR-2026-008 | `WE3-SEC-0029` authorization-boundary consolidation |
| Technical GAP-01 (`::1`) | `WE3-SEC-0030`, closed as a security-vulnerability classification but retained as a corrected security-policy compatibility defect |
| Technical GAP-02 | Current regression/remediation is active as `WE3-SEC-0026` until branch verification; it is not tombstoned yet |
| Technical GAP-03 / absent CI result | Assurance evidence state, not an exploitable finding; retained in source provenance and living-ledger assurance obligations |

# Resolved findings

## WE3-SEC-0001 — OIDC lacked JWT-ID validation and revocation authority

**Domain:** Authentication and token lifecycle  
**Original risk:** High  
**Final classification:** High historical defect; ordinary bearer replay is a separate current limitation  
**Closure:** Resolved — Remediated and Verified in source/tests; deployment runtime remains an assurance obligation  
**Original source:** `SECURITY_ASSESSMENT.md` finding 1; later SR-2026-002.

**Original condition.** The July implementation validated signature, issuer, audience and identity claims but did not require a bounded `jti` or maintain an application revocation authority. A stolen token could not be invalidated by the application before expiry. Later partial work risked recreating isolated revocation lists by constructing authenticators at request scope.

**Root cause.** Authentication treated signed-token validity as sufficient session lifecycle control and did not compose revocation as shared security state across workers.

**Remediation.** `security/oidc.py` now requires and validates `jti`, `sub`, `exp`, `iat`, issuer, audience, algorithm/key type and MFA evidence; `TokenRevocationList` can use Redis; API composition creates an application-lifetime OIDC authenticator bound to production Redis; self-revocation exists; the revocation TTL covers the token's complete remaining signed lifetime plus skew; expired JWKS cache material fails closed after refresh failure.

**Verification basis.** Source trace confirms the shared object is installed during API composition and authentication prefers application state. Unit/security tests exercise claims, revocation and composition. The 2026-08-22 reassessment independently distinguished this control from sender binding. Real multi-worker/IdP runtime verification remains required by the private assurance contract.

**Remaining assumption.** An unrevoked ordinary bearer token remains replayable until expiry/revocation. That separate property is active as `WE3-SEC-0021` rather than falsely extending this old finding.

## WE3-SEC-0002 — Rate limiting was process-local and later trusted unsafe request identity

**Domain:** Abuse prevention / distributed security state  
**Original risk:** High  
**Closure:** Resolved — Remediated and Verified in source/tests; deployment runtime evidence required  
**Sources:** July finding 2; SR-2026-001.

The original limiter stored sliding-window state in one Python process, so horizontally scaled instances did not share a limit. A later Redis implementation still needed hardening because blindly trusted `X-Forwarded-For`, caller-selected project metadata, privacy-truncated client addresses, or Redis fail-open behavior could undermine the control.

The current `security/rate_limit.py` uses an atomic Redis Lua sliding window, a hash of the complete normalized enforcement address, and distinct privacy-reduced log labels. Forwarded addresses are used only when the direct peer is inside configured trusted proxy CIDRs; pre-authentication buckets do not depend on caller-controlled project headers. Assurance environments require Redis and return a bounded 503 when distributed rate authority is unavailable; development intentionally retains an in-memory fallback. Caddy overwrites forwarding identity at public ingress.

Closure is based on source composition plus dedicated rate/proxy tests. The exact production CIDR and Redis topology remain private deployment facts and therefore runtime assurance, not unresolved source defects.

## WE3-SEC-0003 — “No CSRF” finding was over-broad for explicit Bearer authentication

**Domain:** Browser request integrity  
**Original risk:** High  
**Final risk:** Not applicable to the current explicit Bearer-header credential model; defense-in-depth retained  
**Closure:** Resolved — No Longer Applicable to current production credential transport  
**Source:** July finding 3.

The historical report treated the absence of a CSRF token as a current High vulnerability even though production identity is explicitly carried in the `Authorization` header rather than automatically attached browser cookies. Classic CSRF depends on ambient credentials and therefore was not demonstrated under the stated production path.

The repository nonetheless implements a bound CSRF control for any state-changing path that uses ambient session/cookie credentials. Current Bearer OIDC and development-header authentication are intentionally exempt, while exact CORS policy independently constrains browser origins. Closure is a threat-model correction, not a claim that cookie-based authentication could be added without revisiting CSRF.

## WE3-SEC-0004 — Raw operation exception text could reach client-visible state

**Domain:** Error handling / information disclosure  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified  
**Source:** July finding 4.

The earlier operation executor persisted truncated `str(exc)` content that could include host paths, backend details, or other diagnostics later returned through operation status. Current operation failure handling stores a bounded error code plus `ErrorSanitizer.sanitize_exception`; public middleware also emits stable error envelopes and logs exception class rather than raw client-facing internals. Regression coverage verifies safe errors. Full internal diagnostics remain server-side.

## WE3-SEC-0005 — A Fernet key was committed to repository history

**Domain:** Secrets and credentials  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified for active repository state  
**Source:** July finding 5; reassessment residual history note.

A Fernet key existed in repository content, was later archived, and therefore had to be treated as compromised. Commit `6350d867fd59d4c21e925899c2fe53cfa7949e96` removed the archived key and added ignore protection; commit `2062246372f26fde3e12518f8858c8b03c2de211` further confined the legacy Fernet manager to development and stopped key replication. Production secret authority is now external/mounted via `security/secrets_backend.py` and `api/secure_entrypoint.py`.

Removal does not erase disclosure from Git history. The closure applies to active-tree exposure and production-source design only. Any deployment that ever used the historical value must keep it revoked/rotated; private rotation evidence is an assurance obligation and the tombstone intentionally preserves that caveat.

## WE3-SEC-0006 — Missing COOP/CORP/COEP response policy

**Domain:** Browser response hardening  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified in source  
**Source:** July finding 6.

The API and public Caddy response policy now include Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy and Cross-Origin-Embedder-Policy alongside CSP, frame, MIME, referrer, permissions, cache and transport policy. Source tests check security composition; browser compatibility remains part of runtime/browser assurance rather than an active missing-control finding.

## WE3-SEC-0007 — No explicit CORS enforcement

**Domain:** Browser/API boundary  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified  
**Source:** July finding 7.

`StrictCORSMiddleware` uses an exact origin allowlist, rejects wildcard origins, validates requested methods and headers during preflight, and rejects a disallowed `Origin` before route side effects. Credentialed CORS is disabled by default for the explicit Bearer-header model. `If-Match` is included in the conditional-request contract. CORS remains defense in depth, not authentication.

## WE3-SEC-0008 — API authentication/authorization audit evidence was not durably persisted

**Domain:** Auditability / authorization  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified in source/tests  
**Sources:** July finding 8; SR-2026-005.

The historical API primarily emitted structured operational logs despite the presence of a hash-linked `AuditLedger`. A later compatibility audit helper also used “fail closed” language while swallowing persistence errors.

Current authentication persists request intent to `AuditLedger` before protected route side effects. `authorization_audit_scope` installs a request-scoped callback around exact authorization decisions; persistence failure raises a dedicated unavailable condition so protected actions fail with a bounded service-unavailable result instead of continuing silently. Compatibility best-effort logging is explicitly distinguished from required audit persistence. Real PostgreSQL concurrency/outage testing remains part of private assurance.

## WE3-SEC-0009 — Request content type was not validated

**Domain:** Input/parser boundary  
**Original risk:** Low  
**Closure:** Resolved — Remediated and Verified  
**Source:** July finding 9.

The supported middleware composition now validates media types for state-changing JSON/form routes and returns a bounded 415 for mismatches before route parsing/side effects. The allowed content-type surface is explicit and covered by API security tests.

## WE3-SEC-0010 — Idempotency keys lacked bounded format and authoritative intent binding

**Domain:** Concurrency / state integrity  
**Original risk:** Low, later strengthened as a distributed-integrity control  
**Closure:** Resolved — Remediated and Verified in source/tests  
**Source:** July finding 10.

Keys are now length/format validated and project scoped. Assurance deployments use Redis and atomically establish a binding between project, key, request-intent hash and operation ID; reuse for a different intent is rejected. Security-state failure is fail-closed in assurance environments. The synchronous operation registry remains process-local, but a durable binding whose local operation state is gone is not replayed as new work; the API returns a safe conflict/unavailable result.

## WE3-SEC-0011 — HSTS header lacked the `preload` token

**Domain:** Transport/browser policy  
**Original risk:** Low  
**Closure:** Resolved — Remediated in source; operational enrollment deliberately excluded  
**Source:** July finding 11.

API/Caddy policy now emits `max-age=31536000; includeSubDomains; preload`. The source change closes only the header finding. Browser preload-list enrollment is a separate domain-owner action with organization-wide subdomain and rollback implications; the repository correctly does not claim enrollment based on header text.

## WE3-SEC-0012 — Dependency/security scanning was absent from the automated pipeline

**Domain:** Supply chain / CI  
**Original risk:** Low  
**Closure:** Resolved — Remediated in repository controls  
**Source:** July finding 12.

Current CI/hardening workflows include repository-native supply-chain scanning, Trivy high/critical filesystem scanning, focused security regression suites, package build checks, and Dependabot configuration. The Makefile/security tooling also provides a manual lane. Workflow definition is not equivalent to a passed run; each release still requires its own CI evidence.

## WE3-SEC-0013 — Supported GUI could expose an unauthenticated remote administrative control plane

**Domain:** GUI authentication and network exposure  
**Original risk:** High  
**Closure:** Resolved — Remediated and Verified for the original supported-path condition  
**Source:** Aug-01 SEC-0001.

The original GUI had state-changing administrative REST/WebSocket operations and allowed non-loopback binding without a true identity boundary. The modern architecture introduced `GUIIdentityMiddleware`, an explicit local-vs-OIDC access profile, bounded Bearer parsing/role policy, and a loopback-default launcher. The original condition was removed from the supported path.

A later adjacency review found that the separate `WE3_GUI_ALLOW_REMOTE_BIND` opt-in could still be combined with default local synthetic identity. That is a regression of the same security goal but a distinct implementation condition and is therefore active as `WE3-SEC-0024` until its branch remediation passes independent tests. The legacy `server:app` alternate-start condition is active separately as `WE3-SEC-0023`.

## WE3-SEC-0014 — Production services and weak defaults could bypass the intended TLS proxy boundary

**Domain:** Deployment/network segmentation  
**Original risk:** High  
**Closure:** Resolved — Remediated and Verified in source/configuration; runtime topology must still be proven  
**Sources:** Aug-01 SEC-0002; SR-2026-007.

Earlier Compose definitions published internal API/monitoring surfaces and contained weak fallback secrets, allowing access around Caddy. Current production/secure Compose requires secret files and digest-pinned images, publishes only Caddy, segments ingress/data/observability/egress networks, authenticates Redis, enables PostgreSQL TLS material, keeps Prometheus internal, and uses Caddy to deny public diagnostics/schema paths and overwrite forwarding identity. Synthetic Compose topology tests enforce these definitions. A real deployment remains subject to private network/TLS verification.

## WE3-SEC-0015 — Report subprocess credentials were written to plaintext regular temporary files

**Domain:** Secrets / process boundary  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified in supported launcher design  
**Source:** Aug-01 SEC-0003.

The original child handoff wrote decrypted provider credentials into a mode-0600 regular file. Mode 0600 protects against other OS users but does not make plaintext at rest disappear and remains readable to the same service account/backup/crash tooling. The supported launcher now replaces the compatibility helper with a one-shot POSIX FIFO transport created under restrictive directory permissions, bounds secret size/read count, clears mutable parent buffers, and cleans up on completion/cancellation. Unsupported non-POSIX production platforms require a reviewed private transport plugin and fail closed without one.

The old `api_key_vault.py` compatibility helpers are not promoted as a production secret authority. Production application secrets use the external secret-backend contract.

## WE3-SEC-0016 — CI/release-integrity labels exceeded actual enforcement

**Domain:** Build/CI/CD integrity  
**Original risk:** High  
**Closure:** Resolved — Remediated in current workflow design  
**Source:** Aug-01 SEC-0006.

The historical pipeline suppressed mandatory lint failures, had incomplete branch coverage, called a single hash “determinism,” and described non-cryptographic digest handling as signing. Current CI uses pinned action commits, non-suppressed lint/test/coverage/build gates, repository-native and Trivy security scanning, tested distribution artifacts, GitHub build-provenance attestation on main, focused hardening workflows, browser/security/secure-compose contracts and recovery lanes. Each commit/release still requires an actual successful run; that is evidence state rather than a permanent source finding.

## WE3-SEC-0017 — Production image contract was internally inconsistent

**Domain:** Container/build integrity  
**Original risk:** High  
**Closure:** Resolved — Remediated and source-verified  
**Sources:** Aug-01 SEC-0007; SR-2026-006.

The earlier image installed the project before source was copied and attempted to run undeclared Gunicorn, later also risking a Redis-runtime dependency mismatch despite production security state requiring Redis. Current `Dockerfile.prod` builds a complete project wheel, constructs a runtime wheelhouse including PostgreSQL/backup/Redis dependencies, installs offline into the runtime stage, runs as non-root, and starts the declared secure Uvicorn entry point. The base image must be an immutable caller-supplied digest reference. Exact image build/scan/readiness remains release assurance.

## WE3-SEC-0018 — Report geometry and chart windows violated required operator containment contracts

**Domain:** Operator UX / evidence presentation  
**Original risk:** Medium in Aug-01 report  
**Final risk:** Primarily reliability/usability, not a standalone confidentiality/integrity exploit under reviewed conditions  
**Closure:** Resolved — Remediated; reclassified outside active vulnerability ledger  
**Source:** Aug-01 SEC-0005.

The finding covered non-deterministic report-card columns and chart windows that could be dragged/resized outside the visible viewport. UX6/browser work added exact desktop column rules, responsive collapse, viewport clamping/reset and accessibility tests. Because investigation did not establish an independent privilege, confidentiality or data-integrity violation from layout alone, it is preserved here as security-adjacent operational history rather than kept as an active vulnerability.

## WE3-SEC-0019 — Security and production-readiness documentation was stale and contradictory

**Domain:** Governance / security knowledge integrity  
**Original risk:** Medium  
**Closure:** Resolved — Superseded by the living-ledger/tombstone control system  
**Source:** Aug-01 SEC-0008 and subsequent reassessment drift.

Point-in-time reports accumulated findings, remediation checkmarks, stale branch facts and mutually inconsistent “current” statements. This consolidation eliminates document boundaries as finding boundaries. The authoritative active state is now `docs/security/MASTER-SECURITY-LIVING-DOCUMENT.md`; resolved history is here; original reports are preserved only as immutable provenance in the security archive. A security document being old is no longer sufficient to keep its claims active.

## WE3-SEC-0020 — Body-size enforcement trusted declared `Content-Length`

**Domain:** Input/resource exhaustion  
**Original risk:** Medium  
**Closure:** Resolved — Remediated and Verified in source/tests  
**Source:** Aug-01 SEC-0009.

A client could omit or misstate `Content-Length` while streaming more bytes to downstream parsing. `StreamingBodyLimitMiddleware` now counts actual ASGI body bytes independently of the header, rejects malformed/conflicting length metadata and over-limit streams with stable responses, and covers chunked/missing-length boundary cases in raw ASGI regression tests.

## WE3-SEC-0028 — API-key/local-model operations guide encouraged obsolete or overclaimed secret handling

**Domain:** Operational documentation / secrets  
**Original risk:** Medium  
**Closure:** Resolved — Documentation/architecture superseded  
**Source:** Aug-01 SEC-0010.

The older guide mixed environment-specific topology, plaintext environment/token-file workflows, a broken tilde expansion command, an obsolete GUI entry point and claims stronger than the same-account file-vault threat model. Current docs separate local development from production authority, use the supported launcher and external-secret model, and explicitly state the residual limits of local encrypted storage. This tombstone keeps the reason the old operational pattern was unsafe so it is not accidentally reintroduced.

## WE3-SEC-0029 — Authorization role/action semantics allowed bypasses, namespace collapse, and privileged fallback

**Domain:** Authorization / privilege boundaries  
**Original risk:** High  
**Closure:** Resolved — Remediated and Verified in source/tests  
**Sources:** SR-2026-003, SR-2026-004, SR-2026-008.

Three second-order defects shared one root problem: authorization was not consistently represented by one exact canonical matrix. Workload roles such as `workload:api` could be normalized incorrectly; core routes could rely only on authenticated context/hard-coded roles; extended actions referenced missing grants; and dossier generation could fall back from `create:dossier` to a broader ordinary-export permission.

Current authorization uses exact canonical role names; core and extended routes enter `check_authorization`; intended start/regrade actions are explicitly granted; generic export permission cannot satisfy dossier authority; and request-scoped required audit records matrix allow/deny decisions. Tests cover workload namespace isolation, route denials, matrix/action consistency and dossier privilege separation. No implicit system-admin bypass is added by merely recognizing a role in OIDC.

## WE3-SEC-0030 — IPv6 loopback was treated as permanently forbidden provider address

**Domain:** Network policy compatibility  
**Original classification:** High gap in the technical assessment  
**Final risk:** Security-control correctness / local availability, not a vulnerability that widened access  
**Closure:** Resolved — Disproven as an exposure; corrected for policy consistency  
**Source:** `TECHNICAL_ASSESSMENT_BRANCH_INTEGRATION.md` GAP-01.

Python's `ipaddress` classifies `::1` as loopback and also as reserved. The GUI egress policy checked `is_reserved` before applying its explicit local-provider opt-in, so an operator who deliberately enabled local providers could still not use IPv6 loopback. This failed closed and therefore did not create SSRF exposure; the old High severity was not supported by realistic security impact.

The living-ledger remediation branch now treats loopback as its own class before the permanent-reserved-range test. `::1` remains denied by default and becomes usable only when `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1`, while link-local, multicast, unspecified and other reserved ranges remain permanently blocked. Targeted regression coverage includes the IPv6 positive and denied-default cases.

# Historical supply-chain remediation note

Commit `6350d867fd59d4c21e925899c2fe53cfa7949e96` also upgraded `cryptography` to a release line addressing the repository's then-recorded 2026 cryptography advisories and added governance/dependency automation. Those package advisories are preserved here as resolved supply-chain history rather than copied into the active ledger without evidence that the currently resolved dependency range is vulnerable. Current releases remain subject to fresh dependency scanning.

# Reopening rules

A tombstoned finding must be reopened or linked to a new regression finding when current evidence again satisfies its threat condition. The new active record should cite this stable ID, identify the regression path and affected release/commit, and must not overwrite or erase this historical closure rationale.
