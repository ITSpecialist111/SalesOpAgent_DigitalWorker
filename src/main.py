import asyncio
import logging
import os
from azure.identity import DefaultAzureCredential
from microsoft_agents.hosting.aiohttp import AioHttpHost
from microsoft_agents.authentication.msal import MsalAuthenticationHandler

from agent import SalesOpsAgent

# Configure logging
_root_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _root_log_level, logging.INFO))
logger = logging.getLogger(__name__)

for noisy_logger in ("azure", "azure.identity", "azure.core", "httpx", "httpcore", "msal"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

async def main():
    logger.info("🚀 Starting Sales Ops Agent Host...")

    # Initialize the Agent
    agent = SalesOpsAgent()
    await agent.initialize()

    # Configure Authentication (Entra ID)
    # In production (container), we use Managed Identity or Client Secret
    client_id = os.getenv("AZURE_CLIENT_ID")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    
    auth_handler = None
    if client_id and tenant_id:
        logger.info("🔐 Configuring MSAL Authentication...")
        credential = DefaultAzureCredential()
        auth_handler = MsalAuthenticationHandler(
            credential=credential,
            client_id=client_id,
            tenant_id=tenant_id
        )
    else:
        logger.warning("⚠️ No Authentication configured! Agent may be insecure.")

    # Start the Host
    # Port 8000 is standard for Azure Container Apps
    host = AioHttpHost(
        agent=agent,
        auth_handler=auth_handler,
        port=8000
    )
    
    await host.start()

if __name__ == "__main__":
    asyncio.run(main())
