"""
Logger — Rich-powered console logger for the agent.

This is what the user *sees* during a run. Designed to be visually
expressive: panels for phases, colored step status, final summary.

Keeping the logger separate from the executor lets us swap in a Streamlit
or web-based renderer later without touching agent logic.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent.memory import AgentMemory, StepResult
from agent.planner import Plan, PlanStep


import io
import sys

_console = Console(
    file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "buffer")
    else sys.stdout
)


def banner(goal: str) -> None:
    """Print the welcome banner with the user's goal."""
    _console.print(
        Panel.fit(
            Text(f"🎯 {goal}", style="bold white"),
            title="🤖 AI Operations Agent",
            border_style="cyan",
        )
    )


def show_plan(plan: Plan) -> None:
    """Render the plan as a nice table + the planner's reasoning."""
    table = Table(
        title="📋 Plan",
        show_header=True,
        header_style="bold magenta",
        border_style="magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Description")
    table.add_column("Tool", style="cyan")
    table.add_column("Expected output", style="green")

    for step in plan.steps:
        table.add_row(
            str(step.id),
            step.description,
            step.suggested_tool,
            step.expected_output,
        )

    _console.print(table)
    _console.print(
        Panel(plan.reasoning, title="🧠 Planner reasoning", border_style="blue")
    )


def step_start(step: PlanStep, total: int) -> None:
    _console.rule(
        f"[bold cyan]⚙️  Step {step.id}/{total}[/bold cyan] — {step.description}"
    )


def step_success(step: PlanStep, result: StepResult) -> None:
    preview = str(result.output)[:120].replace("\n", " ") if result.output else "(no output)"
    _console.print(
        f"   [green]✓[/green] [cyan]{result.tool_used}[/cyan] → {preview}"
    )


def step_error(step: PlanStep, result: StepResult) -> None:
    _console.print(
        f"   [red]✗[/red] [cyan]{result.tool_used}[/cyan] → [red]{result.error}[/red]"
    )


def final_summary(memory: AgentMemory) -> None:
    """Print the run summary at the end."""
    success = sum(1 for r in memory.results if r.status == "success")
    failed = sum(1 for r in memory.results if r.status == "error")

    artifacts = (
        "\n".join(f"  • {n}: {p}" for n, p in memory.artifacts.items())
        or "  (none)"
    )

    body = (
        f"[green]✓ Successful steps:[/green] {success}\n"
        f"[red]✗ Failed steps:[/red] {failed}\n\n"
        f"[bold]Artifacts:[/bold]\n{artifacts}"
    )
    _console.print(Panel(body, title="✅ Run complete", border_style="green"))


def info(message: str) -> None:
    _console.print(f"[dim]›[/dim] {message}")


def warn(message: str) -> None:
    _console.print(f"[yellow]⚠ {message}[/yellow]")


def error(message: str) -> None:
    _console.print(f"[red]✗ {message}[/red]")
