# Deterministic Local Foundation-Lane Runbook

This runbook is intentionally scoped to the historical deterministic **foundation lane** and its retained example filenames. It is not a statement that the entire current Wilson Eval3ngine repository is a foundation build; for the broader platform and production-assurance position see [../STATUS.md](../STATUS.md).

## Validate the supplied local experiment

```bash
we3 validate examples/experiments/foundation.yaml
```

Expected result: a valid contract, eight cases, eight prompt families, and a computed dataset hash. The manifest is deliberately small so the measurement path can be inspected without real provider credentials.

## Execute the deterministic comparison

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

Inspect the generated result artifacts:

```bash
python -m json.tool var/foundation/release_dossier.json
python -m json.tool var/foundation/experiment_result.json
```

The balanced mock profile should have false-refusal rate `0.0`, while the over-refusal candidate should have false-refusal rate `1.0`. The gates remain `indeterminate` because this synthetic example is intentionally below approved statistical support, demonstrating that a small sample is not allowed to become an artificial pass.

## Verify the dossier

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

The local lane may create a development signing key when none is supplied. That key is appropriate for the deterministic demonstration and local integrity verification, but it is not a managed production signing identity.

## Execute the critical-event demonstration

```bash
we3 run examples/experiments/critical_failure.yaml --output var/critical-failure --database-url sqlite:///./var/we3-critical.db --artifact-root var/artifacts-critical
```

The under-refusal mock candidate should receive a `block` because at least one inert unsafe-compliance sentinel is observed. This demonstrates the gate engine's critical-event precedence independently of a production provider.

## Verify source tests

```bash
python -m pytest -q
```

A successful source test run validates the checked-out code under the executed test environment. It does not by itself prove production OIDC, real providers, network boundaries, external key/storage systems, backup restores, or other private runtime controls.

## Failure handling

- **Contract error:** correct the YAML; no experiment should be accepted from an invalid definition.
- **Provider simulation failure:** inspect the provider-attempt artifact and reliability reason instead of counting it as a behavioral refusal.
- **Artifact verification failure:** stop publication, preserve the directory, and investigate corruption or mismatch.
- **Audit verification failure:** treat the dossier as invalid until lineage is reconciled.
- **Signature failure:** do not distribute the dossier as verified evidence; investigate key/artifact integrity and rerun only from trusted inputs.
- **Database failure:** retain the artifact directory and reconcile logical-run state before rerunning work.

## Prohibited use of this lane

Do not add real production credentials, live target information, personal data, unrestricted live tools, or unreviewed harmful corpora to this deterministic example. Use the real-provider and production-oriented paths only within an authorized environment and follow [api-key-local-model-setup.md](api-key-local-model-setup.md) plus [../security/PRIVATE_RUNTIME_ASSURANCE.md](../security/PRIVATE_RUNTIME_ASSURANCE.md).
