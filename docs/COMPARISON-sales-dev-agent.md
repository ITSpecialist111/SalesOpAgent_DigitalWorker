# Comparison: Sales Ops Bot vs Microsoft Sales Development Agent

**Date:** 16 February 2026  
**Reference:** [Use the Sales Development Agent](https://learn.microsoft.com/en-us/microsoft-agent-365/use#use-the-sales-development-agent)

---

## Overview

| Dimension | **Our Sales Ops Bot** | **Microsoft Sales Development Agent** |
|---|---|---|
| **Purpose** | Post-meeting intelligence: extract CRM updates from transcripts | Pre-meeting outreach: automate prospect email campaigns |
| **Sales stage** | Mid-funnel / post-call (meetings → CRM updates) | Top-of-funnel (cold outreach → qualification → handoff) |
| **Trigger** | Event-driven: "Meeting Ended" signal | User-driven: upload CSV prospect list, type "Go live" |
| **Core workflow** | Meeting → Transcript → LLM extraction → CRM proposal → Human approval → Dynamics update | Prospect list → Playbook → Email cadence → Track replies → Qualify → Handoff |
| **Human-in-the-loop** | Approval email before CRM write | Playbook/guidelines confirmation + live testing before go-live |
| **Configuration** | Code-defined (Python agent class, handler/service architecture) | Conversational: configure playbook, guidelines, product knowledge, settings via Teams chat |
| **Product knowledge** | None (extracts from meeting transcripts) | Upload docs, URLs, SharePoint files — agent learns your products |
| **Hosting** | Self-hosted: Azure Container Apps (custom code) | Microsoft-hosted template agent (no infrastructure needed) |
| **SDK** | `microsoft-agents-a365` Python SDK | Pre-built template — no SDK/coding required |
| **Identity** | Service Principal + split-tenant deployment | Standard Agent 365 instance from Teams Store |

---

## MCP Servers Comparison

| MCP Server | **Ours** | **Theirs** |
|---|---|---|
| Teams | ❌ *(not currently in ToolingManifest)* | ✅ |
| Outlook Mail | ❌ | ✅ |
| Calendar | ❌ *(handled via local Graph tools, not MCP)* | ❌ |
| Dynamics 365 / Dataverse | ❌ *(planned)* | ✅ |
| Work IQ (Knowledge) | ❌ *(planned)* | ✅ |
| Word | ✅ | ✅ |
| Excel | ❌ *(not in catalog)* | ✅ |
| SharePoint Lists | ✅ | ✅ |
| OneDrive/SharePoint | ❌ *(scope available, not currently enabled)* | ✅ |
| Sales | ❌ *(not in catalog)* | ✅ |
| Me (Profile) | ❌ *(not in catalog)* | ✅ |
| Copilot MCP | ❌ *(scope available, not currently enabled)* | ✅ |
| Search (DASearch) | ❌ *(scope available, not currently enabled)* | ✅ |
| Planner | ✅ | ❌ |
| M365 Copilot | ❌ *(not currently enabled)* | ✅ |

**Summary (updated 16 Feb 2026):** The checked-in runtime baseline currently uses **4 MCP servers** (Word, SharePoint Lists, Knowledge, Planner). Additional scopes exist in tenant consent but are not all enabled in `ToolingManifest.json` yet.

---

## Graph Permissions Comparison

| Permission | **Ours** | **Theirs** |
|---|---|---|
| Mail.Send | ✅ | ✅ |
| Mail.ReadWrite.Shared | ❌ | ✅ |
| Chat.Read | ❌ | ✅ |
| Chat.Create | ❌ | ✅ |
| ChatMessage.Send | ❌ | ✅ |
| ChannelMessage.Read.All | ❌ | ✅ |
| Files.ReadWrite.All | ❌ | ✅ |
| Sites.ReadWrite.All | ❌ | ✅ |
| User.Read.All | ❌ | ✅ |
| Presence.ReadWrite | ❌ | ✅ |

**Summary:** Their permissions footprint is much broader (Files, Sites, Chat, Presence). Ours is deliberately narrow — we only need transcript access + mail + Dynamics 365 CRM.

### Additional Permissions (theirs only)

| API | Permission |
|---|---|
| Power Platform Environment Service | `user_impersonation` |
| Dataverse | `user_impersonation` |
| Power Platform API | `Connectivity.Connections.Read` |
| Power Platform API | `CopilotStudio.Copilots.Invoke` |
| Messaging Bot API Application | `AgentData.ReadWrite` |

---

## Key Differences

1. **Complementary, not competing** — They solve different sales problems. Ours is post-meeting CRM automation; theirs is pre-meeting outreach automation. They could work together: theirs generates meetings, ours processes them.

2. **Template vs custom** — The Sales Development Agent is a pre-built template you configure conversationally. Ours is custom code with full control over the pipeline logic — necessary for our transcript extraction + CRM approval workflow, which isn't a template scenario.

3. **MCP surface area** — Their agent currently has broader active MCP coverage. Ours is intentionally pinned to a 4-server stable baseline while delivery-oriented servers are validated.

4. **Permissions footprint** — Their agent has much broader Graph permissions (Files, Sites, Chat, Presence). Ours is deliberately narrow — we only need transcript access + mail + CRM.

5. **Meeting detection approach** — We detect meetings via direct Graph calendar polling/local tools rather than Calendar MCP.

6. **Conversational config vs code** — Their agent is configured entirely through Teams chat (playbook, guidelines, product knowledge). Our agent's behavior is defined in Python code. Their approach is more accessible; ours is more customizable.

---

## Their Configuration Framework

The Sales Development Agent uses a conversational configuration model with four components:

| Component | What it does | How to manage it |
|---|---|---|
| **Playbook** | Defines prospect progression (outreach → qualification → handoff). Stages are fixed; rules are customizable | Comes with defaults; customize through Teams chat |
| **Guidelines** | Sets communication tone and acceptable/unacceptable behaviors | Modify through Teams chat |
| **Product knowledge** | Documents and URLs that teach the agent about products (.docx, .pdf, .pptx, .txt, SharePoint, web URLs up to 2 levels deep) | Upload directly in Teams chat |
| **Settings** | Controls email cadence, signature, unsubscribe text | Modify through Teams chat |

### Their Staged Rollout

1. **Onboard** — Configure playbook, guidelines, product knowledge, settings
2. **Test in chat** — Role-play scenarios in 1:1 Teams chat
3. **Upload prospect CSV** — Validate prospect list (Email, Company Name, Product, First Name)
4. **Run test** — Agent generates sample outreach emails for review
5. **Go live** — Type "Go live" → agent starts sending real emails
6. **Scale** — Create additional instances for new products/regions/campaigns

---

## Their Current Limitations

| Area | Limitation |
|---|---|
| Teams chat | Only 1:1 chats between the agent's creator and the agent |
| Communication | Email and Teams chats only — no Channels, document comments, or meetings |
| Email threads | Only replies to threads it started |
| Renaming | Agent names are permanent after deployment |
| Data ingestion | No recursive crawling or media files |
| Analytics | No visual dashboards; progress shared via Teams chat |
| Human oversight | Runs autonomously once launched until stopped |
| Email sending | Sends at all hours including weekends |

---

## Opportunities to Learn From

- **Product knowledge ingestion** — their doc/URL upload capability for agent learning is powerful; we could add similar context enrichment
- **Draft → test → go-live workflow** — their staged rollout pattern is a good UX model for our approval workflow
- **Additional MCP servers** — IN PROGRESS: Keep 4-server stable baseline while validating re-enable of Teams/OneDrive and other consented scopes
- **Conversational configuration** — worth exploring as a future UX layer on top of our code-defined pipeline
- **Prospect CSV format** — their structured input format is clean; we could adopt similar patterns for batch meeting processing
