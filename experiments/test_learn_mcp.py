
import asyncio
import logging
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    url = "https://learn.microsoft.com/api/mcp"
    logger.info(f"Connecting to {url}...")

    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("✅ Connected to Learn MCP!")

                # List Tools
                tools = await session.list_tools()
                logger.info(f"🛠️ Available Tools: {[t.name for t in tools.tools]}")

                # Call a tool (assuming 'search' exists based on docs)
                # We need to find the search tool name
                search_tool = next((t for t in tools.tools if "search" in t.name), None)
                
                if search_tool:
                    logger.info(f"🔍 Testing {search_tool.name} with query 'Copilot'...")
                    result = await session.call_tool(search_tool.name, {"query": "Microsoft 365 Copilot"})
                    logger.info(f"📄 Result: {str(result)[:200]}...")
                else:
                    logger.warning("⚠️ No search tool found.")

    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
