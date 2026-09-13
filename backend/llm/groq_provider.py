"""
backend/llm/groq_provider.py
==============================
Groq LLM provider — talks to Groq's cloud API.

WHY GROQ?
    Groq runs LLMs on custom LPU (Language Processing Unit) hardware.
    Their API is extremely fast — often sub-second responses.
    It's free-tier friendly for learning, and the API format is
    OpenAI-compatible, meaning the request/response structure is
    nearly identical to what we'd send to OpenAI, llama-server,
    or any other compatible provider.

THIS PROVES THE ABSTRACTION LAYER WORKS:
    We're adding a second provider without changing:
        - chat.py (router)
        - llm_service.py (service)
        - main.py (app)
    Only THREE things change:
        1. This new file (groq_provider.py)
        2. factory.py (one new elif)
        3. .env (switch LLM_PROVIDER=groq)
    That's the power of the abstraction.

THE REQUEST:
    POST https://api.groq.com/openai/v1/chat/completions
    Authorization: Bearer <GROQ_API_KEY>
    {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are ProjectMind AI..."},
            {"role": "user", "content": "What is an API?"}
        ],
        "temperature": 0.7
    }

    Same format as llama-server. Same format as OpenAI.
    The only differences are: the URL, the API key, and the model name.
"""

import httpx
from backend.llm.base import BaseLLMProvider
from backend.config import settings


class GroqProvider(BaseLLMProvider):
    """
    LLM provider for Groq's cloud API.

    Groq hosts models like LLaMA 3.3, Mixtral, Gemma on their
    custom LPU hardware. The API is OpenAI-compatible.
    """

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.llm_timeout

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file."
            )

        # Groq's OpenAI-compatible endpoint
        self.chat_url = "https://api.groq.com/openai/v1/chat/completions"

    async def chat(self, message: str) -> str:
        """
        Send a message to Groq and return the response.

        The request format is identical to llama-server (OpenAI format).
        The only additions are:
            - The URL points to Groq's cloud instead of localhost
            - We include an Authorization header with the API key

        Why Authorization header?
            llama-server runs locally — no auth needed, it's your machine.
            Groq is a remote service — they need to verify who you are
            and track your usage. The Bearer token does that.
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

        # Same response format as llama-server (OpenAI-compatible)
        choices = data.get("choices")
        if not choices:
            raise ValueError(
                f"Groq response has no 'choices'. Raw response: {data}"
            )

        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise ValueError(
                f"Groq response has no 'content'. Raw response: {data}"
            )

        return content


# ============================================================
# Quick standalone test
# ============================================================
# Run: python -m backend.llm.groq_provider
# ============================================================
if __name__ == "__main__":
    import asyncio

    async def test():
        try:
            provider = GroqProvider()
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
            print("ERROR: Cannot connect to Groq API. Check your internet.")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

    asyncio.run(test())
