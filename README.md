# Agent 365 Synthetic Worker: Sales Ops Bot

This repository contains the source code for a **Sales Operations Digital Employee**, built using the **Microsoft Agent 365 SDK** and **Model Context Protocol (MCP)**.

## Current Status (2026-02-16)

- ✅ Deployment healthy in Azure Container Apps (`<container-app-revision>` active, 100% traffic)
- ✅ Health endpoint reports `status: ok`, `agent_initialized: true`, MCP state `ready`
- ✅ Tests passing locally (`pytest -q`)
- ✅ Report/email UX updates live (summary normalization, readable header, sentiment + expansion sections)

## \uD83D\uDCC2 Documentation

| Document | Purpose |
|----------|---------|
| **[SETUP.md](SETUP.md)** | **Start Here**. Prerequisites and "Definition of Ready". |
| **[PLAN.md](PLAN.md)** | Step-by-step technical execution plan. |
| **[ROADMAP.md](ROADMAP.md)** | Strategic milestones from "Intern" to "Enterprise". |
| **[SPEC-SyntheticWorker.md](SPEC-SyntheticWorker.md)** | Detailed architecture and functional specification. |
| **[HANDOVER.md](HANDOVER.md)** | Current state of the codebase vs. the desired state. |
| **[docs/a365-guided-setup.md](docs/a365-guided-setup.md)** | AI-guided a365 CLI setup reference (from [Agent365-devTools](https://github.com/microsoft/Agent365-devTools)). |
| **[docs/TROUBLESHOOTING-A365.md](docs/TROUBLESHOOTING-A365.md)** | Known issues and fixes (ISS-001 – ISS-029). |
| **[docs/INCIDENT-2026-02-MEETING-REPORT.md](docs/INCIDENT-2026-02-MEETING-REPORT.md)** | Post-incident write-up for transcript/report stabilization and runbook learnings. |

## \uD83D\uDE80 Quick Start

1.  **Prerequisites**: Ensure you have Python 3.11+, .NET 8 SDK, and Agent 365 CLI installed (`dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli --prerelease`). See [SETUP.md](SETUP.md).
2.  **Install**: `pip install -e .`
3.  **Configure**: Copy `.env.template` to `.env` and add your LLM keys.
4.  **Lifecycle flow**: Follow [Agent 365 development lifecycle](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/a365-dev-lifecycle) steps: build/run → config → blueprint → deploy/publish.

## 🤖 AI-Guided Setup (Recommended)

The fastest way to set up or redeploy this agent is using the **AI-guided setup prompt** from the official [Agent365-devTools](https://github.com/microsoft/Agent365-devTools) repository. This is an AI-agent-compatible runbook that walks a coding agent (e.g. GitHub Copilot, Cursor, Claude) through the full a365 CLI pipeline end-to-end.

### How to Use

1. Copy the [a365-setup-instructions.md](https://github.com/microsoft/Agent365-devTools/blob/main/docs/agent365-guided-setup/a365-setup-instructions.md) into your AI agent's context (paste it as a prompt, or save it locally and reference it).
2. The prompt instructs the agent to execute 5 steps autonomously:

| Step | What It Does |
|------|-------------|
| **1. Verify CLI** | Installs/updates the `a365` CLI (.NET global tool) |
| **2. Prerequisites** | Validates Azure CLI login, Entra ID roles, custom client app registration with 5 required Graph permissions, and language-specific build tools |
| **3. Configure** | Gathers inputs (resource group, location, agent name, manager email), derives naming conventions, creates `a365.config.json`, imports via `a365 config init` |
| **4. Setup** | Runs `a365 setup all` — provisions infrastructure, creates Entra ID blueprint, configures permissions, registers messaging endpoint |
| **5. Publish & Deploy** | Reviews manifest, runs `a365 publish` + `a365 deploy`, configures agent in Teams Developer Portal, creates agent instance |

### Why This Matters

- **Repeatable**: Same prompt produces a consistent setup every time, across any Agent 365 project
- **Self-healing**: The prompt includes validation gates at every step, error handling, and troubleshooting for common failures (RBAC, quota limits, Graph permission errors, dev tunnel issues)
- **Project-agnostic**: Detects .NET, Node.js, or Python projects automatically and validates the correct build toolchain
- **Split-tenant aware**: Handles scenarios where Azure infrastructure and M365 identity live in different tenants (as in this project)
- **Idempotent**: Steps can be safely re-run after fixing issues — the CLI skips existing resources

### Key Prerequisites (from the guided setup)

The custom client app registration in Entra ID requires these **5 delegated permissions** with admin consent:

| Permission | Purpose |
|------------|---------|
| `AgentIdentityBlueprint.ReadWrite.All` | Manage Agent 365 Blueprints |
| `AgentIdentityBlueprint.UpdateAuthProperties.All` | Update Blueprint auth properties |
| `Application.ReadWrite.All` | Create and manage Azure AD applications |
| `DelegatedPermissionGrant.ReadWrite.All` | Grant delegated permissions |
| `Directory.Read.All` | Read directory data |

### Self-Hosted vs Azure-Hosted

This project uses a **self-hosted** deployment model (`needDeployment: false`) since we deploy to Azure Container Apps rather than the CLI's built-in Azure App Service. When running the guided setup:

- Choose **"No"** when asked about creating a web app in Azure
- Set the `messagingEndpoint` to your Container App URL: `https://<your-app>.azurecontainerapps.io/api/messages`
- The CLI still provisions the Entra ID blueprint, permissions, and agent identity

### Local Reference

A local reference is maintained at [`docs/a365-guided-setup.md`](docs/a365-guided-setup.md).

> **Source**: [microsoft/Agent365-devTools](https://github.com/microsoft/Agent365-devTools/blob/main/docs/agent365-guided-setup/a365-setup-instructions.md) — keep in sync as the CLI evolves.

## Architecture

The agent runs as a headless service:
1.  **Triggers** on `MeetingEnded`.
2.  **Fetches** transcripts via Microsoft Graph client (`GraphTranscriptClient`) using event → online meeting resolution and transcript content retrieval.
3.  **Computes** structured insights using LLM (summary, executive summary, tasks, sentiment, churn risk, customer satisfaction, CRM update hints).
4.  **Generates** a post-meeting Word report autonomously via Word MCP when the tool is active.
5.  **Pushes** account-note updates autonomously via Dynamics/Dataverse MCP when available, with a safe local Dynamics stub fallback.
6.  **Delivers** summaries via Graph and/or MCP tools depending on enabled server set (`ToolingManifest.json` currently enables Word, SharePoint Lists, Knowledge, Planner), with local tool fallback paths for resilience.

## Deployment

### Docker (Local Build)
```bash
docker build -t sales-ops-bot .
docker run -p 8000:8000 --env-file .env sales-ops-bot
```

### Azure Container Apps
1.  **Build & Push**:
    ```bash
    az acr build --registry <your-registry> --image sales-ops-bot:latest .
    ```
2.  **Deploy**:
    ```bash
    az containerapp create --yaml deployment.yaml --resource-group <your-rg>
    ```

## Project Structure
- `src/`: Core agent logic.
- `tests/`: Unit and integration tests.
- `docs/`: Reference documentation (MCP Registry).
- `Dockerfile`: Container definition.
- `deployment.yaml`: Azure manifest.

## Repository Hygiene

- **Canonical lifecycle/runbooks**: `docs/a365-guided-setup.md` and `docs/TROUBLESHOOTING-A365.md`.
- **Generated diagnostics/artifacts** (logs, build outputs, captured doc extracts) are excluded via `.gitignore` and should not be treated as source of truth for implementation decisions.
- If a generated artifact conflicts with canonical docs, update the canonical docs and regenerate artifacts as needed.

