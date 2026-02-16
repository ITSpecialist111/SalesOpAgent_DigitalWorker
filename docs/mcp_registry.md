# Azure MCP Server Registry
*Verified Access List as of 2026-02-16*

This document lists the Model Context Protocol (MCP) servers available via Azure App Registrations (Delegated Permissions).

## Runtime Baseline (this repository)

`ToolingManifest.json` is the source of truth for MCP servers enabled at runtime in this repo. Current active set:

- `mcp_WordServer` (`McpServers.Word.All`)
- `mcp_SharePointListsTools` (`McpServers.SharepointLists.All`)
- `mcp_KnowledgeTools` (`McpServers.Knowledge.All`)
- `mcp_PlannerServer` (`McpServers.Planner.All`)

All other scopes below should be treated as *catalog/consent availability*, not active runtime connections.

## 🌍 Web & Knowledge
*   **`McpServers.WebSearch.All`**: Web Search Tool (Bing). *Target for "Live Knowledge" feature.*
*   **`McpServers.Knowledge.All`**: Knowledge MCP Server.
*   **`McpServers.CopilotMCP.All`**: Copilot MCP Server.

## 💼 Dynamics 365 & Dataverse
*   **`McpServers.Dataverse.All`**: Dataverse MCP Server (Dynamics 365 data platform). *Primary target for core CRM updates in this project.*
*   **`McpServers.D365Sales.All`**: D365 Sales MCP Server. *Target for Opportunity management.*
*   **`McpServers.D365Service.All`**: D365 Service MCP Server.
*   **`McpServers.D365ContactCenter.All`**: D365 Contact Center.

## 🤝 Productivity & Collaboration
*   **`McpServers.Teams.All`**: Teams MCP Server. *Target for Interactive Presence (Chat).*
*   **`McpServers.Calendar.All`**: Calendar MCP Server. *Target for Meeting Detection.*
*   **`McpServers.Mail.All`**: Mail MCP Server. *Target for Email Detection/Reporting.*
*   **`McpServers.Files.All`**: ODSP Files Tool.
*   **`McpServers.OneDriveSharepoint.All`**: OneDrive & SharePoint.
*   **`McpServers.Planner.All`**: Planner MCP Server.
*   **`McpServers.Word.All`**: Word MCP Server.
*   **`McpServers.Excel.All`**: Excel MCP Server.
*   **`McpServers.PowerPoint.All`**: PowerPoint MCP Server.

## 🛠️ Admin & Management
*   **`McpServers.Admin365Graph.All`**: Admin365 Graph Tool.
*   **`McpServers.M365Admin.All`**: Microsoft Admin Center.
*   **`McpServers.Management.All`**: Management MCP Server.
*   **`McpServers.Me.All`**: Me MCP Server.

## 🧩 Agent Tools
*   `AgentTools.AgentBluePrint.Create`
*   `AgentTools.AgentBluePrint.Delete`
*   `AgentTools.ListDataverseEnvironments.All`
*   `AgentTools.ListMCPServers.All`
*   `AgentTools.PublishMCPServer.All`
*   `AgentTools.UnpublishMCPServer.All`
