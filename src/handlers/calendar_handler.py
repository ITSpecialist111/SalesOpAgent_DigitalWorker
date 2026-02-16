# Copyright (c) Microsoft. All rights reserved.

"""
Calendar Handler for Background Polling.
Polls the agent's own calendar via Microsoft Graph to:
  1. Detect recently ended meetings and trigger transcript processing.
  2. Detect upcoming meetings and send intro messages.
  3. Accept pending meeting invitations automatically.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Set, Dict, Any, Callable, Optional

from integrations.graph_transcript_client import GraphTranscriptClient

logger = logging.getLogger(__name__)


class CalendarHandler:
    """
    Polls the agent's calendar via Microsoft Graph.
    """

    def __init__(self, graph_client: GraphTranscriptClient):
        self.graph_client = graph_client
        self.processed_meeting_ids: Set[str] = set()
        self.polling_interval_seconds = 300  # 5 minutes

    async def start_polling_loop(self, callback: Callable):
        """
        Start the background polling loop.

        Args:
            callback: Async function to call when a new meeting is found.
                      Signature: await callback(meeting_context)
        """
        logger.info("Starting Calendar Polling Loop (interval=%ds)", self.polling_interval_seconds)
        while True:
            try:
                await self._accept_pending_invitations()
                await self.check_calendar(callback)
            except Exception as e:
                logger.error("Error in calendar polling: %s", e)

            await asyncio.sleep(self.polling_interval_seconds)

    # ------------------------------------------------------------------
    # Calendar view query
    # ------------------------------------------------------------------
    async def check_calendar(self, callback: Callable):
        """
        Check for recently ended and upcoming meetings.
        """
        now = datetime.now(timezone.utc)

        # 1. ENDED Meetings (look back 15 mins)
        ended_start = now - timedelta(minutes=15)
        ended_end = now

        # 2. UPCOMING Meetings (look ahead 5 mins)
        upcoming_start = now
        upcoming_end = now + timedelta(minutes=5)

        logger.info("Polling calendar...")

        try:
            ended_events = await self.graph_client.get_calendar_view(ended_start, ended_end)
        except Exception as e:
            logger.warning("Failed to fetch ended events: %s", e)
            ended_events = []

        try:
            upcoming_events = await self.graph_client.get_calendar_view(upcoming_start, upcoming_end)
        except Exception as e:
            logger.warning("Failed to fetch upcoming events: %s", e)
            upcoming_events = []

        # Process ended meetings
        for event in ended_events:
            event_id = event.get("id", "")
            unique_key = f"{event_id}_ended"
            if unique_key in self.processed_meeting_ids:
                continue
            # Only process events the agent actually accepted
            response_status = (event.get("responseStatus") or {}).get("response", "")
            if response_status not in ("accepted", "organizer"):
                continue
            subject = event.get("subject", "(no subject)")
            logger.info("Found ended meeting: %s", subject)
            self.processed_meeting_ids.add(unique_key)
            await callback({
                "trigger": "calendar_poll",
                "type": "ended",
                "meeting_id": event_id,
                "subject": subject,
            })

        # Process upcoming meetings
        for event in upcoming_events:
            event_id = event.get("id", "")
            unique_key = f"{event_id}_upcoming"
            if unique_key in self.processed_meeting_ids:
                continue
            response_status = (event.get("responseStatus") or {}).get("response", "")
            if response_status not in ("accepted", "organizer"):
                continue
            subject = event.get("subject", "(no subject)")
            logger.info("Found upcoming meeting: %s", subject)
            self.processed_meeting_ids.add(unique_key)
            await callback({
                "trigger": "calendar_poll",
                "type": "upcoming",
                "meeting_id": event_id,
                "subject": subject,
            })

    # ------------------------------------------------------------------
    # Auto-accept meeting invitations
    # ------------------------------------------------------------------
    async def _accept_pending_invitations(self):
        """
        Find calendar events where the agent has not yet responded
        and accept them automatically.
        """
        try:
            pending = await self.graph_client.get_pending_invitations()
            if not pending:
                return

            for event in pending:
                event_id = event.get("id", "")
                subject = event.get("subject", "(no subject)")
                logger.info("Auto-accepting meeting invitation: %s", subject)
                try:
                    await self.graph_client.accept_event(event_id)
                    logger.info("Accepted: %s", subject)
                except Exception as e:
                    logger.warning("Failed to accept '%s': %s", subject, e)

        except Exception as e:
            logger.warning("Failed to fetch pending invitations: %s", e)
