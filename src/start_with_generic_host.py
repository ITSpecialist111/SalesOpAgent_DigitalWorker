# Copyright (c) Microsoft. All rights reserved.

"""
Entry point to start the Sales Ops Agent Host
"""

import asyncio
import logging
import os

# Compatibility shim: agent-framework v1.0 renamed ChatAgent → Agent,
# but microsoft_agents_a365 tooling v0.1 still imports ChatAgent.
# Patch before any imports that cascade into the a365 tooling package.
import agent_framework
if not hasattr(agent_framework, 'ChatAgent'):
    agent_framework.ChatAgent = agent_framework.Agent

from host_agent_server import create_and_run_host
from agent import SalesOpsAgent

# Configure logging
_root_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _root_log_level, logging.INFO))
logger = logging.getLogger(__name__)

for noisy_logger in ("azure", "azure.identity", "azure.core", "httpx", "httpcore", "msal"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting Sales Ops Agent Host...")
        create_and_run_host(SalesOpsAgent)
    except Exception as e:
        logger.error(f"❌ Failed to start host: {e}")
        raise
