# Project Setup & Prerequisites

To successfully build and deploy the Sales Ops Bot as an Agent 365 "Digital Employee", you must ensure the following environment and access requirements are met.

## Current Runtime Validation (2026-02-16)

- Active revision: `azcaxyseurue7b6nw--azd-1771242381` (healthy, running, 100% traffic)
- Health endpoint: `status=ok`, `agent_initialized=true`, `mcp.state=ready`
- Focused report tests: passing

## 1. Access Requirements
You will need a Microsoft 365 Tenant with the following:
- [x] **Tenant Admin Access**: To register the agent identity and grant admin consent.
- [x] **Agent 365 Preview**: Your tenant must be allowlisted for Agent 365 features.
- [x] **Agent 365 License**: Trial or production license pack applied to tenant.
- [x] **Azure Subscription**: For hosting the agent logic (Azure Container Apps) and LLM resources (Azure OpenAI).

> **Note:** This project uses a **split-tenant** configuration. Azure infrastructure is in the HOSKING tenant; the M365 identity is in the Contoso tenant. See `docs/TROUBLESHOOTING-A365.md` for details.

## 2. App Registration (Permissions)

### Custom Client App Registration (required by Agent 365 CLI)

The custom client app used by `a365 config init` and setup commands must include these delegated permissions with admin consent:

| Permission | Purpose |
|------------|---------|
| `AgentIdentityBlueprint.ReadWrite.All` | Create/update Agent 365 blueprints |
| `AgentIdentityBlueprint.UpdateAuthProperties.All` | Update blueprint auth properties |
| `Application.ReadWrite.All` | Create/manage app registrations |
| `DelegatedPermissionGrant.ReadWrite.All` | Create delegated permission grants |
| `Directory.Read.All` | Read Entra directory objects |

The agent uses **delegated permissions** via the Agent 365 agentic token exchange. MCP servers authenticate using these delegated scopes — you do NOT need Graph application permissions for most operations.

### Agent 365 Tools API (ea9ffc3e-8a23-4a7d-836d-234d7c7565c1)

These scopes are configured via `a365 setup permissions mcp`:

| Scope | Purpose | Status |
|-------|---------|--------|
| `McpServers.Calendar.All` | Meeting detection (CalendarServer returns 403 — use local tools) | Consented |
| `McpServers.CopilotMCP.All` | Copilot MCP integration | Consented |
| `McpServers.DASearch.All` | Data search | Consented |
| `McpServers.Knowledge.All` | Knowledge graph queries | Consented |
| `McpServers.OneDriveSharepoint.All` | File storage/sharing | Consented |
| `McpServers.Planner.All` | Task management | Consented |
| `McpServers.SharepointLists.All` | SharePoint list operations | Consented |
| `McpServers.Teams.All` | Teams messaging/delivery | Consented |
| `McpServers.Word.All` | Document creation | Consented |
| `McpServersMetadata.Read.All` | Server metadata | Consented |

**Not consented**: `McpServers.Mail.All` — not available in current consent set.

### Other Required APIs

| API | Scopes | Purpose |
|-----|--------|---------|
| Messaging Bot API (`5a807f24-...`) | `Authorization.ReadWrite`, `user_impersonation` | Teams messaging |
| Observability API (`9b975845-...`) | `user_impersonation` | Agent telemetry |
| Power Platform API (`8578e004-...`) | `Connectivity.Connections.Read` | Connection management |
| Microsoft Graph | `Calendars.ReadWrite` (delegated via client credentials) | Calendar polling |

### Core Microsoft Graph (Client Credentials)

Used by `DefaultAzureCredential` for background operations (calendar polling):
*   `Calendars.ReadWrite` — Granted as application permission

## 3. ToolingManifest.json (MCP Server Configuration)

The `ToolingManifest.json` file declares which MCP servers the agent connects to in Development mode. Current checked-in manifest: 4 proven servers:

```json
{
  "mcpServers": [
    { "mcpServerName": "mcp_WordServer", "scope": "McpServers.Word.All" },
    { "mcpServerName": "mcp_SharePointListsTools", "scope": "McpServers.SharepointLists.All" },
    { "mcpServerName": "mcp_KnowledgeTools", "scope": "McpServers.Knowledge.All" },
    { "mcpServerName": "mcp_PlannerServer", "scope": "McpServers.Planner.All" }
  ]
}
```

`mcp_TeamsServer` and `mcp_OneDriveSharepointServer` remain candidates for re-enable, but are not currently declared in the repository manifest.

**Important**: Adding a server that returns 403 can cascade and kill all MCP connections. Always test one server at a time.

## 4. Local Developer Environment

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Python | 3.11+ | Bot runtime | `python --version` |
| .NET 8 SDK | 8.0.418 | Required for a365 CLI | [Download](https://dot.net) |
| a365 CLI | 1.1.62+ preview | Agent 365 lifecycle tooling | `dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli --prerelease` |
| Azure CLI | 2.83.0 | Azure resource management | [Download](https://aka.ms/installazurecliwindows) |
| AZD CLI | 1.23.5 | Azure Developer CLI | [Download](https://aka.ms/azd-install) |
| PowerShell 7 | 7.5.4 | Required by a365 setup | ZIP install at `%LOCALAPPDATA%\PowerShell` |
| Docker | 27.4.0 | Container image builds | [Download](https://docker.com) |

> `create-instance` is removed in current CLI preview builds; use lifecycle flow (`a365 setup` → `a365 publish`) and create instances from admin center/Teams as documented.

## 5. API Keys & Secrets

Stored in Azure Key Vault (`azkvxyseurue7b6nw`) and referenced via Container App `secretRef`:

| Secret | Environment Variable | Source |
|--------|---------------------|--------|
| Azure OpenAI API Key | `AZURE_OPENAI_API_KEY` | Key Vault |
| Client Secret (Contoso) | `AZURE_CLIENT_SECRET` | Key Vault |
| Service Connection Secret | `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET` | Key Vault |

## 6. Build & Deploy

```powershell
# Build container image
az acr build --registry azcrxyseurue7b6nw --image salesopsbot:<tag> --file Dockerfile . --no-logs

# Deploy to Container App
az containerapp update --name azcaxyseurue7b6nw --resource-group rg-salesopsbot --image azcrxyseurue7b6nw.azurecr.io/salesopsbot:<tag>

# Check revision status
az containerapp revision list --name azcaxyseurue7b6nw --resource-group rg-salesopsbot -o table

# Tail logs
az containerapp logs show --name azcaxyseurue7b6nw --resource-group rg-salesopsbot --type console --tail 80 --follow false
```

## 7. Verification

```powershell
# Check container is running
Invoke-RestMethod -Uri "https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/" -Method GET

# Check logs for tool count
az containerapp logs show --name azcaxyseurue7b6nw --resource-group rg-salesopsbot --type console --tail 50 --follow false 2>&1 | Select-String "running agent with"

# Run tests locally
pip install -e ".[dev]"
python -m pytest tests/ -v

# Optional smoke check (after deployment)
# Ask in Teams chat: "run meeting report for my most recent meeting with autonomous actions"
```
