# Project Specification: Agent 365 Synthetic Worker ("Sales Ops Bot")

> **Status (2026-02-16):** Working in production with transcript analysis, enriched reporting, and autonomous post-meeting action paths enabled.

## 1. Executive Summary
**Goal:** Build an autonomous "Synthetic Worker" using the **Microsoft Agent 365 SDK** and **Model Context Protocol (MCP)**.
**Key Pattern:** "Digital Employee" - The agent is treated as a colleague and **must be invited to meetings** to perform its duties. This grants it direct access to transcripts and chat context.

## 2. Technology Stack
*   **SDK:** `microsoft-agents-a365` (Python).
*   **Data Layer (MCP):**
    *   **Current runtime baseline:** `mcp_WordServer`, `mcp_SharePointListsTools`, `mcp_KnowledgeTools`, `mcp_PlannerServer`.
    *   **Local tools:** calendar/report tools in `agent.py` for reliable meeting access when MCP gateway is degraded.
    *   **Business servers (target):** Dataverse/Dynamics 365 MCP.
*   **Identity:** Entra Agent ID (Service Principal).

## 3. Architecture Overview
**Class:** `SalesOpsAgent` inherits `AgentInterface`.

1.  **Preparation (The Invite)**:
    *   User invites the agent (e.g., `sales-ops-bot@contoso.com`) to the meeting.
    *   Agent automatically accepts (via Exchange rule or Logic App, or manual acceptance initially).

2.  **Meeting Detection Strategy (Participant-Based)**:
    *   **Calendar Poller:** Checks the agent's *own* calendar for recently ended meetings where it was a participant.
    *   **Email Handler:** Listens for "Meeting Ended" notifications sent to the agent.

3.  **Logic Pipeline (`MeetingProcessor`)**:
    *   **Input:** Meeting ID (from Calendar/Email).
    *   **Context Gathering:** Use **Work IQ** to find related emails/files from the participants.
    *   **Transcript Fetch:** Use `GraphTranscriptClient` (acting as the participant agent).
    *   **Extraction:** LLM extracts `MeetingIntelligence` (Summary, Executive Summary, Next Steps, CRM Updates, Sentiment, Churn Risk, Customer Satisfaction, Expansion Likelihood).
    *   **Review:** Agent sends an "Approval Needed" email with the proposed CRM changes.
    *   **Action:** Autonomous path can generate Word report + Dynamics account note (`DynamicsClient` / `Dataverse`), with safe fallback behavior.

## 4. Implementation Steps

### Phase 1: Foundation & Identity (Done)
*   Basic scaffolding, hosting, and agent class.
*   Work IQ integration plan.

### Phase 2: Tooling & Integrations (Done)
*   `work-iq` installed.
*   `GraphTranscriptClient` implemented for real transcript/calendar retrieval.
*   `DynamicsClient` currently stubbed pending Dataverse wiring.

### Phase 3: Meeting Detection (Done)
*   `EmailHandler` & `CalendarHandler` implemented.
*   *Refinement:* Ensure handlers look for "My Meetings".

### Phase 4: Intelligence Pipeline ("The Brain")
*   **MeetingProcessor Service**:
    *   Orchestrates the flow: Trigger -> Transcript -> Intelligence -> CRM Proposal.
*   **Transcript Access**:
    *   Agent uses Graph user-scoped routes with event → onlineMeeting resolution and transcript content retrieval.

### Phase 5: Deployment
*   Host on Azure Container Apps / App Service.
