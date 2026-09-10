# Frontend — Affiliate FinOps Dashboard

React 18 + TypeScript + Vite + Tailwind, with TanStack Query, Recharts, and Heroicons.

## Run
```powershell
npm install
npm run dev        # http://localhost:5174  (proxies /api -> http://localhost:8081)
```
Start the [backend](../backend/README.md) first (or run both from repo root helpers).

## Build
```powershell
npm run build      # tsc -b && vite build  ->  dist/
npm run preview
```

## Structure
| Path | Purpose |
|---|---|
| `src/api/client.ts` + `types.ts` | Axios instance (`baseURL: /api/v1`) + typed API namespaces mirroring the backend contract |
| `src/components/` | Layout shell (Sidebar/Topbar), KpiCard, ChartCard, Badge, ProgressBar, States |
| `src/pages/` | Overview, Affiliates, MACC (burn-down), Costs, Licenses |
| `src/lib/format.ts` | Currency / percent / date / month formatting |

## Pages
- **Overview** — portfolio KPIs, cost trend, commitment gauge, top affiliates, cost-by-service.
- **Affiliates** — searchable registry with agreement, status, data-freshness.
- **MACC** — master list + burn-down chart, projected exhaustion, drawdown events.
- **Cost & Usage** — actual vs. amortized trend, cost by service.
- **Licenses** — utilization + estimated annual cost (phase-2 import).

