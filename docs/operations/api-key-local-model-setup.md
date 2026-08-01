# API Key & Local Model Configuration Guide

## Overview

Wilson Eval3ngine supports two model access pathways:

1. **Kilo Gateway** (`https://api.kilo.ai/api/gateway`) — OpenAI-compatible API proxy with 346 models across 60+ providers (Anthropic, OpenAI, Google, DeepSeek, Qwen, etc.)
2. **Local Ollama** (`http://10.133.7.211:11434`) — On-premises model serving with 6 locally hosted models

This document covers how to obtain, configure, and activate API keys for both pathways.

---

## 1. Kilo Gateway API Key

### 1.1 How to Obtain

The Kilo Gateway uses OAuth device-flow authentication. No static API key is generated — instead, the Kilo CLI exchanges a device code for a short-lived access token (JWT) and a refresh token (JWT).

**Prerequisites:**
- Kilo CLI installed at `/usr/local/bin/kilo` (v7.3.50)
- A Kilo account at `https://app.kilo.ai`

**Steps:**

```bash
# Step 1: Initiate device auth flow
kilo auth login --provider kilo

# Step 2: The CLI prints a URL and code:
#   Go to: https://app.kilo.ai/device-auth?code=XXXX-XXXX
#   Enter code: XXXX-XXXX

# Step 3: Open the URL in a browser, confirm the code
# Step 4: Wait for "Login successful" in the terminal
```

The CLI polls until you complete the browser step, then writes credentials to `~/.local/share/kilo/auth.json`.

**Resulting credential file:**

```json
{
  "kilo": {
    "type": "oauth",
    "refresh": "eyJhbGciOiJIUzI1NiIs...<JWT>",
    "access": "eyJhbGciOiJIUzI1NiIs...<JWT>",
    "expires": 1816956593874
  }
}
```

- **Access token** (JWT): Used as Bearer token for gateway requests. Valid ~1 hour.
- **Refresh token** (JWT): Used to obtain new access tokens. Valid ~1 year.
- **Expires**: Unix epoch in milliseconds (currently ~2027-07-30).

### 1.2 Where It Goes

The OAuth tokens are stored in:

| Location | Purpose |
|---|---|
| `~/.local/share/kilo/auth.json` | Kilo CLI credential store (OAuth tokens) |
| `gui/data/endpoints.json` | Wilson Eval3ngine GUI endpoint registry (apiKey field) |
| Environment variable `WE3_REPORT_GATEWAY_API_KEY` | Report generation script fallback |
| Environment variable `WE3_REPORT_API_KEY_FILE` | Path to a file containing the API key (preferred for scripts) |
| `~/.we3/secret_key` | Fernet master key for encrypted key vault |
| `~/.we3/audit.log` | Audit trail of all key access events |

### 1.3 How to Apply It

#### For the Kilo CLI (automatic)

After `kilo auth login`, the CLI automatically uses the access token from `auth.json`. No manual configuration needed.

#### For Wilson Eval3ngine GUI

The GUI reads credentials from `gui/data/endpoints.json`. Each endpoint has an `apiKey` field:

```json
[
  {
    "id": "ep_26c09ed6",
    "name": "Kilo Gateway",
    "provider": "kilo",
    "url": "https://api.kilo.ai/api/gateway",
    "apiKey": null,
    "available": true
  }
]
```

**To set the API key via the GUI:**
1. Start the GUI server: `python -m wilson_eval3ngine.gui.server`
2. Navigate to `http://localhost:8080`
3. Go to **Settings → Endpoints**
4. Click "Edit" on the "Kilo Gateway" endpoint
5. Paste the access token into the API Key field
6. Click "Save" and "Test Connection"

The GUI automatically migrates plaintext `apiKey` fields to encrypted `encryptedApiKey` fields on startup (see `_migrate_legacy_api_keys()` in `server.py`).

#### For the Report Generation Script

```bash
# Method 1: Direct environment variable
export WE3_REPORT_GATEWAY_API_KEY="<access_token_from_auth.json>"

# Method 2: Key file (more secure — no env var exposure)
echo "<access_token>" > /tmp/we3_key.txt
chmod 600 /tmp/we3_key.txt
export WE3_REPORT_API_KEY_FILE="/tmp/we3_key.txt"

# Then run the script
python scripts/generate_5_reports.py --gateway https://api.kilo.ai/api/gateway \
  --provider kilo --model kilo-auto/free --prompts 5
```

#### For Direct API Usage

```bash
# Extract the access token from auth.json
ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('~/.local/share/kilo/auth.json'))['kilo']['access'])")

# Use it as a Bearer token
curl -s "https://api.kilo.ai/api/gateway/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"model":"kilo-auto/free","messages":[{"role":"user","content":"Hello"}],"stream":false,"max_tokens":50}'
```

### 1.4 Process to Have It Be Active

1. **Authenticate** — Run `kilo auth login --provider kilo` and complete the device flow
2. **Verify** — Run `kilo auth list` to confirm credentials are stored:
   ```
   ┌  Credentials ~/.local/share/kilo/auth.json
   │
   └  ●  Kilo Gateway  oauth
   ```
3. **Test** — Verify the access token works with the gateway:
   ```bash
   ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('~/.local/share/kilo/auth.json'))['kilo']['access'])")
   curl -s "https://api.kilo.ai/api/gateway/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $ACCESS_TOKEN" \
     -d '{"model":"kilo-auto/free","messages":[{"role":"user","content":"Hello"}],"stream":false,"max_tokens":10}'
   ```
4. **Configure in GUI** — Paste the access token into `gui/data/endpoints.json` (apiKey field) or use the GUI Settings page
5. **Token refresh** — The Kilo CLI auto-refreshes the access token. For long-running scripts, re-run `kilo auth login` if you get 401 errors

### 1.5 Available Kilo Gateway Models

The gateway provides 346 models across 60+ providers. Key routing models:

| Model | Description |
|---|---|
| `kilo-auto/frontier` | Routes to the most capable model available |
| `kilo-auto/balanced` | Routes to a balanced performance/cost model |
| `kilo-auto/efficient` | Routes to a fast, efficient model |
| `kilo-auto/free` | Routes to free-tier models (currently stepfun/step-3.7-flash) |
| `kilo-auto/small` | Routes to lightweight models |

**Provider examples:**
- `anthropic/claude-sonnet-5`, `anthropic/claude-opus-5`
- `openai/gpt-5.6-sol`, `openai/gpt-4.1`
- `google/gemini-3.6-flash`, `google/gemini-2.5-pro`
- `deepseek/deepseek-v4-pro`
- `qwen/qwen3.7-plus`, `qwen/qwen3.7-flash`
- `poolside/laguna-s-2.1` (the model currently running this session)

**Note:** The Kilo CLI prefixes models with `kilo/` when listing (e.g., `kilo/auto/free`), but the gateway API uses the bare provider path (e.g., `kilo-auto/free`).

---

## 2. Local Ollama Models

### 2.1 Available Local Models

The local Ollama gateway at `http://10.133.7.211:11434` hosts 6 models:

| Model | Size | Purpose |
|---|---|---|
| `bge-m3:latest` | 1.1 GB | Embedding/indexing model (used by Kilo for code search) |
| `gemma3:4b` | 3.2 GB | General-purpose small model |
| `gpt-oss:latest` | 13.2 GB | Main OSS model (large, slow) |
| `llama3.2:1b` | 1.3 GB | Lightweight model for quick tests |
| `qwen3:4b` | 2.4 GB | Qwen 3 instruction model |
| `tinyllama:latest` | 608 MB | Smallest model, fastest response |

### 2.2 No API Key Required

The local Ollama gateway does **not** require an API key. Requests are sent directly:

```bash
curl -s "http://10.133.7.211:11434/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss:latest","messages":[{"role":"user","content":"Hello"}],"stream":false,"options":{"temperature":0.0}}'
```

### 2.3 Configuring in Wilson Eval3ngine

In `gui/data/endpoints.json`, the Ollama endpoint has `"apiKey": null`:

```json
{
  "id": "ep_5806d0e2",
  "name": "SSH Gateway Ollama",
  "provider": "ollama",
  "url": "http://10.133.7.211:11434",
  "apiKey": null,
  "available": true
}
```

**To use local models in the GUI:**
1. Start the GUI server
2. Go to **Settings → Endpoints**
3. The "SSH Gateway Ollama" endpoint is pre-configured
4. Click "Test Connection" to verify availability
5. Select any local model from the model dropdown when configuring evaluations

### 2.4 Kilo CLI Indexing Configuration

The Kilo CLI uses `bge-m3:latest` on the local Ollama gateway for code indexing. This is configured in `~/.config/kilo/kilo.jsonc`:

```jsonc
"indexing": {
  "enabled": true,
  "model": "bge-m3:latest",
  "provider": "ollama",
  "embeddingBatchSize": 64,
  "dimension": 1024,
  "ollama": {
    "baseUrl": "http://10.133.7.211:11434"
  }
}
```

**To rebuild the index:**
```bash
# From any workspace directory
kilo index
```

### 2.5 Adding New Local Models

To pull a new model to the local Ollama gateway:

```bash
# SSH to the gateway host (or run locally if Ollama is on this machine)
ssh geezeradmin@10.133.7.211

# Pull a model
ollama pull <model-name>

# List available models
ollama list

# Run a test
ollama run <model-name> "Hello, what is 2+2?"
```

---

## 3. Security Notes

### 3.1 Key Storage

| Method | Security Level | Notes |
|---|---|---|
| `~/.local/share/kilo/auth.json` | High | OAuth tokens, auto-managed by Kilo CLI |
| `~/.we3/secret_key` | High | Fernet master key for encrypted vault |
| `WE3_REPORT_API_KEY_FILE` | Medium | Temp file with 0600 permissions |
| `WE3_REPORT_GATEWAY_API_KEY` | Low | Exposed in process environment |
| `gui/data/endpoints.json` (plaintext) | Low | Auto-migrated to encrypted on startup |

### 3.2 Best Practices

1. **Prefer the encrypted vault** — The GUI's `api_key_vault.py` uses Fernet (AES-128-CBC + HMAC-SHA256) with PBKDF2 key derivation (260k iterations)
2. **Never commit API keys** — `gui/data/endpoints.json` is in `.gitignore`
3. **Use key files for scripts** — `WE3_REPORT_API_KEY_FILE` avoids env var exposure
4. **Rotate tokens** — Re-run `kilo auth login` if you get 401 errors
5. **Audit logs** — Check `~/.we3/audit.log` for key access events

### 3.3 Key Redaction

The telemetry system automatically redacts API keys in logs:
- `sk-[A-Za-z0-9_-]{20,}` → `[REDACTED_API_KEY]`
- `"apiKey": "value"` → `"apiKey": "[REDACTED]"`

---

## 4. Troubleshooting

### 4.1 "Not authenticated with Kilo Gateway"

```bash
kilo auth login --provider kilo
# Complete the device flow in your browser
kilo auth list  # Verify credentials are stored
```

### 4.2 Gateway Returns Empty Content

Some routing models (e.g., `stepfun/step-3.7-flash`) return reasoning in the `reasoning` field instead of `content`. Check both fields in the response:

```bash
# The response may have content in "reasoning" instead of "content"
curl -s "https://api.kilo.ai/api/gateway/v1/chat/completions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"model":"kilo-auto/free","messages":[{"role":"user","content":"Hello"}],"stream":false,"max_tokens":50}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['choices'][0]['message']; print(m.get('content') or m.get('reasoning','(empty)'))"
```

### 4.3 Local Ollama Timeout

Large models (`gpt-oss:latest` at 13.2 GB) may take 60+ seconds for first response. Use smaller models for testing:

```bash
curl -s "http://10.133.7.211:11434/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"model":"tinyllama:latest","messages":[{"role":"user","content":"Hello"}],"stream":false,"options":{"temperature":0.0}}'
```

### 4.4 Endpoint Not Available in GUI

Check `gui/data/endpoints.json` — endpoints with `"available": null` or `"available": false` will be skipped. Test connectivity from the GUI Settings page.
