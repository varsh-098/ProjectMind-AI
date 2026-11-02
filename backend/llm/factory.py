"""
backend/llm/factory.py
=======================
Factory that creates the correct LLM provider based on configuration.

Supports:
  1. Resilient Routing (Default in Phase 21): Returns ResilientLLMProvider
     with automatic failover chain across all providers.
  2. Concrete Provider Selection: Specific concrete instance (Groq, Gemini, Nemotron).
"""

from typing import Optional
from backend.config import settings
from backend.llm.base import BaseLLMProvider


def get_llm_provider(
    provider_name: Optional[str] = None,
    resilient: bool = True,
) -> BaseLLMProvider:
    """
    Return an LLM provider instance.

    Args:
        provider_name: Optional explicit provider name ('nemotron', 'groq', 'gemini').
        resilient: If True and provider_name is None, returns the ResilientLLMProvider
                   with automatic failover and health probing.

    Returns:
        An instance of BaseLLMProvider.
    """
    if resilient and provider_name is None:
        from backend.llm.router import default_llm_router
        return default_llm_router

    name = (provider_name or settings.llm_provider).lower()

    if name == "nemotron":
        from backend.llm.nemotron import NemotronProvider
        return NemotronProvider()

    elif name == "groq":
        from backend.llm.groq_provider import GroqProvider
        return GroqProvider()

    elif name == "gemini":
        from backend.llm.gemini_provider import GeminiProvider
        return GeminiProvider()

    raise ValueError(
        f"Unknown LLM provider: '{name}'. "
        f"Check LLM_PROVIDER in your .env file. "
        f"Supported providers: nemotron, groq, gemini"
    )
