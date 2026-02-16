# Copyright (c) Microsoft. All rights reserved.

"""
Teams Chat Service.
Handles sending interactive messages to Teams threads (e.g., introductions, summaries).
"""

import logging
from typing import Optional

# Integration Client for Graph calls
try:
    from integrations.graph_transcript_client import GraphTranscriptClient
except ImportError:
    from src.integrations.graph_transcript_client import GraphTranscriptClient

logger = logging.getLogger(__name__)


class TeamsChatService:
    """
    Service for sending messages to Teams meeting chats via the Graph API.
    """

    def __init__(self, graph_client: GraphTranscriptClient):
        self.graph_client = graph_client

    async def send_intro_message(self, meeting_id: str, subject: str) -> bool:
        """
        Send a friendly introduction message to the meeting chat.

        Args:
            meeting_id: The ID of the online meeting.
            subject: The meeting subject (for context / logging).

        Returns:
            True if sent successfully, False otherwise.
        """
        logger.info(f"Sending Intro Message to Meeting: '{subject}' ({meeting_id})")

        message_content = (
            "<p><strong>Hi everyone!</strong></p>"
            "<p>I'm your <strong>Sales Ops Assistant</strong>. I'll be joining this meeting to:</p>"
            "<ul>"
            "<li>Take notes</li>"
            "<li>Capture action items</li>"
            "<li>Identify updates for <strong>Dynamics 365</strong></li>"
            "</ul>"
            "<p>Feel free to clarify any details during the call. See you soon!</p>"
        )

        sent = await self.graph_client.send_meeting_chat_message(
            meeting_id, message_content, content_type="html"
        )
        if sent:
            logger.info("Intro message sent to '%s'", subject)
        else:
            logger.warning("Failed to send intro message to '%s'", subject)
        return sent

    async def send_summary_message(
        self,
        meeting_id: str,
        subject: str,
        summary_html: str,
    ) -> bool:
        """
        Post a meeting summary card/message into the meeting chat.

        Args:
            meeting_id: The online-meeting ID.
            subject: Meeting subject for logging.
            summary_html: HTML content of the summary to post.

        Returns:
            True if posted successfully, False otherwise.
        """
        logger.info(f"Posting summary to meeting chat: '{subject}' ({meeting_id})")

        # Wrap in a styled container so it renders nicely in Teams
        content = (
            f"<div>"
            f"<h2>Meeting Summary: {subject}</h2>"
            f"{summary_html}"
            f"<p><em>Generated automatically by SalesOpsBot.</em></p>"
            f"</div>"
        )

        sent = await self.graph_client.send_meeting_chat_message(
            meeting_id, content, content_type="html"
        )
        if sent:
            logger.info("Summary posted to meeting chat for '%s'", subject)
        else:
            logger.warning("Failed to post summary to meeting chat for '%s'", subject)
        return sent

    async def send_knowledge_message(
        self,
        meeting_id: str,
        title: str,
        summary: str,
        url: str,
    ) -> bool:
        """
        Post a knowledge-injection message (MS Learn link) into the meeting chat.

        Args:
            meeting_id: The online-meeting ID.
            title: Title of the documentation article.
            summary: Short description / excerpt.
            url: Full URL to the documentation.

        Returns:
            True if sent, False otherwise.
        """
        content = (
            f"<p><strong>Knowledge Injection</strong></p>"
            f"<p>I heard you ask about <em>{title}</em>.</p>"
            f"<blockquote>{summary}</blockquote>"
            f'<p><a href="{url}">Read more on Microsoft Learn</a></p>'
        )

        return await self.graph_client.send_meeting_chat_message(
            meeting_id, content, content_type="html"
        )
