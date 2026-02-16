"""Shared pytest fixtures for the SalesOpsBot test suite."""

from __future__ import annotations

import pytest

from src.extraction.schemas import (
    ActionItem,
    MeetingIntelligence,
    Objection,
    Sentiment,
)


@pytest.fixture
def sample_transcript() -> str:
    """A sample meeting transcript for testing extraction."""
    return """
    Sarah Johnson: Good morning everyone. Thanks for joining the quarterly review
    with Acme Corp. Let's get started.

    Mike Chen: Thanks Sarah. We've been really impressed with the platform so far.
    The team adoption has been great.

    Sarah Johnson: That's wonderful to hear. How are things going with the
    enterprise rollout?

    Mike Chen: Very well. We're looking at expanding from 500 to about 2,000 seats.
    Our budget for this is around 450,000 dollars for the annual contract.

    Sarah Johnson: Excellent. That's a significant expansion.

    Tom Williams: One concern we have is around the data residency requirements.
    We need all data stored in the EU region. Is that possible?

    Sarah Johnson: Absolutely. We have EU-based data centers and can configure
    your instance accordingly.

    Mike Chen: Great. We also want to make sure we're not locked in. We've been
    looking at Salesforce and HubSpot as alternatives, just to keep our options open.

    Sarah Johnson: Understood. We're confident in our value proposition and happy
    to do a competitive comparison.

    Tom Williams: OK, so next steps — Mike, can you get the procurement team
    to review the contract by next Friday? And Sarah, could you send over the
    EU data residency documentation by Wednesday?

    Sarah Johnson: Will do. I'll have that to you by Wednesday March 5th.

    Mike Chen: Perfect. Let's reconvene in two weeks to finalize.

    Sarah Johnson: Sounds great. Thanks everyone.
    """


@pytest.fixture
def sample_intelligence() -> MeetingIntelligence:
    """A pre-built MeetingIntelligence instance for testing."""
    return MeetingIntelligence(
        meeting_id="test-meeting-123",
        meeting_subject="Quarterly Review - Acme Corp",
        sentiment=Sentiment.POSITIVE,
        sentiment_confidence=0.85,
        deal_size=450000,
        deal_currency="USD",
        deal_stage="Negotiation",
        participants=["Sarah Johnson", "Mike Chen", "Tom Williams"],
        organizer="Sarah Johnson",
        organizer_email="sarah@company.com",
        account_name="Acme Corp",
        next_steps=[
            ActionItem(
                description="Get procurement team to review the contract",
                owner="Mike Chen",
                due_date="next Friday",
                priority="high",
            ),
            ActionItem(
                description="Send EU data residency documentation",
                owner="Sarah Johnson",
                due_date="2026-03-05",
                priority="high",
            ),
        ],
        objections=[
            Objection(
                topic="Data Residency",
                details="Need all data stored in EU region",
                response_given="EU-based data centers available, can configure instance",
            ),
        ],
        competitors_mentioned=["Salesforce", "HubSpot"],
        executive_summary=(
            "Positive quarterly review with Acme Corp. They plan to expand from "
            "500 to 2,000 seats with a $450K annual budget. Main concern is EU "
            "data residency, which was addressed. Competitors Salesforce and "
            "HubSpot mentioned as alternatives being evaluated."
        ),
    )


@pytest.fixture
def sample_vtt_content() -> str:
    """Sample WebVTT transcript content."""
    return """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Sarah Johnson: Good morning everyone.

2
00:00:05.000 --> 00:00:10.000
Mike Chen: Thanks Sarah. Great to be here.

3
00:00:10.000 --> 00:00:15.000
Sarah Johnson: Let's discuss the Q1 numbers.
"""
