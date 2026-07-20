"""
tests/test_mcp_server.py — Tests for the MCP server exposing the agent's
CSV-analysis tools.

Skips entirely if the `mcp` package isn't installed (it's an optional
dependency only needed to run the MCP server). Uses FastMCP's own
async list_tools()/call_tool() so these tests exercise the exact
registration path Claude Desktop/Code would use, not the wrapped
functions directly.

Run with:
    pytest tests/test_mcp_server.py -v
"""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from tools import ALL_TOOLS, _state  # noqa: E402


@pytest.fixture(autouse=True)
def clear_state():
    _state.reset()
    yield
    _state.reset()


@pytest.fixture
def server():
    """Fresh FastMCP instance per test — importing the module re-registers
    tools onto module-level `mcp`, which would leak state across tests."""
    import importlib

    import mcp_server as module
    importlib.reload(module)
    return module.mcp


def _run(coro):
    return asyncio.run(coro)


def _call(server, name: str, arguments: dict) -> dict:
    """Call an MCP tool and parse its JSON payload out of the TextContent
    FastMCP wraps plain-dict returns in (no output schema is declared)."""
    result = _run(server.call_tool(name, arguments))
    blocks = result[0] if isinstance(result, tuple) else result
    return json.loads(blocks[0].text)


class TestToolRegistration:

    def test_all_langchain_tools_are_registered(self, server):
        registered = {t.name for t in _run(server.list_tools())}
        expected = {t.name for t in ALL_TOOLS}

        assert expected.issubset(registered)

    def test_list_datasets_is_registered(self, server):
        registered = {t.name for t in _run(server.list_tools())}

        assert "list_datasets" in registered

    def test_registered_count_matches(self, server):
        registered = _run(server.list_tools())

        assert len(registered) == len(ALL_TOOLS) + 1  # + list_datasets

    def test_tool_descriptions_are_not_empty(self, server):
        for tool in _run(server.list_tools()):
            assert tool.description


class TestPathAbsolutization:

    def test_chart_path_becomes_absolute(self):
        from mcp_server import _absolutize_paths, REPO_ROOT

        result = _absolutize_paths({"chart_path": "outputs/charts/x.png"})

        assert result["chart_path"] == str(REPO_ROOT / "outputs/charts/x.png")

    def test_report_path_becomes_absolute(self):
        from mcp_server import _absolutize_paths, REPO_ROOT

        result = _absolutize_paths({"report_path": "outputs/report.md"})

        assert result["report_path"] == str(REPO_ROOT / "outputs/report.md")

    def test_already_absolute_path_is_untouched(self):
        from mcp_server import _absolutize_paths

        abs_path = str((__file__,)[0])  # any real absolute path
        result = _absolutize_paths({"chart_path": abs_path})

        assert result["chart_path"] == abs_path

    def test_non_dict_passes_through(self):
        from mcp_server import _absolutize_paths

        assert _absolutize_paths({"error": "boom"}) == {"error": "boom"}
        assert _absolutize_paths("not a dict") == "not a dict"

    def test_wrap_preserves_function_metadata_for_fastmcp_introspection(self):
        from mcp_server import _wrap
        from tools.csv_tools import load_csv

        wrapped = _wrap(load_csv.func)

        assert wrapped.__name__ == load_csv.func.__name__
        assert wrapped.__doc__ == load_csv.func.__doc__


class TestEndToEndCallChain:

    def test_load_then_aggregate_through_the_server(self, server):
        """The exact chain a real MCP client would perform: load a CSV,
        then aggregate it by dataset_id — proving the in-process dataset
        registry survives across separate call_tool invocations."""
        load_payload = _call(server, "load_csv", {"file_path": "data/sales.csv"})
        dataset_id = load_payload.get("dataset_id")
        assert dataset_id, f"unexpected load_csv payload: {load_payload!r}"

        listed_payload = _call(server, "list_datasets", {})
        assert dataset_id in listed_payload["datasets"]

        agg_payload = _call(
            server,
            "aggregate_by",
            {
                "dataset_id": dataset_id,
                "group_by": "region",
                "metric": "revenue",
                "agg": "sum",
            },
        )
        assert "error" not in agg_payload
        assert "result" in agg_payload

    def test_unknown_dataset_id_returns_error_not_crash(self, server):
        payload = _call(server, "profile_dataset", {"dataset_id": "ds_does_not_exist"})

        assert "error" in payload
