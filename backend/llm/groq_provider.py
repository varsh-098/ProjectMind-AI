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
from typing import Optional
from backend.llm.base import BaseLLMProvider
from backend.config import settings


class GroqProvider(BaseLLMProvider):
    """
    LLM provider for Groq's cloud API.

    Groq hosts models like LLaMA 3.3, Mixtral, Gemma on their
    custom LPU hardware. The API is OpenAI-compatible.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.timeout = timeout if timeout is not None else settings.llm_timeout

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file."
            )

        # Groq's OpenAI-compatible endpoint
        self.chat_url = "https://api.groq.com/openai/v1/chat/completions"

    async def chat(
        self,
        message: str,
        system_instruction: str | None = None,
    ) -> str:
        """
        Send a message to Groq and return the response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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

        import asyncio
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(5):
                response = await client.post(
                    url=self.chat_url,
                    headers=headers,
                    json=request_body,
                )
                if response.status_code == 429 and attempt < 4:
                    retry_after = response.headers.get('retry-after')
                    wait_s = 2.0
                    if retry_after:
                        try:
                            wait_s = max(float(retry_after) + 0.5, 1.0)
                        except ValueError:
                            wait_s = 2.0 * (attempt + 1)
                    else:
                        wait_s = 2.0 * (attempt + 1)
                    await asyncio.sleep(wait_s)
                    continue
                response.raise_for_status()
                data = response.json()
                break

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

    def chat_sync(
        self,
        message: str,
        system_instruction: str | None = None,
    ) -> str:
        """Synchronous chat using httpx.Client."""
        sys_prompt = system_instruction or (
            "You are ProjectMind AI, an intelligent coding and research assistant. "
            "You help developers understand codebases, write clean code, and debug issues. "
            "You are direct, concise, and technically precise. Prefer clear code examples "
            "and accurate responses."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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

        import time
        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(5):
                response = client.post(
                    url=self.chat_url,
                    headers=headers,
                    json=request_body,
                )
                if response.status_code == 429 and attempt < 4:
                    retry_after = response.headers.get('retry-after')
                    wait_s = 2.0
                    if retry_after:
                        try:
                            wait_s = max(float(retry_after) + 0.5, 1.0)
                        except ValueError:
                            wait_s = 2.0 * (attempt + 1)
                    else:
                        wait_s = 2.0 * (attempt + 1)
                    time.sleep(wait_s)
                    continue
                response.raise_for_status()
                data = response.json()
                break

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

    async def health_check(self) -> dict:
        """Probe Groq API to verify key and network connectivity."""
        import time
        t0 = time.perf_counter()
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                if res.status_code == 200:
                    return {
                        "provider": "groq",
                        "status": "online",
                        "model": self.model,
                        "latency_ms": latency_ms,
                    }
                return {
                    "provider": "groq",
                    "status": "offline",
                    "status_code": res.status_code,
                    "error": f"HTTP {res.status_code}: {res.text[:100]}",
                }
        except Exception as e:
            return {
                "provider": "groq",
                "status": "offline",
                "error": str(e),
                "model": self.model,
            }


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
