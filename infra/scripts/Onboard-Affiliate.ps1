<#
.SYNOPSIS
  One repeatable command to onboard an affiliate (EA or MCA) into the central FinOps
  platform. This is the SCALE PRIMITIVE — loop it over affiliates.csv to onboard 100+.

.DESCRIPTION
  Per affiliate:
    1. Deploy a satellite FinOps hub that pushes to the central hub storage.
    2. EA / subscription  -> grant hub MI cost access + register scope (managed exports).
       MCA billing profile -> create automated FOCUS exports (New-FinOpsCostExport).
    3. Grant the MACC add-on identity Billing Reader on the billing account (read-only).
    4. Upsert a row into the affiliate registry.

.EXAMPLE
  Import-Csv .\affiliates.sample.csv | ForEach-Object { .\Onboard-Affiliate.ps1 @PSItem }
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$AffiliateId,
  [Parameter(Mandatory)][string]$Name,
  [Parameter(Mandatory)][string]$TenantId,
  [Parameter(Mandatory)][ValidateSet('EA', 'MCA')][string]$AgreementType,
  [Parameter(Mandatory)][string]$BillingAccount,
  [string]$BillingProfile,
  [string]$SubscriptionId,
  [Parameter(Mandatory)][string]$RemoteHubStorageUri,
  [Parameter(Mandatory)][string]$CentralStorageAccountId,
  [string]$HubManagedIdentityObjectId,
  [string]$MaccReaderObjectId,
  [string]$RegistryPath = "$PSScriptRoot\..\affiliate-registry.json"
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

Write-Host "================ Onboarding $Name ($AffiliateId, $AgreementType) ================" -ForegroundColor Magenta

# 1) Satellite hub (RemoteHubStorageKey resolved from Key Vault at runtime — placeholder here)
$key = ConvertTo-SecureString 'REPLACE_FROM_KEYVAULT' -AsPlainText -Force
& "$here\Deploy-Satellite.ps1" -AffiliateId $AffiliateId -RemoteHubStorageUri $RemoteHubStorageUri -RemoteHubStorageKey $key

# 2) Exports — path depends on agreement type
if ($AgreementType -eq 'MCA') {
  & "$here\New-McaExport.ps1" -AffiliateId $AffiliateId -BillingAccount $BillingAccount `
    -BillingProfile $BillingProfile -StorageAccountId $CentralStorageAccountId
}
else {
  $scope = if ($SubscriptionId) { "/subscriptions/$SubscriptionId" } else { "/providers/Microsoft.Billing/billingAccounts/$BillingAccount" }
  if ($HubManagedIdentityObjectId) {
    & "$here\Grant-ManagedExportAccess.ps1" -HubManagedIdentityObjectId $HubManagedIdentityObjectId -Scope $scope
  }
}

# 3) MACC add-on read access (Billing Reader on the billing account)
if ($MaccReaderObjectId) {
  Write-Host "==> Granting Billing Reader (MACC add-on) on billing account $BillingAccount" -ForegroundColor Cyan
  New-AzRoleAssignment -ObjectId $MaccReaderObjectId -RoleDefinitionName 'Billing Reader' `
    -Scope "/providers/Microsoft.Billing/billingAccounts/$BillingAccount" -ErrorAction SilentlyContinue | Out-Null
}

# 4) Upsert affiliate registry
$registry = @()
if (Test-Path $RegistryPath) { $registry = @(Get-Content $RegistryPath -Raw | ConvertFrom-Json) }
$registry = $registry | Where-Object { $_.affiliateId -ne $AffiliateId }
$registry += [pscustomobject]@{
  affiliateId    = $AffiliateId
  name           = $Name
  tenantId       = $TenantId
  agreementType  = $AgreementType
  billingAccount = $BillingAccount
  billingProfile = $BillingProfile
  subscriptionId = $SubscriptionId
  status         = 'Onboarding'
  onboardedOn    = (Get-Date).ToString('yyyy-MM-dd')
}
$registry | ConvertTo-Json -Depth 5 | Set-Content $RegistryPath

Write-Host "==> $Name onboarded. Registry updated at $RegistryPath" -ForegroundColor Green
