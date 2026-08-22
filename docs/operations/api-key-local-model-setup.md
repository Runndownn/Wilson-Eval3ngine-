# Provider Credentials and Local Model Endpoints

## Purpose

This guide explains the supported operator workflow for hosted and local model endpoints without placing credentials in source files, shell history, process arguments, or regular plaintext report-key files. It documents repository behavior, not any private provider/network inventory. Provider model counts, token lifetimes, endpoint availability, and CLI credential locations can change and must be verified in the authorized environment.

## GUI listener security

The supported launcher defaults to loopback:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` on the same host. Historical wildcard defaults (`0.0.0.0`, `::`) are repaired to loopback unless the operator explicitly enables remote binding:

```bash
WE3_GUI_ALLOW_REMOTE_BIND=1 we3-gui-start --host 10.0.0.25 --port 8080
```

`WE3_GUI_ALLOW_REMOTE_BIND=1` changes only the bind-policy check. It does **not** add authentication, authorization, TLS, firewalling, trusted proxy handling, or multi-user isolation. Use it only when the deployment deliberately supplies those controls and has validated the exposed listener. A broad wildcard bind with the override receives an explicit launcher warning.

For normal desktop/operator use, keep loopback and put any required remote access behind an independently authenticated and authorized TLS reverse proxy.

## Credential security model

Endpoint credentials are encrypted in local GUI state using a master key owned by the same operating-system account. This reduces accidental disclosure/offline-copy risk when the master key is absent; it is not equivalent to an external vault and does not protect against compromise of the account/process. Production use should rely on the approved secret authority/credential store for that deployment.

On supported POSIX systems, the keyed report-job path replaces the historical regular temporary key file with a one-shot FIFO. The FIFO is mode `0600`, its containing directory is mode `0700`, the secret is bounded, one child reads it, parent memory is overwritten, and the path is cleaned after success/cancellation/failure. Platforms without the supported secure transport must fail closed rather than restore a plaintext fallback.

## Endpoint network profiles

The GUI distinguishes public HTTPS providers from intentional local/private gateways.

### Public hosted provider

Use the provider's canonical HTTPS base URL. Embedded URL credentials are prohibited, automatic redirects are constrained/disabled for the protected flow, and destination addresses are validated before dispatch. Configure the credential through the GUI rather than editing `gui/data/endpoints.json` manually.

Example:

```text
Name: Hosted provider
Provider: openai
URL: https://api.example.invalid/v1
API key: supplied through the password field
```

`.invalid` is intentionally non-routable documentation data.

### Local/private provider gateway

Private and loopback provider destinations require explicit provider-policy enablement:

```bash
WE3_GUI_ALLOW_LOCAL_PROVIDERS=1 we3-gui-start --host 127.0.0.1 --port 8080
```

This flag is different from `WE3_GUI_ALLOW_REMOTE_BIND`:

- `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1` controls whether the GUI may call intentional private/loopback **provider destinations**;
- `WE3_GUI_ALLOW_REMOTE_BIND=1` controls whether the GUI **listener itself** may bind to a non-loopback address.

Do not confuse the two. Enabling local providers does not remotely expose the GUI, and enabling remote GUI binding does not authorize arbitrary private-provider egress.

The provider policy continues to block unsafe destination classes such as link-local/metadata/multicast/unspecified/reserved addresses as implemented. Host/container egress controls are still required.

A common local Ollama endpoint is:

```text
Name: Local Ollama
Provider: ollama
URL: http://127.0.0.1:11434
API key: empty unless the local gateway requires one
```

Connectivity-only verification:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags
```

Do not use sensitive prompts for connectivity testing or copy private IPs/model inventories from somebody else's environment.

### CLI providers

CLI adapters use the local operating-system identity and the provider CLI's own credential store. Register the exact adapter identifier shown by the GUI (for example `cli://codex`) only after installing/authenticating that CLI under the same restricted account that runs WE3.

Check executable availability without printing credentials:

```bash
command -v codex
```

Do not run the GUI as `root` solely to reach another credential store.

## Register and prove an endpoint

1. Start the GUI using the secure-default loopback listener unless your deployment explicitly requires/controls remote binding.
2. Open **Endpoints**.
3. Select the provider adapter.
4. Enter a descriptive display name and canonical URL.
5. Enter the credential in the API-key field when required.
6. Save the endpoint.
7. Run the connection/health test and inspect its safe status response.
8. Move to **Models** and discover/reconcile inventory only after connectivity succeeds.

The browser-facing endpoint list must not return credential values. Logs/telemetry should use constant redaction rather than stable secret prefixes/suffixes.

An endpoint becoming `online` establishes connectivity at that moment. It does not establish model quality, safety, release eligibility, or even that every model exposed by the endpoint is usable for every evaluation mode.

## Credential acquisition and rotation

Obtain credentials only through the provider's supported login/device-authorization/organization/secret-management workflow. Avoid extracting tokens into shell variables or printing them for ad-hoc `curl`; histories, environment inspection, crash reporting, terminal recording, and process tooling can retain them.

Rotate a GUI endpoint credential as follows:

1. issue/refresh the replacement through the provider;
2. stop new jobs for that endpoint;
3. update/recreate the endpoint through the supported workflow;
4. test connectivity and a synthetic approved evaluation;
5. revoke the previous credential;
6. review audit/error telemetry for old-credential use;
7. handle any retained state/backups according to the **actual** storage/retention control in the target environment.

The current WE3 database-backup/PITR manager is provisional; do not assume its metadata proves encrypted backup protection. See [Backup and Recovery Runbook](backup-recovery-runbook.md).

## Report generation

Use the supported GUI workflow rather than secret-bearing ad-hoc environment variables or regular plaintext key files. Historical patterns such as these are unsupported for production operation:

```text
WE3_REPORT_GATEWAY_API_KEY=<secret>
WE3_REPORT_API_KEY_FILE=/tmp/plaintext-key
python -m wilson_eval3ngine.gui.server
```

The supported entry point is `we3-gui-start`, which composes access control, secure secret transport, and current UX overlays before starting the listener.

## Local model verification

List Ollama models:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags \
  | python -m json.tool
```

After confirming the model/data are approved, a minimal local smoke prompt is:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/chat \
  --header 'Content-Type: application/json' \
  --data '{"model":"MODEL_ID","messages":[{"role":"user","content":"Return the word ready."}],"stream":false}' \
  | python -m json.tool
```

Replace `MODEL_ID` with a value from the local inventory. This is a connectivity/capability smoke check, not evaluation evidence.

## Production deployment secrets

`docker-compose.prod.yml` requires production values including database/cache/dashboard credentials, OIDC issuer/JWKS, and public TLS routing configuration. Supply them through the deployment platform's approved secret/configuration mechanism. A Git-ignored plaintext `.env` file is still not a production secret manager.

Only the intended ingress should be externally reachable in the production topology. Direct local debugging and intentionally remote GUI operation are separate modes and require their own explicit controls/evidence.

Validate Compose interpolation with synthetic values only:

```bash
WE3_POSTGRES_PASSWORD=test-postgres \
WE3_REDIS_PASSWORD=test-redis \
WE3_GRAFANA_PASSWORD=test-grafana \
WE3_OIDC_ISSUER=https://issuer.invalid \
WE3_OIDC_JWKS_URI=https://issuer.invalid/jwks \
WE3_DOMAIN=example.invalid \
WE3_TLS_EMAIL=security@example.invalid \
docker compose -f docker-compose.prod.yml config >/dev/null
```

## Troubleshooting

### GUI unexpectedly binds to loopback

If a legacy command asks for `0.0.0.0` without `WE3_GUI_ALLOW_REMOTE_BIND=1`, the supported launcher intentionally repairs it to `127.0.0.1`. Prefer that secure default. If remote binding is genuinely required, configure the independent TLS/auth/network controls first, then use the explicit override and a specific address when practical.

### Endpoint is rejected as private

Confirm it is an intentional private/local provider, then enable `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1`. Do not use that flag to work around a public provider DNS error; inspect resolution and egress policy instead.

### Endpoint redirects

Use the canonical final endpoint rather than enabling unrestricted redirect following for credential-bearing traffic.

### Keyed report job cannot establish secure transport

Use a supported POSIX host/container or implement/validate a native protected transport. Do not fall back to a regular plaintext temporary key file.

### Credential decrypt fails after moving state

The encrypted record/master key belong to the installation. Restore them only through an authorized state/secret procedure, or issue a new provider credential and recreate the endpoint. Never copy the master key into source control/shared storage.

### Provider returns unauthorized

Verify current credential, expiry/revocation, canonical URL, scope/audience, and endpoint association. Rotate rather than repeatedly printing or logging the token.

## Validation checklist

- [ ] GUI listener is loopback by default.
- [ ] Any non-loopback bind is explicitly enabled with `WE3_GUI_ALLOW_REMOTE_BIND=1` and protected by independently validated TLS/authentication/authorization/firewall controls.
- [ ] Local/private provider egress is separately enabled only when intentional and constrained by network policy.
- [ ] No endpoint credential appears in source, shell history, arguments, environment dumps, logs, telemetry, reports, or screenshots.
- [ ] Endpoint health is not treated as model-quality evidence.
- [ ] Keyed report jobs use protected one-shot transport on supported paths.
- [ ] Old credentials are revoked after rotation.
- [ ] Production configuration fails closed when mandatory secrets are absent.
- [ ] Only intended production ingress is externally reachable.
- [ ] Backup/encryption/restore claims are supported by real target-environment evidence rather than scaffold metadata.
- [ ] Security/CI/runtime-assurance evidence matches the exact deployed commit.

See [Security Policy](../../SECURITY.md), [Current Status](../STATUS.md), and [Private Runtime Assurance](../security/PRIVATE_RUNTIME_ASSURANCE.md) for the surrounding assurance model.
