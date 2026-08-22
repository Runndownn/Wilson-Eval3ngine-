## Description

<!-- Brief description of what this PR does -->

## Motivation

<!-- Why is this change needed? Link to an issue or describe the problem -->

## Changes

<!-- Summary of changes, key files reviewed/modified -->

- [ ]
- [ ]
- [ ]

## Testing

<!-- How was this validated? -->

- [ ] `make test` passes
- [ ] `make coverage` meets the 80 % branch threshold
- [ ] New tests added/updated with justification
- [ ] Security regression suite passes:
  ```bash
  python -m pytest -q \
    tests/governance/test_production_deployment_contract.py \
    tests/unit/test_gui_secret_transport.py \
    tests/unit/test_streaming_body_limit.py \
    tests/unit/test_gui_bind_security.py \
    tests/unit/test_gui_egress_policy.py \
    tests/unit/test_assurance_inventory.py \
    tests/unit/test_log_redaction.py \
    tests/unit/test_runtime_evidence.py \
    tests/unit/test_secret_transport_factory.py \
    tests/unit/test_secrets_backend.py
  ```
- `we3 scan-ci --source .` reports no blocking findings

## Security checklist

- [ ] No secrets, credentials, or private topology committed or pasted in
  comments
- [ ] `.env.example` updated if new configuration values were added
- [ ] Changes to auth, RBAC, input validation, egress, or rendering reviewed
  against [SECURITY.md](SECURITY.md)
- [ ] New endpoints include appropriate authorization and rate-limiting
- [ ] Error responses do not leak internal state

## Documentation

- [ ] README.md updated for user-facing changes (CLI flags, config, behaviour)
- [ ] CHANGELOG.md updated under "Added" / "Fixed" / "Removed"
- [ ] New commands or config variables documented
- [ ] Runbooks updated if operational procedures changed

## Release

- [ ] Breaking changes documented and justified
- [ ] Schema or API changes registered in `contracts/`
- [ ] ADR created if an architectural decision was made
