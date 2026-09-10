# Infrastructure & onboarding

Cross-tenant, scale-to-100+ automation for the affiliate FinOps platform, built on the
[FinOps toolkit](https://microsoft.github.io/finops-toolkit/) (FinOps hubs) with a
custom MACC + license add-on.

## Topology

```
Affiliate tenant (x1..100+)          Central hub tenant
┌───────────────────────────┐        ┌──────────────────────────────┐
│ Satellite FinOps hub       │  push  │ Central hub storage (ADLS)   │
│  • managed/automated FOCUS │ ─────► │  → Azure Data Explorer/Fabric│
│    exports                 │        │  → Power BI + React dashboard│
└───────────────────────────┘        │  → MACC + license add-on     │
                                      └──────────────────────────────┘
```

## Files

| File | Purpose |
|---|---|
| `modules/export.bicep` | FOCUS Cost Management exports (daily MTD + monthly) for a **subscription** scope. `az deployment sub create`. |
| `scripts/Deploy-Satellite.ps1` | Deploy a satellite FinOps hub in an affiliate tenant that pushes to the central hub (`Deploy-FinOpsHub -RemoteHubStorageUri/-Key`). |
| `scripts/Grant-ManagedExportAccess.ps1` | Grant the hub MI cost access (EA/subscription) so **managed exports** run automatically. |
| `scripts/New-McaExport.ps1` | Automated FOCUS + price/reservation exports for **MCA billing profiles** (`New-FinOpsCostExport`, no portal). |
| `scripts/Onboard-Affiliate.ps1` | **Scale primitive** — one command to onboard an affiliate (EA or MCA). Loop over the CSV for 100+. |
| `affiliates.sample.csv` | Example onboarding input. |

## Prerequisites (once, central)

1. Deploy a central FinOps hub (ADX or Fabric) in the hub tenant. Register the
   `Microsoft.CostManagementExports` and `Microsoft.EventGrid` resource providers.
2. Register a **multi-tenant Entra app** for the MACC add-on; note its object ID.
3. Store the central hub storage key in Key Vault (used by satellites).

## Onboard one affiliate

```powershell
cd infra/scripts
./Onboard-Affiliate.ps1 `
  -AffiliateId aff-001 -Name "Contoso Retail" -TenantId <tenant> `
  -AgreementType EA -BillingAccount 7654321 -SubscriptionId <sub> `
  -RemoteHubStorageUri https://hubstore.dfs.core.windows.net/ `
  -CentralStorageAccountId <hub-storage-resource-id> `
  -HubManagedIdentityObjectId <hub-mi-object-id> `
  -MaccReaderObjectId <macc-app-object-id>
```

## Onboard many (scale to 100+)

```powershell
Import-Csv ./affiliates.sample.csv | ForEach-Object {
  ./scripts/Onboard-Affiliate.ps1 @PSItem `
    -HubManagedIdentityObjectId <hub-mi> -MaccReaderObjectId <macc-app>
}
```

## Automation matrix — no portal clicks anywhere

| Affiliate type | Export mechanism | How it's automated |
|---|---|---|
| EA billing account / subscription / RG | FinOps hubs **managed exports** | Grant hub MI + add `scopes` entry (`Grant-ManagedExportAccess.ps1`) |
| **MCA billing profile** | **Self-managed but automated** exports | `New-FinOpsCostExport` / Bicep / REST (`New-McaExport.ps1`) |
| MACC balance + events | Consumption REST (`lots` + `events`) | `backend/app/services/macc_puller.py` (timer Function) |

> "Manual" in the FinOps docs means *not hub-managed* — it does **not** mean the portal.
> Every path here is code-driven and idempotent.

## Validate locally

```powershell
az bicep build --file modules/export.bicep          # compiles to ARM
# PowerShell parse check:
Get-ChildItem scripts/*.ps1 | ForEach-Object {
  $e=$null; [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$null,[ref]([ref]$e).Value) | Out-Null
}
```

## Security / least privilege

- Satellite hub MI: **Cost Management Contributor** (subs) / **Enrollment Reader** (EA).
- MACC add-on: **Billing Reader** (read-only) on the billing account.
- Cross-tenant transfer uses the central storage **account key** (`RemoteHubStorageKey`)
  — keep it in **Key Vault**, enable **private networking**, and **rotate** regularly.
