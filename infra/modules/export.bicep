// -----------------------------------------------------------------------------
// export.bicep — creates FOCUS Cost Management exports for a SUBSCRIPTION scope.
// Deploy at subscription scope:
//   az deployment sub create -l eastus -f export.bicep -p storageAccountId=... 
// For EA billing accounts, prefer FinOps hubs "managed exports" (grant + scopes).
// For MCA billing profiles, use scripts/New-McaExport.ps1 (New-FinOpsCostExport),
// which targets the billing-profile scope that ARM/Bicep handles awkwardly.
// -----------------------------------------------------------------------------
targetScope = 'subscription'

@description('Resource ID of the destination storage account (in the hub or affiliate).')
param storageAccountId string

@description('Blob container that receives export files.')
param container string = 'msexports'

@description('Directory path prefix inside the container (unique per scope).')
param rootFolderPath string = 'subscriptions'

@description('Export start date (UTC, ISO 8601).')
param fromDate string = '2026-10-01T00:00:00Z'

@description('Export end date (UTC, ISO 8601).')
param toDate string = '2030-01-01T00:00:00Z'

@description('Prefix for the generated export names.')
param exportPrefix string = 'ftk'

var focusDefinition = {
  type: 'FocusCost'
  dataSet: {
    granularity: 'Daily'
  }
}

resource focusDaily 'Microsoft.CostManagement/exports@2023-08-01' = {
  name: '${exportPrefix}-focus-daily'
  properties: {
    schedule: {
      status: 'Active'
      recurrence: 'Daily'
      recurrencePeriod: {
        from: fromDate
        to: toDate
      }
    }
    format: 'Csv'
    partitionData: true
    deliveryInfo: {
      destination: {
        resourceId: storageAccountId
        container: container
        rootFolderPath: rootFolderPath
      }
    }
    definition: union(focusDefinition, {
      timeframe: 'MonthToDate'
    })
  }
}

resource focusMonthly 'Microsoft.CostManagement/exports@2023-08-01' = {
  name: '${exportPrefix}-focus-monthly'
  properties: {
    schedule: {
      status: 'Active'
      recurrence: 'Monthly'
      recurrencePeriod: {
        from: fromDate
        to: toDate
      }
    }
    format: 'Csv'
    partitionData: true
    deliveryInfo: {
      destination: {
        resourceId: storageAccountId
        container: container
        rootFolderPath: rootFolderPath
      }
    }
    definition: union(focusDefinition, {
      timeframe: 'TheLastMonth'
    })
  }
}

output dailyExportName string = focusDaily.name
output monthlyExportName string = focusMonthly.name
