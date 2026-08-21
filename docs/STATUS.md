# Current Implementation Status

**Status date:** 2026-08-21  
**Package version:** `0.1.0`  
**Release position:** foundation / internal evaluation; **not approved for production certification**

This page is the public documentation source of truth for distinguishing code that exists from behavior that is integrated and runtime-assured.

## Status vocabulary

- **Integrated foundation** — exercised by the current synchronous/local evaluation path.
- **Implemented module** — substantial code exists, but it is not necessarily wired into the foundation path or production-validated.
- **Partial / provisional** — implementation exists with known placeholders, approximations, or missing validation.
- **External assurance required** — repository code cannot prove the deployment property.

## Capability matrix

| Capability | Current state | Important boundary |
|---|---|---|
| Contract validation | **Integrated foundation** | Versioned Pydantic experiment/dataset/case contracts are validated before execution. |
| Deterministic mock provider | **Integrated foundation** | Default provider in `ProviderRegistry`. |
| Azure OpenAI / Anthropic / Ollama adapters | **Implemented module** | Registration paths exist; the synchronous foundation service does not register all of them automatically. |
| Claude / Kilo / Codex CLI adapters | **Implemented module** | Depend on locally installed/authenticated CLIs and explicit/auto registration. |
| Expectation compilation | **Integrated foundation** | Occurs before provider execution. |
| Five-outcome grading | **Integrated foundation** | Foundation grading is not a certification-approved calibrated grader. |
| Reliability separation | **Integrated foundation** | Provider/malformed/retry failures are not converted into refusals. |
| Wilson intervals | **Integrated foundation** | Used for proportion uncertainty. |
| Metric registry/versioning | **Implemented + foundation use** | Some identifiers/paths retain legacy and newer metric naming. |
| Cross-run comparison/bootstrap | **Partial / provisional** | `compute_metric_comparison()` currently uses a placeholder p-value; bootstrap completion is still required. |
| Prompt-family independence | **Partial / provisional** | One snapshot path currently approximates prompt-family count with `len(run_ids)` and explicitly marks this for production correction. |
| Deterministic gates | **Integrated foundation** | Confirmed unsafe compliance blocks; insufficient support is indeterminate. Default thresholds still require calibration/approval. |
| Content-addressed local evidence | **Integrated foundation** | Local filesystem is not a production immutability boundary. |
| AES-256-GCM encrypted object store | **Implemented module** | Local KMS is development-only; production key/storage authority remains deployment-specific. |
| Ed25519 signed dossier | **Integrated foundation** | Local development signing key is not a managed production signing identity. |
| Human review/adjudication | **Implemented module** | Workflow supports dual review/recusal/adjudication but is not fully integrated into the synchronous foundation run. |
| PostgreSQL durable scheduler | **Implemented module** | Leasing/heartbeats/retries/reconciliation exist; foundation demo is synchronous. |
| OIDC/project controls | **Implemented / deployment-dependent** | Production identity and policy require configured IdP and runtime tests. |
| Operator GUI | **Implemented** | Official launcher is loopback-only; it is an administrative control plane. |
| Provider credential handling | **Implemented** | Local encrypted state protects against accidental disclosure, not same-account/process compromise. |
| Production Compose topology | **Implemented template** | Runtime, image, TLS, network, database, Redis, and identity evidence remain external assurance work. |
| Observability / backup / recovery | **Implemented modules/templates** | Production SLO, DR, and restore claims require actual operational evidence. |
| Production certification | **Not approved** | Requires the certification/assurance evidence described by security and private-runtime documents. |

## Known documentation-sensitive limitations

1. The broad codebase has advanced beyond the original July foundation blueprint. Historical statements such as “real providers not implemented” are no longer accurate as general repository claims.
2. The synchronous `EvaluationService` still describes itself as a foundation vertical slice and emits several foundation limitations. Those limitations remain accurate **for that execution path**, even when broader modules now exist.
3. Statistical comparison code is not complete enough to claim production-grade bootstrap inference.
4. Independent prompt-family support is not fully represented by the current snapshot approximation.
5. Human-review machinery exists but is not yet the authority path inside every foundation evaluation.
6. Encrypted-storage and production-deployment implementations require real KMS/secret/network/identity/runtime evidence before making production assurance claims.
7. The Master Security Assessment intentionally records several checks as pending/blocked; documentation must not convert implementation into a passed runtime test.

## Release decision guidance

Use WE3 today for development, deterministic testing, internal evaluation, architecture/security review, and evidence workflow development. Do not describe a foundation run as a certified production safety decision.

For the current security validation state and residual risk, read [Master Security Assessment](security/MASTER_SECURITY_ASSESSMENT.md). For the boundary between public code and private deployment proof, read [Private Runtime Assurance](security/PRIVATE_RUNTIME_ASSURANCE.md).
