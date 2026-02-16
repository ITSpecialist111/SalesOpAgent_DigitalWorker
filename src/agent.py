# Copyright (c) Microsoft. All rights reserved.

"""
Sales Ops Synthetic Worker Agent
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
_root_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _root_log_level, logging.INFO))
logger = logging.getLogger(__name__)

for noisy_logger in (
    "azure",
    "azure.identity",
    "azure.core",
    "azure.core.pipeline",
    "httpx",
    "httpcore",
    "urllib3",
    "msal",
):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# AgentFramework SDK
from agent_framework import Agent as FrameworkAgent, FunctionTool, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

# Agent Interface
from agent_interface import AgentInterface
from azure.identity import AzureCliCredential, DefaultAzureCredential

# Microsoft Agents SDK
from local_authentication_options import LocalAuthenticationOptions
from microsoft_agents.hosting.core import Authorization, TurnContext

# Notifications
from microsoft_agents_a365.notifications.agent_notification import NotificationTypes

# Observability Components
from microsoft_agents_a365.observability.extensions.agentframework.trace_instrumentor import (
    AgentFrameworkInstrumentor,
)

# MCP Tooling
from microsoft_agents_a365.tooling.extensions.agentframework.services.mcp_tool_registration_service import (
    McpToolRegistrationService,
)
from microsoft_agents_a365.tooling.utils.constants import Constants
from microsoft_agents_a365.tooling.utils.utility import get_mcp_platform_authentication_scope
from token_cache import get_cached_agentic_token

# Handlers & Integrations
from handlers.email_handler import EmailHandler
from handlers.calendar_handler import CalendarHandler
from integrations.graph_transcript_client import GraphTranscriptClient
from services.meeting_processor import MeetingProcessor
# from integrations.salesforce_client import SalesforceClient # Removing
from integrations.dynamics_client import DynamicsClient
from services.teams_chat_service import TeamsChatService
from services.live_knowledge_service import LiveKnowledgeService


class SalesOpsAgent(AgentInterface):
    """Sales Ops Agent integrated with MCP servers and Observability"""
    
    # Static base prompt — identity, rules, and behaviour. Never lists capabilities statically.
    AGENT_PROMPT_BASE = (
        "You are SalesOpsAgent, a Sales Operations digital employee deployed as a Microsoft Agent 365 agent. "
        "You are a real participant in the organisation — you have your own calendar, email inbox, and Teams presence. "
        "You are NOT a chatbot that only answers questions. You are an autonomous worker that actively monitors and acts.\n\n"

        "BACKGROUND CAPABILITIES (these run automatically — do NOT describe them as interactive tools):\n"
        "- You poll your own calendar every 5 minutes for upcoming and recently ended meetings.\n"
        "- During active meetings you are monitoring, the backend injects relevant knowledge in real-time.\n"
        "- You process incoming email notifications in the background to detect meeting signals.\n\n"

        "ON-DEMAND CAPABILITIES (use the corresponding tool when asked):\n"
        "- When a user asks you to 'run a meeting report', 'generate a report', or 'process a meeting', "
        "call the run_meeting_report tool with the meeting subject or keyword.\n"
        "- The report pipeline fetches the transcript, extracts intelligence with the LLM, generates report cards, "
        "and enriches with MS Learn documentation.\n"
        "- When users ask for a richer/cooler report, include sentiment analysis, churn risk, customer satisfaction, "
        "and expansion-likelihood insights in your response summary from run_meeting_report results.\n"
        "- After run_meeting_report returns, if the user asked you to EMAIL the report, use your MCP email/mail tools "
        "to send the email_html content from the result. The report result includes a ready-to-send email_html field.\n"
        "- After run_meeting_report returns, if the user asked to post to Teams, use your MCP Teams tools.\n"
        "- If the user asks you to create a Word document and/or push a Dynamics note as part of running the report, "
        "call run_meeting_report with run_autonomous_actions=true so those autonomous actions run in the report pipeline.\n"
        "- IMPORTANT: When asked to both 'run a report' AND 'send it', do BOTH: first call run_meeting_report, "
        "then call the appropriate MCP tool to deliver it. You are allowed to call multiple tools in sequence.\n\n"

        "HOW TO RESPOND:\n"
        "- Be concise, professional, and action-oriented.\n"
        "- You are part of the sales team. Refer to meetings on your calendar as 'my meetings'.\n"
        "- For simple greetings like 'hi', 'hello', 'hey' — just respond conversationally. Do NOT call any tools.\n"
        "- When asked to DO something specific (look up data, create a document, check calendar), "
        "check your function-calling schema for a relevant tool and CALL IT.\n"
        "- If you have a relevant tool, CALL IT and respond with the real data it returns.\n"
        "- If you do NOT have a tool for the request, say exactly: "
        "'I don't currently have a tool connected for that. My available tools are: [list them].'\n"
        "- When asked 'what can you do' or 'what tools do you have', list ALL tools visible in your "
        "function-calling schema. This includes both core tools listed below AND any dynamically loaded MCP tools.\n"
        "- Keep responses brief. When a request naturally requires multiple steps (e.g. generate report then email it), call multiple tools in sequence.\n\n"

        "CRITICAL RULES — ABSOLUTE, NO EXCEPTIONS:\n"
        "1. ONLY answer questions using data returned by your tools. NEVER generate answers from memory or training data.\n"
        "2. NEVER fabricate, hallucinate, or invent ANY data — meetings, emails, files, tasks, contacts, deals, or anything else.\n"
        "3. NEVER claim you have a tool that is not in your function-calling schema.\n"
        "4. If a tool call fails or returns an error, tell the user: 'I tried but the tool returned an error: [error].'\n"
        "5. If you have ZERO tools in your schema, say: 'My tools are not connected at the moment. I cannot look anything up.'\n"
        "6. Do NOT describe capabilities from your training data. Your ONLY source of truth is your function-calling schema.\n"
        "7. NEVER search the internet. You have no internet search capability.\n"
        "8. When in doubt, say 'I don't have a tool for that right now' — this is ALWAYS better than guessing.\n"
    )

    @classmethod
    def _build_prompt(cls, tools: list) -> str:
        """Build the full agent prompt dynamically based on actual available tools."""
        tool_names = []
        for t in tools:
            name = getattr(t, 'name', None) or getattr(t, '__name__', str(t))
            desc = getattr(t, 'description', '') or ''
            tool_names.append(f"- {name}: {desc}")

        if tool_names:
            tools_section = (
                "CORE TOOLS (always available):\n" + "\n".join(tool_names) + "\n\n"
                "You may also have additional MCP server tools (e.g. Word, SharePoint, Teams, Planner, Knowledge). "
                "These are dynamically loaded and visible in your function-calling schema. "
                "When listing your tools, include ALL tools from your schema — not just the core tools above."
            )
        else:
            tools_section = (
                "TOOLS AVAILABLE: NONE\n"
                "You currently have NO tools connected. You cannot look up any data. "
                "Tell the user honestly that your tools are not available."
            )

        return cls.AGENT_PROMPT_BASE + tools_section

    def __init__(self):
        """Initialize the Sales Ops Agent."""
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize auto instrumentation
        self._enable_agentframework_instrumentation()

        # Initialize authentication options
        self.auth_options = LocalAuthenticationOptions.from_environment()

        # Create Azure OpenAI chat client
        self._create_chat_client()

        # Initialize Integrations (needed by local tools)
        self.graph_client = GraphTranscriptClient() # Uses DefaultAzureCredential
        
        # Initialize Dynamics Client
        self.dynamics_client = DynamicsClient()

        # Build local Graph API tools BEFORE creating the agent
        # so the dynamic prompt reflects the actual tools
        self._local_tools = self._build_local_tools()
        logger.info(f"✅ Built {len(self._local_tools)} local Graph API tools")

        # Create the agent with local tools and dynamic prompt
        self._create_agent()

        # Initialize MCP services
        self._initialize_services()

        # Initialize Handlers
        self.email_handler = EmailHandler()
        self.calendar_handler = CalendarHandler(self.graph_client)

        # Initialize Services
        self.meeting_processor = MeetingProcessor(self, self.graph_client)
        self.chat_service = TeamsChatService(self.graph_client)
        self.knowledge_service = LiveKnowledgeService(self.graph_client, self.chat_service)
        
        # Active Meetings Tracker (for live monitoring)
        self.active_meetings = {} # id -> subject

        # MCP setup state machine
        self.mcp_setup_state = "not_started"  # not_started | ready | degraded
        self.mcp_last_error: Optional[str] = None
        self._mcp_setup_attempts = 0
        self._mcp_next_retry_at = 0.0
        self._mcp_manifest_servers = self._load_manifest_server_names()
        self.mcp_telemetry = {
            "setup_attempts": 0,
            "setup_successes": 0,
            "setup_failures": 0,
            "last_error": None,
            "servers": {
                name: {
                    "successes": 0,
                    "failures": 0,
                    "last_error": None,
                }
                for name in self._mcp_manifest_servers
            },
        }

    # ... existing methods ...

    async def initialize(self):
        """Initialize the agent"""
        logger.info("Sales Ops Agent initialized")
        # Start background tasks
        asyncio.create_task(self.calendar_handler.start_polling_loop(self.handle_meeting_detected))
        asyncio.create_task(self.start_live_monitoring_loop())

    async def start_live_monitoring_loop(self):
        """Mock loop to monitor 'Active' meetings for knowledge injection."""
        while True:
            if self.active_meetings:
                logger.debug(f"👀 Monitoring {len(self.active_meetings)} active meetings for knowledge gaps...")
                for m_id, subject in list(self.active_meetings.items()):
                    await self.knowledge_service.monitor_meeting(m_id, subject)
            await asyncio.sleep(10) # Poll transcripts every 10s

    async def handle_meeting_detected(self, context: dict):
        """Callback when a meeting is detected by a handler."""
        trigger_type = context.get('type', 'ended')
        subject = context.get('subject')
        meeting_id = context.get('meeting_id')
        
        logger.info(f"🚨 Pipeline Triggered: {context.get('trigger')} [{trigger_type}] for '{subject}'")
        
        if trigger_type == 'upcoming':
            # Phase 4c: Send Intro Message
            if self.chat_service:
                await self.chat_service.send_intro_message(meeting_id, subject)
            # Add to active monitoring list
            self.active_meetings[meeting_id] = subject
            return
            
        if trigger_type == 'ended':
            # Stop monitoring
            if meeting_id in self.active_meetings:
                del self.active_meetings[meeting_id]
                
            # Phase 4: Pass to MeetingProcessor
            if self.meeting_processor:
                report = await self.meeting_processor.process_meeting(meeting_id, subject)
                # ... existing reporting logic ...

    def _create_chat_client(self):
        """Create the Azure OpenAI chat client"""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")

        if not endpoint or not deployment or not api_version:
             raise ValueError("Missing Azure OpenAI environment variables")

        # Use API key if provided, otherwise fall back to Azure Identity
        if api_key:
            from azure.core.credentials import AzureKeyCredential
            credential = AzureKeyCredential(api_key)
            logger.info("Using API key authentication for Azure OpenAI")
        else:
            credential = DefaultAzureCredential()
            logger.info("Using DefaultAzureCredential for Azure OpenAI")

        self.chat_client = AzureOpenAIChatClient(
            endpoint=endpoint,
            credential=credential,
            deployment_name=deployment,
            api_version=api_version,
        )
        # Limit tool-calling rounds to prevent runaway loops (default is 40)
        self.chat_client.function_invocation_configuration["max_iterations"] = 10
        logger.info("✅ AzureOpenAIChatClient created (max_iterations=10)")

    def _build_local_tools(self) -> list:
        """Build local FunctionTool wrappers around Graph API for calendar, etc.
        These work even when MCP servers are unavailable."""
        import json
        from datetime import datetime, timedelta, timezone

        async def get_my_calendar_today(**kwargs) -> str:
            """Get all meetings on the agent's calendar for today."""
            try:
                now = datetime.now(timezone.utc)
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                events = await self.graph_client.get_calendar_view(start, end)
                if not events:
                    return json.dumps({"meetings": [], "message": "No meetings on the calendar today."})
                meetings = []
                for e in events:
                    meetings.append({
                        "subject": e.get("subject", "(no subject)"),
                        "start": e.get("start", {}).get("dateTime", ""),
                        "end": e.get("end", {}).get("dateTime", ""),
                        "organizer": (e.get("organizer") or {}).get("emailAddress", {}).get("name", ""),
                        "response": (e.get("responseStatus") or {}).get("response", ""),
                    })
                return json.dumps({"meetings": meetings, "count": len(meetings)})
            except Exception as ex:
                logger.error(f"get_my_calendar_today failed: {ex}")
                return json.dumps({"error": str(ex)})

        async def get_my_calendar_range(start_date: str = "", end_date: str = "", **kwargs) -> str:
            """Get meetings on the agent's calendar for a date range.
            Args:
                start_date: Start date in YYYY-MM-DD format (defaults to today)
                end_date: End date in YYYY-MM-DD format (defaults to 7 days from start)
            """
            try:
                now = datetime.now(timezone.utc)
                if start_date:
                    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                else:
                    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                if end_date:
                    end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                else:
                    end = start + timedelta(days=7)
                events = await self.graph_client.get_calendar_view(start, end)
                if not events:
                    return json.dumps({"meetings": [], "message": f"No meetings between {start_date or 'today'} and {end_date or '7 days out'}."})
                meetings = []
                for e in events:
                    meetings.append({
                        "subject": e.get("subject", "(no subject)"),
                        "start": e.get("start", {}).get("dateTime", ""),
                        "end": e.get("end", {}).get("dateTime", ""),
                        "organizer": (e.get("organizer") or {}).get("emailAddress", {}).get("name", ""),
                        "response": (e.get("responseStatus") or {}).get("response", ""),
                    })
                return json.dumps({"meetings": meetings, "count": len(meetings)})
            except Exception as ex:
                logger.error(f"get_my_calendar_range failed: {ex}")
                return json.dumps({"error": str(ex)})

        async def get_upcoming_meetings(**kwargs) -> str:
            """Get meetings coming up in the next 24 hours."""
            try:
                now = datetime.now(timezone.utc)
                end = now + timedelta(hours=24)
                events = await self.graph_client.get_calendar_view(now, end)
                if not events:
                    return json.dumps({"meetings": [], "message": "No upcoming meetings in the next 24 hours."})
                meetings = []
                for e in events:
                    meetings.append({
                        "subject": e.get("subject", "(no subject)"),
                        "start": e.get("start", {}).get("dateTime", ""),
                        "end": e.get("end", {}).get("dateTime", ""),
                        "organizer": (e.get("organizer") or {}).get("emailAddress", {}).get("name", ""),
                        "response": (e.get("responseStatus") or {}).get("response", ""),
                    })
                return json.dumps({"meetings": meetings, "count": len(meetings)})
            except Exception as ex:
                logger.error(f"get_upcoming_meetings failed: {ex}")
                return json.dumps({"error": str(ex)})

        async def run_meeting_report(meeting_subject: str = "", run_autonomous_actions: bool = False, **kwargs) -> str:
            """Run the meeting intelligence report for a specific meeting. Finds the meeting on today's calendar by subject keyword, fetches the transcript, analyses it with LLM, generates a report card, and returns the results.
            Args:
                meeting_subject: A keyword or partial subject to match the meeting (e.g. 'Avon', 'Contoso review')
                run_autonomous_actions: When True, also run Word document creation and Dynamics account-note update actions.
            """
            try:
                if not meeting_subject:
                    return json.dumps({"error": "Please provide a meeting subject or keyword to search for."})

                # 1. Search today's calendar for a matching meeting
                now = datetime.now(timezone.utc)
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                events = await self.graph_client.get_calendar_view(start, end)

                if not events:
                    return json.dumps({"error": "No meetings found on the calendar today."})

                def normalize_subject(value: str) -> str:
                    normalized = (value or "").strip().strip('"\'`')
                    normalized = re.sub(r"\s+", " ", normalized)
                    return normalized.lower()

                # Find best match (case-insensitive, quote-insensitive substring)
                search_lower = normalize_subject(meeting_subject)
                matched_event = None
                for e in events:
                    subj = e.get("subject", "")
                    subj_lower = normalize_subject(subj)
                    if search_lower and (search_lower in subj_lower or subj_lower in search_lower):
                        matched_event = e
                        break

                if not matched_event:
                    available = [e.get("subject", "(no subject)") for e in events]
                    return json.dumps({
                        "error": f"No meeting matching '{meeting_subject}' found today.",
                        "available_meetings": available,
                    })

                meeting_id = matched_event.get("id", "")
                subject = matched_event.get("subject", meeting_subject)

                recipients: list[str] = []
                for attendee in (matched_event.get("attendees") or []):
                    address = ((attendee.get("emailAddress") or {}).get("address") or "").strip()
                    if address:
                        recipients.append(address)

                organizer_address = (
                    ((matched_event.get("organizer") or {}).get("emailAddress") or {}).get("address") or ""
                ).strip()
                if organizer_address:
                    recipients.append(organizer_address)

                deduped_recipients: list[str] = []
                seen_recipients: set[str] = set()
                for recipient in recipients:
                    key = recipient.lower()
                    if key in seen_recipients:
                        continue
                    seen_recipients.add(key)
                    deduped_recipients.append(recipient)

                logger.info(f"run_meeting_report: matched '{subject}' (id={meeting_id[:20]}...)")

                # 2. Run the meeting processing pipeline
                if not self.meeting_processor:
                    return json.dumps({"error": "Meeting processor is not initialized."})

                report = await self.meeting_processor.process_meeting(
                    meeting_id,
                    subject,
                    email_recipients=deduped_recipients,
                )

                if not report:
                    return json.dumps({"error": f"Meeting processor returned no results for '{subject}'."})

                if report.get("error"):
                    return json.dumps(
                        {
                            "error": report.get("error"),
                            "meeting": subject,
                            "meeting_id": meeting_id,
                        },
                        indent=2,
                    )

                # 3. Build a user-friendly summary
                raw = report.get("raw_data", {})

                raw_summary = raw.get("summary", "No summary available.")
                if isinstance(raw_summary, str):
                    summary_text = raw_summary
                elif isinstance(raw_summary, dict):
                    key_agreements = raw_summary.get("key_agreements")
                    if isinstance(key_agreements, list) and key_agreements:
                        summary_text = " ".join(
                            [str(item).strip() for item in key_agreements if str(item).strip()]
                        )
                    else:
                        summary_text = "; ".join(
                            [f"{k}: {v}" for k, v in raw_summary.items() if v not in (None, "", [], {})]
                        )
                    if not summary_text:
                        summary_text = json.dumps(raw_summary, ensure_ascii=False)
                elif isinstance(raw_summary, list):
                    summary_text = " ".join([str(item).strip() for item in raw_summary if str(item).strip()])
                else:
                    summary_text = str(raw_summary or "No summary available.")

                raw_tasks = raw.get("tasks", [])
                if not isinstance(raw_tasks, list):
                    raw_tasks = [raw_tasks]
                tasks = [
                    item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                    for item in raw_tasks
                    if item not in (None, "")
                ]

                raw_crm = raw.get("crm_updates", {})
                if isinstance(raw_crm, dict):
                    crm_updates = {
                        str(k): v
                        for k, v in raw_crm.items()
                        if v not in (None, "", [], {}, "None")
                    }
                else:
                    crm_updates = {}

                summary = {
                    "meeting": subject,
                    "summary": summary_text,
                    "tasks": tasks,
                    "crm_updates": crm_updates,
                    "email_sent": report.get("email_sent", False),
                    "email_recipients": report.get("email_recipients", []),
                    "teams_sent": report.get("teams_sent", False),
                }

                # Include the full HTML report so the agent can email it via MCP tools
                email_html = report.get("email_html", "")
                if email_html:
                    summary["email_html"] = email_html
                    summary["email_subject"] = f"Meeting Summary: {subject}"

                # Include learn references if present
                refs = report.get("learn_references", [])
                if refs:
                    summary["learn_references"] = [
                        {"title": r.get("title", ""), "url": r.get("url", "")}
                        for r in refs
                    ]

                if run_autonomous_actions:
                    autonomous = await self._run_autonomous_post_meeting_actions(
                        meeting_id=meeting_id,
                        subject=subject,
                        report=report,
                    )
                    summary["autonomous_actions"] = autonomous

                return json.dumps(summary, indent=2)

            except Exception as ex:
                logger.error(f"run_meeting_report failed: {ex}")
                import traceback
                logger.error(traceback.format_exc())
                return json.dumps({"error": str(ex)})

        async def graph_get_meeting_transcript(meeting_subject: str = "", meeting_id: str = "", **kwargs) -> str:
            """Fetch transcript content via Microsoft Graph directly.
            Args:
                meeting_subject: Optional subject/keyword to find today's meeting.
                meeting_id: Optional event/meeting id. If provided, it is used directly.
            """
            try:
                target_meeting_id = (meeting_id or "").strip()
                target_subject = (meeting_subject or "").strip()

                if not target_meeting_id:
                    from datetime import datetime, timedelta, timezone

                    now = datetime.now(timezone.utc)
                    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                    events = await self.graph_client.get_calendar_view(start, end)
                    if not events:
                        return json.dumps({"error": "No meetings found on the calendar today."})

                    if target_subject:
                        lowered = target_subject.lower()
                        match = next((e for e in events if lowered in (e.get("subject", "")).lower()), None)
                    else:
                        match = sorted(
                            events,
                            key=lambda e: (e.get("start") or {}).get("dateTime", ""),
                            reverse=True,
                        )[0]

                    if not match:
                        available = [e.get("subject", "(no subject)") for e in events]
                        return json.dumps({
                            "error": f"No meeting matching '{target_subject}' found today.",
                            "available_meetings": available,
                        })

                    target_meeting_id = match.get("id", "")
                    target_subject = match.get("subject", target_subject)

                transcript = await self.graph_client.get_transcript_content(target_meeting_id)
                if not transcript:
                    return json.dumps({
                        "error": "Transcript not available. Confirm Graph transcript permissions for this meeting.",
                        "meeting_id": target_meeting_id,
                    })

                return json.dumps(
                    {
                        "meeting_id": target_meeting_id,
                        "meeting_subject": target_subject,
                        "transcript": transcript,
                    },
                    indent=2,
                )
            except Exception as ex:
                logger.error(f"graph_get_meeting_transcript failed: {ex}")
                return json.dumps({"error": str(ex)})

        async def graph_send_email(to: str = "", subject: str = "", html_body: str = "", **kwargs) -> str:
            """Send email via Microsoft Graph directly.
            Args:
                to: Comma-separated recipient email addresses.
                subject: Email subject.
                html_body: HTML body content.
            """
            try:
                recipients = [item.strip() for item in (to or "").split(",") if item.strip()]
                if not recipients:
                    return json.dumps({"error": "Parameter 'to' is required (comma-separated recipients)."})
                if not subject.strip():
                    return json.dumps({"error": "Parameter 'subject' is required."})
                if not html_body.strip():
                    return json.dumps({"error": "Parameter 'html_body' is required."})

                sent = await self.graph_client.send_email(
                    to_recipients=recipients,
                    subject=subject,
                    html_body=html_body,
                )
                if not sent:
                    return json.dumps({
                        "ok": False,
                        "error": "Graph sendMail failed. Check Mail.Send application permission/admin consent.",
                    })

                return json.dumps({"ok": True, "recipients": recipients, "subject": subject})
            except Exception as ex:
                logger.error(f"graph_send_email failed: {ex}")
                return json.dumps({"error": str(ex)})

        async def graph_post_meeting_chat_message(meeting_id: str = "", content: str = "", **kwargs) -> str:
            """Post a message into a meeting chat via Microsoft Graph directly.
            Args:
                meeting_id: Online meeting id (or resolvable event id when available).
                content: HTML/text content to post.
            """
            try:
                if not meeting_id.strip():
                    return json.dumps({"error": "Parameter 'meeting_id' is required."})
                if not content.strip():
                    return json.dumps({"error": "Parameter 'content' is required."})

                sent = await self.graph_client.send_meeting_chat_message(
                    meeting_id=meeting_id,
                    content=content,
                    content_type="html",
                )
                if not sent:
                    return json.dumps({
                        "ok": False,
                        "error": "Graph chat post failed. Check OnlineMeetings/Chat permissions and thread access.",
                    })

                return json.dumps({"ok": True, "meeting_id": meeting_id})
            except Exception as ex:
                logger.error(f"graph_post_meeting_chat_message failed: {ex}")
                return json.dumps({"error": str(ex)})

        tools = [
            FunctionTool(
                func=get_my_calendar_today,
                name="get_my_calendar_today",
                description="Get all meetings on the agent's calendar for today. Always call this when asked about today's meetings.",
            ),
            FunctionTool(
                func=get_my_calendar_range,
                name="get_my_calendar_range",
                description="Get meetings on the agent's calendar for a specific date range. Parameters: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD).",
            ),
            FunctionTool(
                func=get_upcoming_meetings,
                name="get_upcoming_meetings",
                description="Get meetings coming up in the next 24 hours from the agent's calendar.",
            ),
            FunctionTool(
                func=run_meeting_report,
                name="run_meeting_report",
                description="Run the meeting intelligence report for a specific meeting. Finds the meeting on today's calendar, fetches the transcript, analyses it with the LLM, and returns a summary with tasks, CRM updates, and MS Learn references. Parameter: meeting_subject (keyword to match, e.g. 'Avon').",
            ),
            FunctionTool(
                func=graph_get_meeting_transcript,
                name="graph_get_meeting_transcript",
                description="Fallback Graph tool to fetch meeting transcript content directly. Parameters: meeting_subject (optional), meeting_id (optional).",
            ),
            FunctionTool(
                func=graph_send_email,
                name="graph_send_email",
                description="Fallback Graph tool to send email directly. Parameters: to (comma-separated), subject, html_body.",
            ),
            FunctionTool(
                func=graph_post_meeting_chat_message,
                name="graph_post_meeting_chat_message",
                description="Fallback Graph tool to post message directly to meeting chat. Parameters: meeting_id, content.",
            ),
        ]
        return tools

    def _create_agent(self):
        """Create the AgentFramework agent with initial configuration"""
        try:
            # Include local tools so the agent always has calendar access
            local_tools = getattr(self, '_local_tools', [])
            # Build prompt dynamically from actual tools
            prompt = self._build_prompt(local_tools)
            self.agent = FrameworkAgent(
                client=self.chat_client,
                instructions=prompt,
                tools=list(local_tools),
            )
            logger.info(f"✅ AgentFramework agent created with {len(local_tools)} tools")
            self._log_tool_inventory(local_tools, "initial")
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise

    def _log_tool_inventory(self, tools: list, phase: str):
        """Log the actual tool inventory for diagnostics."""
        names = [getattr(t, 'name', str(t)) for t in tools]
        logger.info(f"📋 Tool inventory ({phase}): {names}")

    def token_resolver(self, agent_id: str, tenant_id: str) -> str | None:
        """Token resolver for Agent 365 Observability"""
        try:
            cached_token = get_cached_agentic_token(tenant_id, agent_id)
            if not cached_token:
                logger.warning(f"No cached token for agent {agent_id}")
            return cached_token
        except Exception as e:
            logger.error(f"Error resolving token: {e}")
            return None

    def _enable_agentframework_instrumentation(self):
        """Enable AgentFramework instrumentation"""
        try:
            AgentFrameworkInstrumentor().instrument()
            logger.info("✅ Instrumentation enabled")
        except Exception as e:
            logger.warning(f"⚠️ Instrumentation failed: {e}")

    def _initialize_services(self):
        """Initialize MCP services"""
        try:
            self.tool_service = McpToolRegistrationService()
            logger.info("✅ MCP tool service initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ MCP tool service failed: {e}")
            self.tool_service = None
            self.mcp_setup_state = "degraded"
            self.mcp_last_error = f"MCP tool service init failed: {e}"

    def _load_manifest_server_names(self) -> list[str]:
        """Load configured MCP server names from ToolingManifest.json for telemetry baselines."""
        return [s.get("name") for s in self._load_manifest_servers() if s.get("name")]

    def _load_manifest_servers(self) -> list[dict]:
        """Load MCP server entries from ToolingManifest.json with normalized name/url fields."""
        manifest_path = os.path.join(os.getcwd(), "ToolingManifest.json")
        if not os.path.exists(manifest_path):
            return []

        try:
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)

            servers = []
            for item in manifest.get("mcpServers", []):
                server_name = item.get("mcpServerName") or item.get("mcpServerUniqueName")
                server_url = item.get("url", "")
                if server_name and server_url:
                    servers.append({"name": server_name, "url": server_url})
            return servers
        except Exception as ex:
            logger.warning(f"Failed to read ToolingManifest.json for MCP fallback: {ex}")
            return []

    def _ensure_server_telemetry(self, server_name: str):
        if server_name not in self.mcp_telemetry["servers"]:
            self.mcp_telemetry["servers"][server_name] = {
                "successes": 0,
                "failures": 0,
                "last_error": None,
            }

    def _record_server_success(self, server_name: str):
        self._ensure_server_telemetry(server_name)
        self.mcp_telemetry["servers"][server_name]["successes"] += 1
        self.mcp_telemetry["servers"][server_name]["last_error"] = None

    def _record_server_failure(self, server_name: str, reason: str):
        self._ensure_server_telemetry(server_name)
        self.mcp_telemetry["servers"][server_name]["failures"] += 1
        self.mcp_telemetry["servers"][server_name]["last_error"] = reason

    def _extract_server_names_from_error(self, reason: str) -> list[str]:
        """Extract MCP server names from error/log text (e.g. URLs ending in /agents/servers/<name>)."""
        if not reason:
            return []

        matches = re.findall(r"/agents/servers/([A-Za-z0-9_\-]+)", reason)
        unique = []
        for name in matches:
            if name not in unique:
                unique.append(name)
        return unique

    def _extract_tool_server_name(self, tool) -> Optional[str]:
        """Best-effort extraction of MCP server name from a tool instance."""
        for attr in [
            "server_name",
            "mcp_server_name",
            "_server_name",
            "_mcp_server_name",
            "server",
        ]:
            value = getattr(tool, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()

        tool_name = getattr(tool, "name", "")
        if isinstance(tool_name, str):
            parts = tool_name.split("__")
            if len(parts) >= 3 and parts[0] == "mcp":
                return parts[1]
        return None

    def _log_mcp_telemetry_snapshot(self, label: str):
        servers = self.mcp_telemetry.get("servers", {})
        summary = {
            "setup_attempts": self.mcp_telemetry.get("setup_attempts", 0),
            "setup_successes": self.mcp_telemetry.get("setup_successes", 0),
            "setup_failures": self.mcp_telemetry.get("setup_failures", 0),
            "state": self.mcp_setup_state,
            "last_error": self.mcp_last_error,
        }
        logger.info(f"MCP telemetry ({label}): {summary}")

        for server_name, data in sorted(servers.items()):
            logger.info(
                "MCP server telemetry: %s success=%s failure=%s last_error=%s",
                server_name,
                data.get("successes", 0),
                data.get("failures", 0),
                data.get("last_error"),
            )

    def get_mcp_health_snapshot(self) -> dict:
        """Return a compact MCP health snapshot for diagnostics and health endpoints."""
        servers = self.mcp_telemetry.get("servers", {})
        server_summary = {}
        for server_name, data in servers.items():
            successes = int(data.get("successes", 0) or 0)
            failures = int(data.get("failures", 0) or 0)
            last_error = data.get("last_error")
            if successes > 0 or failures > 0 or last_error:
                server_summary[server_name] = {
                    "successes": successes,
                    "failures": failures,
                    "last_error": last_error,
                }

        return {
            "state": self.mcp_setup_state,
            "setup_attempts": int(self.mcp_telemetry.get("setup_attempts", 0) or 0),
            "setup_successes": int(self.mcp_telemetry.get("setup_successes", 0) or 0),
            "setup_failures": int(self.mcp_telemetry.get("setup_failures", 0) or 0),
            "last_error": self.mcp_telemetry.get("last_error") or self.mcp_last_error,
            "next_retry_in_seconds": max(0, int(self._mcp_next_retry_at - time.monotonic())),
            "active_servers": server_summary,
        }

    def _schedule_mcp_retry(self, reason: str):
        """Mark MCP setup as degraded and schedule next retry with bounded backoff."""
        self.mcp_setup_state = "degraded"
        self.mcp_last_error = reason
        self.mcp_telemetry["setup_failures"] += 1
        self.mcp_telemetry["last_error"] = reason
        for server_name in self._extract_server_names_from_error(reason):
            self._record_server_failure(server_name, reason)
        delay = min(300, 15 * max(1, self._mcp_setup_attempts))
        self._mcp_next_retry_at = time.monotonic() + delay
        logger.warning(f"MCP setup degraded: {reason}. Next retry in {delay}s")
        self._log_mcp_telemetry_snapshot("degraded")

    async def _build_agent_with_manifest_mcp_tools(
        self,
        auth: Authorization,
        auth_handler_name: str,
        context: TurnContext,
    ) -> Optional[FrameworkAgent]:
        """Compatibility fallback: build MCP tools directly from ToolingManifest.json."""
        try:
            auth_token = None
            scopes = get_mcp_platform_authentication_scope()
            token_result = await auth.exchange_token(context, scopes, auth_handler_name)
            if token_result and token_result.token:
                auth_token = token_result.token

            if not auth_token:
                logger.warning("MCP compat fallback: token exchange returned no token")
                return None

            manifest_servers = self._load_manifest_servers()
            if not manifest_servers:
                logger.warning("MCP compat fallback: no servers found in ToolingManifest.json")
                return None

            mcp_tools = []
            headers = {
                Constants.Headers.AUTHORIZATION: f"{Constants.Headers.BEARER_PREFIX} {auth_token}"
            }
            for server in manifest_servers:
                server_name = server["name"]
                server_url = server["url"]
                try:
                    mcp_tool = MCPStreamableHTTPTool(
                        name=server_name,
                        url=server_url,
                        headers=headers,
                        description=f"MCP tools from {server_name}",
                    )
                    mcp_tools.append(mcp_tool)
                    logger.info(f"MCP compat fallback: added server {server_name} -> {server_url}")
                except Exception as ex:
                    logger.warning(f"MCP compat fallback: failed to add server {server_name}: {ex}")

            if not mcp_tools:
                logger.warning("MCP compat fallback: no MCP tools could be constructed")
                return None

            merged_tools = list(self._local_tools) + mcp_tools
            compatible_agent = FrameworkAgent(
                client=self.chat_client,
                instructions=self._build_prompt(merged_tools),
                tools=merged_tools,
            )
            logger.info(f"MCP compat fallback: built agent with {len(merged_tools)} total tools")
            return compatible_agent
        except Exception as ex:
            logger.warning(f"MCP compat fallback failed: {ex}")
            return None

    async def setup_mcp_servers(self, auth: Authorization, auth_handler_name: Optional[str], context: TurnContext):
        """Set up MCP server connections using the SDK's McpToolRegistrationService.
        
        The SDK handles:
        1. Token exchange for MCP platform scopes
        2. Server discovery from ToolingManifest.json (dev) or gateway (prod)
        3. Creating MCPStreamableHTTPTool instances with auth headers
        4. Tools auto-connect lazily during agent.run()
        """
        if self.mcp_setup_state == "ready":
            logger.info("MCP setup: state=ready, skipping")
            return

        now = time.monotonic()
        if now < self._mcp_next_retry_at:
            remaining = int(self._mcp_next_retry_at - now)
            logger.info(f"MCP setup: backoff active, retry in ~{remaining}s")
            return

        if not self.tool_service:
            self._schedule_mcp_retry("tool_service unavailable")
            return

        if not auth_handler_name:
            self._schedule_mcp_retry("auth handler missing")
            return

        try:
            self._mcp_setup_attempts += 1
            self.mcp_telemetry["setup_attempts"] += 1
            logger.info(f"MCP setup: calling add_tool_servers_to_agent (auth_handler={auth_handler_name})...")
            try:
                new_agent = await self.tool_service.add_tool_servers_to_agent(
                    chat_client=self.chat_client,
                    agent_instructions=self._build_prompt(self._local_tools),
                    initial_tools=list(self._local_tools),
                    auth=auth,
                    auth_handler_name=auth_handler_name,
                    turn_context=context,
                )
            except TypeError as type_error:
                if "missing 1 required positional argument: 'client'" in str(type_error):
                    logger.warning("MCP setup: SDK ChatAgent signature mismatch detected; using compatibility fallback")
                    new_agent = await self._build_agent_with_manifest_mcp_tools(
                        auth=auth,
                        auth_handler_name=auth_handler_name,
                        context=context,
                    )
                else:
                    raise
            if new_agent:
                self.agent = new_agent
                # Introspect agent to find tool list
                all_tools = self._get_agent_tools(new_agent)
                logger.info(f"MCP setup: SDK returned agent with {len(all_tools)} tools")
                for t in all_tools:
                    tname = getattr(t, 'name', str(t))
                    ttype = type(t).__name__
                    logger.info(f"  -> tool: {tname} ({ttype})")

                # ── Merge local tools back if the SDK dropped them ──
                mcp_tool_names = {getattr(t, 'name', str(t)) for t in all_tools}
                local_tool_names = {getattr(t, 'name', str(t)) for t in self._local_tools}
                missing = local_tool_names - mcp_tool_names
                if missing:
                    logger.warning(f"MCP setup: SDK dropped local tools {missing} – rebuilding agent with merged tools")
                    merged = list(all_tools) + list(self._local_tools)
                    self.agent = FrameworkAgent(
                        client=self.chat_client,
                        instructions=self._build_prompt(merged),
                        tools=merged,
                    )
                    final_tools = self._get_agent_tools(self.agent)
                    logger.info(f"MCP setup SUCCESS: merged agent now has {len(final_tools)} total tools")
                    for t in final_tools:
                        tname = getattr(t, 'name', str(t))
                        ttype = type(t).__name__
                        logger.info(f"  -> tool: {tname} ({ttype})")
                else:
                    logger.info(f"MCP setup SUCCESS: all {len(local_tool_names)} local tools preserved, {len(all_tools)} total")

                final_tools = self._get_agent_tools(self.agent)
                final_tool_names = {getattr(t, 'name', str(t)) for t in final_tools}
                discovered_servers = set()
                for tool in final_tools:
                    server_name = self._extract_tool_server_name(tool)
                    if server_name:
                        discovered_servers.add(server_name)
                for server_name in discovered_servers:
                    self._record_server_success(server_name)

                mcp_count = len(final_tool_names - local_tool_names)
                if mcp_count > 0:
                    self.mcp_setup_state = "ready"
                    self.mcp_last_error = None
                    self.mcp_telemetry["setup_successes"] += 1
                    self.mcp_telemetry["last_error"] = None
                    self._mcp_next_retry_at = 0.0
                    logger.info(f"MCP setup state=ready (discovered {mcp_count} MCP tool(s))")
                    self._log_mcp_telemetry_snapshot("ready")
                else:
                    self._schedule_mcp_retry("no MCP tools discovered after setup")
            else:
                self._schedule_mcp_retry("add_tool_servers_to_agent returned None")

        except Exception as e:
            logger.error(f"MCP setup FAILED with exception: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"MCP setup traceback:\n{traceback.format_exc()}")
            self._schedule_mcp_retry(f"{type(e).__name__}: {e}")

    async def initialize(self):
        """Initialize the agent"""
        logger.info("Sales Ops Agent initialized")
        # Start background tasks
        asyncio.create_task(self.calendar_handler.start_polling_loop(self.handle_meeting_detected))
        asyncio.create_task(self.start_live_monitoring_loop())

    async def start_live_monitoring_loop(self):
        """Mock loop to monitor 'Active' meetings for knowledge injection."""
        while True:
            if self.active_meetings:
                logger.debug(f"👀 Monitoring {len(self.active_meetings)} active meetings for knowledge gaps...")
                for m_id, subject in list(self.active_meetings.items()):
                    await self.knowledge_service.monitor_meeting(m_id, subject)
            await asyncio.sleep(10) # Poll transcripts every 10s

    async def handle_meeting_detected(self, context: dict):
        """Callback when a meeting is detected by a handler (Email or Calendar)."""
        trigger_type = context.get('type', 'ended') # 'ended' or 'upcoming'
        subject = context.get('subject')
        meeting_id = context.get('meeting_id')
        
        logger.info(f"🚨 Pipeline Triggered: {context.get('trigger')} [{trigger_type}] for '{subject}'")
        
        if trigger_type == 'upcoming':
            # Phase 4c: Send Intro Message
            if self.chat_service:
                await self.chat_service.send_intro_message(meeting_id, subject)
            # Add to active monitoring list
            self.active_meetings[meeting_id] = subject
            return

        if trigger_type == 'ended':
            # Stop monitoring
            if meeting_id in self.active_meetings:
                del self.active_meetings[meeting_id]

        # Phase 4: Pass to MeetingProcessor (Ended meetings)
        if self.meeting_processor:
            report = await self.meeting_processor.process_meeting(meeting_id, subject)
            if report:
                logger.info("Reports Generated for '%s'.", subject)

                # Log email delivery status
                if report.get("email_sent"):
                    logger.info("Email summary sent successfully for '%s'", subject)
                else:
                    logger.warning("Email summary was NOT sent for '%s'", subject)

                # Log Teams delivery status
                if report.get("teams_sent"):
                    logger.info("Teams summary posted successfully for '%s'", subject)
                else:
                    logger.warning("Teams summary was NOT posted for '%s'", subject)

                # Log MS Learn references
                refs = report.get("learn_references", [])
                if refs:
                    logger.info(
                        "Enriched with %d MS Learn reference(s) for '%s'",
                        len(refs), subject,
                    )

                if report.get("error"):
                    logger.warning(
                        "Skipping autonomous post-meeting actions for '%s' because report returned error: %s",
                        subject,
                        report.get("error"),
                    )
                    return

                autonomous = await self._run_autonomous_post_meeting_actions(
                    meeting_id=meeting_id,
                    subject=subject,
                    report=report,
                )

                word_status = autonomous.get("word_document", {})
                dynamics_status = autonomous.get("dynamics_note", {})

                logger.info(
                    "Autonomous post-meeting actions for '%s': word_success=%s, dynamics_success=%s",
                    subject,
                    word_status.get("success"),
                    dynamics_status.get("success"),
                )
            else:
                logger.warning("Meeting Processor returned no content for '%s'.", subject)

    @staticmethod
    def _coerce_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _normalize_tasks(self, raw_tasks: Any) -> List[str]:
        if raw_tasks in (None, ""):
            return []
        if not isinstance(raw_tasks, list):
            raw_tasks = [raw_tasks]
        return [self._coerce_text(item).strip() for item in raw_tasks if self._coerce_text(item).strip()]

    def _normalize_crm_updates(self, raw_crm: Any) -> Dict[str, str]:
        if not isinstance(raw_crm, dict):
            return {}
        updates: Dict[str, str] = {}
        for key, value in raw_crm.items():
            key_text = self._coerce_text(key).strip()
            value_text = self._coerce_text(value).strip()
            if key_text and value_text and value_text.lower() != "none":
                updates[key_text] = value_text
        return updates

    def _build_autonomous_meeting_payload(
        self,
        meeting_id: str,
        subject: str,
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = report.get("raw_data", {}) if isinstance(report, dict) else {}
        summary = self._coerce_text(raw.get("summary") or "No summary available.").strip()
        executive_summary = self._coerce_text(raw.get("executive_summary") or summary).strip()
        sentiment = self._coerce_text(raw.get("sentiment") or "unknown").strip()

        sentiment_timeline_raw = raw.get("sentiment_timeline")
        if sentiment_timeline_raw in (None, ""):
            sentiment_timeline = []
        elif isinstance(sentiment_timeline_raw, list):
            sentiment_timeline = [self._coerce_text(item).strip() for item in sentiment_timeline_raw if self._coerce_text(item).strip()]
        else:
            single = self._coerce_text(sentiment_timeline_raw).strip()
            sentiment_timeline = [single] if single else []

        churn_risk = raw.get("churn_risk")
        if isinstance(churn_risk, dict):
            churn_level = self._coerce_text(churn_risk.get("level") or "unknown").strip()
            churn_reason = self._coerce_text(churn_risk.get("reason") or "Not provided").strip()
        else:
            churn_level = self._coerce_text(churn_risk or "unknown").strip()
            churn_reason = "Not provided"

        customer_satisfaction = raw.get("customer_satisfaction")
        if isinstance(customer_satisfaction, dict):
            csat_score = self._coerce_text(customer_satisfaction.get("score") or "N/A").strip()
            csat_reason = self._coerce_text(customer_satisfaction.get("reason") or "Not provided").strip()
        else:
            csat_score = self._coerce_text(customer_satisfaction or "N/A").strip()
            csat_reason = "Not provided"

        expansion_likelihood = raw.get("expansion_likelihood")
        if isinstance(expansion_likelihood, dict):
            expansion_level = self._coerce_text(expansion_likelihood.get("level") or "unknown").strip()
            expansion_score = self._coerce_text(expansion_likelihood.get("score") or "N/A").strip()
            expansion_reason = self._coerce_text(expansion_likelihood.get("reason") or "Not provided").strip()
            expansion_products_raw = expansion_likelihood.get("products")
            if isinstance(expansion_products_raw, list):
                expansion_products = [
                    self._coerce_text(item).strip()
                    for item in expansion_products_raw
                    if self._coerce_text(item).strip()
                ]
            else:
                single_product = self._coerce_text(expansion_products_raw).strip()
                expansion_products = [single_product] if single_product else []
        else:
            expansion_level = self._coerce_text(expansion_likelihood or "unknown").strip()
            expansion_score = "N/A"
            expansion_reason = "Not provided"
            expansion_products = []

        tasks = self._normalize_tasks(raw.get("tasks", []))
        crm_updates = self._normalize_crm_updates(raw.get("crm_updates", {}))

        account_note = self._coerce_text(raw.get("account_note") or "").strip()
        if not account_note:
            note_lines = [
                f"Meeting: {subject}",
                f"Summary: {executive_summary}",
                f"Sentiment: {sentiment}",
                f"Churn Risk: {churn_level} ({churn_reason})",
                f"Customer Satisfaction: {csat_score} ({csat_reason})",
                f"Expansion Likelihood: {expansion_level} / {expansion_score} ({expansion_reason})",
            ]
            if expansion_products:
                note_lines.append("Potential Products: " + "; ".join(expansion_products[:5]))
            if tasks:
                note_lines.append("Tasks: " + "; ".join(tasks[:5]))
            if crm_updates:
                crm_text = "; ".join([f"{k}: {v}" for k, v in crm_updates.items()])
                note_lines.append("CRM Updates: " + crm_text)
            account_note = "\n".join(note_lines)

        return {
            "meeting_id": self._coerce_text(meeting_id).strip(),
            "subject": self._coerce_text(subject).strip() or "Unknown Meeting",
            "summary": summary,
            "executive_summary": executive_summary,
            "tasks": tasks,
            "crm_updates": crm_updates,
            "sentiment": sentiment,
            "sentiment_timeline": sentiment_timeline,
            "churn_risk": {"level": churn_level, "reason": churn_reason},
            "customer_satisfaction": {"score": csat_score, "reason": csat_reason},
            "expansion_likelihood": {
                "level": expansion_level,
                "score": expansion_score,
                "reason": expansion_reason,
                "products": expansion_products,
            },
            "account_note": account_note,
            "learn_references": report.get("learn_references", []) if isinstance(report, dict) else [],
        }

    def _render_word_document_markdown(self, payload: Dict[str, Any]) -> str:
        subject = payload.get("subject", "Unknown Meeting")
        meeting_id = payload.get("meeting_id", "")
        summary = payload.get("summary", "")
        executive_summary = payload.get("executive_summary", "")
        sentiment = payload.get("sentiment", "unknown")
        churn = payload.get("churn_risk", {}) or {}
        csat = payload.get("customer_satisfaction", {}) or {}
        expansion = payload.get("expansion_likelihood", {}) or {}
        tasks = payload.get("tasks", []) or []
        crm_updates = payload.get("crm_updates", {}) or {}
        sentiment_timeline = payload.get("sentiment_timeline", []) or []

        lines = [
            f"# Post-Meeting Report: {subject}",
            "",
            f"- Meeting ID: {meeting_id}",
            f"- Sentiment: {sentiment}",
            f"- Churn Risk: {churn.get('level', 'unknown')} ({churn.get('reason', 'Not provided')})",
            f"- Customer Satisfaction: {csat.get('score', 'N/A')} ({csat.get('reason', 'Not provided')})",
            f"- Expansion Likelihood: {expansion.get('level', 'unknown')} / {expansion.get('score', 'N/A')} ({expansion.get('reason', 'Not provided')})",
            "",
            "## Executive Summary",
            executive_summary or summary or "Not available",
            "",
            "## Key Summary",
            summary or "Not available",
            "",
            "## Action Items",
        ]

        if tasks:
            lines.extend([f"- {task}" for task in tasks])
        else:
            lines.append("- No action items identified")

        lines.extend(["", "## CRM Updates"])
        if crm_updates:
            lines.extend([f"- {key}: {value}" for key, value in crm_updates.items()])
        else:
            lines.append("- No CRM updates identified")

        lines.extend(["", "## Sentiment Timeline"])
        if sentiment_timeline:
            lines.extend([f"- {item}" for item in sentiment_timeline])
        else:
            lines.append("- No sentiment timeline provided")

        expansion_products = expansion.get("products", [])
        lines.extend(["", "## Expansion Product Opportunities"])
        if isinstance(expansion_products, list) and expansion_products:
            lines.extend([f"- {self._coerce_text(item)}" for item in expansion_products])
        else:
            lines.append("- No expansion products identified")

        refs = payload.get("learn_references", []) or []
        lines.extend(["", "## Related Microsoft Documentation"])
        if isinstance(refs, list) and refs:
            for ref in refs:
                if isinstance(ref, dict):
                    title = self._coerce_text(ref.get("title") or "Reference").strip()
                    url = self._coerce_text(ref.get("url") or "").strip()
                    if url:
                        lines.append(f"- {title}: {url}")
        else:
            lines.append("- No related documentation links")

        return "\n".join(lines).strip()

    async def _run_word_mcp_document_creation(
        self,
        subject: str,
        markdown_content: str,
    ) -> Dict[str, Any]:
        tool_names = [getattr(tool, "name", "") for tool in self._get_agent_tools()]
        has_word = any("word" in (name or "").lower() for name in tool_names)
        if not has_word:
            return {
                "attempted": False,
                "success": False,
                "message": "Word MCP tool not active in current runtime toolset",
            }

        instruction = (
            "Use only your Word MCP tools to create a new Word document for this meeting report. "
            "Title the document with the meeting subject, populate it with the provided markdown content, "
            "and return a compact JSON object with keys: success, document_name, document_id_or_url, notes.\n\n"
            f"Meeting subject: {subject}\n"
            "Markdown content:\n"
            f"{markdown_content}"
        )

        try:
            result = await asyncio.wait_for(self.agent.run(instruction), timeout=90)
            response_text = self._extract_result(result)
            lowered = (response_text or "").lower()
            success = not any(token in lowered for token in (
                "tool returned an error",
                "don't currently have a tool connected",
                "failed",
                "error",
            ))
            return {
                "attempted": True,
                "success": success,
                "response": response_text,
            }
        except Exception as ex:
            logger.warning("Autonomous Word MCP document creation failed for '%s': %s", subject, ex)
            return {
                "attempted": True,
                "success": False,
                "error": str(ex),
            }

    async def _run_dynamics_account_note_update(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        subject = payload.get("subject", "Unknown Meeting")
        account_note = payload.get("account_note", "")
        crm_updates = payload.get("crm_updates", {})
        tool_names = [getattr(tool, "name", "") for tool in self._get_agent_tools()]
        has_dynamics_mcp = any(
            any(marker in (name or "").lower() for marker in ("dataverse", "d365", "dynamics"))
            for name in tool_names
        )

        if has_dynamics_mcp:
            instruction = (
                "Use only your Dynamics/Dataverse MCP tools to append a note to the relevant account record. "
                "Use the meeting context and CRM updates below. "
                "Return compact JSON with keys: success, account, record_id, operation.\n\n"
                f"Meeting subject: {subject}\n"
                f"Meeting id: {payload.get('meeting_id', '')}\n"
                f"CRM updates: {json.dumps(crm_updates, ensure_ascii=False)}\n"
                "Account note text:\n"
                f"{account_note}"
            )
            try:
                result = await asyncio.wait_for(self.agent.run(instruction), timeout=90)
                response_text = self._extract_result(result)
                lowered = (response_text or "").lower()
                success = not any(token in lowered for token in (
                    "tool returned an error",
                    "don't currently have a tool connected",
                    "failed",
                    "error",
                ))
                if success:
                    return {
                        "attempted": True,
                        "success": True,
                        "mode": "mcp",
                        "response": response_text,
                    }
                logger.warning(
                    "Dynamics MCP note update returned non-success response for '%s': %s",
                    subject,
                    response_text,
                )
            except Exception as ex:
                logger.warning("Dynamics MCP note update failed for '%s': %s", subject, ex)

        try:
            fallback_ok = await self.dynamics_client.append_account_note(
                account_reference=subject,
                note_text=account_note,
                metadata={
                    "meeting_id": payload.get("meeting_id", ""),
                    "crm_updates": crm_updates,
                },
            )
            return {
                "attempted": True,
                "success": bool(fallback_ok),
                "mode": "stub-fallback",
            }
        except Exception as ex:
            logger.error("Fallback Dynamics note update failed for '%s': %s", subject, ex)
            return {
                "attempted": True,
                "success": False,
                "mode": "stub-fallback",
                "error": str(ex),
            }

    async def _run_autonomous_post_meeting_actions(
        self,
        meeting_id: str,
        subject: str,
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = self._build_autonomous_meeting_payload(
            meeting_id=meeting_id,
            subject=subject,
            report=report,
        )
        markdown = self._render_word_document_markdown(payload)

        word_result = await self._run_word_mcp_document_creation(
            subject=payload.get("subject", subject),
            markdown_content=markdown,
        )
        dynamics_result = await self._run_dynamics_account_note_update(payload)

        result = {
            "word_document": word_result,
            "dynamics_note": dynamics_result,
            "payload": {
                "meeting_id": payload.get("meeting_id", ""),
                "subject": payload.get("subject", ""),
                "sentiment": payload.get("sentiment", "unknown"),
                "churn_risk": payload.get("churn_risk", {}),
                "customer_satisfaction": payload.get("customer_satisfaction", {}),
            },
        }
        report["autonomous_actions"] = result
        return result

    def _get_agent_tools(self, agent=None) -> list:
        """Introspect agent to find its tool list, checking multiple possible attributes."""
        a = agent or self.agent
        # Try common attribute names
        for attr in ['_tools', 'tools', '_function_tools', 'mcp_tools']:
            val = getattr(a, attr, None)
            if val and isinstance(val, (list, tuple)):
                return list(val)
        # Try default_options dict
        opts = getattr(a, 'default_options', None)
        if opts and isinstance(opts, dict):
            tools = opts.get('tools', [])
            if tools:
                return list(tools)
        # Try _default_options
        opts2 = getattr(a, '_default_options', None)
        if opts2 and isinstance(opts2, dict):
            tools = opts2.get('tools', [])
            if tools:
                return list(tools)
        return []

    def _get_local_tool(self, tool_name: str):
        """Return a local FunctionTool by name."""
        for tool in getattr(self, "_local_tools", []):
            if getattr(tool, "name", "") == tool_name:
                return tool
        return None

    async def _invoke_local_tool(self, tool_name: str, **kwargs) -> str:
        """Invoke a local FunctionTool directly (without LLM orchestration)."""
        tool = self._get_local_tool(tool_name)
        if tool is None:
            return json.dumps({"error": f"Local tool '{tool_name}' is not available."})

        tool_func = None
        for attr_name in ("func", "_func", "function", "handler", "_function"):
            candidate = getattr(tool, attr_name, None)
            if callable(candidate):
                tool_func = candidate
                break

        if tool_func is None and callable(tool):
            tool_func = tool

        if tool_func is None:
            return json.dumps({"error": f"Local tool '{tool_name}' cannot be invoked."})

        result = tool_func(**kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result if isinstance(result, str) else json.dumps(result)

    def _format_calendar_today_response(self, raw_payload: str) -> str:
        try:
            data = json.loads(raw_payload)
        except Exception:
            return raw_payload

        meetings = data.get("meetings", []) if isinstance(data, dict) else []
        if not meetings:
            return "No meetings on the calendar today."

        lines = ["Today’s meetings:"]
        for item in meetings:
            subject = item.get("subject", "(no subject)")
            start = item.get("start", "")
            end = item.get("end", "")
            lines.append(f"- {subject} ({start} to {end})")
        return "\n".join(lines)

    def _format_meeting_report_response(self, raw_payload: str) -> str:
        try:
            data = json.loads(raw_payload)
        except Exception:
            return raw_payload

        if not isinstance(data, dict):
            return raw_payload

        if data.get("error"):
            return f"run_meeting_report failed: {data.get('error')}"

        meeting = data.get("meeting", "(unknown meeting)")
        summary = data.get("summary", "No summary available.")
        tasks = data.get("tasks", []) or []
        crm = data.get("crm_updates", {}) or {}

        lines = [f"Meeting report: {meeting}", f"Summary: {summary}"]
        if tasks:
            lines.append("Tasks:")
            for task in tasks[:5]:
                lines.append(f"- {task}")
        if crm:
            lines.append("CRM updates:")
            for key, value in crm.items():
                lines.append(f"- {key}: {value}")

        refs = data.get("learn_references", []) or []
        if refs:
            lines.append("Learn references:")
            for ref in refs[:3]:
                lines.append(f"- {ref.get('title', 'Reference')}: {ref.get('url', '')}")

        return "\n".join(lines)

    async def _run_report_for_most_recent_meeting(self) -> str:
        """Find the most recent meeting and run local report generation for it."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        events = await self.graph_client.get_calendar_view(start, now)
        if not events:
            return json.dumps({"error": "No meetings found in the last 7 days."})

        def parse_event_start(event: dict) -> datetime:
            raw = (event.get("start") or {}).get("dateTime") or ""
            if not raw:
                return datetime.min.replace(tzinfo=timezone.utc)
            normalized = raw.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)

        recent = sorted(events, key=parse_event_start, reverse=True)[0]
        subject = recent.get("subject", "").strip()
        if not subject:
            return json.dumps({"error": "Most recent meeting has no subject to match for report generation."})

        logger.info("process_user_message: local fast-path run_meeting_report for most recent meeting '%s'", subject)
        return await self._invoke_local_tool("run_meeting_report", meeting_subject=subject)

    async def process_user_message(
        self, message: str, auth: Authorization, auth_handler_name: Optional[str], context: TurnContext
    ) -> str:
        """Process user message using the AgentFramework SDK"""
        try:
            message_text = (message or "").strip().lower()
            if message_text in {"hi", "hello", "hey", "hiya", "good morning", "good afternoon", "good evening"}:
                return "Hi — I’m online and ready. How can I help?"

            # Fast-path inventory response to avoid unnecessary MCP tool execution
            tool_inventory_triggers = (
                "what tools do you have",
                "what can you do",
                "which tools",
                "list tools",
                "available tools",
            )
            if any(trigger in message_text for trigger in tool_inventory_triggers):
                try:
                    await asyncio.wait_for(
                        self.setup_mcp_servers(auth, auth_handler_name, context),
                        timeout=20,
                    )
                except asyncio.TimeoutError:
                    logger.warning("tool-inventory fast-path: MCP setup timed out after 20s; returning current tool inventory")
                except Exception as ex:
                    logger.warning(f"tool-inventory fast-path: MCP setup failed: {ex}")

                local_tool_names = [getattr(t, 'name', str(t)) for t in getattr(self, '_local_tools', [])]
                runtime_tool_names = [getattr(t, 'name', str(t)) for t in self._get_agent_tools()]

                # Report both local core tools and active runtime tools (MCP), because
                # current SDK/framework combinations may drop FunctionTool entries when MCP plugins are attached.
                tool_names = sorted(set(local_tool_names + runtime_tool_names))
                if not tool_names:
                    return "My tools are not connected at the moment. I cannot look anything up."
                return "Available tools: " + ", ".join(sorted(tool_names))

            # Fast-path local meeting report requests to avoid MCP timeout/400 stalls.
            if "run_meeting_report" in message_text or (
                "meeting report" in message_text
                and any(verb in message_text for verb in ("run", "generate", "process", "create"))
            ):
                try:
                    if "most recent meeting" in message_text or "latest meeting" in message_text:
                        local_result = await self._run_report_for_most_recent_meeting()
                    else:
                        subject_match = re.search(r"(?:for|about)\s+(.+)$", message.strip(), flags=re.IGNORECASE)
                        subject = subject_match.group(1).strip(" .\"'`") if subject_match else ""
                        local_result = await self._invoke_local_tool(
                            "run_meeting_report",
                            meeting_subject=subject,
                        )
                    return self._format_meeting_report_response(local_result)
                except Exception as ex:
                    logger.error(f"process_user_message: local meeting report fast-path failed: {ex}")
                    return json.dumps({"error": f"run_meeting_report failed: {ex}"})

            meeting_list_triggers = (
                "what meetings do you have",
                "what meetings are on my calendar",
                "show my meetings",
                "list my meetings",
                "what meetings today",
            )
            if any(trigger in message_text for trigger in meeting_list_triggers):
                try:
                    local_result = await self._invoke_local_tool("get_my_calendar_today")
                    return self._format_calendar_today_response(local_result)
                except Exception as ex:
                    logger.error(f"process_user_message: local meeting list fast-path failed: {ex}")
                    return json.dumps({"error": f"get_my_calendar_today failed: {ex}"})

            logger.info(
                "process_user_message: mcp_state=%s, auth_handler=%s",
                self.mcp_setup_state,
                auth_handler_name,
            )
            await self.setup_mcp_servers(auth, auth_handler_name, context)
            tools = self._get_agent_tools()
            tool_names = [getattr(t, 'name', str(t)) for t in tools]
            logger.info(f"process_user_message: running agent with {len(tools)} tools: {tool_names}")
            # Timeout to prevent hanging if MCP tools fail to connect
            try:
                result = await asyncio.wait_for(self.agent.run(message), timeout=90)
            except asyncio.TimeoutError:
                logger.error("process_user_message: agent.run() TIMED OUT after 90s")
                # Degrade to local-only mode so subsequent turns don't repeatedly hang
                self._schedule_mcp_retry("agent.run timeout - degrading to local tools only")
                self.agent = FrameworkAgent(
                    client=self.chat_client,
                    instructions=self._build_prompt(self._local_tools),
                    tools=list(self._local_tools),
                )
                return "Sorry, MCP tools timed out. I switched to local-only tools for now — please try again."
            response = self._extract_result(result) or "I couldn't process your request at this time."
            logger.info(f"process_user_message: response length={len(response)}")
            return response
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            logger.error(f"process_user_message traceback:\n{traceback.format_exc()}")
            return f"Sorry, I encountered an error: {str(e)}"

    async def handle_agent_notification_activity(
        self, notification_activity, auth: Authorization, auth_handler_name: Optional[str], context: TurnContext
    ) -> str:
        """Handle agent notification activities"""
        try:
            notification_type = notification_activity.notification_type
            logger.info(f"📬 Processing notification: {notification_type}")

            await self.setup_mcp_servers(auth, auth_handler_name, context)

            if notification_type == NotificationTypes.EMAIL_NOTIFICATION:
                # Use EmailHandler to check for Meeting Detection
                meeting_context = await self.email_handler.process_email(notification_activity)
                if meeting_context:
                    await self.handle_meeting_detected(meeting_context)
                    return "Meeting detected and processing started."

                # Fallback: Standard Email Reply
                if not hasattr(notification_activity, "email") or not notification_activity.email:
                    return "I could not find the email notification details."

                email = notification_activity.email
                email_body = getattr(email, "html_body", "") or getattr(email, "body", "")
                message = f"You have received the following email. Please follow any instructions in it. {email_body}"

                result = await self.agent.run(message)
                return self._extract_result(result) or "Email processed."
            
            else:
                notification_message = notification_activity.text or f"Notification received: {notification_type}"
                result = await self.agent.run(notification_message)
                return self._extract_result(result) or "Notification processed."

        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            return f"Error: {str(e)}"

    def _extract_result(self, result) -> str:
        """Extract text content from agent result"""
        if not result:
            return ""
        if hasattr(result, "contents"):
            return str(result.contents)
        elif hasattr(result, "text"):
            return str(result.text)
        elif hasattr(result, "content"):
            return str(result.content)
        else:
            return str(result)

    async def cleanup(self) -> None:
        """Clean up agent resources"""
        try:
            if hasattr(self, "tool_service") and self.tool_service:
                await self.tool_service.cleanup()
            logger.info("Agent cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
