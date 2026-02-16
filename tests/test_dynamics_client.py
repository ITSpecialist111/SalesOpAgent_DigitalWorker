"""Tests for the Dynamics 365 integration client stub."""

from __future__ import annotations

import pytest

from src.integrations.dynamics_client import DynamicsClient


class TestDynamicsClient:
    @pytest.mark.asyncio
    async def test_find_opportunity_by_email_domain_returns_stub_payload(self):
        client = DynamicsClient()

        result = await client.find_opportunity_by_email_domain("contoso.com")

        assert client.enabled is False
        assert result is not None
        assert result["name"] == "Global Expansion - contoso.com"
        assert result["statuscode"] == 1

    @pytest.mark.asyncio
    async def test_update_opportunity_returns_true(self):
        client = DynamicsClient()

        result = await client.update_opportunity("opp-123", {"estimatedvalue": 75000})

        assert result is True

    @pytest.mark.asyncio
    async def test_create_task_returns_true(self):
        client = DynamicsClient()

        result = await client.create_task("opp-123", "Follow up", "Send proposal")

        assert result is True

    @pytest.mark.asyncio
    async def test_append_account_note_returns_true(self):
        client = DynamicsClient()

        result = await client.append_account_note(
            account_reference="contoso",
            note_text="Meeting summary note",
            metadata={"meeting_id": "mid-1"},
        )

        assert result is True
