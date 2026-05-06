"""
LLM Factory — Multi-provider abstraction.

This module is the single entry point for instantiating an LLM in the project.
It supports BYOK (Bring Your Own Key) for multiple providers, so users can
choose whichever fits their budget and infrastructure.

Supported providers:
    - groq      (free tier available, recommended for first-time users)
    - ollama    (local, fully free, no key needed)
    - openai    (paid)
    - anthropic (paid)
    - demo      (mock responses for testing)

Usage:
    from agent.llm_factory import get_llm
    llm = get_llm()  # Reads config from environment variables
"""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()


# Default model per provider — chosen for a good cost/quality balance
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "demo": "demo-model",
}


class LLMConfigError(Exception):
    """Raised when the LLM provider is misconfigured (missing key, bad name, etc.)."""


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    demo: bool = False,
) -> BaseChatModel:
    """
    Build a LangChain chat model from environment variables or explicit args.

    Args:
        provider: One of "groq", "ollama", "openai", "anthropic", "demo".
                  If None, uses the LLM_PROVIDER env variable.
        model:    Specific model name. If None, uses LLM_MODEL or the default
                  for the chosen provider.
        temperature: Sampling temperature. Lower = more deterministic.
                     0.2 is a good default for agent reasoning.
        demo:     Force demo mode regardless of provider.

    Returns:
        An instance of a LangChain BaseChatModel ready to use.

    Raises:
        LLMConfigError: If the provider is unknown or the API key is missing.
    """
    if demo:
        return _build_demo()
    
    provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower().strip()
    model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider)

    if not model:
        raise LLMConfigError(
            f"No model specified and no default exists for provider '{provider}'."
        )

    if provider == "groq":
        return _build_groq(model, temperature)
    if provider == "ollama":
        return _build_ollama(model, temperature)
    if provider == "openai":
        return _build_openai(model, temperature)
    if provider == "anthropic":
        return _build_anthropic(model, temperature)

    raise LLMConfigError(
        f"Unknown provider '{provider}'. "
        f"Valid options: {list(DEFAULT_MODELS.keys())}"
    )


def get_planner_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    demo: bool = False,
) -> BaseChatModel:
    """
    Get LLM optimized for planning tasks (low temperature, higher token limit).
    """
    return get_llm(
        provider=provider,
        model=model,
        temperature=0.1,  # Low temperature for consistent planning
        demo=demo
    )


def get_reasoning_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    demo: bool = False,
) -> BaseChatModel:
    """
    Get LLM optimized for reasoning decisions (balanced temperature).
    """
    return get_llm(
        provider=provider,
        model=model,
        temperature=0.3,  # Slightly higher for nuanced decisions
        demo=demo
    )


def get_analysis_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    demo: bool = False,
) -> BaseChatModel:
    """
    Get LLM optimized for data analysis (balanced settings).
    """
    return get_llm(
        provider=provider,
        model=model,
        temperature=0.2,  # Balanced for analysis
        demo=demo
    )


# -----------------------------------------------------------------------------
# Provider builders — kept as private functions so adding a new provider is
# just a matter of writing one more builder + adding it to DEFAULT_MODELS.
# -----------------------------------------------------------------------------

def _build_groq(model: str, temperature: float) -> BaseChatModel:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.startswith("gsk_your_key"):
        raise LLMConfigError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
            "and add it to your .env file."
        )
    from langchain_groq import ChatGroq
    return ChatGroq(model=model, temperature=temperature, api_key=api_key)


def _build_ollama(model: str, temperature: float) -> BaseChatModel:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, temperature=temperature, base_url=base_url)


def _build_openai(model: str, temperature: float) -> BaseChatModel:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your_key"):
        raise LLMConfigError(
            "OPENAI_API_KEY is not set. Get a key at https://platform.openai.com/api-keys "
            "and add it to your .env file."
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)


def _build_anthropic(model: str, temperature: float) -> BaseChatModel:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("sk-ant-your_key"):
        raise LLMConfigError(
            "ANTHROPIC_API_KEY is not set. Get a key at https://console.anthropic.com/ "
            "and add it to your .env file."
        )
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)


def _build_demo() -> BaseChatModel:
    """Build demo model for testing without API keys."""
    return DemoChatModel()


class DemoChatModel(BaseChatModel):
    """Mock chat model for demo purposes."""
    
    def _generate(self, messages, **kwargs):
        """Generate mock response."""
        from langchain_core.messages import AIMessage
        
        # Simple mock responses based on the last message content
        last_message = messages[-1].content.lower() if messages else ""
        
        if "plan" in last_message or "steps" in last_message:
            response = """{
    "reasoning": "I'll break this down into logical steps for data analysis",
    "estimated_time": 300,
    "confidence": 0.8,
    "steps": [
        {
            "step_id": 1,
            "description": "Load and explore the dataset",
            "tool_name": "load_csv",
            "parameters": {"file_path": "data/ventas.csv"},
            "reasoning": "First step is always to load the data",
            "dependencies": []
        },
        {
            "step_id": 2,
            "description": "Analyze data patterns",
            "tool_name": "pandas_analyze",
            "parameters": {},
            "reasoning": "Statistical analysis to find patterns",
            "dependencies": [1]
        }
    ]
}"""
        elif "continue" in last_message or "stop" in last_message:
            response = "continue"
        else:
            response = "I understand the task and will proceed with execution."
        
        return AIMessage(content=response)
    
    async def _agenerate(self, messages, **kwargs):
        """Async version of generate."""
        return self._generate(messages, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        return "demo"


def validate_provider_config(provider: str) -> bool:
    """
    Validate if a provider is properly configured.
    
    Args:
        provider: Provider name to validate.
        
    Returns:
        True if provider is properly configured, False otherwise.
    """
    provider = provider.lower()
    
    if provider == "demo":
        return True
    elif provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    elif provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    elif provider == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    elif provider == "ollama":
        return True  # Ollama doesn't need API key
    else:
        return False


def get_available_providers() -> dict:
    """
    Get dictionary of available providers and their descriptions.
    
    Returns:
        Dictionary mapping provider names to descriptions.
    """
    return {
        "groq": "Groq fast inference (requires GROQ_API_KEY, free tier available)",
        "ollama": "Ollama local models (no API key required, fully free)",
        "openai": "OpenAI GPT models (requires OPENAI_API_KEY, paid)",
        "anthropic": "Anthropic Claude models (requires ANTHROPIC_API_KEY, paid)",
        "demo": "Demo mode with mock responses (no API key required)"
    }
