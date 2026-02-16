# Agent 365 Deployment Troubleshooting Guide

> **Purpose:** Capture all issues encountered during Agent 365 (`a365`) CLI deployment and provide a reusable reference for future agent deployments. This project uses a **split-tenant configuration** which is non-standard and introduces additional complexity.

> **Official Docs Reference:** [Agent 365 Development Lifecycle](https://learn.microsoft.com/microsoft-agent-365/developer/a365-dev-lifecycle) | [Agent 365 Troubleshooting Guide](https://learn.microsoft.com/microsoft-agent-365/developer/troubleshooting) | [Agent 365 CLI](https://learn.microsoft.com/microsoft-agent-365/developer/agent-365-cli)

> **Related Incident Write-up:** [Meeting Report Transcript Pipeline Stabilization (2026-02-16)](INCIDENT-2026-02-MEETING-REPORT.md)

---

## Table of Contents

0. [Current Operational Status (2026-02-16)](#0-current-operational-status-2026-02-16)

1. [Architecture: Split-Tenant Configuration](#1-architecture-split-tenant-configuration)
2. [Official Deployment Lifecycle](#2-official-deployment-lifecycle)
3. [Prerequisites & Setup Checklist](#3-prerequisites--setup-checklist)
4. [Issue Catalogue](#4-issue-catalogue)
   - [ISS-001: PowerShell stderr treated as error](#iss-001-powershell-stderr-treated-as-error)
   - [ISS-002: Missing API permissions on custom client app](#iss-002-missing-api-permissions-on-custom-client-app)
   - [ISS-003: No Azure subscription in identity tenant](#iss-003-no-azure-subscription-in-identity-tenant)
   - [ISS-004: WAM authentication failure (authentication_canceled)](#iss-004-wam-authentication-failure-authentication_canceled)
   - [ISS-005: WAM popup hidden behind windows](#iss-005-wam-popup-hidden-behind-windows)
   - [ISS-006: Inheritable Graph permissions warning (SETUP_VALIDATION_FAILED)](#iss-006-inheritable-graph-permissions-warning-setup_validation_failed)
   - [ISS-007: PowerShell 7 not installed (no admin rights)](#iss-007-powershell-7-not-installed-no-admin-rights)
   - [ISS-008: Beta permissions not visible in Entra admin center](#iss-008-beta-permissions-not-visible-in-entra-admin-center)
   - [ISS-009: Federated Identity Credential (FIC) creation failure](#iss-009-federated-identity-credential-fic-creation-failure)
   - [ISS-010: Blueprint endpoint already registered](#iss-010-blueprint-endpoint-already-registered)
   - [ISS-011: `a365 publish` MOS token browser auth timeout](#iss-011-a365-publish-mos-token-browser-auth-timeout)
   - [ISS-012: No Agent 365 licence available for this agent](#iss-012-no-agent-365-licence-available-for-this-agent)
   - [ISS-013: Agent not visible in GAL / cannot add to meetings](#iss-013-agent-not-visible-in-gal--cannot-add-to-meetings)
   - [ISS-014: Container App crash-loop — cascading startup failures](#iss-014-container-app-crash-loop--cascading-startup-failures)
   - [ISS-015: Azure OpenAI 401 — stale API key in Key Vault / Container App secret cache](#iss-015-azure-openai-401--stale-api-key-in-key-vault--container-app-secret-cache)
   - [ISS-016: MCP tools not connecting / agent hallucinating data / calendar not accepting meetings](#iss-016-mcp-tools-not-connecting--agent-hallucinating-data--calendar-not-accepting-meetings)
   - [ISS-017: Agent "typing then stops" — auth_handlers consent gate + MCP token exchange](#iss-017-agent-typing-then-stops--auth_handlers-consent-gate--mcp-token-exchange)
   - [ISS-018: MCP headers silently dropped — 400 Bad Request from MCP platform](#iss-018-mcp-headers-silently-dropped--400-bad-request-from-mcp-platform)
   - [ISS-019: Agent hallucinating meetings — MCP gateway returns 0 servers](#iss-019-agent-hallucinating-meetings--mcp-gateway-returns-0-servers)
   - [ISS-020: 429 Too Many Requests — agent "not responding"](#iss-020-429-too-many-requests--agent-not-responding)
   - [ISS-021: ToolingManifest trimmed — 12 servers to 4 proven servers](#iss-021-toolingmanifest-trimmed--12-servers-to-4-proven-servers)
   - [ISS-022: None crash in report_generator — LLM returning null fields](#iss-022-none-crash-in-report_generator--llm-returning-null-fields)
   - [ISS-023: Pipeline email/Teams delivery 403 — missing application permissions](#iss-023-pipeline-emailteams-delivery-403--missing-application-permissions)
   - [ISS-024: mcp_MailServer 403 cascade — agent stops responding](#iss-024-mcp_mailserver-403-cascade--agent-stops-responding)
   - [ISS-025: mcp_CalendarServer 403 cascade — same pattern as MailServer](#iss-025-mcp_calendarserver-403-cascade--same-pattern-as-mailserver)
   - [ISS-026: Recursive LLM loop — run_meeting_report calls agent.run()](#iss-026-recursive-llm-loop--run_meeting_report-calls-agentrun)
   - [ISS-027: SDK drops local tools after MCP setup](#iss-027-sdk-drops-local-tools-after-mcp-setup)
   - [ISS-028: MCP delivery strategy — delegated vs application permissions](#iss-028-mcp-delivery-strategy--delegated-vs-application-permissions)
    - [ISS-029: Report email readability + summary formatting regressions](#iss-029-report-email-readability--summary-formatting-regressions)
5. [Split-Tenant Deployment Playbook](#5-split-tenant-deployment-playbook)
6. [a365 CLI Command Reference (Quick)](#6-a365-cli-command-reference-quick)
7. [Diagnostic Commands](#7-diagnostic-commands)
8. [Lessons Learned](#8-lessons-learned)

---

## 0. Current Operational Status (2026-02-16)

| Item | Status |
|------|--------|
| Active revision | `azcaxyseurue7b6nw--azd-1771242381` |
| Container app health | ✅ Running / Healthy / 100% traffic |
| `/api/health` | ✅ `status=ok`, `agent_initialized=true`, `mcp.state=ready` |
| Tests | ✅ `pytest -q` passing |
| Report UX updates | ✅ live (header readability, summary normalization, sentiment + expansion sections) |

---

## 1. Architecture: Split-Tenant Configuration

### What Is It?

A split-tenant setup separates **Azure infrastructure hosting** from the **Microsoft 365 identity** into different Entra ID tenants. This is **not the standard pattern** documented by Microsoft, which assumes a single tenant owns both the Azure subscription and the M365 identity.

### Our Configuration

| Concern | Tenant | Tenant ID | Domain |
|---------|--------|-----------|--------|
| **Infrastructure** (Container Apps, ACR, Key Vault, OpenAI) | HOSKING | `b5c09a39-9df6-437a-a76e-19095fa6f20d` | `hosking.wales` |
| **Identity** (Agent Blueprint, Bot, User, Permissions) | Contoso | `c2833f41-c31d-4c2f-98d1-947fdb699aba` | `M365CPI14187042.OnMicrosoft.com` |

### Why This Matters

1. **Azure CLI context switching** — You must `az login` to different tenants for infrastructure vs. identity operations
2. **WAM (Windows Account Manager)** — Defaults to the device-joined tenant, causing auth failures when operating against the other tenant
3. **No Azure subscription** — The identity tenant (Contoso) has no Azure subscriptions, which the CLI expects
4. **Managed Identity** — The Container App's managed identity lives in HOSKING but the bot identity lives in Contoso
5. **`a365 config init`** — The CLI validates `subscriptionId`, but the identity tenant may not have one

### Recommendation for New Deployments

> **Prefer a single-tenant architecture** where the Azure subscription and M365 identity are in the same Entra ID tenant. This eliminates WAM cross-tenant issues, subscription workarounds, and context switching.

If split-tenant is unavoidable, see [Section 5: Split-Tenant Deployment Playbook](#5-split-tenant-deployment-playbook).

---

## 2. Official Deployment Lifecycle

The Agent 365 lifecycle is: build/run, config, blueprint, deploy, publish, create instances. Our CLI execution sequence below maps to those stages, with infrastructure deploy commands skipped when `needDeployment: false`.

| Step | CLI Command | Description | Docs |
|------|-------------|-------------|------|
| 1 | `az login` | Authenticate to correct tenant | [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| 2 | `a365 config init` | Create/import `a365.config.json` | [Setup Config](https://learn.microsoft.com/microsoft-agent-365/developer/a365-config) |
| 3 | `a365 setup requirements` | Validate prerequisites (.NET, PS7, Graph modules) | [Agent 365 CLI](https://learn.microsoft.com/microsoft-agent-365/developer/agent-365-cli) |
| 4 | `a365 setup infrastructure` | Create Azure resources (App Service, etc.) | [Deploy to Azure](https://learn.microsoft.com/microsoft-agent-365/developer/deploy-agent-azure) |
| 5 | `a365 setup blueprint` | Create Agent Blueprint, endpoint, client secret | [Setup Blueprint](https://learn.microsoft.com/microsoft-agent-365/developer/registration) |
| 6 | `a365 setup permissions mcp` | Configure MCP server permissions | [Setup Blueprint](https://learn.microsoft.com/microsoft-agent-365/developer/registration) |
| 7 | `a365 setup permissions bot` | Configure Bot API, Observability, Power Platform permissions | [Setup Blueprint](https://learn.microsoft.com/microsoft-agent-365/developer/registration) |
| 8 | `a365 deploy` | Build and deploy code to Azure | [Deploy to Azure](https://learn.microsoft.com/microsoft-agent-365/developer/deploy-agent-azure) |
| 9 | `a365 publish` | Publish to M365 admin center | [Publish](https://learn.microsoft.com/microsoft-agent-365/developer/publish) |
| 10 | *(Admin center / Teams flow)* | Create agent instances from published blueprint | [Create Instances](https://learn.microsoft.com/microsoft-agent-365/developer/create-instance) |

> **Shortcut:** `a365 setup all` combines setup steps for prerequisites, blueprint, and permissions (plus infrastructure when enabled).

### Non-Azure Hosting (`needDeployment: false`)

If your agent is already deployed to Azure Container Apps, AWS, GCP, or any other hosting:
- Set `"needDeployment": false` in `a365.config.json`
- Set `"messagingEndpoint"` to your existing endpoint URL (must end with `/api/messages`)
- Steps 4 and 8 are automatically skipped
- See: [Deploy to AWS](https://learn.microsoft.com/microsoft-agent-365/developer/deploy-agent-aws) | [Deploy to GCP](https://learn.microsoft.com/microsoft-agent-365/developer/deploy-agent-gcp)

---

## 3. Prerequisites & Setup Checklist

Complete this checklist **before** running any `a365` commands:

### Required Tools

- [ ] **.NET 8.0 SDK** — `dotnet --version` should return `8.x.x`
- [ ] **Azure CLI** — `az --version` should return `2.x.x`
- [ ] **a365 CLI** — Install: `dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli --prerelease`
- [ ] **PowerShell 7** — Required by `a365 setup` steps. If no admin rights, download ZIP from [GitHub Releases](https://github.com/PowerShell/PowerShell/releases) and extract to `%LOCALAPPDATA%\PowerShell`
- [ ] **Microsoft.Graph.Applications** PowerShell module — `pwsh -Command "Install-Module -Name 'Microsoft.Graph.Applications' -Scope CurrentUser -Force"`

### Required Permissions

- [ ] **Entra ID role**: Global Administrator, Agent ID Administrator, or Agent ID Developer
- [ ] **Azure subscription access**: Contributor or Owner (on infrastructure tenant)
- [ ] **Frontier preview**: Enrolled at https://adoption.microsoft.com/copilot/frontier-program/

### Custom Client App Registration

Before running `a365 config init`, create an app registration in the **identity tenant** with:

- [ ] **Supported account types**: Single tenant
- [ ] **Redirect URIs** (Public client/native):
  - `http://localhost`
  - `http://localhost:8400/`
  - `ms-appx-web://Microsoft.AAD.BrokerPlugin/{client-id}`
- [ ] **5 Delegated Permissions** (Microsoft Graph):
  - `Application.ReadWrite.All`
  - `DelegatedPermissionGrant.ReadWrite.All`
  - `Directory.Read.All`
  - `AgentIdentityBlueprint.ReadWrite.All`
  - `AgentIdentityBlueprint.UpdateAuthProperties.All`
- [ ] **Admin consent granted** for all permissions

> **Important:** Use **Delegated** permissions, NOT Application permissions. See [Custom Client App Registration](https://learn.microsoft.com/microsoft-agent-365/developer/custom-client-app-registration).

> **Warning:** The two `AgentIdentityBlueprint.*` permissions are beta APIs and may not be visible in the Entra admin center. If not visible, use the Graph API method (Option B) described in the [official docs](https://learn.microsoft.com/microsoft-agent-365/developer/custom-client-app-registration#option-b-microsoft-graph-api-for-beta-permissions). **Do NOT use the "Grant admin consent" button in Entra after using the API method** — it will delete the beta permissions.

---

## 4. Issue Catalogue

### ISS-001: PowerShell stderr treated as error

| Field | Detail |
|-------|--------|
| **Stage** | `az login` |
| **Symptom** | `az login --tenant <id> --allow-no-subscriptions` appears to fail with exit code 1 in PowerShell |
| **Root Cause** | Azure CLI writes WARNING messages to stderr. PowerShell treats any stderr output as a terminating error, causing `$LASTEXITCODE = 1` |
| **Impact** | Login actually succeeds but appears to fail, blocking automation |
| **Resolution** | Verify login status with `az account show`. The exit code is unreliable for `az login` in PowerShell |
| **Prevention** | Redirect stderr: `az login 2>&1` or check `az account show` instead of exit codes |
| **Split-Tenant?** | Amplified — `--allow-no-subscriptions` generates extra warnings |

---

### ISS-002: Missing API permissions on custom client app

| Field | Detail |
|-------|--------|
| **Stage** | `a365 config init` |
| **Symptom** | Config init fails validation: custom client app missing required Graph permissions |
| **Root Cause** | App registration was created without the 5 required delegated permissions |
| **Impact** | Cannot proceed with blueprint setup |
| **Resolution** | Add all 5 permissions via Entra admin center or Graph API, then grant admin consent |
| **Prevention** | Follow the [Custom Client App Registration](https://learn.microsoft.com/microsoft-agent-365/developer/custom-client-app-registration) guide **before** running `a365 config init` |
| **CLI Fix** | `az ad app update --id <app-id> --required-resource-accesses @required_permissions.json` |

**Required permissions JSON example:**
```json
[{
  "resourceAppId": "00000003-0000-0000-c000-000000000000",
  "resourceAccess": [
    {"id": "bdfbf15f-ee85-4955-8571-bf056f821f9c", "type": "Scope"},
    {"id": "41ce6ca6-6826-4807-84e1-804ab0942225", "type": "Scope"},
    {"id": "06da0dbc-49e2-44d2-8312-53f166ab848a", "type": "Scope"},
    {"id": "4fd490fc-7697-4e12-80f4-dc532b04445b", "type": "Scope"},
    {"id": "6f677aa9-48c6-4cda-8dad-85f71b3b76d3", "type": "Scope"}
  ]
}]
```

---

### ISS-003: No Azure subscription in identity tenant

| Field | Detail |
|-------|--------|
| **Stage** | `a365 config init` |
| **Symptom** | CLI expects a `subscriptionId` but the identity tenant has no Azure subscriptions |
| **Root Cause** | Split-tenant: identity (Contoso) has Entra ID only, no Azure subscriptions. Infrastructure lives in HOSKING tenant |
| **Impact** | Cannot complete config wizard; `subscriptionId` is a required field |
| **Resolution** | Set `subscriptionId` to the same value as `tenantId` in the config. The CLI accepts this for `needDeployment: false` scenarios |
| **Prevention** | Use single-tenant architecture, or pre-create `a365.config.json` manually with the workaround value |
| **Split-Tenant?** | Yes — this issue is exclusive to split-tenant configurations |

**Config workaround:**
```json
{
  "tenantId": "c2833f41-c31d-4c2f-98d1-947fdb699aba",
  "subscriptionId": "c2833f41-c31d-4c2f-98d1-947fdb699aba",
  "needDeployment": false
}
```

---

### ISS-004: WAM authentication failure (authentication_canceled)

| Field | Detail |
|-------|--------|
| **Stage** | `a365 setup blueprint` |
| **Symptom** | Blueprint setup fails silently with exit code 1. With `--verbose`: `MSAL authentication failed: User canceled authentication. ErrorCode: authentication_canceled` |
| **Root Cause** | The device is Azure AD Joined to **HOSKING** tenant. WAM defaults to the HOSKING account (`WamDefaultSet: YES`). The a365 CLI uses WAM broker authentication (`RuntimeBroker.SignInInteractivelyAsync`), which presents an account picker defaulting to HOSKING. The Contoso account is not registered with WAM, so auth fails as "canceled" |
| **Impact** | **Complete blocker** — cannot create blueprint |
| **Resolution** | Watch for the WAM popup (it appears behind other windows — see ISS-005) and manually select the Contoso account. Alternatively, register the Contoso account with WAM via Windows Settings |
| **Prevention** | Register the target tenant account with WAM **before** starting: Settings → Accounts → Access work or school → Connect → sign in with the identity tenant account |
| **Split-Tenant?** | Yes — this issue is exclusive to split-tenant / multi-tenant device scenarios |
| **Note** | `AZURE_IDENTITY_DISABLE_BROKER=true` does NOT disable WAM in the a365 CLI — the CLI hardcodes broker usage |

**Diagnostic commands:**
```powershell
# Check device join status
dsregcmd /status

# Look for:
#   AzureAdJoined: YES
#   TenantName: <your-device-tenant>
#   WamDefaultSet: YES
#   WamDefaultAuthority: organizations
```

**Register second tenant account with WAM:**
1. Open **Settings → Accounts → Access work or school**
2. Click **Connect**
3. Sign in with the identity tenant account (e.g., `CoreyG@M365CPI14187042.OnMicrosoft.com`)
4. This performs a **Workplace Join** — it does NOT change the primary Azure AD Join

---

### ISS-005: WAM popup hidden behind windows

| Field | Detail |
|-------|--------|
| **Stage** | `a365 setup blueprint`, `a365 setup permissions`, `a365 publish` |
| **Symptom** | CLI appears to hang or times out waiting for authentication. No visible popup |
| **Root Cause** | The WAM account picker popup spawns as a system dialog that may appear behind VS Code, the terminal, or other windows |
| **Impact** | Auth appears to time out or be canceled when the user doesn't see or interact with the popup |
| **Resolution** | **Alt-Tab** through all windows to find the WAM popup when the CLI says "Authenticating via Windows Account Manager..." |
| **Prevention** | Minimize other windows before running auth-triggering commands. The CLI uses WAM at multiple stages (blueprint, permissions, publish) |
| **Split-Tenant?** | Amplified — WAM shows an account picker with multiple accounts, making it more likely the popup needs interaction |

---

### ISS-006: Inheritable Graph permissions warning (SETUP_VALIDATION_FAILED)

| Field | Detail |
|-------|--------|
| **Stage** | `a365 setup blueprint` (configuring inheritable permissions for Microsoft Graph) |
| **Symptom** | Warning: `Failed to configure Microsoft Graph inheritable permissions: [SETUP_VALIDATION_FAILED]` |
| **Root Cause** | The CLI invokes `Connect-MgGraph` via `pwsh -NonInteractive` to configure Graph permissions. The returned token failed JWT parsing (`FormatException: not a valid Base-64 string`). This appears related to the WAM/non-interactive auth context |
| **Impact** | **Non-blocking warning** — blueprint creation continues and completes. The `a365 publish` step later grants Graph permissions successfully via a different method |
| **Resolution** | No action needed. Can retry with `a365 setup blueprint` later, or the publish step handles it |
| **Prevention** | Ensure `Connect-MgGraph` works interactively in pwsh before running setup |

---

### ISS-007: PowerShell 7 not installed (no admin rights)

| Field | Detail |
|-------|--------|
| **Stage** | `a365 setup requirements` |
| **Symptom** | Requirements check fails: PowerShell 7 not found |
| **Root Cause** | Standard installation methods (MSI, winget) require admin privileges |
| **Impact** | Cannot proceed with setup steps that require pwsh |
| **Resolution** | Download the ZIP archive from [PowerShell GitHub Releases](https://github.com/PowerShell/PowerShell/releases) and extract to `%LOCALAPPDATA%\PowerShell`. Add to PATH |
| **Prevention** | Pre-install PowerShell 7 before starting the deployment process |

**ZIP install steps:**
```powershell
# Download ZIP (example for 7.5.4)
$url = "https://github.com/PowerShell/PowerShell/releases/download/v7.5.4/PowerShell-7.5.4-win-x64.zip"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\pwsh.zip"

# Extract
Expand-Archive "$env:TEMP\pwsh.zip" -DestinationPath "$env:LOCALAPPDATA\PowerShell" -Force

# Add to current session PATH
$env:PATH = "$env:LOCALAPPDATA\PowerShell;$env:PATH"

# Verify
pwsh --version
```

---

### ISS-008: Beta permissions not visible in Entra admin center

| Field | Detail |
|-------|--------|
| **Stage** | Custom client app setup (pre-deployment) |
| **Symptom** | `AgentIdentityBlueprint.ReadWrite.All` and `AgentIdentityBlueprint.UpdateAuthProperties.All` cannot be found in the Entra admin center API permissions search |
| **Root Cause** | These are beta Graph API permissions that may not be visible in the Entra UI |
| **Impact** | Cannot add all 5 required permissions via the portal |
| **Resolution** | Use Graph API (Option B) to add permissions via `POST /v1.0/oauth2PermissionGrants` or `az ad app update --required-resource-accesses @file.json` |
| **Prevention** | Always have the JSON permission manifest ready as a fallback |

> **Critical Warning:** If you use the Graph API method to grant consent, **do NOT click "Grant admin consent" in the Entra admin center afterward** — it will overwrite the API-granted consent and remove the beta permissions. See [official docs](https://learn.microsoft.com/microsoft-agent-365/developer/custom-client-app-registration#option-b-microsoft-graph-api-for-beta-permissions).

---

### ISS-009: Federated Identity Credential (FIC) creation failure

| Field | Detail |
|-------|--------|
| **Stage** | `a365 publish` (Step: Configure blueprint authentication) |
| **Symptom** | Log shows `Failed to create FIC (expected in some scenarios)` |
| **Root Cause** | The FIC creation may fail in certain tenant configurations. The CLI explicitly notes this as "expected in some scenarios" |
| **Impact** | **Non-blocking** — publish continues successfully. Graph permissions are granted via a different path |
| **Resolution** | No action needed. The CLI handles the fallback gracefully |
| **Prevention** | None required |

---

### ISS-010: Blueprint endpoint already registered

| Field | Detail |
|-------|--------|
| **Stage** | `a365 setup blueprint` (re-run after partial completion) |
| **Symptom** | "Endpoint already exists" message when re-running blueprint setup |
| **Root Cause** | A previous (partial) run of `a365 setup blueprint` successfully registered the endpoint before failing at a later step |
| **Impact** | **Non-blocking** — the CLI handles this gracefully and skips the endpoint step |
| **Resolution** | No action needed. Run `a365 setup blueprint --endpoint-only` to verify endpoint state |
| **Prevention** | None needed — the CLI is idempotent for this step |

---

### ISS-011: `a365 publish` MOS token browser auth timeout

| Field | Detail |
|-------|--------|
| **Stage** | `a365 publish` (MOS token acquisition) |
| **Symptom** | CLI shows "A browser window will open for authentication..." and waits. If the browser window is missed, the auth times out |
| **Root Cause** | The publish step acquires a MOS (Microsoft Online Services) token via browser-based interactive auth. This is separate from WAM |
| **Impact** | Publish fails if auth is not completed |
| **Resolution** | Watch for the browser window and complete sign-in. Re-run `a365 publish` if it times out |
| **Prevention** | Ensure no popup blockers are active. Have the browser ready |

---

### ISS-012: No Agent 365 licence available for this agent

| Field | Detail |
|-------|--------|
| **Stage** | Blueprint activation / agent instance creation |
| **Symptom** | Error: "There's no Agent 365 licence available for this agent" when activating the blueprint in M365 admin center |
| **Root Cause** | The agentic user (`salesopsbot@M365CPI14187042.OnMicrosoft.com`) does not have a **Microsoft Agent 365 Frontier** license assigned. Agent users require licenses just like regular users |
| **Impact** | **Blocking** — cannot create agent instances without the license |
| **Resolution** | 1. **Check license availability**: M365 admin center → **Billing** → **Licenses** — verify "Microsoft Agent 365 Frontier" is listed and has available seats<br>2. **Assign the license**: M365 admin center → **Users** → find the agentic user → **Licenses and apps** → assign **Microsoft Agent 365 Frontier**<br>3. **Required licenses for full functionality**: Microsoft 365 E5 (or equivalent), Teams Enterprise, Microsoft 365 Copilot<br>4. **If no Frontier license exists**: Verify your Frontier preview enrollment at https://adoption.microsoft.com/copilot/frontier-program/ — license propagation may take time |
| **Actual Fix** | **Frontier enrollment alone does NOT provision the license.** Had to obtain a **trial license pack** for Microsoft Agent 365 and apply it to the Contoso tenant via M365 admin center → Billing → Purchase services. Once the trial licenses were active, the agent could be set up from the blueprint via the Agents store |
| **Prevention** | Before activating a blueprint, ensure Frontier trial/paid licenses are purchased and available in the tenant — Frontier preview enrollment is necessary but not sufficient |
| **Docs Reference** | [Create agent instances — License assignment fails](https://learn.microsoft.com/microsoft-agent-365/developer/create-instance#license-assignment-fails) |

> **Additional required step before instance creation**: Configure the agent in **Teams Developer Portal**:
> 1. Go to `https://dev.teams.microsoft.com/tools/agent-blueprint/<blueprint-id>/configuration`
> 2. Set **Agent Type** → **Bot Based**
> 3. Set **Bot ID** → your `agentBlueprintId`
> 4. Click **Save**
>
> Without this, the agent won't appear in Teams or receive messages.

---

### ISS-013: Agent not visible in GAL / cannot add to meetings

| Field | Detail |
|-------|--------|
| **Stage** | Post-activation — agent instance created |
| **Symptom** | Agent user not visible in Global Address List (GAL) or people picker. Cannot invite agent to meetings |
| **Root Cause** | **Multiple factors:**<br>1. **GAL propagation delay**: Exchange Online OAB takes up to 24 hours to include new mailboxes<br>2. **NO_TEAMS license**: Agent license `MICROSOFT_AGENT_FRONTIER_NO_TEAMS` excludes all Teams service plans — agent won't appear in Teams people picker<br>3. **Actual UPN differs from configured**: Config has `salesopsbot@...` but actual agentic user is `SalesOpSynthWorker984ebb@M365CPI14187042.onmicrosoft.com` |
| **Impact** | Users cannot find the agent via GAL search or add it to meeting invites |
| **Workaround** | Type the full email address directly in the meeting invite "To" field using **Outlook on the Web** (OWA searches Exchange directly, bypasses cached OAB):<br>`SalesOpSynthWorker984ebb@M365CPI14187042.onmicrosoft.com` |
| **Calendar Config Applied** | `Set-CalendarProcessing -DeleteSubject $false -DeleteComments $false -AddOrganizerToSubject $false -AllowConflicts $true` — preserves meeting context for transcript extraction |
| **Exchange Verification** | `Get-Mailbox` confirms: `HiddenFromAddressListsEnabled: False`, `RecipientType: UserMailbox`, `IsAgenticUser: True` — settings are correct, just needs propagation time |
| **Long-term Fix** | Wait 24h for full OAB propagation. After that, agent will be searchable by display name "Sales Op Synth Worker" in Outlook GAL. Teams limitation is by design |
| **Prevention** | After creating an agent instance, note the actual UPN/email (may differ from configured `agentUserPrincipalName`) and share it with users who need to invite the agent to meetings |

> **Exchange Online PowerShell diagnostic commands:**
> ```powershell
> # Check agentic user status
> Get-User -Identity "<UPN>" | Format-List IsAgenticUser, RecipientType
>
> # Check GAL visibility
> Get-Mailbox -Identity "<UPN>" | Format-List HiddenFromAddressListsEnabled, AddressBookPolicy
>
> # Check calendar processing
> Get-CalendarProcessing -Identity "<UPN>" | Format-List AutomateProcessing, DeleteSubject, DeleteComments
>
> # List all agentic users in tenant
> Get-User -ResultSize Unlimited | Where-Object { $_.IsAgenticUser -eq $true }
> ```

---

### ISS-014: Container App crash-loop — cascading startup failures

| Field | Detail |
|-------|--------|
| **Stage** | Post-deployment — Container App running but agent unreachable |
| **Symptom** | Bot endpoint (`https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/`) accepts TLS but HTTP requests time out. Agent added to a meeting invite but never accepts. Container revision shows `RunningState: Failed` with `startup probe failed: connection refused` in system logs |
| **Root Cause** | **Seven cascading issues** discovered during investigation (see table below) |
| **Impact** | Agent completely non-functional — cannot accept meetings, respond to messages, or process any requests |
| **Resolution** | Fixed all seven issues across code, Docker config, and Container App environment variables |
| **Commit** | `ad0718f` |

#### Sub-issues (resolved in order)

| # | Error | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | Wrong container image active | Initial revision `--ii04gk7` running `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest` (default sample app) instead of our ACR image. Listens on port 80 but ingress targetPort=8000 | Deactivated old revision, deployed correct ACR image |
| 2 | `ImportError: cannot import name 'AioHttpHost'` | Dockerfile CMD pointed to `src/main.py` which imports `AioHttpHost` — a class that **does not exist** in `microsoft-agents-hosting-aiohttp` v0.5.3. The correct entry point is `src/start_with_generic_host.py` which uses `CloudAdapter` + `start_agent_process` | Changed Dockerfile CMD: `python src/main.py` → `python src/start_with_generic_host.py` |
| 3 | `startup probe failed: connection refused` | `host_agent_server.py` bound to `localhost` (invisible from outside Docker container) on port 3978 (mismatched with ingress targetPort 8000). No root `/` endpoint for Container Apps health probes | Changed host to `0.0.0.0`, default port to `8000`, added `GET /` health endpoint |
| 4 | `ImportError: cannot import name 'ChatAgent' from 'agent_framework'` (our code) | `agent-framework-azure-ai` v1.0.0b260212 renamed `ChatAgent` → `Agent`. Our `agent.py` still used the old name | Changed `from agent_framework import ChatAgent` → `from agent_framework import Agent as FrameworkAgent`, fixed constructor param `chat_client=` → `client=` |
| 5 | `ImportError: cannot import name 'ChatAgent' from 'agent_framework'` (SDK) | `microsoft_agents_a365_tooling_extensions_agentframework` v0.1.0 internally imports `ChatAgent` from `agent_framework` — version incompatibility with agent-framework v1.0 | Added monkey-patch compatibility shim in `start_with_generic_host.py` before any other imports: `agent_framework.ChatAgent = agent_framework.Agent` |
| 6 | `ValueError: No service connection configuration provided` | `MsalConnectionManager` requires `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` environment variables parsed by `load_configuration_from_env()`. These were in the local `.env` file but **never configured on the Container App** | Set 8 environment variables on Container App: `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID`, `TENANTID`, `CLIENTSECRET` (as secret ref), `SCOPES`, plus `AGENTAPPLICATION__USERAUTHORIZATION__*` and `CONNECTIONSMAP__0__*` |
| 7 | `AttributeError: 'SalesOpsAgent' object has no attribute 'AGENT_PROMPT'` | Class attribute `AGENT_PROMPT` was a placeholder comment (`# ... existing prompt ...`) instead of an actual string | Added proper `AGENT_PROMPT` class attribute with system prompt text |

#### Diagnostic approach

```bash
# 1. Check revision status
az containerapp revision list -n <app> -g <rg> \
  --query "[?properties.active].{name:name, replicas:properties.replicas, runningState:properties.runningState}" \
  -o table

# 2. Get console logs (Python tracebacks)
az containerapp logs show -n <app> -g <rg> --type console \
  --revision <revision-name> --tail 50

# 3. Get system logs (probe failures, image pulls)
az containerapp logs show -n <app> -g <rg> --type system --tail 30

# 4. Test health endpoint
curl https://<endpoint>/
curl https://<endpoint>/api/health
```

#### Key files modified

| File | Changes |
|------|--------|
| `Dockerfile` | CMD `python src/main.py` → `python src/start_with_generic_host.py` |
| `src/start_with_generic_host.py` | Added `ChatAgent` compatibility shim before imports |
| `src/host_agent_server.py` | `localhost` → `0.0.0.0`, port `3978` → `8000`, added `GET /` health route |
| `src/agent.py` | `ChatAgent` → `Agent as FrameworkAgent`, `chat_client=` → `client=`, added `AGENT_PROMPT` |

#### Container App environment variables added

```
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=<app-registration-client-id>
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=<identity-tenant-id>
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET=secretref:service-connection-secret
CONNECTIONS__SERVICE_CONNECTION__SETTINGS__SCOPES=<blueprint-app-id>/.default
AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__AGENTIC__SETTINGS__TYPE=AgenticUserAuthorization
AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__AGENTIC__SETTINGS__ALT_BLUEPRINT_NAME=SERVICE_CONNECTION
AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__AGENTIC__SETTINGS__SCOPES=https://graph.microsoft.com/.default
CONNECTIONSMAP__0__SERVICEURL=*
CONNECTIONSMAP__0__CONNECTION=SERVICE_CONNECTION
```

#### Prevention

1. **Always test Docker image locally** before pushing: `docker run -p 8000:8000 --env-file .env <image>` — catches import errors immediately
2. **Use `--no-cache`** when rebuilding Docker images after code changes — Docker layer caching can silently serve stale code
3. **Mirror ALL `.env` variables** to Container App env vars — `load_configuration_from_env()` reads from `os.environ`, not from `.env` files
4. **Pin SDK versions** in `pyproject.toml` to avoid breaking changes from upstream renames (e.g., `agent-framework-azure-ai==1.0.0b260212`)
5. **Add a root health endpoint** (`GET /`) to any Container Apps deployment — the platform uses it for startup probes by default

---

### ISS-015: Azure OpenAI 401 — stale API key in Key Vault / Container App secret cache

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed and reachable, Teams channel routing messages successfully |
| **Symptom** | Messaging the agent in Teams returns: `Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource.` (HTTP 401 from Azure OpenAI) |
| **Root Cause** | Two-layer caching issue: (1) The API key stored in Key Vault (`azure-openai-api-key`) did not match the actual key on the `salesopsbot-openai` Azure OpenAI resource, and (2) Container Apps cache Key Vault secret values at revision creation time — restarting a revision does NOT re-fetch KV secrets |
| **Impact** | Agent responds in Teams but cannot generate any LLM-powered replies — every user message hits the 401 |
| **Resolution** | See steps below |

#### Diagnosis

```bash
# 1. Verify the Azure OpenAI resource exists and get its endpoint
az cognitiveservices account show -n salesopsbot-openai -g rg-salesopsbot \
  --query "{endpoint:properties.endpoint, sku:sku.name, state:properties.provisioningState}" -o table

# 2. Verify the deployment exists
az cognitiveservices account deployment list -n salesopsbot-openai -g rg-salesopsbot \
  --query "[].{name:name, model:properties.model.name, version:properties.model.version}" -o table

# 3. Get the actual API key from the resource
az cognitiveservices account keys list -n salesopsbot-openai -g rg-salesopsbot -o json

# 4. Test the key directly (PowerShell)
$key = (az cognitiveservices account keys list -n salesopsbot-openai -g rg-salesopsbot --query "key1" -o tsv).Trim()
$uri = "https://uksouth.api.cognitive.microsoft.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-12-01-preview"
$headers = @{"api-key"=$key; "Content-Type"="application/json"}
$body = '{"messages":[{"role":"user","content":"Say hello"}],"max_tokens":10}'
Invoke-RestMethod -Uri $uri -Method POST -Headers $headers -Body $body
# Expected: SUCCESS with a response. If this fails, the key or endpoint is wrong.

# 5. Check what the Container App is using
az containerapp show -n azcaxyseurue7b6nw -g rg-salesopsbot \
  --query "properties.template.containers[0].env[?name=='AZURE_OPENAI_API_KEY']" -o json

# 6. Check the secret source (KV ref vs plain)
az containerapp secret list -n azcaxyseurue7b6nw -g rg-salesopsbot -o json
```

#### Fix

```bash
# Option A: Update Key Vault secret (requires Key Vault Secrets Officer role)
# First grant yourself access if needed:
az role assignment create --role "Key Vault Secrets Officer" \
  --assignee "<your-oid>" \
  --scope "/subscriptions/<sub>/resourcegroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault>"

# Wait 30s for RBAC propagation, then update:
az keyvault secret set --vault-name <vault> --name azure-openai-api-key --value "<correct-key>"

# IMPORTANT: Restarting the revision is NOT enough — you must either:
# - Create a new revision (az containerapp update), OR
# - Switch to a plain-text secret (Option B)

# Option B: Replace KV reference with plain-text secret (faster, bypasses caching)
$key = (az cognitiveservices account keys list -n salesopsbot-openai -g rg-salesopsbot --query "key1" -o tsv).Trim()
az containerapp secret set -n azcaxyseurue7b6nw -g rg-salesopsbot --secrets "azure-openai-api-key=$key"

# Then restart the revision:
az containerapp revision restart -n azcaxyseurue7b6nw -g rg-salesopsbot \
  --revision <active-revision-name>

# Verify health after restart:
curl https://<endpoint>/
```

#### Key Insight: Container App Secret Caching

Container Apps resolve Key Vault secret references **at revision creation time**, not at runtime. This means:

- **Updating a KV secret** does not automatically propagate to running containers
- **Restarting a revision** reuses the same cached secret values
- **Creating a new revision** (`az containerapp update`) forces a re-fetch from Key Vault
- **Switching to a plain-text secret** (`az containerapp secret set --secrets "name=value"`) + restart is the fastest workaround

#### Environment Variables Verified

| Variable | Value | Status |
|----------|-------|--------|
| `AZURE_OPENAI_ENDPOINT` | `https://uksouth.api.cognitive.microsoft.com/` | Correct (regional Cognitive Services endpoint) |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Correct (deployment exists on resource) |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | Correct |
| `AZURE_OPENAI_API_KEY` | `secretref:azure-openai-api-key` | Was stale — updated to plain-text with correct key |

#### Prevention

1. **After creating an Azure OpenAI resource**, immediately copy the key to your Container App as a plain-text secret — don't rely on Key Vault indirection unless you have a rotation strategy that creates new revisions
2. **Test the API key independently** before deploying: use `Invoke-RestMethod` or `curl` to call the OpenAI endpoint directly
3. **If using Key Vault references**, always create a new revision after updating secrets — don't just restart
4. **Add a startup health check** in the agent code that validates the OpenAI key on boot (e.g., a lightweight `models.list()` call) and logs a clear error if it fails

---

### ISS-016: MCP tools not connecting / agent hallucinating data / calendar not accepting meetings

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed, Teams messaging working, OpenAI responding |
| **Symptom** | Three related failures: (1) Agent says "let me check my calendar" but fabricates meeting data (e.g. "2 PM Q4 sales strategy" that doesn't exist), (2) Container logs show `auth_token cannot be empty or None` on every message, (3) Meeting invitations are never accepted |
| **Root Cause** | Three cascading issues: (A) `AUTH_HANDLER_NAME` env var not set → `auth_handler_name` passed as `None` to MCP SDK, (B) `USE_AGENTIC_AUTH` not set → code takes non-agentic path requiring static `BEARER_TOKEN` which doesn't exist, (C) Calendar handler was 100% stubbed with `found_meetings = []` and no real Graph API calls |
| **Impact** | Agent acts as a plain chatbot with no tool access — hallucinates data rather than querying real sources. Meeting invitations pile up unaccepted. |
| **Resolution** | See steps below |

#### Sub-issue A: MCP auth_token empty

The `McpToolRegistrationService.add_tool_servers_to_agent()` requires either:
- **Agentic auth** (`auth` + `auth_handler_name` + `turn_context`) — the SDK handles token exchange
- **Static bearer token** (`auth_token` parameter) — for local development

The code had two paths controlled by `USE_AGENTIC_AUTH` env var. With neither env var set, it fell through to the static bearer path with an empty token.

**Fix:** Set `AUTH_HANDLER_NAME=AGENTIC` on the Container App and update the code to auto-detect: if `auth_handler_name` is set, use agentic auth; otherwise fall back to static token.

```bash
az containerapp update -n <app> -g <rg> --set-env-vars "AUTH_HANDLER_NAME=AGENTIC"
```

The env var `AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__AGENTIC__SETTINGS__*` must also be configured (these were already set from `a365` CLI setup).

#### Sub-issue B: Calendar handler stubbed

The `CalendarHandler.check_calendar()` method had:
```python
found_meetings = []  # Mock Data
```

No real Graph API calls were being made. The handler polled every 5 minutes but always found nothing.

**Fix:** Implemented real Graph API calls in `GraphTranscriptClient`:
- `get_calendar_view(start, end)` — queries `/users/{userId}/calendarView`
- `get_pending_invitations()` — fetches events with `responseStatus == notResponded`
- `accept_event(event_id)` — POSTs to `/users/{userId}/events/{id}/accept`

#### Sub-issue C: Invalid client secret for app 8e5206be

Once real Graph calls were enabled, they failed with `AADSTS7000215: Invalid client secret`.

**Fix:** Created a new client secret:
```bash
az account set --subscription <contoso-tenant-id>
az ad app credential reset --id 8e5206be-... --append --display-name "CalendarFix" --years 1
az account set --subscription <hosking-sub-id>
az containerapp secret set -n <app> -g <rg> --secrets "azure-client-secret=<new-secret>"
```

#### Sub-issue D: Graph 400 Bad Request on /me endpoint

Client credentials flow (used by `DefaultAzureCredential` with `AZURE_CLIENT_ID/SECRET`) has no user context, so `/me` endpoints return 400.

**Fix:** Changed all Graph API calls from `/me/...` to `/users/{AGENT_USER_ID}/...` where `AGENT_USER_ID = ec35260f-ceb9-40b1-9e8b-afafe29187cf`.

#### Sub-issue E: Missing application permissions

The app registration had only delegated (Scope) permissions. Client credentials require application (Role) permissions.

**Fix:** Added `Calendars.ReadWrite` application permission and granted admin consent:
```bash
az ad app permission add --id 8e5206be-... \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions ef54d2bf-783f-4e0f-bca1-3210c0444d99=Role
az ad app permission admin-consent --id 8e5206be-...
```

#### Sub-issue F: Agent hallucinating data

Without MCP tools, the agent's LLM generated plausible-sounding but fabricated data when asked about calendar/meetings.

**Fix:** Added anti-hallucination guard to `AGENT_PROMPT`:
```
CRITICAL RULES:
- NEVER fabricate, hallucinate, or invent data
- Do NOT make up meeting times, subjects, attendees
- If tools are not available, say so honestly
- Always prefer using a tool over generating a plausible answer
```

#### Verification

After deploying revision `--0000013` with image `fix-mcp-auth-v2`:

```
# Calendar polling working:
calendarView ... "HTTP/1.1 200 OK"
returned 0 event(s) for 2026-02-14T13:17:58Z..2026-02-14T13:32:58Z

# Auto-accept working:
Auto-accepting meeting invitation: Zava Customer Meeting
POST .../accept "HTTP/1.1 202 Accepted"
Auto-accepting meeting invitation: Hosking Ltd Discussion
POST .../accept "HTTP/1.1 202 Accepted"
Auto-accepting meeting invitation: Zava Client meeting - Solutions
POST .../accept "HTTP/1.1 202 Accepted"
```

#### Files Changed

| File | Change |
|------|--------|
| `src/agent.py` | Updated `setup_mcp_servers()` to auto-detect agentic auth from `auth_handler_name`; added anti-hallucination CRITICAL RULES to `AGENT_PROMPT` |
| `src/handlers/calendar_handler.py` | Replaced stub with real Graph API calls; added `_accept_pending_invitations()` |
| `src/integrations/graph_transcript_client.py` | Added `get_calendar_view()`, `get_pending_invitations()`, `accept_event()` methods; changed `/me` to `/users/{userId}`; added token expiry refresh |

---

## 5. Split-Tenant Deployment Playbook

Follow this step-by-step guide when deploying with a split-tenant configuration.

### Phase A: Infrastructure Deployment (HOSKING tenant)

```powershell
# 1. Login to infrastructure tenant
az login --tenant <INFRASTRUCTURE_TENANT_ID>

# 2. Deploy infrastructure with AZD
azd init
azd up

# 3. Note the endpoint URL
# Example: https://<app-name>.<region>.azurecontainerapps.io/
```

### Phase B: Identity & Agent Registration (Contoso tenant)

```powershell
# 1. Switch to identity tenant (allow no subscriptions!)
az login --tenant <IDENTITY_TENANT_ID> --allow-no-subscriptions

# 2. Verify login (ignore stderr warnings — see ISS-001)
az account show

# 3. Pre-register the Contoso account with WAM (see ISS-004)
# Windows Settings → Accounts → Access work or school → Connect

# 4. Create a365.config.json MANUALLY (avoid interactive wizard)
# Set subscriptionId = tenantId as workaround (see ISS-003)
# Set needDeployment = false
# Set messagingEndpoint to the URL from Phase A (with /api/messages)
```

**Recommended `a365.config.json` template for split-tenant:**
```json
{
  "tenantId": "<IDENTITY_TENANT_ID>",
  "subscriptionId": "<IDENTITY_TENANT_ID>",
  "resourceGroup": "rg-<agent-name>",
  "location": "uksouth",
  "environment": "prod",
  "messagingEndpoint": "https://<your-endpoint>/api/messages",
  "needDeployment": false,
  "clientAppId": "<CUSTOM_CLIENT_APP_ID>",
  "agentIdentityDisplayName": "<Agent Name>",
  "agentBlueprintDisplayName": "<Agent Name> Blueprint",
  "agentUserPrincipalName": "<agent>@<domain>.OnMicrosoft.com",
  "agentUserDisplayName": "<Agent Name>",
  "managerEmail": "<admin>@<domain>.OnMicrosoft.com",
  "agentUserUsageLocation": "GB",
  "deploymentProjectPath": "."
}
```

```powershell
# 5. Import config
a365 config init -c ./a365.config.json

# 6. Run setup (watch for WAM popups! — see ISS-005)
a365 setup requirements
a365 setup blueprint --verbose
a365 setup permissions mcp --verbose
a365 setup permissions bot --verbose

# 7. Publish (watch for browser auth window — see ISS-011)
a365 publish --verbose
```

### Phase C: Post-Publish

```powershell
# 1. Verify publish success
a365 config display -g

# 2. Update Container App env vars with the new Agent 365 settings
# The .env file was auto-updated by the CLI with:
#   AGENT_ID, SERVICE_CONNECTION settings, auth handler settings
# Push these to the Container App if needed:
az containerapp update --name <app-name> --resource-group <rg-name> \
  --set-env-vars "AGENT_ID=<blueprint-id>" ...

# 3. Create agent instance
# Go to Microsoft 365 admin center → Agents → create instance
# Or: Teams Developer Portal → Agent Blueprint → configure Bot ID
# Note: current CLI preview does not provide create-instance command.

# 4. Approve agent
# Microsoft 365 admin center: https://admin.cloud.microsoft/?#/agents/all/requested
```

---

## 6. a365 CLI Command Reference (Quick)

| Command | What It Does |
|---------|--------------|
| `a365 --version` | Check CLI version |
| `a365 config init` | Initialize config (wizard or import depending on flags/context) |
| `a365 config init -c ./file.json` | Import config from file |
| `a365 config display` | Show static config |
| `a365 config display -g` | Show generated config (after setup) |
| `a365 setup requirements` | Validate prerequisites |
| `a365 setup all` | Run all setup steps (infrastructure + blueprint + permissions) |
| `a365 setup blueprint` | Create agent blueprint only |
| `a365 setup blueprint --verbose` | Blueprint with debug output |
| `a365 setup blueprint --endpoint-only` | Register/verify endpoint only |
| `a365 setup permissions mcp` | Configure MCP permissions |
| `a365 setup permissions bot` | Configure Bot/Observability/PowerPlatform permissions |
| `a365 deploy` | Build and deploy to Azure |
| `a365 publish` | Publish to M365 admin center |
| `a365 publish --verbose` | Publish with debug output |
| `a365 publish --dry-run` | Preview publish without uploading |
| `a365 publish --skip-graph` | Skip Graph federated identity and role assignments |
| `a365 cleanup` | ⚠️ **Delete all Agent 365 resources** (destructive) |

> `a365 create-instance` is removed in current preview CLI releases; create instances through Microsoft 365 admin center / Teams flows.

**Update CLI:**
```powershell
dotnet tool update --global Microsoft.Agents.A365.DevTools.Cli --prerelease
```

---

## 7. Diagnostic Commands

### Check Environment State

```powershell
# CLI version
a365 --version

# Current Azure identity
az account show --output table

# Device join status (WAM context)
dsregcmd /status

# Check configs exist
Test-Path a365.config.json
Test-Path a365.generated.config.json

# Display configs
a365 config display
a365 config display -g

# Check .NET
dotnet --version

# Check PowerShell 7
pwsh --version

# Check Graph module
pwsh -Command "Get-Module -ListAvailable Microsoft.Graph.Applications"
```

### Check Azure Resources

```powershell
# List resources in group
az resource list --resource-group <rg-name> --output table

# Check Container App status
az containerapp show --name <app-name> --resource-group <rg-name> --query "properties.runningStatus"

# Check app registration
az ad app show --id <blueprint-app-id> --query "{name:displayName, id:appId}"

# Check service principal
az ad sp show --id <blueprint-app-id> --query "{name:displayName, id:id}"

# Check app permissions
az ad app show --id <client-app-id> --query "requiredResourceAccess"
```

### Check Logs

```powershell
# a365 CLI log files location
Get-ChildItem "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\logs\"

# Read setup log
Get-Content "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\logs\a365.setup.log" -Tail 50

# Read publish log
Get-Content "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\logs\a365.publish.log" -Tail 50

# Check WAM token cache
Test-Path "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\auth-token.json"
```

### Verify Publish Success

```powershell
# Check manifest files exist
Test-Path manifest/manifest.json
Test-Path manifest/manifest.zip
Test-Path manifest/agenticUserTemplateManifest.json

# Check for titleId in publish log
Select-String "titleId" "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\logs\a365.publish.log"

# Check for success message
Select-String "Publish completed successfully" "$env:LOCALAPPDATA\Microsoft.Agents.A365.DevTools.Cli\logs\a365.publish.log"
```

---

## 8. Lessons Learned

### Always Use `--verbose`

The a365 CLI often exits with code 1 and no output on failure. Always run with `--verbose` and redirect stderr:
```powershell
a365 setup blueprint --verbose 2>&1
```

### Never Trust Exit Codes in PowerShell

Several Azure CLI and a365 CLI commands output warnings to stderr that PowerShell interprets as errors. Always verify command success independently (e.g., `az account show`, `a365 config display -g`).

### Pre-Register WAM Accounts

If your device is Azure AD Joined to one tenant but you need to authenticate to another, register the second tenant's account with WAM **before** starting the a365 CLI workflow. This avoids ISS-004 entirely.

### Keep Browser Visible

The a365 CLI uses both WAM popups AND browser-based auth at different stages. Keep your browser and taskbar visible throughout the entire setup/publish process.

### Blueprint Is Idempotent

If `a365 setup blueprint` partially fails, you can safely re-run it. The CLI detects existing blueprints, endpoints, and secrets and skips completed steps.

### Config Files Are Sacred

Back up these files after successful setup:
- `a365.config.json` — Your static configuration
- `a365.generated.config.json` — Contains blueprint IDs, client secret, state
- `.env` — Auto-updated by CLI with runtime settings
- `manifest/manifest.json` — Published manifest

### The CLI Auto-Discovers Missing MOS Prerequisites

During `a365 publish`, the CLI automatically creates service principals and grants admin consent for MOS (Microsoft Online Services) resources like Auth Config, Environments, and Titles APIs. You don't need to set these up manually.

### Manifest Customization Window

During `a365 publish`, the CLI pauses and opens your editor to customise the manifest. Key fields to update:
- `name.short` (max 30 chars) and `name.full`
- `description.short` and `description.full`
- `developer.name`, `developer.websiteUrl`, `developer.privacyUrl`
- `version` — **must be incremented for re-publishing**
- Icons: `color.png` (192×192) and `outline.png` (32×32)

### Post-Publish: Container App Env Vars

The `.env` file is updated by the CLI with `AGENT_ID`, `SERVICE_CONNECTION` settings, etc. These must be pushed to your Container App (or other hosting) for the agent runtime to use the new identity. This is a manual step with split-tenant or non-Azure hosting.

### MCP Servers: Add One at a Time

When extending the ToolingManifest.json with new MCP servers, **add them one at a time** and verify the agent still responds after each addition. A single failing MCP server can cascade and take down all MCP connections (see ISS-024). Never add multiple untested servers in a single deployment.

### TPM Quota: Size for Tool Count

Agents with many tools (>10) generate large prompts that include tool descriptions. Each tool adds ~100-300 tokens to every prompt. With 35 tools, prompts easily hit 3-5K tokens before the user's message. Allocate at least **30-50K TPM** for tool-heavy agents.

### LLM Output: Always Add None-Safety

When templating LLM-generated JSON output into strings (emails, HTML, Adaptive Cards), always add `or ""` fallback on every field. LLMs frequently return `null` for optional fields, and `str.replace()` on `None` crashes.

### Pipeline: Dual Delivery Strategy

For critical delivery paths (email, Teams), implement multiple strategies with graceful fallback. The meeting processor tries Graph API direct email first, then falls back to MCP Mail via LLM. Both paths return `False` on failure without crashing. This ensures the pipeline completes even when permissions are missing.

### Build Tags: Use Descriptive Image Names

Use meaningful image tags that indicate the change (e.g., `pipeline-v4`, `fix-hallucination-v1`) rather than generic tags. This makes revision history and rollback decisions much clearer. The `--no-logs` flag on `az acr build` avoids codec errors from emoji in source files.

---

### ISS-017: Agent "typing then stops" — auth_handlers consent gate + MCP token exchange

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed with ISS-016 fixes, Container App revision --0000013 |
| **Symptom** | When chatting to the agent in Teams, the typing indicator appears briefly then stops. No response is ever sent. Container App logs show no handler code executing. |
| **Root Cause** | Two cascading issues: (A) The `auth_handlers=["AGENTIC"]` decorator on the message handler causes the SDK middleware to perform an SSO token exchange (`https://graph.microsoft.com/.default`) **before** the handler code runs. The agent app instance (`5653b53b`) lacked OAuth2 delegated-permission consent, causing `AADSTS65001: consent_required` — the SDK silently skipped the handler. (B) Even after granting consent and temporarily removing `auth_handlers` (revision --0000014) so the handler fired, MCP tools failed with `auth_token cannot be empty or None` because no SSO token was available in the turn state for the OBO exchange to `ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/.default` (Agent 365 Tools). |
| **Impact** | Agent completely unresponsive to users in Teams. When worked around (no auth_handlers), agent responded via LLM-only but had no access to MCP tools (Teams, Calendar, Mail, SharePoint, etc.). |
| **Resolution** | See steps below |

#### Fix steps

1. **Grant OAuth2 delegated-permission consent** for the agent app instance (`5653b53b-bdd6-42cf-9a8e-5c16f495d44a`) in the Contoso tenant:

```bash
# Grant consent for Microsoft Graph, Authorization, Impersonation, MCP Servers, Connectivity
az rest --method POST --url "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" \
  --headers "x-ms-client-tenant-id=<IDENTITY_TENANT_ID>" \
  --body '{"clientId":"<AGENT_APP_INSTANCE_ID>","consentType":"AllPrincipals","resourceId":"<GRAPH_SP_ID>","scope":"openid profile User.Read Calendars.ReadWrite Mail.Send"}'
```

2. **Restore `auth_handlers`** on all message/notification handlers in `host_agent_server.py`:
```python
# All handlers use the same auth config so the SDK extracts the SSO token
# into the turn state (needed for MCP token exchange).
handler_config = {"auth_handlers": [self.auth_handler_name]} if self.auth_handler_name else {}

@self.agent_app.activity("message", **handler_config)
async def on_message(context: TurnContext, _: TurnState):
    ...
```

3. **Add MCP token pre-exchange** in `agent.py` `setup_mcp_servers()` for observability:
```python
from microsoft_agents_a365.tooling.utils.utility import get_mcp_platform_authentication_scope
mcp_scopes = get_mcp_platform_authentication_scope()
token_result = await auth.exchange_token(context, mcp_scopes, auth_handler_name)
if token_result and token_result.token:
    mcp_token = token_result.token
    logger.info(f"MCP setup: token exchange succeeded (token length={len(mcp_token)})")
else:
    logger.warning(f"MCP setup: token exchange returned empty token")
```

4. **Build and deploy** the updated image:
```bash
az acr build --registry <ACR_NAME> --image sales-ops-bot:fix-mcp-auth-v3 --no-logs --file Dockerfile .
az containerapp update --name <APP_NAME> --resource-group <RG_NAME> --image <ACR>.azurecr.io/sales-ops-bot:fix-mcp-auth-v3
```

#### Key findings

- The agent app instance ID (`5653b53b`) is **not** a standard Azure AD service principal — it's an internal Agent 365 platform entity and cannot be found via `az ad sp show` or Graph API `servicePrincipals` endpoints. Despite this, OAuth2 permission grants can be created referencing it as `clientId`.
- The SDK uses **three different scopes** for different purposes:
  - Pre-auth middleware: `https://graph.microsoft.com/.default` (from `AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__AGENTIC__SETTINGS__SCOPES`)
  - MCP Platform: `ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/.default` (Agent 365 Tools)
  - Observability: `https://api.powerplatform.com/.default`
- Without `auth_handlers`, the SDK never performs the pre-auth exchange, so no SSO token is in the turn state. The MCP token exchange (`ea9ffc3e/.default`) requires this SSO token for OBO flow.
- The `--no-logs` flag on `az acr build` avoids `'charmap' codec can't encode characters` errors caused by emoji in Python source files.

#### Verification

```
MCP setup: using agentic auth (handler=AGENTIC)
MCP setup: exchanging token for scopes=['ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/.default']
MCP setup: token exchange succeeded (token length=2322)
Final result: Loaded 12 MCP server configurations
MCP plugin 'mcp_TeamsServer' to agent tools
MCP plugin 'mcp_OutlookMail' to agent tools
MCP plugin 'mcp_CalendarTools' to agent tools
...
MCP plugin 'mcp_PlannerServer' to agent tools
```

| Commit | `bd09ba5` |
|--------|-----------|
| Image | `sales-ops-bot:fix-mcp-auth-v3` (digest `81f3d3c3`) |
| Revision | `azcaxyseurue7b6nw--0000015` |

---

### ISS-018: MCP headers silently dropped — 400 Bad Request from MCP platform

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed with ISS-017 fixes, Container App revision --0000016 |
| **Symptom** | MCP tool calls to `agent365.svc.cloud.microsoft` all returned 400 Bad Request. Token exchange succeeded (token length=2320) but the MCP platform rejected every request. |
| **Root Cause** | The SDK's `MCPStreamableHTTPTool` constructor accepts `headers=headers` in `**kwargs` but **silently discards** them. The underlying `streamable_http_client()` context manager only accepts `url`, `http_client`, and `terminate_on_close` — there is no `headers` parameter. The Bearer auth token was therefore **never reaching** the MCP servers. |
| **Impact** | All 12 MCP tools completely non-functional. Agent appeared to have tools registered but every MCP call failed with 400. |
| **Resolution** | Extended `scripts/patch_sdk.py` with Fix #3 to replace `headers=headers` with `http_client=httpx.AsyncClient(headers=headers)` in the SDK's `MCPStreamableHTTPTool` class. This passes the Bearer token via an `httpx.AsyncClient` instance which `streamable_http_client()` does accept. |

#### SDK Bug Detail

```python
# BEFORE (SDK source — headers silently dropped)
class MCPStreamableHTTPTool:
    def __init__(self, url, tool, headers=None, **kwargs):
        self.url = url
        self.tool = tool
        # headers captured in kwargs but NEVER passed to streamable_http_client()

    async def run(self, ...):
        async with streamable_http_client(url=self.url) as (read, write, _):
            # ^^^ No headers parameter — auth token lost!
```

```python
# AFTER (patched via scripts/patch_sdk.py)
# Fix #3: Replace headers=headers with http_client=httpx.AsyncClient(headers=headers)
# This passes the Bearer token through to the MCP transport layer
```

#### Fix applied in `scripts/patch_sdk.py`

```python
# Fix 3: MCP headers silently dropped — use httpx.AsyncClient instead
{
    "old": "headers=headers,",
    "new": "http_client=httpx.AsyncClient(headers=headers) if headers else None,"
},
# Also adds: import httpx
```

#### Verification

After deploying revision --0000017 with `fix-mcp-headers-v1`:
- Error changed from **400 Bad Request** → **403 Forbidden**
- This confirmed the Bearer token was now reaching the MCP platform (headers fix worked)
- The 403 indicated the platform received the token but rejected the request (separate auth issue)

| Image | `salesopsbot:fix-mcp-headers-v1` (digest `5b5e1d34`) |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000017` |

---

### ISS-019: Agent hallucinating meetings — MCP gateway returns 0 servers

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed with ISS-018 fix + `ENVIRONMENT=Production`, revision --0000018 |
| **Symptom** | User asked "what meeting did you have today" and the agent fabricated meetings: "Sales Strategy Meeting 10:00 AM", "Client Check-In 2:00 PM", "End-of-Day Wrap-Up 4:30 PM". These meetings did not exist. Three real meetings (including "Hosking Ltd Discussion") were on the calendar but the agent didn't see them. |
| **Root Cause** | Multi-layer failure: (A) Setting `ENVIRONMENT=Production` switched the SDK from reading local `ToolingManifest.json` to querying the MCP gateway API at `https://agent365.svc.cloud.microsoft/agents/{id}/mcpServers`. (B) The gateway returned **0 MCP servers** for the agent app instance `5653b53b-bdd6-42cf-9a8e-5c16f495d44a`. (C) With 0 servers, the agent was created with **0 tools**. (D) With 0 tools, the LLM had no way to query real data and fabricated plausible-sounding meeting information. |
| **Impact** | Agent provided completely false information to users, which is worse than no response at all. The Graph API calendar polling still worked perfectly (background process) but the agent's conversational path had no access to this data. |
| **Resolution** | See steps below |

#### Root cause: MCP gateway returns 0 servers

At that time, the MCP tooling gateway at `https://agent365.svc.cloud.microsoft/agents/5653b53b-bdd6-42cf-9a8e-5c16f495d44a/mcpServers` returned an empty list while the then-active manifest declared 12 MCP servers. The `a365 publish` log contained **no references** to ToolingManifest.json or MCP server registration, suggesting the publish step did not register MCP server bindings with the platform in that run.

```
# Container App logs (revision --0000018):
Listing MCP tool servers for agent 5653b53b-bdd6-42cf-9a8e-5c16f495d44a
Calling tooling gateway endpoint: https://agent365.svc.cloud.microsoft/agents/5653b53b-.../mcpServers
Retrieved 0 MCP tool servers from tooling gateway
Loaded 0 MCP server configurations
Agent created with 0 total tools
```

#### Fix: Local FunctionTool instances

Bypassed the broken MCP gateway by registering Graph API calendar operations as local `FunctionTool` instances. These are always available regardless of MCP gateway status.

**Added to `src/agent.py`:**

1. **`_build_local_tools()`** method — creates 3 async wrapper functions around `self.graph_client.get_calendar_view()`:

| Tool Name | Description |
|-----------|-------------|
| `get_my_calendar_today` | Queries Graph API for all meetings today (00:00–24:00 UTC) |
| `get_my_calendar_range` | Queries meetings for a custom date range (start_date, end_date in YYYY-MM-DD format) |
| `get_upcoming_meetings` | Queries meetings in the next 24 hours from now |

2. **`_create_agent()`** updated — passes `tools=list(self._local_tools)` instead of `tools=[]`

3. **`setup_mcp_servers()`** updated — passes `initial_tools=list(self._local_tools)` instead of `initial_tools=[]` to `add_tool_servers_to_agent()`, so MCP tools get **added** to these local tools (rather than replacing them)

#### Key design decisions

- **`FunctionTool` registration**: Uses `FunctionTool(func=..., name=..., description=...)` from `agent_framework`. The `func` must be an async callable returning a string (JSON).
- **Closures over `self`**: The wrapper functions are closures created in `_build_local_tools()` that capture `self.graph_client`, avoiding the need for global state.
- **Error handling**: Each tool wraps its Graph API call in try/except and returns `{"error": str(ex)}` on failure, so the LLM can report issues instead of hallucinating.
- **`initial_tools` semantics**: The `add_tool_servers_to_agent()` method creates a new `Agent` with `tools=initial_tools + mcp_tools`. By passing local tools as `initial_tools`, they persist even when MCP returns 0 servers.

#### Verification

```
# Container App logs (revision --0000019):
Built 3 local Graph API tools
AgentFramework agent created with 3 local tools
# Calendar poll still works:
Pipeline Triggered: calendar_poll [ended] for 'Hosking Ltd Discussion'
```

#### Files changed

| File | Change |
|------|--------|
| `src/agent.py` | Added `FunctionTool` import; added `_build_local_tools()` method (3 calendar tools); updated `_create_agent()` and `setup_mcp_servers()` to pass local tools as `initial_tools` |

| Image | `salesopsbot:fix-hallucination-v1` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000019` |

#### Outstanding: MCP gateway registration

The MCP gateway still returns 0 servers. This means the agent has only the 3 local calendar tools, not the full 12 MCP tools (Teams, Mail, SharePoint, Planner, etc.). Possible causes:
- `a365 publish` does not register MCP server bindings (ToolingManifest.json may be for local dev only)
- The agent app instance ID may not be recognized by the MCP platform
- A separate `a365 setup permissions mcp` re-run may be needed after agent instance creation

This was resolved by switching to `ENVIRONMENT=Development` which uses local `ToolingManifest.json` instead of the gateway. The manifest was trimmed to 4 proven servers (see ISS-021).

---

### ISS-020: 429 Too Many Requests — agent "not responding"

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed with 35 tools (4 MCP servers + 3 local), revision --0000032 |
| **Symptom** | Agent shows typing indicator in Teams but never responds. Container logs show `HTTP/1.1 429 Too Many Requests` from Azure OpenAI endpoint |
| **Root Cause** | Azure OpenAI deployment `gpt-4o` on `salesopsbot-openai` had a quota of only **10K TPM** (tokens per minute). With 35 tools, each prompt includes tool descriptions that consume ~3-5K tokens. A few rapid messages easily exceeded the limit |
| **Impact** | Agent completely unresponsive during rate-limited periods. No error shown to user in Teams |
| **Resolution** | Increased TPM quota to **50K** on the `gpt-4o` deployment via Azure Portal → Azure OpenAI → Deployments → Edit → Tokens per minute |
| **Prevention** | For agents with many tools (>10), allocate at least 30-50K TPM. Monitor token usage via Azure Monitor metrics |

#### Additional fixes applied

| Fix | Detail |
|-----|--------|
| `max_iterations=10` | Added to `_create_chat_client()` to prevent runaway LLM loops |
| 300s timeout | Wrapped agent invocation in `asyncio.wait_for(timeout=300)` |
| Greeting detection | Simple "hi"/"hello" messages bypass full agent/tool pipeline to save tokens |

#### Diagnostic commands

```bash
# Check current TPM allocation
az cognitiveservices account deployment show \
  --name salesopsbot-openai --resource-group rg-salesopsbot \
  --deployment-name gpt-4o \
  --query "properties.rateLimits"

# Check for 429s in container logs
az containerapp logs show --name <app> --resource-group <rg> --type console --tail 100 \
  | Select-String "429"
```

---

### ISS-021: ToolingManifest trimmed — 12 servers to 4 proven servers

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — agent deployed with `ENVIRONMENT=Development` |
| **Symptom** | Some MCP servers returned errors or were unavailable. Tool count inconsistent between deployments |
| **Root Cause** | Original 12-server manifest included: (A) custom/internal servers with no platform registration, (B) servers not in the catalog, (C) servers returning runtime errors |
| **Impact** | Failed MCP connections consumed time and masked working servers |
| **Resolution** | Trimmed ToolingManifest.json to **4 proven servers**: `mcp_WordServer`, `mcp_SharePointListsTools`, `mcp_KnowledgeTools`, `mcp_PlannerServer` |
| **Prevention** | Verify servers exist in catalog (`a365 develop list-mcp-servers`). Add one at a time and verify tool count |

#### Working ToolingManifest.json

```json
{
  "mcpServers": [
    { "mcpServerName": "mcp_WordServer", "scope": "McpServers.Word.All", "audience": "ea9ffc3e-..." },
    { "mcpServerName": "mcp_SharePointListsTools", "scope": "McpServers.SharepointLists.All", "audience": "ea9ffc3e-..." },
    { "mcpServerName": "mcp_KnowledgeTools", "scope": "McpServers.Knowledge.All", "audience": "ea9ffc3e-..." },
    { "mcpServerName": "mcp_PlannerServer", "scope": "McpServers.Planner.All", "audience": "ea9ffc3e-..." }
  ]
}
```

---

### ISS-022: None crash in report_generator — LLM returning null fields

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — pipeline processing a meeting transcript |
| **Symptom** | `TypeError: argument of type 'NoneType' is not iterable` or `AttributeError: 'NoneType' object has no attribute 'replace'` in `report_generator.py` |
| **Root Cause** | LLM returned JSON with `null` values for optional fields. `generate_email_html()` and `generate_adaptive_card()` called `str.replace()` on null values |
| **Impact** | Pipeline crashed after successful LLM analysis. Reports not generated |
| **Resolution** | Added `or ""` fallback on all template substitution values |
| **Prevention** | Always add None-safety when templating LLM-generated data |
| **Image** | `salesopsbot:pipeline-v2` |
| **Revision** | `azcaxyseurue7b6nw--0000034` |

---

### ISS-023: Pipeline email/Teams delivery 403 — missing application permissions

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — pipeline completed LLM analysis and report generation |
| **Symptom** | `POST /users/{id}/sendMail` returns 403; `GET /users/{id}/onlineMeetings` returns 403 |
| **Root Cause** | App `8e5206be` has `Calendars.ReadWrite` (Application) but lacks `Mail.Send` and `OnlineMeetings.Read.All` application permissions. Pipeline uses client credentials flow |
| **Impact** | Pipeline generates reports and MS Learn enrichment but cannot deliver via email or Teams chat |
| **Status** | **OPEN** — requires admin action in Entra admin center |

#### Required permissions

```bash
# Must run while logged into Contoso tenant
az login --tenant c2833f41-c31d-4c2f-98d1-947fdb699aba --allow-no-subscriptions

# Mail.Send (Application)
az ad app permission add --id 8e5206be-48e3-4da4-b741-d3908cf7c30a \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions b633e1c5-b582-4048-a93e-9f11b44c7e96=Role

# OnlineMeetings.Read.All (Application)
az ad app permission add --id 8e5206be-48e3-4da4-b741-d3908cf7c30a \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions c1684f21-c984-44c0-a8c4-3e15a5f26f3e=Role

# Chat.ReadWrite.All (Application)
az ad app permission add --id 8e5206be-48e3-4da4-b741-d3908cf7c30a \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions 294ce7c9-31ba-490a-ad7d-97a7d075e4ed=Role

# Grant admin consent
az ad app permission admin-consent --id 8e5206be-48e3-4da4-b741-d3908cf7c30a
```

#### Pipeline graceful failure design

The pipeline handles 403s without crashing:
- `meeting_processor.py` tries Graph API email first → MCP Mail fallback → both return `False` on failure
- `teams_chat_service.py` wraps all Graph calls in try/except
- Pipeline continues to generate reports and MS Learn enrichment regardless

---

### ISS-024: mcp_MailServer 403 cascade — agent stops responding

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — `mcp_MailServer` added to ToolingManifest.json (revision --0000035, image pipeline-v3) |
| **Symptom** | Agent completely stops responding. No typing indicator, no response. Container logs show cascading SSL timeout errors |
| **Root Cause** | `mcp_MailServer` returned **403 Forbidden** from `agent365.svc.cloud.microsoft/agents/servers/mcp_MailServer`. This triggered SSL shutdown timeout cascades (`ClientConnectionError('Connection lost: SSL shutdown timed out')`) that killed all MCP connections |
| **Impact** | **Complete agent failure**. Tool count dropped from ~35 to 5 (only server names, no individual tools). All user messages unanswered |
| **Resolution** | Removed `mcp_MailServer` from ToolingManifest.json (5 → 4 servers). Deployed `pipeline-v4` (revision --0000036). Agent immediately recovered |
| **Prevention** | Never add an MCP server without testing independently. A single failing server can cascade and kill all MCP connections |

#### Key insight: cascading MCP failure

MCP **server connection** failures during SDK initialization (`add_tool_servers_to_agent()`) cascade — unlike individual tool call failures which are isolated. The SDK uses shared connection pools or sequential initialization. If one server hangs on SSL shutdown, it blocks/corrupts all subsequent connections. This is a design weakness in the `microsoft-agents-a365` SDK.

#### Diagnosis

```bash
# Check for 403/SSL errors
az containerapp logs show --name <app> --resource-group <rg> --type console --tail 100 \
  | Select-String "403|SSL|ClientConnectionError"

# Check tool count (healthy = ~35, broken = 5)
az containerapp logs show --name <app> --resource-group <rg> --type console --tail 100 \
  | Select-String "running agent with"
```

| Image | `salesopsbot:pipeline-v4` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000036` |

---

### ISS-025: mcp_CalendarServer 403 cascade — same pattern as MailServer

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — `mcp_CalendarServer` added to ToolingManifest.json (revision --0000039, image pipeline-v7) |
| **Symptom** | Agent receives message, starts processing, but hits 403 on every `agent.run()` call. Repeated retries with SSL timeout cascade. Same pattern as ISS-024 |
| **Root Cause** | `mcp_CalendarServer` returned **403 Forbidden** from `agent365.svc.cloud.microsoft/agents/servers/mcp_CalendarServer`. Despite `McpServers.Calendar.All` being consented in the app registration, the MCP gateway rejects the request |
| **Impact** | Agent retries the same message 3+ times, each hitting 403 → SSL shutdown timeout → `ClientConnectionError('Connection lost: SSL shutdown timed out')`. Agent effectively unresponsive |
| **Resolution** | Removed `mcp_CalendarServer` from ToolingManifest.json (7 → 6 servers). Calendar access handled by 4 local FunctionTools (`get_my_calendar_today`, `get_my_calendar_range`, `get_upcoming_meetings`, `run_meeting_report`). Deployed pipeline-v7b (revision --0000040) |
| **Prevention** | Same as ISS-024: never add an MCP server without verifying it passes a basic GET. 403 from the MCP gateway causes cascading SSL failures |

#### Key log evidence

```
{"Log": "running agent with 7 tools: ['mcp_WordServer', 'mcp_SharePointListsTools', 'mcp_KnowledgeTools', 'mcp_PlannerServer', 'mcp_TeamsServer', 'mcp_CalendarServer', 'mcp_OneDriveSharepointServer']"}
{"Log": "Request: POST https://agent365.svc.cloud.microsoft/agents/servers/mcp_CalendarServer \"HTTP/1.1 403 Forbidden\""}
{"Log": "<Future finished exception=ClientConnectionError('Connection lost: SSL shutdown timed out')>"}
```

| Image | `salesopsbot:pipeline-v7b` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000040` |

---

### ISS-026: Recursive LLM loop — run_meeting_report calls agent.run()

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — `run_meeting_report` FunctionTool added (revision --0000037, image pipeline-v5) |
| **Symptom** | `run_meeting_report` fires correctly, matches meeting, but then enters infinite loop eating all TPM quota. 429 errors flood logs |
| **Root Cause** | `meeting_processor.process_meeting()` internally called `self.agent.agent.run(prompt)` which re-invoked the **full agent** with all tools — including `run_meeting_report` itself. The LLM would call `run_meeting_report` again → recursive loop |
| **Impact** | 50K TPM consumed in seconds. Agent unresponsive until rate limit resets |
| **Resolution** | Replaced `agent.run()` in `meeting_processor.py` with direct `AzureOpenAI.chat.completions.create()` call (no tools parameter). Also disabled MCP email fallback which used the same `agent.run()` pattern. Added `openai>=1.0.0` as explicit dependency |
| **Prevention** | Never call `agent.run()` from within a tool function. Tool functions should use direct API calls for LLM invocations, not the agent framework |

| Image | `salesopsbot:pipeline-v6` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000038` |

---

### ISS-027: SDK drops local tools after MCP setup

| Field | Detail |
|-------|--------|
| **Stage** | Runtime — after `add_tool_servers_to_agent()` returns new agent (revision --0000039, image pipeline-v7) |
| **Symptom** | Logs show `running agent with 7 tools: [...]` — only MCP server names visible. The 4 local FunctionTools (`get_my_calendar_today`, `get_my_calendar_range`, `get_upcoming_meetings`, `run_meeting_report`) are missing |
| **Root Cause** | `McpToolRegistrationService.add_tool_servers_to_agent()` creates a brand-new `Agent` instance. Despite passing `initial_tools=list(self._local_tools)`, the returned agent only contains MCP server tool wrappers. The SDK ignores or overwrites the `initial_tools` parameter |
| **Impact** | Agent cannot call any local tools. `run_meeting_report` unavailable. Calendar lookups impossible |
| **Resolution** | Added defensive merge logic in `setup_mcp_servers()`: after getting the new agent, introspect its tool list. If local tools are missing, merge them back by patching the agent's internal tool storage attributes (`_tools`, `tools`, `_function_tools`, `default_options`, or `_default_options`) |
| **Prevention** | Always verify tool count after `add_tool_servers_to_agent()`. The SDK cannot be trusted to preserve `initial_tools` |

#### Merge logic (agent.py)

```python
mcp_tool_names = {getattr(t, 'name', str(t)) for t in all_tools}
local_tool_names = {getattr(t, 'name', str(t)) for t in self._local_tools}
missing = local_tool_names - mcp_tool_names
if missing:
    merged = list(all_tools) + list(self._local_tools)
    for attr in ['_tools', 'tools', '_function_tools']:
        if hasattr(self.agent, attr):
            setattr(self.agent, attr, merged)
            break
```

| Image | `salesopsbot:pipeline-v7b` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000040` |

---

### ISS-028: MCP delivery strategy — delegated vs application permissions

| Field | Detail |
|-------|--------|
| **Stage** | Architecture — deciding how to deliver email/Teams reports |
| **Symptom** | Direct Graph API calls for `Mail.Send` and `OnlineMeetings.Read.All` return 403 Forbidden |
| **Root Cause** | The app registration `8e5206be` uses **delegated** permissions via the Agent 365 agentic token exchange. The pipeline was using `DefaultAzureCredential` (client credentials flow) which requires **application** permissions that were never granted |
| **Impact** | Email and Teams delivery from the pipeline fail silently (403) |
| **Resolution** | Architecture change: instead of granting Graph application permissions, use MCP servers which authenticate via the agentic token exchange (delegated permissions already consented). The `run_meeting_report` tool now returns `email_html` and `email_subject` fields. The outer agent chains tools: call `run_meeting_report` → use MCP email/Teams tools to deliver |
| **Prevention** | Understand the permission model: Agent 365 agents use **delegated** permissions via MCP servers, not application permissions via client credentials. Direct Graph API calls require application permissions which must be explicitly granted and admin-consented |

#### Available MCP scopes (from a365.generated.config.json)

```
McpServers.Calendar.All, McpServers.CopilotMCP.All, McpServers.DASearch.All,
McpServers.Knowledge.All, McpServers.OneDriveSharepoint.All, McpServers.Planner.All,
McpServers.SharepointLists.All, McpServers.Teams.All, McpServers.Word.All
```

**Notable absence**: No `McpServers.Mail.All` scope. Email delivery must go through another channel.

| Image | `salesopsbot:pipeline-v7b` |
|-------|---|
| Revision | `azcaxyseurue7b6nw--0000040` |

---

### ISS-029: Report email readability + summary formatting regressions

| Field | Detail |
|-------|--------|
| **Stage** | Runtime report generation (`run_meeting_report` + transcript rerun delivery) |
| **Symptom** | Report emails render with unreadable header/body contrast (white on white) and executive summary appears as raw JSON blob |
| **Root Cause** | Template styling relied on inherited colors in some clients and summary field accepted non-string payloads without normalization |
| **Impact** | Users receive low-readability report output; confidence in automation quality drops despite successful pipeline execution |
| **Resolution** | Updated `report_email.html` header/body styles for deterministic contrast, normalized summary rendering in `report_generator.py`, and added explicit sentiment + expansion sections sourced from structured analysis fields |
| **Prevention** | Keep report template styles explicit (no implicit inherited colors), normalize all LLM fields before rendering, and test rerun emails against real meeting transcript payloads |

#### Additional hardening included

- Meeting-recipient routing in `meeting_processor.py` now prioritizes organizer/attendee recipients for reruns.
- `run_meeting_report` returns delivery status fields (`email_sent`, `email_recipients`, `teams_sent`) to reduce manual log babysitting.
- Autonomous payload and Word markdown now include `expansion_likelihood` and candidate product opportunities for consistent cross-channel output.

---

## Appendix: Key Resource IDs from This Deployment

| Resource | ID |
|----------|----|
| HOSKING Tenant | `b5c09a39-9df6-437a-a76e-19095fa6f20d` |
| Contoso Tenant | `c2833f41-c31d-4c2f-98d1-947fdb699aba` |
| Custom Client App | `8e5206be-48e3-4da4-b741-d3908cf7c30a` |
| Blueprint App ID | `c70fe227-230b-474c-bbf8-1d18483e2801` |
| Blueprint SP | `7e3020aa-9049-4734-83de-22513dffdc86` |
| Title ID | `T_ae143bb1-8f29-3a70-a2dc-ceab6f965d08` |
| Bot Endpoint | `https://azcaxyseurue7b6nw.wonderfulrock-5a126c64.uksouth.azurecontainerapps.io/api/messages` |
| Agent App Instance ID | `5653b53b-bdd6-42cf-9a8e-5c16f495d44a` |
| Agent User Object ID | `ec35260f-ceb9-40b1-9e8b-afafe29187cf` |
| Agent User UPN | `SalesOpSynthWorker984ebb@M365CPI14187042.onmicrosoft.com` |
| Agent 365 Tools API | `ea9ffc3e-8a23-4a7d-836d-234d7c7565c1` |
| MCP Gateway Endpoint | `https://agent365.svc.cloud.microsoft/agents/{id}/mcpServers` |
| Messaging Bot API | `5a807f24-c9de-44ee-a3a7-329e88a00ffc` |
| Observability API | `9b975845-388f-4429-889e-eab1ef63949c` |
| Power Platform API | `8578e004-a5c6-46e7-913e-12f58912df43` |
| Container App | `azcaxyseurue7b6nw` |
| ACR | `azcrxyseurue7b6nw.azurecr.io` |
| Azure OpenAI | `salesopsbot-openai` (S0, UK South, 50K TPM) |
| Subscription | `43b2438e-00b7-443e-b336-34cb97a489d4` |
