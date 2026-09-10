<#
.SYNOPSIS
  Create automated FOCUS Cost Management exports for an MCA billing profile — where
  FinOps hubs "managed exports" are NOT supported. Uses New-FinOpsCostExport, so this is
  fully automated (no portal), including a 12-month backfill.

.NOTES
  MCA-only datasets (Price sheet, Reservation recommendations/details) live at the
  billing-profile scope, so we export from there.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$AffiliateId,
  [Parameter(Mandatory)][string]$BillingAccount,
  [Parameter(Mandatory)][string]$BillingProfile,
  [Parameter(Mandatory)][string]$StorageAccountId,
  [string]$Container = 'msexports',
  [int]$BackfillMonths = 12
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name FinOpsToolkit)) {
  Install-Module FinOpsToolkit -Scope CurrentUser -Force
}
Import-Module FinOpsToolkit

$scope = "/providers/Microsoft.Billing/billingAccounts/$BillingAccount/billingProfiles/$BillingProfile"
$path  = "billingProfiles/$BillingProfile"

$datasets = @(
  @{ Name = "ftk-$AffiliateId-focus";    Dataset = 'FocusCost';                  Version = '1.0r2' },
  @{ Name = "ftk-$AffiliateId-prices";   Dataset = 'PriceSheet';                 Version = '2023-05-01' },
  @{ Name = "ftk-$AffiliateId-recadv";   Dataset = 'ReservationRecommendations'; Version = '2023-05-01' },
  @{ Name = "ftk-$AffiliateId-rezdet";   Dataset = 'ReservationDetails';         Version = '2023-03-01' }
)

foreach ($d in $datasets) {
  Write-Host "==> Creating export '$($d.Name)' ($($d.Dataset)) at MCA billing profile scope" -ForegroundColor Cyan
  New-FinOpsCostExport `
    -Name $d.Name `
    -Scope $scope `
    -StorageAccountId $StorageAccountId `
    -StorageContainer $Container `
    -StorageContainerPath $path `
    -Dataset $d.Dataset `
    -DatasetVersion $d.Version `
    -Backfill $BackfillMonths `
    -Execute
}

Write-Host "==> MCA exports created and backfilled ($BackfillMonths months)." -ForegroundColor Green
