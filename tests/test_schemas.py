"""Tests for the MeetingIntelligence Pydantic models."""

from src.extraction.schemas import (
    ActionItem,
    MeetingIntelligence,
    Objection,
    Sentiment,
)


class TestSentimentEnum:
    def test_values(self):
        assert Sentiment.POSITIVE == "positive"
        assert Sentiment.NEUTRAL == "neutral"
        assert Sentiment.NEGATIVE == "negative"


class TestActionItem:
    def test_minimal(self):
        item = ActionItem(description="Do something")
        assert item.description == "Do something"
        assert item.owner is None
        assert item.due_date is None
        assert item.priority == "medium"

    def test_full(self):
        item = ActionItem(
            description="Review contract",
            owner="Mike",
            due_date="2026-03-05",
            priority="high",
        )
        assert item.owner == "Mike"
        assert item.priority == "high"


class TestMeetingIntelligence:
    def test_defaults(self):
        intel = MeetingIntelligence()
        assert intel.sentiment == Sentiment.NEUTRAL
        assert intel.sentiment_confidence == 0.5
        assert intel.deal_size is None
        assert intel.next_steps == []
        assert intel.objections == []
        assert intel.competitors_mentioned == []

    def test_to_salesforce_dict_empty(self):
        intel = MeetingIntelligence()
        assert intel.to_salesforce_dict() == {}

    def test_to_salesforce_dict_with_data(self, sample_intelligence):
        sf_data = sample_intelligence.to_salesforce_dict()
        assert sf_data["StageName"] == "Negotiation"
        assert sf_data["Amount"] == 450000
        assert "review the contract" in sf_data["NextStep"]
        assert "Description" in sf_data

    def test_to_salesforce_dict_excludes_none(self):
        intel = MeetingIntelligence(
            deal_size=100000,
            executive_summary="Test summary",
        )
        sf_data = intel.to_salesforce_dict()
        assert "StageName" not in sf_data  # None values excluded
        assert sf_data["Amount"] == 100000

    def test_format_next_steps_empty(self):
        intel = MeetingIntelligence()
        assert intel.format_next_steps() == "No action items identified."

    def test_format_next_steps_with_items(self, sample_intelligence):
        formatted = sample_intelligence.format_next_steps()
        assert "Mike Chen" in formatted
        assert "Sarah Johnson" in formatted
        assert "procurement" in formatted.lower()

    def test_from_llm_json(self):
        """Test creating MeetingIntelligence from typical LLM JSON output."""
        llm_output = {
            "sentiment": "positive",
            "sentiment_confidence": 0.9,
            "deal_size": 250000,
            "deal_currency": "GBP",
            "deal_stage": "Proposal",
            "next_steps": [
                {"description": "Send proposal", "owner": "Alice", "priority": "high"}
            ],
            "objections": [
                {"topic": "Price", "details": "Too expensive for current budget"}
            ],
            "competitors_mentioned": ["Competitor A"],
            "account_name": "Test Corp",
            "executive_summary": "Good meeting with positive outcome.",
            "participants": ["Alice", "Bob"],
        }
        intel = MeetingIntelligence(**llm_output)
        assert intel.sentiment == Sentiment.POSITIVE
        assert intel.deal_size == 250000
        assert intel.deal_currency == "GBP"
        assert len(intel.next_steps) == 1
        assert intel.next_steps[0].owner == "Alice"

    def test_sentiment_confidence_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        intel = MeetingIntelligence(sentiment_confidence=0.0)
        assert intel.sentiment_confidence == 0.0

        intel = MeetingIntelligence(sentiment_confidence=1.0)
        assert intel.sentiment_confidence == 1.0

    def test_objection_model(self):
        obj = Objection(
            topic="Pricing",
            details="Over budget",
            response_given="Offered discount",
        )
        assert obj.topic == "Pricing"
        assert obj.response_given == "Offered discount"
