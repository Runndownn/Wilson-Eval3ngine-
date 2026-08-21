# Getting Started

This guide gets Wilson Eval3ngine running locally with no provider credentials, then shows how to open the operator GUI.

## 1. Prerequisites

- Python `3.12`, `3.13`, or `3.14`
- Git
- Node.js only if you intend to run the JavaScript syntax checks in `make lint`

## 2. Install from source

```bash
git clone https://github.com/Runndownn/Wilson-Eval3ngine-.git
cd Wilson-Eval3ngine-
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The package installs two main entry points: `we3` for CLI workflows and `we3-gui-start` for the local operator workspace.

## 3. Run the credential-free foundation demo

Validate the included experiment:

```bash
we3 validate examples/experiments/foundation.yaml
```

Run it against the deterministic mock provider:

```bash
we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts
```

Verify the signed dossier:

```bash
we3 verify-dossier var/foundation/release_dossier.json
```

The Makefile exposes the same flow as `make validate`, `make demo`, and `make verify`.

## 4. Start the operator GUI

```bash
we3-gui-start --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

The official launcher is intentionally loopback-only. Do not expose it directly on a LAN or public interface. Remote access requires a separately authenticated TLS proxy and an explicit access policy.

## 5. Connect a model provider

Use **Endpoints** in the GUI. Provider credentials should be entered through the supported credential field rather than committed to files or shell history.

For local/private endpoints, the default policy denies private/loopback provider destinations. Enable them deliberately only for a trusted local gateway:

```bash
WE3_GUI_ALLOW_LOCAL_PROVIDERS=1 we3-gui-start --host 127.0.0.1 --port 8080
```

For a full walkthrough of hosted providers, Ollama, CLI providers, credential rotation, and production secret handling, see [Provider Credentials and Local Model Endpoints](operations/api-key-local-model-setup.md).

## 6. Run the API locally

```bash
WE3_DATABASE_URL=sqlite:///./var/api.db WE3_ARTIFACT_ROOT=./var/api-artifacts we3 serve --host 127.0.0.1 --port 8000
```

This is a local development configuration, not a production deployment.

## 7. Validate the checkout

```bash
make lint
make test
make coverage
```

## What to read next

- [Features](FEATURES.md) — what WE3 does and why.
- [GUI and Evidence Guide](GUI_AND_EVIDENCE_GUIDE.md) — operator workflow and visuals.
- [Architecture](ARCHITECTURE.md) — how the components fit together.
- [Current Status](STATUS.md) — what is implemented, integrated, and still unproven.
