# Wilson Eval3ngine Current Status

**Package version:** `0.1.0`  
**Project stage:** **active evaluation platform / pre-production assurance**  
**Production certification status:** **not automatically established by repository source**

This page is the current status authority for public documentation. It exists to prevent historical planning language, old point-in-time test reports, or the original deterministic vertical slice from being mistaken for the state of the entire repository.

## The important correction: “foundation” is a lane, not the whole project

The repository still contains names such as `examples/experiments/foundation.yaml`, `we3.foundation_result.v1`, and comments/docstrings referring to the original foundation runner. Those names describe the deterministic local/CI vertical slice that established the first complete evaluation path; they do not accurately describe the maturity of the whole current codebase.

Since that slice was created, the repository has accumulated production-oriented provider adapters, durable PostgreSQL scheduling, human review/adjudication, encrypted evidence storage, OIDC/project security controls, telemetry, backup/recovery, hardened deployment material, browser/operator controls, and a certification orchestration subsystem. The correct project-level description is therefore **an active evaluation platform in pre-production assurance**, with a retained deterministic local foundation lane.

The version remains `0.1.0` because that is the package's declared semantic version in `pyproject.toml`. A low semantic version is not, by itself, evidence that only foundation code exists; conversely, a large amount of implemented code is not, by itself, evidence that a particular production deployment is certified.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Implemented** | A concrete source implementation exists in the repository. |
| **Integrated** | The capability is composed into at least one supported execution/deployment path. |
| **Local-lane exercised** | The deterministic local path uses the capability directly. |
| **Provisional** | Implementation exists, but calibration, statistical reference work, policy approval, or other evidence is incomplete. |
| **Runtime assurance required** | Source exists, but the production claim depends on the target environment and executed evidence. |
| **Historical** | Useful provenance or planning material that is not current product truth. |

## Capability matrix

| Capability | Current repository status | What that does and does not mean |
|---|---|---|
| Versioned experiment/dataset contracts | **Implemented / local-lane exercised** | Schema, identity, split, and dataset-hash checks are part of the synchronous path. Production datasets still require governance and approval. |
| Expectation compilation before execution | **Implemented / local-lane exercised** | The expected treatment is established before provider output is seen. |
| Deterministic mock provider | **Implemented / local-lane exercised** | Supports credential-free local/CI runs and failure simulation. |
| Azure OpenAI adapter | **Implemented** | Real use still requires authorized endpoint, credentials, capability validation, and runtime evidence. |
| Anthropic adapter | **Implemented** | Real use still requires authorized endpoint/credentials and provider-specific validation. |
| Ollama adapter | **Implemented** | Local/private destination access is policy constrained and opt-in where required. |
| CLI-backed provider adapters | **Implemented** | Availability depends on locally installed/authenticated CLIs and operating-system identity. |
| Provider retry/attempt evidence | **Implemented / local-lane exercised** | Attempts and reliability outcomes remain distinct from behavioral labels. |
| Five-outcome grading | **Implemented / local-lane exercised** | Foundation deterministic grading is useful for the local lane; certification-grade calibration must be supported by evidence for the target program. |
| Human review/adjudication workflow | **Implemented** | Includes dual review, recusal, abstention, disagreement, and adjudication primitives; a live review operation still needs identities, staffing, policy, SLA, and integration evidence. |
| Metric snapshots | **Implemented / local-lane exercised** | Results retain numerator, denominator, exclusions, method/version, and run population. |
| Wilson score intervals | **Implemented / local-lane exercised** | Core proportion uncertainty is present. |
| Cross-run comparisons and drift | **Implemented with provisional portions** | Comparison eligibility/drift primitives exist; one comparison p-value path remains a placeholder pending bootstrap/reference completion. |
| Prompt-family independence accounting | **Provisional in one snapshot path** | `create_metric_snapshot` currently notes that prompt-family count may use run count as an approximation; certification statistics must not overclaim independence from this path. |
| Release gate engine | **Implemented / local-lane exercised** | Includes minimum support, pass/warn/indeterminate/block precedence, and critical unsafe-compliance blocking. Threshold authority still depends on approved benchmark/use-case policy. |
| Content-addressed local evidence | **Implemented / local-lane exercised** | Strong traceability for development/CI; local filesystem storage alone is not a managed production immutability control. |
| Encrypted evidence store | **Implemented** | AES-256-GCM envelope-encryption/retention interfaces exist; the development `LocalKMSClient` is explicitly not a production KMS authority. |
| Audit chain | **Implemented** | External checkpoint/trust operation depends on deployment configuration and evidence. |
| Ed25519 dossier signing | **Implemented / local-lane exercised** | Development key generation is not equivalent to managed production signing identity/key custody. |
| Durable PostgreSQL scheduler | **Implemented** | Fenced leases, heartbeats, retry/dead-letter behavior, and reconciliation code exist; target workload/runtime behavior still needs execution evidence. |
| OIDC/project authorization | **Implemented** | Real issuer/JWKS, claims, role mapping, RLS/object policy, revocation, and negative authorization results are environment-specific. |
| GUI loopback boundary | **Implemented / integrated in official launcher** | Direct non-loopback binding is rejected; authenticated remote proxying is a separate deployment responsibility. |
| Provider destination policy | **Implemented / GUI integrated** | Application controls reduce risk; network-level egress assurance and deployment allowlists remain environment responsibilities. |
| GUI secret transport | **Implemented in supported POSIX official path** | One-shot FIFO avoids the historical regular plaintext temp file; non-POSIX secure transport remains a platform-specific concern. |
| Streaming request-body limit | **Implemented** | Actual ASGI bytes are counted rather than trusting `Content-Length`; runtime deployment tests remain relevant. |
| Telemetry/tracing | **Implemented** | Production SLOs, alerts, tracing backends, and evidence must be validated in the running environment. |
| Backup/recovery | **Implemented modules and workflows** | A real recovery claim requires executed restore/PITR/object-reconciliation evidence. |
| Production Compose/Caddy topology | **Implemented templates** | Only intended ingress is published in the template; source configuration does not prove deployed firewall/network behavior. |
| Certification requirements/orchestration | **Implemented** | Certification categories and blocking requirements exist; a release can only pass when the required evidence is actually satisfied. |
| Production certification of a specific deployment | **Runtime assurance required** | The public repository cannot establish private identities, secrets, provider destinations, certificates, network policy, restores, scans, or real runtime results by itself. |

## What the deterministic local lane proves

The local example proves that the core measurement contract can be exercised without external credentials: load/validate the manifest and dataset, establish expectations, execute deterministic provider behavior, preserve evidence, grade responses, compute metrics and Wilson intervals, evaluate gates, build reports/dossiers, and verify signatures. This path is intentionally small enough to be repeatable in development and CI.

It does **not** exercise every provider, production scheduler, external KMS/secret manager, organizational IdP, private egress boundary, multi-user review operation, real backup service, production certificates, or target deployment. That distinction is why the lane remains useful even though the platform around it has grown substantially.

## Known implementation limitations that must stay visible

### Statistical comparison completion

`src/wilson_eval3ngine/metrics/engine.py` contains comparison primitives, but its current comparison function uses a placeholder p-value rather than a completed bootstrap/reference significance calculation. The same module notes that one `create_metric_snapshot` path currently approximates prompt-family count using run count, so certification claims about independent prompt-family support must use a validated path and reference evidence rather than relying on that approximation.

### Calibration and threshold authority

The existence of deterministic grading and gate code does not make every grader or threshold certification-approved. Grader calibration, benchmark composition, severity/category policy, minimum support, and release thresholds must be validated and approved for the specific evaluation program using them.

### Local versus managed evidence controls

Content-addressed local artifacts, local audit data, development signing keys, and the development KMS implementation are appropriate for deterministic development workflows but are not substitutes for managed production storage, key custody, retention/legal hold, secret management, and external audit/checkpoint controls. The broader codebase provides interfaces and implementations for stronger controls, while the actual production authority remains deployment-specific.

### GUI identity boundary

The official GUI is protected primarily by its loopback binding and optional access-control composition, not by pretending every local desktop session is a production multi-user security boundary. A remotely exposed GUI requires an authenticated, authorized TLS proxy and must be validated as part of the target deployment.

## Security assessment status

`docs/security/MASTER_SECURITY_ASSESSMENT.md` is a valuable **point-in-time security assessment dated 2026-08-01**. It records implementation and residual risks for the branch/head reviewed at that time, so later code and documentation should not present its “runtime pending” statements as if they were freshly re-executed on every current commit.

`docs/security/PRIVATE_RUNTIME_ASSURANCE.md` remains the stronger enduring contract for what the public repository can prove versus what must be verified privately. Production validation should preserve raw private evidence outside the public repository and publish only bounded outcomes/fingerprints where appropriate.

## Historical documents

The original `docs/Plans_/` and `docs/08-planning/Plans_/` material remains in place by design. Those files record the plan/TODO process used to build the platform and should not be rewritten to mimic current documentation; current readers should use this file, the README, Features, Architecture, and operations/security guides for present-tense claims.

Superseded public-facing documents are stored under `.archive/documentation/`. Historical Phase-1 “all tests passing” reports are evidence about that earlier snapshot, not proof that the latest branch or a production deployment has passed the same matrix.

## Current release statement

A concise, accurate public statement is:

> **Wilson Eval3ngine `0.1.0` is an active evidence-first LLM evaluation platform in pre-production assurance. The deterministic local foundation lane is functional for development/CI, while the repository also contains substantial production-oriented provider, scheduling, review, security, evidence, operations, and certification capabilities. Production certification is evidence-dependent and must be established by executing the required repository and private-runtime assurance checks for the exact release/deployment being approved.**

See [Architecture](ARCHITECTURE.md) for how these components fit together and [Getting Started](GETTING_STARTED.md) for the fastest way to exercise the local path.
