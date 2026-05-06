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
    - xai       (Grok models by xAI — free tier available)
    - gemini    (Google Gemini — generous free tier via AI Studio)

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
    "xai": "grok-3-mini",
    "gemini": "gemini-2.0-flash",
}


class LLMConfigError(Exception):
    """Raised when the LLM provider is misconfigured (missing key, bad name, etc.)."""


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> BaseChatModel:
    """
    Build a LangChain chat model from environment variables or explicit args.

    Args:
        provider: One of "groq", "ollama", "openai", "anthropic", "xai", "gemini".
                  If None, uses the LLM_PROVIDER env variable.
        model:    Specific model name. If None, uses LLM_MODEL or the default
                  for the chosen provider.
        temperature: Sampling temperature. Lower = more deterministic.
                     0.2 is a good default for agent reasoning.

    Returns:
        An instance of a LangChain BaseChatModel ready to use.

    Raises:
        LLMConfigError: If the provider is unknown or the API key is missing.
    """
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
    if provider == "xai":
        return _build_xai(model, temperature)
    if provider == "gemini":
        return _build_gemini(model, temperature)

    raise LLMConfigError(
        f"Unknown provider '{provider}'. "
        f"Valid options: {list(DEFAULT_MODELS.keys())}"
    )


def get_planner_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """Get LLM optimized for planning (low temperature for consistent plans)."""
    return get_llm(provider=provider, model=model, temperature=0.1)


def get_reasoning_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """Get LLM optimized for execution reasoning (slightly higher temperature)."""
    return get_llm(provider=provider, model=model, temperature=0.3)


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


def _build_xai(model: str, temperature: float) -> BaseChatModel:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key or api_key.startswith("xai-your_key"):
        raise LLMConfigError(
            "XAI_API_KEY is not set. Get a free key at https://console.x.ai/ "
            "and add it to your .env file."
        )
    from langchain_xai import ChatXAI
    return ChatXAI(model=model, temperature=temperature, xai_api_key=api_key)


def _build_gemini(model: str, temperature: float) -> BaseChatModel:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.startswith("AIza-your_key"):
        raise LLMConfigError(
            "GOOGLE_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey "
            "and add it to your .env file."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=api_key)

