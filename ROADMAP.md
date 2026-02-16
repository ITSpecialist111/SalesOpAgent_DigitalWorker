# Project Roadmap: Agent 365 Synthetic Worker

This roadmap outlines the evolution of the "Sales Ops Bot" from a basic script to a fully governed Digital Employee.

## Milestone 1: The "Digital Intern" (Foundation) — COMPLETE
**Focus**: Identity, Connectivity, and Basic Observation.
*   **Goal**: The agent exists in the Global Address List (GAL) and can attend meetings.
*   **Key Deliverables**:
    *   [x] Agent registered in Entra ID (Contoso tenant).
    *   [x] Agent 365 Blueprint created and published to M365.
    *   [x] Agent responding in Teams 1:1 chats.
    *   [x] Calendar handler detecting meeting events via Graph API polling.
    *   [x] Email handler parsing "Meeting Ended" signals.
    *   [x] Exchange Online mailbox configured (auto-accept, visible in GAL).
    *   [x] Deployed to Azure Container Apps (UK South).

## Milestone 2: The "Junior Analyst" (Intelligence) — COMPLETE
**Focus**: Reasoning and Basic Output.
*   **Goal**: The agent can read transcripts and formulate insights.
*   **Key Deliverables**:
    *   [x] **LLM Integration** — GPT-4o (50K TPM) for transcript analysis.
    *   [x] **Meeting Processor** — Full pipeline: transcript to LLM analysis to reports to MS Learn enrichment.
    *   [x] **On-demand reports** — `run_meeting_report` FunctionTool callable from Teams.
    *   [x] **MS Learn enrichment** — Real API calls to `learn.microsoft.com/api/search`.
    *   [x] **Report generation** — HTML email and Adaptive Card formats.
    *   [x] **Transcript fetching** — Implemented via Graph API (event → onlineMeeting resolution + transcript content retrieval).

## Milestone 2.5: The "Communicator" (Delivery) — IN PROGRESS
**Focus**: Delivering reports via email and Teams using MCP tools.
*   **Goal**: The agent can send generated reports to users via their preferred channel.
*   **Key Deliverables**:
    *   [ ] **MCP TeamsServer** re-enable in ToolingManifest.json after stability validation.
    *   [ ] **MCP OneDriveSharepointServer** re-enable in ToolingManifest.json after stability validation.
    *   [x] **Tool chaining** — Agent prompt supports: `run_meeting_report` then MCP delivery.
    *   [x] **Local tool merge** — SDK tool-drop bug worked around.
    *   [x] **Report UX quality** — readable email styles + sentiment and expansion sections live.
    *   [x] **Autonomous payload enrichment** — expansion likelihood carried into Word/Dynamics paths.
    *   [ ] **Email delivery** — Testing MCP-based email send (no `McpServers.Mail.All` scope).
    *   [ ] **Teams delivery** — Testing MCP TeamsServer for message posting.
    *   [x] **Verify end-to-end core path** — transcript/report generation + health/deploy validations passing.

## Milestone 3: The "Sales Ops Assistant" (Integration & Approval)
**Focus**: System-to-System Action with CRM Flexibility.
*   **Goal**: The agent updates the CRM (Dynamics 365) after human approval.
*   **Key Deliverables**:
    *   [ ] **Dynamics 365 MCP** connected (Primary Dev Target).
    *   [ ] **Salesforce MCP** configured (Demo Target).
    *   [ ] **Human-in-the-loop**: "Approve/Edit" Actionable Messages.
    *   [ ] **CRM Abstraction Layer**: Code handles switching between CRMs.

## Milestone 4: Enterprise Ready (Scale)
**Focus**: Governance, Security, and Advanced Workflows.
*   **Goal**: Trusted operation at scale.
*   **Key Deliverables**:
    *   [ ] **Work IQ MCP** integration.
    *   [ ] **Observability** dashboards (Application Insights already provisioned).
    *   [ ] **Compliance** policies.
    *   [ ] **Production mode** MCP gateway (currently using Development mode).

## Future Horizons
*   **Voice Interactivity** (Realtime API).
*   **Proactive Nudges** (Pre-meeting briefings).
*   **Multi-agent orchestration** — coordinator agent delegates to specialist agents.
