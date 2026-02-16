import asyncio
import logging
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# MOCK DEPENDENCIES
from unittest.mock import MagicMock
sys.modules["agent_framework"] = MagicMock()
sys.modules["agent_framework.azure"] = MagicMock()
sys.modules["microsoft_agents"] = MagicMock()
sys.modules["microsoft_agents.hosting"] = MagicMock()
sys.modules["microsoft_agents.hosting.core"] = MagicMock()
sys.modules["microsoft_agents_a365"] = MagicMock()
sys.modules["microsoft_agents_a365.notifications"] = MagicMock()
sys.modules["microsoft_agents_a365.notifications.agent_notification"] = MagicMock()
sys.modules["microsoft_agents_a365.observability"] = MagicMock()
sys.modules["microsoft_agents_a365.observability.extensions"] = MagicMock()
sys.modules["microsoft_agents_a365.observability.extensions.agentframework"] = MagicMock()
sys.modules["microsoft_agents_a365.observability.extensions.agentframework.trace_instrumentor"] = MagicMock()
sys.modules["microsoft_agents_a365.tooling"] = MagicMock()
sys.modules["microsoft_agents_a365.tooling.extensions"] = MagicMock()
sys.modules["microsoft_agents_a365.tooling.extensions.agentframework"] = MagicMock()
sys.modules["microsoft_agents_a365.tooling.extensions.agentframework.services"] = MagicMock()
sys.modules["microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service"] = MagicMock()

# Now import agent
from agent import SalesOpsAgent

# Patch methods that require Azure Env Vars
async def mock_create_chat_client(self):
    print("⚠️ Mocking AzureOpenAIChatClient")
    self.chat_client = MagicMock()

async def mock_create_agent(self):
    print("⚠️ Mocking ChatAgent")
    self.agent = MagicMock()
    # Mock the run method to return a valid response object
    mock_response = MagicMock()
    mock_response.content = "Subject: Approval Needed for Dynamics 365 Update\n\nProposed Changes:\n- Opportunity: Global Expansion\n- Stage: Negotiation"
    self.agent.run.return_value = mock_response

SalesOpsAgent._create_chat_client = mock_create_chat_client
SalesOpsAgent._create_agent = mock_create_agent

# Configure logging to see the agent's output
logging.basicConfig(level=logging.INFO)

async def run_verification():
    print("🚀 Starting Mock Verification...")
    
    # 1. Initialize Agent
    agent = SalesOpsAgent()
    # Mock the create methods which (improperly) were sync in the original code but we made async in patch? 
    # Wait, in the original code they are sync methods called in __init__.
    # We must patch them on the class BEFORE instantiation, but they are instance methods called in __init__.
    # The patch above works for future instances.
    
    # However, _create_chat_client and _create_agent are SYNC in the original code. 
    # My mock functions above are async, which might break __init__ if it calls them.
    # Let's fix the mock functions to be sync.
    pass 
    
    # CORRECT CORRECTION inside the replacement block:
    # redefine mocks as sync
    
def mock_create_chat_client_sync(self):
    print("⚠️ Mocking AzureOpenAIChatClient")
    self.chat_client = MagicMock()

def mock_create_agent_sync(self):
    print("⚠️ Mocking ChatAgent")
    self.agent = MagicMock()
    
    # Mock the LLM response for the MeetingProcessor
    # The MeetingProcessor calls `await self.agent.agent.run(prompt)`
    # So agent.agent (the inner ChatAgent) needs a run method.
    # self.agent IS the ChatAgent in the class.
    
    async def mock_run(message):
        mock_res = MagicMock()
        # Return JSON string as expected by the new MeetingProcessor
        mock_content = json.dumps({
            "summary": "The team agreed to move forward with the global expansion plan.",
            "tasks": ["Update CRM", "Schedule follow-up"],
            "crm_updates": {"Opportunity": "Global Expansion", "Stage": "Negotiation"},
            "crm_link": "https://dynamics.microsoft.com/mock-link"
        })
        mock_res.content = mock_content
        return mock_res
        
    self.agent.run = mock_run

SalesOpsAgent._create_chat_client = mock_create_chat_client_sync
SalesOpsAgent._create_agent = mock_create_agent_sync

async def run_verification():
    print("🚀 Starting Mock Verification...")
    
    # 1. Initialize Agent
    agent = SalesOpsAgent()
    
    # IMPORTANT: We also need to mock the MeetingProcessor's graph client fetch
    # because we don't have real credentials for it either.
    agent.graph_client = MagicMock()
    async def mock_get_transcript(meeting_id):
        return "Speaker 1: Let's move the deal to Negotiation. Speaker 2: Agreed."
    agent.graph_client.get_transcript_content = mock_get_transcript
    
    # Re-initialize processor with the mock graph client if needed, 
    # but agent.__init__ already created it with the real one. 
    # We can swap it out.
    agent.meeting_processor.graph_client = agent.graph_client

    await agent.initialize()
    print("✅ Agent Initialized.")

    # 2. Simulate "Meeting Ended" Event (Mock Context)
    mock_context_ended = {
        "trigger": "calendar_poll",
        "type": "ended",
        "meeting_id": "MOCK_MEETING_123",
        "subject": "Q4 Strategy Review"
    }
    
    # 3. Simulate "Upcoming Meeting" Event (Phase 4c)
    mock_context_upcoming = {
        "trigger": "calendar_poll",
        "type": "upcoming",
        "meeting_id": "MOCK_MEETING_456",
        "subject": "Client Kickoff"
    }

    # 4. Trigger Handler Manually
    print(f"🚦 Triggering Pipeline (Ended): {mock_context_ended['subject']}")
    await agent.handle_meeting_detected(mock_context_ended)
    
    print(f"🚦 Triggering Pipeline (Upcoming): {mock_context_upcoming['subject']}")
    await agent.handle_meeting_detected(mock_context_upcoming)

    # 4. Phase 4d: Simulate Live Knowledge Injection
    print("⏳ Simulating Live Transcript Update...")
    
    # Mock the transcript to contain a trigger keyword
    async def mock_get_live_transcript(meeting_id):
        return "Speaker 1: Welcome everyone. Speaker 2: What is Microsoft 365 Copilot? Speaker 1: Good question."
    
    agent.graph_client.get_transcript_content = mock_get_live_transcript
    
    # Manually trigger the monitor once (instead of waiting for the loop)
    # The agent.active_meetings should have the upcoming meeting
    if "MOCK_MEETING_456" in agent.active_meetings:
        print("👀 Monitoring Active Meeting...")
        await agent.knowledge_service.monitor_meeting("MOCK_MEETING_456", "Client Kickoff")
    else:
        print("❌ Meeting not active!")

    print("✅ Verification Complete. Check logs for 'Knowledge Injection'.")

if __name__ == "__main__":
    asyncio.run(run_verification())
