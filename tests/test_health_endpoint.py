"""Tests for host health endpoint MCP telemetry payload."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest
from aiohttp.test_utils import make_mocked_request

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import host_agent_server as host_module


@pytest.mark.asyncio
async def test_health_endpoint_includes_mcp_snapshot(monkeypatch):
    captured: dict = {}

    def fake_run_app(app, *args, **kwargs):
        captured["app"] = app

    monkeypatch.setattr(host_module, "run_app", fake_run_app)

    host = object.__new__(host_module.GenericAgentHost)
    host.agent_class = type("DummyAgent", (), {})
    host.agent_instance = SimpleNamespace(
        get_mcp_health_snapshot=lambda: {
            "state": "degraded",
            "setup_attempts": 3,
            "setup_successes": 1,
            "setup_failures": 2,
            "last_error": "HTTP 403",
            "next_retry_in_seconds": 20,
            "active_servers": {
                "mcp_SharePointListsTools": {
                    "successes": 0,
                    "failures": 2,
                    "last_error": "HTTP 403",
                }
            },
        }
    )
    host.agent_app = SimpleNamespace(adapter=object())

    async def initialize_agent():
        return None

    async def cleanup():
        return None

    host.initialize_agent = initialize_agent
    host.cleanup = cleanup

    host.start_server(auth_configuration=None)

    app = captured["app"]

    health_route = None
    for route in app.router.routes():
        resource = getattr(route, "resource", None)
        canonical = getattr(resource, "canonical", "") if resource else ""
        if route.method == "GET" and canonical == "/api/health":
            health_route = route
            break

    assert health_route is not None, "Expected GET /api/health route to be registered"

    request = make_mocked_request("GET", "/api/health", app=app)
    response = await health_route.handler(request)

    assert response.status == 200

    payload = response.body.decode("utf-8")
    assert '"status": "ok"' in payload
    assert '"mcp"' in payload
    assert '"state": "degraded"' in payload
    assert '"mcp_SharePointListsTools"' in payload
