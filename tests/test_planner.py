"""
tests/test_planner.py — Unit tests for the Planner component.

The Planner talks to an LLM, so we mock it out completely.
No API key, no network call, no Ollama required — ever.

The goal is to test the Planner's own logic:
  - Does it correctly invoke the prompt | structured_llm chain?
  - Does it normalize dict responses to Plan objects?
  - Does it raise ValueError on empty step lists?
  - Does PlanStep enforce its required fields?

Run with:
    pytest tests/test_planner.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.language_models.chat_models import BaseChatModel

from agent.planner import Plan, PlanStep, Planner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOLS_CATALOG = "- **load_csv**(file_path): Load a CSV file."


def _minimal_step(step_id: int = 1) -> PlanStep:
    return PlanStep(
        id=step_id,
        description="Load the CSV file",
        suggested_tool="load_csv",
        expected_output="dataset_id",
    )


def _minimal_plan(steps=None) -> Plan:
    return Plan(
        goal="Analyze data/sales.csv",
        reasoning="Start by loading the data",
        steps=steps if steps is not None else [_minimal_step()],
    )


def _make_planner_with_result(invoke_result) -> Planner:
    """
    Build a Planner with a fully mocked LangChain chain.

    LangChain's Planner does:
        structured_llm = self.llm.with_structured_output(Plan)
        chain = self.prompt | structured_llm   # __or__ is on the PROMPT
        result = chain.invoke({...})

    So we patch build_planner_prompt to return a fake prompt whose
    __or__ gives us a chain whose invoke returns `invoke_result`.
    """
    fake_chain = MagicMock()
    fake_chain.invoke.return_value = invoke_result

    fake_prompt = MagicMock()
    # __or__ is called as: fake_prompt | structured_llm → fake_chain
    fake_prompt.__or__ = MagicMock(return_value=fake_chain)

    fake_llm = MagicMock(spec=BaseChatModel)
    # with_structured_output returns something; the actual chain comes from prompt.__or__
    fake_llm.with_structured_output.return_value = MagicMock()

    with patch("agent.planner.build_planner_prompt", return_value=fake_prompt):
        planner = Planner(llm=fake_llm, tools_catalog=TOOLS_CATALOG)

    # Keep fake_chain accessible for assertions if needed
    planner._fake_chain = fake_chain
    return planner


# ---------------------------------------------------------------------------
# Planner.plan() — happy path
# ---------------------------------------------------------------------------

class TestPlannerHappyPath:

    def test_returns_plan_instance(self):
        """plan() must return a Plan object when the LLM succeeds."""
        planner = _make_planner_with_result(_minimal_plan())

        result = planner.plan("Analyze data/sales.csv")

        assert isinstance(result, Plan)

    def test_plan_has_at_least_one_step(self):
        """A valid plan must have at least one step."""
        planner = _make_planner_with_result(_minimal_plan())

        result = planner.plan("Analyze data/sales.csv")

        assert len(result.steps) >= 1

    def test_plan_goal_is_preserved(self):
        """The plan object must carry the original goal."""
        plan = _minimal_plan()
        planner = _make_planner_with_result(plan)

        result = planner.plan("Analyze data/sales.csv")

        assert result.goal == plan.goal

    def test_normalizes_dict_response_to_plan(self):
        """When the LLM returns a dict, Planner must convert it to a Plan."""
        plan_dict = {
            "goal": "Analyze data",
            "reasoning": "Simple plan",
            "steps": [
                {
                    "id": 1,
                    "description": "Load CSV",
                    "suggested_tool": "load_csv",
                    "expected_output": "dataset_id",
                }
            ],
        }
        planner = _make_planner_with_result(plan_dict)

        result = planner.plan("Analyze data")

        assert isinstance(result, Plan)
        assert len(result.steps) == 1


# ---------------------------------------------------------------------------
# Planner.plan() — error handling
# ---------------------------------------------------------------------------

class TestPlannerErrorHandling:

    def test_raises_on_empty_steps(self):
        """A plan with zero steps must raise ValueError — unusable for executor."""
        planner = _make_planner_with_result(_minimal_plan(steps=[]))

        with pytest.raises(ValueError, match="zero steps"):
            planner.plan("Analyze data/sales.csv")

    def test_raises_when_llm_raises(self):
        """If the LLM chain throws, Planner must not swallow the exception."""
        fake_chain = MagicMock()
        fake_chain.invoke.side_effect = RuntimeError("LLM timeout")

        fake_prompt = MagicMock()
        fake_prompt.__or__ = MagicMock(return_value=fake_chain)

        fake_llm = MagicMock(spec=BaseChatModel)
        fake_llm.with_structured_output.return_value = MagicMock()

        with patch("agent.planner.build_planner_prompt", return_value=fake_prompt):
            planner = Planner(llm=fake_llm, tools_catalog=TOOLS_CATALOG)

        with pytest.raises(RuntimeError, match="LLM timeout"):
            planner.plan("Analyze data/sales.csv")


# ---------------------------------------------------------------------------
# PlanStep — field validation
# ---------------------------------------------------------------------------

class TestPlanStepFields:

    def test_step_has_required_fields(self):
        """Every PlanStep must expose id, description, and suggested_tool."""
        step = _minimal_step()

        assert hasattr(step, "id")
        assert hasattr(step, "description")
        assert hasattr(step, "suggested_tool")
        assert hasattr(step, "expected_output")

    def test_step_id_is_int(self):
        step = _minimal_step(step_id=3)
        assert isinstance(step.id, int)
        assert step.id == 3

    def test_step_dependencies_defaults_to_empty_list(self):
        """dependencies must default to [] — no required fields beyond the basics."""
        step = _minimal_step()
        assert step.dependencies == []

    def test_multi_step_plan_ids_are_sequential(self):
        """A well-formed plan has steps with sequential 1-based ids."""
        steps = [_minimal_step(i) for i in range(1, 4)]
        plan = _minimal_plan(steps=steps)

        ids = [s.id for s in plan.steps]
        assert ids == [1, 2, 3]
