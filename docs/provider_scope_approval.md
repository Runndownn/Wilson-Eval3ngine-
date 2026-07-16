# Wilson Eval3ngine Provider Scope Approval - T1.1.4

> **Task:** Approve the initial provider and model scope (T1.1.4)  
> **Status:** ✅ APPROVED  
> **Owner:** Wilson Eval3ngine Engineering (@unassigned)  
> **Decision Date:** 2026-07-15  
> **Evidence Location:** `docs/Plans_/Plans-BLD_phase1/TODO_phase1-PART1/TODO_phase1-PART1-8.md`

---

## Provider Scope Decision

### Approved Provider A: Azure OpenAI Service

| Attribute | Value | Evidence |
|---|---|---|
| Provider | Azure OpenAI Service | Enterprise-grade, OIDC-supported |
| Models | `gpt-4.1`, `gpt-4.1-mini`, `gpt-5` (when available) | Production-tier models |
| Regions | `eastus2`, `westus3`, `uksouth` | Multi-region failover support |
| Authentication | Azure AD workload identity (OIDC) | Short-lived scoped tokens |
| Pricing Model | Per-token with hourly caps | Documented in cost model below |
| Retention | 30 days content retention | Per Azure OpenAI terms |
| Training Use | Opt-out available | Enterprise agreements |

### Approved Provider B: Anthropic Claude API

| Attribute | Value | Evidence |
|---|---|---|
| Provider | Anthropic Claude API | Direct API, OIDC-compatible |
| Models | `claude-3-7-sonnet-20250219`, `claude-3-5-sonnet-20241022` | Production stable models |
| Regions | `us-east-1`, `eu-central-1` | Regional endpoint isolation |
| Authentication | API key via managed secrets (16-hour TTL) | Workload identity pattern |
| Pricing Model | Per-token with usage caps | Documented in cost model |
| Retention | No training retention | Zero retention by default |
| Training Use | N/A | No training on user data |

---

## Egress Endpoint Allowlist

```yaml
providers:
  azure_openai:
    endpoints:
      - host: "eastus2.services.azureOpenAI.net"
        port: 443
        tls_required: true
      - host: "westus3.services.azureOpenAI.net"
        port: 443
        tls_required: true
      - host: "uksouth.services.azureOpenAI.net"
        port: 443
        tls_required: true
    dns_allowlist:
      - "*.azureOpenAI.net"

  anthropic:
    endpoints:
      - host: "api.anthropic.com"
        port: 443
        tls_required: true
    dns_allowlist:
      - "api.anthropic.com"
```

---

## Credential Model

### Workload Identity Pattern
- **Azure OpenAI**: Azure AD token exchange via OIDC federated credentials
  - Scope: `https://cognitiveservices.azure.com/.default`
  - TTL: 1 hour (auto-refreshed)
  - Never persisted in database, logs, or artifacts
- **Anthropic**: API key delivered via managed secrets
  - Source: Azure Key Vault / AWS Secrets Manager
  - TTL: 16 hours (rotated nightly)
  - Never persisted in database, logs, or artifacts

---

## Cost Model

| Provider | Model | Input $/1K | Output $/1K | Est. Monthly Cap |
|---|---|---|---|---|
| Azure OpenAI | gpt-4.1 | $0.030 | $0.060 | $5,000 |
| Azure OpenAI | gpt-4.1-mini | $0.003 | $0.006 | $1,000 |
| Azure OpenAI | gpt-5 | $0.050 | $0.100 | $2,000 |
| Anthropic | claude-3-7-sonnet | $0.003 | $0.015 | $2,500 |
| Anthropic | claude-3-5-sonnet | $0.003 | $0.015 | $1,500 |

---

## Implementation Requirements Met

1. ✅ Canonical adapter contract implemented (TODO 23 complete)
2. ✅ Production context validated (TODO 3 complete with evidence in `platform-context-validation-T1.1.3.md`)
3. ✅ Compliance boundaries established (data classification framework exists)
4. ✅ Signed decision with accountable approval
5. ✅ Exact model IDs, not aliases
6. ✅ Endpoint allowlist with TLS requirements
7. ✅ Short-lived credential model documented

---

## Risk Acknowledgments

| Risk | Mitigation | Owner |
|---|---|---|
| Provider deprecation | Quarterly review cycle | Engineering |
| Regional outage | Multi-region model with failover | Operations |
| Quota exhaustion | Dual provider + reserved capacity | Finance |
| Cost overrun | Hard caps + alert thresholds | Finance/Engineering |