"""
backend/llm/nemotron.py
========================
Nemotron LLM provider — talks to your local llama-server.

THE FULL FLOW:
    1. You start llama-server on your laptop, loading the Nemotron model
    2. llama-server listens on http://localhost:8080
    3. llama-server exposes an OpenAI-compatible API
    4. This file sends HTTP POST requests to that API
    5. llama-server feeds the message to Nemotron (running on your GPU)
    6. Nemotron generates a response
    7. llama-server sends it back as JSON
    8. This file extracts the text and returns it

WHY OPENAI-COMPATIBLE FORMAT?
    llama-server deliberately mimics the OpenAI API format.
    This means the request and response structure looks exactly
    like what you'd send to OpenAI's API.

    Benefits:
    - When we later add GPT-6 Astra, the request format is nearly identical
    - Tools, libraries, and SDKs built for OpenAI also work with llama-server
    - You learn one API format and it transfers everywhere

THE REQUEST FORMAT (OpenAI chat completions):
    POST /v1/chat/completions
    {
        "model": "nemotron",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is an API?"}
        ],
        "temperature": 0.7
    }

    "messages" is a list of conversation turns.
    Each message has a "role":
        - "system": Instructions for the model (personality, rules)
        - "user": What the human said
        - "assistant": What the model previously said (for multi-turn conversations)

    "temperature" controls randomness:
        - 0.0 = deterministic, always picks the most likely word
        - 1.0 = more creative, picks less likely words sometimes
        - 0.7 = a good balance for general conversation

THE RESPONSE FORMAT:
    {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "An API is..."
                }
            }
        ]
    }

    We extract: response["choices"][0]["message"]["content"]
"""

import httpx
from typing import Optional
from backend.llm.base import BaseLLMProvider
from backend.config import settings


class NemotronProvider(BaseLLMProvider):
    """
    LLM provider for local Nemotron via llama-server.

    Uses httpx (async HTTP client) to call the OpenAI-compatible
    endpoint that llama-server exposes.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize the provider with settings from config or explicit overrides.
        """
        raw_url = base_url or settings.nemotron_base_url
        self.base_url = raw_url.rstrip("/")
        self.model = model or settings.nemotron_model
        self.timeout = timeout if timeout is not None else settings.llm_timeout

        # The endpoint llama-server exposes for chat completions.
        # This is the same path OpenAI uses.
        self.chat_url = f"{self.base_url}/v1/chat/completions"

    async def chat(
        self,
        message: str,
        system_instruction: str | None = None,
    ) -> str:
        """
        Send a message to Nemotron via llama-server and return the response.
        """
        sys_prompt = system_instruction or (
            "You are ProjectMind AI, a helpful and knowledgeable "
            "AI development assistant. Provide clear, concise, "
            "and accurate responses."
        )

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": sys_prompt,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            "temperature": 0.7,
        }

        # -------------------------------------------------------
        # Send the request
        # -------------------------------------------------------
        # async with httpx.AsyncClient() creates a temporary HTTP client.
        #
        # Why `async with` and not just `httpx.post(...)`?
        #   `async with` ensures the connection is properly closed
        #   even if an error occurs. This is called a "context manager"
        #   — it handles setup and cleanup automatically.
        #
        # timeout: How long to wait for llama-server.
        #   Local inference on a 4B model can take 10-60 seconds
        #   depending on the input length and your GPU.
        # -------------------------------------------------------
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url=self.chat_url,
                json=request_body,
            )

            # raise_for_status() throws an exception if the status
            # code is 4xx or 5xx. Without this, httpx silently gives
            # you the error response body and you'd have to check
            # the status code manually.
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

        # -------------------------------------------------------
        # Extract the generated text
        # -------------------------------------------------------
        # OpenAI format: data["choices"][0]["message"]["content"]
        #
        # We use .get() with checks rather than direct indexing
        # so we get a clear error message instead of a cryptic
        # KeyError if the format is unexpected.
        # -------------------------------------------------------
        choices = data.get("choices")
        if not choices:
            raise ValueError(
                f"Nemotron response has no 'choices'. Raw response: {data}"
            )

        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise ValueError(
                f"Nemotron response has no 'content'. Raw response: {data}"
            )

        return content

    async def health_check(self) -> dict[str, Any]:
        """Probe llama-server endpoint to test if local model is online."""
        import time
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/health")
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                if res.status_code == 200:
                    return {
                        "provider": "nemotron",
                        "status": "online",
                        "model": self.model,
                        "base_url": self.base_url,
                        "latency_ms": latency_ms,
                    }
                return {
                    "provider": "nemotron",
                    "status": "offline",
                    "status_code": res.status_code,
                    "error": f"HTTP {res.status_code}",
                }
        except Exception as e:
            return {
                "provider": "nemotron",
                "status": "offline",
                "error": str(e),
                "base_url": self.base_url,
            }


# ============================================================
# Quick standalone test
# ============================================================
# Run this file directly to test: python -m backend.llm.nemotron
# Make sure llama-server is running first!
# ============================================================
if __name__ == "__main__":
    import asyncio

    async def test():
        provider = NemotronProvider()
        print(f"Connecting to: {provider.chat_url}")
        print(f"Model: {provider.model}")
        print("-" * 60)

        try:
            response = await provider.chat("Hello! What is an API? Explain briefly.")
            print("Nemotron response:")
            print(response)
        except httpx.ConnectError:
            print("ERROR: Cannot connect to llama-server.")
            print(f"Make sure llama-server is running at: {provider.base_url}")
            print("Start it with: llama-server -m <model_path> --port 8080")
        except httpx.TimeoutException:
            print(f"ERROR: Request timed out after {provider.timeout} seconds.")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")

    asyncio.run(test())
