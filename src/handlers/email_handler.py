# Copyright (c) Microsoft. All rights reserved.

"""
Email Handler for Meeting Detection.
Parses incoming emails to identify "Meeting Ended" signals and extract context.
"""

import logging
import re
from typing import Optional, Dict, Any

from microsoft_agents_a365.notifications.agent_notification import AgentNotificationActivity

logger = logging.getLogger(__name__)


class EmailHandler:
    """
    Parses email notifications to detect meeting endings.
    """

    def __init__(self):
        # Regex patterns for common "Meeting Ended" or "Recap" emails
        self.meeting_patterns = [
            r"Meeting recap: (.*)",
            r"(.*) - Meeting Recap",
            r"Transcript is ready for (.*)",
        ]

    async def process_email(self, activity: AgentNotificationActivity) -> Optional[Dict[str, Any]]:
        """
        Process an email notification to see if it triggers a meeting workflow.
        
        Args:
            activity: The notification activity containing the email.
            
        Returns:
            A dictionary with meeting context if a trigger is found, else None.
            Example: {"meeting_id": "...", "subject": "Sales Call", "trigger": "email"}
        """
        if not hasattr(activity, "email") or not activity.email:
            return None

        email = activity.email
        subject = email.subject or ""
        body = getattr(email, "html_body", "") or getattr(email, "body", "") or ""

        logger.info(f"📧 Analyzing Email: '{subject}'")

        # 1. Check Subject Line Patterns
        is_meeting_email = False
        meeting_subject = subject

        for pattern in self.meeting_patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                is_meeting_email = True
                meeting_subject = match.group(1) if match.groups() else subject
                logger.info(f"✅ Detected Meeting Recap Email for: '{meeting_subject}'")
                break

        # 2. Advanced: Check Body for "Join Meeting" URL or "Transcript" links to extract IDs
        # (Simplified for now - relying on subject triggers)
        
        if is_meeting_email:
            # TODO: Extract actual Meeting ID from body if possible, 
            # or rely on finding the meeting by subject via Graph/Calendar lookup later.
            
            return {
                "trigger": "email",
                "subject": meeting_subject,
                "original_subject": subject,
                "sender": email.sender.address if email.sender else "unknown",
                # "meeting_id": extracted_id # Ideally extract this from deep links
            }

        return None
