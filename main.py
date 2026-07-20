"""
AI Operations Agent — CLI entry point.

This is what the user runs. It wires together:
    - LLM (multi-provider via llm_factory)
    - Planner + Executor (the agent core)
    - Tools (CSV, analysis, report)
    - Memory + Logger (state + UX)

Run:
    python main.py --goal "Analyze data/sales.csv and generate insights"
    python main.py --demo                  # No API key required
    python main.py --list-examples         # Show example goals
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent import logger as ui
from agent.executor import Executor
from agent.llm_factory import (
    LLMConfigError,
    get_planner_llm,
    get_reasoning_llm,
)
from agent.memory import AgentMemory
from agent.planner import Planner
from tools import ALL_TOOLS, build_tools_catalog


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
OUTPUTS_DIR = Path("outputs")
DATA_DIR = Path("data")
MEMORY_DUMP = OUTPUTS_DIR / "agent_memory.json"


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-ops-agent",
        description=(
            "Autonomous AI agent that turns high-level goals into "
            "actionable insights from your data."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --goal \"Analyze data/sales.csv and find top regions\"\n"
            "  python main.py --demo\n"
            "  python main.py --list-examples\n"
        ),
    )
    parser.add_argument(
        "--goal",
        type=str,
        help="The objective for the agent, in natural language.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with mocked responses — no API key required.",
    )
    parser.add_argument(
        "--list-examples",
        action="store_true",
        help="Print example goals and exit.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM_PROVIDER from .env (openai|anthropic|groq|ollama).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM_MODEL from .env.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        choices=["en", "es"],
        help="Output language for the final report. Defaults to REPORT_LANGUAGE in .env.",
    )
    return parser


# -----------------------------------------------------------------------------
# Bootstrap helpers
# -----------------------------------------------------------------------------
def ensure_sample_data() -> None:
    """Generate sample CSVs the first time the user runs the agent."""
    expected = ["sales.csv", "employees.csv", "tickets.csv"]
    if all((DATA_DIR / f).exists() for f in expected):
        return

    ui.info("Sample datasets not found. Generating them now...")
    try:
        # Imported lazily because data generation is a one-time cost.
        from data.generate_samples import main as generate
        generate()
    except Exception as exc:  # noqa: BLE001
        ui.warn(f"Could not auto-generate sample data: {exc}")
        ui.warn("You can still point --goal at your own CSV file.")


def print_examples() -> None:
    examples_path = Path("examples/example_goals.md")
    if examples_path.exists():
        ui.info(f"See {examples_path} for a full list. Quick picks:\n")
    quick = [
        'python main.py --goal "Analyze data/sales.csv and find the top 3 regions"',
        'python main.py --goal "Detect salary anomalies in data/employees.csv"',
        'python main.py --goal "Summarize support tickets in data/tickets.csv"',
    ]
    for cmd in quick:
        print(f"  {cmd}")


# -----------------------------------------------------------------------------
# Main run
# -----------------------------------------------------------------------------
def run_agent(goal: str, provider: str | None, model: str | None, language: str | None) -> int:
    """Build the agent, run it on the given goal, return an exit code."""
    load_dotenv()

    report_language = language or os.getenv("REPORT_LANGUAGE", "es")

    # 1. LLMs -----------------------------------------------------------------
    # Two specialized instances: planning is deterministic (low temp),
    # reasoning during execution allows a bit more flexibility.
    try:
        planner_llm = get_planner_llm(provider=provider, model=model)
        executor_llm = get_reasoning_llm(provider=provider, model=model)
    except LLMConfigError as exc:
        ui.error(str(exc))
        ui.info(
            "Tip: run `python main.py --demo` to try the agent without an API key."
        )
        return 2

    # 2. Tools + Planner + Executor -------------------------------------------
    tools_catalog = build_tools_catalog()
    planner = Planner(llm=planner_llm, tools_catalog=tools_catalog)
    executor = Executor(
        llm=executor_llm,
        tools=ALL_TOOLS,
        report_language=report_language,
        on_step_start=ui.step_start,
        on_step_success=ui.step_success,
        on_step_error=ui.step_error,
    )

    # 3. Run ------------------------------------------------------------------
    ui.banner(goal)
    memory = AgentMemory(goal=goal)

    try:
        ui.info("🧠 Planning...")
        plan = planner.plan(goal)
        memory.set_plan(plan.model_dump())
        ui.show_plan(plan)
    except Exception as exc:  # noqa: BLE001
        ui.error(f"Planner failed: {type(exc).__name__}: {exc}")
        return 3

    try:
        executor.run(plan, memory)
    except KeyboardInterrupt:
        ui.warn("Interrupted by user.")
        return 130
    except Exception as exc:  # noqa: BLE001
        ui.error(f"Executor crashed: {type(exc).__name__}: {exc}")
        return 4

    # 4. Persist memory + summary --------------------------------------------
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    memory.register_artifacts_from_results()
    memory.save_to_json(str(MEMORY_DUMP))
    ui.info(f"Decision log saved to {MEMORY_DUMP}")
    ui.final_summary(memory)
    return 0


def run_demo() -> int:
    """Run the agent with mocked LLM responses — no API key required."""
    from demo_mode import run_demo_flow
    return run_demo_flow()


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.list_examples:
        print_examples()
        return 0

    ensure_sample_data()

    if args.demo:
        return run_demo()

    if not args.goal:
        ui.error("You must provide --goal, or use --demo / --list-examples.")
        ui.info("Run `python main.py --help` for usage.")
        return 1

    return run_agent(
        goal=args.goal,
        provider=args.provider,
        model=args.model,
        language=args.language,
    )


if __name__ == "__main__":
    sys.exit(main())
