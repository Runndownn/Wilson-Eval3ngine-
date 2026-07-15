# Wilson Eval3ngine Threat Model

## Assets

Model-provider credentials, hidden benchmark content, raw harmful responses, personal or secret-bearing source material, release thresholds, grader prompts/models, approvals, signing keys, audit events, and published dossiers.

## Trust boundaries

1. User/browser to API.
2. API to scheduler/executor.
3. Executor to provider.
4. Executor to evidence storage.
5. Evidence storage to grader.
6. Quarantined evidence to reviewer.
7. Release authority to gate/override.
8. Signing service to dossier publication.

## Priority abuse cases

| Abuse case | Control |
|---|---|
| Stored XSS/prompt content compromises reviewer | Inert rendering, strict CSP, no remote fetch, quarantine |
| Response manipulates grader to use tools | No tools, no provider credentials, no default egress, schema-only output |
| Secret enters artifact/log | Workload identity, redaction, canaries, secret scanning |
| Cross-project evidence access | OIDC claims, API checks, PostgreSQL RLS, object-prefix policy |
| Evaluation performs a live harmful action | Tool simulators in certification; sandbox approval and egress deny |
| Metric/threshold/dataset is modified silently | Immutable versions, hashes, approvals, signed dossier |
| Override bypasses governance | Two-person approval, expiry, rationale, monitoring, audit |
| Provider alias changes | Provider-reported metadata and fingerprint canaries |
| Attachment executes | MIME-by-content validation, quarantine, safe derivative |
| Audit/signing key compromised | Managed KMS, rotation, external checkpoints, revocation |

## Foundation residual risk

Local filesystem artifacts, development headers, in-process grading, and a generated development signing key are accepted only for synthetic local testing. Production mode rejects the development identity configuration.
