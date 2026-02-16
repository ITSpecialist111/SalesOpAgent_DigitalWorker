"""Tests for the current MeetingProcessor orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.meeting_processor import MeetingProcessor


@pytest.fixture
def processor():
    agent = SimpleNamespace()
    graph_client = AsyncMock()

    proc = MeetingProcessor(agent_instance=agent, graph_client=graph_client)

    proc.report_generator = MagicMock()
    proc.report_generator.generate_email_html.return_value = "<div>report</div>"
    proc.report_generator.generate_adaptive_card.return_value = {"type": "AdaptiveCard"}

    proc._fetch_learn_references = AsyncMock(return_value=[])
    proc._send_email_summary = AsyncMock(return_value=True)
    proc._post_teams_summary = AsyncMock(return_value=False)

    return proc


class TestMeetingProcessor:
    @pytest.mark.asyncio
    async def test_process_meeting_returns_expected_shape(self, processor):
        processor.graph_client.get_transcript_content.return_value = "Speaker: Discuss Dynamics 365 next steps"

        oai_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"summary":"ok","tasks":["t1"],"crm_updates":{"stage":"negotiation"},"crm_link":"#"}'
                    )
                )
            ]
        )
        processor._oai_client = MagicMock()
        processor._oai_client.chat.completions.create.return_value = oai_response

        result = await processor.process_meeting("meeting-1", "Quarterly review")

        assert "email_html" in result
        assert "card_json" in result
        assert "raw_data" in result
        assert result["email_sent"] is True
        assert result["teams_sent"] is False
        assert isinstance(result["raw_data"], dict)
        assert result["raw_data"]["subject"] == "Quarterly review"
        assert result["raw_data"]["meeting_id"] == "meeting-1"
        assert result["raw_data"]["executive_summary"] == "ok"
        assert result["raw_data"]["sentiment"] == "unknown"
        assert result["raw_data"]["sentiment_timeline"] == []
        assert result["raw_data"]["churn_risk"]["level"] == "unknown"
        assert result["raw_data"]["customer_satisfaction"]["score"] == "N/A"

    @pytest.mark.asyncio
    async def test_process_meeting_returns_error_when_transcript_unavailable(self, processor):
        processor.graph_client.get_transcript_content.return_value = None

        result = await processor.process_meeting("meeting-2", "Avon")
        assert "error" in result
        assert "Transcript unavailable" in result["error"]
        assert result["email_sent"] is False
        assert result["teams_sent"] is False

    @pytest.mark.asyncio
    async def test_process_meeting_handles_llm_failure(self, processor):
        processor.graph_client.get_transcript_content.return_value = "line1"

        processor._oai_client = MagicMock()
        processor._oai_client.chat.completions.create.side_effect = RuntimeError("LLM down")

        result = await processor.process_meeting("meeting-3", "Client sync")

        assert result["raw_data"]["summary"] == "Failed to analyze meeting."
        assert result["raw_data"]["tasks"] == []
        assert result["raw_data"]["crm_updates"] == {}
        assert result["raw_data"]["sentiment"] == "unknown"
        assert result["raw_data"]["churn_risk"]["level"] == "unknown"
        assert result["raw_data"]["customer_satisfaction"]["score"] == "N/A"

    @pytest.mark.asyncio
    async def test_fetch_learn_references_handles_dict_summary(self, processor):
        processor._fetch_learn_references = MeetingProcessor._fetch_learn_references.__get__(
            processor, MeetingProcessor
        )
        processor.learn_client.search_multiple_terms = AsyncMock(return_value=[])

        refs = await processor._fetch_learn_references(
            {
                "summary": {"topic": "Dynamics 365", "outcome": "next steps"},
                "tasks": [],
                "crm_updates": {},
            }
        )

        assert refs == []
        processor.learn_client.search_multiple_terms.assert_awaited_once()
