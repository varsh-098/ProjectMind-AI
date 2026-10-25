"""
backend/services/llm_service.py
================================
Service layer — the BUSINESS LOGIC for talking to the LLM.

WHY A SERVICE LAYER?
    The router (chat.py) handles HTTP concerns:
        - Parse the request body
        - Validate input
        - Return the right HTTP status code

    The service handles BUSINESS LOGIC:
        - Get the right LLM provider
        - Call it
        - Handle LLM-specific errors
        - Later: add memory context, RAG results, etc.

    Separation of concerns. If you put everything in the router,
    it becomes a huge messy function that handles HTTP + business
    logic + LLM calls + error handling all at once.

    With this separation:
        chat.py    → "What comes in and goes out over HTTP"
        llm_service.py → "What do we actually DO with the request"

FUTURE GROWTH:
    Right now this is simple — it just calls the LLM.
    Later, this is where we'll add:
        1. RAG retrieval → inject project context into the prompt
        2. Memory lookup → add remembered facts to the prompt
        3. Agent selection → route to the right agent
        4. Conversation history → maintain multi-turn context

    The router stays the same. Only this service grows.
"""

import httpx
from backend.llm.factory import get_llm_provider


async def get_chat_response(message: str) -> str:
    """
    Process a chat message and return the LLM's response.

    Currently: just calls the LLM directly.
    Future: will add RAG context, memory, agent routing.

    Args:
        message: The user's input message.

    Returns:
        The LLM's generated response text.

    Raises:
        ConnectionError: If the LLM server is not reachable.
        TimeoutError: If the LLM takes too long to respond.
        RuntimeError: For any other LLM-related errors.
    """
    # Get the configured provider (Nemotron for now).
    # The factory reads from settings — we don't know or care
    # which concrete provider this returns.
    provider = get_llm_provider()

    try:
        response = await provider.chat(message)
        return response

    except httpx.ConnectError:
        # llama-server is not running or unreachable.
        # We translate this into a domain-specific error message
        # so the router doesn't need to know about httpx.
        raise ConnectionError(
            "Cannot connect to the LLM server. "
            "Make sure llama-server is running."
        )

    except httpx.TimeoutException:
        raise TimeoutError(
            "The LLM took too long to respond. "
            "The model might be processing a complex request, "
            "or the server might be overloaded."
        )

    except Exception as e:
        # Catch-all for unexpected errors.
        # We log the real error but give a clean message upstream.
        raise RuntimeError(
            f"LLM error: {type(e).__name__}: {e}"
        )
