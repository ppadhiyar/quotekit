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
    envName: environmentName
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint
output API_URL string = resources.outputs.apiUrl
output AZURE_SEARCH_ENDPOINT string = resources.outputs.searchEndpoint
output AZURE_OPENAI_ENDPOINT string = resources.outputs.openAiEndpoint
