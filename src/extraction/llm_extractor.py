"""LLM-based transcript extraction with provider abstraction.

Supports Azure OpenAI and Anthropic Claude, selected via LLM_PROVIDER env var.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from .prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_prompt
from .schemas import MeetingIntelligence

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def extract_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Send prompts to the LLM and return parsed JSON."""


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI GPT-4o provider."""

    def __init__(self):
        from openai import AsyncAzureOpenAI

        self.client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    async def extract_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    async def extract_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        # Append JSON instruction since Claude doesn't have a native json_object mode
        user_with_json_hint = (
            user_prompt + "\n\nRespond ONLY with the JSON object, no other text."
        )
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_with_json_hint}],
            temperature=0.1,
        )
        raw = response.content[0].text
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        return json.loads(raw.strip())


def _create_provider() -> LLMProvider:
    """Factory: create the LLM provider based on environment config."""
    provider_name = os.getenv("LLM_PROVIDER", "azure_openai").lower()

    if provider_name == "azure_openai":
        return AzureOpenAIProvider()
    elif provider_name == "anthropic":
        return AnthropicProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider_name}. "
            "Supported: azure_openai, anthropic"
        )


class LLMExtractor:
    """Extracts structured MeetingIntelligence from transcript text using an LLM."""

    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or _create_provider()

    async def extract(self, transcript_text: str) -> MeetingIntelligence:
        """Extract structured meeting intelligence from raw transcript text."""
        user_prompt = build_extraction_user_prompt(transcript_text)

        logger.info("Sending transcript to LLM for extraction (%d chars)", len(transcript_text))

        try:
            parsed = await self.provider.extract_json(EXTRACTION_SYSTEM_PROMPT, user_prompt)
            intelligence = MeetingIntelligence(**parsed)
            logger.info(
                "Extraction complete: sentiment=%s, %d action items, %d objections",
                intelligence.sentiment.value,
                len(intelligence.next_steps),
                len(intelligence.objections),
            )
            return intelligence
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", e)
            raise
        except Exception as e:
            logger.error("Extraction failed: %s", e)
            raise
