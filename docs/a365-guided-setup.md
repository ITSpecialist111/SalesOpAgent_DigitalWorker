# Agent 365 AI-Guided Setup Reference

> **Source**: [microsoft/Agent365-devTools/docs/agent365-guided-setup/a365-setup-instructions.md](https://github.com/microsoft/Agent365-devTools/blob/main/docs/agent365-guided-setup/a365-setup-instructions.md)
>
> This document summarises the official AI-guided setup prompt for the Agent 365 CLI. The full prompt (706 lines, ~46KB) is designed to be fed directly to an AI coding agent to autonomously execute the entire setup pipeline. See the source link for the complete version.

> **Validation note (2026-02-16):** This repository has been successfully redeployed and validated on Azure Container Apps using this lifecycle-aligned setup pattern.

---

## Overview

The guided setup is a structured prompt that instructs an AI coding agent to set up, configure, and deploy an Agent 365–compliant agent using the `a365` CLI. It aligns to the official lifecycle:

1. Build and run agent
2. Setup Agent 365 config
3. Setup agent blueprint
4. Deploy
5. Publish agent to Microsoft 365 admin center
6. Create agent instances

The AI-guided prompt primarily automates steps 2-5, with validation gates between steps.

## Guided Setup Workflow (Steps 2-5)

### Step 1: Verify and Install/Update the Agent 365 CLI

- Verify .NET 8 SDK is installed (`dotnet --version`)
- Install or update: `dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli --prerelease`
- Confirm with `a365 -h`

### Step 2: Ensure Prerequisites and Environment Configuration

- **Azure CLI**: Verify `az` is installed and logged in to the correct tenant/subscription
- **Entra ID Roles**: Account needs Agent ID Administrator/Developer or Global Admin + Azure Contributor
- **Custom Client App**: Validate the app registration exists with 5 required delegated permissions (all with admin consent):
  - `AgentIdentityBlueprint.ReadWrite.All`
  - `AgentIdentityBlueprint.UpdateAuthProperties.All`
  - `Application.ReadWrite.All`
  - `DelegatedPermissionGrant.ReadWrite.All`
  - `Directory.Read.All`
- **Build Tools**: Validate Python 3.10+/pip (or .NET 8/Node.js 18+ depending on project type)

Validation command:
```bash
az ad app show --id <CLIENT_APP_ID> --query "{appId:appId, displayName:displayName, requiredResourceAccess:requiredResourceAccess}" -o json && az ad app permission list-grants --id <CLIENT_APP_ID> --query "[].{resourceDisplayName:resourceDisplayName, scope:scope}" -o table
```

### Step 3: Configure the Agent 365 CLI (Initialize Configuration)

1. **Auto-detect** tenant ID and subscription ID from `az account show`
2. **Ask deployment type**: Azure-hosted (`needDeployment: true`) or self-hosted (`needDeployment: false`)
3. **Collect inputs**: Resource Group, Location, Agent Name, Manager Email, (+ App Service Plan if Azure-hosted)
4. **Derive naming values** from base name:
   - `agentIdentityDisplayName`: `{baseName} Identity`
   - `agentBlueprintDisplayName`: `{baseName} Blueprint`
   - `agentUserPrincipalName`: `UPN.{baseName}@{domain}`
   - `agentUserDisplayName`: `{baseName} Agent User`
   - `agentDescription`: `{baseName} - Agent 365 Agent`
   - `webAppName` (Azure-hosted only): `{baseName}-webapp`
5. **Create** `a365.config.json` and import with `a365 config init -c ./a365.config.json`

### Step 4: Run Agent 365 Setup to Provision Prerequisites

- Run `a365 setup all` — provisions everything in one command:
  - Azure infrastructure (Resource Group, App Service Plan, Web App, Managed Identity)
  - Entra ID Blueprint (Azure AD application for agent identity)
  - Blueprint permissions (MCP + bot/App Service)
  - Messaging endpoint registration
- Command is idempotent — safe to re-run after fixing issues
- Common failures: quota limits, region not supported, Graph API permission errors, interactive auth in headless environments

### Step 5: Publish and Deploy the Agent Application

1. **Review manifest**: Customise `manifest/manifest.json` (name, description, icons, developer info)
2. **Publish**: `a365 publish` — registers the agent package with the M365 admin center
3. **Deploy**: `a365 deploy` — builds and deploys the agent code to Azure App Service
4. **Post-deployment** (manual):
   - Configure agent blueprint in [Teams Developer Portal](https://dev.teams.microsoft.com/tools/agent-blueprint/)
   - Set Agent Type to `Bot Based`, set Bot ID to the blueprint app ID
  - Publish approval and instance creation happen through Microsoft 365 admin center / Teams experiences

## Step 6: Create Agent Instances

After publish succeeds and admins approve the package/blueprint, create agent instances from the published blueprint in Microsoft 365 admin center (or Teams flows backed by the same blueprint).

> Current CLI preview removed `create-instance`; use the publish + admin center/Teams flow for instance creation.

## Configuration Templates

### Azure-Hosted (`needDeployment: true`)
```json
{
  "tenantId": "<from az account show>",
  "subscriptionId": "<from az account show>",
  "resourceGroup": "<user provided>",
  "location": "<user provided>",
  "environment": "prod",
  "needDeployment": true,
  "clientAppId": "<from Step 2>",
  "appServicePlanName": "<user provided>",
  "webAppName": "<derived>-webapp",
  "agentIdentityDisplayName": "<derived> Identity",
  "agentBlueprintDisplayName": "<derived> Blueprint",
  "agentUserPrincipalName": "UPN.<derived>@<domain>",
  "agentUserDisplayName": "<derived> Agent User",
  "managerEmail": "<user provided>",
  "agentUserUsageLocation": "US",
  "deploymentProjectPath": "<cwd>",
  "agentDescription": "<derived> - Agent 365 Agent"
}
```

### Self-Hosted (`needDeployment: false`)
```json
{
  "tenantId": "<from az account show>",
  "subscriptionId": "<from az account show>",
  "resourceGroup": "<user provided>",
  "location": "<user provided>",
  "environment": "prod",
  "messagingEndpoint": "<custom URL>/api/messages",
  "needDeployment": false,
  "clientAppId": "<from Step 2>",
  "agentIdentityDisplayName": "<derived> Identity",
  "agentBlueprintDisplayName": "<derived> Blueprint",
  "agentUserPrincipalName": "UPN.<derived>@<domain>",
  "agentUserDisplayName": "<derived> Agent User",
  "managerEmail": "<user provided>",
  "agentUserUsageLocation": "US",
  "deploymentProjectPath": "<cwd>",
  "agentDescription": "<derived> - Agent 365 Agent"
}
```

## This Project's Configuration

For the Sales Ops Bot, we use the **self-hosted** model because we deploy to Azure Container Apps (not Azure App Service). Key values:

| Field | Value |
|-------|-------|
| Deployment Type | Self-hosted (`needDeployment: false`) |
| Messaging Endpoint | `https://<container-app-fqdn>/api/messages` |
| Resource Group | `<resource-group>` |
| Location | `uksouth` |
| Blueprint App ID | `c70fe227-230b-474c-bbf8-1d18483e2801` |
| Agent UPN | `agent.user@example.com` |
| M365 Tenant | `<m365-tenant-id>` |
| Azure Tenant | `<azure-tenant-id>` |

## Troubleshooting Quick Reference

| Issue | Fix |
|-------|-----|
| CLI not found | `dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli --prerelease` |
| Permission denied on Graph API | Ensure custom app has all 5 permissions with admin consent |
| Quota exceeded on App Service | Change region or SKU in config, re-run `a365 setup all` |
| Interactive auth in headless env | Use `az login --use-device-code` first |
| Dev tunnel URL changed | `a365 setup blueprint --update-endpoint <new-url>` |
| Config validation fails | Fix `a365.config.json` and re-run `a365 config init -c ./a365.config.json` |

For full troubleshooting, see [TROUBLESHOOTING-A365.md](TROUBLESHOOTING-A365.md) and the [official guide](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/troubleshooting).
