"""
backend/llm/factory.py
=======================
Factory that creates the correct LLM provider based on configuration.

Supports:
  1. Resilient Routing (Phase 21): Returns ResilientLLMProvider with automatic failover.
  2. Tier-to-Model Specialization (Phase 22): Resolves providers based on task tiers
     (FAST, BALANCED, COMPLEX, LOCAL) or specific tasks (coding, review, routing).
  3. Concrete Provider Selection: Specific concrete instance (Groq, Gemini, Nemotron).
"""

from typing import Optional
from backend.config import settings
from backend.llm.base import BaseLLMProvider


def get_llm_provider(
    provider_name: Optional[str] = None,
    resilient: bool = True,
    model: Optional[str] = None,
) -> BaseLLMProvider:
    """
    Return an LLM provider instance.

    Args:
        provider_name: Optional explicit provider name ('nemotron', 'groq', 'gemini')
                       or tier name ('fast', 'balanced', 'complex', 'local').
        resilient: If True and provider_name is None, returns the ResilientLLMProvider
                   with automatic failover and health probing.
        model: Optional model name override.

    Returns:
        An instance of BaseLLMProvider.
    """
    if resilient and provider_name is None:
        from backend.llm.router import default_llm_router
        return default_llm_router

    name = (provider_name or settings.llm_provider).lower()

    # Phase 22: Allow requesting by tier name (fast, balanced, complex, local)
    from backend.llm.model_registry import ModelTier, model_registry
    if name in [t.value for t in ModelTier]:
        return model_registry.get_provider_for_tier(name, resilient=resilient)

    if name == "nemotron":
        from backend.llm.nemotron import NemotronProvider
        return NemotronProvider(model=model)

    elif name == "groq":
        from backend.llm.groq_provider import GroqProvider
        return GroqProvider(model=model)

    elif name == "gemini":
        from backend.llm.gemini_provider import GeminiProvider
        return GeminiProvider(model=model)

    raise ValueError(
        f"Unknown LLM provider or tier: '{name}'. "
        f"Supported providers: nemotron, groq, gemini. "
        f"Supported tiers: fast, balanced, complex, local."
    )


def get_tier_provider(
    tier_or_task: str,
    resilient: bool = True,
) -> BaseLLMProvider:
    """
    Convenience factory to obtain an LLM provider tuned for a specific tier or task.

    Examples:
        get_tier_provider("fast")     # Returns provider configured for FAST tier
        get_tier_provider("coding")   # Resolves task 'coding' -> COMPLEX tier provider
        get_tier_provider("review")   # Resolves task 'review' -> BALANCED tier provider
    """
    from backend.llm.model_registry import model_registry
    return model_registry.get_provider_for_task(tier_or_task, resilient=resilient)
