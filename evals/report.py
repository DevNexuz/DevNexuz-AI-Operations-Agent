"""
Benchmark reporting — aggregate TrialRecords into Markdown + JSON.

The summary table is designed to be pasted straight into the README:
one row per provider/model, plus a per-case breakdown for debugging.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.schema import BenchmarkResult, TrialRecord


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _tokens_cell(records: list[TrialRecord]) -> str:
    tracked = [r for r in records if r.input_tokens is not None]
    if not tracked:
        return "—"
    total_in = sum(r.input_tokens or 0 for r in tracked)
    total_out = sum(r.output_tokens or 0 for r in tracked)
    return f"{total_in:,} in / {total_out:,} out"


def summary_row(result: BenchmarkResult) -> str:
    r = result.records
    return (
        f"| {result.provider} | {result.model} | "
        f"{result.success_rate:.0%} ({sum(x.success for x in r)}/{len(r)}) | "
        f"{_avg([x.n_steps for x in r]):.1f} | "
        f"{_avg([x.n_retries for x in r]):.1f} | "
        f"{_avg([x.latency_s for x in r]):.1f}s | "
        f"{_tokens_cell(r)} |"
    )


SUMMARY_HEADER = (
    "| Provider | Model | Success | Avg steps | Avg retries | Avg latency | Tokens |\n"
    "|---|---|---|---|---|---|---|"
)


def to_markdown(result: BenchmarkResult) -> str:
    """Full Markdown report: summary table + per-case breakdown."""
    lines = [
        f"# Benchmark — {result.provider} / {result.model}",
        "",
        f"{len(result.records)} trials "
        f"({result.trials_per_case} per case). Deterministic checks, no LLM judge.",
        "",
        SUMMARY_HEADER,
        summary_row(result),
        "",
        "## Per case",
        "",
        "| Case | Trial | Success | Steps | Retries | Latency | Failed checks |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in result.records:
        if r.error:
            failed = f"CRASH: {r.error}"
        else:
            failed = ", ".join(c.kind for c in r.checks if not c.passed) or "—"
        lines.append(
            f"| {r.case_id} | {r.trial} | {'✅' if r.success else '❌'} | "
            f"{r.n_steps} | {r.n_retries} | {r.latency_s:.1f}s | {failed} |"
        )

    lines += ["", "## Check details", ""]
    for r in result.records:
        lines.append(f"### {r.case_id} — trial {r.trial}")
        if r.error:
            lines.append(f"- 💥 crashed before scoring: `{r.error}`")
        for c in r.checks:
            lines.append(f"- {'✅' if c.passed else '❌'} `{c.kind}` — {c.detail}")
        lines.append(f"- 📁 run dir: `{r.run_dir}`")
        lines.append("")

    return "\n".join(lines)


def save(result: BenchmarkResult, output: Path) -> None:
    """Write the Markdown report and a JSON dump next to it."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(to_markdown(result), encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
