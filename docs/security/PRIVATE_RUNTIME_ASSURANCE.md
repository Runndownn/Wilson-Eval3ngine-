# Private Runtime Assurance Contract

This document defines how Wilson Eval3ngine receives production assurance without publishing private operational material. It contains no real registry, host, address, domain, user, group, issuer, namespace, certificate, key, token, provider, allowlist, proxy range, or policy value.

## Boundary

The public repository owns:

- stable application and adapter contracts;
- fail-closed configuration validation;
- deterministic repository inventory;
- sanitized runtime-evidence schemas;
- tests using synthetic values only;
- immutable-image validation;
- secure container and network topology templates;
- current source-level security reassessment and historical assessment records.

The private deployment environment owns:

- external secret-backend implementation and workload identity;
- image registry and approved image digests;
- OIDC issuer, client, claims, groups, role mappings, token lifetime, and sender-constraint policy;
- domains, certificates, trust anchors, and renewal controls;
- PostgreSQL and Redis credentials and connection material;
- provider endpoints, approved destinations, and local/private gateways;
- egress-proxy implementation and allowlist;
- trusted reverse-proxy CIDRs and host placement;
- firewall policy, service accounts, and incident contacts;
- raw scanner output, logs, packet captures, screenshots, and test accounts.

Private content is never copied into this repository. Only bounded statuses, reason codes, control versions, and SHA-256 evidence fingerprints may cross the boundary.

## Public implementation points

| Concern | Public component | Private input |
|---|---|---|
| Repository coverage | `wilson_eval3ngine.assurance.inventory` | None |
| Production secrets | `security.secrets_backend` and `api.secure_entrypoint` | Backend plugin or mounted secret files |
| Shared security state | `security.redis_authority`, OIDC revocation, rate limiter, idempotency store | Private Redis endpoint/credential/transport policy |
| API request boundary | `api.security_middleware`, `api.authorization_audit` | Exact CORS origins and trusted Caddy-to-API CIDRs |
| Non-POSIX child secrets | `gui.secret_transport_factory` | Reviewed private transport plugin |
| Remote GUI identity | `gui.access_control` | OIDC and role configuration |
| Runtime evidence | `assurance.runtime_evidence` | Sanitized private probe outcomes |
| Image integrity | `assurance.image_references` | Approved digest-pinned references |
| Secure topology | `docker-compose.secure.yml` / `docker-compose.prod.yml` | Private files, images, identity, proxy ranges, and egress policy |
| Browser behavior | `tests/browser/` | None for hermetic tests; authorized staging URL for separate private tests |

## Private validation sequence

Run these steps in a disposable, authorized environment with no production user data and with output retained privately.

1. Resolve every container image to an approved digest and validate each reference:

```bash
printf '%s\n' "$WE3_API_IMAGE" "$WE3_POSTGRES_IMAGE" "$WE3_REDIS_IMAGE" "$WE3_CADDY_IMAGE" "$WE3_PROMETHEUS_IMAGE" "$WE3_GRAFANA_IMAGE" "$WE3_EGRESS_PROXY_IMAGE" | python scripts/assurance/validate_image_references.py
```

2. Validate configuration without printing resolved secret values:

```bash
docker compose -f docker-compose.secure.yml config --quiet
```

3. Build the API image from the production/secure Dockerfile with an approved digest-pinned base image. Store the build log, SBOM, provenance, scanner output, and resulting digest privately.

4. Validate Caddy using the exact digest-pinned image selected for deployment. Confirm the public API site rejects `/metrics`, `/ready`, `/openapi.json`, `/docs*`, and `/redoc*`; confirm there is no public Prometheus Caddy route.

5. Start the isolated stack and verify that only Caddy publishes host ports. Confirm API, PostgreSQL, Redis, Prometheus, and the egress control plane are not directly reachable from the test client network. Grafana exposure, if enabled, must be tested through its intended authenticated surface.

6. Verify reverse-proxy identity handling. From an untrusted client, send forged `X-Forwarded-For` values and confirm they do not create attacker-selected rate buckets. From the intended Caddy path, confirm Caddy overwrites forwarding identity and the API trusts only the private configured `WE3_TRUSTED_PROXY_CIDRS`. Retain the real CIDRs privately.

7. Run OIDC positive and negative tests using dedicated test identities. Cover valid signature/audience, expired token, wrong issuer, wrong audience, absent token, duplicate authorization headers, malformed/oversized bearer values, missing/invalid `jti` and `sub`, disallowed role, and workload-role namespace behavior.

8. Exercise token revocation against the shared Redis authority across more than one API worker/process. Verify a revoked token is rejected until its complete signed lifetime has elapsed and verify Redis loss produces service-unavailable/fail-closed behavior. Separately document the residual fact that an unrevoked ordinary bearer token is reusable until expiry/revocation unless the deployment implements sender-constrained authentication.

9. Verify TLS protocol, hostname, chain, expiry policy, renewal health, and downgrade rejection. Retain certificate bodies and hostnames privately. Treat HSTS preload-list enrollment as a separate domain-owner check; the header token alone is not evidence of enrollment.

10. Verify PostgreSQL connectivity over TLS with hostname verification, authorization boundaries, transaction behavior, audit-chain behavior, backup/restore as applicable to the exact release, and denial of plaintext connections.

11. Exercise API authorization allow and deny paths and verify corresponding hash-linked audit events are persisted before an allowed state change proceeds. Force the audit store unavailable and confirm protected authorization fails closed with a bounded service-unavailable response rather than continuing without forensic evidence.

12. Verify Redis authentication, unauthorized denial, TLS or private-segment policy as selected by the deployment, rate-limit state, revocation behavior, idempotency intent binding, multi-worker sharing, and fail-closed dependency handling. Confirm raw Redis/backend exceptions are not returned to clients.

13. Exercise one approved provider destination and representative denied destinations through the egress proxy. Verify cloud metadata, link-local, multicast, reserved, and destinations outside the private allowlist are denied without credential forwarding.

14. Run browser checks for exact CORS origin/preflight behavior, including `If-Match` conditional requests. Verify disallowed origins are rejected before side effects. If any future endpoint uses ambient cookie/session authentication, exercise the bound CSRF path; do not invent CSRF requirements for the current explicit Bearer-header path.

15. Run the complete quality, build, security, browser, container, and recovery matrix. Preserve exact commands, versions, exit codes, and raw output privately. If GitHub Actions remain disabled, execute the repository-owned manual lane rather than presenting workflow YAML as proof:

```bash
make install-security
make lint
make security-check
make test
make coverage
```

16. Convert each relevant result into `we3.runtime_evidence.v1`. Use a SHA-256 digest of the retained private evidence as `evidence_sha256`; never embed the evidence itself or a reversible location.

17. Verify the sanitized envelope publicly:

```bash
python scripts/assurance/verify_runtime_evidence.py runtime-evidence.json
```

## Runtime checks

The public runtime-evidence schema has a baseline completion set for OIDC, TLS, database, Redis, provider, network, and container checks. It also permits additional bounded check identifiers. The following security checks should be included for a production assurance package even when the current baseline schema does not yet make every one mandatory under `require_complete`:

```text
oidc.discovery
oidc.signature
oidc.audience
oidc.expiry
oidc.role_denial
oidc.revocation_shared_state
oidc.bearer_replay_boundary
tls.protocol
tls.hostname
tls.chain
database.connectivity
database.tls
database.authorization
audit.authentication_persistence
audit.authorization_persistence
audit.fail_closed
redis.connectivity
redis.authentication
redis.rate_limit_shared_state
redis.revocation_shared_state
redis.idempotency_shared_state
redis.fail_closed
provider.allowed_destination
provider.denied_destination
network.only_proxy_ingress
network.trusted_forwarding
network.public_diagnostics_denied
network.prometheus_internal_only
network.egress_default_deny
network.metadata_denied
browser.cors_allowed_origin
browser.cors_denied_origin
browser.conditional_if_match
container.readiness
container.non_root
container.read_only_root
```

A `passed` result requires a private evidence fingerprint. A failed, blocked, or unexecuted result remains visible and cannot be converted into a pass through documentation. Extra check identifiers are bounded labels, not permission to put hosts, addresses, URLs, account names, or error text into public evidence.

## Browser evidence

The public browser suite uses only synthetic content and validates exact two-column geometry, responsive collapse, horizontal overflow, keyboard reachability, chart-window containment, reduced motion, and 125–200% zoom emulation.

Private staging browser tests may add authenticated end-to-end flows, CORS/conditional-request behavior, and screenshots. Screenshots must be reviewed for tokens, account names, domains, provider identifiers, prompts, report content, browser history, developer tools, and operating-system chrome before any public publication. Prefer publishing the bounded runtime check and screenshot hash rather than the screenshot itself.

## Inventory and final coverage hash

Generate the baseline and final inventories from clean checkouts:

```bash
python scripts/assurance/inventory_repository.py . --output artifacts/assurance/repository-inventory.json
```

The bundle identity excludes timestamps and absolute checkout paths. Symlinks are not followed; absolute symlink targets are represented only by a digest. Any read error or unsupported filesystem object fails completeness by default.

## Security assertions

- A local encrypted file store is not a production secret authority.
- A `jti`/revocation list is not sender-constrained bearer authentication.
- CORS is not authentication and Bearer-header OIDC is not ambient cookie authentication.
- A reverse proxy is not trusted merely because a forwarding header exists; the direct peer and private CIDR contract matter.
- Structured logs are not a replacement for the hash-linked audit ledger.
- A Redis client library or configured URL is not proof that distributed security state worked across workers.
- A tag is not an immutable image identity.
- HSTS `preload` text is not browser preload-list enrollment evidence.
- A successful configuration parse is not runtime proof.
- A repository change or workflow definition is not deployment/CI execution proof.
- Sanitization is not approval to publish raw private evidence.
- No risk is accepted on behalf of maintainers.
