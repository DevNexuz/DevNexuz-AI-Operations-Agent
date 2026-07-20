"""
Built-in benchmark cases.

Four scenarios over the bundled sample datasets, mirroring the example
goals users actually run. Checks are strict on purpose: a small local
model that writes a report but names the wrong top region SHOULD fail —
that difference between providers is exactly what the benchmark exists
to show.
"""

from evals.schema import CheckSpec, EvalCase


BUILTIN_CASES: list[EvalCase] = [
    EvalCase(
        id="sales_top_regions",
        description="Aggregate revenue by region, chart it, name the true leader.",
        goal_template=(
            "Analyze {dataset} and find the top regions by total revenue. "
            "Generate a bar chart and write a report."
        ),
        dataset="data/sales.csv",
        checks=[
            CheckSpec(kind="no_failed_steps"),
            CheckSpec(kind="tool_was_used", tool="aggregate_by"),
            CheckSpec(kind="report_exists"),
            CheckSpec(kind="chart_exists"),
            CheckSpec(kind="agg_top_group", group_by="region", metric="revenue", agg="sum"),
            CheckSpec(kind="max_steps", limit=8),
        ],
    ),
    EvalCase(
        id="sales_anomalies",
        description="Detect revenue outliers and explain them in a report.",
        goal_template=(
            "Detect anomalies in the revenue column of {dataset} and write a "
            "report explaining what you found."
        ),
        dataset="data/sales.csv",
        checks=[
            CheckSpec(kind="no_failed_steps"),
            CheckSpec(kind="tool_was_used", tool="detect_anomalies"),
            CheckSpec(kind="report_exists"),
            # Stem matches anomaly/anomalies/anomalías alike.
            CheckSpec(kind="report_contains", text="anomal"),
            CheckSpec(kind="report_min_insights", min_count=2),
            CheckSpec(kind="max_steps", limit=8),
        ],
    ),
    EvalCase(
        id="employees_salaries",
        description="Average salary by department; report must name the true top.",
        goal_template=(
            "Analyze {dataset}: compute the average salary by department and "
            "write a report with your findings."
        ),
        dataset="data/employees.csv",
        checks=[
            CheckSpec(kind="no_failed_steps"),
            CheckSpec(kind="tool_was_used", tool="aggregate_by"),
            CheckSpec(kind="report_exists"),
            CheckSpec(kind="agg_top_group", group_by="department", metric="salary", agg="mean"),
            CheckSpec(kind="max_steps", limit=8),
        ],
    ),
    EvalCase(
        id="tickets_by_category",
        description="Ticket volume by category with a chart.",
        goal_template=(
            "Summarize the support tickets in {dataset}: how many tickets per "
            "category? Include a chart and write a report."
        ),
        dataset="data/tickets.csv",
        checks=[
            CheckSpec(kind="no_failed_steps"),
            CheckSpec(kind="report_exists"),
            CheckSpec(kind="chart_exists"),
            CheckSpec(kind="report_min_insights", min_count=2),
            CheckSpec(kind="max_steps", limit=8),
        ],
    ),
]


def get_cases(ids: list[str] | None = None) -> list[EvalCase]:
    """All built-in cases, optionally filtered by id."""
    if not ids:
        return list(BUILTIN_CASES)
    by_id = {c.id: c for c in BUILTIN_CASES}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise KeyError(f"Unknown case ids: {unknown}. Known: {list(by_id)}")
    return [by_id[i] for i in ids]
