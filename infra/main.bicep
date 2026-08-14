// azd entry point: subscription scope — creates the resource group, then
// deploys all resources via the module below.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Region for the Azure OpenAI account (model availability varies)')
param openAiLocation string = 'eastus2'

@description('Region for AI Search (decoupled — eastus2 has capacity constraints)')
param searchLocation string = 'canadacentral'

@secure()
@description('Code that unlocks live LLM responses (public traffic gets demo data)')
param accessCode string

@secure()
@description('Key required for document ingestion via /ingest')
param adminApiKey string

@description('Monthly budget alert threshold in USD')
param budgetAmount int = 20

@description('Email for budget alerts')
param budgetAlertEmail string = 'parthpadhiyar31@gmail.com'

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    baseName: 'quotekit'
    location: location
    openAiLocation: openAiLocation
    searchLocation: searchLocation
    envName: environmentName
    accessCode: accessCode
    adminApiKey: adminApiKey
  }
}

// Budget alert: emails at 80% and 100% of the monthly threshold. An alert,
// not a hard cap — Azure has no true kill switch — but the app-level daily
// LLM budget and scale-to-zero keep actual spend near the ACR baseline.
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'quotekit-budget'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-08-01T00:00:00Z'
      endDate: '2036-08-01T00:00:00Z'
    }
    filter: {
      dimensions: {
        name: 'ResourceGroupName'
        operator: 'In'
        values: [rg.name]
      }
    }
    notifications: {
      warning80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: [budgetAlertEmail]
      }
      exceeded100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: [budgetAlertEmail]
      }
    }
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint
output API_URL string = resources.outputs.apiUrl
output WEB_URL string = resources.outputs.webUrl
output AZURE_SEARCH_ENDPOINT string = resources.outputs.searchEndpoint
output AZURE_OPENAI_ENDPOINT string = resources.outputs.openAiEndpoint
