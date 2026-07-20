"""
tests/test_executor.py — Unit tests for the Executor component.

The Executor is the most delicate part of the agent: it drives the LLM,
picks tools, retries on failure and feeds errors back into the prompt.
All of that is tested here with a fully mocked LLM — no API key, no
network, no Ollama.

Run with:
    pytest tests/test_executor.py -v
"""

import pytest
from unittest.mock import MagicMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent.executor import Executor, ToolExecutionError
from agent.memory import AgentMemory
from agent.planner import Plan, PlanStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_call_message(name: str, args: dict) -> AIMessage:
    """An AIMessage shaped like a provider that supports native tool calling."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": "call_1", "type": "tool_call"}],
    )


def _fake_llm(responses: list) -> BaseChatModel:
    """Mock chat model whose bound version returns `responses` in order.

    The Executor calls llm.bind_tools(tools) once in __init__ and then
    invokes the bound model, so that's the object we need to control.
    """
    bound = MagicMock()
    bound.invoke.side_effect = list(responses)

    llm = MagicMock(spec=BaseChatModel)
    llm.bind_tools.return_value = bound
    return llm


def _plan_with_one_step(suggested_tool: str) -> Plan:
    return Plan(
        goal="Analyze the data",
        reasoning="Single step is enough for this test",
        steps=[
            PlanStep(
                id=1,
                description="Do the thing",
                suggested_tool=suggested_tool,
                expected_output="a result",
            )
        ],
    )


def _run(executor: Executor, plan: Plan) -> AgentMemory:
    memory = AgentMemory(goal=plan.goal)
    executor.run(plan, memory)
    return memory


# ---------------------------------------------------------------------------
# Tools that report failure via {"error": ...} — the project's convention
# ---------------------------------------------------------------------------

class TestToolErrorsAreNotSuccesses:
    """Regression tests: a tool returning {"error": ...} is a FAILED step.

    Tools in this project never raise — they return an error dict. Before
    this was handled explicitly, such steps were recorded as successes whose
    output happened to be an error, which silently corrupted the memory
    context for every step that followed.
    """

    def test_error_dict_marks_step_as_error(self):
        @tool("failing_tool")
        def failing_tool(value: str) -> dict:
            """Always reports a failure."""
            return {"error": "Column 'ghost' not in dataset."}

        llm = _fake_llm([_tool_call_message("failing_tool", {"value": "x"})] * 2)
        executor = Executor(llm=llm, tools=[failing_tool])

        memory = _run(executor, _plan_with_one_step("failing_tool"))

        assert memory.results[0].status == "error"

    def test_error_message_is_preserved_for_the_user(self):
        @tool("failing_tool")
        def failing_tool(value: str) -> dict:
            """Always reports a failure."""
            return {"error": "Column 'ghost' not in dataset."}

        llm = _fake_llm([_tool_call_message("failing_tool", {"value": "x"})] * 2)
        executor = Executor(llm=llm, tools=[failing_tool])

        memory = _run(executor, _plan_with_one_step("failing_tool"))

        assert "ghost" in memory.results[0].error

    def test_error_payload_is_not_stored_as_output(self):
        """The failed step must not leak its error dict into `output`."""
        @tool("failing_tool")
        def failing_tool(value: str) -> dict:
            """Always reports a failure."""
            return {"error": "Column 'ghost' not in dataset."}

        llm = _fake_llm([_tool_call_message("failing_tool", {"value": "x"})] * 2)
        executor = Executor(llm=llm, tools=[failing_tool])

        memory = _run(executor, _plan_with_one_step("failing_tool"))

        assert memory.results[0].output is None

    def test_failing_tool_is_retried(self):
        """max_retries=1 means the tool gets two attempts, not one."""
        calls = []

        @tool("failing_tool")
        def failing_tool(value: str) -> dict:
            """Always reports a failure."""
            calls.append(value)
            return {"error": "nope"}

        llm = _fake_llm([_tool_call_message("failing_tool", {"value": "x"})] * 2)
        executor = Executor(llm=llm, tools=[failing_tool], max_retries=1)

        _run(executor, _plan_with_one_step("failing_tool"))

        assert len(calls) == 2

    def test_retry_prompt_includes_the_previous_error(self):
        """Self-healing only works if the error is fed back to the LLM."""
        @tool("failing_tool")
        def failing_tool(value: str) -> dict:
            """Always reports a failure."""
            return {"error": "Column 'ghost' not in dataset."}

        llm = _fake_llm([_tool_call_message("failing_tool", {"value": "x"})] * 2)
        executor = Executor(llm=llm, tools=[failing_tool])

        _run(executor, _plan_with_one_step("failing_tool"))

        second_attempt_messages = executor.llm_with_tools.invoke.call_args_list[1][0][0]
        user_text = second_attempt_messages[-1].content
        assert "ghost" in user_text

    def test_step_recovers_when_second_attempt_succeeds(self):
        """The whole point of the retry: a fixed argument must yield success."""
        attempts = {"n": 0}

        @tool("flaky_tool")
        def flaky_tool(column: str) -> dict:
            """Fails for the wrong column, succeeds for the right one."""
            attempts["n"] += 1
            if column != "revenue":
                return {"error": f"Column '{column}' not in dataset."}
            return {"total": 42}

        llm = _fake_llm([
            _tool_call_message("flaky_tool", {"column": "ghost"}),
            _tool_call_message("flaky_tool", {"column": "revenue"}),
        ])
        executor = Executor(llm=llm, tools=[flaky_tool])

        memory = _run(executor, _plan_with_one_step("flaky_tool"))

        assert attempts["n"] == 2
        assert memory.results[0].status == "success"
        assert memory.results[0].output == {"total": 42}


# ---------------------------------------------------------------------------
# Happy path and plan-level behaviour
# ---------------------------------------------------------------------------

class TestExecutorHappyPath:

    def test_successful_step_is_recorded(self):
        @tool("working_tool")
        def working_tool(value: str) -> dict:
            """Always succeeds."""
            return {"result": value.upper()}

        llm = _fake_llm([_tool_call_message("working_tool", {"value": "ok"})])
        executor = Executor(llm=llm, tools=[working_tool])

        memory = _run(executor, _plan_with_one_step("working_tool"))

        assert memory.results[0].status == "success"
        assert memory.results[0].tool_used == "working_tool"
        assert memory.results[0].output == {"result": "OK"}

    def test_all_steps_run_even_after_a_failure(self):
        """A failed step degrades context but must not abort the plan."""
        @tool("failing_tool")
        def failing_tool() -> dict:
            """Always reports a failure."""
            return {"error": "nope"}

        @tool("working_tool")
        def working_tool() -> dict:
            """Always succeeds."""
            return {"ok": True}

        llm = _fake_llm([
            _tool_call_message("failing_tool", {}),  # step 1, attempt 1
            _tool_call_message("failing_tool", {}),  # step 1, retry
            _tool_call_message("working_tool", {}),  # step 2
        ])
        executor = Executor(llm=llm, tools=[failing_tool, working_tool])
        plan = Plan(
            goal="Two steps",
            reasoning="Testing continuation after failure",
            steps=[
                PlanStep(id=1, description="fail", suggested_tool="failing_tool",
                         expected_output="nothing"),
                PlanStep(id=2, description="work", suggested_tool="working_tool",
                         expected_output="something"),
            ],
        )

        memory = _run(executor, plan)

        assert [r.status for r in memory.results] == ["error", "success"]

    def test_ui_callbacks_fire(self):
        @tool("working_tool")
        def working_tool() -> dict:
            """Always succeeds."""
            return {"ok": True}

        started, succeeded = [], []
        llm = _fake_llm([_tool_call_message("working_tool", {})])
        executor = Executor(
            llm=llm,
            tools=[working_tool],
            on_step_start=lambda step, total: started.append(step.id),
            on_step_success=lambda step, result: succeeded.append(step.id),
        )

        _run(executor, _plan_with_one_step("working_tool"))

        assert started == [1]
        assert succeeded == [1]


# ---------------------------------------------------------------------------
# Malformed LLM behaviour
# ---------------------------------------------------------------------------

class TestExecutorHandlesBadLLMOutput:

    def test_unknown_tool_name_fails_the_step(self):
        @tool("working_tool")
        def working_tool() -> dict:
            """Always succeeds."""
            return {"ok": True}

        llm = _fake_llm([_tool_call_message("hallucinated_tool", {})] * 2)
        executor = Executor(llm=llm, tools=[working_tool])

        memory = _run(executor, _plan_with_one_step("working_tool"))

        assert memory.results[0].status == "error"
        assert "hallucinated_tool" in memory.results[0].error

    def test_plain_text_answer_fails_the_step(self):
        """The executor requires a tool call; prose is not an acceptable answer."""
        @tool("working_tool")
        def working_tool() -> dict:
            """Always succeeds."""
            return {"ok": True}

        llm = _fake_llm([AIMessage(content="Sure, I'd analyze the sales data.")] * 2)
        executor = Executor(llm=llm, tools=[working_tool])

        memory = _run(executor, _plan_with_one_step("working_tool"))

        assert memory.results[0].status == "error"

    def test_tool_call_embedded_in_content_is_recovered(self):
        """Some Ollama models put the tool call in `content` as raw JSON."""
        @tool("working_tool")
        def working_tool(value: str) -> dict:
            """Always succeeds."""
            return {"result": value}

        llm = _fake_llm([
            AIMessage(content='{"name": "working_tool", "arguments": {"value": "hi"}}')
        ])
        executor = Executor(llm=llm, tools=[working_tool])

        memory = _run(executor, _plan_with_one_step("working_tool"))

        assert memory.results[0].status == "success"
        assert memory.results[0].output == {"result": "hi"}


# ---------------------------------------------------------------------------
# Fallback parser for models without native tool calling
# ---------------------------------------------------------------------------

class TestParseToolCallFromContent:

    def test_parses_arguments_key(self):
        call = Executor._parse_tool_call_from_content(
            '{"name": "load_csv", "arguments": {"file_path": "a.csv"}}'
        )
        assert call == {"name": "load_csv", "args": {"file_path": "a.csv"}}

    def test_parses_args_key(self):
        call = Executor._parse_tool_call_from_content(
            '{"name": "load_csv", "args": {"file_path": "a.csv"}}'
        )
        assert call == {"name": "load_csv", "args": {"file_path": "a.csv"}}

    def test_strips_markdown_fences(self):
        call = Executor._parse_tool_call_from_content(
            '```json\n{"name": "load_csv", "args": {}}\n```'
        )
        assert call is not None
        assert call["name"] == "load_csv"

    def test_missing_args_defaults_to_empty_dict(self):
        call = Executor._parse_tool_call_from_content('{"name": "profile_dataset"}')
        assert call == {"name": "profile_dataset", "args": {}}

    @pytest.mark.parametrize("content", [
        "I will now load the CSV file.",   # prose
        "",                                 # empty
        '{"args": {"file_path": "a.csv"}}',  # no name
        '["load_csv"]',                     # not an object
        '{"name": "load_csv",',             # truncated JSON
    ])
    def test_returns_none_for_non_tool_calls(self, content):
        assert Executor._parse_tool_call_from_content(content) is None


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------

class TestTruncate:

    def test_short_output_is_returned_untouched(self):
        assert Executor._truncate({"a": 1}) == {"a": 1}

    def test_long_output_is_truncated_with_a_marker(self):
        result = Executor._truncate("x" * 5000, limit=4000)
        assert len(result) < 5000
        assert "truncated" in result

    def test_output_at_the_limit_is_not_truncated(self):
        text = "x" * 4000
        assert Executor._truncate(text, limit=4000) == text
