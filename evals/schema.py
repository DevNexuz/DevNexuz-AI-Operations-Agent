"""
Eval schema — cases, checks, and result records.

An EvalCase is a goal template plus a list of deterministic checks.
Checks never call an LLM: they assert on the run's memory, the files it
produced, and ground truth recomputed with pandas from the dataset.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


CheckKind = Literal[
    "no_failed_steps",     # every executed step succeeded
    "tool_was_used",       # a specific tool ran successfully (params: tool)
    "report_exists",       # a Markdown report was written
    "report_contains",     # report text contains a substring (params: text)
    "report_min_insights", # report has >= N insight bullets (params: min_count)
    "chart_exists",        # at least one PNG chart was produced
    "agg_top_group",       # report names the true top group and its value
                           #   (params: group_by, metric, agg)
    "max_steps",           # plan stayed within a step budget (params: limit)
]


class CheckSpec(BaseModel):
    """One deterministic assertion to run against a finished trial."""

    kind: CheckKind
    tool: Optional[str] = None
    text: Optional[str] = None
    min_count: Optional[int] = None
    limit: Optional[int] = None
    group_by: Optional[str] = None
    metric: Optional[str] = None
    agg: Literal["sum", "mean", "count"] = "sum"


class EvalCase(BaseModel):
    """A benchmark scenario: a goal to give the agent, and how to score it."""

    id: str
    description: str = ""
    goal_template: str = Field(
        description="Goal text with a {dataset} placeholder for the CSV path."
    )
    dataset: str = Field(description="Dataset path relative to the repo root.")
    checks: list[CheckSpec]


class CheckResult(BaseModel):
    kind: str
    passed: bool
    detail: str = ""


class TrialRecord(BaseModel):
    """Outcome of one end-to-end run of one case."""

    case_id: str
    trial: int
    success: bool                      # all checks passed and no crash
    checks: list[CheckResult] = Field(default_factory=list)
    n_steps: int = 0
    n_retries: int = 0
    latency_s: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None        # crash outside the checks, if any
    run_dir: str = ""


class BenchmarkResult(BaseModel):
    """All trials of one provider/model combination."""

    provider: str
    model: str
    trials_per_case: int
    records: list[TrialRecord] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.success for r in self.records) / len(self.records)
