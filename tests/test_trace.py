"""
tests/test_trace.py — Unit tests for the trace parser and artifact backfill.

parse_trace() consumes persisted agent_memory.json dumps, which come in
three flavors it must survive: complete modern dumps, dumps with retries
recorded in the log, and legacy/partial dumps missing keys entirely.

Run with:
    pytest tests/test_trace.py -v
"""

import pytest

from agent.memory import AgentMemory, StepResult
from agent.trace import parse_trace


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _dump(
    results: list[dict] | None = None,
    log: list[dict] | None = None,
    plan_steps: list[dict] | None = None,
    artifacts: dict | None = None,
) -> dict:
    return {
        "goal": "Analyze data/sales.csv",
        "plan": {
            "goal": "Analyze data/sales.csv",
            "reasoning": "Load then analyze.",
            "steps": plan_steps
            or [
                {"id": 1, "description": "Load the CSV", "suggested_tool": "load_csv"},
                {"id": 2, "description": "Aggregate revenue", "suggested_tool": "aggregate_by"},
            ],
        },
        "results": results if results is not None else [],
        "artifacts": artifacts or {},
        "log": log if log is not None else [],
    }


def _result(step_id: int, status: str = "success", **kw) -> dict:
    base = {
        "step_id": step_id,
        "status": status,
        "tool_used": "load_csv",
        "output": {"rows": 10},
        "error": None,
        "timestamp": "2026-07-20T10:00:00",
    }
    base.update(kw)
    return base


def _log(message: str, timestamp: str = "2026-07-20T10:00:00") -> dict:
    return {"timestamp": timestamp, "phase": "executor", "message": message, "data": None}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestParseTraceBasics:

    def test_counts_and_goal(self):
        data = _dump(results=[_result(1), _result(2, status="error", error="boom", output=None)])

        trace = parse_trace(data)

        assert trace.goal == "Analyze data/sales.csv"
        assert trace.total_steps == 2
        assert trace.succeeded == 1
        assert trace.failed == 1

    def test_steps_carry_plan_context(self):
        data = _dump(results=[_result(1)])

        trace = parse_trace(data)

        assert trace.steps[0].description == "Load the CSV"
        assert trace.steps[0].suggested_tool == "load_csv"

    def test_duration_from_log_timestamps(self):
        data = _dump(
            results=[_result(1)],
            log=[
                _log("Plan generated", "2026-07-20T10:00:00"),
                _log("Step 1 -> success", "2026-07-20T10:00:42"),
            ],
        )

        trace = parse_trace(data)

        assert trace.duration_seconds == pytest.approx(42.0)

    def test_artifacts_pass_through(self):
        data = _dump(results=[_result(1)], artifacts={"final_report": "outputs/report.md"})

        trace = parse_trace(data)

        assert trace.artifacts == {"final_report": "outputs/report.md"}


# ---------------------------------------------------------------------------
# Retry reconstruction from executor log lines
# ---------------------------------------------------------------------------

class TestRetryReconstruction:

    def test_success_after_one_failed_attempt(self):
        """One logged failure + success result = 2 attempts, 1 retry."""
        data = _dump(
            results=[_result(1)],
            log=[_log("Step 1 attempt 1 failed: ToolExecutionError: bad column")],
        )

        trace = parse_trace(data)
        step = trace.steps[0]

        assert step.attempts == 2
        assert trace.total_retries == 1
        assert step.retry_errors == ["ToolExecutionError: bad column"]

    def test_exhausted_retries_keep_final_error_separate(self):
        """Two logged failures + error result = 2 attempts; the retried error
        is the first one, the final error lives in the result itself."""
        data = _dump(
            results=[_result(1, status="error", error="second failure", output=None)],
            log=[
                _log("Step 1 attempt 1 failed: first failure"),
                _log("Step 1 attempt 2 failed: second failure"),
            ],
        )

        trace = parse_trace(data)
        step = trace.steps[0]

        assert step.attempts == 2
        assert step.retry_errors == ["first failure"]
        assert step.error == "second failure"

    def test_clean_run_has_zero_retries(self):
        data = _dump(results=[_result(1), _result(2)])

        trace = parse_trace(data)

        assert trace.total_retries == 0
        assert all(s.attempts == 1 for s in trace.steps)

    def test_retries_attach_to_the_right_step(self):
        data = _dump(
            results=[_result(1), _result(2)],
            log=[_log("Step 2 attempt 1 failed: whoops")],
        )

        trace = parse_trace(data)

        assert trace.steps[0].attempts == 1
        assert trace.steps[1].attempts == 2


# ---------------------------------------------------------------------------
# Legacy / partial / malformed dumps
# ---------------------------------------------------------------------------

class TestDefensiveParsing:

    def test_empty_dump(self):
        trace = parse_trace({})

        assert trace.total_steps == 0
        assert trace.duration_seconds is None
        assert trace.artifacts == {}

    def test_non_dict_raises(self):
        with pytest.raises(ValueError):
            parse_trace(["not", "a", "dump"])

    def test_result_without_matching_plan_step(self):
        """Steps the plan doesn't know about still show up, undescribed."""
        data = _dump(results=[_result(99)])

        trace = parse_trace(data)

        assert trace.steps[0].step_id == 99
        assert trace.steps[0].description == ""

    def test_garbage_entries_are_skipped(self):
        data = _dump(results=[_result(1)])
        data["log"].append("not a dict")
        data["results"].append({"no_step_id": True})

        trace = parse_trace(data)

        assert trace.total_steps == 1

    def test_unparsable_timestamps_do_not_crash(self):
        data = _dump(results=[_result(1)], log=[_log("hello", timestamp="not-a-date")])

        trace = parse_trace(data)

        assert trace.duration_seconds is None


# ---------------------------------------------------------------------------
# AgentMemory.register_artifacts_from_results
# ---------------------------------------------------------------------------

class TestRegisterArtifacts:

    def _memory_with_outputs(self) -> AgentMemory:
        memory = AgentMemory(goal="g")
        memory.add_result(StepResult(step_id=1, status="success", tool_used="load_csv",
                                     output={"dataset_id": "ds_1"}))
        memory.add_result(StepResult(step_id=2, status="success", tool_used="generate_chart",
                                     output={"chart_path": "outputs/charts/a.png"}))
        memory.add_result(StepResult(step_id=3, status="success", tool_used="write_report",
                                     output={"report_path": "outputs/report.md"}))
        return memory

    def test_registers_charts_and_report(self):
        memory = self._memory_with_outputs()

        memory.register_artifacts_from_results()

        assert memory.artifacts["chart_1"] == "outputs/charts/a.png"
        assert memory.artifacts["final_report"] == "outputs/report.md"

    def test_is_idempotent(self):
        memory = self._memory_with_outputs()

        memory.register_artifacts_from_results()
        before = dict(memory.artifacts)
        log_len = len(memory.log)
        memory.register_artifacts_from_results()

        assert memory.artifacts == before
        assert len(memory.log) == log_len  # no duplicate log spam

    def test_failed_steps_are_ignored(self):
        memory = AgentMemory(goal="g")
        memory.add_result(StepResult(step_id=1, status="error", tool_used="generate_chart",
                                     error="nope"))

        memory.register_artifacts_from_results()

        assert memory.artifacts == {}
