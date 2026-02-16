"""Pydantic models for structured meeting intelligence extraction."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ActionItem(BaseModel):
    """A single action item extracted from a meeting transcript."""

    description: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "medium"


class Objection(BaseModel):
    """A customer objection raised during the meeting."""

    topic: str
    details: str
    response_given: Optional[str] = None


class MeetingIntelligence(BaseModel):
    """Structured output from transcript analysis.

    This is the central data model that flows through the entire pipeline:
    transcript → LLM extraction → Salesforce update → email summary.
    """

    # Meeting metadata
    meeting_id: str = ""
    meeting_subject: str = ""
    meeting_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None

    # Participants
    participants: List[str] = Field(default_factory=list)
    organizer: Optional[str] = None
    organizer_email: Optional[str] = None

    # Deal intelligence
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    deal_size: Optional[float] = None
    deal_currency: str = "USD"
    deal_stage: Optional[str] = None

    # Action items
    next_steps: List[ActionItem] = Field(default_factory=list)

    # Objections
    objections: List[Objection] = Field(default_factory=list)

    # Competitors
    competitors_mentioned: List[str] = Field(default_factory=list)

    # Salesforce mapping
    opportunity_id: Optional[str] = None
    account_name: Optional[str] = None

    # Summary
    executive_summary: str = ""

    def to_salesforce_dict(self) -> dict:
        """Convert to Salesforce Opportunity field update dictionary.

        Only includes fields that have non-None values.
        """
        data: dict = {}

        if self.deal_stage:
            data["StageName"] = self.deal_stage
        if self.executive_summary:
            data["Description"] = self.executive_summary
        if self.next_steps:
            data["NextStep"] = self.next_steps[0].description
        if self.deal_size is not None:
            data["Amount"] = self.deal_size

        return data

    def format_next_steps(self) -> str:
        """Format action items as a readable bullet list."""
        if not self.next_steps:
            return "No action items identified."
        lines = []
        for item in self.next_steps:
            line = f"- {item.description}"
            if item.owner:
                line += f" (Owner: {item.owner})"
            if item.due_date:
                line += f" [Due: {item.due_date}]"
            lines.append(line)
        return "\n".join(lines)
