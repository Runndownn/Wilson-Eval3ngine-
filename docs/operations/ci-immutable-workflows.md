# CI Immutable Workflows

This document describes the deterministic, immutable CI workflow configuration for Wilson Eval3ngine.

## Workflow Pinning

All GitHub Actions are pinned to immutable SHA references to prevent supply chain attacks:

```yaml
# Example: Action pinned to SHA
- uses: actions/checkout@9fa26c6fa94ac1d24e1a3f4e5e6e7e8e9fa0b1c2  # v4.1.0
```

Never use:
- Branch names: `actions/checkout@main`
- Version tags only: `actions/checkout@v4` (use SHA instead)

## Build Determinism

### Input Digest Recording
- Source commit SHA recorded for each build
- All dependencies pinned with exact versions
- Lock files verified with SHA256 hashes

### Artifact Verification
- All artifacts must be signed with Ed25519 keys
- Artifact digests computed and stored
- Trust registry validation in production

## Backup Verification Job

Weekly cron job `backup-verification` runs:
1. Backup integrity verification tests
2. PITR restore to isolated environment
3. Reconciliation report generation

## Drift Detection

The CI pipeline detects:
- Unpinned actions (high severity)
- Missing signatures (block)
- Dependency vulnerabilities (risk-based)
- IaC security issues (fail)

## Reproduction Environment

To reproduce a build:

```bash
# Set exact environment
export PYTHON_VERSION=3.13
export PIP_VERSION=25.0.1
export COMMIT_SHA=<target_commit>

# Install pinned tools
pip install build==1.2.1 twine==6.0.1

# Build
python -m build --no-isolation
sha256sum dist/*.whl
```