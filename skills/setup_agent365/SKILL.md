---
description: How to set up an Agent 365 project with the "Slick" configuration (verified MCPs, SDK patches, ACA deployment).
---

# Agent 365 Setup Skill (The "Slick" Config)

This skill guides you through setting up a robust Microsoft Agent 365 project using the "Hybrid" deployment model (`needDeployment: false`) and proven configurations for MCP servers, SDK patching, and Azure Container Apps.

> **Goal**: Get the agent working **1st time** by avoiding known pitfalls (hallucinations, 403 errors, WAM auth issues).

## 1. Verification & Prerequisites (The "Gatekeeper")

**BEFORE** running any commands, verify the environment.

1.  **Check Tools**:
    ```powershell
    dotnet --version # Must be 8.x
    az --version # Must be 2.x
    docker --version # Must be installed
    pwsh --version # Must be 7.x
    ```

2.  **Check Tenant Configuration** (Identify "Split-Tenant" risk):
    *   Run `az account show`.
    *   **IF** the tenant ID matches the M365 identity tenant: **Good** (Single-Tenant).
    *   **IF** they differ: **Warning** (Split-Tenant). You must login to the Identity tenant (`--allow-no-subscriptions`) for `a365` commands, and the Infra tenant for `az`/`azd` commands.

3.  **Check WAM Registration**:
    *   Run `dsregcmd /status`.
    *   Ensure the M365 identity account is listed under "Workplace Join" or "AzureAdJoined". If not, the user MUST add it via Windows Settings -> Accounts -> Access work or school.

## 2. Configuration ("The Configurator")

Do **NOT** use the interactive wizard. Generate a robust `a365.config.json` manually.

1.  **Determine Endpoint**:
    *   Ask the user: "Where will this be hosted? (Azure Container Apps, Local, etc.)".
    *   Base URL: `https://<app-name>.<region>.azurecontainerapps.io` (or similar).
    *   Messaging Endpoint: `<Base URL>/api/messages`.

2.  **Generate Config**:
    Create `a365.config.json` with `needDeployment: false`:
    ```json
    {
      "tenantId": "<IDENTITY_TENANT_ID>",
      "subscriptionId": "<IDENTITY_TENANT_ID>", // Workaround for CLI validation
      "resourceGroup": "rg-<agent-name>",
      "location": "uksouth",
      "messagingEndpoint": "https://<your-app>.azurecontainerapps.io/api/messages",
      "needDeployment": false,
      "agentIdentityDisplayName": "<Agent Name>",
      "agentBlueprintDisplayName": "<Agent Name> Blueprint",
      "managerEmail": "<admin-email>"
    }
    ```

## 3. The "Slick" Setup (Code Generation)

Inject these **proven patterns** into the codebase. Do not rely on default scaffolding.

### A. The SDK Patch (Fixes 400 Bad Request / Auth)
Copy the pre-made patch script:
```powershell
cp skills/setup_agent365/assets/patch_sdk.py scripts/
```

### B. The Proven Tooling Manifest (Fixes 403 Cascades)
Copy the known-good manifest (ONLY 4 proven servers):
```powershell
cp skills/setup_agent365/assets/ToolingManifest.json .
```

### C. Local Tools Fallback (Fixes Hallucinations)
In `agent.py`, implement `_build_local_tools()` to wrap Graph API calls (Calendar/Mail) as `FunctionTool`s.
*   **Why**: If the MCP gateway fails (returns 0 servers), the agent MUST fallback to these local tools.
*   **How**: Initialize agent with `initial_tools=local_tools`.

### D. Dockerfile & Infrastructure
*   **Dockerfile**: Must include `RUN python scripts/patch_sdk.py` after pip install.
*   **Startup**: ENTRYPOINT should be `python src/start_with_generic_host.py` (not main.py).
*   **Deployment**: Use the pre-configured ACA manifest:
    ```powershell
    cp skills/setup_agent365/assets/deployment.yaml .
    ```
    Ensure secrets (Client ID/Secret) are referenced from Key Vault.

## 4. Execution (The "Happy Path")

1.  **Pre-Setup Check**: Ensure custom client app (`clientAppId` in config) has the 5 required delegated permissions + admin consent.
2.  **Run Setup**:
    ```powershell
    a365 setup requirements
    a365 setup blueprint --verbose 2>&1  # Watch for WAM popup!
    a365 setup permissions mcp --verbose
    a365 setup permissions bot --verbose
    ```
3.  **Publish**:
    ```powershell
    a365 publish --verbose 2>&1 # Watch for browser window!
    ```

## 5. Post-Flight Checks

1.  **License**: Go to M365 Admin Center -> Users -> Agent. Verify "Microsoft Agent 365 Frontier" license is assigned.
2.  **App Permissions**: Go to Entra ID -> App Registration -> `<your-app-id>`. Grant **Application** permissions for:
    *   `Mail.Send` (to send emails)
    *   `OnlineMeetings.Read.All` (to read transcripts)
3.  **Env Vars**: Push the new `AGENT_ID` (from `.env`) to the Container App. Restart the revision.

> **Success Indicator**: Agent responds in Teams, can list its tools (including Planner/SharePoint), and successfully runs `run_meeting_report` with readable email/report output (summary text + sentiment/expansion sections).
