"""
AI Operations Agent - Tool Registry

Manages registration and discovery of available tools.
"""

from typing import Dict, List, Type, Optional
from .base_tool import BaseTool


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register default tools."""
        # Import and register default tools
        try:
            from .csv_tools import LoadCSVTool
            self.register_tool_class("load_csv", LoadCSVTool)
        except ImportError:
            pass
        
        try:
            from .analysis_tools import PandasAnalyzeTool, DetectAnomaliesTool
            self.register_tool_class("pandas_analyze", PandasAnalyzeTool)
            self.register_tool_class("detect_anomalies", DetectAnomaliesTool)
        except ImportError:
            pass
        
        try:
            from .report_tools import GenerateVisualizationsTool, WriteReportTool
            self.register_tool_class("generate_visualizations", GenerateVisualizationsTool)
            self.register_tool_class("write_report", WriteReportTool)
        except ImportError:
            pass
        
        try:
            from .python_tools import PythonExecTool, SummarizeDataTool
            self.register_tool_class("python_exec", PythonExecTool)
            self.register_tool_class("summarize_data", SummarizeDataTool)
        except ImportError:
            pass
    
    def register_tool_class(self, name: str, tool_class: Type[BaseTool]) -> None:
        """Register a tool class."""
        self._tool_classes[name] = tool_class
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool instance by name."""
        if name not in self._tools:
            if name in self._tool_classes:
                self._tools[name] = self._tool_classes[name]()
            else:
                return None
        
        return self._tools[name]
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return list(self._tool_classes.keys())
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available tools."""
        descriptions = {}
        for name, tool_class in self._tool_classes.items():
            tool_instance = tool_class()
            descriptions[name] = tool_instance.description
        return descriptions
    
    def get_tool_schemas(self) -> List[Dict]:
        """Get schemas for all available tools."""
        schemas = []
        for name in self._tool_classes:
            tool = self.get_tool(name)
            if tool:
                schemas.append(tool.get_schema())
        return schemas
    
    def validate_tool_name(self, name: str) -> bool:
        """Check if a tool name is valid."""
        return name in self._tool_classes
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._tool_classes.clear()
    
    def __len__(self) -> int:
        """Get the number of registered tools."""
        return len(self._tool_classes)
    
    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tool_classes
