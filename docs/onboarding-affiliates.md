# Onboarding affiliates (scaling the real-data pull)

The backend turns **affiliates** into live Azure Cost Management pulls. Onboarding
a new affiliate — a business unit, customer, or tenant — is a **config change**,
not a code change. Three modes, in order of scale:

## 1. Zero-config (single tenant, auto-discovery)

Just `az login` and set `USE_MOCK=false`. Every subscription the signed-in
identity can read becomes its own affiliate. Good for getting started.

```dotenv
USE_MOCK=false
DATA_BACKEND=azure
# AZURE_SUBSCRIPTION_IDS blank -> discover all
```

Narrow to specific subscriptions without a registry:

```dotenv
AZURE_SUBSCRIPTION_IDS=1111-....,2222-....
```

## 2. Affiliate registry (recommended for scale)

Map affiliates to subscriptions/tenants in a JSON file. One affiliate can span
**multiple subscriptions**, optionally in **its own tenant**. Copy the sample and
edit:

```powershell
cd backend
copy affiliates.example.json affiliates.json
```

```jsonc
{
  "affiliates": [
    {
      "affiliate_id": "aff-001",
      "name": "Contoso Retail",
      "tenant_id": "1111....",          // omit to use the signed-in tenant
      "agreement_type": "EA",           // EA | MCA
      "billing_account": "7654321",
      "billing_profile": null,
      "subscription_ids": ["aaaa...."]  // one or many
    }
  ]
}
```

The backend auto-detects `backend/affiliates.json`, or point it anywhere:

```dotenv
AFFILIATE_REGISTRY=C:\config\affiliates.json
```

`affiliates.json` is git-ignored (it holds real tenant/subscription IDs). To
onboard the next affiliate, add an entry and restart the backend (or wait for the
cache TTL). No redeploy, no code.

### Bulk onboarding from the infra CSV

`infra/affiliates.sample.csv` is the same data in spreadsheet form. Convert it to
a registry:

```powershell
Import-Csv infra\affiliates.sample.csv |
  Group-Object AffiliateId | ForEach-Object {
    $r = $_.Group[0]
    [pscustomobject]@{
      affiliate_id     = $r.AffiliateId
      name             = $r.Name
      tenant_id        = $r.TenantId
      agreement_type   = $r.AgreementType
      billing_account  = $r.BillingAccount
      billing_profile  = if ($r.BillingProfile) { $r.BillingProfile } else { $null }
      subscription_ids = @($_.Group.SubscriptionId | Where-Object { $_ })
    }
  } | ConvertTo-Json -Depth 5 |
  ForEach-Object { '{ "affiliates": ' + $_ + ' }' } |
  Set-Content backend\affiliates.json
```

## 3. Central FinOps hub (100+ affiliates, cross-tenant exports)

For fleet scale, keep the registry but back the data with FinOps-hub exports into
ADX/Fabric (`DATA_BACKEND=adx`) instead of live per-subscription queries. See
[`../infra/README.md`](../infra/README.md) — `Onboard-Affiliate.ps1` provisions
satellite exports, and the registry still names the affiliates the dashboard shows.

## Cross-tenant authentication

| Scenario | Auth |
|---|---|
| Affiliates in **your** tenant | `az login` (DefaultAzureCredential) — nothing else |
| Affiliates in **other** tenants | A **multi-tenant app registration**: set `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET`, grant it the read roles below in each affiliate tenant, and set each affiliate's `tenant_id` in the registry. The backend mints a token per tenant automatically. |

## Per-feed permissions

Each data feed needs its own read-only grant. Missing grants degrade that feed to
empty (never an error), so onboard incrementally.

| Feed | Grant | Where |
|---|---|---|
| **Cost / breakdown / AI $ / TCO / offer mix** | Cost Management Reader | Subscription (or billing scope) |
| **RI & savings-plan recommendations, existing commitments** | Reader / Cost Management Reader | Subscription + tenant |
| **Licenses & M365 Copilot seats** | Microsoft Graph **Organization.Read.All** (app permission, admin-consented) or Directory.Read.All | Affiliate tenant (Entra ID) |
| **GitHub Copilot seats & acceptance** | `GITHUB_TOKEN` with **manage_billing:copilot** (or read:org + Copilot) | GitHub org(s) |
| **Azure OpenAI tokens** | Monitoring Reader (covered by Reader) | AI resources |
| **MACC** commitments | **Billing Reader** | Billing account, plus set `billing_account` on the affiliate |

### GitHub Copilot (external seats)

Copilot seats and acceptance come from the GitHub REST API per org. Create a
token with `manage_billing:copilot` (or `read:org` + Copilot) and list the orgs
globally or per affiliate:

```dotenv
GITHUB_TOKEN=ghp_xxx
GITHUB_ORGS=my-org,another-org
GITHUB_COPILOT_SEAT_COST=39.0   # USD/seat/mo (Enterprise; Business ~19)
M365_COPILOT_SEAT_COST=30.0
```

Or scope orgs to an affiliate in the registry:

```jsonc
{ "affiliate_id": "aff-001", "name": "Contoso", "subscription_ids": ["..."],
  "github_orgs": ["contoso", "contoso-labs"] }
```

GitHub returns seats + acceptance, not price, so cost is `seats x seat_cost`.
M365 Copilot seats come from the Entra licenses feed (already counted in license
spend); GitHub Copilot is the only truly *external* Copilot in TCO.

### Azure OpenAI tokens

Real prompt/completion token counts come from Azure Monitor (`TokenTransaction`
metric) on your Azure OpenAI / AI Foundry resources — no extra config beyond
Reader. Platform metrics retain ~93 days, so older months show 0 tokens.

### Licenses (Microsoft Graph)

Seats come from Graph `subscribedSkus` per affiliate **tenant**. For an app
registration, add the **Organization.Read.All** *application* permission and grant
admin consent in each tenant. Graph returns no price, so costs use built-in
list-price estimates keyed by `skuPartNumber`; override with your negotiated
pricing via `LICENSE_PRICE_MAP`:

```dotenv
LICENSE_PRICE_MAP=C:\config\license-prices.json
```

```json
{
  "SPE_E5": { "name": "Microsoft 365 E5", "unit_cost": 54.0 },
  "POWER_BI_PRO": 8.5
}
```

### MACC (Microsoft Azure Consumption Commitment)

Set the affiliate's `billing_account` in the registry and grant the identity
**Billing Reader** on that billing account. The backend reads commitment `lots`
(balance) and `events` (drawdown) via the Consumption API. Without a
`billing_account` (e.g. subscription auto-discovery mode) MACC is simply empty —
correct for subscriptions with no commitment.

Read-only access is enough everywhere — Cost Management Reader / Billing Reader /
Graph Organization.Read.All.

## Verify

```powershell
cd backend
$env:USE_MOCK="false"
python -m app.live_smoke                 # lists affiliates + real spend
```

The dashboard header shows a **Live Azure** / **Demo data** badge reflecting the
current `USE_MOCK` mode.
