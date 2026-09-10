<#
.SYNOPSIS
  Grant a satellite hub's Data Factory managed identity the cost access required for
  FinOps hubs "managed exports" (EA / subscription scopes), then register the scope.

.DESCRIPTION
  For EA billing accounts use EnrollmentReader (assigned via the EA portal / billing API).
  For subscriptions / resource groups, assign 'Cost Management Contributor' to the hub MI.
  Finally, add the scope to the hub's config/settings.json so managed exports pick it up.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$HubManagedIdentityObjectId,
  [Parameter(Mandatory)][string]$Scope,                 # /subscriptions/{id} or .../resourceGroups/{rg}
  [string]$Role = 'Cost Management Contributor'
)

$ErrorActionPreference = 'Stop'

Write-Host "==> Assigning '$Role' to hub MI on $Scope" -ForegroundColor Cyan
New-AzRoleAssignment `
  -ObjectId $HubManagedIdentityObjectId `
  -RoleDefinitionName $Role `
  -Scope $Scope

Write-Host @"
==> Role assigned.
    Next: add the scope to the hub storage 'config' container settings.json:
      { "scopes": [ { "scope": "$Scope" } ] }
    FinOps hubs will create + maintain the FOCUS exports automatically (managed exports).
"@ -ForegroundColor Green
