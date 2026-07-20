"""
Deterministic checks — score a finished trial without an LLM judge.

Ground truth is recomputed from the dataset with pandas at check time
(never hardcoded), so regenerating the sample data can't silently break
the benchmark. Numeric matching against the report is fuzzy: thousands
separators are ignored and values match within a 1% tolerance, because
models legitimately round.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from agent.memory import AgentMemory
from evals.schema import CheckResult, CheckSpec


@dataclass
class TrialContext:
    """Everything a check may inspect about a finished trial."""

    memory: AgentMemory
    run_dir: Path        # cwd during the trial; tools wrote outputs/ under it
    dataset_path: Path   # absolute path to the CSV the goal referenced


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _report_path(ctx: TrialContext) -> Path | None:
    """Locate the Markdown report the run produced, if any."""
    registered = ctx.memory.artifacts.get("final_report")
    if registered:
        path = Path(registered)
        if not path.is_absolute():
            path = ctx.run_dir / path
        if path.exists():
            return path
    candidates = sorted((ctx.run_dir / "outputs").glob("*.md"))
    return candidates[0] if candidates else None


def _report_text(ctx: TrialContext) -> str:
    path = _report_path(ctx)
    return path.read_text(encoding="utf-8") if path else ""


def _numbers_in(text: str) -> list[float]:
    """All numbers in the text, thousands separators stripped."""
    values = []
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _insight_bullets(text: str) -> list[str]:
    """Bullets under the Key Insights heading (format of write_report)."""
    lines = text.splitlines()
    bullets: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith("## "):
            in_section = "insight" in line.lower()
            continue
        if in_section and line.strip().startswith("- "):
            bullets.append(line.strip())
    return bullets


# -----------------------------------------------------------------------------
# Check implementations
# -----------------------------------------------------------------------------

def _check_no_failed_steps(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    failed = [r.step_id for r in ctx.memory.results if r.status == "error"]
    return CheckResult(
        kind=spec.kind,
        passed=not failed,
        detail=f"failed steps: {failed}" if failed else "all steps succeeded",
    )


def _check_tool_was_used(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    used = {r.tool_used for r in ctx.memory.results if r.status == "success"}
    return CheckResult(
        kind=spec.kind,
        passed=spec.tool in used,
        detail=f"expected '{spec.tool}', successful tools: {sorted(t for t in used if t)}",
    )


def _check_report_exists(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    path = _report_path(ctx)
    return CheckResult(
        kind=spec.kind,
        passed=path is not None,
        detail=str(path) if path else "no report file found under outputs/",
    )


def _check_report_contains(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    text = _report_text(ctx)
    found = (spec.text or "").lower() in text.lower()
    return CheckResult(
        kind=spec.kind,
        passed=found,
        detail=f"substring '{spec.text}' {'found' if found else 'NOT found'} in report",
    )


def _check_report_min_insights(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    bullets = _insight_bullets(_report_text(ctx))
    needed = spec.min_count or 1
    return CheckResult(
        kind=spec.kind,
        passed=len(bullets) >= needed,
        detail=f"{len(bullets)} insight bullets (needed >= {needed})",
    )


def _check_chart_exists(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    charts = list((ctx.run_dir / "outputs" / "charts").glob("*.png"))
    return CheckResult(
        kind=spec.kind,
        passed=bool(charts),
        detail=f"{len(charts)} chart(s) produced",
    )


def _check_agg_top_group(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    """The report must name the ACTUAL top group, recomputed from the data,
    and mention its value within 1% (separator-insensitive)."""
    df = pd.read_csv(ctx.dataset_path)
    if spec.agg == "count":
        series = df.groupby(spec.group_by).size()
    else:
        series = df.groupby(spec.group_by)[spec.metric].agg(spec.agg)
    top_group = str(series.idxmax())
    top_value = float(series.max())

    text = _report_text(ctx)
    group_ok = top_group.lower() in text.lower()
    value_ok = any(
        abs(n - top_value) <= 0.01 * abs(top_value) for n in _numbers_in(text)
    )
    return CheckResult(
        kind=spec.kind,
        passed=group_ok and value_ok,
        detail=(
            f"true top: {top_group} = {top_value:,.2f} | "
            f"group named: {group_ok}, value (±1%) present: {value_ok}"
        ),
    )


def _check_max_steps(ctx: TrialContext, spec: CheckSpec) -> CheckResult:
    n = len(ctx.memory.results)
    limit = spec.limit or 10
    return CheckResult(
        kind=spec.kind,
        passed=n <= limit,
        detail=f"{n} steps executed (budget {limit})",
    )


_CHECKS = {
    "no_failed_steps": _check_no_failed_steps,
    "tool_was_used": _check_tool_was_used,
    "report_exists": _check_report_exists,
    "report_contains": _check_report_contains,
    "report_min_insights": _check_report_min_insights,
    "chart_exists": _check_chart_exists,
    "agg_top_group": _check_agg_top_group,
    "max_steps": _check_max_steps,
}


def run_checks(ctx: TrialContext, specs: list[CheckSpec]) -> list[CheckResult]:
    """Run every check; a crash inside a check is a failed check, not a crash."""
    results = []
    for spec in specs:
        try:
            results.append(_CHECKS[spec.kind](ctx, spec))
        except Exception as exc:  # noqa: BLE001 — scoring must never kill the run
            results.append(
                CheckResult(
                    kind=spec.kind,
                    passed=False,
                    detail=f"check crashed: {type(exc).__name__}: {exc}",
                )
            )
    return results
