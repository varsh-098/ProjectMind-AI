"""
backend/llm/base.py
====================
Abstract base class for ALL LLM providers.

WHY THIS FILE EXISTS:
This defines the CONTRACT — the interface that every LLM provider
(Nemotron, Groq, Gemini, or anything else in the future) MUST follow.

Think of it like a job description:
    "Every LLM provider must be able to:
       1. Accept a message (string)
       2. Return a response (string)"

That's it. HOW each provider does it internally is their own business.
Nemotron calls llama-server. Groq calls Groq's cloud. Gemini calls
Google's API. But from the outside, the rest of our app sees the same interface.

INTERVIEW QUESTION:
    "Why use an abstract base class instead of just writing the
     Nemotron code directly?"

Answer:
    If we write Nemotron logic directly into the FastAPI route, then
    switching to GPT-6 Astra later means rewriting the route code.
    With an abstraction, the route calls `provider.chat(message)` —
    it doesn't care what provider it is. We swap the provider in
    ONE place (the factory), and everything else stays unchanged.
    This is the Open/Closed Principle: open for extension (adding
    new providers), closed for modification (existing code untouched).
"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Every concrete provider (NemotronProvider, GroqProvider, GeminiProvider, etc.)
    must inherit from this and implement the `chat` method.

    ABC = Abstract Base Class.
    @abstractmethod = "you MUST implement this method in subclasses,
                       or Python will raise TypeError when you try
                       to create an instance."
    """

    @abstractmethod
    async def chat(self, message: str) -> str:
        """
        Send a message to the LLM and return the generated text.

        Why async?
            FastAPI is asynchronous. When it handles a request,
            if we use a blocking (synchronous) HTTP call to the LLM,
            the ENTIRE server freezes until the LLM responds.
            No other user can be served during that time.

            With async, FastAPI says "start the LLM call, and while
            waiting for the response, go handle other requests."
            When the LLM responds, FastAPI picks up where it left off.

        Args:
            message: The user's input text.

        Returns:
            The LLM's generated response as a string.
        """
        pass
