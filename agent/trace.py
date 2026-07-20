"""
Trace parsing — turns a persisted agent_memory.json dump into an
inspectable run trace.

The decision log already contains everything needed for observability:
step results, artifacts, and one log line per failed attempt written by
the Executor ("Step {id} attempt {n} failed: {error}"). This module
reconstructs per-step retry history and run-level totals from that dump
without touching the agent core.

Kept free of any UI imports on purpose: the Streamlit trace tab renders
what this module parses, and tests exercise it directly.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# Matches the retry lines the Executor writes into memory.log
# (see Executor._run_step in agent/executor.py).
_ATTEMPT_RE = re.compile(r"Step (\d+) attempt (\d+) failed: (.*)", re.DOTALL)


class StepTrace(BaseModel):
    """Everything known about one executed step, retries included."""

    step_id: int
    description: str = ""
    suggested_tool: str = ""
    status: str = "unknown"  # "success" | "error" | "unknown"
    tool_used: Optional[str] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    attempts: int = 1
    retry_errors: list[str] = Field(default_factory=list)


class TraceSummary(BaseModel):
    """Run-level view assembled from a persisted memory dump."""

    goal: str = ""
    plan_reasoning: str = ""
    steps: list[StepTrace] = Field(default_factory=list)
    total_steps: int = 0
    succeeded: int = 0
    failed: int = 0
    total_retries: int = 0
    duration_seconds: Optional[float] = None
    artifacts: dict[str, str] = Field(default_factory=dict)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_trace(data: dict) -> TraceSummary:
    """Parse a dict loaded from agent_memory.json into a TraceSummary.

    Tolerant of legacy or partial dumps: missing keys, steps without
    results, results without matching plan steps, and unparsable
    timestamps all degrade gracefully instead of raising.
    """
    if not isinstance(data, dict):
        raise ValueError("Trace data must be a JSON object (dict).")

    plan = data.get("plan") or {}
    plan_steps = {
        s.get("id"): s
        for s in (plan.get("steps") or [])
        if isinstance(s, dict) and s.get("id") is not None
    }

    # Retry history from executor log lines.
    retries_by_step: dict[int, list[str]] = {}
    for entry in data.get("log") or []:
        if not isinstance(entry, dict):
            continue
        match = _ATTEMPT_RE.match(entry.get("message") or "")
        if match:
            step_id = int(match.group(1))
            retries_by_step.setdefault(step_id, []).append(match.group(3).strip())

    steps: list[StepTrace] = []
    for result in data.get("results") or []:
        if not isinstance(result, dict) or result.get("step_id") is None:
            continue
        step_id = int(result["step_id"])
        plan_step = plan_steps.get(step_id, {})
        attempt_errors = retries_by_step.get(step_id, [])

        # Every logged attempt line is a failure; a successful step means one
        # extra (final) attempt succeeded on top of those.
        failed_attempts = len(attempt_errors)
        status = result.get("status", "unknown")
        attempts = failed_attempts + 1 if status == "success" else max(failed_attempts, 1)
        # retry_errors = the errors that triggered a retry. On success every
        # logged failure was retried; on error the last failure is final and
        # already lives in result["error"].
        retry_errors = attempt_errors if status == "success" else attempt_errors[:-1]

        steps.append(
            StepTrace(
                step_id=step_id,
                description=plan_step.get("description", ""),
                suggested_tool=plan_step.get("suggested_tool", ""),
                status=status,
                tool_used=result.get("tool_used"),
                output=result.get("output"),
                error=result.get("error"),
                timestamp=result.get("timestamp"),
                attempts=attempts,
                retry_errors=retry_errors,
            )
        )

    # Duration from the first/last parsable log timestamps.
    timestamps = sorted(
        ts
        for entry in data.get("log") or []
        if isinstance(entry, dict)
        and (ts := _parse_timestamp(entry.get("timestamp"))) is not None
    )
    duration = (
        (timestamps[-1] - timestamps[0]).total_seconds()
        if len(timestamps) >= 2
        else None
    )

    succeeded = sum(1 for s in steps if s.status == "success")
    failed = sum(1 for s in steps if s.status == "error")

    return TraceSummary(
        goal=data.get("goal", ""),
        plan_reasoning=plan.get("reasoning", ""),
        steps=steps,
        total_steps=len(steps),
        succeeded=succeeded,
        failed=failed,
        total_retries=sum(s.attempts - 1 for s in steps),
        duration_seconds=duration,
        artifacts={
            str(k): str(v)
            for k, v in (data.get("artifacts") or {}).items()
        },
    )
