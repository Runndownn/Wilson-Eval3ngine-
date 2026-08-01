# Private Runtime Assurance Contract

This document defines how Wilson Eval3ngine receives production assurance without publishing private operational material. It contains no real registry, host, address, domain, user, group, issuer, namespace, certificate, key, token, provider, allowlist, or policy value.

## Boundary

The public repository owns:

- stable application and adapter contracts;
- fail-closed configuration validation;
- deterministic repository inventory;
- sanitized runtime-evidence schemas;
- tests using synthetic values only;
- immutable-image validation;
- secure container and network topology templates;
- the master assessment and traceability record.

The private deployment environment owns:

- external secret-backend implementation and workload identity;
- image registry and approved image digests;
- OIDC issuer, client, claims, groups, and role mappings;
- domains, certificates, trust anchors, and renewal controls;
- PostgreSQL and Redis credentials and connection material;
- provider endpoints, approved destinations, and local/private gateways;
- egress-proxy implementation and allowlist;
- host placement, firewall policy, service accounts, and incident contacts;
- raw scanner output, logs, packet captures, screenshots, and test accounts.

Private content is never copied into this repository. Only bounded statuses and SHA-256 evidence fingerprints may cross the boundary.

## Public implementation points

| Concern | Public component | Private input |
|---|---|---|
| Repository coverage | `wilson_eval3ngine.assurance.inventory` | None |
| Production secrets | `security.secrets_backend` and `api.secure_entrypoint` | Backend plugin or mounted secret files |
| Non-POSIX child secrets | `gui.secret_transport_factory` | Reviewed private transport plugin |
| Remote GUI identity | `gui.access_control` | OIDC and role configuration |
| Runtime evidence | `assurance.runtime_evidence` | Sanitized private probe outcomes |
| Image integrity | `assurance.image_references` | Approved digest-pinned references |
| Secure topology | `docker-compose.secure.yml` | Private files, images, identity, and egress policy |
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

3. Build the API image from `Dockerfile.secure` with an approved digest-pinned base image. Store the build log, SBOM, provenance, scanner output, and resulting digest privately.

4. Validate Caddy using the exact digest-pinned image selected for deployment. Do not substitute a local binary or a different tag.

5. Start the isolated stack and verify that only the proxy publishes host ports. Confirm the API, database, cache, metrics, dashboard, and egress control plane are not directly reachable from the test client network.

6. Run OIDC positive and negative tests using dedicated test identities. Cover valid signature and audience, expired token, wrong issuer, wrong audience, absent token, duplicate authorization headers, disallowed role, and WebSocket denial.

7. Verify TLS protocol, hostname, chain, expiry policy, renewal health, and downgrade rejection. Retain certificate bodies and hostnames privately.

8. Verify PostgreSQL connectivity over TLS with hostname verification, authorization boundaries, transaction behavior, backup/restore, and denial of plaintext connections.

9. Verify Redis authentication, unauthorized denial, TLS or private-segment policy as selected by the deployment, rate-limit state, revocation behavior, and fail-closed dependency handling.

10. Exercise one approved provider destination and representative denied destinations through the egress proxy. Verify cloud metadata, link-local, multicast, reserved, and destinations outside the private allowlist are denied without credential forwarding.

11. Run the complete quality, build, security, browser, container, and recovery matrix. Preserve exact commands, versions, exit codes, and raw output privately.

12. Convert each result into `we3.runtime_evidence.v1`. Use a SHA-256 digest of the retained private evidence as `evidence_sha256`; never embed the evidence itself or a reversible location.

13. Verify the sanitized envelope publicly:

```bash
python scripts/assurance/verify_runtime_evidence.py runtime-evidence.json
```

## Required runtime checks

The envelope supports the following completion set:

```text
oidc.discovery
oidc.signature
oidc.audience
oidc.expiry
oidc.role_denial
tls.protocol
tls.hostname
tls.chain
database.connectivity
database.tls
database.authorization
redis.connectivity
redis.authentication
provider.allowed_destination
provider.denied_destination
network.only_proxy_ingress
network.egress_default_deny
network.metadata_denied
container.readiness
container.non_root
container.read_only_root
```

A `passed` result requires a private evidence fingerprint. A failed, blocked, or unexecuted result remains visible and cannot be converted into a pass through documentation.

## Browser evidence

The public browser suite uses only synthetic content and validates exact two-column geometry, responsive collapse, horizontal overflow, keyboard reachability, chart-window containment, reduced motion, and 125–200% zoom emulation.

Private staging browser tests may add authenticated end-to-end flows and screenshots. Screenshots must be reviewed for tokens, account names, domains, provider identifiers, prompts, report content, browser history, developer tools, and operating-system chrome before any public publication. Prefer publishing the bounded runtime check and screenshot hash rather than the screenshot itself.

## Inventory and final coverage hash

Generate the baseline and final inventories from clean checkouts:

```bash
python scripts/assurance/inventory_repository.py . --output artifacts/assurance/repository-inventory.json
```

The bundle identity excludes timestamps and absolute checkout paths. Symlinks are not followed; absolute symlink targets are represented only by a digest. Any read error or unsupported filesystem object fails completeness by default.

## Security assertions

- A local encrypted file store is not a production secret authority.
- A reverse proxy is not the sole GUI authorization boundary.
- A tag is not an immutable image identity.
- A successful configuration parse is not runtime proof.
- A repository change is not deployment proof.
- Sanitization is not approval to publish raw private evidence.
- No risk is accepted on behalf of maintainers.
