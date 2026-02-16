"""
Script to apply critical patches to the installed microsoft-agents-a365 SDK.
This fixes known issues with MCP headers, class renames, and argument names.

Usage: python scripts/patch_sdk.py
"""
import os
import site
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def patch_sdk():
    site_packages = site.getsitepackages()[0]
    
    # Path to MCP extensions
    target_dir = os.path.join(site_packages, "microsoft_agents_a365", "tooling", "extensions", "agentframework")
    tool_file = os.path.join(target_dir, "mcp_tool.py")

    fixes = [
        # Fix 1: ChatAgent -> Agent (SDK v1.0 change)
        {
            "old": "from agent_framework import ChatAgent",
            "new": "from agent_framework import Agent"
        },
        {
            "old": "class Agent365ToolExtensions(ChatAgent):",
            "new": "class Agent365ToolExtensions(Agent):"
        },
        # Fix 2: chat_client -> client (SDK v1.0 change)
        {
            "old": "super().__init__(chat_client=client, **kwargs)",
            "new": "super().__init__(client=client, **kwargs)"
        },
        # Fix 3: MCP headers silently dropped (ISS-018)
        {
            "old": "headers=headers,",
            "new": "http_client=httpx.AsyncClient(headers=headers) if headers else None,"
        }
    ]

    if not os.path.exists(tool_file):
        logging.error(f"Target file not found: {tool_file}")
        return

    # Backup
    if not os.path.exists(tool_file + ".bak"):
        shutil.copy(tool_file, tool_file + ".bak")
        logging.info(f"Backed up {tool_file}")

    with open(tool_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Add import httpx if missing (for Fix 3)
    if "import httpx" not in content:
        content = "import httpx\n" + content

    patched_content = content
    for fix in fixes:
        if fix["old"] in patched_content:
            patched_content = patched_content.replace(fix["old"], fix["new"])
            logging.info(f"Applied fix: {fix['old'][:30]}...")

    if patched_content != content:
        with open(tool_file, "w", encoding="utf-8") as f:
            f.write(patched_content)
        logging.info("SDK patched successfully.")
    else:
        logging.info("SDK already patched or patterns not found.")

if __name__ == "__main__":
    try:
        patch_sdk()
    except Exception as e:
        logging.error(f"Patch failed: {e}")
