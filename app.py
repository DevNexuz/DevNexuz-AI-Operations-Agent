"""
Streamlit web UI for the AI Operations Agent.

Run locally:
    streamlit run app.py

Design notes:
    - The agent core (Planner/Executor/tools) is untouched: this app is just
      another renderer plugged into the same callbacks the terminal logger uses.
    - Demo mode is the default experience so the public deployment works
      without any API key. Real runs are BYOK: the key comes from the sidebar
      field, Streamlit secrets, or the environment — in that order — and is
      never persisted.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agent.memory import AgentMemory
from agent.planner import Plan, PlanStep

load_dotenv()

st.set_page_config(
    page_title="AI Operations Agent",
    page_icon="🤖",
    layout="wide",
)

OUTPUTS_DIR = Path("outputs")
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
DATA_DIR = Path("data")

PROVIDERS = ["groq", "ollama", "openai", "anthropic", "xai", "gemini"]

PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    # ollama needs no key
}

SAMPLE_DATASETS = {
    "Sales (sample)": "data/sales.csv",
    "Employees (sample)": "data/employees.csv",
    "Support tickets (sample)": "data/tickets.csv",
    "Ventas LATAM (muestra)": "data/latam_ventas.csv",
    "Empleados LATAM (muestra)": "data/latam_empleados.csv",
    "Tickets LATAM (muestra)": "data/latam_tickets.csv",
}

EXAMPLE_GOALS = [
    "Analyze {file} and find the top 3 regions by revenue, with a chart.",
    "Detect anomalies in {file} and explain what makes them unusual.",
    "Profile {file} and write an executive report with actionable insights.",
    "Analiza {file} y genera un reporte con hallazgos y recomendaciones.",
]


# -----------------------------------------------------------------------------
# Streamlit renderer — same protocol as agent/logger.py
# -----------------------------------------------------------------------------
class StreamlitRenderer:
    """Renders agent progress into a Streamlit container.

    Implements the same function names as agent/logger.py so it can be
    passed to demo_mode.run_demo_flow() and wired into the Executor's
    on_step_* callbacks without any adapter code.
    """

    def __init__(self, container):
        self.container = container
        self._status = None

    def banner(self, goal: str) -> None:
        self.container.markdown(f"#### 🎯 {goal}")

    def show_plan(self, plan: Plan) -> None:
        with self.container.expander("📋 Plan", expanded=True):
            st.table(
                [
                    {
                        "#": s.id,
                        "Description": s.description,
                        "Tool": s.suggested_tool,
                        "Expected output": s.expected_output,
                    }
                    for s in plan.steps
                ]
            )
            st.caption(f"🧠 {plan.reasoning}")

    def step_start(self, step: PlanStep, total: int) -> None:
        self._status = self.container.status(
            f"⚙️ Step {step.id}/{total} — {step.description}", state="running"
        )

    def step_success(self, step: PlanStep, result) -> None:
        if self._status is None:
            return
        preview = str(result.output)[:300] if result.output else "(no output)"
        self._status.update(
            label=f"✅ Step {step.id} — {step.description}", state="complete"
        )
        with self._status:
            st.code(preview, language="json")

    def step_error(self, step: PlanStep, result) -> None:
        if self._status is None:
            return
        self._status.update(
            label=f"❌ Step {step.id} — {step.description}", state="error"
        )
        with self._status:
            st.error(result.error or "Unknown error")

    def info(self, message: str) -> None:
        self.container.caption(message)

    def warn(self, message: str) -> None:
        self.container.warning(message)

    def error(self, message: str) -> None:
        self.container.error(message)

    def final_summary(self, memory: AgentMemory) -> None:
        success = sum(1 for r in memory.results if r.status == "success")
        failed = sum(1 for r in memory.results if r.status == "error")
        if failed:
            self.container.warning(
                f"Run finished: {success} steps succeeded, {failed} failed."
            )
        else:
            self.container.success(f"Run complete — {success}/{success} steps succeeded.")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def get_secret(name: str) -> str | None:
    """Streamlit Cloud secrets, guarded for local runs without a secrets file."""
    try:
        return st.secrets.get(name)  # type: ignore[no-any-return]
    except Exception:
        return None


def resolve_api_key(provider: str, typed_key: str) -> str | None:
    """Sidebar field > Streamlit secrets > environment. Never persisted."""
    env_var = PROVIDER_KEY_ENV.get(provider)
    if env_var is None:
        return None  # provider needs no key
    return typed_key.strip() or get_secret(env_var) or os.getenv(env_var)


def ensure_sample_data() -> None:
    if not (DATA_DIR / "sales.csv").exists():
        from data.generate_samples import main as generate
        generate()


def save_upload(uploaded_file) -> Path:
    """Persist an uploaded CSV under outputs/uploads/ and return its path."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", uploaded_file.name)
    dest = UPLOADS_DIR / safe_name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def strip_markdown_images(text: str) -> str:
    """Charts are rendered natively with st.image; drop the file-path image
    links from the report body (which Streamlit cannot resolve) and the
    Visualizations heading that would otherwise sit empty above nothing."""
    text = re.sub(r"^!\[[^\]]*\]\([^)]*\)\s*$", "", text, flags=re.MULTILINE)
    return re.sub(r"^##[^\n]*Visualizations\s*$", "", text, flags=re.MULTILINE)


def collect_artifacts(memory: AgentMemory) -> dict:
    """Pull chart/report paths out of the step results of a finished run."""
    charts: list[str] = []
    report_path: str | None = None
    for r in memory.results:
        if r.status != "success" or not isinstance(r.output, dict):
            continue
        if "chart_path" in r.output:
            charts.append(r.output["chart_path"])
        if "report_path" in r.output:
            report_path = r.output["report_path"]
    return {"charts": charts, "report_path": report_path}


def run_real_agent(
    goal: str, provider: str, model: str | None, language: str, renderer: StreamlitRenderer
) -> AgentMemory | None:
    """Mirror of main.run_agent(), rendering into Streamlit instead of the terminal."""
    from agent.executor import Executor
    from agent.llm_factory import LLMConfigError, get_planner_llm, get_reasoning_llm
    from agent.planner import Planner
    from tools import ALL_TOOLS, build_tools_catalog

    try:
        planner_llm = get_planner_llm(provider=provider, model=model)
        executor_llm = get_reasoning_llm(provider=provider, model=model)
    except LLMConfigError as exc:
        renderer.error(str(exc))
        return None

    planner = Planner(llm=planner_llm, tools_catalog=build_tools_catalog())
    executor = Executor(
        llm=executor_llm,
        tools=ALL_TOOLS,
        report_language=language,
        on_step_start=renderer.step_start,
        on_step_success=renderer.step_success,
        on_step_error=renderer.step_error,
    )

    renderer.banner(goal)
    memory = AgentMemory(goal=goal)

    try:
        with st.spinner("🧠 Planning..."):
            plan = planner.plan(goal)
        memory.set_plan(plan.model_dump())
        renderer.show_plan(plan)
    except Exception as exc:  # noqa: BLE001 — surface any planner failure to the user
        renderer.error(f"Planner failed: {type(exc).__name__}: {exc}")
        return None

    try:
        executor.run(plan, memory)
    except Exception as exc:  # noqa: BLE001
        renderer.error(f"Executor crashed: {type(exc).__name__}: {exc}")
        return None

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    memory.register_artifacts_from_results()
    memory.save_to_json(str(OUTPUTS_DIR / "agent_memory.json"))
    renderer.final_summary(memory)
    return memory


# -----------------------------------------------------------------------------
# Sidebar — mode + provider configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🤖 AI Operations Agent")
    st.caption("Give it a goal in plain English (or Spanish). It plans, executes, and delivers.")

    mode = st.radio(
        "Mode",
        ["🎬 Demo (no API key)", "🚀 Real agent (BYOK)"],
        help="Demo replays a deterministic run with real tools and no LLM. "
        "Real agent plans and executes with the LLM provider you configure.",
    )
    demo_mode_on = mode.startswith("🎬")

    st.divider()

    if demo_mode_on:
        st.info(
            "Demo mode runs the full pipeline on the sample sales dataset "
            "with pre-recorded agent decisions — real tools, no LLM calls."
        )
        provider, model, api_key, language = "demo", None, None, "en"
    else:
        default_provider = os.getenv("LLM_PROVIDER", "groq").lower()
        provider = st.selectbox(
            "LLM provider",
            PROVIDERS,
            index=PROVIDERS.index(default_provider) if default_provider in PROVIDERS else 0,
            help="BYOK — bring your own key. Groq has a free tier; Ollama runs locally with no key.",
        )

        if provider == "ollama":
            base_url = st.text_input(
                "Ollama base URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            )
            os.environ["OLLAMA_BASE_URL"] = base_url
            typed_key = ""
        else:
            typed_key = st.text_input(
                f"{provider.capitalize()} API key",
                type="password",
                help="Used only for this session — never stored. "
                "Leave empty to use your .env or Streamlit secrets.",
            )

        model = st.text_input(
            "Model (optional)",
            value=os.getenv("LLM_MODEL", ""),
            help="Leave empty to use the provider's default.",
        ) or None

        language = st.selectbox("Report language", ["es", "en"], index=0)

        api_key = resolve_api_key(provider, typed_key)
        if provider != "ollama":
            if api_key:
                st.caption("🔑 Key found — ready to run.")
            else:
                st.warning(f"No {PROVIDER_KEY_ENV[provider]} found. Paste a key above.")

    st.divider()
    st.caption(
        "[GitHub](https://github.com/DevNexuz/DevNexuz-AI-Operations-Agent) · "
        "MIT License · Built with LangChain + Streamlit"
    )


# -----------------------------------------------------------------------------
# Trace inspector tab
# -----------------------------------------------------------------------------
def render_trace_tab() -> None:
    """Render the decision log of a run as an inspectable trace."""
    import json

    from agent.trace import parse_trace

    st.subheader("🔍 Trace inspector")
    st.caption(
        "Every run persists its full decision log. Inspect the last run below, "
        "or upload any agent_memory.json to analyze it."
    )

    uploaded_dump = st.file_uploader(
        "Upload a decision log (agent_memory.json)", type=["json"], key="trace_upload"
    )
    default_dump = OUTPUTS_DIR / "agent_memory.json"

    if uploaded_dump is not None:
        raw, source_label = uploaded_dump.getvalue(), uploaded_dump.name
    elif default_dump.exists():
        raw, source_label = default_dump.read_bytes(), str(default_dump)
    else:
        st.info("No run recorded yet — run the agent (or the demo) first.")
        return

    try:
        trace = parse_trace(json.loads(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        st.error(f"Could not parse {source_label}: {exc}")
        return

    st.markdown(f"**Goal:** {trace.goal or '(unknown)'}")
    if trace.plan_reasoning:
        st.caption(f"🧠 {trace.plan_reasoning}")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Steps", trace.total_steps)
    m2.metric("Succeeded", trace.succeeded)
    m3.metric("Failed", trace.failed)
    m4.metric("Retries", trace.total_retries)
    m5.metric(
        "Duration",
        f"{trace.duration_seconds:.1f}s" if trace.duration_seconds is not None else "—",
    )

    for step in trace.steps:
        icon = {"success": "✅", "error": "❌"}.get(step.status, "❔")
        retry_note = f" · {step.attempts} attempts" if step.attempts > 1 else ""
        title = f"{icon} Step {step.step_id} — {step.description or step.tool_used or '?'}{retry_note}"
        with st.expander(title):
            st.markdown(
                f"**Tool:** `{step.tool_used or step.suggested_tool or '?'}` · "
                f"**Status:** {step.status}"
                + (f" · **Finished:** {step.timestamp}" if step.timestamp else "")
            )
            for i, err in enumerate(step.retry_errors, start=1):
                st.warning(f"Attempt {i} failed and was retried: {err}")
            if step.error:
                st.error(step.error)
            if step.output is not None:
                if isinstance(step.output, (dict, list)):
                    st.json(step.output, expanded=False)
                else:
                    st.code(str(step.output))

    if trace.artifacts:
        st.markdown("**Artifacts**")
        for name, path in trace.artifacts.items():
            exists = Path(path).exists()
            st.markdown(f"- `{name}` → `{path}`" + ("" if exists else " *(missing)*"))
            if exists and path.lower().endswith(".png"):
                st.image(path, width=420)


# -----------------------------------------------------------------------------
# Main area
# -----------------------------------------------------------------------------
st.header("Autonomous data analysis, from goal to report")

tab_run, tab_trace = st.tabs(["🚀 Run", "🔍 Trace inspector"])

with tab_trace:
    render_trace_tab()

with tab_run:
    if demo_mode_on:
        st.markdown(
            "Press the button and watch the agent load, profile, analyze and "
            "chart the sample sales data, then write its report."
        )
        if st.button("🎬 Run demo", type="primary"):
            ensure_sample_data()
            progress_area = st.container()
            renderer = StreamlitRenderer(progress_area)
            from demo_mode import run_demo_flow

            run_demo_flow(ui=renderer)
            st.session_state["last_artifacts"] = {
                "charts": ["outputs/charts/revenue_by_region.png"],
                "report_path": "outputs/report.md",
            }
    else:
        # 1. Data source ----------------------------------------------------------
        st.subheader("1 · Choose your data")
        source = st.radio(
            "Data source", ["Sample dataset", "Upload a CSV"], horizontal=True,
            label_visibility="collapsed",
        )
        if source == "Sample dataset":
            ensure_sample_data()
            choice = st.selectbox("Sample dataset", list(SAMPLE_DATASETS.keys()))
            csv_path = SAMPLE_DATASETS[choice]
        else:
            uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
            csv_path = str(save_upload(uploaded)).replace("\\", "/") if uploaded else None
            if csv_path:
                st.caption(f"Saved as `{csv_path}`")

        # 2. Goal -----------------------------------------------------------------
        st.subheader("2 · What should the agent do?")

        def _fill_goal(template: str) -> None:
            st.session_state["goal_text"] = template.format(file=csv_path or "your CSV")

        cols = st.columns(2)
        for i, template in enumerate(EXAMPLE_GOALS):
            label = template.format(file=Path(csv_path).name if csv_path else "…")
            cols[i % 2].button(
                label, key=f"example_{i}", on_click=_fill_goal, args=(template,),
                use_container_width=True,
            )

        goal = st.text_area(
            "Goal",
            key="goal_text",
            placeholder=f"e.g. Analyze {csv_path or 'data/sales.csv'} and find the top regions…",
            height=90,
        )

        # 3. Run ------------------------------------------------------------------
        st.subheader("3 · Run")
        needs_key = provider != "ollama" and not api_key
        run_disabled = not goal.strip() or not csv_path or needs_key
        if st.button("🚀 Run agent", type="primary", disabled=run_disabled):
            env_var = PROVIDER_KEY_ENV.get(provider)
            if env_var and api_key:
                os.environ[env_var] = api_key  # session-scoped; llm_factory reads env

            progress_area = st.container()
            renderer = StreamlitRenderer(progress_area)
            memory = run_real_agent(goal.strip(), provider, model, language, renderer)
            if memory is not None:
                st.session_state["last_artifacts"] = collect_artifacts(memory)

        if run_disabled:
            hints = []
            if not csv_path:
                hints.append("choose or upload a dataset")
            if not goal.strip():
                hints.append("write a goal")
            if needs_key:
                hints.append("configure an API key in the sidebar")
            st.caption("To enable the run button: " + ", ".join(hints) + ".")


    # -----------------------------------------------------------------------------
    # Results — persisted across reruns so downloads don't wipe the view
    # -----------------------------------------------------------------------------
    artifacts = st.session_state.get("last_artifacts")
    if artifacts:
        st.divider()
        st.subheader("📄 Results")

        report_path = artifacts.get("report_path")
        charts = [p for p in artifacts.get("charts", []) if Path(p).exists()]

        col_report, col_charts = st.columns([3, 2])

        with col_report:
            if report_path and Path(report_path).exists():
                report_text = Path(report_path).read_text(encoding="utf-8")
                st.markdown(strip_markdown_images(report_text))
                st.download_button(
                    "⬇️ Download report (Markdown)",
                    data=report_text,
                    file_name="report.md",
                    mime="text/markdown",
                )

        with col_charts:
            for chart in charts:
                st.image(chart, use_container_width=True)

            memory_dump = OUTPUTS_DIR / "agent_memory.json"
            if memory_dump.exists():
                st.download_button(
                    "⬇️ Download decision log (JSON)",
                    data=memory_dump.read_text(encoding="utf-8"),
                    file_name="agent_memory.json",
                    mime="application/json",
                )
