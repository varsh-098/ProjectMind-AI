"""
backend/llm/factory.py
=======================
Factory that creates the correct LLM provider based on configuration.

WHAT IS A FACTORY?
    A factory is a function (or class) that creates objects for you.
    Instead of the rest of the app knowing HOW to create a NemotronProvider
    or a future KIEProvider, they just call get_llm_provider() and get
    back whatever provider is configured.

WHY USE A FACTORY?
    1. The router (chat.py) just says: provider = get_llm_provider()
       It never imports NemotronProvider directly.

    2. When we later add GPT-6 Astra via KIE, we:
       - Create backend/llm/kie.py  (new file)
       - Add one elif here           (one line)
       - Set LLM_PROVIDER=kie in .env (config change)
       That's it. Zero changes to chat.py, llm_service.py, or main.py.

    3. This is the Factory Pattern — one of the most common design patterns.
       Interviewers love asking about it.

INTERVIEW QUESTION:
    "What design patterns does ProjectMind use?"

Answer:
    "The LLM layer uses the Factory Pattern combined with the Strategy Pattern.
     The factory (factory.py) creates the right provider at runtime based on
     config. Each provider (nemotron.py, future kie.py) is a strategy —
     a different algorithm for the same interface (chat). The rest of the app
     is decoupled from which strategy is active."
"""

from backend.config import settings
from backend.llm.base import BaseLLMProvider


def get_llm_provider() -> BaseLLMProvider:
    """
    Return the configured LLM provider instance.

    Reads settings.llm_provider to decide which concrete class to create.
    Currently supports: "nemotron" (local llama-server).

    Returns:
        An instance of a class that implements BaseLLMProvider.

    Raises:
        ValueError: If the configured provider name is not recognized.
    """
    provider_name = settings.llm_provider.lower()

    if provider_name == "nemotron":
        # Import here (not at the top of the file) to avoid circular imports
        # and to only load the provider code when it's actually needed.
        from backend.llm.nemotron import NemotronProvider
        return NemotronProvider()

    elif provider_name == "groq":
        from backend.llm.groq_provider import GroqProvider
        return GroqProvider()

    # -----------------------------------------------------------
    # Future providers go here:
    #
    # elif provider_name == "kie":
    #     from backend.llm.kie import KIEProvider
    #     return KIEProvider()
    # -----------------------------------------------------------

    raise ValueError(
        f"Unknown LLM provider: '{provider_name}'. "
        f"Check LLM_PROVIDER in your .env file. "
        f"Supported providers: nemotron, groq"
    )
