"""
Eval harness — end-to-end benchmarks for the agent.

Runs the real Planner + Executor + tools pipeline on predefined goals
against the bundled sample datasets, and scores each run with
deterministic checks (no LLM judge): did the report get written, was the
right tool used, does the report name the actually-correct top group,
how many steps and retries did it take, how long, how many tokens.

Usage:
    python -m evals.run --provider groq --trials 3
    python -m evals.run --provider ollama --model qwen2.5-coder:7b

Not collected by pytest (tests/ only) — CI exercises the harness through
tests/test_eval_harness.py with mocked LLMs instead.
"""
