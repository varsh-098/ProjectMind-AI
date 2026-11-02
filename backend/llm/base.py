"""
backend/llm/base.py
====================
Abstract base class for ALL LLM providers in ProjectMind AI.

Defines the contract:
  1. chat(message, system_instruction=None) -> str
  2. health_check() -> dict
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    Every concrete provider (Nemotron, Groq, Gemini) implements this interface.
    """

    @abstractmethod
    async def chat(
        self,
        message: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Send a message to the LLM and return the generated text.

        Args:
            message: The user's input text or prompt.
            system_instruction: Optional custom system instructions/persona.

        Returns:
            The LLM's generated response string.
        """
        pass

    async def health_check(self) -> Dict[str, Any]:
        """
        Probe provider availability and return status metadata.

        Returns:
            Dict containing status ('online' | 'offline'), latency_ms, model, and any error message.
        """
        return {"status": "unknown"}
