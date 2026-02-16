# Copyright (c) Microsoft. All rights reserved.

"""
Live Knowledge Service.
Monitors transcript streams and injects helpful MS Learn links.
"""

import logging
import re
from typing import Dict, Set

try:
    from services.teams_chat_service import TeamsChatService
    from integrations.graph_transcript_client import GraphTranscriptClient
    from integrations.ms_learn_client import MsLearnClient
except ImportError:
    from src.services.teams_chat_service import TeamsChatService
    from src.integrations.graph_transcript_client import GraphTranscriptClient
    from src.integrations.ms_learn_client import MsLearnClient

logger = logging.getLogger(__name__)


class LiveKnowledgeService:
    """
    Monitors active meetings for knowledge gaps.
    """

    def __init__(self, graph_client: GraphTranscriptClient, chat_service: TeamsChatService):
        self.graph_client = graph_client
        self.chat_service = chat_service
        self.learn_client = MsLearnClient()
        
        # Track processed transcript lines per meeting to avoid duplicate posts
        # Key: meeting_id -> Set[processed_content_hash/index]
        self.processed_cursors: Dict[str, int] = {}
        
        # Simple keywords to trigger search
        # Format: "keyword": "min_length_query"
        self.triggers = {
            r"what is (.*)": "definition",
            r"how do i (.*)": "howto",
            r"tell me about (.*)": "info"
        }

    async def monitor_meeting(self, meeting_id: str, subject: str):
        """
        Polls the transcript for the given meeting and injects knowledge.
        Should be called periodically during the meeting.
        """
        # 1. Fetch latest transcript
        # Note: In a real "Live" system, we'd use delta tokens.
        # Here we just fetch the whole thing and check the length.
        transcript = await self.graph_client.get_transcript_content(meeting_id)
        
        if not transcript:
            return

        # Split into lines/sentences
        lines = transcript.split('\n')
        current_length = len(lines)
        last_processed = self.processed_cursors.get(meeting_id, 0)
        
        if current_length <= last_processed:
            return # No new content

        # Process new lines
        new_lines = lines[last_processed:]
        logger.info(f"👂 Heard {len(new_lines)} new lines in '{subject}'")
        
        for line in new_lines:
            await self.process_line(meeting_id, line)

        # Update cursor
        self.processed_cursors[meeting_id] = current_length

    async def process_line(self, meeting_id: str, text: str):
        """
        Analyze a single line of speech for knowledge triggers.
        """
        text_clean = text.lower().strip()
        
        # Simple Regex Trigger Check
        for pattern, type_ in self.triggers.items():
            match = re.search(pattern, text_clean)
            if match:
                query = match.group(0) # The whole matched phrase e.g. "what is microsoft 365"
                
                # Filter: Ensure it's about Microsoft tech (heuristic)
                # To prevent spamming for "what is the time"
                if any(x in query for x in ["microsoft", "azure", "copilot", "teams", "dynamics", "365"]):
                    logger.info(f"💡 Detected Knowledge Request: '{query}'")
                    
                    # Search Learn
                    result = await self.learn_client.search_term(query)
                    
                    if result:
                        # Post to Chat via Teams chat service
                        await self.chat_service.send_knowledge_message(
                            meeting_id,
                            title=result["title"],
                            summary=result["summary"],
                            url=result["url"],
                        )
                        break # Only one answer per line to avoid spam
