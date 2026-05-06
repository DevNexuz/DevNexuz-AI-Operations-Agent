"""
Tools package — capabilities that agent can call.

Each tool is a LangChain `@tool`-decorated function with:
    - a clear docstring (used by the LLM to decide when to call it),
    - typed Pydantic args (validated automatically),
    - a JSON-serializable return value (so it survives logging/memory).

To add a new tool:
    1. Write the function in one of the modules below (or a new one).
    2. Decorate with @tool.
    3. Add it to `ALL_TOOLS` and `build_tools_catalog()`.
"""

from langchain_core.tools import BaseTool

from tools.csv_tools import load_csv, profile_dataset
from tools.analysis_tools import (
    aggregate_by,
    detect_anomalies,
    generate_chart,
    top_n,
)
from tools.report_tools import write_report


ALL_TOOLS: list[BaseTool] = [
    load_csv,
    profile_dataset,
    aggregate_by,
    top_n,
    detect_anomalies,
    generate_chart,
    write_report,
]


def build_tools_catalog() -> str:
    """
    Human-readable catalog injected into the Planner prompt.

    Format kept compact on purpose: the LLM only needs name + one-line
    description + arg names to plan correctly.
    """
    lines = []
    for t in ALL_TOOLS:
        # Handle different LangChain versions safely
        arg_names = "—"
        try:
            if hasattr(t, "args") and t.args:
                if hasattr(t.args, "keys"):
                    arg_names = ", ".join(t.args.keys())
                elif hasattr(t.args, "__iter__"):
                    arg_names = ", ".join(t.args)
            elif hasattr(t, "args_schema") and t.args_schema:
                # Try to get field names from Pydantic schema
                if hasattr(t.args_schema, "model_fields"):
                    arg_names = ", ".join(t.args_schema.model_fields.keys())
                elif hasattr(t.args_schema, "__fields__"):
                    arg_names = ", ".join(t.args_schema.__fields__.keys())
        except Exception:
            # Fallback to generic if anything fails
            arg_names = "—"
        
        # First line of the docstring is the user-facing description.
        desc = (t.description or "").strip().splitlines()[0]
        lines.append(f"- **{t.name}**({arg_names}): {desc}")
    return "\n".join(lines)


__all__ = ["ALL_TOOLS", "build_tools_catalog"]
