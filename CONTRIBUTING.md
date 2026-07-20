# Contributing to AI Operations Agent

Thanks for your interest! This project is intentionally small and approachable, so contributions of any size are welcome.

## 🚀 Quick start for contributors

```bash
git clone https://github.com/[your-username]/DevNexuz-AI-Operations-Agent.git
cd DevNexuz-AI-Operations-Agent
pip install -r requirements.txt
cp .env.example .env   # add your key, or run with --demo
python main.py --demo  # verify everything works
```

## 🧩 Adding a new tool

The fastest way to extend the agent is to give it new capabilities.

Create your function in a module under `tools/` (or reuse an existing one).
Decorate it with `@tool` and define a Pydantic `args_schema`.
Return a JSON-serializable dict. On failure, return `{"error": "..."}` instead of raising.
Register the tool in `tools/__init__.py` (ALL_TOOLS list).
Test it: the planner will pick it up automatically.

Example skeleton:

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class MyToolArgs(BaseModel):
    dataset_id: str = Field(description="ID returned by load_csv.")

@tool("my_tool", args_schema=MyToolArgs)
def my_tool(dataset_id: str) -> dict:
    """One-line description the LLM will read to decide when to call this."""
    ...
    return {"result": ...}
```

## 🔌 Adding a new LLM provider

Edit `agent/llm_factory.py`:

1. Add the provider to `DEFAULT_MODELS`.
2. Write a `_build_<provider>` function.
3. Wire it into `get_llm()`.
4. Document the env vars in `.env.example`.

## ✅ Style guidelines

- **Type hints everywhere.** Pydantic for tool args, dataclasses or plain types elsewhere.
- **Docstrings on public functions.** The first line of a tool's docstring is what the LLM reads.
- **Errors over exceptions in tools.** Return `{"error": "..."}` so the agent can self-heal.
- **Keep prompts in `prompts/prompts.py`.** No prompt strings inline in logic files.

## 🐛 Reporting bugs

Open an issue with:

1. **What you ran** (command + provider + OS).
2. **What you expected vs what happened.**
3. **The contents of `outputs/agent_memory.json`** if the run got that far.

## 📜 License

By contributing, you agree your code will be released under the MIT License.

## 🤝 Questions?

Open an issue or start a discussion! We're happy to help.
