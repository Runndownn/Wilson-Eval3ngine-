# Private Runtime Assurance Contract

This document defines how Wilson Eval3ngine receives production assurance without publishing private operational material. It contains no real registry, host, address, domain, user, group, issuer, namespace, certificate, key, token, provider, allowlist, KMS key, backup object, or policy value.

## Boundary

The public repository owns:

- stable application, provider, recovery, and evidence contracts;
- fail-closed configuration/integrity validation where the source contract requires it;
- deterministic repository inventory;
- sanitized runtime-evidence schemas;
- tests using synthetic/disposable values only;
- immutable-image validation;
- secure container/network topology templates;
- encrypted PostgreSQL backup/PITR implementation and disposable recovery test harness;
- public status/security/runbook documentation explaining what runtime evidence is still required;
- point-in-time assessments and traceability records.

The private deployment environment owns:

- external secret-backend implementation and workload identity;
- image registry and approved image digests;
- OIDC issuer, client, claims, groups, and role mappings;
- domains, certificates, trust anchors, and renewal controls;
- PostgreSQL/Redis credentials and connection material;
- provider endpoints, approved destinations, and local/private gateways;
- egress-proxy implementation and allowlist;
- production KMS authority, key policy, rotation/revocation, and signer trust governance;
- backup storage durability, immutability/object lock, retention/legal hold, replication, deletion policy, and restore access;
- WAL archival service, observed archive lag, protected recovery point, and database/tablespace topology;
- measured restore/RTO evidence, calculated RPO evidence, external-artifact reconciliation, and return-to-service approvals;
- host placement, firewall policy, service accounts, and incident contacts;
- raw scanner output, logs, packet captures, screenshots, backup manifests, restore logs, and test accounts.

Private content is never copied into this repository. Only bounded statuses and SHA-256 evidence fingerprints may cross the boundary.

## Public implementation points

| Concern | Public component | Private input/evidence |
|---|---|---|
| Repository coverage | `wilson_eval3ngine.assurance.inventory` | None |
| Production secrets | `security.secrets_backend` and `api.secure_entrypoint` | Backend plugin or mounted secret files |
| Non-POSIX child secrets | `gui.secret_transport_factory` | Reviewed private transport plugin |
| Remote GUI identity | `gui.access_control` | OIDC and role configuration |
| Runtime evidence | `assurance.runtime_evidence` | Sanitized private probe outcomes |
| Image integrity | `assurance.image_references` | Approved digest-pinned references |
| Secure topology | `docker-compose.secure.yml` | Private files, images, identity, and egress policy |
| Browser behavior | `tests/browser/` | Hermetic tests; authorized staging URL for private tests |
| PostgreSQL physical backup/PITR | `wilson_eval3ngine.backup` / `we3-backup` | Approved KMS, backup storage, WAL archive, signer trust, target database, operator authorization |
| Recovery reconciliation | `RecoveryBaseline`, `RecoveryOrchestrator` | Signed approved baseline plus target-environment restore evidence |
| Recovery runtime regression | `tests/integration/test_backup_restore.py` | None beyond disposable CI PostgreSQL; production claims require separate target evidence |

## Private validation sequence

Run these steps in a disposable, authorized environment with no production user data and retain raw output privately.

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

6. Run OIDC positive and negative tests using dedicated test identities. Cover valid signature/audience, expired token, wrong issuer/audience, absent token, duplicate authorization headers, disallowed role, and WebSocket denial.

7. Verify TLS protocol, hostname, chain, expiry policy, renewal health, and downgrade rejection. Retain certificate bodies and hostnames privately.

8. Verify PostgreSQL connectivity over the required protected transport with hostname/identity policy, authorization boundaries, transaction behavior, and denial of unapproved plaintext/route behavior.

9. Verify Redis authentication, unauthorized denial, protected-transport/private-segment policy, rate-limit state, revocation behavior, and fail-closed dependency handling.

10. Exercise one approved provider destination and representative denied destinations through the egress proxy. Verify metadata/link-local/multicast/reserved and destinations outside the private allowlist are denied without credential forwarding.

11. Validate the recovery trust chain before a disaster exercise: confirm the approved backup KMS identity/policy, trusted Ed25519 signer fingerprints, backup-root/object permissions, retention/object-lock policy, WAL archive health, and the exact PostgreSQL system/timeline/segment-size identity being protected. Do not publish those private values.

12. Capture or identify the approved signed recovery baseline and confirm the selected full backup plus encrypted real WAL provide continuous coverage through the intended recovery point. A restore plan is evidence about available inputs; it is not restore evidence.

13. Execute an isolated target-like restore with `we3-backup restore` (or the approved platform recovery adapter), retain the encrypted-object identities, selected WAL sequence, target timestamp/LSN, PostgreSQL/tool versions, restore log, measured duration, and reconciliation result, and prove that the restored service is not returned to release authority before required approval.

14. Reconcile any evidence outside PostgreSQL—such as managed object/evaluation evidence stores—according to the deployment's architecture. The native database reconciliation does not imply that external stores were recovered automatically.

15. Run the complete quality, build, security, browser, container, and other required recovery/operations matrices. Preserve exact commands, versions, exit codes, and raw output privately.

16. Convert each bounded result into `we3.runtime_evidence.v1`. Use a SHA-256 digest of the retained private evidence as `evidence_sha256`; never embed the raw evidence or a reversible private location.

17. Verify the sanitized envelope publicly:

```bash
python scripts/assurance/verify_runtime_evidence.py runtime-evidence.json
```

## Required runtime checks

The existing runtime-evidence schema supports the established deployment checks below. Production recovery certification should additionally carry bounded recovery checks in the private assurance set; if the current envelope's enumerated check types do not yet include those identifiers, retain them in the private release record until the public schema is versioned rather than inventing an unsupported public value.

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

The private recovery record should answer, at minimum:

- was the backup payload actually encrypted by the approved KMS/key version;
- did manifest/signature/ciphertext/KMS/AEAD/plaintext verification pass;
- did WAL coverage remain continuous through the approved target;
- what recovery point was reached and what RPO did that imply;
- how long did the real restore/reconciliation take and what RTO did that imply;
- did PostgreSQL reach/promote at the intended timestamp/LSN;
- did database reconciliation and external-artifact reconciliation pass;
- were the required independent approvals recorded before return to service.

A `passed` public runtime-evidence result requires a private evidence fingerprint. A failed, blocked, or unexecuted result remains visible and cannot be converted into a pass through documentation.

## Browser evidence

The public browser suite uses synthetic content and validates two-column geometry, responsive collapse, horizontal overflow, keyboard reachability, chart-window containment, reduced motion, and 125–200% zoom emulation.

Private staging browser tests may add authenticated end-to-end flows and screenshots. Screenshots must be reviewed for tokens, account names, domains, provider identifiers, prompts, report content, browser history, developer tools, and operating-system chrome before public publication. Prefer publishing a bounded runtime check and screenshot hash rather than the screenshot itself.

## Recovery evidence handling

Backup manifests, KMS ARNs/key IDs, database system identifiers, WAL filenames/LSNs, restore paths, PostgreSQL logs, storage versions, and signer fingerprints can reveal useful internal topology or trust information. Even when none is a password, that does not make the full recovery bundle appropriate for a public repository.

Public CI may retain synthetic/disposable recovery artifacts because its database, key material, paths, and contents are generated only for that job. Production recovery evidence should remain in the private evidence system. Public traceability should normally consist of a bounded pass/fail/blocked status, the release/commit identity, and a SHA-256 fingerprint of the retained private evidence.

The repository's configured 15-minute RPO and four-hour RTO are policy objectives. Do not publish them as observed results unless the target exercise measured and retained the data needed to calculate them.

## Inventory and final coverage hash

Generate baseline and final inventories from clean checkouts:

```bash
python scripts/assurance/inventory_repository.py . --output artifacts/assurance/repository-inventory.json
```

The bundle identity excludes timestamps and absolute checkout paths. Symlinks are not followed; absolute symlink targets are represented only by a digest. Any read error or unsupported filesystem object fails completeness by default.

## Security assertions

- A local encrypted file store is not a production secret authority.
- A local backup catalogue is not automatically immutable/replicated backup storage.
- A KMS adapter is not proof of the deployment's KMS IAM/key policy.
- A signed manifest is not a substitute for decrypting/authenticating the actual backup object.
- A restore plan is not a completed restore.
- A disposable CI restore is not a production disaster-recovery exercise.
- A configured RPO/RTO is not an observed RPO/RTO.
- A reverse proxy is not the sole GUI authorization boundary.
- A tag is not an immutable image identity.
- A successful configuration parse is not runtime proof.
- A repository change is not deployment proof.
- Sanitization is not approval to publish raw private evidence.
- No risk is accepted on behalf of maintainers.
