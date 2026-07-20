"""
Eval runner — executes benchmark cases end-to-end and records outcomes.

Each trial runs the REAL pipeline (Planner -> Executor -> tools) inside
its own working directory, so the relative outputs/ paths the tools
write land in an isolated per-trial folder. The persisted memory dump in
each trial folder is trace-compatible: any run can be opened later in
the Streamlit trace inspector.

Isolation notes:
    - tools._state is reset before every trial (fresh dataset registry).
    - os.chdir is process-global: the runner is CLI-only by design and
      must never be invoked from inside the Streamlit app.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agent.executor import Executor
from agent.memory import AgentMemory
from agent.planner import Planner
from agent.trace import _ATTEMPT_RE
from evals.checks import TrialContext, run_checks
from evals.schema import BenchmarkResult, EvalCase, TrialRecord
from tools import ALL_TOOLS, _state, build_tools_catalog

REPO_ROOT = Path(__file__).resolve().parent.parent

# Returns (planner_llm, executor_llm); the seam tests use to inject fakes.
LLMPairFactory = Callable[[], tuple[object, object]]


def default_llm_pair_factory(
    provider: Optional[str], model: Optional[str], temperature: float = 0.0
) -> LLMPairFactory:
    """Real LLMs at fixed temperature for reproducibility."""

    def factory() -> tuple[object, object]:
        from agent.llm_factory import get_llm

        return (
            get_llm(provider=provider, model=model, temperature=temperature),
            get_llm(provider=provider, model=model, temperature=temperature),
        )

    return factory


def _attach_usage_tracking(llms: list[object]):
    """Best-effort token capture; returns the shared handler or None."""
    try:
        from langchain_core.callbacks import UsageMetadataCallbackHandler
    except ImportError:
        return None
    handler = UsageMetadataCallbackHandler()
    for llm in llms:
        try:
            llm.callbacks = [handler]
        except Exception:  # noqa: BLE001 — fakes in tests may reject attribute
            return None
    return handler


def _usage_totals(handler) -> tuple[Optional[int], Optional[int]]:
    if handler is None or not getattr(handler, "usage_metadata", None):
        return None, None
    input_tokens = sum(u.get("input_tokens", 0) for u in handler.usage_metadata.values())
    output_tokens = sum(u.get("output_tokens", 0) for u in handler.usage_metadata.values())
    return input_tokens, output_tokens


def _count_retries(memory: AgentMemory) -> int:
    return sum(
        1 for entry in memory.log if _ATTEMPT_RE.match(entry.message or "")
    )


def run_trial(
    case: EvalCase,
    trial: int,
    llm_pair_factory: LLMPairFactory,
    base_dir: Path,
    report_language: str = "en",
) -> TrialRecord:
    """One end-to-end run of one case, scored. Crashes are recorded, not raised."""
    dataset_path = (REPO_ROOT / case.dataset).resolve()
    goal = case.goal_template.format(dataset=dataset_path.as_posix())

    run_dir = base_dir / f"{case.id}_t{trial}_{datetime.now().strftime('%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    memory = AgentMemory(goal=goal)
    error: Optional[str] = None
    handler = None
    started = time.perf_counter()

    previous_cwd = os.getcwd()
    _state.reset()
    os.chdir(run_dir)
    try:
        planner_llm, executor_llm = llm_pair_factory()
        handler = _attach_usage_tracking([planner_llm, executor_llm])

        planner = Planner(llm=planner_llm, tools_catalog=build_tools_catalog())
        executor = Executor(
            llm=executor_llm, tools=ALL_TOOLS, report_language=report_language
        )

        plan = planner.plan(goal)
        memory.set_plan(plan.model_dump())
        executor.run(plan, memory)
    except Exception as exc:  # noqa: BLE001 — one crashed trial must not stop the benchmark
        error = f"{type(exc).__name__}: {exc}"
    finally:
        os.chdir(previous_cwd)
        _state.reset()

    latency = time.perf_counter() - started

    memory.register_artifacts_from_results()
    memory.save_to_json(str(run_dir / "outputs" / "agent_memory.json"))

    ctx = TrialContext(memory=memory, run_dir=run_dir, dataset_path=dataset_path)
    checks = run_checks(ctx, case.checks) if error is None else []
    input_tokens, output_tokens = _usage_totals(handler)

    return TrialRecord(
        case_id=case.id,
        trial=trial,
        success=error is None and all(c.passed for c in checks),
        checks=checks,
        n_steps=len(memory.results),
        n_retries=_count_retries(memory),
        latency_s=round(latency, 2),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error=error,
        run_dir=str(run_dir),
    )


def run_benchmark(
    cases: list[EvalCase],
    llm_pair_factory: LLMPairFactory,
    base_dir: Path,
    provider: str,
    model: str,
    trials: int = 1,
    sleep_s: float = 0.0,
    on_trial_done: Optional[Callable[[TrialRecord], None]] = None,
) -> BenchmarkResult:
    """Run every case x trials sequentially."""
    result = BenchmarkResult(provider=provider, model=model, trials_per_case=trials)
    for case in cases:
        for trial in range(1, trials + 1):
            record = run_trial(case, trial, llm_pair_factory, base_dir)
            result.records.append(record)
            if on_trial_done:
                on_trial_done(record)
            if sleep_s:
                time.sleep(sleep_s)
    return result
