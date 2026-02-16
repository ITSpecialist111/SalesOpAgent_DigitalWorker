// ──────────────────────────────────────────────────────────────
// Sales Ops Bot — Azure Infrastructure (Bicep)
// Deploys: Container App, Container Registry, Key Vault,
//          Log Analytics, Application Insights, Managed Identity
// ──────────────────────────────────────────────────────────────

targetScope = 'subscription'

// ── Parameters ──────────────────────────────────────────────
@minLength(1)
@maxLength(64)
@description('Name of the AZD environment')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the resource group')
param resourceGroupName string = 'rg-${environmentName}'

// App-specific parameters — populated from azd env or .env
@secure()
@description('Azure OpenAI API Key')
param azureOpenAiApiKey string = ''

@description('Azure OpenAI endpoint URL')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI deployment name')
param azureOpenAiDeployment string = 'gpt-4o'

@description('Azure OpenAI API version')
param azureOpenAiApiVersion string = '2024-12-01-preview'

@secure()
@description('Entra ID client secret for the service principal')
param azureClientSecret string = ''

@description('Entra ID client ID')
param azureClientId string = ''

@description('Entra ID tenant ID')
param azureTenantId string = ''

@description('LLM provider to use')
param llmProvider string = 'azure_openai'

// ── Resource Group ──────────────────────────────────────────
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

// ── Module: all resources ──────────────────────────────────
module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    azureOpenAiApiKey: azureOpenAiApiKey
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiDeployment: azureOpenAiDeployment
    azureOpenAiApiVersion: azureOpenAiApiVersion
    azureClientSecret: azureClientSecret
    azureClientId: azureClientId
    azureTenantId: azureTenantId
    llmProvider: llmProvider
  }
}

// ── Outputs (required by AZD) ───────────────────────────────
output RESOURCE_GROUP_ID string = rg.id
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint
