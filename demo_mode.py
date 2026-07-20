"""
Demo mode — runs the full agent UI with pre-recorded responses.

Goal: let anyone try the project end-to-end without configuring an
API key. We bypass the LLM entirely and replay a deterministic plan +
deterministic tool calls. The Rich UI looks identical to a real run.

This is also what you record for the README's demo.gif.
"""

from __future__ import annotations

import time
from pathlib import Path

from agent import logger as terminal_ui
from agent.memory import AgentMemory, StepResult
from agent.planner import Plan, PlanStep
from tools.analysis_tools import (
    aggregate_by,
    detect_anomalies,
    generate_chart,
    top_n,
)
from tools.csv_tools import load_csv, profile_dataset
from tools.report_tools import write_report


DEMO_GOAL = (
    "Analyze data/sales.csv and generate a report with the top regions, "
    "any anomalies, and a chart."
)

# Slow down the simulated steps so the demo *feels* like an agent thinking.
STEP_DELAY_S = 0.6


def _demo_plan() -> Plan:
    return Plan(
        goal=DEMO_GOAL,
        reasoning=(
            "We first load and profile the dataset to understand its structure, "
            "then aggregate revenue by region, find the top products, detect "
            "outliers in revenue, generate a chart, and finally compile a report."
        ),
        steps=[
            PlanStep(
                id=1,
                description="Load the sales dataset.",
                suggested_tool="load_csv",
                expected_output="Dataset id and shape.",
            ),
            PlanStep(
                id=2,
                description="Profile the dataset to understand columns and stats.",
                suggested_tool="profile_dataset",
                expected_output="Profile dict with dtypes and summaries.",
            ),
            PlanStep(
                id=3,
                description="Aggregate revenue by region.",
                suggested_tool="aggregate_by",
                expected_output="Revenue per region, sorted descending.",
            ),
            PlanStep(
                id=4,
                description="Find the top 5 orders by revenue.",
                suggested_tool="top_n",
                expected_output="Top 5 rows by revenue.",
            ),
            PlanStep(
                id=5,
                description="Detect revenue anomalies.",
                suggested_tool="detect_anomalies",
                expected_output="List of revenue outliers.",
            ),
            PlanStep(
                id=6,
                description="Generate a bar chart of revenue per region.",
                suggested_tool="generate_chart",
                expected_output="Path to the chart image.",
            ),
            PlanStep(
                id=7,
                description="Write the final Markdown report.",
                suggested_tool="write_report",
                expected_output="Path to outputs/report.md.",
            ),
        ],
    )


def run_demo_flow(ui=None) -> int:
    """Replay a full agent run using real tools + a hardcoded plan.

    Args:
        ui: Renderer implementing the logger protocol (banner, show_plan,
            step_start, step_success, info, warn, final_summary). Defaults
            to the Rich terminal logger; the Streamlit app injects its own.
    """
    if ui is None:
        ui = terminal_ui

    ui.info("🎬 Demo mode — no API key required. Using mocked agent responses.\n")
    ui.banner(DEMO_GOAL)

    memory = AgentMemory(goal=DEMO_GOAL)
    plan = _demo_plan()
    memory.set_plan(plan.model_dump())
    ui.show_plan(plan)

    if not Path("data/sales.csv").exists():
        ui.warn("data/sales.csv not found — generating sample data now.")
        from data.generate_samples import main as generate
        generate()

    # Step 1: load_csv
    step = plan.steps[0]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out1 = load_csv.invoke({"file_path": "data/sales.csv"})
    dataset_id = out1["dataset_id"]
    r = StepResult(step_id=1, status="success", tool_used="load_csv", output=out1)
    memory.add_result(r)
    ui.step_success(step, r)

    # Step 2: profile_dataset
    step = plan.steps[1]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out2 = profile_dataset.invoke({"dataset_id": dataset_id})
    r = StepResult(step_id=2, status="success", tool_used="profile_dataset", output=out2)
    memory.add_result(r)
    ui.step_success(step, r)

    # Step 3: aggregate_by
    step = plan.steps[2]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out3 = aggregate_by.invoke({
        "dataset_id": dataset_id,
        "group_by": "region",
        "metric": "revenue",
        "agg": "sum",
    })
    r = StepResult(step_id=3, status="success", tool_used="aggregate_by", output=out3)
    memory.add_result(r)
    ui.step_success(step, r)

    # Step 4: top_n
    step = plan.steps[3]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out4 = top_n.invoke({
        "dataset_id": dataset_id,
        "sort_by": "revenue",
        "n": 5,
        "ascending": False,
    })
    r = StepResult(step_id=4, status="success", tool_used="top_n", output=out4)
    memory.add_result(r)
    ui.step_success(step, r)

    # Step 5: detect_anomalies
    step = plan.steps[4]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out5 = detect_anomalies.invoke({
        "dataset_id": dataset_id,
        "column": "revenue",
        "z_threshold": 3.0,
    })
    r = StepResult(step_id=5, status="success", tool_used="detect_anomalies", output=out5)
    memory.add_result(r)
    ui.step_success(step, r)

    # Step 6: generate_chart
    step = plan.steps[5]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)
    out6 = generate_chart.invoke({
        "dataset_id": dataset_id,
        "chart_type": "bar",
        "x": "region",
        "y": "revenue",
        "title": "Revenue by Region",
        "filename": "revenue_by_region.png",
    })
    r = StepResult(step_id=6, status="success", tool_used="generate_chart", output=out6)
    memory.add_result(r)
    memory.add_artifact("revenue_by_region_chart", out6["chart_path"])
    ui.step_success(step, r)

    # Step 7: write_report
    step = plan.steps[6]
    ui.step_start(step, len(plan.steps))
    time.sleep(STEP_DELAY_S)

    # Build narrative content from the actual tool outputs above.
    region_results = out3["result"]
    top_region = next(iter(region_results))
    anomaly_count = out5.get("count", 0)

    insights = [
        f"**{top_region}** is the top-performing region with "
        f"${region_results[top_region]:,.0f} in total revenue.",
        f"The top 5 orders alone account for a sizeable portion of total revenue, "
        f"suggesting a long-tail distribution.",
        f"{anomaly_count} revenue outliers were flagged "
        f"(z-score > 3) — these warrant closer inspection.",
    ]
    recommendations = [
        f"Investigate the {anomaly_count} anomalous orders to confirm they are "
        f"legitimate (large enterprise deals) and not data-entry errors.",
        f"Replicate the playbook from {top_region} into lower-performing regions.",
        "Consider segmenting analyses by channel and product for deeper insights.",
    ]

    out7 = write_report.invoke({
        "title": "Sales Performance Report",
        "executive_summary": (
            f"Across all regions in 2024, {top_region} leads in revenue. "
            f"{anomaly_count} unusually large orders were detected and should be "
            "validated. Overall sales distribution is healthy but concentrated."
        ),
        "insights": insights,
        "recommendations": recommendations,
        "chart_paths": [out6["chart_path"]],
        "filename": "report.md",
    })
    r = StepResult(step_id=7, status="success", tool_used="write_report", output=out7)
    memory.add_result(r)
    memory.add_artifact("final_report", out7["report_path"])
    ui.step_success(step, r)

    # Persist + final summary
    memory.save_to_json("outputs/agent_memory.json")
    ui.info("Decision log saved to outputs/agent_memory.json")
    ui.final_summary(memory)
    return 0
