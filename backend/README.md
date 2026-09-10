# Backend — Affiliate FinOps API

FastAPI service exposing affiliate, MACC, cost, and license data to the dashboard.
Runs in **demo mode** (deterministic mock data) with zero Azure dependencies, or in
**live mode** against the central FinOps hub store + Consumption REST.

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
| GET | `/health` | Liveness + mode (mock/live) |
| GET | `/summary` | Portfolio KPIs (commitment, remaining, at-risk, MTD cost) |
| GET | `/affiliates` | Affiliate registry |
| GET | `/macc/balances` | MACC balance per affiliate |
| GET | `/macc/{affiliate_id}` | MACC detail — balance + burn-down trend + drawdown events |
| GET | `/costs?affiliate_id=` | Cost summary (trend + by-service) |
| GET | `/licenses?affiliate_id=` | License inventory |

## Going live (`USE_MOCK=false`)
`app/services/provider.py` selects `MockDataProvider` or `LiveDataProvider`. The live
provider's methods are integration points that:
- read the **affiliate registry** (Cosmos/SQL/ADX),
- query the **FOCUS Costs** + reservation tables in **ADX/Fabric** (populated by FinOps hubs),
- read **MaccBalance / FactMaccEvent** populated by `app/services/macc_puller.py`
  (`Microsoft.Consumption/lots` + `events`), and
- read the **DimLicense** reference table.

The API response shapes are identical in both modes, so the frontend never changes.

