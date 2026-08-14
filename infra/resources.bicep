// QuoteKit resources — tuned for near-zero idle cost:
//   AI Search free tier, pay-per-token OpenAI, scale-to-zero Container App.
//   The only fixed monthly cost is the Basic container registry (~$5 USD/mo).
targetScope = 'resourceGroup'

param baseName string
param location string
param openAiLocation string
param searchLocation string
param envName string

@secure()
param accessCode string

@secure()
param adminApiKey string

var suffix = uniqueString(resourceGroup().id)

// --- Azure AI Search (FREE tier: 50 MB, 3 indexes) -------------------------
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: '${baseName}-search-${suffix}'
  location: searchLocation
  sku: {
    name: 'free'
  }
  properties: {
    hostingMode: 'default'
  }
}

// --- Azure OpenAI (pay-per-token) -------------------------------------------
resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${baseName}-aoai-${suffix}'
  location: openAiLocation
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${baseName}-aoai-${suffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'gpt-5.4-mini'
  sku: {
    // Subscription has 0 GlobalStandard quota for this model but 200 units
    // of DataZoneStandard (~10% higher per-token cost, negligible at demo scale).
    name: 'DataZoneStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.4-mini'
      version: '2026-03-17'
    }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'text-embedding-3-small'
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
  dependsOn: [chatDeployment] // deployments must be created serially
}

// --- Container registry (Basic, ~$5/mo — the only fixed cost) ---------------
resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: '${baseName}acr${suffix}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// --- Log Analytics + Container Apps environment -----------------------------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs-${suffix}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${baseName}-env-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-api-${suffix}'
  location: location
  tags: {
    'azd-service-name': 'api'
    'azd-env-name': envName
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
      registries: [
        {
          server: registry.properties.loginServer
          username: registry.name
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: registry.listCredentials().passwords[0].value
        }
        {
          name: 'aoai-key'
          value: openAi.listKeys().key1
        }
        {
          name: 'search-key'
          value: search.listAdminKeys().primaryKey
        }
        {
          name: 'access-code'
          value: accessCode
        }
        {
          name: 'admin-key'
          value: adminApiKey
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 0 // scale-to-zero: no traffic, no cost
        maxReplicas: 1
      }
      containers: [
        {
          name: 'api'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' // azd replaces on deploy
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'aoai-key' }
            { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeployment.name }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment.name }
            { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
            { name: 'AZURE_SEARCH_API_KEY', secretRef: 'search-key' }
            { name: 'AZURE_SEARCH_INDEX', value: 'quotekit-items' }
            { name: 'ACCESS_CODE', secretRef: 'access-code' }
            { name: 'ADMIN_API_KEY', secretRef: 'admin-key' }
            { name: 'LLM_DAILY_REQUEST_LIMIT', value: '100' }
            { name: 'DEMO_MODE', value: 'false' }
          ]
        }
      ]
    }
  }
}

// --- Static Web App (Free tier) for the demo UI -----------------------------
resource staticSite 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${baseName}-web-${suffix}'
  location: location
  tags: {
    'azd-service-name': 'web'
    'azd-env-name': envName
  }
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

output containerRegistryEndpoint string = registry.properties.loginServer
output webUrl string = 'https://${staticSite.properties.defaultHostname}'
output apiUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output openAiEndpoint string = openAi.properties.endpoint
