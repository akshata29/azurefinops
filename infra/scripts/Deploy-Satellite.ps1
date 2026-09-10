<#
.SYNOPSIS
  Deploy a satellite FinOps hub in an affiliate tenant that pushes cost data to the
  central hub's storage. Cross-tenant scale primitive (FinOps hubs v0.4+).

.NOTES
  Run inside the affiliate tenant with rights to create a resource group + hub.
  RemoteHubStorageKey should be pulled from Key Vault, not passed in plaintext.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$AffiliateId,
  [string]$Location = 'eastus',
  [string]$ResourceGroup = "rg-finops-$AffiliateId",
  [Parameter(Mandatory)][string]$RemoteHubStorageUri,   # central hub ADLS dfs endpoint
  [Parameter(Mandatory)][securestring]$RemoteHubStorageKey
)

$ErrorActionPreference = 'Stop'

Write-Host "==> Deploying satellite FinOps hub for '$AffiliateId' in $Location" -ForegroundColor Cyan

if (-not (Get-Module -ListAvailable -Name FinOpsToolkit)) {
  Write-Host "Installing FinOpsToolkit module..." -ForegroundColor Yellow
  Install-Module FinOpsToolkit -Scope CurrentUser -Force
}
Import-Module FinOpsToolkit

New-AzResourceGroup -Name $ResourceGroup -Location $Location -Force | Out-Null

Deploy-FinOpsHub `
  -Name "finops-$AffiliateId" `
  -ResourceGroup $ResourceGroup `
  -Location $Location `
  -RemoteHubStorageUri $RemoteHubStorageUri `
  -RemoteHubStorageKey $RemoteHubStorageKey

Write-Host "==> Satellite hub deployed. Data will flow to the central hub storage." -ForegroundColor Green
