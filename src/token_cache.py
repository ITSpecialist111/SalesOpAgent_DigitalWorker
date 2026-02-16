# Copyright (c) Microsoft. All rights reserved.

"""
Token cache implementation for the AgentFramework Agent.
"""

from typing import Dict, Optional

# Simple in-memory cache for OBO tokens
# In a production environment, this should be replaced with a distributed cache (e.g., Redis)
_token_cache: Dict[str, str] = {}


def cache_agentic_token(tenant_id: str, agent_id: str, token: str) -> None:
    """
    Cache the OBO token for a specific tenant and agent.
    
    Args:
        tenant_id: The tenant ID.
        agent_id: The agent ID.
        token: The OBO token.
    """
    key = f"{tenant_id}:{agent_id}"
    _token_cache[key] = token


def get_cached_agentic_token(tenant_id: str, agent_id: str) -> Optional[str]:
    """
    Get the cached OBO token for a specific tenant and agent.
    
    Args:
        tenant_id: The tenant ID.
        agent_id: The agent ID.
        
    Returns:
        The cached OBO token, or None if not found.
    """
    key = f"{tenant_id}:{agent_id}"
    return _token_cache.get(key)
