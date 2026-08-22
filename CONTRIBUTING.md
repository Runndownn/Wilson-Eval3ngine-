# Contributing to Wilson Eval3ngine

Thank you for your interest in contributing to Wilson Eval3ngine (WE3). This
document explains how to set up a development environment, run tests, and submit
changes. Please read it before opening a pull request.

## Table of contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting started](#getting-started)
3. [Development workflow](#development-workflow)
4. [Code style](#code-style)
5. [Testing](#testing)
6. [Security and secrets](#security-and-secrets)
7. [Documentation](#documentation)
8. [Pull request process](#pull-request-process)
9. [Reporting vulnerabilities](#reporting-vulnerabilities)

## Code of Conduct

By participating in this project you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md). Be respectful and constructive in all
interactions.

## Getting started

### Prerequisites

- **Python** 3.12, 3.13, or 3.14 (developed against 3.13)
- **Git**
- **Docker** and **Docker Compose** (only needed for full-stack testing)
- **Playwright** (only needed for browser-assurance tests; see
  [Browser assurance](#browser-assurance))

### Clone and install

```bash
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip

# Install with dev, postgres, and redis extras for full test coverage
python -m pip install -e ".[dev,postgres,redis]"
```

### Quick sanity check

```bash
we3 validate examples/experiments/foundation.yaml
```

You should see `"valid": true` in the output.

## Development workflow

WE3 follows a **modular monolith** architecture (see
[ADR-001](docs/adrs/ADR-001-modular-monolith.md)). Source code lives under
`src/wilson_eval3ngine/` and is organized into bounded modules:

| Module | Responsibility |
|---|---|
| `domain/` | Pydantic contracts, enums, state machines, provenance |
| `expectations/` | Immutable expectation compilation before execution |
| `providers/` | Provider adapters (mock, Ollama, local, etc.) |
| `grading/` | Five-outcome classification and calibration |
| `metrics/` | Metric snapshots and Wilson confidence intervals |
| `gates/` | Release-gate logic with critical-event precedence |
| `evidence/` | Content-addressed, SHA-256 immutable evidence |
| `api/` | REST API with OIDC, CSRF, and rate limiting |
| `security/` | OIDC auth, RBAC, input validation, redaction |
| `gui/` | Local-operator browser interface (loopback-bound) |
| `observability/` | SLIs/SLOs, dashboards, error budgets |
| `persistence/` | SQLAlchemy models, migrations, outbox pattern |
| `assurance/` | Inventory, image-reference, and runtime-evidence controls |

### Branch naming

| Type | Format |
|---|---|
| Feature | `feat/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Security | `security/<short-description>` |
| Documentation | `docs/<short-description>` |
| Maintenance | `chore/<short-description>` |

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(grading): add multilingual ambiguity classifier

The deterministic grader now normalizes Unicode before classification so
that visually identical prompts with different encodings produce consistent
outcomes. Adds 12 golden-fixture tests covering CJK, Arabic, and accented
Latin scripts.
```

Prefixes used in this project:

- `feat` — new capability
- `fix` — bug fix
- `security` — security hardening
- `refactor` — internal restructuring without behaviour change
- `docs` — documentation only
- `chore` — housekeeping, CI, tooling

## Code style

- **Formatter**: The project does not enforce a formatter in CI yet. Use
  [Black](https://black.readthedocs.io/) with the default line length (88)
  for consistency.
- **Linting**: `python -m compileall -q src tests scripts` followed by
  `node --check` on the JavaScript files under `gui/static/`.
- **Type hints**: All new functions should include type annotations.
- **Imports**: Follow
  [PEP 8 import ordering](https://peps.python.org/pep-0008/#imports):
  standard library, third-party, local.
- **Docstrings**: Use
  [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

### Security review before merging

Every pull request that touches authentication, authorization, secret
handling, input validation, provider egress, or rendering must be reviewed
for the relevant security invariants listed in
[SECURITY.md](SECURITY.md).

## Testing

### Run the full suite

```bash
make test
```

### Run with coverage

```bash
make coverage
```

The coverage gate is 80 % branch coverage for foundation modules.

### Run specific test groups

```bash
# Security-focused regression suite
python -m pytest -q \
  tests/governance/test_production_deployment_contract.py \
  tests/unit/test_gui_secret_transport.py \
  tests/unit/test_gui_ux6.py \
  tests/unit/test_streaming_body_limit.py \
  tests/unit/test_gui_bind_security.py \
  tests/unit/test_gui_egress_policy.py \
  tests/unit/test_assurance_inventory.py \
  tests/unit/test_gui_access_control.py \
  tests/unit/test_image_references.py \
  tests/unit/test_log_redaction.py \
  tests/unit/test_runtime_evidence.py \
  tests/unit/test_secret_transport_factory.py \
  tests/unit/test_secrets_backend.py

# Adversarial and governance tests
python -m pytest -q tests/governance/adversarial/ tests/governance/compliance/

# Hostile scenario tests
python -m pytest -q tests/hostile/
```

### Test markers

| Marker | Meaning |
|---|---|
| `@pytest.mark.browser` | Requires Playwright + Chromium; run with `pip install ".[dev,browser]"` |
| `@pytest.mark.runtime` | Requires an explicitly authorized isolated runtime |

Skip browser and runtime tests in CI:

```bash
python -m pytest -q -m "not browser and not runtime"
```

### Browser assurance

```bash
python -m pip install -e ".[dev,browser]"
python -m playwright install --with-deps chromium
python -m pytest -q -m browser tests/browser
```

### Adding tests

- New features must include unit tests covering the primary behaviour.
- Security-relevant changes must include negative tests (e.g., injection,
  path traversal, authorization bypass).
- Statistical or metric changes must include mutation tests that detect
  denominator drift (see
  `tests/governance/adversarial/test_adversarial_gates.py`).
- Integration tests should use the mock provider unless a real provider is
  required by the test, and the test must document the dependency.

## Security and secrets

**Never commit secrets.** The repository includes a
[secret-detection](src/wilson_eval3ngine/supply_chain/__init__.py) step in CI.
If you add a file that looks like a credential and it is committed, the CI
pipeline will fail.

Guidelines:

- Copy `.env.example` to `.env` and fill in values locally; `.env` is
  git-ignored.
- Do not paste credentials, API keys, or private topology into issues, pull
  requests, or comments.
- Do not include screenshots that show real credentials.
- Development header authentication is prohibited in production mode
  (see [SECURITY.md](SECURITY.md)).

### Supply-chain scanning

The CLI includes a built-in supply-chain scanner:

```bash
we3 scan-ci --source . --output var/supply_chain_report.json
```

You can also run it via the full security extras:

```bash
python -m pip install -e ".[security]"
```

## Documentation

Documentation lives under `docs/` and is organised as follows:

| Directory | Purpose |
|---|---|
| `docs/adrs/` | Architecture Decision Records |
| `docs/architecture/` | Threat model and system architecture |
| `docs/operations/` | Runbooks for CI, certification, backup, game-day, etc. |
| `docs/design/` | Interface and workflow design notes |
| `docs/security/` | Master security assessment and runtime assurance contracts |
| `docs/reports/` | Model evaluation results and charts |

When you add or change a user-facing feature, update the relevant README
section and any design or runbook documents.

## Pull request process

1. **Fork** the repository and create a feature branch from `main`.
2. **Write tests** that cover the new behaviour (see
  [Testing](#testing)).
3. **Run the full test suite** locally: `make test` and `make coverage`.
4. **Verify lint**: `make lint`.
5. **Check supply chain**: `we3 scan-ci --source .` should report no
  blocking items.
6. **Open a pull request** using the
  [PR template](.github/PULL_REQUEST_TEMPLATE.md).
7. **Wait for CI** to pass. The full quality and security suite may take
  several minutes.
8. **Request review** from a maintainer. Security-sensitive changes
  require at least one security-aware reviewer.

### PR review checklist

- [ ] Tests added or updated and passing locally
- [ ] `make lint` passes
- [ ] `we3 scan-ci` reports no blocking findings
- [ ] Documentation updated for user-facing changes
- [ ] No secrets, credentials, or private topology introduced
- [ ] New commands or CLI flags documented in the README
- [ ] Breaking changes documented in `CHANGELOG.md`

## Reporting vulnerabilities

See the [Security Policy](SECURITY.md). Report suspected vulnerabilities
privately — do not open public issues for security problems.

## Acknowledgements

This project was built using the
[Geezer Mekanix Agentic Engineering Platform](https://github.com/Runndownn/geezer-mekanix).
See the [Agentic Engineering Origin](README.md#agentic-engineering-origin)
section in the README for details.
