"""Tests for the LLM extraction engine."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.extraction.llm_extractor import LLMExtractor, LLMProvider
from src.extraction.prompts import build_extraction_user_prompt
from src.extraction.schemas import MeetingIntelligence, Sentiment


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns a predefined JSON response."""

    def __init__(self, response: dict[str, Any]):
        self._response = response

    async def extract_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return self._response


class TestBuildExtractionUserPrompt:
    def test_short_transcript(self):
        prompt = build_extraction_user_prompt("Hello world")
        assert "Hello world" in prompt
        assert "TRUNCATED" not in prompt

    def test_long_transcript_truncated(self):
        long_text = "x" * 60000
        prompt = build_extraction_user_prompt(long_text, max_chars=50000)
        assert len(prompt) < 60000
        assert "TRUNCATED" in prompt

    def test_includes_instruction(self):
        prompt = build_extraction_user_prompt("test")
        assert "Analyze" in prompt
        assert "transcript" in prompt.lower()


class TestLLMExtractor:
    @pytest.mark.asyncio
    async def test_extract_valid_response(self):
        mock_response = {
            "sentiment": "positive",
            "sentiment_confidence": 0.85,
            "deal_size": 450000,
            "deal_currency": "USD",
            "deal_stage": "Negotiation",
            "next_steps": [
                {"description": "Review contract", "owner": "Mike", "priority": "high"}
            ],
            "objections": [],
            "competitors_mentioned": ["Salesforce"],
            "account_name": "Acme Corp",
            "executive_summary": "Positive meeting with expansion planned.",
            "participants": ["Sarah", "Mike"],
        }

        provider = MockLLMProvider(mock_response)
        extractor = LLMExtractor(provider=provider)

        result = await extractor.extract("Some transcript text")

        assert isinstance(result, MeetingIntelligence)
        assert result.sentiment == Sentiment.POSITIVE
        assert result.deal_size == 450000
        assert len(result.next_steps) == 1
        assert result.next_steps[0].owner == "Mike"
        assert result.account_name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_extract_minimal_response(self):
        """LLM returns only required fields with defaults."""
        mock_response = {
            "sentiment": "neutral",
            "sentiment_confidence": 0.5,
            "deal_size": None,
            "deal_currency": "USD",
            "deal_stage": None,
            "next_steps": [],
            "objections": [],
            "competitors_mentioned": [],
            "account_name": None,
            "executive_summary": "Brief meeting with no commitments.",
            "participants": [],
        }

        provider = MockLLMProvider(mock_response)
        extractor = LLMExtractor(provider=provider)

        result = await extractor.extract("Short meeting")

        assert result.sentiment == Sentiment.NEUTRAL
        assert result.deal_size is None
        assert result.next_steps == []

    @pytest.mark.asyncio
    async def test_extract_invalid_json_raises(self):
        """Provider returning invalid JSON should raise."""

        class BadProvider(LLMProvider):
            async def extract_json(self, system_prompt, user_prompt):
                raise ValueError("LLM returned garbage")

        extractor = LLMExtractor(provider=BadProvider())

        with pytest.raises(ValueError):
            await extractor.extract("test")
