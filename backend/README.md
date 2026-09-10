# Backend — Affiliate FinOps API

FastAPI service exposing affiliate, MACC, cost, and license data to the dashboard.
Runs in **demo mode** (deterministic mock data) with zero Azure dependencies, or in
**live mode** pulling real data straight from Azure Cost Management / Consumption /
Microsoft Graph — no FinOps hub required for a single subscription.

## Run (demo)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env         # USE_MOCK=true
uvicorn app.main:app --reload --port 8081
# Swagger: http://localhost:8081/docs
```

## Test
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Endpoints (`/api/v1`)
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + mode (mock/live) + data_source |
| GET | `/summary` | Portfolio KPIs (commitment, remaining, at-risk, MTD cost) |
| GET | `/affiliates` | Affiliate registry |
| GET | `/macc/balances` | MACC balance per affiliate |
| GET | `/macc/{affiliate_id}` | MACC detail — balance + burn-down trend + drawdown events |
| GET | `/costs?affiliate_id=` | Cost summary (trend + by-service) |
| GET | `/licenses?affiliate_id=` | License inventory |

## Going live (`USE_MOCK=false`)
`app/services/provider.py` selects `MockDataProvider` or the real
`AzureDataProvider` (`app/services/azure_provider.py`). The live provider pulls:

- **Affiliates** — the affiliate registry (`affiliates.json`) or auto-discovered
  subscriptions (`app/services/affiliate_registry.py`).
- **Cost / breakdown / hierarchy / AI / TCO / offer mix** — Azure Cost Management
  Query API (`app/services/azure_cost.py`), with 429 backoff + TTL cache.
- **Reservation & savings-plan recommendations + existing commitments** —
  Consumption `reservationRecommendations`, CostManagement `benefitRecommendations`,
  Capacity `reservationOrders`, BillingBenefits `savingsPlans`.
- **Licenses** — Microsoft Graph `subscribedSkus` (`app/services/graph_client.py`)
  valued via `app/services/license_prices.py`.
- **MACC** — Consumption `lots` + `events` per billing account.

Auth is `DefaultAzureCredential` (`az login`) or a multi-tenant app registration;
tokens are minted per tenant. Each feed degrades to empty when its permission is
missing. See [`../docs/onboarding-affiliates.md`](../docs/onboarding-affiliates.md)
for per-feed permissions and scaling. Preview live numbers with
`python -m app.live_smoke`. The API response shapes are identical in both modes,
so the frontend never changes.

> `app/services/macc_puller.py` remains as a standalone timer-Function example of
> the same `lots`/`events` pull; the live provider now calls the integrated
> `AzureCostClient` methods directly.


