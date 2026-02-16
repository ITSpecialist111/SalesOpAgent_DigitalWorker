# Copyright (c) Microsoft. All rights reserved.

"""
Dynamics 365 Client Stub.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DynamicsClient:
    """
    Client for interacting with Dynamics 365 (Dataverse).
    Currently a stub to allow development of the core agent logic.
    """

    def __init__(self):
        """Initialize the Dynamics client."""
        self.enabled = False
        logger.info("DynamicsClient initialized (Stub Mode)")

    async def find_opportunity_by_email_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Find an open opportunity related to the email domain.
        
        Args:
            domain: The domain of the email sender (e.g., 'contoso.com').
            
        Returns:
            A dictionary representing the opportunity, or None.
        """
        logger.info(f"STUB: Searching Dynamics for opportunities in domain '{domain}'")
        # Mock return
        return {
            "opportunityid": "00000000-0000-0000-0000-000000000000",
            "name": f"Global Expansion - {domain}",
            "statuscode": 1, # Open
            "estimatedvalue": 50000.0,
            "estimatedclosedate": "2024-12-31"
        }

    async def update_opportunity(self, opportunity_id: str, fields: Dict[str, Any]) -> bool:
        """
        Update fields on a Dynamics Opportunity.
        
        Args:
            opportunity_id: The ID of the opportunity.
            fields: Dictionary of fields to update.
            
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"STUB: Updating Dynamics Opportunity {opportunity_id} with {fields}")
        return True

    async def create_task(self, opportunity_id: str, subject: str, description: str) -> bool:
        """
        Create a task in Dynamics linked to an opportunity.
        """
        logger.info(f"STUB: Creating Task '{subject}' on Opportunity {opportunity_id}")
        return True

    async def append_account_note(
        self,
        account_reference: str,
        note_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Append a note to a Dynamics account timeline/activity history.

        Args:
            account_reference: Account identifier or human-readable lookup key.
            note_text: The note content to append.
            metadata: Optional structured metadata (e.g., meeting id, CRM update hints).

        Returns:
            True if successful, False otherwise.
        """
        logger.info(
            "STUB: Appending account note for '%s'. Note length=%s metadata=%s",
            account_reference,
            len(note_text or ""),
            metadata or {},
        )
        return True
