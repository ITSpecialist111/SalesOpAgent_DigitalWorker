# Copyright (c) Microsoft. All rights reserved.

"""
Interface for Integration Clients.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

class IntegrationClientInterface(ABC):
    
    @abstractmethod
    async def get_resource(self, resource_id: str) -> Optional[Any]:
        pass
