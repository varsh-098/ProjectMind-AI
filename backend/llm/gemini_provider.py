"""
backend/llm/gemini_provider.py
===============================
Gemini LLM provider — talks to Google's Gemini API (Google AI Studio).

WHY GEMINI?
    Google's Gemini models (2.5 Flash, 2.5 Pro, etc.) are powerful,
    multi-modal LLMs available through Google AI Studio with a generous
    free tier. Perfect for learning and prototyping.

    Originally, the plan was to use GPT-6 Astra via KIE.ai for Phase 9.
    Since we don't have KIE access, we're using Gemini instead — the
    architecture is exactly the same. That's the entire point of
    the abstraction layer.

THE KEY INSIGHT — OPENAI-COMPATIBLE ENDPOINT:
    Google provides an OpenAI-compatible endpoint for Gemini:
        https://generativelanguage.googleapis.com/v1beta/openai/chat/completions

    This means we use the EXACT SAME request/response format as:
        - Nemotron (local llama-server)
        - Groq (cloud API)
        - OpenAI (if we added it)

    The only differences are:
        1. The URL (Google's endpoint instead of Groq's or localhost)
        2. The API key (Google AI Studio key instead of Groq key)
        3. The model name (gemini-2.5-flash instead of llama-3.3-70b)

    This PROVES the abstraction works. Three providers, three different
    companies, three different models — but the same interface.

THIS PROVES THE ABSTRACTION LAYER WORKS (AGAIN):
    We're adding a THIRD provider without changing:
        - chat.py (router)
        - llm_service.py (service)
        - main.py (app)
    Only THREE things change:
        1. This new file (gemini_provider.py)
        2. factory.py (one new elif)
        3. .env (switch LLM_PROVIDER=gemini)

THE REQUEST:
    POST https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
    Authorization: Bearer <GEMINI_API_KEY>
    {
        "model": "gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": "You are ProjectMind AI..."},
            {"role": "user", "content": "What is an API?"}
        ],
        "temperature": 0.7
    }

    Same format as llama-server. Same format as Groq. Same format as OpenAI.
    The ONLY differences are: the URL, the API key, and the model name.

HOW TO GET YOUR API KEY:
    1. Go to https://aistudio.google.com/
    2. Sign in with your Google account
    3. Click "Get API Key" → "Create API Key"
    4. Copy the key and add it to your .env file as GEMINI_API_KEY=...

INTERVIEW QUESTION:
    "You've now built three providers. What pattern is this?"

Answer:
    "This is the Strategy Pattern combined with Factory Pattern.
     Each provider (Nemotron, Groq, Gemini) is a strategy — a different
     implementation of the same interface (BaseLLMProvider.chat).
     The factory (factory.py) selects the right strategy at runtime
     based on configuration. Adding a new provider requires zero
     changes to existing business logic."
"""

import httpx
from backend.llm.base import BaseLLMProvider
from backend.config import settings


class GeminiProvider(BaseLLMProvider):
    """
    LLM provider for Google's Gemini API via Google AI Studio.

    Uses the OpenAI-compatible endpoint that Google provides,
    so the request/response format is identical to Groq and Nemotron.

    Supported models (as of 2025):
        - gemini-2.5-flash     (fast, great for most tasks)
        - gemini-2.5-pro       (more capable, slower)
        - gemini-2.0-flash     (previous gen, still solid)
    """

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = settings.llm_timeout

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Get your free API key at https://aistudio.google.com/ "
                "and add it to your .env file."
            )

        # Google's OpenAI-compatible endpoint for Gemini.
        # This endpoint accepts the same request format as OpenAI/Groq.
        # Why /v1beta? Google keeps newer features in beta.
        # The /openai/ path specifically enables OpenAI compatibility.
        self.chat_url = (
            "https://generativelanguage.googleapis.com"
            "/v1beta/openai/chat/completions"
        )

    async def chat(self, message: str) -> str:
        """
        Send a message to Gemini and return the response.

        The request format is IDENTICAL to Groq and Nemotron.
        Compare this method with groq_provider.py and nemotron.py —
        the only difference is the URL and the auth header.

        Why Authorization: Bearer?
            Same as Groq. Google AI Studio issues API keys, and
            the Bearer token format is the standard way to authenticate
            with cloud APIs. All three cloud providers (OpenAI, Groq,
            Google) use this exact same authentication pattern.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are ProjectMind AI, a helpful and knowledgeable "
                        "AI development assistant. Provide clear, concise, "
                        "and accurate responses."
                    ),
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url=self.chat_url,
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        # Same response format as Groq and Nemotron (OpenAI-compatible)
        # data["choices"][0]["message"]["content"]
        choices = data.get("choices")
        if not choices:
            raise ValueError(
                f"Gemini response has no 'choices'. Raw response: {data}"
            )

        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise ValueError(
                f"Gemini response has no 'content'. Raw response: {data}"
            )

        return content


# ============================================================
# Quick standalone test
# ============================================================
# Run: python -m backend.llm.gemini_provider
# ============================================================
if __name__ == "__main__":
    import asyncio

    async def test():
        try:
            provider = GeminiProvider()
        except ValueError as e:
            print(f"ERROR: {e}")
            return

        print(f"Model: {provider.model}")
        print(f"Endpoint: {provider.chat_url}")
        print("-" * 60)

        try:
            response = await provider.chat(
                "Hello! I am testing my ProjectMind AI application. "
                "Please introduce yourself briefly in 2-3 sentences."
            )
            print("Response:")
            print(response)
        except httpx.HTTPStatusError as e:
            print(f"ERROR: HTTP {e.response.status_code}")
            print(f"Details: {e.response.text}")
        except httpx.ConnectError:
            print("ERROR: Cannot connect to Gemini API. Check your internet.")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

    asyncio.run(test())
