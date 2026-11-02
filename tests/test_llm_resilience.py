"""
tests/test_llm_resilience.py
=============================
Automated unit tests for Phase 21: LLM Abstraction Layer & Resilient Router.
Tests automatic failover, health probing, dynamic provider switching,
and all-down error reporting with isolated mock providers.
"""

import unittest

from backend.llm.base import BaseLLMProvider
from backend.llm.router import ResilientLLMProvider


def run_async(coro):
    """
    Drive a non-blocking coroutine to completion safely without requiring
    an external network socket on Windows sandboxes.
    """
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for simulating online, offline, and rate-limited behavior."""

    def __init__(self, name: str, should_fail: bool = False, fail_type: str = "connection", response: str = "Mock response"):
        self.name = name
        self.should_fail = should_fail
        self.fail_type = fail_type
        self.response = response
        self.call_count = 0

    async def chat(self, message: str, system_instruction: str | None = None) -> str:
        self.call_count += 1
        if self.should_fail:
            if self.fail_type == "connection":
                raise ConnectionError(f"Mock server {self.name} is down")
            elif self.fail_type == "timeout":
                raise TimeoutError(f"Mock server {self.name} timed out")
            else:
                raise RuntimeError(f"Mock error on {self.name}")
        return f"[{self.name}] {self.response}"

    def chat_sync(self, message: str, system_instruction: str | None = None) -> str:
        return run_async(self.chat(message, system_instruction))

    async def health_check(self) -> dict:
        if self.should_fail:
            return {"provider": self.name, "status": "offline", "error": f"{self.name} is down"}
        return {"provider": self.name, "status": "online", "model": f"mock-{self.name}", "latency_ms": 12.5}


class TestLLMResilience(unittest.TestCase):
    """Test suite for ResilientLLMProvider failover logic."""

    def setUp(self):
        self.router = ResilientLLMProvider(
            active_provider="nemotron",
            fallback_chain=["nemotron", "groq", "gemini"],
        )
        self.mock_nemotron = MockProvider("nemotron")
        self.mock_groq = MockProvider("groq")
        self.mock_gemini = MockProvider("gemini")
        self.router._provider_instances = {
            "nemotron": self.mock_nemotron,
            "groq": self.mock_groq,
            "gemini": self.mock_gemini,
        }

    def test_default_config(self):
        """Router must initialize with active provider and fallback chain."""
        config = self.router.get_config()
        self.assertEqual(config["active_provider"], "nemotron")
        self.assertEqual(config["fallback_chain"], ["nemotron", "groq", "gemini"])
        self.assertIn("groq", config["supported_providers"])

    def test_dynamic_active_provider_switching(self):
        """Switching active provider must move it to the front of the fallback chain."""
        self.router.set_active_provider("gemini")
        config = self.router.get_config()
        self.assertEqual(config["active_provider"], "gemini")
        self.assertEqual(config["fallback_chain"][0], "gemini")

    def test_invalid_provider_rejected(self):
        """Setting unknown provider must raise ValueError."""
        with self.assertRaises(ValueError):
            self.router.set_active_provider("non_existent_llm")

        with self.assertRaises(ValueError):
            self.router.set_fallback_chain(["groq", "fake_model"])

    def test_successful_primary_call(self):
        """When primary provider is healthy, it answers without invoking fallbacks."""
        self.mock_nemotron.response = "Nemotron answer"

        response = run_async(self.router.chat("Hello"))
        self.assertIn("[nemotron]", response)
        self.assertEqual(self.mock_nemotron.call_count, 1)

        meta = self.router.last_execution_meta
        self.assertEqual(meta["provider_used"], "nemotron")
        self.assertEqual(len(meta["fallbacks_attempted"]), 0)

    def test_automatic_failover_recovery(self):
        """When primary provider is down, router must automatically failover to secondary provider."""
        # Nemotron is down
        self.mock_nemotron.should_fail = True
        self.mock_nemotron.fail_type = "connection"

        # Groq is healthy
        self.mock_groq.response = "Groq answer"

        response = run_async(self.router.chat("Hello"))
        self.assertIn("[groq]", response)
        self.assertEqual(self.mock_nemotron.call_count, 1)
        self.assertEqual(self.mock_groq.call_count, 1)

        meta = self.router.last_execution_meta
        self.assertEqual(meta["provider_used"], "groq")
        self.assertEqual(len(meta["fallbacks_attempted"]), 1)
        self.assertEqual(meta["fallbacks_attempted"][0]["provider"], "nemotron")

    def test_all_providers_fail_raises_runtime_error(self):
        """When all providers in chain fail, router must raise RuntimeError with full trace."""
        self.mock_nemotron.should_fail = True
        self.mock_groq.should_fail = True
        self.mock_gemini.should_fail = True

        with self.assertRaises(RuntimeError) as ctx:
            run_async(self.router.chat("Hello"))

        err_msg = str(ctx.exception)
        self.assertIn("All LLM providers in fallback chain failed", err_msg)
        self.assertIn("nemotron", err_msg)
        self.assertIn("groq", err_msg)
        self.assertIn("gemini", err_msg)

    def test_health_check_probes(self):
        """check_health must report status for all supported providers."""
        self.mock_nemotron.should_fail = True

        health = run_async(self.router.check_health())
        self.assertIn("providers", health)
        self.assertEqual(health["providers"]["nemotron"]["status"], "offline")
        self.assertEqual(health["providers"]["groq"]["status"], "online")
        self.assertEqual(health["providers"]["gemini"]["status"], "online")

    def test_chat_sync_wrapper(self):
        """chat_sync must bridge synchronously to the router."""
        self.mock_nemotron.response = "Sync test"

        result = self.router.chat_sync("Hello sync")
        self.assertIn("Sync test", result)


if __name__ == "__main__":
    unittest.main()
