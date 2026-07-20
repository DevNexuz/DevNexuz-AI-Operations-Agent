"""
Executor — runs the plan one step at a time using bound tools.

For each step:
    1. Build a prompt with memory context.
    2. Ask the LLM to choose and call a tool (via native tool-calling).
    3. Execute the tool call locally.
    4. Store the result in memory.
    5. On failure, retry once with the error fed back to the LLM
       (self-healing prompt pattern).

This keeps the agent loop simple, auditable, and provider-agnostic.
"""

import json
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from agent.memory import AgentMemory, StepResult
from agent.planner import Plan, PlanStep
from prompts.prompts import EXECUTOR_SYSTEM_PROMPT, EXECUTOR_USER_PROMPT


class ToolExecutionError(RuntimeError):
    """A tool ran but reported a failure in its return value."""


class Executor:
    """Sequential plan executor with tool binding and basic error recovery."""

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        report_language: str = "es",
        max_retries: int = 1,
        on_step_start=None,
        on_step_success=None,
        on_step_error=None,
    ):
        """
        Args:
            llm: A LangChain chat model.
            tools: List of LangChain tools the agent can call.
            report_language: Language for any user-facing output (e.g. "es", "en").
            max_retries: How many times to re-prompt on tool errors per step.
            on_step_start / on_step_success / on_step_error:
                Optional callbacks for live UI rendering. Each receives
                (step, ...) and returns nothing.
        """
        self.llm = llm
        self.tools = tools
        self.tools_by_name = {t.name: t for t in tools}
        self.llm_with_tools = llm.bind_tools(tools)
        self.report_language = report_language
        self.max_retries = max_retries

        # UI hooks — kept optional so the executor stays headless-friendly.
        self._on_step_start = on_step_start
        self._on_step_success = on_step_success
        self._on_step_error = on_step_error

    # -- public API -----------------------------------------------------------

    def run(self, plan: Plan, memory: AgentMemory) -> AgentMemory:
        """Execute every step of the plan, updating memory in place."""
        total = len(plan.steps)
        for step in plan.steps:
            if self._on_step_start:
                self._on_step_start(step, total)

            result = self._run_step(step, total, plan.goal, memory)
            memory.add_result(result)

            if result.status == "success" and self._on_step_success:
                self._on_step_success(step, result)
            elif result.status == "error":
                if self._on_step_error:
                    self._on_step_error(step, result)
                memory.add_log(
                    "executor",
                    f"Step {step.id} failed after retries; continuing with degraded context.",
                )

        return memory

    # -- internals ------------------------------------------------------------

    def _run_step(
        self, step: PlanStep, total_steps: int, goal: str, memory: AgentMemory
    ) -> StepResult:
        """Run one step, with up to `max_retries` self-healing attempts."""
        attempts = 0
        last_error: Optional[str] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                tool_name, _tool_args, raw_output = self._invoke_step(
                    step, total_steps, goal, memory, last_error
                )
                return StepResult(
                    step_id=step.id,
                    status="success",
                    tool_used=tool_name,
                    output=self._truncate(raw_output),
                )
            except Exception as exc:  # noqa: BLE001 — agent must not crash on tool errors
                last_error = f"{type(exc).__name__}: {exc}"
                memory.add_log(
                    "executor",
                    f"Step {step.id} attempt {attempts} failed: {last_error}",
                )

        return StepResult(
            step_id=step.id,
            status="error",
            tool_used=step.suggested_tool,
            error=last_error,
        )

    def _invoke_step(
        self,
        step: PlanStep,
        total_steps: int,
        goal: str,
        memory: AgentMemory,
        last_error: Optional[str],
    ) -> tuple[str, dict, Any]:
        """One LLM call -> one tool call -> raw output."""
        system = SystemMessage(
            content=EXECUTOR_SYSTEM_PROMPT.format(
                report_language=self.report_language,
                memory_context=memory.context_summary(),
            )
        )
        user_text = EXECUTOR_USER_PROMPT.format(
            goal=goal,
            step_id=step.id,
            total_steps=total_steps,
            step_description=step.description,
            suggested_tool=step.suggested_tool,
            expected_output=step.expected_output,
        )
        if last_error:
            # Self-healing prompt: feed the error back so the LLM can fix args.
            user_text += (
                f"\n\nPrevious attempt failed with error:\n{last_error}\n"
                "Try again, fixing the arguments accordingly."
            )

        ai_msg: AIMessage = self.llm_with_tools.invoke(
            [system, HumanMessage(content=user_text)]
        )

        if not ai_msg.tool_calls:
            # Fallback: some Ollama models return tool calls as JSON in content
            # instead of using the structured tool_calls field.
            call = self._parse_tool_call_from_content(ai_msg.content or "")
            if call is None:
                raise RuntimeError(
                    "LLM did not call any tool. Content was: "
                    f"{(ai_msg.content or '')[:200]}"
                )
        else:
            call = ai_msg.tool_calls[0]

        # We execute only the FIRST tool call per step: one step = one action.
        tool_name = call["name"]
        tool_args = call.get("args", {}) or call.get("arguments", {}) or {}

        if tool_name not in self.tools_by_name:
            raise RuntimeError(
                f"LLM called unknown tool '{tool_name}'. "
                f"Valid tools: {list(self.tools_by_name)}"
            )

        tool = self.tools_by_name[tool_name]
        output = tool.invoke(tool_args)

        # Tools signal failure by returning {"error": ...} rather than raising,
        # so without this the step would be recorded as a success carrying an
        # error payload, and the retry loop would never run.
        if isinstance(output, dict) and "error" in output:
            raise ToolExecutionError(
                f"Tool '{tool_name}' called with arguments {tool_args} "
                f"failed: {output['error']}"
            )

        return tool_name, tool_args, output

    @staticmethod
    def _parse_tool_call_from_content(content: str) -> Optional[dict]:
        """Fallback parser for models (e.g. Ollama) that return tool calls as
        JSON in the message content instead of the structured tool_calls field.

        Handles two common formats:
            {"name": "tool", "arguments": {...}}
            {"name": "tool", "args": {...}}

        Returns a dict compatible with the tool_calls format, or None if the
        content cannot be parsed as a tool call.
        """
        content = content.strip()
        # Strip markdown code fences if present (```json ... ```)
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None
        if "name" not in data:
            return None
        # Normalise to the tool_calls dict shape the executor expects.
        args = data.get("arguments") or data.get("args") or {}
        return {"name": data["name"], "args": args}

    @staticmethod
    def _truncate(value: Any, limit: int = 4000) -> Any:
        """Avoid bloating memory with huge tool outputs (e.g. CSV dumps)."""
        text = value if isinstance(value, str) else str(value)
        if len(text) <= limit:
            return value
        return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


# Compatibility alias for existing code
AgentExecutor = Executor
