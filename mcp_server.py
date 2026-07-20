"""
MCP server — exposes the agent's CSV-analysis tools over the Model
Context Protocol, so Claude Desktop, Claude Code, or any MCP client can
call them directly (no Planner/Executor involved; the client itself
decides which tool to call and in what order).

The core is untouched: every tool here is the SAME LangChain @tool
function used by the CLI, the Streamlit app, and the eval harness.
LangChain's @tool decorator keeps the original function reachable as
`.func`, with real type hints intact, which FastMCP introspects to
build each tool's schema — no re-implementation, no drift.

Run standalone (stdio transport):
    python mcp_server.py

Configure in Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "csv-analyst": {
          "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
          "args": ["C:\\path\\to\\mcp_server.py"]
        }
      }
    }

Or register with the Claude Code CLI:
    claude mcp add csv-analyst -- <path-to-venv-python> <path-to-mcp_server.py>
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from tools import ALL_TOOLS, _state

REPO_ROOT = Path(__file__).resolve().parent

mcp = FastMCP("csv-analyst")


def _absolutize_paths(result: Any) -> Any:
    """Make chart_path/report_path absolute against the repo root.

    Tools write relative "outputs/..." paths assuming cwd == repo root.
    MCP clients (e.g. Claude Desktop) launch this process with an
    arbitrary cwd, so a relative path handed back to the client would be
    meaningless without this.
    """
    if not isinstance(result, dict):
        return result
    for key in ("chart_path", "report_path"):
        if key in result and result[key]:
            path = Path(result[key])
            if not path.is_absolute():
                result[key] = str(REPO_ROOT / path)
    return result


def _wrap(func: Callable) -> Callable:
    """Wrap a tool's raw function so its outputs carry absolute paths.

    functools.wraps preserves __name__/__doc__/__annotations__, which is
    what FastMCP inspects to build the tool's schema — the wrapper must
    be transparent to that introspection.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return _absolutize_paths(func(*args, **kwargs))

    return wrapper


for _tool in ALL_TOOLS:
    mcp.tool(name=_tool.name, description=_tool.description)(_wrap(_tool.func))


@mcp.tool(name="list_datasets", description="List CSV datasets currently loaded in this session, with their source file path.")
def list_datasets() -> dict:
    """Return every dataset_id registered so far via load_csv, with its source path."""
    return {"datasets": _state.all_datasets()}


def main() -> None:
    # Tools write relative "outputs/..." paths assuming cwd == repo root,
    # but MCP clients launch this process with an arbitrary cwd.
    os.chdir(REPO_ROOT)
    mcp.run()


if __name__ == "__main__":
    main()
