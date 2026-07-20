"""
tests/test_eval_harness.py — CI coverage for the eval harness, no LLM.

The real benchmark (python -m evals.run) talks to providers and is never
collected by pytest. These tests exercise the same machinery through the
llm_pair_factory seam with fake LLMs, so CI catches breakage in the
schema, the checks, the runner isolation, and the report format.

Run with:
    pytest tests/test_eval_harness.py -v
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from agent.memory import AgentMemory, StepResult
from agent.planner import Plan, PlanStep
from evals.cases import BUILTIN_CASES, get_cases
from evals.checks import TrialContext, run_checks
from evals.report import to_markdown
from evals.runner import REPO_ROOT, run_benchmark, run_trial
from evals.schema import CheckSpec


# ---------------------------------------------------------------------------
# Fake LLM helpers (same shapes as tests/test_executor.py)
# ---------------------------------------------------------------------------

def _tool_call_message(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": "call_1", "type": "tool_call"}],
    )


def _fake_planner_llm(plan: Plan) -> BaseChatModel:
    """with_structured_output returns a Runnable so `prompt | llm` still works."""
    llm = MagicMock(spec=BaseChatModel)
    llm.with_structured_output.return_value = RunnableLambda(lambda _: plan)
    return llm


def _fake_executor_llm(responses: list[AIMessage]) -> BaseChatModel:
    bound = MagicMock()
    bound.invoke.side_effect = list(responses)
    llm = MagicMock(spec=BaseChatModel)
    llm.bind_tools.return_value = bound
    return llm


def _scripted_factory(plan: Plan, responses: list[AIMessage]):
    def factory():
        return _fake_planner_llm(plan), _fake_executor_llm(responses)
    return factory


# ---------------------------------------------------------------------------
# Case definitions are sane
# ---------------------------------------------------------------------------

class TestBuiltinCases:

    def test_ids_are_unique(self):
        ids = [c.id for c in BUILTIN_CASES]
        assert len(ids) == len(set(ids))

    def test_datasets_exist(self):
        for case in BUILTIN_CASES:
            assert (REPO_ROOT / case.dataset).exists(), case.dataset

    def test_goal_templates_format(self):
        for case in BUILTIN_CASES:
            goal = case.goal_template.format(dataset="X.csv")
            assert "X.csv" in goal

    def test_get_cases_filters(self):
        assert [c.id for c in get_cases(["sales_anomalies"])] == ["sales_anomalies"]

    def test_get_cases_rejects_unknown(self):
        with pytest.raises(KeyError):
            get_cases(["nope"])


# ---------------------------------------------------------------------------
# Checks against synthetic trial contexts
# ---------------------------------------------------------------------------

def _ctx(tmp_path: Path, memory: AgentMemory | None = None,
         report: str | None = None, chart: bool = False) -> TrialContext:
    if report is not None:
        (tmp_path / "outputs").mkdir(exist_ok=True)
        (tmp_path / "outputs" / "report.md").write_text(report, encoding="utf-8")
    if chart:
        (tmp_path / "outputs" / "charts").mkdir(parents=True, exist_ok=True)
        (tmp_path / "outputs" / "charts" / "c.png").write_bytes(b"png")
    return TrialContext(
        memory=memory or AgentMemory(goal="g"),
        run_dir=tmp_path,
        dataset_path=REPO_ROOT / "data" / "sales.csv",
    )


REPORT_WITH_INSIGHTS = """# Report

## 🔍 Key Insights

- First insight about revenue.
- Second insight about anomalies.

## ✅ Recommendations

- Do something.
"""


class TestChecks:

    def test_no_failed_steps_passes_and_fails(self, tmp_path):
        ok = AgentMemory(goal="g")
        ok.add_result(StepResult(step_id=1, status="success", tool_used="load_csv"))
        bad = AgentMemory(goal="g")
        bad.add_result(StepResult(step_id=1, status="error", error="x"))

        assert run_checks(_ctx(tmp_path, ok), [CheckSpec(kind="no_failed_steps")])[0].passed
        assert not run_checks(_ctx(tmp_path, bad), [CheckSpec(kind="no_failed_steps")])[0].passed

    def test_tool_was_used_requires_success(self, tmp_path):
        memory = AgentMemory(goal="g")
        memory.add_result(StepResult(step_id=1, status="error", tool_used="aggregate_by", error="x"))

        result = run_checks(
            _ctx(tmp_path, memory), [CheckSpec(kind="tool_was_used", tool="aggregate_by")]
        )[0]

        assert not result.passed

    def test_report_exists_and_contains(self, tmp_path):
        ctx = _ctx(tmp_path, report="Revenue anomalies were found.")

        results = run_checks(ctx, [
            CheckSpec(kind="report_exists"),
            CheckSpec(kind="report_contains", text="ANOMAL"),
            CheckSpec(kind="report_contains", text="unicorns"),
        ])

        assert [r.passed for r in results] == [True, True, False]

    def test_report_min_insights_counts_bullets(self, tmp_path):
        ctx = _ctx(tmp_path, report=REPORT_WITH_INSIGHTS)

        results = run_checks(ctx, [
            CheckSpec(kind="report_min_insights", min_count=2),
            CheckSpec(kind="report_min_insights", min_count=3),
        ])

        assert [r.passed for r in results] == [True, False]

    def test_chart_exists(self, tmp_path):
        with_chart = tmp_path / "with_chart"
        without_chart = tmp_path / "without_chart"
        with_chart.mkdir()
        without_chart.mkdir()

        assert run_checks(_ctx(with_chart, chart=True), [CheckSpec(kind="chart_exists")])[0].passed
        assert not run_checks(_ctx(without_chart), [CheckSpec(kind="chart_exists")])[0].passed

    def test_agg_top_group_uses_dynamic_ground_truth(self, tmp_path):
        """The check recomputes the top region from the CSV; a report naming it
        with a ~rounded value passes, one naming another region fails."""
        import pandas as pd
        df = pd.read_csv(REPO_ROOT / "data" / "sales.csv")
        series = df.groupby("region")["revenue"].sum()
        top_group, top_value = str(series.idxmax()), float(series.max())
        loser = str(series.idxmin())

        spec = CheckSpec(kind="agg_top_group", group_by="region", metric="revenue", agg="sum")

        good = _ctx(tmp_path, report=f"{top_group} leads with ${top_value:,.0f} in revenue.")
        assert run_checks(good, [spec])[0].passed

        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        bad = _ctx(bad_dir, report=f"{loser} leads with $1.00 in revenue.")
        assert not run_checks(bad, [spec])[0].passed

    def test_max_steps(self, tmp_path):
        memory = AgentMemory(goal="g")
        for i in range(3):
            memory.add_result(StepResult(step_id=i + 1, status="success", tool_used="t"))

        results = run_checks(_ctx(tmp_path, memory), [
            CheckSpec(kind="max_steps", limit=3),
            CheckSpec(kind="max_steps", limit=2),
        ])

        assert [r.passed for r in results] == [True, False]

    def test_crashing_check_is_a_failure_not_a_crash(self, tmp_path):
        # group_by=None makes pandas raise inside the check.
        spec = CheckSpec(kind="agg_top_group", group_by=None, metric="revenue")

        result = run_checks(_ctx(tmp_path), [spec])[0]

        assert not result.passed
        assert "crashed" in result.detail


# ---------------------------------------------------------------------------
# Runner end-to-end with scripted LLMs and real tools
# ---------------------------------------------------------------------------

class TestRunner:

    def test_trial_runs_real_tools_in_isolated_dir(self, tmp_path):
        """Scripted planner + executor drive REAL tools; outputs land in the
        per-trial dir and the memory dump is written there."""
        from evals.schema import EvalCase

        dataset = (REPO_ROOT / "data" / "sales.csv").as_posix()
        plan = Plan(
            goal="scripted", reasoning="scripted",
            steps=[PlanStep(id=1, description="load", suggested_tool="load_csv",
                            expected_output="dataset id")],
        )
        case = EvalCase(
            id="load_only", goal_template="Load {dataset}", dataset="data/sales.csv",
            checks=[CheckSpec(kind="no_failed_steps"),
                    CheckSpec(kind="tool_was_used", tool="load_csv")],
        )
        factory = _scripted_factory(
            plan, [_tool_call_message("load_csv", {"file_path": dataset})]
        )

        cwd_before = Path.cwd()
        record = run_trial(case, 1, factory, tmp_path)

        assert Path.cwd() == cwd_before  # cwd restored
        assert record.success, record
        assert record.n_steps == 1
        assert (Path(record.run_dir) / "outputs" / "agent_memory.json").exists()

    def test_crashing_planner_is_recorded_not_raised(self, tmp_path):
        from evals.schema import EvalCase

        def exploding_factory():
            llm = MagicMock(spec=BaseChatModel)
            llm.with_structured_output.return_value = RunnableLambda(
                lambda _: (_ for _ in ()).throw(RuntimeError("planner down"))
            )
            return llm, _fake_executor_llm([])

        case = EvalCase(
            id="crash", goal_template="{dataset}", dataset="data/sales.csv",
            checks=[CheckSpec(kind="report_exists")],
        )

        record = run_trial(case, 1, exploding_factory, tmp_path)

        assert not record.success
        assert "planner down" in (record.error or "")

    def test_benchmark_aggregates_and_reports(self, tmp_path):
        from evals.schema import EvalCase

        dataset = (REPO_ROOT / "data" / "sales.csv").as_posix()
        plan = Plan(
            goal="scripted", reasoning="scripted",
            steps=[PlanStep(id=1, description="load", suggested_tool="load_csv",
                            expected_output="dataset id")],
        )
        case = EvalCase(
            id="load_only", goal_template="Load {dataset}", dataset="data/sales.csv",
            checks=[CheckSpec(kind="no_failed_steps")],
        )

        def factory():
            return (
                _fake_planner_llm(plan),
                _fake_executor_llm([_tool_call_message("load_csv", {"file_path": dataset})]),
            )

        result = run_benchmark(
            cases=[case], llm_pair_factory=factory, base_dir=tmp_path,
            provider="fake", model="scripted", trials=2,
        )

        assert result.success_rate == 1.0
        assert len(result.records) == 2

        markdown = to_markdown(result)
        assert "| fake | scripted | 100% (2/2) |" in markdown
        assert "load_only" in markdown
