"""
Benchmark CLI.

    python -m evals.run --provider groq --trials 3
    python -m evals.run --provider ollama --model qwen2.5-coder:7b
    python -m evals.run --provider groq --cases sales_top_regions,sales_anomalies

Results land in evals/results/ as Markdown (README-ready table) + JSON.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Windows consoles default to cp1252, which can't encode the ✅/💥 markers
# below; reconfigure to UTF-8 the same way agent/logger.py does for Rich.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run",
        description="Run the end-to-end agent benchmark against a provider.",
    )
    parser.add_argument("--provider", default=None,
                        help="LLM provider (defaults to LLM_PROVIDER from .env).")
    parser.add_argument("--model", default=None,
                        help="Model name (defaults to the provider default).")
    parser.add_argument("--trials", type=int, default=1,
                        help="Trials per case (3 recommended for the README table).")
    parser.add_argument("--cases", default=None,
                        help="Comma-separated case ids (default: all).")
    parser.add_argument("--sleep", type=float, default=0.0,
                        help="Seconds to sleep between trials (rate limits).")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="Sampling temperature (0.0 for reproducibility).")
    parser.add_argument("--output", default=None,
                        help="Output .md path (default: evals/results/<provider>_<model>_<ts>.md)")
    parser.add_argument("--list-cases", action="store_true",
                        help="Print available cases and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_arg_parser().parse_args(argv)

    from evals.cases import BUILTIN_CASES, get_cases

    if args.list_cases:
        for case in BUILTIN_CASES:
            print(f"  {case.id:<22} {case.description}")
        return 0

    from agent.llm_factory import DEFAULT_MODELS, LLMConfigError
    from evals.report import save, summary_row, SUMMARY_HEADER
    from evals.runner import REPO_ROOT, default_llm_pair_factory, run_benchmark

    provider = (args.provider or os.getenv("LLM_PROVIDER", "groq")).lower().strip()
    model = args.model or os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider, "?")
    cases = get_cases(args.cases.split(",") if args.cases else None)

    # Fail fast on missing keys before burning any time.
    try:
        default_llm_pair_factory(provider, model, args.temperature)()
    except LLMConfigError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "-").replace(":", "-")
    base_dir = REPO_ROOT / "evals" / "results" / f"runs_{provider}_{safe_model}_{timestamp}"
    output = Path(args.output) if args.output else (
        REPO_ROOT / "evals" / "results" / f"{provider}_{safe_model}_{timestamp}.md"
    )

    print(f"Benchmark: {provider}/{model} — {len(cases)} cases x {args.trials} trials")
    print(f"Run dirs under: {base_dir}\n")

    def progress(record):
        mark = "✅" if record.success else ("💥" if record.error else "❌")
        extra = record.error or ", ".join(
            c.kind for c in record.checks if not c.passed
        ) or "all checks passed"
        print(f"  {mark} {record.case_id} t{record.trial} "
              f"({record.n_steps} steps, {record.latency_s:.1f}s) — {extra}")

    result = run_benchmark(
        cases=cases,
        llm_pair_factory=default_llm_pair_factory(provider, model, args.temperature),
        base_dir=base_dir,
        provider=provider,
        model=model,
        trials=args.trials,
        sleep_s=args.sleep,
        on_trial_done=progress,
    )

    save(result, output)
    print(f"\n{SUMMARY_HEADER}\n{summary_row(result)}")
    print(f"\nReport: {output}")
    return 0 if result.success_rate == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
