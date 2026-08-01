# Provider Credentials and Local Model Endpoints

## Purpose

This guide explains the supported operator workflow for registering hosted or local model endpoints without placing credentials in source files, shell history, process arguments, or regular plaintext report-key files. It describes repository behavior, not the current inventory of any private network or third-party account. Provider model counts, token lifetimes, endpoint availability, and CLI storage locations can change and must be verified against the provider's current documentation.

## Security model

The official GUI launcher binds only to loopback. Start it with:

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` from the same host. Do not bind the GUI directly to a LAN, VPN, container host interface, or public address; it has administrative authority over endpoints, credentials, jobs, reports, charts, and deletion actions. Remote operation requires a separately authenticated TLS reverse proxy that connects to the loopback listener and enforces an explicit authorization policy.

Endpoint credentials are encrypted in local GUI state using a master key owned by the same operating-system account. This protects accidental disclosure and offline copies that do not include the master key, but it is not equivalent to an external vault and does not protect against compromise of that account or process. Production use should migrate endpoint references to an approved secret manager or operating-system credential store.

When the official launcher starts a keyed report job on POSIX, it replaces the historical regular temporary file with a one-shot FIFO. The FIFO is mode `0600`, its containing directory is mode `0700`, the secret is bounded to 4096 bytes, one child reads it, parent memory is overwritten, and the path is removed after success, cancellation, or cleanup. Platforms without FIFO support fail closed for keyed report jobs rather than writing a plaintext fallback.

## Endpoint network profiles

The GUI distinguishes public HTTPS providers from local or private development gateways.

### Public hosted provider

Use the provider's canonical HTTPS base URL. Embedded URL credentials are prohibited, automatic redirects are disabled, and destination addresses are checked before dispatch. Configure the credential through the GUI rather than editing `gui/data/endpoints.json` directly.

Example values:

```text
Name: Hosted provider
Provider: openai
URL: https://api.example.invalid/v1
API key: supplied through the password field
```

The `.invalid` domain is illustrative and will not connect.

### Loopback or private development gateway

Local and private destinations are denied unless the operator deliberately enables them for the GUI process:

```bash
WE3_GUI_ALLOW_LOCAL_PROVIDERS=1 we3-gui-start --host 127.0.0.1 --port 8080
```

This setting allows configured private or loopback providers; it does not disable the permanent blocks for link-local, metadata, multicast, unspecified, and reserved destinations. It also does not replace host or container egress policy. Limit the process to the exact gateway addresses and ports required for the deployment.

A common local Ollama endpoint is:

```text
Name: Local Ollama
Provider: ollama
URL: http://127.0.0.1:11434
API key: empty unless the local gateway requires one
```

Verify the local service without sending a model prompt:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags
```

Do not copy private IP addresses, usernames, SSH targets, or model inventories from another operator's documentation. Register the address that belongs to the current authorized environment.

### CLI providers

CLI adapters use the local operating-system identity and the provider CLI's own credential store. Register the exact adapter URL shown by the GUI, such as `cli://codex`, only after installing and authenticating that CLI under the same restricted account that runs the GUI.

Check availability without printing credentials:

```bash
command -v codex
```

The GUI must not be run as `root` merely to reach a CLI credential file.

## Register an endpoint

1. Start the official loopback launcher.
2. Open the **Endpoints** tab.
3. Select the provider adapter.
4. Enter a descriptive name and canonical URL.
5. Enter the credential in the API-key field when required.
6. Save the endpoint.
7. Run **Test** and inspect the safe status response.
8. Open the **Models** tab and run discovery only after the endpoint test succeeds.

The endpoint list returned to the browser omits credential values. Logs and telemetry use a constant redaction marker rather than stable key prefixes or suffixes.

## Credential acquisition and rotation

Obtain credentials only through the provider's supported login, device authorization, organization administration, or secret-management workflow. Do not extract tokens from a credential file into a shell variable merely to paste them into `curl`; shell history, environment inspection, crash reporting, and terminal recording can retain them.

For provider CLIs, use the provider's interactive login command and its credential-status command. The exact command, token lifetime, refresh behavior, and storage location are provider-controlled and should be verified from current official documentation.

Rotate a GUI endpoint credential as follows:

1. Issue or refresh the replacement credential through the provider.
2. Stop new evaluation jobs for that endpoint.
3. Update or recreate the endpoint through the GUI.
4. Test the endpoint and one synthetic evaluation.
5. Revoke the previous credential at the provider.
6. Review audit and error telemetry for failed use of the old credential.
7. Remove stale local backups that contain the old encrypted endpoint record according to the retention policy.

If a GUI instance, report-key path, terminal transcript, log, or backup may have exposed a credential, revoke first and investigate second.

## Report generation

Use the GUI job workflow rather than invoking `scripts/generate_5_reports.py` with a secret-bearing environment variable or an ad-hoc key file. The official launcher installs the one-shot transport and handles cleanup around the child process.

The following historical patterns are unsupported for production operations:

```text
WE3_REPORT_GATEWAY_API_KEY=<secret>
WE3_REPORT_API_KEY_FILE=/tmp/plaintext-key
python -m wilson_eval3ngine.gui.server
```

They may remain as compatibility code while migration is completed, but documentation and automation must not rely on them. The supported entry point is `we3-gui-start`.

## Local model verification

List Ollama models:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/tags \
  | python -m json.tool
```

Run a minimal local-only smoke prompt after confirming that the model and data are approved for the environment:

```bash
curl --fail --silent --show-error http://127.0.0.1:11434/api/chat \
  --header 'Content-Type: application/json' \
  --data '{"model":"MODEL_ID","messages":[{"role":"user","content":"Return the word ready."}],"stream":false}' \
  | python -m json.tool
```

Replace `MODEL_ID` with a value returned by the local inventory. Do not use sensitive prompts for connectivity testing.

## Production deployment secrets

`docker-compose.prod.yml` requires these values and has no development fallback:

```text
WE3_POSTGRES_PASSWORD
WE3_REDIS_PASSWORD
WE3_GRAFANA_PASSWORD
WE3_OIDC_ISSUER
WE3_OIDC_JWKS_URI
WE3_DOMAIN
WE3_TLS_EMAIL
```

Supply them through the deployment platform's approved secret mechanism. A local `.env` file is excluded from Git, but a plaintext environment file is still not a production secret manager. Restrict its mode, lifecycle, backups, and operator access when it is used for isolated validation.

Only Caddy publishes production host ports. API, PostgreSQL, Redis, Prometheus, and Grafana remain on internal container networks. A separate loopback-only development override should be used when direct local debugging is necessary.

Validate interpolation without using real secrets:

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

These values are synthetic and must not be deployed.

## Troubleshooting

### Endpoint is rejected as private

Confirm that the endpoint is intentionally local or private, then start the GUI with `WE3_GUI_ALLOW_LOCAL_PROVIDERS=1`. Do not enable the setting to work around a public provider DNS error. Review all resolved addresses and the network egress policy.

### Endpoint redirects

Automatic provider redirects are disabled to prevent credential forwarding. Configure the canonical final HTTPS endpoint. Do not enable unrestricted redirect following.

### Report job cannot create a secure transport

Keyed report jobs require POSIX FIFO support on this branch. Use a supported POSIX host/container or implement and validate a native secure transport for the platform. Do not restore a regular plaintext temporary file.

### Credential decrypt fails after moving state

The encrypted endpoint record and its local master key belong to the same installation. Restore both only through an authorized backup procedure, or recreate the endpoint with a newly issued credential. Do not copy the master key into source control or a shared filesystem.

### Provider returns unauthorized

Verify that the endpoint references the current credential, the credential has not expired or been revoked, the provider URL is canonical, and the required scope/audience is correct. Rotate rather than repeatedly logging or printing the token.

## Validation checklist

- [ ] GUI listener is loopback-only.
- [ ] Remote proxy, when used, requires TLS, authentication, authorization, and trusted forwarding configuration.
- [ ] No endpoint credential appears in source, shell history, process arguments, environment dumps, logs, telemetry, reports, or screenshots.
- [ ] Local/private provider access is explicitly enabled and limited by host/container egress policy.
- [ ] Report jobs use the one-shot transport and leave no stale secret directory.
- [ ] Old credentials are revoked after rotation.
- [ ] Production Compose fails when required secrets are absent.
- [ ] Only the intended TLS ingress is reachable from outside the production network.
- [ ] Master security assessment and CI results match the deployed commit.

See `docs/security/MASTER_SECURITY_ASSESSMENT.md` for current findings, residual risk, validation state, and rollout/rollback requirements.
