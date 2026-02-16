# Project Handover: Sales Ops Bot (Agent 365 Synthetic Worker)

## 1. Context & Purpose
**Goal:** Build an autonomous "Synthetic Worker" (Digital Employee) that joins meetings, extracts intelligence, and updates **Dynamics 365** (Dataverse).
**Key Pattern:** "Agent as Participant" - The agent is invited to meetings to gain direct access to transcripts and context via Microsoft Graph.

## 1.1 Lifecycle Alignment (Canonical Runbooks)

This project now follows the official Agent 365 lifecycle language and sequencing (build/run → config → blueprint → deploy → publish → create instances).

Use these as the canonical runbooks:

1. `docs/a365-guided-setup.md` — lifecycle-aligned setup reference, including current CLI behavior and instance-creation guidance.
2. `docs/TROUBLESHOOTING-A365.md` — lifecycle-mapped troubleshooting and operational playbook.
3. `docs/INCIDENT-2026-02-MEETING-REPORT.md` — transcript/report stabilization post-incident timeline, root causes, fixes, and prevention controls.

If any other document conflicts with these two files, treat these runbooks as the source of truth and update the stale document.

## 2. Current Codebase State ("As-Built")
**Status:** Phases 1-11 Complete. Deployed to Azure Container Apps (revision `azcaxyseurue7b6nw--azd-1771242381`, active 100% traffic). Published to M365 via Agent 365 CLI (v1.2.0). Current repository baseline uses **4 MCP servers + 7 local tools**. ISS-014 through ISS-029 resolved (see `docs/TROUBLESHOOTING-A365.md`).

### Core Components
*   **Identity**: Service Principal (Entra Agent ID).
*   **Foundation (`src/agent.py`, ~737 lines)**:
    *   Implements `AgentInterface` using the `microsoft-agents-a365` SDK.
    *   Initializes all handlers and services.
    *   Registers **7 local FunctionTool instances**: `get_my_calendar_today`, `get_my_calendar_range`, `get_upcoming_meetings`, `run_meeting_report`, `graph_get_meeting_transcript`, `graph_send_email`, `graph_post_meeting_chat_message` — these work even when MCP gateway returns 0 servers.
    *   **Dynamic system prompt** (`_build_prompt()`) — enumerates available tools at runtime. ON-DEMAND CAPABILITIES section instructs the LLM to chain `run_meeting_report` → MCP email/Teams tools for delivery.
    *   **MCP server discovery** via `ToolingManifest.json` (Development mode) or MCP gateway (Production mode).
    *   **Local tool merge** — after `add_tool_servers_to_agent()`, detects if the SDK dropped local tools and re-adds them by patching the agent's tool list.
    *   **`max_iterations=10`** and **300s timeout** on agent invocations to prevent runaway LLM loops.
    *   **Status**: Complete & Working.

*   **Detection ("The Eyes")**:
    *   **Email Handler (`src/handlers/email_handler.py`)**: Parses "Meeting Ended" emails.
    *   **Calendar Handler (`src/handlers/calendar_handler.py`)**: Polls for recently ended meetings where the agent was a participant. Real Graph API calls via `graph_transcript_client.py`.
    *   **Status**: Implemented — auto-accepts meeting invitations, detects recently ended meetings.

*   **Intelligence ("The Brain")**:
    *   **Meeting Processor (`src/services/meeting_processor.py`, ~292 lines)**: Full pipeline orchestration — transcript → LLM analysis (direct `AzureOpenAI` `chat.completions.create()` call, no tools, avoids recursive loops) → reports → MS Learn enrichment. Returns `email_html` and `email_subject` for the outer agent to deliver via MCP tools. Internal email/Teams delivery attempts gracefully fail (403) — delivery is now the responsibility of the outer agent using MCP servers.
    *   **MS Learn Client (`src/integrations/ms_learn_client.py`, ~130 lines)**: Real HTTP calls to `https://learn.microsoft.com/api/search`. Methods: `search_term()`, `search()`, `search_multiple_terms()`. **Working** — confirmed in production logs.
    *   **Live Knowledge Service (`src/services/live_knowledge_service.py`)**: MS Learn knowledge injection into Teams chats.
    *   **Transcript Access (`src/integrations/graph_transcript_client.py`, ~390 lines)**: Graph API client for transcripts, calendar, email, chat. Includes `send_email()`, `resolve_chat_thread_id()`, `post_chat_message()`, `send_meeting_chat_message()`. Email/Teams chat methods implemented but blocked by missing permissions (see Known Issues).
    *   **Status**: Pipeline implemented; LLM analysis and MS Learn search working. Delivery via MCP tool chaining (outer agent calls `run_meeting_report` → uses MCP Teams/email tools to send).

*   **Delivery ("The Hands")**:
    *   **Report Generator (`src/services/report_generator.py`)**: Generates HTML email and Adaptive Card reports. None-safety fix applied.
    *   **Teams Chat Service (`src/services/teams_chat_service.py`, ~120 lines)**: Real Graph API Teams chat messaging. Methods: `send_intro_message()`, `send_summary_message()`, `send_knowledge_message()`.
    *   **Email Composer (`src/services/email_composer.py`)**: Email composition and formatting.
    *   **Dynamics 365 (`src/integrations/dynamics_client.py`)**: Stubbed client for Dataverse operations.
    *   **Status**: Code complete. Direct Graph API email/Teams returns 403 — delivery now handled via MCP servers (delegated permissions via agentic token exchange).

### Verification
*   **`tests/verify_pipeline.py`**: End-to-end mock verification script.
    *   **Result**: PASSED. Confirmed that a meeting signal triggers the processor, fetches a transcript, and generates a Dynamics update proposal.

## 3. Deployment — Phase 5 (Container Apps — COMPLETE)

### What Was Deployed
Deployed **14 February 2026** to **Azure Container Apps** (UK South) using the Azure Developer CLI (`azd`).

| Resource | Type | Name |
|----------|------|------|
| Resource Group | Microsoft.Resources/resourceGroups | `rg-salesopsbot` |
| Container App | Microsoft.App/containerApps | `azcaxyseurue7b6nw` |
| Container Apps Env | Microsoft.App/managedEnvironments | `azcexyseurue7b6nw` |
| Container Registry | Microsoft.ContainerRegistry/registries | `azcrxyseurue7b6nw` |
| Key Vault | Microsoft.KeyVault/vaults | `azkvxyseurue7b6nw` |
| Application Insights | Microsoft.Insights/components | `azaixyseurue7b6nw` |
| Log Analytics | Microsoft.OperationalInsights/workspaces | `azlaxyseurue7b6nw` |
| Managed Identity | Microsoft.ManagedIdentity/userAssignedIdentities | Auto-generated |

*   **Endpoint**: `https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/`
*   **Azure Portal**: [Resource Group](https://portal.azure.com/#@hosking.wales/resource/subscriptions/43b2438e-00b7-443e-b336-34cb97a489d4/resourceGroups/rg-salesopsbot/overview)
*   **Subscription**: VS Sub No1 (`43b2438e-00b7-443e-b336-34cb97a489d4`)
*   **Tenant**: HOSKING (`b5c09a39-9df6-437a-a76e-19095fa6f20d`)
*   **AZD Environment**: `salesopsbot`
*   **Provisioning Tool**: AZD with Bicep IaC
*   **Status**: **Running** (Provisioning Succeeded)

### Infrastructure-as-Code
All infrastructure is defined in Bicep and managed via `azd up`:
*   `infra/main.bicep` — Main template (subscription scope), creates RG and delegates to resources module.
*   `infra/resources.bicep` — All Azure resources: Managed Identity, ACR, Key Vault, Log Analytics, App Insights, Container Apps Environment, Container App.
*   `infra/main.parameters.json` — Parameter bindings (reads from AZD environment variables).
*   `azure.yaml` — AZD project definition linking the service to the Dockerfile.

### Security
*   **User-Assigned Managed Identity** assigned to the Container App.
*   **AcrPull** role granted to Managed Identity on Container Registry (passwordless image pull).
*   **Key Vault Secrets Officer** role granted to Managed Identity on Key Vault.
*   Secrets (`AZURE_OPENAI_API_KEY`, `AZURE_CLIENT_SECRET`) stored in Key Vault and referenced via `secretRef` in the Container App config.
*   No admin credentials enabled on ACR. No hardcoded secrets.

### How to Redeploy
```bash
# Set real credentials
azd env set AZURE_OPENAI_API_KEY <real-key>
azd env set AZURE_OPENAI_ENDPOINT https://<instance>.openai.azure.com/
azd env set AZURE_CLIENT_ID <app-registration-client-id>
azd env set AZURE_CLIENT_SECRET <client-secret>

# Deploy
azd up
```

## 4. Credential & Identity Configuration (COMPLETE)

### Azure OpenAI
*   **Resource**: `salesopsbot-openai` (UK South) in `rg-salesopsbot`
*   **Model**: GPT-4o (GlobalStandard, **50K TPM** — increased from 10K to resolve 429 rate limiting)
*   **Status**: Deployed and configured in AZD env vars

### Entra ID App Registrations
Two app registrations were created during the session:

| Tenant | App Name | Client ID | Status |
|--------|----------|-----------|--------|
| HOSKING | `sales-ops-bot` | `85d7e8d6-bdb1-4f6b-99bb-76c296e5a030` | Created, superseded |
| Contoso | *(pre-existing)* | `8e5206be-48e3-4da4-b741-d3908cf7c30a` | **Active** |

### Split-Tenant Architecture
*   **Infrastructure tenant**: HOSKING (`b5c09a39-9df6-437a-a76e-19095fa6f20d`) — hosts all Azure resources
*   **Identity tenant**: Contoso (`c2833f41-c31d-4c2f-98d1-947fdb699aba`) — bot's identity lives here
*   **Contoso Client Secret**: stored in Key Vault / local `.env` only (not committed)
*   The Container App was redeployed with Contoso identity credentials successfully.

## 5. Official Agent 365 Deployment — Phase 6 (COMPLETE)

### Context
The initial deployment (Section 3) used AZD + Container Apps. The **official** Microsoft Agent 365 deployment method uses the `a365` CLI tool. Since we already have Container Apps hosting, we're using the `needDeployment: false` pattern (non-Azure hosting). See: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/deploy-agent-azure

> **Troubleshooting:** See `docs/TROUBLESHOOTING-A365.md` for a comprehensive catalogue of all issues encountered, the split-tenant deployment playbook, and lessons learned for future Agent 365 deployments.

### Pipeline Status — ALL COMPLETE

| Step | Command | Status |
|------|---------|--------|
| 1 | `az login --tenant c2833f41-... --allow-no-subscriptions` | ✅ Logged in as `CoreyG@M365CPI14187042.OnMicrosoft.com` |
| 2 | `a365 config init -c ./a365.config.json` | ✅ Config imported successfully |
| 3 | `a365 setup requirements` | ✅ All checks passed (Frontier = warning only) |
| 4 | `a365 setup infrastructure` | ⏭️ Skipped (`needDeployment: false`) |
| 5 | `a365 setup blueprint` | ✅ Blueprint created, endpoint registered, client secret generated |
| 6 | `a365 setup permissions mcp` | ✅ Agent 365 Tools inheritable permissions configured |
| 7 | `a365 setup permissions bot` | ✅ Messaging Bot, Observability, Power Platform permissions configured |
| 8 | `a365 deploy` | ⏭️ Skipped (`needDeployment: false`) |
| 9 | `a365 publish` | ✅ **Published to M365** — Title `T_ae143bb1-8f29-3a70-a2dc-ceab6f965d08` (v1.2.0) |

### Blueprint Details
*   **Blueprint App ID**: `c70fe227-230b-474c-bbf8-1d18483e2801`
*   **Blueprint SP Object ID**: `7e3020aa-9049-4734-83de-22513dffdc86`
*   **Blueprint Display Name**: `Sales Ops Bot Blueprint`
*   **Bot ID**: `c70fe227-230b-474c-bbf8-1d18483e2801` (same as blueprint)
*   **Bot Messaging Endpoint**: `https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/api/messages`
*   **Endpoint Name**: `azcaxyseurue7b6nw-wonderfulrock-5a126c64-u`
*   **Generated Config**: `a365.generated.config.json` (`completed: true`)

### Publish Details
*   **Title ID**: `T_ae143bb1-8f29-3a70-a2dc-ceab6f965d08`
*   **Operation ID (v1.1.4)**: `fbe063dc-eda6-402c-9d67-a24fd25c5749`
*   **Operation ID (v1.2.0)**: `56170ef3-15f3-4092-9c21-75579359bbfe`
*   **MOS Environment**: `prod`
*   **Manifest**: `manifest/manifest.json` (version 1.2.0 — republished 14 Feb 2026)
*   **Title Access**: Configured for all users in tenant
*   **Graph Permissions**: Granted to blueprint service principal
*   **Federated Identity**: Workload identity authentication already configured

### MCP Server Configuration (Current repo manifest — 4 active servers)

The current checked-in `ToolingManifest.json` contains the original **4 proven servers**. Additional servers were trialed during delivery experiments, but are not currently enabled in the repo manifest.

| Server | Scope | Status | Purpose |
|--------|-------|--------|--------|
| `mcp_WordServer` | McpServers.Word.All | ✅ Working | Document creation |
| `mcp_SharePointListsTools` | McpServers.SharepointLists.All | ✅ Working | SharePoint list operations |
| `mcp_KnowledgeTools` | McpServers.Knowledge.All | ✅ Working | Knowledge graph queries |
| `mcp_PlannerServer` | McpServers.Planner.All | ✅ Working | Task management |

**Removed servers (caused errors):**
| Server | Reason Removed |
|--------|---------------|
| `mcp_CalendarServer` | **403 Forbidden** — caused SSL timeout cascade, same pattern as MailServer (see ISS-025) |
| `mcp_MailServer` | **403 Forbidden** — caused SSL timeout cascade, killed agent (see ISS-024) |
| `mcp_TeamsServer` | Trialed for delivery path; not currently enabled in checked-in manifest |
| `mcp_OneDriveSharepointServer` | Trialed for delivery path; not currently enabled in checked-in manifest |
| `mcp_OutlookMail` | Not available in catalog |
| `mcp_CalendarTools` | Not available in catalog |
| `mcp_Dataverse` | Custom — not registered with platform |
| `workiq` | Custom — not registered with platform |
| `mcp_M365Copilot` | Returned errors |
| `mcp_ODSPRemoteServer` | Returned errors |
| `mcp_DASearch` | Returned errors |

**Total tools at runtime:** ~4 MCP server wrappers + 4 local tools (expandable when MCP servers expose individual tool schemas)

**Available MCP scopes** (from `a365.generated.config.json`): Calendar, CopilotMCP, DASearch, Knowledge, OneDriveSharepoint, Planner, SharepointLists, Teams, Word. **No `McpServers.Mail.All` scope** — email delivery relies on Teams MCP or other available servers.

**Not available in catalog**: Excel, Sales, Me, Search (DASearch is the closest alternative).

### Permissions Configured

| API | Scopes | Status |
|-----|--------|--------|
| Agent 365 Tools (`ea9ffc3e-...`) | `McpServers.Calendar.All`, `McpServers.Teams.All`, `McpServers.CopilotMCP.All`, `McpServers.DASearch.All`, `McpServers.Knowledge.All`, `McpServers.OneDriveSharepoint.All`, `McpServers.Planner.All`, `McpServers.SharepointLists.All`, `McpServers.Word.All`, `McpServersMetadata.Read.All` | ✅ Verified (10 scopes) |
| Messaging Bot API (`5a807f24-...`) | `Authorization.ReadWrite`, `user_impersonation` | ✅ Verified |
| Observability API (`9b975845-...`) | `user_impersonation` | ✅ Verified |
| Power Platform API (`8578e004-...`) | `Connectivity.Connections.Read` | ✅ Verified |
| MOS Auth Config (`6ec511af-...`) | `AuthConfig.Read` | ✅ Admin consent granted |
| MOS Environments (`8578e004-...`) | `EnvironmentManagement.Environments.Read` | ✅ Admin consent granted |
| MOS Titles (`e8be65d6-...`) | `Title.ReadWrite.All` | ✅ Admin consent granted |

### MOS Service Principals Created
*   **TPS Client App**: `eee0e003-a0ee-449d-bdf9-ef32d1edd976` (first-party client)
*   **MOS Resource App**: `fcb824e2-a058-4e06-8c09-f097dd565b1c` (for `6ec511af-...`)

### Resolved Issues

#### WAM Authentication Failure (RESOLVED)
The blueprint step was initially blocked by WAM (Windows Account Manager) authentication failures. The device is Azure AD Joined to HOSKING, not Contoso. WAM popups were appearing **behind other windows**. Resolution: User watched for and interacted with WAM popups manually to select Contoso account.

#### Inheritable Graph Permissions Warning (NON-BLOCKING)
During blueprint setup, `Connect-MgGraph` via `pwsh -NonInteractive` returned a token that failed JWT parsing. The CLI logged `SETUP_VALIDATION_FAILED` as a warning but continued. The publish step later successfully granted Microsoft Graph permissions directly.

### Configuration Files

#### `a365.config.json` (Static)
*   `tenantId`: `c2833f41-c31d-4c2f-98d1-947fdb699aba`
*   `subscriptionId`: `c2833f41-c31d-4c2f-98d1-947fdb699aba` (same as tenantId — no subscription)
*   `clientAppId`: `8e5206be-48e3-4da4-b741-d3908cf7c30a`
*   `messagingEndpoint`: `https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/api/messages`
*   `agentUserPrincipalName`: `salesopsbot@M365CPI14187042.OnMicrosoft.com`
*   `managerEmail`: `CoreyG@M365CPI14187042.OnMicrosoft.com`
*   `needDeployment`: `false`

#### `a365.generated.config.json` (Auto-generated by CLI)
*   `completed`: `true` (`completedAt: 2026-02-14T09:42:19`)
*   Blueprint IDs, client secret (encrypted), bot config, endpoint details

#### `.env` (Auto-updated by CLI)
*   `AGENT_ID`, `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID/SECRET/TENANTID/SCOPES`, `AGENTAPPLICATION` auth handler settings

### Prerequisite Installation
*   **PowerShell 7.5.4**: Downloaded ZIP from GitHub, extracted to `%LOCALAPPDATA%\PowerShell`.
*   **Microsoft.Graph.Applications**: Installed via `pwsh -Command "Install-Module -Name 'Microsoft.Graph.Applications' -Scope CurrentUser -Force"`.

### Permission Remediation (Pre-Blueprint)
`a365 config init` initially failed because the Contoso app registration was missing 5 required Microsoft Graph permissions. These were added via `az ad app update` and admin-consented:
`Application.ReadWrite.All`, `DelegatedPermissionGrant.ReadWrite.All`, `Directory.Read.All`, `AgentIdentityBlueprint.ReadWrite.All`, `AgentIdentityBlueprint.UpdateAuthProperties.All`

## 6. ISS-017 / ISS-018 Runtime Fixes (COMPLETE)

### ISS-017: Agent "typing then stops" (RESOLVED)
Root cause was AADSTS65001 consent_required — the agent app instance lacked OAuth2 delegated-permission consent. Fixed by creating permission grants, restoring auth_handlers with pre-exchange MCP token, and patching the SDK (`scripts/patch_sdk.py`) at Docker build time for three issues: `ChatAgent` → `Agent` import mismatch, `chat_client` → `client` constructor kwarg, and MCP headers silently dropped (replaced `headers=headers` with `httpx.AsyncClient(headers=headers)`).

### ISS-018: Agent hallucinating meetings (RESOLVED)
- **Symptom**: Agent fabricated "Sales Strategy Meeting 10:00 AM", "Client Check-In 2:00 PM", "End-of-Day Wrap-Up 4:30 PM" — none of which existed. Real meetings (e.g. "Hosking Ltd Discussion") were visible to the Graph API calendar poll but the agent had zero tools.
- **Root Cause Chain**: MCP gateway (`GET /agents/{id}/mcpServers`) returned **0 servers** for agent `5653b53b` → agent created with 0 tools → LLM fabricated answers.
- **Fix**: Added 3 local `FunctionTool` instances (`get_my_calendar_today`, `get_my_calendar_range`, `get_upcoming_meetings`) in `agent.py` that wrap `graph_client.get_calendar_view()`. These are passed as `initial_tools` to both `_create_agent()` and `setup_mcp_servers()`, ensuring the agent always has calendar access regardless of MCP gateway status.
- **Image**: `salesopsbot:fix-hallucination-v1`
- **Revision**: `azcaxyseurue7b6nw--0000019`

### Revision History

| Revision | Image | State | Notes |
|----------|-------|-------|-------|
| --0000040 | pipeline-v7b | **Running** | 4 MCP servers, 4 local tools, local tool merge fix, CalendarServer removed |
| --0000039 | pipeline-v7 | Deactivated | 7 MCP servers — CalendarServer 403 cascade broke agent (see ISS-025) |
| --0000038 | pipeline-v6 | Deactivated | Direct AzureOpenAI in meeting_processor (recursive loop fix), 4 MCP servers, 4 local tools |
| --0000037 | pipeline-v5 | Deactivated | Added `run_meeting_report` tool — hit recursive loop (meeting_processor called agent.run()) |
| --0000036 | pipeline-v4 | Deactivated | 4 MCP servers (MailServer removed), 3 local tools, pipeline code |
| --0000035 | pipeline-v3 | Deactivated | **BROKEN** — MailServer 403 cascade killed agent |
| --0000034 | pipeline-v2 | Deactivated | Pipeline working, email/Teams 403 (missing perms) |
| --0000033 | pipeline-v1 | Deactivated | Pipeline code, None crash in report_generator |
| --0000032 | mcp-prompt-v4 | Deactivated | Last known good before pipeline — 35 tools working |
| --0000019 | fix-hallucination-v1 | Deactivated | 3 local FunctionTools, anti-hallucination |
| --0000018 | fix-mcp-headers-v1 | Deactivated | ENVIRONMENT=Production, 0 MCP servers, hallucinated |
| --0000017 | fix-mcp-headers-v1 | Deactivated | Dev mode, MCP 403 Forbidden |
| --0000016 | fix-mcp-auth-v4 | Deactivated | SDK patch working, MCP 400 |
| --0000015 | fix-mcp-auth-v3 | Deactivated | auth_handlers + MCP pre-exchange |

### MCP Gateway Status (RESOLVED via Development mode)
The MCP gateway at `https://agent365.svc.cloud.microsoft/agents/5653b53b/mcpServers` returned **0 servers** in Production mode. Switching to `ENVIRONMENT=Development` mode uses the local `ToolingManifest.json` directly, bypassing the broken gateway. The 4 proven servers in ToolingManifest are discovered and their tools (~32) registered at first user message, plus 3 local calendar tools = ~35 tools total.

## 7. Agent 365 Session — Phase 8 (COMPLETE — 15 Feb 2026)

### ISS-020: 429 Rate Limiting — "Not Responding" (RESOLVED)
**Root cause**: Azure OpenAI quota was only 10K TPM. Agent with 35 tools generates large prompts that exceed this limit quickly.
**Fix**: Increased to **50K TPM** on the `gpt-4o` deployment.

### ISS-021: ToolingManifest Trimmed to 4 Proven Servers (RESOLVED)
**Root cause**: Original 12-server manifest included servers that weren't available in the MCP catalog or returned errors.
**Fix**: Trimmed to 4 servers that reliably connect: Word, SharePoint, Knowledge, Planner.

### ISS-022: Agent created with `max_iterations=10` and 300s timeout
Added to prevent runaway LLM loops. `_create_chat_client()` passes `max_iterations=10` and `process_user_message()` wraps agent invocation in `asyncio.wait_for(timeout=300)`.

### ISS-023: Dynamic Prompt System
`_build_prompt()` dynamically generates the system prompt by enumerating available tools and their descriptions. Greeting detection short-circuits the agent invocation for simple "hi"/"hello" messages to save tokens.

## 8. Pipeline Features — Phase 9 (COMPLETE — 15 Feb 2026)

### What Was Implemented
Full meeting intelligence pipeline: detect meeting end → fetch transcript → LLM analysis → generate reports → email summary → Teams message summary → MS Learn doc references.

### Files Modified (6 files, ~800 lines of new/modified code)

| File | Changes |
|------|---------|
| `src/integrations/graph_transcript_client.py` | Added `send_email()`, `resolve_chat_thread_id()`, `post_chat_message()`, `send_meeting_chat_message()` — all real Graph API calls |
| `src/integrations/ms_learn_client.py` | Replaced stubs with real `https://learn.microsoft.com/api/search` HTTP calls |
| `src/services/teams_chat_service.py` | Real Graph API calls, added `send_summary_message()`, `send_knowledge_message()` |
| `src/services/meeting_processor.py` | Full pipeline wiring with MS Learn enrichment, dual email strategy (Graph API first, MCP fallback), Teams post |
| `src/services/report_generator.py` | Fixed None-safety bug in `generate_email_html()` and `generate_adaptive_card()` — `str.replace()` crash when LLM returns null |
| `src/agent.py` | Replaced `# TODO: Phase 4.3` with delivery status logging in `handle_meeting_detected()` |

### Pipeline Execution Flow
1. Calendar handler detects meeting ended → triggers `handle_meeting_detected()`
2. Meeting processor fetches transcript (stub) and calls LLM for analysis
3. Report generator creates HTML email and Adaptive Card
4. MS Learn client searches for relevant documentation
5. Email sent via Graph API `sendMail` (requires `Mail.Send` permission)
6. Teams chat message posted (requires `OnlineMeetings.Read.All`)
7. Live knowledge service sends MS Learn references to Teams chat

### Pipeline Status (Production)
| Step | Status |
|------|--------|
| LLM transcript analysis | ✅ Working (gpt-4o 200 OK) |
| MS Learn search | ✅ Working ("Dynamics 365 Sales opportunity management" returned 1 result) |
| Report generation | ✅ Working (HTML + Adaptive Card) |
| Email send | ❌ 403 Forbidden — app `8e5206be` lacks `Mail.Send` application permission |
| Teams chat resolve | ❌ 403 Forbidden — app `8e5206be` lacks `OnlineMeetings.Read.All` permission |
| Transcript fetching | ✅ Working — Graph transcript retrieval implemented |

### ISS-024: mcp_MailServer 403 Cascade (RESOLVED)
**Symptom**: Adding `mcp_MailServer` to ToolingManifest.json caused the agent to stop responding entirely.
**Root cause**: `mcp_MailServer` returned 403 Forbidden from `agent365.svc.cloud.microsoft`. This triggered SSL shutdown timeout cascades that killed all MCP connections. Tool count dropped from 35 to 5 (only server names, no individual tools).
**Fix**: Removed `mcp_MailServer` from ToolingManifest.json. Deployed as `pipeline-v4` (revision `--0000036`). Agent responding again.

### Licensing — RESOLVED
**Issue**: "There's no Agent 365 licence available for this agent" when activating the blueprint.
**Fix**: Obtained a **trial license pack** for Microsoft Agent 365 and applied it to the Contoso tenant. Frontier enrollment alone does not provision the license. Once trial licenses were active, the agent could be set up from the blueprint via the **Agents store** in M365 admin center.

See: `docs/TROUBLESHOOTING-A365.md` (ISS-012) for full details.

### Agent Instance Details
The Agent 365 instance was created via the Agents store. The actual agentic user created differs from the configured UPN:

| Property | Configured (a365.config) | Actual (Entra ID) |
|----------|--------------------------|-------------------|
| UPN | `salesopsbot@M365CPI14187042.OnMicrosoft.com` | `SalesOpSynthWorker984ebb@M365CPI14187042.onmicrosoft.com` |
| Display Name | (not set) | `Sales Op Synth Worker` |
| Object ID | — | `ec35260f-ceb9-40b1-9e8b-afafe29187cf` |
| IsAgenticUser | — | `True` |
| RecipientType | — | `UserMailbox` |
| License SKU | — | `MICROSOFT_AGENT_FRONTIER_NO_TEAMS` |

**Key License Service Plans**: `AGENT_365_TOOLS`, `EXCHANGE_S_STANDARD`, `SHAREPOINTENTERPRISE_A365`, `AAD_PREMIUM_P2`, `OFFICESUBSCRIPTION`, `BI_AZURE_P2`, plus 30+ others.  
**Missing**: No Teams service plans (license is explicitly `NO_TEAMS`).

### Exchange Online Configuration (Completed 14 Feb 2026)
*   **Mailbox**: UserMailbox — created at 10:36 AM
*   **HiddenFromAddressListsEnabled**: `False` (visible in GAL)
*   **Calendar Processing**: `AutoUpdate` (meeting invites auto-update calendar)
    *   `DeleteSubject`: `False` (preserves meeting subject)
    *   `DeleteComments`: `False` (preserves meeting body/notes)
    *   `AddOrganizerToSubject`: `False` (clean subject line)
    *   `AllowConflicts`: `True` (can attend overlapping meetings)

### GAL Visibility — PROPAGATION DELAY
**Issue**: Agent not visible in GAL/people picker immediately after creation.  
**Root Cause**: Exchange Online GAL/OAB propagation takes up to 24 hours for new mailboxes.  
**Workaround**: Type the full email address directly in meeting invite "To" field in **Outlook on the Web** (OWA queries Exchange directly, bypasses cached OAB).  
**Email**: `SalesOpSynthWorker984ebb@M365CPI14187042.onmicrosoft.com`  
**Teams limitation**: The `NO_TEAMS` license means the agent won't appear in Teams people picker. This is by design — the agent accesses meeting transcripts via Graph API after meetings, not by joining the Teams call.

## 9. Agent Activation — Phase 7 (COMPLETE)

## 9a. On-Demand Meeting Reports — Phase 10 (COMPLETE — 15 Feb 2026)

### Problem
User asked the agent "can you run the meeting report for the Avon meeting today" → agent said "I don't have a tool for that." The `handle_meeting_detected()` and `MeetingProcessor` only triggered by the calendar poller, NOT exposed as an LLM-callable tool.

### Solution
Added `run_meeting_report` as a 4th `FunctionTool` in `_build_local_tools()`. Updated `AGENT_PROMPT_BASE` to add "ON-DEMAND CAPABILITIES" section instructing the LLM how and when to call it.

### ISS-026: Recursive LLM Loop (RESOLVED)
`run_meeting_report` called `meeting_processor.process_meeting()` which internally called `self.agent.agent.run(prompt)` — this re-invoked the full agent with all tools including `run_meeting_report` itself → infinite recursive loop eating TPM.

**Fix**: Replaced `agent.run()` in `meeting_processor.py` with direct `AzureOpenAI` `chat.completions.create()` call (no tools). Also disabled MCP email fallback which used the same pattern. Added `openai>=1.0.0` as explicit dependency.

## 9b. MCP-Based Delivery — Phase 11 (IN PROGRESS — 15 Feb 2026)

### Problem
Email/Teams delivery via direct Graph API returns 403 because the app registration uses **delegated** MCP scopes, not Graph **application** permissions. The correct approach (per Agent 365 architecture) is to use MCP servers which authenticate via the agentic token exchange.

### Solution
1. **Delivery strategy updates**: Prompt/tool chaining and report payload were updated so delivery can be delegated to MCP tools when those servers are enabled.
2. **Updated `run_meeting_report` output**: Now returns `email_html` and `email_subject` fields so the outer agent can pass them to MCP tools.
3. **Updated agent prompt**: ON-DEMAND CAPABILITIES section instructs the LLM to chain `run_meeting_report` → MCP email/Teams tools for delivery. Multi-tool sequential calling enabled.
4. **Local tool merge**: After `add_tool_servers_to_agent()`, the code detects if the SDK dropped local tools and re-adds them by patching the agent's tool list attributes.

### ISS-025: mcp_CalendarServer 403 Cascade (RESOLVED)
Same pattern as ISS-024 (`mcp_MailServer`). Despite `McpServers.Calendar.All` being consented, the MCP gateway returns 403. This cascaded into SSL timeout errors killing all MCP connections. **Fix**: Removed `mcp_CalendarServer` from ToolingManifest.json. Calendar access handled by local FunctionTools.

### ISS-027: SDK Drops Local Tools After MCP Setup (RESOLVED)
`add_tool_servers_to_agent()` returned a new agent with only MCP server tools — the 4 local FunctionTools were dropped. **Fix**: Added merge logic in `setup_mcp_servers()` that detects missing local tools and re-adds them by patching the agent's internal tool list.

### ISS-028: Agent Shows Only MCP Server Names, Not Individual Tools (OBSERVED)
After MCP setup, the tool log shows 6-7 entries (one per MCP server) rather than ~35 individual tools. This may be expected if MCP tools are lazily expanded at `agent.run()` time, or it may indicate that the MCP tool schema expansion isn't working. Under investigation.

## 10. Known Issues & Remaining Work

### Resolved: Transcript Fetching
`graph_transcript_client.get_transcript_content()` now performs real Graph API transcript retrieval, including event → onlineMeeting resolution and transcript listing/content fetch.

### In Progress: MCP-Based Email/Teams Delivery
The `run_meeting_report` tool now returns `email_html` and `email_subject` fields. The agent prompt instructs the LLM to chain: call `run_meeting_report` → then use MCP email/Teams tools to deliver the report. This approach uses **delegated permissions** via the agentic token exchange (A365 MCP scopes), avoiding the need for Graph application permissions.

**Status:** Pipeline-v7b deployed (revision `--0000040`). Delivery flow design is in place; current checked-in manifest remains on 4 proven servers.

**Risk:** No `McpServers.Mail.All` scope exists in the consented scopes. Email must go through another available MCP tool, or the TeamsServer may have email capabilities.

### Resolved: Direct Graph API Delivery 403s
The pipeline's internal Graph API calls for email (`Mail.Send`) and Teams chat (`OnlineMeetings.Read.All`, `Chat.ReadWrite.All`) return 403 because the app registration uses delegated permissions via A365, not Graph application permissions. **This is by design** — the correct approach is to use MCP servers which authenticate via the agentic token exchange.

### Non-Blocking: mcp_CalendarServer 403
Despite `McpServers.Calendar.All` being consented, `mcp_CalendarServer` returns 403 from the MCP gateway. Same cascade pattern as `mcp_MailServer` (see ISS-025). Calendar access is handled by the 4 local FunctionTools instead.

### Non-Blocking: App Registration Architecture
The current setup uses `8e5206be` ("Agent 365 Claude Bridge") as `AZURE_CLIENT_ID`. There is no separate "Synthetic Worker" app registration in the Contoso tenant. The pipeline uses client credentials flow via `DefaultAzureCredential` with this app's client secret for Graph API calls. MCP tools use agentic delegated token exchange.

### Future Work
1.  **Replace Dynamics client stubs** with real Dataverse API / MCP calls.
2.  **Investigate CalendarServer / MailServer 403** — may need platform-side consent or different server names.
3.  **Production hardening**: Auto-scaling rules, custom domain, TLS, Azure Monitor alerts.
4.  **Consider MCP gateway (Production mode)**: Currently using Development mode with local ToolingManifest.json. Production mode queries the gateway API which returned 0 servers — may work after platform updates.
5.  **Human-in-the-loop**: Add approval workflows for CRM updates via Actionable Messages.

## 11. Key Decisions & Pivots
*   **CRM**: Pivoted from **Salesforce** to **Dynamics 365**.
*   **Access Model**: Pivoted from "Application Permissions" to "**Agent as Participant**" (Delegated/Service Principal acting as user) to simplify transcript access.
*   **Deployment (Phase 5)**: Used **AZD + Bicep** (IaC) to deploy to Container Apps. This is working and running.
*   **Deployment (Phase 6)**: Completed **official `a365` CLI** deployment per MS Learn docs. Used `needDeployment: false` pattern to keep existing Container Apps hosting while registering with Agent 365 identity/blueprint system. Agent published to M365 as Title `T_ae143bb1-8f29-3a70-a2dc-ceab6f965d08`.
*   **Secrets**: Stored in **Azure Key Vault** and referenced by the Container App, rather than injected as plain env vars.
*   **Split-Tenant**: Infrastructure hosted in HOSKING tenant; bot identity in Contoso tenant. This adds complexity to auth flows.
*   **Subscription Workaround**: Contoso tenant has no Azure subscriptions. Config uses `tenantId` as `subscriptionId` to satisfy the CLI.
*   **MCP Server Selection**: Trimmed from 12 servers to 4 proven ones. Only servers available in the Agent 365 catalog and passing runtime checks are included.
*   **Development Mode**: Using `ENVIRONMENT=Development` to bypass broken MCP gateway. Local `ToolingManifest.json` provides reliable tool discovery.
*   **Pipeline Delivery Strategy**: Shifted from direct Graph API email/Teams (requires application permissions) to **MCP tool chaining** — the outer agent calls `run_meeting_report` then uses MCP servers (delegated agentic tokens) for delivery. This aligns with the Agent 365 architecture.
*   **Meeting Processor Direct LLM**: Replaced `agent.run()` in meeting_processor with direct `AzureOpenAI` `chat.completions.create()` to prevent recursive tool loops.
*   **Local Tool Merge**: Added defensive code to re-add local tools after `add_tool_servers_to_agent()` since the SDK drops them.
*   **OpenAI Quota**: Increased from 10K to 50K TPM to handle tool-heavy prompts without 429 rate limiting.
*   **Agent Iteration Limits**: `max_iterations=10` and 300s timeout to prevent runaway LLM loops.

## 12. Installed Tooling
| Tool | Version | Purpose |
|------|---------|---------|
| Azure CLI | v2.83.0 | Azure resource management |
| AZD CLI | v1.23.5 | Azure Developer CLI (deploy via Bicep) |
| .NET 8 SDK | v8.0.418 | Prerequisite for a365 CLI |
| a365 CLI | v1.1.62-preview | Official Agent 365 deployment tool |
| PowerShell 7 | v7.5.4 | Required by a365 setup steps (ZIP install at `%LOCALAPPDATA%\PowerShell`) |
| Microsoft.Graph.Applications | Latest | PowerShell module for Graph operations |
| Docker | v27.4.0 | Container image builds |
| Python | 3.11 | Bot runtime |

## 13. File Manifest
| File | Purpose | Status |
|------|---------|--------|
| `src/agent.py` | Main agent entry point | **Complete** |
| `src/main.py` | HTTP host bootstrap (port 8000) | **Complete** |
| `src/handlers/email_handler.py` | Meeting Detection (Email) | **Complete** |
| `src/handlers/calendar_handler.py` | Meeting Detection (Calendar) | **Complete** |
| `src/services/meeting_processor.py` | Intelligence Pipeline (~290 lines) | **Complete** — full pipeline with LLM analysis, MS Learn enrichment, dual email strategy, Teams delivery |
| `src/integrations/dynamics_client.py` | CRM Client (Stub) | **Complete** |
| `src/integrations/graph_transcript_client.py` | Graph API client (~390 lines) | **Complete** — calendar, email send, chat resolve/post, meeting chat |
| `src/integrations/ms_learn_client.py` | Microsoft Learn search (~130 lines) | **Complete** — real API calls working |
| `src/extraction/llm_extractor.py` | LLM-powered data extraction | **Complete** |
| `src/extraction/prompts.py` | Extraction prompt templates | **Complete** |
| `src/extraction/schemas.py` | Pydantic data models | **Complete** |
| `src/services/email_composer.py` | Email composition service | **Complete** |
| `src/services/teams_chat_service.py` | Teams chat messaging (~120 lines) | **Complete** — real Graph API calls |
| `src/services/live_knowledge_service.py` | MS Learn knowledge injection | **Complete** |
| `src/services/report_generator.py` | Report generation (HTML + Adaptive Card) | **Complete** — None-safety fix applied |
| `ToolingManifest.json` | MCP server declarations (4 proven servers) | **Complete** — stable baseline (Word, SharePoint Lists, Knowledge, Planner) |
| `tests/verify_pipeline.py` | Logic Verification | **Verified** |
| `Dockerfile` | Container image definition (includes `RUN python scripts/patch_sdk.py`) | **Complete** |
| `scripts/patch_sdk.py` | SDK patches: ChatAgent→Agent, chat_client→client, headers→httpx.AsyncClient | **Complete** |
| `deployment.yaml` | Legacy K8s-style manifest (superseded by Bicep) | **Superseded** |
| `azure.yaml` | AZD project configuration | **Complete** |
| `infra/main.bicep` | Main Bicep IaC template | **Complete** |
| `infra/resources.bicep` | Azure resource definitions | **Complete** |
| `infra/main.parameters.json` | Bicep parameter bindings | **Complete** |
| `.azure/plan.copilotmd` | Deployment plan | **Complete** |
| `.azure/summary.copilotmd` | Deployment summary | **Complete** |
| `a365.config.json` | Agent 365 CLI configuration | **Complete** |
| `a365.generated.config.json` | Agent 365 CLI generated state (blueprint IDs, secret) | **Complete** |
| `manifest/manifest.json` | Teams/M365 app manifest (published) | **Complete** |
| `manifest/agenticUserTemplateManifest.json` | Agentic user template manifest | **Complete** |
| `manifest/manifest.zip` | Published package archive | **Complete** |
| `manifest/color.png` | Agent icon (color) | **Default** |
| `manifest/outline.png` | Agent icon (outline) | **Default** |
| `blueprint_full.txt` | Blueprint setup output log (debug) | **Temp** |
| `required_permissions.json` | Graph permission JSON (used for az ad app update) | **Temp** |
| `docs/TROUBLESHOOTING-A365.md` | Agent 365 deployment troubleshooting & split-tenant playbook | **Complete** |
| `SPEC-SyntheticWorker.md` | Architecture Spec | **Updated** |
| `PLAN.md` | Implementation Plan | **Updated** |
| `SETUP.md` | Prerequisites & setup guide | **Updated** |
| `README.md` | Project overview & quick start | **Updated** |
