"""
AI Operations Agent - Base Tool

Abstract base class for all agent tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio


class BaseTool(ABC):
    """Abstract base class for agent tools."""
    
    def __init__(self):
        self.name = self.__class__.__name__.lower().replace("tool", "")
        self.description = self.__doc__ or "No description available"
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters."""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate that parameters are correct for this tool."""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the parameter schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    
    async def safe_execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool with error handling and validation."""
        try:
            # Validate parameters
            if not self.validate_parameters(parameters):
                raise ValueError(f"Invalid parameters for {self.name}")
            
            # Execute the tool
            result = await self.execute(parameters)
            
            return {
                "success": True,
                "result": result,
                "tool": self.name,
                "parameters": parameters
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": self.name,
                "parameters": parameters
            }
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"
