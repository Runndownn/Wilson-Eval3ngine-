# Security Policy

## Current security position

Wilson Eval3ngine `0.2.0` is an active evaluation platform in pre-production assurance. Source contains substantial identity, authorization, evidence-protection, deployment, recovery, and security controls, but repository implementation alone is not production certification.

There are exactly two authoritative security-finding records:

- [`docs/security/MASTER-SECURITY-LIVING-DOCUMENT.md`](docs/security/MASTER-SECURITY-LIVING-DOCUMENT.md) answers **what known security concerns still require attention**.
- [`docs/MASTER-TOMBSTONE-SECURITY.md`](docs/MASTER-TOMBSTONE-SECURITY.md) answers **what security concerns existed historically, what changed, and how closure was justified**.

Older point-in-time assessments were ingested, normalized, and preserved byte-for-byte under `.archive/security/2026-08-22/source-documents/`. They are provenance, not current finding-state authorities. A finding does not remain active merely because an old report says it exists, and it does not move to the tombstone merely because a patch or completion label exists.

## Finding lifecycle

Security findings follow one lifecycle regardless of whether they originate from a human review, scanner, test, incident, Codex-style agent, or another AI system:

`Discover → Normalize → Classify → Verify → Record Active → Investigate → Remediate → Test → Re-verify → Tombstone`

The living ledger contains only **Active — Verified**, **Active — Partially Remediated**, and **Active — Verification Pending** records. The tombstone contains **Resolved — Remediated and Verified**, **Resolved — No Longer Applicable**, **Resolved — Disproven**, and **Resolved — Duplicate or Consolidated** records. Stable IDs and provenance follow a finding throughout its lifetime.

An empty living ledger means no known unresolved findings remain within the scope/evidence of the latest completed assessment. It is not proof that undiscovered vulnerabilities do not exist.

## Security invariants

- Raw model/provider content is untrusted and must remain inert at rendering and export boundaries.
- Reliability failures are not behavioral classifications.
- Development authentication is not a production identity authority.
- CORS is not authentication, `jti` is not bearer sender-binding, and structured logs are not the durable security audit ledger.
- Local filesystem artifacts are not automatically production immutability controls.
- Local encrypted credential storage is not a production secret authority.
- Production secret values belong in approved external/mounted authorities, not Git, ordinary logs, issues, PR text, or regular plaintext child-key files.
- The supported operator GUI is loopback/local by default. A non-loopback listener must use the explicit remote-bind decision **and** a validated OIDC access profile; remote-bind permission never disables authentication.
- Application provider-destination checks do not replace host/container egress controls.
- Graders must not inherit target-provider credentials or live tools by default.
- A Boolean metadata field is not proof of encryption, integrity, backup success, or runtime enforcement.
- Repository code/configuration can prove implementation/composition; only executed and retained evidence can prove runtime/certification behavior.

## Authentication, token handling, and authorization

The production-oriented API validates OIDC issuer, audience, allowed signing algorithm/key type, signed time claims, project/role/subject/JWT ID, and MFA evidence. Staging/production compose a shared Redis-backed revocation authority, and self-revocation persists for the token's complete remaining signed lifetime plus skew.

Ordinary bearer credentials are still bearer credentials: a stolen valid token can be reused until expiry/revocation unless the deployment adopts a sender-constrained mechanism. That current limitation is tracked in the living ledger rather than being hidden behind `jti` terminology.

Authorization uses exact canonical role strings, preserving workload namespaces such as `workload:api`. Supported project-scoped API routes pass through the shared matrix, and required authorization audit is persisted before an allowed protected action proceeds. Audit persistence failure at that boundary fails closed with a bounded service-unavailable response.

## Operator GUI security

The supported launcher is `we3-gui-start`. Loopback local mode grants the local operator a synthetic administrative identity and therefore depends on the listener remaining loopback-only. The remediation branch explicitly couples every non-loopback/wildcard bind to `WE3_GUI_ACCESS_MODE=oidc`; `WE3_GUI_ALLOW_REMOTE_BIND=1` authorizes only the socket exposure decision.

The GUI can administer endpoints, credentials, models, jobs, charts, reports, exports, and deletion, so compromise of its process/OS identity remains security-significant. The legacy compatibility module still creates an independently startable FastAPI application; that alternate-entry-point condition remains an active finding until direct legacy startup is removed or equivalently protected.

## Provider and egress security

The modern GUI provider client resolves and revalidates destinations before dispatch, rejects unsafe address classes, disables redirects, verifies TLS, and ignores proxy environment variables. Intentional loopback/private providers require explicit local-provider enablement.

The report-generation child still carries a separate older URL/DNS policy rather than the same authoritative policy object. That divergence, including fail-open DNS behavior in the historical child validator and lack of one shared connection-peer/redirect contract, remains an active finding. Production network egress must therefore remain default-deny/allowlisted while the code-level policy is unified.

## Secrets and child-process transport

A historical Fernet key entered repository history and must always be treated as compromised even though it has been removed from the active tree. Production uses the external secret-backend boundary. The supported POSIX keyed report path uses a one-shot FIFO rather than a regular plaintext credential file; unsupported non-POSIX production platforms require a reviewed private transport plugin and fail closed without one.

Sensitive logging uses centralized field, Bearer, assignment, credential-URL, and query-parameter redaction. A remediation in the current security branch closes an identified gap where secret-bearing URL query values could survive in otherwise ordinary string fields; that finding remains **Verification Pending** until the relevant tests/CI pass.

## API request and filesystem boundaries

The API enforces actual streamed request bytes, content types, bounded security metadata, exact CORS policy, distributed rate limiting, authentication, authorization, and project context. Production/staging require Redis for authoritative distributed rate, revocation, and idempotency state and fail closed if that authority is unavailable.

The retained synchronous `/v1/experiments:run` lane accepts filesystem paths because it exists for local development, deterministic CI, and recovery diagnostics. The current security branch disables that lane in staging/production before route side effects so a remote authenticated evaluation role cannot turn API request fields into arbitrary service-account filesystem read/write/signing-key authority. Durable production execution belongs to the scheduler.

## Browser and ingress protections

Caddy is the provided public ingress authority. The production topology publishes only Caddy, keeps API/database/cache/Prometheus/Grafana on purpose-specific internal networks, overwrites forwarding identity, and denies public diagnostics/schema routes. `WE3_TRUSTED_PROXY_CIDRS` must contain only the private proxy-to-API ranges selected by the deployment.

The API uses exact browser-origin and preflight allowlists; wildcard credentialed origins are not supported. Current production authentication is an explicit Authorization bearer header, so classic ambient-cookie CSRF is not the primary credential threat. A bound CSRF primitive exists for any future ambient session path.

Security headers include CSP, COOP, CORP, COEP, frame/MIME/referrer/permissions/cache controls, and HSTS with `includeSubDomains; preload`. Header text is not proof that a domain is enrolled in browser preload lists.

## Evidence, cryptography, persistence, and recovery

Evaluation evidence uses content addressing, hash-linked database audit, and Ed25519 dossier integrity. The broader artifact layer includes envelope-encryption behavior; development key implementations are not production key custody.

`src/wilson_eval3ngine/backup/` contains encrypted PostgreSQL physical-backup/WAL/PITR implementation with signed manifests, identity/continuity checks, recovery baselines, restore/reconciliation logic, and audit-chain checks. Real cadence, retention, destructive restore success, target-time reachability and measured RPO/RTO require executed target-environment evidence.

## Supply chain and CI

The repository defines Dependabot, repository-native supply-chain checks, Bandit, `pip-audit`, Trivy workflow scanning, pinned GitHub Action revisions, package/build gates, provenance attestation, browser/security contracts, secure-Compose validation and recovery lanes. A workflow definition is not a passing result; security finding closure for a branch requires the relevant exact-revision run or another retained independent verification artifact.

## Private runtime assurance

Private production facts—real identities, issuer configuration, certificates, network ranges, provider destinations/allowlists, KMS/object metadata, raw scanner output, packet captures, test accounts and restore topology—must remain outside the public repository. The detailed historical private-assurance contract is preserved in `.archive/security/2026-08-22/source-documents/PRIVATE_RUNTIME_ASSURANCE.md`; its still-applicable proof requirements are summarized as **Assurance obligations** in the living ledger.

## Reporting vulnerabilities

Report suspected vulnerabilities privately to the repository owner or the organization's approved security intake. Include the affected version/commit, a minimal synthetic reproduction, realistic impact/preconditions, and suggested containment when possible. Do not include real secrets, private topology, harmful evidence, or sensitive user/provider data in public issue trackers.
